# Phase 1 Verification

Independent adversarial audit of the CancerJEV Phase 1 offline synthetic vertical slice.
Audit performed against the committed revision without modifying production code.
No provider (GDC / TypeSafe-Jev / LLM) network call was made at any point.

## Repository state

| Item | Value |
|---|---|
| Branch | `main` |
| Commit | `8a3149c4fa7364dbc48104ad712714a4521190e8` ("Complete Phase 1 UI/API conformance and CLI-UI event consistency") |
| Working tree | clean (`git status --porcelain` empty) before and after all audit runs |
| History | `64b8335` initial commit, `f573add` Phase 1 vertical slice, `8a3149c` Phase 1 conformance |
| Phase 1 files | all of `cancerjev/`, `apps/api/`, `apps/web/`, `tests/`, `docs/`, `.github/workflows/ci.yml`, `pyproject.toml`, `README.md`, `AGENTS.md`, `.env.example`, `.gitignore` |
| Phase 2 code | none found (see Phase 2 leakage) |
| Python lockfile | none (unpinned ranges in `pyproject.toml`) — observation |
| Node lockfile | `apps/web/package-lock.json` present |

Untracked-but-ignored leftovers from the implementing session exist in the repository root
(`.tmp-phase1/`, `.tmp-phase1b/`, `.tmp-e2e-live/`, `.tmp-final-e2e/`, `data/cancerjev.db`,
`apps/web/.next/`, `apps/web/test-results/`). All are covered by `.gitignore`
(`data/*`, `apps/web/.next/`, `apps/web/test-results/`, `*.tsbuildinfo`); the tree stays clean.

## Verification environment

| Item | Value |
|---|---|
| OS | Windows 10 Home Single Language 10.0.19045 (win32) |
| Python | 3.14.3 (system); audit venv `%TEMP%\kilo\cj-audit\venv` (clean, `pip install -e ".[dev]"`) |
| Node / npm | v24.13.1 / 11.8.0 |
| Linux cross-check | WSL Ubuntu, Python 3.11.15 venv (package installed with `--ignore-requires-python`), Node v22.22.2 |
| Browser | Playwright Chromium via `npm run test:e2e` and the Playwright MCP browser |
| Ports | documented 8000/3000 are held by Docker Desktop on this machine; audit servers used 8010/8100 and 3100 |
| Data dirs | fresh directories under `%TEMP%\kilo\cj-audit\` (never the repository `data/`) |

## Executive result

**FAILED**

The offline architecture itself is sound and most invariants were proven with direct evidence:
single canonical RunEvent authority, transactional event+projection commit, artifact
immutability/confinement, OS-lock ownership, interrupted-run reconciliation without replay,
fail-closed live mode, zero provider calls, and a genuinely live polling UI.

The FAILED verdict is driven by acceptance-gate failures and contract deviations on the
committed revision:

- BLOCKER B1: the committed browser acceptance test (`npm run test:e2e`) failed 2/2 runs and
  structurally cannot observe the required nonterminal states at the hardcoded fixture delay
  (8-second `/runs` poll interval vs ~7.5-second run). Live observability was proven manually,
  but the documented acceptance gate does not pass.
- MAJOR M1: the Python suite fails on Linux (the documented CI platform): 12 passed / 1 failed.
- MAJOR M2: dossier provenance SHA-256 / artifact ID never render in the browser
  ("—" / "sha256 unavailable") because the API does not expose those headers via CORS.
- MAJOR M3: unknown RunEvent `type`/`schema_version` values are accepted and stored, contrary to
  `RUN_EVENTS.md` ("an unknown type/version is a compatibility error").
- MAJOR M4: content hashes include operational UUIDs (`run_id`, `state_id`, `evidence_state_id`,
  `candidate_id`), contrary to `DOMAIN_MODELS.md` ("content hashes exclude operational
  UUIDs/timestamps"); equivalent fixture science is not recognizable across runs.
- MAJOR M5: `docs/IMPLEMENTATION_STATUS.md` overstates three verified behaviours (see
  Documentation accuracy).

## Acceptance matrix

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | repository installs cleanly | PASS | clean venv + `pip install -e ".[dev]"`; `python -m cancerjev --help` from outside the repo |
| 2 | FastAPI starts locally | PASS | uvicorn on 8010/8100 against empty dir; `/health` 200; restart preserves state |
| 3 | Next.js starts locally | PASS | `npm run dev` (3100); `npm run build` all routes built |
| 4 | `python -m cancerjev run --fixture demo` works | PASS | 71 events, `[DONE] #71` (installed package, cwd outside repo) |
| 5 | run automatically appears on `/runs` | PASS | card `79c8a735…` observed RUNNING at `GDC_FAST_SEARCH`, then `JEV_DEEP` |
| 6 | run detail visibly progresses while active | PASS | live DOM: `JEV_WIDE · live` (24 events) → `FOLLOWUP · live` (57); `EVIDENCE_BUILD · live` (44) → `HYPOTHESIS_VERIFICATION · live` (53) |
| 7 | CLI and UI consume the same persisted RunEvents | PASS | CLI `show --events` 71 event IDs identical, in order, to `/api/.../events`; UI DOM sequences strictly 1..71, unique |
| 8 | SQLite survives API restart | PASS | stop/restart FastAPI: 71 events, dossier, COMPLETED unchanged; no new runs |
| 9 | run history survives research-process restart | PASS | recovery of killed runs; old events byte-identical; new run created |
| 10 | second research owner rejected | PASS | second process exit 1, "already owns this data directory", no second run row |
| 11 | interrupted previous run preserved, not replayed | PASS | `f9af4825…` STOPPED/INTERRUPTED seq 7; `ced171cd…` STOPPED/INTERRUPTED seq 49; in-flight candidate deferred INTERRUPTED; no replay |
| 12 | synthetic StatisticalStates visible | PASS | 12 states via `/states`; state artifact has shape/availability/unit/finite values; UI shows count + per-state event details |
| 13 | synthetic Jev wide vector visible | PASS | persisted wide artifact has Noul/Choice/Score, distributions, confidence, rubric; UI `judgment-vector` ×12 |
| 14 | at least one candidate reaches deep evidence | PASS | candidate `ed88252d…` DOSSIER_READY with 2 EvidenceStates |
| 15 | synthetic Jev deep vector visible | PASS | 2 DEEP evaluations; UI shows 32 vectors total |
| 16 | at least two competing fixture hypotheses | PASS | 2 hypotheses with different statements, both labeled `GENERATED FIXTURE HYPOTHESIS` |
| 17 | each hypothesis receives independent fixture evaluation | PASS | 2 HYPOTHESIS evaluations; each artifact references exactly one `hypothesis_id`; no sibling data |
| 18 | one registered deterministic fixture follow-up executes | PASS | execution row: action `DROP_INFLUENTIAL_FIXTURE_POINTS_V1` v1, slot 1, status COMPLETED, input hash = baseline |
| 19 | follow-up creates a NEW EvidenceState | PASS | iteration 1, new ID/hash `4c9aa940…`, previous link set |
| 20 | original EvidenceState remains unchanged | PASS | baseline `3373f1f0…` file SHA matches recorded artifact SHA; effect 0.88 preserved; no UPDATE path for evidence |
| 21 | at least one synthetic dossier is produced | PASS | `eb09eebc…`; JSON + derived Markdown |
| 22 | dossier JSON is authoritative | PASS | 25 sections in JSON; Markdown/UI derive from it; downloads served from artifact store |
| 23 | Markdown derives deterministically from JSON | PASS | every section title and narrative/reason matched the Markdown verbatim; regeneration reproducible |
| 24 | UI prominently marks fake/synthetic content | PASS | `FAKE · SYNTHETIC` badges, `SYNTHETIC DEMONSTRATION` heading, "NO REAL GDC/JEV/LLM" in dossier JSON/Markdown/UI, all artifacts labeled |
| 25 | actual GDC requests = 0 | PASS | no GDC code/URL/SDK in app; counters 0; network-blocked tests; provider-URL grep only in docs |
| 26 | actual Jev calls = 0 | PASS | no TypeSafe/Jev code; `provider_usage.jev_calls = 0`; fixture vectors generated locally |
| 27 | actual LLM calls = 0 | PASS | no OpenAI/OpenRouter/Anthropic code; `llm_calls = 0` |
| 28 | no forbidden infrastructure exists | PASS | no Postgres/Redis/Celery/Docker/Supabase/Vercel/Railway/S3/MinIO/Kafka/WebSocket/SSE in code or dependencies |
| 29 | Python tests pass | **FAIL** | Windows: 13/13 PASS; Linux (documented CI platform): 12 passed / 1 failed (`test_artifact_paths_are_confined`) |
| 30 | frontend typecheck/build passes | PASS | `npm ci` 0 vulnerabilities; `npm run typecheck` clean; `npm run build` all routes |
| 31 | browser acceptance passes | **FAIL** | `npm run test:e2e` failed 2/2 at `expect(observed.size).toBeGreaterThanOrEqual(2)` with "observed stages: (none)" |
| 32 | documentation accurately states what exists | **FAIL** | Playwright pass claim, dossier-provenance claim, and "strict error envelopes" claim are not true on this revision (see Documentation accuracy) |

## Critical invariant matrix

| Invariant | Result | Evidence |
|---|---|---|
| A. One RunEvent authority | PASS | only `Repository.append_event` writes `run_events`; all projection writes (run/candidate/evidence/dossier) happen inside the same call; no second event log, no console-log parsing, no `run.json`, UI reads API only |
| B. Event + projection transactional consistency | PASS | injected bad registration → event count, `last_sequence`, status and artifact row all unchanged; terminal-run restart rejected with no sequence consumed |
| C. Event sequence monotonicity | PASS | sequences contiguous 1..71 in every run inspected; DB `UNIQUE(run_id, sequence)` verified by direct duplicate INSERT rejection |
| D. Event idempotency | PASS | replayed key returns the original event, no new sequence; single row for key; `UNIQUE(run_id, idempotency_key)` enforced |
| E. Evidence immutability | PASS | baseline artifact bytes unchanged after follow-up; file SHA == recorded artifact SHA; revision is a new row + new file; no update path |
| F. Hypothesis/evidence separation | PASS | hypotheses are text-only, `factual_observation_refs: []`, label `GENERATED FIXTURE HYPOTHESIS`; measured values live in EvidenceState/StatisticalState only |
| G. No generated execution | PASS | no `eval`/`exec`/`subprocess`/shell/SQL built from fixture text anywhere in `cancerjev/`; follow-up action is a static fixture branch |
| H. Artifact path confinement | PASS | `../`, `..\`, absolute, UNC and nested traversal all rejected; missing → FileNotFoundError; corruption → OSError; all indexed artifacts re-hashed and size-checked; zero orphan files in demo data |
| I. Process ownership | PASS | portalocker OS-held lock (not PID file / heartbeat / DB flag); cross-process rejection with exit 1 before run creation |
| J. Recovery without replay | PASS | killed runs STOPPED/INTERRUPTED with only a RUN_STOPPED (and candidate DEFERRED) appended; original sequences intact; new invocation created a new run |
| K. Incremental event polling | PASS | server logs show `events?after_sequence=9/24/40/44/…/71&limit=20`; browser network shows initial drain 0/20/40/60 then cursor-only pages |
| L. Fake/live boundary | PASS | `run` without `--fixture demo` exits 1 with a clear message; same with `TYPESAFE_API_KEY`/`LLM_API_KEY`/`OPENROUTER_API_KEY`/`OPENAI_API_KEY`/`ANTHROPIC_API_KEY=dummy`; no run created, no network client instantiated |
| M. No provider network calls | PASS | fixture execution has no HTTP client (app runtime deps are fastapi/pydantic/uvicorn/portalocker); tests block `socket.create_connection`; counters 0/0/0 |
| N. No Phase 2 architecture | PASS | no provider adapter, transport, cache, budget ledger, queue/lease/fencing, deployment coupling, or empty future packages (`gdc/`, `jev/`, `science/`, `reasoning/` absent) |

## Commands executed

```powershell
# repository / environment
git branch --show-current; git rev-parse HEAD; git status --porcelain; git log --oneline -12
python --version; node --version; npm --version

# clean install outside the repo
python -m venv $env:TEMP\kilo\cj-audit\venv
& $venv\python.exe -m pip install -e "D:\ontojev[dev]"
& $venv\python.exe -m cancerjev --help
& $venv\python.exe -m cancerjev run            # no fixture: fail-closed
& $venv\python.exe -m cancerjev run --fixture demo
& $venv\python.exe -m cancerjev worker --fixture demo
& $venv\python.exe -m cancerjev show <run_id> --events

# documented checks (repo root)
python -m ruff check cancerjev apps tests
python -m pytest
& $venv\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000   # winerror 10013: port held by Docker Desktop

# frontend
npm ci
npm run typecheck
npm run build
$env:CANCERJEV_WEB_URL='http://127.0.0.1:3100'; npm run test:e2e

# Linux CI equivalent (WSL Ubuntu)
python3.11 -m venv /tmp/cj-ci
/tmp/cj-ci/bin/python3.11 -m pip install --ignore-requires-python -e '.[dev]'
/tmp/cj-ci/bin/python3.11 -m ruff check cancerjev apps tests
CANCERJEV_FIXTURE_STAGE_DELAY_MS=0 /tmp/cj-ci/bin/python3.11 -m pytest -q
```

Additional audit harnesses (temporary, outside the repo): invariant/transaction/idempotency
probes, keyset pagination probes, artifact confinement and failure injection, evidence/dossier
inspection, labeling sweep, mutation checks, API contract scripts via httpx, browser observation
via Playwright MCP.

## Automated test results

| Check | Result |
|---|---|
| `python -m ruff check cancerjev apps tests` | PASS, "All checks passed!" (Windows and Linux) |
| `python -m pytest` (Windows, Python 3.14.3) | **13 passed**, 0 failed, 0 skipped, 0 xfailed; 2 deprecation warnings (starlette testclient/anyio) plus the known Python 3.14 pytest temporary-symlink cleanup error printed after success; exit 0 |
| `python -m pytest -q` (WSL Ubuntu, Python 3.11.15) | **12 passed, 1 failed** — `tests/test_artifacts.py::test_artifact_paths_are_confined`: `Failed: DID NOT RAISE <class 'ValueError'>` |
| Mutation probes | 4/4 mutations caught: idempotency bypass, path-confinement bypass, data-cap enlargement, `after_sequence` ignored |
| `npm ci` | PASS, 0 vulnerabilities |
| `npm run typecheck` | PASS |
| `npm run build` | PASS, all application routes built |
| `npm run test:e2e` | **FAILED 2/2** (40.1 s first run; same assertion second run) |

## Browser verification

Servers: FastAPI on `127.0.0.1:8100` (`CANCERJEV_DATA_DIR=%TEMP%\kilo\cj-audit\browser-data`),
Next.js dev on `127.0.0.1:3100` (`NEXT_PUBLIC_CANCERJEV_API_URL=http://127.0.0.1:8100`).

- Run ID `3a8781d8-1fe5-4230-8266-f80e82504328` — observed live: `JEV_WIDE · live` at 24 rendered
  events, then `FOLLOWUP · live` at 57 events (hypotheses panel visible, 30 judgment vectors).
  Refresh during a later run reconstructed history from the API (44 → 53 events after reload,
  status RUNNING, stage `HYPOTHESIS_VERIFICATION · live`), proving no event loss on reload.
- Run ID `14922f0c-301e-4c78-8db5-656f78320a08` — observed live: `EVIDENCE_BUILD · live` (44
  events) and `HYPOTHESIS_VERIFICATION · live` (53 events). With the API stopped, the page kept
  last-good data (65 events, RUNNING) and showed "API unavailable / last updated … Retaining
  last-good data."; after restart, polling recovered, drained to 71/71 events, status COMPLETED,
  and stopped. Event feed DOM: 71 items, strictly ascending unique sequences 1..71, first
  `RUN_CREATED`, last `RUN_COMPLETED`; feed auto-followed to the bottom.
- Filters: candidate `FJEV4` → 2 events (`CANDIDATE_PROMOTED`, `CANDIDATE_DEFERRED`); iteration
  `1` → 8 events (follow-up, new evidence, iteration-1 stages). Correct and combined.
- Dossier ID `eb09eebc-6aae-5310-8318-4711cfadaeb6` — `SYNTHETIC DEMONSTRATION` heading, the
  four-line "NO REAL …" notice, evidence/hypothesis references, and both download links present.
  **Provenance defect:** artifact ID renders "—" and SHA renders "sha256 unavailable" because the
  response headers `x-artifact-id` / `x-artifact-sha256` exist on the wire but no
  `access-control-expose-headers` is sent, so cross-origin JS cannot read them (confirmed via
  captured response headers).
- Automated `npm run test:e2e`: failed twice at
  `expect(observed.size, "observed stages: …").toBeGreaterThanOrEqual(2)` → `Received: 0`.
  Root cause: the test waits for the new card on `/runs`, whose poll interval is 8 s, while the
  500 ms-delay run completes in ~7.5 s (DB timestamps 06:19:03.622 → 06:19:11.266). The detail
  page therefore opened after completion in both runs. The test as written cannot reliably
  observe a nonterminal stage. A subsequent manual run with the same page and a 4 s delay did
  observe four distinct nonterminal stages.

## Offline/provider verification

- GDC calls = **0**
- Jev calls = **0**
- LLM calls = **0**

Evidence: `provider_usage` on every run (`gdc_requests/jev_calls/llm_calls = 0`, cost `null` →
UI "unknown"); `/api/system` reports all providers `false`/disabled; `grep` for
`api.gdc.cancer.gov`, `typesafe`, `openrouter`, `openai`, `anthropic` matches only documentation,
never application code; no HTTP client is imported by `cancerjev/` or `apps/api/` (runtime deps:
fastapi, pydantic, uvicorn, portalocker); `tests/conftest.py` blocks `socket.create_connection`
for the whole suite; fixture execution completes with the suite's network block active; live mode
fails closed with and without fake provider credentials in the environment, creating no run.

## Persistence verification

- App connections: `journal_mode=wal`, `foreign_keys=1`, `busy_timeout=5000`,
  `synchronous=2` (FULL), verified through `Database.connect()` itself (not a raw connection).
- `bootstrap()` idempotent: 1 `schema_info` row and 12 tables after 1 + 5 repeated bootstraps; a
  second `Database` instance on the same file keeps the same pragmas.
- API startup on an empty directory creates the schema and serves zero runs; no ResearchRun,
  event, artifact or reconciliation is produced by API startup or restart (verified on 8010 and
  8100, including a stop/restart cycle after a completed run).
- Demo data directory contains only `cancerjev.db`, `research.lock` and `runs/<run_id>/{evidence,
  hypotheses, jev, statistical_states, dossier}` — no `run.json`, no second status file, no
  console log used as a source of truth.
- All 34 artifacts of a demo run re-hashed from disk: SHA-256 and size match the DB rows; zero
  orphan files; baseline and revised evidence files both match their recorded hashes.

## Process ownership/recovery verification

- Run A (`owner-data`, 10 s stage delay) was live at sequence 6. A second process with the same
  data directory exited 1 with "Another CancerJEV research process already owns this data
  directory" and created **no** ResearchRun. Ownership is portalocker (a real OS lock on
  `research.lock`); file existence alone is not the check (the file persists after the process
  dies).
- Force-killed A mid-run: `f9af4825-5c6d-4da7-8b6c-d8bbe6f6f181` stayed RUNNING with 6 events
  and no candidates until reconciliation. Next invocation printed
  `[RECOVERY] preserved and stopped interrupted run …`, then created a new run:
  `f9af4825…` → STOPPED / INTERRUPTED / coverage PARTIAL, events 1..7 contiguous, original 6
  events unchanged; `884058b4…` (interrupted by an audit pipe artifact) → STOPPED/INTERRUPTED
  seq 4; new `4beb88fe…` COMPLETED seq 71. No stage or provider step was replayed into the old
  runs.
- Second scenario (`owner-data-2`, killed after candidates existed): `ced171cd…` STOPPED /
  INTERRUPTED seq 49; its in-flight candidate `41d73ea6…` was reconciled to DEFERRED with
  `terminal_reason=INTERRUPTED` inside the same canonical event transaction; all 25 of its
  artifacts remained; new run `3814c5b8…` COMPLETED seq 71.

## API verification

All Phase 1 routes exist and were exercised with httpx against a live server:
`/health`, `/api/system`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/events`,
`/api/runs/{id}/candidates`, `/api/runs/{id}/states` (+`disposition`),
`/api/runs/{id}/evaluations` (+`purpose`), `/api/runs/{id}/hypotheses`,
`/api/runs/{id}/dossiers` (plural confirmed; singular returns 404), `/api/dossiers`,
`/api/dossiers/{id}?format=json|markdown`, `/api/artifacts/{id}`.

- Empty state: runs `[]`, system `FAKE_ONLY`, providers disabled, no active run, worker null.
- Unknown IDs → 404; malformed IDs → 422; `limit=0/101/501`, `after_sequence=-1`, bad cursors,
  `format=pdf` → 422; cursor/status mismatch → 422.
- Events: ascending, no duplicates, no gaps, `next_after_sequence`/`has_more`/
  `run_last_sequence` correct; empty page keeps the cursor and reports `has_more=false`; drained
  71/71 in pages of 7; `limit=500` accepted, 501 rejected.
- Corrupt artifact → 503 envelope; missing artifact → 503; restored → 200; ETag equals
  `x-artifact-sha256`; dossier and artifact `Cache-Control: no-store`.
- CORS: only the configured origin is allowed; disallowed origin gets no allow-origin header.
- No secrets, tokens or stack traces in any response inspected.
- Deviation: FastAPI-generated validation errors (bad `limit`, malformed UUID path) return
  `{"detail":[…]}` instead of the documented `{error:{code,message,request_id}}` envelope
  (N1); `/health` has no `Cache-Control: no-store` (N2).

## UI verification

- App Router confirmed: `apps/web/app/` routes `/`, `/runs`, `/runs/[runId]`, `/dossiers`,
  `/dossiers/[dossierId]`, `/system`; no `pages/`, no `react-router-dom`, no
  `dangerouslySetInnerHTML`/`innerHTML`.
- Loading ("Connecting to the local research record…"), empty ("No runs yet" + command hint),
  active, completed and API-unavailable states all observed.
- Run cards persist across polls, survive an API outage, and show status, stage, elapsed, state
  counts, Jev evaluations, candidates, hypotheses, follow-ups, dossiers and the FAKE badge;
  nullable costs render "unknown", not 0.
- Event feed keys/order: React key is `event_id`, ordering is by `sequence`; DOM sequences
  strictly ascending and unique; timestamp collisions cannot affect order.
- Auto-scroll: implementation follows only while the user is at the bottom (`following` ref,
  "new events" indicator otherwise) — code-verified, consistent with the observed bottom-follow.
- Jev UI language: "Noul semantic probability", "model confidence", explicit
  "not statistical significance, a p-value, or scientific confidence" disclaimer; sections are
  visually separated as deterministic evidence / Jev judgment / generated hypotheses.
- Polling: single-flight (`inFlight` guard), next poll scheduled after completion, bounded
  backoff, hidden-tab pause; server logs confirm cursor-only event requests and no full-history
  refetch; terminal events are drained in the same poll cycle before polling stops.
- `/system` reports mode FAKE_ONLY, disabled providers with 0 calls, worker idle + last write,
  data directory, artifact count, versions, and Phase 2-only values as explicit "unknown/absent"
  with reasons — no false "connected" claims.

## Event-system verification

- Single authority: `run_events` is the only event store; the reducer derives run status/stage/
  counters; all candidate/evidence/dossier projection updates are executed as registration
  statements inside `append_event`'s transaction; recovery and heartbeat are the only direct
  writes (heartbeat is explicitly non-authoritative).
- Transactionality: injected failing registration rolled back event insert, projection update,
  artifact row, sequence and status together; terminal-run restart rejected without consuming a
  sequence.
- Limits: data at 65,536 bytes accepted, 65,537 rejected; message 2,048 accepted, 2,049
  rejected; 16 artifact refs accepted, 17 rejected; NaN rejected; multibyte payloads are counted
  conservatively via the escaped JSON form; rejections consume no sequence and never truncate.
- Sequence/idempotency: `UNIQUE(run_id, sequence)`, `UNIQUE(event_id)` and
  `UNIQUE(run_id, idempotency_key)` all enforced at the DB level; duplicate-key retry returns the
  original committed event.
- Contract deviation M3: `RunEvent.type` is a free string and `schema_version` is unvalidated, so
  `append_event(type="TOTALLY_UNKNOWN_TYPE")` is stored (the reducer ignores it) instead of being
  rejected as a compatibility error.

## Evidence immutability verification

- Baseline `3373f1f0…` (effect 0.88, iteration 0) and revision `4c9aa940…` (effect 0.61,
  iteration 1, `previous_evidence_state_id` = baseline) are separate rows and separate files.
- Both files' SHA-256 match their recorded artifact hashes; the baseline file still contains
  0.88 after the follow-up; no repository path updates or deletes evidence; the only evidence
  writer is the append-only insert in the orchestrator.
- Follow-up record: action `DROP_INFLUENTIAL_FIXTURE_POINTS_V1` v1, slot 1 consumed, input hash
  equals the baseline `evidence_hash`, output evidence state = revision, status COMPLETED,
  summary `{before: 0.88, after: 0.61}`.
- PERSISTENCE.md promises immutable rows are additionally protected by "simple SQLite triggers";
  the schema has none (N10). Repository APIs expose no update/delete paths, so this is a
  defence-in-depth gap only.

## Security findings

- Path traversal: artifact store rejects `../`, `..\`, nested traversal, absolute, drive-absolute
  and UNC paths; `C:relative` on Windows resolves inside the data directory (confined, not an
  escape). API reads resolve through the same confinement.
- SQL injection: every statement is parameterized; the only identifier interpolation
  (`list_table`) is guarded by a table allowlist; hostile `status`/`cursor` inputs were handled
  as plain values with the events table intact.
- No subprocess, shell, `eval`/`exec`, or generated-code execution anywhere in `cancerjev/`;
  fixture hypothesis text cannot reach an executor.
- CORS restricted to one configured origin, GET only; no credentials; no secrets in responses,
  logs, repository files or CI.
- Rendering: Markdown/JSON are rendered as text (`<pre>`), no `dangerouslySetInnerHTML`.
- Local-only binding (`127.0.0.1`) and no auth is a documented, acceptable Phase 1 choice.

## KISS/architecture findings

- No generic repository factory, DI container, service locator, workflow engine, event bus or
  abstract base classes with a single implementation. `Repository` is a concrete class over
  SQLite; `Database` is a thin connection/pragma helper; the orchestrator is linear and explicit;
  the fixture is plain functions/data.
- The event reducer + registration-statement pattern is the one justified abstraction: it is what
  enforces the canonical-event invariant.
- `REGISTERED_FIXTURE_ACTIONS` is defined but never consulted (the fixture calls the single action
  directly); it is dead code today but is the documented registry shape for Phase 2 — flagged as
  a test gap rather than a defect.
- `list_table` is a small generic helper used by the read API; acceptable.
- Net assessment: complexity is close to the minimum that satisfies the event/artifact
  invariants. No Phase 2 scaffolding was created.

## Documentation accuracy findings

| Document | Claim | Reality |
|---|---|---|
| `docs/IMPLEMENTATION_STATUS.md` | "Playwright acceptance: 1 passed in 17.5 seconds … observes two nonterminal stages" | FAILED 2/2 on this revision (B1) |
| `docs/IMPLEMENTATION_STATUS.md` | "the web dossier view renders them [artifact ID and SHA-256] as provenance" | renders "—" / "sha256 unavailable" in the browser (M2) |
| `docs/IMPLEMENTATION_STATUS.md` | "strict error envelopes" | validation 422s use `{"detail": …}` (N1) |
| `docs/IMPLEMENTATION_STATUS.md` | "GitHub Actions gates" (implied green) | the Linux CI job fails on `test_artifact_paths_are_confined` (M1) |
| `docs/IMPLEMENTATION_STATUS.md` | "Ruff passed; pytest 13 passed" | reproduced on Windows only; false on the pinned CI platform |
| `README.md` | documented commands | all verified except the documented ports 8000/3000, which are held by Docker Desktop on this machine; identical commands work on 8010/8100/3100. `npm run test:e2e` fails. |
| `README.md` | "The default Python suite blocks outbound network connections" | true (`tests/conftest.py`) |
| `docs/PERSISTENCE.md` | immutability "through repository APIs and simple SQLite triggers" | triggers absent (N10) |
| `docs/RUN_EVENTS.md` | unknown type/version is a compatibility error | unknown types accepted (M3) |
| `docs/DOMAIN_MODELS.md` | content hashes exclude operational UUIDs/timestamps | operational UUIDs included (M4) |

## Defects

### B1 — Browser acceptance test cannot observe nonterminal state (BLOCKER)

- Component: `apps/web/tests/phase1.spec.ts`, `apps/web/components/RunFeed.tsx`
- Expected: `npm run test:e2e` passes and observes at least two nonterminal stages before
  COMPLETED (audit criterion 31, section 54).
- Observed: failed 2/2. `observed stages: (none)`, `Received: 0`. The test waits for the new run
  card on `/runs` (8 s poll interval) while the 500 ms-delay fixture completes in ~7.5 s, so the
  detail page opens after the run is already COMPLETED.
- Reproduction: start API + web dev server, then `npm run test:e2e` (twice).
- Root-cause hypothesis: test design race between the 8 s feed poll and the ~7.5 s fixture run;
  the assertion depends on the card being detected within the first ~5 s.
- Recommended correction: open `/runs/<new id>` directly (or shorten the feed poll in test mode,
  or raise the fixture delay), and assert on `run.current_stage` observed via the detail page.
  Correct `docs/IMPLEMENTATION_STATUS.md`.

### M1 — Python suite fails on the documented CI platform (MAJOR)

- Component: `tests/test_artifacts.py::test_artifact_paths_are_confined`
- Expected: suite passes on ubuntu-latest/Python 3.12 (`.github/workflows/ci.yml`).
- Observed: WSL Ubuntu: `Failed: DID NOT RAISE ValueError` for `"C:/escape.json"`, which is
  absolute on Windows but a confined relative path on POSIX.
- Reproduction: Linux: `CANCERJEV_FIXTURE_STAGE_DELAY_MS=0 python -m pytest -q` → 12 passed, 1 failed.
- Root-cause hypothesis: Windows-specific path semantics baked into a cross-platform test.
- Recommended correction: assert platform-appropriate cases (`"C:/escape.json"` only on Windows;
  keep `../`, absolute and UNC cases for both), or use `PurePosixPath`-independent traversal
  inputs.

### M2 — Dossier provenance artifact ID/SHA-256 never render in the browser (MAJOR)

- Component: `apps/api/routes.py` (CORS middleware), `apps/web/components/DossierView.tsx`
- Expected: dossier view shows the artifact ID and SHA-256 (UI_SPEC, IMPLEMENTATION_STATUS).
- Observed: "artifact —", "sha256 unavailable". Response headers exist but
  `access-control-expose-headers` is absent, so cross-origin fetch cannot read them.
- Reproduction: open `/dossiers/<id>` with API and web on different origins; inspect network
  response headers.
- Root-cause hypothesis: custom headers not added to CORS `expose_headers`.
- Recommended correction: set `expose_headers=["X-Artifact-Id","X-Artifact-SHA256","ETag"]`; make
  the e2e assertion check the hash value, not the word "sha256" (N9).

### M3 — Unknown RunEvent type/version accepted (MAJOR)

- Component: `cancerjev/domain/events.py`, `cancerjev/storage/repositories.py`
- Expected: `RUN_EVENTS.md` — "an unknown type/version is a compatibility error".
- Observed: `append_event(event_type="TOTALLY_UNKNOWN_TYPE")` is stored (reducer ignores it); no
  `schema_version` validation.
- Reproduction: append an unregistered type; the event is committed with a sequence.
- Root-cause hypothesis: no event-type registry validation on the write path.
- Recommended correction: validate `type` against the registered vocabulary and
  `schema_version == 1` before allocating a sequence; add a test.

### M4 — Content hashes include operational UUIDs (MAJOR)

- Component: `cancerjev/domain/states.py`, `cancerjev/domain/hypotheses.py` (hash computation),
  `cancerjev/research/orchestrator.py` (`_record_evidence`)
- Expected: `DOMAIN_MODELS.md` — content hashes exclude operational UUIDs/timestamps so identical
  scientific state is recognizable across runs.
- Observed: `state_hash`/`evidence_hash` are computed over documents containing `run_id`,
  `state_id`, `evidence_state_id`, `candidate_id` (and nested IDs). Two demo runs produce
  different hashes; after stripping operational IDs the payloads are byte-identical.
- Reproduction: run the demo twice in fresh data dirs and compare `statistical_states.state_hash`
  / `evidence_states.evidence_hash`.
- Root-cause hypothesis: hash computed over the full document before only the hash field itself is
  removed.
- Recommended correction: compute the content hash over the scientific sub-document excluding
  operational identifiers/timestamps, and record those separately.

### M5 — Documentation overstates verified behaviour (MAJOR)

- Component: `docs/IMPLEMENTATION_STATUS.md` (and README for `test:e2e`).
- Expected: documentation matches reality (audit criterion 32).
- Observed: three claims false on this revision (see Documentation accuracy table).
- Recommended correction: after fixing B1/M2/N1/M1, re-run the full gate and rewrite the
  verification record with reproducible numbers.

### Minor defects

- **N1** FastAPI request-validation errors return `{"detail": …}` instead of the documented error
  envelope (`apps/api/routes.py` handler coverage).
- **N2** `/health` lacks `Cache-Control: no-store` (all `/api/*` responses have it).
- **N3** `worker_status.owner_id` is overwritten with the run ID by `orchestrator._event`
  (`heartbeat(str(event["run_id"]))`); `/api/system` therefore shows a run ID as worker owner.
- **N4** Fixture Jev vectors in DEEP/HYPOTHESIS evaluations have `chosen` labels
  (`FOLLOW_UP`, `TESTABLE`, `WEAKENED`) absent from the `distribution` keys (`PROMOTE`/`DEFER`),
  and the score distribution contains `6` for a 1–5 rubric. Harmless in Phase 1 but a real
  adapter validation would reject them.
- **N5** `cancerjev show <run_id>` prints the run summary as a Python `repr`, not JSON, while
  `--events` prints JSON.
- **N6** `DossierArchive` load-more falls back to the first-page cursor when a page's
  `next_cursor` is null, so the button can persist; dedupe prevents duplicate cards.
- **N7** `RunFeed` requests `limit=20` and ignores `next_cursor`; runs older than the newest 20
  are not reachable in the UI.
- **N8** `RunDetail`'s event cursor ref is not reset when `runId` changes without a remount
  (only reachable by programmatic client-side navigation between two run detail URLs).
- **N9** The e2e dossier-provenance assertion (`toContainText("sha256")`) passes on the literal
  string "sha256 unavailable" and masks M2.
- **N10** No SQLite triggers protect immutable rows, despite PERSISTENCE.md; repository APIs
  expose no update/delete paths.
- **N11** `Database.bootstrap()` does not close its connection, and concurrent bootstraps could
  each insert a `schema_info` row (idempotent DDL, non-unique version insert).
- **N12** `ArtifactStore.publish` returns a new `artifact_id` when identical content already
  exists at the path; registering that result a second time would violate
  `UNIQUE(relative_path)`.
- **N13** `jev_evaluations.state_id` holds a statistical-state ID for WIDE, an evidence-state ID
  for DEEP and a hypothesis ID for HYPOTHESIS; `purpose` disambiguates but the column is
  overloaded.

### Observations

- **O1** Python dependencies are unpinned (no lockfile); CI is not byte-reproducible.
- **O2** `apps/web/AGENTS.md` and `CLAUDE.md` (generated by `next dev`) are committed; documented
  as intentional.
- **O3** `/api/runs/{id}` embeds full candidate rows although API_CONTRACT describes a "current
  candidate summary"; harmless and useful, but a contract drift.
- **O4** React StrictMode in dev duplicates each poll request (dev only; production build single).

## Test gaps

- No test rejects unknown event types/schema versions (would have caught M3).
- No test asserts content-hash stability across runs or hash-input exclusions (M4).
- The artifact path-confinement test is platform-dependent (M1) — it fails where it should pass.
- The dossier provenance assertion checks for the word, not the value (N9/M2).
- Ownership is only tested in-process; cross-process rejection and force-kill recovery were
  verified manually during this audit and are not covered by the committed suite.
- No test covers UI cursor-based polling, poll-overlap prevention, terminal drain under a
  summary/events race, auto-scroll, or refresh-during-run reconstruction.
- No test covers the API error envelope for FastAPI-generated validation errors (N1).
- No CI coverage of `npm run test:e2e` timing robustness (only a single pass was claimed).

## Risks

- The browser acceptance gate is timing-sensitive; CI or developer machines can flake or fail
  (B1), which erodes the value of the one end-to-end guarantee.
- CI cannot go green on Linux until M1 is fixed; until then the documented gates are not
  trustworthy.
- Phase 2 scientific identity semantics would inherit the hash-input defect (M4) if not fixed
  first; the Jev fixture vectors (N4) would not survive real adapter validation.
- Provenance display (M2) undermines the dossier's verifiability story in the UI.

## Phase 2 readiness

**READY AFTER FIXES**

The architecture is the right shape for Phase 2 (one event authority, transactional projections,
immutable artifacts, fail-closed live mode, narrow adapters, no infrastructure creep). Before
Phase 2 approval, fix B1, M1–M5 and the immutability/identity issues (M4, N10), then re-run the
full documented gate on both Windows and Linux.

## Recommended next action

1. Fix M1 (portable confinement test) so the committed suite passes on Linux, then re-run CI
   locally in WSL.
2. Fix B1 (test timing/design) and re-run `npm run test:e2e` repeatedly (e.g., 3×) to prove it
   observes two nonterminal stages deterministically.
3. Fix M2 (CORS expose-headers) and tighten the e2e assertion to the real SHA value.
4. Fix M3 (event type/version registry validation) and M4 (content-hash input exclusions) with
   tests.
5. Correct `docs/IMPLEMENTATION_STATUS.md`/`README.md` claims, then re-run the full gate and
   update this verification report.

Do not begin Phase 2 before these are corrected and re-verified.

---

### Audit metadata

- Auditor: independent verification pass (no production code modified; four temporary mutations
  applied and reverted within the audit, working tree restored clean before and after).
- Report generated: 2026-09-22.
- All runtime artifacts were created under `%TEMP%\kilo\cj-audit\` (Windows) and `/tmp` (WSL);
  repository `data/` was not touched.

---

## Repair addendum — 2026-09-22

The audit above stands as the record of revision `8a3149c`. A separate repair pass then fixed
every actionable finding on top of that revision. Disposition:

| Finding | Disposition | Repair evidence |
|---|---|---|
| B1 browser acceptance race | FIXED | `tests/phase1.spec.ts` finds the run via the API, asserts the card separately, opens the detail page with a 2.5 s stage delay, and checks auto-follow, refresh and drain; `npm run test:e2e` 4 passed on four consecutive runs (45.3 s, 44.9 s, 45.0 s, 48.1 s) |
| M1 Linux confinement test | FIXED | `tests/test_artifacts.py` uses platform-neutral traversal/absolute cases plus Windows-only drive/UNC cases; Linux pytest 43 passed / 0 failed |
| M2 provenance headers | FIXED | CORS `expose_headers`; browser `fetch` reads `X-Artifact-Id`, `X-Artifact-SHA256`, `ETag`; e2e asserts the served digest |
| M3 unknown event type/version | FIXED | `REGISTERED_EVENT_TYPES` + `schema_version` validator; tests prove no sequence, event or projection change |
| M4 operational UUIDs in content hashes | FIXED | `cancerjev/domain/identity.py` explicit projections; two-run hash equality and sensitivity tests |
| M5 documentation overstatement | FIXED | `IMPLEMENTATION_STATUS.md` rewritten from executed results; README updated |
| N1 validation error envelope | FIXED | `RequestValidationError` handler; pytest asserts the envelope for malformed UUIDs and bounds |
| N2 `/health` no-store | FIXED | Middleware covers `/health`; pytest asserts the header |
| N3 heartbeat owner ID | FIXED | Orchestrator keeps a stable process worker ID; pytest asserts owner == worker_id != run_id |
| N4 invalid fixture Jev vectors | FIXED | Roster-driven Choice/Score helpers on the 0..4 rubric with legend/expected; contract tests; UI shows `selected / 4` |
| N5 CLI summary repr | FIXED | `show` prints JSON; pytest parses the summary |
| N6 archive cursor fallback | FIXED | Explicit cursor-chain state + `lib/pagination.ts`; unit test and 23-dossier browser probe (control removed, not resurrected) |
| N7 run feed capped at 20 | FIXED | Cursor "Load more runs"; unit test and 23-run browser probe (20 → 23 unique cards) |
| N8 run-scoped state reset | FIXED (defensive) | `key={runId}` remount plus a `data-event-id` invariant test; the probe showed the current App Router already remounts the dynamic-segment subtree, so the key is an explicit guarantee rather than the only defence |
| N9 weak provenance assertion | FIXED | e2e asserts a 64-hex digest matching the served header and rejects "unavailable" |
| N10 missing immutability triggers | FIXED | 16 `CREATE TRIGGER IF NOT EXISTS` statements; pytest proves direct UPDATE/DELETE fail and mutable projections still update |
| N11 bootstrap lifecycle/concurrency | FIXED | Connection closed in `finally`; `BEGIN IMMEDIATE` after `executescript`; conditional insert + `UNIQUE(version)`; threaded bootstrap test |
| N12 artifact republish identity | FIXED | Deterministic `uuid5(path, sha256)`; conflict-tolerant registration; repeat/collision/recovery tests |
| N13 overloaded `state_id` | FIXED | `input_ref_kind`/`input_ref_id`; persistence schema v2 with a clear incompatibility error; API/test/doc updates |
| O1 Python lockfile | ACCEPTED | Bounded ranges remain the documented Phase 1 policy; no new dependency-management ecosystem |
| O2 generated Next.js AGENTS/CLAUDE | ACCEPTED | Tracked generated pointers are intentional; no change |
| O3 embedded candidate rows | ACCEPTED | `/api/runs/{run_id}` keeps the simpler embedded rows; API_CONTRACT wording clarified |
| O4 StrictMode dev duplicate polls | ACCEPTED | Development-only; production polling is single-flight; documented |

Repair verification summary: Windows pytest 43/43, Linux pytest 43/43, Ruff clean on both,
`npm ci` 0 vulnerabilities, typecheck and production build pass, browser acceptance 4 passed on
four consecutive runs. Provider calls remain GDC 0 / Jev 0 / LLM 0. Hosted GitHub Actions and the
exact Python 3.12 CI combination were not executed locally and remain UNVERIFIED. The stale local
`data/cancerjev.db` (schema 1) was deleted because persistence schema 2 intentionally does not
migrate pre-repair data directories.
