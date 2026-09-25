"""Stage 4 systematic discovery contracts: typed, frozen, pre-Wide.

One bounded mutation-lane funnel over a fixed indexed gene universe. The
reducer is deterministic; no provider ranking, Jev judgment, LLM output or
hidden biological knowledge selects survivors. This is a pre-Wide funnel
result, not a second ``StatisticalState`` architecture and not a generic
discovery framework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import (
    EntityRef,
    MethodIdentityRef,
    MetricAvailability,
    OperationalSource,
    PopulationFrame,
    TestedUniverse,
    count,
    digest,
    finite,
    require,
    sha256,
    strings,
    text,
)
from cancerjev.domain.scientific import (
    CnvCategory,
    CnvOccurrenceResult,
    ExpressionSummaryResult,
    MutationCountResult,
    UnavailableLane,
)

DISCOVERY_UNIVERSE_METHOD = "GENE_ID_ASC_INDEXED_PREFIX_V1"
UNIVERSE_PAGE_CAP = 10
MAX_UNIVERSE_LIMIT = 1000
MAX_MUTATION_BATCH_SIZE = 100
MAX_DISCOVERY_SURVIVORS = 10
MAX_EXPRESSION_BATCH_SIZE = 100
MIN_EXPRESSION_TAIL_N = 20
MAX_CNV_SURVIVORS = 10
MAX_CNV_PAGES_PER_GENE = 10
CNV_PAGE_SIZE = 250
UNIVERSE_SOURCE = "GDC_GENES_INDEXED_PREFIX"
REDUCER_METHOD_ID = "MUTATION_LUAD_AFFECTED_COUNT_DESC_V1"
REDUCER_VERSION = "1"

UNIVERSE_LIMITATION = (
    "The systematic universe is the first deterministic prefix of the indexed protein-coding "
    "Ensembl gene universe by ascending gene_id at a declared offset; it is reproducible but "
    "biased and incomplete for the genome, not the entire genome and not an unbiased random sample."
)
ABSENCE_LIMITATION = (
    "An absent project/gene mutation aggregation bucket is NOT_OBSERVED: it is not zero, not "
    "wildtype, not mutation-negative, and never a callable-negative denominator; no recurrence "
    "fraction is computed."
)
COMPARATOR_LIMITATION = (
    "Overlap between systematic survivors and the provider top-mutated baseline is a descriptive "
    "comparator only; it is not validation and never enters survivor selection."
)
EXPRESSION_TAIL_METHOD_ID = "EXPRESSION_TUKEY_TAIL_V1"
EXPRESSION_TAIL_VERSION = "1"
EXPRESSION_SELECTION_RULE = "SAME_RELEASE_BOUND_SYSTEMATIC_UNIVERSE"
EXPRESSION_LIMITATIONS = (
    "Expression values are case-labelled GDC UQFPKM observations summarized as log2(UQFPKM+1); "
    "they are not raw counts, differential expression, tumor-normal contrasts or causal effects.",
    "Case identifiers do not establish matched tumor aliquots, so no cross-modal or sample-matched "
    "claim is made.",
    "Empirical tails are within-gene descriptive observations selected on this same cohort; they are "
    "not p-values, diagnoses or confirmatory findings.",
)
CNV_SUMMARY_METHOD_ID = "CNV_INDEXED_POSITIVE_CASES_V1"
CNV_SUMMARY_VERSION = "1"
CNV_SELECTION_RULE = "STAGE4_MUTATION_SURVIVORS_ONLY"
CNV_LIMITATIONS = (
    "CNV rows are provider-labelled positive indexed occurrences for Stage 4 mutation survivors; "
    "absence is not neutral, negative, wild type or callable evidence.",
    "Provider five-category labels and caller/source context are retained; generic Loss is distinct "
    "from Homozygous Deletion and numerical values are not compared across callers.",
    "Category case sets are descriptive and may overlap; conflicts are retained rather than summed "
    "or resolved, and no expression association or causal claim is made.",
)


@dataclass(frozen=True)
class DiscoverySpec:
    """Fixed bounded systematic-discovery configuration.

    The Stage 4 contract is deterministic: the release-bound first
    ``universe_limit`` protein-coding Ensembl gene IDs by ascending gene_id at a
    declared offset, mutated in bounded batches. These are the only supported
    values; the provider-ranked baseline path remains the labelled comparator.
    """

    universe_method: str
    biotype: str
    order: str
    offset: int
    universe_limit: int
    mutation_batch_size: int

    def __post_init__(self) -> None:
        require(self.universe_method == DISCOVERY_UNIVERSE_METHOD,
                f"universe_method must be {DISCOVERY_UNIVERSE_METHOD}")
        require(self.biotype == "protein_coding", "biotype must be protein_coding")
        require(self.order == "GENE_ID_ASC", "order must be GENE_ID_ASC")
        require(self.offset == 0, "offset must be 0")
        require(1 <= self.universe_limit <= MAX_UNIVERSE_LIMIT,
                f"universe_limit must be 1..{MAX_UNIVERSE_LIMIT}")
        require(1 <= self.mutation_batch_size <= MAX_MUTATION_BATCH_SIZE,
                f"mutation_batch_size must be 1..{MAX_MUTATION_BATCH_SIZE}")
        require(self.universe_limit <= UNIVERSE_PAGE_CAP * self.mutation_batch_size,
                f"universe_limit must fit within {UNIVERSE_PAGE_CAP} mutation pages")


@dataclass(frozen=True)
class ExpressionDiscoverySpec:
    """Fixed Stage 5 expression arm over the Stage 4 systematic universe."""

    selection_rule: str = EXPRESSION_SELECTION_RULE
    gene_batch_size: int = MAX_EXPRESSION_BATCH_SIZE
    minimum_tail_n: int = MIN_EXPRESSION_TAIL_N
    quantile_rule: str = "LINEAR_INTERPOLATION_H_N_MINUS_1_P"
    iqr_multiplier: float = 1.5
    input_unit: str = "UQFPKM"
    transform: str = "log2(x+1)"

    def __post_init__(self) -> None:
        require(self.selection_rule == EXPRESSION_SELECTION_RULE, "unsupported expression selection rule")
        require(self.gene_batch_size == MAX_EXPRESSION_BATCH_SIZE,
                f"gene_batch_size must be {MAX_EXPRESSION_BATCH_SIZE}")
        require(self.minimum_tail_n == MIN_EXPRESSION_TAIL_N,
                f"minimum_tail_n must be {MIN_EXPRESSION_TAIL_N}")
        require(self.quantile_rule == "LINEAR_INTERPOLATION_H_N_MINUS_1_P",
                "unsupported expression quantile rule")
        finite(self.iqr_multiplier, "iqr_multiplier")
        require(self.iqr_multiplier == 1.5, "iqr_multiplier must be 1.5")
        require(self.input_unit == "UQFPKM" and self.transform == "log2(x+1)",
                "unsupported expression unit/transform")


@dataclass(frozen=True)
class CnvDiscoverySpec:
    """Fixed Stage 6 lane: complete per-gene queries for Stage 4 survivors only."""

    selection_rule: str = CNV_SELECTION_RULE
    page_size: int = CNV_PAGE_SIZE
    max_pages_per_gene: int = MAX_CNV_PAGES_PER_GENE
    max_genes: int = MAX_CNV_SURVIVORS
    category_field: str = "cnv.cnv_change_5_category"

    def __post_init__(self) -> None:
        require(self.selection_rule == CNV_SELECTION_RULE, "unsupported CNV selection rule")
        require(self.page_size == CNV_PAGE_SIZE, f"CNV page_size must be {CNV_PAGE_SIZE}")
        require(self.max_pages_per_gene == MAX_CNV_PAGES_PER_GENE,
                f"CNV max_pages_per_gene must be {MAX_CNV_PAGES_PER_GENE}")
        require(self.max_genes == MAX_CNV_SURVIVORS,
                f"CNV max_genes must be {MAX_CNV_SURVIVORS}")
        require(self.category_field == "cnv.cnv_change_5_category",
                "unsupported CNV category field")


class DiscoveryDisposition(StrEnum):
    """Exactly one final disposition per requested universe gene."""

    RETAINED = "RETAINED"
    BELOW_SURVIVOR_CUTOFF = "BELOW_SURVIVOR_CUTOFF"
    MUTATION_BUCKET_NOT_OBSERVED = "MUTATION_BUCKET_NOT_OBSERVED"
    MUTATION_AGGREGATION_PARTIAL = "MUTATION_AGGREGATION_PARTIAL"
    ACQUISITION_UNAVAILABLE = "ACQUISITION_UNAVAILABLE"


@dataclass(frozen=True)
class MutationDiscoveryEntry:
    """One universe gene's mutation outcome, disposition and deterministic rank."""

    entity: EntityRef
    outcome: MutationCountResult
    disposition: DiscoveryDisposition
    reason: str
    rank: int | None

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid entry entity")
        require(isinstance(self.outcome, MutationCountResult), "invalid entry outcome")
        require(self.outcome.entity.gene_id == self.entity.gene_id
                and self.outcome.entity.release == self.entity.release,
                "entry entity must match its outcome entity")
        require(isinstance(self.disposition, DiscoveryDisposition), "invalid disposition")
        text(self.reason, "entry reason")
        ranked = self.disposition in (DiscoveryDisposition.RETAINED,
                                      DiscoveryDisposition.BELOW_SURVIVOR_CUTOFF)
        if self.rank is not None:
            count(self.rank, "entry rank")
            require(self.rank >= 1, "entry rank must be at least 1")
        require(ranked == (self.rank is not None), "rank presence must match ranked disposition")


@dataclass(frozen=True)
class DiscoveryComparator:
    """Descriptive overlap with the labelled provider top-mutated baseline."""

    rule: str
    provider_gene_ids: tuple[str, ...]
    survivor_overlap: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.rule, "comparator rule")
        strings(self.provider_gene_ids, "comparator provider gene IDs")
        strings(self.survivor_overlap, "comparator overlap")


@dataclass(frozen=True)
class MutationDiscoveryResult:
    """The sole Stage 4 result: one disposition per requested gene, at most N survivors."""

    spec_id: str
    cohort_id: str
    project_id: str
    release: str
    discovery: DiscoverySpec
    universe: TestedUniverse
    reducer: MethodIdentityRef
    entries: tuple[MutationDiscoveryEntry, ...]
    survivor_ids: tuple[str, ...]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    comparator: DiscoveryComparator | None

    def __post_init__(self) -> None:
        text(self.spec_id, "spec_id")
        text(self.cohort_id, "cohort_id")
        text(self.project_id, "project_id")
        text(self.release, "release")
        require(isinstance(self.discovery, DiscoverySpec), "invalid discovery spec")
        require(isinstance(self.universe, TestedUniverse), "invalid tested universe")
        require(isinstance(self.reducer, MethodIdentityRef), "invalid reducer identity")
        require(type(self.entries) is tuple
                and all(isinstance(entry, MutationDiscoveryEntry) for entry in self.entries),
                "entries must be an immutable tuple")
        strings(self.survivor_ids, "survivor gene IDs")
        require(type(self.sources) is tuple
                and all(isinstance(source, OperationalSource) for source in self.sources),
                "sources must be an immutable tuple")
        strings(self.warnings, "result warnings", unique=False)
        strings(self.limitations, "result limitations")
        require(self.comparator is None or isinstance(self.comparator, DiscoveryComparator),
                "invalid comparator")
        require(len(self.entries) == len(self.universe.ordered_ids),
                "every requested universe gene must have exactly one entry")
        for entry, gene_id in zip(self.entries, self.universe.ordered_ids, strict=True):
            require(entry.entity.gene_id == gene_id, "entry order must match universe order")
        ranked = sorted((entry for entry in self.entries if entry.rank is not None),
                        key=lambda entry: entry.rank or 0)
        require([entry.rank for entry in ranked] == list(range(1, len(ranked) + 1)),
                "ranked entries must have contiguous ranks from 1")
        require(self.survivor_ids == tuple(entry.entity.gene_id for entry in ranked
                                           if entry.disposition is DiscoveryDisposition.RETAINED),
                "survivors must be the retained entries in rank order")
        require(len(self.survivor_ids) <= MAX_DISCOVERY_SURVIVORS,
                f"survivor count exceeds {MAX_DISCOVERY_SURVIVORS}")


@dataclass(frozen=True)
class ExpressionTailDescriptor:
    availability: MetricAvailability
    reason: str | None
    q1: float | None
    q3: float | None
    lower_fence: float | None
    upper_fence: float | None
    lower_case_ids: tuple[str, ...]
    upper_case_ids: tuple[str, ...]
    valid_n: int
    method: MethodIdentityRef

    def __post_init__(self) -> None:
        require(isinstance(self.availability, MetricAvailability), "invalid tail availability")
        count(self.valid_n, "tail valid_n")
        require(isinstance(self.method, MethodIdentityRef), "invalid tail method")
        strings(self.lower_case_ids, "lower tail case IDs")
        strings(self.upper_case_ids, "upper tail case IDs")
        require(self.lower_case_ids == tuple(sorted(self.lower_case_ids))
                and self.upper_case_ids == tuple(sorted(self.upper_case_ids)),
                "tail case IDs must be sorted")
        require(not set(self.lower_case_ids) & set(self.upper_case_ids), "tail case IDs overlap")
        values = (self.q1, self.q3, self.lower_fence, self.upper_fence)
        if self.availability is MetricAvailability.OBSERVED:
            require(self.reason is None, "observed tail cannot have an unavailable reason")
            require(all(value is not None for value in values), "observed tail needs all fences")
            for value in values:
                assert value is not None
                finite(value, "tail value")
            assert self.q1 is not None and self.q3 is not None
            require(self.q1 < self.q3, "observed tail requires positive IQR")
            iqr = self.q3 - self.q1
            require(self.lower_fence == self.q1 - 1.5 * iqr
                    and self.upper_fence == self.q3 + 1.5 * iqr,
                    "tail fences do not match the fixed Tukey rule")
        else:
            require(self.reason is not None, "unavailable tail needs a reason")
            reason = self.reason
            assert reason is not None
            text(reason, "tail reason")
            require(all(value is None for value in values), "unavailable tail cannot carry fences")
            require(not self.lower_case_ids and not self.upper_case_ids,
                    "unavailable tail cannot carry case IDs")


@dataclass(frozen=True)
class ExpressionDiscoveryEntry:
    entity: EntityRef
    outcome: ExpressionSummaryResult | UnavailableLane
    tail: ExpressionTailDescriptor

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid expression entry entity")
        require(isinstance(self.outcome, (ExpressionSummaryResult, UnavailableLane)),
                "invalid expression outcome")
        require(isinstance(self.tail, ExpressionTailDescriptor), "invalid tail descriptor")
        if isinstance(self.outcome, ExpressionSummaryResult):
            require(self.outcome.entity == self.entity, "expression entry entity mismatch")
            require(self.tail.valid_n == len(self.outcome.values), "tail valid_n mismatch")
            valid_ids = set(self.outcome.coverage.valid_ids)
            require(set(self.tail.lower_case_ids) | set(self.tail.upper_case_ids) <= valid_ids,
                    "tail case outside valid expression frame")
            if self.tail.availability is MetricAvailability.OBSERVED:
                assert self.tail.lower_fence is not None and self.tail.upper_fence is not None
                transformed = {
                    value.case_id: math.log2(value.uqfpkm + 1.0)
                    for value in self.outcome.values
                }
                require(self.tail.lower_case_ids == tuple(sorted(
                    case_id for case_id, value in transformed.items()
                    if value < self.tail.lower_fence)), "lower tail membership mismatch")
                require(self.tail.upper_case_ids == tuple(sorted(
                    case_id for case_id, value in transformed.items()
                    if value > self.tail.upper_fence)), "upper tail membership mismatch")
        else:
            require(self.tail.valid_n == 0, "unavailable expression cannot have tail values")
            require(self.outcome.lane.value == "EXPRESSION", "wrong unavailable lane")


@dataclass(frozen=True)
class ExpressionDiscoveryResult:
    spec_id: str
    cohort_id: str
    project_id: str
    release: str
    expression_discovery: ExpressionDiscoverySpec
    universe: TestedUniverse
    population: PopulationFrame
    entries: tuple[ExpressionDiscoveryEntry, ...]
    workflows: tuple[str, ...]
    strategies: tuple[str, ...]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    request_plan_max: int

    def __post_init__(self) -> None:
        for value in (self.spec_id, self.cohort_id, self.project_id, self.release):
            text(value, "expression discovery identity")
        require(isinstance(self.expression_discovery, ExpressionDiscoverySpec),
                "invalid expression discovery spec")
        require(isinstance(self.universe, TestedUniverse), "invalid expression universe")
        require(isinstance(self.population, PopulationFrame), "invalid expression population")
        require(self.population.cohort_id == self.cohort_id
                and self.population.project_id == self.project_id, "population binding mismatch")
        require(type(self.entries) is tuple
                and all(isinstance(entry, ExpressionDiscoveryEntry) for entry in self.entries),
                "entries must be immutable expression entries")
        require(len(self.entries) == len(self.universe.ordered_ids),
                "every expression-universe gene needs one outcome")
        require(tuple(entry.entity.gene_id for entry in self.entries) == self.universe.ordered_ids,
                "expression entry order must match universe order")
        strings(self.workflows, "expression workflows")
        strings(self.strategies, "expression strategies")
        require(type(self.sources) is tuple
                and all(isinstance(source, OperationalSource) for source in self.sources),
                "invalid expression sources")
        strings(self.warnings, "expression warnings", unique=False)
        require(self.limitations == EXPRESSION_LIMITATIONS, "expression limitations changed")
        expected_method_hash = digest({
            "minimum_n": self.expression_discovery.minimum_tail_n,
            "quantile_rule": self.expression_discovery.quantile_rule,
            "iqr_multiplier": self.expression_discovery.iqr_multiplier,
            "input_unit": self.expression_discovery.input_unit,
            "transform": self.expression_discovery.transform,
        })
        require(all(entry.tail.method == MethodIdentityRef(
            EXPRESSION_TAIL_METHOD_ID, EXPRESSION_TAIL_VERSION, expected_method_hash)
                    for entry in self.entries), "tail method identity mismatch")
        count(self.request_plan_max, "request_plan_max")
        require(self.request_plan_max <= 150, "expression request plan exceeds run cap")


@dataclass(frozen=True)
class CnvCategorySummary:
    raw_category: str
    category: CnvCategory
    case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.raw_category, "CNV raw category")
        require(isinstance(self.category, CnvCategory), "invalid CNV category")
        strings(self.case_ids, "CNV category case IDs")
        require(self.case_ids == tuple(sorted(self.case_ids)),
                "CNV category case IDs must be sorted")


@dataclass(frozen=True)
class CnvDiscoveryEntry:
    entity: EntityRef
    outcome: CnvOccurrenceResult | UnavailableLane
    categories: tuple[CnvCategorySummary, ...]
    conflicting_case_ids: tuple[str, ...]
    callers: tuple[str, ...]
    missing_sample_occurrence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid CNV entry entity")
        require(isinstance(self.outcome, (CnvOccurrenceResult, UnavailableLane)),
                "invalid CNV entry outcome")
        require(type(self.categories) is tuple
                and all(isinstance(item, CnvCategorySummary) for item in self.categories),
                "invalid CNV categories")
        strings(tuple(item.raw_category for item in self.categories), "CNV raw categories")
        require(tuple(item.raw_category for item in self.categories)
                == tuple(sorted(item.raw_category for item in self.categories)),
                "CNV categories must be sorted")
        for values, name in (
            (self.conflicting_case_ids, "CNV conflicting case IDs"),
            (self.callers, "CNV callers"),
            (self.missing_sample_occurrence_ids, "CNV missing sample occurrence IDs"),
        ):
            strings(values, name)
            require(values == tuple(sorted(values)), f"{name} must be sorted")
        if isinstance(self.outcome, UnavailableLane):
            require(self.outcome.lane.value == "CNV", "wrong unavailable CNV lane")
            require(not self.categories and not self.conflicting_case_ids and not self.callers
                    and not self.missing_sample_occurrence_ids,
                    "unavailable CNV entry cannot carry measurements")
            return
        require(self.outcome.entity == self.entity, "CNV entry entity mismatch")
        by_raw: dict[str, set[str]] = {}
        by_case: dict[str, set[str]] = {}
        for occurrence in self.outcome.occurrences:
            by_raw.setdefault(occurrence.raw_category, set()).add(occurrence.case_id)
            by_case.setdefault(occurrence.case_id, set()).add(occurrence.raw_category)
        expected_categories = tuple(
            CnvCategorySummary(raw, next(occurrence.category for occurrence in self.outcome.occurrences
                                         if occurrence.raw_category == raw),
                               tuple(sorted(case_ids)))
            for raw, case_ids in sorted(by_raw.items())
        )
        require(self.categories == expected_categories, "CNV category summary mismatch")
        require(self.conflicting_case_ids == tuple(sorted(
            case_id for case_id, labels in by_case.items() if len(labels) > 1)),
            "CNV category conflict summary mismatch")
        require(self.callers == tuple(sorted({occurrence.caller for occurrence in self.outcome.occurrences
                                              if occurrence.caller is not None})),
                "CNV caller summary mismatch")
        require(self.missing_sample_occurrence_ids == tuple(sorted(
            occurrence.occurrence_id for occurrence in self.outcome.occurrences
            if occurrence.sample_id is None)), "CNV missing sample summary mismatch")


@dataclass(frozen=True)
class CnvDiscoveryResult:
    spec_id: str
    cohort_id: str
    project_id: str
    release: str
    mutation_discovery_hash: str
    survivor_ids: tuple[str, ...]
    cnv_discovery: CnvDiscoverySpec
    population: PopulationFrame
    summary_method: MethodIdentityRef
    entries: tuple[CnvDiscoveryEntry, ...]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    request_plan_max: int

    def __post_init__(self) -> None:
        for value in (self.spec_id, self.cohort_id, self.project_id, self.release):
            text(value, "CNV discovery identity")
        sha256(self.mutation_discovery_hash, "mutation discovery hash")
        strings(self.survivor_ids, "CNV survivor IDs")
        require(len(self.survivor_ids) <= MAX_CNV_SURVIVORS,
                "CNV discovery exceeds 10 Stage 4 survivors")
        require(isinstance(self.cnv_discovery, CnvDiscoverySpec), "invalid CNV discovery spec")
        require(isinstance(self.population, PopulationFrame), "invalid CNV population")
        require(self.population.cohort_id == self.cohort_id
                and self.population.project_id == self.project_id, "CNV population binding mismatch")
        require(isinstance(self.summary_method, MethodIdentityRef), "invalid CNV summary method")
        expected_hash = digest({
            "category_field": self.cnv_discovery.category_field,
            "deduplication": "UNIQUE_CASE_WITHIN_EXACT_PROVIDER_CATEGORY",
            "conflicts": "RETAIN_CASES_WITH_MULTIPLE_PROVIDER_CATEGORIES",
        })
        require(self.summary_method == MethodIdentityRef(
            CNV_SUMMARY_METHOD_ID, CNV_SUMMARY_VERSION, expected_hash),
            "CNV summary method mismatch")
        require(type(self.entries) is tuple
                and all(isinstance(entry, CnvDiscoveryEntry) for entry in self.entries),
                "invalid CNV entries")
        require(tuple(entry.entity.gene_id for entry in self.entries) == self.survivor_ids,
                "CNV entries must match Stage 4 survivor order")
        require(all(not isinstance(entry.outcome, CnvOccurrenceResult)
                    or entry.outcome.frame == self.population for entry in self.entries),
                "CNV outcome frame mismatch")
        require(type(self.sources) is tuple
                and all(isinstance(source, OperationalSource) for source in self.sources),
                "invalid CNV sources")
        strings(self.warnings, "CNV warnings", unique=False)
        require(self.limitations == CNV_LIMITATIONS, "CNV limitations changed")
        count(self.request_plan_max, "CNV request_plan_max")
        require(self.request_plan_max == 1 + MAX_CNV_SURVIVORS * MAX_CNV_PAGES_PER_GENE,
                "CNV request plan changed")
