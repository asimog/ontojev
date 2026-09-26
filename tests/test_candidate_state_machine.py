"""Candidate lifecycle is a state machine, not a convention.

The repository refuses illegal candidate transitions the same way run status is
enforced, crash recovery never rewrites a dossier-owning or terminal candidate,
and the vocabulary is single-sourced from ``CandidateStatus``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cancerjev.domain.measurements import ContractError
from cancerjev.domain.states import (
    CANDIDATE_TRANSITIONS,
    RECOVERY_DEFERRABLE_CANDIDATE_STATUSES,
    TERMINAL_CANDIDATE_STATUSES,
    CandidateStatus,
    validate_candidate_transition,
)
from cancerjev.storage.artifacts import PublishedArtifact


def test_declared_transition_table_is_fail_closed():
    validate_candidate_transition("WIDE_EVALUATED", "DEEP_ANALYZED")
    validate_candidate_transition("DEEP_ANALYZED", "DEEP_ANALYZED")
    validate_candidate_transition("DEEP_ANALYZED", "HYPOTHESIZED")
    validate_candidate_transition("HYPOTHESIZED", "DOSSIER_READY")
    validate_candidate_transition("DOSSIER_READY", "CANDIDATE_COMPLETE")

    with pytest.raises(ValueError, match="illegal candidate transition"):
        validate_candidate_transition("WIDE_EVALUATED", "CANDIDATE_COMPLETE")
    with pytest.raises(ValueError, match="illegal candidate transition"):
        validate_candidate_transition("CANDIDATE_COMPLETE", "DEEP_ANALYZED")
    with pytest.raises(ValueError, match="unknown candidate status"):
        validate_candidate_transition("WIDE_EVALUATED", "DEEP_ANALYSIS")


def test_terminal_statuses_have_no_outgoing_edges():
    for status in TERMINAL_CANDIDATE_STATUSES:
        assert CANDIDATE_TRANSITIONS[status] == frozenset()
    assert CandidateStatus.CANDIDATE_COMPLETE in TERMINAL_CANDIDATE_STATUSES
    assert CandidateStatus.DOSSIER_READY not in TERMINAL_CANDIDATE_STATUSES
    assert CandidateStatus.DOSSIER_READY not in RECOVERY_DEFERRABLE_CANDIDATE_STATUSES


def _promoted_candidate(repository, run_id: str, *, slot: int = 1) -> str:
    state_id = str(uuid4())
    artifact = PublishedArtifact(
        artifact_id=str(uuid4()),
        relative_path=f"statistical_states/candidate-state-{slot}.json",
        sha256="a" * 64, size_bytes=2, media_type="application/json", purpose="statistical-state",
    )
    repository.register_artifact(artifact, run_id)
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key=f"state:{slot}",
        message="state", stage="STATE_GENERATION",
        registrations=[repository.state_registration(
            state_id=state_id, run_id=run_id, state_hash="a" * 64,
            artifact_id=artifact.artifact_id, disposition="PROMOTED", summary_json="{}",
            created_at="2026-01-01T00:00:00Z",
        )],
    )
    candidate_id = str(uuid4())
    repository.append_event(
        run_id, event_type="CANDIDATE_PROMOTED", idempotency_key=f"promoted:{slot}",
        message="promoted", stage="JEV_WIDE", candidate_id=candidate_id,
        data={"candidate_id": candidate_id},
        registrations=[repository.candidate_registration(
            candidate_id=candidate_id, run_id=run_id, promotion_slot=slot,
            status="WIDE_EVALUATED", current_stage="JEV_WIDE", source_state_id=state_id,
            entity_json="{}", summary_json="{}",
            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )],
    )
    return candidate_id


def _advance(repository, run_id: str, candidate_id: str, status: str, key: str) -> None:
    repository.append_event(
        run_id, event_type="CANDIDATE_COMPLETED", idempotency_key=key, message=status,
        stage="FINALIZATION", candidate_id=candidate_id, data={"status": status},
        registrations=[repository.candidate_status_registration(
            candidate_id=candidate_id, status=status, current_stage=None,
            updated_at="2026-01-01T00:00:00Z")],
    )


def test_repository_refuses_an_illegal_candidate_transition(runtime):
    _, repository, _ = runtime
    run_id = repository.create_run("state-machine-test")
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="started",
                            message="started")
    candidate_id = _promoted_candidate(repository, run_id)

    with pytest.raises(ContractError) as failure:
        repository.candidate_status_registration(
            candidate_id=candidate_id, status="CANDIDATE_COMPLETE", current_stage=None,
            updated_at="2026-01-01T00:00:00Z")
    assert failure.value.code == "ILLEGAL_CANDIDATE_TRANSITION"
    assert repository.get_candidate(candidate_id)["status"] == "WIDE_EVALUATED"

    with pytest.raises(ContractError) as missing:
        repository.candidate_status_registration(
            candidate_id=str(uuid4()), status="DEEP_ANALYZED", current_stage=None,
            updated_at="2026-01-01T00:00:00Z")
    assert missing.value.code == "CANDIDATE_NOT_FOUND"


def test_recovery_preserves_dossier_ready_and_completed_candidates(runtime):
    _, repository, _ = runtime
    run_id = repository.create_run("recovery-state-machine")
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="started",
                            message="started")
    completed = _promoted_candidate(repository, run_id, slot=1)
    dossier_ready = _promoted_candidate(repository, run_id, slot=2)
    in_flight = _promoted_candidate(repository, run_id, slot=3)

    _advance(repository, run_id, completed, "DEEP_ANALYZED", "c1")
    _advance(repository, run_id, completed, "DOSSIER_READY", "c2")
    _advance(repository, run_id, completed, "CANDIDATE_COMPLETE", "c3")
    _advance(repository, run_id, dossier_ready, "DEEP_ANALYZED", "d1")
    _advance(repository, run_id, dossier_ready, "DOSSIER_READY", "d2")
    _advance(repository, run_id, in_flight, "DEEP_ANALYZED", "f1")

    assert repository.recover_interrupted() == [run_id]

    statuses = {row["candidate_id"]: row["status"]
                for row in repository.list_table("candidates", run_id)}
    assert statuses[completed] == "CANDIDATE_COMPLETE", "completion is never undone by recovery"
    assert statuses[dossier_ready] == "DOSSIER_READY", "a dossier-owning candidate is preserved"
    assert statuses[in_flight] == "DEFERRED"
