"""Persistent Program portfolio using the existing run, event and artifact stores."""

from __future__ import annotations

import json
from typing import Any

from cancerjev.domain.laboratory import (
    AcquisitionOffer,
    CnvCoverageSummary,
    LabState,
    ResearchDecision,
)
from cancerjev.domain.measurements import digest
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
    elif decision.action in {"ACQUIRE", "EXECUTE"}:
        offer = next((o for o in offers if o.offer_id == decision.offer_id), None)
        if offer is None or offer.question_id != decision.question_id:
            raise ValueError("acquisition must select a current preflight offer")
        if questions[offer.question_id].status != "ACTIVE":
            raise ValueError("acquisition requires an active question")
        if offer.project_id != questions[offer.question_id].project_id:
            raise ValueError("offer belongs to a different cohort")
        questions[offer.question_id] = questions[offer.question_id].model_copy(
            update={"next_action": decision.next_action})
    elif decision.action == "STOP":
        changes["operational_state"] = "STOPPED"
    elif decision.question_id:
        question = questions[decision.question_id]
        update: dict[str, Any] = {"next_action": decision.next_action}
        if decision.interpretation:
            update["uncertainty"] = decision.interpretation.uncertainty
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
    progress = decision.action in {"CREATE_QUESTION", "STOP"}
    if decision.interpretation:
        reviewed = {identity for item in state.interpretations
                    if item.question_id == decision.question_id for identity in item.evidence_ids}
        progress = bool(set(decision.interpretation.evidence_ids) - reviewed)
    if decision.action in {"ANSWER", "EXHAUST"} and decision.question_id:
        previous = next(q for q in state.questions if q.question_id == decision.question_id)
        progress = progress or previous.status not in {"ANSWERED", "EXHAUSTED"}
    no_progress = 0 if progress else state.consecutive_no_progress + 1
    return result.model_copy(update={
        "consecutive_no_progress": no_progress,
        "operational_state": "NO_PROGRESS" if no_progress >= NO_PROGRESS_LIMIT
        else result.operational_state,
    })


def compact_projection(state: LabState, offers: tuple[AcquisitionOffer, ...],
                       remaining_seconds: float) -> dict[str, Any]:
    """No raw genomics, logs or repository content; priority is control only."""
    from cancerjev.research.lab_capabilities import capability_catalog

    return {
        "domain": state.domain, "revision": state.revision,
        "questions": [q.model_dump(mode="json") for q in state.questions],
        "interpretations": [i.model_dump(mode="json") for i in state.interpretations[-8:]],
        "evidence_ids": list(state.evidence_ids[-20:]),
        "offers": [{**o.model_dump(mode="json"),
                    "fits_current_run": o.expected_bytes <= o.maximum_bytes
                    and o.estimated_seconds <= o.maximum_seconds
                    and o.estimated_seconds + 20 < remaining_seconds} for o in offers],
        "remaining_seconds": remaining_seconds,
        "operational_state": state.operational_state,
        "consecutive_no_progress": state.consecutive_no_progress,
        "capabilities": capability_catalog(),
        "capability_gaps": ["Survival analysis, mutation co-occurrence and fusion analysis are not yet registered for bounded lab execution."],
    }


def evidence_summaries(repository: Repository, artifacts: ArtifactStore,
                       state: LabState) -> list[dict[str, Any]]:
    from cancerjev.domain.codecs import read_cnv_shard_evidence

    summaries: list[dict[str, Any]] = []
    for identity in state.evidence_ids[-20:]:
        row = repository.artifact(identity)
        if row is None:
            raise ValueError("portfolio contains unsupported evidence identity")
        if row["purpose"] != "cnv-shard-evidence":
            summaries.append(scientific_evidence_summary(repository, artifacts, identity))
            continue
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


def coverage_summaries(repository: Repository, artifacts: ArtifactStore,
                       state: LabState) -> tuple[CnvCoverageSummary, ...]:
    """Count disjoint complete queries from all retained derived evidence."""
    from cancerjev.domain.codecs import read_cnv_shard_evidence

    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for identity in state.evidence_ids:
        row = repository.artifact(identity)
        if row is None:
            raise ValueError("unsupported cumulative evidence")
        if row["purpose"] != "cnv-shard-evidence":
            scientific_evidence_summary(repository, artifacts, identity)
            continue
        repository.require_run_ownership(row["run_id"], ExecutionOwnership.SYSTEM_AUTONOMOUS)
        evidence = read_cnv_shard_evidence(artifacts.read(row["relative_path"], row["sha256"]))
        key = (evidence.project_id, evidence.release, evidence.spec_hash, digest(evidence.cohort_case_ids))
        group = groups.setdefault(key, {"cases": set(), "ids": [], "records": 0,
                                       "cohort_cases": len(evidence.cohort_case_ids)})
        if group["cases"].intersection(evidence.case_ids):
            raise ValueError("cumulative CNV evidence contains overlapping cases")
        group["cases"].update(evidence.case_ids)
        group["ids"].append(identity)
        group["records"] += evidence.records
    return tuple(CnvCoverageSummary(
        project_id=key[0], release=key[1], spec_hash=key[2], cohort_hash=key[3],
        evidence_ids=tuple(group["ids"]), queried_cases=len(group["cases"]),
        cohort_cases=group["cohort_cases"], positive_records=group["records"],
        coverage="COMPLETE_POSITIVE_QUERY" if len(group["cases"]) == group["cohort_cases"] else "PARTIAL",
    ) for key, group in sorted(groups.items()))


def next_revision(repository: Repository, state: LabState, run_id: str) -> LabState:
    previous = repository.artifact_at_path(
        f"runs/{state.last_run_id}/lab/portfolio.json") if state.last_run_id else None
    return state.model_copy(update={"revision": state.revision + 1,
                                    "previous_artifact_id": previous["artifact_id"] if previous else None,
                                    "last_run_id": run_id})


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def scientific_evidence_summary(repository: Repository, artifacts: ArtifactStore,
                                identity: str) -> dict[str, Any]:
    """Verify canonical lane artifacts before projecting derived facts to the director."""
    from cancerjev.domain.codecs import read_discovery, read_expression_discovery
    from cancerjev.research.lab_acquisition import cohort_spec
    from cancerjev.research.resumed_evidence import _require_current_methods

    row = repository.artifact(identity)
    if row is None:
        raise ValueError("unknown scientific evidence")
    if row["purpose"] == "lab-scientific-stage":
        from cancerjev.research.lab_stages import INVESTIGATE, WIDE, read_stage

        receipt = read_stage(repository, artifacts, identity)
        return {"evidence_id": identity, "project_id": receipt.project_id,
                "release": receipt.release, "method": receipt.method,
                "state_ids": list(receipt.state_ids), "candidate_ids": list(receipt.candidate_ids),
                "source_kind": ("SCIENTIFIC_RESULT_WITH_JUDGMENTS" if receipt.method == INVESTIGATE else
                                "JEV_SCIENTIFIC_JUDGMENT" if receipt.method == WIDE else "DETERMINISTIC_DERIVATION"),
                "limitations": ["Computational evidence retains its original maturity and limitations."]}
    repository.require_run_ownership(row["run_id"], ExecutionOwnership.SYSTEM_AUTONOMOUS)
    body = artifacts.read(row["relative_path"], row["sha256"], expected_size=row["size_bytes"])
    if row["purpose"] == "mutation-discovery-result":
        result = read_discovery(body)
        _require_current_methods("mutation", result)
        summary: dict[str, Any] = {"modality": "MUTATION", "genes": len(result.entries),
                                   "nominated_genes": len(result.survivor_ids)}
    elif row["purpose"] == "expression-discovery-result":
        expression = read_expression_discovery(body)
        _require_current_methods("expression", expression)
        summary = {"modality": "EXPRESSION", "genes": len(expression.entries),
                   "nominated_genes": len(expression.retained_ids),
                   "pending_semantic_review": len(expression.jev_review_ids)}
        result_scope = expression
    else:
        raise ValueError("unsupported scientific evidence")
    lane = result if row["purpose"] == "mutation-discovery-result" else result_scope
    spec = cohort_spec(lane.project_id)
    if (lane.spec_id, lane.cohort_id) != (spec.spec_id, spec.cohort.cohort_id):
        raise ValueError("scientific evidence scope mismatch")
    provenance_row = repository.artifact_at_path(f"runs/{row['run_id']}/lab/scientific-acquisition.json")
    if provenance_row is None:
        raise ValueError("scientific acquisition provenance missing")
    provenance = json.loads(artifacts.read(provenance_row["relative_path"], provenance_row["sha256"]))
    if (provenance["evidence_id"] != identity or provenance["evidence_sha256"] != row["sha256"]
            or provenance["spec_hash"] != digest(spec.as_dict())
            or provenance["release"] != lane.release):
        raise ValueError("scientific acquisition identity mismatch")
    return {"evidence_id": identity, "source_kind": "DETERMINISTIC_DERIVATION",
            "project_id": lane.project_id, "release": lane.release,
            "spec_id": lane.spec_id, "universe_complete": lane.universe.complete,
            "universe_membership_hash": lane.universe.membership_hash,
            "limitations": list(lane.limitations), **summary}
