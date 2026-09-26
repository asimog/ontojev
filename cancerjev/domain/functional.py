"""Typed functional/external-source posture, checked against its decision record.

No functional source is adopted this cycle: the record and these constants must
agree, and nothing here can manufacture functional evidence or promote a level.
"""

from __future__ import annotations

from enum import StrEnum

FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION = "1"
FUNCTIONAL_SOURCE_DECISION_RECORD_PATH = "docs/FUNCTIONAL_SOURCES.md"


class SourceDecision(StrEnum):
    ADOPT = "ADOPT"
    DEFER = "DEFER"
    REJECT = "REJECT"


FUNCTIONAL_SOURCE_DECISIONS: dict[str, SourceDecision] = {
    "DEPMAP_CRISPR": SourceDecision.DEFER,
    "SANGER_CGC": SourceDecision.DEFER,
    "TARGETABILITY_RESOURCES": SourceDecision.DEFER,
    "INDEPENDENT_COHORT_REPLICATION": SourceDecision.DEFER,
}

EVIDENCE_AXES = (
    "GENOMIC_DISCOVERY",
    "STATISTICAL_SUPPORT",
    "REPLICATION",
    "FUNCTIONAL_DEPENDENCY",
    "KNOWN_CANCER_CONTEXT",
    "TARGETABILITY",
    "CLINICAL_EVIDENCE",
)

AXIS_SEPARATION_LIMITATION = (
    "pan-cancer dependency is never cohort-specific support; dependency is not therapeutic "
    "efficacy; known-gene status is not proof of a target in this cohort"
)
