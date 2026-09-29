"""Artifact-bound continuation of the canonical Campaign, one stage per run."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from cancerjev.config import Settings
from cancerjev.domain.codecs import read_cnv_shard_evidence
from cancerjev.domain.laboratory import (
    AcquisitionOffer,
    CandidateRunBinding,
    LabState,
    ScientificArtifactRef,
    ScientificStageResult,
)
from cancerjev.domain.measurements import Acquisition, digest
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.domain.states import TERMINAL_CANDIDATE_STATUSES
from cancerjev.jev.service import JevService
from cancerjev.llm.openrouter import OpenRouterGenerator
from cancerjev.research.acquisition import AcquisitionTransport
from cancerjev.research.cnv_discovery import run_cnv_shard_merge, scope_cnv_scan_to_universe
from cancerjev.research.cutover import compose_discovery_states
from cancerjev.research.investigation import run_candidate_investigation
from cancerjev.research.lab_acquisition import SHARD_BYTES, cohort_spec
from cancerjev.research.lab_runtime import RunClock
from cancerjev.research.laboratory import json_bytes
from cancerjev.research.resumed_evidence import load_resumed_evidence
from cancerjev.research.seams import run_stage
from cancerjev.research.state_store import persist_state
from cancerjev.research.wide import (
    record_pre_wide_selection,
    run_wide_evaluation,
    select_pre_wide_states,
)
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.readers import (
    read_candidate_state,
    read_state_record,
    require_lab_candidate_binding,
)
from cancerjev.storage.repositories import Repository

MERGE = "CAMPAIGN_CNV_MERGE_V1"
COMPOSE = "CAMPAIGN_COMPOSE_V1"
WIDE = "CAMPAIGN_WIDE_V1"
INVESTIGATE = "CAMPAIGN_INVESTIGATE_V1"
# A declared pre-Wide ceiling uses the existing stratified policy, with exclusions retained.
LAB_WIDE_STATES = 4


def artifact_ref(repository: Repository, artifacts: ArtifactStore,
                 identity: str) -> ScientificArtifactRef:
    row = repository.artifact(identity)
    if row is None:
        raise ValueError("scientific continuation artifact missing")
    repository.require_run_ownership(row["run_id"], ExecutionOwnership.SYSTEM_AUTONOMOUS)
    artifacts.read(row["relative_path"], row["sha256"], expected_size=row["size_bytes"])
    return ScientificArtifactRef(artifact_id=identity, sha256=row["sha256"], purpose=row["purpose"])


def read_stage(repository: Repository, artifacts: ArtifactStore,
               identity: str) -> ScientificStageResult:
    ref = artifact_ref(repository, artifacts, identity)
    row = repository.artifact(identity)
    assert row is not None
    if ref.purpose != "lab-scientific-stage":
        raise ValueError("scientific continuation receipt required")
    result = ScientificStageResult.model_validate_json(artifacts.read(row["relative_path"], ref.sha256))
    if result.spec_hash != digest(cohort_spec(result.project_id).as_dict()):
        raise ValueError("scientific continuation spec changed")
    for expected in (*result.inputs, *result.outputs):
        if artifact_ref(repository, artifacts, expected.artifact_id) != expected:
            raise ValueError("scientific continuation artifact identity changed")
    for identity in result.state_ids:
        state = read_state_record(repository, artifacts, identity)
        if state.artifact.artifact_id not in {ref.artifact_id for ref in result.outputs}:
            raise ValueError("scientific continuation state binding mismatch")
        if state.state.research.project_id != result.project_id or state.state.entity.release != result.release:
            raise ValueError("scientific continuation state scope mismatch")
    return result


class CampaignLabStages:
    def __init__(self, repository: Repository, artifacts: ArtifactStore, run_id: str,
                 jev: JevService | None = None, transport: AcquisitionTransport | None = None):
        self.repository, self.artifacts, self.run_id = repository, artifacts, run_id
        self.jev = jev
        self.transport = transport
        self.offers: dict[str, AcquisitionOffer] = {}

    def preflight(self, state: LabState, clock: RunClock) -> tuple[AcquisitionOffer, ...]:
        receipts = {identity: read_stage(self.repository, self.artifacts, identity)
                    for identity in state.evidence_ids
                    if (row := self.repository.artifact(identity)) and row["purpose"] == "lab-scientific-stage"}
        offers = []
        for question in sorted((q for q in state.questions if q.status == "ACTIVE"),
                               key=lambda q: (-q.priority, q.question_id))[:2]:
            spec = cohort_spec(question.project_id)
            # Each release is a separate experiment; old and new observations never pool.
            lanes: dict[str, dict[str, str]] = {}
            shards: dict[tuple[str, int, tuple[str, ...]], list[tuple[int, str]]] = {}
            from cancerjev.research.laboratory import scientific_evidence_summary

            for identity in state.evidence_ids:
                row = self.repository.artifact(identity)
                if row is None:
                    raise ValueError("scientific input missing")
                if row["purpose"] in {"mutation-discovery-result", "expression-discovery-result"}:
                    summary = scientific_evidence_summary(self.repository, self.artifacts, identity)
                    if summary["project_id"] == question.project_id:
                        lanes.setdefault(summary["release"], {})[summary["modality"]] = identity
                elif row["purpose"] == "cnv-shard-evidence":
                    shard = read_cnv_shard_evidence(self.artifacts.read(row["relative_path"], row["sha256"]))
                    if shard.project_id == question.project_id and shard.spec_hash == digest(spec.as_dict()):
                        key = (shard.release, shard.case_shard_size, shard.cohort_case_ids)
                        shards.setdefault(key, []).append((shard.shard_index, identity))
            for (release, size, cohort), members in shards.items():
                needed = (len(cohort) + size - 1) // size
                ordered = sorted(members)
                if [index for index, _ in ordered] == list(range(needed)):
                    inputs = tuple(identity for _, identity in ordered)
                    if not any(r.method == MERGE and tuple(ref.artifact_id for ref in r.inputs) == inputs
                               for r in receipts.values()):
                        offers.append(self.offer(question.question_id, question.project_id, MERGE, release, inputs))
            for identity, receipt in receipts.items():
                if receipt.project_id != question.project_id:
                    continue
                if receipt.method == MERGE:
                    available = lanes.get(receipt.release, {})
                    if {"MUTATION", "EXPRESSION"} <= available.keys():
                        inputs = (available["MUTATION"], available["EXPRESSION"], identity)
                        if not any(r.method == COMPOSE and tuple(ref.artifact_id for ref in r.inputs) == inputs
                                   for r in receipts.values()):
                            offers.append(self.offer(question.question_id, question.project_id, COMPOSE, receipt.release, inputs))
                if receipt.method == COMPOSE and receipt.state_ids:
                    if not any(r.method == WIDE and tuple(ref.artifact_id for ref in r.inputs) == (identity,)
                               for r in receipts.values()):
                        offers.append(self.offer(question.question_id, question.project_id, WIDE, receipt.release, (identity,)))
                if receipt.method == WIDE:
                    if receipt.status == "DEFERRED" and not any(
                            r.method == WIDE and tuple(ref.artifact_id for ref in r.inputs) == (identity,)
                            for r in receipts.values()):
                        offers.append(self.offer(question.question_id, question.project_id,
                                                 WIDE, receipt.release, (identity,)))
                    for candidate_id in receipt.candidate_ids:
                        candidate = self.repository.get_candidate(candidate_id)
                        if candidate is None:
                            raise ValueError("Wide continuation Candidate missing")
                        if candidate["status"] not in TERMINAL_CANDIDATE_STATUSES:
                            offers.append(self.offer(question.question_id, question.project_id, INVESTIGATE,
                                                     receipt.release, (identity,), candidate_id))
        self.offers = {offer.offer_id: offer for offer in offers}
        return tuple(offers)

    def offer(self, question_id: str, project_id: Any, method: Any, release: str,
              inputs: tuple[str, ...], candidate_id: str | None = None) -> AcquisitionOffer:
        seconds = 300.0 if method in {WIDE, INVESTIGATE} else 60.0
        return AcquisitionOffer(
            offer_id=digest({"question": question_id, "method": method, "release": release,
                             "inputs": inputs, "candidate_id": candidate_id}),
            question_id=question_id, project_id=project_id, method=method,
            modality="MULTIMODAL" if method != MERGE else "CNV", cases=(),
            expected_bytes=SHARD_BYTES if method == INVESTIGATE else 0,
            maximum_bytes=SHARD_BYTES if method == INVESTIGATE else 1, estimated_seconds=seconds,
            expected_requests=None if method == INVESTIGATE else LAB_WIDE_STATES if method == WIDE else 0,
            evidence_provided={MERGE: "Merge complete canonical CNV case shards.",
                               COMPOSE: "Compose canonical StatisticalStates from verified complete lanes.",
                               WIDE: "Existing Wide Jev, stratified selection, and canonical Candidate admission.",
                               INVESTIGATE: "Canonical Candidate investigation, registered follow-ups, Deep and Stage 8 dossier."}[method],
            prerequisite_evidence_ids=inputs, coverage="VERIFIED_CANONICAL_INPUTS",
            candidate_id=candidate_id,
            limitations=("Experimental scientific maturity is retained.",
                         "Wide judgments are not measurements; excluded states remain unevaluated."),
        )

    def emit(self, run_id: str, kind: str, key: str, message: str, **kwargs: Any) -> None:
        self.repository.append_event(run_id, event_type=kind, idempotency_key=key,
                                     message=message, **kwargs)

    def publish(self, run_id: str, path: str, payload: object, purpose: str) -> PublishedArtifact:
        return self.artifacts.publish(path, payload if isinstance(payload, bytes) else json_bytes(payload),
                                      "application/json", purpose)

    def execute(self, offer: AcquisitionOffer, clock: RunClock) -> tuple[str, ...]:
        if self.offers.get(offer.offer_id) != offer:
            raise ValueError("stage requires an unchanged current offer")
        clock.reserve(offer.estimated_seconds)
        inputs = tuple(artifact_ref(self.repository, self.artifacts, identity)
                       for identity in offer.prerequisite_evidence_ids)
        for ref in inputs:
            row = self.repository.artifact(ref.artifact_id)
            assert row is not None
            source = self.repository.get_run(row["run_id"])
            if source is None or source["status"] not in {"COMPLETED", "FAILED", "STOPPED"}:
                raise ValueError("scientific continuation requires terminal source runs")
        spec = cohort_spec(offer.project_id)
        state_ids: tuple[str, ...] = ()
        candidate_ids: tuple[str, ...] = ()
        deferred_state_ids: tuple[str, ...] = ()
        output_ids: list[str] = []
        if offer.method == MERGE:
            rows = [self.repository.artifact(ref.artifact_id) for ref in inputs]
            assert rows and all(row is not None for row in rows)
            first = rows[0]
            assert first is not None
            shard = read_cnv_shard_evidence(self.artifacts.read(first["relative_path"], first["sha256"]))
            merged = run_cnv_shard_merge(
                self.run_id, self.repository, self.artifacts,
                lambda kind, key, message, **kw: self.emit(self.run_id, kind, key, message, **kw),
                spec, expected_shards=len(rows), case_shard_size=shard.case_shard_size,
                source_run_ids=tuple(row["run_id"] for row in rows if row is not None))
            release = merged.release
            row = self.repository.artifact_at_path(f"runs/{self.run_id}/cnv-discovery/project-scan-result.json")
            assert row is not None
            output_ids.append(row["artifact_id"])
        elif offer.method == COMPOSE:
            rows = [self.repository.artifact(ref.artifact_id) for ref in inputs[:2]]
            merged_receipt = read_stage(self.repository, self.artifacts, inputs[2].artifact_id)
            merged_row = self.repository.artifact(merged_receipt.outputs[0].artifact_id)
            assert rows[0] and rows[1] and merged_row
            resumed = load_resumed_evidence(repository=self.repository, artifacts=self.artifacts, spec=spec,
                                            mutation_run=rows[0]["run_id"], expression_run=rows[1]["run_id"],
                                            cnv_run=merged_row["run_id"])
            assert resumed.mutation and resumed.expression and resumed.cnv
            release = resumed.mutation.release
            cnv = scope_cnv_scan_to_universe(resumed.cnv, frozenset(resumed.mutation.universe.ordered_ids))
            states = compose_discovery_states(resumed.mutation, resumed.expression, cnv, spec)
            records = [persist_state(run_id=self.run_id, state=state, repository=self.repository,
                                     artifacts=self.artifacts, publish_json=self.publish, emit=self.emit,
                                     run_mode="LIVE") for state in states]
            state_ids = tuple(record.state_id for record in records)
            output_ids.extend(read_state_record(self.repository, self.artifacts, identity).artifact.artifact_id
                              for identity in state_ids)
        elif offer.method == WIDE:
            receipt = read_stage(self.repository, self.artifacts, inputs[0].artifact_id)
            release = receipt.release
            records = [read_state_record(self.repository, self.artifacts, identity).record
                       for identity in receipt.state_ids]
            selection = select_pre_wide_states(records, ceiling=LAB_WIDE_STATES)
            record_pre_wide_selection(run_id=self.run_id, selection=selection, repository=self.repository,
                                      publish_json=self.publish, emit=self.emit)
            # A fresh operational binding preserves the immutable scientific hash and
            # satisfies the existing Candidate/run identity contract.
            local = [persist_state(run_id=self.run_id, state=record.state, repository=self.repository,
                                   artifacts=self.artifacts, publish_json=self.publish, emit=self.emit,
                                   run_mode="LIVE") for record in selection.states]
            service = self.jev or JevService(Settings.from_env(), self.repository, self.artifacts)

            clock.reserve(len(local) * service.settings.jev_timeout_seconds + 10)
            wide = run_wide_evaluation(run_id=self.run_id, states=local,
                coverage="PARTIAL" if any(r.state.quality.acquisition != Acquisition.COMPLETE for r in local)
                else "COMPLETE_FOR_SCOPE", repository=self.repository, jev_service=service,
                emit=self.emit, publish_json=self.publish, require_complete=True)
            state_ids = tuple(record.state_id for record in local)
            candidate_ids = tuple(item["candidate_id"] for item in wide["promoted"])
            deferred_state_ids = tuple(wide["deferred_state_ids"])
            output_ids.extend(row["artifact_id"] for row in self.repository.artifacts_for_run(self.run_id)
                              if row["purpose"] in {"statistical-state", "wide-ranking", "pre-wide-selection"})
        elif offer.method == INVESTIGATE:
            receipt = read_stage(self.repository, self.artifacts, inputs[0].artifact_id)
            if offer.candidate_id not in receipt.candidate_ids:
                raise ValueError("Candidate is not admitted by the selected Wide result")
            assert offer.candidate_id is not None
            candidate = self.repository.get_candidate(offer.candidate_id)
            if candidate is None or candidate["status"] in TERMINAL_CANDIDATE_STATUSES:
                raise ValueError("Candidate is missing or already terminal")
            accepted = read_candidate_state(self.repository, self.artifacts, offer.candidate_id)
            binding = CandidateRunBinding(candidate_id=offer.candidate_id,
                source_run_id=accepted.run_id, source_state_id=accepted.state_id,
                source_state_hash=accepted.state_hash, wide_receipt=inputs[0])
            artifact = self.publish(self.run_id, f"runs/{self.run_id}/lab/candidate-binding.json",
                                    binding.model_dump(mode="json"), "lab-candidate-binding")
            self.repository.register_artifact(artifact, self.run_id)
            require_lab_candidate_binding(self.repository, self.artifacts, self.run_id, offer.candidate_id, accepted)
            service = self.jev or JevService(Settings.from_env(), self.repository, self.artifacts)
            generator = (OpenRouterGenerator(model=service.settings.llm_model,
                         timeout=min(service.settings.llm_timeout_seconds, clock.reserve(10)))
                         if os.getenv("OPENROUTER_API_KEY") and service.settings.llm_model else None)

            def stage[T](name: str, operation: Callable[[], T]) -> T:
                clock.reserve(service.settings.jev_timeout_seconds + 5 if name.startswith("JEV") else 10)
                return run_stage(self.emit, self.run_id, name, operation)

            def read_input(identity: str) -> bytes | None:
                row = self.repository.artifact(identity)
                if row is None:
                    return None
                try:
                    return self.artifacts.read(row["relative_path"], row["sha256"])
                except OSError:
                    return None

            investigation = run_candidate_investigation(
                run_id=self.run_id, candidate=candidate, selection="ONTOCODEX_PREFLIGHT_CHOICE",
                repository=self.repository, artifacts=self.artifacts, emit=self.emit,
                publish_json=self.publish, read_artifact=read_input, stage=stage,
                jev_service=service, authorize_iteration=True, hypotheses_requested=True,
                llm_generator=generator,
                transport=self.transport, mode="LIVE", authorized_by="ontocodex-lab-v1")
            if investigation.candidate_status != "CANDIDATE_COMPLETE":
                raise ValueError("Candidate investigation did not finalize")
            release = receipt.release
            candidate_ids = (offer.candidate_id,)
            output_ids.extend(row["artifact_id"] for row in self.repository.artifacts_for_run(self.run_id)
                              if row["purpose"] in {"evidence-state", "authoritative-dossier", "final-candidate-result"})
        else:
            raise ValueError("unregistered scientific stage")
        clock.reserve(1)
        result = ScientificStageResult.model_validate(dict(
            method=offer.method, question_id=offer.question_id, project_id=offer.project_id,
            spec_hash=digest(spec.as_dict()), release=release, inputs=inputs,
            outputs=tuple(artifact_ref(self.repository, self.artifacts, identity) for identity in output_ids),
            state_ids=state_ids, candidate_ids=candidate_ids,
            status="DEFERRED" if deferred_state_ids else "COMPLETE",
            deferred_state_ids=deferred_state_ids))
        artifact = self.publish(self.run_id, f"runs/{self.run_id}/lab/scientific-stage.json",
                                result.model_dump(mode="json"), "lab-scientific-stage")
        self.repository.register_artifact(artifact, self.run_id)
        read_stage(self.repository, self.artifacts, artifact.artifact_id)
        return (artifact.artifact_id,)
