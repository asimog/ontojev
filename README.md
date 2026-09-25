# OntoJev — open-access GDC evidence with deterministic science and Jev judgment

OntoJev retrieves public, open-access GDC data through one bounded anonymous transport,
measures it with deterministic scientific methods, and asks Jev narrow semantic questions
about the resulting typed state. Python policy decides what happens next. Operator-selected
candidates can enter a bounded deep investigation, with optional generated hypotheses and
live dossiers. There is no GDC authentication or GDC file download.

```text
ResearchSpec (reproducible scope)
        ↓
bounded parameterized GDC acquisition (anonymous, open access)
        ↓
strict parsing / normalized observations
        ↓
deterministic science (counts, coverage, log2 summaries)
        ↓
immutable typed StatisticalState (per gene)
        ↓
Wide Jev projection (jev-state-projection-v3) + questions (wide-v3)
        ↓
validated typed answers → Python admission (wide-policy-v2) → Candidate
        ↓
immutable typed EvidenceState E0
        ↓
registered deterministic action → immutable revision E1/E2
        ↓
Deep Jev projection (jev-evidence-projection-v2) + questions (deep-v1)
        ↓
Python next-move policy (deep-policy-v2): COMPLETE / FOLLOW_UP /
GENERATE_HYPOTHESES / ABSTAIN
        ↓
optional bounded hypothesis generation → Jev critique (hypothesis-v2) → dossier (schema 2)
```

`ResearchSpec` owns reproducible research configuration (domain, cohort, project, bounded
page/batch sizes, cohort ceiling, discovery/candidate limits); `Settings` owns operational
configuration (paths, timeouts, budgets, cache, provider/model). The current production
research specification is `LUAD_RESEARCH_V1` (`domain=lung cancer`, `cohort_id=TCGA-LUAD`,
`project_id=TCGA-LUAD`); `ResearchSpec` payloads are schema 3. TCGA-LUAD and TCGA-LUSC are
never pooled. Acquisition uses bounded, validated case pagination (`size ≤250`, `sort=case_id`,
≤10 pages) and deterministic expression batching (each request ≤250 cases × ≤10 genes),
merging returned values by identifier before cohort-wide deterministic summaries.

The Python package is named `cancerjev`; the product is OntoJev. Domain records are named
without legacy suffixes (`StatisticalState`, `EvidenceState`, `ResearchSpec`, `Candidate`,
`HypothesisDraft`); operational ids and hashes travel in `StateRecord` / `EvidenceRecord` /
`HypothesisRecord` envelopes and never enter scientific identity. Serialized scientific
schemas are StatisticalState 4 and EvidenceState 4; unknown or older schemas are rejected
fail-closed, with no migrations and no legacy readers. Question sets are `wide-v3`, `deep-v1`
and `hypothesis-v2`.

`run --fixture demo` runs the same shared `LiveOrchestrator` offline with `FixtureTransport`
and `FixtureJevAdapter` (run mode `FIXTURE`, synthetic notice in the dossier); there is no
second execution engine. See the [current status](docs/IMPLEMENTATION_STATUS.md).

## Run locally

Requires Python 3.12+ and Node.js 20.9+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Terminal 1 — read API (version 3.0.0, SQLite schema 5)
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd apps/web
npm ci
npm run dev

# Terminal 3 — real bounded open-access sweep (no credentials)
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m cancerjev run --live

# Optional: Wide Jev evaluation (server-side TYPESAFE_API_KEY only)
$env:TYPESAFE_API_KEY="<your TypeSafe key>"
python -m cancerjev run --live --jev

# Optional: one explicitly selected candidate investigation, authorized iteration
python -m cancerjev run --live --jev --deep-candidate TP53 --deep-followup

# Fixture demonstration (offline, synthetic, same engine)
python -m cancerjev run --fixture demo

# Bounded anonymous contract capture
python -m cancerjev probe

# Offline baseline-vs-Jev comparison against operator-supplied labels
python -m cancerjev evaluate --run <run-id> --labels <labels.json>
```

Open `http://localhost:3000/runs`. The UI shows deterministic measurements and Jev judgments
in clearly separated panels; the research process never writes through FastAPI.

Configuration:

For local development, copy `.env.local.example` to `.env.local` and fill in the provider keys;
`.env.local` is gitignored and loaded automatically by `cancerjev.config.load_local_env()` (real
environment variables win, blank values are ignored, values are never logged). Set
`CANCERJEV_NO_DOTENV=1` to disable. It includes `TYPESAFE_API_KEY`, `OPENROUTER_API_KEY` (used
for optional explicitly authorized OpenRouter hypothesis generation), the operational
`CANCERJEV_*` settings below, and the frontend URL.

- `CANCERJEV_DATA_DIR` — local persistence directory; defaults to `./data`.
- `CANCERJEV_FIXTURE_STAGE_DELAY_MS` — demo-only delay; defaults to `500`, tests use `0`.
- `CANCERJEV_RUN_INTERVAL_MINUTES` — worker interval; defaults to `60`.
- `CANCERJEV_WEB_ORIGIN` — local CORS origin; defaults to `http://localhost:3000`.
- `CANCERJEV_GDC_MAX_REQUESTS` / `CANCERJEV_GDC_MAX_BYTES` / `CANCERJEV_GDC_PER_RESPONSE_BYTES` — application caps; defaults `150`, `64 MiB`, `5 MiB`.
- `CANCERJEV_GDC_CACHE` — set `0` to disable the normalized response cache.
- `CANCERJEV_JEV_MODEL` — pinned model identity; defaults to `jev-1.13.0`.
- `TYPESAFE_API_KEY` — required only for `--jev`; read at call time and never persisted or logged.
- `OPENROUTER_API_KEY` — optional, environment-only; used only by the explicitly authorized CLI hypothesis path.
- `NEXT_PUBLIC_CANCERJEV_API_URL` — browser API URL; defaults to `http://127.0.0.1:8000`.

`--jev` requires `--live`; the fixture path never constructs a live provider. `--deep-candidate`
accepts `gene`, `gene:<SYMBOL>`, `state:<STATE_ID>` or `slot:N` and requires `--live --jev`;
`--deep-followup` authorizes bounded iteration; `--deep-hypotheses` requests bounded generation
without rewriting the recorded next move. Persistence schema is version 5; earlier databases are
explicitly rejected, not automatically migrated or reset. Retain historical databases and
artifacts; use a separate compatible data directory.

## Open-access guarantees

- One transport owns every GDC request; it has no credential parameter and never constructs
  `Authorization` or `X-Auth-Token`.
- Host, endpoints and methods are allowlisted; `/data`, manifests and file downloads are not
  routable; redirects are refused; responses are size-capped and retained with SHA-256.
- File metadata queries always filter `access=open`; a controlled record fails closed and is
  never admitted to science.
- 401/403 become `UNAVAILABLE_ACCESS` with no retry and no credential lookup.
- Adversarial tests enforce all of the above; live captures record `authentication_headers_sent: []`.

Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may carry a provider
authorization header for generated hypothesis text; that credential is environment-only, never
persisted or logged, and its output is bounded, validated and never evidence.

## Verification

Verified in this environment (2026-09-25):

- `python -m pytest` — **652 passed** offline (live opt-in markers excluded; `tests/live` is
  deselected by default).
- `python -m ruff check cancerjev apps tests` — clean.
- scoped strict `mypy` (the explicit file list in `pyproject.toml`) — clean.

```powershell
python -m ruff check cancerjev apps tests
python -m pytest                      # offline suite; live markers excluded by default
python -m pytest -m live_gdc          # opt-in bounded live GDC contract probe
python -m pytest -m live_jev          # opt-in live Jev evaluation (needs TYPESAFE_API_KEY)
python -m mypy                        # scoped strict check; not whole-repository typing
```

Browser acceptance lives in `tests/browser/` with its own Playwright config and package, and CI
runs it as a separate job. It was **not executed in this environment**: UNVERIFIED here.
Live GDC, TypeSafe/Jev and OpenRouter acceptance was **not run** (no credentials):
LIVE ACCEPTANCE PENDING / UNVERIFIED. No scientific readiness, incremental Jev value or
production use is claimed.

The default Python suite blocks outbound network connections except loopback test servers. No
default test needs Docker, PostgreSQL, Redis, GDC, TypeSafe/Jev, OpenRouter, or secrets. The
current factual verification record is in [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Scope boundary

The registered deep actions currently check retained evidence integrity; they acquire no new
data and compute no new biological measurement. The default hypothesis generator is
deterministic; the optional OpenRouter adapter can make paid model calls only on the authorized
CLI path. Jev judgments are semantic policy inputs, never measurements, significance, or
clinical claims. Public GDC evidence alone does not establish dependency, druggability,
therapeutic efficacy, safety, clinical benefit, biomarker qualification, or drug success;
OntoJev's claim boundary is **candidate-target investigation**, not therapeutic target
validation. Scientific contracts live in `docs/`, indexed by the
[discovery roadmap](docs/DISCOVERY_ROADMAP.md) (indexed systematic discovery is the next Stage 4
task; proposed lane/action contracts there are not current runtime behavior).

See [architecture](docs/ARCHITECTURE.md), [domain models](docs/DOMAIN_MODELS.md),
[persistence](docs/PERSISTENCE.md), [scientific invariants](docs/SCIENTIFIC_INVARIANTS.md),
[research loop](docs/RESEARCH_LOOP.md), [run events](docs/RUN_EVENTS.md),
[GDC strategy](docs/GDC_STRATEGY.md), [GDC budgets](docs/GDC_BUDGETS.md),
[GDC discovery captures](docs/GDC_DISCOVERY_CAPTURES.md), [source review](docs/SOURCE_REVIEW.md),
[Jev design](docs/JEV_DESIGN.md), [question architecture](docs/JEV_QUESTIONS.md),
[API contract](docs/API_CONTRACT.md), [UI spec](docs/UI_SPEC.md),
[testing contract](docs/TESTING.md), [development skills](docs/DEVELOPMENT_SKILLS.md) and
[deployment portability](docs/DEPLOYMENT_PORTABILITY.md).