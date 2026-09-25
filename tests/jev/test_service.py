"""End-to-end JevService tests over typed envelopes with the offline StubAdapter.

This module also owns the small typed builders shared by the other tests/jev
files: a real StatisticalState assembled by ``compute_statistical_state``, its
registered StateRecord, and a bounded E0 -> E1 revision produced through
``cancerjev.research.deep``. No network and no provider SDK is used.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from cancerjev.domain.codecs import state_identity, write_state
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.measurements import Acquisition, OperationalSource, ScientificSource
from cancerjev.domain.scientific import StatisticalState
from cancerjev.gdc.parsers import (
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    GeneRecord,
    ProjectCoverage,
    ProjectRecord,
    ProviderGene,
    ProviderSelection,
)
from cancerjev.jev.contracts import EvaluationRecord
from cancerjev.jev.projection import PROJECTION_VERSION, build_projection, projection_hash
from cancerjev.jev.questions import applicability_map
from cancerjev.jev.service import JevService, is_pinned_model_identity
from cancerjev.jev.typesafe_adapter import JevProviderError
from cancerjev.research import deep
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.science.methods import ProjectFrame, compute_statistical_state
from tests.jev.stub_adapter import StubAdapter

RELEASE = "Data Release 46.0"
COHORT = "TCGA-LUAD"
PROJECT = "TCGA-LUAD"
GENE = GeneRecord(gene_id="ENSG00000141510", symbol="TP53", name="tumor protein p53",
                  biotype="protein_coding", is_cancer_gene_census=True)
CANDIDATE_ID = "00000000-0000-0000-0000-000000000001"
_RESPONSE_ENDPOINTS = (
    ("/analysis/top_cases_counts_by_genes", "counts"),
    ("/analysis/mutated_cases_count_by_project", "coverage"),
    ("/gene_expression/values", "values"),
)

EVALUATION_FIELDS = (
    "evaluation_id", "mode", "purpose", "input_ref_kind", "input_ref_id", "source_state_hash",
    "projection_id", "projection_version", "projection_hash", "question_set_version", "question_hash",
    "question_definitions_ref", "requested_model", "resolved_model", "adapter_version", "answers",
    "applicability", "raw_answers_hash", "request_id", "usage", "latency_ms",
    "cache_source_evaluation_id", "error", "routing_policy_version", "artifact_id",
)


# ------------------------------------------------------------------ typed builders


def _frame(*, project_id: str = PROJECT, cases: int = 60, expression: bool = True,
           missing_expression_cells: int = 0, discovery: bool = True) -> ProjectFrame:
    case_records = [CaseRecord(f"{project_id}-case-{index:04d}", f"S-{index}", project_id,
                               ["Primary Tumor"]) for index in range(cases)]
    returned = cases - missing_expression_cells
    coverage = (
        ExpressionAvailability(
            cases={case.case_id: index < returned for index, case in enumerate(case_records)},
            genes={GENE.gene_id: expression}, with_count=cases, without_count=0,
            missing_cases=[], missing_genes=[], warnings=[],
        ) if expression or missing_expression_cells else None
    )
    values = (
        ExpressionValues(
            values={GENE.gene_id: {
                case.case_id: (5.0 + index * 0.1 if index < returned else None)
                for index, case in enumerate(case_records)
            }},
            missing_case_ids=[], missing_gene_ids=[], nonfinite_values=0, warnings=[],
        ) if expression else None
    )
    provider = (
        ProviderSelection(
            genes={GENE.gene_id: ProviderGene(GENE.gene_id, GENE.symbol, 2.5, 0.3)},
            missing_genes=[], warnings=[],
        ) if expression else None
    )
    hits = {GENE.gene_id: DiscoveryHit(GENE.gene_id, GENE.symbol, 1, 100.0)} if discovery else {}
    return ProjectFrame(
        project_id=project_id,
        project_record=ProjectRecord(project_id=project_id, name=project_id, program_name="TCGA",
                                     primary_site=["Lung"], disease_type=["Adenocarcinoma"],
                                     case_count=cases, file_count=100,
                                     data_categories=["Transcriptome Profiling"]),
        cases=case_records, frame_hash=hashlib.sha256(project_id.encode()).hexdigest(),
        expression_coverage=coverage, provider_selection=provider, expression_values=values,
        workflows=["STAR - Counts"], strategies=["RNA-Seq"], discovery_hits=hits,
    )


def _sources(*, artifacts_by_endpoint: dict | None = None) -> tuple[OperationalSource, ...]:
    mapping = artifacts_by_endpoint or {}
    result: list[OperationalSource] = []
    for index, (endpoint, label) in enumerate(_RESPONSE_ENDPOINTS):
        published = mapping.get(endpoint)
        response_hash = (published.sha256 if published is not None
                         else hashlib.sha256(label.encode()).hexdigest())
        artifact_id = published.artifact_id if published is not None else f"response-artifact-{index}"
        result.append(OperationalSource(
            ScientificSource(
                endpoint=endpoint,
                request_hash=hashlib.sha256(f"request:{label}".encode()).hexdigest(),
                response_hash=response_hash, parser_version="gdc-parser-v1", release=RELEASE,
                acquisition=Acquisition.COMPLETE,
            ),
            attempt_id=f"attempt-{index}", artifact_id=artifact_id,
            retrieved_at="2026-09-22T00:00:00Z", bytes_read=128, latency_ms=1, http_status=200,
            cache_hit=False,
        ))
    return tuple(result)


def statistical_state(*, projects: tuple[str, ...] = (PROJECT,), counts: dict | None = None,
                      acquisition_complete: bool = True, expression: bool = True,
                      missing_expression_cells: int = 0, discovery: bool = True,
                      artifacts_by_endpoint: dict | None = None,
                      selection=None) -> StatisticalState:
    """Assemble one real typed state through the admitted deterministic methods."""
    frames = [
        _frame(project_id=project, expression=expression,
               missing_expression_cells=missing_expression_cells, discovery=discovery)
        for project in projects
    ]
    if counts is None:
        counts = {project: {GENE.gene_id: 10} for project in projects}
    coverage = {project: 60 for project in projects}
    selection_hash = (selection.sha256 if selection is not None
                      else hashlib.sha256(b"selected-gene-ids").hexdigest())
    return compute_statistical_state(
        gene=GENE, frames=frames,
        counts=GeneCaseCounts(
            projects=counts, hits_total=100, complete=acquisition_complete,
            partial_reasons=["simulated partial aggregation"] if not acquisition_complete else [],
            warnings=[],
        ),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=True, partial_reasons=[], warnings=[]),
        sources=_sources(artifacts_by_endpoint=artifacts_by_endpoint),
        warnings=[],
        scope_meta={
            "spec_id": "LUAD_RESEARCH_V1", "domain": "lung cancer", "cohort": COHORT,
            "project_id": PROJECT, "cohort_selection_rule": "SINGLE_COHORT",
            "gene_selection_rule": "PROVIDER_RANK", "examined_case_frame": "ALL_CASES_PAGINATED",
            "gdc_release": RELEASE,
            "research_spec": {"acquisition": {
                "case_page_size": 100, "case_batch_size": 100, "max_cohort_cases": 1000,
                "discovery_gene_limit": 20, "count_gene_limit": 20, "candidate_gene_limit": 1,
                "expression_file_sample_size": 3,
            }},
        },
        discovery_meta={
            "selected_gene_ids": (GENE.gene_id,), "ranking_rule": "PROVIDER_RANK_ASC",
            "examined_genes_hash": selection_hash, "examined_genes_n": 1, "rank_in_lane": 1,
            "observed_in_project_count": 1,
            "examined_genes_ref": selection.artifact_id if selection is not None else None,
        },
    )


def state_record(state_id: str, state: StatisticalState | None = None) -> StateRecord:
    state = state if state is not None else statistical_state()
    return StateRecord(state_id, state_identity(state), state)


def register_state(repository, artifacts, run_id: str, record: StateRecord) -> None:
    artifact = artifacts.publish(f"runs/{run_id}/statistical_states/{record.state_id}.json",
                                 write_state(record.state), "application/json", "statistical-state")
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key=f"state:{record.state_id}",
        message="test state", stage="STATE_GENERATION",
        data={"state_id": record.state_id, "state_hash": record.state_hash},
        registrations=[
            repository.artifact_registration(artifact, run_id),
            repository.state_registration(
                state_id=record.state_id, run_id=run_id, state_hash=record.state_hash,
                artifact_id=artifact.artifact_id, disposition="GENERATED",
                summary_json=canonical_json({
                    "entity": {"gene_id": record.state.entity.gene_id,
                               "gene_symbol": record.state.entity.symbol},
                }).decode(),
                created_at=utc_now(),
            ),
        ],
    )


def _emit(repository):
    def emit(run_id_arg, event_type, key, message, **kwargs):
        return repository.append_event(run_id_arg, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)
    return emit


def service_context(runtime, adapter, *, state_id: str = "state-1") -> tuple[JevService, dict]:
    settings, repository, artifacts = runtime
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("jev-test", mode="LIVE", fixture_id=None, fixture_version=None)
    record = state_record(state_id)
    register_state(repository, artifacts, run_id, record)
    return service, {
        "run_id": run_id, "repository": repository, "artifacts": artifacts,
        "emit": _emit(repository), "state": record, "adapter": adapter,
    }


def _publish_responses(artifacts, repository, run_id: str):
    mapping = {}
    for endpoint, label in _RESPONSE_ENDPOINTS:
        artifact = artifacts.publish(f"runs/{run_id}/responses/{label}.json",
                                     canonical_json({"synthetic": label}), "application/json",
                                     "gdc-response")
        repository.register_artifact(artifact, run_id)
        mapping[endpoint] = artifact
    selection = artifacts.publish(f"runs/{run_id}/selection.json",
                                  canonical_json({"selected_gene_ids": [GENE.gene_id]}),
                                  "application/json", "gene-selection")
    repository.register_artifact(selection, run_id)
    return mapping, selection


def deep_context(runtime, adapter, *, state_id: str = "deep-state-1") -> dict:
    """Register a real state + candidate and produce one immutable E1 revision."""
    settings, repository, artifacts = runtime
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("jev-deep", mode="LIVE", fixture_id=None, fixture_version=None)
    mapping, selection = _publish_responses(artifacts, repository, run_id)
    record = state_record(state_id, statistical_state(artifacts_by_endpoint=mapping,
                                                      selection=selection))
    register_state(repository, artifacts, run_id, record)
    repository.append_event(
        run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="candidate:1",
        message="test candidate", stage="JEV_WIDE", data={"candidate_id": CANDIDATE_ID},
        registrations=[repository.candidate_registration(
            candidate_id=CANDIDATE_ID, run_id=run_id, promotion_slot=1, status="WIDE_EVALUATED",
            current_stage=None, source_state_id=record.state_id,
            entity_json=canonical_json({"gene_id": GENE.gene_id, "gene_symbol": GENE.symbol}).decode(),
            summary_json=canonical_json({}).decode(),
            created_at=utc_now(), updated_at=utc_now(),
        )],
    )
    emit = _emit(repository)

    def publish_json(pub_run_id, relative_path, payload, purpose):
        return artifacts.publish(relative_path, payload, "application/json", purpose)

    def read_artifact(artifact_id):
        metadata = repository.artifact(artifact_id)
        return artifacts.read(metadata["relative_path"]) if metadata else None

    candidate = repository.get_candidate(CANDIDATE_ID)
    plan = deep.plan_deep_slice(run_id=run_id, candidate=candidate, repository=repository,
                                artifacts=artifacts, emit=emit, publish_json=publish_json)
    result = deep.execute_followup(run_id=run_id, plan=plan, repository=repository, emit=emit,
                                   publish_json=publish_json, read_artifact=read_artifact)
    return {
        "service": service, "repository": repository, "artifacts": artifacts, "run_id": run_id,
        "emit": emit, "state": record, "candidate": candidate,
        "candidate_evidence": deep.load_candidate_evidence(repository, artifacts, candidate),
        "plan": plan, "result": result,
        "evidence": result.revision, "read_artifact": read_artifact, "adapter": adapter,
    }


# ------------------------------------------------------------------ wide service


def test_evaluate_record_persists_projection_evaluation_and_events(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    record = context["state"]
    evaluation = service.evaluate_record(run_id=context["run_id"], state=record,
                                         emit=context["emit"])
    assert isinstance(evaluation, EvaluationRecord)
    vector = evaluation.boundary_representation()
    assert vector["error"] is None
    assert vector["resolved_model"] == "jev-1.13.0"
    assert vector["requested_model"] == "jev-1.13.0"
    assert vector["projection_hash"] == projection_hash(build_projection(record))
    assert vector["answers"]["dominant_limitation"]["choice"] == "NONE"
    assert vector["usage"] == {"input_tokens": 1200, "output_tokens": 60}
    assert vector["latency_ms"] == 250
    assert vector["cache_source_evaluation_id"] is None
    assert vector["question_set_version"] == "wide-v3"
    assert adapter.calls == 1

    repository = context["repository"]
    row = repository.get_evaluation(evaluation.evaluation_id)
    assert row is not None and row["model"] == "jev-1.13.0"
    assert row["vector"]["applicability"]["warrants_deeper_investigation"]["applicable"] is True
    projections = repository.page_projections(context["run_id"], 10, None)
    assert len(projections["items"]) == 1
    events = [event["type"] for event in repository.events(context["run_id"], 0, 100)["items"]]
    assert "JEV_PROJECTION_CREATED" in events
    assert "JEV_WIDE_STATE_EVALUATED" in events


def test_cache_hit_reuses_judgment_without_provider_call(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    first = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                    emit=context["emit"])
    second = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                     emit=context["emit"])
    assert adapter.calls == 1
    assert second.cache_source_evaluation_id == first.evaluation_id
    assert second.boundary_representation()["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert second.boundary_representation()["latency_ms"] == 0
    assert second.answers == first.answers
    assert second.evaluation_id != first.evaluation_id
    repository = context["repository"]
    events = repository.events(context["run_id"], 0, 100)["items"]
    evaluated = [event for event in events if event["type"] == "JEV_WIDE_STATE_EVALUATED"]
    assert evaluated[-1]["data"]["cache"] is True
    assert evaluated[-1]["data"]["provider_attempted"] is False
    run = repository.get_run(context["run_id"])
    assert run["provider_usage"]["jev_calls"] == 1, "a cache hit must not count as a provider call"


def test_cache_is_shared_across_runs_but_not_across_models(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    service.evaluate_record(run_id=context["run_id"], state=context["state"], emit=context["emit"])
    second_run = context["repository"].create_run("jev-test-2", mode="LIVE", fixture_id=None,
                                                  fixture_version=None)
    reused = service.evaluate_record(run_id=second_run, state=context["state"],
                                     emit=context["emit"])
    assert reused.cache_source_evaluation_id is not None
    assert adapter.calls == 1

    settings, repository, artifacts = runtime
    other = StubAdapter(model="jev-1.12.0")
    other_settings = dataclasses.replace(settings, jev_model="jev-1.12.0")
    other_service = JevService(other_settings, repository, artifacts, adapter_factory=lambda: other)
    fresh = other_service.evaluate_record(run_id=second_run, state=context["state"],
                                          emit=context["emit"])
    assert fresh.cache_source_evaluation_id is None
    assert other.calls == 1


class _MalformedAdapter:
    model = "jev-1.13.0"

    def evaluate(self, state, definitions):
        raise JevProviderError(
            "PROVIDER_RESPONSE_MALFORMED",
            "provider response could not be converted to owned answers",
        )


def _invalid_probability_adapter():
    return StubAdapter(override={
        "warrants_deeper_investigation": {"kind": "noul", "probability_yes": 1.5},
    })


@pytest.mark.parametrize(("make_adapter", "code"), [
    (_MalformedAdapter, "PROVIDER_RESPONSE_MALFORMED"),
    (lambda: StubAdapter(fail=True), "PROVIDER_ERROR"),
    (_invalid_probability_adapter, "INVALID_PROBABILITY"),
])
def test_provider_failures_persist_typed_abstentions(runtime, make_adapter, code):
    service, context = service_context(runtime, make_adapter())
    evaluation = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                         emit=context["emit"])
    assert evaluation.error_code == code
    assert evaluation.answers is None
    assert evaluation.boundary_representation()["answers"] == {}
    repository = context["repository"]
    stored = repository.get_evaluation(evaluation.evaluation_id)
    assert stored is not None, "a provider failure must still persist a failed evaluation"
    assert stored["vector"]["error"]["code"] == code
    events = [event["type"] for event in repository.events(context["run_id"], 0, 100)["items"]]
    assert "JEV_EVALUATION_FAILED" in events
    assert "JEV_WIDE_STATE_EVALUATED" not in events
    assert repository.get_run(context["run_id"])["status"] != "FAILED", \
        "one bad state must not abort the run"
    with repository.database.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jev_cache").fetchone()[0] == 0


def test_projection_is_registered_once_per_state_and_version(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    service.evaluate_record(run_id=context["run_id"], state=context["state"], emit=context["emit"])
    service.evaluate_record(run_id=context["run_id"], state=context["state"], emit=context["emit"])
    projections = context["repository"].page_projections(context["run_id"], 10, None)
    assert len(projections["items"]) == 1
    assert projections["items"][0]["projection_version"] == PROJECTION_VERSION


def test_evaluation_persistence_contract_and_idempotency(runtime):
    fail_service, fail_context = service_context(runtime, StubAdapter(fail=True),
                                                 state_id="state-fail")
    failed = fail_service.evaluate_record(run_id=fail_context["run_id"],
                                          state=fail_context["state"], emit=fail_context["emit"])
    failed_vector = failed.boundary_representation()
    assert set(failed_vector) == set(EVALUATION_FIELDS) | {"artifact_id"}
    fail_events = [event for event in
                   fail_context["repository"].events(fail_context["run_id"], 0, 100)["items"]
                   if event["type"].startswith("JEV_")]
    assert [event["type"] for event in fail_events] == [
        "JEV_PROJECTION_CREATED", "JEV_EVALUATION_FAILED",
    ]
    assert fail_events[1]["idempotency_key"] == f"jev-wide:{failed_vector['evaluation_id']}:failed"

    service, context = service_context(runtime, StubAdapter(), state_id="state-ok")
    record = context["state"]
    evaluation = service.evaluate_record(run_id=context["run_id"], state=record,
                                         emit=context["emit"])
    vector = evaluation.boundary_representation()
    assert set(vector) == set(EVALUATION_FIELDS) | {"artifact_id"}
    assert vector["applicability"] == applicability_map(build_projection(record))
    repository = context["repository"]
    assert repository.get_evaluation(evaluation.evaluation_id)["vector"] == {
        key: value for key, value in vector.items() if key != "artifact_id"
    }
    events = repository.events(context["run_id"], 0, 100)["items"]
    jev_events = [event for event in events if event["type"].startswith("JEV_")]
    assert [event["type"] for event in jev_events] == [
        "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
    ]
    assert jev_events[0]["idempotency_key"] == f"projection:{vector['projection_id']}"
    assert jev_events[1]["idempotency_key"] == f"jev-wide:{vector['evaluation_id']}"
    assert jev_events[1]["data"]["applicability"] == vector["applicability"]
    assert jev_events[1]["data"]["judgment_vector"] == vector["answers"]


@pytest.mark.parametrize(
    ("model", "pinned"),
    [
        ("jev-1.13.0", True),
        ("gpt-4o-2024-08-06", True),
        ("jev-latest", False),
        ("openrouter/deepseek/flash", False),
    ],
)
def test_only_pinned_model_identities_are_cache_eligible(model, pinned):
    assert is_pinned_model_identity(model) is pinned


def test_mutable_model_alias_is_never_treated_as_a_resolved_identity(runtime):
    settings, repository, artifacts = runtime
    alias_settings = dataclasses.replace(settings, jev_model="jev-latest")
    adapter = StubAdapter(model="jev-latest")
    service = JevService(alias_settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("jev-alias", mode="LIVE", fixture_id=None, fixture_version=None)
    record = state_record("state-1")
    register_state(repository, artifacts, run_id, record)
    emit = _emit(repository)

    first = service.evaluate_record(run_id=run_id, state=record, emit=emit)
    second = service.evaluate_record(run_id=run_id, state=record, emit=emit)
    assert first.cache_source_evaluation_id is None
    assert second.cache_source_evaluation_id is None
    assert adapter.calls == 2, "a mutable alias must always be evaluated by the provider"
    with repository.database.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jev_cache").fetchone()[0] == 0


def test_divergent_provider_resolution_is_not_cached_under_the_requested_identity(runtime):
    settings, repository, artifacts = runtime
    adapter = StubAdapter(model="jev-1.13.0", resolved_model="jev-1.13.0-20260901")
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("jev-divergent", mode="LIVE", fixture_id=None,
                                   fixture_version=None)
    record = state_record("state-1")
    register_state(repository, artifacts, run_id, record)
    emit = _emit(repository)

    first = service.evaluate_record(run_id=run_id, state=record, emit=emit)
    assert first.boundary_representation()["requested_model"] == "jev-1.13.0"
    assert first.boundary_representation()["resolved_model"] == "jev-1.13.0-20260901"
    second = service.evaluate_record(run_id=run_id, state=record, emit=emit)
    assert second.cache_source_evaluation_id is None
    assert adapter.calls == 2, "a resolution that diverges from the pinned name must not be reused"


# --------------------------------------------------------- evidence and hypotheses


def test_evaluate_evidence_record_judges_the_immutable_revision(runtime):
    adapter = StubAdapter()
    context = deep_context(runtime, adapter)
    assert context["result"].status == "COMPLETED"
    evidence = context["evidence"]
    evaluation = context["service"].evaluate_evidence_record(
        run_id=context["run_id"], evidence=evidence,
        eligible_actions=[ACTION_REGISTRY["CHECK_REVISION_FAITHFULNESS_V1"].payload()],
        emit=context["emit"],
    )
    assert isinstance(evaluation, EvaluationRecord)
    assert evaluation.error_code is None
    assert evaluation.input_ref_id == evidence.evidence_state_id
    assert evaluation.answers.probability("revision_reliable") == 0.90
    vector = evaluation.boundary_representation()
    assert vector["purpose"] == "DEEP"
    assert vector["input_ref_kind"] == "EVIDENCE_STATE"
    assert vector["evidence_state_id"] == evidence.evidence_state_id
    assert vector["source_evidence_hash"] == evidence.evidence_hash
    assert vector["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert set(vector["answers"]) == {
        "revision_reliable", "evidence_sufficient_for_next_step", "next_step_warranted",
        "stopping_more_honest", "dominant_limitation",
    }
    assert adapter.calls == 1
    row = context["repository"].get_evaluation(evaluation.evaluation_id)
    assert row["purpose"] == "DEEP" and row["vector"]["error"] is None
    events = [event["type"] for event in
              context["repository"].events(context["run_id"], 0, 300)["items"]]
    assert "JEV_DEEP_EVIDENCE_JUDGED" in events
