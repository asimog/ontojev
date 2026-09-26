"""Offline proof that a validated campaign dispatches the bounded sweep autonomously."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.cli.main import _dispatch_campaign, _run_campaign_sweep
from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.capability import CapabilityError
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.helpers import canned_capability
from tests.integration.replay import ReplayTransport

VALIDATED = replace(LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_V2",
                    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)


def test_validated_campaign_dispatches_the_bounded_sweep_offline(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))

    def transport_factory(repo, artifact_store, budget, run_id, emit):
        return ReplayTransport(artifact_store, run_id, repository=repo)

    dispatched = _dispatch_campaign(settings, repository, artifacts, VALIDATED,
                                    capability=canned_capability(),
                                    transport_factory=transport_factory)

    assert dispatched is True
    runs = repository.list_runs(10, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert len(runs) == 1, "the dispatch creates exactly one autonomous run"
    run = repository.get_run(runs[0]["run_id"])
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "LIVE"
    assert run["purpose"] == "LIVE_SWEEP"
    assert run["spec_id"] == "LUAD_RESEARCH_V1"
    events = repository.events(run["run_id"], 0, 1000)["items"]
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_COMPLETED"
    started = events[0]["data"]
    assert not any((started["deep_selection"], started["deep_selections"],
                    started["deep_action_id"], started["deep_followup_authorized"],
                    started["deep_hypotheses_requested"])), \
        "an autonomous dispatch carries no operator flags"


def test_failed_sweep_is_not_reported_as_dispatched(runtime, monkeypatch):
    settings, repository, artifacts = runtime

    class _FailingOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            run_id = repository.create_run(
                "campaign-worker", mode="LIVE", fixture_id=None, fixture_version=None,
                scope={"purpose": "LIVE_SWEEP"}, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
            repository.append_event(run_id, event_type="RUN_STARTED",
                                    idempotency_key="run:started", message="sweep started")
            repository.append_event(run_id, event_type="RUN_FAILED",
                                    idempotency_key="run:failed", message="sweep failed",
                                    level="error", data={"status": "FAILED",
                                                         "reason_code": "TEST_TRANSPORT_FAILURE",
                                                         "coverage": "PARTIAL"})
            return run_id

    monkeypatch.setattr("cancerjev.cli.main.LiveOrchestrator", _FailingOrchestrator)

    assert _run_campaign_sweep(settings, repository, artifacts, VALIDATED,
                               LUAD_RESEARCH_V1, None) is False


def test_capability_preflight_failure_is_recorded_and_raised(runtime):
    settings, repository, artifacts = runtime

    class _FailingTransport:
        def request(self, request):
            raise CapabilityError("PROJECT_NOT_FOUND", "test project is missing")

    def transport_factory(repo, artifact_store, budget, run_id, emit):
        return _FailingTransport()

    with pytest.raises(CapabilityError):
        _dispatch_campaign(settings, repository, artifacts, VALIDATED,
                           transport_factory=transport_factory)

    runs = repository.list_runs(10, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert len(runs) == 1
    assert runs[0]["status"] == "FAILED"
    events = repository.events(runs[0]["run_id"], 0, 100)["items"]
    assert [event["type"] for event in events] == ["RUN_STARTED", "RUN_FAILED"]
    assert events[-1]["data"]["reason_code"] == "PROJECT_NOT_FOUND"
