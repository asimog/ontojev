"""Bounded synthetic provider-shaped fixtures for offline demonstration runs.

These bodies are clearly labelled SYNTHETIC provider-shaped responses, used only
to exercise the current architecture without network access. They flow through
the same strict parsers, deterministic methods, typed states, registered actions,
Jev projections and dossier path as a live run; only the provider transport and
the Jev adapter are substituted. Real captured provider bytes live under
``tests/contracts/fixtures/gdc`` and are never replaced by these.
"""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import uuid4

from cancerjev.domain.events import utc_now
from cancerjev.gdc.endpoints import GDCRequest
from cancerjev.gdc.transport import GDCResponse
from cancerjev.jev.questions import (
    DEEP_LIMITATION_ROSTER,
    HYPOTHESIS_UNSUPPORTED_ROSTER,
    LIMITATION_ROSTER,
    QuestionDefinition,
)
from cancerjev.jev.typesafe_adapter import ProviderAnswerSet
from cancerjev.storage.artifacts import ArtifactStore

FIXTURE_ID = "demo"
FIXTURE_VERSION = "demo-v1"
FIXTURE_NOTICE = "SYNTHETIC FAKE FIXTURE — NO REAL GDC DATA"

PROJECTS = {"TCGA-LUAD": 100}
GENES = ["ENSG00000000001", "ENSG00000000002"]
COUNTS = {"TCGA-LUAD": {GENES[0]: 20, GENES[1]: 5}}
COVERAGE = {"TCGA-LUAD": 95}


def _json(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _filter_project(request: GDCRequest) -> str:
    params = dict(request.params)
    filters = json.loads(params["filters"])
    # The bounded request builders in gdc.endpoints always place project id strings here.
    return cast(str, filters["content"]["value"][0] if filters["op"] == "in"
                else filters["content"][0]["content"]["value"][0])


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
            "program": {"name": "TESTPROG"}, "primary_site": ["Lung"],
            "disease_type": ["Adenomas and Adenocarcinomas"],
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


def count_records(project_id: str) -> list[dict[str, Any]]:
    """One synthetic released occurrence per (gene, case) pair implied by ``COUNTS``.

    Distinct-case semantics are exactly the counts the legacy bucket fixture used
    to report: the corrected scan must derive the same counts without a bucket.
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


def ssm_occurrence_body(project_id: str, *, offset: int, size: int) -> bytes:
    records = count_records(project_id)
    page = records[offset:offset + size]
    pages = (len(records) + size - 1) // size if records else 0
    return _json({"data": {"hits": page, "pagination": {
        "total": len(records), "count": len(page), "size": size, "from": offset,
        "pages": pages}}})


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


def case_ids(project_id: str, projects: dict[str, int]) -> list[str]:
    return [f"{project_id}-case-{index:04d}" for index in range(projects[project_id])]


def cases_body(project_id: str, projects: dict[str, int], *, size: int, offset: int) -> bytes:
    all_ids = case_ids(project_id, projects)
    ids = all_ids[offset:offset + size]
    hits = [{"case_id": case_id, "submitter_id": case_id.upper(), "project": {"project_id": project_id},
             "samples": [{"sample_type": "Primary Tumor"}]} for case_id in ids]
    total = len(all_ids)
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": total,
                                                       "size": size, "from": offset,
                                                       "pages": (total + size - 1) // size}}})


def files_body(project_id: str) -> bytes:
    hits = [{"file_id": f"{project_id}-file-{index}", "access": "open",
             "analysis": {"workflow_type": "STAR - Counts"}, "experimental_strategy": "RNA-Seq"}
            for index in range(3)]
    return _json({"data": {"hits": hits, "pagination": {"count": len(hits), "total": len(hits),
                                                       "size": 5, "from": 0, "pages": 1}}})


def expression_workflow_facets_body(project_id: str) -> bytes:
    """Aggregate open-file facets for the expression workflow-coverage check."""
    files = PROJECTS.get(project_id, 0)
    return _json({"data": {
        "hits": [],
        "pagination": {"total": files, "count": 0, "size": 0, "from": 0, "pages": 0},
        "aggregations": {
            "access": {"buckets": [{"key": "open", "doc_count": files}]},
            "experimental_strategy": {"buckets": [{"key": "RNA-Seq", "doc_count": files}]},
            "analysis.workflow_type": {"buckets": [{"key": "STAR - Counts", "doc_count": files}]},
            "data_type": {"buckets": [{"key": "Gene Expression Quantification",
                                       "doc_count": files}]},
        },
    }})


def availability_body(case_ids_requested: list[str], gene_ids: list[str]) -> bytes:
    return _json({
        "cases": {
            "details": [{"case_id": case_id, "has_gene_expression_values": True}
                        for case_id in case_ids_requested],
            "with_gene_expression_count": len(case_ids_requested),
            "without_gene_expression_count": 0,
        },
        "genes": {
            "details": [{"gene_id": gene_id, "has_gene_expression_values": True}
                        for gene_id in gene_ids],
            "with_gene_expression_count": len(gene_ids),
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


class FixtureTransport:
    """Network-boundary fixture double: real artifacts, real provider shapes, no sockets."""

    def __init__(self, artifacts: ArtifactStore, run_id: str, *, repository: Any = None,
                 project_case_counts: dict[str, int] | None = None) -> None:
        self.artifacts = artifacts
        self.run_id = run_id
        self.repository = repository
        self.project_case_counts = project_case_counts or PROJECTS
        self.requests: list[GDCRequest] = []
        self.published: list[Any] = []
        self._counter = 0

    def _project_of(self, case_ids: list[str]) -> str:
        return case_ids[0].rsplit("-case-", 1)[0]

    def request(self, request: GDCRequest) -> GDCResponse:
        self.requests.append(request)
        self._counter += 1
        name = request.endpoint.name
        # The expression POST endpoints always carry a body built by gdc.endpoints.expression_*_request.
        request_body = cast(dict[str, Any], request.body)
        if name == "status":
            body = status_body()
        elif name == "projects":
            body = projects_body(self.project_case_counts, _filter_project(request))
        elif name == "top_mutated_genes_by_project":
            body = discovery_body(_filter_project(request))
        elif name == "mutated_cases_count_by_project":
            body = coverage_body()
        elif name == "ssm_occurrences":
            params = dict(request.params)
            body = ssm_occurrence_body(_filter_project(request), offset=int(params["from"]),
                                       size=int(params["size"]))
        elif name == "genes":
            body = genes_body()
        elif name == "cases":
            params = dict(request.params)
            body = cases_body(_filter_project(request), self.project_case_counts,
                              size=int(params["size"]), offset=int(params["from"]))
        elif name == "files":
            if "facets" in dict(request.params):
                body = expression_workflow_facets_body(_filter_project(request))
            else:
                body = files_body(_filter_project(request))
        elif name == "gene_expression_availability":
            body = availability_body(request_body["case_ids"], request_body["gene_ids"])
        elif name == "gene_expression_gene_selection":
            body = gene_selection_body(request_body["case_ids"], request_body["gene_ids"])
        elif name == "gene_expression_values":
            body = values_body(request_body["case_ids"], request_body["gene_ids"])
        else:  # pragma: no cover - guards against silent fixture drift
            raise AssertionError(f"fixture transport has no response for {name}")
        media = "text/tab-separated-values" if request.accept != "application/json" else "application/json"
        artifact = self.artifacts.publish(
            f"fixture/{self.run_id}/{name}-{self._counter}.body", body, media, "gdc-response",
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


class FixtureJevAdapter:
    """Deterministic offline Jev stand-in for the current question sets.

    Answers are a fixed, clearly labelled synthetic judgment: they exercise the
    same projection, validation, admission, deep-policy and hypothesis-review path
    as a live adapter, and the recorded model identity makes the substitution
    explicit. No network, no SDK and no provider credential.
    """

    def __init__(self, *, model: str) -> None:
        self.model = model
        self.calls = 0
        self.last_projection: dict[str, Any] | None = None

    def evaluate(self, projection: dict[str, Any],
                 definitions: tuple[QuestionDefinition, ...]) -> ProviderAnswerSet:
        self.calls += 1
        self.last_projection = projection
        version = projection.get("projection_version")
        if version == "jev-evidence-projection-v2":
            answers = self._deep_answers()
        elif version == "jev-hypothesis-projection-v2":
            answers = self._hypothesis_answers()
        else:
            answers = self._wide_answers(projection)
        return ProviderAnswerSet(
            requested_model=self.model,
            resolved_model=self.model,
            answers=answers,
            usage={"input_tokens": None, "output_tokens": None},
            latency_ms=0,
            request_id="fixture-jev-request",
        )

    def _deep_answers(self) -> dict[str, dict[str, Any]]:
        probabilities = {
            option: (0.88 if option == "NONE" else 0.12 / (len(DEEP_LIMITATION_ROSTER) - 1))
            for option in DEEP_LIMITATION_ROSTER
        }
        return {
            "revision_reliable": {"kind": "noul", "probability_yes": 0.90},
            "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": 0.70},
            "next_step_warranted": {"kind": "noul", "probability_yes": 0.20},
            "stopping_more_honest": {"kind": "noul", "probability_yes": 0.80},
            "dominant_limitation": {
                "kind": "choice", "choice": "NONE", "confidence": 0.88,
                "probabilities": probabilities,
            },
        }

    def _hypothesis_answers(self) -> dict[str, dict[str, Any]]:
        probabilities = {
            option: (0.70 if option == "NONE" else 0.30 / (len(HYPOTHESIS_UNSUPPORTED_ROSTER) - 1))
            for option in HYPOTHESIS_UNSUPPORTED_ROSTER
        }
        return {
            "hypothesis_testable": {"kind": "noul", "probability_yes": 0.80},
            "hypothesis_exceeds_recorded_evidence": {"kind": "noul", "probability_yes": 0.35},
            "hypothesis_dominant_unsupported_assumption": {
                "kind": "choice", "choice": "NONE", "confidence": 0.70, "probabilities": probabilities,
            },
        }

    def _wide_answers(self, projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
        cohort = projection.get("cohort", {})
        limitation = "COVERAGE" if cohort.get("coverage_imbalance") else "NONE"
        probabilities = {
            option: (0.88 if option == limitation else 0.12 / (len(LIMITATION_ROSTER) - 1))
            for option in LIMITATION_ROSTER
        }
        return {
            "evidence_quality_adequate": {"kind": "noul", "probability_yes": 0.85},
            "mutation_evidence_coherent": {"kind": "noul", "probability_yes": 0.82},
            "expression_evidence_coherent": {"kind": "noul", "probability_yes": 0.80},
            "signal_explained_by_coverage": {"kind": "noul", "probability_yes": 0.10},
            "unresolved_uncertainty_material": {"kind": "noul", "probability_yes": 0.85},
            "warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.90},
            "dominant_limitation": {
                "kind": "choice", "choice": limitation, "confidence": 0.88,
                "probabilities": probabilities,
            },
        }
