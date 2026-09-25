"""Typed scientific baseline: schema-4 round trips and explicit unavailability.

No historical hash golden is asserted here. The baseline protects the current
contract relationally: a canonical StatisticalState and an E0 EvidenceState
re-read as the same typed objects, and a measurement the evidence never observed
stays unavailable rather than becoming a zero.
"""

import json

from cancerjev.domain.codecs import (
    evidence_identity,
    read_evidence,
    read_state,
    state_identity,
    write_evidence,
    write_state,
)
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import (
    BaselineObservation,
    EvidenceProvenance,
    EvidenceState,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    Acquisition,
    MetricAvailability,
    MetricRecord,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    ScientificSource,
    UnavailableMeasurement,
    UnavailableStatus,
    digest,
)
from cancerjev.domain.scientific import (
    ExpressionSummaryResult,
    Lane,
    UnavailableLane,
)
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
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.methods import ProjectFrame, compute_statistical_state

GENE = GeneRecord(gene_id="ENSG00000141510", symbol="TP53", name="tumor protein p53",
                  biotype="protein_coding", is_cancer_gene_census=True)
GENE_ID = GENE.gene_id
RELEASE = "Data Release 46.0"
SOURCE_SET = (
    OperationalSource(
        ScientificSource("/analysis/top_cases_counts_by_genes", "b" * 64, "a" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-1", "artifact-1", "2026-09-25T00:00:00Z", 100, 5, 200, False),
    OperationalSource(
        ScientificSource("/analysis/mutated_cases_count_by_project", "b" * 64, "d" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-2", "artifact-2", "2026-09-25T00:00:00Z", 100, 5, 200, False),
    OperationalSource(
        ScientificSource("/gene_expression/values", "b" * 64, "e" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-3", "artifact-3", "2026-09-25T00:00:00Z", 100, 5, 200, False),
)


def scope_meta():
    spec = LUAD_RESEARCH_V1
    return {
        "gdc_release": RELEASE,
        "cohort": spec.cohort.cohort_id,
        "project_id": spec.cohort.project_id,
        "spec_id": spec.spec_id,
        "domain": spec.cohort.domain,
        "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": spec.gene_selection_rule(),
        "examined_case_frame": "ALL_CASES_PAGINATED",
        "research_spec": {"acquisition": {
            "case_page_size": spec.acquisition.case_page_size,
            "case_batch_size": spec.acquisition.case_batch_size,
            "max_cohort_cases": spec.acquisition.max_cohort_cases,
            "discovery_gene_limit": spec.acquisition.discovery_gene_limit,
            "count_gene_limit": spec.acquisition.count_gene_limit,
            "candidate_gene_limit": spec.acquisition.candidate_gene_limit,
            "expression_file_sample_size": spec.acquisition.expression_file_sample_size,
        }},
    }


def discovery_meta():
    return {
        "selected_gene_ids": (GENE_ID,),
        "examined_genes_hash": digest([GENE_ID]),
        "examined_genes_n": 3,
        "rank_in_lane": 1,
        "observed_in_project_count": 1,
        "ranking_rule": "provider top-mutated ranking for the single examined cohort",
        "examined_genes_ref": "selection-artifact-1",
    }


def frame(project_id="TCGA-LUAD", *, cases=6, expression=True):
    case_records = [CaseRecord(case_id=f"{project_id}-case-{index:02d}", submitter_id=f"S-{index}",
                               project_id=project_id, sample_types=["Primary Tumor"])
                    for index in range(cases)]
    if expression:
        coverage = ExpressionAvailability(
            cases={case.case_id: True for case in case_records}, genes={GENE_ID: True},
            with_count=cases, without_count=0, missing_cases=[], missing_genes=[], warnings=[])
        values = ExpressionValues(
            values={GENE_ID: {case.case_id: float(index + 1)
                              for index, case in enumerate(case_records)}},
            missing_case_ids=[], missing_gene_ids=[], nonfinite_values=0, warnings=[])
        provider = ProviderSelection(
            genes={GENE_ID: ProviderGene(gene_id=GENE_ID, symbol="TP53", median=2.5, stddev=0.3)},
            missing_genes=[], warnings=[])
    else:
        coverage = values = provider = None
    hits = {GENE_ID: DiscoveryHit(gene_id=GENE_ID, symbol="TP53", rank=1, score=99.0)}
    return ProjectFrame(
        project_id=project_id,
        project_record=ProjectRecord(project_id=project_id, name=project_id, program_name="TCGA",
                                     primary_site=["Lung"], disease_type=["Adenocarcinoma"],
                                     case_count=cases, file_count=cases * 5,
                                     data_categories=["Transcriptome Profiling"]),
        cases=case_records, frame_hash="f" * 64, expression_coverage=coverage,
        provider_selection=provider, expression_values=values, workflows=["STAR - Counts"],
        strategies=["RNA-Seq"], discovery_hits=hits)


def build_state(*, frames=None, counts=None, coverage=None):
    frames = frames or [frame()]
    counts = counts if counts is not None else {f.project_id: {GENE_ID: 2} for f in frames}
    coverage = coverage if coverage is not None else {f.project_id: len(f.cases) for f in frames}
    return compute_statistical_state(
        gene=GENE, frames=frames,
        counts=GeneCaseCounts(projects=counts, hits_total=10, complete=True, partial_reasons=[],
                              warnings=[]),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=True, partial_reasons=[],
                                 warnings=[]),
        sources=SOURCE_SET, warnings=[], scope_meta=scope_meta(),
        discovery_meta=discovery_meta())


_METRIC_AVAILABILITY = {
    "NOT_OBSERVED": MetricAvailability.NOT_OBSERVED,
    "NOT_ACQUIRED": MetricAvailability.NOT_ACQUIRED,
    "PARTIAL": MetricAvailability.PARTIAL,
    "UNAVAILABLE": MetricAvailability.UNAVAILABLE,
    "INSUFFICIENT": MetricAvailability.INSUFFICIENT,
    "INCOMPATIBLE": MetricAvailability.UNAVAILABLE,
    "INVALID": MetricAvailability.UNAVAILABLE,
}


def metric(measurement, unit="cases"):
    if isinstance(measurement, (ObservedCount, ObservedScalar)):
        return MetricRecord.observed_value(measurement.value, unit)
    if isinstance(measurement, UnavailableMeasurement):
        return MetricRecord.unavailable(unit, _METRIC_AVAILABILITY.get(
            measurement.status.value, MetricAvailability.UNAVAILABLE), measurement.reason)
    return MetricRecord.unavailable(unit, MetricAvailability.NOT_OBSERVED)


def project_row(project):
    expression = project.expression
    if isinstance(expression, ExpressionSummaryResult):
        cases_with_expression = MetricRecord.observed_value(len(expression.coverage.valid_ids), "cases")
        missing_measurements = MetricRecord.observed_value(
            len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids), "cases")
    else:
        availability = _METRIC_AVAILABILITY.get(expression.status.value, MetricAvailability.NOT_OBSERVED)
        cases_with_expression = MetricRecord.unavailable("cases", availability, expression.reason)
        missing_measurements = MetricRecord.unavailable("cases", availability, expression.reason)
    return ProjectEvidenceRow(
        project_id=project.population.frame.project_id,
        affected_case_count=metric(project.mutation.affected_cases),
        examined_cases=MetricRecord.observed_value(len(project.mutation.frame.examined_ids), "cases"),
        project_case_with_ssm=metric(project.mutation.ssm_coverage_cases),
        cases_with_expression=cases_with_expression,
        missing_measurements=missing_measurements)


def baseline_observation(project):
    affected = project.mutation.affected_cases
    return BaselineObservation(
        "MUTATION_AFFECTED_CASE_COUNT_V1", "1",
        canonical_json({"value": affected.value if isinstance(affected, ObservedCount) else None,
                        "unit": "cases"}),
        "OBSERVED" if isinstance(affected, ObservedCount) else "NOT_OBSERVED",
        len(project.mutation.frame.examined_ids), 0, None)


def e0(state):
    accepted = state_identity(state)
    return EvidenceState(
        entity=state.entity, accepted_state_hash=accepted,
        source_state=SourceStateBinding("state-1", accepted, "artifact-1", "c" * 64),
        parent_evidence_hash=None, revision_index=0, action=None,
        puzzle=ResearchPuzzle(
            "STATISTICAL_STATE_BASELINE",
            "What does the recorded evidence support, and what follow-up is eligible?",
            "The baseline revision is the accepted evidence, not a judgment.",
            ("CHECK_EVIDENCE_INTEGRITY_V1",)),
        checks=(),
        baseline_observations=tuple(baseline_observation(project) for project in state.projects),
        project_evidence=tuple(project_row(project) for project in state.projects),
        missing_evidence=(), quality=state.quality, warnings=state.missingness,
        provenance=EvidenceProvenance(state.entity.release, state.sources, state.methods,
                                      state.environment_hash, "2",
                                      state.tested_context.examined_genes_hash, ()))


def test_typed_state_round_trip_preserves_scientific_content():
    state = build_state()
    raw = write_state(state)
    payload = json.loads(raw)
    assert payload["schema_version"] == 4
    assert payload["kind"] == "STATISTICAL_STATE"
    assert payload["state_hash"] == state_identity(state)
    assert read_state(raw) == state
    assert read_state(raw, expected_hash=state_identity(state)) == state
    assert state.research.spec_id == LUAD_RESEARCH_V1.spec_id
    assert state.research.cohort == LUAD_RESEARCH_V1.cohort.cohort_id


def test_typed_e0_round_trip_preserves_the_revision():
    state = build_state()
    base = e0(state)
    assert base.revision_index == 0
    assert base.action is None and base.checks == ()
    assert base.puzzle.origin == "STATISTICAL_STATE_BASELINE"
    raw = write_evidence(base)
    payload = json.loads(raw)
    assert payload["schema_version"] == 4
    assert payload["kind"] == "EVIDENCE_STATE"
    assert payload["evidence_hash"] == evidence_identity(base)
    assert read_evidence(raw) == base
    assert read_evidence(raw, expected_hash=evidence_identity(base)) == base


def test_missing_measurements_stay_unavailable_through_round_trips():
    state = build_state(
        frames=[frame("P1"), frame("P2", expression=False)],
        counts={"P1": {GENE_ID: 2}}, coverage={"P1": 6, "P2": 6})
    p2 = state.projects[1]
    assert isinstance(p2.mutation.affected_cases, UnavailableMeasurement)
    assert p2.mutation.affected_cases.status == UnavailableStatus.NOT_OBSERVED
    assert isinstance(p2.expression, UnavailableLane)
    assert p2.expression.lane == Lane.EXPRESSION
    assert p2.expression.status == UnavailableStatus.NOT_ACQUIRED

    base = e0(state)
    row = next(item for item in base.project_evidence if item.project_id == "P2")
    assert row.affected_case_count.availability == MetricAvailability.NOT_OBSERVED
    assert row.affected_case_count.value is None
    assert row.cases_with_expression.availability == MetricAvailability.NOT_ACQUIRED
    assert row.cases_with_expression.value is None
    assert row.missing_measurements.value is None

    state_roundtrip = read_state(write_state(state))
    assert state_roundtrip == state
    assert isinstance(state_roundtrip.projects[1].mutation.affected_cases, UnavailableMeasurement)
    evidence_roundtrip = read_evidence(write_evidence(base))
    assert evidence_roundtrip == base
    assert evidence_roundtrip.project_evidence[1].affected_case_count.value is None


def test_observed_counts_survive_a_round_trip_as_typed_counts():
    state = build_state(counts={"TCGA-LUAD": {GENE_ID: 0}})
    roundtrip = read_state(write_state(state), expected_hash=state_identity(state))
    affected = roundtrip.projects[0].mutation.affected_cases
    assert isinstance(affected, ObservedCount) and affected.value == 0
    assert roundtrip.cross_project.affected_case_total.value == 0
