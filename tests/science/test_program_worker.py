"""Owner-checked program worker with artifact-backed durable state."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import CampaignStatus, ProgramState
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.program import load_program_state, run_program_worker
from cancerjev.storage.ownership import OwnershipError

VALIDATED = replace(LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_V2",
                    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)


def _worker(runtime, *, ownership: ExecutionOwnership = ExecutionOwnership.SYSTEM_AUTONOMOUS):
    _, repository, artifacts = runtime
    run_id = repository.create_run("program-worker", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "PROGRAM"},
                                   ownership=ownership)
    events: list[dict] = []

    def emit(target_run_id: str, event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(target_run_id, event_type=event_type,
                                              idempotency_key=key, message=message, **kwargs))

    def publish_json(target_run_id: str, path: str, payload: bytes, purpose: str):
        return artifacts.publish(path, payload, "application/json", purpose)

    return run_id, repository, artifacts, emit, publish_json, events


def test_program_worker_selects_persists_and_completes(runtime):
    run_id, repository, artifacts, emit, publish_json, events = _worker(runtime)
    calls: list[str] = []

    def succeed(profile) -> bool:
        calls.append(profile.profile_id)
        return True

    outcome, artifact = run_program_worker(
        run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
        publish_json=publish_json, profiles=(VALIDATED, LUAD_CAMPAIGN_V1),
        run_campaign=succeed)

    assert calls == [VALIDATED.profile_id]
    assert outcome.state is ProgramState.CAMPAIGN_COMPLETE
    assert artifact.sha256
    state = load_program_state(run_id=run_id, repository=repository, artifacts=artifacts)
    assert state is not None
    assert state["state"] == "CAMPAIGN_COMPLETE"
    statuses = {campaign["profile_id"]: campaign["status"] for campaign in state["campaigns"]}
    assert statuses[VALIDATED.profile_id] == "CAMPAIGN_COMPLETE"
    assert statuses[LUAD_CAMPAIGN_V1.profile_id] == "PENDING"
    types = [event["type"] for event in events]
    assert "PROGRAM_RUN_STARTED" in types
    assert "CAMPAIGN_SELECTED" in types
    assert "CAMPAIGN_COMPLETED" in types


def test_program_worker_idles_without_eligible_campaigns(runtime):
    run_id, repository, artifacts, emit, publish_json, events = _worker(runtime)
    completed = replace(VALIDATED, status=CampaignStatus.CAMPAIGN_COMPLETE)

    outcome, _ = run_program_worker(
        run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
        publish_json=publish_json, profiles=(completed, LUAD_CAMPAIGN_V1),
        run_campaign=lambda profile: True)

    assert outcome.state is ProgramState.PROGRAM_IDLE
    assert outcome.selected_profile_id is None
    assert "PROGRAM_IDLE" in [event["type"] for event in events]


def test_program_cli_step_records_idle_and_persists_state(runtime):
    from cancerjev.cli.main import _program

    settings, repository, artifacts = runtime
    _program(settings, repository, artifacts)

    runs = repository.list_runs(5, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert runs
    run_id = runs[0]["run_id"]
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    types = [event["type"] for event in repository.events(run_id, 0, 200)["items"]]
    assert "RUN_STARTED" in types and "PROGRAM_IDLE" in types and "RUN_COMPLETED" in types
    state = load_program_state(run_id=run_id, repository=repository, artifacts=artifacts)
    assert state is not None and state["state"] == "PROGRAM_IDLE"


def test_program_worker_refuses_a_researcher_owned_run(runtime):
    run_id, repository, artifacts, emit, publish_json, _ = _worker(
        runtime, ownership=ExecutionOwnership.RESEARCHER_RUN)

    with pytest.raises(OwnershipError):
        run_program_worker(
            run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
            publish_json=publish_json, profiles=(VALIDATED,), run_campaign=lambda profile: True)
