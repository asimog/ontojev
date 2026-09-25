# OntoJev Data Strategy

> Status: target design and requirements, not a claim that every capability exists. For the inspected current implementation and remaining work, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Mutable versions remain in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## 1. Purpose

Current implementation supports bounded typed API acquisition and immutable source artifacts. The endpoint list below is a candidate capability list, not an implemented allowlist. A bounded cohort capability probe (status + one project record + one aggregate open-file facet request; no per-file listing) now exists; a selected-open-file `gdc-client` adapter, complete-universe shard lifecycle and full workflow/assay compatibility remain planned (P03–P06).

The existing upstream clones are source references, not installed runtime tools. Exact inspected SHAs are recorded in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); `.upstream/SOURCES.lock.json` remains the untracked local inventory.

The `/analysis/top_cases_counts_by_genes` bucket is not a distinct released-case measurement. Stage 4 uses a complete `/ssm_occurrences` scan; the older live path still requires correction. Preserve the frozen reconciliation corpus and never reinterpret bucket values as affected cases merely because the endpoint name suggests counts.

OntoJev aims for scientifically complete analysis without indiscriminate local mirroring of GDC.

The goal is:

> complete scientific coverage using the smallest authoritative data representation sufficient for the method.

## 2. Source priority

Preferred source order:

```text
1. indexed GDC Analysis/API result
2. bounded detailed API records
3. high-level open harmonized file
4. larger harmonized file when scientifically required
5. raw BAM / FASTQ / WGS only when no valid higher-level source answers the question
```

Raw sequencing acquisition is not the default architecture.

## 3. Access boundary

Current architecture uses open GDC data only.

```text
access=open
```

No controlled-access data.

No GDC credential/token runtime.

## 4. Core upstream authorities

Use:

- https://github.com/NCI-GDC/gdc-docs
- https://github.com/NCI-GDC/gdcdatamodel2
- https://github.com/NCI-GDC/gdc-workflow-overview
- https://github.com/NCI-GDC/gdc-client
- https://www.cancer.gov/ccg/research/computational-genomics/genomic-data-analysis-network

`gdcdatamodel2` is the code-level GDC data-model authority.

Do not substitute the legacy `gdcdatamodel`.

Current GDC documentation determines whether a public workflow repository is current or historical.

## 5. Upstream workspace

Maintain upstream source references in an untracked:

```text
.upstream/
```

workspace.

Record:

```text
URL
branch
resolved SHA
clone date
role
installation status
```

Possible roles:

```text
CURRENT_REFERENCE
HISTORICAL_REFERENCE
EXECUTABLE_TOOL
DOCUMENTATION_ONLY
```

Upstream repositories are references by default.

Only install tools that actually need execution.

Use isolated environments under:

```text
.upstream/envs/
```

Do not pollute the OntoJev runtime with every upstream workflow dependency.

## 6. API acquisition

Only admit endpoints with a concrete scientific consumer.

Potential endpoints include:

```text
/genes

/gene_expression/availability
/gene_expression/values
/gene_expression/gene_selection

/ssms
/ssm_occurrences

/cnvs
/cnv_occurrences

/segment_cnvs
/segment_cnv_occurrences

/scrna_seq/gene_expression

/analysis/top_cases_counts_by_genes
/analysis/top_mutated_genes_by_project
/analysis/top_mutated_cases_by_gene
/analysis/mutated_cases_count_by_project
/analysis/survival
```

Every admitted endpoint requires:

```text
scientific purpose
fixed request contract
strict parser
typed output
bounded acquisition
failure semantics
```

No arbitrary runtime URL construction.

No model-generated GDC queries.

## 7. Open-file acquisition

When file-level evidence is scientifically preferable:

```text
GDC metadata query
→ verify access=open
→ deterministic file selection
→ estimate file count/bytes
→ gdc-client
→ checksum verification
→ immutable source identity
→ strict parser
→ typed evidence
```

The system should prefer high-level harmonized products over rebuilding GDC production workflows.

Implemented now: a typed admission gate (`research/file_admission.py`) decides every candidate open-file product as ADMITTED / DEFERRED / REJECTED before any downloader could exist. No consumer method is declared today (`NAMED_FILE_CONSUMERS` is empty), so every candidate defers with `NO_NAMED_CONSUMER`; activation requires a named method consumer, the exact declared product, a complete open-access preflight manifest and a total below the 2 GiB multi-GB prohibition. No `gdc-client` integration, no token and no file format are implemented.

## 8. Data-volume planning

Before any download-heavy method is accepted, determine:

```text
scientific population
expected requests
expected file count
expected bytes
API alternative
higher-level-file alternative
reason file acquisition is required
Shard strategy
cache strategy
retention strategy
```

If projected automatic acquisition approaches multi-GB scale, redesign around indexed or higher-level data before proceeding.

Do not reduce the scientific Universe merely to reduce bytes.

## 9. Universe and Shards

The scientific Universe is independent of operational acquisition.

```text
complete Universe
→ bounded Shards
→ all required Shards terminal
→ global scientific calculation
```

Persist or derive:

```text
Universe identity/hash
required Shards
completed Shards
failed Shards
source hashes
```

Never use Shard-local top-N selection as a substitute for global reduction unless that exact procedure is the declared scientific method.

Implemented now: the systematic universe enumerates every reported protein-coding gene to a stable provider total under the complete-universe method and a declared defect guard ceiling (a sanity check, never a sampler); gene pages, occurrence-scan pages and expression gene batches register in an operational shard ledger, a reduction finalizes only when every required shard is terminal, and historical prefix-universe results remain readable and labelled.

## 10. Streaming

Streaming accumulation is allowed when mathematically equivalent to the complete-data calculation.

A global result may finalize only after the method's required population is complete.

Streaming should be preferred over retaining huge intermediate matrices when the scientific method allows sufficient-statistic accumulation.

## 11. Cache and retention

Retain:

```text
source identifier
checksum/hash
GDC release
workflow provenance
derived typed evidence
```

Reuse verified immutable cached artifacts where useful.

Do not permanently retain dispensable bulk files when deterministic reacquisition is adequate.

## 12. Workflow provenance

Where scientifically material, retain:

```text
experimental strategy
workflow family
caller / quantification family
reference/annotation context
current/historical status
data product type
```

Examples of distinctions that may matter:

```text
WXS vs WGS mutation evidence

current vs historical mutation workflows

STAR expression vs historical HTSeq

ASCAT vs ABSOLUTE vs DNAcopy vs GATK4 CNV

different methylation platforms/workflows
```

Do not build a large provenance ontology without a scientific consumer.

Implemented now: `ScientificSource` carries optional `workflow_family`, `caller_family`, `strategy` and `annotation_context` provenance fields; expression workflow coverage is measured with one aggregate open-file facet request per cohort (per-workflow file counts recorded, `_missing` coverage recorded as a limitation and the single-family source annotation withheld, never a silent full-coverage claim); and the mutation occurrence-scan document pins its requested field set and field-set hash. Cross-workflow comparison remains forbidden by default (`Compatibility.UNVERIFIED`).

## 13. Testing and reconciliation

Selection-critical scientific measurements require independent validation where feasible.

Prioritize:

```text
scientific reconciliation
frozen real-response fixtures
contract tests
replay tests
integration tests
bounded live acceptance
```

Synthetic fixtures verify plumbing.

They are not sufficient proof of real GDC semantics.
