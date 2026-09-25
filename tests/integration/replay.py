"""Offline replay transport and synthetic provider-shaped responses for orchestration tests.

These bodies are SYNTHETIC provider-shaped fixtures (clearly labeled), used only
to exercise the live orchestrator without network access. Real captured provider
bytes are used by the parser tests in tests/contracts.
"""

from __future__ import annotations

import json
import math
from typing import Any
from uuid import uuid4

from cancerjev.domain.events import utc_now
from cancerjev.gdc.endpoints import GDCRequest
from cancerjev.gdc.transport import GDCResponse
from cancerjev.storage.artifacts import ArtifactStore

PROJECTS = {"TCGA-LUAD": 100, "TCGA-LUSC": 80, "TEST-C": 10}
GENES = ["ENSG00000000001", "ENSG00000000002"]
COUNTS = {"TCGA-LUAD": {GENES[0]: 20, GENES[1]: 5}}
COVERAGE = {"TCGA-LUAD": 95}


def _json(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _filter_project(request: GDCRequest) -> str:
    params = dict(request.params)
    filters = json.loads(params["filters"])
    return filters["content"]["value"][0] if filters["op"] == "in" else filters["content"][0]["content"]["value"][0]


def status_body() -> bytes:
    return _json({"commit": "0" * 40, "data_release": "Data Release TEST - 2026-01-01",
                  "status": "OK", "tag": "9.0.0"})


def projects_body(projects: dict[str, int], selected_project_id: str) -> bytes:
    hits = []
    for project_id, case_count in projects.items():
        if project_id != selected_project_id:
            continue
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


def genes_body(*, size: int = 10, offset: int = 0) -> bytes:
    hits = [
        {"gene_id": GENES[0], "symbol": "GENEONE", "name": "Gene One", "biotype": "protein_coding",
         "is_cancer_gene_census": True},
        {"gene_id": GENES[1], "symbol": "GENETWO", "name": "Gene Two", "biotype": "protein_coding",
         "is_cancer_gene_census": False},
    ][offset:offset + size]
    return _json({"data": {"hits": hits, "pagination": {
        "count": len(hits), "total": 2, "size": size, "from": offset, "pages": 1}}})


def count_records(project_id: str) -> list[dict[str, Any]]:
    """One released occurrence per (gene, case) pair implied by ``COUNTS``.

    Distinct-case semantics are exactly the bucket values of the legacy fixture:
    the corrected scan must derive the same counts without ever reading a bucket.
    """
    records: list[dict[str, Any]] = []
    case_pool = case_ids(project_id, PROJECTS)
    cursor = 0
    for gene_id in sorted(COUNTS.get(project_id, {})):
        for _ in range(COUNTS[project_id][gene_id]):
            cursor += 1
            records.append({
                "ssm_occurrence_id": f"{project_id}-occ-{cursor:05d}",
                "case": {"case_id": case_pool[(cursor - 1) % len(case_pool)],
                         "project": {"project_id": project_id}},
                "ssm": {"consequence": [{"transcript": {"gene": {"gene_id": gene_id}}}]},
            })
    return records


def ssm_occurrence_body(project_id: str, *, offset: int, size: int, truncate: bool = False,
                        duplicate_previous: bool = False) -> bytes:
    records = count_records(project_id)
    page = [dict(record) for record in records[offset:offset + size]]
    if duplicate_previous and offset > 0 and page:
        page[0]["ssm_occurrence_id"] = records[offset - 1]["ssm_occurrence_id"]
    if truncate and page and offset + len(page) < len(records):
        page = page[:-1]
    return _json({"data": {"hits": page, "pagination": {
        "total": len(records), "count": len(page), "size": size, "from": offset,
        "pages": math.ceil(len(records) / size) if records else 0}}})


def case_ids(project_id: str, projects: dict[str, int]) -> list[str]:
    return [f"{project_id}-case-{index:04d}" for index in range(projects[project_id])]


def cases_body(project_id: str, projects: dict[str, int], *, size: int, offset: int,
               incomplete: bool = False) -> bytes:
    all_ids = case_ids(project_id, projects)
    ids = all_ids[offset:offset + size]
    hits = [{"case_id": case_id, "submitter_id": case_id.upper(), "project": {"project_id": project_id},
             "samples": [{"sample_type": "Primary Tumor"}]} for case_id in ids]
    total = len(all_ids) + (5 if incomplete else 0)
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": total,
                                                       "size": size, "from": offset,
                                                       "pages": (total + size - 1) // size}}})


def files_body(project_id: str, *, controlled: bool = False) -> bytes:
    hits = [{"file_id": f"{project_id}-file-{index}", "access": "open",
             "analysis": {"workflow_type": "STAR - Counts"}, "experimental_strategy": "RNA-Seq"}
            for index in range(3)]
    if controlled:
        hits.append({"file_id": f"{project_id}-file-controlled", "access": "controlled",
                     "analysis": {"workflow_type": "STAR - Counts"}, "experimental_strategy": "RNA-Seq"})
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": len(hits),
                                                        "size": 5, "from": 0, "pages": 1}}})


def availability_body(case_ids_requested: list[str], gene_ids: list[str], *, empty: bool = False,
                      omit_genes: bool = False) -> bytes:
    has_values = not empty
    return _json({
        "cases": {
            "details": [{"case_id": case_id, "has_gene_expression_values": has_values}
                        for case_id in case_ids_requested],
            "with_gene_expression_count": len(case_ids_requested) if has_values else 0,
            "without_gene_expression_count": 0,
        },
        "genes": {
            "details": [] if omit_genes else [
                {"gene_id": gene_id, "has_gene_expression_values": has_values} for gene_id in gene_ids
            ],
            "with_gene_expression_count": 0 if omit_genes else (len(gene_ids) if has_values else 0),
            "without_gene_expression_count": 0,
        },
    })


def gene_selection_body(case_ids_requested: list[str], gene_ids: list[str]) -> bytes:
    return _json({"gene_selection": [
        {"gene_id": gene_id, "symbol": f"GENE{gene_ids.index(gene_id) + 1}",
         "log2_uqfpkm_median": 3.0 + gene_ids.index(gene_id), "log2_uqfpkm_stddev": 0.5}
        for gene_id in gene_ids
    ]})


def values_body(case_ids_requested: list[str], gene_ids: list[str], *, drop_columns: int = 0,
                constant_value: float | None = None) -> bytes:
    returned = case_ids_requested[: len(case_ids_requested) - drop_columns] if drop_columns else case_ids_requested
    lines = ["gene_id\t" + "\t".join(returned)]
    for gene_index, gene_id in enumerate(gene_ids):
        cells = [f"{(constant_value if constant_value is not None else 3.0 + gene_index + (index % 7) * 0.5):.4f}"
                 for index in range(len(returned))]
        lines.append(gene_id + "\t" + "\t".join(cells))
    return ("\n".join(lines) + "\n").encode()


class ReplayTransport:
    """Network-boundary test double: real artifacts, real shapes, no sockets."""

    def __init__(self, artifacts: ArtifactStore, run_id: str, *, repository: Any = None,
                 controlled_files: bool = False,
                  incomplete_frame: bool = False, empty_expression_projects: set[str] | None = None,
                  drop_value_columns: int = 0, project_case_counts: dict[str, int] | None = None,
                  duplicate_case_across_pages: bool = False,
                  inconsistent_case_total_after_first: bool = False,
                  inconsistent_case_offset_after_first: bool = False,
                  constant_expression_value: float | None = None,
                  truncate_occurrence_page: bool = False,
                  duplicate_occurrence_across_pages: bool = False) -> None:
        self.artifacts = artifacts
        self.run_id = run_id
        self.controlled_files = controlled_files
        self.incomplete_frame = incomplete_frame
        self.empty_expression_projects = empty_expression_projects or set()
        self.drop_value_columns = drop_value_columns
        self.project_case_counts = project_case_counts or PROJECTS
        self.duplicate_case_across_pages = duplicate_case_across_pages
        self.inconsistent_case_total_after_first = inconsistent_case_total_after_first
        self.inconsistent_case_offset_after_first = inconsistent_case_offset_after_first
        self.constant_expression_value = constant_expression_value
        self.truncate_occurrence_page = truncate_occurrence_page
        self.duplicate_occurrence_across_pages = duplicate_occurrence_across_pages
        self.requests: list[GDCRequest] = []
        self.published: list[Any] = []
        self.repository = repository
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
            body = projects_body(self.project_case_counts, _filter_project(request))
        elif name == "top_mutated_genes_by_project":
            body = discovery_body(_filter_project(request))
        elif name == "top_cases_counts_by_genes":
            body = counts_body()
        elif name == "mutated_cases_count_by_project":
            body = coverage_body()
        elif name == "ssm_occurrences":
            params = dict(request.params)
            body = ssm_occurrence_body(
                _filter_project(request), offset=int(params["from"]), size=int(params["size"]),
                truncate=self.truncate_occurrence_page,
                duplicate_previous=self.duplicate_occurrence_across_pages)
        elif name == "genes":
            params = dict(request.params)
            body = genes_body(size=int(params["size"]), offset=int(params.get("from", 0)))
        elif name == "cases":
            params = dict(request.params)
            offset = int(params["from"])
            body = cases_body(
                _filter_project(request), self.project_case_counts,
                size=int(params["size"]), offset=offset,
                incomplete=self.incomplete_frame,
            )
            if offset and (
                self.duplicate_case_across_pages
                or self.inconsistent_case_total_after_first
                or self.inconsistent_case_offset_after_first
            ):
                document = json.loads(body)
                if self.duplicate_case_across_pages:
                    project_id = _filter_project(request)
                    document["data"]["hits"][0]["case_id"] = case_ids(
                        project_id, self.project_case_counts,
                    )[offset - 1]
                if self.inconsistent_case_total_after_first:
                    document["data"]["pagination"]["total"] += 1
                if self.inconsistent_case_offset_after_first:
                    document["data"]["pagination"]["from"] -= 1
                body = _json(document)
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
            body = values_body(request.body["case_ids"], request.body["gene_ids"],
                               drop_columns=self.drop_value_columns,
                               constant_value=self.constant_expression_value)
        else:  # pragma: no cover - guards against silent fixture drift
            raise AssertionError(f"replay transport has no fixture for {name}")
        media = "text/tab-separated-values" if request.accept != "application/json" else "application/json"
        artifact = self.artifacts.publish(
            f"replay/{self.run_id}/{name}-{self._counter}.body", body, media, "gdc-response",
        )
        self.published.append(artifact)
        if self.repository is not None:
            self.repository.register_artifact(artifact, self.run_id)
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": media}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at=utc_now(), latency_ms=1,
            request_id=str(uuid4()), attempt_no=1,
        )
