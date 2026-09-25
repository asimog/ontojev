"""Foundation tests for the single LUAD production research spec.

The typed run is driven by ``LUAD_RESEARCH_V1``: one explicit cohort, bounded
selection, no pooling, and a persisted typed state that reflects the spec.
Offline and provider-free (replay transport only).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from cancerjev.domain.codecs import read_state, state_identity, write_state
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
    MetricAvailability,
    ObservedCount,
    Sufficiency,
    UnavailableMeasurement,
)
from cancerjev.domain.scientific import ExpressionSummaryResult, UnavailableLane
from cancerjev.gdc.parsers import (
    GeneCaseCounts,
    ProjectCoverage,
    ResponseMeta,
    parse_gene_case_counts,
    parse_genes,
    parse_projects,
)
from cancerjev.research.acquisition import (
    _sum_if_complete,
    acquire_mutation_counts,
    acquire_project_frame,
)
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.specs import (
    IMPLEMENTED_ACTIONS,
    LUAD_RESEARCH_V1,
    RESEARCH_SPEC_SCHEMA_VERSION,
    CohortSpec,
    research_spec_from_dict,
)
from cancerjev.science.methods import (
    COMPARABILITY_STATUSES,
    MUTATION_ABSENCE_SEMANTICS,
    compute_statistical_state,
)
from tests.integration.replay import (
    GENES,
    PROJECTS,
    ReplayTransport,
    counts_body,
    genes_body,
    projects_body,
)

RELEASE = "Data Release TEST - 2026-01-01"
GENE = GENES[0]


def _run_luad(runtime, **transport_options):
    settings, repository, artifacts = runtime
    created: list[ReplayTransport] = []

    def factory(repo, store, budget, run_id, emit):
        transport = ReplayTransport(store, run_id, repository=repo, **transport_options)
        created.append(transport)
        return transport

    orchestrator = LiveOrchestrator(settings, repository, artifacts, transport_factory=factory)
    run_id = orchestrator.run()
    rows = repository.list_table("statistical_states", run_id)
    states = []
    for row in rows:
        artifact_row = repository.artifact(row["artifact_id"])
        raw = artifacts.read(artifact_row["relative_path"])
        states.append((row, read_state(raw, expected_hash=row["state_hash"])))
    return run_id, repository, artifacts, created[0], states


def _meta(endpoint: str, body: bytes) -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="GET", request_hash="r" * 64,
                        response_sha256=hashlib.sha256(body).hexdigest(), artifact_id=None,
                        retrieved_at="2026-09-25T00:00:00Z", source_release=RELEASE,
                        completeness="COMPLETE")


def _gene(gene_id: str = GENE):
    body = genes_body()
    return {record.gene_id: record for record in parse_genes(body, _meta("/genes", body))}[gene_id]


def _scope_meta() -> dict:
    spec = LUAD_RESEARCH_V1
    return {
        "gdc_release": RELEASE, "examined_case_frame": "ALL_CASES_PAGINATED",
        "scope_hash": "scope-hash", "spec_id": spec.spec_id,
        "research_spec": spec.as_dict(), "domain": spec.cohort.domain,
        "cohort": spec.cohort.cohort_id, "project_id": spec.cohort.project_id,
        "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": spec.gene_selection_rule(),
    }


def _discovery_meta() -> dict:
    payload = {"selected_gene_ids": list(GENES)}
    return {
        "method_id": "MUTATION_DISCOVERY_V1", "examined_genes_ref": "selection-artifact",
        "examined_genes_hash": hashlib.sha256(canonical_json(payload)).hexdigest(),
        "examined_genes_n": len(GENES), "rank_in_lane": 1, "observed_in_project_count": 1,
        "ranking_rule": LUAD_RESEARCH_V1.gene_selection_rule(), "selected_gene_ids": tuple(GENES),
    }


def _counts(*, drop_gene: str | None = None) -> GeneCaseCounts:
    document = json.loads(counts_body())
    for bucket in document["aggregations"]["projects"]["buckets"]:
        entries = bucket["genes"]["my_genes"]["gene_id"]["buckets"]
        if drop_gene is not None:
            entries[:] = [entry for entry in entries if entry["key"] != drop_gene]
        bucket["doc_count"] = sum(entry["doc_count"] for entry in entries)
    document["hits"]["total"]["value"] = sum(
        bucket["doc_count"] for bucket in document["aggregations"]["projects"]["buckets"])
    body = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    return parse_gene_case_counts(body, _meta("/analysis/top_cases_counts_by_genes", body))


def _direct_luad_state(runtime, *, counts: GeneCaseCounts | None = None,
                       coverage: ProjectCoverage | None = None):
    _, repository, artifacts = runtime
    run_id = repository.create_run("luad-direct-worker", mode="LIVE", scope={
        "spec_id": LUAD_RESEARCH_V1.spec_id, "selected_project_ids": ["TCGA-LUAD"]})
    transport = ReplayTransport(artifacts, run_id, repository=repository)
    body = projects_body(PROJECTS, "TCGA-LUAD")
    project = parse_projects(body, _meta("/projects", body))[0]
    frame, frame_sources, frame_warnings = acquire_project_frame(
        transport, project, LUAD_RESEARCH_V1.acquisition, RELEASE, list(GENES), {})
    mutation = acquire_mutation_counts(transport, list(GENES), RELEASE)
    return compute_statistical_state(
        gene=_gene(), frames=[frame],
        counts=counts if counts is not None else mutation.counts,
        coverage=coverage if coverage is not None else mutation.coverage,
        sources=frame_sources + mutation.sources,
        warnings=list(frame_warnings) + list(mutation.warnings),
        scope_meta=_scope_meta(), discovery_meta=_discovery_meta())


def test_luad_spec_is_the_single_production_spec():
    spec = LUAD_RESEARCH_V1
    assert spec.spec_id == "LUAD_RESEARCH_V1"
    assert spec.cohort == CohortSpec(cohort_id="TCGA-LUAD", domain="lung cancer",
                                     project_id="TCGA-LUAD")
    assert spec.cohort.cohort_id == spec.cohort.project_id
    assert spec.cohort.cohort_id != "TCGA-LUSC"
    assert spec.allowed_actions == ("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1")
    assert set(spec.allowed_actions) <= IMPLEMENTED_ACTIONS
    assert spec.limits.max_promotions < spec.limits.max_survivors <= 10
    assert spec.limits.max_revisions <= 2
    assert spec.acquisition.candidate_gene_limit <= spec.acquisition.count_gene_limit
    assert spec.acquisition.discovery_gene_limit <= spec.acquisition.candidate_gene_limit * 2
    assert "no case-count window and no cross-project pooling" in spec.cohort_selection_rule()
    assert "provider rank" in spec.gene_selection_rule()
    assert "_score is provider selection metadata" in spec.gene_selection_rule()


def test_spec_boundary_reader_is_strict_schema_3():
    payload = LUAD_RESEARCH_V1.as_dict()
    assert payload["schema_version"] == RESEARCH_SPEC_SCHEMA_VERSION == 3
    assert research_spec_from_dict(json.loads(json.dumps(payload))) == LUAD_RESEARCH_V1

    legacy = dict(payload)
    legacy["schema_version"] = 2
    with pytest.raises(ContractError):
        research_spec_from_dict(legacy)
    legacy = dict(payload)
    legacy["kind"] = "LEGACY_SPEC"
    with pytest.raises(ContractError):
        research_spec_from_dict(legacy)
    with pytest.raises(ContractError):
        research_spec_from_dict({**payload, "unexpected": True})


def test_luad_run_is_driven_by_the_luad_spec(runtime):
    run_id, repository, _, _, states = _run_luad(runtime)
    run = repository.get_run(run_id)
    assert run["spec_id"] == "LUAD_RESEARCH_V1"
    assert run["domain"] == "lung cancer"
    assert run["cohort"] == "TCGA-LUAD"
    assert run["project_id"] == "TCGA-LUAD"
    assert run["selected_project_ids"] == ["TCGA-LUAD"]
    assert run["acquisition"] == LUAD_RESEARCH_V1.as_dict()["acquisition"]
    assert run["scope_hash"]
    assert run["status"] == "COMPLETED"

    events = repository.events(run_id, 0, 500)["items"]
    started = [event for event in events if event["type"] == "RUN_STARTED"]
    assert len(started) == 1
    recorded_spec = research_spec_from_dict(started[0]["data"]["research_spec"])
    assert recorded_spec == LUAD_RESEARCH_V1

    assert states, "the LUAD run must produce at least one typed state"
    spec = LUAD_RESEARCH_V1.acquisition
    for row, state in states:
        assert row["disposition"] == "GENERATED"
        assert state.research.spec_id == LUAD_RESEARCH_V1.spec_id
        assert state.research.domain == "lung cancer"
        assert state.research.cohort == "TCGA-LUAD"
        assert state.research.project_id == "TCGA-LUAD"
        assert state.research.projects == ("TCGA-LUAD",)
        assert state.project_ids() == ("TCGA-LUAD",)
        assert state.entity.gene_id in GENES
        assert state_identity(state) == row["state_hash"]
        assert read_state(write_state(state), expected_hash=row["state_hash"]) == state

        acquisition = state.research.acquisition
        assert (acquisition.case_page_size, acquisition.case_batch_size,
                acquisition.max_cohort_cases) == (spec.case_page_size, spec.case_batch_size,
                                                  spec.max_cohort_cases)
        assert (acquisition.discovery_gene_limit, acquisition.count_gene_limit,
                acquisition.candidate_gene_limit) == (spec.discovery_gene_limit,
                                                       spec.count_gene_limit,
                                                       spec.candidate_gene_limit)
        assert acquisition.expression_file_sample_size == spec.expression_file_sample_size
        assert state.research.examined_case_frame == "ALL_CASES_PAGINATED"
        assert state.research.modalities == ("mutation_counts", "expression_summary")
        assert state.research.workflows == ("STAR - Counts",)
        assert state.research.sample_types == ("Primary Tumor",)
        assert state.quality.compatibility == Compatibility.UNVERIFIED
        assert state.quality.acquisition == Acquisition.COMPLETE
        assert state.quality.sufficiency == Sufficiency.SUFFICIENT
        project = state.projects[0]
        assert isinstance(project.mutation.affected_cases, ObservedCount)
        assert project.mutation.affected_cases.value <= PROJECTS["TCGA-LUAD"]
        assert isinstance(project.mutation.ssm_coverage_cases, ObservedCount)
        assert project.mutation.ssm_coverage_cases.value == 95
        assert isinstance(project.expression, ExpressionSummaryResult)
        assert project.provider_expression is not None


def test_luad_run_never_pools_another_cohort(runtime):
    _, _, _, transport, states = _run_luad(runtime)
    seen_projects = set()
    for request in transport.requests:
        params = dict(request.params)
        if "filters" in params:
            for project_id in PROJECTS:
                if project_id in json.dumps(json.loads(params["filters"])):
                    seen_projects.add(project_id)
        body = request.body if isinstance(request.body, dict) else {}
        case_ids = body.get("case_ids")
        if case_ids:
            seen_projects.add(case_ids[0].rsplit("-case-", 1)[0])
    assert seen_projects == {"TCGA-LUAD"}
    for _, state in states:
        assert "TCGA-LUSC" not in write_state(state).decode()
        assert state.research.cross_project_status == "NOT_APPLICABLE"
        assert state.research.within_cohort_status == "UNVERIFIED"
        assert state.research.comparability_statuses == COMPARABILITY_STATUSES
        assert state.cross_project.direction == "NOT_EXAMINED"
        used = {state.research.within_cohort_status, state.research.cross_project_status}
        assert "VERIFIED" not in used, "comparability is never fabricated"
        assert not hasattr(state.research, "comparability_groups")
        assert not hasattr(state.cross_project, "noncomparable_groups")
        assert state.cross_project.comparability_status == "NOT_APPLICABLE"


def test_luad_run_respects_selection_and_acquisition_limits(runtime):
    _, _, _, transport, states = _run_luad(runtime)
    spec = LUAD_RESEARCH_V1.acquisition
    cases_requested = 0
    for request in transport.requests:
        name = request.endpoint.name
        params = dict(request.params)
        body = request.body if isinstance(request.body, dict) else {}
        if name == "cases":
            assert int(params["size"]) <= spec.case_page_size
            cases_requested = max(cases_requested, int(params["from"]) + int(params["size"]))
        elif name == "top_mutated_genes_by_project":
            assert int(params["size"]) == spec.discovery_gene_limit
        elif name == "top_cases_counts_by_genes":
            assert len(params["gene_ids"].split(",")) <= spec.count_gene_limit
        elif name == "files":
            assert int(params["size"]) <= spec.expression_file_sample_size
        elif name in {"gene_expression_values", "gene_expression_availability"}:
            assert len(body["case_ids"]) <= spec.case_batch_size
            assert len(body["gene_ids"]) <= spec.candidate_gene_limit
    assert cases_requested <= spec.max_cohort_cases
    assert len(states) <= spec.candidate_gene_limit
    for _, state in states:
        assert len(state.universe.ordered_ids) <= spec.candidate_gene_limit
        assert state.universe.requested_limit == spec.candidate_gene_limit
        assert state.universe.order == "PROVIDER_RANK_ASC"
        assert state.universe.source == "GDC_MUTATION_DISCOVERY"
        assert state.tested_context.examined_genes_n == len(GENES)
        assert len(state.projects[0].population.frame.examined_ids) <= spec.max_cohort_cases


def test_missing_expression_columns_are_visible_and_not_zero(runtime):
    _, _, _, _, states = _run_luad(runtime, drop_value_columns=2)
    assert states
    for _, state in states:
        project = state.projects[0]
        expression = project.expression
        assert isinstance(expression, ExpressionSummaryResult)
        coverage = expression.coverage
        examined = project.population.frame.examined_ids
        assert len(examined) == PROJECTS["TCGA-LUAD"]
        assert coverage.returned_ids == examined[:-2]
        assert coverage.valid_ids == examined[:-2]
        assert len(expression.values) == PROJECTS["TCGA-LUAD"] - 2
        assert len(examined) - len(coverage.valid_ids) == 2, "missing is never collapsed to zero"
        assert len(coverage.assay_available_ids) == PROJECTS["TCGA-LUAD"], "case-level assay availability stays recorded"
        assert any(group.reason == "CASE_COLUMN_NOT_RETURNED" and len(group.ids) == 2
                   for group in coverage.missing)
        assert any("2 of 100 examined cases" in entry for entry in state.missingness)
        assert state.quality.acquisition == Acquisition.COMPLETE
        assert state.quality.sufficiency == Sufficiency.PARTIAL
        assert project.mutation.affected_cases.value in {20, 5}


def test_unavailable_expression_is_a_lane_not_a_zero(runtime):
    _, _, _, _, states = _run_luad(runtime, empty_expression_projects={"TCGA-LUAD"})
    assert states
    for _, state in states:
        project = state.projects[0]
        assert isinstance(project.expression, UnavailableLane)
        assert project.expression.lane.value == "EXPRESSION"
        assert project.expression.status.value == "NOT_ACQUIRED"
        assert isinstance(project.mutation.affected_cases, ObservedCount)
        assert state.cross_project.projects_with_expression_observation == 0
        assert state.cross_project.expression_median_min.availability.value == "NOT_OBSERVED"
        assert state.quality.sufficiency in (Sufficiency.PARTIAL, Sufficiency.INSUFFICIENT)


def test_wide_run_without_jev_promotes_nothing_and_dispatches_nothing(runtime):
    run_id, repository, _, _, states = _run_luad(runtime)
    assert states
    assert repository.list_table("candidates", run_id) == []
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("followup_executions", run_id) == []
    assert repository.list_table("jev_evaluations", run_id) == []
    assert repository.list_table("hypotheses", run_id) == []


def test_coverage_ssm_total_is_scoped_and_absence_is_not_zero(runtime):
    scoped = _direct_luad_state(runtime, coverage=ProjectCoverage(
        case_with_ssm={"TCGA-LUAD": 7, "TCGA-LUSC": 9, "TCGA-BRCA": 20},
        complete=True, partial_reasons=[], warnings=[]))
    ssm = scoped.projects[0].mutation.ssm_coverage_cases
    assert isinstance(ssm, ObservedCount) and ssm.value == 7
    serialized = write_state(scoped).decode()
    assert '"TCGA-LUSC"' not in serialized and '"TCGA-BRCA"' not in serialized

    absent = _direct_luad_state(runtime, coverage=ProjectCoverage(
        case_with_ssm={"TCGA-LUSC": 9}, complete=True, partial_reasons=[], warnings=[]))
    ssm = absent.projects[0].mutation.ssm_coverage_cases
    assert isinstance(ssm, UnavailableMeasurement)
    assert ssm.status.value == "NOT_OBSERVED" and ssm.reason == "PROJECT_NOT_IN_COVERAGE"


def test_absent_mutation_bucket_is_not_wildtype_or_zero(runtime):
    state = _direct_luad_state(runtime, counts=_counts(drop_gene=GENE))
    result = state.projects[0].mutation
    affected = result.affected_cases
    assert isinstance(affected, UnavailableMeasurement)
    assert affected.status.value == "NOT_OBSERVED"
    assert affected.reason == "GENE_BUCKET_ABSENT"
    assert state.cross_project.affected_case_total.availability == MetricAvailability.NOT_OBSERVED
    assert state.cross_project.affected_case_total.value is None
    assert MUTATION_ABSENCE_SEMANTICS in result.quality.reasons
    assert "not wildtype" in MUTATION_ABSENCE_SEMANTICS
    assert "not a callable negative" in MUTATION_ABSENCE_SEMANTICS
    assert not any(isinstance(value, ObservedCount) and value.value == 0
                   for value in (result.affected_cases,))

    assert _sum_if_complete([3, 4]) == 7
    assert _sum_if_complete([3, 0]) == 3, "an observed zero bucket is a real value"
    assert _sum_if_complete([3, None]) is None, "a missing bucket is never substituted with zero"
