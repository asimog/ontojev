"""GDC endpoint allowlist and validated request builders.

The allowlist is the complete set of GDC paths OntoJev may ever request. Builders
enforce per-endpoint parameter rules and application ID/size caps. Nothing here
knows about credentials; authentication is impossible by construction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.events import canonical_json

MAX_CASE_IDS = 250
MAX_GENE_IDS = 100
MAX_GENE_PAGE = 100
MAX_CASES_PAGE = 250
MAX_FILES_PAGE = 5
MAX_PROJECTS_PAGE = 100
MAX_DISCOVERY_HITS = 20
MAX_CNV_OCCURRENCES_PAGE = 250
CNV_OCCURRENCE_FIELDS = (
    "cnv_occurrence_id", "case.case_id", "case.project.project_id",
    "case.observation.copy_number", "case.observation.sample.tumor_sample_uuid",
    "case.observation.src_file_id",
    "case.observation.variant_calling.variant_caller", "cnv.cnv_id",
    "cnv.cnv_change", "cnv.cnv_change_5_category",
    "cnv.consequence.gene.gene_id",
)
MAX_SSM_OCCURRENCES_PAGE = 10000

GENES_UNIVERSE_BIOTYPE = "protein_coding"
GENES_UNIVERSE_SORT = "gene_id:asc"

GENE_CASE_COUNTS_FIELDS_NOTE = "endpoint rejects fields/format parameters"

SSM_OCCURRENCE_FIELDS = (
    "ssm_occurrence_id",
    "case.case_id",
    "case.project.project_id",
    "ssm.consequence.transcript.gene.gene_id",
    "ssm.consequence.transcript.consequence_type",
    "ssm.consequence.transcript.is_canonical",
    "ssm.consequence.transcript.transcript_id",
)


class EndpointError(Exception):
    """Raised when a request would leave the allowlisted GDC surface."""


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    method: str
    path: str
    retryable: bool = False
    runtime: bool = True


_ENDPOINT_LIST = (
    EndpointSpec("status", "GET", "/status", retryable=True),
    EndpointSpec("projects", "GET", "/projects", retryable=True),
    EndpointSpec("cases", "GET", "/cases", retryable=True),
    EndpointSpec("files", "GET", "/files", retryable=True),
    EndpointSpec("genes", "GET", "/genes", retryable=True),
    EndpointSpec(
        "top_mutated_genes_by_project", "GET", "/analysis/top_mutated_genes_by_project",
        retryable=True,
    ),
    EndpointSpec(
        "top_cases_counts_by_genes", "GET", "/analysis/top_cases_counts_by_genes",
        retryable=True,
    ),
    EndpointSpec(
        "mutated_cases_count_by_project", "GET", "/analysis/mutated_cases_count_by_project",
        retryable=True,
    ),
    EndpointSpec("gene_expression_availability", "POST", "/gene_expression/availability"),
    EndpointSpec("gene_expression_gene_selection", "POST", "/gene_expression/gene_selection"),
    EndpointSpec("gene_expression_values", "POST", "/gene_expression/values"),
    EndpointSpec("cnv_occurrences", "GET", "/cnv_occurrences", retryable=True),
    EndpointSpec("ssm_occurrences", "GET", "/ssm_occurrences", retryable=True),
    EndpointSpec("projects_mapping", "GET", "/projects/_mapping", retryable=True, runtime=False),
)

ENDPOINTS: dict[tuple[str, str], EndpointSpec] = {(spec.method, spec.path): spec for spec in _ENDPOINT_LIST}
FORBIDDEN_PATHS = frozenset({"/data", "/manifest", "/slicing", "/files/versions", "/submissions"})

GDC_DATA_MODEL_REFERENCE = "gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1"


def resolve_endpoint(method: str, path: str) -> EndpointSpec:
    method = method.upper()
    if path in FORBIDDEN_PATHS:
        raise EndpointError(f"forbidden GDC path: {path}")
    spec = ENDPOINTS.get((method, path))
    if spec is None:
        raise EndpointError(f"endpoint not allowlisted: {method} {path}")
    return spec


@dataclass(frozen=True)
class GDCRequest:
    endpoint: EndpointSpec
    params: tuple[tuple[str, str], ...] = ()
    body: dict[str, Any] | None = None
    accept: str = "application/json"
    logical_query_id: str = "default"
    page: int = 1

    @property
    def method(self) -> str:
        return self.endpoint.method

    @property
    def path(self) -> str:
        return self.endpoint.path

    def request_hash(self) -> str:
        payload = {
            "contract": "gdc-request-v1",
            "method": self.method,
            "path": self.path,
            "params": sorted(self.params),
            "body": self.body,
            "accept": self.accept,
        }
        return hashlib.sha256(canonical_json(payload)).hexdigest()


def _validate_ids(values: list[str], *, limit: int, label: str) -> list[str]:
    if not values:
        raise EndpointError(f"{label} must not be empty")
    if len(values) > limit:
        raise EndpointError(f"{label} exceeds application cap {limit}")
    if len(set(values)) != len(values):
        raise EndpointError(f"{label} contains duplicates")
    for value in values:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise EndpointError(f"{label} contains an invalid identifier")
    return list(values)


def _validate_bounded_int(value: int, *, minimum: int, maximum: int | None, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EndpointError(f"{label} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        upper = f"..{maximum}" if maximum is not None else " or greater"
        raise EndpointError(f"{label} must be {minimum}{upper}")
    return value


def _filter_json(filter_object: dict[str, Any]) -> str:
    return json.dumps(filter_object, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _request(spec: EndpointSpec, params: dict[str, Any] | None = None, *, body: dict[str, Any] | None = None,
             accept: str = "application/json", logical_query_id: str = "default", page: int = 1) -> GDCRequest:
    normalized: list[tuple[str, str]] = []
    for key, value in sorted((params or {}).items()):
        if value is None:
            continue
        normalized.append((key, str(value)))
    return GDCRequest(
        endpoint=spec, params=tuple(normalized), body=body, accept=accept,
        logical_query_id=logical_query_id, page=page,
    )


def status_request() -> GDCRequest:
    return _request(resolve_endpoint("GET", "/status"), logical_query_id="status")


def projects_request(size: int = MAX_PROJECTS_PAGE) -> GDCRequest:
    _validate_bounded_int(size, minimum=1, maximum=MAX_PROJECTS_PAGE, label="projects size")
    return _request(
        resolve_endpoint("GET", "/projects"),
        {
            "size": size,
            "fields": ",".join((
                "project_id", "name", "program.name", "primary_site", "disease_type",
                "summary.case_count", "summary.file_count", "summary.data_categories.data_category",
            )),
        },
        logical_query_id="inventory:projects",
    )


def cohort_project_request(project_id: str) -> GDCRequest:
    """Fetch exactly one project record for an explicitly named cohort."""
    if not project_id or len(project_id) > 128:
        raise EndpointError("cohort project_id is invalid")
    return _request(
        resolve_endpoint("GET", "/projects"),
        {
            "size": 1,
            "filters": _filter_json({"op": "in", "content": {"field": "project_id", "value": [project_id]}}),
            "fields": ",".join((
                "project_id", "name", "program.name", "primary_site", "disease_type",
                "summary.case_count", "summary.file_count", "summary.data_categories.data_category",
            )),
        },
        logical_query_id=f"inventory:cohort:{project_id}",
    )


def cases_request(project_id: str, size: int = MAX_CASES_PAGE, *, offset: int = 0,
                  page: int | None = None) -> GDCRequest:
    _validate_bounded_int(size, minimum=1, maximum=MAX_CASES_PAGE, label="cases size")
    _validate_bounded_int(offset, minimum=0, maximum=None, label="cases offset")
    if page is not None:
        _validate_bounded_int(page, minimum=1, maximum=None, label="cases page")
    logical_page = page if page is not None else (offset // size) + 1
    return _request(
        resolve_endpoint("GET", "/cases"),
        {
            "size": size,
            "from": offset,
            "sort": "case_id",
            "filters": _filter_json({"op": "in", "content": {"field": "project.project_id", "value": [project_id]}}),
            "fields": "case_id,submitter_id,project.project_id,samples.sample_type",
        },
        logical_query_id=f"cases:{project_id}",
        page=logical_page,
    )


def files_expression_request(project_id: str, size: int = 5) -> GDCRequest:
    _validate_bounded_int(size, minimum=1, maximum=MAX_FILES_PAGE, label="files size")
    return _request(
        resolve_endpoint("GET", "/files"),
        {
            "size": size,
            "filters": _filter_json({"op": "and", "content": [
                {"op": "in", "content": {"field": "access", "value": ["open"]}},
                {"op": "in", "content": {"field": "data_type", "value": ["Gene Expression Quantification"]}},
                {"op": "in", "content": {"field": "cases.project.project_id", "value": [project_id]}},
            ]}),
            "fields": "file_id,access,analysis.workflow_type,experimental_strategy",
        },
        logical_query_id=f"files-expression:{project_id}",
    )


def files_capability_request(project_id: str, *, data_type: str | None = None) -> GDCRequest:
    """One aggregate open-file facet request: per-access/strategy/workflow/data-type counts.

    The request lists no file: it returns provider aggregate counts only, so a
    cohort capability probe or expression workflow-coverage check stays
    near-zero-bytes. The access facet is requested in addition to the
    server-side open filter so a provider returning a controlled bucket fails
    closed instead of being silently ignored.
    """
    if not isinstance(project_id, str) or not project_id or len(project_id) > 128:
        raise EndpointError("capability project_id is invalid")
    if data_type is not None and (not isinstance(data_type, str) or not data_type):
        raise EndpointError("capability data_type is invalid")
    content: list[dict[str, Any]] = [
        {"op": "in", "content": {"field": "access", "value": ["open"]}},
        {"op": "in", "content": {"field": "cases.project.project_id", "value": [project_id]}},
    ]
    if data_type is not None:
        content.append({"op": "in", "content": {"field": "data_type", "value": [data_type]}})
    return _request(
        resolve_endpoint("GET", "/files"),
        {
            "size": 0,
            "facets": "access,experimental_strategy,analysis.workflow_type,data_type",
            "filters": _filter_json({"op": "and", "content": content}),
        },
        logical_query_id=f"files-capability:{project_id}",
    )


def ssm_occurrence_gene_page_request(project_id: str, gene_id: str, *, offset: int = 0,
                                     size: int = MAX_SSM_OCCURRENCES_PAGE) -> GDCRequest:
    """Fixed bounded detail page for one declared project/gene occurrence query.

    This is the shared per-gene detail contract (P07 composition fields); pages
    are bounded by the caller's declared page budget.
    """
    _validate_ids([project_id], limit=1, label="project_id")
    _validate_ids([gene_id], limit=1, label="gene_id")
    _validate_bounded_int(size, minimum=1, maximum=MAX_SSM_OCCURRENCES_PAGE,
                          label="SSM detail size")
    _validate_bounded_int(offset, minimum=0, maximum=None, label="SSM detail offset")
    return _request(
        resolve_endpoint("GET", "/ssm_occurrences"),
        {
            "size": size,
            "from": offset,
            "sort": "ssm_occurrence_id:asc",
            "filters": _filter_json({"op": "and", "content": [
                {"op": "in", "content": {
                    "field": "case.project.project_id", "value": [project_id]}},
                {"op": "in", "content": {
                    "field": "ssm.consequence.transcript.gene.gene_id", "value": [gene_id]}},
            ]}),
            "fields": ",".join(SSM_OCCURRENCE_FIELDS),
        },
        logical_query_id=f"ssm-gene-detail:{project_id}:{gene_id}",
        page=(offset // size) + 1,
    )


def genes_request(gene_ids: list[str]) -> GDCRequest:
    _validate_ids(gene_ids, limit=MAX_GENE_IDS, label="gene_ids")
    return _request(
        resolve_endpoint("GET", "/genes"),
        {
            "size": len(gene_ids),
            "filters": _filter_json({"op": "in", "content": {"field": "gene_id", "value": gene_ids}}),
            "fields": "gene_id,symbol,name,biotype,is_cancer_gene_census",
        },
        logical_query_id="genes:identity",
    )


def genes_universe_request(offset: int, size: int) -> GDCRequest:
    """Fixed bounded universe enumeration; not a caller-controlled query builder.

    The systematic-discovery contract is deterministic: protein_coding genes,
    gene_id ascending, one page at ``offset``. Only ``offset`` and ``size`` vary
    and both are validated; no arbitrary filter or field is expressible.
    """
    _validate_bounded_int(offset, minimum=0, maximum=None, label="genes universe offset")
    _validate_bounded_int(size, minimum=1, maximum=MAX_GENE_PAGE, label="genes universe page size")
    return _request(
        resolve_endpoint("GET", "/genes"),
        {
            "size": size,
            "from": offset,
            "sort": GENES_UNIVERSE_SORT,
            "filters": _filter_json({
                "op": "in",
                "content": {"field": "biotype", "value": [GENES_UNIVERSE_BIOTYPE]},
            }),
            "fields": "gene_id,symbol,biotype",
        },
        logical_query_id="genes:universe",
        page=(offset // size) + 1,
    )


def top_mutated_genes_request(project_id: str, size: int = MAX_DISCOVERY_HITS) -> GDCRequest:
    _validate_bounded_int(size, minimum=1, maximum=MAX_DISCOVERY_HITS, label="discovery size")
    return _request(
        resolve_endpoint("GET", "/analysis/top_mutated_genes_by_project"),
        {
            "size": size,
            "fields": "gene_id,symbol",
            "filters": _filter_json({"op": "in", "content": {"field": "case.project.project_id", "value": [project_id]}}),
        },
        logical_query_id=f"discovery:{project_id}",
    )


def gene_case_counts_request(gene_ids: list[str]) -> GDCRequest:
    _validate_ids(gene_ids, limit=MAX_GENE_IDS, label="gene_ids")
    return _request(
        resolve_endpoint("GET", "/analysis/top_cases_counts_by_genes"),
        {"gene_ids": ",".join(gene_ids)},
        logical_query_id="counts:genes",
    )


def mutated_cases_count_request() -> GDCRequest:
    return _request(
        resolve_endpoint("GET", "/analysis/mutated_cases_count_by_project"),
        {"size": 0},
        logical_query_id="coverage:projects",
    )


def expression_availability_request(case_ids: list[str], gene_ids: list[str]) -> GDCRequest:
    _validate_ids(case_ids, limit=MAX_CASE_IDS, label="case_ids")
    _validate_ids(gene_ids, limit=MAX_GENE_IDS, label="gene_ids")
    return _request(
        resolve_endpoint("POST", "/gene_expression/availability"),
        body={"case_ids": list(case_ids), "gene_ids": list(gene_ids)},
        logical_query_id="expression:availability",
    )


def expression_gene_selection_request(case_ids: list[str], gene_ids: list[str]) -> GDCRequest:
    _validate_ids(case_ids, limit=MAX_CASE_IDS, label="case_ids")
    _validate_ids(gene_ids, limit=MAX_GENE_IDS, label="gene_ids")
    return _request(
        resolve_endpoint("POST", "/gene_expression/gene_selection"),
        body={"case_ids": list(case_ids), "gene_ids": list(gene_ids), "selection_size": len(gene_ids)},
        logical_query_id="expression:gene-selection",
    )


def expression_values_request(case_ids: list[str], gene_ids: list[str]) -> GDCRequest:
    _validate_ids(case_ids, limit=MAX_CASE_IDS, label="case_ids")
    _validate_ids(gene_ids, limit=MAX_GENE_IDS, label="gene_ids")
    return _request(
        resolve_endpoint("POST", "/gene_expression/values"),
        body={"case_ids": list(case_ids), "gene_ids": list(gene_ids), "tsv_units": "uqfpkm", "format": "tsv"},
        accept="text/tab-separated-values",
        logical_query_id="expression:values",
    )


MAX_CNV_CASE_SHARD_SIZE = 250


def cnv_occurrences_request(project_id: str, gene_id: str, *, offset: int = 0,
                            size: int = MAX_CNV_OCCURRENCES_PAGE) -> GDCRequest:
    """Fixed complete-query page for one declared project/gene survivor."""
    _validate_ids([project_id], limit=1, label="project_id")
    _validate_ids([gene_id], limit=1, label="gene_id")
    _validate_bounded_int(size, minimum=1, maximum=MAX_CNV_OCCURRENCES_PAGE,
                          label="CNV occurrence size")
    _validate_bounded_int(offset, minimum=0, maximum=None, label="CNV occurrence offset")
    return _request(
        resolve_endpoint("GET", "/cnv_occurrences"),
        {
            "size": size,
            "from": offset,
            "sort": "cnv_occurrence_id:asc",
            "filters": _filter_json({"op": "and", "content": [
                {"op": "in", "content": {
                    "field": "case.project.project_id", "value": [project_id]}},
                {"op": "in", "content": {
                    "field": "cnv.consequence.gene.gene_id", "value": [gene_id]}},
            ]}),
            "fields": ",".join(CNV_OCCURRENCE_FIELDS),
        },
        logical_query_id=f"cnv-occurrences:{project_id}:{gene_id}",
        page=(offset // size) + 1,
    )


def cnv_occurrence_shard_page_request(project_id: str, case_ids: list[str], *,
                                      offset: int = 0,
                                      size: int = MAX_CNV_OCCURRENCES_PAGE) -> GDCRequest:
    """Fixed complete-query page for one declared case shard of one project.

    The shard is an operational partition of the declared cohort frame; it can
    never change the recurrence thresholds, which are evaluated only on the
    merged all-shard evidence.
    """
    _validate_ids([project_id], limit=1, label="project_id")
    _validate_ids(case_ids, limit=MAX_CNV_CASE_SHARD_SIZE, label="case_id")
    _validate_bounded_int(size, minimum=1, maximum=MAX_CNV_OCCURRENCES_PAGE,
                          label="CNV shard size")
    _validate_bounded_int(offset, minimum=0, maximum=None, label="CNV shard offset")
    return _request(
        resolve_endpoint("GET", "/cnv_occurrences"),
        {
            "size": size,
            "from": offset,
            "sort": "cnv_occurrence_id:asc",
            "filters": _filter_json({"op": "and", "content": [
                {"op": "in", "content": {
                    "field": "case.project.project_id", "value": [project_id]}},
                {"op": "in", "content": {
                    "field": "case.case_id", "value": sorted(case_ids)}},
            ]}),
            "fields": ",".join(CNV_OCCURRENCE_FIELDS),
        },
        logical_query_id=f"cnv-shard-scan:{project_id}",
        page=(offset // size) + 1,
    )


def ssm_occurrence_page_request(project_id: str, *, offset: int = 0,
                                size: int = MAX_SSM_OCCURRENCES_PAGE) -> GDCRequest:
    """One complete-scan page of the project's released occurrence records.

    Fixed bounded shape: project-scoped filter, deterministic ascending sort,
    occurrence identity plus case identity plus the annotated gene identity.
    No other query surface is expressible; distinct-case derivation happens
    locally over validated records, never from an aggregation bucket.
    """
    _validate_ids([project_id], limit=1, label="project_id")
    _validate_bounded_int(size, minimum=1, maximum=MAX_SSM_OCCURRENCES_PAGE,
                          label="SSM occurrence size")
    _validate_bounded_int(offset, minimum=0, maximum=None, label="SSM occurrence offset")
    return _request(
        resolve_endpoint("GET", "/ssm_occurrences"),
        {
            "size": size,
            "from": offset,
            "sort": "ssm_occurrence_id:asc",
            "filters": _filter_json({"op": "in", "content": {
                "field": "case.project.project_id", "value": [project_id]}}),
            "fields": ",".join(SSM_OCCURRENCE_FIELDS),
        },
        logical_query_id=f"ssm-occurrence-scan:{project_id}",
        page=(offset // size) + 1,
    )


def projects_mapping_request() -> GDCRequest:
    return _request(resolve_endpoint("GET", "/projects/_mapping"), logical_query_id="contract:mapping")
