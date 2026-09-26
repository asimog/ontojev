# OntoJev Deployment and Runbook

> One application architecture: API, web and worker are three processes over one
> persistent data directory. There are no microservices, no external scheduler and
> no distributed queue. The API is a localhost/private/trusted read layer and ships
> with no authentication; do not expose it publicly without a deliberate,
> separately implemented authenticated boundary.

## Components

| Process | Command | Notes |
|---|---|---|
| API | `python -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000` | Read-only FastAPI access to persisted runs, states, evidence, dossiers and system status. |
| Web | `cd apps/web && npm ci && npm run build && npm run start` | Next.js served on port 3000; `NEXT_PUBLIC_CANCERJEV_API_URL` points at the API. |
| Worker | `python -m cancerjev worker --live` | Long-running autonomous program loop; owns the research lock only around each cycle. |
| One-shot program cycle | `python -m cancerjev program` | One durable cycle: observe release, select, dispatch, persist, heartbeat. |
| Doctor | `python -m cancerjev doctor [--prune-stale-temp]` | Read-only integrity report; optional bounded temp cleanup. |

Researcher/comparator work stays on the explicit path: `python -m cancerjev run --live [--jev] [--researcher ...]`.

## Data directory

`CANCERJEV_DATA_DIR` (default `./data`) owns everything persistent:

- `cancerjev.db` (+ `-wal`, `-shm`) — SQLite schema 7: runs, events, artifacts, scientific rows;
- `artifacts/...` — immutable content-addressed evidence files referenced by rows;
- `research.lock` — exclusive ownership lock for research-workspace mutation;
- `program/state/...` — append-only durable program-state artifacts (operational);
- `gdc_cache/...` — disposable acquisition cache (never evidence).

Authoritative evidence = registered artifacts + `run_events` + scientific tables.
Disposable = `gdc_cache`, temp files, report outputs. The doctor distinguishes
them; canonical outputs are never deleted by maintenance.

## Environment and secrets

Copy `.env.local.example` to `.env.local` (gitignored, loaded automatically).
Real process environment variables always win; set `CANCERJEV_NO_DOTENV=1` to
disable loading. Provider keys (`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`) are
server-side only and are never logged or persisted. Only open-access GDC data is
ever used; the system never accepts GDC credentials.

Effective controls and their hard caps are listed in `.env.local.example`; retired
`CANCERJEV_*` knobs are inert and must not be set.

## Startup and restart

1. Start the API first; it bootstraps the schema (with backup + migration when an
   older supported schema is found) and serves `/health` and `/api/system`.
2. Start the web process.
3. Start the worker; it acquires `research.lock` only for the duration of each
   cycle. A second research process is refused with an ownership error, not a wait.
4. Restart order: stop worker → stop web → stop API → start in the order above.
   An interrupted run is preserved and stopped by crash recovery
   (`RECOVERY` log line) on the next owner.

Program state survives restarts: a completed campaign is not redispatched until
the observed release, the method environment or the profile payload changes.

## Health and readiness

- `GET /health` — process + schema reachability.
- `GET /api/system` — schema/policy versions, provider key presence, active run,
  worker heartbeat and freshness (fresh only while a run is active and the
  heartbeat is within 60 s), budget defaults, cache counts.

A green `/health` means the API can read storage. It does not mean an autonomous
campaign ran or that LUAD is scientifically validated: `LUAD_CAMPAIGN_V1` remains
`EXPERIMENTAL` until a full live campaign with real Jev completes and is reviewed.

## Managed production deployment (Railway API, Vercel web)

Live deployment of record: Railway service `ontojev-api` (project `ontojev-api`)
with a persistent volume mounted at `/data`, and Vercel project `ontojev-web`
aliased at `https://ontojev-web.vercel.app`. The same architecture is used as
locally; only the process set is reduced.

Railway (from the repository root):

- build: `Dockerfile` + `railway.json` (healthcheck `/health`, one replica);
- **a volume is mandatory**: `/data` is the only durable filesystem. Without it
  every redeploy loses the database and artifacts (verified the hard way);
- variables: `CANCERJEV_DATA_DIR=/data`, `CANCERJEV_NO_DOTENV=1`,
  `CANCERJEV_WEB_ORIGIN=https://ontojev-web.vercel.app`, provider keys
  (`TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`) as encrypted service variables —
  never in the image or the repository;
- `CANCERJEV_RUN_WORKER=0` in the demo posture: with `LUAD_CAMPAIGN_V1` still
  `EXPERIMENTAL` the worker can only record `PROGRAM_IDLE`, which is noise rather
  than production. Enable it only after a profile is deliberately promoted;
- `CANCERJEV_SEED_DEMO=0` once real runs exist; the synthetic seed is only for a
  first boot with an empty volume.

Operating real bounded work on the deployment (all open-access, anonymous):

```text
railway ssh -s <service> "python -m cancerjev doctor"
railway ssh -s <service> "python -m cancerjev capability"
railway ssh -s <service> "tmux new-session -d -s cnv0 'python -m cancerjev discover-cnv --live --case-shard 0 > /data/cnv-shard0.log 2>&1'"
railway ssh -s <service> "tmux new-session -d -s jev0 'python -m cancerjev run --live --jev --researcher --deep-candidate TP53 --deep-followup --deep-hypotheses > /data/live-deep.log 2>&1'"
```

Long runs must be started detached (tmux) with output under `/data`; a bare
SSH command dies with the client and leaves the run `RUNNING` until crash
recovery. `tmux` is not baked into the image: `apt-get update` then
`apt-get install -y tmux` once per container generation.

Observed production costs (Data Release 46.0, 2026-08-10):

| Operation | Requests | Bytes | Jev calls | Notes |
|---|---|---|---|---|
| Cohort capability probe | 3 | 3.3 KB | 0 | status + project + one facet aggregate |
| CNV case shard 0 (25 cases) | 817 | 107 MB | 0 | one shard of the cohort frame; the full cohort needs every shard |
| Live researcher sweep + Wide/Deep Jev + dossier | 88 | ~7 MB | 13 | 10 states, 1 candidate (TP53), 1 LLM hypothesis call, 1 dossier |

Vercel (from `apps/web`): framework preset Next.js, production environment
variable `NEXT_PUBLIC_CANCERJEV_API_URL=https://<railway-domain>` (required at
build time), and nothing else. The browser origin must match the API
`CANCERJEV_WEB_ORIGIN` exactly.

This posture exposes a read-only API with **no authentication**. That is
deliberate for a demonstration; replace it with an authenticated boundary before
exposing real research data, enabling the worker, or promoting a campaign
profile.

## Backup and restore

Back up as one consistency unit:

1. Stop the worker (or accept that a running cycle is interrupted and recovered).
2. Copy `cancerjev.db` plus `cancerjev.db-wal`/`-shm` if present, and the
   `artifacts/` tree; keep the relative layout.
3. Restore by placing the files back and starting the API, which verifies the
   schema version and fails closed on unsupported or future versions.
4. Schema upgrades create `cancerjev.db.backup-v<old>-<timestamp>` automatically
   before any migration mutation; keep that file until the upgrade is verified.

Run `python -m cancerjev doctor` after a restore: it reports missing or
unregistered artifacts, hash mismatches, stale temp files, schema problems,
stale ownership markers and disk-space concerns without modifying evidence.

## Limits and fail-closed behavior

- GDC budget policy is declared in `cancerjev/gdc/budget.py`; allowances grow
  adaptively within declared caps and an exhausted budget reports incomplete or
  unavailable, never a smaller population labelled complete.
- A run that fails reaches `FAILED`/`STOPPED` in the same invocation; crash
  recovery only handles processes that died without reaching either state.
- Wide evaluation is bounded by `pre-wide-policy-v1`: the complete union stays
  persisted, cuts record explicit reasons, and ambiguous boundaries fail closed.
