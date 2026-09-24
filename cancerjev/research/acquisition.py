"""Concrete bounded cohort and expression acquisition; no scientific policy or planner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from cancerjev.domain.events import canonical_json
from cancerjev.gdc.endpoints import (
    GDCRequest,
    cases_request,
    expression_availability_request,
    expression_gene_selection_request,
    expression_values_request,
    files_expression_request,
    gene_case_counts_request,
    mutated_cases_count_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    ProjectCoverage,
    ProjectRecord,
    ProviderSelection,
    ResponseMeta,
    parse_cases,
    parse_expression_availability,
    parse_expression_values,
    parse_files_provenance,
    parse_gene_case_counts,
    parse_gene_selection,
    parse_mutated_cases_count,
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
    sources: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ExpressionAcquisition:
    availability: ExpressionAvailability | None
    provider: ProviderSelection | None
    values: ExpressionValues | None
    workflows: tuple[str, ...]
    strategies: tuple[str, ...]
    provider_summary_unavailable_reason: str | None
    sources: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MutationAcquisition:
    counts: GeneCaseCounts
    coverage: ProjectCoverage
    sources: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]


def response_meta(response: GDCResponse, release: str | None) -> ResponseMeta:
    return ResponseMeta(
        endpoint=response.endpoint, method=response.method, request_hash=response.request_hash,
        response_sha256=response.body_sha256, artifact_id=response.artifact.artifact_id,
        retrieved_at=response.retrieved_at, source_release=release, completeness=response.completeness,
    )

def response_source(response: GDCResponse, *, locator: str, release: str | None) -> dict[str, Any]:
    """Scientific provenance for one response, linked to its GDC attempt.

    ``normalized_request_hash`` is the logical request; ``request_id`` and
    ``attempt_no`` identify the current cache/network attempt that supplied the
    bytes; the artifact id and response hash identify the retained response; and
    ``json_pointer_or_table_locator`` is the scientific locator inside it.
    Operational fields stay out of scientific identity.
    """
    return {
        "request_id": response.request_id,
        "attempt_no": response.attempt_no,
        "from_cache": response.from_cache,
        "response_artifact_id": response.artifact.artifact_id,
        "response_sha256": response.body_sha256,
        "endpoint": response.endpoint,
        "normalized_request_hash": response.request_hash,
        "retrieved_at": response.retrieved_at,
        "source_release": release,
        "release_status": "KNOWN" if release else "UNVERIFIED",
        "parser_version": PARSER_VERSION,
        "json_pointer_or_table_locator": locator,
        "completeness": response.completeness,
    }

def _sum_if_complete(values: list[int | None]) -> int | None:
    return sum(value for value in values if value is not None) if all(value is not None for value in values) else None


def acquire_mutation_counts(transport: AcquisitionTransport, gene_ids: list[str],
                            release: str | None) -> MutationAcquisition:
    """Existing indexed count contracts, independent of candidate selection policy."""
    response = transport.request(gene_case_counts_request(gene_ids))
    counts = parse_gene_case_counts(response.body, response_meta(response, release))
    count_source = response_source(response, locator="/analysis/top_cases_counts_by_genes", release=release)
    response = transport.request(mutated_cases_count_request())
    coverage = parse_mutated_cases_count(response.body, response_meta(response, release))
    coverage_source = response_source(response, locator="/analysis/mutated_cases_count_by_project", release=release)
    return MutationAcquisition(counts, coverage, (count_source, coverage_source),
                               tuple(counts.warnings + coverage.warnings))


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
    sources: list[dict[str, Any]] = []
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
        sources.append(response_source(
            cases_response, locator=f"/cases[{project.project_id}]/page/{page_number}",
            release=release,
        ))
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
    frame_hash = hashlib.sha256(canonical_json(sorted(case_ids))).hexdigest()
    return CohortAcquisition(tuple(cases), frame_hash, tuple(sources), tuple(warnings))


def acquire_expression(transport: AcquisitionTransport, project: ProjectRecord,
                       acquisition: AcquisitionSpec, release: str | None,
                       cohort: CohortAcquisition, gene_ids: list[str]) -> ExpressionAcquisition:
    sources: list[dict[str, Any]] = []
    warnings: list[str] = []
    case_ids = [case.case_id for case in cohort.cases]
    files_response = transport.request(
        files_expression_request(project.project_id, acquisition.expression_file_sample_size)
    )
    provenance = parse_files_provenance(files_response.body, response_meta(files_response, release))
    sources.append(response_source(files_response, locator=f"/files[{project.project_id}]",
                                release=release))
    warnings += provenance.warnings
    if provenance.non_open_records:
        raise LiveRunError("CONTROLLED_RECORD_RETURNED",
                           f"{project.project_id}: {provenance.non_open_records} non-open file records")
    availability: ExpressionAvailability | None = None
    provider: ProviderSelection | None = None
    values: ExpressionValues | None = None
    provider_summary_unavailable_reason: str | None = None
    if case_ids:
        batches = [case_ids[index:index + acquisition.case_batch_size]
                   for index in range(0, len(case_ids), acquisition.case_batch_size)]
        availability_parts: list[tuple[list[str], ExpressionAvailability]] = []
        value_parts: list[tuple[list[str], ExpressionValues | None]] = []
        for batch_number, batch_case_ids in enumerate(batches, start=1):
            availability_response = transport.request(
                expression_availability_request(batch_case_ids, gene_ids)
            )
            batch_availability = parse_expression_availability(
                availability_response.body, response_meta(availability_response, release),
                expected_cases=batch_case_ids, expected_genes=gene_ids,
            )
            availability_parts.append((batch_case_ids, batch_availability))
            sources.append(response_source(
                availability_response,
                locator=f"/gene_expression/availability[{project.project_id}]/batch/{batch_number}",
                release=release,
            ))
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
                sources.append(response_source(
                    values_response,
                    locator=f"/gene_expression/values[{project.project_id}]/batch/{batch_number}",
                    release=release,
                ))
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
            sources.append(response_source(
                selection_response,
                locator=f"/gene_expression/gene_selection[{project.project_id}]",
                release=release,
            ))
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
    return ExpressionAcquisition(availability, provider, values, tuple(provenance.workflows),
                                 tuple(provenance.strategies), provider_summary_unavailable_reason,
                                 tuple(sources), tuple(warnings))


def acquire_project_frame(transport: AcquisitionTransport, project: ProjectRecord,
                          acquisition: AcquisitionSpec, release: str | None,
                          gene_ids: list[str], discovery_hits: dict[str, DiscoveryHit],
                          ) -> tuple[ProjectFrame, list[dict[str, Any]], list[str]]:
    cohort = acquire_cohort(transport, project, acquisition, release)
    expression = acquire_expression(transport, project, acquisition, release, cohort, gene_ids)
    frame = ProjectFrame(project.project_id, project, list(cohort.cases), cohort.frame_hash,
                         expression.availability, expression.provider, expression.values,
                         list(expression.workflows), list(expression.strategies), discovery_hits,
                         expression.provider_summary_unavailable_reason)
    return frame, list(cohort.sources + expression.sources), list(cohort.warnings + expression.warnings)
