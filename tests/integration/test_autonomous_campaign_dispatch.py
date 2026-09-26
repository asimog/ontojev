"""Offline proof that a validated campaign dispatches the canonical systematic path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.cli.main import _dispatch_campaign, _run_campaign_systematic
from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.capability import CapabilityError
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.helpers import canned_capability
from tests.integration.replay import ReplayTransport
from tests.jev.stub_adapter import StubAdapter

VALIDATED = replace(LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_V2",
                    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)


def _stub_jev(settings, repository, artifacts):
    return JevService(settings, repository, artifacts, adapter_factory=lambda: StubAdapter())


def test_validated_campaign_dispatches_the_systematic_pipeline_offline(runtime):
    settings, repository, artifacts = runtime

    def transport_factory(repo, artifact_store, budget, run_id, emit):
        return ReplayTransport(artifact_store, run_id, repository=repo)

    dispatched = _dispatch_campaign(settings, repository, artifacts, VALIDATED,
                                    capability=canned_capability(),
                                    transport_factory=transport_factory,
                                    jev_service=_stub_jev(settings, repository, artifacts))

    assert dispatched is True
    runs = repository.list_runs(10, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert len(runs) == 1, "the dispatch creates exactly one autonomous run"
    run = repository.get_run(runs[0]["run_id"])
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "LIVE"
    assert run["purpose"] == "SYSTEMATIC_CAMPAIGN"
    assert run["spec_id"] == "LUAD_RESEARCH_V1"
    events = repository.events(run["run_id"], 0, 2000)["items"]
    types = [event["type"] for event in events]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_COMPLETED"
    for expected in ("DISCOVERY_COMPLETED", "EXPRESSION_DISCOVERY_COMPLETED",
                     "CNV_PROJECT_SCAN_COMPLETED", "STATISTICAL_STATE_CREATED",
                     "JEV_WIDE_COMPLETED"):
        assert expected in types, f"the canonical spine must include {expected}"
    assert "GDC_FAST_SEARCH" not in {event["stage"] for event in events if event["stage"]}
    assert run["execution"] == "SYSTEMATIC_MODALITY_UNION"
    assert events[0]["data"]["execution"] == "SYSTEMATIC_MODALITY_UNION"
    assert not any(key.startswith("deep_") for key in run), \
        "an autonomous dispatch carries no operator flags"


def test_failed_systematic_campaign_is_terminal_and_not_dispatched(runtime, monkeypatch):
    settings, repository, artifacts = runtime

    def boom(**kwargs):
        raise LiveRunError("TEST_SYSTEMATIC_FAILURE", "systematic execution exploded")

    monkeypatch.setattr("cancerjev.research.systematic.run_systematic_campaign", boom)

    with pytest.raises(LiveRunError):
        _run_campaign_systematic(settings, repository, artifacts, VALIDATED,
                                 LUAD_RESEARCH_V1, canned_capability(),
                                 jev_service=_stub_jev(settings, repository, artifacts))

    runs = repository.list_runs(10, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    assert len(runs) == 1
    assert runs[0]["status"] == "FAILED"
    events = repository.events(runs[0]["run_id"], 0, 100)["items"]
    assert [event["type"] for event in events] == ["RUN_STARTED", "RUN_FAILED"]
    assert events[-1]["data"]["reason_code"] == "TEST_SYSTEMATIC_FAILURE"


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
