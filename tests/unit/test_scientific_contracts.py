"""Typed schema-4 scientific contracts. All data here is synthetic and offline."""

import json
from dataclasses import FrozenInstanceError, asdict, replace

import pytest

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
    ActionRef,
    BaselineObservation,
    CheckOutcome,
    CheckSummary,
    EvidenceCheck,
    EvidenceProvenance,
    EvidenceState,
    MissingEvidence,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
    Coverage,
    EntityRef,
    MethodParameters,
    MethodRef,
    MetricAvailability,
    MetricRecord,
    MissingGroup,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    Quality,
    ScientificSource,
    Sufficiency,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
    digest,
)
from cancerjev.domain.measurements import (
    TestedUniverse as Universe,
)
from cancerjev.domain.scientific import (
    CnvCategory,
    CnvOccurrence,
    CnvOccurrenceResult,
    ExpressionSummaryResult,
    ExpressionValue,
    Lane,
    MutationCountResult,
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

# ------------------------------------------------------------ typed fixtures

GENE = GeneRecord(gene_id="ENSG00000141510", symbol="TP53", name="tumor protein p53",
                  biotype="protein_coding", is_cancer_gene_census=True)
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

GENE_ID = GENE.gene_id
FRAME = PopulationFrame("TCGA-LUAD", "TCGA-LUAD", PopulationUnit.CASE, ("a", "b"), ("a", "b"),
                        "declared synthetic frame")
ENTITY = EntityRef(GENE_ID, "TP53", "synthetic-release")
SOURCE = ScientificSource("/analysis", "a" * 64, "b" * 64, "1", ENTITY.release, Acquisition.COMPLETE)
QUALITY = Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.VERIFIED, ())
COUNT_METHOD = MethodRef("COUNT", "1", Unit.CASES, MethodParameters(), "unique cases", "none", "count",
                         "missing is unavailable", ())
SCALAR_METHOD = replace(COUNT_METHOD, method_id="LOG2", unit=Unit.LOG2_UQFPKM_PLUS_ONE,
                        parameters=MethodParameters(pseudocount=1), transform="log2(UQFPKM+1)",
                        estimator="local summary")


def observed_count(value=1, **changes):
    return ObservedCount(value, **{"unit": Unit.CASES, "population": FRAME, "method": COUNT_METHOD,
                                   "sources": (SOURCE,), **changes})


def scalar(value=3, **changes):
    return ObservedScalar(value, **{"unit": Unit.LOG2_UQFPKM_PLUS_ONE, "population": FRAME,
                                    "method": SCALAR_METHOD, "sources": (SOURCE,), **changes})


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


def discovery_meta(selected_ids=(GENE_ID,)):
    ids = tuple(selected_ids)
    return {
        "selected_gene_ids": ids,
        "examined_genes_hash": digest(list(ids)),
        "examined_genes_n": max(3, len(ids)),
        "rank_in_lane": 1,
        "observed_in_project_count": 1,
        "ranking_rule": "provider top-mutated ranking for the single examined cohort",
        "examined_genes_ref": "selection-artifact-1",
    }


def frame(project_id="TCGA-LUAD", *, cases=6, drop_columns=0, missing_cells=0, expression=True):
    case_records = [CaseRecord(case_id=f"{project_id}-case-{index:02d}", submitter_id=f"S-{index}",
                               project_id=project_id, sample_types=["Primary Tumor"])
                    for index in range(cases)]
    if expression:
        returned = case_records[: cases - drop_columns]
        coverage = ExpressionAvailability(
            cases={case.case_id: True for case in case_records},
            genes={GENE_ID: True}, with_count=len(returned), without_count=0,
            missing_cases=[case.case_id for case in case_records[cases - drop_columns:]],
            missing_genes=[], warnings=[])
        values = ExpressionValues(
            values={GENE_ID: {case.case_id: (float(index + 1) if index >= missing_cells else None)
                              for index, case in enumerate(returned)}},
            missing_case_ids=[case.case_id for case in case_records[cases - drop_columns:]],
            missing_gene_ids=[], nonfinite_values=0, warnings=[])
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


def build_state(*, frames=None, counts=None, coverage=None, sources=SOURCE_SET, discovery=None):
    frames = frames or [frame()]
    counts = counts if counts is not None else {f.project_id: {GENE_ID: 2} for f in frames}
    coverage = coverage if coverage is not None else {f.project_id: len(f.cases) for f in frames}
    return compute_statistical_state(
        gene=GENE, frames=frames,
        counts=GeneCaseCounts(projects=counts, hits_total=10, complete=True, partial_reasons=[],
                              warnings=[]),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=True, partial_reasons=[],
                                 warnings=[]),
        sources=sources, warnings=[], scope_meta=scope_meta(),
        discovery_meta=discovery if discovery is not None else discovery_meta())


_METRIC_AVAILABILITY = {
    "NOT_OBSERVED": MetricAvailability.NOT_OBSERVED,
    "NOT_ACQUIRED": MetricAvailability.NOT_ACQUIRED,
    "PARTIAL": MetricAvailability.PARTIAL,
    "UNAVAILABLE": MetricAvailability.UNAVAILABLE,
    "INSUFFICIENT": MetricAvailability.INSUFFICIENT,
}


def metric(measurement, unit="cases"):
    if isinstance(measurement, (ObservedCount, ObservedScalar)):
        return MetricRecord.observed_value(measurement.value, unit)
    if isinstance(measurement, UnavailableMeasurement):
        return MetricRecord.unavailable(unit, _METRIC_AVAILABILITY.get(
            measurement.status.value, MetricAvailability.UNAVAILABLE), measurement.reason)
    return MetricRecord.unavailable(unit, MetricAvailability.NOT_OBSERVED)


def project_rows(state):
    rows = []
    for project in state.projects:
        expression = project.expression
        if isinstance(expression, ExpressionSummaryResult):
            cases_with_expression = MetricRecord.observed_value(len(expression.coverage.valid_ids),
                                                                "cases")
            missing_measurements = MetricRecord.observed_value(
                len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids),
                "cases")
        else:
            availability = _METRIC_AVAILABILITY.get(expression.status.value,
                                                    MetricAvailability.NOT_OBSERVED)
            cases_with_expression = MetricRecord.unavailable("cases", availability, expression.reason)
            missing_measurements = MetricRecord.unavailable("cases", availability, expression.reason)
        rows.append(ProjectEvidenceRow(
            project_id=project.population.frame.project_id,
            affected_case_count=metric(project.mutation.affected_cases),
            examined_cases=MetricRecord.observed_value(len(project.mutation.frame.examined_ids),
                                                       "cases"),
            project_case_with_ssm=metric(project.mutation.ssm_coverage_cases),
            cases_with_expression=cases_with_expression,
            missing_measurements=missing_measurements))
    return tuple(rows)


def baseline_observations(state):
    observations = []
    for project in state.projects:
        affected = project.mutation.affected_cases
        observations.append(BaselineObservation(
            "MUTATION_AFFECTED_CASE_COUNT_V1", "1",
            canonical_json({"value": affected.value if isinstance(affected, ObservedCount) else None,
                            "unit": "cases"}),
            "OBSERVED" if isinstance(affected, ObservedCount) else "NOT_OBSERVED",
            len(project.mutation.frame.examined_ids), 0, None))
        expression = project.expression
        if isinstance(expression, ExpressionSummaryResult):
            observed = expression.median.value if isinstance(expression.median, ObservedScalar) else None
            missing = len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids)
            observations.append(BaselineObservation(
                "EXPRESSION_LOG2_SUMMARY_V1", "1",
                canonical_json({"value": observed, "unit": "log2(UQFPKM+1)"}),
                "OBSERVED" if observed is not None else "NOT_OBSERVED",
                len(expression.values), missing,
                "EXAMINED_CASES_WITHOUT_RETURNED_VALUE" if missing else None))
    return tuple(observations)


def baseline(state):
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
        checks=(), baseline_observations=baseline_observations(state),
        project_evidence=project_rows(state),
        missing_evidence=(MissingEvidence("population_exclusions", MetricAvailability.NOT_OBSERVED,
                                          "the recorded population does not list excluded cases"),),
        quality=state.quality, warnings=state.missingness,
        provenance=EvidenceProvenance(state.entity.release, state.sources, state.methods,
                                      state.environment_hash, "2",
                                      state.tested_context.examined_genes_hash, ()))


def revision(base, state, outcome=CheckOutcome.VERIFIED):
    check = EvidenceCheck(
        "CHECK_EVIDENCE_INTEGRITY_V1", "EVIDENCE_INTEGRITY_V1", "1", outcome,
        "recorded counts are internally consistent", (base.accepted_state_hash,),
        None if outcome == CheckOutcome.VERIFIED else "recorded evidence contradicts the claim",
        len(state.projects), canonical_json({"affected": 2}), canonical_json({"affected": 2}),
        missing_count=1 if outcome == CheckOutcome.NOT_OBSERVED else 0,
        missing_reason=("RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION"
                        if outcome == CheckOutcome.NOT_OBSERVED else None))
    return replace(base, parent_evidence_hash=evidence_identity(base), revision_index=1,
                   action=ActionRef("CHECK_EVIDENCE_INTEGRITY_V1", "1"),
                   puzzle=ResearchPuzzle("DETERMINISTIC_ACTION_REGISTRY", "Is the revision faithful?",
                                         "Checks are not measurements.",
                                         ("CHECK_EVIDENCE_INTEGRITY_V1",)),
                   checks=(check,), baseline_observations=())


# --------------------------------------------------------- measurement contracts


@pytest.mark.parametrize(("factory", "value"), [
    (observed_count, None), (observed_count, True), (observed_count, -1),
    (observed_count, 1.5), (observed_count, float("inf")), (observed_count, float("nan")),
    (scalar, None), (scalar, True), (scalar, -1), (scalar, "1"),
    (scalar, float("nan")), (scalar, 10 ** 1000),
])
def test_observed_measurements_reject_invalid_values(factory, value):
    with pytest.raises(ContractError):
        factory(value)


@pytest.mark.parametrize("status", list(UnavailableStatus))
def test_unavailable_measurement_carries_no_value_and_keeps_its_status(status):
    result = UnavailableMeasurement(status, "explicit reason", Unit.CASES, FRAME)
    assert result.status == status
    assert not hasattr(result, "value")
    assert "value" not in asdict(result)
    with pytest.raises(ContractError):
        replace(result, reason="")


def test_observed_zero_is_not_missing_and_needs_completed_source():
    assert observed_count(0).value == 0
    partial = replace(SOURCE, acquisition=Acquisition.PARTIAL)
    assert observed_count(1, sources=(partial,)).value == 1
    with pytest.raises(ContractError):
        observed_count(0, sources=(partial,))
    with pytest.raises(ContractError):
        observed_count(1, sources=(replace(SOURCE, acquisition=Acquisition.FAILED),))


def test_counts_cannot_exceed_their_declared_frame_or_change_unit():
    with pytest.raises(ContractError):
        MutationCountResult(observed_count(3), observed_count(2), False, FRAME, QUALITY, ENTITY)
    with pytest.raises(ContractError):
        observed_count(method=SCALAR_METHOD)


# ------------------------------------------------------------- state contracts


def test_state_cannot_mix_gene_results():
    original = build_state()
    for lane in ("mutation", "expression"):
        wrong = replace(getattr(original.projects[0], lane),
                        entity=replace(original.entity, gene_id="ENSG00000000001"))
        with pytest.raises(ContractError):
            replace(original, projects=(replace(original.projects[0], **{lane: wrong}),))


def test_state_collections_are_immutable_and_typed():
    result = build_state()
    with pytest.raises(FrozenInstanceError):
        result.entity.symbol = "OTHER"
    with pytest.raises(TypeError):
        result.projects[0].expression.values[0] = ExpressionValue("a", 99)
    with pytest.raises(ContractError):
        replace(result, sources=[SOURCE])
    with pytest.raises(ContractError):
        replace(result.projects[0].population.frame, examined_ids=["a", "b"])
    with pytest.raises(ContractError):
        replace(result.projects[0].expression, values=list(result.projects[0].expression.values))
    with pytest.raises(ContractError):
        replace(COUNT_METHOD, parameters={"ddof": 1})


@pytest.mark.parametrize("changes", [
    {"eligible_ids": ("a",)}, {"examined_ids": ("b", "a")}, {"examined_ids": ("a", "a")},
])
def test_population_membership_is_explicit(changes):
    with pytest.raises(ContractError):
        replace(FRAME, **changes)


def test_coverage_accounts_for_every_case_without_equating_availability_and_values():
    coverage = Coverage(FRAME, ("a",), ("a",), (MissingGroup("absent column", ("b",)),), None)
    assert coverage.assay_available_ids is None
    with pytest.raises(ContractError):
        replace(coverage, missing=())
    with pytest.raises(ContractError):
        replace(coverage, missing=(MissingGroup("absent column", ("a", "b")),))
    with pytest.raises(ContractError):
        replace(coverage, returned_ids=("outside",))
    with pytest.raises(ContractError):
        replace(coverage, valid_ids=("a", "b"))


def test_expression_summary_sample_size_and_context_are_checked_not_imputed():
    expression = build_state(frames=[frame(missing_cells=5)]).projects[0].expression
    assert isinstance(expression.sample_sd, UnavailableMeasurement)
    with pytest.raises(ContractError):
        replace(expression, sample_sd=expression.median)
    with pytest.raises(ContractError):
        replace(expression, values=())
    with pytest.raises(ContractError):
        replace(expression, sources=())


def test_quality_axes_and_disabled_lanes_remain_separate():
    quality = Quality(Acquisition.COMPLETE, Sufficiency.INSUFFICIENT, Compatibility.UNVERIFIED,
                      ("no usable measurements",))
    assert quality.acquisition == Acquisition.COMPLETE
    with pytest.raises(ContractError):
        replace(quality, reasons=())
    with pytest.raises(ContractError):
        UnavailableLane(Lane.EXPRESSION, False, UnavailableStatus.NOT_OBSERVED, "disabled")
    original = build_state()
    with pytest.raises(ContractError):
        replace(original, projects=(replace(
            original.projects[0],
            mutation=UnavailableLane(Lane.CNV, True, UnavailableStatus.NOT_ACQUIRED, "wrong lane")),))


def test_universe_slice_is_not_genome_completeness():
    universe = Universe((GENE_ID,), "GDC_MUTATION_DISCOVERY", "synthetic-release", "slice",
                        "GENE_ID_ASC", 0, 2, 30, False)
    assert not universe.complete and universe.reported_total > len(universe.ordered_ids)
    with pytest.raises(ContractError):
        replace(universe, reported_total=0)
    with pytest.raises(ContractError):
        replace(universe, requested_limit=1001)
    with pytest.raises(ContractError):
        replace(universe, order="NOT_DECLARED")
    with pytest.raises(ContractError):
        replace(universe, complete=True)


def test_cnv_retains_raw_categories_and_missing_sample_context():
    occurrence = CnvOccurrence("occurrence", "cnv", "a", GENE_ID, "Loss", None, None, None, None)
    assert occurrence.category == CnvCategory.LOSS_UNSPECIFIED
    assert replace(occurrence, raw_category="Novel").category == CnvCategory.UNSUPPORTED_CATEGORY
    cnv = CnvOccurrenceResult(ENTITY, FRAME, (occurrence,), (SOURCE,), QUALITY)
    with pytest.raises(ContractError):
        replace(cnv, occurrences=(occurrence, occurrence))
    with pytest.raises(ContractError):
        replace(cnv, occurrences=(replace(occurrence, case_id="outside"),))


# ------------------------------------------------------------ boundary codecs


def test_state_schema_4_round_trip_preserves_typed_fields():
    state = build_state()
    raw = write_state(state)
    payload = json.loads(raw)
    assert payload["schema_version"] == 4
    assert payload["kind"] == "STATISTICAL_STATE"
    assert payload["state_hash"] == state_identity(state)
    assert read_state(raw) == state
    assert read_state(raw, expected_hash=state_identity(state)) == state


@pytest.mark.parametrize("outcome", [CheckOutcome.VERIFIED, CheckOutcome.CONTRADICTED])
def test_evidence_schema_4_round_trip_for_baseline_and_revision(outcome):
    state = build_state()
    base = baseline(state)
    assert read_evidence(write_evidence(base), expected_hash=evidence_identity(base)) == base
    changed = revision(base, state, outcome)
    assert read_evidence(write_evidence(changed), expected_hash=evidence_identity(changed)) == changed


def test_evidence_summary_and_revision_consistency():
    state = build_state()
    base = baseline(state)
    changed = revision(base, state)
    assert base.summary == CheckSummary(0, 0, 0, 0)
    with pytest.raises(ContractError):
        CheckSummary(3, 1, 1, 0)
    with pytest.raises(ContractError):
        replace(changed, checks=changed.checks * 2)
    with pytest.raises(ContractError):
        replace(base, parent_evidence_hash=changed.parent_evidence_hash)
    with pytest.raises(ContractError):
        replace(changed, parent_evidence_hash=None)
    with pytest.raises(ContractError):
        replace(changed, revision_index=3)
    with pytest.raises(ContractError):
        replace(changed.checks[0], outcome=CheckOutcome.NOT_OBSERVED)


@pytest.mark.parametrize("mutation", ["null", "bool", "unexpected", "unavailable_value", "hash",
                                      "unit", "release", "schema", "kind"])
def test_schema_4_boundary_rejects_malformed_records(mutation):
    payload = json.loads(write_state(build_state()))
    project = payload["projects"][0]
    if mutation in ("null", "bool"):
        project["mutation"]["affected_cases"]["value"] = None if mutation == "null" else True
    elif mutation == "unexpected":
        project["invented_metric"] = 20
    elif mutation == "unavailable_value":
        measurement = project["mutation"]["affected_cases"]
        project["mutation"]["affected_cases"] = {
            "status": "NOT_OBSERVED", "reason": "absent", "expected_unit": "CASES",
            "population": measurement["population"], "value": 0}
    elif mutation == "hash":
        payload["state_hash"] = "0" * 64
    elif mutation == "unit":
        project["mutation"]["affected_cases"]["unit"] = "UQFPKM"
    elif mutation == "release":
        payload["entity"]["release"] = "different"
    elif mutation == "schema":
        payload["schema_version"] = 3
    else:
        payload["kind"] = "EVIDENCE_STATE"
    with pytest.raises(ContractError):
        read_state(canonical_json(payload))


@pytest.mark.parametrize("data", [b'{"schema_version":4,"schema_version":4}', b'{"x":NaN}',
                                  b'{"schema_version":4,"provider_score":1e9999}', b'\xff'])
def test_invalid_json_rejected(data):
    with pytest.raises(ContractError):
        read_state(data)
