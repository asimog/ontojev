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
from cancerjev.llm.ontocodex import Director, DirectorError
from cancerjev.research.laboratory import (
    apply_decision,
    compact_projection,
    json_bytes,
    load_lab,
    next_revision,
    save_lab,
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
              director: Director, acquisition: LabAcquisition, clock: RunClock) -> LabState:
    state = load_lab(repository, artifacts)
    result = state
    timings: dict[str, float] = {}

    def event(kind: str, category: str, data: dict[str, Any]) -> None:
        repository.append_event(run_id, event_type=kind, idempotency_key=kind,
                                message=kind.replace("_", " ").capitalize() + ".",
                                data={"category": category, **data})

    try:
        started = time.monotonic()
        offers = acquisition.preflight(state, clock)
        timings["preflight_seconds"] = time.monotonic() - started
        projection = compact_projection(state, offers, clock.remaining)
        event("LAB_ACQUISITION_PREFLIGHT", "operational", {"offers": projection["offers"]})
        started = time.monotonic()
        decision = director.decide(projection, timeout=min(120.0, clock.reserve(1)))
        timings["director_seconds"] = time.monotonic() - started
        clock.reserve(1)
        result = apply_decision(state, decision, offers)
        artifact = artifacts.publish(f"runs/{run_id}/lab/decision.json", json_bytes({
            "identity": director.identity.model_dump(mode="json"),
            "projection": projection, "decision": decision.model_dump(mode="json"),
        }), "application/json", "ontocodex-decision")
        repository.append_event(
            run_id, event_type="ONTOCODEX_DECISION", idempotency_key="ontocodex:decision",
            message=decision.rationale,
            data={"category": "director", "action": decision.action,
                  "question_id": decision.question_id, "next_action": decision.next_action,
                  "identity": director.identity.model_dump(mode="json")},
            artifact_refs=[artifact.ref()],
            registrations=[repository.artifact_registration(artifact, run_id)],
        )
        if decision.action == "ACQUIRE":
            offer = next(o for o in offers if o.offer_id == decision.offer_id)
            clock.reserve(offer.estimated_seconds)
            started = time.monotonic()
            evidence_ids = acquisition.execute(offer, clock)
            timings["acquisition_analysis_seconds"] = time.monotonic() - started
            # Publication through the canonical store is checked before control
            # references it. Model output cannot enter this path.
            for evidence_id in evidence_ids:
                row = repository.artifact(evidence_id)
                if row is None or row["run_id"] != run_id:
                    raise ValueError("executor returned unregistered evidence")
                artifacts.read(row["relative_path"], row["sha256"], expected_size=row["size_bytes"])
            result = result.model_copy(update={
                "evidence_ids": tuple(dict.fromkeys((*result.evidence_ids, *evidence_ids))),
                "consecutive_no_progress": 0,
            })
    except DirectorError as exc:
        result = state.model_copy(update={"operational_state": "PROVIDER_UNAVAILABLE",
                                          "consecutive_no_progress": state.consecutive_no_progress + 1})
        event("ONTOCODEX_UNAVAILABLE", "operational", {"reason_code": str(exc)})
    except ContinueNextRun:
        result = state.model_copy(update={"operational_state": "CONTINUE_NEXT_RUN",
                                          "consecutive_no_progress": state.consecutive_no_progress + 1})
    finally:
        started = time.monotonic()
        cleanup = acquisition.cleanup()
        timings["cleanup_seconds"] = time.monotonic() - started
        event("LAB_RAW_CLEANUP", "raw_data", cleanup)
    if result.consecutive_no_progress >= 3:
        result = result.model_copy(update={"operational_state": "NO_PROGRESS"})
    result = next_revision(repository, result, run_id)
    save_lab(repository, artifacts, run_id, result)
    event("LAB_RUN_OUTCOME", "operational", {
        "outcome": result.operational_state, "revision": result.revision,
        "elapsed_seconds": clock.seconds - clock.remaining,
        "budget_seconds": clock.seconds, "timings": timings,
    })
    return result
