from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.research.orchestrator import DemoOrchestrator


def test_api_incremental_events_and_errors(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    pending_id = repository.create_run("pagination-test")
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok", "schema_version": 1}
    assert client.get("/api/system").json()["providers"] == {"gdc": False, "jev": False, "llm": False}
    first_page = client.get("/api/runs?limit=1").json()
    assert first_page["items"][0]["run_id"] == pending_id
    assert first_page["has_more"] is True and first_page["next_cursor"]
    next_page = client.get(f"/api/runs?limit=1&cursor={first_page['next_cursor']}").json()
    assert next_page["items"][0]["run_id"] == run_id
    assert client.get("/api/runs?cursor=bad").status_code == 422
    first = client.get(f"/api/runs/{run_id}/events?after_sequence=0&limit=5").json()
    assert len(first["items"]) == 5 and first["has_more"] is True
    second = client.get(f"/api/runs/{run_id}/events?after_sequence={first['next_after_sequence']}&limit=500").json()
    assert second["items"][0]["sequence"] == 6
    assert second["run_last_sequence"] == 71
    assert client.get(f"/api/runs/{run_id}/dossiers").json()["items"]
    assert client.get("/api/runs/not-a-uuid").status_code == 422
    assert client.get("/api/runs/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get(f"/api/runs/{run_id}/events?limit=0").status_code == 422

    dossier = client.get(f"/api/runs/{run_id}/dossiers").json()["items"][0]
    response = client.get(f"/api/dossiers/{dossier['dossier_id']}")
    assert response.status_code == 200
    assert "SYNTHETIC DEMONSTRATION" in response.json()["warning"]
    assert response.headers["etag"] == f'"{response.headers["x-artifact-sha256"]}"'
    assert len(response.headers["x-artifact-sha256"]) == 64
    markdown = client.get(f"/api/dossiers/{dossier['dossier_id']}?format=markdown")
    assert markdown.status_code == 200 and "SYNTHETIC DEMONSTRATION" in markdown.text
    assert markdown.headers["etag"] != response.headers["etag"]


def test_system_reports_phase1_configuration(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    client = TestClient(create_app())
    system = client.get("/api/system").json()
    assert system["data"]["directory"] == settings.data_dir.name
    assert system["data"]["artifact_files"] > 0
    assert system["versions"] == {"api": "1.0.0", "schema": 1, "worker": "0.1.0"}
    assert system["budget_defaults"]["gdc_requests"] is None
    assert system["cursor"]["present"] is False
    assert system["cache"] == {"entries": 0, "reason": "The GDC cache is Phase 2."}
    assert system["worker"]["fresh"] is None


def test_child_lists_are_paginated_and_filtered(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    client = TestClient(create_app())
    first = client.get(f"/api/runs/{run_id}/states?limit=5").json()
    assert len(first["items"]) == 5 and first["has_more"] is True and first["next_cursor"]
    second = client.get(f"/api/runs/{run_id}/states?limit=5&cursor={first['next_cursor']}").json()
    seen = {item["state_id"] for item in first["items"]} | {item["state_id"] for item in second["items"]}
    assert len(seen) == 10
    promoted = client.get(f"/api/runs/{run_id}/states?disposition=PROMOTED").json()
    assert len(promoted["items"]) == 2
    assert client.get(f"/api/runs/{run_id}/states?disposition=PROMOTED&cursor={first['next_cursor']}").status_code == 422
    assert client.get(f"/api/runs/{run_id}/states?cursor=bad").status_code == 422
    evaluations = client.get(f"/api/runs/{run_id}/evaluations?purpose=WIDE&limit=4").json()
    assert len(evaluations["items"]) == 4 and all(item["purpose"] == "WIDE" for item in evaluations["items"])
    candidate_id = client.get(f"/api/runs/{run_id}/candidates").json()["items"][0]["candidate_id"]
    hypotheses = client.get(f"/api/runs/{run_id}/hypotheses?candidate_id={candidate_id}").json()
    assert len(hypotheses["items"]) == 2


def test_storage_unavailable_returns_503_envelope(runtime, monkeypatch):
    settings, _, _ = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    client = TestClient(create_app(), raise_server_exceptions=False)

    def broken():
        raise sqlite3.Error("storage gone")

    monkeypatch.setattr(client.app.state.repository.database, "read", broken)
    for path in ("/health", "/api/runs"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
