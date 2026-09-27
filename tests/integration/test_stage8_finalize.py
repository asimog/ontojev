"""Stage 8 integration: final candidate result, dossier, no-Jev comparison, lifecycle.

The Stage 8 contract is driven through the real live-shaped run (ReplayTransport,
StubAdapter) exactly like the deep slice tests. Assertions prove: one final
candidate result and one authoritative dossier per investigated candidate, the
actual terminal stop reason (never `MOVE_NOT_FOLLOW_UP`), the fail-closed
multi-action rule, the deterministic no-Jev comparison labels, that the baseline
replay mutates nothing, and that candidate completion precedes run completion with
no human-review gate anywhere in the lifecycle.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import CheckOutcome
from cancerjev.research.dossier import run_dossier_stage
from cancerjev.research.finalize import (
    NO_JEV_BASELINE_VERSION,
    baseline_next_move,
    derive_stage8,
    run_stage8_finalize,
)
from cancerjev.research.ranking import BASELINE_POLICY_VERSION
from cancerjev.science.actions import CHECK_CONTRADICTED
from cancerjev.storage.readers import read_candidate_state, read_dossier_record
from tests.integration.test_deep_slice import (
    _candidate_chain,
    _completed_slice,
    _followup_adapter,
)
from tests.integration.test_live_replay import _events, _orchestrator
from tests.jev.stub_adapter import StubAdapter


def _final_result_payloads(repository, artifacts, run_id) -> list[dict]:
    events = [event for event in _events(repository, run_id)
              if event["type"] == "FINAL_CANDIDATE_RESULT_RECORDED"]
    assert events, "Stage 8 must record the final candidate result event"
    payloads = []
    for event in events:
        artifact_id = event["artifact_refs"][0]["artifact_id"]
        row = repository.artifact(artifact_id)
        payloads.append(json.loads(artifacts.read(row["relative_path"], row["sha256"])))
    return payloads


def _completed_candidate(repository, run_id):
    candidates = repository.list_table("candidates", run_id)
    return next(candidate for candidate in candidates
                if candidate["status"] == "CANDIDATE_COMPLETE")


def test_terminal_candidate_receives_final_result_with_correct_revision_and_reason(
        runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    [payload] = _final_result_payloads(repository, runtime[2], run_id)
    chain = _candidate_chain(runtime, repository,
                             repository.get_candidate(summary["candidate_id"]))
    assert payload["kind"] == "FINAL_CANDIDATE_RESULT"
    assert payload["candidate_id"] == summary["candidate_id"]
    assert payload["final_move"] == "COMPLETE"
    assert payload["stop_reason"] == "INVESTIGATION_COMPLETE"
    assert payload["final_evidence_revision"]["evidence_state_id"] == chain[-1].evidence_state_id
    assert payload["dossier_reference"] == summary["dossier"]["dossier_id"]
    assert payload["provenance"]["baseline_policy_version"] == NO_JEV_BASELINE_VERSION
    recorded = [event for event in _events(repository, run_id)
                if event["type"] == "FINAL_CANDIDATE_RESULT_RECORDED"]
    assert recorded and recorded[-1]["data"]["final_result_id"] == payload["final_result_id"]


def test_abstain_preserves_its_actual_reason_code(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    [payload] = _final_result_payloads(repository, runtime[2], run_id)
    assert payload["final_move"] == "ABSTAIN"
    assert payload["stop_reason"] == "DEEP_JUDGMENT_UNAVAILABLE"
    assert payload["investigation_status"] == "ABSTAINED"


def test_terminal_moves_are_never_routed_through_the_dispatcher(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    dispatched = [event["data"] for event in _events(repository, run_id)
                  if event["type"] == "NEXT_MOVE_DISPATCHED"]
    assert [item["move"] for item in dispatched] == ["FOLLOW_UP"], \
        "only the recorded FOLLOW_UP is ever eligible for dispatch"


def test_baseline_next_move_rule_is_declared_deterministic():
    assert baseline_next_move(0) == {
        "move": "COMPLETE", "reason_code": "INVESTIGATION_COMPLETE",
        "detail": "one selected deterministic action was executed; the baseline stops"}
    assert baseline_next_move(2)["move"] == "ABSTAIN"
    assert baseline_next_move(2)["reason_code"] == "REVISION_CONTRADICTS_RECORDED_EVIDENCE"


def test_comparison_records_actual_and_baseline_decisions_and_is_reproducible(
        runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    [payload] = _final_result_payloads(repository, runtime[2], run_id)
    comparison = payload["baseline_comparison"]
    assert comparison["baseline_policy_version"] == NO_JEV_BASELINE_VERSION
    assert comparison["path"] == {"actual": "OBSERVED", "baseline": "DETERMINISTIC_REPLAY"}
    assert comparison["investigation"]["baseline_next_move"] == "COMPLETE"
    assert comparison["investigation"]["baseline_reason_code"] == "INVESTIGATION_COMPLETE"
    assert comparison["investigation"]["actual_final_move"] == "COMPLETE"
    assert comparison["investigation"]["comparison"] == "SAME_DECISION"
    assert comparison["overall"] in {"SAME_DECISION", "DIFFERENT_ADMISSION", "DIFFERENT_RANK",
                                     "PARTIALLY_COMPARABLE", "NOT_COMPARABLE"}
    # The wide comparison reproduces the persisted ranking artifacts exactly.
    wide = comparison["wide"]
    rankings = {}
    for row in repository.ranking_artifacts(run_id):
        ranking_payload = json.loads(runtime[2].read(row["relative_path"], row["sha256"]))
        rankings[ranking_payload["policy_version"]] = ranking_payload
    baseline_entry = next(entry for entry in rankings[BASELINE_POLICY_VERSION]["entries"]
                          if entry["state_id"] == payload["candidate"]["source_state_id"])
    assert wide["baseline_rank"] == baseline_entry["rank"]
    assert wide["baseline_admitted"] == (
        payload["candidate"]["source_state_id"]
        in rankings[BASELINE_POLICY_VERSION]["top_state_ids"])
    # The baseline leg is derived from the first action revision (E1), the revision
    # the declared baseline rule produces: the rule replayed over the recorded
    # contradiction count must be the recorded baseline decision.
    chain = _candidate_chain(runtime, repository, {"candidate_id": summary["candidate_id"]})
    baseline_entry = chain[1]
    contradicted = sum(1 for check in baseline_entry.evidence.checks
                       if check.outcome == CHECK_CONTRADICTED)
    derived = baseline_next_move(contradicted)
    assert derived["move"] == comparison["investigation"]["baseline_next_move"]
    assert derived["reason_code"] == comparison["investigation"]["baseline_reason_code"]
    assert comparison["investigation"]["baseline_revision"] == {
        "evidence_state_id": baseline_entry.evidence_state_id,
        "evidence_hash": baseline_entry.record.evidence_hash,
        "revision_index": 1,
        "action_id": "CHECK_EVIDENCE_INTEGRITY_V1",
    }


def test_investigation_baseline_consumes_e1_not_the_final_revision(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    [payload] = _final_result_payloads(repository, runtime[2], run_id)
    chain = _candidate_chain(runtime, repository, {"candidate_id": summary["candidate_id"]})
    assert [item.evidence.revision_index for item in chain] == [0, 1, 2]

    investigation = payload["baseline_comparison"]["investigation"]
    assert investigation["baseline_revision_rule"] == "FIRST_ACTION_REVISION"
    assert investigation["baseline_revision"] == {
        "evidence_state_id": chain[1].evidence_state_id,
        "evidence_hash": chain[1].record.evidence_hash,
        "revision_index": 1,
        "action_id": "CHECK_EVIDENCE_INTEGRITY_V1",
    }
    assert investigation["observed_final_revision"]["evidence_state_id"] == \
        chain[2].evidence_state_id
    assert investigation["observed_final_revision"]["revision_index"] == 2
    assert investigation["baseline_next_move"] == "COMPLETE"
    assert investigation["actual_final_move"] == "ABSTAIN"
    assert investigation["comparison"] == "DIFFERENT"
    assert investigation["extra_follow_up_dispatches"] == 1
    assert investigation["hypotheses_generated"] == 0
    assert investigation["stopping_changed"] is True
    assert "follow_up_changed" not in investigation, "the baseline never dispatches; the flag is tautological"
    assert "hypothesis_generation_changed" not in investigation
    assert "evidence_revisions_attributable_to_jev_route" not in investigation, \
        "every dispatch is made by the recorded Python policy, never attributed to Jev"


def test_baseline_leg_uses_e1_even_when_only_a_later_revision_contradicts(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    artifacts = runtime[2]
    candidate = repository.get_candidate(summary["candidate_id"])
    chain = _candidate_chain(runtime, repository, candidate)
    assert [item.evidence.revision_index for item in chain] == [0, 1, 2]
    contradicted = replace(
        chain[2].evidence,
        checks=(replace(chain[2].evidence.checks[0], outcome=CheckOutcome.CONTRADICTED,
                        reason="synthetic contradiction"),))
    synthetic_chain = [
        chain[0], chain[1],
        SimpleNamespace(evidence=contradicted, evidence_state_id=chain[2].evidence_state_id,
                        record=chain[2].record),
    ]
    final_result, comparison = derive_stage8(
        run_id=run_id, candidate=candidate, investigation_status="ABSTAINED",
        final_move="ABSTAIN", stop_reason="DEEP_JUDGMENT_UNAVAILABLE", error_code=None,
        steps=tuple(summary["steps"]), decisions=tuple(summary["decisions"]), hypothesis=None,
        stored_state=read_candidate_state(repository, artifacts, candidate["candidate_id"]),
        chain=synthetic_chain,
        executions=repository.followup_executions_for(candidate["candidate_id"]),
        dossier_id="dossier-test", promoted_by_policy=False, rankings={}, mode="LIVE")

    assert final_result["final_evidence_revision"]["checks"]["contradicted"] == 1
    investigation = comparison["investigation"]
    assert investigation["observed_final_revision"]["revision_index"] == 2
    assert investigation["baseline_revision"]["revision_index"] == 1, \
        "the baseline leg consumes the first action revision, not the final one"
    assert investigation["baseline_next_move"] == "COMPLETE", \
        "a contradiction found only after E1 cannot flip the declared baseline"


def test_multi_candidate_run_finalizes_each_candidate_then_completes_the_run(
        runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selections=("GENEONE", "GENETWO"),
        deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1")
    run_id = orchestrator.run()
    completed = [event for event in _events(repository, run_id)
                 if event["type"] == "RUN_COMPLETED"][-1]["data"]
    assert completed["run_scope"] == "CANDIDATE_QUEUE_EXHAUSTED"
    assert completed["candidate_queue_exhausted"] is True
    assert len(completed["deep"]["candidates_completed"]) == 2
    assert all(item["candidate_status"] == "CANDIDATE_COMPLETE"
               for item in completed["deep"]["candidates_completed"])
    assert len(repository.list_table("dossiers", run_id)) == 2
    assert len(_final_result_payloads(repository, runtime[2], run_id)) == 2
    candidate_events = [event for event in _events(repository, run_id)
                        if event["type"] == "CANDIDATE_COMPLETED"]
    assert len(candidate_events) == 2
    assert len({event["data"]["candidate_id"] for event in candidate_events}) == 2
    run_completed_sequence = next(event["sequence"] for event in _events(repository, run_id)
                                  if event["type"] == "RUN_COMPLETED")
    assert max(event["sequence"] for event in candidate_events) < run_completed_sequence, \
        "RUN_COMPLETE happens only after the candidate queue is exhausted"


def test_every_completed_candidate_has_an_authoritative_dossier_with_stage8_sections(
        runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    candidate = _completed_candidate(repository, run_id)
    assert candidate["dossier_id"]
    dossier = read_dossier_record(repository, runtime[2], candidate["dossier_id"])
    payload = json.loads(dossier.content)
    assert payload["schema_version"] == 3
    assert payload["final_result"]["candidate_id"] == candidate["candidate_id"]
    assert payload["comparison"]["overall"]
    assert payload["sections"]["final_candidate_result"]["availability"] == "OBSERVED"
    assert payload["sections"]["jev_vs_no_jev_comparison"]["availability"] == "OBSERVED"
    assert payload["limitations"]


def test_markdown_is_derived_from_the_same_structured_dossier(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    candidate = _completed_candidate(repository, run_id)
    row = repository.get_dossier(candidate["dossier_id"])
    json_artifact = repository.artifact(row["json_artifact_id"])
    markdown_artifact = repository.artifact(row["markdown_artifact_id"])
    structured = json.loads(runtime[2].read(json_artifact["relative_path"],
                                            json_artifact["sha256"]))
    markdown = runtime[2].read(markdown_artifact["relative_path"],
                               markdown_artifact["sha256"]).decode()
    assert "Final Candidate Result" in markdown
    assert "Jev Vs No Jev Comparison" in markdown
    assert structured["dossier_id"] in markdown


def test_dossier_admission_provenance_reflects_the_recorded_policy(runtime, monkeypatch):
    # GENEONE resolves as the wide-policy promoted candidate; GENETWO stays unqualified
    # (below the admission threshold), so selecting it creates an explicitly
    # operator-selected candidate with its own provenance.
    class _UnqualifyGeneTwo(StubAdapter):
        def evaluate(self, state, definitions):
            if state.get("entity", {}).get("symbol") == "GENETWO":
                self.override = {"warrants_deeper_investigation":
                                     {"kind": "noul", "probability_yes": 0.10}}
            else:
                self.override = {}
            return super().evaluate(state, definitions)

    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_UnqualifyGeneTwo(),
        deep_selections=("GENEONE", "GENETWO"), deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1")
    run_id = orchestrator.run()
    candidates = repository.list_table("candidates", run_id)
    promoted = next(candidate for candidate in candidates
                    if candidate["summary"]["policy_version"] == "wide-policy-v2")
    operator = next(candidate for candidate in candidates
                    if candidate["summary"]["policy_version"] == "operator-selection-v1")
    promoted_payload = json.loads(read_dossier_record(
        repository, runtime[2], promoted["dossier_id"]).content)
    operator_payload = json.loads(read_dossier_record(
        repository, runtime[2], operator["dossier_id"]).content)
    assert "Candidate was admitted by wide-policy-v2" in \
        promoted_payload["sections"]["jev_wide_judgments"]["narrative"]
    operator_narrative = operator_payload["sections"]["jev_wide_judgments"]["narrative"]
    assert "explicitly selected for investigation after Wide evaluation" in operator_narrative
    assert "operator-selection-v1" in operator_narrative


def test_stage8_does_not_emit_human_review_or_require_a_release_gate(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    assert "HUMAN_REVIEW_REQUIRED" not in json.dumps(_events(repository, run_id))
    assert "HUMAN_REVIEW_REQUIRED" not in json.dumps(
        repository.list_table("dossiers", run_id))
    assert summary["candidate_status"] == "CANDIDATE_COMPLETE"
    assert summary["dossier"]["dossier_id"], "the dossier is persisted and referenced"


def test_baseline_replay_mutates_nothing(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    candidate = repository.get_candidate(summary["candidate_id"])
    chain_before = [(row.evidence_state_id, row.record.evidence_hash)
                    for row in _candidate_chain(runtime, repository, candidate)]
    hypotheses_before = repository.page_child("hypotheses", run_id, 50, None, {})["items"]
    deep_before = repository.page_child(
        "jev_evaluations", run_id, 50, None, {"purpose": "DEEP"})["items"]
    executions_before = len(repository.followup_executions_for(candidate["candidate_id"]))
    rerun = run_stage8_finalize(
        run_id=run_id, candidate=candidate, investigation_status="ABSTAINED",
        final_move="ABSTAIN", stop_reason="NO_FURTHER_REGISTERED_ACTION", error_code=None,
        steps=(), decisions=(), hypothesis=None, repository=repository,
        artifacts=runtime[2], emit=lambda *args, **kwargs: None,
        publish_json=lambda run_id, path, payload, purpose: runtime[2].publish(
            path, json.dumps(payload, sort_keys=True).encode(), "application/json", purpose),
    )
    assert rerun["dossier_status"] == "DOSSIER_READY"
    chain_after = [(row.evidence_state_id, row.record.evidence_hash)
                   for row in _candidate_chain(runtime, repository, candidate)]
    assert chain_after == chain_before, "the baseline replay never writes evidence"
    assert len(repository.followup_executions_for(candidate["candidate_id"])) == executions_before
    assert repository.page_child("hypotheses", run_id, 50, None, {})["items"] == hypotheses_before
    assert len(repository.page_child(
        "jev_evaluations", run_id, 50, None, {"purpose": "DEEP"})["items"]) == len(deep_before), \
        "no model call happens in the no-Jev replay"


def test_stage8_replay_repairs_an_interrupted_completion(runtime, monkeypatch):
    """A crash between the dossier and CANDIDATE_COMPLETE must not strand the candidate."""
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    candidate = repository.get_candidate(summary["candidate_id"])
    assert candidate["status"] == "CANDIDATE_COMPLETE"
    with repository.database.connect(write=True) as connection:
        connection.execute("UPDATE candidates SET status='DOSSIER_READY' WHERE candidate_id=?",
                           (candidate["candidate_id"],))

    rerun = run_stage8_finalize(
        run_id=run_id, candidate=candidate, investigation_status="ABSTAINED",
        final_move="ABSTAIN", stop_reason="NO_FURTHER_REGISTERED_ACTION", error_code=None,
        steps=(), decisions=(), hypothesis=None, repository=repository,
        artifacts=runtime[2],
        emit=lambda rid, event_type, key, message, **kwargs: repository.append_event(
            rid, event_type=event_type, idempotency_key=key, message=message, **kwargs),
        publish_json=lambda rid, path, payload, purpose: runtime[2].publish(
            path, json.dumps(payload, sort_keys=True).encode(), "application/json", purpose),
    )

    assert rerun["dossier_status"] == "DOSSIER_READY"
    assert repository.get_candidate(candidate["candidate_id"])["status"] == "CANDIDATE_COMPLETE"
    repairs = [event for event in _events(repository, run_id)
               if event["type"] == "CANDIDATE_COMPLETED"
               and event["data"].get("reason_code") == "FINALIZATION_STATUS_REPAIRED"]
    assert len(repairs) == 1
    assert repairs[0]["data"]["dossier_id"]


def test_dossier_retry_completes_after_an_interrupted_dossier_write(runtime, monkeypatch):
    """Crash between the dossier file write and DOSSIER_CREATED: retry adopts the bytes."""
    _, repository, artifacts = runtime
    original = repository.append_event
    crash = {"on": True}

    def crashing_append(target_run_id, **kwargs):
        if crash["on"] and kwargs.get("event_type") == "DOSSIER_CREATED":
            raise KeyboardInterrupt()
        return original(target_run_id, **kwargs)

    monkeypatch.setattr(repository, "append_event", crashing_append)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE",
        deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1")
    with pytest.raises(KeyboardInterrupt):
        orchestrator.run()
    crash["on"] = False

    run_id = repository.list_runs(5)[0]["run_id"]
    assert repository.get_run(run_id)["status"] == "STOPPED"
    candidate = repository.list_table("candidates", run_id)[0]
    assert candidate["status"] not in {"CANDIDATE_COMPLETE", "FAILED", "DEFERRED"}
    [json_file] = (runtime[0].data_dir / f"runs/{run_id}/dossier").glob("*.json")
    recorded_bytes = json_file.read_bytes()

    retried = run_dossier_stage(
        run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
        decisions=[],
        publish_json=lambda rid, path, payload, purpose: artifacts.publish(
            path, canonical_json(payload), "application/json", purpose),
        emit=lambda rid, event_type, key, message, **kwargs: repository.append_event(
            rid, event_type=event_type, idempotency_key=key, message=message, **kwargs),
        mode="LIVE",
    )

    assert retried.get("error_code") is None, retried
    assert json_file.read_bytes() == recorded_bytes, \
        "the recorded dossier is adopted byte-for-byte, never rewritten"
    assert len(repository.list_table("dossiers", run_id)) == 1

    assert repository.recover_interrupted() == []
    assert repository.get_candidate(candidate["candidate_id"])["status"] == "CANDIDATE_COMPLETE", \
        "the retried dossier is owned, so the orphan is completed, never stranded"
    assert len([event for event in _events(repository, run_id)
                if event["type"] == "CANDIDATE_COMPLETED"]) == 1


def test_dossier_retry_refuses_a_colliding_dossier_as_a_typed_failure(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    candidate = repository.get_candidate(summary["candidate_id"])
    dossier_id = summary["dossier"]["dossier_id"]
    path = f"runs/{run_id}/dossier/{dossier_id}.json"
    (runtime[0].data_dir / path).write_bytes(b'{"dossier_id": "not-this-candidate"}')

    retried = run_dossier_stage(
        run_id=run_id, candidate=candidate, repository=repository, artifacts=runtime[2],
        decisions=[],
        publish_json=lambda rid, path, payload, purpose: runtime[2].publish(
            path, canonical_json(payload), "application/json", purpose),
        emit=lambda rid, event_type, key, message, **kwargs: repository.append_event(
            rid, event_type=event_type, idempotency_key=key, message=message, **kwargs),
        mode="LIVE",
    )

    assert retried["status"] == "UNAVAILABLE"
    assert retried["error_code"] == "DOSSIER_CONTENT_COLLISION"


def test_plan_abstention_is_finalized_not_comparable_downstream(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, deep_action_id="NOT_A_REGISTERED_ACTION")
    [payload] = _final_result_payloads(repository, runtime[2], run_id)
    assert payload["final_move"] is None
    assert payload["stop_reason"] == "SELECTED_ACTION_NOT_ELIGIBLE"
    comparison = payload["baseline_comparison"]
    assert comparison["investigation"]["comparison"] == "NOT_COMPARABLE"
    assert comparison["investigation"]["baseline_next_move"] is None
    dossier = read_dossier_record(repository, runtime[2], payload["dossier_reference"])
    assert json.loads(dossier.content)["final_result"]["stop_reason"] == \
        "SELECTED_ACTION_NOT_ELIGIBLE"


def test_multiple_eligible_dispatch_is_refused_without_hidden_ordering(runtime, monkeypatch):
    import cancerjev.research.deep as deep_module

    original = deep_module.eligible_actions

    def _two_eligible(record, input_kind):
        if input_kind == "STATISTICAL_STATE":
            return original(record, input_kind)
        from cancerjev.science.actions import ActionEligibility
        # Two real registered action ids: the refusal must come from the count rule,
        # not from an unknown id.
        return [
            ActionEligibility(action_id="CHECK_REVISION_FAITHFULNESS_V1", eligible=True,
                              reasons=(), prerequisites={}),
            ActionEligibility(action_id="SUMMARIZE_CNV_CATEGORIES_V1", eligible=True,
                              reasons=(), prerequisites={}),
        ]

    deep_module.eligible_actions = _two_eligible
    try:
        run_id, summary, repository = _completed_slice(
            runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    finally:
        deep_module.eligible_actions = original
    assert summary["stop_reason"] == "EXPLICIT_ACTION_REQUIRED"
    executions = repository.followup_executions_for(summary["candidate_id"])
    assert [row["action_id"] for row in executions] == ["CHECK_EVIDENCE_INTEGRITY_V1"], \
        "lexicographic ordering must not select a second action"


def test_action_registry_bounds_the_dispatch_decision(runtime, monkeypatch):
    from cancerjev.science.actions import ACTION_REGISTRY
    assert "AAA_FAKE_ACTION_V1" not in ACTION_REGISTRY
    assert "ZZZ_FAKE_ACTION_V1" not in ACTION_REGISTRY
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    assert summary["candidate_status"] == "CANDIDATE_COMPLETE"