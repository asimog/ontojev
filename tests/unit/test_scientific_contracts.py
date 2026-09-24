"""Stage 1 domain invariants. All data here is synthetic and offline."""

import json
from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from cancerjev.domain.codecs import (
    evidence_identity,
    read_evidence,
    read_measurement,
    read_state,
    state_identity,
    write_evidence,
    write_state,
)
from cancerjev.domain.evidence import (
    ActionRef,
    CheckOutcome,
    CheckSummary,
    EvidenceCheck,
    EvidenceStateV3,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
    Coverage,
    EntityRef,
    MethodParameters,
    MethodRef,
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
    canonical_bytes,
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
    StatisticalStateV3,
    UnavailableLane,
)
from cancerjev.research.specs import (
    LUAD_RESEARCH_V1,
    CnvLaneSpec,
    ExpressionLaneSpec,
    GeneUniverseSpec,
    MutationLaneSpec,
    ResearchSpecV2,
    ScientificLimits,
    research_spec_v2_from_dict,
)
from cancerjev.science.methods import ScienceError, metric

GENE = "ENSG00000141510"
FRAME = PopulationFrame("TCGA-LUAD", "TCGA-LUAD", PopulationUnit.CASE, ("a", "b"), ("a", "b"), "declared synthetic frame")
ENTITY = EntityRef(GENE, "TP53", "synthetic-release")
SOURCE = ScientificSource("/analysis", "a" * 64, "b" * 64, "1", ENTITY.release, Acquisition.COMPLETE)
QUALITY = Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.VERIFIED, ())
COUNT_METHOD = MethodRef("COUNT", "1", Unit.CASES, MethodParameters(), "unique cases", "none", "count", "missing is unavailable", ())
SCALAR_METHOD = replace(COUNT_METHOD, method_id="LOG2", unit=Unit.LOG2_UQFPKM_PLUS_ONE,
                        parameters=MethodParameters(pseudocount=1), transform="log2(UQFPKM+1)", estimator="local summary")


def observed_count(value=1, **changes):
    return ObservedCount(value, **{"unit": Unit.CASES, "population": FRAME, "method": COUNT_METHOD,
                                  "sources": (SOURCE,), **changes})


def scalar(value=3, **changes):
    return ObservedScalar(value, **{"unit": Unit.LOG2_UQFPKM_PLUS_ONE, "population": FRAME,
                                   "method": SCALAR_METHOD, "sources": (SOURCE,), **changes})


def state():
    expression = ExpressionSummaryResult(
        (ExpressionValue("a", 3), ExpressionValue("b", 15)), Coverage(FRAME, ("a", "b"), ("a", "b"), (), None),
        scalar(3), scalar(2 ** 0.5, method=replace(SCALAR_METHOD, parameters=MethodParameters(1, 1))),
        scalar(2), scalar(4), QUALITY, (SOURCE,), ENTITY,
    )
    return StatisticalStateV3(
        ENTITY, FRAME, Universe((GENE,), "synthetic indexed slice", ENTITY.release, "protein_coding", "GENE_ID_ASC", 0, 1, 30, True),
        MutationCountResult(observed_count(1), observed_count(2), FRAME, QUALITY, ENTITY), expression,
        UnavailableLane(Lane.CNV, False, UnavailableStatus.NOT_ACQUIRED, "disabled"), QUALITY, (SOURCE,),
    )


def evidence(revision=0):
    baseline = EvidenceStateV3(ENTITY, state_identity(state()), None, 0, None, (), QUALITY, (SOURCE,))
    if revision == 0:
        return baseline
    check = EvidenceCheck("CHECK", "INTEGRITY", "1", CheckOutcome.VERIFIED, "input retained",
                          (baseline.accepted_state_hash,), None, 2)
    return replace(baseline, parent_evidence_hash=evidence_identity(baseline), revision_index=revision,
                   action=ActionRef("CHECK_EVIDENCE_INTEGRITY_V1", "1"), checks=(check,))


@pytest.mark.parametrize("value", [None, True, False, -1, 1.5, "1", float("inf"), float("nan")])
def test_observed_count_rejects_invalid_values(value):
    with pytest.raises(ContractError):
        observed_count(value)


@pytest.mark.parametrize("value", [None, True, False, -1, "1", float("inf"), float("-inf"), float("nan"), 10 ** 1000])
def test_observed_scalar_rejects_invalid_values(value):
    with pytest.raises(ContractError):
        scalar(value)


@pytest.mark.parametrize("status", list(UnavailableStatus))
def test_unavailable_has_no_value_and_preserves_distinct_status(status):
    result = UnavailableMeasurement(status, "explicit reason", Unit.CASES, FRAME)
    payload = json.loads(canonical_bytes(asdict(result)))
    assert read_measurement(payload) == result
    assert not hasattr(result, "value")
    with pytest.raises(ContractError):
        read_measurement({**payload, "value": 0})
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


def test_counts_cannot_exceed_their_declared_frame():
    with pytest.raises(ContractError):
        MutationCountResult(observed_count(3), observed_count(2), FRAME, QUALITY, ENTITY)
    with pytest.raises(ContractError):
        observed_count(method=SCALAR_METHOD)


@pytest.mark.parametrize("lane", ["mutation", "expression"])
def test_state_cannot_mix_gene_results(lane):
    original = state()
    wrong = replace(getattr(original, lane), entity=replace(ENTITY, gene_id="ENSG00000000001"))
    with pytest.raises(ContractError):
        replace(original, **{lane: wrong})


def test_nested_collections_are_immutable():
    result = state()
    with pytest.raises(FrozenInstanceError):
        result.entity.symbol = "OTHER"
    with pytest.raises(TypeError):
        result.expression.values[0] = ExpressionValue("a", 99)
    with pytest.raises(ContractError):
        replace(result, sources=[SOURCE])
    with pytest.raises(ContractError):
        replace(result.frame, examined_ids=["a", "b"])
    with pytest.raises(ContractError):
        replace(result.expression, values=list(result.expression.values))
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


def test_summary_sample_size_and_context_are_checked_not_imputed():
    result = state().expression
    with pytest.raises(ContractError):
        replace(result, values=())
    with pytest.raises(ContractError):
        replace(result, minimum=scalar(9))
    unavailable = UnavailableMeasurement(UnavailableStatus.INSUFFICIENT, "n<2", Unit.LOG2_UQFPKM_PLUS_ONE, FRAME)
    one = replace(result, values=(ExpressionValue("a", 3),),
                  coverage=Coverage(FRAME, ("a",), ("a",), (MissingGroup("absent", ("b",)),), None),
                  sample_sd=unavailable)
    with pytest.raises(ContractError):
        replace(one, sample_sd=scalar())
    with pytest.raises(ContractError):
        replace(result, sources=())


def test_quality_axes_and_disabled_lanes_remain_separate():
    q = Quality(Acquisition.COMPLETE, Sufficiency.INSUFFICIENT, Compatibility.UNVERIFIED, ("no usable measurements",))
    assert q.acquisition == Acquisition.COMPLETE
    with pytest.raises(ContractError):
        replace(q, reasons=())
    with pytest.raises(ContractError):
        UnavailableLane(Lane.EXPRESSION, False, UnavailableStatus.NOT_OBSERVED, "disabled")
    with pytest.raises(ContractError):
        replace(state(), mutation=UnavailableLane(Lane.CNV, False, UnavailableStatus.NOT_ACQUIRED, "disabled"))


def test_universe_slice_is_not_genome_completeness():
    universe = state().universe
    assert universe.complete and universe.reported_total > len(universe.ordered_ids)
    with pytest.raises(ContractError):
        replace(universe, ordered_ids=())
    with pytest.raises(ContractError):
        replace(universe, requested_limit=1001)
    with pytest.raises(ContractError):
        replace(state(), entity=replace(ENTITY, gene_id="ENSG00000000001"))


def test_cnv_retains_raw_categories_and_missing_sample_context():
    occurrence = CnvOccurrence("occurrence", "cnv", "a", GENE, "Loss", None, None, None, None)
    assert occurrence.category == CnvCategory.LOSS_UNSPECIFIED
    assert replace(occurrence, raw_category="Novel").category == CnvCategory.UNSUPPORTED_CATEGORY
    cnv = CnvOccurrenceResult(ENTITY, FRAME, (occurrence,), (SOURCE,), QUALITY)
    result = replace(state(), cnv=cnv)
    assert read_state(write_state(result)) == result
    with pytest.raises(ContractError):
        replace(cnv, occurrences=(occurrence, occurrence))
    with pytest.raises(ContractError):
        replace(cnv, occurrences=(replace(occurrence, case_id="outside"),))


def test_v3_state_roundtrip_and_operational_identity_exclusion():
    original = state()
    operational = OperationalSource(SOURCE, "attempt", "artifact", "2026-09-25T00:00:00Z", 10, None, 200, False)
    changed = replace(original, operational_sources=(operational,))
    assert state_identity(original) == state_identity(changed)
    changed_again = replace(changed, operational_sources=(replace(operational, attempt_id="retry", artifact_id="other",
                                                                 retrieved_at="2027-01-01T00:00:00Z", bytes_read=999,
                                                                 latency_ms=3, cache_hit=True),))
    assert state_identity(original) == state_identity(changed_again)
    assert write_state(original) != write_state(changed)
    assert read_state(write_state(changed), expected_hash=state_identity(original)) == changed
    assert state_identity(replace(original, frame=original.frame)) == state_identity(original)
    assert state_identity(replace(original, universe=replace(original.universe, filter_description="different tested scope"))) != state_identity(original)
    assert state_identity(replace(original, mutation=replace(original.mutation, affected_cases=observed_count(0)))) != state_identity(original)
    method_change = replace(original.mutation, affected_cases=observed_count(method=replace(COUNT_METHOD, version="2")))
    assert state_identity(replace(original, mutation=method_change)) != state_identity(original)
    with pytest.raises(ContractError):
        replace(original, operational_sources=(replace(operational, source=replace(SOURCE, response_hash="c" * 64)),))


@pytest.mark.parametrize("revision", [0, 1, 2])
def test_evidence_roundtrip_and_check_identity(revision):
    original = evidence(revision)
    assert read_evidence(write_evidence(original), expected_hash=evidence_identity(original)) == original
    if revision:
        check = replace(original.checks[0], outcome=CheckOutcome.CONTRADICTED, reason="input mismatch")
        assert evidence_identity(replace(original, checks=(check,))) != evidence_identity(original)


def test_evidence_summary_and_revision_consistency():
    original = evidence(1)
    with pytest.raises(ContractError):
        CheckSummary(3, 1, 1, 0)
    with pytest.raises(ContractError):
        replace(original, checks=original.checks * 2)
    with pytest.raises(ContractError):
        replace(original, parent_evidence_hash=None)
    with pytest.raises(ContractError):
        replace(original, revision_index=3)
    with pytest.raises(ContractError):
        replace(original.checks[0], outcome=CheckOutcome.NOT_OBSERVED)
    payload = json.loads(write_evidence(original))
    payload["summary"] = {"total": 1, "verified": 0, "contradicted": 1, "not_observed": 0}
    with pytest.raises(ContractError, match="summary"):
        read_evidence(canonical_bytes(payload))


@pytest.mark.parametrize("schema", [None, True, "3", 0, 4, 3.0])
@pytest.mark.parametrize("reader", [read_state, read_evidence])
def test_unknown_or_coerced_schema_fails_explicitly(schema, reader):
    with pytest.raises(ContractError) as error:
        reader(canonical_bytes({"schema_version": schema}))
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


@pytest.mark.parametrize("data", [b'{"schema_version":3,"schema_version":3}', b'{', b'[]', b'{"x":NaN}', b'\xff'])
def test_invalid_json_rejected(data):
    with pytest.raises(ContractError):
        read_state(data)


def test_overflowing_json_float_is_not_silently_accepted():
    with pytest.raises(ContractError):
        read_state(b'{"schema_version":2,"provider_score":1e9999}')


@pytest.mark.parametrize("mutation", ["null", "bool", "unexpected", "unavailable_value", "hash", "unit", "release"])
def test_v3_boundary_rejects_malformed_records(mutation):
    payload = json.loads(write_state(state()))
    if mutation in ("null", "bool"):
        payload["mutation"]["affected_cases"]["value"] = None if mutation == "null" else True
    elif mutation == "unexpected":
        payload["mutation"]["invented_metric"] = 20
    elif mutation == "unavailable_value":
        payload["cnv"]["value"] = 0
    elif mutation == "hash":
        payload["state_hash"] = "0" * 64
    elif mutation == "unit":
        payload["mutation"]["affected_cases"]["unit"] = "UQFPKM"
    elif mutation == "release":
        payload["entity"]["release"] = "different"
    with pytest.raises(ContractError):
        read_state(canonical_bytes(payload))


@pytest.mark.parametrize("value", [None, True, -1, 0.5, "1"])
def test_legacy_metric_constructor_closes_observed_value_hole(value):
    with pytest.raises(ScienceError):
        metric("affected", value, "cases")
    assert metric("affected", 0, "cases")["value"] == 0


def spec():
    return ResearchSpecV2("TEST_V2", "descriptive discovery", LUAD_RESEARCH_V1.cohort, GeneUniverseSpec(),
                          MutationLaneSpec(), ExpressionLaneSpec(), CnvLaneSpec(), ScientificLimits(),
                          ("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"))


def test_research_composition_does_not_enable_runtime_or_expand_authority():
    result = spec()
    assert not result.expression.enabled and not result.cnv.enabled
    assert LUAD_RESEARCH_V1.spec_id == "LUAD_RESEARCH_V1"
    with pytest.raises(ContractError):
        replace(result, allowed_actions=("INFER_CAUSALITY",))
    with pytest.raises(ContractError):
        replace(result, wide_policy="experimental")
    with pytest.raises(ContractError):
        ExpressionLaneSpec(enabled=False, independent_arm=True)
    with pytest.raises(ContractError):
        replace(result, mutation=MutationLaneSpec(False), cnv=CnvLaneSpec(True))
    with pytest.raises(ContractError):
        replace(result.limits, max_survivors=11)
    with pytest.raises(ContractError):
        replace(result.universe, limit=True)


def test_research_composition_boundary_is_strict_and_versioned():
    result = spec()
    payload = json.loads(canonical_bytes(result.as_dict()))
    assert research_spec_v2_from_dict(payload) == result
    with pytest.raises(ContractError):
        research_spec_v2_from_dict({**payload, "endpoint": "/arbitrary"})
    with pytest.raises(ContractError):
        research_spec_v2_from_dict({**payload, "schema_version": 1})
    payload["mutation"]["enabled"] = "false"
    with pytest.raises(ContractError):
        research_spec_v2_from_dict(payload)
