# FastAPI contract

IMPLEMENTED read API for the current typed architecture (current API version in
[REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)). All routes are local read APIs. JSON
serialization is strict (no NaN/Infinity). No route performs a GDC or Jev call; research runs
remain CLI/worker-owned, and research state is never written through FastAPI.

`apps/api/serializers.py` owns the presentation boundary: internal scientific models stay
canonical typed objects and browser-facing payloads are derived there. Presentation payloads
declare the current versioned `schema_version` (`STATISTICAL_STATE_PRESENTATION` /
`EVIDENCE_STATE_PRESENTATION`; version in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)).
Source artifact identity is reported separately from the response ETag so a presentation change
cannot masquerade as an evidence change:

- `/api/states/{state_id}` and `/api/evidence/{state_id}`: `ETag` is the SHA-256 of the actual
  response bytes; `X-Artifact-Id` and `X-Artifact-SHA256` retain the source artifact identity.
- `/api/dossiers/{dossier_id}`: `ETag`, `X-Artifact-Id` and `X-Artifact-SHA256` are the
  authoritative artifact identity.
- The generic `/api/artifacts/{artifact_id}` route currently exposes only `ETag`
  (PLANNED improvement, not a correctness defect).

`/api/system` reports the current SQLite schema version, `mode: LIVE_AND_FIXTURE`, provider flags
derived from the environment (`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`), worker heartbeat, active
run, data
sizes, configured GDC budget defaults, cache counts and
`versions: {api, schema, worker}`. It never reports secrets. Two labels are stale
runtime metadata, not capability discovery: the `phase: 3` field and the cursor reason text
mentioning “Phase 2 bounded sweeps”. `apps/api/main.py` still carries the historical FastAPI
title/OpenAPI version; OpenAPI metadata cleanup is PLANNED.

List envelope: `{items:[...], next_cursor:string|null, has_more:boolean}`. Opaque cursor binds
ordering/filter; keyset ordering avoids skipped/duplicated rows when new runs appear. Run/dossier
feed defaults 20, max 100. Child lists default 100, max 200. UUID path parameters and numeric
bounds are validated; SQL is parameterized. Cursor decoding checks structure and filter binding
but does not fully enforce every decoded scalar type/length; strict cursor boundary validation is
PLANNED. Unknown ID = 404, malformed request = 422. Error envelope
`{error:{code,message,request_id}}` for every error, including FastAPI request-validation
failures (code `VALIDATION_ERROR`); 503 for unavailable storage, never an empty successful list.
No stack traces or secrets in responses. Undeclared query parameters are silently ignored by
FastAPI (PLANNED strict parameter handling); do not mistake them for working filters.

| Method/path | Parameters | Response |
|---|---|---|
| GET `/health` | none | `{status:"ok",schema_version:<current>}` if the DB is readable; 503 otherwise; does not claim the worker is healthy; `Cache-Control: no-store` |
| GET `/api/system` | none | worker heartbeat/freshness, active run id, mode, environment-derived provider flags, data sizes, configured GDC budget defaults, cursor explanation, GDC cache entries/bytes and Jev entry count, API/schema/worker versions |
| GET `/api/runs` | cursor?, limit?, status? | RunSummary list, descending `(created_at,run_id)`; no embedded event arrays |
| GET `/api/runs/{run_id}` | UUID | ResearchRun projection, last_sequence, stage occurrences, embedded candidate rows and budget/usage snapshots |
| GET `/api/runs/{run_id}/events` | after_sequence>=0 default 0, limit 1..500 default 200 | `{items:RunEvent[],next_after_sequence,has_more,run_last_sequence}` with ≤1 MiB page; ascending sequences |
| GET `/api/runs/{run_id}/candidates` | cursor?, limit? | CandidateInvestigation summaries with evidence/dossier refs |
| GET `/api/runs/{run_id}/states` | cursor?, limit?, disposition? | Stored StatisticalState summary rows: entity, mode, mutation/expression availability, projects observed, affected-case total and top-project share, coverage imbalance, completeness, artifact id/hash |
| GET `/api/states/{state_id}` | UUID | Presentation payload for one immutable StatisticalState artifact with `state_hash`, method refs and source request refs; 404 if absent; 503 if the artifact is missing or corrupt |
| GET `/api/runs/{run_id}/projections` | cursor?, limit? | Versioned Jev projection rows: projection version, source state hash, projection hash, included-field contract, artifact ref |
| GET `/api/runs/{run_id}/rankings` | none | Object with `baseline` and `jev`, each a WideRanking or null; artifacts include policy version, ordered entries, raw dimensions and admitted candidate ids |
| GET `/api/runs/{run_id}/evaluations` | cursor?, limit?, candidate_id?, purpose? | Jev evaluation summary/compact vector with explicit `input_ref_kind` (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`) plus `input_ref_id`, applicability, mode, requested/resolved model, question-set version/hash, projection ref, usage, latency, cache provenance, error state; `purpose=DEEP` returns evidence-revision judgments (`deep-v1`) and `purpose=WIDE` the wide state judgments (`wide-v3`) |
| GET `/api/runs/{run_id}/hypotheses` | cursor?, limit?, candidate_id? | Hypotheses with evidence/evaluation references and clearly marked generated content |
| GET `/api/runs/{run_id}/evidence` | cursor?, limit?, candidate_id? | EvidenceState revision summaries (iteration, parent revision, `evidence_hash`, action, check counts) ordered by creation |
| GET `/api/evidence/{evidence_state_id}` | UUID | Presentation payload for one immutable EvidenceState artifact with its source artifact identity headers; 404 if absent; 503 if the artifact is missing or corrupt |
| GET `/api/runs/{run_id}/followups` | cursor?, limit?, candidate_id?, status? | FollowUpExecution records (action id/version, input evidence hash, output evidence revision, status, outcome, error) |
| GET `/api/runs/{run_id}/dossiers` | cursor?, limit? | Dossier summary list, because a run can have multiple candidate dossiers |
| GET `/api/dossiers` | cursor?, limit? | Archive summaries with run/candidate/mode |
| GET `/api/dossiers/{dossier_id}` | format=json(default) or markdown | Authoritative structured dossier or derived text/markdown, with artifact hash |
| GET `/api/artifacts/{artifact_id}` | UUID | Approved JSON/Markdown artifact (other media types return 404); no arbitrary path traversal, raw secrets or provider payload dumps |

RunSummary includes status, stage, start/end/elapsed, projects attempted/completed, actual GDC
requests/bytes, states generated/valid/evaluated, admitted candidates, Jev/LLM calls/tokens/cost
(nullable), hypotheses, follow-ups, dossier count, mode (`FIXTURE`/`LIVE`), coverage and
last_sequence. Elapsed time freezes at `ended_at`. Zero usage is meaningful in fixture mode;
unknown live usage stays null. The states list distinguishes `OBSERVED`/`PARTIAL`/`NOT_OBSERVED`/
`NOT_ACQUIRED` explicitly; a `NOT_OBSERVED` mutation count is never rendered as zero. Jev
judgments are returned only in evaluation records and never merged into state or evidence fields.

Mutation/start routes remain deliberately omitted: live research runs are started only from the
CLI/worker, never over HTTP. An optional later `POST /api/runs/{id}/stop` returns 202
`{stop_requested:true}` for active runs, is idempotent and only sets a control flag; a terminal
run returns 409. This is deferred; today Ctrl+C in the research terminal is the stop mechanism.

All live-status responses use `Cache-Control: no-store` (`/health` included). Dossier, state and
evidence detail responses expose `X-Artifact-Id`, `X-Artifact-SHA256` and `ETag`; the CORS
middleware lists them in `Access-Control-Expose-Headers` so browser JavaScript on the configured
web origin can read the provenance values. Run projection and `last_sequence` are read
consistently; events expose a high-water mark. The UI tolerates a newer event page than the
summary and refreshes the summary without independently executing state transitions.

The Python routes are the current read contract. `apps/web/` is presentation-only and outside the
research runtime: this document does not audit or change frontend code and makes no
frontend schema-parity claim. Do not add another API proxy/business backend in Next.js. No SSE
or WebSocket routes.

Model-call counters count logical provider invocations. TypeSafe SDK retries are explicitly
disabled (`RetryPolicy(max_retries=0)`), so one logical evaluation corresponds to at most one
HTTP attempt. A total paid-model spend gate is still absent (PLANNED).