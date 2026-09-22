"""Strict parsers: raw GDC bytes to normalized provider records.

Rules: required scientific fields must be present and correctly typed; missing
optional fields become explicit availability, never zero; unknown extra fields
are ignored but API warnings are preserved; completeness metadata is preserved;
NaN/Infinity are rejected; duplicates and unexpected identifiers are errors.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

PARSER_VERSION = "gdc-parser-v1"


class ParserError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ResponseMeta:
    endpoint: str
    method: str
    request_hash: str
    response_sha256: str
    artifact_id: str | None
    retrieved_at: str
    source_release: str | None
    completeness: str


@dataclass(frozen=True)
class ParsedStatus:
    commit: str | None
    data_release: str | None
    tag: str | None
    status: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str | None
    program_name: str | None
    primary_site: list[str]
    disease_type: list[str]
    case_count: int | None
    file_count: int | None
    data_categories: list[str]


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    submitter_id: str | None
    project_id: str
    sample_types: list[str]


@dataclass(frozen=True)
class CasesPage:
    cases: list[CaseRecord]
    total: int | None
    count: int
    size: int | None
    offset: int | None
    pages: int | None
    complete: bool
    warnings: list[str]


@dataclass(frozen=True)
class GeneRecord:
    gene_id: str
    symbol: str
    name: str | None
    biotype: str | None
    is_cancer_gene_census: bool | None


@dataclass(frozen=True)
class DiscoveryHit:
    gene_id: str
    symbol: str | None
    rank: int
    score: float | None


@dataclass(frozen=True)
class GeneCaseCounts:
    projects: dict[str, dict[str, int]]
    hits_total: int | None
    complete: bool
    partial_reasons: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ProjectCoverage:
    case_with_ssm: dict[str, int]
    complete: bool
    partial_reasons: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ExpressionAvailability:
    cases: dict[str, bool]
    genes: dict[str, bool]
    with_count: int | None
    without_count: int | None
    missing_cases: list[str]
    missing_genes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ProviderGene:
    gene_id: str
    symbol: str | None
    median: float | None
    stddev: float | None


@dataclass(frozen=True)
class ProviderSelection:
    genes: dict[str, ProviderGene]
    missing_genes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ExpressionValues:
    values: dict[str, dict[str, float | None]]
    missing_case_ids: list[str]
    missing_gene_ids: list[str]
    nonfinite_values: int
    warnings: list[str]


@dataclass(frozen=True)
class FilesProvenance:
    workflows: list[str]
    strategies: list[str]
    files_seen: int
    non_open_records: int
    warnings: list[str]


def _load_json(body: bytes, meta: ResponseMeta) -> dict[str, Any]:
    if meta.completeness != "COMPLETE":
        raise ParserError("INCOMPLETE_RESPONSE", f"{meta.endpoint} completeness={meta.completeness}")
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParserError("MALFORMED_JSON", f"{meta.endpoint}: {exc}") from exc
    if not isinstance(document, dict):
        raise ParserError("MALFORMED_JSON", f"{meta.endpoint}: top level is not an object")
    return document


def _warnings(document: dict[str, Any]) -> list[str]:
    warnings = document.get("warnings")
    if not warnings:
        return []
    if not isinstance(warnings, dict):
        return ["unparsed warnings payload"]
    result: list[str] = []
    for key, value in warnings.items():
        result.append(f"{key}: {json.dumps(value, sort_keys=True)}")
    return result


def _require(document: dict[str, Any], path: str, types: tuple[type, ...], context: str) -> Any:
    node: Any = document
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ParserError("MISSING_FIELD", f"{context}: missing {path}")
        node = node[part]
    if node is None:
        raise ParserError("MISSING_FIELD", f"{context}: null {path}")
    if isinstance(node, bool) and bool not in types:
        raise ParserError("INVALID_FIELD", f"{context}: {path} has wrong type")
    if not isinstance(node, types):
        raise ParserError("INVALID_FIELD", f"{context}: {path} has wrong type {type(node).__name__}")
    return node


def _optional(document: dict[str, Any], path: str, types: tuple[type, ...], context: str) -> Any:
    node: Any = document
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if node is None:
        return None
    if isinstance(node, bool) and bool not in types:
        return None
    if not isinstance(node, types):
        return None
    return node


def _finite(value: Any, context: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParserError("INVALID_FIELD", f"{context}: non-numeric value")
    number = float(value)
    if not math.isfinite(number):
        raise ParserError("NONFINITE_VALUE", f"{context}: {value!r}")
    return number


def _string_list(document: dict[str, Any], path: str, context: str) -> list[str]:
    value = _optional(document, path, (list,), context)
    if not value:
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ParserError("INVALID_FIELD", f"{context}: {path} contains a non-string")
        result.append(item)
    return result


def _nested_string_list(document: dict[str, Any], list_path: str, key: str, context: str) -> list[str]:
    """Extract a string field from a list of objects, e.g. summary.data_categories[].data_category."""
    value = _optional(document, list_path, (list,), context)
    if not value:
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            raise ParserError("INVALID_FIELD", f"{context}: {list_path} contains a non-object")
        nested = item.get(key)
        if nested is None:
            continue
        if not isinstance(nested, str):
            raise ParserError("INVALID_FIELD", f"{context}: {list_path}[].{key} is not a string")
        result.append(nested)
    return result


def _hits(document: dict[str, Any], context: str) -> list[dict[str, Any]]:
    hits = _require(document, "data.hits", (list,), context)
    for hit in hits:
        if not isinstance(hit, dict):
            raise ParserError("MALFORMED_JSON", f"{context}: hit is not an object")
    return hits


def _aggregation_completeness(node: dict[str, Any], context: str) -> list[str]:
    reasons: list[str] = []
    if node.get("timed_out") is True:
        reasons.append("timed_out")
    shards = node.get("_shards")
    if isinstance(shards, dict) and shards.get("failed"):
        reasons.append(f"failed_shards={shards['failed']}")
    if node.get("sum_other_doc_count"):
        reasons.append(f"sum_other_doc_count={node['sum_other_doc_count']}")
    if node.get("doc_count_error_upper_bound"):
        reasons.append(f"doc_count_error_upper_bound={node['doc_count_error_upper_bound']}")
    return reasons


def response_warnings(body: bytes, meta: ResponseMeta) -> list[str]:
    """Extract API warnings (e.g. unrecognized fields) without full parsing."""
    if meta.completeness != "COMPLETE":
        return [f"incomplete response: {meta.completeness}"]
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ["unparseable response for warnings"]
    if not isinstance(document, dict):
        return ["unparseable response for warnings"]
    return _warnings(document)


def parse_status(body: bytes, meta: ResponseMeta) -> ParsedStatus:
    document = _load_json(body, meta)
    return ParsedStatus(
        commit=_optional(document, "commit", (str,), "status"),
        data_release=_optional(document, "data_release", (str,), "status"),
        tag=_optional(document, "tag", (str,), "status"),
        status=_optional(document, "status", (str,), "status"),
        warnings=_warnings(document),
    )


def parse_projects(body: bytes, meta: ResponseMeta) -> list[ProjectRecord]:
    document = _load_json(body, meta)
    records: list[ProjectRecord] = []
    seen: set[str] = set()
    for hit in _hits(document, "projects"):
        project_id = _require(hit, "project_id", (str,), "projects")
        if project_id in seen:
            raise ParserError("DUPLICATE_ID", f"projects: duplicate {project_id}")
        seen.add(project_id)
        records.append(ProjectRecord(
            project_id=project_id,
            name=_optional(hit, "name", (str,), "projects"),
            program_name=_optional(hit, "program.name", (str,), "projects"),
            primary_site=_string_list(hit, "primary_site", "projects"),
            disease_type=_string_list(hit, "disease_type", "projects"),
            case_count=_optional(hit, "summary.case_count", (int,), "projects"),
            file_count=_optional(hit, "summary.file_count", (int,), "projects"),
            data_categories=_nested_string_list(hit, "summary.data_categories", "data_category", "projects"),
        ))
    return records


def parse_cases(body: bytes, meta: ResponseMeta) -> CasesPage:
    document = _load_json(body, meta)
    records: list[CaseRecord] = []
    seen: set[str] = set()
    for hit in _hits(document, "cases"):
        case_id = _require(hit, "case_id", (str,), "cases")
        if case_id in seen:
            raise ParserError("DUPLICATE_ID", f"cases: duplicate {case_id}")
        seen.add(case_id)
        samples = _optional(hit, "samples", (list,), "cases") or []
        sample_types: list[str] = []
        for sample in samples:
            if not isinstance(sample, dict):
                raise ParserError("MALFORMED_JSON", "cases: sample is not an object")
            sample_type = _optional(sample, "sample_type", (str,), "cases")
            if sample_type:
                sample_types.append(sample_type)
        records.append(CaseRecord(
            case_id=case_id,
            submitter_id=_optional(hit, "submitter_id", (str,), "cases"),
            project_id=_require(hit, "project.project_id", (str,), "cases"),
            sample_types=sample_types,
        ))
    pagination = _optional(document, "data.pagination", (dict,), "cases") or {}
    pagination_values: dict[str, int | None] = {}
    for name in ("total", "count", "size", "from", "pages"):
        value = pagination.get(name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ParserError("INVALID_PAGINATION", f"cases: pagination {name} must be an integer")
        pagination_values[name] = value
    total = pagination_values["total"]
    count = pagination_values["count"]
    size = pagination_values["size"]
    offset = pagination_values["from"]
    pages = pagination_values["pages"]
    for name, value in (("total", total), ("count", count), ("from", offset), ("pages", pages)):
        if value is not None and value < 0:
            raise ParserError("INVALID_PAGINATION", f"cases: pagination {name} must be non-negative")
    if size is not None and size < 1:
        raise ParserError("INVALID_PAGINATION", "cases: pagination size must be positive")
    effective_count = count if count is not None else len(records)
    complete = bool(
        total is not None and effective_count == total and (offset or 0) == 0 and (pages or 1) <= 1
    )
    return CasesPage(cases=records, total=total, count=effective_count, size=size, offset=offset,
                     pages=pages, complete=complete, warnings=_warnings(document))


def parse_genes(body: bytes, meta: ResponseMeta) -> list[GeneRecord]:
    document = _load_json(body, meta)
    records: list[GeneRecord] = []
    seen: set[str] = set()
    for hit in _hits(document, "genes"):
        gene_id = _require(hit, "gene_id", (str,), "genes")
        if gene_id in seen:
            raise ParserError("DUPLICATE_ID", f"genes: duplicate {gene_id}")
        seen.add(gene_id)
        records.append(GeneRecord(
            gene_id=gene_id,
            symbol=_require(hit, "symbol", (str,), "genes"),
            name=_optional(hit, "name", (str,), "genes"),
            biotype=_optional(hit, "biotype", (str,), "genes"),
            is_cancer_gene_census=_optional(hit, "is_cancer_gene_census", (bool,), "genes"),
        ))
    return records


def parse_top_mutated_genes(body: bytes, meta: ResponseMeta) -> list[DiscoveryHit]:
    document = _load_json(body, meta)
    hits: list[DiscoveryHit] = []
    seen: set[str] = set()
    for rank, hit in enumerate(_hits(document, "discovery"), start=1):
        gene_id = _require(hit, "gene_id", (str,), "discovery")
        if gene_id in seen:
            raise ParserError("DUPLICATE_ID", f"discovery: duplicate {gene_id}")
        seen.add(gene_id)
        hits.append(DiscoveryHit(
            gene_id=gene_id,
            symbol=_optional(hit, "symbol", (str,), "discovery"),
            rank=rank,
            score=_finite(hit.get("_score"), "discovery score"),
        ))
    return hits


def parse_gene_case_counts(body: bytes, meta: ResponseMeta) -> GeneCaseCounts:
    document = _load_json(body, meta)
    reasons = _aggregation_completeness(document, "counts")
    projects: dict[str, dict[str, int]] = {}
    buckets = _optional(document, "aggregations.projects.buckets", (list,), "counts")
    if buckets is None:
        raise ParserError("MISSING_FIELD", "counts: missing aggregations.projects.buckets")
    for bucket in buckets:
        if not isinstance(bucket, dict):
            raise ParserError("MALFORMED_JSON", "counts: bucket is not an object")
        project_id = _require(bucket, "key", (str,), "counts")
        if project_id in projects:
            raise ParserError("DUPLICATE_ID", f"counts: duplicate project bucket {project_id}")
        gene_buckets = _optional(bucket, "genes.my_genes.gene_id.buckets", (list,), "counts")
        if gene_buckets is None:
            raise ParserError("MISSING_FIELD", f"counts: missing gene buckets for {project_id}")
        counts: dict[str, int] = {}
        for gene_bucket in gene_buckets:
            if not isinstance(gene_bucket, dict):
                raise ParserError("MALFORMED_JSON", "counts: gene bucket is not an object")
            gene_id = _require(gene_bucket, "key", (str,), "counts")
            doc_count = _require(gene_bucket, "doc_count", (int,), "counts")
            if gene_id in counts:
                raise ParserError("DUPLICATE_ID", f"counts: duplicate gene bucket {project_id}/{gene_id}")
            counts[gene_id] = doc_count
        projects[project_id] = counts
    hits_total = _optional(document, "hits.total.value", (int,), "counts")
    return GeneCaseCounts(projects=projects, hits_total=hits_total, complete=not reasons,
                          partial_reasons=reasons, warnings=_warnings(document))


def parse_mutated_cases_count(body: bytes, meta: ResponseMeta) -> ProjectCoverage:
    document = _load_json(body, meta)
    reasons = _aggregation_completeness(document, "coverage")
    buckets = _optional(document, "aggregations.projects.buckets", (list,), "coverage")
    if buckets is None:
        raise ParserError("MISSING_FIELD", "coverage: missing aggregations.projects.buckets")
    coverage: dict[str, int] = {}
    for bucket in buckets:
        if not isinstance(bucket, dict):
            raise ParserError("MALFORMED_JSON", "coverage: bucket is not an object")
        project_id = _require(bucket, "key", (str,), "coverage")
        if project_id in coverage:
            raise ParserError("DUPLICATE_ID", f"coverage: duplicate project bucket {project_id}")
        coverage[project_id] = _require(bucket, "case_summary.case_with_ssm.doc_count", (int,), "coverage")
    return ProjectCoverage(case_with_ssm=coverage, complete=not reasons,
                           partial_reasons=reasons, warnings=_warnings(document))


def parse_expression_availability(body: bytes, meta: ResponseMeta, *, expected_cases: list[str],
                                  expected_genes: list[str]) -> ExpressionAvailability:
    document = _load_json(body, meta)
    expected_case_set = set(expected_cases)
    expected_gene_set = set(expected_genes)
    cases: dict[str, bool] = {}
    for detail in _require(document, "cases.details", (list,), "availability"):
        if not isinstance(detail, dict):
            raise ParserError("MALFORMED_JSON", "availability: case detail is not an object")
        case_id = _require(detail, "case_id", (str,), "availability")
        if case_id not in expected_case_set:
            raise ParserError("UNEXPECTED_IDENTIFIER", f"availability: unrequested case {case_id}")
        if case_id in cases:
            raise ParserError("DUPLICATE_ID", f"availability: duplicate case {case_id}")
        cases[case_id] = bool(_require(detail, "has_gene_expression_values", (bool,), "availability"))
    genes: dict[str, bool] = {}
    for detail in _require(document, "genes.details", (list,), "availability"):
        if not isinstance(detail, dict):
            raise ParserError("MALFORMED_JSON", "availability: gene detail is not an object")
        gene_id = _require(detail, "gene_id", (str,), "availability")
        if gene_id not in expected_gene_set:
            raise ParserError("UNEXPECTED_IDENTIFIER", f"availability: unrequested gene {gene_id}")
        if gene_id in genes:
            raise ParserError("DUPLICATE_ID", f"availability: duplicate gene {gene_id}")
        genes[gene_id] = bool(_require(detail, "has_gene_expression_values", (bool,), "availability"))
    return ExpressionAvailability(
        cases=cases, genes=genes,
        with_count=_optional(document, "cases.with_gene_expression_count", (int,), "availability"),
        without_count=_optional(document, "cases.without_gene_expression_count", (int,), "availability"),
        missing_cases=[case_id for case_id in expected_cases if case_id not in cases],
        missing_genes=[gene_id for gene_id in expected_genes if gene_id not in genes],
        warnings=_warnings(document),
    )


def parse_gene_selection(body: bytes, meta: ResponseMeta, *, expected_genes: list[str]) -> ProviderSelection:
    document = _load_json(body, meta)
    expected_gene_set = set(expected_genes)
    genes: dict[str, ProviderGene] = {}
    for item in _require(document, "gene_selection", (list,), "gene_selection"):
        if not isinstance(item, dict):
            raise ParserError("MALFORMED_JSON", "gene_selection: entry is not an object")
        gene_id = _require(item, "gene_id", (str,), "gene_selection")
        if gene_id not in expected_gene_set:
            raise ParserError("UNEXPECTED_IDENTIFIER", f"gene_selection: unrequested gene {gene_id}")
        if gene_id in genes:
            raise ParserError("DUPLICATE_ID", f"gene_selection: duplicate {gene_id}")
        genes[gene_id] = ProviderGene(
            gene_id=gene_id,
            symbol=_optional(item, "symbol", (str,), "gene_selection"),
            median=_finite(item.get("log2_uqfpkm_median"), "gene_selection median"),
            stddev=_finite(item.get("log2_uqfpkm_stddev"), "gene_selection stddev"),
        )
    return ProviderSelection(
        genes=genes,
        missing_genes=[gene_id for gene_id in expected_genes if gene_id not in genes],
        warnings=_warnings(document),
    )


def parse_expression_values(body: bytes, meta: ResponseMeta, *, expected_cases: list[str],
                            expected_genes: list[str]) -> ExpressionValues:
    if meta.completeness != "COMPLETE":
        raise ParserError("INCOMPLETE_RESPONSE", f"{meta.endpoint} completeness={meta.completeness}")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserError("MALFORMED_TSV", str(exc)) from exc
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ParserError("MALFORMED_TSV", "empty TSV")
    header = lines[0].split("\t")
    if not header or header[0] != "gene_id":
        raise ParserError("MALFORMED_TSV", "first column is not gene_id")
    case_columns = header[1:]
    if len(set(case_columns)) != len(case_columns):
        raise ParserError("DUPLICATE_ID", "TSV has duplicate case columns")
    unexpected_cases = [case_id for case_id in case_columns if case_id not in set(expected_cases)]
    if unexpected_cases:
        raise ParserError("UNEXPECTED_IDENTIFIER", f"TSV contains unrequested case columns: {unexpected_cases[:3]}")
    values: dict[str, dict[str, float | None]] = {}
    nonfinite = 0
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ParserError("MALFORMED_TSV", f"row width {len(cells)} != header width {len(header)}")
        gene_id = cells[0]
        if not gene_id:
            raise ParserError("MALFORMED_TSV", "empty gene id")
        if gene_id in values:
            raise ParserError("DUPLICATE_ID", f"TSV duplicate gene row {gene_id}")
        if gene_id not in set(expected_genes):
            raise ParserError("UNEXPECTED_IDENTIFIER", f"TSV contains unrequested gene row {gene_id}")
        row: dict[str, float | None] = {}
        for case_id, cell in zip(case_columns, cells[1:], strict=True):
            cell = cell.strip()
            if cell == "":
                row[case_id] = None
                continue
            try:
                number = float(cell)
            except ValueError as exc:
                raise ParserError("MALFORMED_TSV", f"non-numeric cell for {gene_id}/{case_id}") from exc
            if not math.isfinite(number):
                nonfinite += 1
                row[case_id] = None
            else:
                row[case_id] = number
        values[gene_id] = row
    return ExpressionValues(
        values=values,
        missing_case_ids=[case_id for case_id in expected_cases if case_id not in case_columns],
        missing_gene_ids=[gene_id for gene_id in expected_genes if gene_id not in values],
        nonfinite_values=nonfinite,
        warnings=[],
    )


def parse_files_provenance(body: bytes, meta: ResponseMeta) -> FilesProvenance:
    document = _load_json(body, meta)
    workflows: list[str] = []
    strategies: list[str] = []
    non_open = 0
    hits = _hits(document, "files")
    for hit in hits:
        access = _optional(hit, "access", (str,), "files")
        if access is not None and access != "open":
            non_open += 1
        workflow = _optional(hit, "analysis.workflow_type", (str,), "files")
        if workflow and workflow not in workflows:
            workflows.append(workflow)
        strategy = _optional(hit, "experimental_strategy", (str,), "files")
        if strategy and strategy not in strategies:
            strategies.append(strategy)
    return FilesProvenance(workflows=sorted(workflows), strategies=sorted(strategies),
                           files_seen=len(hits), non_open_records=non_open, warnings=_warnings(document))
