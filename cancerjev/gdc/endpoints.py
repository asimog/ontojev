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
MAX_CASES_PAGE = 250
MAX_PROJECTS_PAGE = 100
MAX_DISCOVERY_HITS = 20

GENE_CASE_COUNTS_FIELDS_NOTE = "endpoint rejects fields/format parameters"


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
    EndpointSpec("projects_mapping", "GET", "/projects/_mapping", retryable=True, runtime=False),
)

ENDPOINTS: dict[tuple[str, str], EndpointSpec] = {(spec.method, spec.path): spec for spec in _ENDPOINT_LIST}
FORBIDDEN_PATHS = frozenset({"/data", "/manifest", "/slicing", "/files/versions", "/submissions"})


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
    if not 1 <= size <= MAX_PROJECTS_PAGE:
        raise EndpointError(f"projects size must be 1..{MAX_PROJECTS_PAGE}")
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


def cases_request(project_id: str, size: int = MAX_CASES_PAGE) -> GDCRequest:
    if not 1 <= size <= MAX_CASES_PAGE:
        raise EndpointError(f"cases size must be 1..{MAX_CASES_PAGE}")
    return _request(
        resolve_endpoint("GET", "/cases"),
        {
            "size": size,
            "sort": "case_id",
            "filters": _filter_json({"op": "in", "content": {"field": "project.project_id", "value": [project_id]}}),
            "fields": "case_id,submitter_id,project.project_id,samples.sample_type",
        },
        logical_query_id=f"cases:{project_id}",
    )


def files_expression_request(project_id: str, size: int = 5) -> GDCRequest:
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


def top_mutated_genes_request(project_id: str, size: int = MAX_DISCOVERY_HITS) -> GDCRequest:
    if not 1 <= size <= MAX_DISCOVERY_HITS:
        raise EndpointError(f"discovery size must be 1..{MAX_DISCOVERY_HITS}")
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
        body={"case_ids": list(case_ids), "gene_ids": list(gene_ids), "tsv_units": "uqfpkm"},
        accept="text/tab-separated-values",
        logical_query_id="expression:values",
    )


def projects_mapping_request() -> GDCRequest:
    return _request(resolve_endpoint("GET", "/projects/_mapping"), logical_query_id="contract:mapping")
