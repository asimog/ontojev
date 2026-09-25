"""Declared expression-lane dispositions and pre-run volume planning."""

from __future__ import annotations

import pytest

from cancerjev.domain.discovery import (
    EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO,
    EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER,
    EXPRESSION_RETAIN_REASON,
    ExpressionDiscoveryEntry,
    ExpressionDiscoverySpec,
    ExpressionDisposition,
    ExpressionRunPlan,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
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
    EntityRef,
    ExpressionSummaryResult,
    ExpressionValue,
    Lane,
    UnavailableLane,
)
from cancerjev.research.expression_discovery import _expression_run_plan
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.descriptors import expression_lane_disposition, expression_tail_descriptor

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
                        ("expression disposition test fixture",)),
        sources=_source(), entity=EntityRef(GENE_ID, "TP53", RELEASE),
    )


def _disposition(uqfpkm_by_case: dict[str, float]):
    outcome = _summary(uqfpkm_by_case)
    tail = expression_tail_descriptor(outcome, ExpressionDiscoverySpec())
    return expression_lane_disposition(outcome, tail), tail


def test_balanced_tails_retain_without_a_trigger():
    (disposition, reason, trigger), tail = _disposition(
        {f"case-{index:03d}": (0.0 if index < 5 else 63.0 if index >= 95 else 3.0
                              if index < 35 else 7.0)
         for index in range(100)})

    assert tail.availability is MetricAvailability.OBSERVED
    assert len(tail.lower_case_ids) == len(tail.upper_case_ids) == 5
    assert disposition is ExpressionDisposition.RETAIN
    assert reason == EXPRESSION_RETAIN_REASON
    assert trigger is None


def test_extreme_tail_asymmetry_goes_to_jev_review():
    (disposition, reason, trigger), tail = _disposition(
        {f"case-{index:03d}": (0.0 if index < 8 else 63.0 if index == 99 else 3.0
                              if index < 34 else 7.0)
         for index in range(100)})

    assert len(tail.lower_case_ids) == 8 and len(tail.upper_case_ids) == 1
    assert len(tail.lower_case_ids) >= EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO * len(
        tail.upper_case_ids)
    assert disposition is ExpressionDisposition.JEV_REVIEW
    assert reason == EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER
    assert trigger == EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER


def test_unobserved_outcome_and_insufficient_tail_drop_with_reasons():
    unavailable = UnavailableLane(Lane.EXPRESSION, True, UnavailableStatus.NOT_OBSERVED,
                                  "no observed values")
    unavailable_tail = expression_tail_descriptor(unavailable, ExpressionDiscoverySpec())
    disposition, reason, trigger = expression_lane_disposition(unavailable, unavailable_tail)
    assert disposition is ExpressionDisposition.DROP and reason == "EXPRESSION_NOT_OBSERVED"
    assert trigger is None

    (disposition, reason, trigger), tail = _disposition(
        {f"case-{index:03d}": float(index + 1) for index in range(5)})
    assert tail.availability is MetricAvailability.INSUFFICIENT
    assert disposition is ExpressionDisposition.DROP and reason == "INSUFFICIENT_VALID_VALUES"


def test_jev_review_entry_accepts_an_observed_asymmetric_tail():
    outcome = _summary(
        {f"case-{index:03d}": (0.0 if index < 8 else 63.0 if index == 99 else 3.0
                              if index < 34 else 7.0)
         for index in range(100)})
    tail = expression_tail_descriptor(outcome, ExpressionDiscoverySpec())
    disposition, reason, trigger = expression_lane_disposition(outcome, tail)
    entry = ExpressionDiscoveryEntry(EntityRef(GENE_ID, "TP53", RELEASE), outcome, tail,
                                     disposition, reason, trigger)

    assert entry.disposition is ExpressionDisposition.JEV_REVIEW
    assert entry.review_trigger == EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER


def test_run_plan_refuses_a_plan_beyond_the_declared_budget():
    with pytest.raises(ContractError):
        ExpressionRunPlan(gene_count=100_000, case_count=1_000, gene_batches=1_000,
                          case_batches=4, request_count=8_200, projected_bytes=8_200 * 200_000,
                          max_requests=1_500, max_bytes=384 * 1024 * 1024)

    with pytest.raises(ContractError):
        _expression_run_plan(LUAD_RESEARCH_V1, gene_count=100_000, case_count=1_000)


def test_run_plan_admits_the_declared_luad_scale():
    plan = _expression_run_plan(LUAD_RESEARCH_V1, gene_count=19_843, case_count=600)

    assert plan.gene_batches == 199 and plan.case_batches == 3
    assert plan.request_count == 1_400
    assert plan.projected_bytes <= plan.max_bytes
    assert plan.payload()["max_requests"] == 1_500
