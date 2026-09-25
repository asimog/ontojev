# OntoJev architecture

OntoJev is a system-owned autonomous research program of bounded, independently reproducible
campaigns. This document owns the structural description of the loop. Facts are labeled
IMPLEMENTED, PLANNED or UNVERIFIED; mutable versions (schemas, projections, question sets,
policies, registry) live only in the machine-checked [repository facts](REPOSITORY_FACTS.md);
factual claims live in [implementation status](IMPLEMENTATION_STATUS.md); stage ordering and
deferred work live in [the roadmap](DISCOVERY_ROADMAP.md).

## The loop

```text
RAW CANCER GENOMICS
        ↓
DETERMINISTIC COMPUTATIONAL GENOMICS
        ↓
TYPED FEATURES / DISCOVERY SIGNALS
        ↓
DETERMINISTIC BASELINE
        │
        ├── clear retain/drop
        │
        └── semantic review set
                   ↓
               ARM JEV
                   ↓
           CANDIDATE UNION
                   ↓
        INTEGRATED GENE STATES
                   ↓
                WIDE JEV
                   ↓
            PYTHON ADMISSION
                   ↓
            TARGET CANDIDATES
                   ↓
                DEEP JEV
                   ↓
          PYTHON ACTION POLICY
             ↙             ↘
   deterministic         bounded LLM
     follow-up            hypotheses
        ↓                    ↓
   new evidence          JEV CRITIQUE
        └──────────┬─────────┘
                   ↓
                DEEP JEV
                   ↓
             repeat / stop
                   ↓
                STAGE 8
                   ↓
       FINAL RESULT + DOSSIER
                   ↓
          JEV vs NO-JEV
                   ↓
            NEXT CANDIDATE
                   ↓
          CAMPAIGN COMPLETE
                   ↓
 VERSIONED CAMPAIGN-SELECTION POLICY
                   ↓
           NEXT CAMPAIGN / IDLE
```

Reading the loop honestly (IMPLEMENTED vs provisional):

- Deterministic half and investigation loop (IMPLEMENTED): bounded anonymous GDC acquisition →
  strict parsing → deterministic mutation/expression/CNV analysis → typed features →
  deterministic baseline ranking → Wide Jev → Python admission → target candidates → bounded
  investigation (Deep Jev, Python action policy, deterministic follow-ups, optional bounded LLM
  hypotheses with Jev critique) → Stage 8 final result + dossier → Jev-vs-no-JEV comparison →
  next candidate → campaign complete. Today "campaign" is one bounded `ResearchRun`; the
  continuous worker repeats bounded runs at the operational interval. The campaign-selection
  tail (named versioned policy selecting the next campaign or an explicit idle state) is
  PROVISIONAL.
- Discovery loop below Wide Jev (PARTIAL): the deterministic per-modality arms exist as
  separately invoked bounded commands, and the cutover composes canonical multi-lane states
  per survivor. Arm Jev, the deterministic candidate union over full-modality survivors, and
  the Stage 9 integrated-gene-state generalization are PROVISIONAL (see the skeleton below).
- The scientific rule everywhere in the loop: raw genomics never reaches Jev; Jev judges,
  Python decides and executes; missing is never a negative; discovery is never
  mutation-conditioned.

## PROVISIONAL TARGET ARCHITECTURE — Stage 9 discovery skeleton

SUBJECT TO THE SOURCE-GROUNDED STAGE 9 DESIGN REVIEWS. Structure only; no contracts are
frozen. Do not implement from this section without those reviews.

```text
gene universe
   ↓
deterministic mutation / expression / CNV analysis
   ↓
deterministic discovery features
   ↓
selective Arm Jev where scientifically justified
   ↓
candidate union
   ↓
integrated states
   ↓
Wide Jev
   ↓
target candidates
```

Design constraints recorded so far (provisional, review-gated): each modality independently
preserves genes (discovery is not mutation-conditioned); deterministic genomics acts as a
recall-oriented search-space compressor before Jev; Arm Jev is selective and must be
scientifically justified per modality; per-modality survivors are combined by a deterministic
union; the integrated state reuses the existing canonical state design rather than a parallel
model; the first scientific follow-ups stay narrow and sequential. See
[the roadmap](DISCOVERY_ROADMAP.md).

## IMPLEMENTED: one typed runtime chain

```text
GDC open-access API
  -> strict provider parsers
  -> typed acquisition / lane records
  -> canonical typed StatisticalState
  -> Wide Jev projection -> wide question set -> validated typed answers
  -> Python admission -> Candidate (≤3 promotion slots; zero is valid)
  -> immutable typed EvidenceState E0
  -> operator-authorized registered action (explicit action id)
     -> immutable revision E1/E2
  -> Deep Jev evidence projection -> deep question set
  -> Python next-move policy: COMPLETE / FOLLOW_UP / GENERATE_HYPOTHESES / ABSTAIN
     (recorded; never dispatched by the policy that recorded it)
  -> optional bounded hypothesis generation
       (deterministic template by default; injected OpenRouter adapter on an
        explicitly authorized CLI path)
  -> Jev hypothesis projection -> hypothesis question set critique
  -> Stage 8: deterministic FinalCandidateResult
     -> read-only no-Jev-baseline comparison (NOT_COMPARABLE where unsupported)
     -> authoritative JSON dossier (JSON + derived Markdown)
     -> DOSSIER_READY -> CANDIDATE_COMPLETE -> next candidate -> RUN_COMPLETED
```

Pre-Wide discovery is implemented as separately invoked bounded commands (never fused into
the candidate runtime path):

- `discover` — release-bound indexed protein-coding universe prefix (fixed, non-configurable
  builder), ≤100-gene indexed mutation-count batches with one shared coverage record, exactly
  one typed outcome and disposition per requested gene, deterministic count-descending
  reduction to ≤10 survivors, immutable persisted `MutationDiscoveryResult`.
- `discover-expression` — same release-bound universe and cohort case frame; ≤100-gene ×
  ≤250-case batches; case-labelled UQFPKM values with complete missingness accounting; local
  `log2` summaries and the predeclared within-gene Tukey tail descriptor; immutable persisted
  `ExpressionDiscoveryResult`.
- `discover-cnv` — Stage 4 release/frame/survivor binding only; complete bounded CNV
  occurrence queries with provider category/caller/sample context; immutable persisted
  `CnvDiscoveryResult`.

No provider rank, `_score`, Jev, LLM, census status or hidden biological knowledge enters any
reduction; the provider top-mutated ranking is a labelled comparator only.

Cutover and finalization:

- `research/cutover.py` binds the Stage 4-6 artifacts exactly (spec, release, cohort, universe,
  frame, survivors, entities) and composes one canonical `StatisticalState` per survivor with
  the selection-bias limitation recorded; any cross-stage drift is a typed refusal.
- Shared deterministic descriptors back both discovery summaries and the held-data descriptor
  actions; several eligible actions require one explicit operator action id.
- `research/finalize.py` derives `FinalCandidateResult` from the recorded run state, computes
  the read-only `no-jev-baseline-v1` comparison over the same evidence (no mutation, no action,
  no hypothesis, no model; unsupported dimensions are `NOT_COMPARABLE`, never invented), and
  persists the authoritative dossier; refusal leaves the candidate failed, never complete.
  Admission provenance comes from persisted candidate records.

- `research/live.py` runs the shared `LiveOrchestrator`; `research/orchestrator.py` runs the
  fixture demonstration through the same orchestrator with `FixtureTransport` and
  `FixtureJevAdapter` (mode `FIXTURE`). There is no second execution engine.
- Domain records are unsuffixed (`StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`). Operational ids and hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialization is versioned and fail-closed; current versions live in the
  [repository facts](REPOSITORY_FACTS.md). Older/unknown schemas are rejected; there are no
  migrations and no legacy readers; historical databases and artifacts are retained, not
  rewritten.
- Hypotheses default to deterministic templates. The CLI can inject the implemented
  `cancerjev/llm/openrouter.py` adapter when a model and `OPENROUTER_API_KEY` are configured;
  model use is conditional on that authorization, and generated text is never evidence.

## Autonomous program vs researcher route

- The system-owned autonomous program is the primary product: bounded campaigns that run
  without human control of candidate selection, Jev promotion, follow-up selection, hypothesis
  approval, iteration authorization or candidate completion (Stage 9 reorientation target,
  provisional pending design reviews; today's deep path records explicit operator
  authorization as the implemented CLI control, to remain only as a debug override).
- An optional Researcher Lab (future, isolated) may run researcher-defined investigations on
  the same scientific engine. Researcher-run state, evidence, candidate queues, hypotheses,
  policies and results are isolated from the autonomous program at runtime; influence on
  future autonomous behavior occurs only through an explicit versioned code/scientific change
  outside runtime.
- The API/UI is an observatory over committed records; it never initiates or influences
  research.

## Ownership

| Owner | Owns | Must not own |
|---|---|---|
| Domain | Scientific records, units, populations, identity and invariants | HTTP, SDK, SQLite, side effects |
| GDC | Fixed endpoints, bounded transport, provider schemas/parsing | LUAD biology, ranking, Jev routing |
| Science | Deterministic measurements, descriptors, registered action implementations and method contracts | Provider calls or generated facts |
| Jev | Projections, questions, validated answers, adapter and evaluation coordination | Measurements, authorization or loop execution |
| Research | Intent, composition, acquisition scheduling, selection, dispatch, budgets, stopping and campaign progression | Raw SQL or provider envelope interpretation |
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
- `research/discovery.py`, `research/expression_discovery.py` and `research/cnv_discovery.py`
  own the three deterministic discovery arms; each persists one immutable typed result without
  creating a StatisticalState, candidate or Jev call.
- `science/actions.py` holds the fixed registry; concrete implementations stay in that module
  until a split has a concrete invariant to follow.
- `jev/service.py` retains validated typed answers through the shared evaluation lifecycle and
  policy consumers; versions live in the [repository facts](REPOSITORY_FACTS.md).
- Large provider parsers and the single `Repository` remain coherent; length alone warrants no
  split. No ORM, DI framework, planner/director, workflow graph, microservices, distributed
  queue, arbitrary GDC query DSL or universal science framework is approved.

`ResearchSpec` composes intent, cohort, universe selection, enabled lane specifications,
versioned policies, allowed actions, scientific work limits and the output contract. `Settings`
retains paths, credentials, timeouts, providers/models and operational caps. Effective limits
are the stricter scientific and operational/absolute limits. Endpoint/field allowlists and
absolute safety caps stay in code.

## Verification status

The date-stamped record of what is IMPLEMENTED / PLANNED / UNVERIFIED, and which gates were
executed in which environment, lives in [implementation status](IMPLEMENTATION_STATUS.md);
the offline documentation-facts contract additionally enforces
[repository facts](REPOSITORY_FACTS.md). No scientific readiness, incremental Jev value or
production use is claimed from any demonstration.
