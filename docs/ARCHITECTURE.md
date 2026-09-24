# OntoJev architecture

Reviewed 2026-09-24 at `42b05d40e6edafec0b8613e7dd154a60a46e4fee`.
That architecture review changed documentation only. Stage 1 (2026-09-25) subsequently added
standalone frozen scientific contracts/versioned codecs and a strict ResearchSpecV2 composition
reader. These are not wired into the production flow below; current writers, questions, policies,
transport and database schema are unchanged. [Implementation status](IMPLEMENTATION_STATUS.md) owns current
facts; [the roadmap](DISCOVERY_ROADMAP.md) separates implementation gates from design.

Stage 2 connects validated legacy readers to Deep acceptance and scientific API reads. Dossier
assembly accepts only verified authoritative revisions/hypotheses/evaluations; corruption refuses
publication. Cache hydration validates its original artifacts and contracts before policy can use
answers. Internal scientific composition remains the Stage 3 transition, not a new v3 runtime yet.

## IMPLEMENTED: bounded deterministic-first research

The fixture slice remains offline. Production has one frozen LUAD_RESEARCH_V1, never LUAD/LUSC pooling.

```text
ResearchSpec + operational Settings
 -> bounded anonymous GDC -> strict provider parsers -> deterministic methods
 -> StatisticalState v2 -> projection v2 -> Wide wide-v3
 -> Python wide-policy-v2 -> zero to three admitted candidates
 -> explicit operator selection (also supports a successfully wide-evaluated state)
 -> accept E0 -> integrity action -> E1 -> Deep deep-v1
 -> Python deep-policy-v2 -> separately authorized dispatch -> at most E2
 -> optional bounded hypotheses -> hypothesis-v2 review -> dossier JSON/Markdown
```

next_move() records COMPLETE, FOLLOW_UP, GENERATE_HYPOTHESES or ABSTAIN, never executes.
run_candidate_investigation() owns dispatch and stopping. Repeated --deep-candidate selections share
three promotion slots. --deep-followup authorizes iteration; --deep-hypotheses requests hypotheses
without rewriting the recorded move. Early ineligible/failed paths can end without a dossier.

The two registered actions are CHECK_EVIDENCE_INTEGRITY_V1 and CHECK_REVISION_FAITHFULNESS_V1.
They check held evidence, acquire nothing and measure no new biology. Hypotheses default to templates.
The CLI can inject the implemented llm/openrouter.py adapter when configured with a model and
OPENROUTER_API_KEY. Model use is conditional, not absent. Generated text is never evidence.
No paid model was called in this architecture pass.

## Ownership

| Owner | Owns | Must not own |
|---|---|---|
| Domain | Scientific records, units, populations, identity and invariants | HTTP, SDK, SQLite, side effects |
| GDC | Fixed endpoints, bounded transport, provider schemas/parsing | LUAD biology, ranking, Jev routing |
| Science | Deterministic measurements, descriptors and method contracts | Provider calls or generated facts |
| Jev | Projections, questions, validated answers, adapter and evaluation coordination | Measurements, authorization or loop execution |
| Research | Intent, composition, acquisition scheduling, selection, dispatch, budgets and stopping | Raw SQL or provider envelope interpretation |
| Storage | SQL, artifact publication/read integrity, persisted representation | Scientific meaning or silent schema inference |
| API/renderer | Read and present committed records | Research initiation or independent status authority |

These are responsibilities, not new services. Domain ownership is incomplete today: scientific
states remain dictionary builders in science/research. [Domain models](DOMAIN_MODELS.md) specifies
the transition.

## PLANNED: smallest discovery composition

```text
bounded enumerated gene universe -> cheap indexed evidence -> deterministic reduction
 -> richer survivor acquisition -> typed lane results -> typed StatisticalState
 -> deterministic discovery dimensions -> optional semantic judgments
 -> bounded Python admission -> existing investigation loop
```

Begin with a 1,000-gene protein-coding index slice ordered by Ensembl ID and recorded offset/release,
not provider mutation rank. This is a reproducible subset of the 19,843 indexed protein-coding genes
observed in the campaign, not genome-wide coverage or an unbiased random sample. Mutation-conditioned
reduction cannot claim expression-only/CNV-only sensitivity. An independent expression arm requires
explicit enablement, workload reservation and evaluation. See [GDC strategy](GDC_STRATEGY.md).

Use ordinary functions: acquire common cohort frame, acquire one lane, compute typed lane result,
compose state, serialize. Add a module for a concrete independent lane, not a plugin system.
Do not extend ProjectFrame with more lane-specific optionals or the monolithic state builder with
more endpoint branches. Preserve transport, one Repository, event transactions and investigation loop.

ResearchSpec composes intent, cohort, universe selection, enabled lane specs, versioned policies,
allowed actions, scientific work limits and output contract. Settings retains paths, credentials,
timeouts, providers/models and operational caps. Effective limits are the stricter scientific and
operational/absolute limits. Endpoint/field allowlists and absolute safety caps stay in code.

## Operation ownership and admission

| Operation | Owner | Admission |
|---|---|---|
| IDs, counts, joins, missingness, integrity, eligibility | Deterministic Python | Current or typed transition |
| Distribution summaries and within-gene descriptive extremes | Deterministic classical statistics | Proposed with declared reference frame |
| Recurrence rates, association tests, survival effects | Classical statistics plus scientific review | Deferred: denominator/matching/censoring gaps |
| Contextual uncertainty relevance, eligible-action value, overclaim critique | Jev, composed by Python policy | Current retained; new uses experimental |
| Hypothesis wording | Template or injected generative model | Current, bounded, never observed facts |
| Calibration labels, interpretation, replication, wet-lab validation | Human/external validation | Required for scientific/value claims |

Jev cannot establish assay comparability, repair missing sample IDs, select a denominator, turn absence
into zero, authorize acquisition or confer causality.

## Responsibility stabilization

- science/methods.py: separate lane computations from aggregate serialization.
- research/live.py: extract concrete cohort/lane acquisition as those lanes are implemented.
- research/deep.py: move hydration to validated readers and evidence construction to typed constructors.
- science/actions.py: retain fixed registry; separate concrete implementations only when necessary.
- jev/service.py: share duplicated evaluation lifecycle after typed inputs/answers exist; preserve versions.

Large provider parsers and the single Repository are coherent; length alone warrants no split.
No ORM, DI framework, planner/director, workflow graph, microservices, distributed queue, arbitrary GDC
query DSL or universal science framework is approved. The historical cancerjev/ namespace stays.
