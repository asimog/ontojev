"""Persistent Program portfolio using the existing run, event and artifact stores."""

from __future__ import annotations

import json
from typing import Any

from cancerjev.domain.laboratory import AcquisitionOffer, LabState, ResearchDecision
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

LAB_STATE_PURPOSE = "research-portfolio"
NO_PROGRESS_LIMIT = 3


def load_lab(repository: Repository, artifacts: ArtifactStore) -> LabState:
    row = repository.latest_artifact_by_purpose(
        LAB_STATE_PURPOSE, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    if row is None:
        return LabState()
    return LabState.model_validate_json(artifacts.read(
        row["relative_path"], row["sha256"], expected_size=row["size_bytes"]))


def save_lab(repository: Repository, artifacts: ArtifactStore, run_id: str,
             state: LabState) -> str:
    repository.require_run_ownership(run_id, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    current = load_lab(repository, artifacts)
    if state.revision != current.revision + 1:
        raise ValueError("stale portfolio revision")
    previous = None
    if current.last_run_id:
        previous = repository.artifact_at_path(f"runs/{current.last_run_id}/lab/portfolio.json")
    previous_id = previous["artifact_id"] if previous else None
    if state.previous_artifact_id != previous_id or state.last_run_id != run_id:
        raise ValueError("portfolio predecessor/run mismatch")
    artifact = artifacts.publish(f"runs/{run_id}/lab/portfolio.json",
                                 state.model_dump_json().encode(), "application/json",
                                 LAB_STATE_PURPOSE)
    repository.append_event(
        run_id, event_type="LAB_PORTFOLIO_REVISED", idempotency_key="lab:portfolio",
        message="Research portfolio revision committed.",
        data={"category": "director", "revision": state.revision,
              "operational_state": state.operational_state}, artifact_refs=[artifact.ref()],
        registrations=[repository.artifact_registration(artifact, run_id)],
    )
    # Read through the registered identity before callers can dispose of inputs.
    LabState.model_validate_json(artifacts.read(artifact.relative_path, artifact.sha256))
    return artifact.artifact_id


def apply_decision(state: LabState, decision: ResearchDecision,
                   offers: tuple[AcquisitionOffer, ...] = ()) -> LabState:
    """Pure control transition. Acquisition evidence is added only by Python executors."""
    questions = {q.question_id: q for q in state.questions}
    if decision.question_id is not None and decision.question_id not in questions:
        raise ValueError("unknown question")
    if decision.interpretation:
        if not set(decision.interpretation.evidence_ids) <= set(state.evidence_ids):
            raise ValueError("director cited unknown evidence")
    changes: dict[str, Any] = {"operational_state": "READY"}
    if decision.action == "CREATE_QUESTION":
        assert decision.question is not None
        if decision.question.question_id in questions:
            raise ValueError("question identity already exists")
        if decision.question.status != "ACTIVE":
            raise ValueError("new question must be active")
        questions[decision.question.question_id] = decision.question
    elif decision.action == "ACQUIRE":
        offer = next((o for o in offers if o.offer_id == decision.offer_id), None)
        if offer is None or offer.question_id != decision.question_id:
            raise ValueError("acquisition must select a current preflight offer")
        if questions[offer.question_id].status != "ACTIVE":
            raise ValueError("acquisition requires an active question")
        if offer.project_id != questions[offer.question_id].project_id:
            raise ValueError("offer belongs to a different cohort")
    elif decision.action == "STOP":
        changes["operational_state"] = "STOPPED"
    elif decision.question_id:
        question = questions[decision.question_id]
        update: dict[str, Any] = {"next_action": decision.next_action}
        if decision.action == "PRIORITIZE":
            update.update(priority=decision.priority, status="ACTIVE")
        status = {"DEFER": "DEFERRED", "ANSWER": "ANSWERED", "EXHAUST": "EXHAUSTED",
                  "CAPABILITY_GAP": "CAPABILITY_GAP"}.get(decision.action)
        if status:
            update["status"] = status
        if decision.action == "CAPABILITY_GAP":
            changes["operational_state"] = "CAPABILITY_GAP"
        questions[question.question_id] = question.model_copy(update=update)
    changes["questions"] = tuple(questions.values())
    if decision.interpretation:
        changes["interpretations"] = (*state.interpretations, decision.interpretation)
    result = LabState.model_validate({**state.model_dump(), **changes})
    unchanged = result == state
    no_progress = state.consecutive_no_progress + 1 if unchanged else 0
    return result.model_copy(update={
        "consecutive_no_progress": no_progress,
        "operational_state": "NO_PROGRESS" if no_progress >= NO_PROGRESS_LIMIT
        else result.operational_state,
    })


def compact_projection(state: LabState, offers: tuple[AcquisitionOffer, ...],
                       remaining_seconds: float) -> dict[str, Any]:
    """No raw genomics, logs or repository content; priority is control only."""
    return {
        "domain": state.domain, "revision": state.revision,
        "questions": [q.model_dump(mode="json") for q in state.questions],
        "interpretations": [i.model_dump(mode="json") for i in state.interpretations[-8:]],
        "evidence_ids": list(state.evidence_ids[-20:]),
        "offers": [o.model_dump(mode="json") for o in offers],
        "remaining_seconds": remaining_seconds,
        "operational_state": state.operational_state,
        "capabilities": [{"method": "CNV_POSITIVE_CASE_SHARD_V1", "status": "AVAILABLE",
                          "description": "Descriptive exact-category CNV counts over complete positive occurrence case shards. Missing calls are not neutral."}],
        "capability_gaps": ["Survival analysis, mutation co-occurrence and fusion analysis are not yet registered for bounded lab execution."],
    }


def evidence_summaries(repository: Repository, artifacts: ArtifactStore,
                       state: LabState) -> list[dict[str, Any]]:
    from cancerjev.domain.codecs import read_cnv_shard_evidence

    summaries: list[dict[str, Any]] = []
    for identity in state.evidence_ids[-20:]:
        row = repository.artifact(identity)
        if row is None or row["purpose"] != "cnv-shard-evidence":
            raise ValueError("portfolio contains unsupported evidence identity")
        evidence = read_cnv_shard_evidence(artifacts.read(row["relative_path"], row["sha256"]))
        genes = sorted(evidence.genes, key=lambda gene: (-gene.records, gene.gene_id))[:8]
        summaries.append({
            "evidence_id": identity, "source_kind": "DETERMINISTIC_DERIVATION",
            "project_id": evidence.project_id, "release": evidence.release,
            "case_count": len(evidence.case_ids), "cohort_case_count": len(evidence.cohort_case_ids),
            "positive_records": evidence.records, "genes_with_positive_records": len(evidence.genes),
            "genes_shown": [{"gene_id": gene.gene_id,
                "categories": [{"category": c.raw_category, "cases": len(c.case_ids)} for c in gene.categories],
                "conflicting_cases": len(gene.conflicting_case_ids)} for gene in genes],
            "projection_selection": "At most 8 genes, ordered by positive record count; descriptive, not a significance ranking.",
            "limitations": ["Absence is not CNV neutral.", "Caller compatibility is unverified.",
                            "Shard evidence is not complete-cohort evidence."],
        })
    return summaries


def next_revision(repository: Repository, state: LabState, run_id: str) -> LabState:
    previous = repository.artifact_at_path(
        f"runs/{state.last_run_id}/lab/portfolio.json") if state.last_run_id else None
    return state.model_copy(update={"revision": state.revision + 1,
                                    "previous_artifact_id": previous["artifact_id"] if previous else None,
                                    "last_run_id": run_id})


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
