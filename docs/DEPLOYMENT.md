# Deployment and runbook

Current code posture, 2026-09-29. This document does not certify a live Railway/Vercel deployment. Historical host names and operator timing tables have been removed from the active runbook; they remain in Git history.

## Processes and data root

| Process | Command | Behavior |
|---|---|---|
| Bounded lab | `python -m cancerjev lab --root <absolute-root> --max-runs 3` | One to 100 supervised blocks; default root `.lab`. |
| Continuous worker | `python -m cancerjev worker --live` | Repeated calls to the lab supervisor; uses configured data root. |
| API | `python -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000` | Read-only storage views. |
| Web | `npm ci`, `npm run build`, `npm run start` in `apps/web` | Observatory; API URL configured at build time. |
| Doctor | `python -m cancerjev doctor` | Storage integrity report; inspect before recovery/restore claims. |
| Legacy Program | `python -m cancerjev program` | Explicit autonomous legacy cycle; not read-only diagnostics or a bounded lab run. |

Set `CANCERJEV_DATA_DIR` to the same absolute durable root for worker/API/doctor. Pass that root explicitly to `lab --root`. Only one research writer may own it. Preserve SQLite, registered artifacts, portfolio revisions, events and provenance together. `shards/<run>/` is ephemeral raw workspace; its deletion is recorded and cleanup retried after interruption.

## Configuration

Use `.env.local.example` for supported settings. Local `.env.local` is a convenience; process environment wins, and `CANCERJEV_NO_DOTENV=1` disables local loading. Set `OPENROUTER_API_KEY` for the director and `TYPESAFE_API_KEY` for scientific Jev, server-side only. No GDC credentials or controlled-access data are allowed.

The director uses Codex CLI → OpenRouter. `CANCERJEV_LLM_MODEL` supplies its model unless `ONTOCODEX_MODEL` overrides it. `ONTOCODEX_EXECUTABLE` and `ONTOCODEX_BASE_URL` configure the harness. Research-control Jev shadows default off. Keep secrets out of browser environment, artifacts and image layers.

For web/API integration set `NEXT_PUBLIC_CANCERJEV_API_URL` at frontend build time and `CANCERJEV_WEB_ORIGIN` to the intended browser origin. The API has no authentication boundary; deploy it privately/trusted or supply an authenticated boundary appropriate to the exposed data.

## Container and persistent hosting

The Dockerfile installs/checks pinned Codex CLI, Node, Git and Python application dependencies. It starts `deploy.serve`, which optionally seeds synthetic data, optionally starts `worker --live`, then serves the API. The image is a runtime image, not an engineering checkout with the test suite.

Set `CANCERJEV_DATA_DIR=/data` and mount a persistent volume at `/data`. Set `CANCERJEV_NO_DOTENV=1`. `CANCERJEV_RUN_WORKER=1` enables the laboratory worker; `0` leaves the API-only posture. `CANCERJEV_SEED_DEMO=1` requests labelled synthetic seeding; leave it off for a real research volume. Do not infer that the lab idles solely because a legacy Campaign profile is EXPERIMENTAL: it follows its own registered offers.

`railway.json` describes local deployment configuration; a successful image build does not prove volume provisioning, provider connectivity or live service readiness. Earlier bridge verification built the image and exercised a loopback fake provider. This documentation pass does not redeploy it.

## Startup, health and recovery

1. Configure the durable root and provider environment; run the integrity report for an existing root.
2. Start API/web and one worker, or the configured combined container.
3. Check `/health`, `/api/system`, worker heartbeat and actual lab run outcomes separately.
4. On restart, retain the same root. The supervisor acquires ownership, terminalizes interrupted runs and retries workspace cleanup before new work.

A green `/health` proves API/storage reachability, not active research or scientific validity. `deploy.serve` currently does not monitor/restart its worker child after startup. M5 must address a healthy API with a dead worker. The supervisor bounds the research child but does not independently bound slow parent cleanup/finalization inside the nominal 600 seconds.

Recovery is also not yet scientific-operation reconciliation: a crash between canonical writes, receipt and portfolio can leave unattached outputs. Investigate those artifacts before assuming a retry is harmless; M1 supplies the durable reconciliation protocol. `STOPPED`/`NO_PROGRESS` prevent further lab dispatch; do not manually edit immutable portfolio JSON to restart it.

## Backup and restore

Stop research writers and the API/container before copying storage so SQLite and artifacts form a consistent snapshot. Preserve the whole durable root and relative paths, including the database and any WAL/SHM files present. Restore to an isolated root, point API/doctor at it, inspect integrity and ownership/recovery status, then enable exactly one writer. Do not remove canonical evidence to repair a cache or raw-workspace issue.

## Explicit validation and legacy commands

`campaign --validation` is the existing explicit validation-owned scientific path; it does not establish autonomous readiness or automatically promote a profile. Researcher/comparator commands remain isolated from autonomous consumption. They do not acquire the lab's child deadline merely by sharing modules. Use CLI `--help` and code-defined budgets for exact supported options; historical live populations, shard counts and costs are not current defaults.

Full acceptance requires M1 recovery, M2 bounded continuation and M5 volume/worker failure tests, followed by declared live evidence and independent scientific evaluation in M6. See the [audit](CODE_AUDIT.md) and [plan](IMPLEMENTATION_PLAN.md).
