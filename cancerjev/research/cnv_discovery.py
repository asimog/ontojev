"""Stage 6 complete, survivor-only CNV occurrence acquisition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import (
    cnv_shard_identity,
    discovery_identity,
    read_cnv_shard_evidence,
    write_cnv_discovery,
    write_cnv_project_scan,
    write_cnv_shard_evidence,
)
from cancerjev.domain.discovery import (
    CNV_CASE_SHARD_SIZE,
    CNV_LIMITATIONS,
    CNV_SCAN_LIMITATIONS,
    CNV_SCAN_MAX_PAGES,
    CNV_SCAN_SELECTION_RULE,
    CNV_SUMMARY_METHOD_ID,
    CNV_SUMMARY_VERSION,
    CnvCategorySummary,
    CnvDiscoveryEntry,
    CnvDiscoveryResult,
    CnvDiscoverySpec,
    CnvGeneEvidence,
    CnvProjectCall,
    CnvProjectScanResult,
    CnvShardEvidence,
    MutationDiscoveryResult,
    cnv_scan_summary_method,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    EntityRef,
    MethodIdentityRef,
    OperationalSource,
    Quality,
    ScientificSource,
    Sufficiency,
    UnavailableStatus,
    digest,
)
from cancerjev.domain.scientific import (
    CnvCategory,
    CnvOccurrence,
    CnvOccurrenceResult,
    Lane,
    UnavailableLane,
    cnv_category,
)
from cancerjev.domain.shards import ShardKind, ShardLedger, ShardRecord, ShardStatus
from cancerjev.gdc.endpoints import (
    cnv_occurrence_shard_page_request,
    cnv_occurrences_request,
    cohort_project_request,
    status_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    CnvOccurrenceRecord,
    parse_cnv_occurrence_scan_page,
    parse_cnv_occurrences_page,
    parse_projects,
    parse_status,
)
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    LiveRunError,
    acquire_cohort,
    response_meta,
    response_operational_source,
)
from cancerjev.research.shards import publish_shard_ledger
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.descriptors import cnv_lane_disposition
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

CNV_SHARD_ARTIFACT_PATH = "cnv-shards/shard-{index:04d}.json"

REQUEST_PLAN_MAX = 101
PAGE_CAP_REASON = "CNV_OCCURRENCE_PAGE_CAP_EXCEEDED"
CNV_QUALITY_REASON = (
    "Complete positive-occurrence query; absence is not CNV-neutral evidence and caller "
    "compatibility remains unverified."
)


def merge_cnv_shard_evidence(shards: tuple[CnvShardEvidence, ...], *,
                             expected_shards: int) -> tuple[CnvGeneEvidence, ...]:
    """Union complete case-shard evidence, refusing any missing or overlapping shard.

    Shards are operational: they cannot change the recurrence thresholds, which
    are evaluated only here, on the merged all-shard evidence.
    """
    indices = sorted(shard.shard_index for shard in shards)
    if expected_shards < 1 or indices != list(range(expected_shards)):
        raise LiveRunError(
            "CNV_SHARDS_NOT_TERMINAL",
            f"expected shards 0..{expected_shards - 1}, observed {indices}")
    seen_cases: set[str] = set()
    for shard in shards:
        overlap = seen_cases & set(shard.case_ids)
        if overlap:
            raise LiveRunError("CNV_SHARD_CASE_OVERLAP",
                               f"case shards overlap on {sorted(overlap)[:3]}")
        seen_cases.update(shard.case_ids)
    categories: dict[str, dict[str, tuple[CnvCategory, set[str]]]] = {}
    callers: dict[str, set[str]] = {}
    conflicts: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    records: dict[str, int] = {}
    for shard in shards:
        for gene in shard.genes:
            per_gene = categories.setdefault(gene.gene_id, {})
            for summary in gene.categories:
                existing = per_gene.get(summary.raw_category)
                if existing is None:
                    per_gene[summary.raw_category] = (summary.category, set(summary.case_ids))
                    continue
                category, case_ids = existing
                if category is not summary.category:
                    raise LiveRunError(
                        "CNV_CATEGORY_MAPPING_CONFLICT",
                        f"{gene.gene_id}/{summary.raw_category} maps differently across shards")
                case_ids.update(summary.case_ids)
            callers.setdefault(gene.gene_id, set()).update(gene.callers)
            conflicts.setdefault(gene.gene_id, set()).update(gene.conflicting_case_ids)
            missing.setdefault(gene.gene_id, set()).update(gene.missing_sample_occurrence_ids)
            records[gene.gene_id] = records.get(gene.gene_id, 0) + gene.records
    merged: list[CnvGeneEvidence] = []
    for gene_id in sorted(categories):
        summaries = tuple(
            CnvCategorySummary(raw, category, tuple(sorted(case_ids)))
            for raw, (category, case_ids) in sorted(categories[gene_id].items()))
        merged.append(CnvGeneEvidence(
            gene_id, summaries, tuple(sorted(callers[gene_id])),
            tuple(sorted(conflicts[gene_id])), tuple(sorted(missing[gene_id])),
            records[gene_id],
        ))
    return tuple(merged)


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


def run_cnv_shard_scan(
    run_id: str,
    transport: AcquisitionTransport,
    repository: Repository,
    artifacts: ArtifactStore,
    emit: Callable[..., Any],
    research_spec: ResearchSpec,
    *,
    shard_index: int,
    case_shard_size: int = CNV_CASE_SHARD_SIZE,
) -> CnvShardEvidence:
    """Scan one complete operational case shard of the project's CNV occurrences.

    The shard is a partition of the declared cohort frame; thresholds are never
    evaluated here. Pages are validated strictly, a page-cap breach or a total
    change fails closed, and the shard evidence is published only under a
    terminal page ledger.
    """
    cohort_spec = research_spec.cohort
    emit("CNV_DISCOVERY_STARTED", f"cnv-shard:{shard_index}:started:{uuid4()}",
         "Independent CNV case-shard scan started.",
         data={"spec_id": research_spec.spec_id, "shard_index": shard_index,
               "case_shard_size": case_shard_size})
    status_response = transport.request(status_request())
    status = parse_status(status_response.body, response_meta(status_response, None))
    release = status.data_release or "UNVERIFIED_RELEASE"
    project_response = transport.request(cohort_project_request(cohort_spec.project_id))
    projects = parse_projects(project_response.body, response_meta(project_response, release))
    if len(projects) != 1 or projects[0].project_id != cohort_spec.project_id:
        raise LiveRunError("CNV_PROJECT_NOT_FOUND",
                           f"project {cohort_spec.project_id} did not resolve uniquely")
    cohort = acquire_cohort(transport, projects[0], research_spec.acquisition, release)
    case_ids = sorted(case.case_id for case in cohort.cases)
    if not case_ids:
        raise LiveRunError("CNV_SHARD_NO_CASES", "the declared cohort frame is empty")
    windows = [case_ids[index:index + case_shard_size]
               for index in range(0, len(case_ids), case_shard_size)]
    if shard_index < 0 or shard_index >= len(windows):
        raise LiveRunError("CNV_SHARD_INDEX_OUT_OF_RANGE",
                           f"shard {shard_index} of {len(windows)}")
    shard_cases = windows[shard_index]
    sources: list[OperationalSource] = [
        response_operational_source(status_response, release=release),
        response_operational_source(project_response, release=release),
        *cohort.sources,
    ]
    warnings = list(status.warnings) + list(cohort.warnings)
    categories: dict[str, dict[str, tuple[CnvCategory, set[str]]]] = {}
    callers: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    rows_by_gene: dict[str, set[str]] = {}
    records: list[ShardRecord] = []
    total: int | None = None
    offset = 0
    page_count = 0
    while True:
        response = transport.request(cnv_occurrence_shard_page_request(
            cohort_spec.project_id, shard_cases, offset=offset,
            size=research_spec.cnv_discovery.page_size))
        page = parse_cnv_occurrence_scan_page(
            response.body, response_meta(response, release),
            expected_project=cohort_spec.project_id, expected_cases=set(shard_cases),
            expected_offset=offset, expected_size=research_spec.cnv_discovery.page_size)
        sources.append(response_operational_source(response, release=release))
        warnings.extend(page.warnings)
        page_count += 1
        if page_count > CNV_SCAN_MAX_PAGES:
            raise LiveRunError("CNV_SCAN_PAGE_CAP_EXCEEDED",
                               f"shard {shard_index} exceeded {CNV_SCAN_MAX_PAGES} pages")
        if total is None:
            total = page.total
        elif page.total != total:
            raise LiveRunError("CNV_TOTAL_CHANGED",
                               f"shard {shard_index}: {total} became {page.total}")
        for record in page.occurrences:
            per_gene = categories.setdefault(record.gene_id, {})
            existing = per_gene.get(record.raw_category)
            if existing is None:
                per_gene[record.raw_category] = (cnv_category(record.raw_category),
                                                 {record.case_id})
            else:
                existing[1].add(record.case_id)
            rows_by_gene.setdefault(record.gene_id, set()).add(record.occurrence_id)
            if record.caller is not None:
                callers.setdefault(record.gene_id, set()).add(record.caller)
            if record.sample_id is None:
                missing.setdefault(record.gene_id, set()).add(record.occurrence_id)
        records.append(ShardRecord(
            index=page_count - 1, status=ShardStatus.COMPLETED, item_count=page.count,
            request_hash=response.request_hash, response_hash=response.body_sha256,
            artifact_id=response.artifact.artifact_id, detail=None))
        offset += page.count
        if offset >= page.total:
            break
        if page.count == 0:
            raise LiveRunError("CNV_PAGE_INCOMPLETE",
                               f"shard {shard_index}: empty page before total {page.total}")
    conflicts: dict[str, set[str]] = {}
    for gene_id, per_gene in categories.items():
        labels_by_case: dict[str, set[str]] = {}
        for raw_category, (_, cases) in per_gene.items():
            for case_id in cases:
                labels_by_case.setdefault(case_id, set()).add(raw_category)
        conflicting = {case_id for case_id, labels in labels_by_case.items() if len(labels) > 1}
        if conflicting:
            conflicts[gene_id] = conflicting
    genes = tuple(
        CnvGeneEvidence(
            gene_id,
            tuple(CnvCategorySummary(raw_category, category, tuple(sorted(cases)))
                  for raw_category, (category, cases) in sorted(per_gene.items())),
            tuple(sorted(callers.get(gene_id, set()))),
            tuple(sorted(conflicts.get(gene_id, set()))),
            tuple(sorted(missing.get(gene_id, set()))),
            len(rows_by_gene[gene_id]),
        )
        for gene_id, per_gene in sorted(categories.items())
    )
    evidence = CnvShardEvidence(
        shard_index, tuple(shard_cases), cohort_spec.project_id, release, genes, int(total or 0),
        tuple(sources), tuple(warnings))
    ledger = ShardLedger(kind=ShardKind.CNV_SHARD_PAGES, required=len(records),
                         records=tuple(records))
    publish_shard_ledger(
        artifacts, repository, run_id, ledger,
        relative_path=f"runs/{run_id}/cnv-discovery/shard-{shard_index:04d}-pages.json")
    if not ledger.terminal:
        raise LiveRunError("SHARD_LEDGER_NOT_TERMINAL",
                           f"shard {shard_index} page ledger is not terminal")
    artifact = artifacts.publish(
        CNV_SHARD_ARTIFACT_PATH.format(index=shard_index),
        write_cnv_shard_evidence(evidence), "application/json", "cnv-shard-evidence")
    repository.register_artifact(artifact, run_id)
    emit("CNV_SHARD_SCAN_COMPLETED", f"cnv-shard:{shard_index}:completed:{uuid4()}",
         f"CNV case shard {shard_index} scanned over {len(shard_cases)} case(s).",
         data={"shard_index": shard_index, "cases": len(shard_cases), "genes": len(genes),
               "records": int(total or 0), "release": release,
               "shard_hash": cnv_shard_identity(evidence),
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return evidence


def run_cnv_shard_merge(
    run_id: str,
    repository: Repository,
    artifacts: ArtifactStore,
    emit: Callable[..., Any],
    research_spec: ResearchSpec,
    *,
    expected_shards: int,
    case_shard_size: int = CNV_CASE_SHARD_SIZE,
) -> CnvProjectScanResult:
    """Merge all required shard evidence into one project scan result, or fail closed."""
    shards: list[CnvShardEvidence] = []
    sources: list[OperationalSource] = []
    seen_release: str | None = None
    for index in range(expected_shards):
        path = CNV_SHARD_ARTIFACT_PATH.format(index=index)
        row = repository.artifact_at_path(path)
        if row is None:
            raise LiveRunError("CNV_SHARDS_NOT_TERMINAL", f"shard {index} evidence is missing")
        sha = str(row.get("sha256") or "")
        relative = str(row.get("relative_path") or "")
        if len(sha) != 64 or not relative:
            raise LiveRunError("CNV_SHARD_ARTIFACT_INVALID", f"shard {index} artifact row is invalid")
        body = artifacts.read(relative, sha)
        shard = read_cnv_shard_evidence(body)
        if seen_release is None:
            seen_release = shard.release
        elif shard.release != seen_release:
            raise LiveRunError("CNV_SHARD_RELEASE_MISMATCH",
                               f"shard {index} release differs from {seen_release}")
        shards.append(shard)
        sources.append(OperationalSource(
            source=ScientificSource(
                endpoint="/cnv_occurrences/shard-evidence",
                request_hash=cnv_shard_identity(shard), response_hash=sha,
                parser_version=PARSER_VERSION, release=shard.release,
                acquisition=Acquisition.COMPLETE, caller_family="MULTI_CALLER_CNV"),
            attempt_id=f"cnv-shard-{index}",
            artifact_id=str(row.get("artifact_id") or path),
            retrieved_at=str(row.get("created_at") or "UNKNOWN"),
            bytes_read=0, latency_ms=None, http_status=None, cache_hit=True,
        ))
    merged = merge_cnv_shard_evidence(tuple(shards), expected_shards=expected_shards)
    calls = tuple(
        CnvProjectCall(evidence, *cnv_lane_disposition(evidence)) for evidence in merged)
    result = CnvProjectScanResult(
        research_spec.spec_id, research_spec.cohort.cohort_id, research_spec.cohort.project_id,
        seen_release or "UNVERIFIED_RELEASE", CNV_SCAN_SELECTION_RULE, case_shard_size,
        expected_shards, cnv_scan_summary_method(), calls, tuple(sources), (), CNV_SCAN_LIMITATIONS)
    artifact = artifacts.publish(
        f"runs/{run_id}/cnv-discovery/project-scan-result.json",
        write_cnv_project_scan(result), "application/json", "cnv-project-scan-result")
    repository.register_artifact(artifact, run_id)
    emit("CNV_PROJECT_SCAN_COMPLETED", f"cnv-project-scan:completed:{uuid4()}",
         f"Merged CNV scan completed for {len(calls)} observed gene(s).",
         data={"genes": len(calls), "retained": len(result.retained_ids),
               "jev_review": len(result.jev_review_ids), "shards": expected_shards,
               "release": result.release,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result
