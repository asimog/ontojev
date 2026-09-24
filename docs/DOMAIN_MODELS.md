# Scientific contracts and identity

Baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`, reviewed 2026-09-24.
PLANNED records below are designs, not existing Python classes.
The [source-field trace](GDC_STRATEGY.md) limits admitted scientific content.

## Current contract assessment

| Concept | Classification | Protected invariant in transition |
|---|---|---|
| ResearchSpec, CohortSpec, AcquisitionSpec | STRONGLY TYPED | Validated bounded scope |
| GDC provider records | ADEQUATELY TYPED | Identifier membership and provider types |
| ProjectFrame | ADEQUATELY TYPED, specialized | Common frame separate from lane data |
| StatisticalState, mutation/expression/population/quality | DICTIONARY-CONVENTION DOMAIN OBJECT | Value/status/unit and population identity |
| Candidate, EvidenceState, observation/check | DICTIONARY-CONVENTION DOMAIN OBJECT | Accepted source and immutable revisions |
| ActionDefinition | STRONGLY TYPED | Method/question/unit/limitations/input kind |
| ActionEligibility/ActionOutcome | PARTIALLY TYPED | Typed prereqs and successful results only |
| QuestionDefinition/provider envelope | ADEQUATELY / PARTIALLY TYPED | Exact roster and answer variant |
| Validated Jev evaluation | DICTIONARY-CONVENTION DOMAIN OBJECT | Preserve validation through policy/cache |
| Hypothesis | PARTIALLY TYPED then widened | Generated text cannot become measurements |
| Dossier, API JSON, generic event envelope | SHOULD REMAIN A BOUNDARY DICTIONARY | Validated inputs, truthful section availability |

## PLANNED: common frozen records

Use frozen dataclasses, enums and explicit unions. Tuples/frozensets or immutable snapshots protect
nested values: frozen=True around mutable lists is insufficient. Dynamic identifier maps remain
appropriate when their values are typed. No general inheritance or serialization framework.

| Record | Fields and invariant |
|---|---|
| EntityRef | GENE kind, Ensembl ID, display symbol, release; symbol is not a join key |
| PopulationFrame | cohort/project, CASE or SAMPLE unit, known eligible IDs or UNKNOWN eligibility, examined IDs, membership hash, selection rule; subset membership checked |
| TestedUniverse | ordered IDs, hash, source/release/filter/order/offset, reported total, completeness for declared slice; inferential family separately identified |
| MethodRef | ID/version, parameters, units, duplicate rule, transform, estimator, missingness, limitations |
| ScientificSource | endpoint, canonical request hash, response hash, parser version, release, acquisition outcome |
| OperationalSource | request/attempt/cache/artifact IDs, retrieval time, latency/status/bytes; separate from scientific identity |
| Quality | acquisition COMPLETE/PARTIAL/FAILED/NOT_ACQUIRED; sufficiency SUFFICIENT/PARTIAL/INSUFFICIENT/NOT_ASSESSED; compatibility VERIFIED/INCOMPATIBLE/UNVERIFIED/NOT_APPLICABLE; reasons |
| Coverage | examined, assay-available (possibly unknown), returned, valid, missing, unit and frame; checked arithmetic and disjoint missing categories |

HTTP success, complete query and scientific sufficiency differ. A complete declared gene slice is
still incomplete for the genome.

### Measurement variants

```text
ObservedCount(non-bool integer >= 0, unit CASES|OBSERVATIONS, population, method, sources)
ObservedScalar(finite float, declared unit, population, method, sources)
UnavailableMeasurement(status NOT_ACQUIRED|UNAVAILABLE|NOT_OBSERVED|INCOMPATIBLE|
                       INVALID|INSUFFICIENT, nonempty reason, expected_unit, population)
Measurement = ObservedCount | ObservedScalar | UnavailableMeasurement
```

Observed variants cannot contain null or an unavailable reason. Unavailable variants cannot carry
a value. Zero needs an explicit provider result or eligible complete local computation. Partial
retrieval belongs to Quality; a subset estimate names the subset. Sample SD needs n>=2; zero MAD
is a real dispersion but cannot divide a standardized score.

## PLANNED: ResearchSpec composition

```text
ResearchSpecV2(
  spec_id, intent, cohort,
  universe=IndexedGeneSlice(PROTEIN_CODING, GENE_ID_ASC, offset, limit<=1000),
  lanes: tuple[MutationCountSpec | ExpressionSummarySpec | CnvOccurrenceSpec, ...],
  reduction_policy_version, admission_policy_version, allowed_action_ids,
  limits=ScientificLimits(max_cohort_cases, survivor_count, max_lane_observations),
  output_contract_version)
```

Initially retain TCGA-LUAD, max_cohort_cases=1000, survivors<=10, promotions<=3 and E0/E1/E2.
Freeze effective specification before acquisition. Selection/tested-family changes affect scientific
context; timeouts, paths and cache do not. A lane selects a declared method/population/bounded scope,
never an arbitrary endpoint or executable expression. Operational settings remain separate.

## PLANNED: lanes and states

| Contract | Admitted content | Prohibited inference |
|---|---|---|
| MutationCountResult | LUAD affected-case count, separate SSM coverage, universe and completeness | Absent bucket=wild type; project total=callable denominator |
| ExpressionSummaryResult | case-labelled UQFPKM values or typed matrix ref; local log2(x+1) median/sample SD/min/max, valid/missing IDs; provider summary separate | Tumor-normal differential expression or sample matching from case labels |
| CnvOccurrenceResult | bounded complete queried occurrences, case/gene IDs, provider categories, source file/caller/copy number when present, mapping status and unique-case descriptors | Neutral from absence, clinical amplification or pooling incompatible numeric calls |
| StatisticalStateV3 | entity, frame, universe, enabled typed lane results, deterministic features, methods/sources, Quality | lanes: dict[str, Any]; semantic probabilities in measured fields |
| EvidenceStateV3 | accepted typed state ref, parent scientific hash, revision index, action/version, typed checks/results/quality/sources | Mutating E0 or operational IDs in scientific identity |

Disabled/unacquired lanes have explicit outcomes, not empty successful results. A provider
cnv_change_5_category=Loss becomes LOSS_UNSPECIFIED, not heterozygous deletion. Unknown categories
are UNSUPPORTED_CATEGORY, never neutral. Conflicting case calls remain conflicts. Numeric copy
number remains provider context until caller/sample comparability is accepted.

### Actions, checks, candidates, hypotheses and Jev

EvidenceCheck carries check ID, method, VERIFIED/CONTRADICTED/NOT_OBSERVED outcome, claim, input refs,
reason and n_effective. CheckSummary is constructed from checks; nonnegative counts sum to total.
Missing checks_contradicted cannot mean zero.

ActionInput is a StatisticalState or EvidenceState variant. ActionOutcome is Completed(typed results,
sources) or Ineligible/Unavailable/Failed(reason). Failure creates no successful revision.
Candidate binds run-local identity, accepted scientific hash, policy/operator authority, slot and lifecycle.

HypothesisDraft bounds statement/mechanism, each list string, list counts and eligible registered
test IDs. Unknown test IDs are rejected rather than dropped. HypothesisRecord adds generator/model
metadata, evidence hash and NOT_EVIDENCE label. Neither can be a Measurement.

JevAnswer is NoulAnswer(probability_yes), ChoiceAnswer(choice, distribution, confidence), or
ScoreAnswer(expected_level, distribution, confidence, rubric). Validate finite ranges, exact roster,
sum and rubric consistency. JevEvaluation binds input/projection/question/model/adapter identities,
applicability and success/failure/cache outcomes. SemanticFeatureRecord references evaluations
separately from StatisticalState. A semantic score is not an effect size or cancer probability.

Dossiers remain JSON with the existing DOSSIER_SECTIONS roster. Typed DossierInputs protects valid
readable revisions and evaluations; presentation subsections need not become classes. No current
live rule requires two hypotheses. Corrupt input requires unavailable sections or publication refusal.

## Versioned boundary parsing and identity

PLANNED readers explicitly dispatch fixture schema 1, live schema 2 and typed schema 3.
Unsupported versions return UNSUPPORTED_SCHEMA_VERSION, not a fixture fallback. Retain historical
bytes/hashes/question sets/schema-4 databases. A validated v2 legacy view preserves v2 semantics;
conversion to v3, if needed, writes a new derived artifact with conversion version and old hash.

Load path: verify artifact path/size/hash -> JSON -> direct version parser -> identity check -> typed use.
SQLite JSON remains boundary data until validation. Cache hydration validates roster/primitive/model/
projection binding once on entry. Do not repeatedly parse trusted typed values between functions.
Serialize canonical JSON only at artifact/database/API/provider boundaries.

New scientific identity includes values/units, population membership, tested universe, method
parameters/versions, missingness, release/source hashes and parent evidence hash. Exclude run/database/
event/attempt IDs, artifact location, timestamps, provider rank and UI state. Keep existing v1/v2
identity functions for history; do not retroactively change hashes. Jev inference identity includes
projection/question/model/adapter versions, with policy thresholds separate for replayable experiments.
