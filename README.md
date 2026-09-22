# CancerJEV — Phase 1 offline execution architecture

CancerJEV Phase 1 is an implemented, deliberately synthetic demonstration of a durable autonomous-research execution loop. It proves local process ownership, one canonical `RunEvent` stream, SQLite projections, immutable artifacts, a read-only FastAPI API, and a live Next.js App Router interface.

It does **not** analyze cancer data. Every fixture surface is marked `FAKE` / `SYNTHETIC`.

```text
deterministic demo fixture
        ↓
canonical RunEvent commits
        ↓
SQLite + immutable local artifacts
        ↓
FastAPI read API
        ↓
Next.js polling UI
        ↓
synthetic JSON + Markdown dossier
```

## Run locally

Requires Python 3.12+ and Node.js 20.9+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Terminal 1
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd apps/web
npm ci
npm run dev

# Terminal 3, repository root
$env:CANCERJEV_DATA_DIR="$PWD\data"
python -m cancerjev run --fixture demo
```

Open `http://localhost:3000/runs`. The UI automatically observes the process through the shared database; the research process never writes through FastAPI.

Configuration:

- `CANCERJEV_DATA_DIR` — local persistence directory; defaults to `./data`.
- `CANCERJEV_FIXTURE_STAGE_DELAY_MS` — demo-only delay; defaults to `500`, tests use `0`.
- `CANCERJEV_RUN_INTERVAL_MINUTES` — fake worker interval; defaults to `60`.
- `CANCERJEV_WEB_ORIGIN` — local CORS origin; defaults to `http://localhost:3000`.
- `NEXT_PUBLIC_CANCERJEV_API_URL` — browser API URL; defaults to `http://127.0.0.1:8000`.

`python -m cancerjev run` without `--fixture demo` fails clearly. It never substitutes fixture results for a requested live run. Continuous synthetic mode is `python -m cancerjev worker --fixture demo`; only one research process may own a data directory.

## Verification

```powershell
python -m ruff check cancerjev apps tests
python -m pytest

cd apps/web
npm ci
npm run typecheck
npm run build
npm run test:e2e  # requires the API and web dev servers described above
```

The default Python suite blocks outbound network connections. No test needs Docker, PostgreSQL, Redis, GDC, TypeSafe/Jev, OpenRouter, or secrets.

## Scope boundary

Phase 2 is not approved. There is no real GDC client/cache/attempt ledger, TypeSafe/Jev adapter, LLM adapter, production statistical method, provider credential path, or deployment coupling. The future scientific contracts remain in `docs/`; fixture shortcuts do not redefine them.

See [implementation status](docs/IMPLEMENTATION_STATUS.md), [architecture](docs/ARCHITECTURE.md), [API contract](docs/API_CONTRACT.md), and [testing contract](docs/TESTING.md).
