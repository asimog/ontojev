"""Deterministic baseline and bounded Jev admission over typed states and judgments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.measurements import Acquisition, ObservedCount
from cancerjev.domain.scientific import StatisticalState
from cancerjev.jev.contracts import EvaluationRecord

BASELINE_POLICY_VERSION = "baseline-wide-v2"
JEV_POLICY_VERSION = "wide-policy-v2"
PROMOTION_LIMIT = 3
ADMISSION_MIN_WARRANTS = 0.60
ADMISSION_MIN_UNCERTAINTY = 0.50
ADMISSION_MIN_QUALITY = 0.40
ADMISSION_MAX_CONFOUND = 0.50
PRE_WIDE_POLICY_VERSION = "pre-wide-policy-v1"
PRE_WIDE_ORDERING_DESCRIPTION = (
    "affected_cases desc, mutation_observed desc, coverage_imbalance asc"
)

_ADMISSION_THRESHOLDS = {
    "warrants_deeper_investigation_min": ADMISSION_MIN_WARRANTS,
    "unresolved_uncertainty_material_min": ADMISSION_MIN_UNCERTAINTY,
    "evidence_quality_adequate_min": ADMISSION_MIN_QUALITY,
    "signal_explained_by_coverage_max": ADMISSION_MAX_CONFOUND,
}


@dataclass(frozen=True)
class RankingState:
    state_id: str
    state_hash: str
    gene_symbol: str | None
    affected_cases: float | int | None
    coverage_imbalance: bool
    completeness: str
    expression_availability: str
    pending_semantic_review: bool


def _expression_availability(state: StatisticalState) -> str:
    observed = state.cross_project.projects_with_expression_observation
    total = len(state.projects)
    if observed == total:
        return "OBSERVED"
    return "PARTIAL" if observed else "INSUFFICIENT"


def _ranking_state(record: StateRecord) -> RankingState:
    state = record.state
    project = state.projects[0] if len(state.projects) == 1 else None
    affected: float | int | None = None
    if project is not None and state.research.project_id in (None, project.population.frame.project_id):
        measurement = project.mutation.affected_cases
        if isinstance(measurement, ObservedCount):
            affected = measurement.value
    nominations = getattr(state, "nominations", None) or ()
    pending_review = (
        any(disposition == "JEV_REVIEW" for _, disposition in nominations)
        or "PENDING_SEMANTIC_REVIEW" in state.warnings
    )
    return RankingState(
        record.state_id, record.state_hash, state.gene_symbol, affected,
        state.cross_project.coverage_imbalance,
        "COMPLETE" if state.quality.acquisition is Acquisition.COMPLETE else "PARTIAL",
        _expression_availability(state),
        pending_review,
    )


def measured_ordering_key(record: StateRecord) -> tuple[float, int, int]:
    """Declared pre-Wide measured ordering key; no Jev, no ids, no hashes."""
    state = _ranking_state(record)
    affected = state.affected_cases
    return (
        -(affected if affected is not None else -1.0),
        -int(affected is not None),
        int(state.coverage_imbalance),
    )


def measured_dimensions(record: StateRecord) -> dict[str, object]:
    """The measured evidence behind one pre-Wide ordering key."""
    state = _ranking_state(record)
    return {
        "affected_cases": state.affected_cases,
        "mutation_observed": state.affected_cases is not None,
        "coverage_imbalance": state.coverage_imbalance,
    }


def baseline_ranking(states: list[StateRecord]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for raw_state in states:
        state = _ranking_state(raw_state)
        entries.append({
            "state_id": state.state_id,
            "state_hash": state.state_hash,
            "gene_symbol": state.gene_symbol,
            "dimensions": {
                "affected_cases": state.affected_cases,
                "mutation_observed": state.affected_cases is not None,
                "coverage_imbalance": state.coverage_imbalance,
            },
        })
    entries.sort(key=lambda entry: (
        -(entry["dimensions"]["affected_cases"]
          if entry["dimensions"]["affected_cases"] is not None else -1.0),
        -int(entry["dimensions"]["mutation_observed"]),
        entry["dimensions"]["coverage_imbalance"],
        entry["state_hash"],
    ))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return {
        "policy_version": BASELINE_POLICY_VERSION,
        "kind": "BASELINE",
        "ordering": "affected_cases desc, mutation_observed desc, coverage_imbalance asc, state_hash asc",
        "entries": entries,
        "top_state_ids": [entry["state_id"] for entry in entries[:PROMOTION_LIMIT]],
        "admitted_state_ids": [],
    }


def _applicable(evaluation: EvaluationRecord, question_id: str) -> bool:
    return evaluation.is_applicable(question_id)


def _eligibility_exclusions(state: RankingState) -> list[str]:
    reasons = []
    if state.pending_semantic_review:
        # Arm Jev is deferred: a state whose admission still depends on
        # JEV_REVIEW can never be promoted by favorable Wide answers.
        reasons.append("PENDING_SEMANTIC_REVIEW")
    if state.completeness != "COMPLETE":
        reasons.append("INCOMPLETE_ACQUISITION")
    if state.affected_cases is None:
        reasons.append("MUTATION_NOT_OBSERVED")
    if state.expression_availability not in {"OBSERVED", "PARTIAL"}:
        reasons.append("EXPRESSION_NOT_OBSERVED")
    return reasons


def _answer_probability(evaluation: EvaluationRecord, question_id: str) -> float | None:
    if not _applicable(evaluation, question_id):
        return None
    return evaluation.answers.probability(question_id) if evaluation.answers is not None else None


def _admission_exclusions(state: RankingState, evaluation: EvaluationRecord) -> list[str]:
    reasons = _eligibility_exclusions(state)
    if reasons:
        return reasons

    thresholds = (
        ("warrants_deeper_investigation", ADMISSION_MIN_WARRANTS),
        ("unresolved_uncertainty_material", ADMISSION_MIN_UNCERTAINTY),
        ("evidence_quality_adequate", ADMISSION_MIN_QUALITY),
    )
    for question_id, threshold in thresholds:
        probability = _answer_probability(evaluation, question_id)
        if probability is None:
            reasons.append(f"JUDGMENT_UNAVAILABLE:{question_id}")
        elif probability < threshold:
            reasons.append(f"BELOW_ADMISSION_THRESHOLD:{question_id}")

    if _applicable(evaluation, "signal_explained_by_coverage"):
        confound = _answer_probability(evaluation, "signal_explained_by_coverage")
        if confound is None:
            reasons.append("JUDGMENT_UNAVAILABLE:signal_explained_by_coverage")
        elif confound > ADMISSION_MAX_CONFOUND:
            reasons.append("ABOVE_ADMISSION_THRESHOLD:signal_explained_by_coverage")
    return reasons


def _raw_dimensions(evaluation: EvaluationRecord) -> dict[str, Any]:
    presentation = evaluation.boundary_representation()  # Ranking artifact presentation.
    answers = presentation.get("answers", {})
    dimensions = {
        question_id: answer.get("probability_yes")
        for question_id, answer in answers.items()
        if answer.get("kind") == "noul"
    }
    limitation = answers.get("dominant_limitation", {})
    if limitation.get("kind") == "choice":
        dimensions.update({
            "dominant_limitation": limitation["choice"],
            "dominant_limitation_confidence": limitation["confidence"],
            "dominant_limitation_probabilities": limitation["probabilities"],
        })
    dimensions["applicability"] = presentation.get("applicability", {})
    dimensions["cache_source_evaluation_id"] = presentation.get("cache_source_evaluation_id")
    return dimensions


def _ranking_probability(entry: dict[str, Any], question_id: str) -> float | None:
    dimensions = entry["dimensions"]
    if dimensions.get("applicability", {}).get(question_id, {}).get("applicable") is not True:
        return None
    # The judgment boundary records noul answers as validated probability floats
    # (jev.contracts.validate_answer), so a present question answer is a float.
    return cast(float | None, dimensions.get(question_id))


def _descending_probability(entry: dict[str, Any], question_id: str) -> float:
    probability = _ranking_probability(entry, question_id)
    return -probability if probability is not None else 1.0


def _ascending_probability(entry: dict[str, Any], question_id: str) -> float:
    probability = _ranking_probability(entry, question_id)
    return probability if probability is not None else 1.0


def jev_ranking(states: list[StateRecord], evaluations: list[EvaluationRecord]) -> dict[str, Any]:
    by_state = {evaluation.input_ref_id: evaluation for evaluation in evaluations}
    entries: list[dict[str, Any]] = []
    for raw_state in states:
        state = _ranking_state(raw_state)
        evaluation = by_state.get(state.state_id)
        error = evaluation.error_code if evaluation is not None else None
        exclusion_reasons = _eligibility_exclusions(state)
        if evaluation is None:
            exclusion_reasons.append("EVALUATION_MISSING")
        elif error is not None:
            exclusion_reasons.append("EVALUATION_FAILED")
        else:
            exclusion_reasons = _admission_exclusions(state, evaluation)
        dimensions = _raw_dimensions(evaluation) if evaluation is not None and error is None else {}
        entries.append({
            "state_id": state.state_id,
            "state_hash": state.state_hash,
            "gene_symbol": state.gene_symbol,
            "evaluation_id": evaluation.evaluation_id if evaluation is not None else None,
            "dimensions": {
                **dimensions,
                "affected_cases": state.affected_cases,
            },
            "qualified": not exclusion_reasons,
            "excluded_reason": "; ".join(exclusion_reasons) or None,
        })
    entries.sort(key=lambda entry: (
        not entry["qualified"],
        _descending_probability(entry, "warrants_deeper_investigation"),
        _descending_probability(entry, "unresolved_uncertainty_material"),
        _descending_probability(entry, "evidence_quality_adequate"),
        _ascending_probability(entry, "signal_explained_by_coverage"),
        -(entry["dimensions"].get("affected_cases")
          if entry["dimensions"].get("affected_cases") is not None else -1.0),
        entry["state_hash"],
    ))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank

    qualifiers = [entry for entry in entries if entry["qualified"]]
    admitted = [entry["state_id"] for entry in qualifiers[:PROMOTION_LIMIT]]
    decision = "ADMIT" if admitted else "ABSTAIN"
    return {
        "policy_version": JEV_POLICY_VERSION,
        "kind": "JEV",
        "ordering": (
            "qualified first, applicable warrants_deeper_investigation desc, "
            "applicable unresolved_uncertainty_material desc, applicable evidence_quality_adequate desc, "
            "applicable signal_explained_by_coverage asc, "
            "affected_cases desc, state_hash asc"
        ),
        "entries": entries,
        "admitted_state_ids": admitted,
        "admission": {
            "decision": decision,
            "thresholds": dict(_ADMISSION_THRESHOLDS),
            "promotion_limit": PROMOTION_LIMIT,
            "states": [
                {"state_id": entry["state_id"], "qualified": entry["qualified"],
                 "excluded_reason": entry["excluded_reason"]}
                for entry in entries
            ],
        },
    }
