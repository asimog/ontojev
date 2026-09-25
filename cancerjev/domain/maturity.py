"""Evidence maturity, information roles and external-knowledge classification.

Maturity is a pure deterministic function of persisted typed state: no Jev
judgment, LLM output or ranking can promote it. Known-cancer context is
admissible only as bounded judgment context; it can never serve as a discovery
feature, a disposition threshold or an admission input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import require, sha256, strings, text
from cancerjev.domain.scientific import (
    EVIDENCE_LEVEL_ORDER,
    EvidenceLevel,
    StatisticalState,
)

EVIDENCE_MATURITY_POLICY_VERSION = "evidence-maturity-v1"


class KnowledgeRole(StrEnum):
    DISCOVERY_INPUT = "DISCOVERY_INPUT"
    VALIDATION_LABEL = "VALIDATION_LABEL"
    ORTHOGONAL_FOLLOW_UP = "ORTHOGONAL_FOLLOW_UP"
    KNOWN_CANCER_CONTEXT = "KNOWN_CANCER_CONTEXT"


# GeneAnnotation.cancer_census carries exactly this role: judgment context only,
# never a discovery feature, threshold or admission input.
CANCER_CENSUS_KNOWLEDGE_ROLE = KnowledgeRole.KNOWN_CANCER_CONTEXT


@dataclass(frozen=True)
class ExternalKnowledgeRef:
    """One externally sourced knowledge axis with its declared information role."""

    source: str
    version: str
    license_ref: str
    access_level: str
    role: KnowledgeRole
    mapping_hash: str

    def __post_init__(self) -> None:
        for value in (self.source, self.version, self.license_ref, self.access_level):
            text(value, "external knowledge reference")
        require(self.access_level == "OPEN", "only open-access external knowledge is representable")
        require(isinstance(self.role, KnowledgeRole), "invalid knowledge role")
        sha256(self.mapping_hash, "external knowledge mapping hash")


@dataclass(frozen=True)
class EvidenceMaturity:
    level: EvidenceLevel
    reasons: tuple[str, ...]
    unattained: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        require(isinstance(self.level, EvidenceLevel), "invalid evidence level")
        strings(self.reasons, "evidence maturity reasons")
        require(bool(self.reasons), "a maturity derivation records its reasons")
        for item in self.unattained:
            require(isinstance(item, tuple) and len(item) == 2
                    and isinstance(item[0], str) and bool(item[0])
                    and isinstance(item[1], str) and bool(item[1]),
                    "invalid unattained prerequisite")
        levels = [item[0] for item in self.unattained]
        require(len(set(levels)) == len(levels), "unattained prerequisites must be unique")
        current_rank = EVIDENCE_LEVEL_ORDER.index(self.level)
        known = [member.value for member in EVIDENCE_LEVEL_ORDER]
        ranks: list[int] = []
        for level, _ in self.unattained:
            require(level in known, "unknown unattained level")
            rank = known.index(level)
            require(rank > current_rank, "unattained levels must be above the derived level")
            ranks.append(rank)
        require(ranks == sorted(ranks) and len(set(ranks)) == len(ranks),
                "unattained prerequisites must be ordered and unique")


def derive_evidence_maturity(state: StatisticalState) -> EvidenceMaturity:
    """Pure deterministic derivation from persisted typed evidence only.

    MEASURED = lane measurements exist for this gene at the pinned release;
    DESCRIPTIVE_CANDIDATE = at least one validated modality nominated the gene
    (RETAINED/RETAIN). Higher levels are unattainable without their declared
    contracts and are reported with the exact missing prerequisite.
    """
    nominated = sorted(modality for modality, disposition in state.nominations
                       if disposition in {"RETAINED", "RETAIN"})
    reasons = ["typed lane measurements exist at the pinned release"]
    if nominated:
        level = EvidenceLevel.DESCRIPTIVE_CANDIDATE
        reasons.append("nominated by validated modality: " + ", ".join(nominated))
    else:
        level = EvidenceLevel.MEASURED
    unattained = (
        (EvidenceLevel.STATISTICALLY_SUPPORTED.value,
         "no declared inferential population/null/FDR contract exists"),
        (EvidenceLevel.INTERNALLY_REPLICATED.value,
         "no persisted case-disjoint replication partition exists for this gene"),
        (EvidenceLevel.EXTERNALLY_REPLICATED.value,
         "requires a separately validated independent campaign/cohort"),
        (EvidenceLevel.FUNCTIONALLY_SUPPORTED.value,
         "requires an admitted functional-evidence contract (P17)"),
    )
    return EvidenceMaturity(level=level, reasons=tuple(reasons), unattained=unattained)
