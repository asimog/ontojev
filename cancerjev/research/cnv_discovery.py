"""Stage 6 complete, survivor-only CNV occurrence acquisition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import discovery_identity, write_cnv_discovery
from cancerjev.domain.discovery import (
    CNV_LIMITATIONS,
    CNV_SUMMARY_METHOD_ID,
    CNV_SUMMARY_VERSION,
    CnvCategorySummary,
    CnvDiscoveryEntry,
    CnvDiscoveryResult,
    CnvDiscoverySpec,
    MutationDiscoveryResult,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    EntityRef,
    MethodIdentityRef,
    OperationalSource,
    Quality,
    Sufficiency,
    UnavailableStatus,
    digest,
)
from cancerjev.domain.scientific import (
    CnvOccurrence,
    CnvOccurrenceResult,
    Lane,
    UnavailableLane,
)
from cancerjev.gdc.endpoints import cnv_occurrences_request, status_request
from cancerjev.gdc.parsers import CnvOccurrenceRecord, parse_cnv_occurrences_page, parse_status
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    LiveRunError,
    response_meta,
    response_operational_source,
)
from cancerjev.research.specs import ResearchSpec
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

REQUEST_PLAN_MAX = 101
PAGE_CAP_REASON = "CNV_OCCURRENCE_PAGE_CAP_EXCEEDED"
CNV_QUALITY_REASON = (
    "Complete positive-occurrence query; absence is not CNV-neutral evidence and caller "
    "compatibility remains unverified."
)


def _summary_method(spec: CnvDiscoverySpec) -> MethodIdentityRef:
    parameters = {
        "category_field": spec.category_field,
        "deduplication": "UNIQUE_CASE_WITHIN_EXACT_PROVIDER_CATEGORY",
        "conflicts": "RETAIN_CASES_WITH_MULTIPLE_PROVIDER_CATEGORIES",
    }
    return MethodIdentityRef(
        CNV_SUMMARY_METHOD_ID, CNV_SUMMARY_VERSION, digest(parameters))


def _entry(entity: EntityRef, outcome: CnvOccurrenceResult | UnavailableLane) -> CnvDiscoveryEntry:
    if isinstance(outcome, UnavailableLane):
        return CnvDiscoveryEntry(entity, outcome, (), (), (), ())
    raw_categories = sorted({occurrence.raw_category for occurrence in outcome.occurrences})
    categories = tuple(
        CnvCategorySummary(
            raw_category,
            next(occurrence.category for occurrence in outcome.occurrences
                 if occurrence.raw_category == raw_category),
            tuple(sorted({occurrence.case_id for occurrence in outcome.occurrences
                          if occurrence.raw_category == raw_category})),
        )
        for raw_category in raw_categories
    )
    labels_by_case: dict[str, set[str]] = {}
    for occurrence in outcome.occurrences:
        labels_by_case.setdefault(occurrence.case_id, set()).add(occurrence.raw_category)
    conflicts = tuple(sorted(
        case_id for case_id, labels in labels_by_case.items() if len(labels) > 1))
    callers = tuple(sorted({occurrence.caller for occurrence in outcome.occurrences
                            if occurrence.caller is not None}))
    missing_samples = tuple(sorted(
        occurrence.occurrence_id for occurrence in outcome.occurrences
        if occurrence.sample_id is None))
    return CnvDiscoveryEntry(
        entity, outcome, categories, conflicts, callers, missing_samples)


def run_cnv_discovery(
    run_id: str,
    transport: AcquisitionTransport,
    repository: Repository,
    artifacts: ArtifactStore,
    emit: Callable[..., Any],
    research_spec: ResearchSpec,
    mutation_result: MutationDiscoveryResult,
) -> CnvDiscoveryResult:
    """Acquire complete per-survivor occurrence sets and persist one typed result."""
    if mutation_result.spec_id != research_spec.spec_id:
        raise LiveRunError("MUTATION_DISCOVERY_SPEC_MISMATCH", "Stage 4 spec does not match Stage 6")
    if mutation_result.cohort_id != research_spec.cohort.cohort_id \
            or mutation_result.project_id != research_spec.cohort.project_id:
        raise LiveRunError("MUTATION_DISCOVERY_COHORT_MISMATCH",
                           "Stage 4 cohort/project does not match Stage 6")
    if len(mutation_result.survivor_ids) > research_spec.cnv_discovery.max_genes:
        raise LiveRunError("CNV_SURVIVOR_LIMIT_EXCEEDED", "Stage 4 survivor count exceeds CNV limit")
    mutation_hash = discovery_identity(mutation_result)
    emit("CNV_DISCOVERY_STARTED", f"cnv-discovery:started:{uuid4()}",
         "Narrow survivor-only CNV discovery started.",
         data={"mutation_discovery_hash": mutation_hash,
               "survivor_ids": list(mutation_result.survivor_ids),
               "cnv_discovery": asdict(research_spec.cnv_discovery),
               "request_plan_max": REQUEST_PLAN_MAX})
    status_response = transport.request(status_request())
    status = parse_status(status_response.body, response_meta(status_response, None))
    release = status.data_release or "UNVERIFIED_RELEASE"
    if release != mutation_result.release:
        raise LiveRunError(
            "CNV_RELEASE_MISMATCH",
            f"Stage 6 release {release!r} differs from Stage 4 {mutation_result.release!r}",
        )
    sources = [response_operational_source(status_response, release=release)]
    warnings = list(status.warnings)
    population = mutation_result.entries[0].outcome.frame
    if any(entry.outcome.frame != population for entry in mutation_result.entries):
        raise LiveRunError("MUTATION_DISCOVERY_FRAME_MISMATCH",
                           "Stage 4 entries do not share one population frame")
    entry_by_gene = {entry.entity.gene_id: entry for entry in mutation_result.entries}
    entries: list[CnvDiscoveryEntry] = []
    for gene_id in mutation_result.survivor_ids:
        mutation_entry = entry_by_gene[gene_id]
        page_sources: list[OperationalSource] = []
        records: list[CnvOccurrenceRecord] = []
        expected_total: int | None = None
        previous_id: str | None = None
        offset = 0
        unavailable = False
        while True:
            response = transport.request(cnv_occurrences_request(
                mutation_result.project_id, gene_id, offset=offset,
                size=research_spec.cnv_discovery.page_size))
            page = parse_cnv_occurrences_page(
                response.body, response_meta(response, release),
                expected_project=mutation_result.project_id, expected_gene=gene_id,
                expected_cases=set(population.examined_ids), expected_offset=offset,
                expected_size=research_spec.cnv_discovery.page_size,
            )
            source = response_operational_source(response, release=release)
            sources.append(source)
            page_sources.append(source)
            warnings.extend(page.warnings)
            if expected_total is None:
                expected_total = page.total
                if page.pages > research_spec.cnv_discovery.max_pages_per_gene:
                    warnings.append(
                        f"{gene_id}: {PAGE_CAP_REASON}; provider reported {page.pages} pages")
                    unavailable = True
                    break
            elif page.total != expected_total:
                raise LiveRunError("CNV_TOTAL_CHANGED",
                                   f"{gene_id}: total changed from {expected_total} to {page.total}")
            if page.occurrences and previous_id is not None \
                    and page.occurrences[0].occurrence_id <= previous_id:
                raise LiveRunError("CNV_ORDER_CHANGED", f"{gene_id}: cross-page order regressed")
            if page.occurrences:
                previous_id = page.occurrences[-1].occurrence_id
            records.extend(page.occurrences)
            offset += page.count
            if offset >= page.total:
                break
            if page.count == 0:
                raise LiveRunError("CNV_PAGE_INCOMPLETE",
                                   f"{gene_id}: empty page before total {page.total}")
        if unavailable:
            outcome: CnvOccurrenceResult | UnavailableLane = UnavailableLane(
                Lane.CNV, True, UnavailableStatus.UNAVAILABLE, PAGE_CAP_REASON)
        else:
            assert expected_total is not None
            if len(records) != expected_total:
                raise LiveRunError("CNV_QUERY_INCOMPLETE",
                                   f"{gene_id}: collected {len(records)} of {expected_total}")
            occurrences = tuple(CnvOccurrence(
                record.occurrence_id, record.cnv_id, record.case_id, record.gene_id,
                record.raw_category, record.source_file_id, record.caller, record.sample_id,
                record.copy_number,
            ) for record in records)
            outcome = CnvOccurrenceResult(
                mutation_entry.entity, population, occurrences,
                tuple(source.source for source in page_sources),
                Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.UNVERIFIED,
                        (CNV_QUALITY_REASON,)),
            )
        entries.append(_entry(mutation_entry.entity, outcome))
    result = CnvDiscoveryResult(
        research_spec.spec_id, mutation_result.cohort_id, mutation_result.project_id, release,
        mutation_hash, mutation_result.survivor_ids, research_spec.cnv_discovery, population,
        _summary_method(research_spec.cnv_discovery), tuple(entries), tuple(sources),
        tuple(warnings), CNV_LIMITATIONS, REQUEST_PLAN_MAX,
    )
    artifact = artifacts.publish(
        f"runs/{run_id}/cnv-discovery/result.json", write_cnv_discovery(result),
        "application/json", "cnv-discovery-result",
    )
    repository.register_artifact(artifact, run_id)
    unavailable_n = sum(isinstance(entry.outcome, UnavailableLane) for entry in entries)
    emit("CNV_DISCOVERY_COMPLETED", f"cnv-discovery:completed:{uuid4()}",
         f"Narrow CNV discovery completed for {len(entries)} survivor(s).",
         data={"entries": len(entries), "unavailable": unavailable_n,
               "mutation_discovery_hash": mutation_hash,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result
