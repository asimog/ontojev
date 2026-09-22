from __future__ import annotations

import json

from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.cli.main import main
from cancerjev.research.orchestrator import DemoOrchestrator


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


def test_cli_show_emits_json_summary(runtime, monkeypatch, capsys):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    main(["show", run_id])
    summary = json.loads(capsys.readouterr().out)
    assert summary["run_id"] == run_id
    assert summary["status"] == "COMPLETED"
    assert summary["last_sequence"] == 71
    assert summary["counts"]["states_generated"] == 12


def test_cli_store_and_api_expose_identical_events(runtime, monkeypatch, capsys):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    main(["show", run_id, "--events"])
    cli_events = _json_documents(capsys.readouterr().out)

    stored = repository.events(run_id, 0, 500)["items"]
    client = TestClient(create_app())
    served = client.get(f"/api/runs/{run_id}/events?after_sequence=0&limit=500").json()["items"]

    assert len(cli_events) == len(stored) == len(served) == 71
    assert [event["sequence"] for event in cli_events] == list(range(1, 72))
    assert [event["event_id"] for event in cli_events] == [event["event_id"] for event in stored]
    assert [event["event_id"] for event in served] == [event["event_id"] for event in stored]
    assert cli_events == stored == served
