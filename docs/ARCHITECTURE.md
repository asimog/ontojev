# Architecture

Updated 2026-09-22. Phase 1 (offline synthetic vertical slice) is **IMPLEMENTED** and verified; Phase 2 (real open-access GDC evidence and deterministic StatisticalStates) and Phase 3 (real Jev wide evaluation over those states) are **IMPLEMENTED** and live-verified; the analysis behind them is `docs/GDC_JEV_FIT_ANALYSIS.md` and the evidence record is `docs/IMPLEMENTATION_STATUS.md`. Phase 4+ remains documented, not implemented.

The system is one Python package with a sequential research loop. FastAPI reads its SQLite projections and artifacts; Next.js polls FastAPI. Modules express scientific and provider boundaries without services, job queues, or generic workflow machinery.

| Responsibility | Owner | Must not own |
|---|---|---|
| GDC retrieval, allowlists, budgets, caching | `gdc` | Interpretation, unrestricted URLs, file downloads, credentials |
| Populations, calculations, method registry | `science` | Model SDKs or provider judgments |
| Immutable typed records and identity hashes | `domain` | Network or database operations |
| Typed Jev questions, projection, normalized answers, provider adapter | `jev` | Scientific truth or generative prose |
| Competing hypotheses | `reasoning` (Phase 6) | Measurements or executable follow-up code |
| Sequence, routing, live/fixture orchestration, ranking policy | `research` | New scientific formulas |
| Event commit, projections, artifacts | `storage` | Independent lifecycle rules |
| JSON dossier and derived Markdown | `dossier` | Invented numerical facts |
| Read API and event renderers | API, web, CLI | Research decisions |

Boundaries that are invariants, not conventions:

- **One GDC transport.** `cancerjev/gdc/transport.py` is the only module that opens a socket to GDC. It has no credential parameter and never constructs `Authorization` or `X-Auth-Token`. Host, paths and methods are allowlisted; redirects are refused; response size, request count, page count, case/gene ID counts and concurrency are capped per run.
- **One Jev adapter.** `cancerjev/jev/typesafe_adapter.py` is the only module that knows the provider wire contract or SDK. `science` and `domain` never import provider types.
- **Raw → Jev is never direct.** GDC bytes → strict parser → normalized records → population validation → deterministic method → StatisticalState → deterministic projection → Jev. A Jev input can never contain unparsed provider payloads.
- **One event authority.** All operational changes commit through `Repository.append_event`; the `gdc_attempts` ledger is operational bookkeeping and never a second status source.

Fixture and live paths share every boundary above; only the orchestrator and lane implementations differ (`research/orchestrator.py` for the fixture demo, `research/live.py` for real runs). Run `mode` (`FAKE`/`LIVE`) is stored on the run, artifacts keep their labels, and fixture and live records are never mixed in rankings, caches or dossiers.

## Run path

Fixture (Phase 1, still available): inventory → fast search (fake) → 12 synthetic StatisticalStates → fixture wide ranking → promoted candidates → fake deep evidence → fake Jev vectors → fixture hypotheses → fixture follow-up → dossier. Zero provider calls.

Live Phase 2 (implemented): inventory (`/status`, `/projects`) → deterministic scope (≤8 projects with 50–250 cases) → case manifests → mutation discovery (`top_mutated_genes_by_project`) → gene identity (`/genes`) → gene-specific counts (`top_cases_counts_by_genes`) → SSM coverage (`mutated_cases_count_by_project`) → expression availability, provider summaries and local values → deterministic methods → real StatisticalStates → API/UI inspection. Zero Jev and zero LLM calls.

Live Phase 3 (implemented): the same run continues through projection creation → one Jev request per state with the `wide-v2` question set → fail-closed validation → cache → baseline and Jev rankings persisted → bounded candidate promotion. No deep analysis, no hypotheses, no follow-ups, no LLM.

Phase 4+ (documented only): deep deterministic evidence → EvidenceState → Jev deep fan-out → registered follow-ups → new evidence revisions → dossiers.

## Simplification review

For every choice below the question was: "Is there a simpler design that satisfies the requirement?"

| Choice | Simpler alternatives considered | Selected design |
|---|---|---|
| Research execution | Distributed queue, generic state-machine engine | One sequential function with explicit branches; no infrastructure needed |
| Persistence | File-only job blob, ORM hierarchy | SQLite tables plus immutable JSON artifacts; SQLite supplies transactional event ordering |
| Events and status | Independent logging/status, full event-sourcing framework | Append events and update a small projection in one transaction using one reducer |
| Live UI | WebSockets/SSE, repeated full log fetch | HTTP cursor polling; server components for shell, small client polling components |
| Single ownership | Lease fleet, PID-file checks | OS-held local file lock; heartbeat is observability, not ownership |
| Recovery | Resume arbitrary in-flight providers | Preserve interrupted run, mark STOPPED, create a new run; no automatic replay of uncertain calls |
| Provider boundaries | Generic AI platform, SDK types everywhere | Small owned contracts and one adapter per provider |
| GDC acquisition | Mirror, bulk files, generalized data lake | Allowlisted bounded API requests only; unsupported when inadequate |
| GDC HTTP stack | `requests`/`httpx` with hooks and retry plugins | stdlib `http.client` inside one transport; no new runtime dependency for Phase 2 |
| GDC caching | External cache service | SQLite `gdc_cache` + raw response artifacts keyed by canonical request hash |
| Contract verification | Manual research scripts | Reproducible `probe` command using the same transport and capture sink |
| Scientific registry | Plugin/discovery framework | Dictionary of explicit method/action definitions and functions |
| Jev projection | Template engine, generic serializer | Plain dict builder plus canonical JSON hash and an included-field contract |
| Jev cache | Provider-side cache assumptions | Application cache keyed on projection bytes, question bytes, resolved model, adapter version |
| Wide ranking | Learned/weighted composite score | Versioned lexicographic policy over persisted raw dimensions; baseline ranking retained separately |
| Dossier | Free-form generated report | Structured authoritative JSON and deterministic Markdown first |
| Deployment | Containers/cloud adapters now | Portable local processes; document future constraints only |

## Implemented tree (Phase 2/3)

```text
ontojev/
  README.md, AGENTS.md
  docs/            # authoritative documents incl. GDC_JEV_FIT_ANALYSIS.md
  pyproject.toml
  cancerjev/
    config.py
    domain/        # runs, events, states, hypotheses, dossier, identity
    gdc/           # transport, endpoints, parsers, capture
    science/       # methods (registry + deterministic implementations)
    jev/           # contracts, questions, projection, service, typesafe_adapter
    research/      # orchestrator (fixture), live (Phase 2/3), wide, ranking, policy, fixtures
    storage/       # database (schema 3), repositories, artifacts, ownership
    cli/           # run/worker --live|--fixture, probe, show
    dossier/       # deterministic renderer
  apps/
    api/           # FastAPI read surface
    web/           # Next.js App Router UI
  tests/
    unit/ integration/ science/ contracts/ live/   # live tests disabled by default
  data/            # local database, artifacts, captures (gitignored)
```

Later additions, only when their phases are approved:

```text
cancerjev/reasoning/{__init__,contracts,service,provider}.py   # Phase 6
cancerjev/research/{followups,stopping}.py                      # Phase 4
cancerjev/science/{cnv,cross_project,survival}.py               # only when a real method needs them
```

Use JSON and the standard library where sufficient; add NumPy/SciPy only with deterministic science that needs them. No Parquet dependency is needed.
