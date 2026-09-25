# Scientific invariants and method registry

These are scientific requirements of the current typed architecture. Known enforcement gaps are
listed explicitly and labeled. [Domain models](DOMAIN_MODELS.md) owns record contracts;
[testing](TESTING.md) owns verification.

## Claim and ownership boundary

Deterministic code owns populations, units, source values, arithmetic, missingness, eligibility,
tested universes, budgets and state transitions. Classical statistics may estimate effects and
uncertainty only under an admitted method. Jev provides bounded semantic judgments, not measured
values, significance, causality or action authorization. Generated hypotheses are never
evidence and never write a measured field.

Python owns loops, routing, side effects, action eligibility, stopping and abstention. A Jev
judgment never selects, authorizes or executes an action; deep policy records exactly one typed
move (`COMPLETE` / `FOLLOW_UP` / `GENERATE_HYPOTHESES` / `ABSTAIN`) and a separate Python step
requires explicit operator authorization to dispatch it. Jev cannot establish assay
comparability, repair missing sample IDs, select a denominator, turn absence into zero,
authorize acquisition or confer causality.

OntoJev supports candidate-target investigation, not therapeutic validation. Public GDC evidence
alone does not establish dependency, druggability, efficacy, safety, clinical benefit or
biomarker qualification. Integrity checks and a completed dossier do not establish a biological
mechanism. No scientific readiness or incremental Jev value is claimed.

## Missing-is-not-negative and sufficiency

Missing, unavailable, not acquired, not observed, partial, incompatible, invalid and observed
zero must remain distinct. No mutation occurrence is not a callable wild-type label; no CNV row
is not diploid; no expression column is not zero. Provider indexed availability, completed
acquisition and scientific sufficiency are separate concepts. Partial retrieval belongs to
`Quality` and is never hidden. HTTP 200 is not scientific admission.

## Current deterministic methods (IMPLEMENTED)

All are descriptive; none computes inferential p/q values or establishes biological direction.

| Method | Contract and limitation |
|---|---|
| `MUTATION_AFFECTED_CASE_COUNT_V1` | Gene/project provider unique-case aggregation, unit cases. A missing bucket is `NOT_OBSERVED`, not zero. Provider deduplication is not locally rederived from occurrences in the current runtime. |
| `PROJECT_SSM_COVERAGE_V1` | Retains project total and `case_with_ssm` separately; never treats the latter as a callable-negative denominator. Present zero is observed zero; absent project is `NOT_OBSERVED`. |
| `EXPRESSION_LOG2_SUMMARY_V1` | Returned case-labelled UQFPKM, `log2(x+1)`, median/min/max for at least one finite value, sample SD for at least two; otherwise explicit insufficiency. Missing columns are counted and not imputed. |
| `EXPRESSION_PROVIDER_SUMMARY_V1` | Retains provider median/SD as separate corroborating context; estimator convention is UNVERIFIED. Multi-batch summaries are not combined into cohort statistics. |
| `PROJECT_DOMINANCE_V1` | `max(affected)/sum(affected)` with at least two observed projects and a positive total; otherwise `NOT_APPLICABLE`. Not evidence for cross-project comparability, and not applicable to the single-cohort production scope. |

The source registry is `cancerjev/science/methods.py`. `MUTATION_DISCOVERY_V1` labels the
provider-ranked selection metadata only; it is never a measured value. Minimum computational n
does not imply scientific adequacy. No recurrence fraction or survival/association estimator is
registered.
The current endpoints/captures do not establish a matched denominator; admission requires
evidence, not impossibility claims about uninvestigated sources.

## Population, measurement and inference requirements

- Identify entity level (case/sample/aliquot), requested and returned populations, exclusions,
  duplicate policy, workflow and units before computing a value. Compatible project labels alone
  do not prove matched specimens.
- Reject nonfinite values; preserve exclusions. Empty, constant or undersized inputs are
  untestable, not fabricated p=1 findings. Required denominators must refer to the actual
  assay-eligible frame.
- Do not combine incompatible workflows or pool LUAD/LUSC. A case-level expression matrix does
  not establish a tumor-aliquot join to SSM/CNV observations.
- A proposed method must declare inputs, population, tested universe, method/version/parameters,
  eligibility, estimator, unit, effect definition, uncertainty method, minimum n, assumptions,
  missingness, failure outcomes and limitations.
- Inferential tests also declare the null hypothesis and multiplicity family before inspecting
  results. BH adjustment, if selected, applies to the recorded testable family, not only
  promoted hits. Adaptive discovery is not confirmatory validation.
- Survival requires a defined time origin, diagnosis/follow-up selection, censoring and group
  assignment. The live survival response proves endpoint availability, not an admitted
  estimator.
- Names such as “expression extreme”, “amplification”, “recurrence”, “coherence” and “conflict”
  require the definitions and eligibility gates in the [roadmap](DISCOVERY_ROADMAP.md). Missing
  references make the proposed feature/action ineligible.

## Evidence, identity and judgments

Revisions are immutable E0/E1/E2 with explicit parents. The registered actions
`CHECK_EVIDENCE_INTEGRITY_V1` and `CHECK_REVISION_FAITHFULNESS_V1` acquire no data, call no model
and measure no new biological quantity. Check outcomes VERIFIED/CONTRADICTED/NOT_OBSERVED
describe integrity, not biological effect. A failed action produces no new revision and
promotes nothing; an attempted action consumes follow-up budget.

Deep policy records one typed move; a separate Python dispatcher requires authorization,
eligibility and remaining budget. `FOLLOWUP_LIMIT = 3` and `EVIDENCE_ITERATION_LIMIT = 2` bound
one candidate arc. `COMPLETE` concerns bounded work, not scientific truth. Current provisional
thresholds and question semantics stay unchanged; new discovery judgments require separate
versions and prospective calibration.

Scientific identity excludes run/database/event/request-attempt identifiers and timestamps. It
includes semantic scope, source content/request identity, population, method/version/parameters,
units, results and meaningful missingness. Operational provenance remains linked outside that
hash. Pinned Jev identity gates cache reuse; operational latency/usage does not alter scientific
meaning. Provider rank and provider `_score` never define a measured value.

Generated text is stored separately with generator provenance and bounded review. A provider
model name is not necessarily immutable: the OpenRouter adapter currently lacks a resolved
identity pin check (PLANNED). Factual dossier tables must come from validated observation
references. Numeric-string screening cannot prove arbitrary generated prose scientifically
faithful.

## Known enforcement gaps, not assurances

- IMPLEMENTED: measurement construction rejects observed-null, boolean/non-numeric and
  negative/fractional count values; unavailable variants cannot carry a value; unknown or older
  schema versions are rejected fail-closed.
- IMPLEMENTED: storage/cache boundaries are validated, corrupt authoritative revisions refuse
  dossier publication, and invalid cached answers cause an abstention without a replacement
  provider call.
- IMPLEMENTED: no generated-text field exists in a measurement; hypothesis drafts reject unknown
  fields and apply text/list bounds; generated hypotheses never write a measured field.
- UNVERIFIED: structural validation does not prove source authenticity or the scientific truth
  of a supplied number. Codecs check consistency, not method re-execution or source authenticity.
- UNVERIFIED / provisional: `wide-policy-v2` and `deep-policy-v2` thresholds are uncalibrated;
  no incremental-value result exists. Changed rankings or successful provider calls are not
  value evidence.
- PLANNED: a total paid-model spend gate and whole-request GDC deadlines are not implemented.
  TypeSafe SDK retries are disabled, so application counters correspond to at most one HTTP
  attempt per logical evaluation.
- UNVERIFIED: case-to-sample resolution for expression values and GDC release atomicity across
  requests; reproducibility means replay from retained responses and hashes.
- Calibration, held-out evaluation and error reporting follow [testing](TESTING.md).