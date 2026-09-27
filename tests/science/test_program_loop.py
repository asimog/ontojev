"""Durable program loop: restart safety, identity changes, backoff, lock discipline."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from cancerjev.cli.main import PROGRAM_PROFILES, _program, main
from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import ProgramState
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.campaign_selection import (
    MAX_CAMPAIGN_ATTEMPTS,
    RETRY_BACKOFF_REASON,
    RETRY_EXHAUSTED_REASON,
)
from cancerjev.research.program import load_program_state, run_program_worker
from cancerjev.science.errors import ScienceError
from cancerjev.storage.ownership import ResearchOwnership
from tests.helpers import canned_capability, fake_release_observation

VALIDATED = replace(LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_VALIDATED_TEST",
                    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)
METHOD = "test-method-v1"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _cycle(runtime, *, profiles, run_campaign, observation=None, method_identity=METHOD, now=NOW):
    _, repository, artifacts = runtime
    run_id = repository.create_run("program-worker", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "PROGRAM"},
                                   ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    events: list[dict] = []

    def emit(target_run_id: str, event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(target_run_id, event_type=event_type,
                                              idempotency_key=key, message=message, **kwargs))

    def publish_json(target_run_id: str, path: str, payload: bytes, purpose: str):
        return artifacts.publish(path, payload, "application/json", purpose)

    outcome, artifact = run_program_worker(
        run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
        publish_json=publish_json, profiles=profiles, run_campaign=run_campaign,
        observe=(lambda: observation) if observation is not None else None,
        method_identity=method_identity, now=now)
    return run_id, events, outcome, artifact, repository, artifacts


def test_completed_campaign_is_not_redispatched_after_a_restart(runtime):
    observation = fake_release_observation()
    calls: list[str] = []

    def succeed(profile) -> bool:
        calls.append(profile.profile_id)
        return True

    first = _cycle(runtime, profiles=(VALIDATED,), run_campaign=succeed, observation=observation)
    assert calls == [VALIDATED.profile_id]
    assert first[2].state is ProgramState.CAMPAIGN_COMPLETE

    later: list[str] = []
    second = _cycle(runtime, profiles=(VALIDATED,),
                    run_campaign=lambda profile: later.append(profile.profile_id) or True,
                    observation=observation)
    assert later == [], "a completed same-identity campaign is never redispatched"
    assert second[2].state is ProgramState.PROGRAM_IDLE
    assert second[2].reasons_by_profile[VALIDATED.profile_id] == \
        "CAMPAIGN_ALREADY_COMPLETE_FOR_IDENTITY"

    state = load_program_state(repository=second[4], artifacts=second[5])
    assert state is not None
    campaign = next(item for item in state["campaigns"]
                    if item["profile_id"] == VALIDATED.profile_id)
    assert campaign["status"] == "CAMPAIGN_COMPLETE"
    assert campaign["release_identity"] == state["release_identity"]
    assert state["release"] == observation.release
    assert state["method_identity"] == METHOD


def test_completed_campaign_is_recovered_when_the_state_publish_was_interrupted(runtime):
    observation = fake_release_observation()
    calls: list[str] = []
    _, repository, artifacts = runtime

    run_id = repository.create_run("program-worker", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "PROGRAM"},
                                   ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    events: list[dict] = []

    def emit(target_run_id: str, event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(target_run_id, event_type=event_type,
                                              idempotency_key=key, message=message, **kwargs))

    def crash_before_publish(*args, **kwargs):
        raise RuntimeError("process died before the program state was published")

    with pytest.raises(RuntimeError):
        run_program_worker(
            run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
            publish_json=crash_before_publish, profiles=(VALIDATED,),
            run_campaign=lambda profile: calls.append(profile.profile_id) or True,
            observe=lambda: observation, method_identity=METHOD, now=NOW)

    assert calls == [VALIDATED.profile_id]
    assert "CAMPAIGN_COMPLETED" in [event["type"] for event in events], \
        "the simulated crash happened after completion, before the state publish"
    assert load_program_state(repository=repository, artifacts=artifacts) is None

    second = _cycle(runtime, profiles=(VALIDATED,),
                    run_campaign=lambda profile: calls.append(profile.profile_id) or True,
                    observation=observation)

    assert calls == [VALIDATED.profile_id], "the recorded completion is never rerun"
    assert "CAMPAIGN_COMPLETION_RECOVERED" in [event["type"] for event in second[1]]
    state = load_program_state(repository=second[4], artifacts=second[5])
    assert state is not None
    campaign = next(item for item in state["campaigns"]
                    if item["profile_id"] == VALIDATED.profile_id)
    assert campaign["status"] == "CAMPAIGN_COMPLETE"
    assert campaign["release_identity"] == state["release_identity"]


def test_declared_identity_changes_make_a_completed_campaign_eligible(runtime):
    succeed = lambda profile: True  # noqa: E731 - tiny deterministic callback
    _cycle(runtime, profiles=(VALIDATED,), run_campaign=succeed,
           observation=fake_release_observation(release="Data Release 38.0"))

    changed_release = _cycle(
        runtime, profiles=(VALIDATED,), run_campaign=succeed,
        observation=fake_release_observation(release="Data Release 47.0"))
    assert changed_release[2].reasons_by_profile[VALIDATED.profile_id] == "RELEASE_CHANGED"
    assert changed_release[2].state is ProgramState.CAMPAIGN_COMPLETE

    changed_method = _cycle(
        runtime, profiles=(VALIDATED,), run_campaign=succeed,
        observation=fake_release_observation(release="Data Release 47.0"),
        method_identity="test-method-v2")
    assert changed_method[2].reasons_by_profile[VALIDATED.profile_id] == "METHOD_CHANGED"

    changed_profile = replace(VALIDATED, readiness_reason="profile payload changed")
    profile_change = _cycle(
        runtime, profiles=(changed_profile,), run_campaign=succeed,
        observation=fake_release_observation(release="Data Release 47.0"),
        method_identity="test-method-v2")
    assert profile_change[2].reasons_by_profile[VALIDATED.profile_id] == "PROFILE_CHANGED"


def test_release_downgrade_does_not_redispatch_a_completed_campaign(runtime):
    _cycle(runtime, profiles=(VALIDATED,), run_campaign=lambda profile: True,
           observation=fake_release_observation(release="Data Release 47.0"))
    calls: list[str] = []

    downgrade = _cycle(
        runtime, profiles=(VALIDATED,),
        run_campaign=lambda profile: calls.append(profile.profile_id) or True,
        observation=fake_release_observation(release="Data Release 39.0"))

    assert calls == [], "a downgrade never redispatches a completed campaign"
    assert downgrade[2].reasons_by_profile[VALIDATED.profile_id] == "RELEASE_NOT_ORDERABLE"
    assert downgrade[2].state is ProgramState.PROGRAM_IDLE


def test_status_body_change_does_not_redispatch_a_completed_campaign(runtime):
    _cycle(runtime, profiles=(VALIDATED,), run_campaign=lambda profile: True,
           observation=fake_release_observation(release="Data Release 47.0"))
    calls: list[str] = []

    same_release_new_body = _cycle(
        runtime, profiles=(VALIDATED,),
        run_campaign=lambda profile: calls.append(profile.profile_id) or True,
        observation=fake_release_observation(release="Data Release 47.0",
                                             response_hash="c" * 64))

    assert calls == [], "the response body hash is provenance, never identity"
    assert same_release_new_body[2].reasons_by_profile[VALIDATED.profile_id] == \
        "CAMPAIGN_ALREADY_COMPLETE_FOR_IDENTITY"


def test_unverified_release_fails_closed_instead_of_dispatching(runtime):
    calls: list[str] = []

    outcome = _cycle(
        runtime, profiles=(VALIDATED,),
        run_campaign=lambda profile: calls.append(profile.profile_id) or True,
        observation=fake_release_observation(release="UNVERIFIED_RELEASE"))

    assert calls == [], "a campaign is never dispatched without a verified release"
    assert outcome[2].state is ProgramState.PROGRAM_IDLE
    assert outcome[2].reasons_by_profile[VALIDATED.profile_id] == "RELEASE_UNVERIFIED"
    state = load_program_state(repository=outcome[4], artifacts=outcome[5])
    assert state is not None
    campaign = next(item for item in state["campaigns"]
                    if item["profile_id"] == VALIDATED.profile_id)
    assert campaign["status"] == "PENDING" and campaign["attempts"] == 0


def test_failed_campaign_receives_bounded_backoff_and_then_stops(runtime):
    observation = fake_release_observation()
    calls: list[float] = []

    def fail(profile) -> bool:
        calls.append(1.0)
        return False

    first = _cycle(runtime, profiles=(VALIDATED,), run_campaign=fail,
                   observation=observation, now=NOW)
    record = next(item for item in first[2].records if item.profile_id == VALIDATED.profile_id)
    assert first[2].state is ProgramState.BLOCKED_NOT_READY
    assert first[2].reason_code == "CAMPAIGN_RETRY_SCHEDULED"
    assert record.attempts == 1 and record.next_attempt_at is not None
    assert "CAMPAIGN_BLOCKED" in [event["type"] for event in first[1]]

    second = _cycle(runtime, profiles=(VALIDATED,), run_campaign=fail,
                    observation=observation, now=NOW + timedelta(seconds=1))
    assert len(calls) == 1, "the retry waits out its bounded backoff"
    assert second[2].reasons_by_profile[VALIDATED.profile_id] == RETRY_BACKOFF_REASON

    moment = NOW + timedelta(seconds=10_000)
    for _ in range(MAX_CAMPAIGN_ATTEMPTS - 1):
        last = _cycle(runtime, profiles=(VALIDATED,), run_campaign=fail,
                      observation=observation, now=moment)
        moment += timedelta(seconds=10_000)
    record = next(item for item in last[2].records if item.profile_id == VALIDATED.profile_id)
    assert record.attempts == MAX_CAMPAIGN_ATTEMPTS
    assert record.next_attempt_at is None
    assert record.reason_code == RETRY_EXHAUSTED_REASON

    exhausted = _cycle(runtime, profiles=(VALIDATED,), run_campaign=fail,
                       observation=observation, now=moment + timedelta(seconds=10_000))
    assert exhausted[2].state is ProgramState.PROGRAM_IDLE
    assert exhausted[2].reasons_by_profile[VALIDATED.profile_id] == RETRY_EXHAUSTED_REASON


def test_release_observation_failure_ends_the_cli_cycle_failed(runtime, monkeypatch):
    settings, repository, artifacts = runtime

    def broken(transport):
        raise RuntimeError("status endpoint unavailable")

    monkeypatch.setattr("cancerjev.research.release_monitor.observe_release", broken)

    with pytest.raises(RuntimeError):
        _program(settings, repository, artifacts)

    runs = repository.list_runs(5, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert runs[0]["status"] == "FAILED", "the CLI lifecycle marks the cycle terminal"


def test_dispatch_science_error_increments_the_attempt_ledger(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setattr("cancerjev.cli.main.PROGRAM_PROFILES", (VALIDATED,))
    monkeypatch.setattr("cancerjev.research.release_monitor.observe_release",
                        lambda transport: fake_release_observation())
    monkeypatch.setattr("cancerjev.cli.main.GDCTransport", _NoopTransport)

    def explode(*args, **kwargs):
        raise ScienceError("TEST_SCIENCE_FAILURE", "the science lane refused")

    monkeypatch.setattr("cancerjev.cli.main._dispatch_campaign", explode)

    _program(settings, repository, artifacts)

    state = load_program_state(repository=repository, artifacts=artifacts)
    assert state is not None
    campaign = next(item for item in state["campaigns"]
                    if item["profile_id"] == VALIDATED.profile_id)
    assert campaign["status"] == "BLOCKED"
    assert campaign["attempts"] == 1, "a science failure still uses the attempt ledger"
    runs = repository.list_runs(5, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    events = repository.events(runs[0]["run_id"], 0, 200)["items"]
    assert "CAMPAIGN_DISPATCH_FAILED" in [event["type"] for event in events]
    assert events[-1]["type"] == "RUN_COMPLETED", "the cycle ends terminal, not crashed"


def test_worker_releases_the_research_lock_while_sleeping(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    cycles: list[int] = []
    monkeypatch.setattr("cancerjev.cli.main._program", lambda *args: cycles.append(1))
    acquired: list[bool] = []

    def sleeper(seconds: float) -> None:
        with ResearchOwnership(settings.lock_path):
            acquired.append(True)
        raise KeyboardInterrupt

    monkeypatch.setattr("cancerjev.cli.main.time.sleep", sleeper)
    main(["worker", "--live"])

    assert cycles == [1]
    assert acquired == [True], "the lock is free while the worker sleeps"


def test_worker_defers_a_cycle_when_the_research_lock_is_held(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    cycles: list[int] = []
    monkeypatch.setattr("cancerjev.cli.main._program", lambda *args: cycles.append(1))
    sleeps: list[float] = []

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr("cancerjev.cli.main.time.sleep", sleeper)

    with ResearchOwnership(settings.lock_path):
        main(["worker", "--live"])

    assert cycles == [], "a cycle never runs while another owner holds the lock"
    assert len(sleeps) == 2, "contention defers, then retries; the worker never exits"
    assert all(seconds > 0 for seconds in sleeps)


def test_worker_persists_a_failed_cycle_and_keeps_running(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    monkeypatch.setattr("cancerjev.cli.main.PROGRAM_PROFILES", (VALIDATED,))
    monkeypatch.setattr("cancerjev.research.release_monitor.observe_release",
                        lambda transport: fake_release_observation())
    monkeypatch.setattr("cancerjev.cli.main.GDCTransport", _NoopTransport)

    def explode(*args, **kwargs):
        raise RuntimeError("synthetic dispatch defect")

    monkeypatch.setattr("cancerjev.cli.main._dispatch_campaign", explode)

    def sleeper(seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("cancerjev.cli.main.time.sleep", sleeper)
    main(["worker", "--live"])

    runs = repository.list_runs(5, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert runs[0]["status"] == "FAILED"
    events = repository.events(runs[0]["run_id"], 0, 200)["items"]
    assert events[-1]["type"] == "RUN_FAILED", \
        "a failed cycle is persisted as an event, never print-only"
    assert events[-1]["data"]["reason_code"] == "RuntimeError"


def test_worker_dispatches_the_canonical_executor(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setattr("cancerjev.cli.main.PROGRAM_PROFILES", (VALIDATED,))
    monkeypatch.setattr("cancerjev.research.release_monitor.observe_release",
                        lambda transport: fake_release_observation())
    monkeypatch.setattr("cancerjev.cli.main.GDCTransport", _NoopTransport)
    monkeypatch.setattr("cancerjev.research.capability.discover_cohort_capability",
                        lambda transport, project_id: canned_capability())
    monkeypatch.setattr("cancerjev.cli.main.LiveOrchestrator", _NoLiveOrchestrator)
    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-key")

    calls: list[dict] = []

    def fake_systematic_campaign(**kwargs):
        calls.append(kwargs)
        return _FakeCampaignResult()

    monkeypatch.setattr("cancerjev.research.systematic.run_systematic_campaign",
                        fake_systematic_campaign)

    _program(settings, repository, artifacts)

    assert len(calls) == 1, "the canonical executor handles the autonomous dispatch"
    assert calls[0]["profile"].profile_id == VALIDATED.profile_id
    state = load_program_state(repository=repository, artifacts=artifacts)
    assert state is not None and state["state"] == "CAMPAIGN_COMPLETE"
    campaign_run_id = calls[0]["run_id"]
    types = [event["type"] for event in repository.events(campaign_run_id, 0, 200)["items"]]
    assert "RUN_COMPLETED" in types


class _NoopTransport:
    def __init__(self, *args, **kwargs):
        pass


class _NoLiveOrchestrator:
    def __init__(self, *args, **kwargs):
        raise AssertionError("the autonomous worker must not use the legacy sweep")


class _FakeCampaignResult:
    state_ids = ("state-1",)
    coverage = "COMPLETE_FOR_SCOPE"

    def summary(self) -> dict:
        return {"execution": "SYSTEMATIC_MODALITY_UNION", "states": 1}


def test_program_profiles_seam_defaults_to_the_experimental_luad_profile():
    assert PROGRAM_PROFILES == (LUAD_CAMPAIGN_V1,)


def test_release_observation_binds_the_run_emitter(runtime, monkeypatch):
    """The GDC transport emits three-argument events; the program cycle must bind them."""
    settings, repository, artifacts = runtime
    seen: list[str] = []

    class RecordingTransport:
        def __init__(self, repo, arts, budget, run_id, emit, cache_enabled=False):
            self._emit = emit

        def request(self, request):
            self._emit("GDC_REQUEST_STARTED", "test:status", "recorded transport attempt")
            seen.append("request")
            return object()

    def fake_observe(transport):
        transport.request(object())
        return fake_release_observation()

    monkeypatch.setattr("cancerjev.cli.main.GDCTransport", RecordingTransport)
    monkeypatch.setattr("cancerjev.research.release_monitor.observe_release", fake_observe)

    _program(settings, repository, artifacts)

    runs = repository.list_runs(5, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    types = [event["type"] for event in repository.events(runs[0]["run_id"], 0, 200)["items"]]
    assert seen == ["request"]
    assert "GDC_REQUEST_STARTED" in types
    assert "RELEASE_OBSERVED" in types
    assert "RUN_COMPLETED" in types
