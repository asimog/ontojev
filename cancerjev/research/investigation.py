"""One candidate's bounded deterministic investigation arc (Phase 4 completion).

Python owns the sequence: accept the candidate's evidence as E0, run the selected
registered action, judge the new revision, and while the recorded move is
`FOLLOW_UP`, an explicit authorization is in force and both caps allow it, dispatch
the next distinct eligible action and judge again. When the policy asks for
hypotheses and the operator authorized iteration, bounded statement generation and
its Jev review run; then the candidate's dossier is recorded.

Jev judges; Python decides, executes, caps and stops. Every judgment, decision,
dispatch and refusal is already recorded by the steps this module composes, so this
arc adds no new event type and no new side effect of its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

from cancerjev.jev.service import JevService
from cancerjev.research.deep import (
    FOLLOWUP_LIMIT,
    FollowUpResult,
    dispatch_recorded_move,
    execute_followup,
    judge_evidence_revision,
    plan_deep_slice,
)
from cancerjev.research.dossier import run_dossier_stage
from cancerjev.research.hypotheses import run_hypothesis_stage
from cancerjev.research.seams import HypothesisGenerator, PublishJson, StageRunner
from cancerjev.science.actions import eligible_actions
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository


@dataclass(frozen=True)
class CandidateInvestigation:
    candidate_id: str
    selection: str
    status: str
    final_move: str | None
    stop_reason: str
    steps: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]
    error_code: str | None
    hypothesis: dict[str, Any] | None
    dossier: dict[str, Any] | None

    def summary(self) -> dict[str, Any]:
        first = self.steps[0] if self.steps else {}
        last_dispatch = self.steps[-1].get("dispatch") if self.steps else None
        return {
            "selection": self.selection, "candidate_id": self.candidate_id, "status": self.status,
            "final_move": self.final_move, "stop_reason": self.stop_reason,
            "error_code": self.error_code,
            "first_step": first,
            "steps": list(self.steps),
            "dispatch": first.get("dispatch"),
            "last_dispatch": last_dispatch,
            "decisions": list(self.decisions),
            "hypothesis": self.hypothesis,
            "dossier": self.dossier,
        }


def _step_summary(result: FollowUpResult, judgement: dict[str, Any] | None) -> dict[str, Any]:
    judgement = judgement or {}
    return {
        "action_id": result.action_id, "evidence_state_id": result.evidence_state_id,
        "evidence_hash": result.evidence_hash, "iteration": result.iteration,
        "checks_total": result.checks_total, "checks_verified": result.checks_verified,
        "checks_contradicted": result.checks_contradicted, "checks_not_observed": result.checks_not_observed,
        "deep_evaluation_id": judgement.get("deep_evaluation_id"),
        "deep_error_code": judgement.get("deep_error_code"),
        "deep_model": judgement.get("deep_model"), "deep_usage": judgement.get("deep_usage"),
        "deep_question_set_version": judgement.get("deep_question_set_version"),
        "next_move": judgement.get("next_move"),
    }


def run_candidate_investigation(*, run_id: str, candidate: dict[str, Any], selection: str,
                                repository: Repository, artifacts: ArtifactStore, emit: Callable[..., Any],
                                publish_json: PublishJson,
                                read_artifact: Callable[[str], bytes | None],
                                stage: StageRunner,
                                jev_service: JevService | None = None, requested_action_id: str | None = None,
                                authorize_iteration: bool = False, hypotheses_requested: bool = False,
                                llm_generator: HypothesisGenerator | None = None,
                                mode: str = "LIVE") -> CandidateInvestigation:
    """Run the bounded arc for one explicitly selected candidate."""
    plan = stage("DEEP_ANALYSIS", lambda: plan_deep_slice(
        run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
        emit=emit, publish_json=publish_json, requested_action_id=requested_action_id,
    ))
    if plan.selected_action_id is None:
        reason = plan.abstain_reason or "NOT_PLANNED"
        return CandidateInvestigation(
            candidate_id=candidate["candidate_id"], selection=selection, status=reason,
            final_move=None, stop_reason=reason,
            error_code=None, steps=(), decisions=(), hypothesis=None, dossier=None,
        )
    result = stage("FOLLOWUP", lambda: execute_followup(
        run_id=run_id, plan=plan, repository=repository, emit=emit, publish_json=publish_json,
        read_artifact=read_artifact,
    ))
    if result.status == "FAILED":
        return CandidateInvestigation(
            candidate_id=candidate["candidate_id"], selection=selection, status="FAILED",
            final_move=None, stop_reason="DISPATCH_ACTION_FAILED", error_code=result.error_code,
            steps=(), decisions=(), hypothesis=None, dossier=None,
        )
    steps: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    dispatches = 0
    final_move: str | None = None
    stop_reason = "NOT_STOPPED"
    current: FollowUpResult = result
    while True:
        judgement: dict[str, Any] = stage("JEV_DEEP", partial(
            judge_evidence_revision, run_id=run_id, candidate=plan.candidate, result=current,
            jev_service=jev_service, emit=emit,
        )) if jev_service is not None else {"deep_evaluation_id": None, "deep_error_code": "JEV_DISABLED",
                                            "next_move": None}
        steps.append(_step_summary(current, judgement))
        decision = judgement.get("next_move")
        if decision is None:
            final_move, stop_reason = None, "NO_DECISION"
            break
        decisions.append(decision)
        final_move = decision["move"]
        dispatch = stage("FOLLOWUP", partial(
            dispatch_recorded_move, run_id=run_id, candidate=plan.candidate, result=current,
            decision=decision, repository=repository, emit=emit, publish_json=publish_json,
            read_artifact=read_artifact, authorized=authorize_iteration,
        ))
        steps[-1]["dispatch"] = dispatch.summary()
        if not dispatch.dispatched:
            stop_reason = dispatch.reason_code
            break
        dispatches += 1
        if dispatches >= FOLLOWUP_LIMIT:
            stop_reason = "MAX_STEPS_REACHED"
            break
        # dispatch_recorded_move returns its FollowUpResult whenever dispatched is True.
        current = cast(FollowUpResult, dispatch.result)
    if final_move == "COMPLETE":
        status = "COMPLETED"
    elif final_move == "FOLLOW_UP":
        status = "STOPPED"
    else:
        status = "ABSTAINED"
    hypothesis: dict[str, Any] | None = None
    # The policy asks for hypotheses itself, or the operator requests them explicitly for the
    # current revision; the recorded next move is never rewritten either way.
    generate_hypotheses_now = final_move == "GENERATE_HYPOTHESES" or hypotheses_requested
    if generate_hypotheses_now and authorize_iteration and jev_service is not None \
            and current.revision is not None:
        revision = current.revision
        revision_eligibilities = eligible_actions(revision.revision, "EVIDENCE_STATE")
        hypotheses = stage("HYPOTHESIS_GENERATION", lambda: run_hypothesis_stage(
            run_id=run_id, candidate=candidate, revision=revision,
            eligible_action_ids=[item.action_id for item in revision_eligibilities if item.eligible],
            repository=repository, jev_service=jev_service, emit=emit, publish_json=publish_json,
            llm_generator=llm_generator,
            requested_reason=None if final_move == "GENERATE_HYPOTHESES" else "OPERATOR_REQUESTED_HYPOTHESES",
        ))
        hypothesis = dict(hypotheses)
        if hypothesis.get("status") == "GENERATED":
            status = "HYPOTHESIZED"
    dossier: dict[str, Any] | None = None
    error_code: str | None = None
    if current.revision is not None:
        dossier = stage("DOSSIER", lambda: run_dossier_stage(
            run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
            decisions=decisions, publish_json=publish_json, emit=emit, mode=mode,
        ))
        if dossier.get("status") == "UNAVAILABLE":
            status, stop_reason = "ABSTAINED", "DOSSIER_UNAVAILABLE"
            error_code = dossier["error_code"]
    return CandidateInvestigation(
        candidate_id=candidate["candidate_id"], selection=selection, status=status,
        final_move=final_move, stop_reason=stop_reason, steps=tuple(steps),
        decisions=tuple(decisions), error_code=error_code, hypothesis=hypothesis, dossier=dossier,
    )
