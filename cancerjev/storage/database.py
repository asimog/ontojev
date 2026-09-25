from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 4

IMMUTABLE_TABLES = (
    "run_events", "artifacts", "statistical_states", "evidence_states",
    "jev_evaluations", "hypotheses", "followup_executions", "dossiers",
    "jev_projections", "jev_cache", "gdc_cache",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info(version INTEGER NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS research_runs(
 run_id TEXT PRIMARY KEY, mode TEXT NOT NULL, fixture_id TEXT, fixture_version TEXT,
 status TEXT NOT NULL, current_stage TEXT, last_sequence INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT, worker_id TEXT NOT NULL,
 outcome_reason TEXT, coverage TEXT NOT NULL DEFAULT 'PARTIAL',
 counters_json TEXT NOT NULL, usage_json TEXT NOT NULL, scope_json TEXT NOT NULL,
 stages_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON research_runs(created_at DESC, run_id DESC);
CREATE TABLE IF NOT EXISTS run_events(
 event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(run_id),
 sequence INTEGER NOT NULL, idempotency_key TEXT NOT NULL, event_json TEXT NOT NULL,
 UNIQUE(run_id,sequence), UNIQUE(run_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_events_run_sequence ON run_events(run_id,sequence);
CREATE TABLE IF NOT EXISTS artifacts(
 artifact_id TEXT PRIMARY KEY, run_id TEXT, relative_path TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, media_type TEXT NOT NULL,
 purpose TEXT NOT NULL, schema_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS statistical_states(
 state_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(run_id),
 state_hash TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 disposition TEXT NOT NULL, summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_states_run ON statistical_states(run_id,created_at);
CREATE TABLE IF NOT EXISTS candidates(
 candidate_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(run_id),
 promotion_slot INTEGER NOT NULL, status TEXT NOT NULL, current_stage TEXT,
 source_state_id TEXT NOT NULL REFERENCES statistical_states(state_id),
 latest_evidence_state_id TEXT REFERENCES evidence_states(evidence_state_id), dossier_id TEXT,
 entity_json TEXT NOT NULL, summary_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(run_id,promotion_slot)
);
CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(run_id,promotion_slot);
CREATE TABLE IF NOT EXISTS evidence_states(
 evidence_state_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
 previous_evidence_state_id TEXT REFERENCES evidence_states(evidence_state_id), iteration INTEGER NOT NULL,
 evidence_hash TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jev_evaluations(
 evaluation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 candidate_id TEXT REFERENCES candidates(candidate_id),
 input_ref_kind TEXT NOT NULL, input_ref_id TEXT NOT NULL, purpose TEXT NOT NULL,
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 vector_json TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypotheses(
 hypothesis_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
 evidence_state_id TEXT NOT NULL REFERENCES evidence_states(evidence_state_id),
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 hypothesis_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followup_executions(
 execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
 action_id TEXT NOT NULL, action_version TEXT NOT NULL, input_evidence_hash TEXT NOT NULL,
 output_evidence_state_id TEXT REFERENCES evidence_states(evidence_state_id),
 slot INTEGER NOT NULL, status TEXT NOT NULL,
 summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dossiers(
 dossier_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 candidate_id TEXT NOT NULL UNIQUE REFERENCES candidates(candidate_id),
 json_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 markdown_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dossiers_created ON dossiers(created_at DESC,dossier_id DESC);
CREATE TABLE IF NOT EXISTS worker_status(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner_id TEXT, heartbeat_at TEXT, version TEXT
);
CREATE TABLE IF NOT EXISTS gdc_attempts(
 request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, logical_query_id TEXT NOT NULL,
 attempt_no INTEGER NOT NULL, method TEXT NOT NULL, endpoint TEXT NOT NULL,
 request_hash TEXT NOT NULL, status TEXT NOT NULL, reserved_bytes INTEGER NOT NULL DEFAULT 0,
 bytes_read INTEGER NOT NULL DEFAULT 0, http_status INTEGER, response_artifact_id TEXT,
 response_hash TEXT, completeness TEXT, error TEXT, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_gdc_attempts_run ON gdc_attempts(run_id,started_at);
CREATE INDEX IF NOT EXISTS idx_gdc_attempts_hash ON gdc_attempts(request_hash);
CREATE TABLE IF NOT EXISTS gdc_cache(
 cache_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
 method TEXT NOT NULL, endpoint TEXT NOT NULL,
 response_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 response_hash TEXT NOT NULL, size_bytes INTEGER NOT NULL, completeness TEXT NOT NULL,
 contract_version TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(request_hash,contract_version)
);
CREATE TABLE IF NOT EXISTS jev_projections(
 projection_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 state_id TEXT NOT NULL REFERENCES statistical_states(state_id),
 projection_version TEXT NOT NULL, source_state_hash TEXT NOT NULL,
 projection_hash TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 fields_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(state_id,projection_version)
);
CREATE INDEX IF NOT EXISTS idx_jev_projections_run ON jev_projections(run_id,created_at);
CREATE TABLE IF NOT EXISTS jev_cache(
 cache_key TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, created_at TEXT NOT NULL
);
""" + "".join(
    f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} "
    f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END;\n"
    f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} "
    f"BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END;\n"
    for table in IMMUTABLE_TABLES
)


def _enable_wal(connection: sqlite3.Connection) -> None:
    """Enable WAL with bounded retries.

    Changing the journal mode needs a brief exclusive lock and does not honour
    busy_timeout, so simultaneous first connections (API + research process)
    can otherwise fail with "database is locked".
    """
    for attempt in range(5):
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self, *, write: bool = False) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        _enable_wal(connection)
        connection.execute(f"PRAGMA synchronous={'FULL' if write else 'NORMAL'}")
        return connection

    def bootstrap(self) -> None:
        # Refuse obsolete stores before connect() changes journal mode or SCHEMA
        # creates tables/triggers. Old development data is never migrated.
        if self.path.is_file():
            existing = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                has_schema = existing.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_info'"
                ).fetchone()
                if has_schema:
                    versions = existing.execute("SELECT version FROM schema_info").fetchall()
                    if versions and versions != [(SCHEMA_VERSION,)]:
                        found = ", ".join(str(row[0]) for row in versions)
                        raise RuntimeError(
                            f"unsupported database schema {found}; this build expects schema {SCHEMA_VERSION}. "
                            "Earlier data is not migrated: use a fresh data directory."
                        )
            finally:
                existing.close()
        connection = self.connect(write=True)
        try:
            connection.executescript(SCHEMA)
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT version FROM schema_info").fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO schema_info(version) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM schema_info)",
                    (SCHEMA_VERSION,),
                )
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"unsupported database schema {row['version']}; this build expects schema {SCHEMA_VERSION}. "
                    "Earlier-phase data is not migrated: move or delete the existing data directory."
                )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        finally:
            connection.close()

