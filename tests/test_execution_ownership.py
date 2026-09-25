"""Execution-ownership isolation: recorded owner, bilateral gates, operator boundary."""

from __future__ import annotations

import pytest

from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.storage.ownership import OwnershipError
from tests.integration.replay import ReplayTransport


def _run(repository, ownership: ExecutionOwnership) -> str:
    return repository.create_run("ownership-test", mode="LIVE", fixture_id=None,
                                 fixture_version=None, scope={"purpose": "OWNERSHIP"},
                                 ownership=ownership)


def test_owner_is_recorded_and_listing_can_scope_by_owner(runtime):
    _, repository, _ = runtime
    autonomous = _run(repository, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    researcher = _run(repository, ExecutionOwnership.RESEARCHER_RUN)

    assert repository.run_ownership(autonomous) is ExecutionOwnership.SYSTEM_AUTONOMOUS
    assert repository.run_ownership(researcher) is ExecutionOwnership.RESEARCHER_RUN
    listed = {row["run_id"] for row in repository.list_runs(10, ownership=ExecutionOwnership.RESEARCHER_RUN)}
    assert listed == {researcher}
    assert {row["run_id"] for row in repository.list_runs(10)} >= {autonomous, researcher}


def test_cross_owner_guards_fail_closed_in_both_directions(runtime):
    _, repository, _ = runtime
    autonomous = _run(repository, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    researcher = _run(repository, ExecutionOwnership.RESEARCHER_RUN)

    repository.require_run_ownership(autonomous, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    repository.require_run_ownership(researcher, ExecutionOwnership.RESEARCHER_RUN)
    with pytest.raises(OwnershipError) as failure:
        repository.require_run_ownership(autonomous, ExecutionOwnership.RESEARCHER_RUN)
    assert "RUN_OWNERSHIP_MISMATCH" in str(failure.value)
    with pytest.raises(OwnershipError):
        repository.require_run_ownership(researcher, ExecutionOwnership.SYSTEM_AUTONOMOUS)


def test_autonomous_runs_reject_operator_deep_flags_before_any_work(runtime):
    settings, repository, artifacts = runtime

    def forbidden_factory(repo, store, budget, run_id, emit):
        raise AssertionError("no transport may be created for a rejected operator run")

    orchestrator = LiveOrchestrator(
        settings, repository, artifacts, lambda *args, **kwargs: None,
        transport_factory=forbidden_factory, research_spec=LUAD_RESEARCH_V1,
        deep_selection="GENEONE", execution_ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)

    with pytest.raises(LiveRunError) as failure:
        orchestrator.run()

    assert failure.value.code == "OPERATOR_FLAGS_REQUIRE_RESEARCHER_RUN"
    assert repository.list_runs(10, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS) == []


def test_researcher_runs_keep_their_own_scope(runtime, monkeypatch):

    settings, repository, artifacts = runtime
    holder: dict = {}

    def factory(repo, store, budget, run_id, emit):
        transport = ReplayTransport(store, run_id, repository=repo)
        holder["transport"] = transport
        return transport

    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    orchestrator = LiveOrchestrator(
        settings, repository, artifacts, lambda *args, **kwargs: None,
        transport_factory=factory, research_spec=LUAD_RESEARCH_V1,
        execution_ownership=ExecutionOwnership.RESEARCHER_RUN)
    run_id = orchestrator.run()

    assert repository.get_run(run_id)["status"] == "COMPLETED"
    assert repository.run_ownership(run_id) is ExecutionOwnership.RESEARCHER_RUN
    rows = repository.list_table("statistical_states", run_id)
    assert rows, "researcher runs still produce their own typed states"
    assert all(row["run_id"] == run_id for row in rows)
