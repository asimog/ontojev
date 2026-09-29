"""Small adapters from director offers to the existing scientific lane executors.

These are bounded attempts at complete canonical lanes. A lane that exceeds the
declared budget remains incomplete; no prefix is published as a complete cohort.
The process supervisor is the hard wall-clock boundary, including local analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

from cancerjev.domain.codecs import read_cnv_shard_evidence
from cancerjev.domain.laboratory import (
    FINALIZATION_SECONDS,
    RUN_SECONDS,
    AcquisitionOffer,
    LabState,
)
from cancerjev.domain.measurements import digest
from cancerjev.gdc.endpoints import status_request
from cancerjev.gdc.transport import GDCTransport, TransportError
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import AcquisitionTransport
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.research.expression_discovery import run_expression_discovery
from cancerjev.research.lab_acquisition import (
    CNV_LAB_METHOD,
    LAB_MAX_REQUESTS,
    SHARD_BYTES,
    CnvLabAcquisition,
    cohort_spec,
)
from cancerjev.research.lab_runtime import ContinueNextRun, RunClock
from cancerjev.research.lab_stages import COMPOSE, INVESTIGATE, MERGE, WIDE, CampaignLabStages
from cancerjev.research.laboratory import json_bytes, scientific_evidence_summary
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

LANE_SECONDS = RUN_SECONDS - FINALIZATION_SECONDS
LANE_ESTIMATED_SECONDS = 240.0


@dataclass(frozen=True)
class ScientificCapability:
    method: str
    modality: str
    purpose: str
    result_purpose: str
    result_path: str


MUTATION = ScientificCapability(
    "CAMPAIGN_MUTATION_DISCOVERY_V1", "MUTATION",
    "Complete canonical mutation discovery and deterministic reduction.",
    "mutation-discovery-result", "discovery/result.json")
EXPRESSION = ScientificCapability(
    "CAMPAIGN_EXPRESSION_DISCOVERY_V1", "EXPRESSION",
    "Canonical expression discovery and genome-wide tail descriptors.",
    "expression-discovery-result", "expression-discovery/result.json")
CAPABILITIES = (MUTATION, EXPRESSION)


def capability_catalog() -> list[dict[str, Any]]:
    return [
        {"method": CNV_LAB_METHOD, "modality": "CNV", "status": "AVAILABLE",
         "description": "Complete positive CNV case shards; absence is not neutral."},
        *({"method": item.method, "modality": item.modality, "status": "AVAILABLE",
           "description": item.purpose,
           "limitation": "Whole-lane bounded attempt; oversized lanes require finer resumable units."}
          for item in CAPABILITIES),
        *({"method": method, "status": "AVAILABLE_WITH_VERIFIED_PREREQUISITES"}
          for method in (MERGE, COMPOSE, WIDE, INVESTIGATE)),
    ]


class ScientificLabCapabilities(CnvLabAcquisition):
    """One offer selection executes one canonical lane or one existing CNV shard."""

    def __init__(self, repository: Repository, artifacts: ArtifactStore, run_id: str,
                 transport: AcquisitionTransport, clock: RunClock, jev: JevService | None = None):
        super().__init__(repository, artifacts, run_id, transport, clock)
        self.stages = CampaignLabStages(repository, artifacts, run_id, jev, self.transport)

    def preflight(self, state: LabState, clock: RunClock) -> tuple[AcquisitionOffer, ...]:
        stage_offers = self.stages.preflight(state, clock)
        self.lane_offers: dict[str, AcquisitionOffer] = {}
        try:
            offers = list(super().preflight(state, clock))
        except TransportError as exc:
            if not stage_offers:
                raise
            # Verified historical evidence does not depend on today's GDC availability.
            self.repository.append_event(self.run_id, event_type="LAB_ACQUISITION_UNAVAILABLE",
                idempotency_key="lab:acquisition-unavailable", message="Only persisted-evidence operations are available.",
                data={"reason_code": exc.code})
            return stage_offers
        # The canonical CNV merge requires a single fixed case partition. Once
        # selected, expose only that partition's remaining windows in later runs.
        sizes: dict[tuple[str, str], set[int]] = {}
        for identity in state.evidence_ids:
            row = self.repository.artifact(identity)
            if row and row["purpose"] == "cnv-shard-evidence":
                shard = read_cnv_shard_evidence(self.artifacts.read(row["relative_path"], row["sha256"]))
                sizes.setdefault((shard.project_id, shard.release), set()).add(shard.case_shard_size)
        offers = [offer for offer in offers
                  if not (used := sizes.get((offer.project_id, self.transport.release or "")))
                  or used == {self.plans[offer.offer_id][2]}]
        offers.extend(stage_offers)
        questions = sorted((q for q in state.questions if q.status not in {"ANSWERED", "EXHAUSTED"}),
                           key=lambda q: (-q.priority, q.question_id))[:2]
        if not questions:
            return tuple(offers)
        if self.transport.release is None:
            self.transport.request(status_request())
        prior = []
        for identity in state.evidence_ids:
            row = self.repository.artifact(identity)
            if row and row["purpose"] in {item.result_purpose for item in CAPABILITIES}:
                prior.append(scientific_evidence_summary(self.repository, self.artifacts, identity))
        for question in questions:
            for capability in CAPABILITIES:
                if any(item["project_id"] == question.project_id
                       and item["release"] == self.transport.release
                       and item["modality"] == capability.modality for item in prior):
                    continue
                spec = cohort_spec(question.project_id)
                identity = digest({"question_id": question.question_id,
                                   "method": capability.method, "release": self.transport.release,
                                   "spec_hash": digest(spec.as_dict())})
                offer = AcquisitionOffer(
                    offer_id=identity, question_id=question.question_id,
                    project_id=question.project_id, method=capability.method,
                    modality=capability.modality, cases=(), expected_bytes=SHARD_BYTES,
                    maximum_bytes=SHARD_BYTES, estimated_seconds=LANE_ESTIMATED_SECONDS,
                    maximum_seconds=LANE_SECONDS, maximum_requests=LAB_MAX_REQUESTS,
                    expected_requests=None,
                    estimate_basis="DECLARED_ATTEMPT_ALLOWANCE: bytes are an upper bound; request count and completion time are unknown.",
                    coverage="COMPLETE_LANE_ONLY_IF_CANONICAL_EXECUTOR_COMPLETES",
                    evidence_provided=capability.purpose,
                    limitations=(
                        "Budget exhaustion is incomplete, never a smaller complete population.",
                        "This adapter does not yet checkpoint within a mutation or expression lane.",
                        "Computational investigation does not imply validated scientific claims.",
                    ),
                )
                self.lane_offers[identity] = offer
                offers.append(offer)
        return tuple(offers)

    def execute(self, offer: AcquisitionOffer, clock: RunClock) -> tuple[str, ...]:
        if offer.method == CNV_LAB_METHOD:
            return super().execute(offer, clock)
        if offer.method in {MERGE, COMPOSE, WIDE, INVESTIGATE}:
            if offer.method == INVESTIGATE and isinstance(transport := self.transport.transport, GDCTransport):
                transport.budget.caps = replace(transport.budget.caps,
                    max_bytes=transport.budget.bytes_read + offer.maximum_bytes,
                    max_requests=transport.budget.requests_started + offer.maximum_requests)
            result_ids = self.stages.execute(offer, clock)
            if offer.method == INVESTIGATE:
                provenance = self.artifacts.publish(f"runs/{self.run_id}/lab/investigation-acquisition.json",
                    json_bytes({"offer": offer.model_dump(mode="json"), "result_ids": result_ids,
                                "requests": self.transport.requests}),
                    "application/json", "lab-scientific-acquisition")
                self.repository.register_artifact(provenance, self.run_id)
                self.artifacts.read(provenance.relative_path, provenance.sha256)
            return result_ids
        selected = self.lane_offers.get(offer.offer_id)
        if selected != offer:
            raise ValueError("scientific execution requires an unchanged preflight offer")
        if offer.expected_bytes > offer.maximum_bytes:
            raise ContinueNextRun("scientific operation exceeds byte budget")
        available = clock.reserve(offer.estimated_seconds)
        self.transport.operation_deadline = time.monotonic() + min(available, offer.maximum_seconds)
        transport = self.transport.transport
        if isinstance(transport, GDCTransport):
            transport.budget.caps = replace(
                transport.budget.caps,
                max_bytes=transport.budget.bytes_read + offer.maximum_bytes,
                max_requests=transport.budget.requests_started + offer.maximum_requests)
        spec = cohort_spec(offer.project_id)
        release = self.transport.release

        def emit(kind: str, key: str, message: str, **kwargs: Any) -> None:
            self.repository.append_event(self.run_id, event_type=kind, idempotency_key=key,
                                         message=message, **kwargs)

        capability = next(item for item in CAPABILITIES if item.method == offer.method)
        started = time.monotonic()
        if capability == MUTATION:
            result = run_mutation_discovery(self.run_id, self.transport, self.repository,
                                           self.artifacts, emit, spec)
            observed_release = result.release
        else:
            expression = run_expression_discovery(self.run_id, self.transport, self.repository,
                                                  self.artifacts, emit, spec)
            observed_release = expression.release
        if observed_release != release:
            raise ValueError("scientific acquisition release changed after preflight")
        clock.reserve(1)
        if time.monotonic() >= self.transport.operation_deadline:
            raise ContinueNextRun("scientific operation exceeded its allowance")
        row = self.repository.artifact_at_path(f"runs/{self.run_id}/{capability.result_path}")
        if row is None or row["purpose"] != capability.result_purpose:
            raise ValueError("canonical scientific result was not registered")
        self.artifacts.read(row["relative_path"], row["sha256"], expected_size=row["size_bytes"])
        provenance = self.artifacts.publish(
            f"runs/{self.run_id}/lab/scientific-acquisition.json", json_bytes({
                "offer": offer.model_dump(mode="json"), "release": release,
                "spec": spec.as_dict(), "spec_hash": digest(spec.as_dict()),
                "evidence_id": row["artifact_id"], "evidence_sha256": row["sha256"],
                "requests": self.transport.requests,
                "elapsed_seconds": time.monotonic() - started,
            }), "application/json", "lab-scientific-acquisition")
        self.repository.register_artifact(provenance, self.run_id)
        scientific_evidence_summary(self.repository, self.artifacts, str(row["artifact_id"]))
        return (str(row["artifact_id"]),)
