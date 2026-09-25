"""Schema-4 reader boundary and typed availability. No legacy reader fallthrough.

An absent provider bucket, cell or column is never silently an observed zero: the
readers accept only the current schema and the typed objects keep unavailability
explicit through a round trip.
"""

import json
from dataclasses import replace

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
    EvidenceProvenance,
    EvidenceState,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    Acquisition,
    ContractError,
    MissingGroup,
    ObservedCount,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    ScientificSource,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
    canonical_bytes,
    digest,
)
from cancerjev.domain.scientific import ExpressionSummaryResult, Lane, UnavailableLane
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
FRAME = PopulationFrame("TCGA-LUAD", "TCGA-LUAD", PopulationUnit.CASE, ("a", "b"), ("a", "b"),
                        "declared synthetic frame")
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


def frame(project_id="TCGA-LUAD", *, cases=6, drop_columns=0, missing_cells=0, expression=True,
          missing_gene=False):
    case_records = [CaseRecord(case_id=f"{project_id}-case-{index:02d}", submitter_id=f"S-{index}",
                               project_id=project_id, sample_types=["Primary Tumor"])
                    for index in range(cases)]
    if expression:
        returned = case_records[: cases - drop_columns]
        coverage = ExpressionAvailability(
            cases={case.case_id: True for case in case_records},
            genes={GENE_ID: not missing_gene}, with_count=len(returned), without_count=0,
            missing_cases=[case.case_id for case in case_records[cases - drop_columns:]],
            missing_genes=[GENE_ID] if missing_gene else [], warnings=[])
        values = ExpressionValues(
            values={} if missing_gene else {GENE_ID: {
                case.case_id: (float(index + 1) if index >= missing_cells else None)
                for index, case in enumerate(returned)}},
            missing_case_ids=[case.case_id for case in case_records[cases - drop_columns:]],
            missing_gene_ids=[GENE_ID] if missing_gene else [], nonfinite_values=0, warnings=[])
        provider = ProviderSelection(
            genes={} if missing_gene else {
                GENE_ID: ProviderGene(gene_id=GENE_ID, symbol="TP53", median=2.5, stddev=0.3)},
            missing_genes=[GENE_ID] if missing_gene else [], warnings=[])
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


def minimal_evidence(state):
    accepted = state_identity(state)
    return EvidenceState(
        entity=state.entity, accepted_state_hash=accepted,
        source_state=SourceStateBinding("state-1", accepted, "artifact-1", "c" * 64),
        parent_evidence_hash=None, revision_index=0, action=None,
        puzzle=ResearchPuzzle("STATISTICAL_STATE_BASELINE", "What is supported?",
                              "The baseline is accepted evidence, not a judgment.", ()),
        checks=(), baseline_observations=(), project_evidence=(), missing_evidence=(),
        quality=state.quality, warnings=(),
        provenance=EvidenceProvenance(state.entity.release, state.sources, state.methods,
                                      state.environment_hash, "2",
                                      state.tested_context.examined_genes_hash, ()))


# ------------------------------------------------------- schema-4 strictness


@pytest.mark.parametrize("reader", [read_state, read_evidence])
@pytest.mark.parametrize("schema", [1, 2, 3, 5, 99, None, True, "4", 4.0, -1])
def test_every_other_schema_version_fails_closed(reader, schema):
    with pytest.raises(ContractError) as error:
        reader(canonical_bytes({"schema_version": schema}))
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_swapped_artifact_kind_fails_closed():
    state = build_state()
    payload = json.loads(write_state(state))
    payload["kind"] = "EVIDENCE_STATE"
    with pytest.raises(ContractError) as error:
        read_state(canonical_json(payload))
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"
    payload = json.loads(write_evidence(minimal_evidence(state)))
    payload["kind"] = "STATISTICAL_STATE"
    with pytest.raises(ContractError) as error:
        read_evidence(canonical_json(payload))
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_corrupted_stored_identity_fails_closed():
    state = build_state()
    payload = json.loads(write_state(state))
    payload["state_hash"] = "0" * 64
    with pytest.raises(ContractError):
        read_state(canonical_json(payload))
    evidence = minimal_evidence(state)
    payload = json.loads(write_evidence(evidence))
    payload["evidence_hash"] = "0" * 64
    with pytest.raises(ContractError):
        read_evidence(canonical_json(payload))


def test_tampered_measurement_with_stale_identity_fails_closed():
    state = build_state()
    payload = json.loads(write_state(state))
    payload["projects"][0]["mutation"]["affected_cases"]["value"] = 3
    with pytest.raises(ContractError):
        read_state(canonical_json(payload))
    evidence = minimal_evidence(state)
    payload = json.loads(write_evidence(evidence))
    payload["warnings"] = ["tampered after writing"]
    with pytest.raises(ContractError):
        read_evidence(canonical_json(payload), expected_hash=evidence_identity(evidence))


def test_readers_require_immutable_bytes():
    state = build_state()
    with pytest.raises(ContractError, match="immutable bytes"):
        read_state(bytearray(write_state(state)))
    with pytest.raises(ContractError, match="immutable bytes"):
        read_evidence(bytearray(write_evidence(minimal_evidence(state))))


@pytest.mark.parametrize("data", [b"{", b"[]", b"\xff", b'{"schema_version":4,"x":NaN}',
                                  b'{"schema_version":4,"x":1e9999}',
                                  b'{"schema_version":4,"schema_version":4}'])
def test_invalid_documents_fail_closed(data):
    with pytest.raises(ContractError):
        read_state(data)


# --------------------------------------------------------- typed availability


def test_absent_provider_bucket_is_unavailable_never_zero():
    state = build_state(frames=[frame("P1"), frame("P2")], counts={"P1": {GENE_ID: 2}})
    affected = state.projects[1].mutation.affected_cases
    assert isinstance(affected, UnavailableMeasurement)
    assert affected.status == UnavailableStatus.NOT_OBSERVED
    assert affected.reason == "PROJECT_NOT_IN_AGGREGATION"
    assert not isinstance(affected, ObservedCount)
    roundtrip = read_state(write_state(state), expected_hash=state_identity(state))
    assert roundtrip == state
    assert isinstance(roundtrip.projects[1].mutation.affected_cases, UnavailableMeasurement)


def test_explicit_observed_zero_round_trips_and_is_not_absence():
    state = build_state(counts={"TCGA-LUAD": {GENE_ID: 0}})
    affected = state.projects[0].mutation.affected_cases
    assert isinstance(affected, ObservedCount)
    assert affected.value == 0
    assert state.cross_project.affected_case_total.value == 0
    assert read_state(write_state(state), expected_hash=state_identity(state)) == state


def test_missing_gene_maps_to_an_unavailable_expression_lane():
    state = build_state(frames=[frame(missing_gene=True)])
    expression = state.projects[0].expression
    assert isinstance(expression, UnavailableLane)
    assert expression.lane == Lane.EXPRESSION and expression.enabled
    assert expression.status == UnavailableStatus.NOT_OBSERVED
    assert expression.reason == "GENE_ABSENT_FROM_VALUES"
    assert read_state(write_state(state)) == state


def test_missing_value_cells_are_counted_and_never_imputed_as_zero():
    state = build_state(frames=[frame(missing_cells=2)])
    expression = state.projects[0].expression
    assert isinstance(expression, ExpressionSummaryResult)
    coverage = expression.coverage
    assert coverage.missing == (MissingGroup("VALUE_MISSING_OR_NONFINITE",
                                             ("TCGA-LUAD-case-00", "TCGA-LUAD-case-01")),)
    assert len(coverage.valid_ids) == 4
    assert tuple(value.case_id for value in expression.values) == coverage.valid_ids
    assert read_state(write_state(state)) == state


def test_unreturned_case_column_is_missing_not_zero():
    state = build_state(frames=[frame(drop_columns=1)])
    coverage = state.projects[0].expression.coverage
    assert coverage.missing == (MissingGroup("CASE_COLUMN_NOT_RETURNED", ("TCGA-LUAD-case-05",)),)
    assert coverage.valid_ids == coverage.returned_ids
    assert "TCGA-LUAD-case-05" not in coverage.returned_ids


def test_unacquired_lane_stays_explicitly_unavailable():
    state = build_state(frames=[frame(expression=False)])
    expression = state.projects[0].expression
    assert isinstance(expression, UnavailableLane)
    assert expression.status == UnavailableStatus.NOT_ACQUIRED
    assert read_state(write_state(state)) == state


def test_partial_acquisition_cannot_claim_an_observed_zero():
    state = build_state(counts={"TCGA-LUAD": {GENE_ID: 0}})
    affected = state.projects[0].mutation.affected_cases
    partial = replace(affected.sources[0], acquisition=Acquisition.PARTIAL)
    with pytest.raises(ContractError):
        replace(affected, value=0, sources=(partial,))
    failed = replace(affected.sources[0], acquisition=Acquisition.FAILED)
    with pytest.raises(ContractError):
        replace(affected, value=1, sources=(failed,))


def test_unavailable_measurement_is_typed_without_a_zero_value():
    result = UnavailableMeasurement(UnavailableStatus.NOT_OBSERVED, "bucket absent", Unit.CASES,
                                    FRAME)
    assert not hasattr(result, "value")
    assert result.status == UnavailableStatus.NOT_OBSERVED
