"""One short, durable director block; the supervisor owns its hard wall clock."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from cancerjev.domain.laboratory import (
    FINALIZATION_SECONDS,
    RUN_SECONDS,
    AcquisitionOffer,
    LabState,
)
from cancerjev.jev.service import JevService
from cancerjev.llm.ontocodex import Director, DirectorError
from cancerjev.research.laboratory import (
    apply_decision,
    compact_projection,
    coverage_summaries,
    evidence_summaries,
    json_bytes,
    load_lab,
    next_revision,
    prepare_lab_publication,
    save_lab,
    scientific_evidence_summary,
)
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository


class ContinueNextRun(RuntimeError):
    pass


@dataclass
class RunClock:
    seconds: float = RUN_SECONDS
    started: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if not math.isfinite(self.seconds) or not FINALIZATION_SECONDS < self.seconds <= RUN_SECONDS:
            raise ValueError("Research Run budget must fit the hard ceiling and finalization reserve")

    @property
    def remaining(self) -> float:
        return max(0.0, self.seconds - (time.monotonic() - self.started))

    def reserve(self, estimate: float) -> float:
        if not math.isfinite(estimate) or estimate <= 0:
            raise ValueError("operation estimate must be positive and finite")
        available = self.remaining - FINALIZATION_SECONDS
        if estimate > available:
            raise ContinueNextRun("operation cannot fit remaining Research Run")
        return available


class LabAcquisition(Protocol):
    def preflight(self, state: LabState, clock: RunClock) -> tuple[AcquisitionOffer, ...]: ...

    def execute(self, offer: AcquisitionOffer, clock: RunClock) -> tuple[str, ...]: ...

    def cleanup(self) -> dict[str, Any]: ...


def run_block(repository: Repository, artifacts: ArtifactStore, run_id: str,
              director: Director, acquisition: LabAcquisition, clock: RunClock,
              jev: JevService | None = None, *, comparative_jev: bool = False) -> LabState:
    state = load_lab(repository, artifacts)
    result = state
    timings: dict[str, float] = {}
    control: dict[str, Any] | None = None

    def event(kind: str, category: str, data: dict[str, Any]) -> None:
        repository.append_event(run_id, event_type=kind, idempotency_key=kind,
                                message=kind.replace("_", " ").capitalize() + ".",
                                data={"category": category, **data})

    try:
        started = time.monotonic()
        offers = acquisition.preflight(state, clock)
        timings["preflight_seconds"] = time.monotonic() - started
        projection = compact_projection(state, offers, clock.remaining)
        projection["evidence_summaries"] = evidence_summaries(repository, artifacts, state)
        projection["coverage_summaries"] = [group.model_dump(mode="json")
                                            for group in coverage_summaries(repository, artifacts, state)]
        event("LAB_ACQUISITION_PREFLIGHT", "operational", {"offers": projection["offers"]})
        eligible = tuple(offer for offer in offers
                         if offer.expected_bytes <= offer.maximum_bytes
                         and offer.estimated_seconds + FINALIZATION_SECONDS + 120 + 35 < clock.remaining)
        if jev is not None and eligible:
            clock.reserve(jev.settings.jev_timeout_seconds + 5)
            started = time.monotonic()
            # Experimental judgments are retained for paired evaluation, not
            # injected into the direct OntoCodex baseline decision.
            control = jev.evaluate_lab_control(run_id, state, eligible, comparative=comparative_jev)
            timings["jev_seconds"] = time.monotonic() - started
        started = time.monotonic()
        decision = director.decide(projection, timeout=min(120.0, clock.reserve(1)))
        timings["director_seconds"] = time.monotonic() - started
        clock.reserve(1)
        if decision.interpretation:
            from cancerjev.domain.codecs import read_cnv_shard_evidence

            question = next((q for q in state.questions if q.question_id == decision.question_id), None)
            for identity in decision.interpretation.evidence_ids:
                row = repository.artifact(identity)
                if identity not in state.evidence_ids or row is None:
                    raise ValueError("director cited unknown evidence")
                if row["purpose"] == "cnv-shard-evidence":
                    evidence = read_cnv_shard_evidence(artifacts.read(row["relative_path"], row["sha256"]))
                    project_id = evidence.project_id
                else:
                    project_id = scientific_evidence_summary(repository, artifacts, identity)["project_id"]
                if question is None or project_id != question.project_id:
                    raise ValueError("interpretation evidence belongs to another cohort")
        result = apply_decision(state, decision, offers)
        selected_offer = next((offer for offer in offers if offer.offer_id == decision.offer_id), None)
        artifact = artifacts.publish(f"runs/{run_id}/lab/decision.json", json_bytes({
            "identity": director.identity.model_dump(mode="json"),
            "projection": projection, "decision": decision.model_dump(mode="json"),
        }), "application/json", "ontocodex-decision")
        repository.append_event(
            run_id, event_type="ONTOCODEX_DECISION", idempotency_key="ontocodex:decision",
            message=decision.rationale,
            data={"category": "director", "action": decision.action,
                  "question_id": decision.question_id, "next_action": decision.next_action,
                  "capability": selected_offer.model_dump(mode="json") if selected_offer else None,
                  "jev_control": {"artifact_id": control["artifact_id"],
                                  "execution_mode": "SHADOW", "followed": None,
                                  "reason": "Experimental contract; OntoCodex decided without Jev answers."}
                  if control else None,
                  "identity": director.identity.model_dump(mode="json")},
            artifact_refs=[artifact.ref()],
            registrations=[repository.artifact_registration(artifact, run_id)],
        )
        if decision.action in {"ACQUIRE", "EXECUTE"}:
            offer = next(o for o in offers if o.offer_id == decision.offer_id)
            clock.reserve(offer.estimated_seconds)
            started = time.monotonic()
            evidence_ids = acquisition.execute(offer, clock)
            if not evidence_ids or set(evidence_ids).intersection(state.evidence_ids):
                raise ValueError("acquisition returned no new evidence")
            timings["acquisition_analysis_seconds"] = time.monotonic() - started
            # Publication through the canonical store is checked before control
            # references it. Model output cannot enter this path.
            deferred = False
            for evidence_id in evidence_ids:
                row = repository.artifact(evidence_id)
                if row is None or row["run_id"] != run_id:
                    raise ValueError("executor returned unregistered evidence")
                artifacts.read(row["relative_path"], row["sha256"], expected_size=row["size_bytes"])
                if row["purpose"] != "cnv-shard-evidence":
                    summary = scientific_evidence_summary(repository, artifacts, evidence_id)
                    if summary["project_id"] != offer.project_id:
                        raise ValueError("executor returned evidence for another cohort")
                    deferred = deferred or summary.get("status") == "DEFERRED"
            result = result.model_copy(update={
                "evidence_ids": tuple(dict.fromkeys((*result.evidence_ids, *evidence_ids))),
                "consecutive_no_progress": state.consecutive_no_progress + 1 if deferred else 0,
                "operational_state": "CONTINUE_NEXT_RUN" if deferred else "READY",
            })
    except DirectorError as exc:
        result = state.model_copy(update={"operational_state": "PROVIDER_UNAVAILABLE",
                                          "consecutive_no_progress": state.consecutive_no_progress + 1})
        event("ONTOCODEX_UNAVAILABLE", "operational", {"reason_code": str(exc)})
    except ContinueNextRun:
        result = state.model_copy(update={"operational_state": "CONTINUE_NEXT_RUN",
                                          "consecutive_no_progress": state.consecutive_no_progress + 1})
    except Exception as exc:
        event("LAB_OPERATION_FAILED", "operational", {
            "reason_code": str(getattr(exc, "code", type(exc).__name__)),
            "exception_type": type(exc).__name__,
        })
        cleanup = acquisition.cleanup()
        event("LAB_RAW_CLEANUP", "raw_data", cleanup)
        raise
    if result.consecutive_no_progress >= 3:
        result = result.model_copy(update={"operational_state": "NO_PROGRESS"})
    result = next_revision(repository, result, run_id)
    try:
        coverage = artifacts.publish(f"runs/{run_id}/lab/coverage.json", json_bytes({
            "method": "CNV_QUERY_COVERAGE_V1", "source_revision": result.revision,
            "groups": [group.model_dump(mode="json") for group in coverage_summaries(repository, artifacts, result)],
        }), "application/json", "lab-coverage")
        repository.register_artifact(coverage, run_id)
        artifacts.read(coverage.relative_path, coverage.sha256)
        prepare_lab_publication(repository, artifacts, run_id, result)
        save_lab(repository, artifacts, run_id, result)
    finally:
        started = time.monotonic()
        cleanup = acquisition.cleanup()
        timings["cleanup_seconds"] = time.monotonic() - started
        event("LAB_RAW_CLEANUP", "raw_data", cleanup)
    event("LAB_RUN_OUTCOME", "operational", {
        "outcome": result.operational_state, "revision": result.revision,
        "elapsed_seconds": clock.seconds - clock.remaining,
        "budget_seconds": clock.seconds, "timings": timings,
    })
    return result
