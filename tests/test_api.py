from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.serializers import PRESENTATION_SCHEMA_VERSION, response_etag
from cancerjev.research.dossier import SYNTHETIC_NOTICE
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.database import SCHEMA_VERSION


def _client(settings, monkeypatch) -> TestClient:
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return TestClient(create_app(), raise_server_exceptions=False)


def _run_demo(settings, repository, artifacts) -> str:
    return DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()


def test_health_and_system_report_the_current_configuration(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    _run_demo(settings, repository, artifacts)
    repository.heartbeat("api-test-worker")
    client = _client(settings, monkeypatch)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "schema_version": SCHEMA_VERSION}
    assert health.headers["cache-control"] == "no-store"

    system = client.get("/api/system").json()
    assert system["data"]["directory"] == settings.data_dir.name
    assert system["data"]["artifact_files"] > 0
    assert system["providers"] == {"gdc": True, "jev": False, "llm": False}
    assert system["versions"]["api"] == "3.0.0"
    assert system["versions"]["schema"] == SCHEMA_VERSION
    assert system["versions"]["worker"] == "0.1.0"
    assert system["worker"]["owner_id"] == "api-test-worker"
    assert system["worker"]["fresh"] is None
    assert system["active_run_id"] is None
    assert system["budget_defaults"]["gdc_requests"] == 150
    assert system["budget_defaults"]["per_response_bytes"] == 5 * 1024 * 1024
    assert system["budget_defaults"]["gdc_bytes"] == 64 * 1024 * 1024
    assert system["budget_defaults"]["max_case_ids"] == 250
    assert system["budget_defaults"]["max_gene_ids"] == 100
    assert system["cursor"]["present"] is False
    assert system["cache"]["entries"] == 0
    assert system["cache"]["bytes"] == 0
    assert system["cache"]["jev_entries"] == 5


def test_runs_list_detail_and_event_pagination(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    pending_id = repository.create_run("pagination-worker")
    client = _client(settings, monkeypatch)

    first_page = client.get("/api/runs?limit=1").json()
    assert first_page["items"][0]["run_id"] == pending_id
    assert first_page["has_more"] is True
    assert first_page["next_cursor"]
    second_page = client.get(f"/api/runs?limit=1&cursor={first_page['next_cursor']}").json()
    assert second_page["items"][0]["run_id"] == run_id
    assert second_page["has_more"] is False

    run = repository.get_run(run_id)
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["run_id"] == run_id
    assert detail["status"] == "COMPLETED"
    assert detail["mode"] == "FIXTURE"
    assert len(detail["candidates"]) == 2
    assert detail["counts"]["states_generated"] == 2

    first = client.get(f"/api/runs/{run_id}/events?after_sequence=0&limit=5").json()
    assert len(first["items"]) == 5
    assert first["items"][0]["sequence"] == 1
    assert first["has_more"] is True
    second = client.get(
        f"/api/runs/{run_id}/events?after_sequence={first['next_after_sequence']}&limit=500"
    ).json()
    assert second["items"][0]["sequence"] == 6
    assert second["has_more"] is False
    assert second["run_last_sequence"] == run["last_sequence"]
    assert len(second["items"]) + 5 == run["last_sequence"]


def test_child_lists_are_filtered_and_cursor_mismatch_is_rejected(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    client = _client(settings, monkeypatch)

    states = client.get(f"/api/runs/{run_id}/states?disposition=GENERATED").json()
    assert len(states["items"]) == 2
    assert all(row["disposition"] == "GENERATED" for row in states["items"])
    assert all(row["artifact_id"] for row in states["items"])

    paged = client.get(f"/api/runs/{run_id}/states?limit=1").json()
    assert paged["has_more"] is True and paged["next_cursor"]
    mismatch = client.get(
        f"/api/runs/{run_id}/states?disposition=GENERATED&cursor={paged['next_cursor']}"
    )
    assert mismatch.status_code == 422

    candidates = client.get(f"/api/runs/{run_id}/candidates").json()["items"]
    assert len(candidates) == 2
    assert {candidate["status"] for candidate in candidates} == {"DOSSIER_READY", "WIDE_EVALUATED"}
    ready = next(candidate for candidate in candidates if candidate["status"] == "DOSSIER_READY")
    assert ready["promotion_slot"] == 1
    assert ready["latest_evidence_state_id"]

    evidence = client.get(f"/api/runs/{run_id}/evidence").json()
    assert [row["iteration"] for row in evidence["items"]] == [0, 1]
    assert evidence["items"][1]["previous_evidence_state_id"] == evidence["items"][0]["evidence_state_id"]

    evaluations = client.get(f"/api/runs/{run_id}/evaluations?purpose=WIDE").json()
    assert len(evaluations["items"]) == 2
    assert all(row["purpose"] == "WIDE" for row in evaluations["items"])
    assert all(row["input_ref_kind"] == "STATISTICAL_STATE" for row in evaluations["items"])
    assert all("state_id" not in row for row in evaluations["items"])

    hypotheses = client.get(f"/api/runs/{run_id}/hypotheses").json()
    assert len(hypotheses["items"]) == 2
    filtered = client.get(
        f"/api/runs/{run_id}/hypotheses?candidate_id={ready['candidate_id']}"
    ).json()
    assert len(filtered["items"]) == 2
    assert all(row["candidate_id"] == ready["candidate_id"] for row in filtered["items"])


def test_typed_state_and_evidence_presentations(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    client = _client(settings, monkeypatch)

    states = client.get(f"/api/runs/{run_id}/states").json()["items"]
    row = states[0]
    response = client.get(f"/api/states/{row['state_id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "STATISTICAL_STATE_PRESENTATION"
    assert payload["schema_version"] == PRESENTATION_SCHEMA_VERSION == 4
    assert payload["state_id"] == row["state_id"]
    assert payload["state_hash"] == row["state_hash"]
    assert payload["entity"]["gene_id"]
    assert payload["quality"]["acquisition"] and payload["quality"]["sufficiency"]
    assert payload["tested_context"]["selection_bias"]
    assert payload["sources"] and all(source["response_hash"] for source in payload["sources"])
    metadata = repository.artifact(row["artifact_id"])
    assert response.headers["x-artifact-id"] == metadata["artifact_id"]
    assert response.headers["x-artifact-sha256"] == metadata["sha256"]
    assert response.headers["etag"] == f'"{response_etag(payload)}"'
    assert response.headers["etag"] != f'"{metadata["sha256"]}"'

    evidence = client.get(f"/api/runs/{run_id}/evidence").json()["items"]
    revised = evidence[1]
    response = client.get(f"/api/evidence/{revised['evidence_state_id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "EVIDENCE_STATE_PRESENTATION"
    assert payload["schema_version"] == PRESENTATION_SCHEMA_VERSION
    assert payload["evidence_state_id"] == revised["evidence_state_id"]
    assert payload["evidence_hash"] == revised["evidence_hash"]
    assert payload["iteration_number"] == 1
    assert payload["parent_evidence_hash"] == evidence[0]["evidence_hash"]
    assert payload["action"]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert payload["action"]["version"] == "1"
    assert payload["action"]["title"]
    assert payload["action"]["unit"] == "checks"
    assert payload["research_puzzle"]["origin"] == "DETERMINISTIC_ACTION_REGISTRY"
    assert payload["deterministic_observations"]
    assert payload["quality_and_fragility"]["checks_total"] == 5
    assert payload["quality_and_fragility"]["checks_verified"] == 5
    assert payload["quality_and_fragility"]["checks_contradicted"] == 0
    assert payload["project_level_evidence"][0]["project_id"] == "TCGA-LUAD"
    assert payload["missing_evidence"]
    assert payload["provenance"]["gdc_release"]
    assert payload["provenance"]["response_source_count"] > 0
    metadata = repository.artifact(revised["artifact_id"])
    assert response.headers["x-artifact-id"] == metadata["artifact_id"]
    assert response.headers["x-artifact-sha256"] == metadata["sha256"]
    assert response.headers["etag"] == f'"{response_etag(payload)}"'


def test_hypotheses_dossiers_and_rankings(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    client = _client(settings, monkeypatch)

    hypotheses = client.get(f"/api/runs/{run_id}/hypotheses").json()["items"]
    assert len(hypotheses) == 2
    assert all("NOT EVIDENCE" in row["hypothesis"]["label"] for row in hypotheses)
    assert all(row["hypothesis"]["factual_observation_refs"] == [] for row in hypotheses)

    dossiers = client.get(f"/api/runs/{run_id}/dossiers").json()["items"]
    assert len(dossiers) == 1
    dossier_id = dossiers[0]["dossier_id"]
    json_response = client.get(f"/api/dossiers/{dossier_id}")
    assert json_response.status_code == 200
    document = json_response.json()
    assert document["warning"] == SYNTHETIC_NOTICE
    assert "SYNTHETIC DEMONSTRATION" in document["warning"]
    assert "NO REAL GDC DATA" in document["warning"]
    assert len(document["sections"]) == 25
    assert document["candidate_id"] == dossiers[0]["candidate_id"]
    metadata = repository.artifact(dossiers[0]["json_artifact_id"])
    assert json_response.headers["etag"] == f'"{metadata["sha256"]}"'
    assert json_response.headers["x-artifact-id"] == metadata["artifact_id"]

    markdown_response = client.get(f"/api/dossiers/{dossier_id}?format=markdown")
    assert markdown_response.status_code == 200
    assert "SYNTHETIC DEMONSTRATION" in markdown_response.text
    assert markdown_response.headers["etag"] != json_response.headers["etag"]
    markdown_metadata = repository.artifact(dossiers[0]["markdown_artifact_id"])
    assert markdown_response.headers["etag"] == f'"{markdown_metadata["sha256"]}"'

    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    assert rankings["baseline"]["kind"] == "BASELINE"
    assert rankings["baseline"]["entries"]
    assert rankings["jev"]["kind"] == "JEV"
    assert rankings["jev"]["entries"]
    assert rankings["jev"]["admission"]["decision"] in {"ADMIT", "ABSTAIN"}


def test_cors_exposes_artifact_identity_headers(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    client = _client(settings, monkeypatch)

    dossier_id = client.get(f"/api/runs/{run_id}/dossiers").json()["items"][0]["dossier_id"]
    response = client.get(f"/api/dossiers/{dossier_id}", headers={"Origin": settings.web_origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.web_origin
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "x-artifact-id" in exposed
    assert "x-artifact-sha256" in exposed
    assert "etag" in exposed


def test_corrupt_ranking_artifact_is_refused(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = repository.create_run("corrupt-ranking", mode="LIVE", fixture_id=None,
                                   fixture_version=None)
    artifact = artifacts.publish(f"runs/{run_id}/wide/jev_ranking.json", b'{"kind":"JEV"}',
                                 "application/json", "wide-ranking")
    repository.register_artifact(artifact, run_id)
    (settings.data_dir / artifact.relative_path).write_bytes(b"corrupt")
    client = _client(settings, monkeypatch)

    response = client.get(f"/api/runs/{run_id}/rankings")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "HTTP_503"
    assert "Traceback" not in response.text


def test_unknown_identifiers_are_not_found(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    client = _client(settings, monkeypatch)
    missing = "00000000-0000-0000-0000-000000000000"
    for path in (
        f"/api/runs/{missing}",
        f"/api/runs/{missing}/events",
        f"/api/runs/{missing}/candidates",
        f"/api/states/{missing}",
        f"/api/evidence/{missing}",
        f"/api/dossiers/{missing}",
    ):
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "HTTP_404"


def test_validation_errors_use_the_documented_envelope(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    run_id = _run_demo(settings, repository, artifacts)
    client = _client(settings, monkeypatch)
    for path in (
        "/api/runs/not-a-uuid",
        "/api/runs?limit=0",
        "/api/runs?cursor=bad",
        f"/api/runs/{run_id}/events?limit=0",
        f"/api/runs/{run_id}/events?after_sequence=-1",
        f"/api/runs/{run_id}/states?cursor=bad",
        f"/api/runs/{run_id}/evaluations?limit=0",
        f"/api/dossiers/{run_id}?format=pdf",
    ):
        response = client.get(path)
        assert response.status_code == 422, path
        payload = response.json()
        assert set(payload["error"]) == {"code", "message", "request_id"}
        assert payload["error"]["code"] in {"VALIDATION_ERROR", "HTTP_422"}
        assert "Traceback" not in response.text


def test_storage_unavailable_is_reported_as_503(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    client = _client(settings, monkeypatch)

    def broken():
        raise sqlite3.Error("storage gone")

    monkeypatch.setattr(client.app.state.repository.database, "read", broken)
    for path in ("/health", "/api/runs"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
        assert "Traceback" not in response.text
