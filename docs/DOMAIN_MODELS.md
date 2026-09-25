# Domain models, records and scientific identity

Current typed architecture after the Stage 3 hard cutover (2026-09-25). All records below are
IMPLEMENTED. Python domain names are unsuffixed; operational ids and hashes travel in envelope
records and never enter scientific identity. [Architecture](ARCHITECTURE.md) owns the runtime
chain; [persistence](PERSISTENCE.md) owns storage.

## Domain records

| Record | Role and protected invariant |
|---|---|
| `ResearchSpec` (schema 3) | Sole canonical research configuration: `spec_id`, intent, `CohortSpec` (cohort/domain/project), bounded `AcquisitionSpec` limits, `ScientificLimits`, allowed registered action IDs, and the fixed `wide-policy-v2` / `deep-policy-v2` versions. Unsupported configurations are rejected or not representable |
| `StatisticalState` (schema 4) | Typed entity, annotation, research scope, universe, tested context, per-project lane results, quality and separate scientific/operational sources |
| `EvidenceState` (schema 4) | Accepted state hash, parent evidence hash, E0/E1/E2 index, `ActionRef`, immutable checks, derived `CheckSummary`, quality and sources |
| `Candidate` | Run-local promoted/selected candidate binding (projection row plus `CandidateEvidence` in `research/deep.py`): candidate id, entity, promotion slot, accepted state binding, lifecycle |
| `HypothesisDraft` | Bounded generated statement, mechanism, predictions, falsification criteria, distinguishing tests and assumptions; cannot be a measurement |
| `StateRecord` | Envelope: `state_id`, `state_hash`, typed `StatisticalState` |
| `EvidenceRecord` | Envelope: `evidence_state_id`, `evidence_hash`, typed `EvidenceState` revision |
| `HypothesisRecord` | Envelope: hypothesis id, candidate id, typed `HypothesisDraft` |

`cancerjev/domain/envelopes.py` is the only place operational ids/hashes are bound to typed
scientific objects: storage and runtime consumers never reconstruct one from the other.

## Common frozen records

`cancerjev/domain/measurements.py` contains the shared contracts. They authorize no acquisition.
Frozen dataclasses, enums and explicit unions are used; tuples/frozensets protect nested values.
There is no general inheritance or serialization framework.

| Record | Fields and invariant |
|---|---|
| `EntityRef` | GENE kind, Ensembl ID, display symbol, release; symbol is not a join key |
| `PopulationFrame` | cohort/project, CASE or SAMPLE unit, known eligible IDs or UNKNOWN eligibility, examined IDs, membership hash, selection rule; subset membership checked |
| `TestedUniverse` | ordered IDs, hash, source/release/filter/order/offset, reported total, completeness for the declared slice; inferential family separately identified |
| `MethodRef` / `MethodParameters` | ID/version, units, duplicate rule, transform, estimator, missingness, limitations; parameters are only optional `ddof=1` and `pseudocount=1`, not a metric bag |
| `ScientificSource` | endpoint, canonical request hash, response hash, parser version, release, acquisition outcome |
| `OperationalSource` | request/attempt/cache/artifact IDs, retrieval time, latency/status/bytes; separate from scientific identity |
| `Quality` | acquisition COMPLETE/PARTIAL/FAILED/NOT_ACQUIRED; sufficiency SUFFICIENT/PARTIAL/INSUFFICIENT/NOT_ASSESSED; compatibility VERIFIED/INCOMPATIBLE/UNVERIFIED/NOT_APPLICABLE; reasons |
| `Coverage` | examined, assay-available (possibly unknown), returned, valid, missing, unit and frame; checked arithmetic and disjoint missing categories |

HTTP success, complete query and scientific sufficiency differ. A complete declared gene slice
is still incomplete for the genome.

### Measurement variants

```text
ObservedCount(non-bool integer >= 0, unit CASES|OBSERVATIONS, population, method, sources)
ObservedScalar(finite float, declared unit, population, method, sources)
UnavailableMeasurement(status NOT_ACQUIRED|UNAVAILABLE|NOT_OBSERVED|INCOMPATIBLE|
                       INVALID|INSUFFICIENT, nonempty reason, expected_unit, population)
MetricRecord = ObservedCount | ObservedScalar | UnavailableMeasurement
```

Observed variants cannot contain null or an unavailable reason. Unavailable variants cannot
carry a value. Zero requires an explicit provider result or an eligible complete local
computation. Partial retrieval belongs to `Quality`; a subset estimate names the subset. Sample
SD needs n≥2; zero MAD is a real dispersion but cannot divide a standardized score. Current
scalar units are restricted to nonnegative UQFPKM and `log2(UQFPKM+1)`, not arbitrary signed
effects. A future inferential effect requires its own admitted unit/method contract.

## Lane and state records

| Contract | Admitted content | Prohibited inference |
|---|---|---|
| `MutationCountResult` | entity/frame-bound affected-case and separate SSM coverage measurements, `Quality` | Absent bucket = wild type; project total = callable denominator |
| `ExpressionSummaryResult` | entity-bound immutable case-labelled UQFPKM values; local `log2(x+1)` median/sample SD/min/max, `Coverage`/`Quality`/sources | Tumor-normal differential expression or specimen matching from case labels |
| `CnvOccurrenceResult` | entity/frame-bound raw occurrences with optional source file/caller/sample/copy-number context; `Quality`/sources | Neutral from absence, clinical amplification, or pooling incompatible numeric calls |
| `UnavailableLane` | explicit NOT_ACQUIRED/UNAVAILABLE/NOT_OBSERVED/INCOMPATIBLE outcome with a reason | Empty successful lane |
| `ProviderExpressionSummary` | provider median/stddev retained verbatim as corroborating context | Cohort statistics from pooled batch summaries |
| `StatisticalState` | entity, frame, universe, tested context, typed mutation/expression/CNV slots, `Quality`, scientific and separate operational sources | Semantic probabilities in measured fields |
| `EvidenceCheck` / `CheckSummary` | check id, method, VERIFIED/CONTRADICTED/NOT_OBSERVED outcome, claim, input refs, reason, n_effective; nonnegative counts sum to total | Missing `checks_contradicted` meaning zero |
| `EvidenceState` | accepted state hash, parent scientific hash, E0/E1/E2 index, `ActionRef`, immutable checks, derived summary, `Quality`/sources | Mutating E0 or operational IDs in scientific identity |

Disabled/unacquired lanes have explicit outcomes, not empty successful results. A provider
`cnv_change_5_category=Loss` is `LOSS_UNSPECIFIED`, not heterozygous deletion; unknown
categories are `UNSUPPORTED_CATEGORY`, never neutral; conflicting case calls remain conflicts.
No CNV provider parser, complete-query acquisition or category-count descriptor is admitted by
constructing the record. CNV acquisition and descriptors remain PLANNED (Stage 6).

## Actions, candidates and hypotheses

- Registered actions (`cancerjev/science/actions.py`, registry version 2):
  `CHECK_EVIDENCE_INTEGRITY_V1` (input `STATISTICAL_STATE`) and
  `CHECK_REVISION_FAITHFULNESS_V1` (input `EVIDENCE_STATE`). `ActionDefinition` declares
  question, falsifiable interpretation, method/version, unit, required evidence, limitations and
  input kind. `ActionEligibility` is a deterministic fail-closed prerequisite check;
  `ActionOutcome` carries typed checks. Failure creates no successful revision.
- `CandidateEvidence` binds a run-local candidate to the accepted typed state, its verified
  operand artifact and its promotion slot. Operator selection is recorded as
  `operator-selection-v1` and consumes a promotion slot.
- `HypothesisDraft` bounds statement, mechanism, each list string, list counts and eligible
  registered test IDs. Unknown fields and unknown test IDs are rejected, not filtered.
  `HypothesisRecord` adds generator/model metadata, the evidence hash and the NOT_EVIDENCE label.
  Neither can be a `Measurement`.
- Jev answers are `NoulAnswer(probability_yes)`, `ChoiceAnswer(choice, distribution,
  confidence)` or `ScoreAnswer(expected_level, distribution, confidence, rubric)`. Validation
  enforces finite ranges, exact roster, distribution sum and rubric consistency. A Jev evaluation
  binds input/projection/question/model/adapter identities, applicability, and
  success/failure/cache outcomes. A semantic score is not an effect size or cancer probability.
- Dossiers are JSON (schema 2) with the `DOSSIER_SECTIONS` roster. Corrupt or unverifiable
  authoritative input refuses publication (`DOSSIER_UNAVAILABLE`) or yields explicit unavailable
  sections; an earlier revision never substitutes for a corrupt latest revision.

## Serialization, versioning and identity

- IMPLEMENTED: `domain/codecs.py` reads and writes StatisticalState schema 4 and EvidenceState
  schema 4 only. `research/specs.py` reads and writes ResearchSpec schema 3 only. Older or
  unknown versions fail with a typed unsupported-version error; there is no fixture fallback,
  dictionary identity path, or schema-1/2/3 reader.
- IMPLEMENTED: strict JSON boundary primitives in `domain/_json.py` reject duplicate keys,
  non-finite numbers, kind/version mismatch, missing/extra fields and inconsistent identities.
- Load path: verify artifact path/size/hash → JSON → direct version parser → identity check →
  typed use. SQLite JSON remains boundary data until validated. Serialize canonical JSON only at
  artifact/database/API/provider boundaries. Do not repeatedly parse trusted typed values
  between functions.
- Scientific identity includes measured values/units, population membership, tested universe,
  method parameters/versions, missingness, release/source hashes and the parent evidence hash.
  It excludes run/database/event/attempt IDs, artifact location, timestamps, provider rank and
  provider `_score`, and UI state.
- Operator ids and hashes (`state_id`, `evidence_state_id`, `candidate_id`, `hypothesis_id`,
  attempt/cache/artifact ids) do not change a scientific hash. A changed measurement, method
  parameter, tested universe or population does.
- Jev inference identity includes projection bytes, question definitions, pinned model identity
  and adapter version; policy version is deliberately excluded so policy experiments do not
  rerun inference.