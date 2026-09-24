# Persistence and local runtime

## Stage 2 verified reads — IMPLEMENTED (2026-09-25)

`storage/readers.py` validates recorded sizes/hashes, confined paths, scientific schema/identity
and record bindings before Deep acceptance, dossier assembly and scientific detail API responses.
Repository row decoding remains infrastructure, not scientific validation. Corrupt authoritative
latest revisions refuse dossier publication (`DOSSIER_UNAVAILABLE`); no earlier-revision fallback.
Cached evaluations validate original question/projection artifacts and answer contracts; invalid
entries cause an unusable-cache abstention with no replacement provider call or cache mutation.
See [Stage 2 handoff](STAGE_02_HANDOFF.md). SQLite schema 4 and immutable historical bytes remain.

Use Python's SQLite support and explicit small SQL statements. WAL, foreign_keys=ON, busy_timeout=5000 ms, synchronous=FULL for research writes. Keep transactions short; no network calls or artifact serialization inside a database transaction. Schema version is recorded via a small bootstrap/version check; do not port old migrations or introduce an ORM hierarchy. Phase 2 persistence schema version is **4** (`schema_info` holds one `UNIQUE` version row; bootstrap closes its connection and commits its version check in one short `BEGIN IMMEDIATE` transaction). A data directory from an earlier revision fails with an actionable `unsupported database schema 3; this build expects schema 4` error instead of being migrated or silently reset; retain historical databases and artifacts; no deletion or silent reinterpretation is part of the compatibility policy. Schema 4 adds the relational constraints listed below and re-keys `gdc_cache`; it does not redesign tables.


API and CLI invoke the same idempotent schema bootstrap before serving/starting, so starting the API first creates an empty readable database and the UI can show “No runs yet.” SQLite serializes this short bootstrap transaction. An incompatible existing schema fails clearly; it is never silently reset. Schema bootstrap does not create a ResearchRun or start research.

| Table | Key and role |
|---|---|
| research_runs | run_id PK; current projection, config/scope, last_sequence, terminal/coverage/counters |
| run_events | event_id PK; run FK; UNIQUE(run_id,sequence), UNIQUE(run_id,idempotency_key); immutable full event JSON |
| candidates | candidate_id PK; run FK; UNIQUE(run_id,promotion_slot), unique investigation context; projection only |
| artifacts | artifact_id PK; relative path, sha256, byte size, media type, purpose, schema version |
| statistical_states | state_id PK; run FK, content hash, artifact FK, selection disposition |
| evidence_states | evidence_state_id PK; candidate FK, parent revision FK (null for the baseline E0), iteration 0..2, evidence hash, artifact FK, summary JSON. One immutable revision per accepted baseline or deterministic follow-up, written with its `EVIDENCE_STATE_CREATED` event. |
| jev_evaluations | id PK; candidate FK (nullable for state-level evaluations); explicit input reference kind/id (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`), purpose, artifact FK, full evaluation JSON, model; the evaluation JSON holds mode, question/model/cache identity |
| hypotheses | id PK; candidate FK, originating evidence FK, artifact FK; <=3 lifetime enforced at admission |
| followup_executions | execution_id PK; candidate FK, action id/version, input evidence hash, output evidence revision FK (null on failure), slot, status (`COMPLETED`/`FAILED`), summary JSON |
| dossiers | dossier_id PK; candidate_id UNIQUE, run FK, JSON and Markdown artifact FKs |
| worker_status | one row; owner ID, heartbeat timestamp, version; informational |
| gdc_attempts | operational GDC ledger: one row per dispatch or cache hit with `request_id` PK, run/logical-query refs, attempt number, method/endpoint, canonical request hash, `RESERVED`/`COMPLETED`/`FAILED`/`CACHE_HIT` status, reserved allowance, charged bytes, HTTP status, response artifact/hash, completeness, error, timestamps. Mutable only through the transport's own ledger functions; the RunEvent stream remains the authority and this table is never a second status source. Every attempt that started reaches a terminal status. |
| gdc_cache | `cache_key` PK (`<contract_version>:<canonical request hash>`) with UNIQUE(request_hash,contract_version) → response artifact, response hash, size, endpoint, completeness, created_at. An entry written under an older contract version stays immutable and can never block storing the current contract's entry for the same request. |
| jev_projections | projection_id PK; run/state refs, projection version, source state hash, projection hash, artifact FK, included-field contract; immutable |
| jev_cache | inference identity PK (`sha256(projection_hash + question_set_hash + pinned model identity + adapter_version)`) → origin evaluation_id; immutable. The identity is only computed for a pinned/versioned model name whose provider resolution equals that name, so a mutable alias is always evaluated by the provider and a divergent resolution is never cached. Routing-policy version is deliberately absent so policy experiments do not rerun inference. |

No generic entity-attribute graph or separate domain database. JSON stores complex serialized payloads; most domain payloads currently decode to dictionaries, not validated scientific records; scalar columns index actual API queries. Add indexes `(run_id,sequence)`, `(created_at,run_id)`, `(run_id,candidate_id)` and state/evaluation hash lookup as needed. All foreign IDs referenced by an event must already exist or be inserted in that event's transaction; schema 4 enforces the provenance chain declared relational constraints so a dangling reference fails the event transaction instead of persisting: `candidates.source_state_id` → `statistical_states`, `candidates.latest_evidence_state_id` and `evidence_states.previous_evidence_state_id` → `evidence_states`, `evidence_states.candidate_id`, `hypotheses.candidate_id`/`evidence_state_id`, `followup_executions.candidate_id`/`output_evidence_state_id` and `jev_evaluations.candidate_id` → `candidates`/`evidence_states`, plus the existing artifact FKs.

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

Artifact publish: serialize canonical bytes to a unique temporary file on the same filesystem, flush/fsync, calculate hash and length, close, atomically rename to final immutable name, then insert artifact metadata plus referring records/event in a SQLite transaction. Artifact identity is deterministic (`uuid5` over relative path + SHA-256), so republishing identical bytes at the same path is a safe retry: it returns the same `artifact_id` without rewriting the file, and a different-bytes collision raises instead of overwriting. Artifact registration is conflict-tolerant (`ON CONFLICT(artifact_id) DO NOTHING`), which recovers a file that exists but whose metadata row was never committed. If the DB commit fails, an orphan file is safe and invisible. If rename fails, publish no record/event. Do not claim SQLite and filesystem are one atomic transaction. On read verify metadata/path confinement and, when scientifically consumed, checksum. Most API and deep baseline reads do so. **Known gap:** `research/dossier.py:run_dossier_stage` reads revision artifacts without supplying the expected checksum and catches read/JSON errors into an empty dictionary. `build_live_dossier` can then label a section OBSERVED from a retained row despite unavailable payload. This is not a verified fail-closed path; fixing it is a discovery-transition blocker. Orphan cleanup is a separate explicit maintenance operation, not deletion on worker startup.

The worker uses an OS-held exclusive file lock (one small cross-platform locking dependency if necessary) for the entire research-process lifetime. A second `run` or `worker` process exits with a clear ownership error before creating a run. Do not infer lock ownership from an old PID or heartbeat. API reads do not hold this lock.

After acquiring the lock, a new owner finds previous PENDING/RUNNING records, commits recovery RUN_STOPPED/INTERRUPTED and candidate dispositions, retaining every old event and artifact. It starts a new run rather than replaying uncertain external requests. FastAPI restart does not alter run status or start research. The UI displays a stale worker heartbeat separately from persisted run status until reconciliation.

Local serving: API binds 127.0.0.1:8000; Next.js uses localhost:3000; CLI/research process runs separately. All point to one absolute `CANCERJEV_DATA_DIR` so differing working directories cannot create accidental databases. Phase 1 needs no keys or provider connectivity. Database connections are process-local; API uses read transactions and does not hold long-lived snapshots across HTTP requests.

Keep the existing `Repository` and `ArtifactStore` narrow; there are no separate RunRepository or EventRepository classes to introduce. No generic storage provider framework is necessary.

## Proposed typed hydration and compatibility (PLANNED)

Stage 1 (2026-09-25) adds standalone scientific `domain/codecs.py` readers and canonical v3 writers;
they are not yet wired into Repository, ArtifactStore, dossier, cache or API consumption. Direct
historical readers preserve original bytes and hash semantics; v3 returns frozen records. SQLite
remains schema 4 and current artifact writers remain v1/v2. The next Stage 2 must wrap those readers
with confined-path, size/byte-hash and relational binding checks. This does not fix the dossier gap
described above. See [contract compatibility](DOMAIN_MODELS.md) and [handoff](STAGE_01_HANDOFF.md).

Keep SQL/JSON as boundary representations. Add named version-dispatching readers for scientifically
consumed states, evidence revisions, cached answers and hypothesis records, returning validated
frozen records or explicit unsupported/corrupt outcomes. `_decode_row` remains a generic SQL
boundary helper, not a scientific parser. Checksums prove byte identity, not schema validity.

Retain schema-1 fixtures and schema-2 live artifacts with explicit readers; the proposed typed
state schema receives a new version. Never reinterpret an unknown version using the fixture
identity path. Database schema 4 and scientific artifact versions are independent. Existing
artifacts are retained, not rewritten in place. See [domain contracts](DOMAIN_MODELS.md),
[review](PYTHON_CORE_REVIEW.md) and [roadmap](DISCOVERY_ROADMAP.md).
