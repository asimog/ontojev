# API-first GDC strategy

Authority: live anonymous captures in `data/gdc-contract-captures-2026-09-22/` (30 captures, 80,653 bytes; release 46.0, API tag 8.5.0), the official `NCI-GDC/gdc-docs` documentation at revision `157cef9dac084ce30720f0ad507cd54017263be7`, official pipeline pages, and the supplied `API_UG.pdf` as historical reference. Where the PDF and live behavior differ, the live capture wins and the difference is recorded. **VERIFIED** = retained live capture; **DOCUMENTED** = official source; **UNVERIFIED** = not established. Documentation is not an integration test; the contract-capture command reproduces the verification.

Before any file acquisition, evaluate in order: (1) analysis endpoint, (2) metadata/search, (3) bounded expression endpoint, (4) bounded SSM/CNV occurrences, (5) another small targeted query. **OntoJev performs no GDC file acquisition.** `/data`, manifests, BAM/VCF/MAF/FASTQ, archives and `gdc-client` are outside the transport allowlist. If a requirement needs a large file, the answer is `UNSUPPORTED_IN_V1`.

## Phase 2 admitted slice (the smallest useful evidence set)

| Lane | Endpoints | Bound | Purpose |
|---|---|---|---|
| Release identity | `GET /status` | 1 request | Provenance: release, commit, tag |
| Scope inventory | `GET /projects` | 1 request, size ≤100 | Deterministic project selection and composition context |
| Population frame | `GET /cases` | 1 request per project, size 250, `sort=case_id` | Complete examined-case frame for projects with ≤250 cases |
| Open provenance | `GET /files` | ≤2 requests, **`access=open` mandatory** | Expression workflow/strategy comparability |
| Entity identity | `GET /genes` | 1 request, ≤100 gene IDs | Symbol, biotype, cancer-census flag |
| Discovery (selection only) | `GET /analysis/top_mutated_genes_by_project` | 1 request per project, size ≤20 | Candidate gene universe; `_score` is quarantined ranking metadata |
| Mutation counts | `GET /analysis/top_cases_counts_by_genes` | 1 request, `gene_ids` ≤100 | Gene-specific per-project affected-case counts |
| Mutation coverage | `GET /analysis/mutated_cases_count_by_project` | 1 request, `size=0`, **no filters** | Per-project `case_with_ssm` availability |
| Expression coverage | `POST /gene_expression/availability` | 1 request per project, ≤250 cases × ≤10 genes | Per-case presence flags |
| Expression provider summary | `POST /gene_expression/gene_selection` | 1 request per project, ≤250 cases | Provider median/stddev retained separately |
| Expression local summary | `POST /gene_expression/values` | 1 request per project, `tsv_units=uqfpkm`, ≤250 cases × ≤10 genes | Exact per-case UQFPKM for the local deterministic method |

Every admitted request passes the endpoint admission gate: documentation review, open-access review, live contract check, scientific-semantics check. The full matrix, including rejected endpoints, is in `docs/GDC_JEV_FIT_ANALYSIS.md` §G.

## Endpoint behavior confirmed live

- `top_mutated_genes_by_project` returns `gene_id`, `symbol`, `_score`. Documentation states `_score` “does not represent the number of mutations in a given gene, but a calculation that is used to determine which genes have the greatest number of unique mutations.” It is stored only as `provider_discovery_rank`.
- `top_cases_counts_by_genes` returns a raw aggregation envelope: `hits.total`, `aggregations.projects.buckets[]` with `doc_count`, `genes.my_genes.gene_id.buckets[].{key,doc_count}`; multi-gene requests are verified live (3 genes → per-project gene buckets); completeness fields `timed_out`, `_shards`, `doc_count_error_upper_bound`, `sum_other_doc_count` are preserved. An absent project or gene bucket is `NOT_OBSERVED`, never zero.
- `mutated_cases_count_by_project` documents `case_summary.case_with_ssm.doc_count`. A live call with a `case.project.project_id` filter returned empty buckets while the unfiltered call returned 93 complete project buckets; filtered calls are therefore forbidden by policy, not merely discouraged.
- `gene_expression/values` returns TSV only, header `gene_id` + one column per case UUID, one row per gene; `tsv_units` is exactly one of `uqfpkm` or `median_centered_log2_uqfpkm`. Values are joined by returned labels, never by request order.
- `gene_expression/gene_selection` requires exactly one of `gene_ids` or `gene_type=protein_coding`; the provider median/stddev estimators are not documented (live two-case capture is consistent with a population denominator).
- `/cases` field selection warns through `warnings.fields` for unrecognized fields instead of failing; parsers surface warnings as quality metadata and never assume a requested field exists.
- Per-endpoint field discovery is `GET /<endpoint>/_mapping` (verified for `/projects`); the bare `/_mapping` is 404. Mapping output is used for contract verification only.
- `/analysis/survival` is documented as GET with a JSON array of filter groups; GET and POST probes both returned empty donor sets for attempted shapes, so the contract is not established and the endpoint stays disabled.

Search filters use `{op,content:{field,value}}` and compound `{op:"and",content:[...]}`. `exclude` differs from `excludeifany` for multivalued properties. Endpoint-specific field prefixes differ (`case`, `cases`, `gene`, `genes`); no global field translation is reused blindly. Standard search pagination uses `from`/`size` and `data.pagination`; aggregations need their own parser and completion rules. Missing pagination is not proof of completion. `timed_out`, shard failures, aggregation error bounds and `sum_other_doc_count` are preserved; a nonzero error/truncation makes totals partial.

## Inventory, scope selection and traversal

Phase 2 selects a deterministic scope from the bounded inventory: projects with `50 ≤ summary.case_count ≤ 250`, ordered by `(case_count, project_id)`, up to 8. This keeps every examined case inside one complete page and gives matched populations for both lanes without sampling bias. Gene selection is also deterministic: up to 6 recurrent genes (appearing in ≥2 projects’ provider top-20) ordered by appearance count, affected-case total and gene ID, then round-robin by provider rank across projects to 10 genes total. The selected roster, inventory hash and selection rule are recorded in `PROJECT_SCOPE_SELECTED` and the selection artifact; new projects join a later run. There is no cross-run discovery cursor in Phase 2 because the sweep is a self-contained bounded run; the cursor contract remains documented for later continuous mode.

Case collections are deterministic: sorted stable IDs (`sort=case_id`), complete page, persisted frame hash, `eligible_n`, `selected_n` and completeness. If a project exceeded the page, the frame would be labeled a sample rather than the whole project — which is why the 250-case ceiling is part of the selection rule.

Validity prefilter rejects unusable/malformed/provenance-free states; it does not threshold p/q or demand a large effect. Diversity downselection is not needed for the bounded Phase 2 universe (≤10 gene states); the recorded rule for a larger universe remains strata `(project, lane, modality, anomaly_shape, direction)` with stable hash order and a 1,000-state cap. No model judgment occurs before this cap.

Top-k endpoint discovery remains selection-biased even after local filtering. The state records the discovery lane, the examined gene count and the selection bias, and no claim is made that the gene set explores all possible signals.

## Contract capture and reproducibility

The contract-capture command runs the same sole transport with a capture sink and writes one directory per invocation under `data/gdc-contract-captures-<date>/`: the exact response bytes, plus per-request metadata (method, endpoint, normalized parameters/body, HTTP status, response headers, `retrieved_at`, byte count, SHA-256, truncation flag, error, completeness, parser version). Captures are never scientific evidence by themselves; parsers consume them only through the normal pipeline, and every state cites the response artifact hashes it used. Research captures from 2026-09-22 are retained and indexed in `INDEX.json`.

## Scientific limits of the API-first approach

- `case_with_ssm` is source availability context, not proof of whole-genome callable negatives. Matched recurrence denominators require consistent source/filter semantics; absent denominator means count-only evidence. Phase 2 stores counts and coverage separately and never divides them.
- Expression responses omit unavailable cases. Returned labels and an explicit missingness manifest are used; alignment by request order is forbidden.
- Case-level expression may hide sample selection/aggregation. Exact sample resolution, workflow selection and tie-breaking are **UNVERIFIED**; sample-matched cross-modal claims are refused.
- Categorical CNV cannot be passed to a continuous correlation method without a newly defined valid estimator; deferred.
- Survival group semantics (time origin, censoring, group eligibility) and the estimator are not documented; disabled.
- GDC release atomicity across requests and historical replay by a snapshot token are **UNVERIFIED**. Raw responses/hashes and retrieval times are preserved and the `/status` release identity is recorded. Reproducibility means replay from retained inputs, not that a future request returns identical bytes.
- Provider ranking (`_score`) is not comparable across projects and is never treated as science.

The first registered follow-up remains `STRATIFY_BY_PROJECT_V1`, using already-held deterministic observations (Phase 4). Expression-by-mutation, CNV and survival lanes are added only after their eligibility and mapping contracts pass. The registry is not a commitment to implement every proposed method.
