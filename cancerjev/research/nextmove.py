"""Deterministic Python next-move policy over one deep evidence judgment.

Python owns the decision. A Jev judgment is one input dimension in this mapping,
never a command: Jev does not choose an action, execute anything or control the
loop. The policy records one typed next move and deliberately does not dispatch
it; dispatching a follow-up stays an explicit operator or later-phase decision.

Thresholds are named, versioned and documented. They are not tuned to force an
outcome, and a move that cannot be executed today is recorded as such rather than
silently dropped.
"""

from __future__ import annotations

from typing import Any

DEEP_POLICY_VERSION = "deep-policy-v2"

THRESHOLDS = {
    "revision_reliable_min": 0.5,
    "evidence_sufficient_min": 0.5,
    "next_step_warranted_min": 0.6,
    "stopping_more_honest_min": 0.5,
}

MOVES = ("COMPLETE", "FOLLOW_UP", "GENERATE_HYPOTHESES", "ABSTAIN")


def _probability(judgment: dict[str, Any], question_id: str) -> float | None:
    answer = (judgment.get("answers") or {}).get(question_id)
    if not isinstance(answer, dict) or answer.get("kind") != "noul":
        return None
    value = answer.get("probability_yes")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _choice(judgment: dict[str, Any], question_id: str) -> str | None:
    answer = (judgment.get("answers") or {}).get(question_id)
    if not isinstance(answer, dict) or answer.get("kind") != "choice":
        return None
    choice = answer.get("choice")
    return str(choice) if choice is not None else None


def next_move(*, checks: dict[str, Any], judgment: dict[str, Any],
              eligible_action_ids: list[str]) -> dict[str, Any]:
    """Map one revision's recorded checks plus its deep judgment to one typed move."""
    contradicted = int(checks.get("checks_contradicted") or 0)
    reliable = _probability(judgment, "revision_reliable")
    sufficient = _probability(judgment, "evidence_sufficient_for_next_step")
    warranted = _probability(judgment, "next_step_warranted")
    stopping = _probability(judgment, "stopping_more_honest")
    judgment_error = judgment.get("error")
    producing_action = (judgment.get("action_id") or None)
    distinct_actions = [action_id for action_id in eligible_action_ids if action_id != producing_action]
    dimensions = {
        "revision_reliable": reliable,
        "evidence_sufficient_for_next_step": sufficient,
        "next_step_warranted": warranted,
        "stopping_more_honest": stopping,
        "dominant_limitation": _choice(judgment, "dominant_limitation"),
        "checks_contradicted": contradicted,
        "eligible_action_ids": sorted(eligible_action_ids),
        "distinct_eligible_action_ids": sorted(distinct_actions),
    }
    detail: str
    if judgment_error is not None or reliable is None:
        move, reason, detail = (
            "ABSTAIN", "DEEP_JUDGMENT_UNAVAILABLE",
            "no usable deep judgment exists for this revision",
        )
    elif contradicted > 0:
        move, reason, detail = (
            "ABSTAIN", "REVISION_CONTRADICTS_RECORDED_EVIDENCE",
            f"{contradicted} recorded integrity check(s) were contradicted",
        )
    elif reliable < THRESHOLDS["revision_reliable_min"]:
        move, reason, detail = (
            "ABSTAIN", "REVISION_NOT_RELIABLE",
            "the deep judgment does not support relying on this revision",
        )
    elif stopping is not None and stopping >= THRESHOLDS["stopping_more_honest_min"]:
        move, reason, detail = (
            "COMPLETE", "INVESTIGATION_COMPLETE",
            "the recorded revision stands and stopping here is the honest choice",
        )
    elif warranted is not None and warranted >= THRESHOLDS["next_step_warranted_min"]:
        if distinct_actions:
            move, reason, detail = (
                "FOLLOW_UP", "FOLLOW_UP_WARRANTED",
                "a distinct registered action is eligible; dispatch requires an explicit selection",
            )
        else:
            move, reason, detail = (
                "ABSTAIN", "NO_FURTHER_REGISTERED_ACTION",
                "no distinct registered action is eligible for this revision",
            )
    elif sufficient is not None and sufficient < THRESHOLDS["evidence_sufficient_min"]:
        move, reason, detail = (
            "ABSTAIN", "EVIDENCE_INSUFFICIENT",
            "the revision does not hold enough observed evidence for a further step",
        )
    elif stopping is not None and stopping < THRESHOLDS["stopping_more_honest_min"]:
        move, reason, detail = (
            "GENERATE_HYPOTHESES", "HYPOTHESES_JUSTIFIED",
            "the evidence is usable, no further deterministic step is warranted, and stopping is not "
            "yet honest, so the honest next step is to state competing explanations",
        )
    else:
        move, reason, detail = (
            "ABSTAIN", "UNCERTAINTY_UNRESOLVED",
            "the judgment does not warrant a further step and does not claim completion",
        )
    return {
        "policy_version": DEEP_POLICY_VERSION,
        "move": move,
        "reason_code": reason,
        "detail": detail,
        "dimensions": dimensions,
        "thresholds": dict(THRESHOLDS),
        "executed": False,
        "execution_note": (
            "the recorded move is a decision input; no follow-up is dispatched from the deep slice"
        ),
    }
