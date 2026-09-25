"""Deterministic next-move policy tests. Offline and provider-free.

The policy is a pure function of a typed ``CheckSummary`` and a typed
``DeepJudgment``: Python decides, Jev only supplies one input dimension, and the
recorded move is never dispatched here.
"""

from __future__ import annotations

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import CheckSummary
from cancerjev.jev.contracts import EvaluationRecord, read_answers
from cancerjev.jev.questions import DEEP_LIMITATION_ROSTER, DEEP_QUESTIONS
from cancerjev.research.nextmove import (
    DEEP_POLICY_VERSION,
    MOVES,
    THRESHOLDS,
    DeepJudgment,
    decide_next_move,
)

ACTION = "CHECK_EVIDENCE_INTEGRITY_V1"
OTHER_ACTION = "CHECK_REVISION_FAITHFULNESS_V1"


def _checks(*, contradicted: int = 0, verified: int = 5) -> CheckSummary:
    return CheckSummary(total=contradicted + verified, verified=verified,
                        contradicted=contradicted, not_observed=0)


def _judgment(*, reliable: float | None = 0.9, sufficient: float | None = 0.8,
              warranted: float | None = 0.2, stopping: float | None = 0.8,
              limitation: str | None = "NONE", error: str | None = None,
              producing_action: str | None = ACTION) -> DeepJudgment:
    return DeepJudgment(reliable=reliable, sufficient=sufficient, warranted=warranted,
                        stopping=stopping, dominant_limitation=limitation, error_code=error,
                        producing_action=producing_action)


def _choice_answer(choice: str) -> dict:
    return {
        "kind": "choice",
        "choice": choice,
        "confidence": 0.7,
        "probabilities": {key: (1.0 if key == choice else 0.0) for key in DEEP_LIMITATION_ROSTER},
    }


def _evaluation_record(*, reliable: float = 0.9, sufficient: float = 0.8,
                       warranted: float = 0.2, stopping: float = 0.8,
                       limitation: str = "NONE", error_code: str | None = None,
                       ) -> EvaluationRecord:
    raw = {
        "revision_reliable": {"kind": "noul", "probability_yes": reliable},
        "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": sufficient},
        "next_step_warranted": {"kind": "noul", "probability_yes": warranted},
        "stopping_more_honest": {"kind": "noul", "probability_yes": stopping},
        "dominant_limitation": _choice_answer(limitation),
    }
    answers = read_answers(DEEP_QUESTIONS, raw)
    return EvaluationRecord(
        evaluation_id="evaluation-1", input_ref_id="revision-1", answers=answers,
        error_code=error_code, artifact_id="evaluation-artifact",
        serialized=canonical_json({"answers": answers.boundary_representation()}),
    )


def test_declared_move_vocabulary_is_the_only_output():
    assert MOVES == ("COMPLETE", "FOLLOW_UP", "GENERATE_HYPOTHESES", "ABSTAIN")
    scenarios = [
        (_checks(), _judgment(), [ACTION]),
        (_checks(), _judgment(reliable=0.1), [ACTION]),
        (_checks(), _judgment(stopping=0.9), [ACTION]),
        (_checks(), _judgment(warranted=0.9, stopping=0.1), [ACTION]),
        (_checks(), _judgment(warranted=0.9, stopping=0.1), [ACTION, OTHER_ACTION]),
        (_checks(), _judgment(warranted=0.2, stopping=0.2), [ACTION]),
        (_checks(contradicted=1, verified=4), _judgment(), [ACTION]),
        (_checks(), _judgment(reliable=None, error="PROVIDER_ERROR"), []),
    ]
    for checks, judgment, actions in scenarios:
        decision = decide_next_move(checks=checks, judgment=judgment, eligible_action_ids=actions)
        assert decision["move"] in MOVES
        assert decision["executed"] is False


def test_policy_records_one_versioned_move():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(),
                                eligible_action_ids=[ACTION])
    assert decision["policy_version"] == DEEP_POLICY_VERSION
    assert decision["move"] in {"COMPLETE", "FOLLOW_UP", "ABSTAIN"}
    assert decision["thresholds"] == THRESHOLDS
    assert decision["executed"] is False, "the deep slice never dispatches its own decision"
    assert decision["execution_note"]


def test_unusable_judgment_abstains():
    decision = decide_next_move(
        checks=_checks(),
        judgment=_judgment(reliable=None, error="PROVIDER_ERROR"),
        eligible_action_ids=[ACTION],
    )
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "DEEP_JUDGMENT_UNAVAILABLE")


def test_contradicted_check_abstains_before_any_dimension():
    decision = decide_next_move(checks=_checks(contradicted=1, verified=4), judgment=_judgment(),
                                eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == (
        "ABSTAIN", "REVISION_CONTRADICTS_RECORDED_EVIDENCE")


def test_unreliable_revision_abstains():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(reliable=0.2),
                                eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "REVISION_NOT_RELIABLE")


def test_honest_stopping_completes_the_investigation():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(stopping=0.9),
                                eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("COMPLETE", "INVESTIGATION_COMPLETE")


def test_warranted_step_without_a_distinct_action_abstains():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(warranted=0.9, stopping=0.1),
                                eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "NO_FURTHER_REGISTERED_ACTION")


def test_warranted_step_with_a_distinct_action_is_recorded_not_dispatched():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(warranted=0.9, stopping=0.1),
                                eligible_action_ids=[ACTION, OTHER_ACTION])
    assert (decision["move"], decision["reason_code"]) == ("FOLLOW_UP", "FOLLOW_UP_WARRANTED")
    assert decision["executed"] is False
    assert decision["dimensions"]["distinct_eligible_action_ids"] == [OTHER_ACTION]


def test_insufficient_evidence_abstains():
    decision = decide_next_move(
        checks=_checks(),
        judgment=_judgment(sufficient=0.1, warranted=0.1, stopping=0.1),
        eligible_action_ids=[ACTION],
    )
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "EVIDENCE_INSUFFICIENT")


def test_usable_evidence_without_a_warranted_step_asks_for_hypotheses():
    decision = decide_next_move(
        checks=_checks(),
        judgment=_judgment(sufficient=0.8, warranted=0.2, stopping=0.2),
        eligible_action_ids=[ACTION],
    )
    assert (decision["move"], decision["reason_code"]) == (
        "GENERATE_HYPOTHESES", "HYPOTHESES_JUSTIFIED")


def test_missing_stopping_dimension_falls_back_to_conservative_abstention():
    decision = decide_next_move(checks=_checks(), judgment=_judgment(warranted=0.2, stopping=None),
                                eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "UNCERTAINTY_UNRESOLVED")


def test_policy_is_deterministic_and_records_dimensions():
    first = decide_next_move(checks=_checks(), judgment=_judgment(), eligible_action_ids=[ACTION])
    second = decide_next_move(checks=_checks(), judgment=_judgment(), eligible_action_ids=[ACTION])
    assert first == second
    assert first["dimensions"]["dominant_limitation"] == "NONE"
    assert first["dimensions"]["eligible_action_ids"] == [ACTION]
    assert first["dimensions"]["checks_contradicted"] == 0
    assert first["dimensions"]["revision_reliable"] == 0.9


def test_threshold_boundaries_are_named_and_used():
    assert THRESHOLDS["revision_reliable_min"] == 0.5
    assert THRESHOLDS["evidence_sufficient_min"] == 0.5
    assert THRESHOLDS["next_step_warranted_min"] == 0.6
    assert THRESHOLDS["stopping_more_honest_min"] == 0.5

    at_reliable = decide_next_move(
        checks=_checks(), judgment=_judgment(reliable=THRESHOLDS["revision_reliable_min"]),
        eligible_action_ids=[ACTION],
    )
    assert at_reliable["reason_code"] != "REVISION_NOT_RELIABLE"

    at_stopping = decide_next_move(
        checks=_checks(), judgment=_judgment(stopping=THRESHOLDS["stopping_more_honest_min"]),
        eligible_action_ids=[ACTION],
    )
    assert at_stopping["move"] == "COMPLETE"

    at_warranted = decide_next_move(
        checks=_checks(),
        judgment=_judgment(warranted=THRESHOLDS["next_step_warranted_min"], stopping=0.1),
        eligible_action_ids=[ACTION, OTHER_ACTION],
    )
    assert at_warranted["move"] == "FOLLOW_UP"

    at_sufficient = decide_next_move(
        checks=_checks(),
        judgment=_judgment(sufficient=THRESHOLDS["evidence_sufficient_min"], warranted=0.2, stopping=0.2),
        eligible_action_ids=[ACTION],
    )
    assert at_sufficient["reason_code"] != "EVIDENCE_INSUFFICIENT"


def test_contradicted_check_outranks_favourable_dimensions():
    decision = decide_next_move(
        checks=_checks(contradicted=2, verified=3),
        judgment=_judgment(reliable=1.0, sufficient=1.0, warranted=1.0, stopping=0.0),
        eligible_action_ids=[ACTION, OTHER_ACTION],
    )
    assert (decision["move"], decision["reason_code"]) == (
        "ABSTAIN", "REVISION_CONTRADICTS_RECORDED_EVIDENCE")


def test_typed_judgment_is_built_from_a_validated_evaluation_record():
    record = _evaluation_record(reliable=0.7, sufficient=0.6, warranted=0.65,
                                stopping=0.3, limitation="SCOPE_LIMITS")
    judgment = DeepJudgment.from_evaluation(record, ACTION)
    assert (judgment.reliable, judgment.sufficient, judgment.warranted, judgment.stopping) == (
        0.7, 0.6, 0.65, 0.3)
    assert judgment.dominant_limitation == "SCOPE_LIMITS"
    assert judgment.error_code is None
    assert judgment.producing_action == ACTION
    decision = decide_next_move(checks=_checks(), judgment=judgment,
                                eligible_action_ids=[ACTION, OTHER_ACTION])
    assert (decision["move"], decision["reason_code"]) == ("FOLLOW_UP", "FOLLOW_UP_WARRANTED")


def test_failed_evaluation_record_abstains_instead_of_fabricating_dimensions():
    record = _evaluation_record(error_code="PROVIDER_ERROR")
    record = EvaluationRecord(evaluation_id=record.evaluation_id, input_ref_id=record.input_ref_id,
                              answers=None, error_code="PROVIDER_ERROR",
                              artifact_id=record.artifact_id, serialized=record.serialized)
    judgment = DeepJudgment.from_evaluation(record, ACTION)
    assert judgment.reliable is None and judgment.sufficient is None
    assert judgment.warranted is None and judgment.stopping is None
    assert judgment.error_code == "PROVIDER_ERROR"
    decision = decide_next_move(checks=_checks(), judgment=judgment, eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "DEEP_JUDGMENT_UNAVAILABLE")


@pytest.mark.parametrize("producing_action, expected", [
    (ACTION, [OTHER_ACTION]),
    (None, [ACTION, OTHER_ACTION]),
])
def test_distinct_action_set_excludes_the_producing_action(producing_action, expected):
    decision = decide_next_move(
        checks=_checks(),
        judgment=_judgment(warranted=0.9, stopping=0.1, producing_action=producing_action),
        eligible_action_ids=[ACTION, OTHER_ACTION],
    )
    assert decision["dimensions"]["distinct_eligible_action_ids"] == expected
