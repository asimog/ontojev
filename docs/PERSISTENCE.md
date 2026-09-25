# Persistence and local runtime

Current storage state after the Stage 3 hard cutover and the Stage 4-8 implementations
(2026-09-25). The SQLite schema and the scientific artifact schema versions are the
machine-checked values in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md); they are not restated
here. Older or unknown schemas are rejected fail-closed; there are **no migrations and no
legacy readers**. Historical databases and artifacts are retained, not rewritten.

## Schema bootstrap and reset

- IMPLEMENTED: bootstrap opens an existing database read-only and compares its recorded version
  before changing journal mode or creating current tables/triggers. An unsupported version fails
  with an actionable `unsupported database schema N; this build expects schema M` error naming
  the expected current version and the
  database bytes are not modified.
- IMPLEMENTED: the current SQLite schema keeps the earlier table design (relational provenance
  constraints,
  immutable triggers, version-qualified `gdc_cache`) and rejects older-version stores rather than
  reinterpreting them.
- Reset instructions: stop the research process and the API, move or delete the whole data
  directory (including any `-wal`/`-shm` files and the `research.lock`), then start the API or
  CLI again. Bootstrap creates a fresh current-version database. Never edit `schema_info` by
  hand and
  never leave a copied live `.db` without its WAL when preserving evidence.
- Retain historical databases and artifacts. An older-version directory must be moved to a
  separate location (or deleted only if it is disposable); it is not migrated, reset or
  silently reinterpreted. No stale database or acceptance directory is retained in the
  repository: `data/` holds only its `.gitkeep`.

Use Python's SQLite support and explicit small SQL statements. WAL, `foreign_keys=ON`,
`busy_timeout=5000 ms`, `synchronous=NORMAL` for reads and `FULL` for research writes. Keep
transactions short; no network calls or artifact serialization inside a database transaction.
`schema_info` holds one `UNIQUE` version row. API and CLI invoke the same idempotent bootstrap
before serving/starting; starting the API first creates an empty readable database and the UI
shows “No runs yet.” Bootstrap does not create a `ResearchRun` or start research.

## Tables

| Table | Key and role |
|---|---|
| research_runs | run_id PK; current projection, config/scope, last_sequence, terminal/coverage/counters |
| run_events | event_id PK; run FK; UNIQUE(run_id,sequence), UNIQUE(run_id,idempotency_key); immutable full event JSON |
| candidates | candidate_id PK; run FK; UNIQUE(run_id,promotion_slot); source state FK; latest evidence FK; `operator-selection-v1` selections consume a slot |
| artifacts | artifact_id PK; relative path, sha256, byte size, media type, purpose, schema version |
| statistical_states | state_id PK; run FK, scientific hash, artifact FK, selection disposition, summary JSON |
| evidence_states | evidence_state_id PK; candidate FK, parent revision FK (null for baseline E0), iteration 0..2, evidence hash, artifact FK, summary JSON; one immutable revision per accepted baseline or deterministic action |
| jev_evaluations | evaluation_id PK; candidate FK (nullable for state-level evaluations); explicit input reference kind/id (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`), purpose, artifact FK, full evaluation JSON, model |
| hypotheses | hypothesis_id PK; candidate FK, originating evidence FK, artifact FK; at most three lifetime, enforced at admission |
| followup_executions | execution_id PK; candidate FK, action id/version, input evidence hash, output evidence revision FK (null on failure), slot, status (`COMPLETED`/`FAILED`), summary JSON |
| dossiers | dossier_id PK; candidate_id UNIQUE, run FK, JSON and Markdown artifact FKs |
| worker_status | one row; owner ID, heartbeat timestamp, version; informational |
| gdc_attempts | operational GDC ledger: one row per dispatch or cache hit with `request_id` PK, run/logical-query refs, attempt number, method/endpoint, canonical request hash, `RESERVED`/`COMPLETED`/`FAILED`/`CACHE_HIT` status, reserved allowance, charged bytes, HTTP status, response artifact/hash, completeness, error, timestamps. Mutable only through the transport's ledger functions; the RunEvent stream remains the authority and this table is never a second status source. Every attempt that started reaches a terminal status. |
| gdc_cache | `cache_key` PK (`<contract_version>:<canonical request hash>`) with UNIQUE(request_hash,contract_version) → response artifact, response hash, size, endpoint, completeness, created_at. An entry written under an older contract version stays immutable and can never block the current contract's entry for the same request. |
| jev_projections | projection_id PK; run/state refs, projection version, source state hash, projection hash, artifact FK, included-field contract; immutable; UNIQUE(state_id,projection_version) |
| jev_cache | inference identity PK (`sha256(projection_hash + question_set_hash + pinned model identity + adapter_version)`) → origin evaluation_id; immutable. Computed only for a pinned/versioned model name whose provider resolution equals it; routing-policy version is deliberately absent. |

No generic entity-attribute graph or second domain database. JSON stores events and boundary
payloads; scientific consumers exchange typed records. Scalar columns index actual API queries.
Indexes exist for `(run_id,sequence)`, `(created_at,run_id)`, `(run_id,candidate_id)` and
state/evaluation hash lookups. All foreign IDs referenced by an event must already exist or be
inserted in that event's transaction; foreign keys enforce the provenance chain
(`candidates.source_state_id` → `statistical_states`, `candidates.latest_evidence_state_id` and
`evidence_states.previous_evidence_state_id` → `evidence_states`, `evidence_states.candidate_id`,
`hypotheses`/`followup_executions`/`jev_evaluations` candidate and evidence bindings, plus the
artifact FKs), so a dangling reference fails the event transaction.

Immutable records/events disallow UPDATE/DELETE through repository APIs and SQLite triggers;
corrections create new records. The trigger set covers `run_events`, `artifacts`,
`statistical_states`, `evidence_states`, `jev_evaluations`, `hypotheses`,
`followup_executions`, `dossiers`, `jev_projections`, `jev_cache` and `gdc_cache`. Mutable
records are only the run/candidate projections (`research_runs`, `candidates`), the
informational `worker_status` row, and the operational `gdc_attempts` ledger; all are written
only through the event commit function or the transport ledger functions. The worker heartbeat
is not an alternative run log.

## Artifacts on disk

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
    hypotheses/<id>.json
    followups/<id>.json
    dossier/<dossier-id>.json
    dossier/<dossier-id>.md
```

Do not maintain a second authoritative `run.json` or duplicate dossier archive. `/dossiers` is a
database index over these artifacts. Git ignores `data/` except `.gitkeep`.

Artifact publish: serialize canonical bytes to a unique temporary file on the same filesystem,
flush/fsync, calculate hash and length, close, atomically rename to the final immutable name,
then insert artifact metadata plus referring records/event in one SQLite transaction. Artifact
identity is deterministic (`uuid5` over relative path + SHA-256), so republishing identical
bytes at the same path is a safe retry and returns the same `artifact_id`; a different-bytes
collision raises instead of overwriting. Registration is conflict-tolerant
(`ON CONFLICT(artifact_id) DO NOTHING`), which recovers a file whose metadata row was never
committed. If the DB commit fails, an orphan file is safe and invisible; if rename fails, no
record/event is published. SQLite and the filesystem are not one atomic transaction. On read,
metadata/path confinement and, for scientifically consumed artifacts, checksum are verified.

## Verified reads and typed hydration — IMPLEMENTED

`storage/readers.py` validates recorded sizes/hashes, confined paths, scientific schema/version
and identity, and record bindings before Deep acceptance, dossier assembly and scientific detail
API responses. Readers return typed `StateRecord`/`EvidenceRecord`/`HypothesisRecord` (and typed
evaluation records) or raise `ScientificReadError`; they never reinterpret an unknown version.
Corrupt authoritative latest revisions refuse dossier publication (`DOSSIER_UNAVAILABLE`) and do
not fall back to an earlier revision. Cached evaluations validate original question/projection
artifacts and answer contracts; an invalid entry causes an unusable-cache abstention with no
replacement provider call and no cache mutation. Repository row decoding stays infrastructure,
not scientific validation. `storage` remains the only layer that writes SQL; `research` and
`jev` register records through narrow `Repository` methods inside the same event +
registrations transaction.

## Process ownership and recovery

The worker holds an OS-held exclusive file lock for the entire research-process lifetime. A
second `run` or `worker` process exits with a clear ownership error before creating a run. Do
not infer lock ownership from an old PID or heartbeat. API reads do not hold this lock.

After acquiring the lock, a new owner finds previous PENDING/RUNNING records, commits recovery
RUN_STOPPED/INTERRUPTED and candidate dispositions, and retains every old event and artifact. It
starts a new run rather than replaying uncertain external requests. FastAPI restart does not
alter run status or start research. The UI displays a stale worker heartbeat separately from
persisted run status until reconciliation.

Local serving: API binds 127.0.0.1:8000; Next.js uses localhost:3000; the CLI/research process
runs separately. All point to one absolute `CANCERJEV_DATA_DIR` so differing working directories
cannot create accidental databases. Fixture mode needs no keys or provider connectivity.
Database connections are process-local; the API uses read transactions and does not hold
long-lived snapshots across HTTP requests.

Keep the existing `Repository` and `ArtifactStore` narrow; there are no separate
RunRepository/EventRepository classes and no generic storage provider framework.

## Boundary representations

JSON remains the correct boundary for external provider payloads, SQL parameters and decoded
rows, event envelopes, SDK envelopes, generated-text requests, artifact provenance envelopes and
serialized dossiers. It is not the internal scientific model: once read and validated, records
travel typed. Checksums prove byte identity, not schema validity or scientific truth.