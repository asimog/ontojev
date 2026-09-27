"""Program/Campaign coordination vocabulary.

Coordination is operational: it sequences bounded Campaigns across process
restarts. It never computes a scientific measurement, never promotes readiness
and never mutates prior results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cancerjev.domain.measurements import count, require, text


class ProgramState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CAMPAIGN_COMPLETE = "CAMPAIGN_COMPLETE"
    BLOCKED_NOT_READY = "BLOCKED_NOT_READY"
    PROGRAM_IDLE = "PROGRAM_IDLE"


class CampaignStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CAMPAIGN_COMPLETE = "CAMPAIGN_COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CampaignRecord:
    """Durable operational record for one profile across process restarts.

    The record carries only operational identity and retry bookkeeping. It is
    never scientific evidence and never rewrites a completed campaign.
    """

    profile_id: str
    status: CampaignStatus
    profile_identity: str | None
    release_identity: str | None
    method_identity: str | None
    attempts: int
    next_attempt_at: str | None
    reason_code: str | None
    last_cycle_run_id: str | None
    release: str | None = None
    release_commit: str | None = None

    def __post_init__(self) -> None:
        text(self.profile_id, "campaign record profile id")
        require(isinstance(self.status, CampaignStatus), "invalid campaign record status")
        for label, value in (("profile identity", self.profile_identity),
                             ("release identity", self.release_identity),
                             ("method identity", self.method_identity),
                             ("next attempt", self.next_attempt_at),
                             ("reason code", self.reason_code),
                             ("last cycle run id", self.last_cycle_run_id),
                             ("release", self.release),
                             ("release commit", self.release_commit)):
            if value is not None:
                text(value, f"campaign record {label}")
        count(self.attempts, "campaign record attempts")
        require(self.attempts >= 0, "campaign record attempts must be non-negative")

    def identity(self) -> tuple[str | None, str | None, str | None]:
        return (self.profile_identity, self.release_identity, self.method_identity)

    def payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "status": self.status.value,
            "profile_identity": self.profile_identity,
            "release_identity": self.release_identity,
            "method_identity": self.method_identity,
            "attempts": self.attempts,
            "next_attempt_at": self.next_attempt_at,
            "reason_code": self.reason_code,
            "last_cycle_run_id": self.last_cycle_run_id,
            "release": self.release,
            "release_commit": self.release_commit,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CampaignRecord:
        require(isinstance(payload, dict), "campaign record payload must be an object")
        return cls(
            profile_id=payload["profile_id"],
            status=CampaignStatus(payload["status"]),
            profile_identity=payload.get("profile_identity"),
            release_identity=payload.get("release_identity"),
            method_identity=payload.get("method_identity"),
            attempts=int(payload.get("attempts") or 0),
            next_attempt_at=payload.get("next_attempt_at"),
            reason_code=payload.get("reason_code"),
            last_cycle_run_id=payload.get("last_cycle_run_id"),
            release=payload.get("release"),
            release_commit=payload.get("release_commit"),
        )
