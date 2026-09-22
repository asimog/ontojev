# Phase 1 implementation status

**DONE:** Phase 0 design and Phase 1 offline synthetic vertical slice. **CURRENT:** verified local Phase 1 baseline. **NEXT:** nothing without explicit Phase 2 approval.

## What exists

- One Python research process with an OS-held cross-platform exclusive lock.
- Typed local configuration and idempotent SQLite bootstrap using WAL, foreign keys, a 5-second busy timeout, and FULL synchronous research writes.
- One authoritative `append_event` path: validation, contiguous sequence allocation, idempotency, event insert, projection reduction and commit occur in one short transaction.
- Immutable artifacts published through temporary file, flush/fsync, SHA-256 and atomic rename before database registration.
- A deterministic `demo` fixture with 12 synthetic StatisticalStates, varied patterns, full Noul/Choice/Score shapes, two candidate branches, deep evidence, two competing hypotheses, independent reviews, one registered follow-up and a 25-section dossier.
- CLI `run --fixture demo`, `worker --fixture demo`, and `show <run_id> --events` commands.
- Read-only FastAPI routes with incremental bounded event pages, opaque keyset cursors for runs, dossiers and child lists (with `disposition`, `candidate_id`, `purpose` filters), strict error envelopes, and artifact SHA-256 headers on dossier responses.
- Next.js 16 App Router routes `/`, `/runs`, `/runs/[runId]`, `/dossiers`, `/dossiers/[dossierId]`, and `/system`, with single-flight polling, bounded backoff, hidden-tab pause, stale-data retention, explicit outage state, budget/usage summaries, typed bounded event details with unknown markers, candidate/iteration event filters, grouped dossier views with provenance and JSON/Markdown downloads, and durable history.
- Offline Python tests including a CLI/API/store event-identity test, Playwright browser acceptance, and GitHub Actions gates.

## Verification record — 2026-09-22

Final full-gate rerun on the committed revision:

- Ruff passed.
- Pytest: 13 passed; one Python 3.14/pytest temporary-symlink cleanup warning occurred after success.
- `npm ci`: 0 vulnerabilities.
- TypeScript passed.
- Next.js 16.3.5 production build passed; all application routes built.
- Playwright acceptance: 1 passed in 17.5 seconds. The browser test observes two nonterminal stages, incremental event growth, budget summary, typed event details, Jev vectors, hypotheses, follow-up, completion, dossier provenance and downloads, refresh persistence, and asserts that CLI `show --events` event IDs equal the API-served event IDs for the same run.
- Browser visual check: meaningful content/navigation/synthetic framing rendered with no Next.js error overlay.
- Manual CLI demo: sequences 1–71 committed from `RUN_CREATED` through `RUN_COMPLETED`; the UI observed multiple nonterminal stages.
- API restart/stale-data probe: cards stayed visible during outage, the last-updated warning appeared, and restart restored polling from the same SQLite data.

## Provider-use record

- GDC = 0
- Jev / TypeSafe = 0
- LLM / OpenRouter = 0

Normal project dependencies were downloaded. No provider credential was read or required. Fixture mode remains offline even if provider-like environment variables exist.

## Intentional exclusions

No real GDC client, cache, request-attempt ledger, file download, Jev adapter, LLM adapter, scientific production method, correction-family execution, discovery cursor traversal, deployment integration, queue, lease, fencing, replay, WebSocket, SSE, account system, PostgreSQL, Redis or Docker support exists.

## Known limitations

- Phase 1 is an execution/observability proof, not a scientific result or provider integration test.
- Worker scheduling is a simple sleep loop; there is no calendar scheduling or catch-up.
- SQLite and filesystem publication are ordered, not atomically unified; an orphan file after database failure is acceptable and invisible.
- Read API authentication is intentionally absent because the process binds locally.
- Browser acceptance uses synthetic timing with no scientific meaning.
- Local verification used Python 3.14.3 and Node.js 24.13.1; CI pins supported Python 3.12 and Node.js 22.

## Deviations and corrections from Phase 0

- The singular `/api/runs/{run_id}/dossier` design typo was corrected to plural `/dossiers`, as approved.
- Only the required Phase 1 subset of broader domain models/tables is implemented. Future GDC/scientific fields remain contracts, not fake runtime complexity.
- Simulated Jev evaluations are counted independently from provider usage so the UI shows fixture judgment activity while truthfully reporting zero Jev calls.
- Child-list cursor/filter parameters and `/api/system` configuration fields from API_CONTRACT are implemented. Phase 2-only values (live budget caps, discovery cursor, GDC cache) are reported as explicit null/absent with reasons rather than invented data.
- Provider usage carries nullable token/cost fields; fixture mode leaves them null so cost renders as “unknown”, never a fabricated zero.
- Dossier JSON and Markdown responses expose the artifact ID and SHA-256 in headers; the web dossier view renders them as provenance alongside evidence and hypothesis references.
- The exact Phase 1 detail-event vocabulary (`JEV_WIDE_STATE_EVALUATED`, `EVIDENCE_BUILD_COMPLETED`, `JEV_DEEP_COMPLETED`, and the rest) is now recorded in RUN_EVENTS.md.
- Next.js 16.3 generated a nested `apps/web/AGENTS.md` pointer to bundled version-matched documentation during the verified dev run; it does not alter runtime architecture.

## Phase 2 boundary and recommendation

Do not begin Phase 2 without explicit approval. If approved later, first implement bounded public GDC transport and its attempt/budget ledger with live captures and transport-cap tests. Real Jev/LLM integration and production scientific methods should remain subsequent separately gated work.
