# OntoJev

OntoJev is an autonomous computational cancer target-discovery system.

It combines harmonized GDC evidence with established NCI/GDAN computational-genomics methods, then uses Jev selectively to identify biologically plausible target candidates whose importance may emerge from non-obvious, discordant, multi-modal, or under-ranked genomic patterns.

```text
GDC
→ validated measurements
→ computational genomics
→ deterministic/statistical evidence
→ integrated target state
→ deterministic baseline
→ selective Jev
→ target candidates
→ autonomous investigation
→ new deterministic evidence
→ final target dossier
```

## Scientific model

OntoJev separates measurement, computation, semantic judgment, and execution.

```text
raw GDC evidence
→ strict parsing
→ external reconciliation
→ validated measurements
→ computational genomics
→ typed scientific evidence
→ Jev
```

Core rules:

- Raw genomics never goes directly to Jev.
- Deterministic code owns measurements, statistics, eligibility, and evidence creation.
- Jev provides semantic judgment over structured evidence.
- Python owns candidate selection, registered actions, iteration, stopping, and campaign progression.
- LLM-generated hypotheses are explicitly not evidence.
- Missing data is not negative evidence.
- Computational target discovery does not equal experimental or therapeutic validation.

## GDC and GDAN

GDC is OntoJev's primary harmonized cancer-data source.

OntoJev uses:

- GDC analysis and search APIs for indexed evidence;
- open harmonized GDC files through `gdc-client` where file-level data are scientifically preferable;
- current GDC workflow and bioinformatics documentation to interpret how measurements were produced.

Primary upstream references:

- https://github.com/NCI-GDC/gdc-docs
- https://github.com/NCI-GDC/gdcdatamodel2
- https://github.com/NCI-GDC/gdc-workflow-overview
- https://github.com/NCI-GDC/gdc-client

Upstream clones are pinned in the untracked `.upstream/` workspace with an exact-SHA inventory and current/historical classification (`.upstream/SOURCES.lock.json`).

`gdcdatamodel2` is the data-model implementation authority.

Established NCI/GDAN/TCGA computational methods are preferred over ad hoc bioinformatics methods:

- https://www.cancer.gov/ccg/research/computational-genomics/genomic-data-analysis-network

Each campaign records the GDC release, data sources, workflow provenance, scientific methods, and code/policy versions it actually used.

## Target-discovery architecture

OntoJev is designed around modular cancer cohorts and scientific capabilities rather than a lung-specific pipeline.

```text
Cancer cohort
     ↓
cohort capability profile
     ↓
tested gene universe
     ↓
┌────────────┬────────────┬────────────┐
│ Mutation   │ Expression │ CNV / SV   │
└────────────┴────────────┴────────────┘
     ↓
additional supported modalities
     ↓
validated computational-genomics evidence
     ↓
pathway / multi-omic integration
     ↓
deterministic baseline
     ↓
selective Jev review
     ↓
candidate targets
     ↓
Deep Jev + Python ActionPolicy
     ↓
registered deterministic follow-up
     ↓
evidence revision
     ↓
final target dossier
```

Mutation, expression, CNV, methylation, miRNA, protein, fusion, structural-variant, and single-cell evidence are enabled only when the selected cohort and validated scientific methods support them.

## Cohorts

The engine is cancer-agnostic.

TCGA-LUAD is the first validated campaign profile, not an architectural restriction.

A campaign binds a cohort to:

- a GDC release;
- an eligible gene universe;
- available modalities;
- validated scientific methods;
- registered follow-up actions;
- validation and stopping policies.

Cross-cancer or pooled analysis requires an explicit comparability contract.

## Autonomy

OntoJev's primary mode is a system-owned autonomous research program made of bounded, reproducible campaigns.

```text
Autonomous Program
→ Campaign
→ target discovery
→ candidate investigation
→ dossiers
→ Campaign Complete
→ versioned CampaignSelectionPolicy
→ next campaign or idle
```

Campaign progression is controlled by explicit deterministic Python policy, never by hidden ordering or free-form model choice.

An optional Researcher Lab may run separate researcher-defined investigations using the same scientific engine. Researcher-run state cannot affect the system-owned autonomous program at runtime.

## Research question

> Can Jev operating over validated, GDAN-style computational-genomics evidence identify biologically plausible cancer target candidates that established single-method or single-modality rankings would under-prioritize?

## Claim boundary

OntoJev discovers and investigates **computational target candidates**.

Functional, therapeutic, safety, and clinical validation require additional evidence outside the computational discovery result.
