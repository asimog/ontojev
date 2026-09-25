"""Stage 8: final candidate result, authoritative dossier, no-Jev comparison.

Stage 8 is deterministic and read-only over what the investigation already
recorded. For every candidate whose evidence was accepted it derives one
inspectable terminal result, computes the versioned no-Jev baseline comparison
from the same persisted evidence, persists the final result and the authoritative
dossier, and only then marks the candidate complete and returns control to the
outer candidate loop. Jev judges nothing here and no model is called: the
comparison is a deterministic replay under a declared policy, never an LLM
counterfactual and never a human-labelled experiment. A comparison dimension that
cannot honestly be computed is recorded `NOT_COMPARABLE` rather than invented.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cancerjev.domain.codecs import EVIDENCE_SCHEMA_VERSION, STATE_SCHEMA_VERSION
from cancerjev.domain.dossier import DOSSIER_SCHEMA_VERSION
from cancerjev.domain.events import utc_now
from cancerjev.jev.projection import (
    EVIDENCE_PROJECTION_VERSION,
    HYPOTHESIS_PROJECTION_VERSION,
)
from cancerjev.jev.projection import (
    PROJECTION_VERSION as STATE_PROJECTION_VERSION,
)
from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTION_SET_VERSION,
    WIDE_QUESTION_SET_VERSION,
)
from cancerjev.research.deep import stable_id
from cancerjev.research.nextmove import DEEP_POLICY_VERSION
from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PROMOTION_LIMIT,
)
from cancerjev.science.actions import ACTION_REGISTRY_VERSION
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

NO_JEV_BASELINE_VERSION = "no-jev-baseline-v1"
FINAL_RESULT_SCHEMA_VERSION = 1

NOT_COMPARABLE = "NOT_COMPARABLE"
SAME_DECISION = "SAME_DECISION"
DIFFERENT_ADMISSION = "DIFFERENT_ADMISSION"
DIFFERENT_RANK = "DIFFERENT_RANK"
NO_BASELINE_DECISION = "NO_BASELINE_DECISION"

BASELINE_DETAIL = (
    f"Under {NO_JEV_BASELINE_VERSION}, using the same pre-Jev deterministic evidence, the "
    "baseline decision is replayed; this is a declared deterministic policy replay, not observed "
    "human or Jev behavior and not proof of what any researcher would have done."
)


def baseline_next_move(checks_contradicted: int) -> dict[str, Any]:
    """The declared deterministic no-jev-baseline-v1 deep rule.

    The baseline executes the operator-selected deterministic action on the
    accepted evidence exactly once and then stops: without a deep judgment there
    is no warranted further step, and a contradicted revision abstains. It never
    dispatches an additional follow-up and never generates hypotheses.
    """
    if checks_contradicted > 0:
        return {"move": "ABSTAIN", "reason_code": "REVISION_CONTRADICTS_RECORDED_EVIDENCE",
                "detail": "the baseline abstains on any contradicted revision"}
    return {"move": "COMPLETE", "reason_code": "INVESTIGATION_COMPLETE",
            "detail": "one selected deterministic action was executed; the baseline stops"}


def _load_rankings(repository: Repository, artifacts: ArtifactStore,
                   run_id: str) -> dict[str, dict[str, Any]]:
    """Read the persisted baseline-wide-v2 and wide-policy-v2 ranking payloads."""
    payloads: dict[str, dict[str, Any]] = {}
    for row in repository.ranking_artifacts(run_id):
        try:
            payload = json.loads(artifacts.read(row["relative_path"], row["sha256"]))
        except (ValueError, OSError):
            continue
        policy_version = payload.get("policy_version")
        if policy_version is not None:
            payloads[policy_version] = payload
    return payloads


def _wide_comparison(rankings: dict[str, dict[str, Any]], source_state_id: str, *,
                     promoted_by_policy: bool) -> dict[str, Any]:
    baseline = rankings.get(BASELINE_POLICY_VERSION)
    jev = rankings.get(JEV_POLICY_VERSION)
    if baseline is None or jev is None:
        return {
            "comparison": NO_BASELINE_DECISION,
            "reason": "the run records no baseline-wide-v2 / wide-policy-v2 ranking pair",
            "baseline": None, "jev": None,
        }
    baseline_entry = next((entry for entry in baseline["entries"]
                           if entry["state_id"] == source_state_id), None)
    jev_entry = next((entry for entry in jev["entries"]
                      if entry["state_id"] == source_state_id), None)
    if baseline_entry is None or jev_entry is None:
        return {
            "comparison": NOT_COMPARABLE,
            "reason": "the candidate's source state is absent from one persisted ranking",
            "baseline": None, "jev": None,
        }
    baseline_admitted = source_state_id in baseline["top_state_ids"][:PROMOTION_LIMIT]
    jev_admitted = source_state_id in jev["admitted_state_ids"]
    admission_delta = SAME_DECISION if baseline_admitted == jev_admitted else DIFFERENT_ADMISSION
    rank_delta = (SAME_DECISION if baseline_entry["rank"] == jev_entry["rank"]
                  else DIFFERENT_RANK)
    if admission_delta == DIFFERENT_ADMISSION:
        comparison = DIFFERENT_ADMISSION
    elif rank_delta == DIFFERENT_RANK:
        comparison = DIFFERENT_RANK
    else:
        comparison = SAME_DECISION
    return {
        "path": {"actual": "OBSERVED", "baseline": "DETERMINISTIC_REPLAY"},
        "comparison": comparison,
        "admission_delta": admission_delta,
        "rank_delta": rank_delta,
        "baseline_admitted": baseline_admitted,
        "baseline_rank": baseline_entry["rank"],
        "baseline_policy_version": BASELINE_POLICY_VERSION,
        "jev_admitted": jev_admitted,
        "jev_rank": jev_entry["rank"],
        "jev_qualified": jev_entry.get("qualified"),
        "jev_policy_version": JEV_POLICY_VERSION,
        "abstention_introduced": jev_entry.get("qualified") is False,
        "promoted_only_under_jev": promoted_by_policy and jev_admitted and not baseline_admitted,
        "baseline_advanced_without_jev": baseline_admitted and not jev_admitted,
        "promotion_limit": PROMOTION_LIMIT,
        "note": BASELINE_DETAIL,
    }


def _investigation_comparison(final_revision_summary: dict[str, Any] | None,
                              actual_final_move: str | None, hypotheses_generated: int,
                              extra_dispatches: int) -> dict[str, Any]:
    if final_revision_summary is None or final_revision_summary.get("has_action") is not True:
        return {
            "comparison": NOT_COMPARABLE,
            "reason": ("no deterministic action was executed on this candidate; "
                       "the baseline rule consumes the operator-selected action"),
            "path": {"actual": "OBSERVED", "baseline": "DETERMINISTIC_REPLAY"},
            "baseline_next_move": None,
        }
    baseline = baseline_next_move(int(final_revision_summary.get("contradicted") or 0))
    baseline_move = baseline["move"]
    return {
        "path": {"actual": "OBSERVED", "baseline": "DETERMINISTIC_REPLAY"},
        "comparison": SAME_DECISION if actual_final_move == baseline_move else "DIFFERENT",
        "baseline_rule": NO_JEV_BASELINE_VERSION,
        "baseline_next_move": baseline_move,
        "baseline_reason_code": baseline["reason_code"],
        "baseline_detail": baseline["detail"],
        "actual_final_move": actual_final_move,
        "follow_up_changed": extra_dispatches > 0,
        "stopping_changed": (actual_final_move == "COMPLETE") != (baseline_move == "COMPLETE"),
        "hypothesis_generation_changed": hypotheses_generated,
        "evidence_revisions_attributable_to_jev_route": extra_dispatches,
        "note": BASELINE_DETAIL,
    }


def _comparison_status(wide: dict[str, Any], investigation: dict[str, Any]) -> str:
    parts = [wide.get("comparison"), investigation.get("comparison")]
    if all(part == SAME_DECISION for part in parts):
        return SAME_DECISION
    if all(part in (NO_BASELINE_DECISION, NOT_COMPARABLE) for part in parts):
        return NOT_COMPARABLE
    if any(part in (NO_BASELINE_DECISION, NOT_COMPARABLE) for part in parts):
        return "PARTIALLY_COMPARABLE"
    return "DIFFERENT"


def _hypothesis_status(hypothesis: dict[str, Any] | None) -> dict[str, Any]:
    generated = bool(hypothesis and hypothesis.get("status") == "GENERATED")
    return {
        "invoked": bool(hypothesis),
        "generated": generated,
        "generator": (hypothesis or {}).get("generator"),
        "hypothesis_ids": list((hypothesis or {}).get("hypothesis_ids") or []),
        "requested_reason": (hypothesis or {}).get("requested_reason"),
        "note": "generated hypothesis text is never evidence and never writes a measured field",
    }


def _limitations(state: Any, wide: dict[str, Any],
                 investigation: dict[str, Any]) -> list[str]:
    limitations = [
        "Deterministic checks are integrity and consistency evidence, not biological evidence.",
        "A single cohort is examined and the examined gene set is selection-biased.",
        "Jev judgments are inputs to Python policy; they select, authorize and execute nothing.",
        "The no-Jev comparison is a declared deterministic replay, not proof of human or "
        "real-world behavior; superiority claims need a separate empirical evaluation design.",
    ]
    for project in state.projects:
        reason = getattr(project.expression, "reason", None)
        if reason:
            limitations.append(f"{project.population.frame.project_id} expression lane: {reason}")
    if wide.get("comparison") in (NOT_COMPARABLE, NO_BASELINE_DECISION):
        limitations.append(f"wide comparison unavailable: {wide.get('comparison')}")
    if wide.get("comparison") not in (NOT_COMPARABLE, NO_BASELINE_DECISION) \
            and wide.get("comparison") is None:
        limitations.append("wide comparison unavailable")
    if investigation.get("comparison") == NOT_COMPARABLE:
        limitations.append("investigation-level baseline comparison is not comparable")
    return limitations


def derive_stage8(*, run_id: str, candidate: dict[str, Any], investigation_status: str,
                  final_move: str | None, stop_reason: str, error_code: str | None,
                  steps: tuple[dict[str, Any], ...], decisions: tuple[dict[str, Any], ...],
                  hypothesis: dict[str, Any] | None, stored_state: Any, chain: list[Any],
                  executions: list[dict[str, Any]], dossier_id: str, promoted_by_policy: bool,
                  rankings: dict[str, dict[str, Any]], mode: str,
                  ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive the final candidate result and its comparison from persisted records only."""
    state = stored_state.record.state
    final_revision = chain[-1].evidence if chain else None
    final_revision_summary = None
    if final_revision is not None:
        final_revision_summary = {
            "total": final_revision.summary.total, "verified": final_revision.summary.verified,
            "contradicted": final_revision.summary.contradicted,
            "not_observed": final_revision.summary.not_observed,
            "has_action": final_revision.action is not None,
        }
    extra_dispatches = max(len(steps) - 1, 0) if steps else 0
    hypotheses_generated = 1 if (hypothesis or {}).get("status") == "GENERATED" else 0

    wide_comparison = _wide_comparison(rankings, candidate["source_state_id"],
                                       promoted_by_policy=promoted_by_policy)
    investigation_comparison = _investigation_comparison(
        final_revision_summary, final_move, hypotheses_generated, extra_dispatches)
    comparison = {
        "schema_version": 1,
        "kind": "JEV_NO_JEV_COMPARISON",
        "baseline_policy_version": NO_JEV_BASELINE_VERSION,
        "path": {"actual": "OBSERVED", "baseline": "DETERMINISTIC_REPLAY"},
        "wide": wide_comparison,
        "investigation": investigation_comparison,
        "overall": _comparison_status(wide_comparison, investigation_comparison),
        "claim": ("Decision deltas and trajectory differences only; no claim that Jev improved "
                  "the result, was superior, or found the correct answer."),
        "note": BASELINE_DETAIL,
    }

    last_decision = decisions[-1] if decisions else None
    deep_evaluation_ids = [step.get("deep_evaluation_id") for step in steps
                           if step.get("deep_evaluation_id")]
    candidate_summary = candidate.get("summary") or {}
    population = state.projects[0].population if state.projects else None
    final_result = {
        "schema_version": FINAL_RESULT_SCHEMA_VERSION,
        "kind": "FINAL_CANDIDATE_RESULT",
        "final_result_id": stable_id(run_id, f"final-result:{candidate['candidate_id']}"),
        "run_id": run_id,
        "candidate_id": candidate["candidate_id"],
        "dossier_reference": dossier_id,
        "research_question": (chain[0].evidence.puzzle.question if chain else None),
        "candidate": {
            "entity": candidate.get("entity"),
            "promotion_slot": candidate.get("promotion_slot"),
            "source_state_id": candidate["source_state_id"],
            "admission_policy_version": candidate_summary.get("policy_version"),
        },
        "population": {
            "project_id": population.frame.project_id if population else None,
            "cohort_id": population.frame.cohort_id if population else None,
            "examined_cases": len(population.frame.examined_ids) if population else None,
        },
        "final_evidence_revision": None if final_revision is None else {
            "evidence_state_id": chain[-1].evidence_state_id,
            "evidence_hash": chain[-1].record.evidence_hash,
            "revision_index": final_revision.revision_index,
            "action_id": final_revision.action.action_id if final_revision.action else None,
            "checks": final_revision_summary,
        },
        "investigation_status": investigation_status,
        "final_move": final_move,
        "stop_reason": stop_reason,
        "error_code": error_code,
        "evidence_sufficiency": {
            "state_quality_acquisition": state.quality.acquisition.value,
            "state_quality_sufficiency": state.quality.sufficiency.value,
            "final_revision_checks": final_revision_summary,
        },
        "remaining_uncertainty": {
            "dominant_limitation": (last_decision or {}).get("dimensions", {}).get(
                "dominant_limitation"),
            "state_missingness": list(state.missingness),
            "recorded_stop_detail": (last_decision or {}).get("detail"),
        },
        "hypothesis_status": _hypothesis_status(hypothesis),
        "jev_assisted_outcome": {
            "wide_evaluation_id": candidate_summary.get("wide_evaluation_id"),
            "deep_evaluation_ids": deep_evaluation_ids,
            "next_moves": [
                {"move": item.get("move"), "reason_code": item.get("reason_code"),
                 "policy_version": item.get("policy_version")}
                for item in decisions
            ],
        },
        "baseline_comparison": comparison,
        "limitations": _limitations(state, wide_comparison, investigation_comparison),
        "provenance": {
            "state_id": stored_state.state_id,
            "state_hash": stored_state.state_hash,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "dossier_schema_version": DOSSIER_SCHEMA_VERSION,
            "state_projection_version": STATE_PROJECTION_VERSION,
            "evidence_projection_version": EVIDENCE_PROJECTION_VERSION,
            "hypothesis_projection_version": HYPOTHESIS_PROJECTION_VERSION,
            "wide_question_set_version": WIDE_QUESTION_SET_VERSION,
            "deep_question_set_version": DEEP_QUESTION_SET_VERSION,
            "hypothesis_question_set_version": HYPOTHESIS_QUESTION_SET_VERSION,
            "action_registry_version": ACTION_REGISTRY_VERSION,
            "wide_policy_version": JEV_POLICY_VERSION,
            "operator_selection_policy_version": "operator-selection-v1",
            "deep_policy_version": DEEP_POLICY_VERSION,
            "baseline_policy_version": NO_JEV_BASELINE_VERSION,
            "baseline_wide_policy_version": BASELINE_POLICY_VERSION,
            "executed_actions": [
                {"action_id": row["action_id"], "action_version": row["action_version"],
                 "status": row["status"]} for row in executions
            ],
            "mode": mode,
        },
    }
    return final_result, comparison


def run_stage8_finalize(*, run_id: str, candidate: dict[str, Any], investigation_status: str,
                        final_move: str | None, stop_reason: str, error_code: str | None,
                        steps: tuple[dict[str, Any], ...],
                        decisions: tuple[dict[str, Any], ...],
                        hypothesis: dict[str, Any] | None, repository: Repository,
                        artifacts: ArtifactStore, emit: Callable[..., Any],
                        publish_json: Callable[..., Any], stage: Callable[..., Any] | None = None,
                        mode: str = "LIVE") -> dict[str, Any]:
    """Derive, persist, and publish Stage 8 for one candidate, then mark it complete."""
    from cancerjev.research.dossier import run_dossier_stage
    from cancerjev.storage.readers import read_candidate_state, read_revision_chain

    dossier_id = stable_id(run_id, f"dossier:{candidate['candidate_id']}")
    final_result_id = stable_id(run_id, f"final-result:{candidate['candidate_id']}")
    existing = repository.get_dossier(dossier_id)
    if existing is not None:
        # Idempotent: the candidate already completed; replay only restates the record.
        return {
            "dossier_status": "DOSSIER_READY", "error_code": None,
            "candidate_status": "CANDIDATE_COMPLETE",
            "final_result": {
                "final_result_id": final_result_id, "final_move": final_move,
                "stop_reason": stop_reason, "investigation_status": investigation_status,
                "comparison_status": None, "artifact_id": existing["json_artifact_id"],
            },
            "dossier": existing["summary"],
            "result_artifact_id": existing["json_artifact_id"],
        }
    stored_state = read_candidate_state(repository, artifacts, candidate["candidate_id"])
    candidate_summary = candidate.get("summary") or {}
    promoted_by_policy = candidate_summary.get("policy_version") == JEV_POLICY_VERSION
    final_result, comparison = derive_stage8(
        run_id=run_id, candidate=candidate, investigation_status=investigation_status,
        final_move=final_move, stop_reason=stop_reason, error_code=error_code, steps=steps,
        decisions=decisions, hypothesis=hypothesis, stored_state=stored_state,
        chain=read_revision_chain(repository, artifacts, candidate["candidate_id"]),
        executions=repository.followup_executions_for(candidate["candidate_id"]),
        dossier_id=dossier_id, promoted_by_policy=promoted_by_policy,
        rankings=_load_rankings(repository, artifacts, run_id), mode=mode,
    )
    result_artifact = publish_json(
        run_id, f"runs/{run_id}/stage8/{final_result['final_result_id']}.json",
        final_result, "final-candidate-result")
    repository.register_artifact(result_artifact, run_id)

    def _dossier() -> dict[str, Any]:
        return run_dossier_stage(
            run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
            decisions=list(decisions), publish_json=publish_json, emit=emit, mode=mode,
            final_result=final_result, comparison=comparison,
        )

    dossier_summary = (
        stage("DOSSIER", _dossier) if stage is not None else _dossier()
    )
    if dossier_summary.get("status") == "UNAVAILABLE":
        emit(
            run_id, "CANDIDATE_NOT_COMPLETED",
            f"stage8:{candidate['candidate_id']}:incomplete",
            "Stage 8 did not complete the candidate: the authoritative dossier is unavailable.",
            stage="FINALIZATION", candidate_id=candidate["candidate_id"], level="error",
            data={"candidate_id": candidate["candidate_id"],
                  "error_code": dossier_summary.get("error_code"),
                  "detail": dossier_summary.get("detail")},
        )
        return {"dossier_status": "FAILED", "error_code": dossier_summary.get("error_code"),
                "detail": dossier_summary.get("detail"), "final_result": None, "dossier": None,
                "result_artifact_id": None}
    now = utc_now()
    emit(
        run_id, "FINAL_CANDIDATE_RESULT_RECORDED",
        f"stage8:{final_result['final_result_id']}:recorded",
        f"Recorded the final candidate result for {candidate['candidate_id']}: "
        f"{investigation_status} / {stop_reason}; baseline comparison {comparison['overall']}.",
        stage="FINALIZATION", candidate_id=candidate["candidate_id"],
        data={"final_result_id": final_result["final_result_id"],
              "candidate_id": candidate["candidate_id"], "final_move": final_move,
              "stop_reason": stop_reason, "investigation_status": investigation_status,
              "comparison_status": comparison["overall"],
              "dossier_id": dossier_summary["dossier_id"],
              "baseline_policy_version": NO_JEV_BASELINE_VERSION},
        artifact_refs=[result_artifact.ref()],
        registrations=[
            repository.candidate_status_registration(
                candidate_id=candidate["candidate_id"], status="CANDIDATE_COMPLETE",
                current_stage=None, updated_at=now,
                dossier_id=dossier_summary["dossier_id"],
                latest_evidence_state_id=(
                    final_result["final_evidence_revision"] or {}).get("evidence_state_id"),
            ),
        ],
    )
    emit(
        run_id, "CANDIDATE_COMPLETED", f"candidate:{candidate['candidate_id']}:completed",
        f"Candidate {candidate['candidate_id']} is complete: final result and authoritative "
        "dossier are persisted (DOSSIER_READY); control returns to the candidate loop.",
        stage="FINALIZATION", candidate_id=candidate["candidate_id"],
        data={"candidate_id": candidate["candidate_id"],
              "final_result_id": final_result["final_result_id"],
              "dossier_id": dossier_summary["dossier_id"],
              "dossier_status": "DOSSIER_READY", "candidate_status": "CANDIDATE_COMPLETE"},
        artifact_refs=[result_artifact.ref()],
    )
    return {
        "dossier_status": "DOSSIER_READY", "error_code": None,
        "candidate_status": "CANDIDATE_COMPLETE",
        "final_result": {
            "final_result_id": final_result["final_result_id"],
            "final_move": final_move, "stop_reason": stop_reason,
            "investigation_status": investigation_status,
            "comparison_status": comparison["overall"],
            "artifact_id": result_artifact.artifact_id,
        },
        "dossier": dossier_summary,
        "result_artifact_id": result_artifact.artifact_id,
    }