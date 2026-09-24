"""Phase 4 first slice: E0 -> one registered deterministic action -> immutable E1."""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.domain.identity import content_hash, evidence_state_identity_payload
from cancerjev.research import deep
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.nextmove import DEEP_POLICY_VERSION
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.actions import ACTION_REGISTRY_VERSION, ActionError
from tests.integration.test_live_replay import _orchestrator
from tests.jev.stub_adapter import StubAdapter


def _completed_slice(runtime, monkeypatch, **kwargs):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=StubAdapter(), **kwargs)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    return run_id, run, repository


def _events(repository, run_id, types):
    return [event for event in repository.events(run_id, 0, 400)["items"] if event["type"] in types]


def _deep_summary(repository, run_id) -> dict:
    """The first investigated candidate's arc summary from RUN_COMPLETED."""
    completed = _events(repository, run_id, {"RUN_COMPLETED"})
    assert completed, "the run must complete"
    deep = completed[-1]["data"]["deep"]
    assert deep["candidate_count"] == len(deep["candidates"])
    return deep["candidates"][0]


def _first_step(summary: dict) -> dict:
    return summary["first_step"]


def test_live_deep_slice_creates_e0_and_e1_from_one_explicit_action(runtime, monkeypatch):
    artifacts = runtime[2]
    run_id, run, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert summary["selection"] == "GENEONE"
    started = _events(repository, run_id, {"RUN_STARTED"})[0]
    assert started["data"]["deep_selection"] == "GENEONE"
    assert started["data"]["deep_selection_rule"], "the human-approved selection rule must be recorded"
    assert summary["status"] == "COMPLETED"
    assert first_step["checks_total"] == 5
    assert first_step["checks_contradicted"] == 0

    candidates = repository.list_table("candidates", run_id)
    assert len(candidates) == 2, "both promoted candidates stay recorded"
    selected = next(row for row in candidates if row["entity"]["gene_symbol"] == "GENEONE")
    assert selected["status"] == "DOSSIER_READY", "the arc ends with a recorded dossier"
    assert selected["dossier_id"] == summary["dossier"]["dossier_id"]
    assert selected["latest_evidence_state_id"] == first_step["evidence_state_id"]

    revisions = repository.evidence_revisions(selected["candidate_id"])
    assert [row["iteration"] for row in revisions] == [0, 1]
    baseline, revised = revisions
    assert baseline["previous_evidence_state_id"] is None
    assert revised["previous_evidence_state_id"] == baseline["evidence_state_id"]
    assert revised["iteration"] == 1

    baseline_state = json.loads(artifacts.read(repository.artifact(baseline["artifact_id"])["relative_path"]))
    revised_state = json.loads(artifacts.read(repository.artifact(revised["artifact_id"])["relative_path"]))
    assert baseline_state["research_puzzle"]["origin"] == "STATISTICAL_STATE_BASELINE"
    assert revised_state["action"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert revised_state["previous_evidence_state_id"] == baseline["evidence_state_id"]
    source_row = repository.get_state(selected["source_state_id"])
    source_metadata = repository.artifact(source_row["artifact_id"])
    assert revised_state["source_statistical_state"] == {
        "state_id": selected["source_state_id"],
        "state_identity_hash": source_row["state_hash"],
        "state_artifact_id": source_row["artifact_id"],
        "state_artifact_sha256": source_metadata["sha256"],
    }
    assert set(revised_state["deterministic_observations"][0]) >= {"result_id", "check_id", "outcome", "availability"}
    assert [check["outcome"] for check in revised_state["deterministic_observations"]] == [
        "VERIFIED", "VERIFIED", "VERIFIED", "VERIFIED", "VERIFIED",
    ]
    assert revised_state["provenance"]["action_registry_version"] == ACTION_REGISTRY_VERSION
    assert revised_state["provenance"]["selection_artifact_sha256"]
    assert revised_state["research_only_notice"].startswith("REAL OPEN-ACCESS GDC EVIDENCE")

    executions = repository.followup_executions_for(selected["candidate_id"])
    assert len(executions) == 1
    assert executions[0]["status"] == "COMPLETED"
    assert executions[0]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert executions[0]["output_evidence_state_id"] == revised["evidence_state_id"]
    assert executions[0]["input_evidence_hash"] == source_row["state_hash"]

    types = [event["type"] for event in repository.events(run_id, 0, 400)["items"]]
    assert types.index("ELIGIBLE_ACTIONS_COMPUTED") < types.index("FOLLOWUP_STARTED")
    assert types.count("EVIDENCE_STATE_CREATED") == 2
    assert types[-1] == "RUN_COMPLETED"
    assert run["counts"]["followups_started"] == 1
    assert run["counts"]["followups_completed"] == 1
    assert run["counts"]["evidence_revisions"] == 2


def test_multiple_selected_candidates_each_get_a_bounded_arc(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_abstaining_adapter(),
        deep_selections=("GENEONE", "GENETWO"), deep_followup_authorized=True)
    run_id = orchestrator.run()
    completed = _events(repository, run_id, {"RUN_COMPLETED"})[-1]["data"]["deep"]
    assert completed["selections"] == ["GENEONE", "GENETWO"]
    assert completed["candidate_count"] == 2
    selections = [summary["selection"] for summary in completed["candidates"]]
    assert selections == ["GENEONE", "GENETWO"]
    for summary in completed["candidates"]:
        assert summary["status"] == "COMPLETED", summary
        assert summary["dossier"]["dossier_id"]
        assert summary["first_step"]["checks_total"] == 5
    candidates = repository.list_table("candidates", run_id)
    assert len(candidates) == 2, "each selection consumed one promotion slot"
    assert all(row["status"] == "DOSSIER_READY" for row in candidates)
    assert len(repository.list_table("dossiers", run_id)) == 2
    assert repository.list_table("evidence_states", run_id)
    # two independent candidates, each with its own revision chain
    per_candidate = {row["candidate_id"]: [] for row in candidates}
    for row in repository.list_table("evidence_states", run_id):
        per_candidate[row["candidate_id"]].append(row["iteration"])
    assert sorted(sorted(chain) for chain in per_candidate.values()) == [[0, 1], [0, 1]]


def test_baseline_evidence_never_changes_when_a_revision_is_added(runtime, monkeypatch):
    artifacts = runtime[2]
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="slot:1")
    candidate = next(
        row for row in repository.list_table("candidates", run_id)
        if row["entity"]["gene_symbol"] == "GENEONE"
    )
    revisions = repository.evidence_revisions(candidate["candidate_id"])
    baseline = revisions[0]
    metadata = repository.artifact(baseline["artifact_id"])
    before = artifacts.read(metadata["relative_path"])
    assert len(revisions) == 2
    assert artifacts.read(metadata["relative_path"]) == before, "recorded evidence is immutable"


def test_deep_selection_that_names_no_promoted_candidate_is_a_typed_event(runtime, monkeypatch):
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="NOT-A-GENE")
    events = _events(repository, run_id, {"DEEP_SELECTION_UNAVAILABLE"})
    assert len(events) == 1
    assert events[0]["data"]["reason_code"] == "DEEP_SELECTION_UNAVAILABLE"
    assert _deep_summary(repository, run_id)["status"] == "DEEP_SELECTION_UNAVAILABLE"
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("followup_executions", run_id) == []


def test_requested_action_outside_the_eligible_set_abstains(runtime, monkeypatch):
    run_id, _, repository = _completed_slice(
        runtime, monkeypatch, deep_selection="GENEONE", deep_action_id="NOT_A_REGISTERED_ACTION",
    )
    assert _deep_summary(repository, run_id)["status"] == "SELECTED_ACTION_NOT_ELIGIBLE"
    events = _events(repository, run_id, {"FOLLOWUP_ABSTAINED"})
    assert events[-1]["data"]["reason_code"] == "SELECTED_ACTION_NOT_ELIGIBLE"
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0]
    assert repository.list_table("followup_executions", run_id) == []


def test_explicit_registered_action_selection_is_used(runtime, monkeypatch):
    run_id, _, repository = _completed_slice(
        runtime, monkeypatch, deep_selection="GENEONE", deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1",
    )
    assert _first_step(_deep_summary(repository, run_id))["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]


def test_repeat_execution_on_the_same_evidence_is_skipped(runtime, monkeypatch):
    run_id, run, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    candidate = next(
        row for row in repository.list_table("candidates", run_id)
        if row["entity"]["gene_symbol"] == "GENEONE"
    )
    emitted: list[str] = []

    def emit(event_run_id, event_type, key, message, **kwargs):
        emitted.append(event_type)
        return repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    artifacts = runtime[2]

    def publish_json(pub_run_id, relative_path, payload, purpose):
        return artifacts.publish(relative_path, json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
                                 "application/json", purpose)

    def read_artifact(artifact_id):
        metadata = repository.artifact(artifact_id)
        return artifacts.read(metadata["relative_path"]) if metadata else None

    plan = deep.plan_deep_slice(
        run_id=run_id, candidate=candidate,
        repository=repository, artifacts=artifacts, emit=emit, publish_json=publish_json,
    )
    assert plan.selected_action_id is None
    assert plan.abstain_reason == "ALREADY_EXECUTED_FOR_THIS_EVIDENCE"
    assert "FOLLOWUP_SKIPPED" in emitted
    assert emitted.count("EVIDENCE_STATE_CREATED") == 0, "the baseline revision already exists"
    assert len(repository.evidence_revisions(candidate["candidate_id"])) == 2


def test_action_failure_records_a_typed_failure_and_keeps_e0(runtime, monkeypatch):
    attempts = {"count": 0}

    def failing_execute(action_id, state, *, read_artifact):
        attempts["count"] += 1
        raise ActionError("ACTION_INTERNAL_FAILURE", "simulated deterministic failure")

    monkeypatch.setattr(deep, "execute", failing_execute)
    run2_id, run2, repository2 = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    assert attempts["count"] == 1
    assert run2["status"] == "COMPLETED", "a typed follow-up failure does not abort the run"
    summary = _deep_summary(repository2, run2_id)
    assert summary["status"] == "FAILED"
    assert summary["error_code"] == "ACTION_INTERNAL_FAILURE"
    events = _events(repository2, run2_id, {"FOLLOWUP_FAILED"})
    assert len(events) == 1 and events[0]["level"] == "error"
    revisions = repository2.list_table("evidence_states", run2_id)
    assert [row["iteration"] for row in revisions] == [0], "no revision is created on failure"
    executions = repository2.list_table("followup_executions", run2_id)
    assert [row["status"] for row in executions] == ["FAILED"]
    candidate_row = next(
        row for row in repository2.list_table("candidates", run2_id)
        if row["entity"]["gene_symbol"] == "GENEONE"
    )
    assert candidate_row["status"] == "DEEP_ANALYSIS", "a failure does not advance the candidate"
    assert run2["counts"]["followups_failed"] == 1


@pytest.mark.parametrize(
    ("attribute", "limit", "reason"),
    [
        ("FOLLOWUP_LIMIT", 0, "FOLLOWUP_LIMIT_REACHED"),
        ("EVIDENCE_ITERATION_LIMIT", 0, "EVIDENCE_ITERATION_LIMIT_REACHED"),
    ],
)
def test_budget_exhaustion_abstains_and_stops(runtime, monkeypatch, attribute, limit, reason):
    monkeypatch.setattr(deep, attribute, limit)
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    assert _deep_summary(repository, run_id)["status"] == reason
    events = _events(repository, run_id, {"FOLLOWUP_ABSTAINED"})
    assert events[-1]["data"]["reason_code"] == reason
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0]
    assert repository.list_table("followup_executions", run_id) == []


def test_evidence_identity_excludes_operational_fields_and_tracks_outcomes(runtime, monkeypatch):
    artifacts = runtime[2]
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    candidate = next(
        row for row in repository.list_table("candidates", run_id)
        if row["entity"]["gene_symbol"] == "GENEONE"
    )
    revised = repository.evidence_revisions(candidate["candidate_id"])[1]
    payload = json.loads(artifacts.read(repository.artifact(revised["artifact_id"])["relative_path"]))
    before = content_hash(evidence_state_identity_payload(payload))

    operational = copy.deepcopy(payload)
    operational.update({
        "evidence_state_id": "other", "run_id": "other", "candidate_id": "other",
        "previous_evidence_state_id": "other", "created_at": "2999-01-01T00:00:00Z",
    })
    operational["source_statistical_state"]["state_id"] = "other"
    operational["source_statistical_state"]["state_artifact_id"] = "other"
    operational["source_statistical_state"]["state_artifact_sha256"] = "0" * 64
    operational["provenance"]["input_artifacts"] = [
        {"kind": "RESPONSE_ARTIFACT", "ref": "other", "sha256": "z" * 64, "verified": True},
    ]
    for observation in operational["deterministic_observations"]:
        observation["result_id"] = "other"
    assert content_hash(evidence_state_identity_payload(operational)) == before

    changed_outcome = copy.deepcopy(payload)
    changed_outcome["deterministic_observations"][0]["outcome"] = "CONTRADICTED"
    assert content_hash(evidence_state_identity_payload(changed_outcome)) != before

    changed_iteration = copy.deepcopy(payload)
    changed_iteration["iteration_number"] = 2
    assert content_hash(evidence_state_identity_payload(changed_iteration)) != before


def test_deep_slice_is_visible_through_the_api(runtime, monkeypatch):
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    client = TestClient(create_app())
    evidence = client.get(f"/api/runs/{run_id}/evidence")
    assert evidence.status_code == 200
    items = evidence.json()["items"]
    assert [item["iteration"] for item in items] == [0, 1]
    followups = client.get(f"/api/runs/{run_id}/followups")
    assert followups.status_code == 200
    assert [item["status"] for item in followups.json()["items"]] == ["COMPLETED"]
    detail = client.get(f"/api/evidence/{first_step['evidence_state_id']}")
    assert detail.status_code == 200
    assert detail.headers["X-Artifact-SHA256"]
    payload = detail.json()
    assert payload["action"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert len(payload["deterministic_observations"]) == 5
    filtered = client.get(f"/api/runs/{run_id}/evidence?candidate_id={summary['candidate_id']}")
    assert filtered.json()["has_more"] is False
    assert len(filtered.json()["items"]) == 2
    deep = client.get(f"/api/runs/{run_id}/evaluations?purpose=DEEP")
    assert deep.status_code == 200
    assert len(deep.json()["items"]) == 1
    assert deep.json()["items"][0]["input_ref_kind"] == "EVIDENCE_STATE"


def _abstaining_adapter() -> StubAdapter:
    """A provider whose wide judgment never passes the uncalibrated admission thresholds."""
    return StubAdapter(override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}})


def _operator_slice(runtime, monkeypatch, **kwargs):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_abstaining_adapter(), **kwargs)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    return run_id, run, repository


def test_operator_selected_state_reaches_the_deep_slice_without_policy_promotion(runtime, monkeypatch):
    run_id, run, repository = _operator_slice(runtime, monkeypatch, deep_selection="gene:GENEONE")
    wide_completed = _events(repository, run_id, {"JEV_WIDE_COMPLETED"})[-1]
    assert wide_completed["data"]["admission_decision"] == "ABSTAIN"
    assert wide_completed["data"]["promoted"] == 0

    promotions = _events(repository, run_id, {"CANDIDATE_PROMOTED"})
    assert len(promotions) == 1
    assert promotions[0]["data"]["policy_version"] == "operator-selection-v1"
    assert promotions[0]["data"]["reason"] == "OPERATOR_APPROVED_SELECTION"
    assert promotions[0]["data"]["selection"] == "gene:GENEONE"
    assert promotions[0]["data"]["auto_dispatched"] is False
    assert promotions[0]["data"]["promotion_slot"] == 1

    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert summary["status"] == "COMPLETED"
    assert first_step["checks_total"] == 5 and first_step["checks_contradicted"] == 0
    assert first_step["iteration"] == 1 and first_step["evidence_state_id"]
    assert first_step["deep_evaluation_id"], "the revision must be judged in one deep fan-out"
    assert first_step["deep_error_code"] is None
    assert first_step["next_move"]["move"] == "COMPLETE"
    assert first_step["next_move"]["policy_version"] == DEEP_POLICY_VERSION
    assert first_step["next_move"]["executed"] is False
    assert first_step["deep_usage"]["input_tokens"] == 1200

    event_types = [event["type"] for event in repository.events(run_id, 0, 500)["items"]]
    assert event_types.index("ELIGIBLE_ACTIONS_COMPUTED") < event_types.index("FOLLOWUP_STARTED")
    assert event_types.index("FOLLOWUP_COMPLETED") < event_types.index("JEV_DEEP_STARTED")
    assert "JEV_DEEP_EVIDENCE_JUDGED" in event_types
    assert "NEXT_MOVE_SELECTED" in event_types

    evaluations = repository.page_child("jev_evaluations", run_id, 50, None, {"purpose": "DEEP"})["items"]
    assert len(evaluations) == 1
    deep = evaluations[0]["vector"]
    assert deep["input_ref_kind"] == "EVIDENCE_STATE"
    assert deep["evidence_state_id"] == first_step["evidence_state_id"]
    assert deep["source_evidence_hash"] == first_step["evidence_hash"]
    assert deep["question_set_version"] == "deep-v1"
    assert deep["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert set(deep["answers"]) == {
        "revision_reliable", "evidence_sufficient_for_next_step", "next_step_warranted",
        "stopping_more_honest", "dominant_limitation",
    }
    assert all(rule["applicable"] for rule in deep["applicability"].values())
    assert deep["error"] is None
    assert run["counts"]["followups_completed"] == 1
    assert run["counts"]["evidence_revisions"] == 2
    wide_evaluations = repository.page_child("jev_evaluations", run_id, 50, None,
                                             {"purpose": "WIDE"})["items"]
    assert run["counts"]["jev_evaluations"] == len(wide_evaluations) + 1, \
        "every evaluation record counts once (wide + the deep judgment)"
    assert run["provider_usage"]["jev_calls"] == len(wide_evaluations) + 1, \
        "the deep provider call must be counted in provider usage"
    assert run["provider_usage"]["jev_input_tokens"] == (len(wide_evaluations) + 1) * 1200


def test_operator_selection_grammar(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    orchestrator = LiveOrchestrator(settings, repository, artifacts, lambda event: None,
                                    research_spec=LUAD_RESEARCH_V1)
    index = {
        "state-1": {"state_id": "state-1", "entity": {"gene_symbol": "GENEONE"}},
        "state-2": {"state_id": "state-2", "entity": {"gene_symbol": "GENETWO"}},
    }
    orchestrator.deep_selection = "state:state-2"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index) == ("state-2", None)
    orchestrator.deep_selection = "gene:GENEONE"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index) == ("state-1", None)
    orchestrator.deep_selection = "GENEONE"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index) == ("state-1", None)
    orchestrator.deep_selection = "MISSING"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index)[0] is None
    orchestrator.deep_selection = "state:MISSING"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index)[0] is None
    orchestrator.deep_selection = "slot:1"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, index)[0] is None
    ambiguous = {**index, "state-3": {"state_id": "state-3", "entity": {"gene_symbol": "GENEONE"}}}
    orchestrator.deep_selection = "GENEONE"
    assert orchestrator._operator_selection_target(orchestrator.deep_selection, ambiguous)[0] is None


def test_operator_selection_is_refused_for_an_unevaluated_state(runtime, monkeypatch):
    class _FailsForSecondGene(StubAdapter):
        def evaluate(self, state, definitions):
            if state.get("entity", {}).get("symbol") == "GENETWO":
                from cancerjev.jev.typesafe_adapter import JevProviderError

                self.calls += 1
                raise JevProviderError("PROVIDER_ERROR", "stub failure for one gene")
            return super().evaluate(state, definitions)

    adapter = _FailsForSecondGene(
        override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}})
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter,
                                                deep_selection="GENETWO")
    run_id = orchestrator.run()
    events = _events(repository, run_id, {"DEEP_SELECTION_UNAVAILABLE"})
    assert events[-1]["data"]["reason_code"] == "STATE_NOT_EVALUATED"
    assert repository.list_table("candidates", run_id) == []
    assert repository.list_table("evidence_states", run_id) == []


def test_operator_selection_respects_the_promotion_cap(runtime, monkeypatch):
    monkeypatch.setattr("cancerjev.research.live.PROMOTION_LIMIT", 0)
    run_id, run, repository = _operator_slice(runtime, monkeypatch, deep_selection="GENEONE")
    events = _events(repository, run_id, {"DEEP_SELECTION_UNAVAILABLE"})
    assert events[-1]["data"]["reason_code"] == "PROMOTION_LIMIT_REACHED"
    assert run["counts"]["followups_started"] == 0
    assert repository.list_table("evidence_states", run_id) == []


def test_deep_judgment_failure_is_contained_and_keeps_the_revision(runtime, monkeypatch):
    class _DeepJudgeFails(StubAdapter):
        def evaluate(self, state, definitions):
            if state.get("projection_version") == "jev-evidence-projection-v1":
                from cancerjev.jev.contracts import JevContractError

                self.calls += 1
                raise JevContractError("INVALID_DISTRIBUTION", "stub deep judgment failure")
            return super().evaluate(state, definitions)

    adapter = _DeepJudgeFails(
        override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}})
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter,
                                                deep_selection="GENEONE")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert summary["status"] == "ABSTAINED", "the deterministic revision stands even when its judgment fails"
    assert summary["final_move"] == "ABSTAIN"
    assert first_step["next_move"]["reason_code"] == "DEEP_JUDGMENT_UNAVAILABLE"
    assert first_step["deep_error_code"] == "INVALID_DISTRIBUTION"
    deep_errors = [event for event in repository.events(run_id, 0, 500)["items"]
                   if event["type"] == "JEV_EVALUATION_FAILED"
                   and event["data"]["input_ref_kind"] == "EVIDENCE_STATE"]
    assert deep_errors, "a failed deep judgment must be recorded, not hidden"
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]


def _follow_up_adapter() -> StubAdapter:
    """A provider that warrants a further step and does not claim completion."""
    return StubAdapter(
        override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}},
        deep_override={
            "next_step_warranted": {"kind": "noul", "probability_yes": 0.9},
            "stopping_more_honest": {"kind": "noul", "probability_yes": 0.1},
        },
    )


def _dispatched_slice(runtime, monkeypatch, *, authorized: bool, **kwargs):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_follow_up_adapter(),
        deep_selection="GENEONE", deep_followup_authorized=authorized, **kwargs)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    return run_id, run, repository


def test_authorized_follow_up_dispatches_one_revision_and_rejudges_it(runtime, monkeypatch):
    run_id, run, repository = _dispatched_slice(runtime, monkeypatch, authorized=True)
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert first_step["next_move"]["move"] == "FOLLOW_UP"
    assert first_step["next_move"]["reason_code"] == "FOLLOW_UP_WARRANTED"
    assert first_step["next_move"]["executed"] is False, "the policy never dispatches its own decision"
    assert first_step["next_move"]["dimensions"]["distinct_eligible_action_ids"] == [
        "CHECK_REVISION_FAITHFULNESS_V1",
    ]
    dispatch = summary["dispatch"]
    assert dispatch["dispatched"] is True
    assert dispatch["reason_code"] == "DISPATCHED"
    assert dispatch["action_id"] == "CHECK_REVISION_FAITHFULNESS_V1"
    assert dispatch["iteration"] == 2
    assert dispatch["result_status"] == "COMPLETED"
    assert summary["decisions"][-1]["move"] == "ABSTAIN", "the new revision is judged once by the loop"
    assert summary["decisions"][-1]["reason_code"] == "NO_FURTHER_REGISTERED_ACTION"
    assert len(summary["steps"]) == 2, "one step per judged revision, never a duplicate"
    assert summary["steps"][1]["deep_evaluation_id"], "the dispatched revision's judgment must be named"
    assert summary["steps"][1]["deep_usage"]["input_tokens"] == 1200

    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    revisions = repository.evidence_revisions(candidate["candidate_id"])
    assert [row["iteration"] for row in revisions] == [0, 1, 2]
    assert revisions[2]["previous_evidence_state_id"] == revisions[1]["evidence_state_id"]
    assert revisions[2]["evidence_hash"] != revisions[1]["evidence_hash"]
    assert revisions[0]["evidence_hash"] != revisions[1]["evidence_hash"]
    second = json.loads(repository_runtime_artifact(runtime, repository, revisions[2]["artifact_id"]))
    assert second["action"]["action_id"] == "CHECK_REVISION_FAITHFULNESS_V1"
    assert second["previous_evidence_state_id"] == revisions[1]["evidence_state_id"]
    assert [observation["outcome"] for observation in second["deterministic_observations"]] == [
        "VERIFIED", "VERIFIED", "VERIFIED", "VERIFIED",
    ]
    assert second["quality_and_fragility"]["checks_total"] == 4

    executions = repository.followup_executions_for(candidate["candidate_id"])
    assert [row["action_id"] for row in executions] == [
        "CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1",
    ]
    assert [row["status"] for row in executions] == ["COMPLETED", "COMPLETED"]
    assert executions[1]["input_evidence_hash"] == revisions[1]["evidence_hash"]

    event_types = [event["type"] for event in repository.events(run_id, 0, 700)["items"]]
    assert event_types.count("NEXT_MOVE_SELECTED") == 2
    assert event_types.count("NEXT_MOVE_DISPATCHED") == 2, \
        "one successful dispatch and one recorded refusal that stopped the bounded loop"
    assert event_types.count("EVIDENCE_STATE_CREATED") == 3
    assert event_types.count("JEV_DEEP_EVIDENCE_JUDGED") == 2
    assert len(summary["steps"]) == 2, "two judged revisions in the bounded arc"
    assert summary["final_move"] == "ABSTAIN"
    assert summary["last_dispatch"]["reason_code"] == "MOVE_NOT_FOLLOW_UP"
    assert summary["stop_reason"] == "MOVE_NOT_FOLLOW_UP"
    assert summary["dossier"]["dossier_id"]
    assert summary["hypothesis"] is None, "the move never asked for hypotheses in this arc"
    assert run["counts"]["followups_completed"] == 2
    assert run["counts"]["evidence_revisions"] == 3
    deep_evaluations = repository.page_child("jev_evaluations", run_id, 50, None,
                                             {"purpose": "DEEP"})["items"]
    assert len(deep_evaluations) == 2
    assert run["provider_usage"]["jev_calls"] == 2 + len(
        repository.page_child("jev_evaluations", run_id, 50, None, {"purpose": "WIDE"})["items"]
    )


def repository_runtime_artifact(runtime, repository, artifact_id: str) -> bytes:
    metadata = repository.artifact(artifact_id)
    return runtime[2].read(metadata["relative_path"])


def test_unauthorized_follow_up_is_recorded_but_not_dispatched(runtime, monkeypatch):
    run_id, run, repository = _dispatched_slice(runtime, monkeypatch, authorized=False)
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert first_step["next_move"]["move"] == "FOLLOW_UP"
    assert summary["dispatch"]["dispatched"] is False
    assert summary["dispatch"]["reason_code"] == "DISPATCH_NOT_AUTHORIZED"
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]
    refusals = [event for event in repository.events(run_id, 0, 700)["items"]
                if event["type"] == "NEXT_MOVE_DISPATCHED"]
    assert len(refusals) == 1 and refusals[0]["data"]["authorized"] is False


def test_completed_investigation_is_never_dispatched(runtime, monkeypatch):
    run_id, run, repository = _operator_slice(runtime, monkeypatch, deep_selection="GENEONE",
                                              deep_followup_authorized=True)
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert first_step["next_move"]["move"] == "COMPLETE"
    assert summary["dispatch"]["dispatched"] is False
    assert summary["dispatch"]["reason_code"] == "MOVE_NOT_FOLLOW_UP"
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]


@pytest.mark.parametrize(
    ("attribute", "limit", "reason"),
    [
        ("FOLLOWUP_LIMIT", 1, "FOLLOWUP_LIMIT_REACHED"),
        ("EVIDENCE_ITERATION_LIMIT", 1, "EVIDENCE_ITERATION_LIMIT_REACHED"),
    ],
)
def test_dispatch_respects_the_caps(runtime, monkeypatch, attribute, limit, reason):
    monkeypatch.setattr(deep, attribute, limit)
    run_id, run, repository = _dispatched_slice(runtime, monkeypatch, authorized=True)
    summary = _deep_summary(repository, run_id)
    first_step = _first_step(summary)
    assert first_step["next_move"]["move"] == "FOLLOW_UP"
    assert summary["dispatch"]["dispatched"] is False
    assert summary["dispatch"]["reason_code"] == reason
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]
    assert len(repository.list_table("followup_executions", run_id)) == 1


def test_a_failed_attempt_consumes_follow_up_budget(runtime, monkeypatch):
    """A failed action attempt spent budget, so it must count against the cap."""
    from cancerjev.domain.actions import ComputedEvidenceRevision, IntegrityCheck
    from cancerjev.domain.events import canonical_json, utc_now

    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    artifacts = runtime[2]
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    evidence = deep.load_candidate_evidence(repository, artifacts, candidate)
    revision = json.loads(artifacts.read(
        repository.artifact(repository.evidence_revisions(candidate["candidate_id"])[1]["artifact_id"])["relative_path"]))
    typed_revision = ComputedEvidenceRevision(
        revision["evidence_state_id"], content_hash(evidence_state_identity_payload(revision)),
        candidate["candidate_id"], revision["previous_evidence_state_id"], 1,
        revision["action"]["action_id"],
        tuple(IntegrityCheck(c["check_id"], c["claim"], c["outcome"],
                             canonical_json(c["observed"]), canonical_json(c["expected"]),
                             c["n_effective"], tuple(c["notes"]), tuple(c["limitations"]))
              for c in revision["deterministic_observations"]),
        canonical_json(revision),
    )
    result = deep.FollowUpResult(
        status="COMPLETED", action_id=revision["action"]["action_id"],
        evidence_state_id=revision["evidence_state_id"],
        evidence_hash=content_hash(evidence_state_identity_payload(revision)),
        iteration=1, checks_total=5, checks_verified=5, checks_contradicted=0, checks_not_observed=0,
        error_code=None, revision=typed_revision,
    )
    repository.append_event(
        run_id, event_type="FOLLOWUP_FAILED", idempotency_key="audit:failed-attempt",
        message="failed attempt", stage="FOLLOWUP", level="error", candidate_id=candidate["candidate_id"],
        registrations=[repository.followup_execution_registration(
            execution_id="audit-failed-execution", run_id=run_id, candidate_id=candidate["candidate_id"],
            action_id="CHECK_REVISION_FAITHFULNESS_V1", action_version="1",
            input_evidence_hash="f" * 64, output_evidence_state_id=None, slot=9, status="FAILED",
            summary_json="{}", created_at=utc_now(),
        )],
    )
    monkeypatch.setattr(deep, "FOLLOWUP_LIMIT", 2)
    emitted: list[dict] = []

    def emit(event_run_id, event_type, key, message, **kwargs):
        event = repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                        message=message, **kwargs)
        emitted.append(event)
        return event

    def read_artifact(artifact_id):
        metadata = repository.artifact(artifact_id)
        return artifacts.read(metadata["relative_path"]) if metadata else None

    dispatch = deep.dispatch_recorded_move(
        run_id=run_id, candidate=evidence, result=result,
        decision={"move": "FOLLOW_UP",
                  "dimensions": {"distinct_eligible_action_ids": ["CHECK_REVISION_FAITHFULNESS_V1"]}},
        repository=repository, emit=emit,
        publish_json=lambda pub_run_id, path, payload, purpose: artifacts.publish(
            path, json.dumps(payload, sort_keys=True).encode(), "application/json", purpose),
        read_artifact=read_artifact, authorized=True,
    )
    assert dispatch.dispatched is False
    assert dispatch.reason_code == "FOLLOWUP_LIMIT_REACHED"
    refusals = [event for event in emitted if event["type"] == "NEXT_MOVE_DISPATCHED"]
    assert refusals and refusals[0]["data"]["dispatched"] is False
    assert [row["iteration"] for row in repository.list_table("evidence_states", run_id)] == [0, 1]
