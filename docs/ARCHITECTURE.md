# OntoJev architecture

Current architecture after the Stage 3 hard cutover (2026-09-25). Facts are labeled
IMPLEMENTED, PLANNED or UNVERIFIED. [Implementation status](IMPLEMENTATION_STATUS.md) owns
current facts; [the roadmap](DISCOVERY_ROADMAP.md) separates the next Stage 4 work from design.

## IMPLEMENTED: one typed runtime chain

```text
GDC open-access API
  -> strict provider parsers
  -> typed acquisition / lane records
  -> typed StatisticalState (schema 4)
  -> jev-state-projection-v3 -> wide-v3 questions -> validated typed answers
  -> Python admission (wide-policy-v2) -> Candidate
  -> immutable typed EvidenceState E0 (schema 4)
  -> registered deterministic action -> immutable revision E1/E2
  -> jev-evidence-projection-v2 -> deep-v1 questions
  -> Python next-move policy (deep-policy-v2)
  -> optional bounded hypothesis generation
       (deterministic template by default; injected OpenRouter adapter on an
        explicitly authorized CLI path)
  -> jev-hypothesis-projection-v2 -> hypothesis-v2 critique
  -> dossier (schema 2), JSON + derived Markdown
```

- `research/live.py` runs the shared `LiveOrchestrator`; `research/orchestrator.py` runs the
  fixture demonstration through the same orchestrator with `FixtureTransport` and
  `FixtureJevAdapter` (mode `FIXTURE`). There is no second execution engine and no
  independently implemented Phase-1 engine.
- Domain records are unsuffixed (`StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`). Operational ids and hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialized schemas are StatisticalState 4, EvidenceState 4 and ResearchSpec 3; SQLite is
  schema 5. Older/unknown schemas are rejected fail-closed. There are no migrations and no
  legacy readers; historical databases and artifacts are retained, not rewritten.
- Question sets remain `wide-v3`, `deep-v1` and `hypothesis-v2`; they were not redefined by the
  cutover. Projections are `jev-state-projection-v3`, `jev-evidence-projection-v2` and
  `jev-hypothesis-projection-v2`.
- `next_move()` records exactly one typed move (`COMPLETE`, `FOLLOW_UP`, `GENERATE_HYPOTHESES`
  or `ABSTAIN`) and never dispatches it. `run_candidate_investigation()` owns dispatch and
  stopping; repeated `--deep-candidate` selections share the three promotion slots;
  `--deep-followup` authorizes iteration and `--deep-hypotheses` requests bounded generation
  without rewriting the recorded move. Early ineligible/failed paths can end without a dossier.
- The two registered actions are `CHECK_EVIDENCE_INTEGRITY_V1` and
  `CHECK_REVISION_FAITHFULNESS_V1` (registry version 2). They check held evidence, acquire
  nothing, call no model and measure no new biology. `FOLLOWUP_LIMIT = 3` and
  `EVIDENCE_ITERATION_LIMIT = 2` bound one candidate arc.
- Hypotheses default to deterministic templates. The CLI can inject the implemented
  `cancerjev/llm/openrouter.py` adapter when a model and `OPENROUTER_API_KEY` are configured;
  model use is conditional on that authorization, and generated text is never evidence.

## Ownership

| Owner | Owns | Must not own |
|---|---|---|
| Domain | Scientific records, units, populations, identity and invariants | HTTP, SDK, SQLite, side effects |
| GDC | Fixed endpoints, bounded transport, provider schemas/parsing | LUAD biology, ranking, Jev routing |
| Science | Deterministic measurements, descriptors, registered action implementations and method contracts | Provider calls or generated facts |
| Jev | Projections, questions, validated answers, adapter and evaluation coordination | Measurements, authorization or loop execution |
| Research | Intent, composition, acquisition scheduling, selection, dispatch, budgets and stopping | Raw SQL or provider envelope interpretation |
| Storage | SQL, artifact publication/read integrity, persisted representation | Scientific meaning or silent schema inference |
| API/renderer | Read and present committed records | Research initiation or independent status authority |

These are responsibilities, not new services. JSON remains a boundary representation for
events, storage, API/dossier presentation, generated-text requests and artifact provenance
envelopes; scientific consumers exchange typed records.

## Operation ownership and admission

| Operation | Owner | Admission |
|---|---|---|
| IDs, counts, joins, missingness, integrity, eligibility | Deterministic Python | Current |
| Distribution summaries and within-gene descriptive extremes | Deterministic classical statistics | Current where a declared method exists; new descriptors need a declared reference frame |
| Recurrence rates, association tests, survival effects | Classical statistics plus scientific review | Deferred: denominator/matching/censoring gaps |
| Contextual uncertainty relevance, investigation value, overclaim critique | Jev, composed by Python policy | Current retained versions; new uses experimental |
| Hypothesis wording | Template or injected generative model | Current, bounded, validated, never observed facts |
| Calibration labels, interpretation, replication, wet-lab validation | Human/external validation | Required for scientific/value claims |

Jev cannot establish assay comparability, repair missing sample IDs, select a denominator, turn
absence into zero, authorize acquisition or confer causality.

## IMPLEMENTED responsibility map

- `research/acquisition.py` owns concrete common-frame and lane acquisition;
  `research/live.py` retains research selection and sequencing.
- `science/mutation.py` and `science/expression.py` own lane computations;
  `science/methods.py` composes typed results and canonical serialization.
- `research/deep.py` uses verified hydration and immutable typed check revisions;
  `research/investigation.py` owns the bounded arc.
- `science/actions.py` holds the fixed registry; concrete implementations stay in that module
  until a split has a concrete invariant to follow.
- `jev/service.py` retains validated typed answers through the shared evaluation lifecycle and
  policy consumers; versions remain unchanged.
- Large provider parsers and the single `Repository` remain coherent; length alone warrants no
  split. No ORM, DI framework, planner/director, workflow graph, microservices, distributed
  queue, arbitrary GDC query DSL or universal science framework is approved.

## PLANNED: smallest discovery composition (Stage 4)

```text
bounded enumerated gene universe -> cheap indexed evidence -> deterministic reduction
 -> richer survivor acquisition -> typed lane results -> typed StatisticalState
 -> deterministic discovery dimensions -> optional semantic judgments
 -> bounded Python admission -> existing investigation loop
```

Stage 4 begins with a 1,000-gene protein-coding index slice ordered by Ensembl ID and recorded
offset/release, not provider mutation rank. This is a reproducible subset of the 19,843 indexed
protein-coding genes observed in the campaign, not genome-wide coverage or an unbiased random
sample. Mutation-conditioned reduction cannot claim expression-only/CNV-only sensitivity. An
independent expression arm requires explicit enablement, workload reservation and evaluation.
Proposed lane and action contracts are design, not current runtime behavior; see
[GDC strategy](GDC_STRATEGY.md) and [the roadmap](DISCOVERY_ROADMAP.md).

`ResearchSpec` composes intent, cohort, universe selection, enabled lane specifications,
versioned policies, allowed actions, scientific work limits and the output contract. `Settings`
retains paths, credentials, timeouts, providers/models and operational caps. Effective limits
are the stricter scientific and operational/absolute limits. Endpoint/field allowlists and
absolute safety caps stay in code.

## Verification status (2026-09-25)

- IMPLEMENTED and offline-verified: 652 offline pytest tests pass; `ruff check cancerjev apps
  tests` is clean; scoped strict `mypy` (the explicit file list in `pyproject.toml`) passes.
- UNVERIFIED in this environment: browser acceptance at `tests/browser/` (own Playwright
  config/package; CI runs it as a separate job); live GDC, TypeSafe/Jev and OpenRouter
  acceptance (no credentials).
- No scientific readiness, incremental Jev value or production use is claimed. See
  [testing](TESTING.md) and [implementation status](IMPLEMENTATION_STATUS.md).