from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from cancerjev.domain.events import REGISTERED_EVENT_TYPES
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.database import IMMUTABLE_TABLES, Database

IMMUTABLE_ROW_COUNTS = {
    "run_events": "SELECT COUNT(*) FROM run_events",
    "artifacts": "SELECT COUNT(*) FROM artifacts",
    "statistical_states": "SELECT COUNT(*) FROM statistical_states",
    "evidence_states": "SELECT COUNT(*) FROM evidence_states",
    "jev_evaluations": "SELECT COUNT(*) FROM jev_evaluations",
    "hypotheses": "SELECT COUNT(*) FROM hypotheses",
    "followup_executions": "SELECT COUNT(*) FROM followup_executions",
    "dossiers": "SELECT COUNT(*) FROM dossiers",
}


def test_immutability_triggers_exist_for_every_immutable_table(runtime):
    _, repository, _ = runtime
    with repository.database.read() as connection:
        triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert triggers == {f"{table}_no_{operation}" for table in IMMUTABLE_TABLES for operation in ("update", "delete")}


def test_immutable_tables_reject_direct_update_and_delete(runtime):
    settings, repository, artifacts = runtime
    DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    connection = repository.database.connect(write=True)
    try:
        for table, count_query in IMMUTABLE_ROW_COUNTS.items():
            before = connection.execute(count_query).fetchone()[0]
            assert before > 0, table
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(f"UPDATE {table} SET rowid=rowid")
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(f"DELETE FROM {table}")
            assert connection.execute(count_query).fetchone()[0] == before
    finally:
        connection.close()


def test_mutable_projections_still_update(runtime):
    settings, repository, artifacts = runtime
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    connection = repository.database.connect(write=True)
    try:
        connection.execute("UPDATE research_runs SET coverage='COMPLETE_FOR_SCOPE' WHERE run_id=?", (run_id,))
        connection.execute("UPDATE candidates SET status=status WHERE run_id=?", (run_id,))
        connection.execute("UPDATE worker_status SET version=version WHERE singleton=1")
    finally:
        connection.close()
    assert repository.get_run(run_id)["status"] == "COMPLETED"


def test_bootstrap_is_idempotent_and_closes_its_connection(tmp_path):
    path = tmp_path / "bootstrap" / "cancerjev.db"
    for _ in range(3):
        Database(path).bootstrap()
    with Database(path).read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 1
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 2
    path.unlink()  # fails on Windows if bootstrap leaked an open handle


def test_concurrent_bootstrap_creates_exactly_one_schema_row(tmp_path):
    path = tmp_path / "concurrent" / "cancerjev.db"

    def bootstrap(_: int) -> None:
        Database(path).bootstrap()

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(bootstrap, range(5)))
    with Database(path).read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0] == 2 * len(IMMUTABLE_TABLES)


def test_incompatible_schema_fails_clearly(tmp_path):
    path = tmp_path / "old" / "cancerjev.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_info(version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_info(version) VALUES(1)")
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError, match="unsupported database schema 1"):
        Database(path).bootstrap()


def test_registered_vocabulary_covers_orchestrator_emissions(runtime):
    settings, repository, artifacts = runtime
    emitted: list[dict] = []
    DemoOrchestrator(settings, repository, artifacts, emitted.append).run()
    assert {event["type"] for event in emitted} <= REGISTERED_EVENT_TYPES
