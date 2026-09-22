from __future__ import annotations

import hashlib
import json

from cancerjev.config import Settings
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


def test_complete_fake_orchestration(runtime):
    settings, repository, artifacts = runtime
    emitted = []
    orchestrator = DemoOrchestrator(settings, repository, artifacts, emitted.append)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["counts"]["states_generated"] == 12
    assert run["counts"]["states_evaluated"] == 12
    assert run["counts"]["candidates_promoted"] == 2
    assert run["counts"]["hypotheses_created"] == 2
    assert run["provider_usage"]["gdc_requests"] == 0
    assert run["provider_usage"]["gdc_bytes"] == 0
    assert run["provider_usage"]["jev_calls"] == 0
    assert run["provider_usage"]["llm_calls"] == 0
    assert run["provider_usage"]["jev_cost"] is None
    assert run["provider_usage"]["llm_cost"] is None
    assert [event["sequence"] for event in emitted] == list(range(1, len(emitted) + 1))
    stages = {event["stage"] for event in emitted if event["type"] == "STAGE_COMPLETED"}
    assert {"INVENTORY", "GDC_FAST_SEARCH", "STATE_GENERATION", "JEV_WIDE", "DEEP_ANALYSIS", "EVIDENCE_BUILD", "JEV_DEEP", "HYPOTHESIS_GENERATION", "HYPOTHESIS_VERIFICATION", "FOLLOWUP", "DOSSIER"} <= stages

    candidates = repository.list_table("candidates", run_id)
    assert {candidate["status"] for candidate in candidates} == {"DOSSIER_READY", "DEFERRED"}
    hypotheses = repository.list_table("hypotheses", run_id)
    assert len(hypotheses) == 2
    assert all(item["hypothesis"]["label"] == "GENERATED FIXTURE HYPOTHESIS" for item in hypotheses)
    followups = repository.list_table("followup_executions", run_id)
    assert len(followups) == 1

    with repository.database.read() as connection:
        evidence_rows = connection.execute("SELECT * FROM evidence_states ORDER BY iteration").fetchall()
    assert len(evidence_rows) == 2
    baseline_meta = repository.artifact(evidence_rows[0]["artifact_id"])
    revised_meta = repository.artifact(evidence_rows[1]["artifact_id"])
    baseline_bytes = artifacts.read(baseline_meta["relative_path"], baseline_meta["sha256"])
    baseline = json.loads(baseline_bytes)
    revised = json.loads(artifacts.read(revised_meta["relative_path"], revised_meta["sha256"]))
    assert baseline["deterministic_observations"][0]["effect"]["value"] == 0.88
    assert revised["previous_evidence_state_id"] == baseline["evidence_state_id"]
    assert revised["deterministic_observations"][0]["effect"]["value"] == 0.61
    assert hashlib.sha256(baseline_bytes).hexdigest() == baseline_meta["sha256"]

    with repository.database.read() as connection:
        kinds = {(row["purpose"], row["input_ref_kind"]) for row in connection.execute("SELECT purpose, input_ref_kind FROM jev_evaluations")}
    assert kinds == {("WIDE", "STATISTICAL_STATE"), ("DEEP", "EVIDENCE_STATE"), ("HYPOTHESIS", "HYPOTHESIS")}

    dossier = repository.list_table("dossiers", run_id)[0]
    dossier_meta = repository.artifact(dossier["json_artifact_id"])
    dossier_json = json.loads(artifacts.read(dossier_meta["relative_path"], dossier_meta["sha256"]))
    assert len(dossier_json["sections"]) == 25
    assert "NO REAL GDC DATA" in dossier_json["warning"]

    with repository.database.read() as connection:
        owner = connection.execute("SELECT owner_id FROM worker_status").fetchone()[0]
    assert owner == orchestrator.worker_id == run["worker_id"]
    assert owner != run_id


def test_scientific_hashes_are_stable_across_runs(tmp_path):
    def execute(name: str) -> tuple[str, list[str], list[str]]:
        data_dir = tmp_path / name
        settings = Settings(data_dir, 0, 60, "http://localhost:3000")
        database = Database(settings.database_path)
        database.bootstrap()
        repository = Repository(database)
        run_id = DemoOrchestrator(settings, repository, ArtifactStore(data_dir), lambda event: None).run()
        with database.read() as connection:
            states = [row[0] for row in connection.execute("SELECT state_hash FROM statistical_states ORDER BY json_extract(summary_json,'$.entity.gene_symbol')")]
            evidence = [row[0] for row in connection.execute("SELECT evidence_hash FROM evidence_states ORDER BY iteration")]
        return run_id, states, evidence

    first_id, first_states, first_evidence = execute("first")
    second_id, second_states, second_evidence = execute("second")
    assert first_id != second_id
    assert len(first_states) == 12
    assert first_states == second_states
    assert first_evidence == second_evidence


def test_worker_owner_identity_is_stable_across_runs(runtime):
    settings, repository, artifacts = runtime
    orchestrator = DemoOrchestrator(settings, repository, artifacts, lambda event: None)
    first = orchestrator.run()
    second = orchestrator.run()
    with repository.database.read() as connection:
        owner = connection.execute("SELECT owner_id FROM worker_status").fetchone()[0]
    assert owner == orchestrator.worker_id
    assert owner not in {first, second}
    assert repository.get_run(first)["worker_id"] == owner
    assert repository.get_run(second)["worker_id"] == owner

