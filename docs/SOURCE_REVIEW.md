# Source review and pre-Phase-3 readiness audit

Review date: 2026-09-23. Current `main` HEAD: `60acf6b` (audit changes follow it).
This document records the provider/design authorities, what was actually read, how the
implemented code compares, and the Jev opportunities found. It is the source review for the
targeted pre-Phase-3 readiness audit; it does not implement Phase 3 or Phase 4.

## Authority order

1. The user's current request and its stop boundary.
2. The official GDC documentation for GDC provider behavior.
3. The official TypeSafe/Jev documentation for Jev provider behavior.
4. This repository's own contracts and tests for what OntoJev actually does.
5. CancerHawk/CancerJEV repositories for permitted interaction ideas only.

Provider documentation never authorizes installing skills, credentials, or making calls.

## GDC source of truth (only source)

GDC provider behavior is established **only** from the official GDC documentation repository:

**https://github.com/NCI-GDC/gdc-docs/tree/develop/docs** (branch `develop`)

Files read for this audit (via `raw.githubusercontent.com`/GitHub API on `develop`):

| GDC document | Facts used |
|---|---|
| `API/Users_Guide/Getting_Started.md` | Endpoint families (`status`, `projects`, `cases`, `files`, `genes`, `analysis`, `gene_expression`); `X-Auth-Token` is required only for controlled download and submission, never for open-access search |
| `API/Users_Guide/System_Information.md` | `/status` sample fields `commit`, `status`, `tag`, `version`; a `/v0/notifications` endpoint exists |
| `API/Users_Guide/Data_Analysis.md` | `/genes`, `/gene_expression/{availability,values,gene_selection}`, `/analysis/{top_cases_counts_by_genes,top_mutated_genes_by_project,top_mutated_cases_by_gene,mutated_cases_count_by_project,survival}`, `/ssms`, `/cnvs`, `/segment_cnvs`, `/scrna_seq/gene_expression`; exact expression request/response shapes; `tsv_units` is exactly one of `uqfpkm`/`median_centered_log2_uqfpkm`; values are TSV-only; `selection_size`/`min_median_log2_uqfpkm`; gene expression is protein-coding only; `top_cases_counts_by_genes` rejects `format`/`fields`; `case_with_ssm.doc_count` |
| `API/Users_Guide/Search_and_Retrieval.md` (read, partly truncated) | Search/filter JSON (`op`/`content`), `fields`, `format`, `size`, `from`, `sort`, pagination block shape (`count`,`total`,`size`,`from`,`sort`,`page`,`pages`) |
| Repository tree (`docs/` and `docs/API/Users_Guide/`, `docs/Data/Bioinformatics_Pipelines/`) | Confirms the reviewed file set and that expression/CNV/survival pipelines are documented |

`API/Users_Guide/Appendix_A_Available_Fields.md`, `Appendix_B`, `Appendix_C`, and
`Data/Bioinformatics_Pipelines/Expression_mRNA_Pipeline.md` were **referenced but not read in
full** in this pass; field-level claims that depend on them remain UNVERIFIED here.

The previously used local `API_UG.pdf` and the master specification are **superseded** as GDC
authority by the repository above and are retained only as historical Phase 0 inputs.

## TypeSafe/Jev source of truth

TypeSafe/Jev behavior is established from the live documentation site:

**https://docs.typesafe.ai** — starting from `https://docs.typesafe.ai/llms.txt`

Pages read for this audit:

| TypeSafe document | Facts used |
|---|---|
| `concepts/system-one.md`, `concepts/how-to-build-with-system-one.md` | Jev returns typed judgments/probabilities, not generated text; code owns workflow |
| `primitives.md`, `primitives/noul.md`, `primitives/choice.md`, `primitives/score.md` | Noul = probability of yes, no separate confidence; Choice = one of a defined set with distribution + confidence; Score = ordered levels with probability-weighted position + confidence |
| `concepts/state.md` | Named JSON fields; reference nested paths with backticks; one narrow judgment per question; same-state independent questions run together |
| `confidence.md` | Confidence summarizes distribution concentration, not workflow correctness or permission to act |
| `models.md` | `jev-1.13.0` (alias `jev-latest`); 64k-token context (32k state + longest question); ~250k tok/s; 1200 requests/min; $42/Btok input, output free (**DOCUMENTED, not a contract**) |
| `api.md`, `sdk/python.md` | HTTP API and `typesafe-sdk`; `client.system_one(state=…, questions={…})`; `TYPESAFE_API_KEY`; SDK retries |
| `patterns/fan-out.md`, `patterns/composite-scoring.md` | Ask independent questions over the same state in one request; score dimensions once and let code weight them |
| `cookbooks/pre_parsed_value_extraction_cookbook.md` | Code finds candidate values/spans, a judgment selects the intended one, then code copies/normalizes it; Choice limit 255 |
| `cookbooks/autoformat.md` (structure recovery), `cookbooks/rerank_typesafe.md`, `cookbooks/citation_check.md`, `cookbooks/sde_cascade.md` | Structure recovery, per-candidate relevance scoring, claim verification, verify-then-escalate |
| Jaggedness guidance (via the skill index) | Do not assume arithmetic or complementary semantic answers |

The previously used local `typesafe jev docs with cookbook.docx` is **superseded** as Jev
authority by the live site and is retained only as a historical Phase 0 input.

## Reference-ideas repositories (non-authority)

Read for permitted ideas only, not as provider or architectural authority:

- CancerHawk `b87e98c`: run-card polling/event UI hierarchy (adapt to `ResearchRun`; no capped
  history, no payment concepts, no Pages Router).
- CancerJEV `853b316`: finite/range validation and BH-adjustment references, cross-modal test
  patterns, GDC open-file admission lessons (no Cohort/Finding model, no worker architecture).

## GDC documentation vs implementation (audit)

| GDC fact | Implementation | Verdict |
|---|---|---|
| Open-access search needs no token; `X-Auth-Token` only for controlled download/submission | One transport with no credential parameter; `/data`, `/manifest`, `/slicing` not routable | MATCH |
| `/status` sample: `commit`,`status`,`tag`,`version` | `parse_status` reads `commit`/`status`/`tag` (and optional `data_release`); inventory also records `release_commit`/`release_tag` | MATCH, with a documented gap: the live API also returns `data_release` (present in retained captures) though the docs sample omits it; `data_release` stays optional and never fabricated |
| `/cases` pagination `size`/`from`/`sort` with `count`,`total`,`from`,`pages` | `cases_request` sends `size ≤250`, `from`, `sort=case_id`; parser validates pagination types and requires offset/consistency; orchestrator fails closed on inconsistent totals/offsets | MATCH |
| `/gene_expression/availability` POST `{case_ids,gene_ids}` → `cases.details[]`, `genes.details[]` | `expression_availability_request` and `parse_expression_availability` use exactly these shapes and reject unrequested identifiers | MATCH |
| `/gene_expression/values` is TSV-only; `tsv_units` exactly one value; header `gene_id` + case columns; requested cases may be absent | `expression_values_request` sends `tsv_units=uqfpkm` (and now explicit `format=tsv`); parser validates header, width, duplicates, unrequested IDs and records `missing_case_ids` | MATCH (explicit `format=tsv` added) |
| `/gene_expression/gene_selection` uses `selection_size` (max genes) and is protein-coding only | `expression_gene_selection_request` sets `selection_size=len(gene_ids)`; parser accepts a returned subset and records missing genes | MATCH |
| `/analysis/top_cases_counts_by_genes` rejects `format`/`fields` | `gene_case_counts_request` sends only `gene_ids` | MATCH |
| `/analysis/mutated_cases_count_by_project` → `case_with_ssm.doc_count` | `parse_mutated_cases_count` reads that path | MATCH |
| `/analysis/survival`, `/ssms`, `/cnvs`, `/segment_cnvs`, `/scrna_seq/gene_expression` exist | Not allowlisted/implemented | DELIBERATE (out of current scope; no Phase 4 work) |
| `/files` metadata with `access=open` | `files_expression_request` filters `access=open`; a returned non-open or **access-missing** record fails closed | MATCH (access-missing now fails closed) |

## TypeSafe documentation vs implementation (audit)

| TypeSafe fact | Implementation | Verdict |
|---|---|---|
| Typed answers, not prose | One adapter; owned contracts; fail-closed validation | MATCH |
| Noul has no separate confidence | Contract accepts `probability_yes` only | MATCH |
| Choice ≤255 options; Score 2–10 ordered levels | Question definitions are now validated at import against these limits | MATCH (validation added) |
| Same-state independent questions run together | One `system_one` call per state with the whole question set | MATCH |
| Confidence is distribution concentration, not permission | Wide policy combines raw dimensions deterministically; confidence not used as correctness | MATCH |
| SDK retries; terminal provider failures need stable handling | Adapter now classifies 401/403, 422, 429, 529 into typed provider error codes | MATCH (classification added) |
| Model `jev-1.13.0`, 64k context, 32k state budget | Pinned model; projection byte cap 64 KiB keeps state well inside 32k tokens | MATCH |
| Credentials server-side only | Key read from env at call time; `.env.local` loader never logs values | MATCH |

## Jev opportunity assessment (intelligent judgment instead of fragile code)

The skill asks where a narrow semantic judgment can replace complex parsing or brittle string
logic. The ownership rule is unchanged: **Jev never computes a measurement, never writes a
measured field, and never authorizes an endpoint or action.** Every opportunity below consumes
values that code already extracted and returns a judgment that Python policy may use.

| Fragile code today | Judgment opportunity | Primitive | Guardrail | Status |
|---|---|---|---|---|
| Expression workflow/strategy comparability is raw string equality over `analysis.workflow_type` / `experimental_strategy` (labels drift across releases, e.g. `STAR - Counts` variants) | "Do these two labels describe the same expression quantification pipeline?" over code-extracted labels | Noul (one per candidate pair) or Choice over supplied labels | Annotation only; the deterministic `comparability` field is never overwritten; no label is invented | PLANNED (Wide redesign / Phase 4) |
| Canonical open expression file per case is not selected; only workflow strings are collected | "Which of these code-extracted open file IDs is the canonical quantification file for this case?" | Choice over supplied file IDs (pre-parsed value extraction) | Choice only among supplied IDs; code validates membership and keeps provenance | PLANNED |
| Phase 6 hypothesis text will need to resolve gene mentions | "Which of these code-retrieved `/genes` candidates does this mention refer to?" | Choice over supplied Ensembl IDs | Ensembl ID stays authoritative; Jev selects, never invents an ID | PLANNED (Phase 6) |
| Future clinical fields (`ajcc_pathologic_stage`, `tumor_grade`, `primary_diagnosis`) carry `Not Reported`/`NOS` variants | Normalize to a code-supplied dictionary value | Choice over supplied dictionary values | No clinical measurement from Jev; code owns the dictionary | PLANNED (Phase 4+, out of scope) |
| Single-cohort evidence quality, coherence, confounding, uncertainty and investigation value | `wide-v3` over the v2 single-cohort projection | Six Nouls + closed Choice | Code-owned applicability and deterministic admission/abstention; no measured field is model-owned | IMPLEMENTED (Phase 3); incremental decision value remains unverified |

Explicit **non-opportunities** (must stay deterministic code): JSON/TSV parsing and numeric
values, population membership and counts, missingness, coverage arithmetic, `access` open/closed
classification, pagination/offset/total consistency, request hashes, and budgets. Asking Jev for
any of these would violate the measurement boundary.

## Readiness findings and hardening applied in this audit

- **H1 (config):** added a stdlib `.env.local` loader (`cancerjev.config.load_local_env`), a
  gitignored `.env.local`, and a tracked `.env.local.example` covering `TYPESAFE_API_KEY`,
  `OPENROUTER_API_KEY` (future Phase 6 only), operational `CANCERJEV_*` settings, and the
  frontend URL. Real environment variables win; blank values and invalid names are ignored;
  values are never logged.
- **H2 (GDC request):** `/gene_expression/values` now sends explicit `format: tsv`, matching the
  documented example.
- **H3 (GDC parser):** a UTF-8 BOM before the TSV header is tolerated; a `/files` record with no
  explicit `access` now fails closed as non-open (previously only an explicit non-`open` value
  counted).
- **H4 (Jev contract):** question definitions are validated at import against the documented
  limits (Choice ≤255, Score 2–10, known primitive/applicability, non-empty text).
- **H5 (Jev provider):** terminal provider failures are classified into
  `PROVIDER_AUTH`/`PROVIDER_VALIDATION`/`PROVIDER_RATE_LIMIT`/`PROVIDER_OVERLOADED` so Python
  policy can defer instead of treating them as a scientific result.
- **H6 (budget):** the documented 5 MiB per-response cap already matches the code default
  (corrected in the prior task); no further change.
- **H7 (docs):** GDC/TypeSafe authorities, this audit, and the opportunity plan are recorded here;
  `README`, `ARCHITECTURE`, `JEV_DESIGN`, `JEV_QUESTIONS`, `GDC_STRATEGY`, `GDC_BUDGETS`,
  `TESTING`, and `IMPLEMENTATION_STATUS` are updated to match.

## Remaining UNVERIFIED

- No live GDC, Jev or LLM call was made for this audit; live behavior is from retained
  2026-09-22 captures only.
- `Appendix_A/B/C` field support and `analysis/top_mutated_genes_by_project` `fields` support were
  not re-verified against the field appendix.
- The presence of `data_release` in `/status` across deployments is not guaranteed by the docs
  sample; code treats it as optional.
- Hosted CI, frontend typecheck/build/e2e, provider pricing/quota, and scientific value of Jev
  remain unverified.

## Next sequence

This audit is step 1. The following remain separate tasks (see `IMPLEMENTATION_STATUS.md`):

```text
1. targeted pre-Phase-3 readiness audit            ← this document (complete)
2. TCGA-LUAD Wide Jev semantic/admission redesign (implemented; `docs/PHASE_3_PLAN.md`)
3. baseline-vs-Jev incremental-value evaluation (next; not yet performed)
4. one Phase-4 vertical slice: E0 → one registered follow-up → E1
5. bounded next-candidate autonomous iteration
6. bounded LLM hypothesis generation + Jev hypothesis evaluation
```
