# OntoJev Product Scope

> Status: target design and requirements, not a claim that every capability exists. For current implementation findings, see the [code audit](CODE_AUDIT.md); remaining work is in the [implementation plan](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## 1. Product definition

OntoJev is an autonomous computational cancer target-discovery system.

Its purpose is to combine validated cancer-genomic measurements, established computational-genomics methods, multi-modal evidence integration, and selective Jev semantic judgment to identify target candidates that conventional single-method or single-modality rankings may under-prioritize.

The system-owned autonomous research program is the primary operating mode. The human supplies the lung-cancer domain and permitted GDC/GDAN evidence boundary; the human need not select genes, Candidates, modalities, statistical tests, shard sizes, data volumes, hypotheses or next experiments. OntoCodex owns those scientific proposals within registered capabilities and Python-enforced constraints.

An optional Researcher Lab may reuse the same scientific engine in isolated researcher-owned runs, but researcher state must never influence autonomous runtime state.

## 2. Research question

> Can Jev operating over validated, GDAN-style computational-genomics evidence identify biologically plausible cancer target candidates that established single-method or single-modality rankings would under-prioritize?

## 3. Claim boundary

OntoJev produces computational target candidates and reproducible evidence dossiers.

It does not, by itself, establish:

- experimental validation;
- therapeutic efficacy;
- clinical utility;
- safety;
- druggability;
- causal disease mechanism.

These remain distinct evidence axes.

```text
computational target candidate
!= experimentally validated target
!= therapeutically validated target
```

## 4. Primary product mode

```text
Lung-cancer domain
→ Program / ResearchPortfolio
→ ResearchQuestion
→ Campaign
→ bounded Research Runs
→ scientific-state revisions
→ target discovery
→ candidate investigations
→ Stage 8 dossiers
→ Campaign complete
→ CampaignSelectionPolicy
→ next Campaign / idle
```

The Program may continue across Campaigns.

Each Research Run normally lasts at most ten minutes; a Campaign may span many runs. Research broadly. Execute narrowly. Each Campaign remains versioned, attributable, reproducible, and immutable after completion.

Implemented laboratory scope includes seven adapters into the canonical mutation/expression/CNV, StatisticalState, Wide, Candidate and Stage 8/dossier spine. Replay reaches a dossier across runs. Whole-lane/whole-investigation attempts, recovery defects, sparse director context and capability engineering remain unfinished. See the [current audit](CODE_AUDIT.md) and [active milestones](IMPLEMENTATION_PLAN.md); the hierarchy below is the target lifecycle, not proof that legacy Program and laboratory portfolio records are fully reconciled.

The completed dossier is the external-review boundary. The autonomous loop may proceed to the next target without mandatory human scientific approval.

## 5. Campaign definition

A Campaign is:

> one scientifically coherent cohort + one pinned GDC release/source context + one versioned method profile.

A Campaign binds:

```text
cohort
GDC release/source context
tested Universe
validated modalities
method profile
validation profile
registered actions
policy versions
```

A materially different cohort, GDC release, or method profile is a different Campaign context.

TCGA-LUAD is the first intended validation CampaignProfile; the current LUAD ResearchSpec is not proof of autonomous scientific readiness. The implemented readiness vocabulary is `EXPERIMENTAL` → `VALIDATED_FOR_REPLAY` → `VALIDATED_FOR_AUTONOMOUS_USE`, and the declared LUAD campaign profile currently records `EXPERIMENTAL`. It is not a permanent product limitation.

## 6. Scientific scope

The engine is cancer-agnostic.

The normal target-discovery Universe is the complete eligible release-bound protein-coding gene set unless a Campaign declares another scientifically justified Universe.

Validated modality lanes may include:

- mutation;
- expression;
- CNV;
- structural variation;
- fusion;
- methylation;
- miRNA;
- RPPA/protein;
- scRNA/snRNA;
- clinical/outcome context.

A modality becomes active only when it has:

```text
source contract
workflow contract
QC contract
scientific method
typed evidence
validation
```

## 7. Evidence scope

OntoJev distinguishes:

```text
GENOMIC_DISCOVERY
STATISTICAL_SUPPORT
REPLICATION
FUNCTIONAL_DEPENDENCY
KNOWN_CANCER_CONTEXT
TARGETABILITY
CLINICAL_EVIDENCE
```

These must not be collapsed into one opaque weighted score.

External knowledge such as known drivers, Cancer Gene Census status, historical GDAN/TCGA findings or DepMap data must be explicitly classified as:

```text
DISCOVERY_INPUT
VALIDATION_LABEL
ORTHOGONAL_FOLLOW_UP
```

Validation labels must not leak into discovery thresholds or semantic admission when they are being used to evaluate discovery performance.

## 8. Evidence maturity

Target evidence may progress through:

```text
MEASURED
→ DESCRIPTIVE_CANDIDATE
→ STATISTICALLY_SUPPORTED
→ INTERNALLY_REPLICATED
→ EXTERNALLY_REPLICATED
→ FUNCTIONALLY_SUPPORTED
```

Not every target is expected to reach every level.

Jev can influence semantic prioritization but cannot promote evidence level.

## 9. Scientific method policy

Prefer established GDC/GDAN/TCGA/NCI computational methods.

For each proposed method ask:

> Does an established method already address this scientific question?

If yes, evaluate, reuse, or adapt it.

If no, justify the new deterministic method.

Do not invent ad hoc weighted target scores where established statistical or computational-genomics methods exist.

## 10. Out of scope by default

The following are outside the default architecture unless separately justified:

- controlled-access GDC data;
- authentication/token workflows for GDC;
- bulk raw BAM/FASTQ/WGS mirroring;
- rebuilding GDC production harmonization;
- generic agent frameworks;
- generic DAG/workflow engines;
- microservice decomposition;
- LLM-generated GDC queries;
- Jev-owned action selection;
- unvalidated model execution or model-created numerical evidence;
- researcher approval loops for autonomous runtime.

## 11. Researcher Lab

The optional Researcher Lab must use separate execution ownership such as:

```text
SYSTEM_AUTONOMOUS
RESEARCHER_RUN
```

Researcher runs may share immutable source caches and scientific engine code, but may not alter:

- autonomous Campaign selection;
- candidate admission;
- autonomous candidate queues;
- ActionPolicy;
- EvidenceStates;
- hypotheses;
- dossiers;
- future Campaign progression.

A researcher finding may influence future autonomous behavior only through a later explicit versioned scientific/code change outside runtime.
