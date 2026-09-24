# FastAPI contract, version 2

Stage 2: state/evidence details validate scientific versions, identity and record/artifact bindings
in addition to byte hashes. Dossier reads validate authoritative revision references. Unavailable
or corrupt authoritative content returns 503; successful payloads and ETags are unchanged.
No frontend changes or frontend rendering acceptance are included.

All routes are local read APIs. JSON serialization is strict (no NaN/Infinity). `/api/system` reports provider/configuration flags and local runtime metadata, never secrets. Its current `phase: 3` and `providers.llm: false` values are hard-coded and stale relative to implemented deep/OpenRouter paths; they are not authoritative capability discovery. CORS allows only the configured local web origin; bind to loopback. No account/auth/RBAC system is needed for this local slice. No route performs a GDC or Jev call; research runs remain CLI/worker-owned.

List envelope: `{items:[...], next_cursor:string|null, has_more:boolean}`. Opaque cursor binds ordering/filter; keyset ordering avoids skipped/duplicated rows when new runs appear. Run/dossier feed defaults 20, max100. Child lists default100, max200. UUID path parameters and numeric bounds are validated; SQL is parameterized. Cursor decoding checks structure and filter binding, but does not fully enforce all decoded field types or input lengths. Strict cursor boundary validation is planned; do not describe it as complete. Unknown ID=404, malformed request=422. Error envelope `{error:{code,message,request_id}}` for every error, including FastAPI request-validation failures (bad UUID, out-of-range limit, bad cursor) which use code `VALIDATION_ERROR`; 503 for unavailable storage, not an empty successful list. No stack traces/secrets in responses.

| Method/path | Parameters | Response |
|---|---|---|
| GET `/health` | none | `{status:"ok",schema_version:4}` if DB readable; 503 otherwise; does not claim worker healthy; `Cache-Control: no-store` |
| GET `/api/system` | none | worker heartbeat/freshness, active run id, mode, hard-coded provider flags, data sizes, configured GDC budget defaults, cursor-absent explanation, GDC cache entries/bytes and Jev entry count, API/schema/worker versions; no hit-rate field |
| GET `/api/runs` | cursor?, limit?, status? | RunSummary list, descending `(created_at,run_id)`; no embedded event arrays |
| GET `/api/runs/{run_id}` | UUID | ResearchRun projection, last_sequence, stage occurrences, embedded candidate rows and budget/usage snapshots |
| GET `/api/runs/{run_id}/events` | after_sequence>=0 default0, limit1..500 default200 | `{items:RunEvent[],next_after_sequence,has_more,run_last_sequence}` with <=1MiB page; ascending sequences |
| GET `/api/runs/{run_id}/candidates` | cursor?, limit? | CandidateInvestigation summaries with evidence/dossier refs |
| GET `/api/runs/{run_id}/states` | cursor?, limit?, disposition? | StatisticalState v2 summaries: entity, mutation counts and coverage, local/provider expression summaries, missingness, source refs |
| GET `/api/states/{state_id}` | UUID | Full immutable StatisticalState v2 artifact with its `state_hash`, method refs and source request refs; 404 if absent; 503 if the artifact is missing or corrupt |
| GET `/api/runs/{run_id}/projections` | cursor?, limit? | Versioned JevStateProjection rows: projection version, source state hash, projection hash, included-field contract, artifact ref |
| GET `/api/runs/{run_id}/rankings` | none | Object with `baseline` and `jev`, each a WideRanking or null; artifacts include policy version, ordered entries, raw dimensions and admitted candidate ids |
| GET `/api/runs/{run_id}/evaluations` | cursor?, limit?, candidate_id?, purpose? | JevEvaluation summary/full compact vector with an explicit `input_ref_kind` (`STATISTICAL_STATE`/`EVIDENCE_STATE`/`HYPOTHESIS`) plus `input_ref_id`, applicability, mode, requested/resolved model, question-set version/hash, projection ref, usage, latency, cache provenance, error state; `purpose=DEEP` returns evidence-revision judgments (`deep-v1`) and `purpose=WIDE` the wide state judgments |
| GET `/api/runs/{run_id}/hypotheses` | cursor?, limit?, candidate_id? | Hypotheses with evidence/evaluation references and clearly marked generated content |
| GET `/api/runs/{run_id}/evidence` | cursor?, limit?, candidate_id? | EvidenceState revision summaries (iteration, parent revision, `evidence_hash`, action, check counts) ordered by creation |
| GET `/api/evidence/{evidence_state_id}` | UUID | Full immutable EvidenceState artifact (schema 2 live contract) with its artifact hash headers; 404 if absent; 503 if the artifact is missing or corrupt |
| GET `/api/runs/{run_id}/followups` | cursor?, limit?, candidate_id?, status? | FollowUpExecution records (action id/version, input evidence hash, output evidence revision, status, outcome, error) |
| GET `/api/runs/{run_id}/dossiers` | cursor?, limit? | Dossier summary list, because a run can have multiple candidate dossiers |
| GET `/api/dossiers` | cursor?, limit? | Archive summaries with run/candidate/mode |
| GET `/api/dossiers/{dossier_id}` | format=json(default) or markdown | Authoritative structured dossier or derived text/markdown, with artifact hash |
| GET `/api/artifacts/{artifact_id}` | UUID | Approved JSON/Markdown artifact (other media types return 404); no arbitrary path traversal, raw secrets or huge provider payload UI |

RunSummary includes status, stage, start/end/elapsed, projects attempted/completed, actual GDC requests/bytes, states generated/valid/evaluated, admitted candidates, Jev/LLM calls/tokens/cost (nullable), hypotheses, follow-ups, dossier count, mode (`FAKE`/`LIVE`), coverage, last_sequence. Elapsed time freezes at ended_at. Zero usage is meaningful in fake mode; unknown live usage stays null. The states list distinguishes `OBSERVED`/`PARTIAL`/`NOT_OBSERVED`/`NOT_ACQUIRED` explicitly; a `NOT_OBSERVED` mutation count is never rendered as zero. Jev judgments are returned only in evaluation records and never merged into state or evidence fields.

Mutation/start routes remain deliberately omitted: live research runs are started only from the CLI/worker, never over HTTP. Optional later `POST /api/runs/{id}/stop` returns 202 `{stop_requested:true}` for active runs, is idempotent, and only sets a control flag. The worker emits canonical stop-request/terminal events at safe boundaries. A terminal run returns 409. This is a deferred convenience; today Ctrl+C in the research terminal is the stop mechanism.

All live-status responses use `Cache-Control: no-store` (`/health` included); immutable artifacts may use their hash as ETag. Dossier, state and evidence detail responses expose `X-Artifact-Id`, `X-Artifact-SHA256` and `ETag`; the generic artifact route currently exposes only `ETag`, and the CORS middleware lists them in `Access-Control-Expose-Headers` so browser JavaScript on the configured web origin can read the provenance values. Run projection and `last_sequence` are read consistently; events expose a high-water mark. UI can tolerate a newer event page than summary and refresh the summary, without independently executing state transitions.

The Python routes are the current read contract. This documentation pass did not inspect or modify frontend code and makes no new claim of frontend schema parity. Do not add another API proxy/business backend in Next.js. No SSE or WebSocket routes.

The dictionary list/detail response is a justified serialization boundary, not the proposed internal
scientific domain representation. Typed/versioned hydration and truthful dossier section availability
are planned in [domain models](DOMAIN_MODELS.md) and [roadmap](DISCOVERY_ROADMAP.md); this pass
changes no API behavior. Model-call counters count logical provider invocations, not SDK HTTP retries.
