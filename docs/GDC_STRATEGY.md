# GDC strategy and reality matrix

Baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`; investigated 2026-09-24 UTC.
ADMIT NOW means suitable for the proposed implementation phase **after its acceptance gates**,
not already runtime-allowlisted. HTTP 200 is not scientific admission.
[Capture register](GDC_DISCOVERY_CAPTURES.md) preserves requests, hashes and measurements.

IMPLEMENTED Stage 3 (2026-09-25): `research/acquisition.py` separates existing cohort, mutation-count
and expression calls from selection policy. Builders, fields, parsers, request order, pagination,
batch semantics and caps are unchanged. No new endpoint, live probe or capture was admitted in that
stage; the campaign below remains historical evidence. See [Stage 3](STAGE_03_HANDOFF.md).

## Investigation and reproducibility

69 anonymous sequential attempts, 6,093,958 consumed response-body bytes, all terminal HTTP 200.
No credentials, redirects, retries or files downloaded. Fixed api.gdc.cancer.gov; 30-second socket
timeout; campaign 150 attempts/64 MiB; session 30/8 MiB; response 5 MiB; explicit genes 100/cases 250;
ten pages per logical query. Shared on-disk ledger spans sessions. Failed/incomplete bytes would count.
This is consumed-body accounting, not network/TLS billing.

The temporary isolated harness lives outside production run data:
`C:/Users/Rahul Khatri/AppData/Local/Temp/ontojev-architecture-20260924/`.
It was used uniformly so runtime-supported and research-only endpoints shared one campaign ledger;
runtime allowlists and globals were not changed. Existing parsers were reused offline against all ten
mutation-count batches and twelve expression-value captures. Captures are local audit evidence, not
committed fixtures. Required fixtures below must be retained under a future separately scoped change.

Official sources: [API data analysis](https://docs.gdc.cancer.gov/API/Users_Guide/Data_Analysis/),
[search/retrieval](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/),
[expression pipeline](https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/Expression_mRNA_Pipeline/),
[CNV pipeline](https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/CNV_Pipeline/).
Endpoint mappings were captured before scientific probes. Documentation supports endpoint intent;
captures establish deployed fields; scientific interpretation still needs a defensible unit/population.

## Reality matrix

Capture numbers below refer to the register. Runtime means current allowlist, not future approval.

| Family / operation | Official support; live evidence | Entity, IDs and filters | Population, absence and joins | Shape/workflow/completeness | Cost and decision |
|---|---|---|---|---|---|
| Status/projects | API; 001/002/012 | release; exact project_id=TCGA-LUAD | 585 cases, not an assay denominator | DR46.0, API8.5.0, project inventory | Small; ADMIT NOW; runtime current |
| Cases | mapping 003; 013/026/027/024/069 | case_id ordered; project.project_id | 585 unique sorted cases; case may have multiple tumor/normal samples | Three pages 250/250/85; sample/aliquot links optional | ~100 KiB basic frame; ADMIT NOW; runtime current |
| Genes / broad universe | mapping 005; 014/028–036 | gene_id, symbol, biotype; protein_coding; gene_id ascending | 1,000 unique sorted of reported 19,843; lexicographic subset bias | Ten pages 100; release/filter/offset manifest required | 106,739 B /12.801 s; ADMIT NOW bounded slice; enumeration builder NEW |
| Top mutated genes | 022; official analysis endpoint | project filter; ranked gene IDs and provider score | Mutation-selected universe, score is not measurement | Ranking metadata only | ADMIT NOW for historical comparison, not broad-universe authority; runtime current |
| Mutation case counts | 037–046; existing parser accepts all complete | gene_ids100; project buckets | 1,000 requested LUAD buckets; explicit values preserved; missing bucket not wild type | Aggregation completeness checked; all-project response, extract exact LUAD | 2,523,861 B /28.419 s for1,000; ADMIT NOW counts, not recurrence rates; runtime current |
| SSM coverage | 023 | per-project case_with_ssm | Indexed SSM-data coverage, not per-gene callable-negative set | Separate from mutation numerator | ADMIT NOW context only; runtime current |
| SSMs | mapping 006; 015 | variant ID, GRCh38 coordinates, alleles; occurrence project filter | Variant != case; transcript rows are not independent mutations | Small partial search, explicit paging required | LATER variant-enrichment; NOT ADMITTED as complete mutation burden |
| SSM occurrences | mapping 007; 016/052 | case + ssm IDs, transcript gene IDs; TP53/project filter | 299 occurrences reported; multiple callers same sample observed; dedup by case/gene for case counts | Leaf observation fields work; broad case.observation field gave warning | LATER detailed lane; sample ID present in example, negative callability absent |
| Gene CNVs | mapping 008; 017 | cnv_id + consequence.gene.gene_id, project filter | TP53 has 3 indexed category entities; not 3 cases | GRCh38, gene_level_cn; categories Loss/Gain/Amplification | ADMIT NOW identity/category context for narrow lane; runtime NEW |
| CNV occurrences | mapping 009; 018/050/051/055/067/068 | case + cnv + gene IDs, source file, caller | TP53 264 distinct occurrences/cases: 236 Loss, 25 Gain, 3 Amplification; no negative denominator | Complete two-page TP53 query; ASCAT3 source file confirmed; requested tumor sample ID absent | ADMIT NOW bounded positive occurrence descriptors; NEW parser/builder required |
| CNV 100 workload | 067 | first 100 universe genes + LUAD | 21,032 occurrence total; two sample hits only | Full scan would need 85 pages 250, exceeds 10; facets count occurrences, not assured unique cases | REJECT full broad occurrence scan; reduce first; full 1,000 cost UNMEASURED |
| Segment CNVs | mapping 010; 019 | segment ID, chromosome, start/end/length | 30,681 LUAD entities; no direct gene join admitted | Position/category response; projection to genes needs overlap/build policy | LATER; no segment discovery lane now |
| Segment occurrences | mapping 011; 020/053 | case/segment/source file IDs, copy number | 32,385 reported; only 2 inspected; no complete cohort distribution | Leaf fields work; missing sample mapping | LATER; full scan outside current page budget |
| Expression availability | 047 | explicit case/gene IDs | first 250 cases:221 available/29 unavailable; first 100 genes:91 available/9 unavailable | Independent case/gene availability is not guarantee every matrix cell exists | ADMIT NOW; runtime current |
| Expression values | 049/056–066 | gene row and case column labels; UQFPKM | 1,000x250 requested ->946 gene rows x221 case columns across batches;100x585 ->91x518 | Twelve captures accepted existing strict TSV parser; missing rows/columns preserved; sample mapping unresolved | ADMIT NOW case-labelled descriptive summaries; runtime current |
| Expression selection | 048 | explicit100 genes/250 cases, selection_size100 | Only that requested population; not full LUAD | Provider medians/stddev retained, estimator details not independently established | ADMIT NOW metadata only; no averaging batch medians/SDs |
| Open expression file metadata | mapping 004; 021 | file/case/sample/aliquot IDs; access=open | 601 files reported, not 601 independent cases | Five sampled STAR - Counts files, not complete workflow census | ADMIT NOW bounded provenance context; cannot establish matrix-cell sample linkage |
| Clinical metadata | 024/069 | case, demographic, diagnoses, samples | Null/missing follow-up; multiple samples/diagnoses possible | Two-case sample, no definitive diagnosis selection contract | LATER; preserve raw context only, no clinical scoring |
| Survival analysis | 054, documented GET | filters array with cases.project.project_id | 509 donor records returned for LUAD, versus585 inventory; exclusion/censoring audit unresolved | results/donors with time,censored,ID; nonempty unlike 2026-09-22 probes | LATER; endpoint works, inferential survival NOT ADMITTED |
| scRNA | official API; metadata025 | case OR HDF5 file ID; documented<=10 genes | LUAD open scRNA metadata query returned 0; no applicable source selected | Cell-level units and normalization need separate contract | LATER; live value capability UNVERIFIED |
| Downloads, arbitrary query, controlled evidence | Outside approved runtime | /data, manifest, slicing, auth | Not in scope | No probe or file acquisition | REJECT / DO NOT BUILD in this phase |

The five-category CNV field is not reliably five mutually exclusive biological states in these
responses: cohort facets contained lower-case loss/gain/amplification/homozygous deletion and no
neutral bucket. Preserve case-sensitive raw labels; normalize only through an explicit parser table.
Loss is not proof of heterozygous deletion. Absence is not proof of neutral/diploid.

## Measured versus extrapolated workloads

| Workload | Requests | Bytes | Summed request wall time | Scope |
|---|---:|---:|---:|---|
| Gene inventory 1,000 | 10 | 106,739 | 12.801 s | Measured, sorted protein-coding prefix |
| Mutation counts 100 | 1 | 246,042 | 2.771 s | Measured first batch, all-project response |
| Mutation counts 1,000 | 10 | 2,523,861 | 28.419 s | Measured, LUAD extracted |
| Expression 100 x250 | 1 | 176,337 | 2.246 s | Measured;91x221 returned |
| Expression 1,000 x250 | 10 | 1,834,776 | 25.203 s | Measured;946x221 returned |
| Expression 100 x585 | 3 | 414,305 | 6.478 s | Measured;91x518 returned |
| Expression 1,000 x585 | 30 | ~4.14 MB | ~64.8 s | ESTIMATE by 10×100-gene full-frame workload; not measured |
| Full CNV 100 occurrences | >=85 pages 250 | Unknown | Unknown | Page estimate from 21,032 total; not acquired |

The 1,000x585 expression estimate is a feasibility scenario, not an admitted query plan: splitting
queries must not evade the ten-page logical-query budget. A design must declare independently bounded
gene batches/populations and shared campaign reservations, or use richer evidence only for survivors.
Neither latency nor body size estimates are provider guarantees.

## Admitted field-to-result trace

Proposed parser names describe required functions, not implemented symbols. Existing parser symbols
are named explicitly. Every result also binds response/request hashes, release, method and population.

| Result fields | Endpoint and provider field | Parser/interpretation | Deterministic method / typed result |
|---|---|---|---|
| cohort/project, eligible inventory count | projects.project_id, summary.case_count | existing parse_projects; count not assay eligibility | PopulationFrame inventory |
| examined IDs / membership / sample context | cases.case_id, project.project_id; samples IDs/types/aliquots | existing parse_cases for case frame; NEW sample-link parser if used | unique sorted case frame; sample links remain multivalued |
| gene identity/universe | genes.gene_id,symbol,biotype; pagination.total | existing parse_genes + NEW paginated-universe envelope validation | EntityRef/TestedUniverse, explicit bounded subset |
| mutation affected cases | aggregations.projects.buckets[].genes.my_genes.gene_id.buckets[].doc_count | existing parse_gene_case_counts; retain complete flag | MUTATION_AFFECTED_CASE_COUNT_V1 -> ObservedCount or unavailable |
| SSM coverage | project case_summary.case_with_ssm.doc_count | existing parse_mutated_cases_count | PROJECT_SSM_COVERAGE_V1, no recurrence denominator |
| assay availability | cases/genes.details[].has_gene_expression_values | existing parse_expression_availability; requested membership checks | Coverage, independent axis flags |
| expression values/missing IDs | values TSV header case IDs and gene_id rows | existing parse_expression_values; finite nonnegative UQFPKM; label joins | EXPRESSION_LOG2_SUMMARY_V1 on log2(x+1), explicit n and missingness |
| provider selection summaries | gene_selection[].log2_uqfpkm_median/stddev | existing parse_gene_selection | EXPRESSION_PROVIDER_SUMMARY_V1 metadata, unavailable for multi-batch cohort summary |
| file/workflow context | files.access, analysis.workflow_type, cases/samples/aliquots | existing parse_files_provenance for sampled context; NEW link-preserving parser for matching | Provenance only; no inferred cell-level workflow |
| CNV category evidence | cnv_occurrence_id,case.case_id,cnv.cnv_id,cnv.consequence[].gene.gene_id,cnv.cnv_change/_5_category | NEW strict occurrence parser, required IDs/category; dedup and exact filter membership | CNV_INDEXED_POSITIVE_CASES_V1 proposed: unique cases per category over complete query |
| CNV contextual values | case.observation[].copy_number,src_file_id,variant_calling.variant_caller,sample_ploidy_integer | NEW optional-value variants; missing != invalid; sample UUID may be absent | ProviderObservation, not cross-caller numerical effect |
| quality/completeness | pagination count,total,from; warnings; transport terminal status; missing sets | shared validated envelope + lane-specific completion checks | Quality/Coverage; warnings about requested scientific fields prevent admission |
| derived extremes | parsed expression values and frame/universe above | no new provider field | proposed EXPRESSION_WITHIN_GENE_EXTREME_V1 in roadmap; descriptive only |

Scientific annotations such as dependency, druggability, clinical benefit, mutation-expression
coherence or CNV-expression causation receive no field in the admitted measured contract.

## Joins and denominators

Case/gene ID joins between indexed observations are feasible for descriptive presence intersection.
They do not establish matched assays. CNV source-file lookup returned both a tumor and a blood-normal
sample; the expression API supplies case columns without the chosen sample/aliquot. SSM observations
can repeat across callers and transcripts. Never count these as independent cases or choose the first
sample/file. Exact duplicate records may deduplicate by declared keys; inconsistent duplicates fail
or remain conflicts.

Eligible inventory, examined cases, available assays, returned columns and finite values remain
separate. Mutation-negative and CNV-neutral sets are not established. Mutation-expression and
CNV-expression association actions are INELIGIBLE until exact sample selection, negative/reference
semantics and common analyzable population are independently validated.

## Required future fixtures

Retain bounded redacted-free public captures with request specifications and hashes for: sorted
universe paging/duplicates/changed totals; explicit mutation zero versus absent bucket and truncated
aggregation; expression omitted genes/cases across batches; CNV Loss in five-category field, mixed
callers, duplicate/conflicting calls and missing sample UUID; source file with tumor+normal samples;
nonempty survival with missing follow-up/censoring cases. Add synthetic malformed variants separately
labelled SYNTHETIC. No fixture/test was changed in this pass.
