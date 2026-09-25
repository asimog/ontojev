from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.cli.main import main
from cancerjev.config import Settings
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


def _json_documents(text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    documents: list[dict] = []
    cursor = 0
    while True:
        start = text.find("\n{", cursor)
        if start == -1:
            return documents
        start += 1
        try:
            document, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        documents.append(document)
        cursor = start + end


def _run_demo(settings, repository, artifacts) -> str:
    return DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()


def test_cli_show_reports_committed_run_state(runtime, monkeypatch, capsys):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = _run_demo(settings, repository, artifacts)

    main(["show", run_id])
    summary = json.loads(capsys.readouterr().out)
    run = repository.get_run(run_id)

    assert summary["run_id"] == run_id
    assert summary["status"] == run["status"] == "COMPLETED"
    assert summary["mode"] == "FIXTURE"
    assert summary["fixture_id"] == "demo"
    assert summary["last_sequence"] == run["last_sequence"]
    assert summary["last_sequence"] == len(repository.events(run_id, 0, 500)["items"])
    assert summary["counts"] == run["counts"]
    assert summary["counts"]["states_generated"] == 2
    assert summary["counts"]["dossiers_created"] == 1


def test_cli_and_api_serve_the_same_committed_event_stream(runtime, monkeypatch, capsys):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = _run_demo(settings, repository, artifacts)

    main(["show", run_id, "--events"])
    cli_events = _json_documents(capsys.readouterr().out)
    stored = repository.events(run_id, 0, 500)

    client = TestClient(create_app())
    served = client.get(f"/api/runs/{run_id}/events?after_sequence=0&limit=500").json()

    assert stored["has_more"] is False
    assert stored["run_last_sequence"] == len(stored["items"])
    assert len(cli_events) == len(stored["items"]) == len(served["items"])
    assert len(cli_events) == repository.get_run(run_id)["last_sequence"]
    assert [event["sequence"] for event in cli_events] == list(range(1, len(cli_events) + 1))
    assert cli_events == stored["items"] == served["items"]


def test_cli_fixture_run_completes_offline(tmp_path, monkeypatch):
    data_dir = tmp_path / "cli-fixture"
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(data_dir))

    main(["run", "--fixture", "demo"])

    settings = Settings.from_env()
    database = Database(settings.database_path)
    assert database.path == data_dir / "cancerjev.db"
    repository = Repository(database)
    runs = repository.list_runs()
    assert len(runs) == 1
    run = repository.get_run(runs[0]["run_id"])
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "FIXTURE"
    assert run["counts"]["states_generated"] == 2
    assert run["counts"]["candidates_promoted"] == 2
    assert run["counts"]["dossiers_created"] == 1
    assert run["provider_usage"]["gdc_requests"] == 0
    assert run["provider_usage"]["llm_calls"] == 0
    assert run["provider_usage"]["jev_calls"] == 5


def test_bounded_live_paths_require_explicit_authorization(monkeypatch):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="--jev requires --live"):
        main(["run", "--jev"])
    with pytest.raises(SystemExit, match="--live --jev"):
        main(["run", "--deep-candidate", "gene:FOO"])
    with pytest.raises(SystemExit, match="TYPESAFE_API_KEY"):
        main(["run", "--live", "--jev"])
    with pytest.raises(SystemExit, match="Choose --fixture demo"):
        main(["run"])

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-key")
    with pytest.raises(SystemExit, match="--deep-action requires --deep-candidate"):
        main(["run", "--live", "--jev", "--deep-action", "CHECK_EVIDENCE_INTEGRITY_V1"])
    with pytest.raises(SystemExit, match="--deep-followup requires --deep-candidate"):
        main(["run", "--live", "--jev", "--deep-followup"])
    with pytest.raises(SystemExit, match="--deep-hypotheses requires --deep-candidate --deep-followup"):
        main(["run", "--live", "--jev", "--deep-candidate", "gene:FOO", "--deep-hypotheses"])
    with pytest.raises(SystemExit, match="Unknown action id"):
        main(["run", "--live", "--jev", "--deep-candidate", "gene:FOO",
              "--deep-action", "NOT_REGISTERED_V1"])
