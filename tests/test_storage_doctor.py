"""Storage doctor: read-only integrity reporting and bounded temp pruning."""

from __future__ import annotations

import os
import time
from collections import namedtuple

from cancerjev.storage.database import Database
from cancerjev.storage.doctor import prune_stale_temp_artifacts, run_doctor

_DiskUsage = namedtuple("usage", "total used free")


def _register_artifact(settings, repository, artifacts, relative: str) -> dict:
    run_id = repository.create_run("doctor-test")
    artifact = artifacts.publish(relative, b'{"kind":"STATISTICAL_STATE"}',
                                 "application/json", "statistical-state")
    repository.register_artifact(artifact, run_id)
    return {"run_id": run_id, "artifact_id": artifact.artifact_id,
            "path": settings.data_dir / relative}


def _codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_healthy_store_reports_no_findings(runtime):
    settings, repository, artifacts = runtime
    report = run_doctor(settings)
    assert report.ok(), report.findings
    assert report.schema_version == report.expected_schema_version
    assert report.payload()["ok"] is True


def test_missing_and_corrupt_registered_artifacts_are_reported_without_repair(runtime):
    settings, repository, artifacts = runtime
    missing = _register_artifact(settings, repository, artifacts, "runs/doctor/missing.json")
    corrupt = _register_artifact(settings, repository, artifacts, "runs/doctor/corrupt.json")

    missing["path"].unlink()
    corrupt["path"].write_bytes(b"corrupted")

    report = run_doctor(settings)
    assert {"ARTIFACT_MISSING", "ARTIFACT_HASH_MISMATCH"} <= _codes(report)
    assert report.ok() is False
    assert len(repository.all_artifacts()) == 2, "the doctor never repairs or deletes records"
    assert corrupt["path"].read_bytes() == b"corrupted"


def test_unregistered_file_is_reported_but_never_removed(runtime):
    settings, repository, artifacts = runtime
    stray = settings.data_dir / "stray" / "data.json"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"{}")

    report = run_doctor(settings)
    assert "ARTIFACT_UNREGISTERED" in _codes(report)
    assert report.ok(), "unregistered files are a warning, not evidence damage"
    assert stray.is_file()


def test_stale_temp_is_reported_and_pruned_only_when_declared(runtime):
    settings, repository, artifacts = runtime
    registered = _register_artifact(settings, repository, artifacts, "runs/doctor/kept.tmp")
    stale = settings.data_dir / "runs" / "doctor" / "stale.tmp"
    stale.write_bytes(b"partial")
    old = time.time() - 10 * 24 * 3600
    os.utime(stale, (old, old))

    report = run_doctor(settings)
    assert "TEMP_ARTIFACT_STALE" in _codes(report)
    assert stale.is_file(), "reporting alone never deletes anything"

    removed = prune_stale_temp_artifacts(settings)
    assert removed == ("runs/doctor/stale.tmp",)
    assert not stale.exists()
    assert registered["path"].is_file(), "a registered artifact is never pruned"


def test_future_schema_is_reported_and_the_file_is_untouched(runtime):
    settings, repository, artifacts = runtime
    database = Database(settings.database_path)
    with database.connect(write=True) as connection:
        connection.execute("UPDATE schema_info SET version=99")

    report = run_doctor(settings)
    assert "SCHEMA_INCOMPATIBLE" in _codes(report)
    assert report.ok() is False
    with database.read() as connection:
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 99


def test_stale_heartbeat_and_low_disk_space_are_reported(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    repository.heartbeat("doctor-test-worker")
    with repository.database.connect(write=True) as connection:
        connection.execute(
            "UPDATE worker_status SET heartbeat_at='2020-01-01T00:00:00Z' WHERE singleton=1")

    monkeypatch.setattr(
        "cancerjev.storage.doctor.shutil.disk_usage",
        lambda path: _DiskUsage(0, 0, 1))
    report = run_doctor(settings)

    assert {"WORKER_HEARTBEAT_STALE", "DISK_SPACE_LOW"} <= _codes(report)
