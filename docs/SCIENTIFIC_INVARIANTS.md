# OntoJev Scientific Invariants

> Status: target design and requirements, not a claim that every capability exists. For current implementation findings, see the [code audit](CODE_AUDIT.md); remaining work is in the [implementation plan](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

This document contains hard scientific and control rules. These rules are intended to remain stable even as implementation details and version numbers change.

## 1. Control ownership

The human bounds the permitted domain and access/resource constraints. OntoCodex directs scientific questions, priorities and synthesis. Jev supplies bounded typed semantic judgments; calibration and incremental value require evidence. Python owns deterministic computation, eligibility checks, budget enforcement and execution.

OntoCodex may propose a registered next action. Python must validate its scope, inputs, provenance, readiness and remaining budget before execution. Existing Wide/admission and next-move policies remain deterministic enforcement boundaries; they are not the complete scientific-director architecture.

Research-control Jev affects trajectory and is not biological support. Scientific-evaluation Jev is versioned interpretation, distinct from observed and deterministically derived evidence. Preserve OntoCodex scientific judgments and external literature context as separately attributable records.

## 2. Measurement before interpretation

```text
GDC source
→ strict parser
→ reconciliation/validation where required
→ deterministic measurement
→ scientific method
→ typed evidence
→ Jev
```

Never:

```text
uncontrolled raw genomics → Jev / OntoCodex
```

Raw provider JSON, genomic matrices, event rows, and unparsed files do not become semantic evidence directly.

## 3. Deterministic scientific ownership

Deterministic code owns:

```text
counts
frequencies
normalization
statistics
multiple-testing correction
pathway membership
sample matching
missingness classification
evidence creation
```

Jev may interpret deterministic evidence but cannot manufacture it.

## 4. Missing is not negative

Preserve:

```text
missing != negative
```

Specifically:

```text
no mutation occurrence != automatically wild type
no CNV occurrence != automatically diploid/neutral
no expression assay != expression = 0
```

Distinguish:

```text
ACQUISITION COMPLETENESS
ASSAY AVAILABILITY
SCIENTIFIC MISSINGNESS
```

## 5. Scientific Universe and Shards

The Universe is the scientific population of eligible genes.

A Shard is only an operational acquisition/computation unit.

```text
Universe != Shard
```

Never use batching as scientific sampling.

A Research Run is the atomic execution unit, normally at most ten minutes. Campaigns may span many runs. Preflight significant acquisition; refuse work that cannot fit, persist continuation state and resume in another run.

Successful raw shards are deleted only after derived evidence and reacquisition provenance are durably published and read back. Failed/interrupted workspace cleanup is recoverable. Raw workspace must not accumulate indefinitely.

All scientifically required Shards must reach terminal status before a global method finalizes. Query coverage is not assay callability; partial coverage stays partial.

Streaming sufficient statistics are permitted only where mathematically equivalent to the declared complete-data calculation.

## 6. Cohort integrity

One Campaign uses one scientifically coherent cohort.

Modality-specific assay populations may differ.

Cross-modal calculations require explicit compatible population/sample contracts.

Respect:

```text
case
sample
aliquot
file
```

Case-level overlap does not prove sample-level matching.

## 7. Descriptive vs inferential evidence

Descriptive evidence includes observations such as:

```text
counts
medians
dispersion
tail structure
ranks
event categories
hotspot descriptors
```

Inferential claims require an explicit contract including, where applicable:

```text
population
tested Universe
null/background model
effect size
uncertainty
test statistic
multiple-testing family
FDR/FWER method
sample-size requirement
method/version
limitations
```

Do not create p-values merely because a feature exists.

Jev never substitutes for statistical inference.

## 8. Established methods first

Prefer established GDC/GDAN/TCGA/NCI computational-genomics methods.

Before introducing a method ask:

> Does an established method already address this question?

If yes, evaluate/reuse/adapt it.

If no, justify the new deterministic method.

Do not create opaque weighted target scores by default.

## 9. Evidence levels

```text
MEASURED
→ DESCRIPTIVE_CANDIDATE
→ STATISTICALLY_SUPPORTED
→ INTERNALLY_REPLICATED
→ EXTERNALLY_REPLICATED
→ FUNCTIONALLY_SUPPORTED
```

Jev may influence prioritization.

Jev may not promote scientific evidence level.

## 10. Discovery/validation leakage

External information must be classified as:

```text
DISCOVERY_INPUT
VALIDATION_LABEL
ORTHOGONAL_FOLLOW_UP
```

Validation labels must not leak into discovery thresholds, Arm Jev, Wide Jev, or Python admission when they are later used to assess discovery performance.

## 11. Hypotheses

```text
LLM hypothesis = NOT_EVIDENCE
```

Jev may critique a hypothesis.

Only a registered deterministic analysis can create new evidence from it.

## 12. EvidenceState immutability

Evidence revisions are immutable.

New deterministic evidence produces a new `EvidenceState`.

Historical EvidenceStates are never rewritten.

## 13. Candidate isolation

Each Candidate has its own bounded investigation chain.

Never merge evidence histories across candidates.

## 14. Fail-closed semantic behavior

Invalid Jev output must become typed failure/unavailability.

Failures include:

```text
timeout
transport failure
empty output
malformed output
wrong answer type
unknown question
wrong question-set version
missing field
forbidden field
non-finite/out-of-range value
duplicate answer
partial batch
state/target identity mismatch
stale revision
invalid applicability
```

A semantic failure may never silently retain, admit, advance, or complete a target. A research-control failure may use a declared direct-OntoCodex or deterministic fallback, recorded as a fallback rather than a Jev scientific answer. Invalid director output cannot create measured evidence.

## 15. Pathway evidence

Pathway membership is deterministic, versioned, and source-grounded.

Jev may interpret pathway evidence.

Jev cannot invent pathway membership.

## 16. Scientific validation and readiness

Code execution is not scientific validation.

Scientific methods and CampaignProfiles should expose a readiness state or equivalent:

```text
EXPERIMENTAL
→ VALIDATED_FOR_REPLAY
→ VALIDATED_FOR_AUTONOMOUS_USE
```

Only scientifically validated methods/profiles should enter normal autonomous Campaign selection.

## 17. Historical evidence

Historical scientific artifacts are immutable.

If a measurement or method is later invalidated:

```text
preserve old artifact
record supersession/invalidation
produce new evidence under new method/version
```

Never rewrite history to fit new semantics.

## 18. Claim boundary

OntoJev discovers computational target candidates.

It does not convert computational evidence into experimental, therapeutic, safety, or clinical validation.
