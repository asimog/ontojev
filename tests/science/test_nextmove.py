"""Deterministic next-move policy tests. Offline and provider-free."""

from __future__ import annotations

import pytest

from cancerjev.research.nextmove import DEEP_POLICY_VERSION, MOVES, THRESHOLDS, next_move

ACTION = "CHECK_EVIDENCE_INTEGRITY_V1"


def test_declared_move_vocabulary_is_the_only_output():
    assert MOVES == ("COMPLETE", "FOLLOW_UP", "ABSTAIN")
    scenarios = [
        (_checks(), _judgment(), [ACTION]),
        (_checks(), _judgment(reliable=0.1), [ACTION]),
        (_checks(), _judgment(stopping=0.9), [ACTION]),
        (_checks(), _judgment(warranted=0.9, stopping=0.1), [ACTION]),
        (_checks(), _judgment(warranted=0.9, stopping=0.1), [ACTION, "ANOTHER"]),
        (_checks(contradicted=1), _judgment(), [ACTION]),
        ({}, {"answers": {}, "error": {"code": "X"}}, []),
    ]
    for checks, judgment, actions in scenarios:
        assert next_move(checks=checks, judgment=judgment, eligible_action_ids=actions)["move"] in MOVES


def _judgment(**probabilities) -> dict:
    answers = {
        "revision_reliable": {"kind": "noul", "probability_yes": probabilities.get("reliable", 0.9)},
        "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": probabilities.get("sufficient", 0.8)},
        "next_step_warranted": {"kind": "noul", "probability_yes": probabilities.get("warranted", 0.2)},
        "stopping_more_honest": {"kind": "noul", "probability_yes": probabilities.get("stopping", 0.8)},
        "dominant_limitation": {"kind": "choice", "choice": probabilities.get("limitation", "NONE")},
    }
    return {"answers": answers, "error": probabilities.get("error"), "action_id": ACTION}


def _checks(contradicted: int = 0) -> dict:
    return {"checks_contradicted": contradicted, "checks_verified": 5 - contradicted}


def test_policy_records_one_versioned_move():
    decision = next_move(checks=_checks(), judgment=_judgment(), eligible_action_ids=[ACTION])
    assert decision["policy_version"] == DEEP_POLICY_VERSION
    assert decision["move"] in {"COMPLETE", "FOLLOW_UP", "ABSTAIN"}
    assert decision["thresholds"] == THRESHOLDS
    assert decision["executed"] is False, "the deep slice never dispatches its own decision"


def test_unusable_judgment_abstains():
    decision = next_move(checks=_checks(), judgment={"answers": {}, "error": {"code": "PROVIDER_ERROR"}},
                         eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "DEEP_JUDGMENT_UNAVAILABLE")


def test_contradicted_check_abstains_before_any_dimension():
    decision = next_move(checks=_checks(contradicted=1), judgment=_judgment(), eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == (
        "ABSTAIN", "REVISION_CONTRADICTS_RECORDED_EVIDENCE")


def test_unreliable_revision_abstains():
    decision = next_move(checks=_checks(), judgment=_judgment(reliable=0.2), eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "REVISION_NOT_RELIABLE")


def test_honest_stopping_completes_the_investigation():
    decision = next_move(checks=_checks(), judgment=_judgment(stopping=0.9), eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("COMPLETE", "INVESTIGATION_COMPLETE")


def test_warranted_step_without_a_distinct_action_abstains():
    decision = next_move(checks=_checks(), judgment=_judgment(warranted=0.9, stopping=0.1),
                         eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "NO_FURTHER_REGISTERED_ACTION")


def test_warranted_step_with_a_distinct_action_is_recorded_not_dispatched():
    decision = next_move(checks=_checks(), judgment=_judgment(warranted=0.9, stopping=0.1),
                         eligible_action_ids=[ACTION, "ANOTHER_REGISTERED_ACTION"])
    assert (decision["move"], decision["reason_code"]) == ("FOLLOW_UP", "FOLLOW_UP_WARRANTED")
    assert decision["executed"] is False
    assert decision["dimensions"]["distinct_eligible_action_ids"] == ["ANOTHER_REGISTERED_ACTION"]


def test_insufficient_evidence_abstains():
    decision = next_move(checks=_checks(),
                         judgment=_judgment(sufficient=0.1, warranted=0.1, stopping=0.1),
                         eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "EVIDENCE_INSUFFICIENT")


def test_undecided_case_abstains_conservatively():
    decision = next_move(checks=_checks(),
                         judgment=_judgment(sufficient=0.8, warranted=0.2, stopping=0.2),
                         eligible_action_ids=[ACTION])
    assert (decision["move"], decision["reason_code"]) == ("ABSTAIN", "UNCERTAINTY_UNRESOLVED")


def test_policy_is_deterministic_and_records_dimensions():
    first = next_move(checks=_checks(), judgment=_judgment(), eligible_action_ids=[ACTION])
    second = next_move(checks=_checks(), judgment=_judgment(), eligible_action_ids=[ACTION])
    assert first == second
    assert first["dimensions"]["dominant_limitation"] == "NONE"
    assert first["dimensions"]["eligible_action_ids"] == [ACTION]
    assert first["dimensions"]["checks_contradicted"] == 0


@pytest.mark.parametrize("contradicted", [0, 2])
def test_threshold_boundaries_are_named_and_used(contradicted):
    decision = next_move(checks=_checks(contradicted=contradicted),
                         judgment=_judgment(reliable=THRESHOLDS["revision_reliable_min"]),
                         eligible_action_ids=[ACTION])
    if contradicted:
        assert decision["move"] == "ABSTAIN"
    else:
        assert decision["reason_code"] != "REVISION_NOT_RELIABLE"
