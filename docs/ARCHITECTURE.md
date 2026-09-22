# Proposed architecture

Design dated 2026-09-22. Scope is Phase 0 only; the Phase 1 target is entirely fake and offline. Source authority and documented uncertainties are recorded in [SOURCE_REVIEW.md](SOURCE_REVIEW.md).

The system is one Python package with a sequential research loop. FastAPI reads its SQLite projections and artifacts; Next.js polls FastAPI. Modules express scientific and provider boundaries without services, job queues, or generic workflow machinery.

| Responsibility | Owner | Must not own |
|---|---|---|
| GDC retrieval and budgets | `gdc` | Interpretation, unrestricted URLs, file downloads |
| Populations, calculations, correction | `science` | Model SDKs or provider judgments |
| Immutable typed records | `domain` | Network or database operations |
| Typed Jev questions and normalized answers | `jev` | Scientific truth or generative prose |
| Competing hypotheses | `reasoning` | Measurements or executable follow-up code |
| Sequence, routing, cursor, termination | `research` | New scientific formulas |
| Event commit, projections, artifacts | `storage` | Independent lifecycle rules |
| JSON dossier and derived Markdown | `dossier` | Invented numerical facts |
| Read API and two event renderers | API, web, CLI | Research decisions |

The run path is inventory → bounded project selection → API fast search → StatisticalStates → validity filter → diverse cap → Jev wide ranking → up to 20 candidates → deterministic deep evidence → Jev deep fan-out → competing hypotheses → independent hypothesis review → registered follow-ups → new evidence → stop/defer/dossier. Every committed operational change has a RunEvent. Candidate stages may repeat; there is no dishonest global percentage complete.

**Simplification review.** For every choice below the question was: "Is there a simpler design that satisfies the requirement?"

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
| Scientific registry | Plugin/discovery framework | Dictionary of explicit method/action definitions and functions |
| Dossier | Free-form generated report | Structured authoritative JSON and deterministic Markdown first |
| Deployment | Containers/cloud adapters now | Portable local processes; document future constraints only |
| Routing | Unvalidated weighted discovery score | Versioned lexicographic ranking plus diversity; optional composite only after evaluation |

Exact proposed Phase 1 tree follows. **Only the documentation files exist at Phase 0.** No empty application scaffold is created. `__init__.py` files shown are included in Phase 1; all other later additions are explicitly listed below.

```text
ontojev/
  README.md
  AGENTS.md
  docs/
    ARCHITECTURE.md
    DOMAIN_MODELS.md
    RUN_EVENTS.md
    SCIENTIFIC_INVARIANTS.md
    GDC_STRATEGY.md
    GDC_BUDGETS.md
    JEV_DESIGN.md
    JEV_QUESTIONS.md
    RESEARCH_LOOP.md
    PERSISTENCE.md
    API_CONTRACT.md
    UI_SPEC.md
    DEPLOYMENT_PORTABILITY.md
    TESTING.md
    PHASE_1_PLAN.md
    SOURCE_REVIEW.md
    IMPLEMENTATION_STATUS.md
  pyproject.toml
  .env.example
  .gitignore
  .github/workflows/ci.yml
  cancerjev/
    __init__.py
    __main__.py
    config.py
    domain/
      __init__.py
      runs.py
      events.py
      states.py
      hypotheses.py
      dossier.py
    research/
      __init__.py
      orchestrator.py
      policy.py
      fixtures.py
    storage/
      __init__.py
      database.py
      repositories.py
      artifacts.py
      ownership.py
    cli/
      __init__.py
      main.py
      console.py
    dossier/
      __init__.py
      renderer.py
  apps/
    __init__.py
    api/
      __init__.py
      main.py
      routes.py
    web/
      package.json
      package-lock.json
      tsconfig.json
      next-env.d.ts
      next.config.ts
      app/
        layout.tsx
        globals.css
        page.tsx
        error.tsx
        loading.tsx
        not-found.tsx
        runs/
          page.tsx
          [runId]/page.tsx
        dossiers/
          page.tsx
          [dossierId]/page.tsx
        system/page.tsx
      components/
        navigation.tsx
        run-feed.tsx
        run-card.tsx
        run-detail.tsx
        pipeline.tsx
        event-feed.tsx
        budget-summary.tsx
        candidate-list.tsx
        judgment-vector.tsx
        dossier-view.tsx
        system-status.tsx
      lib/
        api.ts
        contracts.ts
        use-poll.ts
      tests/run-flow.spec.ts
      playwright.config.ts
  tests/
    conftest.py
    fixtures/demo.json
    unit/test_states.py
    unit/test_events.py
    unit/test_policy.py
    unit/test_artifacts.py
    integration/test_fake_run.py
    integration/test_api.py
    integration/test_recovery.py
  data/.gitkeep
```

Later additions, only when their phases are approved:

```text
cancerjev/gdc/{__init__,client,contracts,budgets,cache,inventory,mappers}.py
cancerjev/science/{__init__,registry,mutation,expression,multiple_testing}.py
cancerjev/jev/{__init__,contracts,service,questions,typesafe_adapter}.py
cancerjev/reasoning/{__init__,contracts,service,provider}.py
cancerjev/research/{discovery_cursor,state_builder,prefilter,followups,stopping}.py
cancerjev/science/{cnv,cross_project,survival}.py  # only when a real method needs them
tests/contracts/  # endpoint and provider fixtures added with real adapters
tests/science/    # registered-method tests added with each method
tests/live/      # explicit, disabled by default
```

This is a phase-specific tree, not a request to build all future modules now. Use JSON and the standard library where sufficient; add NumPy/SciPy only with deterministic science. No Parquet dependency is needed for the fake slice.
