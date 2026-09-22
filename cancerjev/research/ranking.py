"""Deterministic wide ranking: baseline and Jev policy over persisted dimensions.

The baseline is always computed from deterministic state fields; the Jev ranking
uses only persisted raw judgment vectors. Both are retained so Phase 3 can
compare baseline vs baseline+Jev on the same states. Jev never replaces the
baseline, and no opaque master score is created.
"""

from __future__ import annotations

from typing import Any

BASELINE_POLICY_VERSION = "baseline-wide-v1"
JEV_POLICY_VERSION = "wide-policy-v1"
PROMOTION_LIMIT = 3
PATTERN_PRIORITY = (
    "WIDESPREAD_RECURRENCE",
    "PROJECT_SPECIFIC_EXCEPTION",
    "WEAK_DISTRIBUTED_SIGNAL",
    "NO_COHERENT_PATTERN",
    "DATA_QUALITY_CONCERN",
    "INSUFFICIENT_EVIDENCE",
)


def _metric_value(metric: dict[str, Any] | None) -> float | None:
    if metric is None or metric.get("availability") != "OBSERVED":
        return None
    return metric.get("value")


def baseline_ranking(states: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for state in states:
        cross = state["cross_project"]
        entries.append({
            "state_id": state["state_id"],
            "state_hash": state["state_hash"],
            "gene_symbol": state["entity"]["gene_symbol"],
            "dimensions": {
                "projects_with_mutation_observation": cross["projects_with_mutation_observation"],
                "affected_case_total": _metric_value(cross["affected_case_total"]),
                "top_project_share": _metric_value(cross["top_project_share"]),
                "coverage_imbalance": cross["coverage_imbalance"],
            },
        })
    entries.sort(key=lambda entry: (
        -entry["dimensions"]["projects_with_mutation_observation"],
        -(entry["dimensions"]["affected_case_total"] or -1.0),
        entry["dimensions"]["top_project_share"] if entry["dimensions"]["top_project_share"] is not None else 1.1,
        entry["state_hash"],
    ))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return {
        "policy_version": BASELINE_POLICY_VERSION,
        "kind": "BASELINE",
        "ordering": (
            "projects_with_mutation_observation desc, affected_case_total desc, top_project_share asc, "
            "state_hash asc"
        ),
        "entries": entries,
        "admitted_state_ids": [entry["state_id"] for entry in entries[:PROMOTION_LIMIT]],
    }


def _applicable(evaluation: dict[str, Any], question_id: str) -> bool:
    return bool(evaluation.get("applicability", {}).get(question_id, {}).get("applicable"))


def jev_ranking(states: list[dict[str, Any]], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    by_state = {
        evaluation["input_ref_id"]: evaluation
        for evaluation in evaluations if evaluation.get("error") is None
    }
    entries = []
    for state in states:
        evaluation = by_state.get(state["state_id"])
        if evaluation is None:
            continue
        answers = evaluation["answers"]
        warrants_applicable = _applicable(evaluation, "warrants_deeper_investigation")
        fragile_applicable = _applicable(evaluation, "likely_fragile")
        pattern_applicable = _applicable(evaluation, "pattern_type")
        pattern = answers.get("pattern_type", {}).get("choice") if pattern_applicable else None
        entries.append({
            "state_id": state["state_id"],
            "state_hash": state["state_hash"],
            "gene_symbol": state["entity"]["gene_symbol"],
            "evaluation_id": evaluation["evaluation_id"],
            "dimensions": {
                "warrants_deeper_investigation": (
                    answers["warrants_deeper_investigation"]["probability_yes"] if warrants_applicable else None
                ),
                "likely_fragile": (
                    answers["likely_fragile"]["probability_yes"] if fragile_applicable else None
                ),
                "pattern_type": pattern,
                "pattern_type_confidence": (
                    answers["pattern_type"]["confidence"] if pattern_applicable else None
                ),
                "applicability": evaluation["applicability"],
                "cache_source_evaluation_id": evaluation.get("cache_source_evaluation_id"),
            },
        })
    entries.sort(key=lambda entry: (
        -(entry["dimensions"]["warrants_deeper_investigation"]
          if entry["dimensions"]["warrants_deeper_investigation"] is not None else -1.0),
        entry["dimensions"]["likely_fragile"] if entry["dimensions"]["likely_fragile"] is not None else 1.0,
        PATTERN_PRIORITY.index(entry["dimensions"]["pattern_type"])
        if entry["dimensions"]["pattern_type"] in PATTERN_PRIORITY else len(PATTERN_PRIORITY),
        entry["state_hash"],
    ))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return {
        "policy_version": JEV_POLICY_VERSION,
        "kind": "JEV",
        "ordering": (
            "warrants_deeper_investigation desc, likely_fragile asc, pattern_type class priority, "
            "state_hash asc; inapplicable dimensions sort last"
        ),
        "entries": entries,
        "admitted_state_ids": [entry["state_id"] for entry in entries[:PROMOTION_LIMIT]],
    }
