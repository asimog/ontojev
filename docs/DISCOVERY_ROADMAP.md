# Discovery implementation roadmap and deliverable index

Documentation architecture contract, reviewed against
`42b05d40e6edafec0b8613e7dd154a60a46e4fee` (main) on 2026-09-24 UTC.
No discovery code, tests, dependencies or frontend were changed; no commit/push.
The next implementation task must explicitly authorize code changes.

## Decision

OntoJev has a strong bounded deterministic foundation, but expanding the dictionary-shaped internal
domain unchanged is unsafe. Stabilize typed state/lane contracts, persisted hydration and dossier
availability first. Admit broader indexed mutation counts, case-labelled expression descriptors and
narrow complete CNV-positive occurrence queries. Do not claim genome-wide discovery, matched
cross-modal inference or scientific Jev value.

## Ordered acceptance gates

| Stage | Concrete work | Acceptance before proceeding |
|---|---|---|
| 0: factual baseline | This documentation reconciliation and bounded reality campaign | Current/proposed/historical authority clear; no forbidden diff; evidence limitations explicit |
| 1: scientific contracts | Frozen measurement/population/quality/state/evidence/check variants; direct version codecs; typed existing seams | Observed-null impossible; malformed/unknown schemas fail typed; v1/v2 artifacts/hashes preserved; scoped static gate and focused offline tests |
| 2: integrity of consumption | Hash+schema-validate dossier inputs, cache answers, candidate evidence; typed hypothesis drafts | Corrupt/missing revisions never OBSERVED; invalid cache never drives policy; unknown test IDs rejected; old valid fixtures replay unchanged |
| 3: lane composition | Separate common acquisition frame from mutation/expression results; compute before serialization | Same current accepted measurements/identity for legacy path; row/batch permutation tests; no repeated internal reparsing |
| 4: bounded broad universe | Explicit release/filter/ordered 1,000-gene manifest, count batches, deterministic reduction | Unique IDs/totals/page guards; absence not zero; all selection/rejection reasons retained; within original request/byte caps |
| 5: independent expression arm | Optional explicitly budgeted case-labelled descriptors and within-gene extremes | Complete declared population/missingness; not tumor-normal/causal; no sample-matching claim; report lane-specific recall/coverage |
| 6: narrow CNV lane | Fixed builders and strict occurrence parser; complete survivor queries only | Real fixtures for generic Loss, missing sample ID, mixed callers; conflict/dedup policy; no neutral/negative inference; budget exhaustion gives PARTIAL/INELIGIBLE |
| 7: actions and semantic experiments | Reuse investigation loop; registered held-data descriptor actions; separate experimental questions/features | Method contracts/units/populations and authorization enforced; explicit model attempt/token budget; unchanged wide-v3/deep-v1 behavior |
| 8: prospective evaluation | Blinded grouped labels, fixed dev/holdout, ablations and resource comparison | Pre-registered improvement/tolerance gate met with uncertainty or remain experimental/disable; no ranking-only value claim |
| 9: conditional inferential extensions | Matched mutation-expression/CNV-expression, survival, later scRNA | Separate source/matching/reference/censoring/statistical review; not unlocked by finishing earlier engineering stages |

Stages 1–3 are BLOCK BEFORE DISCOVERY ARCHITECTURE implementation, not a separate aesthetic cleanup.
Stages 4–7 FIX AS PART OF NEW ARCHITECTURE. SDK HTTP/spend accounting blocks scaling paid model work,
not offline contract implementation. Retain the small deterministic baseline throughout.

## Deterministic funnel and feature definitions (PLANNED)

Universe: release-bound first 1,000 protein-coding Ensembl IDs by ascending ID at declared offset.
The prefix is reproducible but biased and incomplete for the genome. No known-target roster or
provider top-mutated rank enters this new selector. Preserve provider-ranked current baseline separately.

Initial reduction: rank complete observed LUAD affected-case counts descending, tie by gene ID;
retain<=10 survivors with reasons. Missing/incomplete counts are not eligible zeroes. This is a
mutation-conditioned funnel, not comprehensive multi-lane discovery. A parallel expression arm must
be explicitly scheduled before reduction if expression-only findings are desired; otherwise report
that blind spot. CNV broad occurrence acquisition is rejected: even 100 genes reported 21,032 rows.

| Feature | Exact meaning / population / reference | Availability and claim boundary |
|---|---|---|
| Mutation indexed recurrence count | Unique affected-case count supplied for gene/LUAD by validated aggregate | Count, NOT callable recurrence fraction; explicit zero preserved, missing bucket NOT_OBSERVED |
| Expression location/dispersion | Median/sample SD/min/max of finite log2(UQFPKM+1) for one gene over declared returned case-labelled frame | Descriptive cohort slice; missing rows/columns explicit; SD n>=2 |
| Expression extreme | Proposed within-gene empirical tail: values below Q1-1.5*IQR or above Q3+1.5*IQR; Q1/Q3 via declared linear interpolation h=(n-1)p; count/list IDs | Experimental descriptor, n>=20 complete declared valid frame; IQR=0 -> DEGENERATE_REFERENCE, no tail ranking; not differential expression, patient diagnosis or p-value |
| CNV gain/loss/amplification/deletion | Provider label on complete bounded gene/case occurrence query; unique cases per explicit category and caller context | Amplification means provider category only; generic Loss distinct from Homozygous Deletion; absent !=neutral; do not sum overlapping case categories |
| Cross-lane presence overlap | Set intersection of positive indexed case IDs for the same gene, only if both complete query frames exist | Descriptive presence, not matched assay effect/coherence; insufficient now for expression sample matching |
| Quality conflict | Explicit contradictory duplicate IDs/calls or failed invariants | Deterministic data conflict, not biological contradiction |
| Biological coherence/conflict | Requires predefined matched association/effect proposition and compatible reference | NOT ADMITTED in this phase |

The n>=20 tail descriptor guard is a proposed stability policy, not proof of power or normality.
Feature version, quantile convention, selected/valid/missing IDs and reference frame enter identity.
No imputation, reference pooling, normal controls or causal interpretation is assumed.
Discovery metrics are selected on the same data and cannot be repackaged as confirmatory p-values.

## Registered actions and contract change

Current actions are integrity checks only. Adding a measurement-producing action requires an explicit
versioned rule change in AGENTS/science contracts, not quietly treating a descriptor as an integrity
check. Acquisition-capable actions additionally require a declared fixed request plan and reservation
before sending; no generative/model output may supply an endpoint/query.

| Proposed action | Input / question / method / output | Eligibility, reservation and decision |
|---|---|---|
| Existing integrity and revision-faithfulness checks | Current typed-input transition; unchanged check semantics | KEEP; no acquisition/model/new biology |
| SUMMARIZE_EXPRESSION_TAIL_V1 | Held typed case-labelled values; does the declared distribution contain empirical tail observations? Exact quantile/tail rule above; case counts/IDs and coverage | ADMIT as proposed descriptive measurement action only after explicit action-contract change; n>=20, IQR>0, declared complete input frame; zero GDC reservation; no p/q |
| SUMMARIZE_CNV_CATEGORIES_V1 | Held complete typed occurrences; count distinct cases for each provider category, retain conflicts and caller/source refs | ADMIT as proposed descriptive measurement action after contract change; complete filter-bound query, dedup invariant; no neutral denominator; zero new acquisition |
| ACQUIRE_SURVIVOR_CNV_V1 | Fixed bounded gene/project query -> typed evidence outcome | LATER acquisition contract; reserve remaining pages/bytes/attempts pessimistically, refuse if worst-case plan exceeds remaining envelope; never broaden to finish |
| MUTATION_EXPRESSION_ASSOCIATION | Matched mutation-status groups versus expression | INELIGIBLE now; design conditions below |
| CNV_EXPRESSION_ASSOCIATION | Matched category versus expression | INELIGIBLE now; design conditions below |
| SURVIVAL_ASSOCIATION | Time/event and exposure groups | LATER; censoring/clinical selection and confounding contract absent |
| Project stratification / leave-one-project-out | Multiple independent comparable projects | REJECT for current single LUAD cohort |
| Generic missingness action duplicating integrity arithmetic | Same existing evidence check | REJECT unless a distinct falsifiable operation is demonstrated |

### Deferred association contracts (not executable admission)

No association action is ADMIT NOW, because exact matching/reference conditions are unresolved.

| Required element | Mutation-expression | CNV-expression |
|---|---|---|
| Match/unit | Same selected tumor sample, case and gene with explicit aliquot mapping; one independent case observation | Same requirement plus declared CNV caller/category source |
| Population/reference | Gene-callable mutation-positive versus validated callable-negative cases | Explicit gain/amplification versus validated neutral category, not absence |
| Eligibility | Complete input population, no unresolved duplicates, assay-compatible workflows, known exclusions | Additionally no conflicting category/caller interpretation |
| Estimator/test proposal | Descriptive median log2-expression difference; two-sided permutation difference test only after scientific approval | Same contrast for a predeclared category comparison; no numeric CNV correlation until scale comparable |
| Effect/uncertainty | Median difference in log2(UQFPKM+1); bootstrap CI grouped by independent case, fixed recorded seed/replicates | Same unit; preserve category/reference definitions |
| Minimum sample requirement | Proposal n>=20 per eligible group plus separate power/precision review; threshold alone not validation | Same; rare category may remain ineligible |
| Missingness | Exclude and enumerate missing measurements/mapping/callability; no imputation as negative | Exclude missing/ambiguous category or expression; never infer neutral |
| Multiple testing | Pre-register all gene/action contrasts in family; BH only where assumptions accepted; report selection bias; independent validation required for confirmation | Same, including all tested categories, not survivors-only posthoc family |
| Provenance/output | Frame hashes, exact source records, method/seed/parameters, exclusions, effect/CI/p/q or explicit ineligible outcome | Same plus caller/category and matched sample refs |
| Acquisition reservation | Initially held-data only, zero requests; future acquisition requires separate fixed budgeted contract | Same |

The statistical procedures above are design candidates awaiting review, not a supported biological
analysis or a dependency installation request. Unknown matching cannot be “resolved” by Jev.
No wet-lab experiment, drug prediction or clinical recommendation is admitted by this architecture.

## Later hardening and ignore list

LATER: strict cursor scalar/size validation; operational clock injection only if needed; backup/retention;
OpenRouter resolved immutable model identity; remove unused EvaluationContext when touched.
Do not build repository hierarchies, universal lane registries, DI frameworks, workflow/agent engines,
microservices, broad data mirrors or arbitrary provider-query tools. Ignore stylistic dictionary counts,
dynamic ID maps, boundary JSON, readable helpers, operational UUIDs and the historical package namespace.

## The 32 deliverables

The supplied plan requests 32 deliverables without a separately numbered 32-item list. This index
makes its substantive requirements independently reviewable rather than claiming an unavailable
external numbering scheme.

| # | Deliverable | Authoritative location |
|---|---|---|
| 1 | Starting HEAD, scope and verification status | IMPLEMENTATION_STATUS / this document |
| 2 | Current implemented workflow truth | [Architecture](ARCHITECTURE.md) |
| 3 | Prior-audit recheck with defect/risk distinction | [Python review](PYTHON_CORE_REVIEW.md) |
| 4 | Type-evidence flow and Any classification | Python review |
| 5 | Dependency seams and static coverage | Python review / TESTING |
| 6 | Official GDC authority and mappings | [Source review](SOURCE_REVIEW.md) / GDC strategy |
| 7 | Anonymous request/capture/provenance register | [Captures](GDC_DISCOVERY_CAPTURES.md) |
| 8 | GDC reality matrix and admission decisions | [GDC strategy](GDC_STRATEGY.md) |
| 9 |100/1000-gene measured versus estimated workloads | GDC strategy / GDC_BUDGETS |
|10 | Universe source, completeness and bias | Architecture / funnel above |
|11 | Case/sample/aliquot and duplicate handling | GDC strategy / DOMAIN_MODELS |
|12 | Denominators, missingness and sufficiency | GDC strategy / SCIENTIFIC_INVARIANTS |
|13 | Operation ownership | Architecture |
|14 | Modular ResearchSpec composition | [Domain models](DOMAIN_MODELS.md) |
|15 | Common entity/population/universe/method/provenance records | Domain models |
|16 | Measurement variants and invariants | Domain models |
|17 | Mutation/expression/CNV lane contracts | Domain models / GDC source trace |
|18 | Typed StatisticalState and immutable EvidenceState | Domain models |
|19 | Action/check/outcome/candidate/hypothesis contracts | Domain models |
|20 | Typed Jev answers and separate semantic features | Domain models / JEV_DESIGN |
|21 | Serialization, version handling and history compatibility | Domain models / PERSISTENCE |
|22 | Scientific versus operational identity | Domain models / SCIENTIFIC_INVARIANTS |
|23 | Systematic funnel and deterministic feature definitions | This document |
|24 | Registered actions and deferred association contracts | This document |
|25 | Installed/official TypeSafe skill and documentation review | [Jev design](JEV_DESIGN.md) |
|26 | Full cookbook/pattern adoption and failure matrix | Jev design |
|27 | Current and proposed versioned questions | [Questions](JEV_QUESTIONS.md) |
|28 | Blinded calibration, splits, labels and ablations | [Testing](TESTING.md) |
|29 | Incremental value, uncertainty and human-review gates | Testing |
|30 | Implemented/proposed GDC/Jev/LLM costs, latency and budgets | [Budgets](GDC_BUDGETS.md) |
|31 | Reconciled documentation authority and historical notes | IMPLEMENTATION_STATUS / SOURCE_REVIEW |
|32 | Ordered roadmap, blockers, deferred/rejected work and handoff | This document |

## Unresolved limitations

No callable mutation-negative or CNV-neutral denominator; no expression sample/aliquot resolution;
incomplete genome universe and mutation-first selection bias; generic CNV Loss categories; numerical
CNV caller compatibility not established; survival censoring/exclusions not audited; no LUAD scRNA
source in sampled metadata; no prospective Jev labels/value result; no measured model invoice or
account-level quotas. These are explicit gates/deferred work, not fields filled by assumed biology.

## Documentation handoff

Changed documents (25 total):

- Current truth and contracts: README.md, AGENTS.md, IMPLEMENTATION_STATUS.md, ARCHITECTURE.md,
  DOMAIN_MODELS.md, PYTHON_CORE_REVIEW.md (new), RESEARCH_LOOP.md, SCIENTIFIC_INVARIANTS.md.
- GDC evidence and source authority: GDC_STRATEGY.md, GDC_DISCOVERY_CAPTURES.md (new), SOURCE_REVIEW.md.
- Jev/evaluation/resources: JEV_DESIGN.md, JEV_QUESTIONS.md, TESTING.md, GDC_BUDGETS.md.
- Boundary reconciliation: PERSISTENCE.md, API_CONTRACT.md, RUN_EVENTS.md, UI_SPEC.md,
  DEPLOYMENT_PORTABILITY.md. UI/deployment edits correct factual backend descriptions only.
- Historical supersession notices: PHASE_3_PLAN.md, PHASE_4_READINESS_PLAN.md,
  GDC_JEV_FIT_ANALYSIS.md, CODEBASE_AUDIT_2026-09-23.md.
- This DISCOVERY_ROADMAP.md (new).

The three new documents are untracked files in the working tree until the user stages them; no commit
or push was made. No production, test, dependency or frontend changes are included. Temporary capture
bytes and the isolated harness remain outside repository run data. Preserve that local evidence before
temporary-directory cleanup; committed fixtures are a later explicitly scoped implementation gate.
