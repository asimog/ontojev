"""Deterministic held-data descriptors shared by discovery and registered actions."""

from __future__ import annotations

import math
from typing import Any

from cancerjev.domain.discovery import (
    CNV_DROP_REASON,
    CNV_JEV_REVIEW_CONFLICT_TRIGGER,
    CNV_RETAIN_MIN_AMPLIFICATION_CASES,
    CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES,
    CNV_RETAIN_REASON,
    CNV_SUMMARY_METHOD_ID,
    CNV_SUMMARY_VERSION,
    EXPRESSION_DROP_INSUFFICIENT_REASON,
    EXPRESSION_DROP_OBSERVED_REASON,
    EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO,
    EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER,
    EXPRESSION_RETAIN_REASON,
    EXPRESSION_TAIL_METHOD_ID,
    EXPRESSION_TAIL_VERSION,
    CnvCategorySummary,
    CnvDisposition,
    CnvGeneEvidence,
    ExpressionDisposition,
    ExpressionTailDescriptor,
)
from cancerjev.domain.measurements import MethodIdentityRef, MetricAvailability, digest
from cancerjev.domain.scientific import (
    CnvCategory,
    CnvOccurrenceResult,
    ExpressionSummaryResult,
    UnavailableLane,
)


def _linear_quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def expression_tail_descriptor(
    outcome: ExpressionSummaryResult | UnavailableLane,
    spec: Any,
) -> ExpressionTailDescriptor:
    parameters = {
        "minimum_n": spec.minimum_tail_n,
        "quantile_rule": spec.quantile_rule,
        "iqr_multiplier": spec.iqr_multiplier,
        "input_unit": spec.input_unit,
        "transform": spec.transform,
    }
    method = MethodIdentityRef(
        EXPRESSION_TAIL_METHOD_ID, EXPRESSION_TAIL_VERSION, digest(parameters))
    if isinstance(outcome, UnavailableLane):
        return ExpressionTailDescriptor(
            MetricAvailability.NOT_OBSERVED, outcome.reason, None, None, None, None,
            (), (), 0, method,
        )
    transformed = sorted(
        (math.log2(value.uqfpkm + 1.0), value.case_id) for value in outcome.values)
    if len(transformed) < spec.minimum_tail_n:
        return ExpressionTailDescriptor(
            MetricAvailability.INSUFFICIENT, "INSUFFICIENT_FINITE_VALUES", None, None, None, None,
            (), (), len(transformed), method,
        )
    ordered_values = [value for value, _ in transformed]
    q1 = _linear_quantile(ordered_values, 0.25)
    q3 = _linear_quantile(ordered_values, 0.75)
    iqr = q3 - q1
    if iqr == 0:
        return ExpressionTailDescriptor(
            MetricAvailability.UNAVAILABLE, "DEGENERATE_REFERENCE", None, None, None, None,
            (), (), len(transformed), method,
        )
    lower_fence = q1 - spec.iqr_multiplier * iqr
    upper_fence = q3 + spec.iqr_multiplier * iqr
    lower_ids = tuple(sorted(case_id for value, case_id in transformed if value < lower_fence))
    upper_ids = tuple(sorted(case_id for value, case_id in transformed if value > upper_fence))
    return ExpressionTailDescriptor(
        MetricAvailability.OBSERVED, None, q1, q3, lower_fence, upper_fence,
        lower_ids, upper_ids, len(transformed), method,
    )


def cnv_category_summaries(
    outcome: CnvOccurrenceResult,
) -> tuple[tuple[CnvCategorySummary, ...], tuple[str, ...]]:
    raw_categories = sorted({occurrence.raw_category for occurrence in outcome.occurrences})
    categories = tuple(
        CnvCategorySummary(
            raw_category,
            next(occurrence.category for occurrence in outcome.occurrences
                 if occurrence.raw_category == raw_category),
            tuple(sorted({occurrence.case_id for occurrence in outcome.occurrences
                          if occurrence.raw_category == raw_category})),
        )
        for raw_category in raw_categories
    )
    labels_by_case: dict[str, set[str]] = {}
    for occurrence in outcome.occurrences:
        labels_by_case.setdefault(occurrence.case_id, set()).add(occurrence.raw_category)
    conflicts = tuple(sorted(
        case_id for case_id, labels in labels_by_case.items() if len(labels) > 1))
    return categories, conflicts


def cnv_summary_method(parameters: dict[str, object]) -> MethodIdentityRef:
    return MethodIdentityRef(CNV_SUMMARY_METHOD_ID, CNV_SUMMARY_VERSION, digest(parameters))


def expression_lane_disposition(
    outcome: ExpressionSummaryResult | UnavailableLane,
    tail: ExpressionTailDescriptor,
) -> tuple[ExpressionDisposition, str, str | None]:
    """Declared expression-lane disposition; descriptive-only and deterministic.

    RETAIN = an observed tail eligible at the declared minimum; DROP = no observed
    values or an ineligible tail; JEV_REVIEW = the declared extreme-tail asymmetry
    trigger (both tails present and the larger at least
    ``EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO`` times the smaller).
    """
    if not isinstance(outcome, ExpressionSummaryResult):
        return ExpressionDisposition.DROP, EXPRESSION_DROP_OBSERVED_REASON, None
    if tail.availability is not MetricAvailability.OBSERVED:
        return ExpressionDisposition.DROP, EXPRESSION_DROP_INSUFFICIENT_REASON, None
    lower = len(tail.lower_case_ids)
    upper = len(tail.upper_case_ids)
    if (lower and upper
            and max(lower, upper) >= EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO * min(lower, upper)):
        return (ExpressionDisposition.JEV_REVIEW, EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER,
                EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER)
    return ExpressionDisposition.RETAIN, EXPRESSION_RETAIN_REASON, None


def cnv_lane_disposition(evidence: CnvGeneEvidence) -> tuple[CnvDisposition, str, str | None]:
    """Declared recurrence disposition on merged evidence; case-count constants, no p-values.

    RETAIN = recurrent amplification or homozygous deletion at the declared
    category-specific case-count thresholds; JEV_REVIEW = a recurrent gene whose
    cases carry conflicting provider categories (conflicts are never resolved
    here); DROP = below the declared recurrence thresholds. Absence of an
    occurrence never reaches this function.
    """
    amplification_cases = sum(len(summary.case_ids) for summary in evidence.categories
                              if summary.category is CnvCategory.AMPLIFICATION)
    homozygous_deletion_cases = sum(len(summary.case_ids) for summary in evidence.categories
                                    if summary.category is CnvCategory.HOMOZYGOUS_DELETION)
    recurrent = (amplification_cases >= CNV_RETAIN_MIN_AMPLIFICATION_CASES
                 or homozygous_deletion_cases >= CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES)
    if not recurrent:
        return CnvDisposition.DROP, CNV_DROP_REASON, None
    if evidence.conflicting_case_ids:
        return (CnvDisposition.JEV_REVIEW, CNV_JEV_REVIEW_CONFLICT_TRIGGER,
                CNV_JEV_REVIEW_CONFLICT_TRIGGER)
    return CnvDisposition.RETAIN, CNV_RETAIN_REASON, None
