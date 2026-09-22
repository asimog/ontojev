from __future__ import annotations

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
