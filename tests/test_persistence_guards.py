from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

import pytest

import cancerjev
from cancerjev.domain.events import REGISTERED_EVENT_TYPES, canonical_json, utc_now
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.artifacts import artifact_id_for
from cancerjev.storage.database import IMMUTABLE_TABLES, SCHEMA_VERSION, Database
from cancerjev.storage.ownership import OwnershipError, ResearchOwnership
from cancerjev.storage.readers import ScientificReadError, read_artifact

IMMUTABILITY_TABLES = tuple(IMMUTABLE_TABLES)


def _expected_triggers() -> set[str]:
    return {f"{table}_{operation}" for table in IMMUTABILITY_TABLES
            for operation in ("no_update", "no_delete")}


def test_bootstrap_is_idempotent_and_uses_wal(tmp_path):
    path = tmp_path / "bootstrap" / "cancerjev.db"
    for _ in range(3):
        Database(path).bootstrap()

    with Database(path).read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 1
        assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_concurrent_bootstrap_creates_one_schema_row_and_all_triggers(tmp_path):
    path = tmp_path / "concurrent" / "cancerjev.db"
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def bootstrap() -> None:
        try:
            barrier.wait(timeout=10)
            Database(path).bootstrap()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=bootstrap) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    with Database(path).read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_info").fetchone()[0] == 1
        triggers = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )}
    assert triggers == _expected_triggers()


@pytest.mark.parametrize("version", [1, 3, 4, 99])
def test_incompatible_schema_is_refused_without_migration(tmp_path, version):
    path = tmp_path / f"schema-{version}" / "cancerjev.db"
    path.parent.mkdir(parents=True)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_info(version INTEGER NOT NULL UNIQUE)")
    connection.execute("INSERT INTO schema_info(version) VALUES(?)", (version,))
    connection.commit()
    connection.close()
    before = path.read_bytes()

    with pytest.raises(RuntimeError, match=f"unsupported database schema {version}"):
        Database(path).bootstrap()

    assert path.read_bytes() == before
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert tables == {"schema_info"}


def test_corrupt_database_file_is_refused(tmp_path):
    path = tmp_path / "corrupt" / "cancerjev.db"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"this file is not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        Database(path).bootstrap()


def test_ownership_lock_is_exclusive(tmp_path):
    lock_path = tmp_path / "data" / "research.lock"
    with ResearchOwnership(lock_path):
        with pytest.raises(OwnershipError):
            ResearchOwnership(lock_path).__enter__()
    with ResearchOwnership(lock_path):
        pass


def test_immutable_tables_reject_direct_update_and_delete(runtime):
    settings, repository, artifacts = runtime
    DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()

    expected_rows = {
        "run_events", "artifacts", "statistical_states", "evidence_states",
        "jev_evaluations", "hypotheses", "followup_executions", "dossiers",
        "jev_projections", "jev_cache",
    }
    with repository.database.connect(write=True) as connection:
        for table in IMMUTABILITY_TABLES:
            before = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if table in expected_rows:
                assert before > 0, table
            if before == 0:
                continue
            with pytest.raises(sqlite3.IntegrityError, match="is immutable"):
                connection.execute(f"UPDATE {table} SET rowid=rowid")
            connection.rollback()
            with pytest.raises(sqlite3.IntegrityError, match="is immutable"):
                connection.execute(f"DELETE FROM {table}")
            connection.rollback()


def test_mutable_projections_still_update(runtime):
    settings, repository, artifacts = runtime
    run_id = DemoOrchestrator(settings, repository, artifacts, lambda event: None).run()
    repository.heartbeat("mutable-probe")

    with repository.database.connect(write=True) as connection:
        connection.execute("UPDATE research_runs SET coverage='COMPLETE_FOR_SCOPE' WHERE run_id=?", (run_id,))
        connection.execute("UPDATE candidates SET status=status WHERE run_id=?", (run_id,))
        connection.execute("UPDATE worker_status SET version=version WHERE singleton=1")

    assert repository.get_run(run_id)["coverage"] == "COMPLETE_FOR_SCOPE"
    with repository.database.read() as connection:
        assert connection.execute("SELECT owner_id FROM worker_status").fetchone()[0] == "mutable-probe"


def test_dangling_candidate_evidence_and_followup_provenance_is_rejected(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run("dangling-worker")
    artifact = artifacts.publish("runs/dangling/state.json", b'{"kind":"STATISTICAL_STATE"}',
                                 "application/json", "state")
    repository.register_artifact(artifact, run_id)
    state_id = str(uuid4())
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key="state:1",
        message="Synthetic state registration.", stage="STATE_GENERATION",
        data={"state_id": state_id, "state_hash": "a" * 64},
        registrations=[repository.state_registration(
            state_id=state_id, run_id=run_id, state_hash="a" * 64,
            artifact_id=artifact.artifact_id, disposition="GENERATED",
            summary_json=canonical_json({"entity": {"gene_id": "G1"}}).decode(),
            created_at=utc_now(),
        )],
    )
    before_sequence = repository.get_run(run_id)["last_sequence"]

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_event(
            run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="candidate:dangling",
            message="Candidate with a dangling source state.", stage="JEV_WIDE",
            candidate_id=str(uuid4()), data={"candidate_id": str(uuid4())},
            registrations=[repository.candidate_registration(
                candidate_id=str(uuid4()), run_id=run_id, promotion_slot=1,
                status="WIDE_EVALUATED", current_stage=None, source_state_id=str(uuid4()),
                entity_json="{}", summary_json="{}", created_at=utc_now(), updated_at=utc_now(),
            )],
        )
    assert repository.get_run(run_id)["last_sequence"] == before_sequence
    assert repository.list_table("candidates", run_id) == []

    candidate_id = str(uuid4())
    repository.append_event(
        run_id, event_type="CANDIDATE_PROMOTED", idempotency_key="candidate:valid",
        message="Candidate bound to its source state.", stage="JEV_WIDE",
        candidate_id=candidate_id, data={"candidate_id": candidate_id},
        registrations=[repository.candidate_registration(
            candidate_id=candidate_id, run_id=run_id, promotion_slot=1,
            status="WIDE_EVALUATED", current_stage=None, source_state_id=state_id,
            entity_json="{}", summary_json="{}", created_at=utc_now(), updated_at=utc_now(),
        )],
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_event(
            run_id, event_type="EVIDENCE_STATE_CREATED", idempotency_key="evidence:dangling",
            message="Evidence revision with a dangling parent.", stage="EVIDENCE_BUILD",
            candidate_id=candidate_id, iteration=1,
            data={"evidence_state_id": str(uuid4()), "iteration": 1},
            registrations=[repository.evidence_state_registration(
                evidence_state_id=str(uuid4()), run_id=run_id, candidate_id=candidate_id,
                previous_evidence_state_id=str(uuid4()), iteration=1, evidence_hash="b" * 64,
                artifact_id=artifact.artifact_id, summary_json="{}", created_at=utc_now(),
            )],
        )

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_event(
            run_id, event_type="FOLLOWUP_COMPLETED", idempotency_key="followup:dangling",
            message="Follow-up with a dangling candidate.", stage="FOLLOWUP",
            candidate_id=str(uuid4()), iteration=1,
            data={"execution_id": str(uuid4()), "action_id": "CHECK_EVIDENCE_INTEGRITY_V1"},
            registrations=[repository.followup_execution_registration(
                execution_id=str(uuid4()), run_id=run_id, candidate_id=str(uuid4()),
                action_id="CHECK_EVIDENCE_INTEGRITY_V1", action_version="1",
                input_evidence_hash="b" * 64, output_evidence_state_id=None, slot=1,
                status="COMPLETED", summary_json="{}", created_at=utc_now(),
            )],
        )

    execution_id = str(uuid4())
    repository.append_event(
        run_id, event_type="FOLLOWUP_COMPLETED", idempotency_key="followup:valid",
        message="Follow-up bound to its candidate.", stage="FOLLOWUP",
        candidate_id=candidate_id, iteration=1,
        data={"execution_id": execution_id, "action_id": "CHECK_EVIDENCE_INTEGRITY_V1"},
        registrations=[repository.followup_execution_registration(
            execution_id=execution_id, run_id=run_id, candidate_id=candidate_id,
            action_id="CHECK_EVIDENCE_INTEGRITY_V1", action_version="1",
            input_evidence_hash="b" * 64, output_evidence_state_id=None, slot=1,
            status="COMPLETED", summary_json="{}", created_at=utc_now(),
        )],
    )
    assert len(repository.list_table("followup_executions", run_id)) == 1


def test_artifact_identity_and_corruption_are_enforced(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run("artifact-owner")
    artifact = artifacts.publish("runs/artifact/state.json", b'{"kind":"STATISTICAL_STATE"}',
                                 "application/json", "state")
    assert artifact.artifact_id == artifact_id_for("runs/artifact/state.json", artifact.sha256)

    with pytest.raises(FileExistsError):
        artifacts.publish("runs/artifact/state.json", b'{"kind":"OTHER"}',
                          "application/json", "state")
    with pytest.raises(ValueError):
        artifacts.publish("../escape.json", b"{}", "application/json", "state")

    repository.register_artifact(artifact, run_id)
    target = settings.data_dir / artifact.relative_path
    assert target.is_file()
    target.write_bytes(b"corrupt")
    with pytest.raises(ScientificReadError) as error:
        read_artifact(repository, artifacts, artifact.artifact_id)
    assert error.value.code == "EVIDENCE_ARTIFACT_CORRUPT"

    missing = artifacts.publish("runs/artifact/missing.json", b'{"kind":"STATISTICAL_STATE"}',
                                "application/json", "state")
    repository.register_artifact(missing, run_id)
    (settings.data_dir / missing.relative_path).unlink()
    with pytest.raises(ScientificReadError) as error:
        read_artifact(repository, artifacts, missing.artifact_id)
    assert error.value.code == "EVIDENCE_ARTIFACT_UNAVAILABLE"

    mismatched_id = str(uuid4())
    with repository.database.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO artifacts(artifact_id,run_id,relative_path,sha256,size_bytes,media_type,purpose,schema_version) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (mismatched_id, run_id, "runs/artifact/other.json", artifact.sha256,
             artifact.size_bytes, "application/json", "state", 1),
        )
    with pytest.raises(ScientificReadError) as error:
        read_artifact(repository, artifacts, mismatched_id)
    assert error.value.code == "RECORD_BINDING_MISMATCH"


def test_registered_vocabulary_covers_orchestrator_emissions(runtime):
    settings, repository, artifacts = runtime
    emitted: list[dict] = []
    DemoOrchestrator(settings, repository, artifacts, emitted.append).run()
    assert {event["type"] for event in emitted} <= REGISTERED_EVENT_TYPES


def test_research_and_jev_modules_own_no_persistence_sql():
    root = Path(cancerjev.__file__).parent
    modules = sorted((root / "research").glob("*.py")) + sorted((root / "jev").glob("*.py"))
    assert modules
    for module in modules:
        source = module.read_text(encoding="utf-8")
        for token in ("INSERT INTO", "SELECT ", "UPDATE ", "repository.database"):
            assert token not in source, f"{module.name} contains raw persistence SQL: {token}"
