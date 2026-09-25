"""Lane-composition tests: mutation and the local expression summary compose into
one typed state, and missing lanes stay explicit instead of becoming zeros.

Offline, deterministic, provider-shaped replay data only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, dataclass, replace

import pytest

from cancerjev.domain.codecs import read_state, state_identity, write_state
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import (
    ContractError,
    ObservedCount,
    UnavailableMeasurement,
)
from cancerjev.domain.scientific import ExpressionSummaryResult, UnavailableLane
from cancerjev.gdc.parsers import (
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    ProjectCoverage,
    ResponseMeta,
    parse_gene_case_counts,
    parse_genes,
    parse_projects,
)
from cancerjev.jev.projection import PROJECTION_VERSION, build_projection
from cancerjev.research.acquisition import (
    _merge_expression_availability,
    _merge_expression_values,
    acquire_mutation_counts,
    acquire_project_frame,
)
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.expression import expression_log2_summary, expression_observation
from cancerjev.science.methods import compute_statistical_state
from cancerjev.science.mutation import mutation_observation
from cancerjev.storage.artifacts import ArtifactStore
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


def _meta(endpoint: str, body: bytes) -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="GET", request_hash="r" * 64,
                        response_sha256=hashlib.sha256(body).hexdigest(), artifact_id=None,
                        retrieved_at="2026-09-25T00:00:00Z", source_release=RELEASE,
                        completeness="COMPLETE")


def _gene():
    body = genes_body()
    return {record.gene_id: record for record in parse_genes(body, _meta("/genes", body))}[GENE]


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


@dataclass(frozen=True)
class _Sample:
    state: object
    frame: object
    counts: GeneCaseCounts
    coverage: ProjectCoverage
    transport: ReplayTransport
    artifacts: ArtifactStore


def _sample(tmp_path, *, run_id: str = "lanes", drop_gene: str | None = None,
            drop_columns: int = 0, empty_expression: bool = False) -> _Sample:
    artifacts = ArtifactStore(tmp_path)
    transport = ReplayTransport(artifacts, run_id, drop_value_columns=drop_columns,
                                empty_expression_projects={"TCGA-LUAD"} if empty_expression else set())
    body = projects_body(PROJECTS, "TCGA-LUAD")
    project = parse_projects(body, _meta("/projects", body))[0]
    frame, frame_sources, frame_warnings = acquire_project_frame(
        transport, project, LUAD_RESEARCH_V1.acquisition, RELEASE, list(GENES), {})
    mutation = acquire_mutation_counts(transport, list(GENES), RELEASE)
    counts = mutation.counts if drop_gene is None else _counts(drop_gene=drop_gene)
    state = compute_statistical_state(
        gene=_gene(), frames=[frame], counts=counts, coverage=mutation.coverage,
        sources=frame_sources + mutation.sources,
        warnings=list(frame_warnings) + list(mutation.warnings),
        scope_meta=_scope_meta(), discovery_meta=_discovery_meta())
    return _Sample(state, frame, counts, mutation.coverage, transport, artifacts)


def test_unacquired_expression_availability_is_not_zero(tmp_path):
    sample = _sample(tmp_path)
    frame = replace(sample.frame, expression_coverage=None, expression_values=None,
                    provider_selection=None)
    state = compute_statistical_state(
        gene=_gene(), frames=[frame], counts=sample.counts, coverage=sample.coverage,
        sources=sample.state.operational_sources, warnings=[], scope_meta=_scope_meta(),
        discovery_meta=_discovery_meta())
    project = state.projects[0]
    assert isinstance(project.expression, UnavailableLane)
    assert project.expression.lane.value == "EXPRESSION"
    assert project.expression.enabled is True
    assert project.expression.status.value == "NOT_ACQUIRED"
    assert project.expression.reason == "EXPRESSION_VALUES_NOT_ACQUIRED"
    assert not hasattr(project.expression, "median"), "an unavailable lane must not carry zeros"
    assert project.provider_expression is None
    assert isinstance(project.mutation.affected_cases, ObservedCount)
    assert project.mutation.affected_cases.value == 20
    assert state.cross_project.expression_median_min.value is None
    assert state.cross_project.expression_median_min.availability.value == "NOT_OBSERVED"
    assert state.cross_project.projects_with_expression_observation == 0


def test_mutation_missing_bucket_and_explicit_zero_remain_distinct():
    coverage = ProjectCoverage({"P1": 10}, True, [], [])
    observed = mutation_observation(
        "P1", GENE, GeneCaseCounts({"P1": {GENE: 0}}, 0, True, [], []), coverage)
    absent = mutation_observation(
        "P1", GENE, GeneCaseCounts({"P1": {}}, 0, True, [], []), coverage)
    partial = mutation_observation(
        "P1", GENE, GeneCaseCounts({"P1": {}}, 0, False, ["timed_out"], []), coverage)
    assert observed.affected_cases == 0
    assert observed.availability == "OBSERVED"
    assert absent.affected_cases is None and absent.reason == "GENE_BUCKET_ABSENT"
    assert partial.affected_cases is None and partial.availability == "PARTIAL"
    assert coverage.case_with_ssm == {"P1": 10}


def test_expression_is_independent_of_mutation_acquisition(tmp_path):
    absent = _sample(tmp_path, run_id="no-bucket", drop_gene=GENE)
    project = absent.state.projects[0]
    assert isinstance(project.mutation.affected_cases, UnavailableMeasurement)
    assert project.mutation.affected_cases.reason == "GENE_BUCKET_ABSENT"
    assert isinstance(project.expression, ExpressionSummaryResult)
    assert project.expression.median.value is not None
    assert len(project.expression.values) == PROJECTS["TCGA-LUAD"]

    unavailable = _sample(tmp_path, run_id="no-values", empty_expression=True)
    project = unavailable.state.projects[0]
    assert isinstance(project.mutation.affected_cases, ObservedCount)
    assert project.mutation.affected_cases.value == 20
    assert isinstance(project.expression, UnavailableLane)


@pytest.mark.parametrize("missing", ["values", "provider", "coverage"])
def test_lane_missingness_is_explicit(tmp_path, missing):
    sample = _sample(tmp_path)
    frame = sample.frame
    result = expression_observation(
        project_id="TCGA-LUAD", gene_id=GENE,
        case_ids=tuple(case.case_id for case in frame.cases),
        coverage=None if missing == "coverage" else frame.expression_coverage,
        values=None if missing == "values" else frame.expression_values,
        provider=None if missing == "provider" else frame.provider_selection)
    if missing == "values":
        assert result.local is None and result.local_availability == "NOT_ACQUIRED"
    elif missing == "coverage":
        assert result.cases_with_expression is None
    else:
        assert result.provider is None


@pytest.mark.parametrize("mutation,values,provider", [
    (False, False, False), (True, True, True), (False, True, True), (True, False, False),
])
def test_typed_lanes_roundtrip_and_project_independently(tmp_path, mutation, values, provider):
    sample = _sample(tmp_path, run_id=f"lanes-{mutation}-{values}-{provider}",
                     drop_gene=None if mutation else GENE)
    frame = replace(sample.frame,
                    expression_values=sample.frame.expression_values if values else None,
                    provider_selection=sample.frame.provider_selection if provider else None)
    state = compute_statistical_state(
        gene=_gene(), frames=[frame], counts=sample.counts, coverage=sample.coverage,
        sources=sample.state.operational_sources, warnings=[], scope_meta=_scope_meta(),
        discovery_meta=_discovery_meta())
    assert read_state(write_state(state)) == state
    assert state_identity(read_state(write_state(state))) == state_identity(state)

    record = StateRecord("state-lanes", state_identity(state), state)
    projection = build_projection(record)
    assert projection["projection_version"] == PROJECTION_VERSION
    cohort = projection["cohort"]
    project = state.projects[0]
    assert cohort["mutation_observed"] is mutation
    assert cohort["affected_cases"] == (20 if mutation else None)
    expression_observed = isinstance(project.expression, ExpressionSummaryResult)
    assert cohort["expression_observed"] is (values and expression_observed)
    if expression_observed:
        assert cohort["expression_median"] == project.expression.median.value
        assert cohort["expression_n_finite"] == len(project.expression.values)
        assert cohort["expression_n_missing"] == (
            len(project.expression.coverage.frame.examined_ids)
            - len(project.expression.coverage.valid_ids))
    else:
        assert cohort["expression_median"] is None
        assert cohort["expression_n_finite"] is None
        assert cohort["expression_n_missing"] is None
        assert isinstance(project.expression, UnavailableLane)
    expected_provider_median = 3.0 if provider else None
    assert cohort["expression_provider_median"] == expected_provider_median
    assert cohort["examined_cases"] == PROJECTS["TCGA-LUAD"]


def test_computed_state_and_boundary_copy_do_not_share_mutable_state(tmp_path):
    sample = _sample(tmp_path)
    state = sample.state
    original = write_state(state)
    payload = json.loads(original)
    payload["projects"][0]["mutation"]["affected_cases"]["value"] = 999
    assert state.projects[0].mutation.affected_cases.value == 20
    assert write_state(state) == original
    with pytest.raises(FrozenInstanceError):
        state.projects[0].mutation.affected_cases.value = 999
    with pytest.raises(ContractError):
        read_state(canonical_json(payload), expected_hash=state_identity(state))
    assert read_state(original, expected_hash=state_identity(state)) == state


def test_expression_batch_permutation_preserves_merged_values_and_local_result():
    gene = GENE
    parts = [(["a", "b"], ExpressionValues({gene: {"a": 4.0, "b": None}}, [], [], 0, [])),
             (["c", "d"], ExpressionValues({gene: {"c": 8.0}}, ["d"], [], 0, []))]
    first = _merge_expression_values(["a", "b", "c", "d"], [gene], parts)
    second = _merge_expression_values(["a", "b", "c", "d"], [gene], list(reversed(parts)))
    assert first == second
    assert expression_log2_summary(first.values[gene], missing_case_columns=1) == \
        expression_log2_summary(second.values[gene], missing_case_columns=1)
    availability = [
        (["a"], ExpressionAvailability({"a": True}, {gene: True}, 1, 0, [], [], [])),
        (["b"], ExpressionAvailability({"b": False}, {gene: False}, 0, 1, [], [], [])),
    ]
    assert _merge_expression_availability(["a", "b"], [gene], availability) == \
        _merge_expression_availability(["a", "b"], [gene], list(reversed(availability)))


def test_reordered_trusted_rows_preserve_identity_but_changed_source_hash_does_not(tmp_path):
    sample = _sample(tmp_path)
    values = sample.frame.expression_values
    reordered = replace(
        sample.frame,
        cases=list(reversed(sample.frame.cases)),
        expression_values=replace(values, values={
            gene: dict(reversed(list(row.items()))) for gene, row in values.values.items()}))
    recomputed = compute_statistical_state(
        gene=_gene(), frames=[reordered], counts=sample.counts, coverage=sample.coverage,
        sources=sample.state.operational_sources, warnings=[], scope_meta=_scope_meta(),
        discovery_meta=_discovery_meta())
    assert recomputed == sample.state
    assert write_state(recomputed) == write_state(sample.state)
    assert state_identity(recomputed) == state_identity(sample.state)

    first_source = sample.state.sources[0]
    changed_source = replace(first_source, response_hash="b" * 64)
    operational = tuple(
        replace(link, source=changed_source) if link.source == first_source else link
        for link in sample.state.operational_sources)
    changed = replace(sample.state, sources=(changed_source,) + sample.state.sources[1:],
                      operational_sources=operational)
    assert changed.projects == sample.state.projects
    assert state_identity(changed) != state_identity(sample.state)
    assert write_state(changed) != write_state(sample.state)
