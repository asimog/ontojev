from __future__ import annotations

import json

from cancerjev.research.orchestrator import DemoOrchestrator


def test_complete_fake_orchestration(runtime):
    settings, repository, artifacts = runtime
    emitted = []
    run_id = DemoOrchestrator(settings, repository, artifacts, emitted.append).run()
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
    baseline = json.loads(artifacts.read(baseline_meta["relative_path"], baseline_meta["sha256"]))
    revised = json.loads(artifacts.read(revised_meta["relative_path"], revised_meta["sha256"]))
    assert baseline["deterministic_observations"][0]["effect"]["value"] == 0.88
    assert revised["previous_evidence_state_id"] == baseline["evidence_state_id"]
    assert revised["deterministic_observations"][0]["effect"]["value"] == 0.61

    dossier = repository.list_table("dossiers", run_id)[0]
    dossier_meta = repository.artifact(dossier["json_artifact_id"])
    dossier_json = json.loads(artifacts.read(dossier_meta["relative_path"], dossier_meta["sha256"]))
    assert len(dossier_json["sections"]) == 25
    assert "NO REAL GDC DATA" in dossier_json["warning"]

