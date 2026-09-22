from __future__ import annotations

from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PATTERN_PRIORITY,
    baseline_ranking,
    jev_ranking,
)
from tests.science.test_methods import _build, _frame


def _states() -> list[dict]:
    return [
        _build([_frame("P1"), _frame("P2")], counts={"P1": {"ENSG00000141510": 10}, "P2": {"ENSG00000141510": 5}},
               state_id="state-low"),
        _build([_frame("P1"), _frame("P2"), _frame("P3")],
               counts={"P1": {"ENSG00000141510": 40}, "P2": {"ENSG00000141510": 30},
                       "P3": {"ENSG00000141510": 25}},
               state_id="state-high"),
    ]


def _evaluation(state: dict, *, warrants: float, fragile: float, pattern: str,
                warrants_applicable: bool = True, fragile_applicable: bool = True) -> dict:
    return {
        "evaluation_id": f"eval-{state['state_hash'][:8]}",
        "input_ref_id": state["state_id"],
        "error": None,
        "answers": {
            "warrants_deeper_investigation": {"kind": "noul", "probability_yes": warrants},
            "likely_fragile": {"kind": "noul", "probability_yes": fragile},
            "pattern_type": {"kind": "choice", "choice": pattern, "confidence": 0.8,
                             "probabilities": {pattern: 0.8, "INSUFFICIENT_EVIDENCE": 0.2}},
        },
        "applicability": {
            "warrants_deeper_investigation": {"applicable": warrants_applicable, "reason": "x"},
            "likely_fragile": {"applicable": fragile_applicable, "reason": "x"},
            "pattern_type": {"applicable": True, "reason": "x"},
        },
        "cache_source_evaluation_id": None,
    }


def test_baseline_ranking_is_deterministic_and_descriptive():
    states = _states()
    first = baseline_ranking(states)
    second = baseline_ranking(list(reversed(states)))
    assert first["policy_version"] == BASELINE_POLICY_VERSION
    assert [entry["state_id"] for entry in first["entries"]] == [entry["state_id"] for entry in second["entries"]]
    top = first["entries"][0]
    assert top["dimensions"]["affected_case_total"] == 95
    assert first["admitted_state_ids"] == [entry["state_id"] for entry in first["entries"]]
    assert first["entries"][0]["rank"] == 1


def test_jev_ranking_orders_by_warrants_then_fragility():
    states = _states()
    low, high = states[0], states[1]
    evaluations = [
        _evaluation(low, warrants=0.2, fragile=0.9, pattern="NO_COHERENT_PATTERN"),
        _evaluation(high, warrants=0.9, fragile=0.2, pattern="WIDESPREAD_RECURRENCE"),
    ]
    ranking = jev_ranking(states, evaluations)
    assert ranking["policy_version"] == JEV_POLICY_VERSION
    assert ranking["entries"][0]["state_id"] == high["state_id"]
    assert ranking["admitted_state_ids"][0] == high["state_id"]
    assert ranking["entries"][0]["dimensions"]["warrants_deeper_investigation"] == 0.9


def test_jev_ranking_uses_pattern_priority_as_tiebreak():
    states = _states()
    first, second = states[0], states[1]
    evaluations = [
        _evaluation(first, warrants=0.5, fragile=0.5, pattern="DATA_QUALITY_CONCERN"),
        _evaluation(second, warrants=0.5, fragile=0.5, pattern="PROJECT_SPECIFIC_EXCEPTION"),
    ]
    ranking = jev_ranking(states, evaluations)
    assert ranking["entries"][0]["state_id"] == second["state_id"]
    assert PATTERN_PRIORITY.index("PROJECT_SPECIFIC_EXCEPTION") < PATTERN_PRIORITY.index("DATA_QUALITY_CONCERN")


def test_inapplicable_dimensions_sort_last_and_are_preserved():
    states = _states()
    first, second = states[0], states[1]
    evaluations = [
        _evaluation(first, warrants=0.99, fragile=0.1, pattern="WIDESPREAD_RECURRENCE",
                    warrants_applicable=False, fragile_applicable=False),
        _evaluation(second, warrants=0.4, fragile=0.6, pattern="NO_COHERENT_PATTERN"),
    ]
    ranking = jev_ranking(states, evaluations)
    assert ranking["entries"][0]["state_id"] == second["state_id"]
    entry = ranking["entries"][1]
    assert entry["dimensions"]["warrants_deeper_investigation"] is None
    assert entry["dimensions"]["likely_fragile"] is None
    assert entry["dimensions"]["applicability"]["warrants_deeper_investigation"]["applicable"] is False


def test_failed_evaluations_are_excluded_from_jev_ranking():
    states = _states()
    failed = {"input_ref_id": states[0]["state_id"], "error": {"code": "PROVIDER_ERROR"}}
    successful = _evaluation(states[1], warrants=0.5, fragile=0.4, pattern="WIDESPREAD_RECURRENCE")
    ranking = jev_ranking(states, [failed, successful])
    assert [entry["state_id"] for entry in ranking["entries"]] == [states[1]["state_id"]]
    assert ranking["admitted_state_ids"] == [states[1]["state_id"]]
    states_without_evaluation = jev_ranking(states, [failed])
    assert states_without_evaluation["entries"] == []
