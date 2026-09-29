# OntoJev

OntoJev is an experimental autonomous computational cancer target-discovery system. Humans bound the lung-cancer domain; OntoCodex proposes research actions and synthesis; Python computes and validates evidence; Jev supplies bounded typed judgments.

The laboratory runtime is connected to the existing Campaign scientific pipeline. Its seven capabilities cover mutation discovery, expression discovery, CNV case shards, CNV merge, canonical state composition, Wide evaluation and Candidate investigation through Stage 8/dossier. The default worker uses this laboratory supervisor. Offline replay reaches a dossier across research runs.

This is an implemented bridge, not a completed or scientifically validated autonomous laboratory. Whole mutation/expression lanes and Candidate investigations still need finer resumable units. Historical Wide receipt migration, publication crash windows, engineering automation and live evaluation remain. The remaining sequence is recovery → resumable science → director/Campaign context → engineering → deployment → live evaluation. See the [current code audit](docs/CODE_AUDIT.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md).

## Current architecture

```text
Human domain boundary
  → OntoCodex question / validated capability choice
  → bounded Research Run / canonical Campaign operation
  → GDC parsing / deterministic measurements / StatisticalState
  → Wide Jev / Candidate / EvidenceState / Deep and registered follow-ups
  → Stage 8 / dossier / next laboratory decision
```

SQLite, events and immutable artifacts retain scientific state and provenance. Lab portfolio revisions hold questions, interpretations and evidence references; they do not replace StatisticalState or EvidenceState. Runs use a supervised child deadline with a normal 600-second allowance and finalization reserve. Full parent cleanup/finalization deadline guarantees remain an audit item.

Missing is not negative; hypotheses and research-control judgments are not biological evidence. Only open-access data may be acquired. A completed computational dossier is not a validated therapeutic target.

## Local setup

Python 3.12+ and the Codex CLI are required. The Dockerfile pins its CLI version; use that version when reproducing the image's harness behavior.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev]'
Copy-Item .env.local.example .env.local
```

Set server-side `OPENROUTER_API_KEY` for the director and `TYPESAFE_API_KEY` for scientific Jev. The director uses Codex CLI → OpenRouter with `CANCERJEV_LLM_MODEL` (default in `cancerjev/config.py`), optionally overridden by `ONTOCODEX_MODEL`. `ONTOCODEX_EXECUTABLE` selects the CLI. No OpenAI key is required by this configured path. Research-control Jev shadows are optional and off by default.

Run bounded research blocks:

```powershell
.venv\Scripts\python.exe -m cancerjev lab --root .lab --max-runs 3
```

The lab command defaults to `.lab`; the continuous worker and API use `CANCERJEV_DATA_DIR` (otherwise `./data`). Set one absolute root when using them together:

```powershell
$env:CANCERJEV_DATA_DIR = 'C:\dev\ontojev\.lab'
.venv\Scripts\python.exe -m cancerjev worker --live
# In another terminal with the same environment:
.venv\Scripts\python.exe -m uvicorn apps.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

For the read-only Observatory, run `npm ci` and `npm run dev` in `apps/web`; configure `NEXT_PUBLIC_CANCERJEV_API_URL` for the API and open `/lab`. The API has no authentication boundary. Follow the [deployment runbook](docs/DEPLOYMENT.md) for durable storage, private/trusted access and worker health.

Legacy `program` and explicit Campaign/researcher commands still exist. `program` can dispatch autonomous work; it is not just diagnostics and does not inherit the lab supervisor automatically. Their lifecycle convergence is M3.

## Verification

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m tests.repository_facts check
.venv\Scripts\python.exe -m pytest
```

For frontend changes, run `npm run typecheck` and `npm run build` in `apps/web`. Offline replay uses fixture/stub providers; it proves executable integration, not live scientific validity. The audit records verification provenance and distinguishes committed code from pre-existing local changes.

## Documentation

| Document | Purpose |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Current owners and scientific/control boundaries |
| [Laboratory](docs/LABORATORY.md) | Run behavior, configuration and continuation limits |
| [Code audit](docs/CODE_AUDIT.md) | Current findings and evidence limits |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Single active, dependency-ordered roadmap |
| [Deployment](docs/DEPLOYMENT.md) | Processes, storage, health and recovery |
| [Scientific invariants](docs/SCIENTIFIC_INVARIANTS.md) | Required scientific guarantees |
| [Data strategy](docs/DATA_STRATEGY.md) | Source/method and acquisition contracts |
| [Jev design](docs/JEV_DESIGN.md) / [decisions](docs/JEV_DECISIONS.md) | Judgment roles and evaluation boundaries |
| [Product scope](docs/PRODUCT_SCOPE.md) | Intended product and claim limits |
| [Calibration](docs/CALIBRATION_DESIGN.md) / [synthetic rehearsal](docs/JEV_REVIEW_REHEARSAL.md) | Evaluation protocol and explicitly limited rehearsal evidence |
| [Pathway sources](docs/PATHWAY_SOURCES.md) / [functional sources](docs/FUNCTIONAL_SOURCES.md) | Source adoption and evidence-role decisions |
| [Repository facts](docs/REPOSITORY_FACTS.md) | Generated schema, policy and action identities |

Older audit/plan snapshots live in Git history. Scientific design documents describe requirements where explicitly labelled; they do not certify implementation or validation.
