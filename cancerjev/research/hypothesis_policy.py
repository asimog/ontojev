"""Python policy over hypothesis Jev answers: Jev judges, Python decides.

The hypothesis stage records critique but previously consumed none of it. This
policy converts the recorded answers into exactly one declared decision:
dispatch a single registered discriminating action (TEST_HYPOTHESIS), keep the
recorded statements (KEEP_HYPOTHESIS), or abstain with an explicit reason.

A hypothesis can only be tested by an **evidence-producing** action: integrity
and summary actions verify or describe existing evidence and cannot discriminate
between competing explanations. When no evidence-producing action is registered
for the revision, the decision is KEEP_HYPOTHESIS with
``NO_EVIDENCE_PRODUCING_TEST`` rather than a pseudo-test. The policy never
invents an action, never chooses among several proposals by ordering, and never
writes evidence itself: dispatch reuses the existing recorded-move path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HYPOTHESIS_POLICY_VERSION = "hypothesis-policy-v1"
THRESHOLDS = {
    "testable_min": 0.60,
    "exceeds_recorded_evidence_max": 0.50,
}
UNSUPPORTED_ASSUMPTION_NONE = "NONE"
MOVES = ("TEST_HYPOTHESIS", "KEEP_HYPOTHESIS", "ABSTAIN")
RESULTS = ("NO_HYPOTHESES", "NO_TESTABLE_HYPOTHESIS", "MULTIPLE_DISCRIMINATING_ACTIONS",
           "NO_EVIDENCE_PRODUCING_TEST", "SINGLE_DISCRIMINATING_ACTION")


@dataclass(frozen=True)
class HypothesisDecision:
    policy_version: str
    move: str
    reason_code: str
    hypothesis_id: str | None
    action_id: str | None
    critique: tuple[dict[str, Any], ...]

    def payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version, "move": self.move,
            "reason_code": self.reason_code, "hypothesis_id": self.hypothesis_id,
            "action_id": self.action_id, "thresholds": dict(THRESHOLDS),
            "critique": [dict(entry) for entry in self.critique],
        }


def _probability(answers: dict[str, Any], question_id: str) -> float | None:
    entry = answers.get(question_id)
    if not isinstance(entry, dict) or entry.get("kind") != "noul":
        return None
    value = entry.get("probability_yes")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _choice(answers: dict[str, Any], question_id: str) -> str | None:
    entry = answers.get(question_id)
    if not isinstance(entry, dict) or entry.get("kind") != "choice":
        return None
    choice = entry.get("choice")
    return str(choice) if choice else None


def decide_hypothesis_test(*, hypotheses: list[dict[str, Any]],
                           evaluations: list[dict[str, Any]],
                           dispatchable_action_ids: list[str],
                           evidence_producing_action_ids: list[str] | frozenset[str] = (),
                           ) -> HypothesisDecision:
    """One declared decision from recorded hypothesis critique and registered actions."""
    by_id = {str(item.get("hypothesis_id")): item for item in evaluations}
    dispatchable = sorted({str(action_id) for action_id in dispatchable_action_ids})
    evidence_producing = {str(action_id) for action_id in evidence_producing_action_ids}
    critique: list[dict[str, Any]] = []
    actionable: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("hypothesis_id"))
        evaluation = by_id.get(hypothesis_id) or {}
        answers = evaluation.get("answers")
        answers = answers if isinstance(answers, dict) else {}
        error_code = evaluation.get("error_code")
        testable = _probability(answers, "hypothesis_testable")
        exceeds = _probability(answers, "hypothesis_exceeds_recorded_evidence")
        assumption = _choice(answers, "hypothesis_dominant_unsupported_assumption")
        within_recorded_evidence = (
            error_code is None
            and testable is not None and testable >= THRESHOLDS["testable_min"]
            and exceeds is not None and exceeds <= THRESHOLDS["exceeds_recorded_evidence_max"]
            and assumption == UNSUPPORTED_ASSUMPTION_NONE
        )
        proposals = sorted(
            {str(action_id) for action_id in (hypothesis.get("proposed_action_ids") or [])}
            & set(dispatchable))
        entry = {
            "hypothesis_id": hypothesis_id, "error_code": error_code, "testable": testable,
            "exceeds_recorded_evidence": exceeds, "dominant_unsupported_assumption": assumption,
            "within_recorded_evidence": within_recorded_evidence,
            "dispatchable_proposals": proposals,
            "evidence_producing_proposals": [action for action in proposals
                                             if action in evidence_producing],
        }
        critique.append(entry)
        if within_recorded_evidence:
            actionable.append(entry)

    if not hypotheses:
        return HypothesisDecision(HYPOTHESIS_POLICY_VERSION, "ABSTAIN", "NO_HYPOTHESES",
                                  None, None, tuple(critique))
    if not actionable:
        return HypothesisDecision(HYPOTHESIS_POLICY_VERSION, "ABSTAIN",
                                  "NO_TESTABLE_HYPOTHESIS", None, None, tuple(critique))
    for entry in actionable:
        producing = entry["evidence_producing_proposals"]
        if len(producing) == 1:
            return HypothesisDecision(HYPOTHESIS_POLICY_VERSION, "TEST_HYPOTHESIS",
                                      "SINGLE_DISCRIMINATING_ACTION",
                                      str(entry["hypothesis_id"]), producing[0],
                                      tuple(critique))
        if len(producing) > 1:
            # No hidden ordering: several of the statement's own tests are dispatchable.
            return HypothesisDecision(HYPOTHESIS_POLICY_VERSION, "ABSTAIN",
                                      "MULTIPLE_DISCRIMINATING_ACTIONS",
                                      str(entry["hypothesis_id"]), None, tuple(critique))
    return HypothesisDecision(HYPOTHESIS_POLICY_VERSION, "KEEP_HYPOTHESIS",
                              "NO_EVIDENCE_PRODUCING_TEST", str(actionable[0]["hypothesis_id"]),
                              None, tuple(critique))
