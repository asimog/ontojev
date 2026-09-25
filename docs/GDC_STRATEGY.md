# GDC strategy and reality matrix

Status legend: rows describing the current runtime allowlist/parsers are IMPLEMENTED; ADMIT NOW /
LATER / REJECT are design verdicts for future separately authorized work (PLANNED or deferred, not
current runtime); capture measurements are historical evidence that this environment did not
re-run (UNVERIFIED here).
Investigated 2026-09-24; current after the Stage 4-8 implementations (2026-09-25). ADMIT NOW means
suitable for a proposed future implementation phase **after its acceptance gates**, not already
runtime-allowlisted. HTTP 200 is not scientific admission. The design-time capture campaign and
its ledger are archived in git history; the workload table below retains the measured envelopes.

IMPLEMENTED runtime endpoints are: `/status`, `/projects`, `/cases`, `/genes`,
`/analysis/top_mutated_genes_by_project`, `/analysis/top_cases_counts_by_genes`,
`/analysis/mutated_cases_count_by_project` (unfiltered only), `/files` (open metadata only),
`/gene_expression/{availability,gene_selection,values}` and `/cnv_occurrences`, plus per-endpoint
`_mapping` used for contract verification only. SSM/SSM-occurrence, gene/segment CNV, survival and
scRNA endpoints are **not** allowlisted or implemented. `research/acquisition.py` separates
existing cohort, mutation-count and expression calls from selection policy; builders, fields,
parsers, request order, pagination, batch semantics and caps are unchanged. No new endpoint was
admitted by the Stage 3 cutover. Stage 4 reuses the same allowlist for systematic discovery:
`/genes` gains a **fixed** universe-enumeration builder (`genes_universe_request`: protein_coding
filter, `gene_id:asc`, offset/size only, page ≤10 per `genes:universe` query id, 100/page) with a
strict page parser; `/analysis/top_cases_counts_by_genes` gains deterministic ≤100-gene batch
requests (project SSM coverage acquired once). Live contract reverified 2026-09-25: pagination
`{count,total,size,from,pages}`, protein-coding total 19,843, aggregation shape and explicit-zero
vs absent-bucket behavior match the retained captures. Stage 6 adds only the fixed
project-and-single-gene `/cnv_occurrences` builder for Stage 4 survivors, with strict 250-row
pages and a ten-page per-gene cap.

## Investigation and reproducibility

The retained anonymous campaign made 69 sequential attempts and consumed 6,093,958 response-body
bytes, all terminal HTTP 200. No credentials, redirects, retries or downloaded files. Fixed
`api.gdc.cancer.gov`; 30-second socket timeout; campaign 150 attempts/64 MiB; session 30/8 MiB;
response 5 MiB; explicit genes 100/cases 250; ten pages per logical query. The on-disk ledger
spans sessions; failed/incomplete bytes would count. This is consumed-body accounting, not
network/TLS billing.

The temporary isolated harness used for that campaign lives outside production run data and
reused the runtime parsers offline. Captures are local audit evidence, not committed fixtures.
Required fixtures below must be retained under a future separately scoped change. Campaign
numbers are historical evidence; this environment did not re-run them.

Official sources: [API data analysis](https://docs.gdc.cancer.gov/API/Users_Guide/Data_Analysis/),
[search/retrieval](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/),
[expression pipeline](https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/Expression_mRNA_Pipeline/),
[CNV pipeline](https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/CNV_Pipeline/). Endpoint
mappings were captured before scientific probes. Documentation supports endpoint intent; captures
establish deployed fields; scientific interpretation still needs a defensible unit/population.

## Reality matrix

Capture numbers refer to the register. Runtime means current allowlist, not future approval.

| Family / operation | Official support; live evidence | Entity, IDs and filters | Population, absence and joins | Shape/workflow/completeness | Cost and decision |
|---|---|---|---|---|---|
| Status/projects | API; 001/002/012 | release; exact `project_id=TCGA-LUAD` | 585 cases, not an assay denominator | DR46.0, API8.5.0, project inventory | Small; ADMIT NOW; runtime current |
| Cases | mapping 003; 013/026/027/024/069 | `case_id` ordered; `project.project_id` | 585 unique sorted cases; a case may have multiple tumor/normal samples | Three pages 250/250/85; sample/aliquot links optional | ~100 KiB basic frame; ADMIT NOW; runtime current |
| Genes / broad universe | mapping 005; 014/028–036 | `gene_id`, symbol, biotype; protein_coding; `gene_id` ascending | 1,000 unique sorted of reported 19,843; lexicographic subset bias | Ten pages of 100; release/filter/offset manifest required | 106,739 B / 12.801 s; ADMIT NOW bounded slice; enumeration builder NEW |
| Top mutated genes | 022; official analysis endpoint | project filter; ranked gene IDs and provider score | Mutation-selected universe; score is not a measurement | Ranking metadata only | ADMIT NOW for historical comparison, not broad-universe authority; runtime current |
| Mutation case counts | 037–046; existing parser accepts all complete | `gene_ids` 100; project buckets | 1,000 requested LUAD buckets; explicit values preserved; missing bucket not wild type | Aggregation completeness checked; all-project response, extract exact LUAD | 2,523,861 B / 28.419 s for 1,000; ADMIT NOW counts, not recurrence rates; runtime current |
| SSM coverage | 023 | per-project `case_with_ssm` | Indexed SSM-data coverage, not per-gene callable-negative set | Separate from mutation numerator | ADMIT NOW context only; runtime current |
| SSMs | mapping 006; 015 | variant ID, GRCh38 coordinates, alleles; occurrence project filter | Variant ≠ case; transcript rows are not independent mutations | Small partial search; explicit paging required | LATER variant enrichment; NOT ADMITTED as complete mutation burden |
| SSM occurrences | mapping 007; 016/052 | case + ssm IDs, transcript gene IDs; TP53/project filter | 299 occurrences reported; multiple callers same sample observed; dedup by case/gene for case counts | Leaf observation fields work; broad `case.observation` gave a warning | LATER detailed lane; sample ID present, negative callability absent |
| Gene CNVs | mapping 008; 017 | `cnv_id` + `consequence.gene.gene_id`, project filter | TP53 had 3 indexed category entities, not 3 cases | GRCh38, `gene_level_cn`; categories Loss/Gain/Amplification | not runtime-allowlisted; occurrence lane does not require this endpoint |
| CNV occurrences | mapping 009; 018/050/051/055/067/068 plus a bounded shape probe | case + cnv + gene IDs, source file, caller | TP53 264 reported occurrences; no negative denominator | Strict pages; committed fixture preserves generic Loss, ASCAT3 and missing sample ID; probe observed ASCAT2/ASCAT3/AscatNGS plus Loss/Gain/Amplification | IMPLEMENTED for Stage 4 survivors only (live-verified 2026-09-25; see [implementation status](IMPLEMENTATION_STATUS.md)) |
| CNV 100 workload | 067 | first 100 universe genes + LUAD | 21,032 occurrence total; two sample hits only | Full scan would need 85 pages of 250, exceeding 10; facets count occurrences, not assured unique cases | REJECT full broad occurrence scan; reduce first; full 1,000 cost UNMEASURED |
| Segment CNVs | mapping 010; 019 | segment ID, chromosome, start/end/length | 30,681 LUAD entities; no direct gene join admitted | Position/category response; projection to genes needs overlap/build policy | LATER; no segment discovery lane now |
| Segment occurrences | mapping 011; 020/053 | case/segment/source file IDs, copy number | 32,385 reported; only 2 inspected; no complete cohort distribution | Leaf fields work; missing sample mapping | LATER; full scan outside the current page budget |
| Expression availability | 047 | explicit case/gene IDs | first 250 cases: 221 available/29 unavailable; first 100 genes: 91 available/9 unavailable | Independent case/gene availability does not guarantee every matrix cell exists | ADMIT NOW; runtime current |
| Expression values | 049/056–066 | gene row and case column labels; UQFPKM | 1,000×250 requested → 946 gene rows × 221 case columns across batches; 100×585 → 91×518 | Twelve captures accepted by the strict TSV parser; missing rows/columns preserved; sample mapping unresolved | ADMIT NOW case-labelled descriptive summaries; runtime current |
| Expression selection | 048 | explicit 100 genes/250 cases, `selection_size` 100 | Only that requested population; not full LUAD | Provider medians/stddev retained; estimator details not independently established | ADMIT NOW metadata only; no averaging batch medians/SDs |
| Open expression file metadata | mapping 004; 021 | file/case/sample/aliquot IDs; `access=open` | 601 files reported, not 601 independent cases | Five sampled `STAR - Counts` files, not a complete workflow census | ADMIT NOW bounded provenance context; cannot establish matrix-cell sample linkage |
| Clinical metadata | 024/069 | case, demographic, diagnoses, samples | Null/missing follow-up; multiple samples/diagnoses possible | Two-case sample; no definitive diagnosis-selection contract | LATER; preserve raw context only, no clinical scoring |
| Survival analysis | 054, documented GET | filters array with `cases.project.project_id` | 509 donor records returned for LUAD versus 585 inventory; exclusion/censoring audit unresolved | `results`/`donors` with time, censored, ID; nonempty unlike earlier probes | LATER; endpoint works, inferential survival NOT ADMITTED |
| scRNA | official API; metadata 025 | case or HDF5 file ID; documented ≤10 genes | LUAD open scRNA metadata query returned 0; no applicable source selected | Cell-level units and normalization need a separate contract | LATER; live value capability UNVERIFIED |
| Downloads, arbitrary query, controlled evidence | Outside approved runtime | `/data`, manifest, slicing, auth | Not in scope | No probe or file acquisition | REJECT / DO NOT BUILD |

The five-category CNV field is not reliably five mutually exclusive biological states in these
responses: cohort facets contained lower-case loss/gain/amplification/homozygous deletion and no
neutral bucket. Preserve case-sensitive raw labels; normalize only through an explicit parser
table. Loss is not proof of heterozygous deletion. Absence is not proof of neutral/diploid.

## Measured versus extrapolated workloads

| Workload | Requests | Bytes | Summed request wall time | Scope |
|---|---:|---:|---:|---|
| Gene inventory 1,000 | 10 | 106,739 | 12.801 s | Measured, sorted protein-coding prefix |
| Mutation counts 100 | 1 | 246,042 | 2.771 s | Measured first batch, all-project response |
| Mutation counts 1,000 | 10 | 2,523,861 | 28.419 s | Measured, LUAD extracted |
| Expression 100×250 | 1 | 176,337 | 2.246 s | Measured; 91×221 returned |
| Expression 1,000×250 | 10 | 1,834,776 | 25.203 s | Measured; 946×221 returned |
| Expression 100×585 | 3 | 414,305 | 6.478 s | Measured; 91×518 returned |
| Expression 1,000×585 | 30 | ~4.14 MB | ~64.8 s | ESTIMATE by 10×100-gene full-frame workload; not measured |
| Full CNV 100 occurrences | ≥85 pages of 250 | Unknown | Unknown | Page estimate from 21,032 total; not acquired |

The 1,000×585 expression estimate is a feasibility scenario, not an admitted query plan: splitting
queries must not evade the ten-page logical-query budget. A design must declare independently
bounded gene batches/populations and shared campaign reservations, or use richer evidence only
for survivors. Neither latency nor body size estimates are provider guarantees.

## Admitted field-to-result trace

Parser names distinguish implemented symbols from later proposals. Every result also binds response/request hashes, release,
method and population.

| Result fields | Endpoint and provider field | Parser/interpretation | Deterministic method / typed result |
|---|---|---|---|
| cohort/project, eligible inventory count | `projects.project_id`, `summary.case_count` | existing `parse_projects`; count not assay eligibility | `PopulationFrame` inventory |
| examined IDs / membership / sample context | `cases.case_id`, `project.project_id`; samples IDs/types/aliquots | existing `parse_cases` for case frame; NEW sample-link parser if used | unique sorted case frame; sample links remain multivalued |
| gene identity/universe | `genes.gene_id,symbol,biotype`; `pagination.total` | existing `parse_genes` + NEW paginated-universe envelope validation | `EntityRef`/`TestedUniverse`, explicit bounded subset |
| mutation affected cases | `aggregations.projects.buckets[].genes.my_genes.gene_id.buckets[].doc_count` | existing `parse_gene_case_counts`; retain complete flag | `MUTATION_AFFECTED_CASE_COUNT_V1` → `ObservedCount` or unavailable |
| SSM coverage | project `case_summary.case_with_ssm.doc_count` | existing `parse_mutated_cases_count` | `PROJECT_SSM_COVERAGE_V1`, no recurrence denominator |
| assay availability | `cases/genes.details[].has_gene_expression_values` | existing `parse_expression_availability`; requested membership checks | `Coverage`, independent axis flags |
| expression values/missing IDs | values TSV header case IDs and `gene_id` rows | existing `parse_expression_values`; finite nonnegative UQFPKM; label joins | `EXPRESSION_LOG2_SUMMARY_V1` on `log2(x+1)`, explicit n and missingness |
| provider selection summaries | `gene_selection[].log2_uqfpkm_median/stddev` | existing `parse_gene_selection` | `EXPRESSION_PROVIDER_SUMMARY_V1` metadata, unavailable for multi-batch cohort summary |
| file/workflow context | `files.access`, `analysis.workflow_type`, cases/samples/aliquots | existing `parse_files_provenance` for sampled context; NEW link-preserving parser for matching | provenance only; no inferred cell-level workflow |
| CNV category evidence | `cnv_occurrence_id`, `case.case_id`, `cnv.cnv_id`, `cnv.consequence[].gene.gene_id`, `cnv.cnv_change/_5_category` | implemented `parse_cnv_occurrences_page`; required IDs/category, dedup/order and exact filter membership | `CNV_INDEXED_POSITIVE_CASES_V1`: unique positive cases per category over a complete query |
| CNV contextual values | `case.observation[].copy_number`, `src_file_id`, `variant_calling.variant_caller`, tumor sample UUID | implemented optional context; missing ≠ invalid; multiple observations are ambiguous and rejected | provider observation, not a cross-caller numerical effect |
| quality/completeness | `pagination` `count,total,from`; warnings; transport terminal status; missing sets | shared validated envelope + lane-specific completion checks | `Quality`/`Coverage`; warnings about requested scientific fields prevent admission |
| derived extremes | parsed expression values and frame/universe above | no new provider field | implemented `EXPRESSION_TUKEY_TAIL_V1` within-gene empirical tail; descriptive only |

Scientific annotations such as dependency, druggability, clinical benefit, mutation-expression
coherence or CNV-expression causation receive no field in the admitted measured contract.

## Joins and denominators

Case/gene ID joins between indexed observations are feasible for descriptive presence
intersection. They do not establish matched assays. CNV source-file lookup returned both a tumor
and a blood-normal sample; the expression API supplies case columns without the chosen
sample/aliquot. SSM observations can repeat across callers and transcripts. Never count these as
independent cases or choose the first sample/file. Exact duplicate records may deduplicate by
declared keys; inconsistent duplicates fail or remain conflicts.

Eligible inventory, examined cases, available assays, returned columns and finite values remain
separate. Mutation-negative and CNV-neutral sets are not established. Mutation-expression and
CNV-expression association actions are INELIGIBLE until exact sample selection,
negative/reference semantics and a common analyzable population are independently validated.

## Fixture status and remaining fixtures

IMPLEMENTED: a bounded public CNV occurrence fixture retains generic Loss, caller context and a
missing tumor-sample UUID; synthetic contract/replay cases cover mixed callers, category
conflicts, duplicates, pagination and cap refusal. Remaining planned captures include sorted universe
paging/duplicates/changed totals; explicit mutation zero versus absent bucket and truncated
aggregation; expression omitted genes/cases across batches; a source file with tumor+normal
samples; and nonempty survival with missing follow-up/censoring cases. Add synthetic malformed
variants separately labelled SYNTHETIC.
