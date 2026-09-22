from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info(version INTEGER NOT NULL);
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
 source_state_id TEXT NOT NULL, latest_evidence_state_id TEXT, dossier_id TEXT,
 entity_json TEXT NOT NULL, summary_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(run_id,promotion_slot)
);
CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(run_id,promotion_slot);
CREATE TABLE IF NOT EXISTS evidence_states(
 evidence_state_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
 previous_evidence_state_id TEXT, iteration INTEGER NOT NULL, evidence_hash TEXT NOT NULL,
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id), summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jev_evaluations(
 evaluation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT,
 state_id TEXT, purpose TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 vector_json TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypotheses(
 hypothesis_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
 evidence_state_id TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 hypothesis_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followup_executions(
 execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
 action_id TEXT NOT NULL, action_version TEXT NOT NULL, input_evidence_hash TEXT NOT NULL,
 output_evidence_state_id TEXT, slot INTEGER NOT NULL, status TEXT NOT NULL,
 summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dossiers(
 dossier_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL UNIQUE,
 json_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 markdown_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 summary_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dossiers_created ON dossiers(created_at DESC,dossier_id DESC);
CREATE TABLE IF NOT EXISTS worker_status(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner_id TEXT, heartbeat_at TEXT, version TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self, *, write: bool = False) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(f"PRAGMA synchronous={'FULL' if write else 'NORMAL'}")
        return connection

    def bootstrap(self) -> None:
        with self.connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_info").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_info(version) VALUES(?)", (SCHEMA_VERSION,))
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported database schema {row['version']}")
            connection.commit()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        finally:
            connection.close()

