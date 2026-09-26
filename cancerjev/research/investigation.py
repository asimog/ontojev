"""One candidate's bounded deterministic investigation arc and Stage 8 finalization.

Python owns the sequence: accept the candidate's evidence as E0, run the selected
registered action, judge the new revision, and while the recorded move is
`FOLLOW_UP`, an explicit authorization is in force and both caps allow it, dispatch
the next distinct eligible action and judge again. A terminal recorded move
(`COMPLETE` / `ABSTAIN` / any non-follow-up move) ends the loop here with its
actual policy reason; it is never routed through the follow-up dispatcher. When
the policy asks for hypotheses and the operator authorized iteration, bounded
statement generation and its Jev review run.

Stage 8 then finalizes the candidate: it derives the final candidate result from
the recorded run state, builds the authoritative dossier, computes the declared
no-Jev comparison, persists both, marks the dossier ready and the candidate
complete, and returns control to the outer candidate loop. No human review and no
model call participate in finalization.

Jev judges; Python decides, executes, caps and stops. Every judgment, decision,
dispatch and refusal is already recorded by the steps this module composes, so the
arc itself adds no new event kind.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import AcquisitionTransport
from cancerjev.research.deep import (
    FOLLOWUP_LIMIT,
    FollowUpResult,
    dispatch_recorded_move,
    execute_followup,
    judge_evidence_revision,
    plan_deep_slice,
)
from cancerjev.research.finalize import run_stage8_finalize
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
    investigation_status: str
    final_move: str | None
    stop_reason: str
    steps: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]
    error_code: str | None
    hypothesis: dict[str, Any] | None
    dossier: dict[str, Any] | None
    candidate_status: str
    final_result: dict[str, Any] | None

    def summary(self) -> dict[str, Any]:
        first = self.steps[0] if self.steps else {}
        last_dispatch = next(
            (step.get("dispatch") for step in reversed(self.steps)
             if step.get("dispatch") is not None), None)
        return {
            "selection": self.selection, "candidate_id": self.candidate_id, "status": self.status,
            "investigation_status": self.investigation_status,
            "candidate_status": self.candidate_status,
            "final_move": self.final_move, "stop_reason": self.stop_reason,
            "error_code": self.error_code,
            "first_step": first,
            "steps": list(self.steps),
            "dispatch": first.get("dispatch"),
            "last_dispatch": last_dispatch,
            "decisions": list(self.decisions),
            "hypothesis": self.hypothesis,
            "dossier": self.dossier,
            "final_result": self.final_result,
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


def _finalized(status: str, final_move: str | None, stop_reason: str, error_code: str | None,
               steps: tuple[dict[str, Any], ...], decisions: tuple[dict[str, Any], ...],
               hypothesis: dict[str, Any] | None, finalization: dict[str, Any]) -> CandidateInvestigation:
    complete = finalization.get("dossier_status") == "DOSSIER_READY"
    return CandidateInvestigation(
        candidate_id=finalization["candidate_id"], selection=finalization["selection"],
        status=status, investigation_status=status, final_move=final_move,
        stop_reason=stop_reason, steps=steps, decisions=decisions,
        error_code=(None if complete else finalization.get("error_code") or error_code),
        hypothesis=hypothesis, dossier=finalization.get("dossier"),
        candidate_status="CANDIDATE_COMPLETE" if complete else "FAILED",
        final_result=finalization.get("final_result"),
    )


def run_candidate_investigation(*, run_id: str, candidate: dict[str, Any], selection: str,
                                repository: Repository, artifacts: ArtifactStore, emit: Callable[..., Any],
                                publish_json: PublishJson,
                                read_artifact: Callable[[str], bytes | None],
                                stage: StageRunner,
                                jev_service: JevService | None = None, requested_action_id: str | None = None,
                                authorize_iteration: bool = False, hypotheses_requested: bool = False,
                                llm_generator: HypothesisGenerator | None = None,
                                transport: AcquisitionTransport | None = None,
                                mode: str = "LIVE") -> CandidateInvestigation:
    """Run the bounded arc for one explicitly selected candidate, then Stage 8."""
    plan = stage("DEEP_ANALYSIS", lambda: plan_deep_slice(
        run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
        emit=emit, publish_json=publish_json, requested_action_id=requested_action_id,
    ))
    if plan.selected_action_id is None:
        reason = plan.abstain_reason or "NOT_PLANNED"
        if plan.candidate.record is None:
            # The candidate's evidence was never accepted; no dossier can be built.
            return CandidateInvestigation(
                candidate_id=candidate["candidate_id"], selection=selection, status="FAILED",
                investigation_status="FAILED", final_move=None, stop_reason=reason,
                error_code="EVIDENCE_ACCEPTANCE_FAILED",
                steps=(), decisions=(), hypothesis=None, dossier=None,
                candidate_status="FAILED", final_result=None,
            )
        # Evidence was accepted; Stage 8 records the terminal abstention result.
        finalization = stage("FINALIZATION", lambda: run_stage8_finalize(
            run_id=run_id, candidate=candidate, investigation_status="ABSTAINED",
            final_move=None, stop_reason=reason, error_code=None, steps=(), decisions=(),
            hypothesis=None, repository=repository, artifacts=artifacts, emit=emit,
            publish_json=publish_json, stage=stage, mode=mode,
        ))
        return _finalized(status=reason, final_move=None, stop_reason=reason, error_code=None,
                          steps=(), decisions=(), hypothesis=None, finalization={
                              "candidate_id": candidate["candidate_id"], "selection": selection,
                              **finalization})
    result = stage("FOLLOWUP", lambda: execute_followup(
        run_id=run_id, plan=plan, repository=repository, emit=emit, publish_json=publish_json,
        read_artifact=read_artifact, transport=transport,
    ))
    if result.status == "FAILED":
        return CandidateInvestigation(
            candidate_id=candidate["candidate_id"], selection=selection, status="FAILED",
            investigation_status="FAILED", final_move=None, stop_reason="DISPATCH_ACTION_FAILED",
            error_code=result.error_code,
            steps=(), decisions=(), hypothesis=None, dossier=None,
            candidate_status="FAILED", final_result=None,
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
        # Terminal moves stop the loop with their actual policy reason; only a recorded
        # FOLLOW_UP is eligible for dispatch.
        if final_move != "FOLLOW_UP":
            stop_reason = decision["reason_code"]
            break
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
        investigation_status = "COMPLETED"
    elif final_move == "FOLLOW_UP":
        investigation_status = "STOPPED"
    else:
        investigation_status = "ABSTAINED"
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
            investigation_status = "HYPOTHESIZED"
    finalization = stage("FINALIZATION", lambda: run_stage8_finalize(
        run_id=run_id, candidate=candidate, investigation_status=investigation_status,
        final_move=final_move, stop_reason=stop_reason, error_code=None, steps=tuple(steps),
        decisions=tuple(decisions), hypothesis=hypothesis, repository=repository,
        artifacts=artifacts, emit=emit, publish_json=publish_json, stage=stage, mode=mode,
    ))
    return _finalized(status=investigation_status, final_move=final_move, stop_reason=stop_reason,
                      error_code=None, steps=tuple(steps), decisions=tuple(decisions),
                      hypothesis=hypothesis, finalization={
                          "candidate_id": candidate["candidate_id"], "selection": selection,
                          **finalization})