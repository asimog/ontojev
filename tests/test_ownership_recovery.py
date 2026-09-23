from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from cancerjev.storage.artifacts import PublishedArtifact
from cancerjev.storage.ownership import OwnershipError, ResearchOwnership

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_second_research_owner_is_rejected(runtime):
    settings, repository, _ = runtime
    before = len(repository.list_runs())
    with ResearchOwnership(settings.lock_path):
        with pytest.raises(OwnershipError):
            with ResearchOwnership(settings.lock_path):
                repository.create_run("should-not-happen")
    assert len(repository.list_runs()) == before


def test_second_research_owner_in_another_process_is_rejected(runtime):
    settings, repository, _ = runtime
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from cancerjev.storage.ownership import ResearchOwnership\n"
        "with ResearchOwnership(Path(sys.argv[1])):\n"
        "    print('locked', flush=True)\n"
        "    time.sleep(10)\n"
    )
    environment = {**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT)}
    holder = subprocess.Popen(
        [sys.executable, "-c", script, str(settings.lock_path)],
        stdout=subprocess.PIPE, text=True, env=environment, cwd=REPOSITORY_ROOT,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(OwnershipError):
            with ResearchOwnership(settings.lock_path):
                repository.create_run("should-not-happen")
    finally:
        holder.kill()
        holder.wait(timeout=10)
    assert repository.list_runs() == []


def test_recovery_preserves_interrupted_run_and_new_id(runtime):
    _, repository, _ = runtime
    old_id = repository.create_run("old")
    repository.append_event(old_id, event_type="RUN_CREATED", idempotency_key="created", message="created")
    repository.append_event(old_id, event_type="RUN_STARTED", idempotency_key="started", message="started")
    original_events = repository.events(old_id, 0, 20)["items"]
    assert repository.recover_interrupted() == [old_id]
    assert repository.get_run(old_id)["status"] == "STOPPED"
    assert repository.get_run(old_id)["outcome_reason"] == "INTERRUPTED"
    assert repository.events(old_id, 0, 20)["items"][:2] == original_events
    new_id = repository.create_run("new")
    assert new_id != old_id


def test_recovery_defers_in_flight_candidates_without_replay(runtime):
    _, repository, _ = runtime
    run_id = repository.create_run("old")
    repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="created", message="created")
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="started", message="started")
    state_id = str(uuid4())
    artifact = PublishedArtifact(
        artifact_id=str(uuid4()), relative_path="statistical_states/recovery-synthetic.json",
        sha256="a" * 64, size_bytes=2, media_type="application/json", purpose="statistical-state",
    )
    repository.register_artifact(artifact, run_id)
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key="state", message="state",
        stage="STATE_GENERATION",
        registrations=[repository.state_registration(
            state_id=state_id, run_id=run_id, state_hash="a" * 64, artifact_id=artifact.artifact_id,
            disposition="PROMOTED", summary_json="{}", created_at="2026-01-01T00:00:00Z",
        )],
    )
    candidate_id = str(uuid4())
    repository.append_event(
        run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="promoted", message="promoted",
        stage="JEV_WIDE", candidate_id=candidate_id,
        data={"candidate_id": candidate_id, "source_state_id": state_id, "evaluation_id": str(uuid4()),
              "promotion_slot": 1, "policy_version": "fixture-v1", "reason": "fixture"},
        registrations=[repository.candidate_registration(
            candidate_id=candidate_id, run_id=run_id, promotion_slot=1, status="WIDE_EVALUATED",
            current_stage="JEV_WIDE", source_state_id=state_id, entity_json="{}", summary_json="{}",
            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )],
    )
    original_events = repository.events(run_id, 0, 20)["items"]
    assert repository.recover_interrupted() == [run_id]
    run = repository.get_run(run_id)
    assert run["status"] == "STOPPED" and run["outcome_reason"] == "INTERRUPTED"
    candidate = repository.list_table("candidates", run_id)[0]
    assert candidate["status"] == "DEFERRED"
    assert candidate["summary"]["terminal_reason"] == "INTERRUPTED"
    events = repository.events(run_id, 0, 50)["items"]
    assert events[: len(original_events)] == original_events
    assert [event["type"] for event in events[len(original_events):]] == ["CANDIDATE_DEFERRED", "RUN_STOPPED"]
    assert all(event["type"] not in {"STAGE_STARTED", "EVIDENCE_STATE_CREATED"} for event in events)
