"""Existing mutation bucket semantics, retained without a denominator claim."""

from dataclasses import dataclass
from typing import Literal

from cancerjev.gdc.parsers import GeneCaseCounts, ProjectCoverage
from cancerjev.science.errors import ScienceError


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
