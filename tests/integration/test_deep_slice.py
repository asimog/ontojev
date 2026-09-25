"""Deep slice integration: E0/E1/E2 revisions, bounded dispatch and typed readers.

The slice is driven through the real live-shaped run (ReplayTransport, StubAdapter) or
through the explicit collaborator entrypoints. Assertions read immutable schema-4
artifacts through the validated readers; a judgment never selects or executes an action.
"""

from __future__ import annotations

import pytest

from cancerjev.domain.evidence import EvidenceState
from cancerjev.jev.contracts import JevContractError
from cancerjev.jev.typesafe_adapter import JevProviderError
from cancerjev.research import deep
from cancerjev.research.deep import (
    FollowUpResult,
    dispatch_recorded_move,
    load_candidate_evidence,
)
from cancerjev.research.live import LiveOrchestrator
from cancerjev.science.actions import ActionError
from cancerjev.storage.readers import (
    read_evidence_record,
    read_revision_chain,
)
from tests.integration.replay import GENES
from tests.integration.test_live_replay import (
    LUAD_RESEARCH_V1,
    _events,
    _orchestrator,
)
from tests.jev.stub_adapter import StubAdapter

GENE_ONE, GENE_TWO = GENES
INTEGRITY_CHECKS = {
    "COHORT_FRAME_AGREEMENT", "EXPRESSION_COVERAGE_ARITHMETIC", "MUTATION_COUNT_SCOPE",
    "TESTED_UNIVERSE_REPRODUCIBLE", "RESPONSE_ARTIFACT_INTEGRITY",
}


# --------------------------------------------------------------------------- helpers


def _abstaining_adapter() -> StubAdapter:
    return StubAdapter(override={"warrants_deeper_investigation":
                                     {"kind": "noul", "probability_yes": 0.05}})


def _followup_adapter() -> StubAdapter:
    return StubAdapter(
        override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}},
        deep_override={"stopping_more_honest": {"kind": "noul", "probability_yes": 0.2},
                       "next_step_warranted": {"kind": "noul", "probability_yes": 0.8}},
    )


class _FailsForSecondGene(StubAdapter):
    def evaluate(self, state, definitions):
        if state.get("entity", {}).get("symbol") == "GENETWO":
            self.calls += 1
            raise JevProviderError("PROVIDER_ERROR", "synthetic-wide-failure")
        return super().evaluate(state, definitions)


class _FailsOnEvidenceJudgment(StubAdapter):
    def evaluate(self, state, definitions):
        if state.get("projection_version") == "jev-evidence-projection-v2":
            self.calls += 1
            raise JevContractError("INVALID_DISTRIBUTION", "synthetic-deep-judgment-failure")
        return super().evaluate(state, definitions)


def _completed_slice(runtime, monkeypatch, *, jev_adapter=None, **kwargs):
    kwargs.setdefault("deep_action_id", "CHECK_EVIDENCE_INTEGRITY_V1")
    adapter = jev_adapter if jev_adapter is not None else StubAdapter()
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=adapter, deep_selection="GENEONE", **kwargs)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    summaries = completed["data"]["deep"]["candidates"]
    assert len(summaries) == 1
    return run_id, summaries[0], repository


def _operator_slice(runtime, monkeypatch, **kwargs):
    kwargs.setdefault("deep_action_id", "CHECK_EVIDENCE_INTEGRITY_V1")
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_abstaining_adapter(),
        deep_selection="GENEONE", deep_followup_authorized=True, **kwargs)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    return run_id, completed["data"]["deep"]["candidates"][0], repository


def _candidate_chain(runtime, repository, candidate):
    return read_revision_chain(repository, runtime[2], candidate["candidate_id"])


# ------------------------------------------------------------------- selection grammar


def test_deep_slice_requires_explicit_operator_selection(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter())
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    assert repository.list_table("candidates", run_id) != []
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("followup_executions", run_id) == []
    assert repository.list_table("dossiers", run_id) == []

    started = next(event for event in _events(repository, run_id)
                   if event["type"] == "RUN_STARTED")
    assert started["data"]["deep_selection"] is None
    assert started["data"]["deep_selections"] == []
    assert started["data"]["deep_action_id"] is None
    assert started["data"]["deep_followup_authorized"] is False
    assert started["data"]["deep_dispatch_rule"] is None
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    assert "deep" not in completed["data"]


def test_deep_selection_grammar_is_bounded_and_typed(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    orchestrator = LiveOrchestrator(settings, repository, artifacts, lambda event: None,
                                    research_spec=LUAD_RESEARCH_V1)
    index = {
        "state-1": {"state_id": "state-1", "entity": {"gene_symbol": GENE_ONE}},
        "state-2": {"state_id": "state-2", "entity": {"gene_symbol": GENE_ONE}},
        "state-3": {"state_id": "state-3", "entity": {"gene_symbol": GENE_TWO}},
    }
    assert orchestrator._operator_selection_target("slot:1", index) == (
        None, "only a policy-promoted candidate can be named by slot")
    assert orchestrator._operator_selection_target("state:missing", index) == (
        None, "no statistical state in this run has that id")
    assert orchestrator._operator_selection_target(GENE_ONE, index) == (
        None, "the gene symbol is ambiguous in this run; use state:<state_id>")
    assert orchestrator._operator_selection_target(GENE_TWO, index) == ("state-3", None)
    assert orchestrator._operator_selection_target("state:state-1", index) == ("state-1", None)
    assert orchestrator._operator_selection_target(f"gene:{GENE_TWO}", index) == ("state-3", None)
    assert orchestrator._operator_selection_target("NOPE", index) == (
        None, "no statistical state in this run has that gene symbol")


# ------------------------------------------------------------------------ E0 and E1


def test_live_deep_slice_creates_e0_and_e1_from_one_explicit_action(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    assert summary["status"] == "COMPLETED"
    assert summary["investigation_status"] == "COMPLETED"
    assert summary["candidate_status"] == "CANDIDATE_COMPLETE"
    assert summary["final_move"] == "COMPLETE"
    assert summary["stop_reason"] == "INVESTIGATION_COMPLETE"
    assert summary["first_step"]["next_move"]["reason_code"] == "INVESTIGATION_COMPLETE"
    assert summary["first_step"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert summary["first_step"]["checks_total"] == 5
    assert summary["first_step"]["checks_verified"] == 5
    assert summary["first_step"]["deep_model"] == "jev-1.13.0"
    assert summary["first_step"]["deep_question_set_version"] == "deep-v1"
    assert summary["dispatch"] is None, "a terminal move is never routed through the dispatcher"
    assert summary["last_dispatch"] is None

    candidate = repository.get_candidate(summary["candidate_id"])
    assert candidate["status"] == "CANDIDATE_COMPLETE"
    assert candidate["entity"]["gene_symbol"] == "GENEONE"

    chain = _candidate_chain(runtime, repository, candidate)
    assert [stored.evidence.revision_index for stored in chain] == [0, 1]
    baseline_row = repository.get_evidence_state(chain[0].evidence_state_id)
    assert baseline_row["previous_evidence_state_id"] is None
    assert baseline_row["iteration"] == 0
    assert chain[0].evidence.action is None
    assert chain[0].evidence.parent_evidence_hash is None
    assert chain[0].evidence.puzzle.origin == "STATISTICAL_STATE_BASELINE"

    source_state = repository.get_state(candidate["source_state_id"])
    assert chain[0].evidence.accepted_state_hash == source_state["state_hash"]
    assert chain[1].evidence.accepted_state_hash == source_state["state_hash"]
    assert chain[1].evidence.parent_evidence_hash == chain[0].record.evidence_hash
    assert chain[1].evidence.action.action_id == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert chain[1].evidence.action.version == "1"
    assert chain[1].evidence.puzzle.origin == "DETERMINISTIC_ACTION_REGISTRY"
    assert chain[1].evidence.summary.total == 5
    assert chain[1].evidence.summary.verified == 5
    assert chain[1].evidence.summary.contradicted == 0
    assert {check.check_id for check in chain[1].evidence.checks} == INTEGRITY_CHECKS
    assert {check.outcome.value for check in chain[1].evidence.checks} == {"VERIFIED"}
    assert len(chain[1].evidence.missing_evidence) == 1
    absent = chain[1].evidence.missing_evidence[0]
    assert absent.needed_evidence == "new_gdc_measurement"
    assert absent.availability.value == "NOT_ACQUIRED"
    assert len(chain[0].evidence.baseline_observations) == 3
    assert chain[1].evidence.baseline_observations == ()
    assert chain[1].evidence.provenance.input_artifacts
    assert all(item.verified for item in chain[1].evidence.provenance.input_artifacts)

    executions = repository.followup_executions_for(candidate["candidate_id"])
    assert len(executions) == 1
    execution = executions[0]
    assert execution["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert execution["status"] == "COMPLETED"
    assert execution["slot"] == 1
    assert execution["input_evidence_hash"] == source_state["state_hash"]
    assert execution["output_evidence_state_id"] == chain[1].evidence_state_id

    types = [event["type"] for event in _events(repository, run_id)]
    assert types.count("EVIDENCE_STATE_CREATED") == 2
    assert types.count("FOLLOWUP_STARTED") == 1
    assert types.count("FOLLOWUP_COMPLETED") == 1
    assert types.count("JEV_DEEP_EVIDENCE_JUDGED") == 1
    assert types.count("NEXT_MOVE_SELECTED") == 1
    assert types.count("DOSSIER_CREATED") == 1
    assert types.index("ELIGIBLE_ACTIONS_COMPUTED") < types.index("FOLLOWUP_STARTED") \
        < types.index("JEV_DEEP_EVIDENCE_JUDGED") < types.index("DOSSIER_CREATED")

    decisions = [event for event in _events(repository, run_id)
                 if event["type"] == "NEXT_MOVE_SELECTED"]
    assert len(decisions) == 1
    decision = decisions[0]["data"]
    assert decision["executed"] is False, "Jev never selects or executes the recorded move"
    assert decision["policy_version"] == "deep-policy-v2"
    assert decision["evaluation_id"] == summary["first_step"]["deep_evaluation_id"]
    assert set(decision["dimensions"]) == {
        "revision_reliable", "evidence_sufficient_for_next_step", "next_step_warranted",
        "stopping_more_honest", "dominant_limitation", "checks_contradicted",
        "eligible_action_ids", "distinct_eligible_action_ids",
    }
    assert decision["dimensions"]["eligible_action_ids"] == ["CHECK_REVISION_FAITHFULNESS_V1"]
    # The COMPLETE terminal move is never routed through the dispatcher: no
    # NEXT_MOVE_DISPATCHED event exists for a terminal arc.


# ------------------------------------------------------- recorded FOLLOW_UP dispatch


def test_autonomous_follow_up_is_recorded_but_never_dispatched_without_authorization(
        runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(runtime, monkeypatch, jev_adapter=_followup_adapter())
    assert summary["final_move"] == "FOLLOW_UP"
    assert summary["status"] == "STOPPED"
    assert summary["stop_reason"] == "DISPATCH_NOT_AUTHORIZED"
    manifest = summary["first_step"]["next_move"]
    assert manifest["move"] == "FOLLOW_UP"
    assert manifest["executed"] is False
    assert manifest["dimensions"]["distinct_eligible_action_ids"] == ["CHECK_REVISION_FAITHFULNESS_V1"]

    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0, 1]
    assert len(repository.followup_executions_for(candidate["candidate_id"])) == 1
    dispatch = next(event for event in _events(repository, run_id)
                    if event["type"] == "NEXT_MOVE_DISPATCHED")
    assert dispatch["data"]["reason_code"] == "DISPATCH_NOT_AUTHORIZED"
    assert dispatch["data"]["dispatched"] is False
    assert dispatch["data"]["authorized"] is False
    assert dispatch["data"]["move"] == "FOLLOW_UP"


def test_recorded_follow_up_is_dispatched_once_when_authorized(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    assert len(summary["steps"]) == 2
    assert summary["steps"][0]["dispatch"]["dispatched"] is True
    assert summary["steps"][0]["dispatch"]["reason_code"] == "DISPATCHED"
    assert summary["steps"][1]["action_id"] == "CHECK_REVISION_FAITHFULNESS_V1"
    assert summary["steps"][1]["iteration"] == 2
    assert "dispatch" not in summary["steps"][1], "the ABSTAIN terminal move is not dispatched"
    assert summary["final_move"] == "ABSTAIN"
    assert summary["status"] == "ABSTAINED"
    assert summary["stop_reason"] == "NO_FURTHER_REGISTERED_ACTION"
    assert summary["candidate_status"] == "CANDIDATE_COMPLETE"

    candidate = repository.get_candidate(summary["candidate_id"])
    chain = _candidate_chain(runtime, repository, candidate)
    assert [stored.evidence.revision_index for stored in chain] == [0, 1, 2]
    assert chain[2].parent_id == chain[1].evidence_state_id
    assert chain[2].evidence.parent_evidence_hash == chain[1].record.evidence_hash
    assert chain[2].evidence.action.action_id == "CHECK_REVISION_FAITHFULNESS_V1"
    assert chain[2].evidence.puzzle.origin == "DETERMINISTIC_ACTION_REGISTRY"
    assert candidate["latest_evidence_state_id"] == chain[2].evidence_state_id

    executions = repository.followup_executions_for(candidate["candidate_id"])
    assert [(row["action_id"], row["slot"], row["status"]) for row in executions] == [
        ("CHECK_EVIDENCE_INTEGRITY_V1", 1, "COMPLETED"),
        ("CHECK_REVISION_FAITHFULNESS_V1", 2, "COMPLETED"),
    ]
    assert executions[1]["input_evidence_hash"] == chain[1].record.evidence_hash
    assert executions[1]["output_evidence_state_id"] == chain[2].evidence_state_id

    disposition = {check.check_id: check.outcome.value for check in chain[2].evidence.checks}
    assert set(disposition) == {
        "SOURCE_EVIDENCE_RESTATED", "SOURCE_PROVENANCE_UNCHANGED",
        "SOURCE_STATE_IDENTITY_REPRODUCIBLE", "REVISION_CHAIN_LINKED",
    }
    assert disposition["SOURCE_EVIDENCE_RESTATED"] == "VERIFIED"
    assert disposition["SOURCE_PROVENANCE_UNCHANGED"] == "VERIFIED"
    assert disposition["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == "VERIFIED"
    assert disposition["REVISION_CHAIN_LINKED"] == "VERIFIED"
    assert not any(item.needed_evidence == "SOURCE_EVIDENCE_RESTATED"
                   for item in chain[2].evidence.missing_evidence)
    assert any(item.needed_evidence == "new_gdc_measurement"
               for item in chain[2].evidence.missing_evidence)
    assert chain[2].evidence.provenance.gdc_release

    deep_evaluations = repository.page_child("jev_evaluations", run_id, 20, None,
                                             {"purpose": "DEEP"})["items"]
    assert len(deep_evaluations) == 2
    assert [row["vector"]["evidence_state_id"] for row in deep_evaluations] == [
        chain[1].evidence_state_id, chain[2].evidence_state_id]
    assert all(row["vector"]["question_set_version"] == "deep-v1" for row in deep_evaluations)
    assert all(row["vector"]["input_ref_kind"] == "EVIDENCE_STATE" for row in deep_evaluations)
    judgements = [event for event in _events(repository, run_id)
                  if event["type"] == "JEV_DEEP_EVIDENCE_JUDGED"]
    assert len(judgements) == 2, "each revision is judged exactly once"


def test_dispatch_respects_the_caps(runtime, monkeypatch):
    monkeypatch.setattr(deep, "FOLLOWUP_LIMIT", 1)
    _, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    assert summary["status"] == "STOPPED"
    assert summary["stop_reason"] == "FOLLOWUP_LIMIT_REACHED"
    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0, 1]
    executions = [row for row in repository.list_table("followup_executions")
                  if row["candidate_id"] == candidate["candidate_id"]]
    assert len(executions) == 1

    monkeypatch.setattr(deep, "FOLLOWUP_LIMIT", 3)
    monkeypatch.setattr(deep, "EVIDENCE_ITERATION_LIMIT", 1)
    _, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    assert summary["status"] == "STOPPED"
    assert summary["stop_reason"] == "EVIDENCE_ITERATION_LIMIT_REACHED"
    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0, 1]


def test_a_failed_attempt_consumes_follow_up_budget(runtime, monkeypatch):
    monkeypatch.setattr(deep, "FOLLOWUP_LIMIT", 2)

    real_execute = deep.execute

    def failing_execute(action_id, state, *, read_artifact):
        if isinstance(state, EvidenceState):
            raise ActionError("ACTION_EXECUTION_FAILED", "synthetic dispatched-action failure")
        return real_execute(action_id, state, read_artifact=read_artifact)

    monkeypatch.setattr(deep, "execute", failing_execute)
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, jev_adapter=_followup_adapter(), deep_followup_authorized=True)
    assert summary["status"] == "STOPPED"
    assert summary["stop_reason"] == "DISPATCH_ACTION_FAILED"
    candidate = repository.get_candidate(summary["candidate_id"])
    executions = repository.followup_executions_for(candidate["candidate_id"])
    assert [(row["action_id"], row["status"]) for row in executions] == [
        ("CHECK_EVIDENCE_INTEGRITY_V1", "COMPLETED"),
        ("CHECK_REVISION_FAITHFULNESS_V1", "FAILED"),
    ]
    failed = [event for event in _events(repository, run_id) if event["type"] == "FOLLOWUP_FAILED"]
    assert failed and failed[-1]["data"]["error_code"] == "ACTION_EXECUTION_FAILED"
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0, 1]

    monkeypatch.setattr(deep, "execute", real_execute)
    chain = _candidate_chain(runtime, repository, candidate)
    stored = read_evidence_record(repository, runtime[2], chain[1].evidence_state_id)
    result = FollowUpResult(
        status="COMPLETED", action_id=stored.evidence.action.action_id,
        evidence_state_id=stored.evidence_state_id, evidence_hash=stored.record.evidence_hash,
        iteration=stored.evidence.revision_index, checks_total=stored.evidence.summary.total,
        checks_verified=stored.evidence.summary.verified,
        checks_contradicted=stored.evidence.summary.contradicted,
        checks_not_observed=stored.evidence.summary.not_observed,
        error_code=None, revision=stored.record,
    )
    loaded = load_candidate_evidence(repository, runtime[2], candidate)
    assert loaded is not None
    decision = {"move": "FOLLOW_UP",
                "dimensions": {"distinct_eligible_action_ids": ["CHECK_REVISION_FAITHFULNESS_V1"]}}
    emitted: list[str] = []

    def emit(rid, event_type, key, message, **kwargs):
        emitted.append(event_type)
        return repository.append_event(rid, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    refused = dispatch_recorded_move(
        run_id=run_id, candidate=loaded, result=result, decision=decision, repository=repository,
        emit=emit, publish_json=lambda *args: pytest.fail("a refused dispatch never publishes"),
        read_artifact=lambda artifact_id: None, authorized=True,
    )
    assert refused.dispatched is False
    assert refused.reason_code == "FOLLOWUP_LIMIT_REACHED"
    assert emitted == ["NEXT_MOVE_DISPATCHED"]
    refusal_event = _events(repository, run_id)[-1]
    assert "failed attempt consumes budget" in refusal_event["data"]["detail"]
    assert len(repository.followup_executions_for(candidate["candidate_id"])) == 2


@pytest.mark.parametrize(("limit_name", "limit", "reason"), [
    ("FOLLOWUP_LIMIT", 0, "FOLLOWUP_LIMIT_REACHED"),
    ("EVIDENCE_ITERATION_LIMIT", 0, "EVIDENCE_ITERATION_LIMIT_REACHED"),
])
def test_budget_exhaustion_abstains_and_stops(runtime, monkeypatch, limit_name, limit, reason):
    monkeypatch.setattr(deep, limit_name, limit)
    run_id, summary, repository = _completed_slice(runtime, monkeypatch)
    assert summary["status"] == reason
    assert summary["final_move"] is None
    assert summary["stop_reason"] == reason
    assert summary["steps"] == []
    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0]
    assert repository.followup_executions_for(candidate["candidate_id"]) == []
    assert len(repository.list_table("dossiers", run_id)) == 1, \
        "Stage 8 still records the dossier for the accepted-evidence abstention"
    assert candidate["status"] == "CANDIDATE_COMPLETE"


def test_unknown_action_selection_abstains_before_any_attempt(runtime, monkeypatch):
    run_id, summary, repository = _completed_slice(
        runtime, monkeypatch, deep_action_id="NOT_A_REGISTERED_ACTION")
    assert summary["status"] == "SELECTED_ACTION_NOT_ELIGIBLE"
    assert summary["final_move"] is None
    assert summary["steps"] == []
    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0]
    assert repository.followup_executions_for(candidate["candidate_id"]) == []
    abstained = [event for event in _events(repository, run_id)
                 if event["type"] == "FOLLOWUP_ABSTAINED"]
    assert abstained and abstained[-1]["data"]["reason_code"] == "SELECTED_ACTION_NOT_ELIGIBLE"


def test_several_eligible_actions_are_resolved_by_the_declared_policy(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE",
        deep_followup_authorized=True)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    eligibility = next(event for event in _events(repository, run_id)
                       if event["type"] == "ELIGIBLE_ACTIONS_COMPUTED")
    assert len(eligibility["data"]["eligible_action_ids"]) >= 2
    assert eligibility["data"]["selection_policy"] == "deep-action-policy-v1"
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    summary = completed["data"]["deep"]["candidates"][0]
    assert summary["status"] == "COMPLETED"
    assert summary["first_step"]["action_id"] in (
        "CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1",
        "SUMMARIZE_EXPRESSION_TAIL_V1", "SUMMARIZE_CNV_CATEGORIES_V1")
    assert repository.followup_executions_for(summary["candidate_id"])


def test_unmatched_selection_is_not_dispatched(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="NOT-A-GENE")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    summary = completed["data"]["deep"]["candidates"][0]
    assert summary["status"] == "DEEP_SELECTION_UNAVAILABLE"
    assert summary["stop_reason"] == "DEEP_SELECTION_UNAVAILABLE"
    assert summary["candidate_id"] is None
    assert repository.list_table("candidates", run_id) != []
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("dossiers", run_id) == []
    refusal = next(event for event in _events(repository, run_id)
                   if event["type"] == "DEEP_SELECTION_UNAVAILABLE")
    assert refusal["data"]["reason_code"] == "DEEP_SELECTION_UNAVAILABLE"
    assert refusal["data"]["promoted_candidates"] == 2


# -------------------------------------------------------------- operator selections


def test_operator_selection_marks_its_own_rule(runtime, monkeypatch):
    run_id, summary, repository = _operator_slice(runtime, monkeypatch)
    assert summary["status"] == "COMPLETED"
    candidate = repository.get_candidate(summary["candidate_id"])
    assert candidate["summary"]["policy_version"] == "operator-selection-v1"
    assert candidate["summary"]["auto_dispatched"] is False
    promoted = [event for event in _events(repository, run_id)
                if event["type"] == "CANDIDATE_PROMOTED"]
    operator = [event for event in promoted
                if event["data"]["policy_version"] == "operator-selection-v1"]
    assert len(operator) == 1
    assert operator[0]["data"]["auto_dispatched"] is False
    assert "operator" in operator[0]["data"]["selection_rule"]
    assert len(promoted) == 1, "wide admission abstained; only the operator named a candidate"
    assert len(repository.list_table("dossiers", run_id)) == 1


def test_operator_selection_refuses_an_unevaluated_state(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_FailsForSecondGene(), deep_selection="GENETWO")
    run_id = orchestrator.run()
    summary = next(event for event in _events(repository, run_id)
                   if event["type"] == "RUN_COMPLETED")["data"]["deep"]["candidates"][0]
    assert summary["status"] == "DEEP_SELECTION_UNAVAILABLE"
    assert summary["candidate_id"] is None
    refusal = [event for event in _events(repository, run_id)
               if event["type"] == "DEEP_SELECTION_UNAVAILABLE"]
    assert refusal and refusal[-1]["data"]["reason_code"] == "STATE_NOT_EVALUATED"
    candidates = repository.list_table("candidates", run_id)
    assert [candidate["entity"]["gene_symbol"] for candidate in candidates] == ["GENEONE"]
    assert repository.list_table("evidence_states", run_id) == []
    assert repository.list_table("dossiers", run_id) == []


def test_operator_selection_obeys_promotion_cap(runtime, monkeypatch):
    monkeypatch.setattr("cancerjev.research.live.PROMOTION_LIMIT", 0)
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_abstaining_adapter(), deep_selection="GENEONE")
    run_id = orchestrator.run()
    summary = next(event for event in _events(repository, run_id)
                   if event["type"] == "RUN_COMPLETED")["data"]["deep"]["candidates"][0]
    assert summary["status"] == "DEEP_SELECTION_UNAVAILABLE"
    refusal = [event for event in _events(repository, run_id)
               if event["type"] == "DEEP_SELECTION_UNAVAILABLE"]
    assert refusal and refusal[-1]["data"]["reason_code"] == "PROMOTION_LIMIT_REACHED"
    assert repository.list_table("candidates", run_id) == []


def test_multiple_selections_get_independent_arcs(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_abstaining_adapter(),
        deep_selections=("GENEONE", "GENETWO"), deep_followup_authorized=True,
        deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    deep = next(event for event in _events(repository, run_id)
                if event["type"] == "RUN_COMPLETED")["data"]["deep"]
    assert deep["selections"] == ["GENEONE", "GENETWO"]
    assert deep["candidate_count"] == 2
    candidates = repository.list_table("candidates", run_id)
    assert {candidate["entity"]["gene_symbol"] for candidate in candidates} == {"GENEONE", "GENETWO"}
    assert len(repository.list_table("dossiers", run_id)) == 2
    for candidate in candidates:
        chain = _candidate_chain(runtime, repository, candidate)
        assert [stored.evidence.revision_index for stored in chain] == [0, 1]
        assert len(repository.page_child(
            "jev_evaluations", run_id, 20, None,
            {"purpose": "DEEP"})["items"]) == 2


# ------------------------------------------------------------- failure containment


def test_deep_judgment_failure_is_contained_and_typed(runtime, monkeypatch):
    adapter = _FailsOnEvidenceJudgment()
    run_id, summary, repository = _completed_slice(runtime, monkeypatch, jev_adapter=adapter)
    assert summary["status"] == "ABSTAINED"
    assert summary["final_move"] == "ABSTAIN"
    assert summary["stop_reason"] == "DEEP_JUDGMENT_UNAVAILABLE"
    assert summary["first_step"]["deep_error_code"] == "INVALID_DISTRIBUTION"
    assert summary["first_step"]["next_move"]["reason_code"] == "DEEP_JUDGMENT_UNAVAILABLE"
    candidate = repository.get_candidate(summary["candidate_id"])
    assert [stored.evidence.revision_index
            for stored in _candidate_chain(runtime, repository, candidate)] == [0, 1]
    failed = [event for event in _events(repository, run_id) if event["type"] == "JEV_EVALUATION_FAILED"]
    assert failed and failed[-1]["data"]["error_code"] == "INVALID_DISTRIBUTION"
    assert failed[-1]["data"]["evidence_state_id"] == summary["first_step"]["evidence_state_id"]
    assert len(repository.list_table("dossiers", run_id)) == 1, "an available revision still produces a dossier"