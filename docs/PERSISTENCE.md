# Persistence and local runtime

Use Python's SQLite support and explicit small SQL statements. WAL, foreign_keys=ON, busy_timeout=5000 ms, synchronous=FULL for research writes. Keep transactions short; no network calls or artifact serialization inside a database transaction. Schema version is recorded via a small bootstrap/version check; do not port old migrations or introduce an ORM hierarchy. Phase 2 persistence schema version is **4** (`schema_info` holds one `UNIQUE` version row; bootstrap closes its connection and commits its version check in one short `BEGIN IMMEDIATE` transaction). A data directory from an earlier revision fails with an actionable `unsupported database schema 3; this build expects schema 4` error instead of being migrated or silently reset; Phase 1 fixture data is synthetic and disposable. Schema 4 adds the relational constraints listed below and re-keys `gdc_cache`; it does not redesign tables.


API and CLI invoke the same idempotent schema bootstrap before serving/starting, so starting the API first creates an empty readable database and the UI can show “No runs yet.” SQLite serializes this short bootstrap transaction. An incompatible existing schema fails clearly; it is never silently reset. Schema bootstrap does not create a ResearchRun or start research.

| Table | Key and role |
|---|---|
| research_runs | run_id PK; current projection, config/scope, last_sequence, terminal/coverage/counters |
| run_events | event_id PK; run FK; UNIQUE(run_id,sequence), UNIQUE(run_id,idempotency_key); immutable full event JSON |
| candidates | candidate_id PK; run FK; UNIQUE(run_id,promotion_slot), unique investigation context; projection only |
| artifacts | artifact_id PK; relative path, sha256, byte size, media type, purpose, schema version |
| statistical_states | state_id PK; run FK, content hash, artifact FK, selection disposition |
| evidence_states | evidence_state_id PK; candidate FK, parent FK, iteration, content hash, artifact FK |
| jev_evaluations | id PK; candidate FK (nullable for state-level evaluations); explicit input reference kind/id (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`), purpose, artifact FK, full evaluation JSON, model; the evaluation JSON holds mode, question/model/cache identity |
| hypotheses | id PK; candidate FK, originating evidence FK, artifact FK; <=6 lifetime enforced at admission |
| followup_executions | id PK; candidate FK, action/version/input hash, slot, status, result refs |
| dossiers | dossier_id PK; candidate_id UNIQUE, run FK, JSON and Markdown artifact FKs |
| worker_status | one row; owner ID, heartbeat timestamp, version; informational |
| gdc_attempts | operational GDC ledger: one row per dispatch or cache hit with `request_id` PK, run/logical-query refs, attempt number, method/endpoint, canonical request hash, `RESERVED`/`COMPLETED`/`FAILED`/`CACHE_HIT` status, reserved allowance, charged bytes, HTTP status, response artifact/hash, completeness, error, timestamps. Mutable only through the transport's own ledger functions; the RunEvent stream remains the authority and this table is never a second status source. Every attempt that started reaches a terminal status. |
| gdc_cache | `cache_key` PK (`<contract_version>:<canonical request hash>`) with UNIQUE(request_hash,contract_version) → response artifact, response hash, size, endpoint, completeness, created_at. An entry written under an older contract version stays immutable and can never block storing the current contract's entry for the same request. |
| jev_projections | projection_id PK; run/state refs, projection version, source state hash, projection hash, artifact FK, included-field contract; immutable |
| jev_cache | inference identity PK (`sha256(projection_hash + question_set_hash + pinned model identity + adapter_version)`) → origin evaluation_id; immutable. The identity is only computed for a pinned/versioned model name whose provider resolution equals that name, so a mutable alias is always evaluated by the provider and a divergent resolution is never cached. Routing-policy version is deliberately absent so policy experiments do not rerun inference. |

No generic entity-attribute graph or separate domain database. JSON holds typed complex payloads; scalar columns index actual API queries. Add indexes `(run_id,sequence)`, `(created_at,run_id)`, `(run_id,candidate_id)` and state/evaluation hash lookup as needed. All foreign IDs referenced by an event must already exist or be inserted in that event's transaction; schema 4 enforces the provenance chain declared relational constraints so a dangling reference fails the event transaction instead of persisting: `candidates.source_state_id` → `statistical_states`, `candidates.latest_evidence_state_id` and `evidence_states.previous_evidence_state_id` → `evidence_states`, `evidence_states.candidate_id`, `hypotheses.candidate_id`/`evidence_state_id`, `followup_executions.candidate_id`/`output_evidence_state_id` and `jev_evaluations.candidate_id` → `candidates`/`evidence_states`, plus the existing artifact FKs.

Immutable records/events disallow UPDATE/DELETE through repository APIs and simple SQLite triggers; corrections create new records. The trigger set covers `run_events`, `artifacts`, `statistical_states`, `evidence_states`, `jev_evaluations`, `hypotheses`, `followup_executions`, `dossiers`, `jev_projections`, `jev_cache` and `gdc_cache`. Mutable records are only the run/candidate projections (`research_runs`, `candidates`), the informational `worker_status` row, and the operational `gdc_attempts` ledger; all are written only through the event commit function or the transport ledger functions. Projection-rebuild tooling uses the same reducer and a controlled local transaction. The worker heartbeat is not an alternative run log.

```text
data/
  cancerjev.db                 # sole status/event authority
  research.lock                # OS-held lock, not an existence-only PID file
  cache/gdc/<request-hash>/<response-hash>.body  # raw bounded responses
  runs/<run-id>/
    statistical_states/<id>.json
    jev/projections/<id>.json
    jev/<id>.json
    wide/baseline_ranking.json
    wide/jev_ranking.json
    evidence/<id>.json
    jev/<id>.json
    hypotheses/<id>.json
    followups/<id>.json
    dossier/<dossier-id>.json
    dossier/<dossier-id>.md
```

Do not maintain a second authoritative run.json or duplicate dossier archive. `/dossiers` is a database index over these artifacts. Git ignores data except `.gitkeep`. JSON is sufficient initially; Parquet/TSV are optional later formats for bounded tables.

Artifact publish: serialize canonical bytes to a unique temporary file on the same filesystem, flush/fsync, calculate hash and length, close, atomically rename to final immutable name, then insert artifact metadata plus referring records/event in a SQLite transaction. Artifact identity is deterministic (`uuid5` over relative path + SHA-256), so republishing identical bytes at the same path is a safe retry: it returns the same `artifact_id` without rewriting the file, and a different-bytes collision raises instead of overwriting. Artifact registration is conflict-tolerant (`ON CONFLICT(artifact_id) DO NOTHING`), which recovers a file that exists but whose metadata row was never committed. If the DB commit fails, an orphan file is safe and invisible. If rename fails, publish no record/event. Do not claim SQLite and filesystem are one atomic transaction. On read verify metadata/path confinement and, when scientifically consumed, checksum. Missing/corrupt files produce explicit errors. Orphan cleanup is a separate explicit maintenance operation, not deletion on worker startup.

The worker uses an OS-held exclusive file lock (one small cross-platform locking dependency if necessary) for the entire research-process lifetime. A second `run` or `worker` process exits with a clear ownership error before creating a run. Do not infer lock ownership from an old PID or heartbeat. API reads do not hold this lock.

After acquiring the lock, a new owner finds previous PENDING/RUNNING records, commits recovery RUN_STOPPED/INTERRUPTED and candidate dispositions, retaining every old event and artifact. It starts a new run rather than replaying uncertain external requests. FastAPI restart does not alter run status or start research. The UI displays a stale worker heartbeat separately from persisted run status until reconciliation.

Local serving: API binds 127.0.0.1:8000; Next.js uses localhost:3000; CLI/research process runs separately. All point to one absolute `CANCERJEV_DATA_DIR` so differing working directories cannot create accidental databases. Phase 1 needs no keys or provider connectivity. Database connections are process-local; API uses read transactions and does not hold long-lived snapshots across HTTP requests.

Keep RunRepository, EventRepository and ArtifactStore narrow; they can be concrete local implementations without abstract factories. No generic storage provider framework is necessary.
