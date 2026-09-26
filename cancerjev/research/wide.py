"""Wide evaluation: deterministic projections, real Jev calls, rankings, promotion.

Sequence is owned by research: projection per state, one Jev request per state,
fail-closed validation, deterministic rankings persisted for both the baseline
and the Jev policy, and bounded candidate promotion. Jev never queries GDC,
never selects rows, and never creates science facts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.jev.contracts import EvaluationRecord
from cancerjev.jev.projection import ProjectionError
from cancerjev.jev.questions import WIDE_QUESTION_SET_VERSION
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PRE_WIDE_ORDERING_DESCRIPTION,
    PRE_WIDE_POLICY_VERSION,
    PROMOTION_LIMIT,
    baseline_ranking,
    jev_ranking,
    measured_dimensions,
    measured_ordering_key,
)
from cancerjev.research.seams import PublishJson
from cancerjev.storage.artifacts import PublishedArtifact
from cancerjev.storage.repositories import Repository


@dataclass(frozen=True)
class PreWideSelection:
    """Typed pre-Wide boundary: the selected states plus explicit counts/reasons."""

    policy_version: str
    states: tuple[StateRecord, ...]
    considered: int
    ceiling: int | None
    excluded: tuple[dict[str, Any], ...]
    reason_code: str

    def payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "ordering": PRE_WIDE_ORDERING_DESCRIPTION,
            "ceiling": self.ceiling,
            "considered": self.considered,
            "selected": len(self.states),
            "excluded": [dict(entry) for entry in self.excluded],
            "reason_code": self.reason_code,
        }


def select_pre_wide_states(states: list[StateRecord], *,
                           ceiling: int | None) -> PreWideSelection:
    """Bound the Wide population with explicit measured ordering, never list order.

    This is the explicit typed boundary between the complete modality union and
    Wide evaluation. The complete union is already persisted; the population
    entering Jev is all of it while it fits the declared ceiling.

    When a cut is required, states are ordered only by the declared measured
    evidence (affected cases, mutation observation, coverage imbalance) already
    present in the state contract: no Jev judgment, no validation labels, no
    gene-id/database/filesystem/input order. If the ceiling falls inside a group
    of states sharing the boundary key, no scientifically valid deterministic
    choice exists and the run fails closed instead of truncating.
    """
    if ceiling is not None and ceiling < 1:
        raise LiveRunError("INVALID_PRE_WIDE_CEILING", f"ceiling must be positive, got {ceiling}")
    ordered = sorted(states, key=lambda record: (measured_ordering_key(record), record.state_id))
    if ceiling is None or len(ordered) <= ceiling:
        return PreWideSelection(PRE_WIDE_POLICY_VERSION, tuple(ordered), len(ordered), ceiling,
                                (), "WITHIN_CEILING")
    selected: list[StateRecord] = []
    index = 0
    while index < len(ordered) and len(selected) < ceiling:
        key = measured_ordering_key(ordered[index])
        group_end = index
        while group_end < len(ordered) and measured_ordering_key(ordered[group_end]) == key:
            group_end += 1
        group = ordered[index:group_end]
        capacity = ceiling - len(selected)
        if len(group) > capacity:
            raise LiveRunError(
                "PRE_WIDE_ORDERING_AMBIGUOUS",
                f"{len(group)} union states share the boundary ordering key with only "
                f"{capacity} Wide slot(s) left; there is no scientifically valid deterministic "
                "way to choose among them",
            )
        selected.extend(group)
        index = group_end
    excluded = tuple(
        {"state_id": record.state_id, "state_hash": record.state_hash,
         "reason": "BELOW_PRE_WIDE_CUTOFF", **measured_dimensions(record)}
        for record in ordered[index:]
    )
    return PreWideSelection(PRE_WIDE_POLICY_VERSION, tuple(selected), len(ordered), ceiling,
                            excluded, "CUT_AT_MEASURED_ORDERING")


def record_pre_wide_selection(*, run_id: str, selection: PreWideSelection,
                              repository: Repository, publish_json: PublishJson,
                              emit: Callable[..., Any]) -> PublishedArtifact:
    """Persist the pre-Wide policy identity and counts before Wide evaluation."""
    payload = {"kind": "PRE_WIDE_SELECTION", "run_id": run_id, **selection.payload()}
    artifact = publish_json(run_id, f"runs/{run_id}/wide/pre_wide_selection.json",
                            canonical_json(payload), "pre-wide-selection")
    registration = repository.artifact_registration(artifact, run_id)
    emit(
        run_id, "PRE_WIDE_SELECTION_RECORDED", "jev:pre-wide:recorded",
        f"Pre-Wide policy selected {len(selection.states)} of {selection.considered} state(s) "
        f"({selection.reason_code}).",
        stage="JEV_WIDE",
        data={"policy_version": selection.policy_version, "reason_code": selection.reason_code,
              "ordering": PRE_WIDE_ORDERING_DESCRIPTION, "ceiling": selection.ceiling,
              "considered": selection.considered, "selected": len(selection.states),
              "excluded": len(selection.excluded),
              "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
        artifact_refs=[artifact.ref()], registrations=[registration],
    )
    return artifact


def run_wide_evaluation(*, run_id: str, states: list[StateRecord], coverage: str,
                        repository: Repository, jev_service: JevService, emit: Callable[..., Any],
                        publish_json: PublishJson,
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
        skipped_state_ids = [state.state_id for state in states[max_states:]]
        emit(
            run_id, "JEV_WIDE_STATE_CAP_ENFORCED", "jev:wide:state-cap",
            f"Configured Jev state cap {max_states} enforced; {len(skipped_state_ids)} state(s) not evaluated.",
            stage="JEV_WIDE", level="warning",
            data={"cap": max_states, "requested_states": len(states),
                  "evaluated_states": len(evaluated_states), "skipped_state_ids": skipped_state_ids},
        )
    evaluations: list[EvaluationRecord] = []
    deferred: list[str] = []
    for state in evaluated_states:
        symbol = state.state.entity.symbol
        try:
            evaluation = jev_service.evaluate_record(run_id=run_id, state=state, emit=emit)
        except ProjectionError as exc:
            deferred.append(state.state_id)
            emit(
                run_id, "JEV_EVALUATION_FAILED", f"jev-wide:{state.state_id}:projection-failed",
                f"Jev projection failed closed for {symbol or state.state_id}: {exc.code}.",
                stage="JEV_WIDE", level="error",
                data={"state_id": state.state_id, "error_code": exc.code, "detail": str(exc),
                      "provider_attempted": False, "cache": False},
            )
            continue
        if evaluation.error_code is not None:
            deferred.append(state.state_id)
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
    promoted = _promote(run_id, states, evaluations, jev, emit, repository)
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
                     publish_json: PublishJson, repository: Repository) -> PublishedArtifact:
    artifact = publish_json(run_id, f"runs/{run_id}/wide/{filename}", ranking, "wide-ranking")
    repository.register_artifact(artifact, run_id)
    return artifact


def _promote(run_id: str, states: list[StateRecord], evaluations: list[EvaluationRecord],
             jev: dict[str, Any], emit: Callable[..., Any], repository: Repository) -> list[dict[str, Any]]:
    by_state = {state.state_id: state for state in states}
    by_evaluation = {evaluation.input_ref_id: evaluation for evaluation in evaluations}
    promoted: list[dict[str, Any]] = []
    for slot, state_id in enumerate(jev["admitted_state_ids"][:PROMOTION_LIMIT], start=1):
        state = by_state.get(state_id)
        evaluation = by_evaluation.get(state_id)
        if state is None or evaluation is None or evaluation.error_code is not None:
            continue
        entry = next(entry for entry in jev["entries"] if entry["state_id"] == state_id)
        candidate_id = str(uuid4())
        now = utc_now()
        entity = state.state.entity
        summary = {
            "promotion_reason": f"wide-policy-v2 rank {entry['rank']}",
            "policy_version": JEV_POLICY_VERSION,
            "wide_evaluation_id": evaluation.evaluation_id,
            "dimensions": entry["dimensions"],
        }
        registration = repository.candidate_registration(
            candidate_id=candidate_id, run_id=run_id, promotion_slot=slot, status="WIDE_EVALUATED",
            current_stage="JEV_WIDE", source_state_id=state_id,
            entity_json=canonical_json({"gene_id": entity.gene_id,
                                        "gene_symbol": entity.symbol}).decode(),
            summary_json=canonical_json(summary).decode(), created_at=now, updated_at=now,
        )
        emit(
            run_id, "CANDIDATE_PROMOTED", f"candidate:{slot}:promoted",
            f"Promoted {entity.symbol or entity.gene_id} into slot {slot} from the wide Jev ranking.",
            stage="JEV_WIDE", candidate_id=candidate_id,
            data={"candidate_id": candidate_id, "source_state_id": state_id,
                  "evaluation_id": evaluation.evaluation_id, "promotion_slot": slot,
                  "policy_version": JEV_POLICY_VERSION, "reason": summary["promotion_reason"],
                  "dimensions": entry["dimensions"]},
            registrations=[registration],
        )
        promoted.append({"candidate_id": candidate_id, "state_id": state_id, "slot": slot,
                         "evaluation_id": evaluation.evaluation_id})
    return promoted
