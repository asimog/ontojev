from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cancerjev.domain.events import REGISTERED_EVENT_TYPES, RunEvent
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
        repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="bad", message="bad", data={"large": "x" * 66_000})
    assert repository.get_run(run_id)["last_sequence"] == 1
    second = repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start", message="started")
    assert second["sequence"] == 2
    events = repository.events(run_id, 0, 20)["items"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert len({event["event_id"] for event in events}) == 2


def test_unknown_event_type_is_rejected_without_state_change(runtime):
    _, repository, _ = runtime
    run_id = repository.create_run("test")
    repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="create", message="created")
    before = repository.get_run(run_id)
    with pytest.raises(ValueError, match="unknown RunEvent type"):
        repository.append_event(run_id, event_type="TOTALLY_UNKNOWN_TYPE", idempotency_key="unknown", message="?")
    after = repository.get_run(run_id)
    assert after["last_sequence"] == before["last_sequence"]
    assert after["status"] == before["status"]
    assert after["stage_occurrences"] == before["stage_occurrences"]
    assert [event["type"] for event in repository.events(run_id, 0, 20)["items"]] == ["RUN_CREATED"]


def test_unsupported_event_schema_version_is_rejected():
    with pytest.raises(ValidationError, match="unsupported RunEvent schema_version"):
        RunEvent(run_id=uuid4(), sequence=1, type="RUN_CREATED", message="created", idempotency_key="create", schema_version=2)
    accepted = RunEvent(run_id=uuid4(), sequence=1, type="RUN_CREATED", message="created", idempotency_key="create")
    assert accepted.schema_version == 1


def test_registered_vocabulary_contains_every_phase1_type():
    assert {
        "RUN_CREATED", "RUN_STARTED", "RUN_COMPLETED", "RUN_FAILED", "RUN_STOPPED",
        "STAGE_STARTED", "STAGE_COMPLETED", "INVENTORY_COMPLETED", "WIDE_SCAN_STARTED",
        "WIDE_SCAN_COMPLETED", "STATISTICAL_STATE_CREATED", "JEV_WIDE_STATE_EVALUATED",
        "CANDIDATE_PROMOTED", "CANDIDATE_DEFERRED", "EVIDENCE_STATE_CREATED",
        "EVIDENCE_BUILD_COMPLETED", "JEV_DEEP_COMPLETED", "HYPOTHESES_GENERATED",
        "HYPOTHESIS_EVALUATED", "FOLLOWUP_STARTED", "FOLLOWUP_COMPLETED", "DOSSIER_CREATED",
    } <= REGISTERED_EVENT_TYPES
