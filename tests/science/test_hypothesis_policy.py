"""Hypothesis policy: recorded critique becomes exactly one declared decision.

The outcome space is exactly what can happen: no registered action both accepts an
``EvidenceState`` revision and produces evidence, so a testable hypothesis is kept
with ``NO_EVIDENCE_PRODUCING_TEST`` and never given a pseudo-test.
"""

from __future__ import annotations

from typing import Any

from cancerjev.research.hypothesis_policy import (
    HYPOTHESIS_POLICY_VERSION,
    MOVES,
    RESULTS,
    decide_hypothesis_test,
)

ACTION = "OCCURRENCE_DETAIL_EVIDENCE_V1"
OTHER_ACTION = "EXPRESSION_SUMMARY_V1"
CHECK_ACTION = "CHECK_REVISION_FAITHFULNESS_V1"


def _hypothesis(hypothesis_id: str, *actions: str) -> dict[str, Any]:
    return {"hypothesis_id": hypothesis_id, "proposed_action_ids": list(actions)}


def _evaluation(hypothesis_id: str, *, testable: float = 1.0, exceeds: float = 0.0,
                assumption: str = "NONE", error: str | None = None,
                missing_answers: bool = False) -> dict[str, Any]:
    answers: dict[str, Any] = {} if missing_answers else {
        "hypothesis_testable": {"kind": "noul", "probability_yes": testable},
        "hypothesis_exceeds_recorded_evidence": {"kind": "noul", "probability_yes": exceeds},
        "hypothesis_dominant_unsupported_assumption": {
            "kind": "choice", "choice": assumption, "confidence": 0.9, "probabilities": {}},
    }
    return {"hypothesis_id": hypothesis_id, "error_code": error, "answers": answers}


def test_declared_outcome_space_contains_no_unreachable_hypothesis_test():
    assert "TEST_HYPOTHESIS" not in MOVES
    assert RESULTS == ("NO_HYPOTHESES", "NO_TESTABLE_HYPOTHESIS", "NO_EVIDENCE_PRODUCING_TEST")


def test_testable_hypothesis_is_kept_and_the_missing_requirement_is_recorded():
    decision = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION)], evaluations=[_evaluation("h1")],
        dispatchable_action_ids=[ACTION])

    assert decision.move == "KEEP_HYPOTHESIS"
    assert decision.reason_code == "NO_EVIDENCE_PRODUCING_TEST"
    assert decision.hypothesis_id == "h1" and decision.action_id is None
    assert decision.policy_version == HYPOTHESIS_POLICY_VERSION
    assert decision.payload()["critique"][0]["dispatchable_proposals"] == [ACTION]


def test_unfavorable_critique_abstains_without_a_dispatch():
    for evaluation in (_evaluation("h1", testable=0.59),
                       _evaluation("h1", exceeds=0.51),
                       _evaluation("h1", assumption="MECHANISM")):
        decision = decide_hypothesis_test(
            hypotheses=[_hypothesis("h1", ACTION)], evaluations=[evaluation],
            dispatchable_action_ids=[ACTION])
        assert decision.move == "ABSTAIN"
        assert decision.reason_code == "NO_TESTABLE_HYPOTHESIS"
        assert decision.action_id is None


def test_several_dispatchable_proposals_are_kept_without_ordering():
    decision = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION, OTHER_ACTION)], evaluations=[_evaluation("h1")],
        dispatchable_action_ids=[ACTION, OTHER_ACTION])

    assert decision.move == "KEEP_HYPOTHESIS"
    assert decision.reason_code == "NO_EVIDENCE_PRODUCING_TEST"
    assert decision.action_id is None


def test_a_dispatchable_check_is_not_a_hypothesis_test():
    """Integrity and summary actions verify existing evidence; they cannot discriminate."""
    decision = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", CHECK_ACTION)], evaluations=[_evaluation("h1")],
        dispatchable_action_ids=[CHECK_ACTION])

    assert decision.move == "KEEP_HYPOTHESIS"
    assert decision.reason_code == "NO_EVIDENCE_PRODUCING_TEST"
    assert decision.action_id is None
    assert decision.payload()["critique"][0]["dispatchable_proposals"] == [CHECK_ACTION]


def test_actionable_hypothesis_without_any_dispatchable_action_is_kept_with_a_reason():
    decision = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION)], evaluations=[_evaluation("h1")],
        dispatchable_action_ids=[])

    assert decision.move == "KEEP_HYPOTHESIS"
    assert decision.reason_code == "NO_EVIDENCE_PRODUCING_TEST"


def test_missing_hypotheses_or_critique_abstains():
    assert decide_hypothesis_test(
        hypotheses=[], evaluations=[], dispatchable_action_ids=[]).reason_code == "NO_HYPOTHESES"

    no_critique = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION)], evaluations=[],
        dispatchable_action_ids=[ACTION])
    assert no_critique.move == "ABSTAIN"

    failed = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION)],
        evaluations=[_evaluation("h1", error="PROVIDER_ERROR")],
        dispatchable_action_ids=[ACTION])
    assert failed.move == "ABSTAIN"

    partial = decide_hypothesis_test(
        hypotheses=[_hypothesis("h1", ACTION)],
        evaluations=[_evaluation("h1", missing_answers=True)],
        dispatchable_action_ids=[ACTION])
    assert partial.move == "ABSTAIN"


def test_decision_is_deterministic_for_a_fixed_recording():
    arguments = dict(
        hypotheses=[_hypothesis("h2", ACTION), _hypothesis("h1", ACTION)],
        evaluations=[_evaluation("h1"), _evaluation("h2")],
        dispatchable_action_ids=[ACTION])
    assert decide_hypothesis_test(**arguments).payload() == \
        decide_hypothesis_test(**arguments).payload()
