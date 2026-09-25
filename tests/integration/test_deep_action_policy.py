"""Deterministic deep-action policy: declared tiers, abstention, no registry-order fallback."""

from __future__ import annotations

from cancerjev.research.deep import (
    CHECK_ACTION_ORDER,
    DEEP_ACTION_POLICY_VERSION,
    SUMMARY_ACTION_ORDER,
    _policy_select,
)


def test_single_candidate_tiers_select_deterministically():
    assert DEEP_ACTION_POLICY_VERSION == "deep-action-policy-v1"
    check = CHECK_ACTION_ORDER[0]
    summary = SUMMARY_ACTION_ORDER[0]

    assert _policy_select((check,), frozenset()) == (check, None, "POLICY_SELECTED_CHECK_ACTION")
    assert _policy_select((summary,), frozenset()) == (
        summary, None, "POLICY_SELECTED_SUMMARY_ACTION")


def test_ambiguity_abstains_instead_of_using_registry_order():
    action_id, reason, detail = _policy_select(
        (CHECK_ACTION_ORDER[0], CHECK_ACTION_ORDER[1]), frozenset())

    assert action_id is None
    assert reason == "POLICY_AMBIGUOUS_TIER"
    assert CHECK_ACTION_ORDER[0] in detail and CHECK_ACTION_ORDER[1] in detail


def test_already_executed_actions_are_filtered_before_selection():
    action_id, reason, detail = _policy_select(
        (CHECK_ACTION_ORDER[0], SUMMARY_ACTION_ORDER[0]),
        frozenset({CHECK_ACTION_ORDER[0]}))

    assert action_id == SUMMARY_ACTION_ORDER[0]
    assert reason is None and detail == "POLICY_SELECTED_SUMMARY_ACTION"


def test_unresolvable_selection_abstains_with_a_typed_reason():
    assert _policy_select(("UNREGISTERED_V1",), frozenset()) == (
        None, "POLICY_ABSTAINED_NO_PRIORITY", "no declared policy tier resolves an action")
