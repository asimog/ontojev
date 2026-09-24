# Scientific invariants and method registry

These are scientific requirements; known enforcement gaps are explicitly listed below. Current
implementation evidence is at `42b05d40e6edafec0b8613e7dd154a60a46e4fee`.
[Domain contracts](DOMAIN_MODELS.md) distinguish current records from proposed typed versions.

## Claim and ownership boundary

Deterministic code owns populations, units, source values, arithmetic, missingness, eligibility,
tested universes, budgets and state transitions. Classical statistics may estimate effects and
uncertainty only under an admitted method. Jev provides bounded semantic judgments, not measured
values, significance, causality or action authorization. Generated hypotheses are never evidence.

OntoJev supports candidate-target investigation, not therapeutic validation. Public GDC evidence
alone does not establish dependency, druggability, efficacy, safety, clinical benefit or biomarker
qualification. Integrity checks and a completed dossier do not establish a biological mechanism.

Missing, unavailable, not acquired, not observed, partial, incompatible, invalid and observed zero
must remain distinct. No mutation occurrence is not a callable wild-type label; no CNV row is not
diploid; no expression column is not zero. Provider indexed availability, completed acquisition
and scientific sufficiency are separate concepts.

## Current deterministic methods (IMPLEMENTED)

All are descriptive; none computes inferential p/q values or establishes biological direction.

| Method | Contract and limitation |
|---|---|
| `MUTATION_AFFECTED_CASE_COUNT_V1` | Gene/project provider unique-case aggregation, unit cases. A missing bucket is NOT_OBSERVED, not zero. Provider deduplication is not locally rederived from occurrences in current runtime. |
| `PROJECT_SSM_COVERAGE_V1` | Retains project total and `case_with_ssm` separately; never treats the latter as a callable negative denominator. Present zero is observed zero; absent project is NOT_OBSERVED. |
| `EXPRESSION_LOG2_SUMMARY_V1` | Returned case-labelled UQFPKM, `log2(x+1)`, median/min/max for at least one finite value, sample SD for at least two; otherwise explicit insufficiency. Missing columns are counted and not imputed. |
| `EXPRESSION_PROVIDER_SUMMARY_V1` | Retains provider median/SD as separate corroborating context; estimator convention is unverified. Multi-batch summaries are not combined into cohort statistics. |
| `PROJECT_DOMINANCE_V1` | `max(affected)/sum(affected)` with at least two observed projects and positive total; otherwise NOT_APPLICABLE. Not evidence for cross-project comparability, and irrelevant to the single-cohort production scope. |

The source registry is `cancerjev/science/methods.py`. Minimum computational n does not imply
scientific adequacy. No recurrence fraction or survival/association estimator is registered.
The previous blanket claim that open data can never supply a matched denominator is too strong:
the current endpoints/captures do not establish one. Admission requires evidence, not impossibility
claims about uninvestigated sources.

## Population, measurement and inference requirements

- Identify entity level (case/sample/aliquot), requested and returned populations, exclusions,
  duplicate policy, workflow and units before computing a value. Compatible project labels alone
  do not prove matched specimens.
- Reject nonfinite values; preserve exclusions. Empty, constant or undersized inputs are untestable,
  not fabricated p=1 findings. Required denominators must refer to the actual assay-eligible frame.
- Do not combine incompatible workflows or pool LUAD/LUSC. A case-level expression matrix does not
  establish a tumor-aliquot join to SSM/CNV observations.
- A proposed method must declare inputs, population, tested universe, method/version/parameters,
  eligibility, estimator, unit, effect definition, uncertainty method, minimum n, assumptions,
  missingness, failure outcomes and limitations.
- Inferential tests also declare null hypothesis and multiplicity family before inspecting results.
  BH adjustment, if selected, applies to the recorded testable family, not only promoted hits.
  Adaptive discovery is not confirmatory validation.
- Survival requires a defined time origin, diagnosis/follow-up selection, censoring and group
  assignment. The live survival response proves endpoint availability, not an admitted estimator.
- Names such as “expression extreme”, “amplification”, “recurrence”, “coherence” and “conflict” require
  the definitions and eligibility gates in the [roadmap](DISCOVERY_ROADMAP.md). Missing references
  make the proposed feature/action ineligible.

## Evidence, identity and judgments

Revisions are immutable E0/E1/E2 with explicit parents. Current registered actions
`CHECK_EVIDENCE_INTEGRITY_V1` and `CHECK_REVISION_FAITHFULNESS_V1` acquire no data, call no model
and measure no new biological quantity. Check outcomes VERIFIED/CONTRADICTED/NOT_OBSERVED describe
integrity, not biological effect.

Deep policy records COMPLETE/FOLLOW_UP/GENERATE_HYPOTHESES/ABSTAIN. A separate Python dispatcher
requires authorization, eligibility and remaining budget. COMPLETE concerns bounded work, not
scientific truth. Current provisional thresholds and question semantics stay unchanged;
new discovery judgments receive separate versions and prospective calibration.

Scientific identity excludes run/database/event/request-attempt identifiers and timestamps.
Include semantic scope, source content/request identity, population, method/version/parameters,
units, results and meaningful missingness. Operational provenance remains linked outside that hash.
Pinned Jev identity gates cache reuse; operational latency/usage does not alter scientific meaning.

Generated text is stored separately with generator provenance and bounded review. A provider model
name is not necessarily immutable: the OpenRouter adapter currently lacks the required pin check.
Factual dossier tables must come from validated observation references. Numeric-string screening
cannot prove arbitrary generated prose scientifically faithful.

## Known enforcement gaps, not assurances

The metric helper accepts OBSERVED with null value; state/evidence fields are dictionary
conventions rather than validated records. Cached answer hydration lacks domain validation;
unknown state versions can fall through historical identity handling. Dossier revision read
failure can become an empty payload under an OBSERVED section. These are documented precisely in
[the Python review](PYTHON_CORE_REVIEW.md); do not claim actual live measurement corruption where
only a constructor or malformed-artifact path was demonstrated.

The typed transition must enforce these requirements at construction and deserialization without
reparsing trusted records throughout deterministic science. Keep JSON at real boundaries.
Calibration, held-out evaluation and error reporting follow [testing](TESTING.md); changed rankings
or unrelated cookbook results are not incremental-value evidence.
