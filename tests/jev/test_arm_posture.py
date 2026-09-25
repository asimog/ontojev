"""Arm Jev posture: the committed decision record and code agree, and no Arm exists."""

from __future__ import annotations

from pathlib import Path

from cancerjev.jev.posture import (
    ARM_JEV_DECISION,
    ARM_JEV_DEFERRAL_REASON,
    TYPESAFE_DECISION_RECORD_PATH,
    TYPESAFE_DECISION_RECORD_VERSION,
    ArmDecision,
)
from cancerjev.jev.questions import WIDE_QUESTION_SET_VERSION, WIDE_QUESTIONS

ROOT = Path(__file__).resolve().parents[2]


def test_decision_record_matches_the_typed_posture():
    record = (ROOT / TYPESAFE_DECISION_RECORD_PATH).read_text(encoding="utf-8")

    assert TYPESAFE_DECISION_RECORD_VERSION == "1"
    assert ARM_JEV_DECISION is ArmDecision.DEFER
    assert "typesafe-decisions-v1" in record
    assert "**Arm Jev** | **DEFER**" in record
    assert "arm-v1" in record
    assert "pending-semantic-review" in record
    assert "deterministic dispositions" in ARM_JEV_DEFERRAL_REASON


def test_no_arm_question_set_is_registered_and_wide_stays_unchanged():
    from cancerjev.jev import questions

    assert not hasattr(questions, "ARM_QUESTIONS")
    assert WIDE_QUESTION_SET_VERSION == "wide-v3"
    assert len(WIDE_QUESTIONS) >= 1
