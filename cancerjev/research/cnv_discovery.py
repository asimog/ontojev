"""Stage 6 complete, survivor-only CNV occurrence acquisition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import (
    cnv_shard_identity,
    read_cnv_shard_evidence,
    write_cnv_project_scan,
    write_cnv_shard_evidence,
)
from cancerjev.domain.discovery import (
    CNV_CASE_SHARD_SIZE,
    CNV_SCAN_LIMITATIONS,
    CNV_SCAN_MAX_PAGES,
    CNV_SCAN_SELECTION_RULE,
    CnvCategorySummary,
    CnvGeneEvidence,
    CnvProjectCall,
    CnvProjectScanResult,
    CnvShardEvidence,
    cnv_scan_summary_method,
)
from cancerjev.domain.events import utc_now
from cancerjev.domain.measurements import (
    Acquisition,
    OperationalSource,
    ScientificSource,
    digest,
)
from cancerjev.domain.scientific import (
    CnvCategory,
    cnv_category,
)
from cancerjev.domain.shards import ShardKind, ShardLedger, ShardRecord, ShardStatus
from cancerjev.gdc.endpoints import (
    MAX_CNV_CASE_SHARD_SIZE,
    cnv_occurrence_shard_page_request,
    cohort_project_request,
    status_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    parse_cnv_occurrence_scan_page,
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

CNV_SHARD_ARTIFACT_PATH = "runs/{run_id}/cnv-shards/shard-{index:04d}.json"
CNV_SHARD_RAW_EVICTION_POLICY = "cnv-shard-raw-eviction-v1"

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
    first = shards[0]
    identity = (first.project_id, first.release, first.spec_hash,
                first.cohort_case_ids, first.case_shard_size)
    for shard in shards:
        if (shard.project_id, shard.release, shard.spec_hash,
                shard.cohort_case_ids, shard.case_shard_size) != identity:
            raise LiveRunError("CNV_SHARD_SCOPE_MISMATCH", "shards must share one complete cohort manifest")
        start = shard.shard_index * first.case_shard_size
        if shard.case_ids != first.cohort_case_ids[start:start + first.case_shard_size]:
            raise LiveRunError("CNV_SHARD_SCOPE_MISMATCH", "shard cases do not match their declared window")
    required = (len(first.cohort_case_ids) + first.case_shard_size - 1) // first.case_shard_size
    if expected_shards != required or seen_cases != set(first.cohort_case_ids):
        raise LiveRunError("CNV_SHARDS_NOT_TERMINAL", "merge does not cover the full declared cohort")
    return tuple(merged)


def plan_cnv_case_shards(transport: AcquisitionTransport, research_spec: ResearchSpec, *,
                         case_shard_size: int = CNV_CASE_SHARD_SIZE,
                         ) -> tuple[tuple[str, ...], ...]:
    """Partition the declared cohort frame into deterministic sorted-case shards.

    The same partition rule is used by the single-shard scan; this planner exists
    so one canonical Campaign run can enumerate every required shard before the
    terminal merge. It acquires only the cohort frame (no occurrence reads).
    """
    if type(case_shard_size) is not int or not 1 <= case_shard_size <= MAX_CNV_CASE_SHARD_SIZE:
        raise LiveRunError("INVALID_CNV_SHARD_SIZE", f"case shard size must be 1..{MAX_CNV_CASE_SHARD_SIZE}")
    cohort_spec = research_spec.cohort
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
    return tuple(tuple(case_ids[index:index + case_shard_size])
                 for index in range(0, len(case_ids), case_shard_size))


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
    evict_raw: bool = True,
) -> CnvShardEvidence:
    """Scan one complete operational case shard of the project's CNV occurrences.

    The shard is a partition of the declared cohort frame; thresholds are never
    evaluated here. Pages are validated strictly, aggregated page by page while
    later pages download, and the shard evidence is published only under a terminal
    page ledger. With ``evict_raw`` (the canonical campaign behavior) the committed
    shard's raw page payload files are then evicted while the cache index rows stay
    immutable, so the on-disk footprint stays bounded to the derived evidence plus
    the shard in flight; an evicted payload reads as a cache miss and refetches
    live, and the terminal ledger keeps every page's request/response hash as
    provenance.
    """
    if type(case_shard_size) is not int or not 1 <= case_shard_size <= MAX_CNV_CASE_SHARD_SIZE:
        raise LiveRunError("INVALID_CNV_SHARD_SIZE", f"case shard size must be 1..{MAX_CNV_CASE_SHARD_SIZE}")
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
    raw_pages: list[Any] = []
    total: int | None = None
    offset = 0
    page_count = 0
    previous_occurrence_id: str | None = None
    while True:
        response = transport.request(cnv_occurrence_shard_page_request(
            cohort_spec.project_id, shard_cases, offset=offset,
            size=research_spec.cnv_discovery.page_size))
        page = parse_cnv_occurrence_scan_page(
            response.body, response_meta(response, release),
            expected_project=cohort_spec.project_id, expected_cases=set(shard_cases),
            expected_offset=offset, expected_size=research_spec.cnv_discovery.page_size)
        raw_pages.append(response.artifact)
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
        # The parser expands one provider row into multiple genes. Compare distinct
        # row IDs across pages before aggregating; never silently deduplicate a page.
        page_ids = sorted({record.occurrence_id for record in page.occurrences})
        if page_ids and previous_occurrence_id is not None and page_ids[0] <= previous_occurrence_id:
            raise LiveRunError("CNV_PAGE_ORDER_VIOLATION", "CNV row IDs repeat or regress across pages")
        if page_ids:
            previous_occurrence_id = page_ids[-1]
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
        tuple(sources), tuple(warnings), tuple(case_ids), case_shard_size,
        digest(research_spec.as_dict()))
    ledger = ShardLedger(kind=ShardKind.CNV_SHARD_PAGES, required=len(records),
                         records=tuple(records))
    publish_shard_ledger(
        artifacts, repository, run_id, ledger,
        relative_path=f"runs/{run_id}/cnv-discovery/shard-{shard_index:04d}-pages.json")
    if not ledger.terminal:
        raise LiveRunError("SHARD_LEDGER_NOT_TERMINAL",
                           f"shard {shard_index} page ledger is not terminal")
    artifact = artifacts.publish(
        CNV_SHARD_ARTIFACT_PATH.format(run_id=run_id, index=shard_index),
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
    if evict_raw:
        _evict_committed_shard_raw(
            repository=repository, artifacts=artifacts, emit=emit,
            shard_index=shard_index, raw_pages=tuple(raw_pages), ledger=ledger)
    return evidence


def _evict_committed_shard_raw(
    *, repository: Repository, artifacts: ArtifactStore, emit: Callable[..., Any],
    shard_index: int, raw_pages: tuple[Any, ...], ledger: ShardLedger,
) -> None:
    """Delete a committed shard's raw page payloads; derived evidence stays durable.

    Runs only after the terminal page ledger and the shard evidence artifact are
    committed, so an interrupted or failed shard never loses its raw pages. Each
    eviction is registered first (append-only) and the file is deleted after, so a
    payload is never missing without a declared eviction record; the doctor reports
    registered evictions as information instead of corruption. The cache index rows
    stay immutable and a lookup of an evicted payload reads no file and falls back
    to a live fetch; the terminal ledger keeps every page's request/response hash
    as provenance. The merge reads the derived shard evidence, never raw pages.
    """
    identities = tuple((str(page.artifact_id), int(page.size_bytes or 0))
                       for page in raw_pages)
    registered = repository.register_artifact_evictions(
        identities, policy_version=CNV_SHARD_RAW_EVICTION_POLICY, evicted_at=utc_now())
    evicted = 0
    bytes_freed = 0
    for page in raw_pages:
        size = int(getattr(page, "size_bytes", 0) or 0)
        if artifacts.evict(str(getattr(page, "relative_path", ""))):
            evicted += 1
            bytes_freed += size
    emit("CNV_SHARD_RAW_EVICTED", f"cnv-shard:{shard_index}:raw-evicted:{uuid4()}",
         f"Committed CNV shard {shard_index} raw pages evicted; derived evidence retained.",
         stage="STATE_GENERATION", level="warning",
         data={"shard_index": shard_index, "policy_version": CNV_SHARD_RAW_EVICTION_POLICY,
               "raw_artifacts": evicted, "registered": registered, "bytes": bytes_freed,
               "page_records": len(ledger.records)})


def run_cnv_shard_merge(
    run_id: str,
    repository: Repository,
    artifacts: ArtifactStore,
    emit: Callable[..., Any],
    research_spec: ResearchSpec,
    *,
    expected_shards: int,
    case_shard_size: int = CNV_CASE_SHARD_SIZE,
    source_run_ids: tuple[str, ...] | None = None,
    universe_ids: frozenset[str] | None = None,
) -> CnvProjectScanResult:
    """Merge all required shard evidence into one project scan result, or fail closed.

    When ``universe_ids`` is given, merged evidence outside the tested universe is
    excluded from the calls and recorded as a warning; raw shard evidence is
    untouched. The canonical campaign passes the release-bound Stage 4 universe, so
    a CNV call can never nominate a gene the union cannot evidence.
    """
    shards: list[CnvShardEvidence] = []
    sources: list[OperationalSource] = []
    seen_release: str | None = None
    origins = source_run_ids or (run_id,)
    if expected_shards < 1 or len(origins) not in (1, expected_shards):
        raise LiveRunError("CNV_SHARDS_NOT_TERMINAL", "provide one source run or one source run per shard")
    owner = repository.run_ownership(run_id)
    for index in range(expected_shards):
        source_run_id = origins[0] if len(origins) == 1 else origins[index]
        repository.require_run_ownership(source_run_id, owner)
        path = CNV_SHARD_ARTIFACT_PATH.format(run_id=source_run_id, index=index)
        row = repository.artifact_at_path(path)
        if row is None:
            raise LiveRunError("CNV_SHARDS_NOT_TERMINAL", f"shard {index} evidence is missing")
        sha = str(row.get("sha256") or "")
        relative = str(row.get("relative_path") or "")
        if len(sha) != 64 or not relative:
            raise LiveRunError("CNV_SHARD_ARTIFACT_INVALID", f"shard {index} artifact row is invalid")
        body = artifacts.read(relative, sha)
        shard = read_cnv_shard_evidence(body)
        if (shard.project_id != research_spec.cohort.project_id
                or shard.spec_hash != digest(research_spec.as_dict())
                or shard.case_shard_size != case_shard_size or shard.shard_index != index):
            raise LiveRunError("CNV_SHARD_SCOPE_MISMATCH", "shard does not match the requested research scope")
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
        expected_shards, cnv_scan_summary_method(), calls, tuple(sources), (),
        CNV_SCAN_LIMITATIONS)
    excluded_outside_universe = 0
    if universe_ids is not None:
        before = len(result.calls)
        result = scope_cnv_scan_to_universe(result, universe_ids)
        excluded_outside_universe = before - len(result.calls)
    artifact = artifacts.publish(
        f"runs/{run_id}/cnv-discovery/project-scan-result.json",
        write_cnv_project_scan(result), "application/json", "cnv-project-scan-result")
    repository.register_artifact(artifact, run_id)
    emit("CNV_PROJECT_SCAN_COMPLETED", f"cnv-project-scan:completed:{uuid4()}",
         f"Merged CNV scan completed for {len(result.calls)} observed gene(s).",
         data={"genes": len(result.calls), "retained": len(result.retained_ids),
               "jev_review": len(result.jev_review_ids), "shards": expected_shards,
               "excluded_outside_universe": excluded_outside_universe,
               "release": result.release,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result


def scope_cnv_scan_to_universe(
    result: CnvProjectScanResult, universe_ids: frozenset[str],
) -> CnvProjectScanResult:
    """Drop merged CNV calls outside the tested universe, recording the count.

    The published shard and merge artifacts stay untouched; only the in-memory
    result is scoped, so a CNV call can never nominate a gene the union cannot
    evidence. The canonical campaign applies this to a fresh merge; the declared
    evidence-resume continuation applies the same function to an already-merged
    result, so both routes produce identically scoped calls.
    """
    excluded = tuple(sorted(call.evidence.gene_id for call in result.calls
                            if call.evidence.gene_id not in universe_ids))
    if not excluded:
        return result
    calls = tuple(call for call in result.calls if call.evidence.gene_id in universe_ids)
    warnings = result.warnings + (
        f"CNV_UNIVERSE_EXCLUSION: {len(excluded)} merged CNV gene(s) outside the tested universe "
        f"were excluded from the calls",
    )
    return replace(result, calls=calls, warnings=warnings)
