"""Live replay integration: the real typed sweep over provider-shaped synthetic responses.

``ReplayTransport`` publishes real artifacts and returns provider-shaped bodies, so the
strict parsers, deterministic methods, schema-4 typed states, wide Jev admission and
bounded promotion exercised here are production code paths. Every scientific assertion
reads a typed artifact through the validated readers or the presentation API; no legacy
dictionary shape is assumed.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.domain.codecs import read_state, state_identity
from cancerjev.domain.measurements import OperationalSource, ScientificSource
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.gdc.endpoints import SSM_OCCURRENCE_FIELDS
from cancerjev.gdc.parsers import ResponseMeta, parse_expression_availability
from cancerjev.jev.service import JevService
from cancerjev.jev.typesafe_adapter import JevProviderError
from cancerjev.research.live import LiveOrchestrator, _merge_expression_availability
from cancerjev.research.specs import (
    LUAD_RESEARCH_V1,
    AcquisitionSpec,
    CohortSpec,
    ResearchSpec,
    ScientificLimits,
)
from cancerjev.research.wide import run_wide_evaluation
from cancerjev.storage.readers import read_state_record
from tests.integration.replay import GENES, ReplayTransport, availability_body
from tests.jev.stub_adapter import StubAdapter

GENE_ONE, GENE_TWO = GENES
LUAD_CASES = 100
LUAD_AFFECTED = {GENE_ONE: 20, GENE_TWO: 5}
LUAD_MEDIAN = {GENE_ONE: math.log2(5.5), GENE_TWO: math.log2(6.5)}
WIDE_ANSWERS = {
    "evidence_quality_adequate", "mutation_evidence_coherent", "expression_evidence_coherent",
    "signal_explained_by_coverage", "unresolved_uncertainty_material",
    "warrants_deeper_investigation", "dominant_limitation",
}
WIDE_PHASE_EVENTS = {
    "JEV_WIDE_STARTED", "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
    "JEV_EVALUATION_FAILED", "JEV_WIDE_STATE_CAP_ENFORCED", "WIDE_RANKING_COMPLETED",
    "CANDIDATE_PROMOTED", "JEV_WIDE_COMPLETED",
}
WIDE_EVENT_ORDER = [
    "JEV_WIDE_STARTED", "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
    "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED", "WIDE_RANKING_COMPLETED",
    "CANDIDATE_PROMOTED", "CANDIDATE_PROMOTED", "JEV_WIDE_COMPLETED",
]


# --------------------------------------------------------------------------- helpers


def _test_spec(project_id: str = "TCGA-LUAD", *, page_size: int = 200, batch_size: int = 200,
               max_cases: int = 600, occurrence_page_size: int | None = None) -> ResearchSpec:
    discovery = (LUAD_RESEARCH_V1.discovery if occurrence_page_size is None
                 else dataclasses.replace(LUAD_RESEARCH_V1.discovery,
                                          occurrence_scan_page_size=occurrence_page_size))
    return ResearchSpec(
        spec_id=f"TEST_{project_id}_V1",
        intent="bounded offline replay of one explicit cohort",
        cohort=CohortSpec(cohort_id=project_id, domain="test lung cancer", project_id=project_id),
        discovery=discovery,
        acquisition=AcquisitionSpec(
            case_page_size=page_size, case_batch_size=batch_size, max_cohort_cases=max_cases,
            discovery_gene_limit=2, count_gene_limit=2, candidate_gene_limit=2,
            expression_file_sample_size=3,
        ),
        limits=ScientificLimits(),
        allowed_actions=("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
    )


def _orchestrator(runtime, monkeypatch=None, *, jev_adapter=None, research_spec=None,
                  deep_selection=None, deep_selections=(), deep_action_id=None,
                  deep_followup_authorized=False, deep_hypotheses_requested=False,
                  llm_generator=None, **replay_options):
    settings, repository, artifacts = runtime
    if monkeypatch is not None:
        monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    holder: dict = {}

    def transport_factory(repo, artifact_store, budget, run_id, emit):
        transport = ReplayTransport(artifact_store, run_id, repository=repo, **replay_options)
        holder["transport"] = transport
        return transport

    jev_service = None
    if jev_adapter is not None:
        jev_service = JevService(settings, repository, artifacts,
                                 adapter_factory=lambda: jev_adapter)
    operator_flags = any((deep_selection, deep_selections, deep_action_id,
                          deep_followup_authorized, deep_hypotheses_requested))
    orchestrator = LiveOrchestrator(
        settings, repository, artifacts, lambda event: None, jev_service=jev_service,
        transport_factory=transport_factory, research_spec=research_spec or LUAD_RESEARCH_V1,
        deep_selection=deep_selection, deep_selections=tuple(deep_selections),
        deep_action_id=deep_action_id, deep_followup_authorized=deep_followup_authorized,
        deep_hypotheses_requested=deep_hypotheses_requested, llm_generator=llm_generator,
        execution_ownership=(ExecutionOwnership.RESEARCHER_RUN if operator_flags
                             else ExecutionOwnership.SYSTEM_AUTONOMOUS),
    )
    return orchestrator, holder, repository


def _api_client(runtime, monkeypatch) -> TestClient:
    settings = runtime[0]
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    return TestClient(create_app())


def _state_row(repository, run_id, gene_id):
    return next(row for row in repository.list_table("statistical_states", run_id)
                if row["summary"]["entity"]["gene_id"] == gene_id)


def _typed_state(runtime, repository, run_id, gene_id):
    row = _state_row(repository, run_id, gene_id)
    return row, read_state_record(repository, runtime[2], row["state_id"])


def _events(repository, run_id, limit=800):
    return repository.events(run_id, 0, limit)["items"]


def _wide_phase_events(repository, run_id):
    return [event["type"] for event in _events(repository, run_id)
            if event["type"] in WIDE_PHASE_EVENTS]


def _source_meta(endpoint: str, index: int) -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="GET", request_hash=f"request-{index}",
                        response_sha256=f"response-{index}", artifact_id=f"artifact-{index}",
                        retrieved_at="2026-01-01T00:00:00+00:00", source_release="TEST-RELEASE",
                        completeness="COMPLETE")


def _live_state_records(runtime, monkeypatch, **replay_options):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, **replay_options)
    run_id = orchestrator.run()
    records = [read_state_record(repository, runtime[2], row["state_id"]).record
               for row in repository.list_table("statistical_states", run_id)]
    return run_id, repository, records


def _wide_summary(repository, artifacts, run_id):
    rows = repository.list_table("jev_evaluations", run_id)
    ranking = {}
    for name in ("baseline_ranking.json", "jev_ranking.json"):
        artifact = next(item for item in repository.ranking_artifacts(run_id)
                        if item["relative_path"].endswith(name))
        payload = json.loads(artifacts.read(artifact["relative_path"]))
        entries = []
        for entry in payload["entries"]:
            dimensions = {key: value for key, value in entry["dimensions"].items()
                          if key != "cache_source_evaluation_id"}
            entries.append((entry["rank"], entry["state_hash"], entry["gene_symbol"], dimensions))
        ranking[name] = entries
    return {
        "evaluation_count": len(rows),
        "evaluated_hashes": sorted(row["vector"]["source_state_hash"] for row in rows),
        "candidate_count": len(repository.list_table("candidates", run_id)),
        "candidate_modes": sorted(row["summary"]["policy_version"]
                                  for row in repository.list_table("candidates", run_id)),
        "baseline": ranking["baseline_ranking.json"],
        "jev": ranking["jev_ranking.json"],
        "admitted": repository.get_run(run_id)["counts"]["candidates_promoted"],
    }


# ------------------------------------------------------------------ scope and identity


def test_alternate_research_spec_selects_only_its_project(runtime, monkeypatch):
    spec = _test_spec("TCGA-LUSC", page_size=80, batch_size=80, max_cases=100)
    orchestrator, holder, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["spec_id"] == spec.spec_id
    assert run["selected_project_ids"] == ["TCGA-LUSC"]
    assert run["project_id"] == "TCGA-LUSC"
    assert run["acquisition"]["case_page_size"] == 80

    states = repository.list_table("statistical_states", run_id)
    assert len(states) == 2
    for row in states:
        body = json.loads(runtime[2].read(repository.artifact(row["artifact_id"])["relative_path"]))
        assert body["research"]["projects"] == ["TCGA-LUSC"]
        assert body["research"]["spec_id"] == spec.spec_id
    scientific = [request for request in holder["transport"].requests
                  if request.endpoint.name != "status"]
    assert scientific
    project_scoped = {"projects", "top_mutated_genes_by_project", "cases", "files",
                      "gene_expression_availability", "gene_expression_values"}
    for request in scientific:
        rendered = json.dumps(dict(request.params)) + json.dumps(dict(request.body or {})) + request.path
        assert "TCGA-LUAD" not in rendered, "another cohort is never touched"
        if request.endpoint.name in project_scoped:
            assert "TCGA-LUSC" in rendered


# ------------------------------------------------------------------- live shaped sweep


def test_live_replay_produces_typed_states_without_jev(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "LIVE"
    assert run["coverage"] == "COMPLETE_FOR_SCOPE"
    assert run["selected_project_ids"] == ["TCGA-LUAD"]
    assert run["counts"]["states_generated"] == 2
    assert run["counts"]["states_evaluated"] == 0
    assert run["counts"]["candidates_promoted"] == 0
    assert run["provider_usage"]["jev_calls"] == 0
    assert run["provider_usage"]["llm_calls"] == 0

    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"]
                 for row in repository.list_table("statistical_states", run_id)}
    assert set(summaries) == set(GENES)
    for gene_id, summary in summaries.items():
        assert summary["affected_case_total"]["value"] == LUAD_AFFECTED[gene_id]
        assert summary["mutation_availability"] == "OBSERVED"
        assert summary["projects_with_mutation_observation"] == 1
        assert summary["expression_availability"] == "OBSERVED"
        assert summary["completeness"] == "COMPLETE"
        assert summary["top_project_share"]["availability"] == "NOT_APPLICABLE"
        assert summary["top_project_share"]["reason_code"] == "INSUFFICIENT_OBSERVED_PROJECTS"

    assert repository.list_table("candidates", run_id) == []
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("hypotheses", run_id) == []

    for gene_id in GENES:
        row, stored = _typed_state(runtime, repository, run_id, gene_id)
        assert stored.state_hash == row["state_hash"]
        assert state_identity(stored.state) == row["state_hash"]
        assert read_state(stored.artifact.content, expected_hash=row["state_hash"]) == stored.state
        boundary = json.loads(stored.artifact.content)
        assert boundary["schema_version"] == 5
        assert boundary["kind"] == "STATISTICAL_STATE"

        state = stored.state
        assert state.entity.symbol == ("GENEONE" if gene_id == GENE_ONE else "GENETWO")
        assert state.research.domain == "lung cancer"
        assert state.research.cohort == "TCGA-LUAD"
        assert state.research.projects == ("TCGA-LUAD",)
        assert state.quality.acquisition.value == "COMPLETE"
        assert state.quality.sufficiency.value == "SUFFICIENT"
        project = state.projects[0]
        assert len(project.population.frame.examined_ids) == LUAD_CASES
        assert project.mutation.affected_cases.value == LUAD_AFFECTED[gene_id]
        assert project.mutation.ssm_coverage_cases.value == 95
        assert project.mutation.coverage_complete is True
        assert len(project.expression.values) == LUAD_CASES
        assert project.expression.coverage.missing == ()
        assert len(project.expression.coverage.valid_ids) == LUAD_CASES
        assert project.expression.median.value == pytest.approx(LUAD_MEDIAN[gene_id])
        assert project.expression.sample_sd.value > 0
        assert state.cross_project.direction == "NOT_EXAMINED"
        assert state.cross_project.comparability_status == "NOT_APPLICABLE"
        assert state.cross_project.coverage_imbalance is False
        assert state.cross_project.affected_case_total.value == LUAD_AFFECTED[gene_id]
        assert "NOT OBSERVED" not in " ".join(state.warnings + state.missingness).upper()

    types = [event["type"] for event in _events(repository, run_id)]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_COMPLETED"
    assert types.count("STATISTICAL_STATE_CREATED") == 2
    assert types.index("PROJECT_SCOPE_SELECTED") < types.index("INVENTORY_COMPLETED")
    assert types.index("INVENTORY_COMPLETED") < types.index("STATISTICAL_STATE_CREATED")
    assert not any(event_type.startswith("JEV") for event_type in types)

    names = [request.endpoint.name if hasattr(request.endpoint, "name") else str(request.endpoint)
             for request in holder["transport"].requests]
    assert names.count("cases") == 1
    assert names.count("gene_expression_values") == 1
    assert len(names) <= 20

    client = _api_client(runtime, monkeypatch)
    listing = client.get(f"/api/runs/{run_id}/states")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 2
    state_id = _state_row(repository, run_id, GENE_ONE)["state_id"]
    detail = client.get(f"/api/states/{state_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["schema_version"] == 4
    assert payload["kind"] == "STATISTICAL_STATE_PRESENTATION"
    assert payload["state_hash"] == repository.get_state(state_id)["state_hash"]
    assert payload["research"]["domain"] == "lung cancer"
    assert payload["research"]["projects"] == ["TCGA-LUAD"]
    assert payload["quality"]["acquisition"] == "COMPLETE"
    assert payload["quality"]["sufficiency"] == "SUFFICIENT"
    assert payload["projects"][0]["affected_cases"]["value"] == LUAD_AFFECTED[GENE_ONE]
    assert payload["projects"][0]["expression"]["median"]["value"] == pytest.approx(
        LUAD_MEDIAN[GENE_ONE], abs=1e-6)
    assert payload["projects"][0]["expression"]["n_missing"] == 0
    detail_state = repository.get_state(state_id)
    assert detail.headers["x-artifact-sha256"] == repository.artifact(detail_state["artifact_id"])["sha256"]
    assert client.get(f"/api/runs/{run_id}/rankings").json() == {"baseline": None, "jev": None}
    assert client.get(f"/api/runs/{run_id}/projections").json()["items"] == []


def test_live_replay_links_scientific_sources_to_the_responses_that_supplied_them(
        runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch)
    run_id = orchestrator.run()
    issued = {request.request_hash() for request in holder["transport"].requests}
    received = {published.sha256 for published in holder["transport"].published}
    assert issued and received
    scan_artifact = repository.artifact_at_path(
        f"runs/{run_id}/selection/occurrence-scan-TCGA-LUAD.json")
    assert scan_artifact is not None, "the live path publishes its occurrence scan bundle"

    for row in repository.list_table("statistical_states", run_id):
        stored = read_state_record(repository, runtime[2], row["state_id"])
        state = stored.state
        assert len(state.sources) == len(state.operational_sources)
        assert all(isinstance(source, ScientificSource) for source in state.sources)
        assert all(isinstance(source, OperationalSource) for source in state.operational_sources)
        assert {field.name for field in dataclasses.fields(ScientificSource)} == {
            "endpoint", "request_hash", "response_hash", "parser_version", "release", "acquisition",
            "workflow_family", "caller_family", "strategy", "annotation_context"}
        for source in state.sources:
            if source.endpoint == "/ssm_occurrences/scan":
                assert source.response_hash == scan_artifact["sha256"]
                assert source.acquisition.value == "COMPLETE"
                continue
            assert source.request_hash in issued, "every scientific source names a request that started"
            assert source.response_hash in received, "every scientific source names the response that supplied it"
        for source in state.operational_sources:
            assert source.attempt_id and source.artifact_id and source.retrieved_at
            metadata = repository.artifact(source.artifact_id)
            assert metadata is not None
            assert metadata["sha256"] == source.source.response_hash
            if source.source.endpoint == "/ssm_occurrences/scan":
                assert metadata["relative_path"] == scan_artifact["relative_path"]
                continue
            assert source.source.request_hash in issued
            assert source.source.response_hash in received


def test_live_path_derives_affected_cases_from_the_complete_occurrence_scan(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"

    names = [request.endpoint.name for request in holder["transport"].requests]
    assert names.count("ssm_occurrences") == 1
    assert "top_cases_counts_by_genes" not in names, "the invalidated bucket is never requested"

    artifact = repository.artifact_at_path(f"runs/{run_id}/selection/examined_genes.json")
    payload = json.loads(runtime[2].read(artifact["relative_path"]))
    assert payload["affected_count_method"] == "MUTATION_AFFECTED_CASE_COUNT_V2"
    assert payload["affected_totals_in_scope"] == LUAD_AFFECTED

    scan_artifact = repository.artifact_at_path(
        f"runs/{run_id}/selection/occurrence-scan-TCGA-LUAD.json")
    scan_document = json.loads(runtime[2].read(scan_artifact["relative_path"]))
    assert scan_document["requested_fields"] == list(SSM_OCCURRENCE_FIELDS)
    assert scan_document["field_set_hash"]

    for gene_id in GENES:
        _, stored = _typed_state(runtime, repository, run_id, gene_id)
        affected = stored.state.projects[0].mutation.affected_cases
        assert affected.value == LUAD_AFFECTED[gene_id]
        assert affected.method.method_id == "MUTATION_AFFECTED_CASE_COUNT_V2"
        assert tuple(source.endpoint for source in affected.sources) == ("/ssm_occurrences/scan",)


def test_live_path_incomplete_occurrence_scan_fails_closed(runtime, monkeypatch):
    spec = _test_spec(occurrence_page_size=10)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec, truncate_occurrence_page=True)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "FAILED"
    failed = [event for event in _events(repository, run_id) if event["type"] == "RUN_FAILED"]
    assert failed[-1]["data"]["reason_code"] == "INVALID_PAGINATION"
    assert repository.list_table("statistical_states", run_id) == []


def test_live_path_duplicate_occurrence_across_pages_fails_closed(runtime, monkeypatch):
    spec = _test_spec(occurrence_page_size=10)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec, duplicate_occurrence_across_pages=True)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "FAILED"
    failed = [event for event in _events(repository, run_id) if event["type"] == "RUN_FAILED"]
    assert failed[-1]["data"]["reason_code"] == "DUPLICATE_OCCURRENCE_ACROSS_PAGES"
    assert repository.list_table("statistical_states", run_id) == []


# ------------------------------------------------------------------- wide Jev admission


def test_live_replay_with_jev_wide_evaluation(runtime, monkeypatch):
    adapter = StubAdapter()
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["counts"]["states_generated"] == 2
    assert run["counts"]["states_evaluated"] == 2
    assert run["counts"]["candidates_promoted"] == 2
    assert run["provider_usage"]["jev_calls"] == 2
    assert run["provider_usage"]["jev_input_tokens"] == 2400
    assert run["provider_usage"]["jev_output_tokens"] == 120
    assert run["provider_usage"]["llm_calls"] == 0
    assert adapter.calls == 2

    state_hashes = {row["summary"]["entity"]["gene_id"]: row["state_hash"]
                    for row in repository.list_table("statistical_states", run_id)}
    projections = repository.page_child("jev_projections", run_id, 50, None, {})["items"]
    assert len(projections) == 2
    for projection in projections:
        assert projection["projection_version"] == "jev-state-projection-v4"
        assert projection["source_state_hash"] in state_hashes.values()
        assert len(projection["projection_hash"]) == 64

    evaluations = repository.page_child("jev_evaluations", run_id, 20, None,
                                        {"purpose": "WIDE"})["items"]
    assert len(evaluations) == 2
    for evaluation in evaluations:
        vector = evaluation["vector"]
        assert vector["input_ref_kind"] == "STATISTICAL_STATE"
        assert vector["question_set_version"] == "wide-v3"
        assert vector["projection_version"] == "jev-state-projection-v4"
        assert vector["resolved_model"] == "jev-1.13.0"
        assert vector["cache_source_evaluation_id"] is None
        assert vector["error"] is None
        assert set(vector["answers"]) == WIDE_ANSWERS
        assert all(answer["kind"] in {"noul", "choice"} for answer in vector["answers"].values())
        assert vector["applicability"]["dominant_limitation"]["applicable"] is True
        assert vector["source_state_hash"] in state_hashes.values()

    candidates = repository.list_table("candidates", run_id)
    assert len(candidates) == 2
    assert sorted(row["promotion_slot"] for row in candidates) == [1, 2]
    for candidate in candidates:
        assert candidate["status"] == "WIDE_EVALUATED"
        assert candidate["summary"]["policy_version"] == "wide-policy-v2"
        assert candidate["summary"]["wide_evaluation_id"]
        assert candidate["source_state_id"] in {row["state_id"]
                                                for row in repository.list_table("statistical_states", run_id)}

    types = [event["type"] for event in _events(repository, run_id)]
    assert _wide_phase_events(repository, run_id) == WIDE_EVENT_ORDER
    assert types[-1] == "RUN_COMPLETED"
    sequences = [event["sequence"] for event in _events(repository, run_id)]
    assert sequences == sorted(set(sequences)), "the canonical event stream is monotonic"

    client = _api_client(runtime, monkeypatch)
    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    assert rankings["baseline"]["policy_version"] == "baseline-wide-v2"
    assert rankings["jev"]["policy_version"] == "wide-policy-v2"
    assert rankings["baseline"]["admitted_state_ids"] == []
    assert len(rankings["baseline"]["entries"]) == 2
    assert len(rankings["jev"]["entries"]) == 2
    assert len(rankings["jev"]["admitted_state_ids"]) == 2
    assert rankings["jev"]["admission"]["decision"] == "ADMIT"
    assert rankings["jev"]["admission"]["promotion_limit"] == 3
    listing = client.get(f"/api/runs/{run_id}/projections").json()["items"]
    assert len(listing) == 2
    assert {item["projection_version"] for item in listing} == {"jev-state-projection-v4"}


def test_jev_evaluations_are_cacheable_by_pinned_model_identity(runtime, monkeypatch):
    adapter = StubAdapter()
    first_orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    first = first_orchestrator.run()
    first_run = repository.get_run(first)
    assert first_run["provider_usage"]["jev_calls"] == 2
    calls_after_first = adapter.calls

    second_orchestrator, _, _ = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    second = second_orchestrator.run()
    second_run = repository.get_run(second)
    assert second_run["provider_usage"]["jev_calls"] == 0, "an identical pinned evaluation is reused"
    assert adapter.calls == calls_after_first

    evaluations = repository.page_child("jev_evaluations", second, 20, None,
                                        {"purpose": "WIDE"})["items"]
    assert len(evaluations) == 2
    assert all(row["vector"]["cache_source_evaluation_id"] for row in evaluations)
    first_hashes = sorted(row["vector"]["source_state_hash"] for row in
                          repository.page_child("jev_evaluations", first, 20, None,
                                                {"purpose": "WIDE"})["items"])
    assert sorted(row["vector"]["source_state_hash"] for row in evaluations) == first_hashes
    assert repository.get_run(second)["counts"]["states_evaluated"] == 2

    assert _wide_summary(repository, runtime[2], first) == _wide_summary(repository, runtime[2], second)
    for run_id in (first, second):
        assert _wide_phase_events(repository, run_id) == WIDE_EVENT_ORDER
        admitted = [event for event in _events(repository, run_id)
                    if event["type"] == "CANDIDATE_PROMOTED"]
        assert len(admitted) == 2
        assert all(event["data"]["policy_version"] == "wide-policy-v2" for event in admitted)


# --------------------------------------------------------------- bounded acquisition


def test_large_cohort_is_paged_batched_and_merged_deterministically(runtime, monkeypatch):
    spec = _test_spec(page_size=200, batch_size=200, max_cases=600)
    def build():
        orchestrator, holder, _ = _orchestrator(
            runtime, monkeypatch, research_spec=spec, project_case_counts={"TCGA-LUAD": 520},
            drop_value_columns=1)
        return orchestrator.run(), holder
    first, first_holder = build()
    second, _ = build()
    repository = runtime[1]
    for run_id in (first, second):
        assert repository.get_run(run_id)["status"] == "COMPLETED"

    case_offsets = [dict(request.params)["from"] for request in first_holder["transport"].requests
                    if request.endpoint.name == "cases"]
    assert case_offsets == ["0", "200", "400"]
    names = [request.endpoint.name for request in first_holder["transport"].requests]
    assert names.count("gene_expression_availability") == 3
    assert names.count("gene_expression_values") == 3
    assert "gene_expression_gene_selection" not in names
    for request in first_holder["transport"].requests:
        if request.endpoint.name == "gene_expression_values":
            assert len(request.body["case_ids"]) <= 200

    hashes = {row["summary"]["entity"]["gene_id"]: row["state_hash"]
              for row in repository.list_table("statistical_states", first)}
    second_hashes = {row["summary"]["entity"]["gene_id"]: row["state_hash"]
                     for row in repository.list_table("statistical_states", second)}
    assert hashes == second_hashes, "batching order never changes the scientific identity"

    for gene_id in GENES:
        stored = _typed_state(runtime, repository, first, gene_id)[1]
        project = stored.state.projects[0]
        assert len(project.population.frame.examined_ids) == 520
        assert len(project.expression.values) == 517
        assert len(project.expression.coverage.valid_ids) == 517
        missing = {group.reason: group.ids for group in project.expression.coverage.missing}
        assert len(missing["CASE_COLUMN_NOT_RETURNED"]) == 3
        assert stored.state.quality.acquisition.value == "COMPLETE"
        assert stored.state.quality.sufficiency.value == "PARTIAL"
        assert project.provider_expression.median is None
        assert project.provider_expression.stddev is None
        assert project.provider_expression.unavailable_reason == "BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE"
        assert any("not returned" in item for item in stored.state.missingness)


@pytest.mark.parametrize(("replay_options", "code"), [
    ({"duplicate_case_across_pages": True}, "DUPLICATE_CASE_ID"),
    ({"inconsistent_case_total_after_first": True}, "CASE_TOTAL_INCONSISTENT"),
    ({"inconsistent_case_offset_after_first": True}, "CASE_PAGE_OFFSET_INCONSISTENT"),
    ({"incomplete_frame": True}, "CASE_TOTAL_INCONSISTENT"),
])
def test_invalid_case_pagination_fails_closed(runtime, monkeypatch, replay_options, code):
    spec = _test_spec(page_size=200, max_cases=600)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec,
        project_case_counts={"TCGA-LUAD": 520}, **replay_options)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "FAILED"
    failed = [event for event in _events(repository, run_id) if event["type"] == "RUN_FAILED"]
    assert failed and failed[-1]["data"]["reason_code"] == code
    assert repository.list_table("statistical_states", run_id) == []
    assert repository.get_run(run_id)["coverage"] == "PARTIAL"


def test_cohort_ceiling_exceeded_fails_closed(runtime, monkeypatch):
    spec = _test_spec(page_size=200, max_cases=300)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec,
        project_case_counts={"TCGA-LUAD": 520})
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "FAILED"
    failed = [event for event in _events(repository, run_id) if event["type"] == "RUN_FAILED"]
    assert failed[-1]["data"]["reason_code"] == "COHORT_CASE_LIMIT_EXCEEDED"
    assert repository.list_table("statistical_states", run_id) == []


def test_controlled_file_record_fails_closed(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, controlled_files=True)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "FAILED"
    failed = [event for event in _events(repository, run_id) if event["type"] == "RUN_FAILED"]
    assert failed[-1]["data"]["reason_code"] == "CONTROLLED_RECORD_RETURNED"
    assert repository.list_table("statistical_states", run_id) == []


def test_missing_value_columns_stay_visible_in_state(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, drop_value_columns=2)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"

    for gene_id in GENES:
        row, stored = _typed_state(runtime, repository, run_id, gene_id)
        state = stored.state
        assert row["summary"]["expression_availability"] == "OBSERVED"
        assert state.quality.acquisition.value == "COMPLETE"
        assert state.quality.sufficiency.value == "PARTIAL"
        project = state.projects[0]
        assert len(project.expression.values) == 98
        assert len(project.expression.coverage.valid_ids) == 98
        missing = {group.reason: group.ids for group in project.expression.coverage.missing}
        assert len(missing["CASE_COLUMN_NOT_RETURNED"]) == 2
        assert 0 < project.expression.median.value
        assert any("not returned" in item for item in state.missingness)

    state_id = _state_row(repository, run_id, GENE_ONE)["state_id"]
    payload = _api_client(runtime, monkeypatch).get(f"/api/states/{state_id}").json()
    expression = payload["projects"][0]["expression"]
    assert expression["status"] == "OBSERVED"
    assert expression["n_finite"] == 98
    assert expression["n_examined"] == 100
    assert expression["n_missing"] == 2


def test_project_without_expression_values_skips_expression_calls(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(
        runtime, monkeypatch, empty_expression_projects={"TCGA-LUAD"})
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"

    names = [request.endpoint.name for request in holder["transport"].requests]
    assert names.count("gene_expression_availability") == 1
    assert names.count("gene_expression_gene_selection") == 0
    assert names.count("gene_expression_values") == 0

    for gene_id in GENES:
        row, stored = _typed_state(runtime, repository, run_id, gene_id)
        assert row["summary"]["expression_availability"] == "INSUFFICIENT"
        assert row["summary"]["coverage_imbalance"] is True
        project = stored.state.projects[0]
        assert project.expression.status.value == "NOT_ACQUIRED"
        assert project.expression.reason == "EXPRESSION_VALUES_NOT_ACQUIRED"
        assert project.provider_expression is None


def test_expression_availability_merge_keeps_observed_and_missing_genes_disjoint():
    observed = parse_expression_availability(
        availability_body(["P1-case-0"], [GENE_ONE]),
        _source_meta("gene_expression_availability", 1),
        expected_cases=["P1-case-0"], expected_genes=[GENE_ONE],
    )
    missing = parse_expression_availability(
        availability_body(["P1-case-1"], [GENE_ONE], empty=True),
        _source_meta("gene_expression_availability", 2),
        expected_cases=["P1-case-1"], expected_genes=[GENE_ONE],
    )
    merged = _merge_expression_availability(
        ["P1-case-0", "P1-case-1"], [GENE_ONE],
        [(["P1-case-0"], observed), (["P1-case-1"], missing)],
    )
    assert merged.cases == {"P1-case-0": True, "P1-case-1": False}
    observed_ids = {case_id for case_id, has_values in merged.cases.items() if has_values}
    missing_ids = {case_id for case_id, has_values in merged.cases.items() if not has_values}
    assert observed_ids == {"P1-case-0"}
    assert missing_ids == {"P1-case-1"}
    assert observed_ids.isdisjoint(missing_ids)
    assert merged.genes == {GENE_ONE: True}
    assert GENE_ONE not in merged.missing_genes
    assert observed.genes[GENE_ONE] is True
    assert missing.genes[GENE_ONE] is False


# --------------------------------------------------- wide phase as explicit collaborators


def _second_run(repository, label="wide-decoupled"):
    return repository.create_run(label, mode="LIVE", fixture_id=None, fixture_version=None)


def _recording_writer(repository, artifacts):
    emitted: list[str] = []
    published: list[str] = []

    def emit(run_id, event_type, key, message, **kwargs):
        emitted.append(event_type)
        return repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    def publish_json(run_id, path, payload, purpose):
        published.append(path)
        return artifacts.publish(path, json.dumps(payload).encode(), "application/json", purpose)

    return emit, publish_json, emitted, published


def test_run_wide_evaluation_takes_explicit_collaborators(runtime, monkeypatch):
    _, repository, states = _live_state_records(runtime, monkeypatch)
    adapter = StubAdapter()
    service = JevService(runtime[0], repository, runtime[2], adapter_factory=lambda: adapter)
    run_id = _second_run(repository)
    emit, publish_json, emitted, published = _recording_writer(repository, runtime[2])
    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE", repository=repository,
        jev_service=service, emit=emit, publish_json=publish_json)
    assert adapter.calls == 2
    assert len(result["baseline"]["entries"]) == 2
    assert len(result["jev"]["entries"]) == 2
    assert result["jev"]["admission"]["decision"] == "ADMIT"
    assert len(result["promoted"]) == 2
    assert [promotion["slot"] for promotion in result["promoted"]] == [1, 2]
    assert all(promotion["state_id"] in {state.state_id for state in states}
               for promotion in result["promoted"])
    assert emitted == WIDE_EVENT_ORDER
    assert published == [f"runs/{run_id}/wide/baseline_ranking.json",
                         f"runs/{run_id}/wide/jev_ranking.json"]
    for path in published:
        assert repository.artifact_at_path(path) is not None
    candidates = repository.list_table("candidates", run_id)
    assert {row["status"] for row in candidates} == {"WIDE_EVALUATED"}
    assert {row["summary"]["policy_version"] for row in candidates} == {"wide-policy-v2"}
    assert repository.get_run(run_id)["status"] == "PENDING"


def test_run_wide_evaluation_enforces_configured_state_cap(runtime, monkeypatch):
    _, repository, states = _live_state_records(runtime, monkeypatch)
    adapter = StubAdapter()
    service = JevService(runtime[0], repository, runtime[2], adapter_factory=lambda: adapter)
    run_id = _second_run(repository, "wide-capped")
    emit, publish_json, emitted, _ = _recording_writer(repository, runtime[2])
    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE", repository=repository,
        jev_service=service, emit=emit, publish_json=publish_json, max_states=1)
    assert adapter.calls == 1
    assert "JEV_WIDE_STATE_CAP_ENFORCED" in emitted
    cap_event = next(event for event in repository.events(run_id, 0, 50)["items"]
                     if event["type"] == "JEV_WIDE_STATE_CAP_ENFORCED")
    assert cap_event["data"]["cap"] == 1
    assert cap_event["data"]["requested_states"] == 2
    assert cap_event["data"]["evaluated_states"] == 1
    skipped = cap_event["data"]["skipped_state_ids"]
    assert skipped == [state.state_id for state in states[1:]]
    excluded = {entry["state_id"]: entry["excluded_reason"] for entry in result["jev"]["entries"]}
    assert excluded[skipped[0]] and "EVALUATION_MISSING" in excluded[skipped[0]]
    assert len(result["promoted"]) == 1


def test_run_wide_evaluation_abstains_and_defers_provider_failures(runtime, monkeypatch):
    _, repository, states = _live_state_records(runtime, monkeypatch)
    adapter = StubAdapter(fail=True)
    service = JevService(runtime[0], repository, runtime[2], adapter_factory=lambda: adapter)
    run_id = _second_run(repository, "wide-provider-failed")
    emit, publish_json, emitted, _ = _recording_writer(repository, runtime[2])
    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE", repository=repository,
        jev_service=service, emit=emit, publish_json=publish_json)
    assert adapter.calls == 2
    assert result["jev"]["admission"]["decision"] == "ABSTAIN"
    assert result["jev"]["admitted_state_ids"] == []
    assert result["promoted"] == []
    assert repository.list_table("candidates", run_id) == []
    assert all(entry["excluded_reason"] and "EVALUATION_FAILED" in entry["excluded_reason"]
               for entry in result["jev"]["entries"])
    evaluations = repository.page_child("jev_evaluations", run_id, 20, None,
                                        {"purpose": "WIDE"})["items"]
    assert len(evaluations) == 2
    assert all(row["vector"]["error"]["code"] == "PROVIDER_ERROR" for row in evaluations)
    ranking = next(event for event in repository.events(run_id, 0, 50)["items"]
                   if event["type"] == "WIDE_RANKING_COMPLETED")
    assert len(ranking["data"]["deferred_state_ids"]) == 2
    assert ranking["data"]["admission_decision"] == "ABSTAIN"


class _MalformedFirstStateAdapter(StubAdapter):
    """First judged state is malformed; the sweep must continue and record it."""

    def evaluate(self, state, definitions):
        if self.calls == 0:
            self.calls += 1
            self.last_state = state
            raise JevProviderError("PROVIDER_RESPONSE_MALFORMED", "first response is malformed")
        return super().evaluate(state, definitions)


def test_one_malformed_provider_response_does_not_abort_the_run(runtime, monkeypatch):
    _, repository, states = _live_state_records(runtime, monkeypatch)
    adapter = _MalformedFirstStateAdapter()
    service = JevService(runtime[0], repository, runtime[2], adapter_factory=lambda: adapter)
    run_id = _second_run(repository, "wide-one-malformed")
    emit, publish_json, _, _ = _recording_writer(repository, runtime[2])
    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE", repository=repository,
        jev_service=service, emit=emit, publish_json=publish_json)
    assert adapter.calls == 2, "a failed state still consumes exactly one provider attempt"
    assert len(result["jev"]["entries"]) == 2
    failed = [entry for entry in result["jev"]["entries"]
              if entry["excluded_reason"] and "EVALUATION_FAILED" in entry["excluded_reason"]]
    healthy = [entry for entry in result["jev"]["entries"] if entry["qualified"]]
    assert len(failed) == 1
    assert len(healthy) == 1
    assert len(result["promoted"]) == 1
    assert result["promoted"][0]["state_id"] == healthy[0]["state_id"]

    types = [event["type"] for event in _events(repository, run_id)]
    assert types.count("JEV_EVALUATION_FAILED") == 1
    assert types.count("JEV_WIDE_STATE_EVALUATED") == 1
    assert types.count("CANDIDATE_PROMOTED") == 1
    evaluations = repository.page_child("jev_evaluations", run_id, 20, None,
                                        {"purpose": "WIDE"})["items"]
    errors = [row for row in evaluations if row["vector"]["error"] is not None]
    assert len(errors) == 1
    assert errors[0]["vector"]["error"]["code"] == "PROVIDER_RESPONSE_MALFORMED"
    assert errors[0]["vector"]["answers"] == {}
