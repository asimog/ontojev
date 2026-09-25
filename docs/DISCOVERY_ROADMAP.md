# Discovery implementation roadmap and deliverable index

Current roadmap after the Stage 6 survivor-only CNV implementation (2026-09-25). Stages 0–6 are
IMPLEMENTED and offline verified. **Descriptive held-data actions and cutover are the next Stage 7
task.** Stages 7–9 are PLANNED; proposed action and inferential contracts below are design,
**not current runtime behavior**.
[Implementation status](IMPLEMENTATION_STATUS.md) owns current facts;
[architecture](ARCHITECTURE.md) owns the current runtime chain.

## Ordered stages

| Stage | Concrete work | Status and acceptance |
|---|---|---|
| 0: implementation baseline | Clean HEAD/environment; offline baseline; historical identity/projection/question/event goldens; retained captures | IMPLEMENTED: baseline understood, capture integrity verified, no new live claims |
| 1: scientific contracts | Frozen measurement/population/quality/state/evidence/check variants; direct version codecs | IMPLEMENTED: observed-null impossible; malformed/unknown schemas fail typed; historical artifacts unchanged |
| 2: integrity of consumption | Hash+schema validation of dossier inputs, cache answers, candidate evidence; typed hypothesis drafts | IMPLEMENTED: corrupt/missing revisions never `OBSERVED`; invalid cache never drives policy; unknown test IDs rejected |
| 3: typed lane composition | Typed acquisition/lane records, canonical `StatisticalState`/`EvidenceState`, consumer handoffs | IMPLEMENTED and offline-verified; offline suite passes; bounded live acceptance PASSED (2026-09-25) |
| 4: bounded broad universe | Explicit release/filter/ordered 1,000-gene prefix over `/genes`, ≤100-gene indexed count batches, deterministic ≤10-survivor reduction | IMPLEMENTED (2026-09-25): strict page guards (duplicate/offset/total/order/biotype/slice), explicit zero vs absent vs partial, one disposition per requested gene, reducer `MUTATION_LUAD_AFFECTED_COUNT_DESC_V1`, persisted schema-1 result; live acceptance 1,000/1,000 with 10 survivors |
| 5: independent expression arm | Optional explicitly budgeted case-labelled descriptors and within-gene extremes | **IMPLEMENTED (offline verified)**: separate `discover-expression --live`; same release-bound 1,000-gene universe; ≤100-gene × ≤250-case strict batches; complete declared population/missingness; local summaries and Tukey tails only; no tumor-normal, causal or sample-matching claim; live acceptance UNVERIFIED |
| 6: narrow CNV lane | Fixed builders and strict occurrence parser; complete survivor queries only | **IMPLEMENTED (offline verified)**: Stage 4 artifact/release/frame binding; ≤10 survivors × ≤10 strict 250-row pages; real-shape fixture for generic Loss, missing sample ID and caller context; unique positive cases per category with explicit conflicts; no neutral/negative inference; full live acceptance UNVERIFIED |
| 7: descriptive actions and cutover | Reuse the investigation loop; expression-tail/CNV-category actions; typed versioned projections; no new semantic questions | PLANNED: held-data methods and authorization enforced; explicit model attempt/token budget; unchanged judgments/policies |
| 8: prospective evaluation | Blinded grouped labels, fixed development/holdout, ablations and resource comparison | PLANNED: blocked on a labelled historical corpus and human review; no ranking-only value claim |
| 9: conditional inferential extensions | Matched mutation-expression/CNV-expression, survival, later scRNA | DEFERRED: separate source/matching/reference/censoring/statistical review; not unlocked by finishing earlier engineering stages |

Stages 4–6 are IMPLEMENTED as separate bounded pre-Wide tasks in the existing architecture. Stage 7 remains
FIX AS PART OF NEW ARCHITECTURE work. A total paid-model spend gate remains a
prerequisite for scaling paid model work, not for offline contract implementation. Retain the
small deterministic baseline throughout.

## IMPLEMENTED: mutation funnel (Stage 4), expression arm (Stage 5) and survivor CNV arm (Stage 6)

Universe: release-bound first 1,000 protein-coding Ensembl IDs by ascending ID at offset 0 —
IMPLEMENTED in `research/discovery.py` with a fixed, non-configurable builder. The prefix is
reproducible but biased and incomplete for the genome. No known-target roster or provider
top-mutated rank enters this selector; the provider ranking is a labelled comparator. Preserve
the provider-ranked
current baseline separately. This is a reproducible subset of the 19,843 indexed protein-coding
genes observed in the campaign, not genome-wide coverage or an unbiased random sample.

Initial reduction: rank complete observed LUAD affected-case counts descending, tie by gene ID;
retain ≤10 survivors with reasons. Missing/incomplete counts are not eligible zeroes. This is a
mutation-conditioned funnel, not comprehensive multi-lane discovery. The separately scheduled
Stage 5 expression arm now describes every gene in the same release-bound universe independently;
it does not change mutation survivors or combine lanes. Stage 6 queries complete bounded CNV
occurrences only for the Stage 4 survivors and does not combine lanes. Broad CNV occurrence
acquisition is rejected: even 100 genes reported 21,032 rows.

| Feature | Exact meaning / population / reference | Availability and claim boundary |
|---|---|---|
| Mutation indexed recurrence count | Unique affected-case count supplied for gene/LUAD by validated aggregate | Count, NOT callable recurrence fraction; explicit zero preserved, missing bucket `NOT_OBSERVED` |
| Expression location/dispersion | Median/sample SD/min/max of finite `log2(UQFPKM+1)` for one gene over the declared returned case-labelled frame | Descriptive cohort slice; missing rows/columns explicit; SD n≥2 |
| Expression extreme | Within-gene empirical tail: values below Q1−1.5×IQR or above Q3+1.5×IQR; Q1/Q3 via declared linear interpolation `h=(n−1)p`; count/list IDs | IMPLEMENTED experimental descriptor, n≥20 complete declared valid frame; IQR=0 → `DEGENERATE_REFERENCE`, no tail ranking; not differential expression, patient diagnosis or p-value |
| CNV gain/loss/amplification/deletion | Provider label on a complete bounded gene/case occurrence query; unique cases per explicit category and caller context | Amplification means provider category only; generic Loss distinct from Homozygous Deletion; absent ≠ neutral; do not sum overlapping case categories |
| Cross-lane presence overlap | Set intersection of positive indexed case IDs for the same gene, only if both complete query frames exist | Descriptive presence, not matched assay effect/coherence; insufficient for expression sample matching |
| Quality conflict | Explicit contradictory duplicate IDs/calls or failed invariants | Deterministic data conflict, not biological contradiction |
| Biological coherence/conflict | Requires a predefined matched association/effect proposition and compatible reference | NOT ADMITTED |

The n≥20 tail descriptor guard is an implemented stability policy, not proof of power or normality.
Feature version, quantile convention, selected/valid/missing IDs and reference frame enter
identity. No imputation, reference pooling, normal controls or causal interpretation is assumed.
Discovery metrics are selected on the same data and cannot be repackaged as confirmatory
p-values.

## Registered actions and proposed contract change

Current registered actions are integrity checks only:
`CHECK_EVIDENCE_INTEGRITY_V1` (input `STATISTICAL_STATE`) and
`CHECK_REVISION_FAITHFULNESS_V1` (input `EVIDENCE_STATE`). Adding a measurement-producing action
requires an explicit versioned rule change in the action registry and scientific contracts, not
quietly treating a descriptor as an integrity check. Acquisition-capable actions additionally
require a declared fixed request plan and reservation before sending; no generative/model output
may supply an endpoint or query.

| Proposed action | Input / question / method / output | Eligibility, reservation and decision |
|---|---|---|
| Existing integrity and revision-faithfulness checks | Current typed-input contract; unchanged check semantics | KEEP; no acquisition/model/new biology |
| `SUMMARIZE_EXPRESSION_TAIL_V1` | Held typed case-labelled values; does the declared distribution contain empirical tail observations? Exact quantile/tail rule above; case counts/IDs and coverage | Proposed descriptive measurement action only after an explicit action-contract change; n≥20, IQR>0, declared complete input frame; zero GDC reservation; no p/q |
| `SUMMARIZE_CNV_CATEGORIES_V1` | Held complete typed occurrences; count distinct cases for each provider category, retain conflicts and caller/source refs | Proposed descriptive measurement action after contract change; complete filter-bound query, dedup invariant; no neutral denominator; zero new acquisition |
| `ACQUIRE_SURVIVOR_CNV_V1` | Fixed bounded gene/project query → typed evidence outcome | REJECT as a Stage 7 action: Stage 6 already performs separately invoked, fixed-plan acquisition; the action registry must not hide or repeat that side effect |
| `STRATIFY_BY_PROJECT_V1`, `LEAVE_ONE_PROJECT_OUT_V1` | Project stratification / leave-one-project-out | NOT APPLICABLE to the single TCGA-LUAD cohort; not registered |
| `CHECK_MISSINGNESS_V1` | Recompute case-level missingness from retained responses and reconcile against the recorded state | PLANNED contract review only; partly redundant with `EXPRESSION_COVERAGE_ARITHMETIC`; needs a demonstrated non-redundant operation from held evidence |
| `OUTLIER_SENSITIVITY_V1`, `COMPARE_MODALITIES_V1` | Sensitivity/modality comparison proposals | Unapproved placeholders; not registered |
| `MUTATION_EXPRESSION_ASSOCIATION`, `CNV_EXPRESSION_ASSOCIATION` | Matched mutation-status/category groups versus expression | INELIGIBLE now; design conditions below |
| `SURVIVAL_ASSOCIATION` | Time/event and exposure groups | LATER; censoring/clinical selection and confounding contract absent |
| Generic missingness action duplicating integrity arithmetic | Same existing evidence check | REJECT unless a distinct falsifiable operation is demonstrated |

### Deferred association contracts (not executable admission)

No association action is ADMIT NOW, because exact matching/reference conditions are unresolved.

| Required element | Mutation-expression | CNV-expression |
|---|---|---|
| Match/unit | Same selected tumor sample, case and gene with explicit aliquot mapping; one independent case observation | Same requirement plus declared CNV caller/category source |
| Population/reference | Gene-callable mutation-positive versus validated callable-negative cases | Explicit gain/amplification versus validated neutral category, not absence |
| Eligibility | Complete input population, no unresolved duplicates, assay-compatible workflows, known exclusions | Additionally no conflicting category/caller interpretation |
| Estimator/test proposal | Descriptive median `log2`-expression difference; two-sided permutation difference test only after scientific approval | Same contrast for a predeclared category comparison; no numeric CNV correlation until scale is comparable |
| Effect/uncertainty | Median difference in `log2(UQFPKM+1)`; bootstrap CI grouped by independent case, fixed recorded seed/replicates | Same unit; preserve category/reference definitions |
| Minimum sample requirement | Proposal n≥20 per eligible group plus separate power/precision review; threshold alone is not validation | Same; a rare category may remain ineligible |
| Missingness | Exclude and enumerate missing measurements/mapping/callability; no imputation as negative | Exclude missing/ambiguous category or expression; never infer neutral |
| Multiple testing | Pre-register all gene/action contrasts in the family; BH only where assumptions are accepted; report selection bias; independent validation required for confirmation | Same, including all tested categories, not survivors-only post hoc family |
| Provenance/output | Frame hashes, exact source records, method/seed/parameters, exclusions, effect/CI/p/q or explicit ineligible outcome | Same plus caller/category and matched sample refs |
| Acquisition reservation | Initially held-data only, zero requests; future acquisition requires a separate fixed budgeted contract | Same |

These statistical procedures are design candidates awaiting review, not a supported biological
analysis or a dependency-installation request. Unknown matching cannot be “resolved” by Jev. No
wet-lab experiment, drug prediction or clinical recommendation is admitted by this architecture.

## Unresolved limitations

No callable mutation-negative or CNV-neutral denominator; no expression sample/aliquot
resolution; incomplete genome universe and mutation-first selection bias; generic CNV Loss
categories; numerical CNV caller compatibility not established; survival censoring/exclusions
not audited; no LUAD scRNA source in sampled metadata; no prospective Jev labels or value
result; no measured model invoice or account-level quota; no total paid-model spend gate. These
are explicit gates/deferred work, not fields filled by assumed biology.

## Later hardening

LATER: strict cursor scalar/size validation; operational clock injection only if needed;
backup/retention; OpenRouter resolved immutable model identity; whole-request GDC deadlines;
per-event payload shape validation.
Do not build repository hierarchies, universal lane registries, DI frameworks, workflow/agent
engines, microservices, broad data mirrors or arbitrary provider-query tools. Ignore stylistic
dictionary counts, dynamic ID maps, boundary JSON, readable helpers, operational UUIDs and the
historical package namespace.

## Deliverable index

| # | Deliverable | Authoritative location |
|---|---|---|
| 1 | Starting HEAD, scope and verification status | IMPLEMENTATION_STATUS |
| 2 | Current implemented workflow truth | ARCHITECTURE |
| 3 | Type-evidence flow and boundary classification | DOMAIN_MODELS |
| 4 | Official GDC authority and mappings | SOURCE_REVIEW / GDC_STRATEGY |
| 5 | Anonymous request/capture/provenance register | GDC_DISCOVERY_CAPTURES |
| 6 | GDC reality matrix and admission decisions | GDC_STRATEGY |
| 7 | Measured versus estimated workloads | GDC_STRATEGY / GDC_BUDGETS |
| 8 | Universe source, completeness and bias | ARCHITECTURE / this document |
| 9 | Case/sample/aliquot and duplicate handling | GDC_STRATEGY / DOMAIN_MODELS |
| 10 | Denominators, missingness and sufficiency | SCIENTIFIC_INVARIANTS |
| 11 | Operation ownership | ARCHITECTURE |
| 12 | ResearchSpec composition | DOMAIN_MODELS |
| 13 | Entity/population/universe/method/provenance records | DOMAIN_MODELS |
| 14 | Measurement variants and invariants | DOMAIN_MODELS |
| 15 | Mutation/expression/CNV lane contracts | DOMAIN_MODELS / GDC_STRATEGY |
| 16 | Typed StatisticalState and immutable EvidenceState | DOMAIN_MODELS |
| 17 | Action/check/outcome/candidate/hypothesis contracts | DOMAIN_MODELS |
| 18 | Typed Jev answers and separate semantic features | DOMAIN_MODELS / JEV_DESIGN |
| 19 | Serialization, version handling and history policy | PERSISTENCE |
| 20 | Scientific versus operational identity | DOMAIN_MODELS / SCIENTIFIC_INVARIANTS |
| 21 | Systematic funnel and deterministic feature definitions | This document |
| 22 | Registered actions and deferred association contracts | This document |
| 23 | TypeSafe skill and documentation review | JEV_DESIGN / SOURCE_REVIEW |
| 24 | Cookbook/pattern adoption and failure matrix | JEV_DESIGN |
| 25 | Current and proposed versioned questions | JEV_QUESTIONS |
| 26 | Blinded calibration, splits, labels and ablations | TESTING |
| 27 | Incremental value, uncertainty and human-review gates | TESTING / IMPLEMENTATION_STATUS |
| 28 | GDC/Jev/LLM costs, latency and budgets | GDC_BUDGETS |
| 29 | Reconciled documentation authority and transferred findings | SOURCE_REVIEW |
| 30 | Ordered roadmap, blockers, deferred/rejected work | This document |

No new lane, endpoint, action or semantic question set is authorized by this roadmap. Each stage
requires its own separately authorized task and acceptance gate; passing these engineering gates
does not establish scientific Jev value.
