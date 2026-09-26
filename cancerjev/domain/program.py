"""Program/Campaign coordination vocabulary and release-comparison contracts.

Coordination is operational: it sequences bounded Campaigns and classifies
release changes from persisted snapshots. It never computes a scientific
measurement, never promotes readiness and never mutates prior results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cancerjev.domain.measurements import count, require, sha256, strings, text


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

    def __post_init__(self) -> None:
        text(self.profile_id, "campaign record profile id")
        require(isinstance(self.status, CampaignStatus), "invalid campaign record status")
        for label, value in (("profile identity", self.profile_identity),
                             ("release identity", self.release_identity),
                             ("method identity", self.method_identity),
                             ("next attempt", self.next_attempt_at),
                             ("reason code", self.reason_code),
                             ("last cycle run id", self.last_cycle_run_id)):
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
        )


class ComparisonClass(StrEnum):
    NEW_CANDIDATE = "NEW_CANDIDATE"
    LOST_CANDIDATE = "LOST_CANDIDATE"
    RANK_CHANGED = "RANK_CHANGED"
    EVIDENCE_STRENGTHENED = "EVIDENCE_STRENGTHENED"
    EVIDENCE_WEAKENED = "EVIDENCE_WEAKENED"
    MODALITY_CHANGED = "MODALITY_CHANGED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    METHOD_CHANGED = "METHOD_CHANGED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


@dataclass(frozen=True)
class SnapshotCandidate:
    """One finalized candidate as recorded at one pinned release."""

    gene_id: str
    rank: int | None
    modalities: tuple[str, ...]
    evidence_level: str

    def __post_init__(self) -> None:
        text(self.gene_id, "snapshot candidate gene id")
        if self.rank is not None:
            count(self.rank, "snapshot candidate rank")
            require(self.rank >= 1, "snapshot candidate rank must be at least 1")
        strings(self.modalities, "snapshot candidate modalities")
        require(self.modalities == tuple(sorted(set(self.modalities))),
                "snapshot candidate modalities must be sorted and unique")
        text(self.evidence_level, "snapshot candidate evidence level")


@dataclass(frozen=True)
class ReleaseSnapshot:
    """One campaign's persisted outcome summary at one pinned source context."""

    campaign_id: str
    release: str
    release_commit: str | None
    methods_hash: str
    candidates: tuple[SnapshotCandidate, ...]

    def __post_init__(self) -> None:
        text(self.campaign_id, "release snapshot campaign id")
        text(self.release, "release snapshot release")
        if self.release_commit is not None:
            text(self.release_commit, "release snapshot commit")
        sha256(self.methods_hash, "release snapshot methods hash")
        require(type(self.candidates) is tuple
                and all(isinstance(item, SnapshotCandidate) for item in self.candidates),
                "release snapshot candidates must be immutable records")
        gene_ids = [item.gene_id for item in self.candidates]
        require(gene_ids == sorted(gene_ids) and len(set(gene_ids)) == len(gene_ids),
                "release snapshot candidates must be sorted and unique")

    def payload(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "release": self.release,
            "release_commit": self.release_commit,
            "methods_hash": self.methods_hash,
            "candidates": [
                {"gene_id": item.gene_id, "rank": item.rank,
                 "modalities": list(item.modalities), "evidence_level": item.evidence_level}
                for item in self.candidates
            ],
        }


@dataclass(frozen=True)
class ComparisonRow:
    gene_id: str | None
    classification: ComparisonClass
    detail: str

    def __post_init__(self) -> None:
        if self.gene_id is not None:
            text(self.gene_id, "comparison row gene id")
        require(isinstance(self.classification, ComparisonClass), "invalid comparison class")
        text(self.detail, "comparison row detail")
