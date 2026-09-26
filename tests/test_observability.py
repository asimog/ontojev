"""Operational logging and API request correlation; logs are never evidence."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.config import Settings
from cancerjev.observability import StructuredFormatter, configure_logging, log_event


def test_structured_log_records_carry_correlation_fields(caplog):
    configure_logging("DEBUG")
    with caplog.at_level(logging.DEBUG, logger="cancerjev"):
        log_event("campaign dispatched", level="debug", run_id="run-1",
                  campaign_id="LUAD_CAMPAIGN_V1", program_id="program-worker")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.message == "campaign dispatched"
    assert record.run_id == "run-1"
    assert record.campaign_id == "LUAD_CAMPAIGN_V1"
    assert record.program_id == "program-worker"
    rendered = json.loads(StructuredFormatter().format(record))
    assert rendered["message"] == "campaign dispatched"
    assert rendered["level"] == "debug"
    assert rendered["run_id"] == "run-1"


def test_configure_logging_is_idempotent():
    first = configure_logging()
    second = configure_logging()
    assert first is second
    formatters = [type(handler.formatter) for handler in first.handlers
                  if handler.formatter is not None]
    assert formatters.count(StructuredFormatter) == 1


def test_api_generates_and_echoes_request_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(tmp_path))
    settings = Settings(tmp_path, 0, 60, "http://localhost:3000")
    from cancerjev.storage.database import Database

    Database(settings.database_path).bootstrap()
    client = TestClient(create_app())

    generated = client.get("/health")
    assert generated.status_code == 200
    assert generated.headers["x-request-id"]

    echoed = client.get("/health", headers={"x-request-id": "trace-123"})
    assert echoed.headers["x-request-id"] == "trace-123"

    missing = client.get("/api/runs/00000000-0000-0000-0000-000000000000",
                         headers={"x-request-id": "trace-404"})
    assert missing.status_code == 404
    assert missing.json()["error"]["request_id"] == "trace-404"
