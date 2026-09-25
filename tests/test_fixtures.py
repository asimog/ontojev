"""Offline fixture demonstration: the shared engine end-to-end with no network.

``DemoOrchestrator`` substitutes only the transport (``FixtureTransport``) and the Jev
adapter (``FixtureJevAdapter``); the strict parsers, deterministic methods, schema-4
typed states, wide admission, registered actions, deep policy, hypothesis stage and
dossier path are the production code paths. Conftest blocks sockets, so a fixture run
that touched the network fails rather than passing.

The canonical demonstration is built once per module and each test reads a private
copy of its data directory, so a read-only assertion never pays for a full run.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from cancerjev.config import Settings
from cancerjev.domain.codecs import read_state, state_identity
from cancerjev.domain.dossier import DOSSIER_SECTIONS
from cancerjev.domain.events import REGISTERED_EVENT_TYPES
from cancerjev.domain.states import STAGES
from cancerjev.jev.questions import DEEP_QUESTIONS, HYPOTHESIS_QUESTIONS, WIDE_QUESTIONS
from cancerjev.research.dossier import SYNTHETIC_NOTICE
from cancerjev.research.fixtures import (
    FIXTURE_ID,
    FIXTURE_NOTICE,
    FIXTURE_VERSION,
    FixtureJevAdapter,
)
from cancerjev.research.hypotheses import LIVE_HYPOTHESIS_LABEL
from cancerjev.research.orchestrator import DEMO_DEEP_SELECTION, DemoOrchestrator
from cancerjev.research.specs import RESEARCH_SPEC_SCHEMA_VERSION
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.readers import (
    read_dossier_record,
    read_hypothesis_record,
    read_revision_chain,
    read_state_record,
)
from cancerjev.storage.repositories import Repository


@pytest.fixture(scope="module")
def _canned_demo(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("demo-canned")
    settings = Settings(data_dir, 0, 60, "http://localhost:3000")
    database = Database(settings.database_path)
    database.bootstrap()
    repository = Repository(database)
    run_id = DemoOrchestrator(settings, repository, ArtifactStore(data_dir),
                              lambda event: None).run()
    with database.connect(write=True) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return data_dir, run_id


@pytest.fixture
def runtime(tmp_path, _canned_demo):
    data_dir = tmp_path / "data"
    shutil.copytree(_canned_demo[0], data_dir)
    settings = Settings(data_dir, 0, 60, "http://localhost:3000")
    return settings, Repository(Database(settings.database_path)), ArtifactStore(data_dir)


def _demo(runtime):
    return runtime[1].list_runs()[0]["run_id"]


def _fresh_demo(runtime):
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
    assert run["outcome_reason"] == "BOUNDED_SWEEP_COMPLETE"
    assert run["worker_id"] == "demo-worker"
    assert run["selected_project_ids"] == ["TCGA-LUAD"]
    assert run["coverage"] == "COMPLETE_FOR_SCOPE"
    assert [row["run_id"] for row in repository.list_runs()] == [run_id]
    counts = run["counts"]
    assert counts["states_generated"] == counts["states_valid"] == 2
    assert counts["states_evaluated"] == 2
    assert counts["states_selected"] == 0
    assert counts["candidates_promoted"] == 2
    assert counts["hypotheses_created"] == 2
    assert counts["evidence_revisions"] == 2
    assert counts["dossiers_created"] == 1
    assert counts["followups_started"] == counts["followups_completed"] == 1
    assert counts["followups_failed"] == counts["candidates_failed"] == 0
    assert counts["jev_evaluations"] == 5
    usage = run["provider_usage"]
    assert usage["gdc_requests"] == usage["gdc_bytes"] == usage["gdc_cache_hits"] == 0, \
        "fixture responses never leave the process"
    assert usage["jev_calls"] == 5
    assert usage["llm_calls"] == 0
    assert usage["jev_cost"] is None and usage["llm_cost"] is None


def test_demo_run_event_stream_and_caps_are_canonical(runtime):
    _, repository, _ = runtime
    run_id = _demo(runtime)
    events = repository.events(run_id, 0, 1000)["items"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["run_id"] == run_id for event in events)
    assert {event["type"] for event in events} <= REGISTERED_EVENT_TYPES
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_COMPLETED"
    assert repository.get_run(run_id)["last_sequence"] == len(events)

    started = events[0]["data"]
    assert started["mode"] == "FIXTURE"
    assert started["deep_selection"] == DEMO_DEEP_SELECTION == "slot:1"
    assert started["deep_followup_authorized"] is True
    assert started["deep_hypotheses_requested"] is True
    assert started["research_spec"]["schema_version"] == RESEARCH_SPEC_SCHEMA_VERSION
    assert started["research_spec"]["spec_id"] == "LUAD_RESEARCH_V1"
    assert started["caps"] == {
        "max_requests": 150,
        "max_bytes": 64 * 1024 * 1024,
        "per_response_bytes": 5 * 1024 * 1024,
        "max_case_ids": 250,
        "max_gene_ids": 100,
        "timeout_seconds": 30.0,
        "cache_enabled": runtime[0].gdc_cache_enabled,
        "jev_max_states": runtime[0].jev_max_states,
    }

    completed_stages = {event["stage"] for event in events if event["type"] == "STAGE_COMPLETED"}
    assert {
        "INVENTORY", "GDC_FAST_SEARCH", "STATE_GENERATION", "JEV_WIDE", "DEEP_ANALYSIS",
        "FOLLOWUP", "JEV_DEEP", "HYPOTHESIS_GENERATION", "DOSSIER",
    } <= completed_stages
    assert completed_stages <= set(STAGES)


def test_demo_states_are_typed_immutable_and_recomputable(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    states = _states(repository, run_id)
    assert len(states) == 2
    by_symbol = {}
    for row in states:
        stored = read_state_record(repository, artifacts, row["state_id"])
        boundary = json.loads(stored.artifact.content)
        assert boundary["schema_version"] == 5
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
    _, repository, _ = runtime
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
    assert {(row["purpose"], row["input_ref_kind"]) for row in repository.list_table(
        "jev_evaluations", run_id)} == {
        ("WIDE", "STATISTICAL_STATE"), ("DEEP", "EVIDENCE_STATE"),
        ("HYPOTHESIS", "HYPOTHESIS"),
    }
    assert all(row["input_ref_id"] for row in repository.list_table("jev_evaluations", run_id))


def test_demo_evidence_revisions_are_immutable_and_judged_once(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    assert candidate["promotion_slot"] == 1
    assert candidate["status"] == "DOSSIER_READY"
    assert candidate["latest_evidence_state_id"] is not None
    assert candidate["dossier_id"] is not None

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

    baseline = json.loads(chain[0].artifact.content)
    assert baseline["kind"] == "EVIDENCE_STATE" and baseline["schema_version"] == 4
    assert baseline["revision_index"] == 0 and baseline["action"] is None
    assert baseline["source_state"]["state_identity_hash"] == baseline["accepted_state_hash"]
    revised = json.loads(chain[1].artifact.content)
    assert revised["revision_index"] == 1
    assert revised["parent_evidence_hash"] == baseline["evidence_hash"]
    assert revised["checks"] and all(check["input_hashes"] for check in revised["checks"])


def test_demo_hypotheses_are_generated_labelled_and_judged_once(runtime):
    _, repository, artifacts = runtime
    run_id = _demo(runtime)
    rows = repository.page_child("hypotheses", run_id, 50, None, {})["items"]
    assert len(rows) == 2
    assert all(row["hypothesis"]["generator"] == "deterministic-template-v1" for row in rows)
    assert all(row["hypothesis"]["label"] == LIVE_HYPOTHESIS_LABEL for row in rows)
    assert all("NOT EVIDENCE" in row["hypothesis"]["label"] for row in rows)
    assert all(row["hypothesis"]["generator_model"] is None for row in rows)
    assert all(row["hypothesis"]["factual_observation_refs"] == [] for row in rows)
    assert all(row["hypothesis"]["statement"].strip() and row["hypothesis"]["predictions"]
               and row["hypothesis"]["contradicted_if"] for row in rows)
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
    assert dossier["warning"] == SYNTHETIC_NOTICE
    assert dossier["warning"].startswith("SYNTHETIC DEMONSTRATION")
    assert "NO REAL GDC DATA WAS ANALYZED" in dossier["warning"]
    assert "NO REAL JEV CALL WAS MADE" in dossier["warning"]
    assert "NO REAL LLM CALL WAS MADE" in dossier["warning"]
    assert dossier["sections"]["research_only_notice"]["narrative"] == dossier["warning"]
    assert set(dossier["sections"]) == set(DOSSIER_SECTIONS)
    assert dossier["sections"]["deterministic_deep_evidence"]["availability"] == "OBSERVED"
    assert dossier["sections"]["hypothesis_jev_reviews"]["availability"] == "OBSERVED"
    assert dossier["sections"]["llm_provider_model_metadata"]["availability"] == "NOT_ACQUIRED"
    assert dossier["next_moves"] == [{"move": "COMPLETE", "reason_code": "INVESTIGATION_COMPLETE"}]
    assert dossier["candidate_id"] == dossier_row["candidate_id"]
    assert set(dossier["evidence_state_ids"]) == {
        stored.evidence_state_id
        for stored in read_revision_chain(repository, artifacts, dossier_row["candidate_id"])}
    assert dossier["hypothesis_ids"] == [row["hypothesis_id"]
                                         for row in repository.page_child(
                                             "hypotheses", run_id, 50, None, {})["items"]]

    markdown_meta = repository.artifact(dossier_row["markdown_artifact_id"])
    markdown = artifacts.read(markdown_meta["relative_path"], markdown_meta["sha256"]).decode()
    assert dossier["warning"] in markdown


def test_demo_replay_keeps_scientific_identity_and_isolates_operational_ids(runtime):
    _, repository, artifacts = runtime
    first = _demo(runtime)
    second = _fresh_demo(runtime)
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
    assert [stored.record.evidence_hash for stored in first_chain] == \
        [stored.record.evidence_hash for stored in second_chain], "evidence identity is reproducible"
    assert [stored.evidence_state_id for stored in first_chain] != \
        [stored.evidence_state_id for stored in second_chain]

    first_hypotheses = [row["hypothesis"]["statement"] for row in repository.page_child(
        "hypotheses", first, 50, None, {})["items"]]
    second_hypotheses = [row["hypothesis"]["statement"] for row in repository.page_child(
        "hypotheses", second, 50, None, {})["items"]]
    assert first_hypotheses == second_hypotheses


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
