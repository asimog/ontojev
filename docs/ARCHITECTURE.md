# OntoJev Architecture

> Status: target design and requirements, not a claim that every capability exists. For the inspected current implementation and remaining work, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## Current implementation boundary

The diagram and numbered design sections below describe the target architecture. The inspected implementation has these boundaries:

| Area | Current owner and behavior | Remaining target |
|---|---|---|
| Scope | `research/specs.py`: `CohortSpec`, `ResearchSpec`, LUAD profile; `research/capability.py` derives a release-pinned typed capability from status + one project record + one aggregate open-file facet request; `research/campaign.py` gates profiles by readiness | Wider source/capability/readiness bindings and continuous Campaign selection; LUAD scientific validation is not assumed. |
| Universe | `domain/discovery.py`, `research/discovery.py`: complete release-bound protein-coding enumeration (`GENE_ID_ASC_INDEXED_COMPLETE_V1`, defect guard ceiling) with an operational shard ledger and a terminal-all-required gate; historical prefix specs remain readable and labelled | Adopted contracts for any new source; no prefix is ever genome-wide. |
| Mutation | Stage 4 counts distinct cases from complete released-occurrence scans with canonical-transcript composition (`MUTATION_CANONICAL_COMPOSITION_V1`) and DROP / RETAINED / JEV_REVIEW dispositions; background-model driver inference is recorded as `DEFER_WITH_JUSTIFICATION` | Inferential driver support once covariate inputs are admitted. |
| Expression | `research/expression_discovery.py`: case-labelled UQFPKM summaries and descriptive tails with declared RETAIN / DROP / JEV_REVIEW dispositions, independent nomination and an admitted run-volume plan; one aggregate open-file facet request records per-workflow coverage and annotates single-family sources | QC and defensible inference when eligible. |
| CNV | `research/cnv_discovery.py`: independent deterministic case-shard scan/merge of the project occurrence index, caller-aware recurrence dispositions, terminal all-shards-required gate | Caller-aware inference beyond descriptive recurrence. |
| Integration | `research/cutover.py`: deterministic modality union (`MUTATION_EXPRESSION_CNV_UNION_V1`) into the same canonical `StatisticalState`; `research/systematic.py` executes the full spine as the canonical Campaign path | Extend sources inside the same union contract. |
| Control | `research/wide.py`, `deep.py`, `nextmove.py`, `investigation.py`, `program.py`, `hypothesis_policy.py` | `pre-wide-policy-v1` bounds Wide by measured evidence (ties fail closed); the autonomous candidate queue needs no operator flag; `hypothesis-policy-v1` consumes recorded critique and requests exactly one registered evidence-producing test or records a typed KEEP/ABSTAIN; durable `program-loop-v2` owns dispatch identity and bounded retry. |
| Finalization | `research/finalize.py`, dossier contracts/renderer | Already implemented; extend scientific evidence summaries only when needed. |
| Program/ownership | Durable program state (append-only `program-state` artifacts), `campaign-selection-v2`, release observation, exclusive directory lock held only around mutation windows | Continuous multi-campaign scheduling against new release/method/profile identities; LUAD promotion only after live validation. |
| Storage/ops | SQLite schema 7 with sequential DDL migrations (v6→v7), pre-migration backups, read-only `doctor`, structured logging | Retention policy only for disposable caches; canonical evidence is never deleted or rewritten. |

Paths above are under `cancerjev/`. No parallel state architecture or workflow engine is planned. The full evidence map and bounded work units are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

Systematic complete-universe discovery (`GENE_ID_ASC_INDEXED_COMPLETE_V1`) is the canonical path; the older `GDC_FAST_SEARCH` provider-ranked lane is transitional/compatibility behavior retained as a labelled researcher comparator, and live affected-case counts already derive from the complete occurrence scan rather than the invalidated bucket.

**Canonical Campaign execution spine (implemented, offline-verified).** One `SYSTEM_AUTONOMOUS` run executes: profile/spec/capability validation → mutation discovery → expression discovery → complete CNV case-shard completion → terminal CNV merge → deterministic modality union → canonical `StatisticalState` persistence → `pre-wide-policy-v1` selection (complete union persisted; a required cut uses only the declared measured ordering; boundary ties fail closed as `PRE_WIDE_ORDERING_AMBIGUOUS`) → Wide Jev → Python admission → the autonomous candidate queue (Deep Jev, registered deterministic actions, bounded hypotheses, Stage 8 final result, dossier and no-Jev comparison) with no operator candidate flag. `research/systematic.py` is the only autonomous executor; a researcher run keeps its separate ownership path.

**Validation activation (implemented).** An EXPERIMENTAL profile can execute the identical canonical spine without weakening the autonomous gate: `python -m cancerjev campaign --validation` runs under `VALIDATION_RUN` ownership, reports `activation=VALIDATION` and `readiness_effect=NONE`, can never be selected by the Program (`campaign-selection-v2` only ever dispatches autonomous-ready profiles), and cannot change readiness. Readiness still changes only by an explicit code edit after the live dossier is reviewed — the validation route produces that evidence, it does not confer capability.

**One Campaign budget (implemented).** Mutation, expression, every CNV shard, the terminal merge and every candidate follow-up share one `RunBudget` built from the declared `gdc-campaign-v1` ceilings (`CAMPAIGN_REQUESTS`, `CAMPAIGN_PAGES_PER_QUERY`, `CAMPAIGN_DOWNLOAD_BYTES`), sized from the measured live cost of the declared cohort. The per-acquisition-shard 512 MiB allowance remains. A follow-up therefore acquires through the same Campaign budget instead of an uncontrolled new one, and an exhausted budget still reports `INCOMPLETE_OR_UNAVAILABLE`.

**Measurement ≠ nomination (implemented).** Expression measurement is observed for every gene with a computable distribution, but `RETAIN` now requires at least one actual tail case beyond a Tukey fence (`expression-dispositions-v2`); a valid distribution with zero tail cases is `DROP` with `NO_TAIL_CASE_OBSERVED` while its measurement still populates the `StatisticalState`. This keeps ordinary measurable genes out of the modality union without shrinking what is measured, and prevents a union for which the pre-Wide policy would have to fail closed.

**Candidate lifecycle (implemented).** `CandidateStatus` transitions are a declared, enforced state machine: the repository refuses any update that is not a declared edge (`ILLEGAL_CANDIDATE_TRANSITION`), terminal statuses have no outgoing edge, `CANDIDATE_COMPLETE` is preserved by crash recovery (only in-flight candidates are `DEFERRED`), a dossier-owning candidate is never deferred, and a replay that finds a persisted dossier re-asserts completion after an interrupted finalization. Status vocabulary is single-sourced (`DEEP_ANALYZED`, never a free-form label).

**Hypothesis loop (implemented to the action-space boundary).** `hypothesis-policy-v1` consumes the recorded hypothesis critique and produces exactly one declared decision: dispatch one registered **evidence-producing** action (`TEST_HYPOTHESIS`), keep the statements (`KEEP_HYPOTHESIS`), or abstain. Integrity and summary actions can never serve as a hypothesis test — they verify or describe existing evidence and cannot discriminate between explanations. While the registry contains no evidence-producing action eligible on an `EvidenceState` revision, a testable hypothesis is `KEEP_HYPOTHESIS` with the explicit reason `NO_EVIDENCE_PRODUCING_TEST`; the decision, thresholds, per-statement critique and the missing requirement are persisted, so the loop closes the moment such an action is registered without any policy change.

Evidence maturity is derived deterministically from persisted typed evidence (`evidence-maturity-v1`: `MEASURED` → `DESCRIPTIVE_CANDIDATE`, with higher levels reported together with their exact missing prerequisite); no Jev judgment or ranking can promote it. Known-cancer context and evaluation labels are machine-checked out of feature construction, disposition triggers and admission (see `tests/leakage/`), and replication holdouts, when declared, are deterministic hash-sorted case partitions with a method-specific rationale.

Pathway membership is adopted from Reactome top-level pathways (`REACTOME_TOP_LEVEL_ENSEMBL_V1`, CC-BY-4.0, filtered Homo sapiens snapshot with a recorded hash and an exact-identifier contract against the live Content Service for TP53); it is descriptive membership only — enrichment, p/q-values and cross-modal pathway analysis are deferred to their declared contracts, and an unmapped gene is `NO_PATHWAY_MEMBERSHIP_OBSERVED`, never negative.

The TypeSafe/Jev capability posture is committed in [TYPESAFE_DECISIONS.md](TYPESAFE_DECISIONS.md) (`typesafe-decisions-v1`, machine-checked): current Wide/Deep/hypothesis questions are kept and were re-validated live against the pinned model on 2026-09-25; **Arm Jev is DEFERRED** because deterministic dispositions plus typed pending-semantic-review carrying already cover admission, so `JEV_REVIEW` entries are never admitted and never silently dropped. That exclusion is now enforced by the ranking policy itself: while Arm Jev is deferred, a `JEV_REVIEW`-nominated (or `PENDING_SEMANTIC_REVIEW`-warned) state can never be promoted by favorable Wide answers.

Every run records its execution ownership (`SYSTEM_AUTONOMOUS` or `RESEARCHER_RUN`, SQLite schema 7): operator deep flags are rejected before any work on autonomous runs, cross-owner guards fail closed in both directions, and researcher runs keep their own typed scope while sharing only provenance-exact immutable caches. Schema upgrades are sequential DDL-only migrations (currently v6→v7) that checkpoint the WAL, back up the database first, update the version only after success, leave evidence rows untouched, and fail closed on unsupported or future versions.

Campaign coordination is named, versioned and deterministic: `campaign-selection-v2` admits only profiles validated for autonomous use in declared priority-then-campaign-id order, adds the durable identity gate (a completed campaign is redispatched only when the observed release identity, method identity or profile identity changed), and applies a bounded exponential retry (`CAMPAIGN_RETRY_SCHEDULED`, capped at the declared attempt count) for failed dispatches. `program-loop-v2` runs at most one bounded Campaign per cycle, persists each cycle's durable state as an append-only `program-state` artifact (read back by registering-run order, so restarts cannot redispatch the same completed campaign), observes the release once per cycle (`release-monitor-v1`, typed provenance, `RELEASE_OBSERVED` event) and records `PROGRAM_IDLE` with per-profile decision reasons when nothing is eligible. The long-running worker owns the research lock only around each cycle and sleeps outside it; its heartbeat carries the canonical package version.

Functional and external sources are governed by [FUNCTIONAL_SOURCES.md](FUNCTIONAL_SOURCES.md) (`functional-sources-v1`, machine-checked): every candidate (DepMap CRISPR, Sanger CGC, targetability resources, independent-cohort replication) is **DEFERRED** this cycle, the seven evidence axes stay distinct, `FUNCTIONALLY_SUPPORTED` remains unattainable without an adopted contract, and Jev can never manufacture functional evidence.

### Measurement reconciliation retained from the previous architecture document

The frozen `tests/reconciliation/fixtures/reconciliation_dr46` corpus independently compares analysis buckets with released `/ssm_occurrences`. For its TP53/TCGA-LUAD capture, the analysis bucket is 393, released occurrences are 299 and distinct cases are 281. These are fixture-specific observations, not current live counts. A gene with no released occurrences can still have a nonzero analysis bucket. The bucket must therefore not be presented as a distinct released-case measurement.

Stage 4 already uses the complete project occurrence scan and local distinct-case derivation. The older provider-ranked live path retains bucket semantics but is isolated as an explicitly labelled researcher/comparator command and can never produce canonical autonomous Campaign results. Neither released-occurrence absence nor project SSM coverage establishes callable wild-type cases. Historical invalidated results must be superseded explicitly, not rewritten.

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
