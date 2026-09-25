"""Stage 4 systematic mutation discovery: one bounded deterministic funnel.

Sequence: release/project inventory → cohort case frame → indexed gene-universe
enumeration (≤10 strict /genes pages) → one complete per-project released
occurrence scan (bounded pages, distinct-case derivation from validated
records) → per-gene typed outcome → deterministic affected-case-count
descending reduction (≤10 survivors) → immutable persisted result. No provider
ranking, `_score`, Jev, LLM or hidden biological knowledge enters the reduction;
the provider top-mutated ranking is a labelled comparator only. This is a
pre-Wide funnel: no StatisticalState is generated.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import write_discovery
from cancerjev.domain.discovery import (
    ABSENCE_LIMITATION,
    COMPARATOR_LIMITATION,
    COMPLETE_UNIVERSE_LIMITATION,
    COMPLETE_UNIVERSE_METHOD,
    MAX_DISCOVERY_SURVIVORS,
    MAX_UNIVERSE_DEFECT_CEILING,
    MAX_UNIVERSE_DEFECT_PAGES,
    REDUCER_METHOD_ID,
    REDUCER_VERSION,
    SYSTEMATIC_UNIVERSE_PAGE_SIZE,
    UNIVERSE_LIMITATION,
    UNIVERSE_PAGE_CAP,
    UNIVERSE_SOURCE,
    DiscoveryComparator,
    DiscoveryDisposition,
    DiscoverySpec,
    MutationDiscoveryEntry,
    MutationDiscoveryResult,
)
from cancerjev.domain.events import utc_now
from cancerjev.domain.measurements import (
    Acquisition,
    EntityRef,
    MethodIdentityRef,
    ObservedCount,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    ScientificSource,
    TestedUniverse,
    digest,
)
from cancerjev.domain.shards import ShardKind, ShardLedger, ShardRecord, ShardStatus
from cancerjev.domain.scientific import MutationCountResult
from cancerjev.gdc.endpoints import (
    SSM_OCCURRENCE_FIELDS,
    cohort_project_request,
    genes_universe_request,
    mutated_cases_count_request,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    GeneRecord,
    ProjectCoverage,
    parse_genes_page,
    parse_mutated_cases_count,
    parse_projects,
    parse_status,
    parse_top_mutated_genes,
)
from cancerjev.gdc.transport import TransportError
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    LiveRunError,
    MutationOccurrenceScan,
    acquire_cohort,
    acquire_project_mutation_occurrence_scan,
    response_meta,
    response_operational_source,
)
from cancerjev.research.shards import ledger_summary, publish_shard_ledger
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.methods import scanned_mutation_result
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

UNIVERSE_PAGE_SIZE = SYSTEMATIC_UNIVERSE_PAGE_SIZE
UNIVERSE_SOURCE_COMPLETE = "GDC_GENES_INDEXED_COMPLETE"
UNIVERSE_PAGE_CAP_COMPLETE = MAX_UNIVERSE_DEFECT_PAGES
COMPARATOR_RULE = "PROVIDER_TOP_MUTATED_BASELINE"
COMPLETE_COUNT_REASON = "COMPLETE_DISTINCT_AFFECTED_CASE_COUNT"
SCAN_ENDPOINT_DESCRIPTOR = "/ssm_occurrences/scan"


@dataclass(frozen=True)
class GeneUniverseAcquisition:
    universe: TestedUniverse
    genes: dict[str, GeneRecord]
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]
    page_count: int
    ledger: ShardLedger


def acquire_gene_universe(transport: AcquisitionTransport, discovery_spec: DiscoverySpec,
                          release: str | None) -> GeneUniverseAcquisition:
    """Enumerate the declared gene-id-ascending protein-coding universe, failing closed.

    The complete method enumerates every gene the pinned release reports up to a
    declared defect guard ceiling (a sanity check, never a sampler); the
    historical prefix method enumerates its bounded indexed slice. Pages are
    validated independently; across pages the provider total must stay stable and
    ids must ascend with no duplicates. Every page is registered in an
    operational shard ledger; a short page before the declared slice is
    satisfied, a ceiling breach, or a total change raises and no terminal ledger
    is ever published for an incomplete sweep.
    """
    universe_release = release or "UNVERIFIED_RELEASE"
    complete_method = discovery_spec.universe_method == COMPLETE_UNIVERSE_METHOD
    page_ceiling = UNIVERSE_PAGE_CAP_COMPLETE if complete_method else UNIVERSE_PAGE_CAP
    sources: list[OperationalSource] = []
    warnings: list[str] = []
    genes: dict[str, GeneRecord] = {}
    ordered_ids: list[str] = []
    records: list[ShardRecord] = []
    total: int | None = None
    offset = 0
    page_count = 0
    while True:
        if not complete_method and offset >= discovery_spec.universe_limit:
            break
        if complete_method and total is not None and offset >= total:
            break
        response = transport.request(genes_universe_request(offset, UNIVERSE_PAGE_SIZE))
        page = parse_genes_page(response.body, response_meta(response, release),
                                expected_offset=offset, expected_size=UNIVERSE_PAGE_SIZE)
        sources.append(response_operational_source(response, release=release))
        warnings.extend(page.warnings)
        page_count += 1
        if page_count > page_ceiling:
            raise LiveRunError(
                "UNIVERSE_PAGE_CAP_EXCEEDED",
                f"genes universe exceeded {page_ceiling} pages",
            )
        if total is None:
            total = page.total
            if complete_method and total - discovery_spec.offset > discovery_spec.universe_limit:
                raise LiveRunError(
                    "UNIVERSE_DEFECT_CEILING_EXCEEDED",
                    f"genes universe reports {total} genes beyond the declared defect guard "
                    f"ceiling {discovery_spec.universe_limit}",
                )
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
        records.append(ShardRecord(
            index=page_count - 1, status=ShardStatus.COMPLETED, item_count=page.count,
            request_hash=response.request_hash, response_hash=response.body_sha256,
            artifact_id=response.artifact.artifact_id, detail=None,
        ))
        if page.count == UNIVERSE_PAGE_SIZE:
            offset += UNIVERSE_PAGE_SIZE
            continue
        break
    expected = ((total or 0) - discovery_spec.offset) if complete_method else min(
        discovery_spec.universe_limit, total or 0)
    if not records or len(ordered_ids) != expected:
        raise LiveRunError(
            "UNIVERSE_SLICE_INCOMPLETE",
            f"genes universe returned {len(ordered_ids)} of the expected {expected} genes",
        )
    universe = TestedUniverse(
        ordered_ids=tuple(ordered_ids),
        source=UNIVERSE_SOURCE_COMPLETE if complete_method else UNIVERSE_SOURCE,
        release=universe_release, filter_description=discovery_spec.biotype,
        order=discovery_spec.order, offset=discovery_spec.offset,
        requested_limit=discovery_spec.universe_limit, reported_total=total or 0,
        complete=(total is not None and len(ordered_ids) == expected),
    )
    ledger = ShardLedger(kind=ShardKind.UNIVERSE_PAGES, required=len(records),
                         records=tuple(records))
    return GeneUniverseAcquisition(universe, genes, tuple(sources), tuple(warnings), page_count,
                                   ledger)


def _mutation_outcome(project_id: str, gene: GeneRecord, population_frame: PopulationFrame,
                      scan: MutationOccurrenceScan, release: str, coverage: ProjectCoverage,
                      coverage_source: OperationalSource, coverage_complete: bool,
                      scan_source: OperationalSource) -> tuple[MutationCountResult, bool]:
    """Typed per-gene V2 outcome from the complete occurrence scan."""
    distinct, _occurrence_docs = scan.counts_for(gene.gene_id)
    outcome = scanned_mutation_result(
        project_id=project_id, gene=gene, population_frame=population_frame,
        distinct_cases=distinct, release=release, coverage=coverage,
        coverage_source=coverage_source.source, coverage_complete=coverage_complete,
        scan_source=scan_source)
    return outcome, coverage_complete


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
                            ordered_ids: tuple[str, ...], scan: MutationOccurrenceScan,
                            release: str, population_frame: PopulationFrame,
                            coverage: ProjectCoverage, coverage_source: OperationalSource,
                            coverage_complete: bool, scan_source: OperationalSource,
                            max_survivors: int,
                            ) -> tuple[tuple[MutationDiscoveryEntry, ...], tuple[str, ...]]:
    """One typed outcome and exactly one disposition per requested universe gene.

    Every universe gene gets an observed distinct-case count from the complete
    scan (an absent gene is an observed zero); genes are ordered by affected-case
    count descending with gene_id ascending as the deterministic tie break, and
    the first ``max_survivors`` are retained. Entries are emitted in universe
    order.
    """
    candidates: list[_Candidate] = []
    for gene_id in ordered_ids:
        gene = genes[gene_id]
        outcome, eligible = _mutation_outcome(
            project_id, gene, population_frame, scan, release, coverage, coverage_source,
            coverage_complete, scan_source)
        if eligible:
            affected = outcome.affected_cases
            candidates.append(_Candidate(gene_id, outcome,
                                          affected.value if isinstance(affected, ObservedCount) else None,
                                          None, COMPLETE_COUNT_REASON))
        else:
            candidates.append(_Candidate(gene_id, outcome, None,
                                         DiscoveryDisposition.MUTATION_AGGREGATION_PARTIAL,
                                         "MUTATION_COVERAGE_PARTIAL"))
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


def _acquire_project_coverage(transport: AcquisitionTransport,
                              release: str | None) -> tuple[ProjectCoverage, OperationalSource]:
    response = transport.request(mutated_cases_count_request())
    coverage = parse_mutated_cases_count(response.body, response_meta(response, release))
    return coverage, response_operational_source(response, release=release)


def _reducer_identity(project_id: str) -> MethodIdentityRef:
    parameters = {
        "affected_count_method": "MUTATION_AFFECTED_CASE_COUNT_V2",
        "eligibility": COMPLETE_COUNT_REASON,
        "ordering": "AFFECTED_CASE_COUNT_DESC_THEN_GENE_ID_ASC",
        "project": project_id,
        "max_survivors": MAX_DISCOVERY_SURVIVORS,
    }
    return MethodIdentityRef(REDUCER_METHOD_ID, REDUCER_VERSION, digest(parameters))


def publish_occurrence_scan(artifacts: ArtifactStore, repository: Repository, run_id: str,
                            scan: MutationOccurrenceScan, *, relative_path: str,
                            ) -> tuple[Any, OperationalSource]:
    """Persist the immutable scan record bundle and derive its aggregate source.

    The document pins the exact requested field set, so a later field extension
    can never be confused with the reconciled V2 scan semantics.
    """
    field_set_hash = digest(list(SSM_OCCURRENCE_FIELDS))
    document = {
        "kind": "MUTATION_OCCURRENCE_SCAN",
        "project_id": scan.project_id,
        "page_size": scan.page_size,
        "page_count": scan.page_count,
        "total_occurrences": scan.total_occurrences,
        "bytes_read": scan.bytes_read,
        "requested_fields": list(SSM_OCCURRENCE_FIELDS),
        "field_set_hash": field_set_hash,
        "distinct_cases_per_gene": dict(sorted(scan.distinct_cases_per_gene.items())),
        "occurrence_docs_per_gene": dict(sorted(scan.occurrence_docs_per_gene.items())),
        "page_sources": [asdict(page_source.source) for page_source in scan.sources],
    }
    artifact = artifacts.publish(
        relative_path,
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        "application/json", "mutation-occurrence-scan",
    )
    repository.register_artifact(artifact, run_id)
    source = OperationalSource(
        source=ScientificSource(
            endpoint=SCAN_ENDPOINT_DESCRIPTOR,
            request_hash=digest({"project_id": scan.project_id, "page_size": scan.page_size,
                                 "page_count": scan.page_count,
                                 "total_occurrences": scan.total_occurrences,
                                 "field_set_hash": field_set_hash}),
            response_hash=artifact.sha256, parser_version=PARSER_VERSION,
            release=scan.sources[0].source.release if scan.sources else "UNVERIFIED_RELEASE",
            acquisition=Acquisition.COMPLETE,
            workflow_family="GDC_OPEN_MAF_AGGREGATION",
            caller_family="MULTI_CALLER_ENSEMBLE",
        ),
        attempt_id=f"scan:{artifact.artifact_id}", artifact_id=artifact.artifact_id,
        retrieved_at=utc_now(), bytes_read=scan.bytes_read, latency_ms=0, http_status=200,
        cache_hit=False,
    )
    return artifact, source


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
    universe_ledger_artifact = publish_shard_ledger(
        artifacts, repository, run_id, universe_acquisition.ledger,
        relative_path=f"runs/{run_id}/discovery/universe-shards.json")
    if not universe_acquisition.ledger.terminal:
        raise LiveRunError(
            "SHARD_LEDGER_NOT_TERMINAL",
            "the universe shard ledger is not terminal; no reduction may finalize",
        )
    emit("DISCOVERY_UNIVERSE_ACQUIRED", f"discovery:universe:{uuid4()}",
         "Indexed protein-coding gene universe enumerated.",
         data={"total": universe_acquisition.universe.reported_total,
               "requested": universe_acquisition.universe.requested_limit,
               "returned": len(universe_acquisition.universe.ordered_ids),
               "complete": universe_acquisition.universe.complete,
               "pages": universe_acquisition.page_count,
               "membership_hash": universe_acquisition.universe.membership_hash,
               "release": universe_acquisition.universe.release,
               "shard_ledger": ledger_summary(universe_acquisition.ledger)},
         artifact_refs=[universe_ledger_artifact.ref()])
    scan = acquire_project_mutation_occurrence_scan(
        transport, cohort.project_id, discovery.occurrence_scan_page_size, release)
    sources.extend(scan.sources)
    warnings.extend(scan.warnings)
    coverage, coverage_source = _acquire_project_coverage(transport, release)
    sources.append(coverage_source)
    warnings.extend(coverage.warnings)
    emit("DISCOVERY_OCCURRENCE_SCAN_ACQUIRED", f"discovery:scan:{uuid4()}",
         "Complete per-project released-occurrence scan acquired.",
         data={"project_id": scan.project_id, "page_size": scan.page_size,
               "pages": scan.page_count, "total_occurrences": scan.total_occurrences,
               "distinct_cases_total": sum(scan.distinct_cases_per_gene.values()),
               "release": release})
    scan_artifact, scan_source = publish_occurrence_scan(
        artifacts, repository, run_id, scan,
        relative_path=f"runs/{run_id}/discovery/occurrence-scan.json")
    sources.append(scan_source)
    entries, survivor_ids = build_discovery_entries(
        cohort.project_id, universe_acquisition.genes, universe_acquisition.universe.ordered_ids,
        scan, universe_acquisition.universe.release, population_frame, coverage, coverage_source,
        bool(coverage.complete), scan_source, MAX_DISCOVERY_SURVIVORS)
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
        limitations=((COMPLETE_UNIVERSE_LIMITATION
                      if discovery.universe_method == COMPLETE_UNIVERSE_METHOD
                      else UNIVERSE_LIMITATION),
                     ABSENCE_LIMITATION, COMPARATOR_LIMITATION),
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
               "occurrence_scan": {"pages": scan.page_count,
                                   "total_occurrences": scan.total_occurrences,
                                   "artifact_id": scan_artifact.artifact_id,
                                   "artifact_sha256": scan_artifact.sha256},
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[scan_artifact.ref(), artifact.ref()],
         registrations=[repository.artifact_registration(scan_artifact, run_id),
                        repository.artifact_registration(artifact, run_id)])
    return result
