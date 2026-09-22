# Phase 1 implementation status

**DONE:** Phase 0 design, Phase 1 offline synthetic vertical slice, independent audit, and the Phase 1 repair pass. **CURRENT:** locally verified Phase 1 baseline (persistence schema v2). **NEXT:** nothing without explicit Phase 2 approval.

## What exists

- One Python research process with an OS-held cross-platform exclusive lock.
- Typed local configuration and idempotent SQLite bootstrap using WAL, foreign keys, a 5-second busy timeout, FULL synchronous research writes, a single `UNIQUE` schema-version row, and explicit `BEFORE UPDATE`/`BEFORE DELETE` triggers for the eight immutable tables.
- One authoritative `append_event` path: registered-type and schema-version validation, contiguous sequence allocation, idempotency, event insert, projection reduction and commit occur in one short transaction. An unknown event type or version is rejected before a sequence is allocated.
- Immutable artifacts published through temporary file, flush/fsync, SHA-256 and atomic rename before database registration, with deterministic artifact identity (`uuid5` of path + hash) so retries and crash recovery cannot invent a duplicate identity.
- Explicit scientific identity projections (`statistical_state_identity_payload`, `evidence_state_identity_payload`) so equivalent fixture science hashes identically across runs; artifact byte SHA-256 remains a separate exact-bytes hash.
- A deterministic `demo` fixture with 12 synthetic StatisticalStates, varied patterns, contract-valid Noul/Choice/Score shapes (Choice options from the question roster; Score on the 0..4 rubric with legend and expected value), two candidate branches, deep evidence, two competing hypotheses, independent reviews, one registered follow-up and a 25-section dossier.
- CLI `run --fixture demo`, `worker --fixture demo`, and `show <run_id> [--events]` commands; the summary is machine-readable JSON.
- Read-only FastAPI routes with incremental bounded event pages, opaque keyset cursors for runs, dossiers and child lists (with `disposition`, `candidate_id`, `purpose` filters), one error envelope for handler and request-validation failures, `Cache-Control: no-store` on `/health` and `/api/*`, CORS-exposed provenance headers, and explicit `input_ref_kind`/`input_ref_id` on evaluations.
- Next.js 16 App Router routes `/`, `/runs`, `/runs/[runId]`, `/dossiers`, `/dossiers/[dossierId]`, and `/system`, with single-flight polling, bounded backoff, hidden-tab pause, stale-data retention, explicit outage state, budget/usage summaries, typed bounded event details with unknown markers, candidate/iteration event filters, run-scoped state remount on route change, cursor "load more" for runs and dossiers, grouped dossier views with provenance and JSON/Markdown downloads, and durable history.
- Offline Python tests including CLI/API/store event identity, registered-vocabulary enforcement, scientific-hash stability and sensitivity, immutability triggers, bootstrap concurrency, artifact republish/idempotency, cross-process ownership, interrupted-run reconciliation, and Playwright browser acceptance with a deterministic live-progress design.

## Repair history (2026-09-22)

The committed revision `8a3149c` was independently audited and **failed** Phase 1 verification: 1 blocker, 5 major, 13 minor findings (`docs/PHASE_1_VERIFICATION.md` records that audit; it is preserved, not rewritten). The repair pass fixed every actionable finding:

- **B1** browser acceptance was timing-racy (it waited on the 8-second `/runs` feed while the fixture finished in ~7.5 s). The test now discovers the run through the API, asserts the autonomous card separately, opens the detail page while active with a 2.5 s stage delay, and additionally checks auto-follow, refresh-during-run, and terminal drain.
- **M1** the artifact path-confinement test was Windows-specific; it now uses platform-neutral traversal/absolute cases plus Windows-only drive/UNC cases and passes on Linux.
- **M2/N9** dossier provenance headers were invisible to browser JavaScript; CORS now exposes `ETag`, `X-Artifact-Id` and `X-Artifact-SHA256`, and the browser test asserts a real 64-hex digest matching the served response instead of the word "sha256".
- **M3** unknown RunEvent types/schema versions are now rejected by `REGISTERED_EVENT_TYPES` and a `schema_version` validator before any sequence is consumed.
- **M4** content hashes no longer include operational UUIDs; equivalent fixture content hashes identically across runs and changes when scientific inputs, units, membership, methods or limitations change.
- **N1–N13** validation errors use the documented envelope; `/health` is `no-store`; the heartbeat keeps a stable process worker ID instead of a run ID; fixture Jev vectors satisfy their own Choice/Score contracts; CLI `show` emits JSON; the dossier-archive cursor chain stays exhausted; the run feed paginates; run-scoped state resets on route change; SQLite immutability triggers exist; bootstrap closes its connection and cannot duplicate the schema row; artifact republish is idempotent; `jev_evaluations` uses explicit input reference kind/id.
- **O1–O4** were resolved explicitly: bounded Python ranges without a lockfile are accepted Phase 1 policy; the committed Next.js `AGENTS.md`/`CLAUDE.md` pointers are intentional; `/api/runs/{run_id}` legitimately embeds candidate rows and API_CONTRACT now says so; React StrictMode development duplicate polls are accepted (production is single-flight).

The stale local `data/cancerjev.db` from the pre-repair revision (schema 1) was deleted; schema 2 intentionally does not migrate older Phase 1 data directories.

## Verification record — 2026-09-22 (repair)

Commands executed from the repository root unless noted. Results are from the repaired working tree.

| Gate | Command | Result |
|---|---|---|
| Python lint (Windows) | `python -m ruff check cancerjev apps tests` | All checks passed |
| Python tests (Windows, Python 3.14.3) | `CANCERJEV_FIXTURE_STAGE_DELAY_MS=0 python -m pytest` | 43 passed, 0 failed, 0 errors, 0 skipped (19.8 s; junit XML) |
| Python lint (Linux) | `python -m ruff check cancerjev apps tests` | All checks passed |
| Python tests (WSL Ubuntu, Python 3.11.15) | `CANCERJEV_FIXTURE_STAGE_DELAY_MS=0 python -m pytest` | 43 passed, 0 failed, 0 errors, 0 skipped (10.8 s; junit XML) |
| Frontend install | `npm ci` (in `apps/web`) | 0 vulnerabilities |
| Frontend typecheck | `npm run typecheck` | Passed |
| Frontend build | `npm run build` | Passed; all application routes built |
| Browser acceptance | `npm run test:e2e` (API `127.0.0.1:8100`, web `127.0.0.1:3100`) | 4 passed on four consecutive runs: 45.3 s, 44.9 s, 45.0 s, and 48.1 s after reinstalling `node_modules` |
| Browser pagination probe | `/runs` and `/dossiers` with 23 runs/dossiers | 20 cards → "Load more" → 23 unique cards, control removed and not resurrected after a poll cycle |
| CORS provenance probe | `fetch` from the web origin | `X-Artifact-Id` UUID, 64-hex `X-Artifact-SHA256` and `ETag` readable in the browser |

Verified browser observations during the acceptance run: the autonomous run card appears in `/runs`; the detail page is opened while active and observes at least two nonterminal stages (`JEV_WIDE`, `FOLLOWUP`); events append incrementally; scrolling up is not force-scrolled and the new-events control appears; a mid-run refresh reconstructs history and resumes polling; the terminal summary drains to all 71 events; the dossier shows the synthetic framing, a real artifact id and digest; the CLI `show --events` event IDs equal the API-served IDs.

Not executed locally: the hosted GitHub Actions run (no runner available in this environment) and the exact Python 3.12 / Node 22 combination of the CI jobs. The same commands passed locally on Python 3.14.3 (Windows), Python 3.11.15 (Linux) and Node 24.13.1. **UNVERIFIED:** hosted CI status.

## Provider-use record

- GDC = 0
- Jev / TypeSafe = 0
- LLM / OpenRouter = 0

Normal project dependencies were downloaded. No provider credential was read or required. Fixture mode remains offline even if provider-like environment variables exist. Application code contains no provider SDK, provider URL or HTTP client.

## Intentional exclusions

No real GDC client, cache, request-attempt ledger, file download, Jev adapter, LLM adapter, scientific production method, correction-family execution, discovery cursor traversal, deployment integration, queue, lease, fencing, replay, WebSocket, SSE, account system, PostgreSQL, Redis or Docker support exists.

## Known limitations

- Phase 1 is an execution/observability proof, not a scientific result or provider integration test.
- Worker scheduling is a simple sleep loop; there is no calendar scheduling or catch-up.
- SQLite and filesystem publication are ordered, not atomically unified; an orphan file after database failure is acceptable and invisible.
- Read API authentication is intentionally absent because the process binds locally.
- Browser acceptance uses synthetic timing with no scientific meaning. Its run-scoped-state test forces an in-app transition with the Next.js development client router, so it requires the dev server; the same invariant is additionally guaranteed structurally by remounting the run detail component per routed run.
- Persistence schema 2 does not migrate schema 1 Phase 1 data directories; they must be moved or deleted.
- Local verification used Python 3.14.3 and Node.js 24.13.1 plus a Linux cross-check on Python 3.11.15; CI pins supported Python 3.12 and Node.js 22 and was not executed locally.

## Deviations and corrections from Phase 0

- The singular `/api/runs/{run_id}/dossier` design typo was corrected to plural `/dossiers`, as approved.
- Only the required Phase 1 subset of broader domain models/tables is implemented. Future GDC/scientific fields remain contracts, not fake runtime complexity.
- Simulated Jev evaluations are counted independently from provider usage so the UI shows fixture judgment activity while truthfully reporting zero Jev calls.
- Child-list cursor/filter parameters and `/api/system` configuration fields from API_CONTRACT are implemented. Phase 2-only values (live budget caps, discovery cursor, GDC cache) are reported as explicit null/absent with reasons rather than invented data.
- Provider usage carries nullable token/cost fields; fixture mode leaves them null so cost renders as “unknown”, never a fabricated zero.
- Dossier JSON and Markdown responses expose the artifact ID and SHA-256 in headers; CORS exposes those headers and the web dossier view renders the served digest as provenance (verified in the browser).
- The exact Phase 1 detail-event vocabulary is recorded in RUN_EVENTS.md and enforced by `REGISTERED_EVENT_TYPES`.
- Next.js 16.3 generated a nested `apps/web/AGENTS.md` pointer to bundled version-matched documentation during the verified dev run; it does not alter runtime architecture.
- The `workers: 1` Playwright setting keeps the acceptance suite deterministic because the tests spawn real research processes against one shared data directory.

## Phase 2 boundary and recommendation

Do not begin Phase 2 without explicit approval. If approved later, first implement bounded public GDC transport and its attempt/budget ledger with live captures and transport-cap tests. Real Jev/LLM integration and production scientific methods should remain subsequent separately gated work.
