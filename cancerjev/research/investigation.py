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

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.runs import ExecutionOwnership
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

AUTONOMOUS_DISPATCH_AUTHORIZATION = "autonomous-policy-v1"
VALIDATION_DISPATCH_AUTHORIZATION = "validation-policy-v1"


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


def _apply_hypothesis_policy(*, run_id: str, candidate: dict[str, Any], plan: Any,
                             current: FollowUpResult, hypothesis: dict[str, Any],
                             steps: list[dict[str, Any]], decisions: list[dict[str, Any]],
                             dispatches: int, repository: Repository,
                             emit: Callable[..., Any], publish_json: PublishJson,
                             read_artifact: Callable[[str], bytes | None],
                             jev_service: JevService | None,
                             authorize_iteration: bool,
                             authorized_by: str,
                             ) -> tuple[FollowUpResult, int, dict[str, Any]]:
    """Record the hypothesis policy decision and dispatch one requested test.

    The policy consumes the recorded critique; when it requests exactly one
    registered discriminating action, that action is dispatched through the same
    recorded-move path (same caps, same revision limits) and the resulting
    revision is judged once. Otherwise the decision is recorded and nothing is
    executed. Jev never chooses or executes anything.
    """
    from cancerjev.research.hypothesis_policy import decide_hypothesis_test
    from cancerjev.science.actions import EVIDENCE_PRODUCING_ACTION_IDS

    hypothesis_ids = {str(item) for item in (hypothesis.get("hypothesis_ids") or [])}
    rows = [row["hypothesis"] for row in repository.list_table("hypotheses", run_id)
            if row["candidate_id"] == candidate["candidate_id"]
            and row["hypothesis_id"] in hypothesis_ids]
    producing_action: str | None = None
    if current.revision is not None and current.revision.revision.action is not None:
        producing_action = current.revision.revision.action.action_id
    eligible_ids = (
        [item.action_id
         for item in eligible_actions(current.revision.revision, "EVIDENCE_STATE")
         if item.eligible]
        if current.revision is not None else [])
    dispatchable = [action_id for action_id in eligible_ids if action_id != producing_action]
    decision = decide_hypothesis_test(
        hypotheses=rows, evaluations=list(hypothesis.get("evaluations") or []),
        dispatchable_action_ids=dispatchable,
        evidence_producing_action_ids=EVIDENCE_PRODUCING_ACTION_IDS)
    payload: dict[str, Any] = {
        **decision.payload(), "candidate_id": candidate["candidate_id"],
        "evidence_state_id": current.evidence_state_id,
        "dispatchable_action_ids": sorted(dispatchable),
        "evidence_producing_action_ids": sorted(EVIDENCE_PRODUCING_ACTION_IDS),
    }
    artifact = publish_json(
        run_id, f"runs/{run_id}/hypotheses/policy-{candidate['candidate_id']}"
                f"-i{current.iteration}.json",
        canonical_json(payload), "hypothesis-policy")
    emit(
        run_id, "HYPOTHESIS_POLICY_RECORDED",
        f"hypothesis-policy:{candidate['candidate_id']}:{decision.move}",
        f"Hypothesis policy decided {decision.move}: {decision.reason_code}.",
        stage="HYPOTHESIS_VERIFICATION", candidate_id=candidate["candidate_id"],
        data={"candidate_id": candidate["candidate_id"], "move": decision.move,
              "reason_code": decision.reason_code, "hypothesis_id": decision.hypothesis_id,
              "action_id": decision.action_id, "policy_version": decision.policy_version,
              "hypotheses": len(rows), "dispatchable_action_ids": sorted(dispatchable),
              "evidence_state_id": current.evidence_state_id},
        artifact_refs=[artifact.ref()],
        registrations=[repository.artifact_registration(artifact, run_id)],
    )
    if (decision.move != "TEST_HYPOTHESIS" or not authorize_iteration
            or decision.action_id is None or dispatches >= FOLLOWUP_LIMIT):
        return current, dispatches, payload
    dispatch = dispatch_recorded_move(
        run_id=run_id, candidate=plan.candidate, result=current,
        decision={"move": "FOLLOW_UP", "reason_code": "HYPOTHESIS_TEST_REQUESTED",
                  "policy_version": decision.policy_version,
                  "hypothesis_id": decision.hypothesis_id,
                  "dimensions": {"distinct_eligible_action_ids": [decision.action_id]}},
        repository=repository, emit=emit, publish_json=publish_json,
        read_artifact=read_artifact, authorized=True, authorized_by=authorized_by)
    payload["dispatch"] = dispatch.summary()
    if not dispatch.dispatched:
        return current, dispatches, payload
    new_result = cast(FollowUpResult, dispatch.result)
    judgement = judge_evidence_revision(
        run_id=run_id, candidate=plan.candidate, result=new_result,
        jev_service=jev_service, emit=emit) if jev_service is not None else {
            "deep_evaluation_id": None, "deep_error_code": "JEV_DISABLED", "next_move": None}
    steps.append(_step_summary(new_result, judgement))
    steps[-1]["dispatch"] = dispatch.summary()
    next_decision = judgement.get("next_move")
    if isinstance(next_decision, dict):
        decisions.append(next_decision)
    return new_result, dispatches + 1, payload


def run_candidate_investigation(*, run_id: str, candidate: dict[str, Any], selection: str,
                                repository: Repository, artifacts: ArtifactStore, emit: Callable[..., Any],
                                publish_json: PublishJson,
                                read_artifact: Callable[[str], bytes | None],
                                stage: StageRunner,
                                jev_service: JevService | None = None, requested_action_id: str | None = None,
                                authorize_iteration: bool = False, hypotheses_requested: bool = False,
                                llm_generator: HypothesisGenerator | None = None,
                                transport: AcquisitionTransport | None = None,
                                mode: str = "LIVE",
                                authorized_by: str = "OPERATOR_AUTHORIZATION") -> CandidateInvestigation:
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
            authorized_by=authorized_by,
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
            current, dispatches, policy_payload = _apply_hypothesis_policy(
                run_id=run_id, candidate=candidate, plan=plan, current=current,
                hypothesis=hypothesis, steps=steps, decisions=decisions,
                dispatches=dispatches, repository=repository, emit=emit,
                publish_json=publish_json, read_artifact=read_artifact,
                jev_service=jev_service, authorize_iteration=authorize_iteration,
                authorized_by=authorized_by)
            hypothesis["policy"] = policy_payload
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


@dataclass(frozen=True)
class AutonomousCandidateQueue:
    """Every promoted candidate processed to a terminal state by Python policy."""

    candidates: tuple[dict[str, Any], ...]
    failures: tuple[dict[str, str], ...]
    authorized_by: str = AUTONOMOUS_DISPATCH_AUTHORIZATION

    @property
    def completed_count(self) -> int:
        return sum(1 for summary in self.candidates
                   if summary.get("candidate_status") == "CANDIDATE_COMPLETE")

    @property
    def candidate_queue_exhausted(self) -> bool:
        return bool(self.candidates) and self.completed_count == len(self.candidates)

    def summary(self) -> dict[str, Any]:
        return {
            "candidate_count": len(self.candidates),
            "completed_count": self.completed_count,
            "failures": [dict(failure) for failure in self.failures],
            "candidate_queue_exhausted": self.candidate_queue_exhausted,
            "authorized_by": self.authorized_by,
            "run_scope": ("CANDIDATE_QUEUE_EXHAUSTED" if self.candidate_queue_exhausted
                          else "CANDIDATES_INCOMPLETE"),
            "candidates_completed": [
                {"candidate_id": summary.get("candidate_id"),
                 "final_result_id": (summary.get("final_result") or {}).get("final_result_id"),
                 "dossier_id": (summary.get("dossier") or {}).get("dossier_id"),
                 "candidate_status": summary.get("candidate_status"),
                 "comparison_status": (summary.get("final_result") or {}).get("comparison_status")}
                for summary in self.candidates
            ],
        }


def _read_artifact(repository: Repository,
                   artifacts: ArtifactStore) -> Callable[[str], bytes | None]:
    def read(artifact_id: str) -> bytes | None:
        metadata = repository.artifact(artifact_id)
        if metadata is None:
            return None
        return artifacts.read(metadata["relative_path"])
    return read


def _record_terminal_failure(run_id: str, candidate_id: str, reason_code: str, detail: str,
                             emit: Callable[..., Any], repository: Repository,
                             authorized_by: str) -> None:
    current = next((row for row in repository.list_table("candidates", run_id)
                    if row["candidate_id"] == candidate_id), None)
    if current is not None and current.get("status") == "CANDIDATE_COMPLETE":
        return
    emit(
        run_id, "CANDIDATE_NOT_COMPLETED", f"queue:{candidate_id}:terminal-failure",
        f"Candidate {candidate_id} is terminal without a completed dossier: {reason_code}.",
        stage="FINALIZATION", level="error", candidate_id=candidate_id,
        data={"candidate_id": candidate_id, "reason_code": reason_code, "detail": detail,
              "terminal_state": "FAILED", "authorized_by": authorized_by},
        registrations=[repository.candidate_status_registration(
            candidate_id=candidate_id, status="FAILED", current_stage=None, updated_at=utc_now())],
    )


def run_autonomous_candidate_queue(*, run_id: str, repository: Repository,
                                   artifacts: ArtifactStore, emit: Callable[..., Any],
                                   publish_json: PublishJson, stage: StageRunner,
                                   jev_service: JevService | None,
                                   transport: AcquisitionTransport | None = None,
                                   mode: str = "LIVE",
                                   llm_generator: HypothesisGenerator | None = None,
                                   ownership: ExecutionOwnership = ExecutionOwnership.SYSTEM_AUTONOMOUS,
                                   authorized_by: str = AUTONOMOUS_DISPATCH_AUTHORIZATION,
                                   ) -> AutonomousCandidateQueue:
    """Process every policy-promoted Candidate to a terminal state; no operator input.

    Ordering is the deterministic ``promotion_slot`` of the persisted candidates.
    Follow-ups are dispatched under the declared authorization of the owning
    activation (``autonomous-policy-v1`` or ``validation-policy-v1``) and still
    obey every existing cap and refusal. One candidate's failure is recorded with
    an explicit typed reason and a terminal status; it never aborts or corrupts
    another candidate. Researcher-run ownership is refused: this queue is
    reachable only on a SYSTEM_AUTONOMOUS or VALIDATION_RUN run, and researcher
    overrides remain on the separate operator path.
    """
    repository.require_run_ownership(run_id, ownership)
    rows = {row["candidate_id"]: row for row in repository.list_table("candidates", run_id)}
    promoted = sorted(
        (row for row in rows.values()
         if row.get("status") == "WIDE_EVALUATED" and row.get("source_state_id")),
        key=lambda row: (int(row.get("promotion_slot") or 0), str(row["candidate_id"])),
    )
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    read_artifact = _read_artifact(repository, artifacts)
    for row in promoted:
        candidate_id = str(row["candidate_id"])
        selection = f"slot:{row.get('promotion_slot')}"
        try:
            investigation = run_candidate_investigation(
                run_id=run_id, candidate={**row, "entity": row.get("entity") or {}},
                selection=selection, repository=repository, artifacts=artifacts, emit=emit,
                publish_json=publish_json, read_artifact=read_artifact, stage=stage,
                jev_service=jev_service, authorize_iteration=True, hypotheses_requested=False,
                llm_generator=llm_generator, transport=transport, mode=mode,
                authorized_by=authorized_by,
            )
            summaries.append(investigation.summary())
            if investigation.candidate_status != "CANDIDATE_COMPLETE":
                reason = investigation.error_code or investigation.stop_reason
                failures.append({"candidate_id": candidate_id, "reason_code": reason,
                                 "terminal_state": investigation.candidate_status})
                _record_terminal_failure(run_id, candidate_id, reason, investigation.stop_reason,
                                         emit, repository, authorized_by)
        except Exception as exc:  # noqa: BLE001 - one candidate must not abort the queue
            reason = str(getattr(exc, "code", type(exc).__name__))
            summaries.append({
                "selection": selection, "candidate_id": candidate_id, "status": "FAILED",
                "investigation_status": "FAILED", "candidate_status": "FAILED",
                "final_move": None, "stop_reason": reason, "error_code": reason,
                "first_step": {}, "steps": [], "decisions": [], "hypothesis": None,
                "dossier": None, "final_result": None,
            })
            failures.append({"candidate_id": candidate_id, "reason_code": reason,
                             "terminal_state": "FAILED"})
            _record_terminal_failure(run_id, candidate_id, reason, str(exc), emit, repository,
                                     authorized_by)
    return AutonomousCandidateQueue(tuple(summaries), tuple(failures), authorized_by)