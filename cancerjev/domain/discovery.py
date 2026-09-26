"""Stage 4 systematic discovery contracts: typed, frozen, pre-Wide.

One bounded mutation-lane funnel over a fixed indexed gene universe. The
reducer is deterministic; no provider ranking, Jev judgment, LLM output or
hidden biological knowledge selects survivors. This is a pre-Wide funnel
result, not a second ``StatisticalState`` architecture and not a generic
discovery framework.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from cancerjev.domain.measurements import (
    MAX_UNIVERSE_REQUEST_LIMIT,
    EntityRef,
    MethodIdentityRef,
    MetricAvailability,
    ObservedCount,
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
from cancerjev.gdc.budget import (
    PAGE_DEFECT_CEILING,
    REQUEST_DEFECT_CEILING,
    RUN_DOWNLOAD_BYTES,
    SHARD_DOWNLOAD_BYTES,
)

DISCOVERY_UNIVERSE_METHOD = "GENE_ID_ASC_INDEXED_PREFIX_V1"
COMPLETE_UNIVERSE_METHOD = "GENE_ID_ASC_INDEXED_COMPLETE_V1"
UNIVERSE_PAGE_CAP = 10
MAX_UNIVERSE_LIMIT = 1000
MAX_UNIVERSE_DEFECT_CEILING = MAX_UNIVERSE_REQUEST_LIMIT
SYSTEMATIC_UNIVERSE_PAGE_SIZE = 100
MAX_UNIVERSE_DEFECT_PAGES = MAX_UNIVERSE_DEFECT_CEILING // SYSTEMATIC_UNIVERSE_PAGE_SIZE + 1
DISCOVERY_RUN_MAX_PAGES_PER_QUERY = MAX_UNIVERSE_DEFECT_PAGES
EXPRESSION_RUN_MAX_REQUESTS = REQUEST_DEFECT_CEILING
EXPRESSION_RUN_MAX_BYTES = RUN_DOWNLOAD_BYTES
MAX_OCCURRENCE_SCAN_PAGE_SIZE = 10000
OCCURRENCE_SCAN_MAX_PAGES = PAGE_DEFECT_CEILING
OCCURRENCE_SCAN_MAX_BYTES = SHARD_DOWNLOAD_BYTES
MAX_DISCOVERY_SURVIVORS = 10
MAX_EXPRESSION_BATCH_SIZE = 100
MIN_EXPRESSION_TAIL_N = 20
MAX_CNV_SURVIVORS = 10
MAX_CNV_PAGES_PER_GENE = 10
CNV_PAGE_SIZE = 250
UNIVERSE_SOURCE = "GDC_GENES_INDEXED_PREFIX"
REDUCER_METHOD_ID = "MUTATION_AFFECTED_CASE_COUNT_DESC_V1"
REDUCER_VERSION = "3"
MUTATION_CANONICAL_COMPOSITION_METHOD_ID = "MUTATION_CANONICAL_COMPOSITION_V1"
MUTATION_CANONICAL_COMPOSITION_VERSION = "1"
MUTATION_HOTSPOT_TOP_POSITIONS = 5
MUTATION_JEV_REVIEW_POLICY_VERSION = "mutation-dispositions-v1"
JEV_REVIEW_MAX_OCCURRENCE_PER_CASE_RATIO = 4
JEV_REVIEW_HOTSPOT_MIN_RECORDS = 20
JEV_REVIEW_HOTSPOT_TOP_POSITION_SHARE = 0.25
JEV_REVIEW_OCCURRENCE_RATIO_TRIGGER = "OCCURRENCE_PER_CASE_RATIO_GT_4"
JEV_REVIEW_HOTSPOT_TRIGGER = "HOTSPOT_CONCENTRATION"
MUTATION_COMPOSITION_LIMITATIONS = (
    "Composition counts canonical-transcript occurrence terms only; records without canonical "
    "annotation are NOT_OBSERVED, never negative.",
    "Descriptive composition, positions and hotspot descriptors carry no p-values, q-values or "
    "driver-significance claim.",
    "Protein-position recurrence and hotspot descriptors require an admitted file source; "
    "/ssm_occurrences exposes no transcript protein-position field, so they stay unavailable here.",
)


def mutation_composition_method() -> MethodIdentityRef:
    """The one declared canonical-consequence composition identity."""
    return MethodIdentityRef(
        MUTATION_CANONICAL_COMPOSITION_METHOD_ID, MUTATION_CANONICAL_COMPOSITION_VERSION,
        digest({"canonical_only": True, "deduplicate": "OCCURRENCE_X_CONSEQUENCE",
                "top_positions": MUTATION_HOTSPOT_TOP_POSITIONS}),
    )

UNIVERSE_LIMITATION = (
    "The systematic universe is the first deterministic prefix of the indexed protein-coding "
    "Ensembl gene universe by ascending gene_id at a declared offset; it is reproducible but "
    "biased and incomplete for the genome, not the entire genome and not an unbiased random sample."
)
COMPLETE_UNIVERSE_LIMITATION = (
    "The systematic universe is every protein-coding Ensembl gene the pinned release reports by "
    "ascending gene_id; completeness means every reported gene was enumerated to a stable provider "
    "total, and the declared defect ceiling is a sanity guard, not a sampler."
)
ABSENCE_LIMITATION = (
    "Affected-case counts are derived locally from the complete per-project released occurrence "
    "scan: a gene absent from a complete scan is an observed zero, never NOT_OBSERVED, wildtype "
    "or a callable-negative denominator; an incomplete scan is never persisted and no recurrence "
    "fraction is computed."
)
COMPARATOR_LIMITATION = (
    "Overlap between systematic survivors and the provider top-mutated baseline is a descriptive "
    "comparator only; it is not validation and never enters survivor selection."
)
EXPRESSION_TAIL_METHOD_ID = "EXPRESSION_TUKEY_TAIL_V1"
EXPRESSION_TAIL_VERSION = "1"
EXPRESSION_SELECTION_RULE = "SAME_RELEASE_BOUND_SYSTEMATIC_UNIVERSE"
EXPRESSION_DISPOSITION_POLICY_VERSION = "expression-dispositions-v1"
EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO = 5.0
EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER = "EXTREME_TAIL_ASYMMETRY"
EXPRESSION_RETAIN_REASON = "OBSERVED_TAIL_WITH_MINIMUM_VALUES"
EXPRESSION_DROP_OBSERVED_REASON = "EXPRESSION_NOT_OBSERVED"
EXPRESSION_DROP_INSUFFICIENT_REASON = "INSUFFICIENT_VALID_VALUES"
EXPRESSION_REQUEST_AVERAGE_BYTES = 200 * 1024
EXPRESSION_ALIQUOT_IDENTITY_STATUS = "NOT_API_DERIVABLE"
EXPRESSION_ALIQUOT_IDENTITY_NOTE = (
    "The harmonized expression endpoints key values by case; no per-value aliquot identity is "
    "exposed, so case-labelled values never support matched cross-modal claims."
)
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
CNV_SCAN_SELECTION_RULE = "CNV_PROJECT_CASE_SHARD_SCAN_V1"
CNV_SHARD_EVIDENCE_METHOD_ID = "CNV_SHARD_OCCURRENCE_SCAN_V1"
CNV_SHARD_EVIDENCE_VERSION = "1"
CNV_CASE_SHARD_SIZE = 25
CNV_SCAN_MAX_PAGES = PAGE_DEFECT_CEILING
CNV_DISPOSITION_POLICY_VERSION = "cnv-dispositions-v1"
CNV_RETAIN_MIN_AMPLIFICATION_CASES = 5
CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES = 5
CNV_RETAIN_REASON = "RECURRENT_AMPLIFICATION_OR_HOMOZYGOUS_DELETION"
CNV_DROP_REASON = "BELOW_RECURRENCE_THRESHOLD"
CNV_JEV_REVIEW_CONFLICT_TRIGGER = "CALLER_CONFLICT_ON_RECURRENT_EVENT"
CNV_SCAN_LIMITATIONS = (
    "Independent project scan: positive indexed occurrences only; absence is never diploid, "
    "neutral or a callable negative.",
    "Provider five-category labels, caller and source context are retained per record; numerical "
    "copy numbers are not compared across ASCAT, ABSOLUTE, DNAcopy or GATK4 products.",
    "Recurrence dispositions use declared case-count thresholds, never p-values, and are evaluated "
    "only on the merged all-shard evidence; an operational case shard cannot change them.",
)


@dataclass(frozen=True)
class DiscoverySpec:
    """Fixed bounded systematic-discovery configuration.

    The Stage 4 contract is deterministic: the release-bound protein-coding
    Ensembl gene IDs by ascending gene_id at a declared offset, measured by a
    complete per-project released-occurrence scan in bounded pages of
    ``occurrence_scan_page_size``. The complete method enumerates every reported
    gene up to a defect guard ceiling; the historical prefix method enumerates a
    bounded indexed slice. The provider-ranked baseline path remains the labelled
    comparator and the legacy count-bucket endpoint is not a Stage 4 source.
    """

    universe_method: str
    biotype: str
    order: str
    offset: int
    universe_limit: int
    occurrence_scan_page_size: int

    def __post_init__(self) -> None:
        require(self.universe_method in {DISCOVERY_UNIVERSE_METHOD, COMPLETE_UNIVERSE_METHOD},
                f"universe_method must be {DISCOVERY_UNIVERSE_METHOD} or {COMPLETE_UNIVERSE_METHOD}")
        require(self.biotype == "protein_coding", "biotype must be protein_coding")
        require(self.order == "GENE_ID_ASC", "order must be GENE_ID_ASC")
        require(self.offset == 0, "offset must be 0")
        if self.universe_method == DISCOVERY_UNIVERSE_METHOD:
            require(1 <= self.universe_limit <= MAX_UNIVERSE_LIMIT,
                    f"universe_limit must be 1..{MAX_UNIVERSE_LIMIT} "
                    f"for {DISCOVERY_UNIVERSE_METHOD}")
        else:
            require(1 <= self.universe_limit <= MAX_UNIVERSE_DEFECT_CEILING,
                    f"universe_limit must be 1..{MAX_UNIVERSE_DEFECT_CEILING} "
                    f"for {COMPLETE_UNIVERSE_METHOD}")
        require(1 <= self.occurrence_scan_page_size <= MAX_OCCURRENCE_SCAN_PAGE_SIZE,
                f"occurrence_scan_page_size must be 1..{MAX_OCCURRENCE_SCAN_PAGE_SIZE}")


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


@dataclass(frozen=True)
class MutationDescriptiveEvidence:
    """Descriptive mutation composition under one named canonical-only method.

    Counts are occurrence-level: one occurrence contributes at most once per
    canonical consequence term and at most once per protein position, so
    transcript duplication cannot inflate either distribution. No p-value,
    q-value or driver-significance claim is representable here.
    """

    consequence_composition: tuple[tuple[str, int], ...]
    canonical_transcript_n: int
    protein_position_top: tuple[tuple[int, int], ...]
    hotspot_descriptor: str | None
    review_trigger: str | None
    method: MethodIdentityRef
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        require(type(self.consequence_composition) is tuple
                and all(isinstance(item, tuple) and len(item) == 2
                        and isinstance(item[0], str) and bool(item[0])
                        and isinstance(item[1], int) and not isinstance(item[1], bool)
                        and item[1] > 0
                        for item in self.consequence_composition),
                "invalid consequence composition")
        terms = [item[0] for item in self.consequence_composition]
        require(terms == sorted(terms) and len(set(terms)) == len(terms),
                "consequence composition must be sorted and unique")
        count(self.canonical_transcript_n, "canonical transcript count")
        require(type(self.protein_position_top) is tuple
                and all(isinstance(item, tuple) and len(item) == 2
                        and isinstance(item[0], int) and not isinstance(item[0], bool)
                        and item[0] >= 0
                        and isinstance(item[1], int) and not isinstance(item[1], bool)
                        and item[1] > 0
                        for item in self.protein_position_top),
                "invalid protein-position top")
        require(len(self.protein_position_top) <= MUTATION_HOTSPOT_TOP_POSITIONS,
                "protein-position top exceeds the declared size")
        positions = [item[0] for item in self.protein_position_top]
        require(len(set(positions)) == len(positions), "protein positions must be unique")
        require(list(self.protein_position_top)
                == sorted(self.protein_position_top, key=lambda item: (-item[1], item[0])),
                "protein positions must be count-descending then position-ascending")
        if self.hotspot_descriptor is not None:
            text(self.hotspot_descriptor, "hotspot descriptor")
        if self.review_trigger is not None:
            require(self.review_trigger in {JEV_REVIEW_OCCURRENCE_RATIO_TRIGGER,
                                            JEV_REVIEW_HOTSPOT_TRIGGER},
                    "unknown review trigger")
        if self.review_trigger == JEV_REVIEW_HOTSPOT_TRIGGER:
            require(self.hotspot_descriptor is not None,
                    "the hotspot review trigger requires a hotspot descriptor")
        require(self.method == mutation_composition_method(),
                "descriptive composition method identity mismatch")
        require(self.limitations == MUTATION_COMPOSITION_LIMITATIONS,
                "descriptive composition limitations changed")

    def payload(self) -> dict[str, Any]:
        return {
            "consequence_composition": [list(item) for item in self.consequence_composition],
            "canonical_transcript_n": self.canonical_transcript_n,
            "protein_position_top": [list(item) for item in self.protein_position_top],
            "hotspot_descriptor": self.hotspot_descriptor,
            "review_trigger": self.review_trigger,
            "method": asdict(self.method),
            "limitations": list(self.limitations),
        }


class DiscoveryDisposition(StrEnum):
    """Exactly one final disposition per requested universe gene."""

    RETAINED = "RETAINED"
    JEV_REVIEW = "JEV_REVIEW"
    DROP = "DROP"
    BELOW_SURVIVOR_CUTOFF = "BELOW_SURVIVOR_CUTOFF"
    MUTATION_BUCKET_NOT_OBSERVED = "MUTATION_BUCKET_NOT_OBSERVED"
    MUTATION_AGGREGATION_PARTIAL = "MUTATION_AGGREGATION_PARTIAL"
    ACQUISITION_UNAVAILABLE = "ACQUISITION_UNAVAILABLE"


class ExpressionDisposition(StrEnum):
    """Exactly one declared disposition per expression universe gene."""

    RETAIN = "RETAIN"
    JEV_REVIEW = "JEV_REVIEW"
    DROP = "DROP"


class CnvDisposition(StrEnum):
    """Exactly one declared disposition per CNV-observed gene after shard merge."""

    RETAIN = "RETAIN"
    JEV_REVIEW = "JEV_REVIEW"
    DROP = "DROP"


@dataclass(frozen=True)
class ExpressionRunPlan:
    """Declared pre-run volume plan for one expression lane run (operational)."""

    gene_count: int
    case_count: int
    gene_batches: int
    case_batches: int
    request_count: int
    projected_bytes: int
    max_requests: int
    max_bytes: int

    def __post_init__(self) -> None:
        for name in ("gene_count", "case_count", "gene_batches", "case_batches",
                     "request_count", "projected_bytes", "max_requests", "max_bytes"):
            count(getattr(self, name), name)
        require(self.gene_batches >= 1 and self.case_batches >= 1,
                "a run plan needs at least one gene and case batch")
        require(self.request_count >= 2 * self.gene_batches * self.case_batches,
                "a run plan must cover the availability and values matrices")
        require(self.request_count <= self.max_requests,
                "expression request plan exceeds the declared budget")
        require(self.projected_bytes <= self.max_bytes,
                "expression projected bytes exceed the declared budget")

    def payload(self) -> dict[str, Any]:
        return {
            "gene_count": self.gene_count,
            "case_count": self.case_count,
            "gene_batches": self.gene_batches,
            "case_batches": self.case_batches,
            "request_count": self.request_count,
            "projected_bytes": self.projected_bytes,
            "max_requests": self.max_requests,
            "max_bytes": self.max_bytes,
        }


@dataclass(frozen=True)
class MutationDiscoveryEntry:
    """One universe gene's mutation outcome, disposition and deterministic rank."""

    entity: EntityRef
    outcome: MutationCountResult
    disposition: DiscoveryDisposition
    reason: str
    rank: int | None
    descriptive: MutationDescriptiveEvidence | None = None

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef), "invalid entry entity")
        require(isinstance(self.outcome, MutationCountResult), "invalid entry outcome")
        require(self.outcome.entity.gene_id == self.entity.gene_id
                and self.outcome.entity.release == self.entity.release,
                "entry entity must match its outcome entity")
        require(isinstance(self.disposition, DiscoveryDisposition), "invalid disposition")
        text(self.reason, "entry reason")
        if self.descriptive is not None:
            require(isinstance(self.descriptive, MutationDescriptiveEvidence),
                    "invalid descriptive evidence")
        ranked = self.disposition in (DiscoveryDisposition.RETAINED,
                                      DiscoveryDisposition.JEV_REVIEW,
                                      DiscoveryDisposition.BELOW_SURVIVOR_CUTOFF)
        if self.rank is not None:
            count(self.rank, "entry rank")
            require(self.rank >= 1, "entry rank must be at least 1")
        require(ranked == (self.rank is not None), "rank presence must match ranked disposition")
        if self.disposition is DiscoveryDisposition.DROP:
            affected = self.outcome.affected_cases
            require(isinstance(affected, ObservedCount) and affected.value == 0,
                    "DROP is reserved for zero observed affected cases")
        if self.disposition is DiscoveryDisposition.JEV_REVIEW:
            require(self.descriptive is not None
                    and self.descriptive.review_trigger is not None,
                    "JEV_REVIEW requires a declared descriptive trigger")


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
    disposition: ExpressionDisposition | None = None
    disposition_reason: str | None = None
    review_trigger: str | None = None

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
        if self.disposition is None:
            require(self.disposition_reason is None and self.review_trigger is None,
                    "a legacy entry carries no disposition fields")
            return
        require(isinstance(self.disposition, ExpressionDisposition),
                "invalid expression disposition")
        require(bool(self.disposition_reason), "an expression disposition carries its reason")
        if self.disposition is ExpressionDisposition.RETAIN:
            require(isinstance(self.outcome, ExpressionSummaryResult)
                    and self.tail.availability is MetricAvailability.OBSERVED,
                    "RETAIN requires an observed expression tail")
            require(self.disposition_reason == EXPRESSION_RETAIN_REASON, "RETAIN reason mismatch")
            require(self.review_trigger is None, "RETAIN carries no review trigger")
        elif self.disposition is ExpressionDisposition.DROP:
            require(self.disposition_reason in {EXPRESSION_DROP_OBSERVED_REASON,
                                                EXPRESSION_DROP_INSUFFICIENT_REASON},
                    "DROP reason mismatch")
            require(self.review_trigger is None, "DROP carries no review trigger")
        else:
            require(self.disposition_reason == EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER,
                    "JEV_REVIEW reason must name the declared trigger")
            require(self.review_trigger == EXPRESSION_JEV_REVIEW_ASYMMETRY_TRIGGER,
                    "JEV_REVIEW requires the declared asymmetry trigger")
            require(isinstance(self.outcome, ExpressionSummaryResult)
                    and self.tail.availability is MetricAvailability.OBSERVED,
                    "JEV_REVIEW requires an observed expression tail")


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
    workflow_file_counts: tuple[tuple[str, int], ...] = ()
    workflow_coverage_complete: bool = True
    retained_ids: tuple[str, ...] = ()
    jev_review_ids: tuple[str, ...] = ()

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
        require(self.request_plan_max <= EXPRESSION_RUN_MAX_REQUESTS,
                "expression request plan exceeds the declared run budget")
        for name, ids in (("retained", self.retained_ids), ("jev-review", self.jev_review_ids)):
            strings(ids, f"expression {name} ids")
            require(ids == tuple(sorted(ids)) and len(set(ids)) == len(ids),
                    f"expression {name} ids must be sorted and unique")
        require(not set(self.retained_ids) & set(self.jev_review_ids),
                "expression retained and review ids must be disjoint")
        dispositioned = [entry for entry in self.entries if entry.disposition is not None]
        if dispositioned:
            require(len(dispositioned) == len(self.entries),
                    "expression dispositions must cover every entry or none")
            retained = tuple(sorted(entry.entity.gene_id for entry in dispositioned
                                    if entry.disposition is ExpressionDisposition.RETAIN))
            review = tuple(sorted(entry.entity.gene_id for entry in dispositioned
                                  if entry.disposition is ExpressionDisposition.JEV_REVIEW))
            require(retained == self.retained_ids and review == self.jev_review_ids,
                    "expression nomination sets must match entry dispositions")
        require(type(self.workflow_file_counts) is tuple
                and all(isinstance(item, tuple) and len(item) == 2
                        and isinstance(item[0], str) and bool(item[0])
                        and isinstance(item[1], int) and not isinstance(item[1], bool)
                        and item[1] > 0
                        for item in self.workflow_file_counts),
                "invalid expression workflow file counts")
        require(self.workflow_file_counts == tuple(sorted(self.workflow_file_counts)),
                "expression workflow file counts must be sorted")
        require(isinstance(self.workflow_coverage_complete, bool),
                "workflow coverage flag must be a boolean")
        if self.workflow_coverage_complete:
            require(bool(self.workflow_file_counts),
                    "complete workflow coverage requires named workflow counts")


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
class CnvGeneEvidence:
    """Merged per-gene positive CNV evidence; absence is never neutral evidence."""

    gene_id: str
    categories: tuple[CnvCategorySummary, ...]
    callers: tuple[str, ...]
    conflicting_case_ids: tuple[str, ...]
    missing_sample_occurrence_ids: tuple[str, ...]
    records: int

    def __post_init__(self) -> None:
        text(self.gene_id, "CNV evidence gene id")
        require(type(self.categories) is tuple
                and all(isinstance(item, CnvCategorySummary) for item in self.categories),
                "invalid CNV evidence categories")
        raw = tuple(item.raw_category for item in self.categories)
        require(raw == tuple(sorted(raw)) and len(set(raw)) == len(raw),
                "CNV evidence categories must be sorted and unique")
        case_ids = tuple(sorted({case_id for item in self.categories
                                 for case_id in item.case_ids}))
        for values, name in ((self.callers, "CNV evidence callers"),
                             (self.conflicting_case_ids, "CNV evidence conflicts"),
                             (self.missing_sample_occurrence_ids, "CNV evidence missing samples")):
            strings(values, name)
            require(values == tuple(sorted(values)) and len(set(values)) == len(values),
                    f"{name} must be sorted and unique")
        require(set(self.conflicting_case_ids) <= set(case_ids),
                "CNV conflicts must be observed cases")
        count(self.records, "CNV evidence records")
        require(self.records >= 1, "observed CNV evidence requires at least one record")
        require(all(item.case_ids for item in self.categories),
                "CNV categories need case IDs")


@dataclass(frozen=True)
class CnvShardEvidence:
    """One operational case shard's complete positive CNV evidence."""

    shard_index: int
    case_ids: tuple[str, ...]
    project_id: str
    release: str
    genes: tuple[CnvGeneEvidence, ...]
    records: int
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    cohort_case_ids: tuple[str, ...]
    case_shard_size: int
    spec_hash: str

    def __post_init__(self) -> None:
        count(self.shard_index, "CNV shard index")
        strings(self.cohort_case_ids, "CNV cohort cases")
        require(bool(self.cohort_case_ids)
                and self.cohort_case_ids == tuple(sorted(set(self.cohort_case_ids))),
                "CNV cohort frame must be nonempty, sorted and unique")
        count(self.case_shard_size, "CNV case shard size")
        require(self.case_shard_size > 0, "CNV case shard size must be positive")
        require(len(self.spec_hash) == 64, "CNV spec hash is required")
        strings(self.case_ids, "CNV shard cases")
        require(bool(self.case_ids) and self.case_ids == tuple(sorted(self.case_ids))
                and len(set(self.case_ids)) == len(self.case_ids),
                "CNV shard cases must be sorted and unique")
        for value in (self.project_id, self.release):
            text(value, "CNV shard identity")
        require(type(self.genes) is tuple
                and all(isinstance(item, CnvGeneEvidence) for item in self.genes),
                "invalid CNV shard genes")
        gene_ids = [item.gene_id for item in self.genes]
        require(gene_ids == sorted(gene_ids) and len(set(gene_ids)) == len(gene_ids),
                "CNV shard genes must be sorted and unique")
        require(all(set(category.case_ids) <= set(self.case_ids)
                    for gene in self.genes for category in gene.categories),
                "CNV gene cases must belong to their shard")
        count(self.records, "CNV shard records")
        require(bool(self.genes) == (self.records >= 1),
                "a shard records rows exactly when it carries genes")
        require(type(self.sources) is tuple
                and all(isinstance(source, OperationalSource) for source in self.sources),
                "invalid CNV shard sources")
        strings(self.warnings, "CNV shard warnings", unique=False)


def cnv_scan_summary_method() -> MethodIdentityRef:
    """The one declared merged-evidence CNV recurrence identity."""
    return MethodIdentityRef(
        CNV_SHARD_EVIDENCE_METHOD_ID, CNV_SHARD_EVIDENCE_VERSION,
        digest({"deduplication": "UNIQUE_CASE_WITHIN_EXACT_PROVIDER_CATEGORY",
                "conflicts": "RETAIN_CASES_WITH_MULTIPLE_PROVIDER_CATEGORIES",
                "amplification_cases": CNV_RETAIN_MIN_AMPLIFICATION_CASES,
                "homozygous_deletion_cases": CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES}),
    )


@dataclass(frozen=True)
class CnvProjectCall:
    """One merged-evidence gene call under the declared recurrence policy."""

    evidence: CnvGeneEvidence
    disposition: CnvDisposition
    reason: str
    review_trigger: str | None

    def __post_init__(self) -> None:
        require(isinstance(self.evidence, CnvGeneEvidence), "invalid CNV call evidence")
        require(isinstance(self.disposition, CnvDisposition), "invalid CNV call disposition")
        text(self.reason, "CNV call reason")
        if self.disposition is CnvDisposition.RETAIN:
            require(self.reason == CNV_RETAIN_REASON and self.review_trigger is None,
                    "RETAIN requires the declared recurrence reason")
        elif self.disposition is CnvDisposition.DROP:
            require(self.reason == CNV_DROP_REASON and self.review_trigger is None,
                    "DROP requires the declared below-threshold reason")
        else:
            require(self.reason == CNV_JEV_REVIEW_CONFLICT_TRIGGER
                    and self.review_trigger == CNV_JEV_REVIEW_CONFLICT_TRIGGER,
                    "JEV_REVIEW requires the declared caller-conflict trigger")
            require(bool(self.evidence.conflicting_case_ids),
                    "JEV_REVIEW requires observed caller conflicts")


@dataclass(frozen=True)
class CnvProjectScanResult:
    """Merged all-shard CNV evidence and calls for one project at one release."""

    spec_id: str
    cohort_id: str
    project_id: str
    release: str
    selection_rule: str
    case_shard_size: int
    shard_count: int
    summary_method: MethodIdentityRef
    calls: tuple[CnvProjectCall, ...]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.spec_id, self.cohort_id, self.project_id, self.release):
            text(value, "CNV project-scan identity")
        require(self.selection_rule == CNV_SCAN_SELECTION_RULE, "unsupported CNV scan selection rule")
        count(self.case_shard_size, "CNV case shard size")
        require(self.case_shard_size >= 1, "CNV case shard size must be positive")
        count(self.shard_count, "CNV shard count")
        require(self.shard_count >= 1, "CNV scan requires at least one shard")
        require(self.summary_method == cnv_scan_summary_method(), "CNV scan summary method mismatch")
        require(type(self.calls) is tuple
                and all(isinstance(call, CnvProjectCall) for call in self.calls),
                "invalid CNV project calls")
        gene_ids = [call.evidence.gene_id for call in self.calls]
        require(gene_ids == sorted(gene_ids) and len(set(gene_ids)) == len(gene_ids),
                "CNV project calls must be sorted and unique")
        require(type(self.sources) is tuple
                and all(isinstance(source, OperationalSource) for source in self.sources),
                "invalid CNV project sources")
        strings(self.warnings, "CNV project warnings", unique=False)
        require(self.limitations == CNV_SCAN_LIMITATIONS, "CNV scan limitations changed")

    @property
    def retained_ids(self) -> tuple[str, ...]:
        return tuple(call.evidence.gene_id for call in self.calls
                     if call.disposition is CnvDisposition.RETAIN)

    @property
    def jev_review_ids(self) -> tuple[str, ...]:
        return tuple(call.evidence.gene_id for call in self.calls
                     if call.disposition is CnvDisposition.JEV_REVIEW)


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
