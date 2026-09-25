# OntoJev

OntoJev is an autonomous computational cancer target-discovery system.

It combines harmonized GDC evidence with established NCI/GDAN computational-genomics methods, then uses Jev selectively to identify biologically plausible target candidates whose importance may emerge from non-obvious, discordant, multi-modal, or under-ranked genomic patterns.

## Current implementation

At the inspected HEAD, OntoJev has typed GDC acquisition, bounded descriptive discovery, Wide/Deep Jev, Python policies, immutable candidate evidence revisions, hypothesis critique, and Stage 8 dossiers with no-Jev comparisons. Systematic complete-universe discovery (`GENE_ID_ASC_INDEXED_COMPLETE_V1`, declared defect guard, operational shard ledger, terminal gate) is the canonical path; the older provider-ranked `GDC_FAST_SEARCH` live lane is transitional/compatibility behavior retained as a labelled comparator, not the target architecture. Mutation and expression run over the complete release-bound universe with declared RETAIN/DROP/JEV_REVIEW dispositions and independent nomination; CNV is being moved to an independent case-sharded project scan (P09), and integrated states currently cover mutation survivors only. Historical prefix-universe results remain readable and labelled.

Independent modality union, scientific readiness gates, selected-file acquisition and continuous multi-Campaign autonomy are planned. The older provider-ranked live mutation path still needs the measurement correction described in P01. The target flow below must not be read as a list of completed features.

See the [saved implementation plan](docs/IMPLEMENTATION_PLAN.md) for code evidence, pinned upstream references, execution order and acceptance gates. [Repository facts](docs/REPOSITORY_FACTS.md) owns mutable version/action identities.

## Research question

> Can Jev operating over validated, GDAN-style computational-genomics evidence identify biologically plausible cancer target candidates that established single-method or single-modality rankings would under-prioritize?

## Claim boundary

OntoJev discovers and investigates **computational target candidates**.

```text
computational target candidate
!= experimentally validated target
!= therapeutically validated target
```

Functional, therapeutic, safety, and clinical validation require additional evidence outside the computational discovery result.

## Target architecture

```text
GDC release/source context
→ CohortSpec / ResearchSpec / CampaignProfile
→ cohort capability discovery
→ complete scientific gene Universe
→ deterministic computational genomics
→ deterministic/statistical evidence
→ optional Arm Jev
→ deterministic candidate union
→ StatisticalState
→ Wide Jev
→ Python admission
→ Candidate
→ EvidenceState
→ Deep Jev
→ Python ActionPolicy / next-move policy
→ deterministic follow-up or bounded hypotheses + Jev critique
→ evidence revision
→ Stage 8
→ FinalCandidateResult
→ dossier
→ Jev-vs-no-Jev comparison
→ candidate complete
→ campaign complete
→ CampaignSelectionPolicy
→ next campaign or idle
```

The central control rule is:

> **Jev judges. Python decides. Python executes.**

## Target scientific operating model

OntoJev separates six scales:

1. **Program** — the long-running system-owned autonomous research program.
2. **Campaign** — one coherent cohort + one pinned GDC release/source context + one versioned method profile.
3. **Universe** — every scientifically eligible gene for the Campaign.
4. **Shard** — an operational subset used only for bounded acquisition or computation.
5. **Target state** — one integrated `StatisticalState` evaluated by Wide Jev.
6. **Investigation** — one admitted Candidate with its own bounded immutable `EvidenceState` chain.

Operational batching must never redefine the scientific population.

## Scientific data model

OntoJev uses:

- typed GDC API/analysis endpoints where they answer the scientific question directly;
- selected open harmonized GDC files via `gdc-client` where file-level data are preferable;
- current GDC workflow documentation to interpret how measurements were produced;
- `gdcdatamodel2` as the code-level GDC data-model authority;
- established GDAN/TCGA/NCI computational methods before ad hoc alternatives.

Raw BAM/FASTQ/WGS acquisition is not the default. Scientific completeness does not require mirroring GDC locally.

## Jev roles

### Arm Jev

Optional, per modality, and only for `JEV_REVIEW` cases where deterministic/statistical analysis leaves a genuine semantic question.

### Wide Jev

The principal integrated semantic layer over canonical `StatisticalState`.

### Deep Jev

The candidate-investigation semantic layer over immutable `EvidenceState` revisions.

### Hypothesis Jev

Critiques bounded LLM-generated hypotheses. Hypotheses are never evidence.

## Planned evidence levels

```text
MEASURED
→ DESCRIPTIVE_CANDIDATE
→ STATISTICALLY_SUPPORTED
→ INTERNALLY_REPLICATED
→ EXTERNALLY_REPLICATED
→ FUNCTIONALLY_SUPPORTED
```

Jev may affect prioritization. It may never promote scientific evidence level.

## Campaigns

TCGA-LUAD is the first intended validation profile. The current LUAD ResearchSpec does not establish genome-wide discovery or autonomous scientific readiness.

Core scientific code must remain cancer-agnostic. Cross-cancer pooling requires an explicit comparability contract.

## Documentation

- [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md) — product definition, scope and claim boundaries.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system and scientific architecture.
- [`docs/SCIENTIFIC_INVARIANTS.md`](docs/SCIENTIFIC_INVARIANTS.md) — hard scientific and control rules.
- [`docs/DATA_STRATEGY.md`](docs/DATA_STRATEGY.md) — GDC source, sharding, acquisition and provenance rules.
- [`docs/JEV_DESIGN.md`](docs/JEV_DESIGN.md) — Arm, Wide, Deep and hypothesis Jev responsibilities.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — inspected current state and bounded remaining implementation units.
- [`docs/REPOSITORY_FACTS.md`](docs/REPOSITORY_FACTS.md) — generated schema, policy, projection and action identities.

Keep these documents canonical and compact. Git history is the archive.
