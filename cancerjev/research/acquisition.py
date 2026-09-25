"""Concrete bounded cohort and expression acquisition; no scientific policy or planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cancerjev.domain.discovery import OCCURRENCE_SCAN_MAX_PAGES
from cancerjev.domain.measurements import Acquisition, OperationalSource, ScientificSource, digest
from cancerjev.gdc.endpoints import (
    GDCRequest,
    cases_request,
    expression_availability_request,
    expression_gene_selection_request,
    expression_values_request,
    files_capability_request,
    gene_case_counts_request,
    mutated_cases_count_request,
    ssm_occurrence_page_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    FileFacets,
    GeneCaseCounts,
    ProjectCoverage,
    ProjectRecord,
    ProviderSelection,
    ResponseMeta,
    parse_cases,
    parse_expression_availability,
    parse_expression_values,
    parse_file_facets,
    parse_gene_case_counts,
    parse_gene_selection,
    parse_mutated_cases_count,
    parse_ssm_occurrence_page,
)
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.specs import AcquisitionSpec
from cancerjev.science.methods import ProjectFrame


class AcquisitionTransport(Protocol):
    def request(self, request: GDCRequest) -> GDCResponse: ...


class LiveRunError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CohortAcquisition:
    cases: tuple[CaseRecord, ...]
    frame_hash: str
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ExpressionAcquisition:
    availability: ExpressionAvailability | None
    provider: ProviderSelection | None
    values: ExpressionValues | None
    workflows: tuple[str, ...]
    strategies: tuple[str, ...]
    workflow_file_counts: tuple[tuple[str, int], ...]
    workflow_coverage_complete: bool
    provider_summary_unavailable_reason: str | None
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MutationAcquisition:
    counts: GeneCaseCounts
    coverage: ProjectCoverage
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MutationOccurrenceScan:
    """Complete per-project released-occurrence scan with local distinct-case derivation.

    Every page is parsed and validated fail-closed; occurrence ids are unique
    across the whole scan. ``distinct_cases_per_gene`` is the scientific
    quantity (MUTATION_AFFECTED_CASE_COUNT_V2): a gene absent from the maps has
    an observed zero because the scan is complete.
    """

    project_id: str
    page_size: int
    page_count: int
    total_occurrences: int
    bytes_read: int
    distinct_cases_per_gene: dict[str, int]
    occurrence_docs_per_gene: dict[str, int]
    consequences_per_gene: dict[str, dict[str, int]]
    protein_positions_per_gene: dict[str, dict[int, int]]
    canonical_transcript_counts_per_gene: dict[str, dict[str, int]]
    records_without_canonical_rows: int
    genes_without_canonical_rows: int
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]

    def counts_for(self, gene_id: str) -> tuple[int, int]:
        """(distinct affected cases, occurrence records) for one gene; zero when absent."""
        return (self.distinct_cases_per_gene.get(gene_id, 0),
                self.occurrence_docs_per_gene.get(gene_id, 0))


@dataclass(frozen=True)
class ExpressionGeneBatch:
    batch_index: int
    gene_ids: tuple[str, ...]
    availability: ExpressionAvailability
    values: ExpressionValues | None
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class BatchedExpressionAcquisition:
    batches: tuple[ExpressionGeneBatch, ...]
    workflows: tuple[str, ...]
    strategies: tuple[str, ...]
    workflow_file_counts: tuple[tuple[str, int], ...]
    workflow_coverage_complete: bool
    sources: tuple[OperationalSource, ...]
    warnings: tuple[str, ...]


def response_meta(response: GDCResponse, release: str | None) -> ResponseMeta:
    return ResponseMeta(
        endpoint=response.endpoint, method=response.method, request_hash=response.request_hash,
        response_sha256=response.body_sha256, artifact_id=response.artifact.artifact_id,
        retrieved_at=response.retrieved_at, source_release=release, completeness=response.completeness,
    )


def _acquisition_of(response: GDCResponse) -> Acquisition:
    try:
        return Acquisition(response.completeness)
    except ValueError as exc:
        raise LiveRunError(
            "UNKNOWN_RESPONSE_COMPLETENESS",
            f"{response.endpoint}: completeness {response.completeness!r} is not a known acquisition state",
        ) from exc


def response_operational_source(response: GDCResponse, *, release: str | None,
                                workflow_family: str | None = None,
                                caller_family: str | None = None,
                                strategy: str | None = None,
                                annotation_context: str | None = None) -> OperationalSource:
    """Typed provenance for one response, linked to its GDC attempt.

    The scientific source carries the logical request, response hash, parser
    version, acquisition state and any provider-exposed workflow/caller/strategy
    annotation; the operational source carries the attempt, artifact id and
    timestamps. Operational fields stay out of scientific identity.
    """
    return OperationalSource(
        source=ScientificSource(
            endpoint=response.endpoint,
            request_hash=response.request_hash,
            response_hash=response.body_sha256,
            parser_version=PARSER_VERSION,
            release=release or "UNVERIFIED_RELEASE",
            acquisition=_acquisition_of(response),
            workflow_family=workflow_family,
            caller_family=caller_family,
            strategy=strategy,
            annotation_context=annotation_context,
        ),
        attempt_id=f"{response.request_id or response.artifact.artifact_id}:{response.attempt_no}",
        artifact_id=response.artifact.artifact_id,
        retrieved_at=response.retrieved_at,
        bytes_read=len(response.body),
        latency_ms=response.latency_ms,
        http_status=response.http_status,
        cache_hit=response.from_cache,
    )

def _sum_if_complete(values: list[int | None]) -> int | None:
    return sum(value for value in values if value is not None) if all(value is not None for value in values) else None


def _acquire_count_batch(transport: AcquisitionTransport, gene_ids: list[str],
                         release: str | None) -> tuple[GeneCaseCounts, OperationalSource]:
    response = transport.request(gene_case_counts_request(gene_ids))
    counts = parse_gene_case_counts(response.body, response_meta(response, release))
    return counts, response_operational_source(response, release=release)


def acquire_project_coverage(transport: AcquisitionTransport,
                             release: str | None) -> tuple[ProjectCoverage, OperationalSource]:
    """One project-wide SSM coverage response; coverage is not an affected-case count."""
    response = transport.request(mutated_cases_count_request())
    coverage = parse_mutated_cases_count(response.body, response_meta(response, release))
    return coverage, response_operational_source(response, release=release)


def acquire_mutation_counts(transport: AcquisitionTransport, gene_ids: list[str],
                            release: str | None) -> MutationAcquisition:
    """Legacy indexed bucket contracts, retained for their contract tests.

    The live orchestrator derives affected-case counts from the corrected
    complete occurrence scan (``acquire_project_mutation_occurrence_scan``);
    no scientific lane admits a value produced by this bucket path.
    """
    counts, count_source = _acquire_count_batch(transport, gene_ids, release)
    coverage, coverage_source = acquire_project_coverage(transport, release)
    return MutationAcquisition(counts, coverage, (count_source, coverage_source),
                               tuple(counts.warnings + coverage.warnings))


def acquire_project_mutation_occurrence_scan(transport: AcquisitionTransport, project_id: str,
                                             page_size: int, release: str | None,
                                             ) -> MutationOccurrenceScan:
    """Complete deterministic scan of one project's released occurrence records.

    Pages are requested in ascending ``ssm_occurrence_id`` order and every page
    is parsed fail-closed (pagination invariants, project membership, ascending
    unique ids). The provider total must stay stable across pages and the page
    count is capped by the declared scan cap. Distinct-case and per-gene
    occurrence derivations happen here, once, over validated records only; no
    aggregation bucket value enters the quantity.
    """
    if not 1 <= page_size <= 10000:
        raise LiveRunError("INVALID_OCCURRENCE_SCAN_PAGE_SIZE",
                           f"occurrence scan page size {page_size} outside 1..10000")
    cases_per_gene: dict[str, set[str]] = {}
    docs_per_gene: dict[str, int] = {}
    consequences_per_gene: dict[str, dict[str, int]] = {}
    positions_per_gene: dict[str, dict[int, int]] = {}
    transcripts_per_gene: dict[str, dict[str, int]] = {}
    records_without_canonical_rows = 0
    genes_without_canonical_rows: set[str] = set()
    sources: list[OperationalSource] = []
    warnings: list[str] = []
    seen_occurrence_ids: set[str] = set()
    previous_last_id: str | None = None
    total: int | None = None
    bytes_read = 0
    offset = 0
    page_count = 0
    while True:
        response = transport.request(
            ssm_occurrence_page_request(project_id, offset=offset, size=page_size))
        bytes_read += len(response.body)
        page = parse_ssm_occurrence_page(
            response.body, response_meta(response, release), expected_project=project_id,
            expected_offset=offset, expected_size=page_size,
        )
        sources.append(response_operational_source(response, release=release))
        warnings.extend(page.warnings)
        page_count += 1
        if page_count > OCCURRENCE_SCAN_MAX_PAGES:
            raise LiveRunError(
                "OCCURRENCE_SCAN_PAGE_CAP_EXCEEDED",
                f"occurrence scan exceeded {OCCURRENCE_SCAN_MAX_PAGES} pages at offset {offset}",
            )
        if total is None:
            total = page.total
        elif page.total != total:
            raise LiveRunError(
                "OCCURRENCE_SCAN_TOTAL_CHANGED",
                f"occurrence scan total changed from {total} to {page.total} at offset {offset}",
            )
        for record in page.records:
            if record.occurrence_id in seen_occurrence_ids:
                raise LiveRunError(
                    "DUPLICATE_OCCURRENCE_ACROSS_PAGES",
                    f"occurrence scan returned duplicate {record.occurrence_id}",
                )
            if previous_last_id is not None and record.occurrence_id <= previous_last_id:
                raise LiveRunError(
                    "OCCURRENCE_SCAN_ORDER_VIOLATION",
                    f"occurrence scan page at offset {offset} does not ascend after the previous page",
                )
            seen_occurrence_ids.add(record.occurrence_id)
            previous_last_id = record.occurrence_id
            record_consequences: dict[str, set[str]] = {}
            record_positions: dict[str, set[int]] = {}
            record_transcripts: dict[str, set[str]] = {}
            for row in record.canonical_rows:
                if row.consequence:
                    record_consequences.setdefault(row.gene_id, set()).add(row.consequence)
                if row.protein_start is not None:
                    record_positions.setdefault(row.gene_id, set()).add(row.protein_start)
                if row.transcript_id:
                    record_transcripts.setdefault(row.gene_id, set()).add(row.transcript_id)
            if not record.canonical_rows:
                records_without_canonical_rows += 1
            for gene_id in record.gene_ids:
                cases_per_gene.setdefault(gene_id, set()).add(record.case_id)
                docs_per_gene[gene_id] = docs_per_gene.get(gene_id, 0) + 1
                for term in record_consequences.get(gene_id, ()):
                    consequences_per_gene.setdefault(gene_id, {})
                    consequences_per_gene[gene_id][term] = \
                        consequences_per_gene[gene_id].get(term, 0) + 1
                for position in record_positions.get(gene_id, ()):
                    positions_per_gene.setdefault(gene_id, {})
                    positions_per_gene[gene_id][position] = \
                        positions_per_gene[gene_id].get(position, 0) + 1
                for transcript_id in record_transcripts.get(gene_id, ()):
                    transcripts_per_gene.setdefault(gene_id, {})
                    transcripts_per_gene[gene_id][transcript_id] = \
                        transcripts_per_gene[gene_id].get(transcript_id, 0) + 1
                if (gene_id not in record_consequences and gene_id not in record_positions
                        and gene_id not in record_transcripts):
                    genes_without_canonical_rows.add(gene_id)
        offset += page.count
        if total == 0 or offset >= total:
            break
        if page.count == 0:
            raise LiveRunError(
                "OCCURRENCE_SCAN_STALLED",
                f"occurrence scan stalled at offset {offset} of {total}",
            )
    assert total is not None
    if records_without_canonical_rows:
        warnings.append(
            f"{project_id}: {records_without_canonical_rows} occurrence records carry no canonical "
            "transcript annotation")
    if genes_without_canonical_rows:
        warnings.append(
            f"{project_id}: {len(genes_without_canonical_rows)} annotated genes carry no canonical "
            "consequence rows; their composition is NOT_OBSERVED")
    return MutationOccurrenceScan(
        project_id=project_id, page_size=page_size, page_count=page_count, total_occurrences=total,
        bytes_read=bytes_read,
        distinct_cases_per_gene={gene_id: len(cases) for gene_id, cases in cases_per_gene.items()},
        occurrence_docs_per_gene=docs_per_gene,
        consequences_per_gene=consequences_per_gene,
        protein_positions_per_gene=positions_per_gene,
        canonical_transcript_counts_per_gene=transcripts_per_gene,
        records_without_canonical_rows=records_without_canonical_rows,
        genes_without_canonical_rows=len(genes_without_canonical_rows),
        sources=tuple(sources), warnings=tuple(warnings),
    )


def _merge_expression_availability(
    case_ids: list[str], gene_ids: list[str],
    parts: list[tuple[list[str], ExpressionAvailability]],
) -> ExpressionAvailability:
    """Merge per-batch availability into one cohort-wide record.

    A gene returned by any batch is observed even when another batch omitted it,
    so merged observed and missing genes stay disjoint exactly as they are per batch.
    """
    expected_cases = set(case_ids)
    expected_genes = set(gene_ids)
    cases: dict[str, bool] = {}
    genes: dict[str, bool] = {}
    missing_cases: set[str] = set()
    missing_genes: set[str] = set()
    warnings: list[str] = []
    examined_cases: set[str] = set()
    for batch_case_ids, part in parts:
        batch_cases = set(batch_case_ids)
        if not batch_cases <= expected_cases or examined_cases & batch_cases:
            raise LiveRunError("INVALID_EXPRESSION_BATCH", "expression batches overlap or contain unknown cases")
        examined_cases.update(batch_cases)
        unexpected_cases = sorted((set(part.cases) | set(part.missing_cases)) - batch_cases)
        unexpected_genes = sorted((set(part.genes) | set(part.missing_genes)) - expected_genes)
        if unexpected_cases or unexpected_genes:
            raise LiveRunError(
                "UNEXPECTED_EXPRESSION_IDENTIFIER",
                f"availability returned unexpected cases={unexpected_cases[:3]} genes={unexpected_genes[:3]}",
            )
        overlap = set(cases) & set(part.cases)
        if overlap:
            raise LiveRunError(
                "DUPLICATE_EXPRESSION_CASE",
                f"availability returned duplicate cases across batches: {sorted(overlap)[:3]}",
            )
        cases.update(part.cases)
        for gene_id, available in part.genes.items():
            genes[gene_id] = genes.get(gene_id, False) or available
        missing_cases.update(part.missing_cases)
        missing_genes.update(part.missing_genes)
        warnings.extend(part.warnings)
    if examined_cases != expected_cases:
        raise LiveRunError("INCOMPLETE_EXPRESSION_BATCHES", "expression batches do not cover the cohort case frame")
    missing_cases.update(expected_cases - set(cases))
    missing_genes.update(expected_genes - set(genes))
    missing_genes -= set(genes)
    return ExpressionAvailability(
        cases={case_id: cases[case_id] for case_id in case_ids if case_id in cases},
        genes={gene_id: genes[gene_id] for gene_id in gene_ids if gene_id in genes},
        with_count=_sum_if_complete([part.with_count for _, part in parts]),
        without_count=_sum_if_complete([part.without_count for _, part in parts]),
        missing_cases=sorted(missing_cases), missing_genes=sorted(missing_genes),
        warnings=warnings,
    )


def _merge_expression_values(
    case_ids: list[str], gene_ids: list[str], parts: list[tuple[list[str], ExpressionValues | None]],
) -> ExpressionValues:
    expected_cases = set(case_ids)
    values: dict[str, dict[str, float | None]] = {gene_id: {} for gene_id in gene_ids}
    observed_genes: set[str] = set()
    examined_cases: set[str] = set()
    missing_case_ids: set[str] = set()
    warnings: list[str] = []
    nonfinite_values = 0
    for batch_case_ids, part in parts:
        batch_cases = set(batch_case_ids)
        if not batch_cases <= expected_cases or examined_cases & batch_cases:
            raise LiveRunError("INVALID_EXPRESSION_BATCH", "expression batches overlap or contain unknown cases")
        examined_cases.update(batch_cases)
        if part is None:
            missing_case_ids.update(batch_case_ids)
            continue
        returned_cases = batch_cases - set(part.missing_case_ids)
        missing_case_ids.update(part.missing_case_ids)
        nonfinite_values += part.nonfinite_values
        warnings.extend(part.warnings)
        for gene_id in gene_ids:
            row = part.values.get(gene_id)
            if row is None:
                for case_id in sorted(returned_cases):
                    values[gene_id][case_id] = None
                continue
            unexpected = set(row) - batch_cases
            if unexpected:
                raise LiveRunError(
                    "UNEXPECTED_EXPRESSION_IDENTIFIER",
                    f"values returned unexpected cases: {sorted(unexpected)[:3]}",
                )
            observed_genes.add(gene_id)
            values[gene_id].update(row)
    if examined_cases != expected_cases:
        raise LiveRunError("INCOMPLETE_EXPRESSION_BATCHES", "expression batches do not cover the cohort case frame")
    return ExpressionValues(
        values={gene_id: values[gene_id] for gene_id in gene_ids if gene_id in observed_genes},
        missing_case_ids=sorted(missing_case_ids),
        missing_gene_ids=[gene_id for gene_id in gene_ids if gene_id not in observed_genes],
        nonfinite_values=nonfinite_values,
        warnings=warnings,
    )


def acquire_cohort(transport: AcquisitionTransport, project: ProjectRecord,
                   acquisition: AcquisitionSpec, release: str | None) -> CohortAcquisition:
    sources: list[OperationalSource] = []
    warnings: list[str] = []
    cases: list[CaseRecord] = []
    seen_case_ids: set[str] = set()
    expected_total: int | None = None
    offset = 0
    page_number = 1
    while expected_total is None or len(cases) < expected_total:
        cases_response = transport.request(
            cases_request(project.project_id, acquisition.case_page_size, offset=offset, page=page_number)
        )
        page = parse_cases(cases_response.body, response_meta(cases_response, release))
        if page.offset is None or page.offset != offset:
            raise LiveRunError(
                "CASE_PAGE_OFFSET_INCONSISTENT",
                f"{project.project_id}: requested offset {offset}, provider reported {page.offset}",
            )
        if page.total is None:
            raise LiveRunError("CASE_TOTAL_MISSING", f"{project.project_id}: cases page has no total")
        if expected_total is None:
            expected_total = page.total
            if expected_total > acquisition.max_cohort_cases:
                raise LiveRunError(
                    "COHORT_CASE_LIMIT_EXCEEDED",
                    f"{project.project_id}: provider total {expected_total} exceeds configured maximum "
                    f"{acquisition.max_cohort_cases}",
                )
            if project.case_count is not None and expected_total != project.case_count:
                raise LiveRunError(
                    "CASE_TOTAL_INCONSISTENT",
                    f"{project.project_id}: case page total {expected_total} differs from inventory "
                    f"case count {project.case_count}",
                )
        elif page.total != expected_total:
            raise LiveRunError(
                "CASE_TOTAL_INCONSISTENT",
                f"{project.project_id}: cases total changed from {expected_total} to {page.total}",
            )
        if page.count != len(page.cases):
            raise LiveRunError(
                "CASE_PAGE_COUNT_INCONSISTENT",
                f"{project.project_id}: page count {page.count} differs from {len(page.cases)} records",
            )
        if not page.cases and len(cases) < expected_total:
            raise LiveRunError(
                "CASE_FRAME_INCOMPLETE",
                f"{project.project_id}: empty page at offset {offset} before total {expected_total}",
            )
        for case in page.cases:
            if case.project_id != project.project_id:
                raise LiveRunError(
                    "UNEXPECTED_CASE_PROJECT",
                    f"{project.project_id}: case {case.case_id} belongs to {case.project_id}",
                )
            if case.case_id in seen_case_ids:
                raise LiveRunError(
                    "DUPLICATE_CASE_ID",
                    f"{project.project_id}: duplicate case {case.case_id} across pages",
                )
            seen_case_ids.add(case.case_id)
            cases.append(case)
        sources.append(response_operational_source(cases_response, release=release))
        warnings += page.warnings
        offset += page.count
        page_number += 1
    if len(cases) != expected_total:
        raise LiveRunError(
            "CASE_FRAME_INCOMPLETE",
            f"{project.project_id}: collected {len(cases)} of {expected_total} cases",
        )
    cases = sorted(cases, key=lambda case: case.case_id)
    case_ids = [case.case_id for case in cases]
    frame_hash = digest(sorted(case_ids))
    return CohortAcquisition(tuple(cases), frame_hash, tuple(sources), tuple(warnings))


EXPRESSION_WORKFLOW_DATA_TYPE = "Gene Expression Quantification"
MISSING_FACET_KEY = "_missing"


def _expression_workflow_coverage(
    project_id: str, facets: FileFacets,
) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...], tuple[str, ...], bool, tuple[str, ...]]:
    """Provider workflow counts over every open expression file.

    Returns (workflows, workflow_file_counts, strategies, coverage_complete, warnings).
    Coverage is complete only when every open expression file carries a named
    provider workflow type; otherwise the lane stays PARTIAL. A provider-reported
    controlled access bucket fails closed even though the request filters to open
    files, because a controlled file can then never be silently averaged in.
    """
    warnings: list[str] = []
    controlled = {key: count for key, count in facets.facet("access").items()
                  if key != "open" and count > 0}
    if controlled:
        raise LiveRunError(
            "CONTROLLED_RECORD_RETURNED",
            f"{project_id}: provider aggregate reports non-open expression files: {sorted(controlled)}",
        )
    workflows_map = facets.facet("analysis.workflow_type")
    missing_workflow_files = workflows_map.pop(MISSING_FACET_KEY, 0)
    workflow_counts = tuple(sorted((name, count) for name, count in workflows_map.items()
                                   if count > 0))
    strategies_map = facets.facet("experimental_strategy")
    missing_strategy_files = strategies_map.pop(MISSING_FACET_KEY, 0)
    strategies = tuple(sorted(name for name, count in strategies_map.items() if count > 0))
    total = facets.total_open_files
    named_files = sum(count for _, count in workflow_counts)
    coverage_complete = bool(workflow_counts) and missing_workflow_files == 0 and (
        total is None or named_files == total)
    if not coverage_complete:
        warnings.append(
            f"{project_id}: expression workflow coverage is incomplete ({named_files} of "
            f"{total if total is not None else 'unknown'} open files carry a named workflow type; "
            f"{missing_workflow_files} carry none)"
        )
    if missing_strategy_files:
        warnings.append(
            f"{project_id}: {missing_strategy_files} open expression files carry no experimental strategy"
        )
    return (tuple(name for name, _ in workflow_counts), workflow_counts, strategies,
            coverage_complete, tuple(warnings))


def _expression_annotation(
    project_id: str, workflows: tuple[str, ...], strategies: tuple[str, ...], coverage_complete: bool,
) -> tuple[dict[str, str | None], list[str]]:
    """Single-family provider annotation for expression sources, or an explicit note."""
    if not coverage_complete:
        return {}, [f"{project_id}: expression workflow annotation withheld: coverage is incomplete"]
    if workflows == ("STAR - Counts",):
        return {"workflow_family": "STAR_COUNTS",
                "strategy": strategies[0] if len(strategies) == 1 else None,
                "annotation_context": "GENCODE_V36"}, []
    return {}, [f"{project_id}: expression workflow families are mixed; "
                "no single annotation context is claimed"]


def acquire_expression(transport: AcquisitionTransport, project: ProjectRecord,
                       acquisition: AcquisitionSpec, release: str | None,
                       cohort: CohortAcquisition, gene_ids: list[str]) -> ExpressionAcquisition:
    sources: list[OperationalSource] = []
    warnings: list[str] = []
    case_ids = [case.case_id for case in cohort.cases]
    facets_response = transport.request(
        files_capability_request(project.project_id, data_type=EXPRESSION_WORKFLOW_DATA_TYPE)
    )
    facets = parse_file_facets(facets_response.body, response_meta(facets_response, release))
    workflows, workflow_file_counts, strategies, coverage_complete, coverage_warnings = (
        _expression_workflow_coverage(project.project_id, facets))
    annotation, annotation_warnings = _expression_annotation(
        project.project_id, workflows, strategies, coverage_complete)
    sources.append(response_operational_source(facets_response, release=release))
    warnings += list(facets.warnings) + list(coverage_warnings) + annotation_warnings
    if not coverage_complete:
        warnings.append(
            f"{project.project_id}: expression lane stays PARTIAL because workflow coverage is not "
            "complete over the examined cohort"
        )
    availability: ExpressionAvailability | None = None
    provider: ProviderSelection | None = None
    values: ExpressionValues | None = None
    provider_summary_unavailable_reason: str | None = None
    if case_ids:
        batches = [case_ids[index:index + acquisition.case_batch_size]
                   for index in range(0, len(case_ids), acquisition.case_batch_size)]
        availability_parts: list[tuple[list[str], ExpressionAvailability]] = []
        value_parts: list[tuple[list[str], ExpressionValues | None]] = []
        for batch_case_ids in batches:
            availability_response = transport.request(
                expression_availability_request(batch_case_ids, gene_ids)
            )
            batch_availability = parse_expression_availability(
                availability_response.body, response_meta(availability_response, release),
                expected_cases=batch_case_ids, expected_genes=gene_ids,
            )
            availability_parts.append((batch_case_ids, batch_availability))
            sources.append(response_operational_source(
                availability_response, release=release, **annotation))
            warnings += batch_availability.warnings
            cases_with_values = [
                case_id for case_id in batch_case_ids
                if batch_availability.cases.get(case_id) is True
            ]
            if cases_with_values:
                values_response = transport.request(expression_values_request(batch_case_ids, gene_ids))
                batch_values = parse_expression_values(
                    values_response.body, response_meta(values_response, release),
                    expected_cases=batch_case_ids, expected_genes=gene_ids,
                )
                value_parts.append((batch_case_ids, batch_values))
                sources.append(response_operational_source(
                    values_response, release=release, **annotation))
                warnings += batch_values.warnings
            else:
                value_parts.append((batch_case_ids, None))
        availability = _merge_expression_availability(case_ids, gene_ids, availability_parts)
        values = _merge_expression_values(case_ids, gene_ids, value_parts)
        if len(batches) == 1 and any(availability.cases.get(case_id) is True for case_id in case_ids):
            selection_response = transport.request(expression_gene_selection_request(case_ids, gene_ids))
            provider = parse_gene_selection(
                selection_response.body, response_meta(selection_response, release),
                expected_genes=gene_ids,
            )
            sources.append(response_operational_source(
                selection_response, release=release, **annotation))
            warnings += provider.warnings
        elif len(batches) > 1:
            provider_summary_unavailable_reason = "BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE"
            warnings.append(
                f"{project.project_id}: provider expression summary unavailable because per-batch "
                "medians and standard deviations are not valid cohort-wide summaries"
            )
        if not any(availability.cases.get(case_id) is True for case_id in case_ids):
            values = None
            warnings.append(
                f"{project.project_id}: no examined case has gene expression values; "
                "provider selection and local values lanes skipped (expression NOT_OBSERVED)"
            )
    return ExpressionAcquisition(availability, provider, values, workflows, strategies,
                                 workflow_file_counts, coverage_complete,
                                 provider_summary_unavailable_reason,
                                 tuple(sources), tuple(warnings))


def acquire_batched_expression(
    transport: AcquisitionTransport,
    project: ProjectRecord,
    acquisition: AcquisitionSpec,
    release: str | None,
    cohort: CohortAcquisition,
    gene_ids: list[str],
    gene_batch_size: int,
) -> BatchedExpressionAcquisition:
    """Acquire the fixed Stage 5 matrix in disjoint gene and case batches.

    File/workflow provenance is acquired once. Every two-dimensional batch is
    parsed against its exact requested identifiers before gene batches are
    merged over the complete cohort frame.
    """
    if not 1 <= gene_batch_size <= 100:
        raise LiveRunError("INVALID_EXPRESSION_GENE_BATCH", "gene batch size must be 1..100")
    case_ids = [case.case_id for case in cohort.cases]
    facets_response = transport.request(
        files_capability_request(project.project_id, data_type=EXPRESSION_WORKFLOW_DATA_TYPE)
    )
    facets = parse_file_facets(facets_response.body, response_meta(facets_response, release))
    workflows, workflow_file_counts, strategies, coverage_complete, coverage_warnings = (
        _expression_workflow_coverage(project.project_id, facets))
    annotation, annotation_warnings = _expression_annotation(
        project.project_id, workflows, strategies, coverage_complete)
    file_source = response_operational_source(facets_response, release=release)
    all_sources: list[OperationalSource] = [file_source]
    all_warnings: list[str] = (list(facets.warnings) + list(coverage_warnings)
                               + annotation_warnings)
    if not coverage_complete:
        all_warnings.append(
            f"{project.project_id}: expression lane stays PARTIAL because workflow coverage is not "
            "complete over the examined cohort"
        )
    result_batches: list[ExpressionGeneBatch] = []
    case_batches = [case_ids[index:index + acquisition.case_batch_size]
                    for index in range(0, len(case_ids), acquisition.case_batch_size)]
    for gene_index in range(0, len(gene_ids), gene_batch_size):
        batch_ids = gene_ids[gene_index:gene_index + gene_batch_size]
        availability_parts: list[tuple[list[str], ExpressionAvailability]] = []
        value_parts: list[tuple[list[str], ExpressionValues | None]] = []
        batch_sources: list[OperationalSource] = []
        batch_warnings: list[str] = []
        for batch_case_ids in case_batches:
            availability_response = transport.request(
                expression_availability_request(batch_case_ids, batch_ids)
            )
            availability = parse_expression_availability(
                availability_response.body, response_meta(availability_response, release),
                expected_cases=batch_case_ids, expected_genes=batch_ids,
            )
            availability_parts.append((batch_case_ids, availability))
            availability_source = response_operational_source(
                availability_response, release=release, **annotation)
            batch_sources.append(availability_source)
            batch_warnings.extend(availability.warnings)
            if any(availability.cases.get(case_id) is True for case_id in batch_case_ids):
                values_response = transport.request(
                    expression_values_request(batch_case_ids, batch_ids)
                )
                values = parse_expression_values(
                    values_response.body, response_meta(values_response, release),
                    expected_cases=batch_case_ids, expected_genes=batch_ids,
                )
                value_parts.append((batch_case_ids, values))
                batch_sources.append(response_operational_source(
                    values_response, release=release, **annotation))
                batch_warnings.extend(values.warnings)
            else:
                value_parts.append((batch_case_ids, None))
        merged_availability = _merge_expression_availability(
            case_ids, batch_ids, availability_parts)
        merged_values: ExpressionValues | None = _merge_expression_values(
            case_ids, batch_ids, value_parts)
        if not any(merged_availability.cases.get(case_id) is True for case_id in case_ids):
            merged_values = None
            batch_warnings.append(
                f"{project.project_id}: no examined case has expression values for gene batch "
                f"{gene_index // gene_batch_size}"
            )
        result_batches.append(ExpressionGeneBatch(
            gene_index // gene_batch_size, tuple(batch_ids), merged_availability, merged_values,
            tuple(batch_sources), tuple(batch_warnings),
        ))
        all_sources.extend(batch_sources)
        all_warnings.extend(batch_warnings)
    return BatchedExpressionAcquisition(
        tuple(result_batches), workflows, strategies, workflow_file_counts, coverage_complete,
        tuple(all_sources), tuple(all_warnings),
    )


def acquire_project_frame(transport: AcquisitionTransport, project: ProjectRecord,
                          acquisition: AcquisitionSpec, release: str | None,
                          gene_ids: list[str], discovery_hits: dict[str, DiscoveryHit],
                          ) -> tuple[ProjectFrame, tuple[OperationalSource, ...], list[str]]:
    cohort = acquire_cohort(transport, project, acquisition, release)
    expression = acquire_expression(transport, project, acquisition, release, cohort, gene_ids)
    frame = ProjectFrame(project.project_id, project, list(cohort.cases), cohort.frame_hash,
                         expression.availability, expression.provider, expression.values,
                         list(expression.workflows), list(expression.strategies), discovery_hits,
                         expression.provider_summary_unavailable_reason)
    return frame, tuple(cohort.sources + expression.sources), list(cohort.warnings + expression.warnings)
