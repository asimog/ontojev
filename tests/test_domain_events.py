from __future__ import annotations

import pytest

from cancerjev.domain.runs import validate_run_transition


def test_legal_run_transitions():
    validate_run_transition("PENDING", "RUNNING")
    validate_run_transition("RUNNING", "COMPLETED")


def test_terminal_transition_is_rejected():
    with pytest.raises(ValueError, match="illegal"):
        validate_run_transition("COMPLETED", "RUNNING")


def test_event_sequence_idempotency_and_rollback(runtime):
    _, repository, _ = runtime
    run_id = repository.create_run("test")
    first = repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="create", message="created")
    retried = repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="create", message="ignored")
    assert retried == first
    assert repository.get_run(run_id)["last_sequence"] == 1
    with pytest.raises(ValueError, match="65,536"):
        repository.append_event(run_id, event_type="BAD", idempotency_key="bad", message="bad", data={"large": "x" * 66_000})
    assert repository.get_run(run_id)["last_sequence"] == 1
    second = repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start", message="started")
    assert second["sequence"] == 2
    events = repository.events(run_id, 0, 20)["items"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert len({event["event_id"] for event in events}) == 2

