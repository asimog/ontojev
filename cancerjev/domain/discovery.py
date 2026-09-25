"""Stage 4 systematic discovery contracts: typed, frozen, pre-Wide.

One bounded mutation-lane funnel over a fixed indexed gene universe. The
reducer is deterministic; no provider ranking, Jev judgment, LLM output or
hidden biological knowledge selects survivors. This is a pre-Wide funnel
result, not a second ``StatisticalState`` architecture and not a generic
discovery framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import (
    EntityRef,
    MethodIdentityRef,
    OperationalSource,
    TestedUniverse,
    count,
    require,
    strings,
    text,
)
from cancerjev.domain.scientific import MutationCountResult

DISCOVERY_UNIVERSE_METHOD = "GENE_ID_ASC_INDEXED_PREFIX_V1"
UNIVERSE_PAGE_CAP = 10
MAX_UNIVERSE_LIMIT = 1000
MAX_MUTATION_BATCH_SIZE = 100
MAX_DISCOVERY_SURVIVORS = 10
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
