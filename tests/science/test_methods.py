"""Typed scientific-method tests on provider-shaped offline replay data.

These tests protect measured arithmetic (provider counts, coverage, expression
summary on the exact examined case set), explicit missingness, provenance-bound
state identity and the bounded provider-ranked tested universe. All data is
synthetic, deterministic and offline.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, replace

import pytest

from cancerjev.domain.codecs import write_state
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import (
    Acquisition,
    ContractError,
    MetricAvailability,
    MetricRecord,
    ObservedCount,
    Sufficiency,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
)
from cancerjev.domain.scientific import ExpressionSummaryResult
from cancerjev.gdc.parsers import (
    GeneCaseCounts,
    GeneRecord,
    ProjectCoverage,
    ResponseMeta,
    parse_gene_case_counts,
    parse_genes,
    parse_mutated_cases_count,
    parse_projects,
    parse_top_mutated_genes,
)
from cancerjev.research.acquisition import acquire_mutation_counts, acquire_project_frame
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.methods import (
    COMPARABILITY_STATUSES,
    METHODS,
    MUTATION_ABSENCE_SEMANTICS,
    ProjectEvidence,
    ScienceError,
    compute_statistical_state,
    coverage_imbalance,
    expression_log2_summary,
    project_dominance,
    scientific_sufficiency,
)
from cancerjev.storage.artifacts import ArtifactStore
from tests.integration.replay import (
    GENES,
    PROJECTS,
    ReplayTransport,
    counts_body,
    coverage_body,
    discovery_body,
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


def _gene(gene_id: str = GENE) -> GeneRecord:
    body = genes_body()
    return {record.gene_id: record for record in parse_genes(body, _meta("/genes", body))}[gene_id]


def _scope_meta() -> dict:
    spec = LUAD_RESEARCH_V1
    return {
        "gdc_release": RELEASE,
        "examined_case_frame": "ALL_CASES_PAGINATED",
        "scope_hash": "scope-hash",
        "spec_id": spec.spec_id,
        "research_spec": spec.as_dict(),
        "domain": spec.cohort.domain,
        "cohort": spec.cohort.cohort_id,
        "project_id": spec.cohort.project_id,
        "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": spec.gene_selection_rule(),
    }


def _selection_payload(selected: tuple[str, ...]) -> dict:
    return {"selected_gene_ids": list(selected), "provider_ranked": True}


def _discovery_meta(*, selected: tuple[str, ...] = tuple(GENES), examined_genes_n: int = 2,
                    rank_in_lane: int = 1, selection_artifact_id: str = "selection-artifact") -> dict:
    return {
        "method_id": "MUTATION_DISCOVERY_V1",
        "examined_genes_ref": selection_artifact_id,
        "examined_genes_hash": hashlib.sha256(canonical_json(_selection_payload(selected))).hexdigest(),
        "examined_genes_n": examined_genes_n,
        "rank_in_lane": rank_in_lane,
        "observed_in_project_count": 1,
        "ranking_rule": LUAD_RESEARCH_V1.gene_selection_rule(),
        "selected_gene_ids": selected,
    }


def _discovery_hits(project_id: str, first_rank: int) -> dict:
    body = discovery_body(project_id)
    hits = parse_top_mutated_genes(body, _meta("/analysis/top_mutated_genes_by_project", body))
    return {hit.gene_id: replace(hit, rank=first_rank + index, score=800.0 - 10.0 * first_rank - index)
            for index, hit in enumerate(hits)}


def _counts(*, timed_out: bool = False, drop_gene: str | None = None, zero_gene: str | None = None,
            set_count: int | None = None, extra_project: str | None = None,
            extra_count: int = 1) -> GeneCaseCounts:
    document = json.loads(counts_body())
    document["timed_out"] = timed_out
    buckets = document["aggregations"]["projects"]["buckets"]
    for bucket in buckets:
        gene_buckets = bucket["genes"]["my_genes"]["gene_id"]["buckets"]
        if drop_gene is not None:
            gene_buckets[:] = [entry for entry in gene_buckets if entry["key"] != drop_gene]
        for entry in gene_buckets:
            if entry["key"] == zero_gene:
                entry["doc_count"] = 0
            if entry["key"] == GENE and set_count is not None:
                entry["doc_count"] = set_count
        bucket["doc_count"] = sum(entry["doc_count"] for entry in gene_buckets)
    if extra_project is not None:
        buckets.append({
            "key": extra_project, "doc_count": extra_count,
            "genes": {"my_genes": {"gene_id": {"buckets": [{"key": GENE, "doc_count": extra_count}]}}},
        })
    document["hits"]["total"]["value"] = sum(bucket["doc_count"] for bucket in buckets)
    body = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    return parse_gene_case_counts(body, _meta("/analysis/top_cases_counts_by_genes", body))


def _coverage(*, timed_out: bool = False, only_project: str | None = None,
              set_count: int | None = None) -> ProjectCoverage:
    document = json.loads(coverage_body())
    document["timed_out"] = timed_out
    buckets = document["aggregations"]["projects"]["buckets"]
    if only_project is not None:
        for bucket in buckets:
            bucket["key"] = only_project
    if set_count is not None:
        for bucket in buckets:
            bucket["case_summary"]["case_with_ssm"]["doc_count"] = set_count
    body = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    return parse_mutated_cases_count(body, _meta("/analysis/mutated_cases_count_by_project", body))


@dataclass(frozen=True)
class _Sample:
    state: object
    frames: tuple
    counts: GeneCaseCounts
    coverage: ProjectCoverage
    warnings: tuple[str, ...]
    transport: ReplayTransport
    artifacts: ArtifactStore


def _sample(tmp_path, *, run_id: str = "science-methods", project_ids: tuple[str, ...] = ("TCGA-LUAD",),
            gene_id: str = GENE, drop_columns: int = 0, empty_expression: frozenset[str] = frozenset(),
            discovery_rank: int = 1, counts: GeneCaseCounts | None = None,
            coverage: ProjectCoverage | None = None, examined_genes_n: int = 2,
            project_case_counts: dict[str, int] | None = None) -> _Sample:
    artifacts = ArtifactStore(tmp_path)
    case_counts = project_case_counts or PROJECTS
    transport = ReplayTransport(artifacts, run_id, drop_value_columns=drop_columns,
                                empty_expression_projects=set(empty_expression),
                                project_case_counts=case_counts)
    frames = []
    sources: list = []
    warnings: list[str] = []
    for project_id in project_ids:
        project_body = projects_body(case_counts, project_id)
        project = parse_projects(project_body, _meta("/projects", project_body))[0]
        hits = _discovery_hits(project_id, discovery_rank) if discovery_rank else {}
        frame, frame_sources, frame_warnings = acquire_project_frame(
            transport, project, LUAD_RESEARCH_V1.acquisition, RELEASE, list(GENES), hits)
        frames.append(frame)
        sources.extend(frame_sources)
        warnings.extend(frame_warnings)
    mutation = acquire_mutation_counts(transport, list(GENES), RELEASE)
    counts = mutation.counts if counts is None else counts
    coverage = mutation.coverage if coverage is None else coverage
    acquired = list(mutation.sources)
    if not counts.complete or not coverage.complete:
        count_endpoints = {"/analysis/top_cases_counts_by_genes",
                           "/analysis/mutated_cases_count_by_project"}
        acquired = [replace(source, source=replace(source.source, acquisition=Acquisition.PARTIAL))
                    if source.source.endpoint in count_endpoints else source
                    for source in acquired]
    sources.extend(acquired)
    warnings.extend(mutation.warnings)
    state = compute_statistical_state(
        gene=_gene(gene_id), frames=frames, counts=counts, coverage=coverage,
        sources=tuple(sources), warnings=warnings, scope_meta=_scope_meta(),
        discovery_meta=_discovery_meta(examined_genes_n=examined_genes_n),
    )
    return _Sample(state, tuple(frames), counts, coverage, tuple(warnings), transport, artifacts)


# ------------------------------------------------------------------ pure helpers


def test_expression_log2_summary_matches_hand_computation():
    summary = expression_log2_summary({"a": 3.0, "b": 15.0, "c": 0.0})
    hand = [math.log2(value + 1.0) for value in (3.0, 15.0, 0.0)]
    assert summary.n_finite == 3 and summary.n_missing == 0 and summary.n_returned == 3
    assert summary.availability == "OBSERVED"
    assert summary.median == pytest.approx(statistics.median(hand))
    assert summary.sample_sd == pytest.approx(statistics.stdev(hand))
    assert summary.minimum == pytest.approx(min(hand))
    assert summary.maximum == pytest.approx(max(hand))


def test_expression_log2_summary_counts_every_missing_bucket():
    summary = expression_log2_summary({"a": 4.0, "b": None}, missing_case_columns=3)
    assert (summary.n_finite, summary.n_returned, summary.n_missing) == (1, 2, 4)
    assert summary.sample_sd is None
    assert summary.availability == "INSUFFICIENT"

    partial = expression_log2_summary({"a": 4.0, "b": 8.0}, missing_case_columns=1)
    assert (partial.n_finite, partial.n_missing) == (2, 1)
    assert partial.availability == "PARTIAL"

    empty = expression_log2_summary({"a": None}, missing_case_columns=2)
    assert empty.median is None and empty.availability == "INSUFFICIENT"
    assert empty.n_missing == 3


def test_expression_log2_summary_rejects_negative_uqfpkm():
    with pytest.raises(ScienceError) as error:
        expression_log2_summary({"a": -1.0, "b": 3.0})
    assert error.value.code == "NEGATIVE_EXPRESSION"


def test_project_dominance_requires_two_observed_projects():
    assert project_dominance({"P1": 10}) == (None, "NOT_APPLICABLE")
    assert project_dominance({"P1": 0, "P2": 0}) == (None, "NOT_APPLICABLE")
    assert project_dominance({"P1": 30, "P2": 10}) == (0.75, "OBSERVED")
    share, status = project_dominance({"P1": 10, "P2": None})
    assert share is None and status == "NOT_APPLICABLE"


def _row(project_id, *, mutation=True, expression=True, examined=100,
         cases_with_expression=100, missing=0):
    return ProjectEvidence(project_id, mutation, expression, examined,
                           cases_with_expression, missing)


def test_coverage_imbalance_rules():
    assert coverage_imbalance([_row("P1"), _row("P2")]) is False
    assert coverage_imbalance([_row("P1"), _row("P2", mutation=False)]) is True
    assert coverage_imbalance([_row("P1", cases_with_expression=20), _row("P2")]) is True
    assert coverage_imbalance([_row("P1", cases_with_expression=0), _row("P2")]) is True
    assert coverage_imbalance([_row("P1", cases_with_expression=85), _row("P2")]) is False
    assert coverage_imbalance([_row("P1", cases_with_expression=None), _row("P2")]) is False


def test_scientific_sufficiency_requires_complete_acquisition_and_no_missingness():
    assert scientific_sufficiency([], True) == "INSUFFICIENT"
    assert scientific_sufficiency([_row("P1", mutation=False, expression=False)], True) == "INSUFFICIENT"
    assert scientific_sufficiency([_row("P1")], False) == "PARTIAL"
    assert scientific_sufficiency([_row("P1", missing=1)], True) == "PARTIAL"
    assert scientific_sufficiency([_row("P1"), _row("P2", mutation=False)], True) == "PARTIAL"
    assert scientific_sufficiency([_row("P1"), _row("P2", expression=False)], True) == "PARTIAL"
    assert scientific_sufficiency([_row("P1"), _row("P2")], True) == "SUFFICIENT"


@pytest.mark.parametrize("method_id", sorted(METHODS))
def test_method_registry_declares_typed_contract_fields(method_id):
    definition = METHODS[method_id]
    assert definition.version == "1"
    for field in ("purpose", "analysis_unit", "population_semantics", "duplicate_rule",
                  "eligibility", "minimum_n", "sampling_rule", "estimator",
                  "missingness_handling", "provenance_requirements", "limitations"):
        assert getattr(definition, field), field
    assert definition.effect_definition is None, "no effect size is computed by this phase"
    assert definition.interval_method is None
    assert definition.null_hypothesis is None
    assert definition.correction_family is None
    assert definition.unsupported_states
    assert definition.method_id == method_id


def test_metric_records_reject_inconsistent_or_nonfinite_values():
    with pytest.raises(ContractError):
        MetricRecord(5, "cases", MetricAvailability.NOT_OBSERVED)
    with pytest.raises(ContractError):
        MetricRecord(float("nan"), "cases", MetricAvailability.OBSERVED)
    with pytest.raises(ContractError):
        MetricRecord(5.5, "cases", MetricAvailability.OBSERVED)
    observed_zero = MetricRecord(0, "cases", MetricAvailability.OBSERVED)
    assert observed_zero.observed is True and observed_zero.value == 0
    unavailable = MetricRecord.unavailable("cases", MetricAvailability.NOT_OBSERVED, "GENE_BUCKET_ABSENT")
    assert unavailable.value is None and unavailable.reason_code == "GENE_BUCKET_ABSENT"


# ------------------------------------------------------------------ typed state arithmetic


def test_typed_state_expression_arithmetic_on_the_exact_examined_case_set(tmp_path):
    sample = _sample(tmp_path)
    project = sample.state.projects[0]
    expression = project.expression
    assert isinstance(expression, ExpressionSummaryResult)
    examined_ids = project.population.frame.examined_ids
    assert examined_ids == tuple(sorted(case.case_id for case in sample.frames[0].cases))
    assert expression.coverage.frame == project.population.frame
    assert tuple(value.case_id for value in expression.values) == examined_ids
    hand = [math.log2(value.uqfpkm + 1.0) for value in expression.values]
    assert len(hand) == PROJECTS["TCGA-LUAD"]
    assert expression.median.value == pytest.approx(statistics.median(hand))
    assert expression.sample_sd.value == pytest.approx(statistics.stdev(hand))
    assert expression.minimum.value == pytest.approx(min(hand))
    assert expression.maximum.value == pytest.approx(max(hand))
    assert expression.median.unit == Unit.LOG2_UQFPKM_PLUS_ONE
    assert expression.median.method.method_id == "EXPRESSION_LOG2_SUMMARY_V1"
    assert not expression.coverage.missing
    provider = project.provider_expression
    assert provider is not None
    assert provider.source == "GENE_SELECTION"
    assert provider.estimator_note == "INFERRED_POPULATION_SD_UNVERIFIED"
    assert provider.median == 3.0
    assert provider.stddev == 0.5
    assert provider.median != expression.median.value, "provider summary stays separate from local arithmetic"


def test_typed_state_mutation_counts_and_coverage_match_provider_buckets(tmp_path):
    sample = _sample(tmp_path)
    project = sample.state.projects[0]
    affected = project.mutation.affected_cases
    ssm = project.mutation.ssm_coverage_cases
    assert isinstance(affected, ObservedCount) and affected.value == 20
    assert affected.unit == Unit.CASES
    assert isinstance(ssm, ObservedCount) and ssm.value == 95
    assert project.mutation.coverage_complete is True
    assert sample.state.cross_project.affected_case_total.value == 20
    assert sample.state.cross_project.projects_with_mutation_observation == 1
    assert sample.state.cross_project.direction == "NOT_EXAMINED"
    assert sample.state.cross_project.comparability_status == "NOT_APPLICABLE"
    assert sample.state.research.within_cohort_status == "UNVERIFIED"
    assert sample.state.research.comparability_statuses == COMPARABILITY_STATUSES


def test_absent_gene_bucket_is_not_observed_never_zero(tmp_path):
    absent = _sample(tmp_path, run_id="absent", counts=_counts(drop_gene=GENE))
    affected = absent.state.projects[0].mutation.affected_cases
    ssm = absent.state.projects[0].mutation.ssm_coverage_cases
    assert isinstance(affected, UnavailableMeasurement)
    assert affected.status == UnavailableStatus.NOT_OBSERVED
    assert affected.reason == "GENE_BUCKET_ABSENT"
    assert not hasattr(affected, "value")
    assert isinstance(ssm, ObservedCount) and ssm.value == 95
    assert MUTATION_ABSENCE_SEMANTICS in absent.state.projects[0].mutation.quality.reasons
    assert "not wildtype" in MUTATION_ABSENCE_SEMANTICS
    assert "not a callable negative" in MUTATION_ABSENCE_SEMANTICS
    assert absent.state.cross_project.affected_case_total.availability.value == "NOT_OBSERVED"
    assert absent.state.cross_project.affected_case_total.value is None
    assert absent.state.cross_project.projects_with_mutation_observation == 0
    blob = write_state(absent.state).lower()
    assert b"observed_fraction" not in blob
    assert b"recurrence_fraction" not in blob

    zero = _sample(tmp_path, run_id="zero", counts=_counts(zero_gene=GENE))
    observed_zero = zero.state.projects[0].mutation.affected_cases
    assert isinstance(observed_zero, ObservedCount) and observed_zero.value == 0
    assert zero.state.cross_project.affected_case_total.value == 0


def test_partial_aggregation_is_recorded_and_warned(tmp_path):
    counted = _sample(tmp_path, run_id="partial-count", counts=_counts(timed_out=True))
    affected = counted.state.projects[0].mutation.affected_cases
    assert isinstance(affected, ObservedCount) and affected.value == 20
    assert counted.state.quality.acquisition == Acquisition.PARTIAL
    assert counted.state.quality.sufficiency == Sufficiency.PARTIAL
    assert any("mutation counts partial: timed_out" in warning for warning in counted.state.warnings)
    assert all(source.source.acquisition == Acquisition.PARTIAL
               for source in counted.state.operational_sources
               if source.source.endpoint == "/analysis/top_cases_counts_by_genes")

    zero = _sample(tmp_path, run_id="partial-zero", counts=_counts(timed_out=True, zero_gene=GENE))
    affected = zero.state.projects[0].mutation.affected_cases
    assert isinstance(affected, UnavailableMeasurement)
    assert (affected.status, affected.reason) == (UnavailableStatus.UNAVAILABLE, "PARTIAL_AGGREGATION")

    absent = _sample(tmp_path, run_id="partial-absent", counts=_counts(timed_out=True, drop_gene=GENE))
    affected = absent.state.projects[0].mutation.affected_cases
    assert isinstance(affected, UnavailableMeasurement)
    assert affected.reason == "GENE_BUCKET_ABSENT"
    assert affected.status != UnavailableStatus.NOT_OBSERVED


def test_coverage_imbalance_uses_recorded_expression_coverage_fractions(tmp_path):
    sample = _sample(tmp_path, run_id="fractions", project_ids=("TCGA-LUAD", "TEST-C"),
                     counts=_counts(extra_project="TEST-C", extra_count=3), coverage=_coverage())

    def state_with_expression_gap(keep: int):
        frames = []
        for frame in sample.frames:
            if frame.project_id == "TEST-C":
                coverage = replace(frame.expression_coverage,
                                   cases={case_id: index < keep
                                          for index, case_id in enumerate(frame.expression_coverage.cases)})
                frames.append(replace(frame, expression_coverage=coverage))
            else:
                frames.append(frame)
        return compute_statistical_state(
            gene=_gene(), frames=frames, counts=sample.counts, coverage=sample.coverage,
            sources=sample.state.operational_sources, warnings=[],
            scope_meta=_scope_meta(), discovery_meta=_discovery_meta())

    assert state_with_expression_gap(10).cross_project.coverage_imbalance is False
    assert state_with_expression_gap(9).cross_project.coverage_imbalance is False
    assert state_with_expression_gap(5).cross_project.coverage_imbalance is True
    assert state_with_expression_gap(0).cross_project.coverage_imbalance is True


def test_population_frames_carry_examined_ids_and_provider_totals(tmp_path):
    sample = _sample(tmp_path)
    population = sample.state.projects[0].population
    assert population.frame.examined_ids == tuple(
        sorted(case.case_id for case in sample.frames[0].cases))
    assert population.provider_reported_cases == 100
    assert population.frame_hash == sample.frames[0].frame_hash
    assert population.selection_method == "ALL_CASES_PAGINATED"
    assert population.frame.eligible_ids is None
    assert sample.state.research.projects == ("TCGA-LUAD",)
    assert sample.state.research.cohort == "TCGA-LUAD"
    assert sample.state.research.project_id == "TCGA-LUAD"
    assert sample.state.research.acquisition.candidate_gene_limit == LUAD_RESEARCH_V1.acquisition.candidate_gene_limit


def test_two_project_state_keeps_absent_project_unavailable(tmp_path):
    sample = _sample(tmp_path, run_id="two-project", project_ids=("TCGA-LUAD", "TEST-C"),
                     counts=_counts(extra_project="TEST-C", extra_count=0),
                     coverage=_coverage())
    assert sample.state.project_ids() == ("TCGA-LUAD", "TEST-C")
    luad, other = sample.state.projects
    assert luad.mutation.affected_cases.value == 20
    assert isinstance(other.mutation.affected_cases, ObservedCount)
    assert other.mutation.affected_cases.value == 0
    assert isinstance(other.mutation.ssm_coverage_cases, UnavailableMeasurement)
    assert other.mutation.ssm_coverage_cases.reason == "PROJECT_NOT_IN_COVERAGE"
    assert sample.state.cross_project.affected_case_total.value == 20
    assert sample.state.cross_project.coverage_imbalance is False


def test_project_order_is_canonical_in_the_typed_state(tmp_path):
    first = _sample(tmp_path, run_id="order-first", project_ids=("TCGA-LUAD", "TEST-C"),
                    counts=_counts(extra_project="TEST-C", extra_count=3), coverage=_coverage())
    second = _sample(tmp_path, run_id="order-second", project_ids=("TEST-C", "TCGA-LUAD"),
                     counts=_counts(extra_project="TEST-C", extra_count=3), coverage=_coverage())
    assert first.state.project_ids() == second.state.project_ids() == ("TCGA-LUAD", "TEST-C")
    assert [project.population.frame.project_id for project in first.state.projects] == \
        [project.population.frame.project_id for project in second.state.projects]
    assert [project.mutation.affected_cases.value for project in first.state.projects] == \
        [project.mutation.affected_cases.value for project in second.state.projects]


def test_tested_universe_is_provider_ranked_and_bounded(tmp_path):
    sample = _sample(tmp_path)
    universe = sample.state.universe
    assert universe.order == "PROVIDER_RANK_ASC"
    assert universe.ordered_ids == tuple(GENES)
    assert universe.offset == 0
    assert universe.complete is True
    assert universe.reported_total == len(GENES)
    assert universe.requested_limit == LUAD_RESEARCH_V1.acquisition.candidate_gene_limit
    assert "GENE_ID_ASC" not in universe.order
    assert universe.source == "GDC_MUTATION_DISCOVERY"
    assert sample.state.tested_context.examined_genes_n == len(GENES)
    assert sample.state.tested_context.rank_in_lane == 1
    assert "top-mutated ranking" in sample.state.tested_context.selection_rule
    assert "selection-biased" in sample.state.tested_context.selection_bias
