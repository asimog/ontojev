"""Immutable evidence-revision contracts. Integrity outcomes are not biological measurements.

An ``EvidenceState`` is the canonical runtime revision object: E0 is the accepted
baseline of a promoted StatisticalState and E1/E2 are deterministic integrity
revisions produced by registered actions. Check diagnostics are retained as
immutable boundary bytes because artifact fidelity is their subject; they are
never reconstructed into a legacy scientific model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain._json import decode
from cancerjev.domain.measurements import (
    ContractError,
    EntityRef,
    MethodIdentityRef,
    MetricAvailability,
    MetricRecord,
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
    observed: bytes
    expected: bytes
    notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    missing_count: int = 0
    missing_reason: str | None = None

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
        if type(self.observed) is not bytes or type(self.expected) is not bytes:
            raise ContractError("check diagnostics must be immutable boundary bytes")
        decode(self.observed)
        decode(self.expected)
        strings(self.notes, "check notes")
        strings(self.limitations, "check limitations")
        count(self.missing_count, "check missing count")
        require(self.missing_count == 0 or self.missing_reason is not None,
                "missing check evidence requires a reason")
        require((self.outcome == CheckOutcome.NOT_OBSERVED) == (self.missing_count > 0),
                "check availability disagrees with its outcome")

    @property
    def availability(self) -> str:
        return "NOT_OBSERVED" if self.outcome == CheckOutcome.NOT_OBSERVED else "OBSERVED"

    def boundary_representation(self) -> dict[str, object]:
        return {
            "check_id": self.check_id, "claim": self.claim, "outcome": str(self.outcome),
            "observed": decode(self.observed), "expected": decode(self.expected),
            "n_effective": self.n_effective, "notes": list(self.notes),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class MeasuredObservation:
    """One deterministic measured value newly produced by a registered action.

    Unlike a restated baseline, this records evidence computed by the action's
    declared method over an explicit bounded population; an unavailable
    observation carries its typed reason and never fabricates a VERIFIED check.
    """

    method_id: str
    method_version: str
    evidence_kind: str
    observed: bytes
    availability: str
    n_effective: int | None
    population_hash: str
    reason: str | None = None
    notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.method_id, self.method_version, self.evidence_kind):
            text(value, "measured observation")
        require(self.availability in {"OBSERVED", "NOT_OBSERVED"},
                "invalid measured observation availability")
        if type(self.observed) is not bytes:
            raise ContractError("measured observation payload must be immutable boundary bytes")
        decode(self.observed)
        if self.n_effective is not None:
            count(self.n_effective, "measured observation n_effective")
        sha256(self.population_hash, "measured observation population hash")
        if self.reason is not None:
            text(self.reason, "measured observation reason")
        if self.availability == "NOT_OBSERVED":
            require(self.reason is not None, "an unavailable observation requires its reason")
        strings(self.notes, "measured observation notes")
        strings(self.limitations, "measured observation limitations")


@dataclass(frozen=True)
class BaselineObservation:
    """Typed restatement of one measured baseline value.

    A baseline restatement is not a falsifiable integrity check: it records what
    the accepted state measured, with its availability and missingness, so a Deep
    projection can present the revision's own evidence without re-reading JSON.
    """

    method_id: str
    method_version: str
    observed: bytes
    availability: str
    n_effective: int | None
    missingness_count: int | None
    missingness_reason: str | None
    notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        text(self.method_id, "baseline observation method")
        text(self.method_version, "baseline observation method version")
        require(self.availability in {"OBSERVED", "NOT_OBSERVED"}, "invalid baseline availability")
        if type(self.observed) is not bytes:
            raise ContractError("baseline diagnostics must be immutable boundary bytes")
        decode(self.observed)
        if self.n_effective is not None:
            count(self.n_effective, "n_effective")
        if self.missingness_count is not None:
            count(self.missingness_count, "baseline missingness count")
            require(self.missingness_count == 0 or self.missingness_reason is not None,
                    "baseline missingness requires a reason")
        strings(self.notes, "baseline observation notes")
        strings(self.limitations, "baseline observation limitations")

    def boundary_representation(self) -> dict[str, object]:
        return {
            "method_id": self.method_id, "method_version": self.method_version,
            "observed": decode(self.observed), "availability": self.availability,
            "n_effective": self.n_effective,
            "missingness": {"count": self.missingness_count, "reason": self.missingness_reason},
            "notes": list(self.notes), "limitations": list(self.limitations),
        }


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
    def from_checks(cls, checks: tuple[EvidenceCheck, ...]) -> CheckSummary:
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
class SourceStateBinding:
    state_id: str
    state_identity_hash: str
    state_artifact_id: str
    state_artifact_sha256: str

    def __post_init__(self) -> None:
        for value in (self.state_id, self.state_artifact_id):
            text(value, "source state binding")
        sha256(self.state_identity_hash, "source state identity")
        sha256(self.state_artifact_sha256, "source state artifact hash")


@dataclass(frozen=True)
class ResearchPuzzle:
    origin: str
    question: str
    interpretation: str
    proposed_action_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("origin", "question", "interpretation"):
            text(getattr(self, name), name)
        strings(self.proposed_action_ids, "proposed action ids")


@dataclass(frozen=True)
class ProjectEvidenceRow:
    """Typed restatement of the accepted state's project-level metrics."""

    project_id: str
    affected_case_count: MetricRecord
    examined_cases: MetricRecord
    project_case_with_ssm: MetricRecord
    cases_with_expression: MetricRecord
    missing_measurements: MetricRecord

    def __post_init__(self) -> None:
        text(self.project_id, "project id")
        for name in ("affected_case_count", "examined_cases", "project_case_with_ssm",
                     "cases_with_expression", "missing_measurements"):
            require(isinstance(getattr(self, name), MetricRecord), f"{name} must be a typed metric")
        require(self.examined_cases.unit == "cases" and self.cases_with_expression.unit == "cases",
                "project evidence counts must use the case unit")

    def metrics(self) -> tuple[tuple[str, MetricRecord], ...]:
        return (
            ("affected_case_count", self.affected_case_count),
            ("examined_cases", self.examined_cases),
            ("project_case_with_ssm", self.project_case_with_ssm),
            ("cases_with_expression", self.cases_with_expression),
            ("missing_measurements", self.missing_measurements),
        )


@dataclass(frozen=True)
class MissingEvidence:
    needed_evidence: str
    availability: MetricAvailability
    reason: str | None

    def __post_init__(self) -> None:
        text(self.needed_evidence, "needed evidence")
        require(isinstance(self.availability, MetricAvailability), "invalid missing evidence availability")
        if self.availability == MetricAvailability.OBSERVED:
            raise ContractError("observed evidence cannot be listed as missing")
        if self.reason is not None:
            text(self.reason, "missing evidence reason")


@dataclass(frozen=True)
class InputArtifactRef:
    kind: str
    ref: str | None
    sha256: str | None
    verified: bool

    def __post_init__(self) -> None:
        text(self.kind, "input artifact kind")
        if self.ref is not None:
            text(self.ref, "input artifact ref")
        if self.sha256 is not None:
            sha256(self.sha256, "input artifact hash")
        require(type(self.verified) is bool, "verified must be bool")


@dataclass(frozen=True)
class EvidenceProvenance:
    gdc_release: str
    sources: tuple[ScientificSource, ...]
    methods: tuple[MethodIdentityRef, ...]
    environment_hash: str
    action_registry_version: str
    selection_artifact_sha256: str
    input_artifacts: tuple[InputArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        text(self.gdc_release, "gdc release")
        require(type(self.sources) is tuple and all(isinstance(s, ScientificSource) for s in self.sources),
                "evidence sources must be immutable records")
        require(type(self.methods) is tuple and all(isinstance(m, MethodIdentityRef) for m in self.methods),
                "evidence methods must be typed identities")
        strings(tuple(m.method_id for m in self.methods), "evidence method ids")
        sha256(self.environment_hash, "environment hash")
        text(self.action_registry_version, "action registry version")
        sha256(self.selection_artifact_sha256, "selection artifact hash")
        require(type(self.input_artifacts) is tuple
                and all(isinstance(a, InputArtifactRef) for a in self.input_artifacts),
                "input artifacts must be immutable records")


@dataclass(frozen=True)
class EvidenceState:
    """One immutable evidence revision: accepted baseline (E0) or action revision."""

    entity: EntityRef
    accepted_state_hash: str
    source_state: SourceStateBinding
    parent_evidence_hash: str | None
    revision_index: int
    action: ActionRef | None
    puzzle: ResearchPuzzle | None
    checks: tuple[EvidenceCheck, ...]
    baseline_observations: tuple[BaselineObservation, ...]
    project_evidence: tuple[ProjectEvidenceRow, ...]
    missing_evidence: tuple[MissingEvidence, ...]
    quality: Quality
    warnings: tuple[str, ...]
    provenance: EvidenceProvenance
    measured_observations: tuple[MeasuredObservation, ...] = ()

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid evidence entity")
        sha256(self.accepted_state_hash, "accepted_state_hash")
        require(isinstance(self.source_state, SourceStateBinding), "invalid source state binding")
        require(self.source_state.state_identity_hash == self.accepted_state_hash,
                "source state binding does not match the accepted state hash")
        count(self.revision_index, "revision index")
        require(self.revision_index <= 2, "revision exceeds E0/E1/E2")
        if self.revision_index == 0:
            require(self.parent_evidence_hash is None and self.action is None and not self.checks,
                    "E0 is an accepted baseline, not an action revision")
            require(self.puzzle is not None and self.puzzle.origin == "STATISTICAL_STATE_BASELINE",
                    "E0 requires its baseline puzzle")
            require(not self.measured_observations,
                    "E0 carries no action-measured observations")
        else:
            require(self.parent_evidence_hash is not None and isinstance(self.action, ActionRef),
                    "action revision requires parent hash and action")
            parent_evidence_hash = self.parent_evidence_hash
            if parent_evidence_hash is not None:
                sha256(parent_evidence_hash, "parent_evidence_hash")
            require(bool(self.checks), "integrity revision requires checks")
            require(not self.baseline_observations,
                    "action revision restates only its own checks")
        if self.parent_evidence_hash is not None:
            sha256(self.parent_evidence_hash, "parent_evidence_hash")
        require(isinstance(self.quality, Quality), "invalid evidence quality")
        require(type(self.checks) is tuple and all(isinstance(c, EvidenceCheck) for c in self.checks),
                "evidence checks must be immutable records")
        require(type(self.baseline_observations) is tuple
                and all(isinstance(o, BaselineObservation) for o in self.baseline_observations),
                "baseline observations must be immutable records")
        require(type(self.measured_observations) is tuple
                and all(isinstance(o, MeasuredObservation) for o in self.measured_observations),
                "measured observations must be immutable records")
        CheckSummary.from_checks(self.checks)
        require(type(self.project_evidence) is tuple
                and all(isinstance(r, ProjectEvidenceRow) for r in self.project_evidence),
                "project evidence must be immutable typed rows")
        strings(tuple(r.project_id for r in self.project_evidence), "project evidence ids")
        require(type(self.missing_evidence) is tuple
                and all(isinstance(m, MissingEvidence) for m in self.missing_evidence),
                "missing evidence must be immutable records")
        require(isinstance(self.provenance, EvidenceProvenance), "invalid evidence provenance")
        require(all(s.release == self.entity.release for s in self.provenance.sources),
                "mixed evidence/source releases")
        require(type(self.warnings) is tuple and all(isinstance(w, str) and w for w in self.warnings),
                "evidence warnings must be nonblank strings")

    @property
    def summary(self) -> CheckSummary:
        return CheckSummary.from_checks(self.checks)

    @property
    def sources(self) -> tuple[ScientificSource, ...]:
        return self.provenance.sources


__all__ = [
    "ActionRef",
    "BaselineObservation",
    "CheckOutcome",
    "CheckSummary",
    "EvidenceCheck",
    "EvidenceProvenance",
    "EvidenceState",
    "InputArtifactRef",
    "MethodIdentityRef",
    "MissingEvidence",
    "ProjectEvidenceRow",
    "ResearchPuzzle",
    "SourceStateBinding",
]
