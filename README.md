# OntoJev

OntoJev is an autonomous computational cancer target-discovery system.

It combines harmonized GDC evidence with established NCI/GDAN computational-genomics methods, then uses Jev selectively to identify biologically plausible target candidates whose importance may emerge from non-obvious, discordant, multi-modal, or under-ranked genomic patterns.

## Current implementation

OntoJev now has one canonical autonomous Campaign spine, implemented, production-wired and offline-verified: typed cohort/profile/capability validation → complete-universe mutation discovery → independent expression discovery → complete CNV case-shard scan and terminal merge → deterministic modality union (`MUTATION_EXPRESSION_CNV_UNION_V1`) → one canonical `StatisticalState` per union member → the `pre-wide-policy-v1` measured-evidence boundary → Wide Jev → Python admission → an autonomous candidate queue that drives every promoted Candidate through Deep Jev, registered deterministic follow-ups, immutable evidence revisions, Stage 8, dossier and the deterministic no-Jev comparison. No operator candidate flag exists on that path.

The durable `program-loop-v2` worker observes the GDC release once per cycle, selects an eligible Campaign by the declared `campaign-selection-v2` policy, refuses to redispatch a completed Campaign whose profile/release/method identity is unchanged, applies bounded exponential retry to failures, holds the research lock only around each cycle, and heartbeats the canonical package version. Storage is SQLite schema 7 with sequential DDL migrations and a read-only `doctor`; dependencies are locked in `uv.lock`; strict mypy covers 85 production modules; CI verifies the production-built frontend and browser path.

Live-verified to date: the individual mutation, expression, CNV-shard, reconciliation and Jev question-set captures recorded in the implementation plan. **Not yet scientifically validated:** `LUAD_CAMPAIGN_V1` remains `EXPERIMENTAL`; a full live Campaign with real Wide/Deep Jev and dossier review has not completed, and readiness is not implied by green software tests. `GDC_FAST_SEARCH` remains available only as the explicitly labelled researcher/comparator path.

## Running it

```text
python -m cancerjev probe --live                 # bounded anonymous GDC contract capture
python -m cancerjev capability                   # typed cohort capability probe
python -m cancerjev run --live [--jev]           # researcher/comparator bounded sweep
python -m cancerjev program                      # one durable autonomous program cycle
python -m cancerjev worker --live                # long-running autonomous worker loop
python -m cancerjev doctor                       # read-only storage integrity report
```

Offline verification: `python -m ruff check cancerjev apps tests`, `python -m mypy`, `python -m pytest`.
Frontend: `cd apps/web && npm ci && npm run typecheck && npm run build`.
Deployment, health/readiness, backup/restore and the localhost-only API posture are documented in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Research question

> Can Jev operating over validated, GDAN-style computational-genomics evidence identify biologically plausible cancer target candidates that established single-method or single-modality rankings would under-prioritize?

## Claim boundary

OntoJev discovers and investigates **computational target candidates**.

```text
computational target candidate
!= experimentally validated target
!= therapeutically validated target
```

Functional, therapeutic, safety, and clinical validation require additional evidence outside the computational discovery result. No functional or external axis is adopted today: every evaluated source (DepMap CRISPR, Sanger CGC, targetability resources, independent-cohort replication) is deferred with its access/licensing reason in [docs/FUNCTIONAL_SOURCES.md](docs/FUNCTIONAL_SOURCES.md), and `FUNCTIONALLY_SUPPORTED` remains unattainable without an adopted contract.

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
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — current status plus the historical bounded implementation units.
- [`docs/TYPESAFE_DECISIONS.md`](docs/TYPESAFE_DECISIONS.md) — TypeSafe/Jev capability posture, including deferred Arm Jev.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — supported operation: processes, data directory, health, backup/restore.
- [`docs/REPOSITORY_FACTS.md`](docs/REPOSITORY_FACTS.md) — generated schema, policy, projection and action identities.

Keep these documents canonical and compact. Git history is the archive.
