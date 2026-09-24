# Scientific contracts and identity

Architecture baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`, reviewed 2026-09-24.
Stage 1 contracts added from `fb52305b3d42a39b05f6c269bbfa3d6213fd51d2` on 2026-09-25.
The current production runtime still writes v1 fixture/v2 live JSON artifacts. The records below
are now implemented where explicitly labelled; later consumers/features remain PLANNED.
The [source-field trace](GDC_STRATEGY.md) limits admitted scientific content.

## Current production contract assessment

Stage 2 adds immutable HypothesisDraft and Noul/Choice/Score answer records, plus verified stored
state/revision/hypothesis/evaluation wrappers. Stage 3 computes frozen MutationObservation and
ExpressionObservation/Log2Summary records before v2 serialization; StateSummary travels through Wide,
and typed answers/checks/revisions travel through policy and investigation. These compatibility
records preserve v2 semantics; they do not relabel v2 as v3. See [Stage 3](STAGE_03_HANDOFF.md).

| Concept | Classification | Protected invariant in transition |
|---|---|---|
| ResearchSpec, CohortSpec, AcquisitionSpec | STRONGLY TYPED | Validated bounded scope |
| GDC provider records | ADEQUATELY TYPED | Identifier membership and provider types |
| ProjectFrame | ADEQUATELY TYPED, specialized | Common frame separate from lane data |
| Current StatisticalState composition | PARTIALLY TYPED | Typed lane/quality computations and immutable summary; full v2 serialization retained |
| Candidate, EvidenceState, observation/check | PARTIALLY TYPED | Validated candidate source, immutable typed checks/revision and bound summary; legacy presentation metadata retained |
| ActionDefinition | STRONGLY TYPED | Method/question/unit/limitations/input kind |
| ActionEligibility/ActionOutcome | PARTIALLY TYPED | Typed checks and checked contradiction counts; artifact-inspection diagnostics remain dictionaries |
| QuestionDefinition/provider envelope | ADEQUATELY / PARTIALLY TYPED | Exact roster and answer variant |
| Validated Jev evaluation | ADEQUATELY TYPED for Wide/Deep policy | EvaluationRecord retains immutable answers/applicability through policy/cache |
| Hypothesis | PARTIALLY TYPED then widened | Generated text cannot become measurements |
| Dossier, API JSON, generic event envelope | SHOULD REMAIN A BOUNDARY DICTIONARY | Validated inputs, truthful section availability |

## IMPLEMENTED, standalone: common frozen records

`cancerjev/domain/measurements.py` contains these contracts. They authorize no acquisition.

Use frozen dataclasses, enums and explicit unions. Tuples/frozensets or immutable snapshots protect
nested values: frozen=True around mutable lists is insufficient. Dynamic identifier maps remain
appropriate when their values are typed. No general inheritance or serialization framework.

| Record | Fields and invariant |
|---|---|
| EntityRef | GENE kind, Ensembl ID, display symbol, release; symbol is not a join key |
| PopulationFrame | cohort/project, CASE or SAMPLE unit, known eligible IDs or UNKNOWN eligibility, examined IDs, membership hash, selection rule; subset membership checked |
| TestedUniverse | ordered IDs, hash, source/release/filter/order/offset, reported total, completeness for declared slice; inferential family separately identified |
| MethodRef | ID/version, units, duplicate rule, transform, estimator, missingness, limitations; MethodParameters has only optional ddof=1 and pseudocount=1, not a metric bag |
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
Current scalar units are restricted to nonnegative UQFPKM and log2(UQFPKM+1), not arbitrary signed
effects. A future inferential effect requires its own admitted unit/method contract.

## IMPLEMENTED contract only: ResearchSpec composition

```text
ResearchSpecV2(
  spec_id, intent, cohort,
  universe=GeneUniverseSpec(limit<=1000, offset=0, protein_coding, GENE_ID_ASC),
  mutation=MutationLaneSpec, expression=ExpressionLaneSpec, cnv=CnvLaneSpec,
  reduction_policy, wide_policy, deep_policy, allowed_actions,
  limits=ScientificLimits(max_cohort_cases<=1000, max_survivors<=10,
                         max_promotions<=3, max_revisions<=2),
  output_version=3)
```

Initially retain TCGA-LUAD, max_cohort_cases=1000, survivors<=10, promotions<=3 and E0/E1/E2.
These are three concrete slots, not a generic lane registry. The strict
`research_spec_v2_from_dict` reader requires the RESEARCH_SPEC kind/version and rejects extra fields.
No discovery profile is registered yet. A CNV survivor spec requires mutation enablement; the
independent expression arm requires expression enablement. Only existing registered action IDs and
unchanged Wide/Deep policy versions are accepted. Runtime safety caps remain outside this spec.
Freeze effective specification before acquisition. Selection/tested-family changes affect scientific
context; timeouts, paths and cache do not. A lane selects a declared method/population/bounded scope,
never an arbitrary endpoint or executable expression. Operational settings remain separate.

## IMPLEMENTED standalone lane/state contracts; runtime composition PLANNED

| Contract | Admitted content | Prohibited inference |
|---|---|---|
| MutationCountResult | entity/frame-bound affected-case and separate SSM coverage measurements, Quality | Absent bucket=wild type; project total=callable denominator |
| ExpressionSummaryResult | entity-bound immutable case-labelled UQFPKM values; local log2(x+1) median/sample SD/min/max, Coverage/Quality/sources | Tumor-normal differential expression or specimen matching from case labels |
| CnvOccurrenceResult | entity/frame-bound raw occurrences, optional source file/caller/sample/copy-number context; Quality/sources | Neutral from absence, clinical amplification or pooling incompatible numeric calls |
| StatisticalStateV3 | entity, frame, universe, typed mutation/expression/CNV slots, Quality, scientific and separate operational sources | lanes: dict[str, Any]; semantic probabilities in measured fields |
| EvidenceStateV3 | accepted state hash, parent scientific hash, E0/E1/E2 index, ActionRef, immutable EvidenceChecks, derived CheckSummary, Quality/sources | Mutating E0 or operational IDs in scientific identity |

Disabled/unacquired lanes have explicit outcomes, not empty successful results. A provider
cnv_change_5_category=Loss becomes LOSS_UNSPECIFIED, not heterozygous deletion. Unknown categories
are UNSUPPORTED_CATEGORY, never neutral. Conflicting case calls remain conflicts. Numeric copy
number remains provider context until caller/sample comparability is accepted.
No CNV provider parser, complete-query acquisition or category-count descriptor is admitted by
constructing this record. These remain Stage 6. Expression tails remain Stage 5. Stage 3 implements
typed existing lane computation/composition with separate ProviderGene context; historical provider summaries
are retained separately and verbatim by the legacy reader, never averaged or converted to local values.
E0 references the accepted state; E1/E2 require parent/action/checks. Resolving those hashes to
stored artifacts and authorizing action IDs are consumer responsibilities, not constructor side effects.

### Current checks and handoffs; future v3 integration distinguished

EvidenceCheck carries check ID, method, VERIFIED/CONTRADICTED/NOT_OBSERVED outcome, claim, input refs,
reason and n_effective. CheckSummary is constructed from checks; nonnegative counts sum to total.
Missing checks_contradicted cannot mean zero.

Stage 3's current v2 integrity actions produce IntegrityCheck and ComputedEvidenceRevision.
Their checked summaries feed Deep policy without dictionary reconstruction. CandidateEvidence
retains a validated LegacyArtifact; the two existing integrity actions inspect serialized artifacts
deliberately. Current projection/hypothesis/dossier presentation retains v2 boundary conversion.
The following fuller v3 action/candidate integration remains PLANNED, not a second active runtime.

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

IMPLEMENTED `domain/codecs.py:read_state/read_evidence` explicitly dispatch fixture schema 1,
live schema 2 and typed schema 3. V3 fields are parsed directly with extra/missing-field rejection;
duplicate JSON keys, invalid numeric values, kind/version mismatch and inconsistent identities fail.
`write_state/write_evidence` emit canonical v3 JSON; they are not used by production writers yet.
Unsupported versions return UNSUPPORTED_SCHEMA_VERSION, not a fixture fallback. Retain historical
bytes/hashes/question sets/schema-4 databases. A validated v2 legacy view preserves v2 semantics;
conversion to v3, if needed, writes a new derived artifact with conversion version and old hash.

`legacy_codecs.py` returns a frozen LegacyArtifact boundary snapshot: original bytes, original
version/hash, typed legacy metric/population summaries and checked integrity counts where applicable.
Legacy units/statuses are not mapped onto v3 variants. Its fresh `boundary_representation()` is for
presentation/replay, not an internal scientific domain object. Readers check numeric/status contracts,
required scientific structure and internal population/check consistency; they do not reexecute
scientific methods or prove source authenticity. Provide `expected_hash` when bound to a stored row.
Stage 2 must add size/byte-hash/path and entity/candidate/parent/artifact binding validation before
replacing current consumers. A scientific hash alone is not an artifact-integrity proof.

Load path: verify artifact path/size/hash -> JSON -> direct version parser -> identity check -> typed use.
SQLite JSON remains boundary data until validation. Cache hydration validates roster/primitive/model/
projection binding once on entry. Do not repeatedly parse trusted typed values between functions.
Serialize canonical JSON only at artifact/database/API/provider boundaries.

New scientific identity includes values/units, population membership, tested universe, method
parameters/versions, missingness, release/source hashes and parent evidence hash. Exclude run/database/
event/attempt IDs, artifact location, timestamps, provider rank and UI state. Keep existing v1/v2
identity functions for history; do not retroactively change hashes. Jev inference identity includes
projection/question/model/adapter versions, with policy thresholds separate for replayable experiments.
