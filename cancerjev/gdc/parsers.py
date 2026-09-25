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
from typing import Any, cast

PARSER_VERSION = "gdc-parser-v1"
GENES_UNIVERSE_BIOTYPE = "protein_coding"


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
class GenesPage:
    """One strictly validated universe-enumeration page of /genes."""

    genes: list[GeneRecord]
    total: int
    count: int
    size: int
    offset: int
    pages: int | None
    warnings: list[str]


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
class CanonicalConsequenceRow:
    """One canonical-transcript consequence row; missing terms stay NOT_OBSERVED."""

    gene_id: str
    transcript_id: str | None
    consequence: str | None
    protein_start: int | None


@dataclass(frozen=True)
class SsmOccurrenceRecord:
    occurrence_id: str
    case_id: str
    gene_ids: tuple[str, ...]
    canonical_rows: tuple[CanonicalConsequenceRow, ...] = ()


@dataclass(frozen=True)
class SsmOccurrencePage:
    records: tuple[SsmOccurrenceRecord, ...]
    total: int
    count: int
    size: int
    offset: int
    pages: int
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


@dataclass(frozen=True)
class CnvOccurrenceRecord:
    occurrence_id: str
    cnv_id: str
    case_id: str
    gene_id: str
    raw_change: str
    raw_category: str
    source_file_id: str | None
    caller: str | None
    sample_id: str | None
    copy_number: float | None


@dataclass(frozen=True)
class CnvOccurrencesPage:
    occurrences: tuple[CnvOccurrenceRecord, ...]
    total: int
    count: int
    size: int
    offset: int
    pages: int
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


def _nonnegative_count(value: Any, context: str) -> int:
    """A provider count is a non-negative integer; an impossible count fails closed."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ParserError("INVALID_COUNT", f"{context}: count must be a non-negative integer")
    return value


def _optional_count(document: dict[str, Any], path: str, context: str) -> int | None:
    value = _optional(document, path, (int,), context)
    if value is None:
        return None
    return _nonnegative_count(value, f"{context}: {path}")


def _required_count(document: dict[str, Any], path: str, context: str) -> int:
    return _nonnegative_count(_require(document, path, (int,), context), f"{context}: {path}")


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
    return cast(list[dict[str, Any]], hits)


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


def _nested_aggregation_reasons(node: Any, context: str) -> list[str]:
    """Completeness flags on a nested terms aggregation node, prefixed by path.

    Root callers keep bare reasons for continuity; nested nodes must be inspected
    because a terms aggregation can omit or approximate buckets even when the
    response root reports no truncation (fail-closed toward PARTIAL).
    """
    if not isinstance(node, dict):
        return []
    return [f"{context}:{reason}" for reason in _aggregation_completeness(node, context)]


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
            case_count=_optional_count(hit, "summary.case_count", "projects"),
            file_count=_optional_count(hit, "summary.file_count", "projects"),
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


def parse_genes_page(body: bytes, meta: ResponseMeta, *, expected_offset: int,
                     expected_size: int) -> GenesPage:
    """Strict universe-enumeration page reader; malformed provider output fails closed.

    Validated here: pagination scalar types and non-negative totals/offsets,
    count/record consistency, unique identifiers, valid Ensembl gene IDs,
    protein_coding membership and provider gene_id-ascending ordering within the
    page. Cross-page continuity is the acquisition caller's contract.
    """
    document = _load_json(body, meta)
    records: list[GeneRecord] = []
    seen: set[str] = set()
    previous_id: str | None = None
    for hit in _hits(document, "genes"):
        gene_id = _require(hit, "gene_id", (str,), "genes")
        if not (gene_id.startswith("ENSG") and len(gene_id) == 15
                and gene_id[4:].isascii() and gene_id[4:].isdigit()):
            raise ParserError("INVALID_FIELD", f"genes: invalid Ensembl gene id {gene_id!r}")
        if gene_id in seen:
            raise ParserError("DUPLICATE_ID", f"genes: duplicate {gene_id}")
        if previous_id is not None and gene_id <= previous_id:
            raise ParserError("UNEXPECTED_ORDER", f"genes: {gene_id} does not ascend after {previous_id}")
        previous_id = gene_id
        seen.add(gene_id)
        biotype = _require(hit, "biotype", (str,), "genes")
        if biotype != GENES_UNIVERSE_BIOTYPE:
            raise ParserError("UNEXPECTED_BIOTYPE", f"genes: {gene_id} biotype {biotype!r} "
                                                    f"is not {GENES_UNIVERSE_BIOTYPE!r}")
        records.append(GeneRecord(
            gene_id=gene_id,
            symbol=_require(hit, "symbol", (str,), "genes"),
            name=None,
            biotype=biotype,
            is_cancer_gene_census=None,
        ))
    pagination = _optional(document, "data.pagination", (dict,), "genes") or {}
    values: dict[str, int | None] = {}
    for name in ("total", "count", "size", "from", "pages"):
        value = pagination.get(name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ParserError("INVALID_PAGINATION", f"genes: pagination {name} must be an integer")
        values[name] = value
    total = values["total"]
    count = values["count"]
    size = values["size"]
    offset = values["from"]
    if total is None or count is None or offset is None:
        raise ParserError("MISSING_FIELD", "genes: pagination total, count and from are required")
    for name, value in (("total", total), ("count", count), ("from", offset), ("size", size),
                        ("pages", values["pages"])):
        if value is not None and value < 0:
            raise ParserError("INVALID_PAGINATION", f"genes: pagination {name} must be non-negative")
    if size is not None and size < 1:
        raise ParserError("INVALID_PAGINATION", "genes: pagination size must be positive")
    if count != len(records):
        raise ParserError("INVALID_PAGINATION",
                          f"genes: pagination count {count} differs from {len(records)} records")
    if offset != expected_offset:
        raise ParserError("INVALID_PAGINATION",
                          f"genes: provider offset {offset} differs from requested {expected_offset}")
    if count > expected_size:
        raise ParserError("INVALID_PAGINATION",
                          f"genes: page returned {count} records, above requested size {expected_size}")
    if size is not None and size != expected_size and count == expected_size:
        raise ParserError("INVALID_PAGINATION",
                          f"genes: provider size {size} differs from requested {expected_size}")
    return GenesPage(genes=records, total=total, count=count, size=expected_size,
                     offset=offset, pages=values["pages"], warnings=_warnings(document))


def parse_cnv_occurrences_page(
    body: bytes,
    meta: ResponseMeta,
    *,
    expected_project: str,
    expected_gene: str,
    expected_cases: set[str],
    expected_offset: int,
    expected_size: int,
) -> CnvOccurrencesPage:
    """Strict one-gene CNV occurrence page with exact filter membership."""
    document = _load_json(body, meta)
    occurrences: list[CnvOccurrenceRecord] = []
    seen: set[str] = set()
    previous_id: str | None = None
    for hit in _hits(document, "cnv_occurrences"):
        occurrence_id = _require(hit, "cnv_occurrence_id", (str,), "cnv_occurrences")
        if occurrence_id in seen:
            raise ParserError("DUPLICATE_ID", f"cnv_occurrences: duplicate {occurrence_id}")
        if previous_id is not None and occurrence_id <= previous_id:
            raise ParserError(
                "UNEXPECTED_ORDER",
                f"cnv_occurrences: {occurrence_id} does not ascend after {previous_id}",
            )
        previous_id = occurrence_id
        seen.add(occurrence_id)
        project_id = _require(hit, "case.project.project_id", (str,), "cnv_occurrences")
        case_id = _require(hit, "case.case_id", (str,), "cnv_occurrences")
        if project_id != expected_project:
            raise ParserError("UNEXPECTED_IDENTIFIER",
                              f"cnv_occurrences: unrequested project {project_id}")
        if case_id not in expected_cases:
            raise ParserError("UNEXPECTED_IDENTIFIER",
                              f"cnv_occurrences: case {case_id} outside Stage 4 frame")
        consequences = _require(hit, "cnv.consequence", (list,), "cnv_occurrences")
        gene_ids: list[str] = []
        for consequence in consequences:
            if not isinstance(consequence, dict):
                raise ParserError("MALFORMED_JSON",
                                  "cnv_occurrences: consequence is not an object")
            gene_id = _optional(consequence, "gene.gene_id", (str,), "cnv_occurrences")
            if gene_id is not None:
                gene_ids.append(gene_id)
        if expected_gene not in gene_ids:
            raise ParserError("UNEXPECTED_IDENTIFIER",
                              f"cnv_occurrences: occurrence excludes requested gene {expected_gene}")
        observations = _optional(hit, "case.observation", (list,), "cnv_occurrences") or []
        if len(observations) > 1:
            raise ParserError("AMBIGUOUS_OBSERVATION",
                              f"cnv_occurrences: {occurrence_id} has multiple observations")
        observation: dict[str, Any]
        if observations:
            if not isinstance(observations[0], dict):
                raise ParserError("MALFORMED_JSON",
                                  "cnv_occurrences: observation is not an object")
            observation = observations[0]
        else:
            observation = {}
        occurrences.append(CnvOccurrenceRecord(
            occurrence_id=occurrence_id,
            cnv_id=_require(hit, "cnv.cnv_id", (str,), "cnv_occurrences"),
            case_id=case_id,
            gene_id=expected_gene,
            raw_change=_require(hit, "cnv.cnv_change", (str,), "cnv_occurrences"),
            raw_category=_require(
                hit, "cnv.cnv_change_5_category", (str,), "cnv_occurrences"),
            source_file_id=_optional(observation, "src_file_id", (str,), "cnv_occurrences"),
            caller=_optional(
                observation, "variant_calling.variant_caller", (str,), "cnv_occurrences"),
            sample_id=_optional(
                observation, "sample.tumor_sample_uuid", (str,), "cnv_occurrences"),
            copy_number=_finite(observation.get("copy_number"), "cnv_occurrences copy_number"),
        ))
    pagination = _require(document, "data.pagination", (dict,), "cnv_occurrences")
    values: dict[str, int] = {}
    for name in ("total", "count", "size", "from", "pages"):
        value = pagination.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ParserError("INVALID_PAGINATION",
                              f"cnv_occurrences: pagination {name} must be non-negative integer")
        values[name] = value
    if values["size"] < 1:
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: size must be positive")
    if values["count"] != len(occurrences):
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: count/records mismatch")
    if values["from"] != expected_offset:
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: offset mismatch")
    if values["size"] != expected_size:
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: size mismatch")
    expected_pages = math.ceil(values["total"] / expected_size) if values["total"] else 0
    if values["pages"] != expected_pages:
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: pages/total mismatch")
    if expected_offset + values["count"] > values["total"]:
        raise ParserError("INVALID_PAGINATION", "cnv_occurrences: page exceeds total")
    if expected_offset + values["count"] < values["total"] \
            and values["count"] != expected_size:
        raise ParserError("INVALID_PAGINATION",
                          "cnv_occurrences: short page before reported total")
    return CnvOccurrencesPage(
        tuple(occurrences), values["total"], values["count"], values["size"],
        values["from"], values["pages"], _warnings(document),
    )


def parse_ssm_occurrence_page(
    body: bytes,
    meta: ResponseMeta,
    *,
    expected_project: str,
    expected_offset: int,
    expected_size: int,
) -> SsmOccurrencePage:
    """Strict one-page slice of the project's released occurrence records.

    Every record must carry a unique ascending ``ssm_occurrence_id``, a
    non-empty ``case.case_id`` inside the requested project, and an optional
    consequence-annotated gene list (a record without any gene annotation is
    kept and contributes to no gene). Pagination invariants are exact; a short
    page before the reported total is an error, never a stop condition.
    """
    document = _load_json(body, meta)
    records: list[SsmOccurrenceRecord] = []
    seen: set[str] = set()
    previous_id: str | None = None
    for hit in _hits(document, "ssm_occurrences"):
        occurrence_id = _require(hit, "ssm_occurrence_id", (str,), "ssm_occurrences")
        if occurrence_id in seen:
            raise ParserError("DUPLICATE_ID", f"ssm_occurrences: duplicate {occurrence_id}")
        if previous_id is not None and occurrence_id <= previous_id:
            raise ParserError(
                "UNEXPECTED_ORDER",
                f"ssm_occurrences: {occurrence_id} does not ascend after {previous_id}",
            )
        previous_id = occurrence_id
        seen.add(occurrence_id)
        project_id = _require(hit, "case.project.project_id", (str,), "ssm_occurrences")
        case_id = _require(hit, "case.case_id", (str,), "ssm_occurrences")
        if project_id != expected_project:
            raise ParserError("UNEXPECTED_IDENTIFIER",
                              f"ssm_occurrences: unrequested project {project_id}")
        consequences = _optional(hit, "ssm.consequence", (list,), "ssm_occurrences") or []
        gene_ids: set[str] = set()
        canonical_rows: list[CanonicalConsequenceRow] = []
        for consequence in consequences:
            if not isinstance(consequence, dict):
                raise ParserError("MALFORMED_JSON", "ssm_occurrences: consequence is not an object")
            gene_id = _optional(consequence, "transcript.gene.gene_id", (str,), "ssm_occurrences")
            if not gene_id:
                continue
            gene_ids.add(gene_id)
            is_canonical = _optional(consequence, "transcript.is_canonical", (bool,),
                                     "ssm_occurrences")
            if is_canonical is not True:
                continue
            transcript_id = _optional(consequence, "transcript.transcript_id", (str,),
                                      "ssm_occurrences")
            raw_consequence = _optional(consequence, "transcript.consequence_type", (str, list),
                                        "ssm_occurrences")
            if raw_consequence is None:
                terms: tuple[str | None, ...] = (None,)
            elif isinstance(raw_consequence, str):
                terms = (raw_consequence or None,)
            else:
                parsed: list[str | None] = []
                for item in raw_consequence:
                    if not isinstance(item, str):
                        raise ParserError("INVALID_FIELD",
                                          "ssm_occurrences: consequence term must be text")
                    if item:
                        parsed.append(item)
                terms = tuple(parsed) or (None,)
            transcript_node = consequence.get("transcript")
            raw_protein_start = (transcript_node.get("protein_start")
                                 if isinstance(transcript_node, dict) else None)
            if isinstance(raw_protein_start, bool):
                raise ParserError("INVALID_FIELD",
                                  "ssm_occurrences: protein_start must be an integer")
            protein_start = _optional(consequence, "transcript.protein_start", (int,),
                                      "ssm_occurrences")
            for term in terms:
                canonical_rows.append(CanonicalConsequenceRow(
                    gene_id=gene_id, transcript_id=transcript_id, consequence=term,
                    protein_start=protein_start,
                ))
        records.append(SsmOccurrenceRecord(
            occurrence_id=occurrence_id, case_id=case_id, gene_ids=tuple(sorted(gene_ids)),
            canonical_rows=tuple(canonical_rows),
        ))
    pagination = _require(document, "data.pagination", (dict,), "ssm_occurrences")
    values: dict[str, int] = {}
    for name in ("total", "count", "size", "from", "pages"):
        value = pagination.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ParserError("INVALID_PAGINATION",
                              f"ssm_occurrences: pagination {name} must be non-negative integer")
        values[name] = value
    if values["size"] < 1:
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: size must be positive")
    if values["count"] != len(records):
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: count/records mismatch")
    if values["from"] != expected_offset:
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: offset mismatch")
    if values["size"] != expected_size:
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: size mismatch")
    expected_pages = math.ceil(values["total"] / expected_size) if values["total"] else 0
    if values["pages"] != expected_pages:
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: pages/total mismatch")
    if expected_offset + values["count"] > values["total"]:
        raise ParserError("INVALID_PAGINATION", "ssm_occurrences: page exceeds total")
    if expected_offset + values["count"] < values["total"] \
            and values["count"] != expected_size:
        raise ParserError("INVALID_PAGINATION",
                          "ssm_occurrences: short page before reported total")
    return SsmOccurrencePage(
        tuple(records), values["total"], values["count"], values["size"],
        values["from"], values["pages"], _warnings(document),
    )


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
    projects_node = _optional(document, "aggregations.projects", (dict,), "counts")
    reasons += _nested_aggregation_reasons(projects_node, "aggregations.projects")
    projects: dict[str, dict[str, int]] = {}
    buckets = _optional(document, "aggregations.projects.buckets", (list,), "counts")
    if buckets is None:
        raise ParserError("MISSING_FIELD", "counts: missing aggregations.projects.buckets")
    for bucket in buckets:
        if not isinstance(bucket, dict):
            raise ParserError("MALFORMED_JSON", "counts: bucket is not an object")
        project_id = _require(bucket, "key", (str,), "counts")
        reasons += _nested_aggregation_reasons(bucket, f"counts.project[{project_id}]")
        if project_id in projects:
            raise ParserError("DUPLICATE_ID", f"counts: duplicate project bucket {project_id}")
        gene_terms = _optional(bucket, "genes.my_genes.gene_id", (dict,), "counts")
        reasons += _nested_aggregation_reasons(gene_terms, f"counts.project[{project_id}].genes")
        gene_buckets = _optional(bucket, "genes.my_genes.gene_id.buckets", (list,), "counts")
        if gene_buckets is None:
            raise ParserError("MISSING_FIELD", f"counts: missing gene buckets for {project_id}")
        counts: dict[str, int] = {}
        for gene_bucket in gene_buckets:
            if not isinstance(gene_bucket, dict):
                raise ParserError("MALFORMED_JSON", "counts: gene bucket is not an object")
            gene_id = _require(gene_bucket, "key", (str,), "counts")
            reasons += _nested_aggregation_reasons(gene_bucket, f"counts.project[{project_id}].gene[{gene_id}]")
            doc_count = _required_count(gene_bucket, "doc_count", "counts")
            if gene_id in counts:
                raise ParserError("DUPLICATE_ID", f"counts: duplicate gene bucket {project_id}/{gene_id}")
            counts[gene_id] = doc_count
        projects[project_id] = counts
    hits_total = _optional_count(document, "hits.total.value", "counts")
    return GeneCaseCounts(projects=projects, hits_total=hits_total, complete=not reasons,
                          partial_reasons=reasons, warnings=_warnings(document))


def parse_mutated_cases_count(body: bytes, meta: ResponseMeta) -> ProjectCoverage:
    document = _load_json(body, meta)
    reasons = _aggregation_completeness(document, "coverage")
    projects_node = _optional(document, "aggregations.projects", (dict,), "coverage")
    reasons += _nested_aggregation_reasons(projects_node, "aggregations.projects")
    buckets = _optional(document, "aggregations.projects.buckets", (list,), "coverage")
    if buckets is None:
        raise ParserError("MISSING_FIELD", "coverage: missing aggregations.projects.buckets")
    coverage: dict[str, int] = {}
    for bucket in buckets:
        if not isinstance(bucket, dict):
            raise ParserError("MALFORMED_JSON", "coverage: bucket is not an object")
        project_id = _require(bucket, "key", (str,), "coverage")
        reasons += _nested_aggregation_reasons(bucket, f"coverage.project[{project_id}]")
        reasons += _nested_aggregation_reasons(
            bucket.get("case_summary", {}).get("case_with_ssm") if isinstance(bucket.get("case_summary"), dict) else None,
            f"coverage.project[{project_id}].case_with_ssm",
        )
        if project_id in coverage:
            raise ParserError("DUPLICATE_ID", f"coverage: duplicate project bucket {project_id}")
        coverage[project_id] = _required_count(
            bucket, "case_summary.case_with_ssm.doc_count", "coverage",
        )
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
        with_count=_optional_count(document, "cases.with_gene_expression_count", "availability"),
        without_count=_optional_count(document, "cases.without_gene_expression_count", "availability"),
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
    if text.startswith("\ufeff"):
        text = text[1:]
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
        if access != "open":
            non_open += 1
        workflow = _optional(hit, "analysis.workflow_type", (str,), "files")
        if workflow and workflow not in workflows:
            workflows.append(workflow)
        strategy = _optional(hit, "experimental_strategy", (str,), "files")
        if strategy and strategy not in strategies:
            strategies.append(strategy)
    return FilesProvenance(workflows=sorted(workflows), strategies=sorted(strategies),
                           files_seen=len(hits), non_open_records=non_open, warnings=_warnings(document))


FACET_NAMES = ("experimental_strategy", "analysis.workflow_type", "data_type")


@dataclass(frozen=True)
class FileFacets:
    """Provider aggregate counts for one bounded open-file facet request."""

    total_open_files: int | None
    counts: dict[str, dict[str, int]]
    warnings: list[str]

    def facet(self, name: str) -> dict[str, int]:
        return dict(self.counts.get(name, {}))


def parse_file_facets(body: bytes, meta: ResponseMeta) -> FileFacets:
    """Strict aggregate parse of a bounded ``/files`` facet response.

    Only provider aggregate counts are read; the response is rejected when a
    requested facet is missing, malformed, duplicated or carries a negative or
    non-integer count. No file-level record is parsed or retained here.
    """
    document = _load_json(body, meta)
    data = document.get("data")
    if not isinstance(data, dict):
        raise ParserError("MISSING_FIELD", "files: data object is missing")
    aggregations = data.get("aggregations")
    if not isinstance(aggregations, dict):
        raise ParserError("MISSING_FIELD", "files: aggregations object is missing")
    counts: dict[str, dict[str, int]] = {}
    for name, facet in aggregations.items():
        if not isinstance(name, str) or not name:
            raise ParserError("INVALID_FACET", "files: facet name is invalid")
        if not isinstance(facet, dict) or not isinstance(facet.get("buckets"), list):
            raise ParserError("INVALID_FACET", f"files: facet {name} is missing or malformed")
        buckets: dict[str, int] = {}
        for bucket in facet["buckets"]:
            if not isinstance(bucket, dict):
                raise ParserError("INVALID_FACET", f"files: facet {name} bucket is malformed")
            key = bucket.get("key")
            count = bucket.get("doc_count")
            if not isinstance(key, str) or not key:
                raise ParserError("INVALID_FACET", f"files: facet {name} bucket key is invalid")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ParserError("INVALID_FACET", f"files: facet {name}/{key} has a non-integer count")
            if key in buckets:
                raise ParserError("DUPLICATE_ID", f"files: facet {name} repeats {key}")
            buckets[key] = count
        counts[name] = buckets
    for name in FACET_NAMES:
        if name not in counts:
            raise ParserError("INVALID_FACET", f"files: facet {name} is missing or malformed")
    pagination = data.get("pagination")
    total = pagination.get("total") if isinstance(pagination, dict) else None
    if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
        raise ParserError("INVALID_FACET", "files: pagination total is not a count")
    return FileFacets(total_open_files=total, counts=counts, warnings=_warnings(document))
