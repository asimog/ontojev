"""Immutable integrity outcomes. Diagnostic JSON is not a scientific measurement."""

from dataclasses import dataclass
from typing import Literal

from cancerjev.domain._json import decode
from cancerjev.domain.evidence import CheckSummary
from cancerjev.domain.measurements import ContractError

CheckOutcome = Literal["VERIFIED", "CONTRADICTED", "NOT_OBSERVED"]


@dataclass(frozen=True)
class IntegrityCheck:
    check_id: str
    claim: str
    outcome: CheckOutcome
    observed_json: bytes
    expected_json: bytes
    n_effective: int | None
    notes: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.outcome not in {"VERIFIED", "CONTRADICTED", "NOT_OBSERVED"}:
            raise ContractError("unknown integrity check outcome")
        if not self.check_id or not self.claim:
            raise ContractError("integrity checks require an identity and claim")
        if self.n_effective is not None and (type(self.n_effective) is not int or self.n_effective < 0):
            raise ContractError("invalid effective count")
        if type(self.notes) is not tuple or type(self.limitations) is not tuple:
            raise ContractError("check annotations must be immutable")
        if type(self.observed_json) is not bytes or type(self.expected_json) is not bytes:
            raise ContractError("check diagnostics must be immutable boundary bytes")

    def boundary_representation(self) -> dict[str, object]:
        return {"check_id": self.check_id, "claim": self.claim, "outcome": self.outcome,
                "observed": decode(self.observed_json), "expected": decode(self.expected_json),
                "n_effective": self.n_effective, "notes": list(self.notes),
                "limitations": list(self.limitations)}


@dataclass(frozen=True)
class ComputedEvidenceRevision:
    """Typed held check results plus the unchanged v2 archival representation.

    The integrity actions inspect that representation deliberately: their question
    is whether retained artifacts faithfully restate their inputs, not whether a
    new biological measurement can be inferred from JSON.
    """

    evidence_state_id: str
    scientific_hash: str
    candidate_id: str
    parent_id: str
    iteration: int
    action_id: str
    checks: tuple[IntegrityCheck, ...]
    serialized: bytes

    def __post_init__(self) -> None:
        if type(self.checks) is not tuple or not all(isinstance(c, IntegrityCheck) for c in self.checks):
            raise ContractError("revision checks must be immutable typed checks")
        if len({c.check_id for c in self.checks}) != len(self.checks):
            raise ContractError("duplicate integrity check identity")
        if type(self.iteration) is not int or self.iteration < 1:
            raise ContractError("a computed revision requires a positive iteration")
        if not all((self.evidence_state_id, self.scientific_hash, self.candidate_id,
                    self.parent_id, self.action_id)) or type(self.serialized) is not bytes:
            raise ContractError("revision identity, parent and immutable serialization required")

    @property
    def check_summary(self) -> CheckSummary:
        return CheckSummary(len(self.checks),
                            sum(c.outcome == "VERIFIED" for c in self.checks),
                            sum(c.outcome == "CONTRADICTED" for c in self.checks),
                            sum(c.outcome == "NOT_OBSERVED" for c in self.checks))

    def boundary_representation(self) -> dict[str, object]:
        return decode(self.serialized)
