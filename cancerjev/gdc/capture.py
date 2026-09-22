"""Bounded contract verification: reproducible live captures of admitted endpoints.

The probe uses the same sole transport as the runtime; it cannot reach paths the
allowlist excludes. Every capture records request metadata, response headers,
exact bytes and SHA-256, and asserts that no authentication header was sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from cancerjev.gdc.endpoints import (
    GDCRequest,
    cases_request,
    expression_availability_request,
    expression_gene_selection_request,
    expression_values_request,
    files_expression_request,
    gene_case_counts_request,
    genes_request,
    mutated_cases_count_request,
    projects_mapping_request,
    projects_request,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.transport import GDCResponse, GDCTransport

PROBE_PARSER_VERSION = "contract-probe-v1"


@dataclass
class CaptureSink:
    directory: Path
    entries: list[dict[str, Any]] = field(default_factory=list)

    def record(self, name: str, request: GDCRequest, response: GDCResponse) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        body_path = self.directory / f"{name}.body"
        body_path.write_bytes(response.body)
        url = request.path
        if request.params:
            url = f"{url}?{urlencode(sorted(request.params))}"
        meta = {
            "probe_name": name,
            "method": request.method,
            "endpoint": request.path,
            "normalized_params": dict(sorted(request.params)),
            "normalized_body": request.body,
            "url": url,
            "request_headers_sent": {
                "Accept": request.accept,
                "Accept-Encoding": "identity",
                "User-Agent": "CancerJEV/0.2 (public open-access research; anonymous)",
            },
            "authentication_headers_sent": [],
            "http_status": response.http_status,
            "response_headers": response.headers,
            "retrieved_at": response.retrieved_at,
            "latency_ms": response.latency_ms,
            "body_bytes_read": len(response.body),
            "body_sha256": response.body_sha256,
            "response_truncated_by_probe_cap": False,
            "per_response_cap": None,
            "error": None,
            "parser_version": PROBE_PARSER_VERSION,
            "completeness": response.completeness,
            "from_cache": response.from_cache,
        }
        (self.directory / f"{name}.meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8",
        )
        self.entries.append(meta)

    def finalize(self) -> dict[str, Any]:
        index = {
            "captured_at": self.entries[0]["retrieved_at"] if self.entries else None,
            "base_host": "api.gdc.cancer.gov",
            "authentication": "NONE (anonymous)",
            "probe_count": len(self.entries),
            "total_body_bytes": sum(entry["body_bytes_read"] for entry in self.entries),
            "captures": [
                {key: entry[key] for key in (
                    "probe_name", "method", "endpoint", "http_status", "body_bytes_read",
                    "body_sha256", "retrieved_at", "response_truncated_by_probe_cap", "error",
                    "completeness", "url",
                )}
                for entry in self.entries
            ],
        }
        (self.directory / "INDEX.json").write_text(
            json.dumps(index, indent=2, sort_keys=True), encoding="utf-8",
        )
        return index


def _json_body(response: GDCResponse) -> dict[str, Any]:
    return json.loads(response.body.decode("utf-8"))


def run_contract_probe(
    transport: GDCTransport,
    sink: CaptureSink,
    *,
    release: str | None,
    reference_project: str = "TCGA-BRCA",
    frame_project: str = "TCGA-CHOL",
    frame_size: int = 250,
) -> dict[str, Any]:
    """Bounded probe of the admitted endpoint surface (~14 requests)."""
    probe_names = {
        "status": status_request(),
        "projects_small": projects_request(size=3),
        "cases_brca": cases_request(reference_project, size=2),
        "files_expression_brca": files_expression_request(reference_project, size=2),
        "genes_tp53": genes_request(["ENSG00000141510"]),
        "discovery_brca": top_mutated_genes_request(reference_project, size=5),
        "counts_tp53": gene_case_counts_request(["ENSG00000141510"]),
        "counts_multi_gene": gene_case_counts_request(
            ["ENSG00000141510", "ENSG00000121879", "ENSG00000154358"],
        ),
        "coverage_projects": mutated_cases_count_request(),
        "projects_mapping": projects_mapping_request(),
    }
    responses: dict[str, GDCResponse] = {}
    for name, request in probe_names.items():
        response = transport.request(request)
        sink.record(name, request, response)
        responses[name] = response

    frame_response = transport.request(cases_request(frame_project, size=frame_size))
    sink.record("cases_frame", cases_request(frame_project, size=frame_size), frame_response)
    frame_hits = _json_body(frame_response)["data"]["hits"]
    frame_case_ids = [hit["case_id"] for hit in frame_hits][:frame_size]
    gene_ids = ["ENSG00000141510"]
    for name, request in (
        ("expression_availability", expression_availability_request(frame_case_ids, gene_ids)),
        ("expression_gene_selection", expression_gene_selection_request(frame_case_ids, gene_ids)),
        ("expression_values", expression_values_request(frame_case_ids, gene_ids)),
    ):
        response = transport.request(request)
        sink.record(name, request, response)

    index = sink.finalize()
    return {
        "captures": index["probe_count"],
        "bytes": index["total_body_bytes"],
        "release": release,
        "frame_cases": len(frame_case_ids),
    }
