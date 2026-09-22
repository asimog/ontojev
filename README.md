# OntoJev — open-access GDC evidence with deterministic science and Jev judgment

OntoJev retrieves public, open-access GDC data through one bounded anonymous transport,
measures it with deterministic scientific methods, and asks Jev narrow semantic questions
about the resulting compact state. Python policy decides what happens next. There is no LLM
hypothesis generation, no GDC authentication, and no GDC file download.

```text
ResearchSpec (reproducible scope)
        ↓
bounded parameterized GDC acquisition (anonymous, open access)
        ↓
strict parsing / normalized observations
        ↓
deterministic science (counts, coverage, log2 summaries)
        ↓
immutable StatisticalState (per gene)
        ↓
optional Wide Jev (compact projection → atomic semantic judgment)
        ↓
Python ranking / admission policy → bounded candidate admission
```

`ResearchSpec` owns reproducible research configuration; `Settings` owns operational
configuration (paths, timeouts, budgets, cache, provider/model). The current production
research specification is `LUAD_RESEARCH_V1` (`domain=lung cancer`, `cohort_id=TCGA-LUAD`,
`project_id=TCGA-LUAD`). TCGA-LUAD and TCGA-LUSC are never pooled. Acquisition uses bounded,
validated case pagination (`size ≤250`, `sort=case_id`, ≤10 pages) and deterministic
expression batching (each request ≤250 cases × ≤10 genes), merging returned values by
identifier before cohort-wide deterministic summaries.

The Python package is named `cancerjev`; the product is OntoJev. Phase 1 remains available as
an offline synthetic vertical slice (`run --fixture demo`) and is never mixed with live
records. Phases 4–7 (deep evidence, registered follow-ups, generative hypotheses, autoresearch)
are documented only.

## Run locally

Requires Python 3.12+ and Node.js 20.9+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Terminal 1 — read API
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd apps/web
npm ci
npm run dev

# Terminal 3 — real bounded open-access sweep (no credentials)
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m cancerjev run --live

# Optional: Phase 3 wide Jev evaluation (server-side key only)
$env:TYPESAFE_API_KEY="<your TypeSafe key>"
python -m cancerjev run --live --jev

# Fixture demonstration (offline, synthetic)
python -m cancerjev run --fixture demo

# Bounded anonymous contract capture
python -m cancerjev probe
```

Open `http://localhost:3000/runs`. The UI shows deterministic measurements and Jev judgments
in clearly separated panels; the research process never writes through FastAPI.

Configuration:

- `CANCERJEV_DATA_DIR` — local persistence directory; defaults to `./data`.
- `CANCERJEV_FIXTURE_STAGE_DELAY_MS` — demo-only delay; defaults to `500`, tests use `0`.
- `CANCERJEV_RUN_INTERVAL_MINUTES` — worker interval; defaults to `60`.
- `CANCERJEV_WEB_ORIGIN` — local CORS origin; defaults to `http://localhost:3000`.
- `CANCERJEV_GDC_MAX_REQUESTS` / `CANCERJEV_GDC_MAX_BYTES` / `CANCERJEV_GDC_PER_RESPONSE_BYTES` — application caps; defaults `150`, `64 MiB`, `5 MiB`.
- `CANCERJEV_GDC_CACHE` — set `0` to disable the normalized response cache.
- `CANCERJEV_JEV_MODEL` — pinned model; defaults to `jev-1.13.0`.
- `TYPESAFE_API_KEY` — required only for `--jev`; read at call time and never persisted or logged.
- `NEXT_PUBLIC_CANCERJEV_API_URL` — browser API URL; defaults to `http://127.0.0.1:8000`.

`--jev` requires `--live`; the fixture path never constructs a live provider. Persistence
schema is version 3; earlier data directories are intentionally not migrated and should be
moved or deleted.

## Open-access guarantees

- One transport owns every GDC request; it has no credential parameter and never constructs
  `Authorization` or `X-Auth-Token`.
- Host, endpoints and methods are allowlisted; `/data`, manifests and file downloads are not
  routable; redirects are refused; responses are size-capped and retained with SHA-256.
- File metadata queries always filter `access=open`; a controlled record fails closed and is
  never admitted to science.
- 401/403 become `UNAVAILABLE_ACCESS` with no retry and no credential lookup.
- Adversarial tests enforce all of the above; live captures record `authentication_headers_sent: []`.

## Verification

```powershell
python -m ruff check cancerjev apps tests
python -m pytest                      # offline suite; live markers excluded by default
python -m pytest -m live_gdc          # opt-in bounded live contract probe
python -m pytest -m live_jev          # opt-in live Jev evaluation (needs TYPESAFE_API_KEY)

cd apps/web
npm run typecheck
npm run build
npm run test:e2e                      # requires the API and web dev servers above
```

The default Python suite blocks outbound network connections except loopback test servers. No
default test needs Docker, PostgreSQL, Redis, GDC, TypeSafe/Jev, OpenRouter, or secrets. The
current factual verification record, including any live runs, is in
[implementation status](docs/IMPLEMENTATION_STATUS.md); this README does not assert test
counts or live results of its own.

## Scope boundary

Phase 4+ is not implemented: no deep evidence revisions, no registered follow-up execution, no
generative hypotheses, no LLM calls. Jev judgments are semantic policy inputs, never
measurements, significance, or clinical claims. Public GDC evidence alone does not establish
dependency, druggability, therapeutic efficacy, safety, clinical benefit, biomarker
qualification, or drug success; OntoJev's claim boundary is **candidate-target investigation**,
not therapeutic target validation. Scientific contracts live in `docs/`, including the central
[GDC × Jev fit analysis](docs/GDC_JEV_FIT_ANALYSIS.md).

See [architecture](docs/ARCHITECTURE.md), [domain models](docs/DOMAIN_MODELS.md),
[scientific invariants](docs/SCIENTIFIC_INVARIANTS.md), [GDC strategy](docs/GDC_STRATEGY.md),
[GDC budgets](docs/GDC_BUDGETS.md), [Jev design](docs/JEV_DESIGN.md),
[question architecture](docs/JEV_QUESTIONS.md), [research loop](docs/RESEARCH_LOOP.md),
[API contract](docs/API_CONTRACT.md), [UI spec](docs/UI_SPEC.md), and
[testing contract](docs/TESTING.md).
