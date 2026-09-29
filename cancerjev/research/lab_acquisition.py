"""Preflighted, ephemeral CNV blocks over the canonical GDC/parser/science path."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import read_cnv_shard_evidence
from cancerjev.domain.events import utc_now
from cancerjev.domain.laboratory import AcquisitionOffer, LabState
from cancerjev.gdc.budget import PAGE_DEFECT_CEILING, REQUEST_DEFECT_CEILING
from cancerjev.gdc.endpoints import GDCRequest, cnv_occurrence_shard_page_request
from cancerjev.gdc.parsers import parse_cnv_occurrence_scan_page, parse_status
from cancerjev.gdc.transport import BudgetCaps, GDCResponse, GDCTransport, RunBudget
from cancerjev.research.acquisition import AcquisitionTransport, response_meta
from cancerjev.research.cnv_discovery import plan_cnv_case_shards, run_cnv_shard_scan
from cancerjev.research.lab_runtime import ContinueNextRun, RunClock
from cancerjev.research.laboratory import json_bytes
from cancerjev.research.specs import LUAD_RESEARCH_V1, CohortSpec, ResearchSpec
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.repositories import Repository

# Declared run control: the first live one-case metadata estimate was 17 MB.
# A 32 MiB allowance admits that bounded alternative under the 600 s ceiling.
SHARD_BYTES = 32 * 1024 * 1024
PREFLIGHT_BYTES = 2 * 1024 * 1024
INITIAL_BYTES_PER_SECOND = 64 * 1024.0
CNV_LAB_METHOD = "CNV_POSITIVE_CASE_SHARD_V1"
SHARD_SIZES = (1, 5, 25)
LAB_MAX_REQUESTS = 512
LAB_MAX_PAGES = 256


class ShardArtifactStore(ArtifactStore):
    def __init__(self, data_dir: Path, run_id: str):
        super().__init__(data_dir)
        self.run_id = run_id

    def publish(self, relative_path: str, content: bytes, media_type: str,
                purpose: str) -> PublishedArtifact:
        if purpose == "gdc-response":
            relative_path = f"shards/{self.run_id}/{uuid4().hex}.body"
        return super().publish(relative_path, content, media_type, purpose)


def cleanup_shard(repository: Repository, artifacts: ArtifactStore, run_id: str) -> dict[str, Any]:
    """Recoverable cleanup confined to this run; includes unregistered failed writes."""
    rows = repository.artifacts_for_run(run_id, purpose="gdc-response")
    selected = [row for row in rows if row["relative_path"].startswith(f"shards/{run_id}/")]
    repository.register_artifact_evictions(
        tuple((row["artifact_id"], row["size_bytes"]) for row in selected),
        policy_version="lab-ephemeral-shard-v1", evicted_at=utc_now())
    root = (artifacts.data_dir / "shards").resolve()
    target = (root / run_id).resolve()
    if target.parent != root or target == root:
        raise ValueError("invalid shard workspace")
    try:
        size = sum(path.stat().st_size for path in target.glob("*.body") if path.is_file())
        if target.exists():
            shutil.rmtree(target)
    except OSError:
        return {"status": "CLEANUP_FAILED", "run_id": run_id, "bytes_deleted": 0}
    return {"status": "CLEAN", "run_id": run_id, "bytes_deleted": size}


class DeadlineTransport:
    def __init__(self, transport: AcquisitionTransport, clock: RunClock):
        self.transport = transport
        self.clock = clock
        self.release: str | None = None
        self.expected_cases: tuple[str, ...] | None = None
        self.requests: list[dict[str, Any]] = []

    def request(self, request: GDCRequest) -> GDCResponse:
        self.clock.reserve(35)
        if self.expected_cases is not None and request.path == "/cnv_occurrences":
            filters = json.loads(dict(request.params)["filters"])
            cases = tuple(filters["content"][1]["content"]["value"])
            if cases != self.expected_cases:
                raise ValueError("acquisition differs from selected preflight cases")
        response = self.transport.request(request)
        self.requests.append({"method": request.method, "endpoint": request.path,
                              "params": dict(request.params), "body": request.body,
                              "request_hash": response.request_hash,
                              "response_hash": response.body_sha256,
                              "response_bytes": len(response.body),
                              "retrieved_at": response.retrieved_at})
        if request.path == "/status":
            release = parse_status(response.body, response_meta(response, None)).data_release
            if not release or (self.release and release != self.release):
                raise ValueError("GDC release unavailable or changed during Research Run")
            self.release = release
        self.clock.reserve(1)
        return response


def cohort_spec(project_id: str) -> ResearchSpec:
    return replace(LUAD_RESEARCH_V1, spec_id=f"LAB_{project_id}_CNV_V1",
                   cohort=CohortSpec(project_id, "lung cancer", project_id))


class CnvLabAcquisition:
    def __init__(self, repository: Repository, artifacts: ArtifactStore, run_id: str,
                 transport: AcquisitionTransport, clock: RunClock):
        self.repository, self.artifacts, self.run_id = repository, artifacts, run_id
        self.transport = DeadlineTransport(transport, clock)
        self.plans: dict[str, tuple[ResearchSpec, int, int, tuple[str, ...], int]] = {}

    @classmethod
    def live(cls, repository: Repository, artifacts: ArtifactStore, run_id: str,
             clock: RunClock) -> CnvLabAcquisition:
        shard_store = ShardArtifactStore(artifacts.data_dir, run_id)

        def emit(kind: str, key: str, message: str, **kwargs: Any) -> None:
            repository.append_event(run_id, event_type=kind, idempotency_key=key,
                                    message=message, **kwargs)

        transport = GDCTransport(repository, shard_store, RunBudget(BudgetCaps(
            max_requests=LAB_MAX_REQUESTS, max_pages_per_query=LAB_MAX_PAGES,
            max_bytes=PREFLIGHT_BYTES,
            per_response_bytes=5 * 1024 * 1024, max_retries=0,
        )), run_id, emit, cache_enabled=False)
        return cls(repository, artifacts, run_id, transport, clock)

    def preflight(self, state: LabState, clock: RunClock) -> tuple[AcquisitionOffer, ...]:
        acquired: dict[tuple[str, str], set[str]] = {}
        for identity in state.evidence_ids:
            row = self.repository.artifact(identity)
            if row and row["purpose"] == "cnv-shard-evidence":
                evidence = read_cnv_shard_evidence(self.artifacts.read(row["relative_path"], row["sha256"]))
                acquired.setdefault((evidence.project_id, evidence.release), set()).update(evidence.case_ids)
        offers: list[AcquisitionOffer] = []
        active = sorted((q for q in state.questions if q.status not in {"ANSWERED", "EXHAUSTED"}),
                        key=lambda q: (-q.priority, q.question_id))[:2]
        for question in active:
            spec = cohort_spec(question.project_id)
            singletons = plan_cnv_case_shards(self.transport, spec, case_shard_size=1)
            cohort = tuple(case for window in singletons for case in window)
            already = acquired.get((question.project_id, self.transport.release or ""), set())
            for size in SHARD_SIZES:
                windows = [cohort[index:index + size] for index in range(0, len(cohort), size)]
                available = next(((index, cases) for index, cases in enumerate(windows)
                                  if not already.intersection(cases)), None)
                if available is None:
                    continue
                index, cases = available
                response = self.transport.request(cnv_occurrence_shard_page_request(
                    question.project_id, list(cases), size=1))
                page = parse_cnv_occurrence_scan_page(
                    response.body, response_meta(response, self.transport.release),
                    expected_project=question.project_id, expected_cases=set(cases),
                    expected_offset=0, expected_size=1)
                expected = max(len(response.body), page.total * len(response.body) * 2)
                pages = math.ceil(page.total / spec.cnv_discovery.page_size)
                if pages > min(LAB_MAX_PAGES, PAGE_DEFECT_CEILING) or pages + 20 > min(LAB_MAX_REQUESTS, REQUEST_DEFECT_CEILING):
                    continue
                estimate = 15 + expected / INITIAL_BYTES_PER_SECOND + math.ceil(page.total / 250) * 2
                offer_id = hashlib.sha256(json_bytes({"question": question.question_id,
                    "release": self.transport.release, "cases": cases, "method": CNV_LAB_METHOD})).hexdigest()
                offers.append(AcquisitionOffer(
                    offer_id=offer_id, question_id=question.question_id,
                    project_id=question.project_id, method=CNV_LAB_METHOD, modality="CNV",
                    cases=cases, expected_bytes=expected, maximum_bytes=SHARD_BYTES,
                    estimated_seconds=estimate,
                    evidence_provided="Complete released positive CNV occurrences for these cases; exact-category case counts.",
                    limitations=("Absence is not a CNV-neutral observation.",
                                 "Caller compatibility is unverified; no clinical or causal inference.",
                                 "API bytes/time are estimates from one row, not file-size metadata."),
                ))
                self.plans[offer_id] = (spec, index, size, cohort, page.total)
        return tuple(offers)

    def execute(self, offer: AcquisitionOffer, clock: RunClock) -> tuple[str, ...]:
        if offer.offer_id not in self.plans:
            raise ValueError("unregistered acquisition offer")
        if offer.expected_bytes > offer.maximum_bytes:
            raise ContinueNextRun("selected operation exceeds temporary storage budget")
        clock.reserve(offer.estimated_seconds)
        spec, index, size, cohort, expected_records = self.plans[offer.offer_id]
        self.transport.expected_cases = offer.cases
        transport = self.transport.transport
        if isinstance(transport, GDCTransport):
            transport.budget.caps = replace(transport.budget.caps,
                max_bytes=transport.budget.bytes_read + offer.maximum_bytes)

        def emit(kind: str, key: str, message: str, **kwargs: Any) -> None:
            self.repository.append_event(self.run_id, event_type=kind, idempotency_key=key,
                                         message=message, **kwargs)

        evidence = run_cnv_shard_scan(self.run_id, self.transport, self.repository,
                                      self.artifacts, emit, spec, shard_index=index,
                                      case_shard_size=size, evict_raw=False)
        if (evidence.case_ids != offer.cases or evidence.cohort_case_ids != cohort
                or evidence.records != expected_records):
            raise ValueError("acquisition changed after preflight; result not admitted to portfolio")
        row = self.repository.artifact_at_path(f"runs/{self.run_id}/cnv-shards/shard-{index:04d}.json")
        if row is None:
            raise ValueError("derived evidence was not registered")
        read_cnv_shard_evidence(self.artifacts.read(row["relative_path"], row["sha256"]))
        provenance = self.artifacts.publish(f"runs/{self.run_id}/lab/acquisition.json", json_bytes({
            "offer": offer.model_dump(mode="json"), "release": evidence.release,
            "cohort_case_ids": cohort, "spec": spec.as_dict(),
            "evidence_id": row["artifact_id"], "evidence_sha256": row["sha256"],
            "requests": self.transport.requests,
        }), "application/json", "lab-acquisition")
        self.repository.register_artifact(provenance, self.run_id)
        self.artifacts.read(provenance.relative_path, provenance.sha256)
        return (str(row["artifact_id"]),)

    def cleanup(self) -> dict[str, Any]:
        return cleanup_shard(self.repository, self.artifacts, self.run_id)
