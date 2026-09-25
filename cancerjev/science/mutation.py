"""Existing mutation bucket semantics, retained without a denominator claim.

Also owns the declared canonical-consequence composition method: descriptive
counts only, transcript-duplication-safe, and explicitly free of p-values,
q-values or any driver-significance claim.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from cancerjev.domain.discovery import (
    JEV_REVIEW_HOTSPOT_MIN_RECORDS,
    JEV_REVIEW_HOTSPOT_TOP_POSITION_SHARE,
    JEV_REVIEW_HOTSPOT_TRIGGER,
    JEV_REVIEW_MAX_OCCURRENCE_PER_CASE_RATIO,
    JEV_REVIEW_OCCURRENCE_RATIO_TRIGGER,
    MUTATION_COMPOSITION_LIMITATIONS,
    MUTATION_HOTSPOT_TOP_POSITIONS,
    MutationDescriptiveEvidence,
    mutation_composition_method,
)
from cancerjev.gdc.parsers import GeneCaseCounts, ProjectCoverage
from cancerjev.science.errors import ScienceError


def mutation_descriptive_evidence(
    *, distinct_cases: int, occurrence_docs: int,
    consequences: Mapping[str, int], positions: Mapping[int, int],
    transcript_counts: Mapping[str, int],
) -> MutationDescriptiveEvidence:
    """Deterministic canonical-only composition; occurrence-level dedup protects transcripts."""
    composition = tuple(sorted((term, count) for term, count in consequences.items()
                               if count > 0))
    top = tuple(sorted(((position, count) for position, count in positions.items()
                        if count > 0), key=lambda item: (-item[1], item[0]))
                [:MUTATION_HOTSPOT_TOP_POSITIONS])
    hotspot: str | None = None
    total_positions = sum(count for count in positions.values() if count > 0)
    if top and total_positions >= JEV_REVIEW_HOTSPOT_MIN_RECORDS:
        position, count = top[0]
        if count / total_positions >= JEV_REVIEW_HOTSPOT_TOP_POSITION_SHARE:
            hotspot = f"HOTSPOT_PROTEIN_START_{position}"
    trigger: str | None = None
    if (distinct_cases > 0
            and occurrence_docs > JEV_REVIEW_MAX_OCCURRENCE_PER_CASE_RATIO * distinct_cases):
        trigger = JEV_REVIEW_OCCURRENCE_RATIO_TRIGGER
    elif hotspot is not None:
        trigger = JEV_REVIEW_HOTSPOT_TRIGGER
    return MutationDescriptiveEvidence(
        consequence_composition=composition,
        canonical_transcript_n=len(transcript_counts),
        protein_position_top=top,
        hotspot_descriptor=hotspot,
        review_trigger=trigger,
        method=mutation_composition_method(),
        limitations=MUTATION_COMPOSITION_LIMITATIONS,
    )


@dataclass(frozen=True)
class MutationObservation:
    project_id: str
    gene_id: str
    affected_cases: int | None
    availability: Literal["OBSERVED", "NOT_OBSERVED", "PARTIAL"]
    reason: str | None
    ssm_coverage_cases: int | None
    acquisition_complete: bool

    def __post_init__(self) -> None:
        if (self.availability == "OBSERVED") != (self.affected_cases is not None):
            raise ScienceError("INVALID_METRIC", "mutation observation value/status mismatch")
        for value in (self.affected_cases, self.ssm_coverage_cases):
            if value is not None and (type(value) is not int or value < 0):
                raise ScienceError("INVALID_METRIC", "mutation counts must be nonnegative integers")
        if self.availability != "OBSERVED" and not self.reason:
            raise ScienceError("INVALID_METRIC", "unobserved mutation requires a reason")


def mutation_observation(project_id: str, gene_id: str, counts: GeneCaseCounts,
                         coverage: ProjectCoverage) -> MutationObservation:
    projects = counts.projects.get(project_id)
    affected = None if projects is None else projects.get(gene_id)
    reason = ("PROJECT_NOT_IN_AGGREGATION" if projects is None else "GENE_BUCKET_ABSENT")
    return MutationObservation(
        project_id, gene_id, affected,
        "OBSERVED" if affected is not None else ("NOT_OBSERVED" if counts.complete else "PARTIAL"),
        None if affected is not None else reason,
        coverage.case_with_ssm.get(project_id), counts.complete and coverage.complete,
    )
