# OntoJev architecture

Current architecture after the Stage 3 hard cutover (2026-09-25). Facts are labeled
IMPLEMENTED, PLANNED or UNVERIFIED. [Implementation status](IMPLEMENTATION_STATUS.md) owns
current facts; [the roadmap](DISCOVERY_ROADMAP.md) separates the next Stage 9 work from design.

## IMPLEMENTED: one typed runtime chain

```text
GDC open-access API
  -> strict provider parsers
  -> typed acquisition / lane records
  -> typed StatisticalState (schema 5)
  -> jev-state-projection-v4 -> wide-v3 questions -> validated typed answers
  -> Python admission (wide-policy-v2) -> Candidate
  -> immutable typed EvidenceState E0 (schema 4)
  -> operator-authorized registered action (explicit action id)
     -> immutable revision E1/E2
  -> jev-evidence-projection-v2 -> deep-v1 questions
  -> Python next-move policy (deep-policy-v2)
  -> optional bounded hypothesis generation
       (deterministic template by default; injected OpenRouter adapter on an
        explicitly authorized CLI path)
  -> jev-hypothesis-projection-v2 -> hypothesis-v2 critique
  -> dossier (schema 3), JSON + derived Markdown

Systematic pre-Wide funnel (Stage 4, `python -m cancerjev discover --live`):

  inventory -> cohort case frame
  -> fixed /genes universe enumeration (protein_coding, gene_id asc, ≤10 strict pages)
  -> ≤100-gene indexed count batches (coverage once) -> typed per-gene outcomes
  -> deterministic reduction (≤10 survivors) -> immutable MutationDiscoveryResult (schema 1)

Independent pre-Wide arms:

  Stage 5: fixed universe/case-frame expression acquisition -> local summaries and tails
           -> immutable ExpressionDiscoveryResult (schema 1)
  Stage 6: Stage 4 survivors/release/case frame -> bounded complete CNV occurrences
           -> category/caller/conflict summaries -> immutable CnvDiscoveryResult (schema 1)

Stage 7 cutover and held-data descriptor actions:

  exact Stage 4-6 binding (spec/release/cohort/universe/frame/survivors/entities)
  -> one schema-5 StatisticalState per Stage 4 survivor (`research/cutover.py`)
  -> shared descriptors (`science/descriptors.py`) back discovery and the
     SUMMARIZE_EXPRESSION_TAIL_V1 / SUMMARIZE_CNV_CATEGORIES_V1 actions
  -> several eligible actions require one explicit operator action id

Stage 8 finalization (`research/finalize.py`, `research/investigation.py`):

  terminal recorded move stops the arc with its actual policy reason
  -> FinalCandidateResult derived from the recorded run state
  -> no-jev-baseline-v1 read-only deterministic comparison
     (observed Jev path vs declared baseline replay; NOT_COMPARABLE when unsupported)
  -> authoritative JSON dossier (schema 3) embedding the result and comparison;
     Markdown derived from the same structured payload
  -> DOSSIER_READY -> CANDIDATE_COMPLETE -> next candidate -> RUN_COMPLETED

Optional evaluation harness (outside the numbered runtime stages):

  `research/prospective.py` + `research/evaluation.py`: blinded grouped labels,
  arm comparison, grouped bootstrap — operator-supplied documents only; the
  runtime never invokes them and candidate completion never depends on them
```

- `research/live.py` runs the shared `LiveOrchestrator`; `research/orchestrator.py` runs the
  fixture demonstration through the same orchestrator with `FixtureTransport` and
  `FixtureJevAdapter` (mode `FIXTURE`). There is no second execution engine and no
  independently implemented Phase-1 engine.
- Domain records are unsuffixed (`StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`). Operational ids and hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialized schemas are StatisticalState 5, EvidenceState 4, ResearchSpec 7,
  MutationDiscoveryResult 1, ExpressionDiscoveryResult 1 and CnvDiscoveryResult 1; SQLite is schema 5.
  Older/unknown schemas are rejected fail-closed.
  There are no migrations and no
  legacy readers; historical databases and artifacts are retained, not rewritten.
- Question sets remain `wide-v3`, `deep-v1` and `hypothesis-v2`; they were not redefined by the
  cutover. Projections are `jev-state-projection-v4` (adds observed CNV fields and the
  Python-computed `eligible_followups` list), `jev-evidence-projection-v2` and
  `jev-hypothesis-projection-v2`.
- `next_move()` records exactly one typed move (`COMPLETE`, `FOLLOW_UP`, `GENERATE_HYPOTHESES`
  or `ABSTAIN`) and never dispatches it. `run_candidate_investigation()` owns dispatch and
  stopping; repeated `--deep-candidate` selections share the three promotion slots;
  `--deep-followup` authorizes iteration and `--deep-hypotheses` requests bounded generation
  without rewriting the recorded move. Early ineligible/failed paths can end without a dossier.
- The registered actions are `CHECK_EVIDENCE_INTEGRITY_V1`,
  `CHECK_REVISION_FAITHFULNESS_V1`, `SUMMARIZE_EXPRESSION_TAIL_V1` and
  `SUMMARIZE_CNV_CATEGORIES_V1` (registry version 3). They check held evidence or restate held
  case-labelled values with predeclared methods, acquire nothing, call no model and measure no
  new biology. `FOLLOWUP_LIMIT = 3` and `EVIDENCE_ITERATION_LIMIT = 2` bound one candidate arc.
  With several eligible actions, an operator must request exactly one action id
  (`EXPLICIT_ACTION_REQUIRED` otherwise).
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

- `research/discovery.py` owns the systematic pre-Wide funnel (Stage 4): fixed universe
  enumeration, batched counts with one shared coverage record, per-gene typed outcomes and the
  deterministic reducer, persisting one immutable schema-1 result via the existing
  artifact/event/repository path. It generates no StatisticalState, no Wide candidate and no Jev
  call; the provider top-mutated ranking stays a labelled comparator. No Stage-4 orchestrator
  object exists and none is approved.
- `research/expression_discovery.py` owns the independently invoked Stage 5 expression arm;
  `research/cnv_discovery.py` owns the independently invoked Stage 6 survivor-only CNV arm.
  Both persist immutable typed results without creating a StatisticalState, candidate or Jev call.

## Implemented discovery composition (Stages 4-7)

```text
bounded enumerated gene universe (IMPLEMENTED, Stage 4)
 -> cheap indexed evidence (IMPLEMENTED, Stage 4)
 -> deterministic reduction (IMPLEMENTED, Stage 4)
 -> richer survivor acquisition (IMPLEMENTED, Stage 6) -> typed lane results
 -> deterministic held-data actions -> typed StatisticalState
 -> optional semantic judgments
 -> bounded Python admission -> existing investigation loop
```

The mutation funnel and separately invoked expression and survivor-only CNV arms are implemented
and offline verified. Mutation-conditioned reduction still cannot claim CNV-only sensitivity.
Stage 7 action/cutover contracts remain design, not current runtime behavior; see
[GDC strategy](GDC_STRATEGY.md) and [the roadmap](DISCOVERY_ROADMAP.md).

`ResearchSpec` composes intent, cohort, universe selection, enabled lane specifications,
versioned policies, allowed actions, scientific work limits and the output contract. `Settings`
retains paths, credentials, timeouts, providers/models and operational caps. Effective limits
are the stricter scientific and operational/absolute limits. Endpoint/field allowlists and
absolute safety caps stay in code.

## Verification status (2026-09-25)

- IMPLEMENTED and offline-verified: 555 offline pytest tests pass; `ruff check cancerjev apps
  tests` is clean; scoped strict `mypy` (the explicit file list in `pyproject.toml`) passes.
- UNVERIFIED in this environment: browser acceptance at `tests/browser/` (own Playwright
  config/package; CI runs it as a separate job); live GDC, TypeSafe/Jev and OpenRouter
  acceptance (no credentials).
- No scientific readiness, incremental Jev value or production use is claimed. See
  [testing](TESTING.md) and [implementation status](IMPLEMENTATION_STATUS.md).
