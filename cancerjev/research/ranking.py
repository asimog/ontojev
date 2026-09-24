"""Deterministic baseline and bounded Jev admission over persisted judgments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cancerjev.domain.state_summary import StateSummary
from cancerjev.jev.contracts import EvaluationRecord

BASELINE_POLICY_VERSION = "baseline-wide-v2"
JEV_POLICY_VERSION = "wide-policy-v2"
PROMOTION_LIMIT = 3
ADMISSION_MIN_WARRANTS = 0.60
ADMISSION_MIN_UNCERTAINTY = 0.50
ADMISSION_MIN_QUALITY = 0.40
ADMISSION_MAX_CONFOUND = 0.50

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
    gene_symbol: str
    affected_cases: float | int | None
    coverage_imbalance: bool
    completeness: str
    expression_availability: str


def _ranking_state(state: StateSummary | dict[str, Any]) -> RankingState:
    if isinstance(state, StateSummary):
        project = state.projects[0] if len(state.projects) == 1 else None
        affected = project.affected_cases if project and state.project_id in (None, project.project_id) else None
        return RankingState(state.state_id, state.scientific_hash, state.gene_symbol, affected,
                            state.coverage_imbalance, state.completeness, state.expression_availability)
    mutation, scope = _project_result(state)
    return RankingState(state["state_id"], state["state_hash"], state["entity"]["gene_symbol"],
                        _metric_value(mutation.get("affected_case_count")), scope["coverage_imbalance"],
                        state["quality"]["completeness"], state["expression"]["availability"])


def _metric_value(metric: dict[str, Any] | None) -> float | None:
    if metric is None or metric.get("availability") != "OBSERVED":
        return None
    return metric.get("value")


def _project_result(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    project_ids = state["scope"]["projects"]
    project_id = state["scope"].get("project_id")
    if len(project_ids) != 1:
        return {}, state["cross_project"]
    project_id = project_id or project_ids[0]
    if project_id != project_ids[0]:
        return {}, state["cross_project"]
    mutation = next(
        (result for result in state["mutation"]["project_results"] if result["project_id"] == project_id),
        {},
    )
    return mutation, state["cross_project"]


def baseline_ranking(states: list[StateSummary] | list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
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


def _applicable(evaluation: EvaluationRecord | dict[str, Any], question_id: str) -> bool:
    if isinstance(evaluation, EvaluationRecord):
        return evaluation.is_applicable(question_id)
    return evaluation.get("applicability", {}).get(question_id, {}).get("applicable") is True


def _eligibility_exclusions(state: RankingState) -> list[str]:
    reasons = []
    if state.completeness != "COMPLETE":
        reasons.append("INCOMPLETE_ACQUISITION")
    if state.affected_cases is None:
        reasons.append("MUTATION_NOT_OBSERVED")
    if state.expression_availability not in {"OBSERVED", "PARTIAL"}:
        reasons.append("EXPRESSION_NOT_OBSERVED")
    return reasons


def _answer_probability(evaluation: EvaluationRecord | dict[str, Any], question_id: str) -> float | None:
    if not _applicable(evaluation, question_id):
        return None
    if isinstance(evaluation, EvaluationRecord):
        return evaluation.answers.probability(question_id) if evaluation.answers is not None else None
    answer = evaluation.get("answers", {}).get(question_id)
    if not answer or answer.get("kind") != "noul":
        return None
    return answer["probability_yes"]


def _admission_exclusions(state: RankingState, evaluation: EvaluationRecord | dict[str, Any]) -> list[str]:
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


def _raw_dimensions(evaluation: EvaluationRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(evaluation, EvaluationRecord):
        evaluation = evaluation.boundary_representation()  # Ranking artifact presentation.
    answers = evaluation.get("answers", {})
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
    dimensions["applicability"] = evaluation.get("applicability", {})
    dimensions["cache_source_evaluation_id"] = evaluation.get("cache_source_evaluation_id")
    return dimensions


def _ranking_probability(entry: dict[str, Any], question_id: str) -> float | None:
    dimensions = entry["dimensions"]
    if dimensions.get("applicability", {}).get(question_id, {}).get("applicable") is not True:
        return None
    return dimensions.get(question_id)


def _descending_probability(entry: dict[str, Any], question_id: str) -> float:
    probability = _ranking_probability(entry, question_id)
    return -probability if probability is not None else 1.0


def _ascending_probability(entry: dict[str, Any], question_id: str) -> float:
    probability = _ranking_probability(entry, question_id)
    return probability if probability is not None else 1.0


def jev_ranking(states: list[StateSummary] | list[dict[str, Any]],
                evaluations: list[EvaluationRecord] | list[dict[str, Any]]) -> dict[str, Any]:
    by_state = {(evaluation.input_ref_id if isinstance(evaluation, EvaluationRecord) else evaluation["input_ref_id"]):
                evaluation for evaluation in evaluations}
    entries = []
    for raw_state in states:
        state = _ranking_state(raw_state)
        evaluation = by_state.get(state.state_id)
        error = (evaluation.error_code if isinstance(evaluation, EvaluationRecord)
                 else evaluation.get("error") if evaluation else None)
        exclusion_reasons = _eligibility_exclusions(state)
        if evaluation is None:
            exclusion_reasons.append("EVALUATION_MISSING")
        elif error is not None:
            exclusion_reasons.append("EVALUATION_FAILED")
        else:
            exclusion_reasons = _admission_exclusions(state, evaluation)
        dimensions = _raw_dimensions(evaluation) if evaluation and error is None else {}
        entries.append({
            "state_id": state.state_id,
            "state_hash": state.state_hash,
            "gene_symbol": state.gene_symbol,
            "evaluation_id": (evaluation.evaluation_id if isinstance(evaluation, EvaluationRecord)
                              else evaluation.get("evaluation_id") if evaluation else None),
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
