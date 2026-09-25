from __future__ import annotations

import hashlib
import json

from cancerjev.config import Settings
from cancerjev.domain.dossier import DOSSIER_SECTIONS
from cancerjev.domain.events import REGISTERED_EVENT_TYPES
from cancerjev.domain.states import STAGES
from cancerjev.research.dossier import SYNTHETIC_NOTICE
from cancerjev.research.hypotheses import LIVE_HYPOTHESIS_LABEL
from cancerjev.research.orchestrator import DEMO_DEEP_SELECTION, DemoOrchestrator
from cancerjev.research.specs import RESEARCH_SPEC_SCHEMA_VERSION
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


def _demo(settings, repository, artifacts, emitted=None):
    render = emitted.append if emitted is not None else (lambda event: None)
    return DemoOrchestrator(settings, repository, artifacts, render).run()


def test_demo_run_is_one_completed_fixture_run(runtime):
    settings, repository, artifacts = runtime
    emitted: list[dict] = []
    run_id = _demo(settings, repository, artifacts, emitted)
    run = repository.get_run(run_id)

    assert run["status"] == "COMPLETED"
    assert run["mode"] == "FIXTURE"
    assert run["fixture_id"] == "demo"
    assert run["fixture_version"] == "demo-v1"
    assert run["outcome_reason"] == "BOUNDED_SWEEP_COMPLETE"
    assert run["coverage"] == "COMPLETE_FOR_SCOPE"
    assert run["worker_id"] == "demo-worker"
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
    assert usage["gdc_requests"] == usage["gdc_bytes"] == usage["gdc_cache_hits"] == 0
    assert usage["jev_calls"] == 5
    assert usage["llm_calls"] == 0
    assert usage["jev_cost"] is None and usage["llm_cost"] is None

    sequences = [event["sequence"] for event in emitted]
    assert sequences == list(range(1, len(emitted) + 1))
    assert run["last_sequence"] == len(emitted)
    assert all(event["run_id"] == run_id for event in emitted)
    assert {event["type"] for event in emitted} <= REGISTERED_EVENT_TYPES
    assert emitted[0]["type"] == "RUN_STARTED"
    assert emitted[-1]["type"] == "RUN_COMPLETED"

    started = emitted[0]["data"]
    assert started["mode"] == "FIXTURE"
    assert started["deep_selection"] == DEMO_DEEP_SELECTION == "slot:1"
    assert started["deep_followup_authorized"] is True
    assert started["deep_hypotheses_requested"] is True
    assert started["research_spec"]["schema_version"] == RESEARCH_SPEC_SCHEMA_VERSION
    assert started["research_spec"]["spec_id"] == "LUAD_RESEARCH_V1"
    caps = started["caps"]
    assert caps["max_requests"] == 150
    assert caps["max_bytes"] == 64 * 1024 * 1024
    assert caps["per_response_bytes"] == 5 * 1024 * 1024
    assert caps["max_case_ids"] == 250
    assert caps["max_gene_ids"] == 100
    assert caps["timeout_seconds"] == 30.0
    assert caps["jev_max_states"] == 1000

    completed_stages = {event["stage"] for event in emitted if event["type"] == "STAGE_COMPLETED"}
    assert {
        "INVENTORY", "GDC_FAST_SEARCH", "STATE_GENERATION", "JEV_WIDE", "DEEP_ANALYSIS",
        "FOLLOWUP", "JEV_DEEP", "HYPOTHESIS_GENERATION", "DOSSIER",
    } <= completed_stages
    assert completed_stages <= set(STAGES)


def test_demo_run_records_typed_candidates_and_evidence(runtime):
    settings, repository, artifacts = runtime
    run_id = _demo(settings, repository, artifacts)

    candidates = repository.list_table("candidates", run_id)
    assert len(candidates) == 2
    assert sorted(candidate["status"] for candidate in candidates) == ["DOSSIER_READY", "WIDE_EVALUATED"]
    ready = next(candidate for candidate in candidates if candidate["status"] == "DOSSIER_READY")
    assert ready["promotion_slot"] == 1
    assert ready["entity"]["gene_symbol"] == "GENEONE"
    assert ready["latest_evidence_state_id"] is not None
    assert ready["dossier_id"] is not None

    evidence = repository.list_table("evidence_states", run_id)
    assert [row["iteration"] for row in evidence] == [0, 1]
    assert {row["candidate_id"] for row in evidence} == {ready["candidate_id"]}
    assert evidence[0]["previous_evidence_state_id"] is None
    assert evidence[1]["previous_evidence_state_id"] == evidence[0]["evidence_state_id"]
    assert evidence[0]["summary"]["origin"] == "STATISTICAL_STATE_BASELINE"
    assert evidence[1]["summary"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert evidence[1]["summary"]["checks_verified"] == 5
    assert evidence[1]["summary"]["checks_contradicted"] == 0

    baseline_meta = repository.artifact(evidence[0]["artifact_id"])
    baseline_bytes = artifacts.read(baseline_meta["relative_path"], baseline_meta["sha256"])
    assert hashlib.sha256(baseline_bytes).hexdigest() == baseline_meta["sha256"]
    baseline = json.loads(baseline_bytes)
    assert baseline["kind"] == "EVIDENCE_STATE"
    assert baseline["schema_version"] == 4
    assert baseline["revision_index"] == 0 and baseline["action"] is None
    assert baseline["source_state"]["state_identity_hash"] == baseline["accepted_state_hash"]

    revised_meta = repository.artifact(evidence[1]["artifact_id"])
    revised = json.loads(artifacts.read(revised_meta["relative_path"], revised_meta["sha256"]))
    assert revised["revision_index"] == 1
    assert revised["parent_evidence_hash"] == baseline["evidence_hash"]
    assert revised["action"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert revised["checks"] and all(check["input_hashes"] for check in revised["checks"])


def test_demo_run_records_labelled_hypotheses_and_synthetic_dossier(runtime):
    settings, repository, artifacts = runtime
    run_id = _demo(settings, repository, artifacts)

    evidence = repository.list_table("evidence_states", run_id)
    hypotheses = repository.list_table("hypotheses", run_id)
    assert len(hypotheses) == 2
    for row in hypotheses:
        draft = row["hypothesis"]
        assert draft["label"] == LIVE_HYPOTHESIS_LABEL
        assert "NOT EVIDENCE" in draft["label"]
        assert draft["generator"] == "deterministic-template-v1"
        assert draft["generator_model"] is None
        assert draft["factual_observation_refs"] == []
        assert draft["evidence_state_id"] == evidence[1]["evidence_state_id"]
        assert draft["statement"].strip() and draft["predictions"] and draft["contradicted_if"]

    dossier = repository.list_table("dossiers", run_id)[0]
    meta = repository.artifact(dossier["json_artifact_id"])
    payload = json.loads(artifacts.read(meta["relative_path"], meta["sha256"]))
    assert set(payload["sections"]) == set(DOSSIER_SECTIONS)
    assert len(payload["sections"]) == 25
    assert payload["warning"] == SYNTHETIC_NOTICE
    assert "SYNTHETIC DEMONSTRATION" in payload["warning"]
    assert "NO REAL GDC DATA" in payload["warning"]
    assert payload["mode"] == "FIXTURE"
    assert payload["candidate_id"] == dossier["candidate_id"]
    assert payload["evidence_state_ids"] == [row["evidence_state_id"] for row in evidence]
    assert payload["next_moves"] == [{"move": "COMPLETE", "reason_code": "INVESTIGATION_COMPLETE"}]
    markdown_meta = repository.artifact(dossier["markdown_artifact_id"])
    markdown = artifacts.read(markdown_meta["relative_path"], markdown_meta["sha256"]).decode()
    assert payload["warning"] in markdown


def test_demo_run_evaluations_expose_explicit_input_references(runtime):
    settings, repository, artifacts = runtime
    run_id = _demo(settings, repository, artifacts)

    rows = repository.list_table("jev_evaluations", run_id)
    kinds = {(row["purpose"], row["input_ref_kind"]) for row in rows}
    assert kinds == {
        ("WIDE", "STATISTICAL_STATE"),
        ("DEEP", "EVIDENCE_STATE"),
        ("HYPOTHESIS", "HYPOTHESIS"),
    }
    assert all(row["input_ref_id"] for row in rows)
    assert all("state_id" not in row for row in rows)


def test_repeat_demo_runs_reproduce_scientific_identities(tmp_path):
    def execute(name: str) -> dict:
        data_dir = tmp_path / name
        settings = Settings(data_dir, 0, 60, "http://localhost:3000")
        database = Database(settings.database_path)
        database.bootstrap()
        repository = Repository(database)
        run_id = DemoOrchestrator(settings, repository, ArtifactStore(data_dir),
                                  lambda event: None).run()
        with database.read() as connection:
            states = [row[0] for row in connection.execute(
                "SELECT state_hash FROM statistical_states "
                "ORDER BY json_extract(summary_json,'$.entity.gene_symbol')"
            )]
            evidence = [row[0] for row in connection.execute(
                "SELECT evidence_hash FROM evidence_states ORDER BY iteration"
            )]
            state_ids = [row[0] for row in connection.execute(
                "SELECT state_id FROM statistical_states "
                "ORDER BY json_extract(summary_json,'$.entity.gene_symbol')"
            )]
            evidence_ids = [row[0] for row in connection.execute(
                "SELECT evidence_state_id FROM evidence_states ORDER BY iteration"
            )]
        return {
            "run_id": run_id,
            "states": states,
            "evidence": evidence,
            "state_ids": state_ids,
            "evidence_ids": evidence_ids,
            "statements": [row["hypothesis"]["statement"]
                           for row in repository.list_table("hypotheses", run_id)],
            "warnings": [row["summary"]["warning"]
                         for row in repository.list_table("dossiers", run_id)],
        }

    first = execute("first")
    second = execute("second")

    assert first["run_id"] != second["run_id"]
    assert first["state_ids"] != second["state_ids"]
    assert first["evidence_ids"] != second["evidence_ids"]
    assert len(first["states"]) == 2
    assert first["states"] == second["states"]
    assert first["statements"] == second["statements"]
    assert first["warnings"] == second["warnings"] == [SYNTHETIC_NOTICE]
    assert first["evidence"] == second["evidence"]


def test_each_demo_run_is_an_independent_run(runtime):
    settings, repository, artifacts = runtime
    first = _demo(settings, repository, artifacts)
    second = _demo(settings, repository, artifacts)
    assert first != second

    runs = {row["run_id"]: row for row in repository.list_runs()}
    assert set(runs) == {first, second}
    for run_id in (first, second):
        assert runs[run_id]["status"] == "COMPLETED"
        assert runs[run_id]["mode"] == "FIXTURE"
        assert runs[run_id]["worker_id"] == "demo-worker"
        assert len(repository.list_table("candidates", run_id)) == 2
        assert len(repository.list_table("evidence_states", run_id)) == 2
