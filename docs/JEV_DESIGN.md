# OntoJev Jev Design

> Status: target design and requirements, not a claim that every capability exists. For the inspected current implementation and remaining work, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## 1. Purpose

Current code implements Wide, Deep and hypothesis judgments through `cancerjev/jev/` and Python research policies. Arm Jev is a conditional target capability and is not implemented. Noul/Choice/Score support already exists; proposed batching/routing changes require current provider-contract verification and a complete failure corpus (P11).

Wide currently includes cancer-census annotation. If that annotation is used as a validation label, it must be excluded from discovery/admission inputs under the planned information-role contract (P09). Existing semantic output must not be described as independent validation against the same label.

Jev supplies bounded semantic judgment over structured deterministic scientific evidence.

It does not replace measurement, statistical genomics, policy, or action execution.

Core rule:

```text
Jev judges.
Python decides.
Python executes.
```

## 2. Jev boundary

Never:

```text
raw genomics → Jev
```

Correct boundary:

```text
GDC source
→ strict parser
→ deterministic measurement/statistics
→ typed scientific evidence
→ bounded Jev projection
→ typed semantic judgment
→ Python policy
```

Jev never performs:

```text
provider acquisition
parsing
mutation counting
expression normalization
statistical testing
multiple-testing correction
pathway membership
sample matching
missingness inference
action execution
```

## 3. Arm Jev

Arm Jev is optional and modality-specific.

Flow:

```text
deterministic modality evidence
        ↓
Python classification
   ┌──────────┬──────────┬─────────────┐
   ↓          ↓          ↓
 RETAIN      DROP      JEV_REVIEW
   ↓                     ↓
   │                  ARM JEV
   └────────────┬────────┘
                ↓
        modality candidates
```

Only `JEV_REVIEW` requires Arm Jev.

Purpose:

> Does this structured within-modality evidence contain a potentially important pattern that conventional ranking underrepresents?

Strong deterministic retains bypass Arm Jev.

Clear deterministic drops bypass Arm Jev.

Arm Jev may affect semantic preservation only.

It cannot alter measurements or evidence level.

## 4. Wide Jev

Wide Jev is the primary integrated discovery judgment layer.

Input:

```text
one canonical StatisticalState
```

Suitable semantic dimensions may include:

```text
rank discordance
cross-modal coherence
cross-modal discordance
non-obvious evidence configuration
under-ranked target pattern
dominant uncertainty
value of deeper investigation
```

Wide Jev returns typed judgments.

Python owns ranking, admission, candidate creation, caps, and failure behavior.

## 5. Deep Jev

Deep Jev operates during Candidate investigation.

Input:

```text
Candidate
+
immutable EvidenceState revision
```

Deep Jev may judge:

```text
remaining uncertainty
evidence sufficiency
robustness
information value of a registered follow-up
information value of hypothesis generation
whether investigation should continue
```

Deep Jev cannot select arbitrary tools or execute actions.

Python ActionPolicy owns the next move.

## 6. Hypothesis Jev

```text
LLM hypothesis
→ NOT_EVIDENCE
→ Jev critique
```

Jev may assess:

```text
groundedness
testability
overclaim
distinguishing value
```

A hypothesis becomes scientifically relevant only if a registered deterministic action can test it.

## 7. TypeSafe capability policy

Before changing Jev behavior, review current TypeSafe capabilities such as:

```text
Noul
Choice
Score
batching
fan-out
reranking
confidence routing
semantic feature discovery
uncertainty judgment
action-value judgment
hypothesis critique
cascades
```

Classify each:

```text
ADOPT
KEEP
DEFER
REJECT
```

For every semantic question record:

```text
why deterministic code/statistics cannot answer it exactly
typed input
question
primitive
applicability
failure semantics
Python consumer
```

Do not add TypeSafe capabilities merely because they exist.

## 8. Failure semantics

All Jev layers should fail closed on:

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
out-of-range value
non-finite value
duplicate answer
partial batch
state/target identity mismatch
stale revision
invalid applicability
```

Invalid semantic output becomes typed failure/unavailability.

It must never silently retain, admit, advance, or complete a target.

## 9. No-Jev comparator

OntoJev must preserve a deterministic comparator based on the same pre-Jev scientific evidence.

```text
validated computational genomics
vs
validated computational genomics + selective Jev
```

Report decision/ranking/trajectory deltas.

Do not claim Jev superiority merely because outcomes differ.

## 10. Evidence-level boundary

Jev cannot promote:

```text
MEASURED
DESCRIPTIVE_CANDIDATE
STATISTICALLY_SUPPORTED
INTERNALLY_REPLICATED
EXTERNALLY_REPLICATED
FUNCTIONALLY_SUPPORTED
```

Evidence maturity changes only when deterministic/external scientific evidence supports it.
