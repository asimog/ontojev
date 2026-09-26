"""Autonomous candidate queue: every promoted Candidate reaches Stage 8.

The canonical Campaign executor invokes the autonomous queue itself: no operator
selection flag exists on this path. These tests prove multi-candidate
determinism, terminal Stage 8 results and dossiers, immutable evidence
revisions, explicit isolation of a failing candidate, and ownership separation.
"""

from __future__ import annotations

import pytest

from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research import investigation as investigation_module
from cancerjev.research.investigation import (
    AUTONOMOUS_DISPATCH_AUTHORIZATION,
    run_autonomous_candidate_queue,
)
from cancerjev.storage.ownership import OwnershipError
from cancerjev.storage.readers import read_revision_chain
from tests.integration.test_systematic_campaign import _execute


def _candidate_rows(repository, run_id):
    return {row["candidate_id"]: row
            for row in repository.list_table("candidates", run_id)}


def test_multiple_promoted_candidates_reach_terminal_stage8_results(runtime):
    _, repository, _ = runtime
    run_id, _, events, result = _execute(runtime)
    types = [event["type"] for event in events]

    queue = result.candidate_queue
    assert queue is not None
    assert queue["candidate_count"] == 2, "both wide-promoted candidates are processed"
    assert queue["completed_count"] == 2
    assert queue["candidate_queue_exhausted"] is True
    assert queue["run_scope"] == "CANDIDATE_QUEUE_EXHAUSTED"
    assert queue["failures"] == []

    rows = _candidate_rows(repository, run_id)
    assert len(rows) == 2
    for row in rows.values():
        assert row["status"] == "CANDIDATE_COMPLETE"
        assert row["dossier_id"], "every terminal candidate owns a dossier"
        assert row["latest_evidence_state_id"], "every terminal candidate owns an E0 revision"
    assert types.count("FINAL_CANDIDATE_RESULT_RECORDED") == 2
    assert types.count("CANDIDATE_COMPLETED") == 2
    assert types.count("DOSSIER_CREATED") == 2

    for event in events:
        if event["type"] == "NEXT_MOVE_DISPATCHED":
            assert event["data"]["authorized"] is True
            assert event["data"]["authorized_by"] == AUTONOMOUS_DISPATCH_AUTHORIZATION
    assert "CANDIDATE_DEFERRED" not in types


def test_autonomous_progression_requires_no_candidate_selection_flag(runtime):
    _, _, events, result = _execute(runtime)
    assert result.wide is not None and result.wide["promoted"], "Wide promoted candidates"
    assert "DEEP_SELECTION_UNAVAILABLE" not in [event["type"] for event in events]
    assert "run_scope" in result.candidate_queue
    assert result.candidate_queue["authorized_by"] == AUTONOMOUS_DISPATCH_AUTHORIZATION


def test_evidence_revisions_and_stage8_comparison(runtime):
    _, repository, artifacts = runtime
    run_id, _, events, _ = _execute(runtime)
    finalization = [event for event in events
                    if event["type"] == "FINAL_CANDIDATE_RESULT_RECORDED"]
    assert len(finalization) == 2
    for event in finalization:
        assert event["data"]["baseline_policy_version"] == "no-jev-baseline-v1"
        assert event["data"]["comparison_status"] is not None
        assert event["data"]["dossier_id"]

    for row in _candidate_rows(repository, run_id).values():
        chain = read_revision_chain(repository, artifacts, row["candidate_id"])
        assert chain, "the immutable revision chain is readable"
        assert chain[-1].evidence_state_id == row["latest_evidence_state_id"]
        assert chain[-1].record.evidence_hash
        for revision in chain:
            assert revision.parent_id != revision.evidence_state_id


def test_one_failing_candidate_is_explicit_and_isolated(runtime, monkeypatch):
    _, repository, _ = runtime
    original = investigation_module.run_candidate_investigation
    calls = {"count": 0}

    def flaky(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("candidate one exploded")
        return original(**kwargs)

    monkeypatch.setattr(investigation_module, "run_candidate_investigation", flaky)

    run_id, _, events, result = _execute(runtime)

    queue = result.candidate_queue
    assert queue["candidate_count"] == 2
    assert queue["completed_count"] == 1
    assert queue["candidate_queue_exhausted"] is False
    assert queue["run_scope"] == "CANDIDATES_INCOMPLETE"
    assert len(queue["failures"]) == 1
    assert queue["failures"][0]["reason_code"] == "RuntimeError"

    rows = sorted(_candidate_rows(repository, run_id).values(),
                  key=lambda row: row["promotion_slot"])
    assert rows[0]["status"] == "FAILED"
    assert rows[1]["status"] == "CANDIDATE_COMPLETE", "the next candidate still completes"
    not_completed = [event for event in events if event["type"] == "CANDIDATE_NOT_COMPLETED"]
    assert len(not_completed) == 1
    assert not_completed[0]["data"]["reason_code"] == "RuntimeError"
    assert not_completed[0]["data"]["terminal_state"] == "FAILED"


def test_autonomous_followup_produces_measured_evidence(runtime):
    """The Campaign-owned transport must turn a candidate follow-up into real evidence."""
    _, repository, artifacts = runtime
    run_id, _, _, _ = _execute(runtime)

    executed = []
    for row in _candidate_rows(repository, run_id).values():
        executed.extend((row["candidate_id"], execution)
                        for execution in repository.followup_executions_for(row["candidate_id"]))

    assert executed, "the autonomous queue dispatches at least one candidate follow-up"
    assert {execution["action_id"] for _, execution in executed} == {"OCCURRENCE_DETAIL_EVIDENCE_V1"}
    assert any(execution["status"] == "COMPLETED" for _, execution in executed), \
        "the follow-up acquired occurrence detail rather than reporting transport unavailable"
    for candidate_id, _ in executed:
        chain = read_revision_chain(repository, artifacts, candidate_id)
        assert chain[-1].evidence.measured_observations, \
            "the occurrence-detail follow-up records real measured observations"


def test_queue_refuses_researcher_owned_runs(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run(
        "researcher-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "SYSTEMATIC_CAMPAIGN"}, ownership=ExecutionOwnership.RESEARCHER_RUN)

    with pytest.raises(OwnershipError):
        run_autonomous_candidate_queue(
            run_id=run_id, repository=repository, artifacts=artifacts,
            emit=lambda *args, **kwargs: None, publish_json=lambda *args: None,
            stage=lambda name, function: function(), jev_service=None)
