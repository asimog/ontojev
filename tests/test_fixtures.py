"""Offline fixture demonstration: the shared engine end-to-end with no network.

``DemoOrchestrator`` substitutes only the transport (``FixtureTransport``) and the Jev
adapter (``FixtureJevAdapter``); the strict parsers, deterministic methods, schema-4
typed states, wide admission, registered actions, deep policy, hypothesis stage and
dossier path are the production code paths. Conftest blocks sockets, so a fixture run
that touched the network fails rather than passing.
"""

from __future__ import annotations

import hashlib
import json

from cancerjev.domain.codecs import read_state, state_identity
from cancerjev.jev.questions import DEEP_QUESTIONS, HYPOTHESIS_QUESTIONS, WIDE_QUESTIONS
from cancerjev.research.fixtures import (
    FIXTURE_ID,
    FIXTURE_NOTICE,
    FIXTURE_VERSION,
    FixtureJevAdapter,
)
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.storage.readers import (
    read_dossier_record,
    read_hypothesis_record,
    read_revision_chain,
    read_state_record,
)


def _demo(runtime):
    return DemoOrchestrator(runtime[0], runtime[1], runtime[2], lambda event: None).run()


def _states(repository, run_id):
    return repository.list_table("statistical_states", run_id)


def test_offline_demo_runs_the_shared_engine_end_to_end(runtime):
    _, repository, _ = runtime
    run_id = _demo(runtime)
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "FIXTURE"
    assert run["fixture_id"] == FIXTURE_ID
    assert run["fixture_version"] == FIXTURE_VERSION
    assert run["selected_project_ids"] == ["TCGA-LUAD"]
    assert run["coverage"] == "COMPLETE_FOR_SCOPE"
    assert run["counts"]["states_generated"] == 2
    assert run["counts"]["states_evaluated"] == 2
    assert run["counts"]["candidates_promoted"] == 2
    assert run["counts"]["evidence_revisions"] == 2
    assert run["counts"]["followups_completed"] == 1
    assert run["counts"]["hypotheses_created"] == 2
    assert run["counts"]["dossiers_created"] == 1
    assert run["provider_usage"]["gdc_requests"] == 0, "fixture responses never leave the process"
    assert run["provider_usage"]["jev_calls"] == 5
    assert run["provider_usage"]["llm_calls"] == 0


def test_demo_states_are_typed_immutable_and_recomputable(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    states = _states(repository, run_id)
    assert len(states) == 2
    by_symbol = {}
    for row in states:
        stored = read_state_record(repository, artifacts, row["state_id"])
        boundary = json.loads(stored.artifact.content)
        assert boundary["schema_version"] == 4
        assert boundary["kind"] == "STATISTICAL_STATE"
        assert state_identity(stored.state) == row["state_hash"]
        assert read_state(stored.artifact.content, expected_hash=row["state_hash"]) == stored.state
        assert hashlib.sha256(stored.artifact.content).hexdigest() == stored.artifact.sha256
        by_symbol[stored.state.entity.symbol] = stored.state
    assert set(by_symbol) == {"GENEONE", "GENETWO"}
    assert by_symbol["GENEONE"].projects[0].mutation.affected_cases.value == 20
    assert by_symbol["GENETWO"].projects[0].mutation.affected_cases.value == 5
    for state in by_symbol.values():
        project = state.projects[0]
        assert project.mutation.ssm_coverage_cases.value == 95
        assert len(project.expression.values) == 100
        assert project.expression.median.value > 0


def test_demo_wide_admission_promotes_within_the_bound(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    candidates = repository.list_table("candidates", run_id)
    assert len(candidates) == 2
    assert all(candidate["summary"]["policy_version"] == "wide-policy-v2"
               for candidate in candidates)
    assert sorted(candidate["promotion_slot"] for candidate in candidates) == [1, 2]
    assert sorted(candidate["status"] for candidate in candidates) == ["DOSSIER_READY", "WIDE_EVALUATED"]
    evaluations = repository.page_child("jev_evaluations", run_id, 50, None,
                                        {"purpose": "WIDE"})["items"]
    assert len(evaluations) == 2
    assert {row["vector"]["resolved_model"] for row in evaluations} == {"jev-1.13.0"}
    assert {row["vector"]["question_set_version"] for row in evaluations} == {"wide-v3"}
    assert all(row["vector"]["cache_source_evaluation_id"] is None for row in evaluations)


def test_demo_evidence_revisions_are_immutable_and_judged_once(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    chain = read_revision_chain(repository, artifacts, candidate["candidate_id"])
    assert [stored.iteration for stored in chain] == [0, 1]
    assert chain[0].parent_id is None
    assert chain[1].parent_id == chain[0].evidence_state_id
    assert chain[1].evidence.action.action_id == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert chain[1].evidence.summary.total == 5
    assert chain[1].evidence.summary.verified == 5
    assert chain[1].evidence.accepted_state_hash == repository.get_state(
        candidate["source_state_id"])["state_hash"]
    executions = repository.followup_executions_for(candidate["candidate_id"])
    assert [(row["action_id"], row["status"]) for row in executions] == [
        ("CHECK_EVIDENCE_INTEGRITY_V1", "COMPLETED")]
    deep_evaluations = repository.page_child("jev_evaluations", run_id, 50, None,
                                             {"purpose": "DEEP"})["items"]
    assert len(deep_evaluations) == 1
    assert deep_evaluations[0]["vector"]["question_set_version"] == "deep-v1"
    assert deep_evaluations[0]["vector"]["evidence_state_id"] == chain[1].evidence_state_id


def test_demo_hypotheses_are_generated_labelled_and_judged_once(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    rows = repository.page_child("hypotheses", run_id, 50, None, {})["items"]
    assert len(rows) == 2
    assert all(row["hypothesis"]["generator"] == "deterministic-template-v1" for row in rows)
    assert all(row["hypothesis"]["label"] == "GENERATED HYPOTHESIS — NOT EVIDENCE" for row in rows)
    evaluations = repository.page_child("jev_evaluations", run_id, 50, None,
                                        {"purpose": "HYPOTHESIS"})["items"]
    assert len(evaluations) == 2
    assert {row["input_ref_id"] for row in evaluations} == {row["hypothesis_id"] for row in rows}
    assert {row["vector"]["question_set_version"] for row in evaluations} == {"hypothesis-v2"}
    for row in rows:
        stored = read_hypothesis_record(
            repository, artifacts, row["hypothesis_id"],
            candidate_id=row["candidate_id"], allowed_action_ids=frozenset(ACTION_REGISTRY))
        assert stored.draft.statement == row["hypothesis"]["statement"]


def test_demo_dossier_declares_itself_a_synthetic_demonstration(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    dossier_row = repository.list_table("dossiers", run_id)[0]
    artifact = read_dossier_record(repository, artifacts, dossier_row["dossier_id"])
    dossier = json.loads(artifact.content)
    assert dossier["schema_version"] == 2
    assert dossier["mode"] == "FIXTURE"
    assert dossier["warning"].startswith("SYNTHETIC DEMONSTRATION")
    assert "NO REAL GDC DATA WAS ANALYZED" in dossier["warning"]
    assert "NO REAL JEV CALL WAS MADE" in dossier["warning"]
    assert "NO REAL LLM CALL WAS MADE" in dossier["warning"]
    assert dossier["sections"]["research_only_notice"]["narrative"] == dossier["warning"]
    assert dossier["sections"]["deterministic_deep_evidence"]["availability"] == "OBSERVED"
    assert dossier["sections"]["hypothesis_jev_reviews"]["availability"] == "OBSERVED"
    assert dossier["sections"]["llm_provider_model_metadata"]["availability"] == "NOT_ACQUIRED"
    assert dossier["next_moves"] == [{"move": "COMPLETE", "reason_code": "INVESTIGATION_COMPLETE"}]
    assert set(dossier["evidence_state_ids"]) == {
        stored.evidence_state_id
        for stored in read_revision_chain(repository, artifacts, dossier_row["candidate_id"])}
    assert dossier["hypothesis_ids"] == [row["hypothesis_id"]
                                         for row in repository.page_child(
                                             "hypotheses", run_id, 50, None, {})["items"]]


def test_demo_replay_keeps_scientific_identity_and_isolates_operational_ids(runtime):
    _, repository, artifacts = runtime
    first = _demo(runtime)
    second = _demo(runtime)
    assert first != second

    first_states = {row["summary"]["entity"]["gene_id"]: row for row in _states(repository, first)}
    second_states = {row["summary"]["entity"]["gene_id"]: row for row in _states(repository, second)}
    assert {key: row["state_hash"] for key, row in first_states.items()} == \
        {key: row["state_hash"] for key, row in second_states.items()}
    for key in first_states:
        assert first_states[key]["state_id"] != second_states[key]["state_id"]
        assert first_states[key]["artifact_id"] != second_states[key]["artifact_id"]

    def revision_science(chain):
        return [
            (stored.iteration,
             stored.evidence.action.action_id if stored.evidence.action else None,
             stored.evidence.accepted_state_hash,
             tuple((check.check_id, check.outcome.value) for check in stored.evidence.checks))
            for stored in chain
        ]

    candidate_by_run = {
        run_id: next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
        for run_id in (first, second)
    }
    first_chain = read_revision_chain(repository, artifacts, candidate_by_run[first]["candidate_id"])
    second_chain = read_revision_chain(repository, artifacts, candidate_by_run[second]["candidate_id"])
    assert revision_science(first_chain) == revision_science(second_chain)
    assert [stored.evidence_state_id for stored in first_chain] != \
        [stored.evidence_state_id for stored in second_chain]

    first_hypotheses = [row["hypothesis"]["statement"] for row in repository.page_child(
        "hypotheses", first, 50, None, {})["items"]]
    second_hypotheses = [row["hypothesis"]["statement"] for row in repository.page_child(
        "hypotheses", second, 50, None, {})["items"]]
    assert first_hypotheses == second_hypotheses


def test_demo_evidence_revision_identity_is_reproducible(runtime):
    _, repository, _ = runtime
    first = _demo(runtime)
    second = _demo(runtime)
    first_candidate = next(row for row in repository.list_table("candidates", first)
                           if row["entity"]["gene_symbol"] == "GENEONE")
    second_candidate = next(row for row in repository.list_table("candidates", second)
                            if row["entity"]["gene_symbol"] == "GENEONE")
    first_hashes = [row["evidence_hash"]
                    for row in repository.evidence_revisions(first_candidate["candidate_id"])]
    second_hashes = [row["evidence_hash"]
                     for row in repository.evidence_revisions(second_candidate["candidate_id"])]
    assert first_hashes == second_hashes


def test_fixture_adapter_covers_every_current_question_set_offline():
    assert "SYNTHETIC" in FIXTURE_NOTICE
    adapter = FixtureJevAdapter(model="fixture-model")
    wide = adapter.evaluate({"projection_version": "jev-state-projection-v3",
                             "cohort": {"coverage_imbalance": False}}, ())
    deep = adapter.evaluate({"projection_version": "jev-evidence-projection-v2"}, ())
    hypothesis = adapter.evaluate({"projection_version": "jev-hypothesis-projection-v2"}, ())
    assert set(wide.answers) == {question.question_id for question in WIDE_QUESTIONS}
    assert set(deep.answers) == {question.question_id for question in DEEP_QUESTIONS}
    assert set(hypothesis.answers) == {question.question_id for question in HYPOTHESIS_QUESTIONS}
    assert wide.resolved_model == "fixture-model"
    assert adapter.calls == 3
    assert adapter.last_projection["projection_version"] == "jev-hypothesis-projection-v2"