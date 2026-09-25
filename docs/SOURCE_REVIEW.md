# Source review

Current source authority and transferred limitations after the Stage 3 hard cutover
(2026-09-25). Claims are labeled IMPLEMENTED, PLANNED or UNVERIFIED. The user's current scope
governs actions; current code/tests establish implementation; official provider documentation
plus bounded representative responses establish what can be proposed. Prior-project designs do
not authorize new calls or architecture, and this repository is not an OntoJev template.

## Authority order

1. The user's current request and its stop boundary.
2. The official GDC documentation for GDC provider behavior.
3. The official TypeSafe/Jev documentation for Jev provider behavior.
4. This repository's own contracts and tests for what OntoJev actually does.
5. External repositories for permitted interaction ideas only.

Provider documentation never authorizes installing skills, credentials or making calls.

## GDC

Read the official [API guide](https://docs.gdc.cancer.gov/API/Users_Guide/Getting_Started/),
[search/retrieval documentation](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/)
and [official source repository](https://github.com/NCI-GDC/gdc-docs/tree/develop/docs), including
expression, analysis, CNV and scRNA material. Per-family live `_mapping` responses were inspected
before the corresponding queries. Official documentation supports an endpoint, not every
scientific interpretation of its fields.

The 69-request anonymous campaign is retained in the [capture register](GDC_DISCOVERY_CAPTURES.md)
with canonical recipes, hashes and local metadata location. [GDC strategy](GDC_STRATEGY.md) owns
the reality matrix, field traces and ADMIT NOW/LATER/REJECT decisions. The documented GET survival
request returned 509 donors; older empty-response observations are not a current endpoint
limitation, but the response still does not establish a local survival-analysis contract.

Current GDC documentation vs implementation (IMPLEMENTED unless noted):

| GDC fact | Implementation | Verdict |
|---|---|---|
| Open-access search needs no token; `X-Auth-Token` only for controlled download/submission | One transport with no credential parameter; `/data`, `/manifest`, `/slicing` not routable | MATCH |
| `/status` sample fields `commit`,`status`,`tag`,`version` | `parse_status` reads them; optional `data_release` retained when present, never fabricated | MATCH, with documented gap |
| `/cases` pagination `size`/`from`/`sort`, `count`/`total`/`from`/`pages` | `size ≤250`, `from`, `sort=case_id`; parser validates types/offset; orchestrator fails closed on inconsistent totals/offsets | MATCH |
| `/gene_expression/{availability,values,gene_selection}` shapes; values TSV-only; `tsv_units` one of `uqfpkm`/`median_centered_log2_uqfpkm` | Availability/gene-selection POST bodies and TSV parser match; `tsv_units=uqfpkm`, explicit `format=tsv`; requested-membership, width, duplicate and unrequested-ID checks | MATCH |
| `/analysis/top_cases_counts_by_genes` rejects `format`/`fields` | Builder sends only `gene_ids` | MATCH |
| `/analysis/mutated_cases_count_by_project` → `case_with_ssm.doc_count`; filters silently ignored | Unfiltered `size=0`; reads that path; no filtered calls | MATCH as unfiltered context only |
| `/analysis/survival`, `/ssms`, `/cnvs`, `/segment_cnvs`, `/scrna_seq/gene_expression` exist | Not allowlisted/implemented | DELIBERATE (out of current scope) |
| `/files` metadata with `access=open` | Always filtered; non-open or access-missing records fail closed | MATCH |
| Unknown requested fields warn; some are silently omitted | Parser surfaces `warnings.fields`; requested fields are never assumed present | MATCH |

`Appendix_A/B/C` field support and `top_mutated_genes_by_project` `fields` support were not
re-verified against the field appendix; treat those claims as UNVERIFIED.

## TypeSafe / Jev

The installed `typesafe-ai` skill was read and compared with the
[official skill repository](https://github.com/typesafe-ai/skills) (identical after newline
normalization). The [live documentation index](https://docs.typesafe.ai/llms.txt) was followed
through concepts, primitives, confidence, models, API/Python integration and cookbook patterns.
The unavailable build-guide/autoformat pages were not treated as verified support.
[Jev design](JEV_DESIGN.md) owns the source-linked pattern/adoption matrix;
[questions](JEV_QUESTIONS.md) separates implemented versions from proposals;
[budgets](GDC_BUDGETS.md) separates documented pricing, historical measurements and estimates.
Cookbook examples are illustrative, not LUAD validation.

Current TypeSafe documentation vs implementation (IMPLEMENTED unless noted):

| TypeSafe fact | Implementation | Verdict |
|---|---|---|
| Typed answers, not prose | One adapter; owned contracts; fail-closed validation | MATCH |
| Noul has no separate confidence | Contract accepts `probability_yes` only | MATCH |
| Choice ≤255 options; Score 2–10 ordered levels | Question definitions validated at import | MATCH |
| Same-state independent questions run together | One `system_one` call per state with the whole question set | MATCH |
| Confidence is distribution concentration, not permission | Policy combines raw dimensions deterministically | MATCH |
| Provider failures need stable handling | Typed provider error classification; persisted failed evaluations | MATCH |
| SDK retries | Explicitly disabled (`RetryPolicy(max_retries=0)`) | MATCH |
| Model `jev-1.13.0`, 64k context, 32k state budget | Pinned model; 64 KiB projection byte cap | MATCH |
| Credentials server-side only | Key read from env at call time; `.env.local` loader never logs values | MATCH |
| Immutable resolved-model identity | OpenRouter adapter checks only non-blank identity | PLANNED tightening |

Carried TypeSafe unknowns (UNVERIFIED): exact `confidence` formula; server timeout; maximum
question count; state byte limit; 429 body shape; no cost field in responses; no idempotency
key; no seed/temperature control (`jev-1.13.0` is documented as stable, not guaranteed
deterministic). Documented model limits and pricing are subject to change and are not account
guarantees.

## Jev opportunity assessment (narrow judgment instead of fragile code)

The ownership rule is unchanged: Jev never computes a measurement, never writes a measured field,
and never authorizes an endpoint or action. Every opportunity consumes values that code already
extracted and returns a judgment Python policy may use.

| Fragile code today | Judgment opportunity | Primitive | Guardrail | Status |
|---|---|---|---|---|
| Expression workflow/strategy comparability is raw string equality over `analysis.workflow_type` / `experimental_strategy` | “Do these two labels describe the same expression quantification pipeline?” over code-extracted labels | Noul per pair or Choice over supplied labels | Annotation only; the deterministic `comparability` field is never overwritten; no label invented | PLANNED |
| Canonical open expression file per case is not selected; only workflow strings are collected | “Which of these code-extracted open file IDs is the canonical quantification file for this case?” | Choice over supplied file IDs | Choice only among supplied IDs; code validates membership and keeps provenance | PLANNED |
| Hypothesis text may mention genes | “Which of these code-retrieved `/genes` candidates does this mention refer to?” | Choice over supplied Ensembl IDs | Ensembl ID stays authoritative; Jev selects, never invents an ID | PLANNED |
| Clinical fields carry `Not Reported`/`NOS` variants | Normalize to a code-supplied dictionary value | Choice over supplied dictionary values | No clinical measurement from Jev; code owns the dictionary | PLANNED |
| Single-cohort evidence quality, coherence, confounding, uncertainty and investigation value | `wide-v3` over the typed single-cohort projection | Six Nouls + closed Choice | Code-owned applicability and deterministic admission/abstention; no measured field is model-owned | IMPLEMENTED; incremental decision value UNVERIFIED |
| Revision reliability, sufficiency, next-step warrant and stopping | `deep-v1` over the immutable revision plus eligible registered actions | Four Nouls + closed Choice | Python policy records the move; dispatch needs separate authorization | IMPLEMENTED; thresholds uncalibrated |
| Generated-hypothesis testability and overclaim | `hypothesis-v2` over the bounded hypothesis projection | Two Nouls + closed Choice | Review only; generated text is never evidence | IMPLEMENTED; live critique PASSED for the bounded 2026-09-25 case (2 of ≤3 reviews) |

Explicit **non-opportunities** (must stay deterministic code): JSON/TSV parsing and numeric
values, population membership and counts, missingness, coverage arithmetic, `access` open/closed
classification, pagination/offset/total consistency, request hashes, eligibility, evidence
integrity and budgets. Asking Jev for any of these would violate the measurement boundary.

## Transferred findings, limitations and safety requirements

Transferred from the retired Stage/plan/review/audit documents before deletion. Each item is
current unless labeled otherwise; none preserves a historical architecture instruction.

### Safety and boundaries

- IMPLEMENTED: exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may carry a
  provider authorization header; the GDC tree contains zero authentication literals and the
  GDC boundary is asserted separately. The credential is environment-only and never persisted,
  logged or placed in a request body or record.
- IMPLEMENTED: GDC attempt finality — every attempt that started reaches a terminal ledger status,
  including a storage/publish failure after the body was read.
- PLANNED: acquisition-capable or measurement-producing actions require a new explicit action
  contract (question, unit, eligibility, fixed request plan) plus pessimistic budget reservation
  before sending. No such action is registered today; model/generated output may never supply an
  endpoint or query.
- IMPLEMENTED boundary: a registered action deliberately inspects the serialized record contract
  of its declared input kind (a `StatisticalState` or an `EvidenceState`); the action does not
  become a second untyped reader of runtime state. Provider identifier maps and the resolved
  project frame are retained so future reductions can reuse typed records; retaining them does
  not change any version semantics.
- PLANNED: whole-attempt GDC deadlines are not implemented. A peer sending data before the socket
  timeout can keep an attempt alive; per-attempt terminal status and per-response/run byte caps
  bound the damage.
- PLANNED: a total paid-model spend gate and shared attempt/token/spend reservation are absent.
  TypeSafe SDK retries are disabled, so logical evaluations correspond to at most one HTTP
  attempt; failed-attempt billing behavior remains unknown, not zero.
- PLANNED (low): repeated identical GDC cache hits collapse into one RunEvent because the
  idempotency key uses only the request hash.
- PLANNED (low, apps/web only): the default Playwright origin in `apps/web` conflicts with the
  default API CORS origin; current browser acceptance has its own configuration under
  `tests/browser/` and is UNVERIFIED in this environment.

### Evidence and identity

- IMPLEMENTED limitation: structural validation (schema, hash, binding) does not prove source
  authenticity or the scientific truth of a supplied number; codecs do not re-execute methods.
- IMPLEMENTED limitation: integrity checks describe provenance and consistency, not biology.
  A verified check is not biological evidence, and `COMPLETE`/stop decisions concern bounded
  work, not scientific truth.
- UNVERIFIED: case-to-sample resolution for expression values; no sample-matched cross-modal
  claim is made. GDC release atomicity across requests is also UNVERIFIED; reproducibility means
  replay from retained responses and hashes.
- UNVERIFIED: provider expression `median`/`stddev` estimator convention. A historical two-case
  capture is consistent with a population denominator (`INFERRED_POPULATION_SD_UNVERIFIED`);
  `gene_selection` may omit cases silently. Provider summaries never drive policy.
- UNVERIFIED: `mutated_cases_count_by_project` silently ignored a supplied filter in a
  historical probe, so the runtime forbids filtered calls. Unknown requested fields produce a
  `warnings.fields` notice and may be silently omitted, so a requested field is never assumed
  present.
- UNVERIFIED: `files.access` is assigned by the API/platform, not a dictionary enum; `ssm`,
  `gene`, `cnv` and occurrence entities are API-layer records absent from `gdcdictionary`.
  Generated model files track a development branch rather than a release tag.
- UNVERIFIED: `/analysis/survival` returned 509 LUAD donor records for a documented GET request,
  but time origin, censoring and exclusion semantics are not audited, so no survival estimator is
  admitted.

### Runtime, API and static quality

- PLANNED (medium): RunEvent payload shape is not validated per event type; a registered event
  can be persisted with `data={}`, and `message` uses a character count rather than UTF-8 bytes.
- PLANNED (low): undeclared query parameters are silently ignored by FastAPI routes; strict
  parameter handling belongs with OpenAPI cleanup. Wrongly typed cursor fields can produce a 503
  instead of a 422.
- PLANNED (low): OpenAPI metadata disagrees with `/api/system`; `apps/api/main.py` keeps the
  historical title/version. `/api/system` still reports the stale `phase: 3` label and a cursor
  reason mentioning “Phase 2 bounded sweeps”; provider flags are environment-derived.
- PLANNED (low): the generic `/api/artifacts/{artifact_id}` route omits `X-Artifact-Id` /
  `X-Artifact-SHA256` (state/evidence/dossier detail expose them).
- PLANNED (low): `show --events` stops at 500 events.
- IMPLEMENTED observation: the Wide projection's `eligible_followups` list is always empty
  because no registered action declares a `STATISTICAL_STATE` input other than the integrity
  check, which is not registered as a wide follow-up; emptiness is not evidence that no action
  exists. Deep projection artifacts are published per revision but are not rows in the
  state-keyed `jev_projections` table.
- PLANNED (low): the package version (`pyproject.toml` 0.2.0) and the API contract version
  (3.0.0) are separate identities; align them only if distribution metadata requires it.
- PLANNED (low): tests/jev/test_typesafe_adapter.py replaces `typesafe_sdk` in `sys.modules`; a
  small injected client/factory protocol is preferable when that test is next touched.
- PLANNED (low): an unused `EvaluationContext` seam and the duplicated wide/general evaluation
  lifecycle may be consolidated when touched, without changing question versions.

### Proposed, unregistered work

- PLANNED: candidate action IDs `STRATIFY_BY_PROJECT_V1`, `LEAVE_ONE_PROJECT_OUT_V1`,
  `CHECK_MISSINGNESS_V1`, `OUTLIER_SENSITIVITY_V1` and `COMPARE_MODALITIES_V1` are proposals,
  not registered actions. Project stratification and leave-one-project-out are NOT APPLICABLE to
  the single-cohort production scope. `CHECK_MISSINGNESS_V1` is partly redundant with the
  `EXPRESSION_COVERAGE_ARITHMETIC` check of `CHECK_EVIDENCE_INTEGRITY_V1`; before registration it
  needs a non-redundant, independently reproducible operation from retained evidence.
- PLANNED: a bounded independent expression arm and a narrow CNV lane require their own official
  mapping review, fixed request plans, immutable fixtures and acceptance gates.
- UNVERIFIED: no demonstrated sample-matchable mutation-negative or CNV-neutral reference set
  exists in the admitted endpoints; recurrence rates, association tests and survival effects
  remain ineligible.

## Remaining UNVERIFIED

- No live GDC, TypeSafe/Jev or OpenRouter call was made in this environment; verbatim live
  behavior claims come from retained captures/history, not a fresh run.
- Browser acceptance at `tests/browser/` exists and is a CI job; it was not executed here.
- Provider pricing/quota, account limits and scientific value of Jev remain unverified.
- `Appendix_A/B/C` field support was not re-verified against the field appendix.

## Next sequence

Indexed systematic discovery is the next separately authorized Stage 4 task: bounded ordered
gene universe, cheap indexed mutation reduction, immutable fixtures and its own acceptance gate.
Stages 5–9 (independent expression arm, narrow CNV lane, descriptive actions, prospective
evaluation, conditional inferential extensions) remain as indexed in the
[roadmap](DISCOVERY_ROADMAP.md). Engineering success cannot establish Jev incremental value; a
labelled, human-reviewed corpus is required.