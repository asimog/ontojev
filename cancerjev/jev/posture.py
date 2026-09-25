"""Typed TypeSafe/Jev capability posture, checked against docs/TYPESAFE_DECISIONS.md.

The decision record is the authority; these constants make its critical posture
machine-checkable so a future adoption cannot drift silently.
"""

from __future__ import annotations

from enum import StrEnum

TYPESAFE_DECISION_RECORD_VERSION = "1"
TYPESAFE_DECISION_RECORD_PATH = "docs/TYPESAFE_DECISIONS.md"


class ArmDecision(StrEnum):
    ADOPT = "ADOPT"
    DEFER = "DEFER"
    REJECT = "REJECT"


ARM_JEV_DECISION = ArmDecision.DEFER

ARM_JEV_DEFERRAL_REASON = (
    "no named consumer requires preserve-or-drop triage: deterministic dispositions decide "
    "admission in Python and JEV_REVIEW entries are carried as typed pending-semantic-review "
    "through the modality union without being admitted or silently dropped"
)
