# OntoJev Architecture

> Status: target design and requirements, not a claim that every capability exists. For the inspected current implementation and remaining work, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## Current implementation boundary

The diagram and numbered design sections below describe the target architecture. The inspected implementation has these boundaries:

| Area | Current owner and behavior | Remaining target |
|---|---|---|
| Scope | `research/specs.py`: `CohortSpec`, `ResearchSpec`, LUAD profile; `research/capability.py` derives a release-pinned typed capability from status + one project record + one aggregate open-file facet request; `research/campaign.py` gates profiles by readiness | Wider source/capability/readiness bindings and continuous Campaign selection; LUAD scientific validation is not assumed. |
| Universe | `domain/discovery.py`, `research/discovery.py`: bounded indexed protein-coding prefix | Complete eligible universe with operational shard completion and global reduction. |
| Mutation | Stage 4 counts distinct cases from complete released-occurrence scans | Correct older `research/live.py` bucket consumer; add only justified scientific methods. |
| Expression | `research/expression_discovery.py`: case-labelled UQFPKM summaries and descriptive tails; one aggregate open-file facet request records per-workflow coverage and annotates single-family sources | QC, defensible inference when eligible, independent nomination. |
| CNV | `research/cnv_discovery.py`: positive indexed categories on mutation survivors | Independent caller-aware nomination; no assumed neutral denominator. |
| Integration | `research/cutover.py`: states only for mutation survivors | Deterministic modality union into the same `StatisticalState`. |
| Control | `research/wide.py`, `deep.py`, `nextmove.py`, `investigation.py` | Preserve bounded Python control; extend scientific follow-up and explicit dispatch policy. |
| Finalization | `research/finalize.py`, dossier contracts/renderer | Already implemented; extend scientific evidence summaries only when needed. |
| Program/ownership | Existing run lifecycle and exclusive directory lock | Continuous Campaign selection, release comparison and separate researcher ownership. |

Paths above are under `cancerjev/`. No parallel state architecture or workflow engine is planned. The full evidence map and bounded work units are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

### Measurement reconciliation retained from the previous architecture document

The frozen `tests/reconciliation/fixtures/reconciliation_dr46` corpus independently compares analysis buckets with released `/ssm_occurrences`. For its TP53/TCGA-LUAD capture, the analysis bucket is 393, released occurrences are 299 and distinct cases are 281. These are fixture-specific observations, not current live counts. A gene with no released occurrences can still have a nonzero analysis bucket. The bucket must therefore not be presented as a distinct released-case measurement.

Stage 4 already uses the complete project occurrence scan and local distinct-case derivation. The older provider-ranked live path still uses bucket semantics and needs P01. Neither released-occurrence absence nor project SSM coverage establishes callable wild-type cases. Historical invalidated results must be superseded explicitly, not rewritten.

Current GDC workflow interpretation is grounded in the pinned upstream sources in the plan: STAR-derived expression differs from historical HTSeq, and ASCAT/ABSOLUTE/DNAcopy/GATK4 CNV products are not interchangeable. Inspect current pipeline documentation before enabling any new source or method.

## 1. Purpose

OntoJev is an autonomous computational cancer target-discovery system.

Its architecture separates measurement, deterministic computational genomics, semantic judgment, policy, evidence revision, and campaign progression.

The core principle is:

> **Jev judges. Python decides. Python executes.**

The system strengthens evidence flowing into the existing Wide/Deep Jev control spine rather than replacing that spine.

## 2. End-to-end architecture

```text
GDC RELEASE / SOURCE CONTEXT
        ↓
CohortSpec / ResearchSpec / CampaignProfile
        ↓
COHORT CAPABILITY DISCOVERY
        ↓
COMPLETE SCIENTIFIC GENE UNIVERSE
        ↓
DETERMINISTIC COMPUTATIONAL GENOMICS

 mutation     expression     CNV/SV      other validated modalities
    ↓             ↓            ↓                    ↓
 validated    validated     validated            validated
 evidence     evidence      evidence             evidence
    └───────────────┬───────────────┬────────────────┘
                    ↓
        deterministic/statistical evidence
                    ↓
          per-modality baseline
                    ↓
    RETAIN / DROP / SEMANTIC REVIEW
                    ↓
         optional selective ARM JEV
                    ↓
           modality candidates
                    ↓
        deterministic candidate union
                    ↓
              StatisticalState
                    ↓
                 WIDE JEV
                    ↓
          Python Wide/admission policy
                    ↓
                Candidate
                    ↓
             EvidenceState E0
                    ↓
                 DEEP JEV
                    ↓
            Python ActionPolicy
              /             \
             ↓               ↓
 deterministic follow-up   bounded hypotheses
             ↓               ↓
       new evidence       Jev hypothesis critique
             └───────┬───────┘
                     ↓
              EvidenceState E1
                     ↓
                  DEEP JEV
                     ↓
          Python next-move policy
                     ↓
 FOLLOW_UP / GENERATE_HYPOTHESES /
        COMPLETE / ABSTAIN
                     ↓
               bounded repeat
                     ↓
                  STAGE 8
                     ↓
          FinalCandidateResult
                     ↓
          authoritative dossier
                     ↓
         Jev vs no-Jev comparison
                     ↓
            CANDIDATE_COMPLETE
                     ↓
              next candidate
                     ↓
            CAMPAIGN_COMPLETE
                     ↓
       CampaignSelectionPolicy
                     ↓
          next campaign / idle
```

## 3. Architectural invariants

The following are core architecture and must not be replaced by parallel systems:

```text
StatisticalState
Wide Jev
Python Wide/admission policy
Candidate
EvidenceState
Deep Jev
Python ActionPolicy
Python next-move policy
hypothesis generation
Jev hypothesis critique
Stage 8
FinalCandidateResult
authoritative dossier
Jev-vs-no-Jev comparison
candidate completion
```

Existing types should be extended where possible.

No second integrated target-state architecture should be introduced unless the current `StatisticalState` contract is demonstrably incapable of representing the required scientific evidence.

## 4. Six scales

### Program

The continuously operating autonomous research program.

```text
AutonomousProgram
→ Campaign
→ Campaign
→ ...
```

### Campaign

One scientifically coherent cohort + one pinned GDC release/source context + one versioned method profile.

### Universe

Every scientifically eligible gene for the Campaign.

The scientific Universe is not an API page, one batch, one Shard, or a provider top-gene list.

### Shard

An operational subset used only for acquisition or computation.

Shard boundaries may not alter scientific membership, null models, multiple-testing families, ranking, or candidate eligibility.

### Target state

One canonical integrated `StatisticalState` for a single gene/target.

Wide Jev evaluates Target states.

### Investigation

One admitted Candidate with an independent immutable `EvidenceState` chain.

Different candidates never share an investigation chain.

## 5. Cohort and assay architecture

A Campaign uses one scientifically coherent cohort.

Modality-specific assay populations may differ:

```text
COHORT CASE FRAME
        │
        ├── mutation-eligible cases
        ├── RNA-eligible cases
        ├── CNV-eligible cases
        └── other assay-eligible populations
```

Cross-modal calculations must derive explicit compatible intersections when required.

Respect GDC identity levels:

```text
case
sample
aliquot
file
```

Case-level correspondence is not automatically sample-level correspondence.

## 6. Scientific discovery architecture

Each validated modality may nominate candidates independently.

```text
complete Universe
→ modality-specific deterministic analysis
→ deterministic/statistical evidence
→ per-modality disposition
```

Potential deterministic disposition:

```text
RETAIN
DROP
JEV_REVIEW
```

Strong deterministic candidates do not require Arm Jev.

Clear deterministic drops do not require Arm Jev.

Only semantically ambiguous cases should reach Arm Jev.

## 7. Arm Jev

Arm Jev is optional and per modality.

Its role is to judge whether a structured within-modality pattern is underrepresented by conventional ranking.

It never calculates measurements or statistics.

Examples of deterministic inputs that may be summarized before mutation Arm Jev include:

```text
recurrence
background-adjusted evidence
hotspot/clustering evidence
functional-impact composition
subgroup concentration
uncertainty
deterministic rank
```

Arm Jev may preserve a `JEV_REVIEW` case into a modality candidate set.

It does not create final Candidates.

## 8. Candidate union and StatisticalState

Validated modality candidates are combined deterministically:

```text
mutation candidates
expression candidates
CNV candidates
other modality candidates
        ↓
deterministic candidate union
        ↓
canonical StatisticalState
```

Missing modalities remain explicit.

Cross-modal evidence is calculated only where scientifically valid matching and comparability contracts exist.

## 9. Wide Jev

Wide Jev operates over the canonical integrated target state.

Suitable semantic questions may include:

```text
rank discordance
cross-modal coherence
cross-modal discordance
non-obvious evidence configuration
under-ranked target pattern
dominant uncertainty
value of deeper investigation
```

Wide Jev provides typed semantic judgment.

Python owns ranking, admission, candidate creation, caps, and failure behavior.

## 10. Candidate investigation and Deep Jev

After Python admission:

```text
Candidate
→ EvidenceState E0
→ Deep Jev
→ Python ActionPolicy
→ deterministic action or bounded hypothesis path
→ EvidenceState E1
→ Deep Jev
→ Python next move
```

Deep Jev may judge uncertainty, evidence sufficiency, robustness, and information value.

Python owns actions and stopping.

Each registered action must be:

```text
typed
versioned
bounded
scientifically specified
source-grounded
deterministic
```

If ActionPolicy cannot resolve the next safe deterministic move, it must abstain.

## 11. Hypothesis path

```text
LLM hypothesis
→ NOT_EVIDENCE
→ Jev critique
→ registered deterministic test if available
→ new EvidenceState
```

No hypothesis becomes evidence merely because a model generated or endorsed it.

## 12. Stage 8

Every bounded Candidate investigation terminates in reproducible finalization:

```text
final EvidenceState
→ deterministic finalization
→ FinalCandidateResult
→ authoritative dossier
→ Jev-vs-no-Jev comparison
→ CANDIDATE_COMPLETE
```

The no-Jev comparator uses the same validated pre-Jev evidence and declared deterministic baseline policy.

Differences are decision deltas, not proof that Jev is superior.

## 13. Campaign progression

```text
CAMPAIGN_COMPLETE
→ CampaignSelectionPolicy
→ next validated Campaign / PROGRAM_IDLE
```

`CampaignSelectionPolicy` must be named, versioned, deterministic, testable, and persistently attributable.

It may not rely on lexical order, registry order, model choice, or Jev choice.

## 14. Researcher isolation

The optional Researcher Lab uses the same scientific engine but separate run ownership.

Researcher state cannot alter autonomous:

```text
CampaignProfile
candidate admission
candidate queue
ActionPolicy
EvidenceStates
hypotheses
dossiers
CampaignSelectionPolicy
campaign progression
```

Shared immutable source caches are acceptable if provenance and ownership remain exact.

## 15. KISS engineering boundary

Do not introduce:

- generic agent frameworks;
- generic DAG/workflow engines;
- microservices without demonstrated need;
- generic scientific plugin systems;
- a second domain/state architecture;
- LLM-generated GDC queries;
- LLM/Jev-owned action selection.

Prefer small typed Python objects, explicit functions, narrow adapters, deterministic policies, and current repository patterns.
