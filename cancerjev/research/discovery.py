"""Stage 4 systematic mutation discovery: one bounded deterministic funnel.

Sequence: release/project inventory → cohort case frame → indexed gene-universe
enumeration (≤10 strict /genes pages) → per-batch indexed mutation counts (≤100
genes per request, coverage acquired once) → per-gene typed outcome →
deterministic count-descending reduction (≤10 survivors) → immutable persisted
result. No provider ranking, `_score`, Jev, LLM or hidden biological knowledge
enters the reduction; the provider top-mutated ranking is a labelled comparator
only. This is a pre-Wide funnel: no StatisticalState is generated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import write_discovery
from cancerjev.domain.discovery import (
    ABSENCE_LIMITATION,
    COMPARATOR_LIMITATION,
    MAX_DISCOVERY_SURVIVORS,
    REDUCER_METHOD_ID,
    REDUCER_VERSION,
    UNIVERSE_LIMITATION,
    UNIVERSE_PAGE_CAP,
    UNIVERSE_SOURCE,
    DiscoveryComparator,
    DiscoveryDisposition,
    DiscoverySpec,
    MutationDiscoveryEntry,
    MutationDiscoveryResult,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    CountMeasurement,
    EntityRef,
    MethodIdentityRef,
    ObservedCount,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    Quality,
    Sufficiency,
    TestedUniverse,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
    digest,
)
from cancerjev.domain.scientific import MutationCountResult
from cancerjev.gdc.endpoints import (
    cohort_project_request,
    genes_universe_request,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.parsers import (
    GeneRecord,
    parse_genes_page,
    parse_projects,
    parse_status,
    parse_top_mutated_genes,
)
from cancerjev.gdc.transport import TransportError
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    BatchedMutationCounts,
    LiveRunError,
    MutationCountBatch,
    acquire_batched_mutation_counts,
    acquire_cohort,
    response_meta,
    response_operational_source,
)
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.methods import (
    ACQUISITION_COMPLETENESS_DEFINITION,
    MUTATION_ABSENCE_SEMANTICS,
    MUTATION_COUNT_METHOD,
    SSM_COVERAGE_METHOD,
)
from cancerjev.science.mutation import mutation_observation
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

UNIVERSE_PAGE_SIZE = 100
COMPARATOR_RULE = "PROVIDER_TOP_MUTATED_BASELINE"
COMPLETE_COUNT_REASON = "COMPLETE_OBSERVED_AFFECTED_CASE_COUNT"
BUDGET_EXHAUSTED_REASON = "MUTATION_COUNT_BUDGET_EXHAUSTED"


@dataclass(frozen=True)
class GeneUniverseAcquisition:
    universe: TestedUniverse
    genes: dict[str, GeneRecord]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    page_count: int


def acquire_gene_universe(transport: AcquisitionTransport, discovery_spec: DiscoverySpec,
                          release: str | None) -> GeneUniverseAcquisition:
    """Enumerate the fixed gene-id-ascending protein-coding prefix, failing closed.

    Pages are validated by ``parse_genes_page`` independently; across pages the
    provider total must stay stable and ids must ascend with no duplicates. The
    loop stops at the declared limit or the provider's end of records; a short
    page before the declared slice is satisfied is an error.
    """
    universe_release = release or "UNVERIFIED_RELEASE"
    sources: list[OperationalSource] = []
    warnings: list[str] = []
    genes: dict[str, GeneRecord] = {}
    ordered_ids: list[str] = []
    total: int | None = None
    offset = 0
    page_count = 0
    while offset < discovery_spec.universe_limit:
        response = transport.request(genes_universe_request(offset, UNIVERSE_PAGE_SIZE))
        page = parse_genes_page(response.body, response_meta(response, release),
                                expected_offset=offset, expected_size=UNIVERSE_PAGE_SIZE)
        sources.append(response_operational_source(response, release=release))
        warnings.extend(page.warnings)
        page_count += 1
        if page_count > UNIVERSE_PAGE_CAP:
            raise LiveRunError("UNIVERSE_PAGE_CAP_EXCEEDED",
                               f"genes universe exceeded {UNIVERSE_PAGE_CAP} pages")
        if total is None:
            total = page.total
        elif page.total != total:
            raise LiveRunError(
                "UNIVERSE_TOTAL_CHANGED",
                f"genes universe total changed from {total} to {page.total} at offset {offset}",
            )
        for gene in page.genes:
            if gene.gene_id in genes:
                raise LiveRunError(
                    "DUPLICATE_UNIVERSE_GENE",
                    f"genes universe returned duplicate {gene.gene_id} across pages",
                )
            genes[gene.gene_id] = gene
            ordered_ids.append(gene.gene_id)
        if page.count == UNIVERSE_PAGE_SIZE:
            offset += UNIVERSE_PAGE_SIZE
            continue
        break
    expected = min(discovery_spec.universe_limit, total or 0)
    if len(ordered_ids) != expected:
        raise LiveRunError(
            "UNIVERSE_SLICE_INCOMPLETE",
            f"genes universe returned {len(ordered_ids)} of the expected {expected} genes",
        )
    universe = TestedUniverse(
        ordered_ids=tuple(ordered_ids), source=UNIVERSE_SOURCE, release=universe_release,
        filter_description=discovery_spec.biotype, order=discovery_spec.order,
        offset=discovery_spec.offset, requested_limit=discovery_spec.universe_limit,
        reported_total=total or 0,
        complete=(total is not None and len(ordered_ids) == expected),
    )
    return GeneUniverseAcquisition(universe, genes, tuple(sources), tuple(warnings), page_count)


def _mutation_outcome(project_id: str, gene: GeneRecord, population_frame: PopulationFrame,
                      batch: MutationCountBatch, batched: BatchedMutationCounts, release: str,
                      ) -> tuple[MutationCountResult, bool]:
    """Typed per-gene outcome from one validated batch, plus batch-level eligibility."""
    observation = mutation_observation(project_id, gene.gene_id, batch.counts, batched.coverage)
    affected: CountMeasurement
    if observation.affected_cases is None:
        status = (UnavailableStatus.UNAVAILABLE if observation.availability == "PARTIAL"
                  else UnavailableStatus.NOT_OBSERVED)
        affected = UnavailableMeasurement(
            status, observation.reason or "GENE_BUCKET_ABSENT", Unit.CASES, population_frame)
    elif observation.affected_cases == 0 and not batch.counts.complete:
        affected = UnavailableMeasurement(
            UnavailableStatus.UNAVAILABLE, "PARTIAL_AGGREGATION", Unit.CASES, population_frame)
    else:
        affected = ObservedCount(observation.affected_cases, Unit.CASES, population_frame,
                                 MUTATION_COUNT_METHOD, (batch.source.source,))
    ssm = _coverage_measurement(project_id, population_frame, batched)
    acquisition = (Acquisition.COMPLETE if observation.acquisition_complete else Acquisition.PARTIAL)
    if observation.affected_cases is not None:
        sufficiency = (Sufficiency.SUFFICIENT if acquisition == Acquisition.COMPLETE
                       else Sufficiency.PARTIAL)
    elif observation.ssm_coverage_cases is not None:
        sufficiency = Sufficiency.PARTIAL
    else:
        sufficiency = Sufficiency.INSUFFICIENT
    quality = Quality(acquisition, sufficiency, Compatibility.UNVERIFIED,
                      (MUTATION_ABSENCE_SEMANTICS, ACQUISITION_COMPLETENESS_DEFINITION))
    outcome = MutationCountResult(affected, ssm, batched.coverage.complete, population_frame,
                                  quality, EntityRef(gene.gene_id, gene.symbol, release))
    eligible = (isinstance(affected, ObservedCount) and batch.counts.complete
                and batched.coverage.complete)
    return outcome, eligible


def _coverage_measurement(project_id: str, population_frame: PopulationFrame,
                          batched: BatchedMutationCounts) -> CountMeasurement:
    raw_coverage = batched.coverage.case_with_ssm.get(project_id)
    if raw_coverage is None:
        return UnavailableMeasurement(UnavailableStatus.NOT_OBSERVED, "PROJECT_NOT_IN_COVERAGE",
                                      Unit.CASES, population_frame)
    if raw_coverage == 0 and not batched.coverage.complete:
        return UnavailableMeasurement(UnavailableStatus.UNAVAILABLE, "PARTIAL_AGGREGATION",
                                      Unit.CASES, population_frame)
    return ObservedCount(raw_coverage, Unit.CASES, population_frame, SSM_COVERAGE_METHOD,
                         (batched.coverage_source.source,))


def _unavailable_outcome(project_id: str, gene: GeneRecord, population_frame: PopulationFrame,
                         batched: BatchedMutationCounts, release: str,
                         ) -> MutationCountResult:
    """Outcome for a gene whose mutation batch was never acquired (budget exhausted)."""
    affected: CountMeasurement = UnavailableMeasurement(
        UnavailableStatus.NOT_ACQUIRED, BUDGET_EXHAUSTED_REASON, Unit.CASES, population_frame)
    return MutationCountResult(
        affected, _coverage_measurement(project_id, population_frame, batched),
        batched.coverage.complete, population_frame,
        Quality(Acquisition.NOT_ACQUIRED, Sufficiency.INSUFFICIENT, Compatibility.UNVERIFIED,
                (ACQUISITION_COMPLETENESS_DEFINITION,)),
        EntityRef(gene.gene_id, gene.symbol, release),
    )


@dataclass(frozen=True)
class _Candidate:
    gene_id: str
    outcome: MutationCountResult
    count_value: int | None
    disposition: DiscoveryDisposition | None
    reason: str

    def reduction_key(self) -> tuple[int, str]:
        assert self.count_value is not None
        return -self.count_value, self.gene_id


def build_discovery_entries(project_id: str, genes: dict[str, GeneRecord],
                            ordered_ids: tuple[str, ...], batched: BatchedMutationCounts,
                            population_frame: PopulationFrame, release: str, max_survivors: int,
                            ) -> tuple[tuple[MutationDiscoveryEntry, ...], tuple[str, ...]]:
    """One typed outcome and exactly one disposition per requested universe gene.

    Eligible genes are ordered by affected-case count descending with gene_id
    ascending as the deterministic tie break; the first ``max_survivors`` are
    retained. Missing and incomplete observations are never eligible zeroes.
    Entries are emitted in universe order.
    """
    batch_of: dict[str, MutationCountBatch] = {}
    for known_batch in batched.batches:
        for gene_id in known_batch.gene_ids:
            if gene_id in batch_of:
                raise LiveRunError("DUPLICATE_BATCH_GENE", f"gene {gene_id} occurs in two batches")
            batch_of[gene_id] = known_batch
    candidates: list[_Candidate] = []
    for gene_id in ordered_ids:
        gene = genes[gene_id]
        gene_batch = batch_of.get(gene_id)
        if gene_batch is None:
            outcome = _unavailable_outcome(project_id, gene, population_frame, batched, release)
            candidates.append(_Candidate(gene_id, outcome, None,
                                         DiscoveryDisposition.ACQUISITION_UNAVAILABLE,
                                         BUDGET_EXHAUSTED_REASON))
            continue
        outcome, eligible = _mutation_outcome(project_id, gene, population_frame, gene_batch,
                                              batched, release)
        if eligible:
            affected = outcome.affected_cases
            candidates.append(_Candidate(gene_id, outcome,
                                         affected.value if isinstance(affected, ObservedCount) else None,
                                         None, COMPLETE_COUNT_REASON))
        elif isinstance(outcome.affected_cases, ObservedCount):
            reason = ("MUTATION_AGGREGATION_PARTIAL" if not gene_batch.counts.complete
                      else "MUTATION_COVERAGE_PARTIAL")
            candidates.append(_Candidate(gene_id, outcome, None,
                                         DiscoveryDisposition.MUTATION_AGGREGATION_PARTIAL, reason))
        else:
            unavailable = outcome.affected_cases
            disposition = (DiscoveryDisposition.MUTATION_BUCKET_NOT_OBSERVED
                           if unavailable.status is UnavailableStatus.NOT_OBSERVED
                           else DiscoveryDisposition.MUTATION_AGGREGATION_PARTIAL)
            candidates.append(_Candidate(gene_id, outcome, None, disposition, unavailable.reason))
    eligible_sorted = sorted((candidate for candidate in candidates
                              if candidate.count_value is not None),
                             key=_Candidate.reduction_key)
    dispositions: dict[str, tuple[DiscoveryDisposition, int | None, str]] = {}
    survivor_ids: list[str] = []
    for index, candidate in enumerate(eligible_sorted):
        retained = index < max_survivors
        disposition = (DiscoveryDisposition.RETAINED if retained
                       else DiscoveryDisposition.BELOW_SURVIVOR_CUTOFF)
        if retained:
            survivor_ids.append(candidate.gene_id)
        dispositions[candidate.gene_id] = (disposition, index + 1, candidate.reason)
    for candidate in candidates:
        if candidate.gene_id not in dispositions:
            assert candidate.disposition is not None
            dispositions[candidate.gene_id] = (candidate.disposition, None, candidate.reason)
    outcome_of = {candidate.gene_id: candidate.outcome for candidate in candidates}
    entries = tuple(
        MutationDiscoveryEntry(
            entity=EntityRef(gene_id, genes[gene_id].symbol, release), outcome=outcome_of[gene_id],
            disposition=dispositions[gene_id][0], reason=dispositions[gene_id][2],
            rank=dispositions[gene_id][1],
        )
        for gene_id in ordered_ids
    )
    return entries, tuple(survivor_ids)


def _reducer_identity(project_id: str) -> MethodIdentityRef:
    parameters = {
        "eligibility": "COMPLETE_OBSERVED_AFFECTED_CASE_COUNT",
        "ordering": "AFFECTED_CASE_COUNT_DESC_THEN_GENE_ID_ASC",
        "project": project_id,
        "max_survivors": MAX_DISCOVERY_SURVIVORS,
    }
    return MethodIdentityRef(REDUCER_METHOD_ID, REDUCER_VERSION, digest(parameters))


def _comparator(transport: AcquisitionTransport, research_spec: ResearchSpec, release: str | None,
                survivor_ids: tuple[str, ...],
                ) -> tuple[DiscoveryComparator | None, OperationalSource | None, list[str]]:
    """Labelled provider top-mutated baseline overlap; never a reducer input."""
    try:
        response = transport.request(top_mutated_genes_request(
            research_spec.cohort.project_id, research_spec.acquisition.discovery_gene_limit))
    except TransportError as exc:
        return None, None, [f"comparator unavailable: {exc.code}"]
    hits = parse_top_mutated_genes(response.body, response_meta(response, release))
    provider_ids = tuple(hit.gene_id for hit in sorted(hits, key=lambda hit: hit.rank))
    overlap = tuple(sorted(set(provider_ids) & set(survivor_ids)))
    comparator = DiscoveryComparator(COMPARATOR_RULE, provider_ids, overlap)
    return comparator, response_operational_source(response, release=release), []


def run_mutation_discovery(run_id: str, transport: AcquisitionTransport, repository: Repository,
                           artifacts: ArtifactStore, emit: Callable[..., Any],
                           research_spec: ResearchSpec) -> MutationDiscoveryResult:
    """Execute the bounded Stage 4 funnel and persist one immutable result artifact."""
    cohort = research_spec.cohort
    discovery = research_spec.discovery
    emit("DISCOVERY_STARTED", f"discovery:started:{uuid4()}",
         "Systematic mutation discovery started.",
         data={"spec_id": research_spec.spec_id, "discovery": asdict(discovery),
               "selection_rule": research_spec.discovery_selection_rule()})
    status_response = transport.request(status_request())
    status = parse_status(status_response.body, response_meta(status_response, None))
    release = status.data_release
    project_response = transport.request(cohort_project_request(cohort.project_id))
    projects = parse_projects(project_response.body, response_meta(project_response, release))
    selected = [project for project in projects if project.project_id == cohort.project_id]
    if not selected:
        raise LiveRunError("COHORT_PROJECT_NOT_FOUND",
                           f"cohort project {cohort.project_id} not present in the open inventory")
    project = selected[0]
    sources: list[OperationalSource] = [
        response_operational_source(status_response, release=release),
        response_operational_source(project_response, release=release),
    ]
    warnings: list[str] = list(status.warnings)
    cohort_acquisition = acquire_cohort(transport, project, research_spec.acquisition, release)
    sources.extend(cohort_acquisition.sources)
    warnings.extend(cohort_acquisition.warnings)
    population_frame = PopulationFrame(
        cohort_id=cohort.cohort_id, project_id=cohort.project_id, unit=PopulationUnit.CASE,
        examined_ids=tuple(sorted(case.case_id for case in cohort_acquisition.cases)),
        eligible_ids=None, selection_rule="ALL_CASES_PAGINATED",
    )
    universe_acquisition = acquire_gene_universe(transport, discovery, release)
    sources.extend(universe_acquisition.sources)
    warnings.extend(universe_acquisition.warnings)
    emit("DISCOVERY_UNIVERSE_ACQUIRED", f"discovery:universe:{uuid4()}",
         "Indexed protein-coding gene universe enumerated.",
         data={"total": universe_acquisition.universe.reported_total,
               "requested": universe_acquisition.universe.requested_limit,
               "returned": len(universe_acquisition.universe.ordered_ids),
               "complete": universe_acquisition.universe.complete,
               "pages": universe_acquisition.page_count,
               "membership_hash": universe_acquisition.universe.membership_hash,
               "release": universe_acquisition.universe.release})
    batched = acquire_batched_mutation_counts(
        transport, list(universe_acquisition.universe.ordered_ids),
        discovery.mutation_batch_size, release)
    sources.append(batched.coverage_source)
    sources.extend(batch.source for batch in batched.batches)
    warnings.extend(batched.warnings)
    entries, survivor_ids = build_discovery_entries(
        cohort.project_id, universe_acquisition.genes, universe_acquisition.universe.ordered_ids,
        batched, population_frame, universe_acquisition.universe.release, MAX_DISCOVERY_SURVIVORS)
    comparator, comparator_source, comparator_warnings = _comparator(
        transport, research_spec, release, survivor_ids)
    if comparator_source is not None:
        sources.append(comparator_source)
    warnings.extend(comparator_warnings)
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.disposition.value] = totals.get(entry.disposition.value, 0) + 1
    result = MutationDiscoveryResult(
        spec_id=research_spec.spec_id, cohort_id=cohort.cohort_id,
        project_id=cohort.project_id, release=universe_acquisition.universe.release,
        discovery=discovery, universe=universe_acquisition.universe,
        reducer=_reducer_identity(cohort.project_id), entries=entries,
        survivor_ids=survivor_ids, sources=tuple(sources), warnings=tuple(warnings),
        limitations=(UNIVERSE_LIMITATION, ABSENCE_LIMITATION, COMPARATOR_LIMITATION),
        comparator=comparator,
    )
    artifact = artifacts.publish(
        f"runs/{run_id}/discovery/result.json", write_discovery(result), "application/json",
        "mutation-discovery-result",
    )
    repository.register_artifact(artifact, run_id)
    emit("DISCOVERY_COMPLETED", f"discovery:completed:{uuid4()}",
         f"Systematic mutation discovery completed with {len(survivor_ids)} survivor(s).",
         data={"survivor_ids": list(survivor_ids), "entries": len(entries),
               "disposition_totals": totals,
               "universe_membership_hash": universe_acquisition.universe.membership_hash,
               "release": universe_acquisition.universe.release,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result
