"""Operational envelopes binding registered ids/hashes to scientific objects.

Run, state, candidate, artifact and attempt identifiers are operational. They
never enter scientific identity; these records carry them alongside the typed
scientific object so runtime and storage consumers never reconstruct one from
the other.
"""

from dataclasses import dataclass

from cancerjev.domain.evidence import EvidenceState
from cancerjev.domain.hypotheses import HypothesisDraft
from cancerjev.domain.measurements import require, sha256, text
from cancerjev.domain.scientific import StatisticalState


@dataclass(frozen=True)
class StateRecord:
    """One registered StatisticalState plus its operational id and identity hash."""

    state_id: str
    state_hash: str
    state: StatisticalState

    def __post_init__(self) -> None:
        text(self.state_id, "state id")
        sha256(self.state_hash, "state hash")
        require(isinstance(self.state, StatisticalState), "state record requires a typed state")


@dataclass(frozen=True)
class EvidenceRecord:
    """One registered EvidenceState revision plus its operational id and hash."""

    evidence_state_id: str
    evidence_hash: str
    revision: EvidenceState

    def __post_init__(self) -> None:
        text(self.evidence_state_id, "evidence state id")
        sha256(self.evidence_hash, "evidence hash")
        require(isinstance(self.revision, EvidenceState), "evidence record requires a typed revision")


@dataclass(frozen=True)
class HypothesisRecord:
    """One registered generated hypothesis plus its operational ids.

    The hypothesis id and candidate id are operational: they bind the review to
    the run's records and never enter the hypothesis projection.
    """

    hypothesis_id: str
    candidate_id: str
    draft: HypothesisDraft

    def __post_init__(self) -> None:
        text(self.hypothesis_id, "hypothesis id")
        text(self.candidate_id, "hypothesis candidate id")
        require(isinstance(self.draft, HypothesisDraft), "hypothesis record requires a typed draft")
