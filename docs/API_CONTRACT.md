# FastAPI contract, version 2

All routes are local read APIs. JSON serialization is strict (no NaN/Infinity). `/api/system` reports provider mode/configuration booleans and redacted model names, never secrets. CORS allows only the configured local web origin; bind to loopback. No account/auth/RBAC system is needed for this local slice. No route performs a GDC or Jev call; research runs remain CLI/worker-owned.

List envelope: `{items:[...], next_cursor:string|null, has_more:boolean}`. Opaque cursor binds ordering/filter; keyset ordering avoids skipped/duplicated rows when new runs appear. Run/dossier feed defaults 20, max100. Child lists default100, max200. Validate lengths and IDs; use parameterized SQL. Unknown ID=404, malformed request=422. Error envelope `{error:{code,message,request_id}}` for every error, including FastAPI request-validation failures (bad UUID, out-of-range limit, bad cursor) which use code `VALIDATION_ERROR`; 503 for unavailable storage, not an empty successful list. No stack traces/secrets in responses.

| Method/path | Parameters | Response |
|---|---|---|
| GET `/health` | none | `{status:"ok",schema_version:4}` if DB readable; 503 otherwise; does not claim worker healthy; `Cache-Control: no-store` |
| GET `/api/system` | none | worker heartbeat/freshness, active run, live/fixture modes, effective budget defaults and limits, cursor summary, cache stats (entries, bytes, hit rate), versions; secret values omitted |
| GET `/api/runs` | cursor?, limit?, status? | RunSummary list, descending `(created_at,run_id)`; no embedded event arrays |
| GET `/api/runs/{run_id}` | UUID | ResearchRun projection, last_sequence, stage occurrences, embedded candidate rows and budget/usage snapshots |
| GET `/api/runs/{run_id}/events` | after_sequence>=0 default0, limit1..500 default200 | `{items:RunEvent[],next_after_sequence,has_more,run_last_sequence}` with <=1MiB page; ascending sequences |
| GET `/api/runs/{run_id}/candidates` | cursor?, limit? | CandidateInvestigation summaries with evidence/dossier refs |
| GET `/api/runs/{run_id}/states` | cursor?, limit?, disposition? | StatisticalState v2 summaries: entity, mutation counts and coverage, local/provider expression summaries, missingness, source refs |
| GET `/api/states/{state_id}` | UUID | Full immutable StatisticalState v2 artifact with its `state_hash`, method refs and source request refs; 404 if absent; 503 if the artifact is missing or corrupt |
| GET `/api/runs/{run_id}/projections` | cursor?, limit? | Versioned JevStateProjection rows: projection version, source state hash, projection hash, included-field contract, artifact ref |
| GET `/api/runs/{run_id}/rankings` | none | `{baseline: WideRanking|null, jev: WideRanking|null}` computed artifacts for the run; each with policy version, ordered entries, raw dimensions and admitted candidate ids |
| GET `/api/runs/{run_id}/evaluations` | cursor?, limit?, candidate_id?, purpose? | JevEvaluation summary/full compact vector with an explicit `input_ref_kind` (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`) plus `input_ref_id`, applicability, mode, requested/resolved model, question-set version/hash, projection ref, usage, latency, cache provenance, error state |
| GET `/api/runs/{run_id}/hypotheses` | cursor?, limit?, candidate_id? | Hypotheses with evidence/evaluation references and clearly marked generated content |
| GET `/api/runs/{run_id}/dossiers` | cursor?, limit? | Dossier summary list, because a run can have multiple candidate dossiers |
| GET `/api/dossiers` | cursor?, limit? | Archive summaries with run/candidate/mode |
| GET `/api/dossiers/{dossier_id}` | format=json(default) or markdown | Authoritative structured dossier or derived text/markdown, with artifact hash |
| GET `/api/artifacts/{artifact_id}` | UUID | Bounded approved JSON/Markdown/table artifact; no arbitrary path traversal, raw secrets or huge provider payload UI |

RunSummary includes status, stage, start/end/elapsed, projects attempted/completed, actual GDC requests/bytes, states generated/valid/evaluated, admitted candidates, Jev/LLM calls/tokens/cost (nullable), hypotheses, follow-ups, dossier count, mode (`FAKE`/`LIVE`), coverage, last_sequence. Elapsed time freezes at ended_at. Zero usage is meaningful in fake mode; unknown live usage stays null. The states list distinguishes `OBSERVED`/`PARTIAL`/`NOT_OBSERVED`/`NOT_ACQUIRED` explicitly; a `NOT_OBSERVED` mutation count is never rendered as zero. Jev judgments are returned only in evaluation records and never merged into state or evidence fields.

Mutation/start routes remain deliberately omitted: live research runs are started only from the CLI/worker, never over HTTP. Optional later `POST /api/runs/{id}/stop` returns 202 `{stop_requested:true}` for active runs, is idempotent, and only sets a control flag. The worker emits canonical stop-request/terminal events at safe boundaries. A terminal run returns 409. This is a deferred convenience; today Ctrl+C in the research terminal is the stop mechanism.

All live-status responses use `Cache-Control: no-store` (`/health` included); immutable artifacts may use their hash as ETag. Dossier and artifact responses expose `X-Artifact-Id`, `X-Artifact-SHA256` and `ETag`, and the CORS middleware lists them in `Access-Control-Expose-Headers` so browser JavaScript on the configured web origin can read the provenance values. Run projection and `last_sequence` are read consistently; events expose a high-water mark. UI can tolerate a newer event page than summary and refresh the summary, without independently executing state transitions.

API schema is authoritative for TypeScript contracts. The small manually mirrored type file (`apps/web/lib/types.ts`) is checked against schema fixtures rather than generating a client; prefer the simpler verified option. Do not add another API proxy/business backend in Next.js. No SSE or WebSocket routes.
