# GDC × Jev fit analysis — what open GDC evidence should feed Jev

Status: **PROPOSED** analysis for Phase 2/3 approval. Written 2026-09-22 against repository HEAD `43653cfad1657acda4ff578a20db726d44c6dc31` and live public GDC API captures recorded in `data/gdc-contract-captures-2026-09-22/` (30 captures, 80,653 bytes read, anonymous access, no authentication headers, redirects refused, 512 KiB per-response cap). Labels: **VERIFIED** = observed in a retained live capture or in this repository's tested code; **DOCUMENTED** = stated by an official source cited inline; **INFERRED** = derived from captured bytes by explicit reasoning; **UNVERIFIED** = not confirmed.

This document answers one question before any Phase 2 code is written:

> Which public, open-access GDC data, metadata, derived analysis results, coverage information, or structured context produces the most useful, compact, reproducible semantic state for Jev?

The answer determines the Phase 2 vertical slice (deterministic real-GDC evidence) and the Phase 3 wide Jev question set.

---

## A. Current repository audit (2026-09-22)

This section is the **pre-implementation audit snapshot** taken before Phase 2/3 work began; the live implementation status is recorded in `docs/IMPLEMENTATION_STATUS.md`.

| Item | State |
|---|---|
| HEAD | `43653cf` — “Fix Phase 1 audit findings and verify the repaired slice” |
| Phase 1 | **VERIFIED** offline synthetic vertical slice; 43/43 Python tests green on this machine (`python -m pytest`, 2026-09-22) |
| Persistence | SQLite schema **2**; 8 immutable tables with triggers; single `append_event` authority; artifacts published atomically with SHA-256 |
| Domain contracts | `ResearchRun`, `CandidateInvestigation`, `StatisticalState` (fixture shape), `EvidenceState`, `JevEvaluation`, 25-section dossier (`docs/DOMAIN_MODELS.md`) |
| Event contract | `RunEventV1`, 22 registered types (`cancerjev/domain/events.py`); one canonical stream consumed by CLI and API |
| Fixture Jev representation | Deterministic Noul/Choice/Score-shaped vectors labeled `FAKE` (`cancerjev/research/fixtures.py`); zero provider calls |
| Provider abstraction | **None.** No GDC client, no HTTP client, no TypeSafe import, no credential path (grep over all `.py`/`.ts`/`.tsx` confirms no `api.gdc.cancer.gov`, `typesafe`, `Authorization`, or `X-Auth-Token`) |
| Scientific methods | Contracts only in `docs/SCIENTIFIC_INVARIANTS.md`; no production method implemented |
| Persistence gaps for Phase 2 | No `gdc_attempts`, `gdc_cache`, `jev_projections`, or `jev_cache` tables yet (`docs/PERSISTENCE.md` declares them later-phase) |

Phase 1 infrastructure is preserved as-is; Phase 2 extends it (schema 3, new modules) rather than redesigning it.

## B. GDC source authority matrix

| Rank | Source | Role | Status |
|---|---|---|---|
| 1 | Live `api.gdc.cancer.gov` responses retained in `data/gdc-contract-captures-2026-09-22/` | What the deployed API actually does | **VERIFIED** (28 captures; release 46.0, tag 8.5.0, commit `8f7c2a51…`) |
| 2 | `NCI-GDC/gdc-docs` (official API documentation repository) | Published request/response contracts, field discovery, release notes | **DOCUMENTED** (commit examined: see §B.1) |
| 3 | `NCI-GDC/gdcdatamodel2` | Current data-model design repository; replaces `gdcdatamodel` | **DOCUMENTED** (commit examined: see §B.1) |
| 4 | `NCI-GDC/gdcdictionary` | Field-level schema semantics: types, enums, required/optional, links | **DOCUMENTED** (targeted schemas only; see §B.1) |
| 5 | Official GDC bioinformatics pipeline documentation (DNA/RNA processing) | Scientific meaning of derived analysis results | **DOCUMENTED** (see §H) |
| 6 | `NCI-GDC/gdc-mutation-indexer`, `gdc-models`, `gdc-rnaseq-cwl`, `gdc-dnaseq-cwl`, `maf-lib`, `gdc-client` | Secondary/background only; none is a runtime dependency | Reference only |
| — | Supplied local `API_UG.pdf` (Phase 0) | Historical reference; superseded by live captures where they differ | Reference only |

Rule applied: documentation establishes intent; the retained live capture establishes deployed behavior; where they disagree, the capture wins for what the code may rely on, and the disagreement is recorded.

### B.1 Documentation pass record

The documentation pass examined the repositories below and recorded exact revisions. (Revision SHAs are recorded here after the pass completes; this section is the only place where they appear.)

- `NCI-GDC/gdc-docs`: revision **`157cef9dac084ce30720f0ad507cd54017263be7`** (2026-08-28), examined pages: Getting Started, Search and Retrieval, Data Analysis, System Information, Appendix A Available Fields, API Release Notes (latest v8.5.0), Data Release Notes (DR 46.0), Data Dictionary Release Notes, Downloading Files, Data Security, Expression mRNA Pipeline, CNV Pipeline, MAF Format.
- `NCI-GDC/gdcdatamodel2`: revision **`9c6a046b96c130ea131d2ce2c9160381edd2fcc1`** (2026-05-18; equals release tag `4.0.3`). README examined; it states: “This project replaces [gdcdatamodel](https://github.com/NCI-GDC/gdcdatamodel) to overcome the challenges and obscurity associated with using gdcdatamodel.” The same README carries a notice that the code is public as-is for informational purposes, that private resources may be used to build it, and that documentation may refer to restricted URLs — those references are **not** permission to use private resources; OntoJev runtime remains public/open-data-only. Generated model files state they are generated from gdcdictionary 4.0.3, while `plaster.toml` pins the dictionary branch `develop` — a lockstep caveat recorded as UNVERIFIED alignment.
- `NCI-GDC/gdcdictionary`: revision **`88d66b0fe361aa638977850c180bd9130d705924`** (2026-09-18); release tag `4.0.3` is its parent commit `bd56b99f6859cf7c47d0e49cb1def94d8400453e` and the only difference is a PR-template document, so schema content is identical. Targeted schemas examined: program, project, case, diagnosis, demographic, exposure, sample, portion, analyte, aliquot, slide, file and the file subtypes (`gene_expression`, `simple_somatic_mutation`, `masked_somatic_mutation`, `copy_number_estimate`, `copy_number_segment`), and the workflow schemas. The dictionary does **not** define `gene`, `ssm`, `ssm_occurrence`, `cnv`, `cnv_occurrence`; those are API-layer entities (see §D).
- Official pipeline documentation: DNA-seq somatic mutation pipeline (MAF semantics, VEP/impact annotations) and RNA-seq expression pipeline (STAR, UQFPKM definition).

Documentation-pass findings that changed the design:

- `/_mapping` is **per endpoint** (`/<endpoint>/_mapping`), which is why the probe of the bare `/_mapping` returned 404. A live probe of `/projects/_mapping` returned HTTP 200 (5,036 bytes) with `_mapping`, `defaults`, `expand`, `fields`, `multi`, `nested`. Field discovery is therefore available but is used only for contract verification, never for runtime science.
- `top_mutated_genes_by_project` `_score` is documented prose: “the `score` field does not represent the number of mutations in a given gene, but a calculation that is used to determine which genes have the greatest number of unique mutations.” This confirms the quarantine decision with an exact quote.
- `/analysis/survival` is documented as **GET**; POST is not documented. Live probes of both GET and POST returned HTTP 200 with empty `donors` for every attempted filter shape, so the contract remains unestablished and the endpoint stays disabled.
- Maximum `case_ids`/`gene_ids` counts for `/gene_expression/*` are **not documented**; the 250/100 caps are application limits, exactly as `docs/GDC_BUDGETS.md` already states.
- Expression semantics: FPKM-UQ is documented with its formula; `median_centered_log2_uqfpkm` is documented in three steps; the `log2_uqfpkm_median`/`log2_uqfpkm_stddev` estimators returned by `gene_selection` are **not documented**.
- Authentication: only controlled-access downloads and data submission require `X-Auth-Token`; browsing indexed metadata requires no login. OntoJev never constructs that header and never uses controlled data.

## C. Open-access security model (scientific invariant, not a setting)

`GDC_TRANSPORT_AUTH_MODE = NONE`.

| Rule | Enforcement |
|---|---|
| One transport | `GDCTransport` is the only module allowed to open a GDC socket; no other module constructs an HTTP client for GDC |
| Fixed host | `https://api.gdc.cancer.gov` only; any other host is a programming error |
| Method allowlist | `GET` and `POST` only, per-endpoint; `POST` is never auto-retried |
| No authentication | The transport has no credential parameter, no token loader, no OAuth code, no `Authorization`/`X-Auth-Token` header path; outgoing headers are exactly `Accept`, `Accept-Encoding: identity`, `User-Agent`, and `Content-Type` for POST |
| No environment token | No `GDC_TOKEN`, no credential file, no dbGaP/eRA integration anywhere; grep tests assert this |
| No redirects | Redirect responses are refused, not followed |
| No file acquisition | `/data`, manifests, `gdc-client`, BAM/VCF/MAF/FASTQ, archives, bulk download are absent from the allowlist and from the codebase |
| Open filter on file metadata | If `/files` is queried, the request must contain `access = open`; a returned `access != open` record fails closed (`UNAVAILABLE_ACCESS`) and is never admitted to scientific use |
| 401/403 | Terminal `UNAVAILABLE_ACCESS`; no retry, no credential lookup |
| Test proof | Adversarial tests assert outgoing request headers contain no `Authorization`/`X-Auth-Token`, that `access=controlled` results are rejected, and that `/data` is not routable |

Live evidence: 28 anonymous captures succeeded with HTTP 200 (one deliberate `/_mapping` probe returned 404); request metadata records `authentication_headers_sent: []` for every capture.

## D. Current data-model analysis (`gdcdatamodel2` + `gdcdictionary`)

GDC operates **two planes**, and conflating them would be a scientific error:

1. **Submitted graph model** (`gdcdatamodel2` + `gdcdictionary`): `program → project → case → sample → portion → analyte → aliquot`, plus `case → diagnosis | demographic | exposure`, `aliquot → file`, workflow nodes (`rna_expression_workflow`, `somatic_mutation_calling_workflow`, `genomic_profile_harmonization_workflow`), and file subtypes (`gene_expression`, `simple_somatic_mutation`, `masked_somatic_mutation`, `copy_number_estimate`, `copy_number_segment`). Links are documented per schema (`links.programs`, `links.cases`, `links.samples`, …).
2. **API Elasticsearch indexes** (`api.gdc.cancer.gov`): these add derived entities **not present in the dictionary** — `gene`, `ssm`, `ssm_occurrence`, `cnv`, `cnv_occurrence`. The dictionary has no `gene.yaml`, `ssm.yaml`, `cnv.yaml`, `ssm_occurrence.yaml` or `cnv_occurrence.yaml`; their field semantics come only from the API mapping and documentation. Any claim that Phase 2 “dictionary-verified” those fields would be false.

Field semantics the deterministic parsers may rely on:

- **Case as biological unit.** The API case document carries `case_id`, `submitter_id`, `project.project_id`, `samples[].sample_type`, and expands `diagnoses[]`, `demographic`, `exposures[]`. A case can carry **multiple diagnoses** (a live example showed three for one case, including duplicate primary diagnoses with divergent ages and one “Not Reported”), so any clinical field would need an explicit selection rule — another reason Phase 2 uses no clinical fields.
- **Identifier semantics.** `uuid` is the system identifier; `submitter_id` is project-scoped and unique only within a project (`uniqueKeys: [id]`, `[project_id, submitter_id]`). TCGA barcodes are convention, not a schema pattern. Sentinels `Unknown`, `Not Reported`, `Not Allowed To Collect`, `Not Applicable` are explicit enum values, not nulls.
- **Clinical field names at this revision.** `gender` no longer exists (it is `demographic.sex_at_birth`); `tumor_stage` is superseded by `ajcc_*`/`uicc_*`/`figo_stage` families; `vital_status` and `days_to_death` live on `demographic`; `is_ffpe` lives on `portion`. Live probes requesting the old names produced `warnings.fields` — consistent with the dictionary.
- **Mutation/CNV path (API plane).** `case → ssm_occurrence → ssm → consequence.transcript.gene`; `case → cnv_occurrence → cnv → consequence.gene`; occurrence ids are `ssm_occurrence_id`/`cnv_occurrence_id` (the legacy singular endpoints return 404). One SSM occurrence carries many transcript consequences (14 in the sampled record), and `ssm.consequence.transcript.impact` was not recognized under that path.
- **File provenance.** `file.access ∈ {open, controlled}` is assigned by the API/platform, **not** a dictionary enum; `files.acl` carries dbGaP accessions. Live facet counts on 2026-09-22: 390,418 open vs 946,942 controlled files. Open-access file counts include Gene Expression Quantification 27,843, Masked Somatic Mutation 24,498, Gene Level Copy Number 41,083. `analysis.workflow_type` is an API object field (`"analysis": {"workflow_type": "STAR - Counts"}`), and workflow values are defined by the workflow schemas (`rna_expression_workflow` enumerates `STAR - Counts`, `HTSeq - FPKM-UQ`, …).
- **Dictionary/model lockstep caveat.** Generated model files state they are generated from dictionary version 4.0.3, while `plaster.toml` pins `version = "develop"`, so regeneration tracks a branch, not the release tag. The dictionary HEAD examined is one documentation-only commit ahead of tag 4.0.3, so schema YAML content is identical between the tag and HEAD.

Dictionary-level field tables (required/optional, enums, links) are used only to validate parser field manifests; the runtime does not ship the dictionary.

## E. GDC data inventory for Jev (live-verified)

| # | Source | What it is | Volume observed | Bound in Phase 2 |
|---|---|---|---|---|
| 1 | `GET /status` | Release identity: commit, data release 46.0, tag 8.5.0 | 221 B | 1 request |
| 2 | `GET /projects` | Project/program identity, primary site, disease type, case/file counts, data categories | 2.7 KB for 3 projects; 93 projects total | 1 request, ≤100 projects |
| 3 | `GET /cases` | Case manifest: `case_id`, `submitter_id`, project, sample types; optional clinical expansions | 1.1 KB for 2 cases; 51-case project complete in one 250-size page | ≤12 requests (one per selected project), size 250 |
| 4 | `GET /files` (metadata) | Open-file provenance: data type, strategy, workflow, platform | 0.96 KB for 2 files; 390,418 open files (vs 946,942 controlled); open Gene Expression Quantification 27,843, Masked Somatic Mutation 24,498 | ≤2 requests, `access=open` mandatory |
| 5 | `GET /genes` | Gene identity: symbol, name, biotype, cancer-census flag | 355 B for TP53 | 1 request, ≤100 genes |
| 6 | `GET /analysis/top_mutated_genes_by_project` | Provider-ranked mutated genes per project with `_score` | 485 B for 5 hits; 20,102 genes for BRCA | ≤12 requests, size ≤20; `_score` is ranking metadata only |
| 7 | `GET /analysis/top_cases_counts_by_genes` | Gene-specific affected-case counts per project, nested buckets | 14.4 KB (1 gene) / 19.9 KB (3 genes); 61 project buckets | 1 request, ≤100 genes |
| 8 | `GET /analysis/mutated_cases_count_by_project` | Per-project `case_with_ssm` coverage | 10.8 KB, 93 buckets | 1 request, `size=0` |
| 9 | `GET /gene_expression/availability` | Per-case/per-gene presence flags and counts | 410 B | ≤12 requests, ≤250 cases and ≤100 genes each |
| 10 | `POST /gene_expression/gene_selection` | Provider median/`stddev` of log2 UQFPKM per gene | 153 B | ≤12 requests (one per project), ≤250 cases |
| 11 | `POST /gene_expression/values` | Exact per-case UQFPKM matrix (TSV) or median-centered log2 variant | 115 B for 2 cases × 1 gene | ≤12 requests (one per project), ≤250 cases × ≤10 genes |
| 12 | `GET /ssms`, `GET /ssm_occurrences` | Variant records and case occurrences | 4.1 M occurrence rows | **Not used** in Phase 2 |
| 13 | `GET /cnvs`, `GET /cnv_occurrences`, `GET /segment_cnvs` | Categorical CNV records | 75 K CNVs, 84.8 M occurrences | **Not used** in Phase 2 |
| 14 | `GET /analysis/survival` | Grouped survival curves/statistics | Returned empty `donors` for all attempted request shapes (GET and POST) | **Not used**; UNVERIFIED semantics |
| 15 | `GET /<endpoint>/_mapping` | Per-endpoint field mapping and descriptions | 5.0 KB for `/projects/_mapping`; bare `/_mapping` is 404 | **Not used at runtime**; contract-verification only |

## F. GDC × Jev fit matrix

Columns: open access, API available, bounded request, volume, semantic richness, deterministic precomputation, cross-project comparability, missingness visibility, provenance quality, scientific ambiguity, likely Jev value, classification.

| Source | Open | API | Bounded | Volume | Rich | Det. precompute | Comparable | Missingness | Provenance | Ambiguity | Jev value | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Project/program context | yes | yes | yes | tiny | medium | yes (counts, categories) | high (identity only) | high (data categories, case counts) | high (`/status`, project ids) | low alone | context, not an endpoint | **USE IN PHASE 2** (scope + context) |
| Case manifests (ids, project, sample types) | yes | yes | yes | small | medium | yes (counts by type) | high (frame definition) | high (complete frame for ≤250-case projects) | high | low | defines examined population | **USE IN PHASE 2** |
| Clinical fields (diagnosis/demographic/exposure) | yes | yes | yes | medium | high | partial | medium (harmonization varies) | high (nullable, “Not Reported”) | medium | high (time origin, staging, treatment) | high later | **DEEP PHASE LATER** (not needed for first state; survival semantics unresolved) |
| Sample-type composition | yes | yes | yes | tiny | medium | yes | medium | medium | high | medium | comparability context | **USE IN PHASE 2** (counts only) |
| Mutation discovery (`top_mutated_genes_by_project`) | yes | yes | yes | small | low (rank only) | selection only | **no** (rank is provider-internal, not comparable across projects) | none | medium | high (`_score` undocumented) | discovery only | **USE IN PHASE 2 as selection metadata** — never as evidence |
| Gene-specific affected-case counts (`top_cases_counts_by_genes`) | yes | yes | yes | small | medium | yes | high within scope (same endpoint semantics) | **partial** (absent bucket ≠ zero) | high (completeness metadata present) | medium (provider case universe, no matched denominator) | high (recurrence vs exception vs coverage) | **USE IN PHASE 2** — count-only |
| Project `case_with_ssm` coverage (`mutated_cases_count_by_project`) | yes | yes | yes | small | medium | yes | high (per project) | high (zero-bucket projects visible, e.g. NCICCR-DLBCL 0/489) | high | medium (SSM pipeline availability, not callability) | coverage explanation | **USE IN PHASE 2** as coverage context |
| Expression availability | yes | yes | yes | small | medium | yes (counts) | high (per project) | high (explicit presence flags) | high | low | coverage explanation | **USE IN PHASE 2** |
| Expression provider summary (`gene_selection`) | yes | yes | yes | tiny | medium | retained as provider statistic | medium (provider case universe UNVERIFIED) | partial | medium | medium (estimator convention undocumented) | variability/exception | **USE IN PHASE 2** retained separately |
| Expression local summary (`values` TSV) | yes | yes | yes | small | high | **yes** (log2(x+1), median, SD) | high (exact case set, one unit/workflow) | **high** (missing columns explicit) | high | low after documented units | variability/exception/fragility | **USE IN PHASE 2** — primary expression method |
| SSM/occurrence detail, consequence strata | yes | yes | per-variant only | huge | high | no matched aggregation | low (per-variant) | high | high | high (impact semantics) | high later | **DEEP PHASE LATER** |
| CNV categorical | yes | yes | aggregate only | huge | medium | no | low (category policy needed) | medium | medium | high (gain≠amplification, no denominator) | medium later | **DEEP PHASE LATER** |
| Survival | yes | partially verified | yes | small | high | no | low | high | medium | **very high** (censoring, time origin, groups) | high later | **EXPERIMENTAL / DEFERRED** (GET and POST probes empty) |
| File metadata provenance | yes | yes | yes | small | medium | yes | high | high | high | low | prevents incomparable comparisons | **USE IN PHASE 2** (`access=open`, workflow) |
| Per-endpoint `_mapping` | yes | **200 live** | yes | small per endpoint | low (field names) | no | n/a | n/a | high (describes fields) | low | contract verification only | **USE FOR CONTRACT VERIFICATION ONLY** |
| `/data`, manifests, BAM/VCF/MAF/FASTQ, gdc-client | controlled mix | yes | **no** | huge | — | — | — | — | — | — | none | **REJECT — out of scope by invariant** |

Reasoning for the central selection:

1. **Mutation affected-case counts** are the only open, bounded, gene-specific, cross-project *count* signal with visible completeness metadata. They are compact (one integer per gene–project pair) and create real semantic ambiguity: a gene may recur broadly, recur in one project, or appear absent because the project lacks SSM data. Deterministic code can compute the counts, dominance and coverage; only semantic judgment can weigh whether a pattern is a coherent cross-project signal, a project exception, or a coverage artifact.
2. **Local expression summaries** complement mutation counts with an independently measured, deterministic continuous quantity on an exact case set with a documented unit. They are computed by code (not the provider), so reproducibility is complete; they add a second modality whose cross-project dispersion supports fragility/exception questions without inventing a directional biological claim.
3. **Coverage/missingness** is a first-class input, not decoration. Without it, an absent bucket or a project with no expression values would be misread as a biological negative. The API makes coverage explicit (availability flags, `case_with_ssm`, case counts), so Jev can be asked the one question deterministic code cannot answer: whether the apparent pattern is plausibly a coverage artifact.
4. **Provider `_score` and rank are quarantined** as selection metadata. They never fill counts, fractions, or effect fields.

## G. Endpoint contract matrix (admission gate)

Every admitted endpoint passed documentation review, open-access review, live contract check, and scientific-semantics review. Live captures: `data/gdc-contract-captures-2026-09-22/INDEX.json`.

| Endpoint | Purpose | Open | Request contract (verified) | Response contract (verified) | Scientific meaning | Remaining ambiguity | Parser | Enabled |
|---|---|---|---|---|---|---|---|---|
| `GET /status` | release identity | yes | none | `commit`, `data_release`, `tag`, `status` | provenance only | none | strict | **yes** |
| `GET /projects` | scope inventory | yes | `size`, `fields`; 93 total | `data.hits[]` with `summary.case_count`, `summary.file_count`, `summary.data_categories[]`, `primary_site[]`, `disease_type[]`, `program.name` | composition context | `Not Reported` values exist | strict | **yes** |
| `GET /cases` | examined-case frame | yes | filter `project.project_id`, `size ≤250`, `sort=case_id`, `fields` | `data.hits[]`; `warnings.fields` for unknown fields | population definition | sample-type ordering; multiple samples per case | strict | **yes** |
| `GET /files` | open provenance | yes | **must filter `access=open`** | `access`, `data_type`, `experimental_strategy`, `analysis.workflow_type` | comparability | none for admitted use | strict | **yes (provenance only)** |
| `GET /genes` | gene identity | yes | filter `symbol`/`gene_id`, ≤100 | `gene_id`, `symbol`, `name`, `biotype`, `is_cancer_gene_census` | entity identity | `start`/`end`/`chromosome` unrecognized | strict | **yes** |
| `GET /analysis/top_mutated_genes_by_project` | discovery | yes | filter `case.project.project_id`, `size ≤20`, `fields=gene_id,symbol` | hits with `_score` | ranking metadata only | `_score` semantics undocumented | strict | **yes (selection only)** |
| `GET /analysis/top_cases_counts_by_genes` | recurrence counts | yes | `gene_ids` ≤100 | `hits.total`, `aggregations.projects.buckets[]` with `genes.my_genes.gene_id.buckets[]` | affected-case counts | provider case universe; bucket absence ≠ 0; multi-gene shape verified live | strict | **yes** |
| `GET /analysis/mutated_cases_count_by_project` | SSM coverage | yes | `size=0`; filters silently ignored → **no filters** | `aggregations.projects.buckets[].case_summary.case_with_ssm.doc_count` | pipeline availability context | filter semantics unsafe; complete-bucket metadata present | strict | **yes (unfiltered only)** |
| `POST /gene_expression/availability` | expression coverage | yes | `case_ids ≤250`, `gene_ids ≤100` | `cases.details[].has_gene_expression_values`, counts | coverage | assay/sample matching not guaranteed | strict | **yes** |
| `POST /gene_expression/gene_selection` | provider summary | yes | `case_ids ≤250`, `gene_ids`, `selection_size` | `gene_id`, `symbol`, `log2_uqfpkm_median`, `log2_uqfpkm_stddev` | provider statistic | estimator convention undocumented | strict | **yes (retained separately)** |
| `POST /gene_expression/values` | local summary input | yes | `case_ids ≤250`, `gene_ids ≤100`, `tsv_units=uqfpkm` | TSV `gene_id` + one column per case | exact per-case UQFPKM | case-level aggregation provider-side UNVERIFIED | strict TSV | **yes** |
| `GET /analysis/survival` (documented method) | — | yes | `filters` JSON array of groups | empty `donors` for GET and POST probes | unresolved | **contract not established** | none | **no** |
| `GET /_mapping` | — | — | — | HTTP 404 live | — | — | none | **no** |
| `/data` and file acquisition | — | — | — | — | — | — | none | **no (invariant)** |

Live-verified safety behaviors: unknown requested fields produce `warnings.fields` (never silently dropped); `mutated_cases_count_by_project` silently ignored a filter and returned empty buckets — therefore the design forbids filtered calls to it; pagination carries `count/total/size/from/pages`, and aggregations carry `timed_out`, `_shards`, `doc_count_error_upper_bound`, `sum_other_doc_count`.

## H. GDC scientific semantics gaps

| Question | Finding | Consequence |
|---|---|---|
| Is `case_with_ssm` a callable-negative denominator? | No. It is SSM pipeline availability, not whole-genome callability. | Mutation evidence is **count-only**; no recurrence fraction is computed. |
| Is `_score` a mutation count or effect size? | Documented prose: “the `score` field does not represent the number of mutations in a given gene, but a calculation that is used to determine which genes have the greatest number of unique mutations.” No formula is published. | Stored only as `provider_discovery_rank`; never aggregated as science. |
| Are `top_cases_counts_by_genes` bucket counts unique-case counts? | Buckets are provider-computed case counts; uniqueness is provider-defined. | Method declares the provider-defined duplicate rule; local re-derivation is impossible without occurrence rows. |
| What is the expression unit and transform? | `tsv_units=uqfpkm` returns UQFPKM; local transform is `log2(x+1)`, documented in the method. | Local summaries are reproducible; units explicit. |
| Is provider `log2_uqfpkm_stddev` a sample or population SD? | Live capture with two cases returned 0.29998 where sample SD = 0.4243 and population SD = 0.3000 → **INFERRED population SD**, not documented. | Provider statistic is retained as `PROVIDER_STATISTIC` with an explicit estimator note; it is not used for eligibility or thresholds. |
| Does `gene_selection` aggregate the exact requested case set? | Not documented; missing cases are omitted silently. | Local `values`-based summary is the primary expression evidence; provider summary is corroborating context only. |
| What does `/analysis/survival` accept? | Documented as GET with a JSON array of filter groups; POST is not documented. Live GET and POST probes with project and gene filters both returned empty donor sets. | Survival is excluded from Phase 2/3; any later use needs a dedicated contract pass. |
| Are there documented limits on `case_ids`/`gene_ids`? | No numeric limits are documented for `/gene_expression/*`; only guidance that very large requests time out and should be split. | The 250-case and 100-gene caps are application limits enforced by the transport, not provider guarantees. |
| Where is field discovery? | Per endpoint: `GET /<endpoint>/_mapping` (verified live for `/projects`). The bare `/_mapping` is 404. | Used for contract verification only; runtime parsers rely on documented field manifests and surface `warnings.fields`. |
| Does `/cases` field selection fail on unknown fields? | No; it warns via `warnings.fields`. The API also silently omits some unknown fields, so “requested successfully” is never proof a field exists. | Parsers must surface warnings as quality metadata and never assume a requested field is present. |
| Are `ssm`, `gene`, `cnv` and occurrence fields dictionary-verified? | No. They are API-layer entities absent from `gdcdictionary`; only the API mapping and documentation define them. | State provenance cites the API mapping/live captures, never a dictionary claim. |
| Is `files.access` a dictionary enum? | No. `open`/`controlled` are assigned by the API/platform; `files.acl` carries dbGaP accessions. | Open-access enforcement is transport policy (`access=open` filter + fail-closed check), not a dictionary validation. |
| Are GDC releases atomic across requests? | No documented snapshot token. | Provenance records per-request `retrieved_at`, response hashes and the `/status` release identity; reproducibility means replay from retained inputs, not a guarantee of future API identity. |

## I. TypeSafe/Jev skill research table

Authority: live `docs.typesafe.ai` (fetched 2026-09-22) plus the installed `typesafe-ai` skill. No TypeSafe API call was made during research.

| Topic | Confirmed contract | Phase 3 use | Classification |
|---|---|---|---|
| HTTP endpoint | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`, body `{state, model, questions}` | Adapter calls this (or SDK) | **USE PHASE 3** |
| Response | `{model, answers:{<id>:{type,…}}, usage:{input_tokens,output_tokens}}`; request id in `x-typesafe-request-id` header; no latency/cost fields | Persist resolved model, usage, measured latency | **USE PHASE 3** |
| Python SDK | `typesafe-sdk`, `from typesafe_sdk import Choice, Noul, Score, TypeSafeClient`; `client.system_one(state=…, questions={…})`; `.nouls/.choices/.scores`; env `TYPESAFE_API_KEY`; default model `jev-latest` | One adapter; owned contracts outside | **USE PHASE 3** (or minimal HTTP adapter with identical semantics) |
| Noul | `{"type":"noul","noul":0..1}`; no separate confidence | `warrants_deeper_investigation`, exception/fragility/coverage questions | **USE PHASE 3** |
| Choice | `{"type":"choice","choice":…,"confidence":0..1,"probabilities":{…}}`; ≤255 options | `pattern_type` with reduced roster | **USE PHASE 3** |
| Score | `{"type":"score","score":expected level,"confidence":…,"legend":{…},"probabilities":{…}}`; 2–10 levels, 0-based | Not used until an eligible follow-up exists | **USE LATER** |
| State | string/object/array; 64k token context (32k state + longest question); all questions share one state and are independent | One compact projection per state | **USE PHASE 3** |
| Question IDs | Not sent to the model; meaning must live in `instructions`/`criteria` | Owned question definitions carry full semantics | **USE PHASE 3** |
| Parallel questions | Mixed primitives in one call; 12.2× cheaper / 10× faster than per-question calls | Evaluate the full question set per state in one call | **USE PHASE 3** |
| Model | `jev-1.13.0` (alias `jev-latest`); pin the versioned ID; response reports resolved model | Pin `jev-1.13.0`; persist requested + resolved | **USE PHASE 3** |
| Confidence | Choice/Score distribution concentration; not correctness; Noul has none | Gates provisional; never a scientific confidence | **USE PHASE 3 (as policy input only)** |
| Reranking pattern | One Noul per candidate over the same query; sort by probability; batch independent questions | Wide reranking per state | **USE PHASE 3** |
| Function/action selection | Choice over closed action set + presence Nouls for optional args | Registered follow-up selection | **USE LATER (Phase 4+)** |
| Speculative fan-out | Ask all possibly-needed independent questions at once; ignore unused answers | Wide battery design | **USE PHASE 3** |
| Composite scoring | One Score per dimension, normalize, weights in code | Deterministic policy instead of hidden model score | **USE LATER** |
| Extraction cascade / citation check | Cheap check → verifier battery → escalate | Hypothesis critique | **USE LATER (Phase 6+)** |
| Autoresearch feature discovery | LLM proposes questions; classical model tests usefulness; prune | Offline question-set improvement | **USE LATER (documented only)** |
| Cache identity | Docs do not define caching; application owns it | Cache on projection bytes + question bytes + resolved model + adapter version | **USE PHASE 3** |
| Determinism | No seed/temperature documented; “designed to return stable answers”, not guaranteed | Persist raw answers; policy must be deterministic for identical stored evaluations | **USE PHASE 3 with recorded limitation** |

Explicit unknowns carried into code as limitations: exact `confidence` formula, server timeout, maximum question count, state byte limit, 429 body shape, cost fields absent, no idempotency key.

## J. Proposed StatisticalState (real, Phase 2)

Schema version 2 replaces the fixture shape. Every measured number is a `Metric` with unit, availability and provenance; no provider payloads.

```text
StatisticalState v2 (mode LIVE)
  state_id, schema_version: 2, state_hash, created_at, run_id
  entity: {gene_id, gene_symbol, biotype, is_cancer_gene_census, genome_build: "GRCh38"|null}
  scope: {programs[], projects[], modalities: ["mutation_counts", "expression_summary"],
          workflows: ["STAR - Counts"], sample_types[], examined_case_frame: "ALL_CASES_LE_250",
          comparability_groups[]}
  generation: {lane_ids[], lane_versions[], discovery: {method_id, examined_genes_n,
               selection_bias}, source_hit_refs[]}
  populations: Population[]                    # one per project; examined = all project cases
  mutation:
    availability: OBSERVED|PARTIAL|INSUFFICIENT
    project_results: MutationSummary[]
    coverage: {case_with_ssm: Metric, project_case_count: Metric}
  expression:
    availability: OBSERVED|PARTIAL|INSUFFICIENT|NOT_ACQUIRED
    project_results: ExpressionSummary[]
    coverage: {cases_with_expression: Metric, examined_cases: Metric}
  cross_project: {projects_with_mutation_observation: int,
                  projects_with_expression_observation: int,
                  affected_case_total: Metric, top_project_share: Metric,
                  expression_median_min/max: Metric, coverage_imbalance: bool,
                  noncomparable_groups[], notes[]}
  quality: {api_warnings[], missingness[], duplicate_checks, finite_checks, truncation,
            completeness}
  tested_context: {examined_genes_ref, examined_genes_hash, discovery_method,
                   selection_bias, coverage}
  provenance: {gdc_release, sources: SourceRef[], methods: MethodRef[], environment_hash}

MutationSummary = {project_id, population_id,
  affected_case_count: Metric(unit "cases", source PROVIDER_AGGREGATION),
  project_case_with_ssm: Metric, project_case_count: Metric,
  provider_discovery_rank: {rank:int, score:float, lane_id:str}|null}

ExpressionSummary = {project_id, population_id, unit: "log2(UQFPKM+1)",
  transformation: "log2(x+1)",
  local: {median, sample_sd, minimum, maximum, n_finite, n_missing: Metric,
          method_id: "EXPRESSION_LOG2_SUMMARY_V1"},
  provider: {median, stddev: Metric, source: "GENE_SELECTION",
             estimator_note: "INFERRED_POPULATION_SD_UNVERIFIED"}}
```

Deliberate exclusions: raw provider JSON, per-case expression vectors, SSM/occurrence rows, CNV records, clinical fields, survival, provider `_score` outside `provider_discovery_rank`, and any fabricated direction/recurrence fraction. Cross-project direction is `NOT_EXAMINED` because no signed comparable measure exists.

Deterministic methods (full declarations in `docs/SCIENTIFIC_INVARIANTS.md`):

| Method | Estimator | Eligibility | Missingness rule |
|---|---|---|---|
| `MUTATION_AFFECTED_CASE_COUNT_V1` | Provider per-project gene bucket count | Bucket present | Absent bucket → `NOT_OBSERVED`, never 0 |
| `PROJECT_SSM_COVERAGE_V1` | `case_with_ssm` / project case count | Project present in both sources | Absent → `NOT_OBSERVED` |
| `EXPRESSION_LOG2_SUMMARY_V1` | median (n≥1), sample SD (n≥2), min/max over `log2(UQFPKM+1)` | ≥1 finite value for median | Missing columns counted, never imputed |
| `EXPRESSION_PROVIDER_SUMMARY_V1` | Retain provider median/stddev verbatim | Gene returned by provider | Absent → `NOT_OBSERVED` |
| `PROJECT_DOMINANCE_V1` | `max(affected)/sum(affected)` over observed projects | ≥2 observed projects, sum>0 | Observed only; no extrapolation |

## K. Proposed Jev projection (`jev-state-projection-v1`)

A deterministic, size-bounded JSON projection built only from StatisticalState fields; persisted with `projection_version`, `source_state_id`, `source_state_hash`, `projection_hash`, artifact ref and the included-field contract.

```json
{
  "projection_version": "jev-state-projection-v1",
  "entity": {"gene_id": "...", "symbol": "TP53", "biotype": "protein_coding", "cancer_census": true},
  "scope": {"projects": ["TCGA-CHOL", "..."], "modalities": ["mutation_counts", "expression_summary"],
            "expression_unit": "log2(UQFPKM+1)", "workflow": "STAR - Counts",
            "examined_case_frame": "ALL_CASES_LE_250", "selection_bias": "genes discovered from provider top-mutated ranking per project"},
  "project_observations": [
    {"project_id": "TCGA-CHOL", "cases_examined": 51, "cases_with_ssm": 51,
     "cases_with_expression": 44, "affected_cases": 12,
     "expression_local": {"median": 2.9, "sample_sd": 0.4, "n_finite": 44, "n_missing": 7},
     "expression_provider": {"median": 2.8, "stddev": 0.3}}
  ],
  "cross_project": {"projects_with_mutation_observation": 8, "projects_with_expression_observation": 7,
                    "affected_total": 214, "top_project_share": 0.41,
                    "expression_median_range": [1.2, 5.6], "coverage_imbalance": true},
  "missingness": ["TCGA-X has no SSM data", "3 cases lack expression values in TCGA-Y"],
  "limitations": ["Counts are provider-defined; no matched denominator; no callable-negative claim.",
                  "Provider expression stddev estimator convention UNVERIFIED.",
                  "Gene set is provider-rank selected; selection bias applies."],
  "eligible_followups": []
}
```

## L. Proposed minimal wide Jev question set (`wide-v2`, Phase 3)

Only questions answerable from the actual projection are retained. `multimodal_convergence`, `direction_reversal`, and `followup_value` are excluded: the state has no signed effects, no defined cross-modal proposition, and no registered eligible follow-up. `Score` returns when Phase 4 registers executable actions.

| ID | Primitive | Instruction (full meaning in the definition, not the ID) | Applicability |
|---|---|---|---|
| `warrants_deeper_investigation` | Noul | Does the supplied gene-level cross-project mutation count and expression summary profile, with its coverage context, warrant a bounded deterministic follow-up investigation? | ≥1 usable observation |
| `mutation_project_exception` | Noul | Does at least one supplied project depart materially from the dominant cross-project pattern of affected-case counts? | ≥3 projects with mutation observations |
| `expression_project_exception` | Noul | Does at least one supplied project depart materially from the dominant cross-project expression pattern (median or dispersion)? | ≥3 projects with local expression summaries |
| `coverage_explains_apparent_difference` | Noul | Is the apparent cross-project difference plausibly explained by unequal coverage or missingness rather than a biological difference? | coverage imbalance flag |
| `likely_fragile` | Noul | Does the supplied dominance and coverage context indicate the apparent cross-project pattern is fragile — dependent on one project or on incomplete coverage? | ≥2 projects with observations |
| `pattern_type` | Choice | Which supplied pattern description best fits the observed evidence? Roster: `WIDESPREAD_RECURRENCE`, `PROJECT_SPECIFIC_EXCEPTION`, `WEAK_DISTRIBUTED_SIGNAL`, `NO_COHERENT_PATTERN`, `DATA_QUALITY_CONCERN`, `INSUFFICIENT_EVIDENCE`. | ≥1 usable observation |

All six are asked in one request per state; they are independent and cannot see one another’s answers.

Deterministic wide policy (`wide-policy-v1`): `warrants_deeper_investigation` descending, then `likely_fragile` ascending, then `pattern_type` class priority, then `state_hash` ascending; top-K (≤3) admitted as `WIDE_EVALUATED` candidates. Raw dimensions are persisted; the deterministic baseline ranking is retained separately for comparison.

## M. Proposed Phase 2 scope

**2A — transport, capture, contract verification.** `GDCTransport` (single socket owner, host/endpoint/method allowlists, no auth, no redirects, streamed reads with per-response and per-run byte caps, attempt ledger, response publication and hashing, cache, pagination ledger), strict parsers for the admitted endpoints, budget tables (schema 3), contract-capture command that reproduces the research captures, adversarial offline tests, and the open-access security tests.

**2B — mutation + coverage lane.** Project inventory → deterministic scope (up to 8 projects with 50–250 cases, sorted by `(case_count, project_id)`) → case manifests (one complete page each) → discovery (`top_mutated_genes_by_project`, ≤20/project) → gene selection (up to 6 recurrent genes appearing in ≥2 projects ordered by appearance count, affected total, gene ID; then round-robin by provider rank across projects to 10 total) → gene resolution (`/genes`) → gene-specific counts (`top_cases_counts_by_genes`, ≤100 genes) → SSM coverage (`mutated_cases_count_by_project`, unfiltered) → deterministic methods → StatisticalStates. The recurrence + round-robin rule was added after the first live sweep produced a locus-clustered gene set; it is deterministic and documented in the run’s selection artifact.

**2C — expression lane.** Availability per project; local values TSV per project (`tsv_units=uqfpkm`, ≤10 selected genes) with `EXPRESSION_LOG2_SUMMARY_V1`; provider `gene_selection` retained separately; coverage folded into the same states.

Phase 2 acceptance gate is §25 of the task: real bounded anonymous calls, immutable captures, strict parsers, explicit populations, ≥1 valid method, reproducible states, preserved missingness, API/UI inspection, zero Jev and zero LLM calls.

Measured budget envelope for one full slice: ≈44 requests, <2 MiB, no file acquisition — against caps of 150 requests and 64 MiB.

## N. Proposed Phase 3 scope

`JevService.evaluate(projection_ref, question_set, purpose) -> JevEvaluation` behind one adapter; owned `JevNoulAnswer`/`JevChoiceAnswer`/`JevScoreAnswer`/`JevEvaluation` contracts with fail-closed validation; projection builder and versioning; cache keyed on projection bytes + question bytes + resolved model + adapter version; one request per state with the six wide questions; deterministic reranking and bounded promotion; API/UI separation of deterministic facts from Jev judgments; raw judgment vectors preserved; deterministic baseline retained for later comparison. Live TypeSafe calls are authorized for Phase 3 with the provided key supplied via `TYPESAFE_API_KEY` (server-side only); model pinned to `jev-1.13.0`.

## O. KISS architecture review

| Decision | Simpler alternative | Selected |
|---|---|---|
| GDC HTTP | `requests`/`httpx` with hooks | stdlib `http.client` in one transport; no new runtime dependency for Phase 2 |
| Budgets | Separate limiter service | In-process ledger + SQLite rows, short transactions |
| Parsers | Generic schema framework | One explicit function per admitted endpoint |
| Methods | Plugin registry | Dictionary of method definitions + plain functions |
| Projection | Template engine | Plain dict builder + canonical JSON hash |
| Jev adapter | Provider SDK types in domain | One adapter module; owned contracts; minimal HTTP or SDK inside the adapter only |
| Ranking | Learned/weighted composite | Explicit lexicographic policy with persisted raw dimensions |
| State store | New database | SQLite schema 3 extension + immutable JSON artifacts |

## Conclusion — the first real OntoJev research state

> **The first real OntoJev research state should contain: gene-specific cross-project mutation affected-case counts (count-only), exact-case-set local expression summaries in `log2(UQFPKM+1)`, provider expression summaries retained separately, project/case/SSM/expression coverage and missingness, sample-type and workflow comparability context, and full request/response provenance — for a bounded scope of ≤8 projects and ≤10 genes selected by a deterministic recurrence-plus-round-robin rule through the provider ranking lane, with `_score` quarantined as selection metadata and no recurrence fraction, direction, or clinical claim.**

What Jev should **not** see yet: raw GDC JSON, per-case or per-variant records, SSM/CNV occurrence lists, clinical/survival fields, raw expression matrices, provider `_score` values, file-level metadata dumps, or any field whose scientific semantics are not established by §H.
