"""Phase 3 wide evaluation: projections, real Jev calls, rankings, promotion.

Sequence is owned by research: projection per state, one Jev request per state,
fail-closed validation, deterministic rankings persisted for both the baseline
and the Jev policy, and bounded candidate promotion. Jev never queries GDC,
never selects rows, and never creates science facts.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.jev.projection import ProjectionError
from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PROMOTION_LIMIT,
    baseline_ranking,
    jev_ranking,
)


def run_wide_evaluation(orchestrator: Any, run_id: str, states: list[dict[str, Any]],
                        coverage: str) -> dict[str, Any]:
    orchestrator._event(
        run_id, "JEV_WIDE_STARTED", "jev:wide:started",
        f"Wide Jev evaluation started for {len(states)} states.",
        stage="JEV_WIDE", data={"states": len(states), "question_set": "wide-v2"},
    )
    evaluations: list[dict[str, Any]] = []
    deferred: list[str] = []
    for state in states:
        try:
            evaluation = orchestrator.jev_service.evaluate(run_id=run_id, state=state, emit=orchestrator._event)
        except ProjectionError as exc:
            deferred.append(state["state_id"])
            orchestrator._event(
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
    baseline_artifact = _publish_ranking(orchestrator, run_id, "baseline_ranking.json", baseline)
    jev = jev_ranking(states, evaluations)
    jev_artifact = _publish_ranking(orchestrator, run_id, "jev_ranking.json", jev)
    orchestrator._event(
        run_id, "WIDE_RANKING_COMPLETED", "jev:wide:ranking",
        f"Wide rankings recorded: {len(baseline['entries'])} baseline entries, {len(jev['entries'])} Jev entries.",
        stage="JEV_WIDE",
        data={
            "baseline_ranking_artifact_id": baseline_artifact.artifact_id,
            "baseline_policy_version": BASELINE_POLICY_VERSION,
            "jev_ranking_artifact_id": jev_artifact.artifact_id,
            "jev_policy_version": JEV_POLICY_VERSION,
            "admitted_state_ids": jev["admitted_state_ids"],
            "deferred_state_ids": deferred,
        },
        artifact_refs=[baseline_artifact.ref(), jev_artifact.ref()],
    )
    promoted = _promote(orchestrator, run_id, states, evaluations, jev)
    orchestrator._event(
        run_id, "JEV_WIDE_COMPLETED", "jev:wide:completed",
        f"Wide Jev evaluation completed: {len(evaluations)} evaluations, {len(promoted)} promoted.",
        stage="JEV_WIDE",
        data={
            "evaluations": len(evaluations), "deferred": len(deferred), "promoted": len(promoted),
            "coverage": coverage,
        },
    )
    return {"baseline": baseline, "jev": jev, "promoted": promoted}


def _publish_ranking(orchestrator: Any, run_id: str, filename: str, ranking: dict[str, Any]) -> Any:
    artifact = orchestrator._publish_json(
        run_id, f"runs/{run_id}/wide/{filename}", ranking, "wide-ranking",
    )
    orchestrator.repository.register_artifact(artifact, run_id)
    return artifact


def _promote(orchestrator: Any, run_id: str, states: list[dict[str, Any]],
             evaluations: list[dict[str, Any]], jev: dict[str, Any]) -> list[dict[str, Any]]:
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
            "promotion_reason": f"wide-policy-v1 rank {entry['rank']}",
            "policy_version": JEV_POLICY_VERSION,
            "wide_evaluation_id": evaluation["evaluation_id"],
            "dimensions": entry["dimensions"],
        }
        registration = (
            "INSERT INTO candidates(candidate_id,run_id,promotion_slot,status,current_stage,source_state_id,entity_json,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (candidate_id, run_id, slot, "WIDE_EVALUATED", "JEV_WIDE", state_id,
             canonical_json(state["entity"]).decode(), canonical_json(summary).decode(), now, now),
        )
        orchestrator._event(
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
