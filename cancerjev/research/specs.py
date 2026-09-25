"""Typed, reproducible scientific scope for live research runs.

One canonical ``ResearchSpec`` owns the reproducible configuration of a research
run: the explicit single cohort, bounded acquisition sizes, the systematic Stage 4
discovery configuration (bounded indexed gene-universe enumeration and mutation
batching), the implemented composition (mutation counts plus the local expression
summary), the registered deterministic actions, the policy identities and the
scientific limits.

Unsupported runtime configurations are not representable: an independent
expression arm and CNV acquisition have no field in schema 4 and are rejected
explicitly here and by the strict reader. The systematic discovery configuration
is a fixed deterministic contract, not a caller-controlled query builder. JSON
exists only as a boundary representation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from cancerjev.domain._json import integer, obj, string, string_tuple
from cancerjev.domain.discovery import DISCOVERY_UNIVERSE_METHOD, DiscoverySpec
from cancerjev.domain.measurements import count, require, strings, text
from cancerjev.gdc.endpoints import (
    MAX_CASE_IDS,
    MAX_CASES_PAGE,
    MAX_DISCOVERY_HITS,
    MAX_FILES_PAGE,
    MAX_GENE_IDS,
)

RESEARCH_SPEC_SCHEMA_VERSION = 4
IMPLEMENTED_ACTIONS = frozenset({"CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"})
IMPLEMENTED_WIDE_POLICY = "wide-policy-v2"
IMPLEMENTED_DEEP_POLICY = "deep-policy-v2"
UNIVERSE_PAGE_CAP = 10

__all__ = [
    "AcquisitionSpec", "CohortSpec", "DiscoverySpec", "LUAD_RESEARCH_V1", "LUAD_DISCOVERY_V1",
    "RESEARCH_SPEC_SCHEMA_VERSION", "ResearchSpec", "ScientificLimits", "UNIVERSE_PAGE_CAP",
    "research_spec_from_dict",
]


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
class ScientificLimits:
    max_survivors: int = 10
    max_promotions: int = 3
    max_revisions: int = 2

    def __post_init__(self) -> None:
        for value, ceiling in ((self.max_survivors, 10), (self.max_promotions, 3),
                               (self.max_revisions, 2)):
            count(value, "scientific limit")
            require(1 <= value <= ceiling, "scientific limit outside supported bounds")
        require(self.max_promotions <= self.max_survivors, "promotion limit exceeds survivors")


@dataclass(frozen=True)
class ResearchSpec:
    """The sole canonical research configuration of the current architecture."""

    spec_id: str
    intent: str
    cohort: CohortSpec
    discovery: DiscoverySpec
    acquisition: AcquisitionSpec
    limits: ScientificLimits
    allowed_actions: tuple[str, ...]
    wide_policy: str = IMPLEMENTED_WIDE_POLICY
    deep_policy: str = IMPLEMENTED_DEEP_POLICY

    def __post_init__(self) -> None:
        text(self.spec_id, "spec_id")
        text(self.intent, "research intent")
        require(isinstance(self.cohort, CohortSpec), "invalid cohort spec")
        require(isinstance(self.discovery, DiscoverySpec), "invalid discovery spec")
        require(isinstance(self.acquisition, AcquisitionSpec), "invalid acquisition spec")
        require(isinstance(self.limits, ScientificLimits), "invalid scientific limits")
        strings(self.allowed_actions, "allowed actions")
        require(bool(self.allowed_actions), "a research spec requires at least one allowed action")
        require(set(self.allowed_actions) <= IMPLEMENTED_ACTIONS,
                "action requires a registered implementation")
        require(self.wide_policy == IMPLEMENTED_WIDE_POLICY
                and self.deep_policy == IMPLEMENTED_DEEP_POLICY,
                "new policy semantics require a versioned task")
        require(self.limits == ScientificLimits(), "unsupported scientific limits")

    def as_dict(self) -> dict[str, Any]:
        # JSON is a boundary representation, never the internal composition.
        return {"schema_version": RESEARCH_SPEC_SCHEMA_VERSION, "kind": "RESEARCH_SPEC", **asdict(self)}

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

    def discovery_selection_rule(self) -> str:
        return (
            f"systematic discovery: the release-bound first {self.discovery.universe_limit} "
            f"{self.discovery.biotype} Ensembl gene IDs by ascending gene_id from offset "
            f"{self.discovery.offset} ({DISCOVERY_UNIVERSE_METHOD}); this is the first "
            "deterministic prefix of the indexed protein-coding universe, not the entire genome "
            "and not an unbiased random sample; the provider top-mutated ranking is a separate "
            "labelled comparator and never selects systematic survivors"
        )


def research_spec_from_dict(value: object) -> ResearchSpec:
    """Strict schema-4 boundary. Never interpret a legacy spec as the current one."""
    d = obj(value, "schema_version kind spec_id intent cohort discovery acquisition limits "
                   "allowed_actions wide_policy deep_policy")
    require(integer(d["schema_version"]) == RESEARCH_SPEC_SCHEMA_VERSION
            and d["kind"] == "RESEARCH_SPEC", "unsupported research spec version/kind")
    c = obj(d["cohort"], "cohort_id domain project_id")
    disc = obj(d["discovery"], "universe_method biotype order offset universe_limit mutation_batch_size")
    a = obj(d["acquisition"], "case_page_size case_batch_size max_cohort_cases discovery_gene_limit "
                              "count_gene_limit candidate_gene_limit expression_file_sample_size")
    limits = obj(d["limits"], "max_survivors max_promotions max_revisions")
    return ResearchSpec(
        string(d["spec_id"]), string(d["intent"]),
        CohortSpec(string(c["cohort_id"]), string(c["domain"]), string(c["project_id"])),
        DiscoverySpec(string(disc["universe_method"]), string(disc["biotype"]), string(disc["order"]),
                      integer(disc["offset"]), integer(disc["universe_limit"]),
                      integer(disc["mutation_batch_size"])),
        AcquisitionSpec(integer(a["case_page_size"]), integer(a["case_batch_size"]),
                        integer(a["max_cohort_cases"]), integer(a["discovery_gene_limit"]),
                        integer(a["count_gene_limit"]), integer(a["candidate_gene_limit"]),
                        integer(a["expression_file_sample_size"])),
        ScientificLimits(integer(limits["max_survivors"]), integer(limits["max_promotions"]),
                         integer(limits["max_revisions"])),
        string_tuple(d["allowed_actions"]), string(d["wide_policy"]), string(d["deep_policy"]),
    )


LUAD_DISCOVERY_V1 = DiscoverySpec(
    universe_method=DISCOVERY_UNIVERSE_METHOD,
    biotype="protein_coding",
    order="GENE_ID_ASC",
    offset=0,
    universe_limit=1000,
    mutation_batch_size=100,
)

LUAD_RESEARCH_V1 = ResearchSpec(
    spec_id="LUAD_RESEARCH_V1",
    intent=(
        "Bounded, deterministic-first examination of one explicit lung-adenocarcinoma cohort for a "
        "provider-ranked gene set, with narrow Jev judgment and no cross-cohort pooling; Stage 4 "
        "systematic discovery runs over the fixed indexed protein-coding prefix."
    ),
    cohort=CohortSpec(
        cohort_id="TCGA-LUAD",
        domain="lung cancer",
        project_id="TCGA-LUAD",
    ),
    discovery=LUAD_DISCOVERY_V1,
    acquisition=AcquisitionSpec(
        case_page_size=250,
        case_batch_size=250,
        max_cohort_cases=1_000,
        discovery_gene_limit=20,
        count_gene_limit=100,
        candidate_gene_limit=10,
        expression_file_sample_size=5,
    ),
    limits=ScientificLimits(),
    allowed_actions=("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
)
