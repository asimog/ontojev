# OntoJev Architecture

## 1. Purpose

OntoJev is an autonomous computational cancer target-discovery system.

Its scientific purpose is to combine validated cancer genomic measurements, established computational-genomics methods, multi-modal evidence integration, and selective Jev semantic judgment to identify target candidates that conventional independent rankings may under-prioritize.

OntoJev is not an alternative to GDC harmonization, statistical genomics, functional validation, or experimental biology.

It orchestrates those evidence layers while maintaining explicit scientific and execution boundaries.

---

# 2. Architectural principles

## 2.1 Measurement before interpretation

```text
GDC source
→ strict parser
→ independent reconciliation
→ validated measurement
→ scientific method
→ typed evidence
```

A deterministic result is not automatically a correct result.

Scientifically important measurements must be reconcilable against their authoritative source or an independent calculation.

Synthetic fixtures verify software behavior.

Frozen real-response reconciliation fixtures verify scientific measurement semantics.

---

## 2.2 Established methods before ad hoc methods

OntoJev follows this principle:

> Do not invent cancer-genomics methods when established GDAN/TCGA/NCI computational methods already address the scientific question.

Primary methodological and data authorities include:

- GDC documentation:
  https://github.com/NCI-GDC/gdc-docs
- GDC data model:
  https://github.com/NCI-GDC/gdcdatamodel2
- GDC production-workflow overview:
  https://github.com/NCI-GDC/gdc-workflow-overview
- GDC data transfer client:
  https://github.com/NCI-GDC/gdc-client
- NCI Genomic Data Analysis Network:
  https://www.cancer.gov/ccg/research/computational-genomics/genomic-data-analysis-network

Relevant public NCI-GDC workflow/tool repositories are retained locally as pinned upstream references when developing scientific methods.

They are not automatically installed into the OntoJev runtime.

---

## 2.3 Jev boundary

```text
raw genomics
        X
        │
        ▼
       Jev
```

Jev never performs:

- provider acquisition;
- parsing;
- mutation counting;
- normalization;
- statistical testing;
- pathway membership calculation;
- missingness inference;
- sample matching;
- action execution.

Correct flow:

```text
raw evidence
→ deterministic genomics/statistics
→ typed scientific evidence
→ bounded Jev projection
→ typed semantic judgment
```

The central control rule is:

> **Jev judges. Python decides. Python executes.**

---

## 2.4 Hypotheses are not evidence

```text
LLM hypothesis
→ NOT_EVIDENCE
→ Jev critique
→ registered deterministic test if available
→ new EvidenceState
```

Only registered deterministic scientific methods can create evidence.

---

# 3. Source architecture

## 3.1 GDC release context

OntoJev develops against the latest verified GDC documentation and data model.

Every campaign pins the exact source context it used:

```text
GDC release
GDC source identifiers
gdcdatamodel2 reference revision
workflow provenance
OntoJev code version
scientific method versions
policy versions
```

A historical campaign is never silently reinterpreted using a newer GDC release.

A new GDC release creates a new campaign/source context.

---

## 3.2 GDC acquisition

OntoJev uses two explicit acquisition boundaries.

### Analysis/API acquisition

Typed request builders and strict parsers may consume approved GDC endpoints such as:

```text
/genes

/gene_expression/*

/ssms
/ssm_occurrences

/cnvs
/cnv_occurrences

/segment_cnvs
/segment_cnv_occurrences

/scrna_seq/gene_expression

/analysis/*
```

An endpoint is admitted only for a defined scientific use case.

No LLM creates arbitrary GDC API queries.

### Open-file acquisition

When higher-level harmonized files are scientifically preferable:

```text
GDC file metadata
→ access=open verification
→ deterministic file selection
→ gdc-client
→ checksum verification
→ immutable artifact
→ strict domain parser
```

Controlled-access support is outside the current architecture.

No authentication token is required or accepted for the open-data runtime.

---

# 4. GDC workflow awareness

A value cannot be interpreted independently of how it was generated.

OntoJev therefore records enough workflow identity to prevent scientifically invalid comparisons.

Examples include:

### Mutation

Potential workflow/caller context includes:

```text
WXS / targeted sequencing
WGS
MuTect2
MuSE
VarScan
SomaticSniper historical output
current WGS callers
GDC aggregation / masking
```

### Expression

Current expression interpretation must distinguish:

```text
STAR-derived current GDC expression
raw counts
FPKM
FPKM-UQ
TPM
historical HTSeq-derived data
```

Historical `htseq-tool` remains a provenance/reference implementation, not the default current expression method.

### CNV

Potentially distinct workflows include:

```text
ASCAT
ABSOLUTE
DNAcopy
GATK4 CNV
```

They are not interchangeable by default.

### Other modalities

The architecture can represent validated:

```text
methylation
miRNA
RPPA/protein
fusion
structural variation
scRNA/snRNA
clinical/outcome context
```

Each requires its own source, workflow, QC, and scientific method contract.

---

# 5. Cohort architecture

Core scientific code is cancer-agnostic.

A `CohortSpec` defines the population.

A `ResearchSpec` defines the scientific run.

A validated campaign profile binds a cohort to the methods OntoJev is permitted to use.

Conceptually:

```text
CampaignProfile
├── CohortSpec
├── GDC source/release context
├── TestedUniverse
├── enabled modalities
├── scientific method profile
├── validation profile
├── registered actions
└── policy identities
```

TCGA-LUAD is the first validated profile.

It does not define the engine.

One scientifically coherent cohort is the normal campaign unit.

Pooling projects or cancers requires an explicit comparability contract.

---

# 6. Gene universe

Acquisition batching and the scientific universe are separate concepts.

```text
TestedUniverse
      │
      ├── AcquisitionShard 1
      ├── AcquisitionShard 2
      ├── AcquisitionShard 3
      └── ...
      │
      ▼
complete measurement table
      ↓
global scientific reduction
```

The default target-discovery universe is the full eligible release-bound protein-coding gene universe unless a campaign defines another scientifically justified universe.

Acquisition shards never become independent scientific universes.

Known cancer drivers may be used as post-selection validation controls.

They must not receive privileged selection treatment.

---

# 7. Computational-genomics lanes

Available lanes depend on cohort capability.

## 7.1 Mutation

Target mutation evidence may contain:

```text
unique affected cases
occurrence counts
variant classes
functional consequences
protein-position recurrence
hotspot/clustering evidence
caller/workflow provenance
case membership
background-adjusted driver evidence where valid
```

Raw mutation recurrence alone is descriptive.

Inferential driver claims require an explicit background model and multiple-testing contract.

---

## 7.2 Expression

Expression analysis follows:

```text
RNA source
→ case/sample/aliquot identity
→ workflow/unit validation
→ technical QC
→ batch/confounding analysis
→ deterministic expression features
```

Possible features include:

```text
central tendency
dispersion
extreme-tail structure
subgroups/clusters
differential effects under a declared comparison
```

A Tukey/IQR tail is a descriptive feature, not statistical significance.

---

## 7.3 CNV

CNV evidence remains caller/workflow-aware.

Potential evidence includes:

```text
gene-level copy number
segment state
focal/broad events
amplification
deletion
allele-specific copy number
LOH
purity/ploidy context
recurrent events
```

No CNV occurrence does not imply diploid/neutral.

---

## 7.4 Additional modalities

Future or cohort-dependent evidence may include:

```text
structural variation
fusion
methylation
miRNA
RPPA
scRNA/snRNA
```

Adding a modality requires:

```text
source contract
workflow contract
QC contract
scientific method
typed evidence result
validation
```

No generic plugin framework is required.

---

# 8. Statistical validity

OntoJev distinguishes descriptive and inferential evidence.

## Descriptive evidence

Examples:

```text
count
median
dispersion
tail structure
event category
hotspot descriptor
rank
```

These do not require artificial p-values.

## Inferential evidence

Claims involving:

```text
significance
association
enrichment
differential effect
driver evidence
survival relationship
```

must predeclare:

```text
population
null/background model
effect size
uncertainty
test statistic
multiple-testing family
correction
minimum N
method/version
limitations
```

Jev never supplies statistical significance.

---

# 9. Evidence levels

Target evidence is explicitly staged.

Conceptually:

```text
MEASURED
    ↓
DESCRIPTIVE_CANDIDATE
    ↓
STATISTICALLY_SUPPORTED
    ↓
INTERNALLY_REPLICATED
    ↓
EXTERNALLY_REPLICATED
    ↓
FUNCTIONALLY_SUPPORTED
```

Not every candidate will reach every level.

Jev cannot promote an evidence level.

---

# 10. Target discovery

Each validated modality may nominate candidates independently.

```text
mutation candidates
expression candidates
CNV candidates
other modality candidates
        ↓
deterministic candidate union
        ↓
canonical integrated target state
```

Missing modalities remain explicit.

They are not automatically disqualifying.

Cross-modal relationships are computed only where compatible population/sample contracts support them.

---

# 11. Deterministic baseline

Before Jev, OntoJev produces a conventional deterministic/statistical result.

```text
validated target evidence
        ↓
deterministic baseline
        ↓
rank / retain / drop / semantic-review
```

This baseline establishes what conventional computational genomics already concludes.

It also provides the comparator for measuring Jev's contribution.

---

# 12. Selective Jev architecture

Jev is applied only where semantic judgment adds information.

## Arm Jev

Optional per modality.

Question:

> Does this within-modality evidence contain an important structured pattern that conventional ranking underrepresents?

A modality does not need Arm Jev merely because another modality uses it.

## Wide Jev

Operates over the integrated target state.

Questions may concern:

```text
rank discordance
cross-modal coherence
cross-modal discordance
non-obvious evidence combinations
unresolved structure
value of deeper investigation
```

Python owns admission and ranking policy.

## Deep Jev

Operates during candidate investigation.

It judges:

```text
what remains uncertain
whether existing evidence is sufficient
whether another registered investigation has information value
```

Python chooses the action.

---

# 13. Autonomous candidate investigation

```text
Candidate
   ↓
EvidenceState E0
   ↓
Deep Jev
   ↓
Python ActionPolicy
   ↓
registered deterministic action
   ↓
EvidenceState E1
   ↓
Deep Jev
   ↓
repeat / hypothesis / complete / abstain
```

Actions are:

```text
registered
typed
bounded
versioned
scientifically specified
```

No alphabetical or hidden action selection.

No arbitrary model-created tools.

If the deterministic ActionPolicy cannot resolve the next step:

```text
ABSTAIN
```

---

# 14. Functional and external evidence

A genomic target candidate may later be supplemented by orthogonal evidence such as:

```text
DepMap CRISPR dependency
lineage-specific dependency
known cancer-gene context
targetability/druggability evidence
independent cohort support
```

These remain separate evidence axes.

For example:

```text
druggable
!=
cancer dependency

dependency
!=
safe therapeutic target

known cancer gene
!=
target in this cohort
```

Jev may judge the combined evidence.

It cannot manufacture functional evidence.

---

# 15. Stage 8 finalization

Every bounded candidate investigation ends in a reproducible target result.

```text
final evidence state
→ deterministic finalization
→ final target result
→ authoritative dossier
→ Jev-vs-no-Jev comparison
→ CANDIDATE_COMPLETE
```

The dossier states the actual evidence level and limitations.

It does not upgrade a computational discovery into therapeutic validation.

---

# 16. System-owned autonomous program

OntoJev's primary execution mode is independent of any researcher.

```text
AutonomousProgram
      ↓
bounded Campaign
      ↓
target discovery
      ↓
candidate investigations
      ↓
dossiers
      ↓
CAMPAIGN_COMPLETE
      ↓
CampaignSelectionPolicy
      ↓
next campaign / PROGRAM_IDLE
```

`CampaignSelectionPolicy` is:

```text
named
versioned
deterministic
testable
persistently attributable
```

It never relies on hidden ordering or free-form model choice.

---

# 17. GDC release monitoring

New GDC releases are a first-class autonomous trigger.

```text
GDC Release N
→ campaigns
→ immutable results

GDC Release N+1
→ new campaigns
→ deterministic comparison
```

Potential comparisons include:

```text
NEW_CANDIDATE
LOST_CANDIDATE
RANK_CHANGED
EVIDENCE_STRENGTHENED
EVIDENCE_WEAKENED
MODALITY_ADDED
SOURCE_CHANGED
METHOD_CHANGED
NOT_COMPARABLE
```

Source or method changes must not be misrepresented as biological changes.

---

# 18. Researcher Lab

The Researcher Lab is optional.

It reuses the same scientific engine in a separate execution context.

```text
SYSTEM_AUTONOMOUS
        X
        │
RESEARCHER_RUN
```

Researcher-run state cannot influence the autonomous program at runtime.

Separate state includes:

```text
ResearchSpec
candidate queue
evidence revisions
hypotheses
actions
events
dossiers
campaign completion
```

Immutable provider artifacts may be shared only where ownership and provenance remain exact.

Researcher findings can affect future autonomous behavior only through an explicit versioned scientific/code change outside runtime.

---

# 19. Product claim

OntoJev's target product description is:

> **OntoJev is an autonomous computational cancer target-discovery system that combines harmonized GDC evidence with established computational-genomics analysis patterns derived from NCI/GDAN practice, then uses Jev to identify non-obvious targets emerging from relationships among mutation, expression, copy-number, pathway and eventually functional-dependency evidence.**

The central research question is:

> **Can Jev operating over validated, GDAN-style computational-genomics evidence identify biologically plausible cancer target candidates that established single-method or single-modality rankings would under-prioritize?**

The scientific claim boundary remains:

```text
computationally discovered target candidate
!=
experimentally validated target
!=
therapeutically validated target
```
