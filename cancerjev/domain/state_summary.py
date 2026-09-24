"""Typed existing descriptive fields consumed by Wide projection and policy.

This is the v2 compatibility contract, not a relabelling of history as v3.
"""

from dataclasses import dataclass
from typing import Any

from cancerjev.domain._json import decode
from cancerjev.domain.measurements import ContractError


@dataclass(frozen=True)
class ProjectSummary:
    project_id: str
    examined_cases: int
    affected_cases: int | None
    ssm_coverage_cases: int | None
    expression_median: float | None
    expression_sample_sd: float | None
    expression_n_finite: int | None
    expression_n_missing: int | None
    provider_median: float | None
    provider_stddev: float | None


@dataclass(frozen=True)
class StateSummary:
    state_id: str
    scientific_hash: str
    gene_id: str
    gene_symbol: str
    biotype: str | None
    cancer_census: bool | None
    project_id: str | None
    cohort: str | None
    domain: str | None
    projects: tuple[ProjectSummary, ...]
    modalities: tuple[str, ...]
    workflows: tuple[str, ...]
    examined_case_frame: str
    selection_bias: str
    mutation_coverage_complete: bool
    expression_availability: str
    completeness: str
    scientific_sufficiency: str
    coverage_imbalance: bool
    missingness: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        for values in (self.projects, self.modalities, self.workflows, self.missingness, self.warnings):
            if type(values) is not tuple:
                raise ContractError("state summary collections must be immutable")
        if not all(isinstance(p, ProjectSummary) for p in self.projects):
            raise ContractError("typed project summaries required")


@dataclass(frozen=True)
class ComputedStatisticalState:
    summary: StateSummary
    serialized: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.summary, StateSummary) or type(self.serialized) is not bytes:
            raise ContractError("typed summary and immutable serialization required")

    def boundary_representation(self) -> dict[str, Any]:
        return decode(self.serialized)
