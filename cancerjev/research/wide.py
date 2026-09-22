"""Phase 3 wide evaluation: projections, real Jev calls, rankings, promotion.

Sequence is owned by research: projection per state, one Jev request per state,
fail-closed validation, deterministic rankings persisted for both the baseline
and the Jev policy, and bounded candidate promotion. Jev never queries GDC,
never selects rows, and never creates science facts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.jev.projection import ProjectionError
from cancerjev.jev.questions import WIDE_QUESTION_SET_VERSION
from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PROMOTION_LIMIT,
    baseline_ranking,
    jev_ranking,
)
from cancerjev.storage.repositories import Repository


def run_wide_evaluation(*, run_id: str, states: list[dict[str, Any]], coverage: str,
                        repository: Repository, jev_service: Any, emit: Callable[..., Any],
                        publish_json: Callable[[str, str, Any, str], Any],
                        max_states: int | None = None) -> dict[str, Any]:
    emit(
        run_id, "JEV_WIDE_STARTED", "jev:wide:started",
        f"Wide Jev evaluation started for {len(states)} states.",
        stage="JEV_WIDE", data={"states": len(states), "question_set": WIDE_QUESTION_SET_VERSION,
                                "max_states": max_states},
    )
    evaluated_states = states
    skipped_state_ids: list[str] = []
    if max_states is not None and len(states) > max_states:
        evaluated_states = states[:max_states]
        skipped_state_ids = [state["state_id"] for state in states[max_states:]]
        emit(
            run_id, "JEV_WIDE_STATE_CAP_ENFORCED", "jev:wide:state-cap",
            f"Configured Jev state cap {max_states} enforced; {len(skipped_state_ids)} state(s) not evaluated.",
            stage="JEV_WIDE", level="warning",
            data={"cap": max_states, "requested_states": len(states),
                  "evaluated_states": len(evaluated_states), "skipped_state_ids": skipped_state_ids},
        )
    evaluations: list[dict[str, Any]] = []
    deferred: list[str] = []
    for state in evaluated_states:
        try:
            evaluation = jev_service.evaluate(run_id=run_id, state=state, emit=emit)
        except ProjectionError as exc:
            deferred.append(state["state_id"])
            emit(
                run_id, "JEV_EVALUATION_FAILED", f"jev-wide:{state['state_id']}:projection-failed",
                f"Jev projection failed closed for {state['entity']['gene_symbol']}: {exc.code}.",
                stage="JEV_WIDE", level="error",
                data={"state_id": state["state_id"], "error_code": exc.code, "detail": str(exc),
                      "provider_attempted": False, "cache": False},
            )
            continue
        if evaluation.get("error") is not None:
            deferred.append(state["state_id"])
        evaluations.append(evaluation)

    baseline = baseline_ranking(states)
    baseline_artifact = _publish_ranking(run_id, "baseline_ranking.json", baseline, publish_json, repository)
    jev = jev_ranking(states, evaluations)
    jev_artifact = _publish_ranking(run_id, "jev_ranking.json", jev, publish_json, repository)
    emit(
        run_id, "WIDE_RANKING_COMPLETED", "jev:wide:ranking",
        f"Wide rankings recorded: {len(baseline['entries'])} baseline entries, {len(jev['entries'])} Jev entries.",
        stage="JEV_WIDE",
        data={
            "baseline_ranking_artifact_id": baseline_artifact.artifact_id,
            "baseline_policy_version": BASELINE_POLICY_VERSION,
            "jev_ranking_artifact_id": jev_artifact.artifact_id,
            "jev_policy_version": JEV_POLICY_VERSION,
            "admitted_state_ids": jev["admitted_state_ids"],
            "admission_decision": jev["admission"]["decision"],
            "admission_thresholds": jev["admission"]["thresholds"],
            "promotion_limit": jev["admission"]["promotion_limit"],
            "deferred_state_ids": deferred,
        },
        artifact_refs=[baseline_artifact.ref(), jev_artifact.ref()],
    )
    promoted = _promote(run_id, states, evaluations, jev, emit)
    emit(
        run_id, "JEV_WIDE_COMPLETED", "jev:wide:completed",
        f"Wide Jev evaluation completed: {len(evaluations)} evaluations, admission {jev['admission']['decision']}, "
        f"{len(promoted)} promoted.",
        stage="JEV_WIDE",
data={
            "evaluations": len(evaluations), "deferred": len(deferred), "promoted": len(promoted),
            "coverage": coverage, "admission_decision": jev["admission"]["decision"],
            "promotion_limit": jev["admission"]["promotion_limit"],
            "skipped_states": len(skipped_state_ids),
        },
    )
    return {"baseline": baseline, "jev": jev, "promoted": promoted}


def _publish_ranking(run_id: str, filename: str, ranking: dict[str, Any],
                     publish_json: Callable[[str, str, Any, str], Any], repository: Repository) -> Any:
    artifact = publish_json(run_id, f"runs/{run_id}/wide/{filename}", ranking, "wide-ranking")
    repository.register_artifact(artifact, run_id)
    return artifact


def _promote(run_id: str, states: list[dict[str, Any]], evaluations: list[dict[str, Any]],
             jev: dict[str, Any], emit: Callable[..., Any]) -> list[dict[str, Any]]:
    by_state = {state["state_id"]: state for state in states}
    by_evaluation = {evaluation["input_ref_id"]: evaluation for evaluation in evaluations}
    promoted: list[dict[str, Any]] = []
    for slot, state_id in enumerate(jev["admitted_state_ids"][:PROMOTION_LIMIT], start=1):
        state = by_state.get(state_id)
        evaluation = by_evaluation.get(state_id)
        if state is None or evaluation is None or evaluation.get("error") is not None:
            continue
        entry = next(entry for entry in jev["entries"] if entry["state_id"] == state_id)
        candidate_id = str(uuid4())
        now = utc_now()
        summary = {
            "promotion_reason": f"wide-policy-v2 rank {entry['rank']}",
            "policy_version": JEV_POLICY_VERSION,
            "wide_evaluation_id": evaluation["evaluation_id"],
            "dimensions": entry["dimensions"],
        }
        registration = (
            "INSERT INTO candidates(candidate_id,run_id,promotion_slot,status,current_stage,source_state_id,entity_json,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (candidate_id, run_id, slot, "WIDE_EVALUATED", "JEV_WIDE", state_id,
             canonical_json(state["entity"]).decode(), canonical_json(summary).decode(), now, now),
        )
        emit(
            run_id, "CANDIDATE_PROMOTED", f"candidate:{slot}:promoted",
            f"Promoted {state['entity']['gene_symbol']} into slot {slot} from the wide Jev ranking.",
            stage="JEV_WIDE", candidate_id=candidate_id,
            data={"candidate_id": candidate_id, "source_state_id": state_id,
                  "evaluation_id": evaluation["evaluation_id"], "promotion_slot": slot,
                  "policy_version": JEV_POLICY_VERSION, "reason": summary["promotion_reason"],
                  "dimensions": entry["dimensions"]},
            registrations=[registration],
        )
        promoted.append({"candidate_id": candidate_id, "state_id": state_id, "slot": slot,
                         "evaluation_id": evaluation["evaluation_id"]})
    return promoted
