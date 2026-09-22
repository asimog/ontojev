"""Offline replay transport and synthetic provider-shaped responses for orchestration tests.

These bodies are SYNTHETIC provider-shaped fixtures (clearly labeled), used only
to exercise the live orchestrator without network access. Real captured provider
bytes are used by the parser tests in tests/contracts.
"""

from __future__ import annotations

import json
from typing import Any

from cancerjev.domain.events import utc_now
from cancerjev.gdc.endpoints import GDCRequest
from cancerjev.gdc.transport import GDCResponse
from cancerjev.storage.artifacts import ArtifactStore

PROJECTS = {"TEST-A": 100, "TEST-B": 80, "TEST-C": 10}
GENES = ["ENSG00000000001", "ENSG00000000002"]
COUNTS = {"TEST-A": {GENES[0]: 20, GENES[1]: 5}, "TEST-B": {GENES[0]: 12}}
COVERAGE = {"TEST-A": 95, "TEST-B": 70}


def _json(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _filter_project(request: GDCRequest) -> str:
    params = dict(request.params)
    filters = json.loads(params["filters"])
    return filters["content"]["value"][0] if filters["op"] == "in" else filters["content"][0]["content"]["value"][0]


def status_body() -> bytes:
    return _json({"commit": "0" * 40, "data_release": "Data Release TEST - 2026-01-01",
                  "status": "OK", "tag": "9.0.0"})


def projects_body() -> bytes:
    hits = []
    for project_id, case_count in PROJECTS.items():
        hits.append({
            "project_id": project_id, "name": f"Project {project_id}",
            "program": {"name": "TESTPROG"}, "primary_site": ["Breast"],
            "disease_type": ["Ductal and Lobular Neoplasms"],
            "summary": {"case_count": case_count, "file_count": case_count * 5,
                        "data_categories": [{"data_category": "Transcriptome Profiling"}]},
        })
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": len(hits),
                                                       "size": 100, "from": 0, "pages": 1}}})


def discovery_body(project_id: str) -> bytes:
    return _json({"data": {"hits": [
        {"gene_id": GENES[0], "symbol": "GENEONE", "_score": 800.0},
        {"gene_id": GENES[1], "symbol": "GENETWO", "_score": 120.0},
    ], "pagination": {"count": 2, "total": 2, "size": 20, "from": 0, "pages": 1}}})


def counts_body() -> bytes:
    buckets = []
    for project_id, counts in COUNTS.items():
        gene_buckets = [{"key": gene_id, "doc_count": count} for gene_id, count in sorted(counts.items())]
        buckets.append({"key": project_id, "doc_count": sum(counts.values()),
                        "genes": {"my_genes": {"gene_id": {"buckets": gene_buckets}}}})
    return _json({"took": 5, "timed_out": False, "_shards": {"total": 5, "successful": 5, "failed": 0},
                  "hits": {"total": {"value": sum(sum(c.values()) for c in COUNTS.values())}},
                  "sum_other_doc_count": 0, "doc_count_error_upper_bound": 0,
                  "aggregations": {"projects": {"buckets": buckets}}})


def coverage_body() -> bytes:
    buckets = [{"key": project_id, "doc_count": count,
                "case_summary": {"case_with_ssm": {"doc_count": count}}}
               for project_id, count in sorted(COVERAGE.items())]
    return _json({"took": 3, "timed_out": False, "_shards": {"total": 5, "successful": 5, "failed": 0},
                  "sum_other_doc_count": 0, "doc_count_error_upper_bound": 0,
                  "aggregations": {"projects": {"buckets": buckets}}})


def genes_body() -> bytes:
    return _json({"data": {"hits": [
        {"gene_id": GENES[0], "symbol": "GENEONE", "name": "Gene One", "biotype": "protein_coding",
         "is_cancer_gene_census": True},
        {"gene_id": GENES[1], "symbol": "GENETWO", "name": "Gene Two", "biotype": "protein_coding",
         "is_cancer_gene_census": False},
    ], "pagination": {"count": 2, "total": 2, "size": 10, "from": 0, "pages": 1}}})


def case_ids(project_id: str) -> list[str]:
    return [f"{project_id}-case-{index:03d}" for index in range(PROJECTS[project_id])]


def cases_body(project_id: str, *, incomplete: bool = False) -> bytes:
    ids = case_ids(project_id)
    hits = [{"case_id": case_id, "submitter_id": case_id.upper(), "project": {"project_id": project_id},
             "samples": [{"sample_type": "Primary Tumor"}]} for case_id in ids]
    total = len(ids) + (5 if incomplete else 0)
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": total,
                                                       "size": 250, "from": 0, "pages": 2 if incomplete else 1}}})


def files_body(project_id: str, *, controlled: bool = False) -> bytes:
    hits = [{"file_id": f"{project_id}-file-{index}", "access": "open",
             "analysis": {"workflow_type": "STAR - Counts"}, "experimental_strategy": "RNA-Seq"}
            for index in range(3)]
    if controlled:
        hits.append({"file_id": f"{project_id}-file-controlled", "access": "controlled",
                     "analysis": {"workflow_type": "STAR - Counts"}, "experimental_strategy": "RNA-Seq"})
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": len(hits),
                                                        "size": 5, "from": 0, "pages": 1}}})


def availability_body(case_ids_requested: list[str], gene_ids: list[str], *, empty: bool = False) -> bytes:
    has_values = not empty
    return _json({
        "cases": {
            "details": [{"case_id": case_id, "has_gene_expression_values": has_values}
                        for case_id in case_ids_requested],
            "with_gene_expression_count": len(case_ids_requested) if has_values else 0,
            "without_gene_expression_count": 0,
        },
        "genes": {
            "details": [{"gene_id": gene_id, "has_gene_expression_values": has_values} for gene_id in gene_ids],
            "with_gene_expression_count": len(gene_ids) if has_values else 0,
            "without_gene_expression_count": 0,
        },
    })


def gene_selection_body(case_ids_requested: list[str], gene_ids: list[str]) -> bytes:
    return _json({"gene_selection": [
        {"gene_id": gene_id, "symbol": f"GENE{gene_ids.index(gene_id) + 1}",
         "log2_uqfpkm_median": 3.0 + gene_ids.index(gene_id), "log2_uqfpkm_stddev": 0.5}
        for gene_id in gene_ids
    ]})


def values_body(case_ids_requested: list[str], gene_ids: list[str]) -> bytes:
    lines = ["gene_id\t" + "\t".join(case_ids_requested)]
    for gene_index, gene_id in enumerate(gene_ids):
        cells = [f"{3.0 + gene_index + (index % 7) * 0.5:.4f}" for index in range(len(case_ids_requested))]
        lines.append(gene_id + "\t" + "\t".join(cells))
    return ("\n".join(lines) + "\n").encode()


class ReplayTransport:
    """Network-boundary test double: real artifacts, real shapes, no sockets."""

    def __init__(self, artifacts: ArtifactStore, run_id: str, *, controlled_files: bool = False,
                 incomplete_frame: bool = False, empty_expression_projects: set[str] | None = None) -> None:
        self.artifacts = artifacts
        self.run_id = run_id
        self.controlled_files = controlled_files
        self.incomplete_frame = incomplete_frame
        self.empty_expression_projects = empty_expression_projects or set()
        self.requests: list[GDCRequest] = []
        self._counter = 0

    def _project_of(self, case_ids: list[str]) -> str:
        return case_ids[0].rsplit("-case-", 1)[0]

    def request(self, request: GDCRequest) -> GDCResponse:
        self.requests.append(request)
        self._counter += 1
        name = request.endpoint.name
        if name == "status":
            body = status_body()
        elif name == "projects":
            body = projects_body()
        elif name == "top_mutated_genes_by_project":
            body = discovery_body(_filter_project(request))
        elif name == "top_cases_counts_by_genes":
            body = counts_body()
        elif name == "mutated_cases_count_by_project":
            body = coverage_body()
        elif name == "genes":
            body = genes_body()
        elif name == "cases":
            body = cases_body(_filter_project(request), incomplete=self.incomplete_frame)
        elif name == "files":
            body = files_body(_filter_project(request), controlled=self.controlled_files)
        elif name == "gene_expression_availability":
            project = self._project_of(request.body["case_ids"])
            body = availability_body(request.body["case_ids"], request.body["gene_ids"],
                                     empty=project in self.empty_expression_projects)
        elif name == "gene_expression_gene_selection":
            project = self._project_of(request.body["case_ids"])
            assert project not in self.empty_expression_projects, "guard failed: selection requested without values"
            body = gene_selection_body(request.body["case_ids"], request.body["gene_ids"])
        elif name == "gene_expression_values":
            project = self._project_of(request.body["case_ids"])
            assert project not in self.empty_expression_projects, "guard failed: values requested without values"
            body = values_body(request.body["case_ids"], request.body["gene_ids"])
        else:  # pragma: no cover - guards against silent fixture drift
            raise AssertionError(f"replay transport has no fixture for {name}")
        media = "text/tab-separated-values" if request.accept != "application/json" else "application/json"
        artifact = self.artifacts.publish(
            f"replay/{self.run_id}/{name}-{self._counter}.body", body, media, "gdc-response",
        )
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": media}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at=utc_now(), latency_ms=1,
        )
