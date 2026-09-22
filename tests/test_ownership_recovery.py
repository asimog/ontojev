from __future__ import annotations

import pytest

from cancerjev.storage.ownership import OwnershipError, ResearchOwnership


def test_second_research_owner_is_rejected(runtime):
    settings, repository, _ = runtime
    before = len(repository.list_runs())
    with ResearchOwnership(settings.lock_path):
        with pytest.raises(OwnershipError):
            with ResearchOwnership(settings.lock_path):
                repository.create_run("should-not-happen")
    assert len(repository.list_runs()) == before


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

