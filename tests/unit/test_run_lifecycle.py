"""The shared CLI run lifecycle: every started run reaches a terminal state."""

from __future__ import annotations

import pytest

from cancerjev.cli.main import _discover, _probe, _started_run
from cancerjev.research.acquisition import LiveRunError


def test_normal_exception_ends_the_run_failed(runtime):
    settings, repository, artifacts = runtime

    with pytest.raises(RuntimeError, match="boom"):
        with _started_run(repository, worker_id="lifecycle-test",
                          scope={"purpose": "TEST"}, started_message="test run started") as run_id:
            raise RuntimeError("boom")

    run = repository.get_run(run_id)
    assert run is not None
    assert run["status"] == "FAILED"
    events = repository.events(run_id, 0, 100)["items"]
    assert [event["type"] for event in events] == ["RUN_STARTED", "RUN_FAILED"]
    assert events[-1]["data"]["reason_code"] == "RuntimeError"
    assert repository.recover_interrupted() == []


def test_operator_interrupt_ends_the_run_stopped(runtime):
    settings, repository, artifacts = runtime

    with pytest.raises(KeyboardInterrupt):
        with _started_run(repository, worker_id="lifecycle-test",
                          scope={"purpose": "TEST"}, started_message="test run started") as run_id:
            raise KeyboardInterrupt

    assert repository.get_run(run_id)["status"] == "STOPPED"
    events = repository.events(run_id, 0, 100)["items"]
    assert [event["type"] for event in events] == ["RUN_STARTED", "RUN_STOPPED"]
    assert events[-1]["data"]["reason_code"] == "INTERRUPTED_BY_OPERATOR"
    assert repository.recover_interrupted() == []


def test_probe_failure_leaves_no_running_run(runtime, monkeypatch, tmp_path):
    settings, repository, artifacts = runtime

    def boom(transport, sink, release):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr("cancerjev.cli.main.run_contract_probe", boom)

    with pytest.raises(RuntimeError, match="probe exploded"):
        _probe(settings, repository, artifacts, capture_dir=str(tmp_path / "captures"))

    runs = repository.list_runs(5)
    assert [run["status"] for run in runs] == ["FAILED"]
    assert repository.recover_interrupted() == []


def test_discovery_failure_is_terminal_before_system_exit(runtime, monkeypatch):
    settings, repository, artifacts = runtime

    class _UnusedTransport:
        def __init__(self, *args, **kwargs):
            pass

    def boom(*args, **kwargs):
        raise LiveRunError("TEST_DISCOVERY_FAILURE", "discovery exploded")

    monkeypatch.setattr("cancerjev.cli.main.GDCTransport", _UnusedTransport)
    monkeypatch.setattr("cancerjev.research.discovery.run_mutation_discovery", boom)

    with pytest.raises(SystemExit):
        _discover(settings, repository, artifacts)

    runs = repository.list_runs(5)
    assert [run["status"] for run in runs] == ["FAILED"]
    events = repository.events(runs[0]["run_id"], 0, 100)["items"]
    assert events[-1]["type"] == "RUN_FAILED"
    assert events[-1]["data"]["reason_code"] == "TEST_DISCOVERY_FAILURE"
    assert repository.recover_interrupted() == []
