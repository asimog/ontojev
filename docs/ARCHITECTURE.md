# Architecture

OntoJev is one Python package with a sequential research loop. FastAPI reads its SQLite
projections and artifacts; Next.js polls FastAPI. Modules express scientific and provider
boundaries without services, job queues, or generic workflow machinery.

Status labels used throughout: **IMPLEMENTED** (code exists and is tested), **PLANNED**
(approved direction, no code), **UNVERIFIED** (not established by a retained check).

## Implemented responsibility model

| Responsibility | Owner | Must not own |
|---|---|---|
| GDC retrieval, allowlists, budgets, caching | `gdc` | Interpretation, unrestricted URLs, file downloads, credentials |
| Populations, calculations, method registry | `science` | Model SDKs or provider judgments |
| Immutable typed records and identity hashes | `domain` | Network or database operations |
| Typed Jev questions, projection, normalized answers, provider adapter | `jev` | Scientific truth or generative prose |
| Sequence, routing, live/fixture orchestration, ranking policy | `research` | New scientific formulas |
| Event commit, projections, artifacts | `storage` | Independent lifecycle rules |
| Deterministic dossier rendering | `dossier` | Invented numerical facts |
| Read API and event renderers | API, web, CLI | Research decisions |

Boundaries that are invariants, not conventions:

- **One GDC transport.** `cancerjev/gdc/transport.py` is the only module that opens a socket to
  GDC. It has no credential parameter and never constructs `Authorization` or `X-Auth-Token`.
  Host, paths and methods are allowlisted; redirects are refused; response size, request count,
  page count and case/gene ID counts are capped per run.
- **One Jev adapter.** `cancerjev/jev/typesafe_adapter.py` is the only module that knows the
  provider wire contract or SDK. `science` and `domain` never import provider types.
- **Raw → Jev is never direct.** GDC bytes → strict parser → normalized records → population
  validation → deterministic method → StatisticalState → deterministic projection → Jev. A Jev
  input can never contain unparsed provider payloads.
- **One event authority.** All operational changes commit through `Repository.append_event`;
  every attempt that started is finalized in the `gdc_attempts` ledger, which is operational
  bookkeeping and never a second status source.
- **One persistence owner.** `storage` is the only layer that writes SQL; `research` and `jev`
  register records through narrow `Repository` methods inside the same event transaction.

Fixture and live paths share every boundary above; only the orchestrator and lane
implementations differ (`research/orchestrator.py` for the fixture demo, `research/live.py` for
real runs). Run `mode` (`FAKE`/`LIVE`) is stored on the run, artifacts keep their labels, and
fixture and live records are never mixed in rankings, caches or dossiers.

## Configuration ownership

- `ResearchSpec` (`cancerjev/research/specs.py`) owns reproducible research parameters: domain,
  cohort, exact `project_id`, bounded case-page size, case-batch size, cohort ceiling,
  discovery-gene limit, count-gene limit, candidate limit and expression file sample size.
  `LUAD_RESEARCH_V1` is the only production specification. A future single-cohort spec (for
  example TCGA-LUSC) reuses the same GDC/science core without modifying it.
- `Settings` (`cancerjev/config.py`) owns operational configuration: paths, timeouts, transport
  byte/request budgets, cache enablement, and provider/model identity. The two are never mixed.
  Local development may place these values plus `TYPESAFE_API_KEY` in a gitignored `.env.local`;
  `load_local_env` loads them only when the real environment does not already define the name,
  never logs values, and is disabled by `CANCERJEV_NO_DOTENV=1`. Provider keys remain server-side
  and never enter `ResearchSpec` or any artifact.
- GDC code owns endpoint allowlists, allowed fields, open-access enforcement, parsers and
  absolute safety caps. Those are code, not `ResearchSpec` values; there are no
  runtime-configurable arbitrary GDC queries.

## Run path

**Fixture (Phase 1, IMPLEMENTED):** inventory → fast search (fake) → synthetic
StatisticalStates → fixture wide ranking → promoted candidates → fake deep evidence → fake Jev
vectors → fixture hypotheses → fixture follow-up → dossier. Zero provider calls.

**Live Phase 2 (IMPLEMENTED):** `LUAD_RESEARCH_V1` → inventory (`/status`, `/projects`) → one
exact project selected by `project_id` → bounded paginated case frame (`/cases`, `size ≤250`,
`sort=case_id`, ≤10 pages) → mutation discovery (`top_mutated_genes_by_project`) → gene identity
(`/genes`) → gene-specific counts (`top_cases_counts_by_genes`) → SSM coverage
(`mutated_cases_count_by_project`) → open-file provenance (`/files`, `access=open`) → batched
expression availability and local values (each ≤250 cases × ≤10 genes) → deterministic methods →
real StatisticalStates → API/UI inspection. Provider expression summaries are retained only
when the complete cohort fits one admitted request; per-batch medians/standard deviations are
never combined. Zero Jev and zero LLM calls.

**Live Phase 3 (IMPLEMENTED):** the same run continues through a single-project
`jev-state-projection-v2` → one Jev request per state with the `wide-v3` question set → fail-closed
validation → cache → deterministic baseline and explicit Jev admission rankings → at most three
candidate promotions. The deterministic gate may exclude incomplete or unobserved evidence, and
the Jev policy may return `ABSTAIN` with zero promotions. Baseline top-3 is comparison-only.
Changed ranking is not evidence of improved research decision quality; that remains a separate
evaluation.

**Live Phase 4 first slice (IMPLEMENTED, 2026-09-23):** only when the operator names one promoted
candidate explicitly (`--deep-candidate`), the same run continues through `DEEP_ANALYSIS` → accept
the candidate's immutable StatisticalState as E0 (verify the retained artifact hash and recorded
`state_hash`) → record the baseline EvidenceState revision → Python computes the eligible registered
deterministic actions → execute exactly one selected action over retained evidence → record the
immutable EvidenceState revision E1 whose parent is E0. Nothing is acquired from GDC and no model is
called. Wide admission never dispatches a follow-up; zero eligible actions, an exhausted budget, an
already-executed action or an unmatched selection record a typed abstention, and a deterministic
failure leaves E0 and the candidate unchanged. When wide admission selects nothing, the operator may
instead name a wide-evaluated state (`gene:<SYMBOL>`/`state:<STATE_ID>`); that creates the candidate
with recorded `operator-selection-v1` provenance and still consumes a promotion slot.

**Live Phase 4 deep fan-out (IMPLEMENTED, 2026-09-23):** after E1 is recorded, one Deep Jev fan-out
judges the revision plus the eligible registered action set with the versioned `deep-v1` question set
(`JEV_DEEP_STARTED`, one evaluation per revision recorded as `purpose=DEEP` /
`input_ref_kind=EVIDENCE_STATE` via `JEV_DEEP_EVIDENCE_JUDGED`), and the Python next-move policy
(`deep-policy-v1`) records one typed move (`COMPLETE`/`FOLLOW_UP`/`ABSTAIN`) with its dimensions and
reason. Jev judges; Python decides: a judgment never selects, authorizes or executes an action, and
the recorded move is deliberately not dispatched by the policy.

**Live Phase 4 dispatch (IMPLEMENTED, 2026-09-23):** a recorded `FOLLOW_UP` may be dispatched once per
run, only when the operator authorizes it (`--deep-followup`), only to the sorted-first distinct
eligible registered action for that revision (`CHECK_REVISION_FAITHFULNESS_V1`, input kind
`EVIDENCE_STATE`), and only inside the existing follow-up and revision caps. The new immutable
revision `E2` has parent `E1`, cites its producing action, and is judged again by the same deep
fan-out; its producing action is excluded from its own eligible set, so the follow-on decision is
`NO_FURTHER_REGISTERED_ACTION`. Refusals are typed `NEXT_MOVE_DISPATCHED` records. Autonomous
iteration beyond one authorized dispatch, hypotheses and multi-candidate iteration remain
unimplemented; the autonomous loop below is unchanged.

## Simplification review

For every choice below the question was: "Is there a simpler design that satisfies the
requirement?"

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
| GDC HTTP stack | `requests`/`httpx` with hooks and retry plugins | stdlib `http.client` inside one transport |
| GDC caching | External cache service | SQLite `gdc_cache` + raw response artifacts keyed by canonical request hash and transport contract version |
| Scientific registry | Plugin/discovery framework | Dictionary of explicit method/action definitions and functions |
| Jev projection | Template engine, generic serializer | Plain dict builder plus canonical JSON hash and an included-field contract |
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
    config.py      # operational Settings (paths, budgets, provider/model)
    domain/        # runs, events, states, hypotheses, dossier, identity
    gdc/           # transport, endpoints, parsers, capture
    science/       # methods (registry + deterministic implementations)
    jev/           # contracts, questions, projection, service, typesafe_adapter
    research/      # orchestrator (fixture), live (Phase 2/3), wide, ranking, specs, fixtures
    storage/       # database (schema 4), repositories, artifacts, ownership
    cli/           # run/worker --live|--fixture, probe, show
    dossier/       # deterministic renderer
  apps/
    api/           # FastAPI read surface
    web/           # Next.js App Router UI
  tests/
    unit/ integration/ science/ contracts/ jev/ live/   # live tests disabled by default
  data/            # local database, artifacts, captures (gitignored)
```

## Future autonomous research direction (PLANNED, not implemented)

This is a responsibility model, not a mandate to create classes, services, tables or modules.
The smallest representation compatible with the existing repository is preferred; a refresh is
normally just another bounded `ResearchRun`.

```text
ResearchSpec
↓
GDC
↓
deterministic science
↓
StatisticalState
↓
WIDE JEV
↓
Python admission policy
↓
candidate investigation
↓
current immutable evidence
↓
Python computes eligible registered actions
↓
ONE DEEP JEV FAN-OUT where the state is shared
↓
Python next-move policy
│
├─ deterministic follow-up → new evidence → Deep Jev again
├─ bounded hypothesis generation → Python schema validation
│      → Python determines applicable registered tests → Jev hypothesis/test judgments → Python policy
├─ next candidate
├─ complete
└─ abstain
```

- Python owns loops, routing, candidate iteration, state transitions, budgets, action
  eligibility, side effects, registered-action execution, stopping and abstention.
- Jev evaluates narrow typed propositions against supplied state. It never computes a
  measurement, controls execution, creates action IDs, or proves scientific truth.
- A later generative LLM (PLANNED) may produce bounded hypotheses; Python validates their
  schema and determines applicable registered tests, and Jev evaluates them. The LLM never
  controls execution, creates measured values, authorizes endpoints, or emits executable code.
- Before broad autonomous expansion, Jev incremental value must be evaluated
  (deterministic baseline vs baseline + Jev on the same candidate universe and budget);
  changed ranking alone is not evidence of a better research decision.
- Do not introduce planner/director objects, agent frameworks, graph or workflow engines,
  frontier/cycle services, plugin systems or distributed queues. A next move can be a plain
  Python result (`FOLLOW_UP`, `GENERATE_HYPOTHESES`, `TEST_HYPOTHESIS`, `NEXT_CANDIDATE`,
  `COMPLETE`, `ABSTAIN`), and candidate selection can remain
  `candidate = next_eligible_candidate(...)`.

Use JSON and the standard library where sufficient; add NumPy/SciPy only with deterministic
science that needs them. No Parquet dependency is needed.
