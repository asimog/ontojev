"""Typed, reproducible scientific scope for live research runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from cancerjev.domain._json import boolean, integer, obj, string, string_tuple
from cancerjev.domain.measurements import count, require, strings, text
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


@dataclass(frozen=True)
class GeneUniverseSpec:
    """A declared indexed slice, not a genome-wide or inferred universe."""

    limit: int = 1000
    offset: int = 0
    biotype: str = "protein_coding"
    order: str = "GENE_ID_ASC"

    def __post_init__(self) -> None:
        count(self.limit, "gene limit")
        count(self.offset, "gene offset")
        require(1 <= self.limit <= 1000 and self.offset == 0, "unsupported gene slice")
        require(self.biotype == "protein_coding" and self.order == "GENE_ID_ASC", "unsupported universe policy")


@dataclass(frozen=True)
class MutationLaneSpec:
    enabled: bool = True
    method_version: str = "1"

    def __post_init__(self) -> None:
        require(type(self.enabled) is bool, "mutation enabled must be bool")
        require(self.method_version == "1", "unsupported mutation method")


@dataclass(frozen=True)
class ExpressionLaneSpec:
    enabled: bool = False
    independent_arm: bool = False
    independent_gene_limit: int = 100
    summary_method_version: str = "1"

    def __post_init__(self) -> None:
        require(type(self.enabled) is bool and type(self.independent_arm) is bool, "invalid expression switch")
        require(self.enabled or not self.independent_arm, "disabled lane cannot acquire an independent arm")
        count(self.independent_gene_limit, "expression gene limit")
        require(self.independent_gene_limit == 100, "independent arm is exactly a bounded 100-gene slice")
        require(self.summary_method_version == "1", "unsupported summary version")


@dataclass(frozen=True)
class CnvLaneSpec:
    enabled: bool = False
    scope: str = "MUTATION_SURVIVORS"

    def __post_init__(self) -> None:
        require(type(self.enabled) is bool, "CNV enabled must be bool")
        require(self.scope == "MUTATION_SURVIVORS", "unsupported CNV scope")


@dataclass(frozen=True)
class ScientificLimits:
    max_cohort_cases: int = 1000
    max_survivors: int = 10
    max_promotions: int = 3
    max_revisions: int = 2

    def __post_init__(self) -> None:
        for value, ceiling in ((self.max_cohort_cases, 1000), (self.max_survivors, 10),
                               (self.max_promotions, 3), (self.max_revisions, 2)):
            count(value, "scientific limit")
            require(1 <= value <= ceiling, "scientific limit outside supported bounds")
        require(self.max_promotions <= self.max_survivors, "promotion limit exceeds survivors")


@dataclass(frozen=True)
class ResearchSpecV2:
    """Composition contract only; Stage 1 does not register a production profile."""

    spec_id: str
    intent: str
    cohort: CohortSpec
    universe: GeneUniverseSpec
    mutation: MutationLaneSpec
    expression: ExpressionLaneSpec
    cnv: CnvLaneSpec
    limits: ScientificLimits
    allowed_actions: tuple[str, ...]
    reduction_policy: str = "mutation-count-desc-gene-id-v1"
    wide_policy: str = "wide-policy-v2"
    deep_policy: str = "deep-policy-v2"
    output_version: int = 3

    def __post_init__(self) -> None:
        text(self.spec_id, "spec_id")
        text(self.intent, "research intent")
        require(isinstance(self.cohort, CohortSpec) and isinstance(self.universe, GeneUniverseSpec)
                and isinstance(self.limits, ScientificLimits), "invalid research composition")
        require(isinstance(self.mutation, MutationLaneSpec) and isinstance(self.expression, ExpressionLaneSpec)
                and isinstance(self.cnv, CnvLaneSpec), "invalid lane specification")
        strings(self.allowed_actions, "allowed actions")
        require(set(self.allowed_actions) <= {"CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"},
                "action requires a registered implementation")
        require(self.wide_policy == "wide-policy-v2" and self.deep_policy == "deep-policy-v2",
                "new policy semantics require a versioned task")
        require(self.reduction_policy == "mutation-count-desc-gene-id-v1", "unsupported reduction policy")
        require(type(self.output_version) is int and self.output_version == 3, "unsupported output version")
        require(not self.cnv.enabled or self.mutation.enabled, "survivor CNV requires mutation lane")
        require(self.limits.max_survivors <= self.universe.limit, "survivors exceed universe")

    def as_dict(self) -> dict[str, Any]:
        # JSON is a boundary representation, never the internal composition.
        return {"schema_version": 2, "kind": "RESEARCH_SPEC", **asdict(self)}


def research_spec_v2_from_dict(value: object) -> ResearchSpecV2:
    """Strict composition boundary. Never interpret a legacy spec as version 2."""
    d = obj(value, "schema_version kind spec_id intent cohort universe mutation expression cnv limits allowed_actions reduction_policy wide_policy deep_policy output_version")
    require(integer(d["schema_version"]) == 2 and d["kind"] == "RESEARCH_SPEC", "unsupported research spec version/kind")
    c = obj(d["cohort"], "cohort_id domain project_id")
    u = obj(d["universe"], "limit offset biotype order")
    m = obj(d["mutation"], "enabled method_version")
    e = obj(d["expression"], "enabled independent_arm independent_gene_limit summary_method_version")
    n = obj(d["cnv"], "enabled scope")
    limits = obj(d["limits"], "max_cohort_cases max_survivors max_promotions max_revisions")
    return ResearchSpecV2(
        string(d["spec_id"]), string(d["intent"]),
        CohortSpec(string(c["cohort_id"]), string(c["domain"]), string(c["project_id"])),
        GeneUniverseSpec(integer(u["limit"]), integer(u["offset"]), string(u["biotype"]), string(u["order"])),
        MutationLaneSpec(boolean(m["enabled"]), string(m["method_version"])),
        ExpressionLaneSpec(boolean(e["enabled"]), boolean(e["independent_arm"]), integer(e["independent_gene_limit"]), string(e["summary_method_version"])),
        CnvLaneSpec(boolean(n["enabled"]), string(n["scope"])),
        ScientificLimits(integer(limits["max_cohort_cases"]), integer(limits["max_survivors"]),
                         integer(limits["max_promotions"]), integer(limits["max_revisions"])),
        string_tuple(d["allowed_actions"]), string(d["reduction_policy"]), string(d["wide_policy"]), string(d["deep_policy"]), integer(d["output_version"]),
    )
