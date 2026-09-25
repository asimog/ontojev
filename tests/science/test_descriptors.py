"""Deterministic descriptor contracts: fixed Tukey tails and CNV category summaries.

The descriptors are held-data arithmetic shared by Stage 5/6 discovery and the
registered descriptive actions. These tests protect the realistic failure
modes: unstable quantile interpolation, tie-order dependence, IQR=0 ranking,
and conflict/category folding that would sum overlapping case sets.
"""

from __future__ import annotations

from cancerjev.domain.discovery import (
    CNV_SUMMARY_METHOD_ID,
    CNV_SUMMARY_VERSION,
    EXPRESSION_TAIL_METHOD_ID,
    EXPRESSION_TAIL_VERSION,
    ExpressionDiscoverySpec,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    Coverage,
    MetricAvailability,
    PopulationFrame,
    PopulationUnit,
    Quality,
    ScientificSource,
    Sufficiency,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
)
from cancerjev.domain.scientific import (
    CnvOccurrence,
    CnvOccurrenceResult,
    EntityRef,
    ExpressionSummaryResult,
    ExpressionValue,
    Lane,
    UnavailableLane,
)
from cancerjev.science.descriptors import (
    cnv_category_summaries,
    cnv_summary_method,
    expression_tail_descriptor,
)

RELEASE = "Data Release 46.0 - August 10, 2026"
GENE_ID = "ENSG00000141510"


def _frame(case_ids: tuple[str, ...]) -> PopulationFrame:
    return PopulationFrame("TCGA-LUAD", "TCGA-LUAD", PopulationUnit.CASE,
                           tuple(sorted(case_ids)), None, "ALL_CASES_PAGINATED")


def _source() -> tuple[ScientificSource, ...]:
    return (ScientificSource(
        endpoint="/gene_expression/values", request_hash="a" * 64, response_hash="b" * 64,
        parser_version="gdc-parser-v1", release=RELEASE, acquisition=Acquisition.COMPLETE),)


def _summary(uqfpkm_by_case: dict[str, float]) -> ExpressionSummaryResult:
    case_ids = tuple(sorted(uqfpkm_by_case))
    frame = _frame(case_ids)
    unavailable = UnavailableMeasurement(
        UnavailableStatus.NOT_OBSERVED, "TEST_NOT_COMPUTED", Unit.LOG2_UQFPKM_PLUS_ONE, frame)
    return ExpressionSummaryResult(
        values=tuple(ExpressionValue(case_id, uqfpkm_by_case[case_id]) for case_id in case_ids),
        coverage=Coverage(frame, case_ids, case_ids, (), None),
        median=unavailable, sample_sd=unavailable, minimum=unavailable, maximum=unavailable,
        quality=Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.UNVERIFIED,
                        ("descriptor test fixture",)),
        sources=_source(), entity=EntityRef(GENE_ID, "TP53", RELEASE),
    )


def _values(uqfpkm: list[float]) -> dict[str, float]:
    return {f"{GENE_ID}-case-{index:04d}": value for index, value in enumerate(uqfpkm)}


def test_observed_tail_matches_the_fixed_linear_rule_and_sorts_ties():
    # log2(uqfpkm+1) = k exactly for uqfpkm = 2**k - 1.
    values = _values([2.0 ** k - 1.0 for k in range(21)] + [2.0 ** 100 - 1.0])
    descriptor = expression_tail_descriptor(_summary(values), ExpressionDiscoverySpec())
    assert descriptor.availability is MetricAvailability.OBSERVED
    assert descriptor.valid_n == 22
    assert descriptor.q1 == 5.25 and descriptor.q3 == 15.75
    assert descriptor.lower_fence == -10.5 and descriptor.upper_fence == 31.5
    assert descriptor.lower_case_ids == ()
    assert descriptor.upper_case_ids == (f"{GENE_ID}-case-0021",)
    assert descriptor.method.method_id == EXPRESSION_TAIL_METHOD_ID
    assert descriptor.method.version == EXPRESSION_TAIL_VERSION


def test_quantiles_interpolate_between_observations_instead_of_snapping():
    values = _values([2.0 ** k - 1.0 for k in range(22)])
    descriptor = expression_tail_descriptor(_summary(values), ExpressionDiscoverySpec())
    assert descriptor.q1 == 5.25 and descriptor.q3 == 15.75
    assert descriptor.lower_fence == -10.5 and descriptor.upper_fence == 31.5
    assert descriptor.lower_case_ids == () and descriptor.upper_case_ids == ()


def test_upper_tail_membership_uses_transformed_value_not_rank_order():
    # 30 zeros, then 40 (x5) and 50 (x5): q1=1, q3=10.75, upper fence 25.375.
    values = _values([1.0] * 30 + [2.0 ** 40 - 1.0] * 5 + [2.0 ** 50 - 1.0] * 5)
    descriptor = expression_tail_descriptor(_summary(values), ExpressionDiscoverySpec())
    assert descriptor.q1 == 1.0 and descriptor.q3 == 10.75
    assert descriptor.lower_fence == -13.625 and descriptor.upper_fence == 25.375


def test_fewer_than_twenty_values_are_insufficient_not_zero_tailed():
    values = _values([1.0 + index for index in range(19)])
    descriptor = expression_tail_descriptor(_summary(values), ExpressionDiscoverySpec())
    assert descriptor.availability is MetricAvailability.INSUFFICIENT
    assert descriptor.reason == "INSUFFICIENT_FINITE_VALUES"
    assert descriptor.valid_n == 19
    assert descriptor.q1 is None and descriptor.upper_case_ids == ()


def test_zero_iqr_is_a_degenerate_reference_never_a_ranking():
    values = _values([1.0] * 25)
    descriptor = expression_tail_descriptor(_summary(values), ExpressionDiscoverySpec())
    assert descriptor.availability is MetricAvailability.UNAVAILABLE
    assert descriptor.reason == "DEGENERATE_REFERENCE"
    assert descriptor.q1 is None and descriptor.upper_case_ids == ()


def test_unavailable_lane_is_not_observed_with_no_tail_values():
    lane = UnavailableLane(Lane.EXPRESSION, True, UnavailableStatus.NOT_ACQUIRED,
                           "EXPRESSION_VALUES_NOT_ACQUIRED")
    descriptor = expression_tail_descriptor(lane, ExpressionDiscoverySpec())
    assert descriptor.availability is MetricAvailability.NOT_OBSERVED
    assert descriptor.reason == "EXPRESSION_VALUES_NOT_ACQUIRED"
    assert descriptor.valid_n == 0


def _cnv_result() -> CnvOccurrenceResult:
    gene = EntityRef(GENE_ID, "TP53", RELEASE)
    examined = tuple(f"{GENE_ID}-case-{index:04d}" for index in range(4))
    frame = _frame(examined)
    source = (ScientificSource(
        endpoint="/cnv_occurrences", request_hash="c" * 64, response_hash="d" * 64,
        parser_version="gdc-cnv-v1", release=RELEASE, acquisition=Acquisition.COMPLETE),)
    quality = Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.UNVERIFIED,
                      ("descriptor test fixture",))
    occurrences = (
        CnvOccurrence("occ-0", "cnv-occ-0", examined[0], GENE_ID, "Gain", "file-0", "ASCAT3",
                      "sample-a", 4.0),
        CnvOccurrence("occ-1", "cnv-occ-1", examined[1], GENE_ID, "Gain", "file-1", "ASCAT3",
                      None, 4.0),
        CnvOccurrence("occ-2", "cnv-occ-2", examined[0], GENE_ID, "Loss", "file-2", "ASCAT3",
                      None, 2.0),
        CnvOccurrence("occ-3", "cnv-occ-3", examined[2], GENE_ID, "Loss", "file-3", "ASCAT3",
                      None, None),
    )
    return CnvOccurrenceResult(gene, frame, occurrences, source, quality)


def test_cnv_category_summaries_keep_exact_categories_and_conflicts_distinct():
    result = _cnv_result()
    categories, conflicts = cnv_category_summaries(result)
    assert [(item.raw_category, len(item.case_ids)) for item in categories] == [
        ("Gain", 2), ("Loss", 2)]
    gain = categories[0]
    assert gain.category.value == "GAIN"
    assert set(gain.case_ids) == {f"{GENE_ID}-case-0000", f"{GENE_ID}-case-0001"}
    loss = categories[1]
    assert loss.category.value == "LOSS_UNSPECIFIED"
    assert set(loss.case_ids) == {f"{GENE_ID}-case-0000", f"{GENE_ID}-case-0002"}
    assert conflicts == (f"{GENE_ID}-case-0000",)
    # Overlapping category case sets are never summed: 3 unique positive cases.
    assert len({case_id for item in categories for case_id in item.case_ids}) == 3


def test_cnv_summary_method_is_pinned():
    method = cnv_summary_method({"category_field": "cnv.cnv_change_5_category"})
    assert method.method_id == CNV_SUMMARY_METHOD_ID
    assert method.version == CNV_SUMMARY_VERSION
    assert len(method.parameters_hash) == 64