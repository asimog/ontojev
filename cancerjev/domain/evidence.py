"""Immutable revision contracts. Integrity outcomes are not biological measurements."""

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import (
    ContractError,
    EntityRef,
    Quality,
    ScientificSource,
    count,
    require,
    sha256,
    strings,
    text,
)


class CheckOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    NOT_OBSERVED = "NOT_OBSERVED"


@dataclass(frozen=True)
class EvidenceCheck:
    check_id: str
    method_id: str
    method_version: str
    outcome: CheckOutcome
    claim: str
    input_hashes: tuple[str, ...]
    reason: str | None
    n_effective: int | None

    def __post_init__(self) -> None:
        for value in (self.check_id, self.method_id, self.method_version, self.claim):
            text(value, "check contract")
        require(isinstance(self.outcome, CheckOutcome), "invalid check outcome")
        strings(self.input_hashes, "check input hashes")
        require(bool(self.input_hashes), "check must reference its input")
        for value in self.input_hashes:
            sha256(value, "input hash")
        if self.reason is not None:
            text(self.reason, "check reason")
        require(self.outcome == CheckOutcome.VERIFIED or self.reason is not None, "nonverified check requires reason")
        if self.n_effective is not None:
            count(self.n_effective, "n_effective")


@dataclass(frozen=True)
class CheckSummary:
    total: int
    verified: int
    contradicted: int
    not_observed: int

    def __post_init__(self) -> None:
        for value in (self.total, self.verified, self.contradicted, self.not_observed):
            count(value, "check count")
        require(self.total == self.verified + self.contradicted + self.not_observed, "check counts do not sum")

    @classmethod
    def from_checks(cls, checks: tuple[EvidenceCheck, ...]) -> "CheckSummary":
        require(type(checks) is tuple and all(isinstance(c, EvidenceCheck) for c in checks), "invalid checks")
        strings(tuple(c.check_id for c in checks), "check IDs")
        return cls(len(checks), sum(c.outcome == CheckOutcome.VERIFIED for c in checks),
                   sum(c.outcome == CheckOutcome.CONTRADICTED for c in checks),
                   sum(c.outcome == CheckOutcome.NOT_OBSERVED for c in checks))


@dataclass(frozen=True)
class ActionRef:
    action_id: str
    version: str

    def __post_init__(self) -> None:
        text(self.action_id, "action_id")
        text(self.version, "action version")


@dataclass(frozen=True)
class EvidenceStateV3:
    entity: EntityRef
    accepted_state_hash: str
    parent_evidence_hash: str | None
    revision_index: int
    action: ActionRef | None
    checks: tuple[EvidenceCheck, ...]
    quality: Quality
    sources: tuple[ScientificSource, ...]

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid evidence entity")
        sha256(self.accepted_state_hash, "accepted_state_hash")
        count(self.revision_index, "revision index")
        require(self.revision_index <= 2, "revision exceeds E0/E1/E2")
        if self.revision_index == 0:
            require(self.parent_evidence_hash is None and self.action is None and not self.checks,
                    "E0 is an accepted baseline, not an action revision")
        else:
            require(self.parent_evidence_hash is not None and isinstance(self.action, ActionRef),
                    "action revision requires parent hash and action")
            if self.parent_evidence_hash is None:
                raise ContractError("action revision requires parent hash")
            sha256(self.parent_evidence_hash, "parent_evidence_hash")
            require(bool(self.checks), "integrity revision requires checks")
        require(isinstance(self.quality, Quality), "invalid evidence quality")
        require(type(self.sources) is tuple and all(isinstance(s, ScientificSource) for s in self.sources),
                "invalid evidence sources")
        require(all(s.release == self.entity.release for s in self.sources), "mixed evidence/source releases")
        CheckSummary.from_checks(self.checks)

    @property
    def summary(self) -> CheckSummary:
        return CheckSummary.from_checks(self.checks)
