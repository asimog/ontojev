"""Typed, reproducible scientific scope for live research runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from cancerjev.gdc.endpoints import (
    MAX_CASE_IDS,
    MAX_CASES_PAGE,
    MAX_DISCOVERY_HITS,
    MAX_FILES_PAGE,
    MAX_GENE_IDS,
)


@dataclass(frozen=True)
class CohortSpec:
    cohort_id: str
    domain: str
    project_id: str

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ValueError(f"{name} must be a non-empty string of at most 128 characters")


@dataclass(frozen=True)
class AcquisitionSpec:
    case_page_size: int
    case_batch_size: int
    max_cohort_cases: int
    discovery_gene_limit: int
    count_gene_limit: int
    candidate_gene_limit: int
    expression_file_sample_size: int

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.case_page_size <= MAX_CASES_PAGE:
            raise ValueError(f"case_page_size must be 1..{MAX_CASES_PAGE}")
        if not 1 <= self.case_batch_size <= MAX_CASE_IDS:
            raise ValueError(f"case_batch_size must be 1..{MAX_CASE_IDS}")
        if not 1 <= self.max_cohort_cases <= self.case_page_size * 10:
            raise ValueError("max_cohort_cases must fit within the ten-page query budget")
        if not 1 <= self.discovery_gene_limit <= MAX_DISCOVERY_HITS:
            raise ValueError(f"discovery_gene_limit must be 1..{MAX_DISCOVERY_HITS}")
        if not 1 <= self.count_gene_limit <= MAX_GENE_IDS:
            raise ValueError(f"count_gene_limit must be 1..{MAX_GENE_IDS}")
        if not 1 <= self.candidate_gene_limit <= self.count_gene_limit:
            raise ValueError("candidate_gene_limit must be 1..count_gene_limit")
        if self.candidate_gene_limit > MAX_GENE_IDS:
            raise ValueError(f"candidate_gene_limit must not exceed {MAX_GENE_IDS}")
        if not 1 <= self.expression_file_sample_size <= MAX_FILES_PAGE:
            raise ValueError(f"expression_file_sample_size must be 1..{MAX_FILES_PAGE}")


@dataclass(frozen=True)
class ResearchSpec:
    spec_id: str
    cohort: CohortSpec
    acquisition: AcquisitionSpec

    def __post_init__(self) -> None:
        if not isinstance(self.spec_id, str) or not self.spec_id.strip() or len(self.spec_id) > 128:
            raise ValueError("spec_id must be a non-empty string of at most 128 characters")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def cohort_selection_rule(self) -> str:
        return (
            f"single explicit cohort: domain={self.cohort.domain}, cohort={self.cohort.cohort_id}; "
            "the cohort is selected by exact project_id from the open GDC project inventory; "
            "no case-count window and no cross-project pooling"
        )

    def gene_selection_rule(self) -> str:
        return (
            f"genes discovered from the provider top-mutated ranking for {self.cohort.project_id} "
            f"(size {self.acquisition.discovery_gene_limit}); selection takes the top "
            f"{self.acquisition.candidate_gene_limit} genes by provider rank, skipping duplicates; "
            "_score is provider selection metadata and is never a mutation count or effect size"
        )


LUAD_RESEARCH_V1 = ResearchSpec(
    spec_id="LUAD_RESEARCH_V1",
    cohort=CohortSpec(
        cohort_id="TCGA-LUAD",
        domain="lung cancer",
        project_id="TCGA-LUAD",
    ),
    acquisition=AcquisitionSpec(
        case_page_size=250,
        case_batch_size=250,
        max_cohort_cases=1_000,
        discovery_gene_limit=20,
        count_gene_limit=100,
        candidate_gene_limit=10,
        expression_file_sample_size=5,
    ),
)
