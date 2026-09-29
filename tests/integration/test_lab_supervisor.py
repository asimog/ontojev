"""Worker startup exclusion and supervisor failure reporting at durable boundaries."""

import sys

import pytest

from cancerjev.research import lab_worker
from cancerjev.research.laboratory import load_lab, next_revision, save_lab
from cancerjev.storage.ownership import OwnershipError, ResearchOwnership


@pytest.mark.parametrize("exit_code, reason", [(1, "OPERATION_FAILED"), (124, "CONTINUE_NEXT_RUN")])
def test_failure_after_portfolio_commit_keeps_science_and_reports_failure(runtime, monkeypatch, exit_code, reason):
    settings, repository, artifacts = runtime

    def committed_then_failed(command, *, timeout):
        run_id = command[command.index("--child") + 1]
        state = next_revision(repository, load_lab(repository, artifacts), run_id)
        save_lab(repository, artifacts, run_id, state)
        return exit_code

    monkeypatch.setattr(lab_worker, "supervise", committed_then_failed)
    [run_id] = lab_worker.run_lab(settings)
    run = repository.get_run(run_id)
    assert run["status"] == "STOPPED"
    assert run["outcome_reason"] == reason
    retained = load_lab(repository, artifacts)
    assert retained.last_run_id == run_id and retained.revision == 1


def test_recovery_excludes_workers_until_interrupted_runs_are_stopped(runtime, monkeypatch):
    settings, repository, _ = runtime
    run_id = repository.create_run("interrupted", scope={"purpose": "LAB"})
    recover = type(repository).recover_interrupted

    def exclusive_recovery(self):
        with pytest.raises(OwnershipError):
            with ResearchOwnership(settings.data_dir / "lab-worker.lock"):
                pass
        return recover(self)

    monkeypatch.setattr(type(repository), "recover_interrupted", exclusive_recovery)
    monkeypatch.setattr(lab_worker, "supervise", lambda *args, **kwargs: 1)
    lab_worker.run_lab(settings)
    assert repository.get_run(run_id)["outcome_reason"] == "INTERRUPTED"


def test_worker_locks_before_provider_initialization_and_rejects_recovered_run(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = repository.create_run("interrupted", scope={"purpose": "LAB"})
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start", message="Start.")
    monkeypatch.setattr(sys, "argv", ["lab_worker", "--child", run_id, "--root", str(settings.data_dir),
                                     "--seconds", "600"])
    monkeypatch.setattr(lab_worker.Settings, "from_env", lambda: settings)
    initialized = []

    def initialize(_settings):
        with pytest.raises(OwnershipError):
            with ResearchOwnership(settings.data_dir / "lab-worker.lock"):
                pass
        initialized.append(True)
        raise RuntimeError("provider initialization sentinel")

    monkeypatch.setattr(lab_worker.CodexDirector, "from_settings", initialize)
    with pytest.raises(RuntimeError, match="provider initialization sentinel"):
        lab_worker.child_main()
    assert initialized == [True]
    repository.recover_interrupted()
    with pytest.raises(ValueError, match="active autonomous laboratory run"):
        lab_worker.child_main()
    assert initialized == [True]
    assert load_lab(repository, artifacts).revision == 0
