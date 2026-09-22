# Phase 1 implementation record

**Status: implemented and locally verified on 2026-09-22. Phase 2 requires explicit approval.**

Phase 1 proves one coherent offline path: a process-held fake research runner commits canonical events and projections to SQLite, publishes immutable local artifacts, and is observed by FastAPI and a Next.js App Router UI. It creates 12 varied synthetic StatisticalStates, 16 Jev-shaped evaluations, two promoted candidates, two competing generated fixture hypotheses, one registered deterministic follow-up, two immutable evidence revisions, one deferred candidate, and one JSON/Markdown dossier.

Implementation order followed the approved plan:

1. Python package, configuration, SQLite bootstrap, typed events and run reducer.
2. Atomic artifact publication, OS lock and interrupted-run recovery.
3. Deterministic fixture orchestrator, CLI renderer, run/worker/show commands.
4. Read-only FastAPI routes with incremental event paging and keyset run/dossier cursors.
5. App Router UI with persistent polling, live incremental events, judgment vectors and dossier views.
6. Offline unit/integration tests, production frontend build, Playwright acceptance and manual API-restart/stale-data verification.
7. GitHub Actions gates for Ruff/pytest, typecheck/build and browser acceptance.

Implemented clarifications:

- The run dossier route is plural: `GET /api/runs/{run_id}/dossiers`.
- `CANCERJEV_FIXTURE_STAGE_DELAY_MS` is executor-only and defaults to 500 ms.
- Recovery is lock + canonical interruption events + a new run; there are no leases, queues or replay.
- Provider usage remains exactly zero. Simulated Jev-shaped evaluations are a separate counter.
- JSON is the authoritative dossier; Markdown derives deterministically from it.

No Phase 2 modules or empty future provider/science directories were created.
