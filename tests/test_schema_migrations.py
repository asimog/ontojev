"""Supported schema upgrades: sequential, backed up, transactional, fail closed."""

from __future__ import annotations

import sqlite3

import pytest

from cancerjev.storage import database as database_module
from cancerjev.storage.database import SCHEMA, SCHEMA_VERSION, Database

V6_SCHEMA = SCHEMA.replace(database_module.V7_ARTIFACT_PURPOSE_INDEX + ";\n", "")


def _create_v6_store(path) -> None:
    """Reproduce the immediately previous supported schema (v6) with sample rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(V6_SCHEMA)
    connection.execute("INSERT INTO schema_info(version) VALUES(6)")
    connection.execute(
        "INSERT INTO research_runs(run_id,mode,fixture_id,fixture_version,status,current_stage,"
        "last_sequence,created_at,started_at,ended_at,worker_id,outcome_reason,coverage,"
        "counters_json,usage_json,scope_json,stages_json,execution_ownership) "
        "VALUES('run-v6','LIVE',NULL,NULL,'COMPLETED',NULL,0,'2026-01-01T00:00:00Z',NULL,NULL,"
        "'v6-worker',NULL,'COMPLETE_FOR_SCOPE','{}','{}','{\"purpose\":\"LEGACY\"}','[]',"
        "'SYSTEM_AUTONOMOUS')")
    connection.execute(
        "INSERT INTO artifacts(artifact_id,run_id,relative_path,sha256,size_bytes,media_type,"
        "purpose,schema_version) VALUES('artifact-v6','run-v6','runs/v6/state.json',?,2,"
        "'application/json','statistical-state',5)", ("a" * 64,))
    connection.commit()
    connection.close()


def _indexes(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}


def test_v6_store_upgrades_to_current_with_backup_and_intact_evidence(tmp_path):
    path = tmp_path / "data" / "cancerjev.db"
    _create_v6_store(path)
    assert "idx_artifacts_purpose" not in _indexes(path)

    Database(path).bootstrap()

    with Database(path).read() as connection:
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
        rows = [tuple(row) for row in connection.execute("SELECT run_id FROM research_runs")]
        assert rows == [("run-v6",)]
        artifacts = [tuple(row) for row in connection.execute("SELECT artifact_id FROM artifacts")]
        assert artifacts == [("artifact-v6",)]
    assert "idx_artifacts_purpose" in _indexes(path)
    backups = sorted(path.parent.glob("cancerjev.db.backup-v6-*"))
    assert len(backups) == 1, "the upgrade is recoverable from a pre-migration backup"
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("SELECT version FROM schema_info").fetchone()[0] == 6
        assert [tuple(row) for row in backup.execute("SELECT run_id FROM research_runs")] == \
            [("run-v6",)]
    finally:
        backup.close()
    Database(path).bootstrap()
    assert len(sorted(path.parent.glob("cancerjev.db.backup-v6-*"))) == 1, \
        "an already-current store is never re-migrated"


def test_failed_migration_rolls_back_and_keeps_the_previous_version(tmp_path, monkeypatch):
    path = tmp_path / "data" / "cancerjev.db"
    _create_v6_store(path)

    def broken(connection) -> None:
        connection.execute("CREATE TABLE should_roll_back(id INTEGER)")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setitem(database_module.MIGRATIONS, 6, broken)

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        Database(path).bootstrap()

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 6
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "should_roll_back" not in tables, "a failed migration commits nothing"
    assert len(sorted(path.parent.glob("cancerjev.db.backup-v6-*"))) == 1


def test_fresh_store_is_current_and_has_the_purpose_index(tmp_path):
    path = tmp_path / "fresh" / "cancerjev.db"
    Database(path).bootstrap()
    with Database(path).read() as connection:
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
    assert "idx_artifacts_purpose" in _indexes(path)
    assert sorted(path.parent.glob("cancerjev.db.backup-*")) == []


def test_multiple_schema_rows_are_refused_before_mutation(tmp_path):
    path = tmp_path / "multi" / "cancerjev.db"
    path.parent.mkdir(parents=True)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_info(version INTEGER NOT NULL UNIQUE)")
    connection.execute("INSERT INTO schema_info(version) VALUES(6)")
    connection.execute("INSERT INTO schema_info(version) VALUES(5)")
    connection.commit()
    connection.close()
    before = path.read_bytes()

    with pytest.raises(RuntimeError, match="corrupt database schema rows"):
        Database(path).bootstrap()

    assert path.read_bytes() == before
