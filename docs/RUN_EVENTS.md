# One canonical RunEvent stream

SQLite `run_events` is the sole event authority. There is no second JSON log store. Human console text is a rendering, not input. Commit an event and its projection changes together, then render the committed event to the CLI. FastAPI returns the same record unchanged.

```text
RunEventV1
  schema_version: 1
  event_id: UUID
  run_id: UUID
  sequence: integer >= 1                    # contiguous per run
  timestamp: UTC RFC3339                    # ordering uses sequence, not clock
  stage: INVENTORY|GDC_FAST_SEARCH|STATE_GENERATION|JEV_WIDE|
         DEEP_ANALYSIS|EVIDENCE_BUILD|JEV_DEEP|HYPOTHESIS_GENERATION|
         HYPOTHESIS_VERIFICATION|FOLLOWUP|DOSSIER|null
  type: registered event discriminator
  level: debug|info|warning|error
  message: string, <= 2,048 UTF-8 bytes       # explanatory only
  candidate_id: UUID|null
  iteration: 0..2|null
  data: typed payload selected by type      # <=65,536 UTF-8 JSON bytes
  artifact_refs: ArtifactRef[], maximum 16
  idempotency_key: string                   # local step identity
```

An additional 96 KiB whole-event cap bounds envelope overhead. Large outputs go to artifacts before commit. Secrets, raw matrices, and full prompts are not event payloads. An unknown type/version is a compatibility error, not silently parsed into status: `domain/events.py` owns `REGISTERED_EVENT_TYPES` (the Phase 1 vocabulary below) and validates `type` and `schema_version` before a sequence is allocated, so a rejected append stores no event and mutates no projection.

Payload families:

| Types | Required payload |
|---|---|
| RUN_CREATED, RUN_STARTED, RUN_COMPLETED, RUN_FAILED, RUN_STOPPED | status, reason_code?, config_ref at creation, final counters and coverage on completion |
| STAGE_STARTED, STAGE_COMPLETED | stage, candidate_id?, iteration?, outcome, elapsed_ms on completion |
| INVENTORY_STARTED/COMPLETED, PROJECT_SCOPE_SELECTED | inventory_ref?, selected_project_ids, cursor_ref, completeness, release identity |
| GDC_REQUEST_STARTED | request_id, logical_query_id, endpoint, attempt_no, request ordinal, reserved bytes, cache=false |
| GDC_REQUEST_COMPLETED/FAILED, GDC_CACHE_HIT | request_id/source_request_id, status, body bytes, response ref?, completeness, latency, totals, reason? |
| GDC_RESPONSE_LIMIT_EXCEEDED, GDC_REQUEST_BUDGET_EXHAUSTED, GDC_RUN_BYTE_BUDGET_EXHAUSTED | resource, configured_limit, consumed, requested, affected query/candidate, disposition |
| WIDE_SCAN_STARTED/COMPLETED, STATISTICAL_STATE_CREATED, PREFILTER_REJECTED, WIDE_STATE_DEFERRED | state refs, lane, counts, validity/selection reason |
| JEV_PROJECTION_CREATED | projection_id, state_id, projection_version, source_state_hash, projection_hash, artifact ref, included-field contract |
| JEV_WIDE_STARTED/COMPLETED, JEV_DEEP_STARTED/COMPLETED | evaluation refs, state count, call count, full-vector summary ref, model, usage, errors |
| JEV_WIDE_STATE_EVALUATED, JEV_EVALUATION_FAILED | evaluation ref, input ref, applicability map, raw judgment vector or fail-closed error, cache source, model |
| WIDE_RANKING_COMPLETED | baseline ranking artifact ref, policy ranking artifact ref, policy version, admitted candidate refs |
| CANDIDATE_PROMOTED | candidate_id, source_state_id, evaluation_id, promotion_slot, policy_version, reason |
| DEEP_ANALYSIS_STARTED/COMPLETED, EVIDENCE_STATE_CREATED | method/action refs, input/output state hashes, observation refs, availability |
| HYPOTHESES_GENERATED, HYPOTHESIS_EVALUATED | hypothesis refs, evidence hash, evaluation refs, usage |
| FOLLOWUP_SELECTED/STARTED/COMPLETED | action/version, execution_id, slot, iteration, input hash, output refs, outcome |
| CANDIDATE_TERMINATED/DEFERRED/FAILED, DOSSIER_CREATED | terminal state, reason, candidate_id, dossier refs when applicable |

Use stage start/completion records for every Phase 1 stage. This resolves the master spec's shorthand list (`INVENTORY`, `FOLLOWUP`, etc.) as stage names rather than a competing event vocabulary. Operation-specific records provide detail; counters are updated only by their designated records, never double-counted by stage completion.

Phase 1 registered the 22-type fixture subset. Phase 2 adds the live GDC families (`INVENTORY_STARTED`, `PROJECT_SCOPE_SELECTED`, `GDC_REQUEST_STARTED/COMPLETED/FAILED`, `GDC_CACHE_HIT`, the three budget-limit types) and Phase 3 adds the Jev families (`JEV_PROJECTION_CREATED`, `JEV_WIDE_STARTED/COMPLETED`, `JEV_WIDE_STATE_EVALUATED`, `JEV_EVALUATION_FAILED`, `WIDE_RANKING_COMPLETED`). `REGISTERED_EVENT_TYPES` is the single source of truth for the exact current set; a test asserts the live and fixture orchestrators emit only registered types, and an unknown type or schema version is rejected before a sequence is allocated. The event schema version stays 1: Phase 2/3 add registered types, not a new envelope. Fixture and live runs share the same vocabulary; the run `mode` distinguishes them, and fixture events continue to carry explicit `FAKE`/`SYNTHETIC` markers.

`domain/runs.py` owns allowed transitions and `domain/events.py` owns payload validation and the reducer. `append_event` starts a short SQLite transaction, validates current state, allocates `last_sequence+1`, inserts the event, applies the reducer and commits. Uniqueness on `(run_id,sequence)`, `event_id`, and `(run_id,idempotency_key)` prevents duplicates. A failed transaction consumes no sequence. An uncertain caller retries with the same idempotency key and receives the existing event.

Scientific artifact/state references and their creation event are registered in that same commit. Status summaries are replaceable projections with `last_sequence`; they are not independent truth. Projection reconstruction is one tested reducer pass, not a generic replay platform. Replaying events never executes providers or follow-ups.

CLI normally renders committed events synchronously. If it crashes after commit, history remains available; a `show --events` command can replay records without rerunning research. Exact-once terminal display is not promised across a console crash.

Incremental API: `GET /api/runs/{id}/events?after_sequence=47&limit=200`. Response: `{items, next_after_sequence, has_more, run_last_sequence}`. Limit 1..500 and maximum serialized page size 1 MiB; fetch stops before the byte limit and returns a continuation. `next_after_sequence` equals the last returned sequence or the input cursor for an empty page. Read items and high-water sequence in a single read transaction.

The UI deduplicates by event_id, orders by sequence, and fetches the next page immediately when `has_more`. It does not advance its cursor past data it has not received. Terminal-state polling stops only after draining events through the observed terminal sequence. There is no event-history truncation analogous to CancerHawk's capped event array.
