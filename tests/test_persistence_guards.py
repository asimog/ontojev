from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

import cancerjev
from cancerjev.domain.events import REGISTERED_EVENT_TYPES
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.artifacts import PublishedArtifact
from cancerjev.storage.database import IMMUTABLE_TABLES, SCHEMA_VERSION, Database

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
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
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


def test_dangling_candidate_evidence_and_followup_provenance_is_rejected(runtime):
    _, repository, artifacts = runtime
    run_id = repository.create_run("dangling-provenance")
    repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="created", message="created")
    state_artifact = PublishedArtifact(
        artifact_id=str(uuid4()), relative_path="statistical_states/dangling-synthetic.json",
        sha256="b" * 64, size_bytes=2, media_type="application/json", purpose="statistical-state",
    )
    repository.register_artifact(state_artifact, run_id)
    state_id = str(uuid4())
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key="state", message="state",
        stage="STATE_GENERATION",
        registrations=[repository.state_registration(
            state_id=state_id, run_id=run_id, state_hash="b" * 64,
            artifact_id=state_artifact.artifact_id, disposition="GENERATED", summary_json="{}",
            created_at="2026-01-01T00:00:00Z",
        )],
    )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        repository.append_event(
            run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="dangling-state",
            message="promoted", stage="JEV_WIDE",
            registrations=[repository.candidate_registration(
                candidate_id=str(uuid4()), run_id=run_id, promotion_slot=1, status="WIDE_EVALUATED",
                current_stage="JEV_WIDE", source_state_id=str(uuid4()), entity_json="{}",
                summary_json="{}", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
            )],
        )

    candidate_id = str(uuid4())
    repository.append_event(
        run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="promoted", message="promoted",
        stage="JEV_WIDE", candidate_id=candidate_id,
        registrations=[repository.candidate_registration(
            candidate_id=candidate_id, run_id=run_id, promotion_slot=1, status="WIDE_EVALUATED",
            current_stage="JEV_WIDE", source_state_id=state_id, entity_json="{}", summary_json="{}",
            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )],
    )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        repository.append_event(
            run_id, event_type="EVIDENCE_STATE_CREATED", idempotency_key="dangling-previous",
            message="evidence", stage="EVIDENCE_BUILD", candidate_id=candidate_id,
            registrations=[repository.evidence_state_registration(
                evidence_state_id=str(uuid4()), run_id=run_id, candidate_id=candidate_id,
                previous_evidence_state_id=str(uuid4()), iteration=1, evidence_hash="c" * 64,
                artifact_id=state_artifact.artifact_id, summary_json="{}",
                created_at="2026-01-01T00:00:00Z",
            )],
        )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        repository.append_event(
            run_id, event_type="FOLLOWUP_COMPLETED", idempotency_key="dangling-candidate",
            message="followup", stage="FOLLOWUP",
            registrations=[repository.followup_execution_registration(
                execution_id=str(uuid4()), run_id=run_id, candidate_id=str(uuid4()),
                action_id="ACTION", action_version="1", input_evidence_hash="d" * 64,
                output_evidence_state_id=None, slot=1, status="COMPLETED", summary_json="{}",
                created_at="2026-01-01T00:00:00Z",
            )],
        )


def test_research_and_jev_modules_own_no_persistence_sql():
    root = Path(cancerjev.__file__).parent
    modules = sorted((root / "research").glob("*.py")) + sorted((root / "jev").glob("*.py"))
    assert modules
    for module in modules:
        source = module.read_text(encoding="utf-8")
        assert "INSERT INTO" not in source, module
        assert "SELECT " not in source, module
        assert "UPDATE " not in source, module
        assert "repository.database" not in source, module
