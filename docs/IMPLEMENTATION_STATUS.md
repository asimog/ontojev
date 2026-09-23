# Implementation status

Factual source of truth for the current repository state. The Phase 3 single-cohort semantic and
admission redesign is implemented and validated; see the acceptance and verification records below.

**DONE:** Phase 0 design; Phase 1 offline synthetic vertical slice (verified); the GDC × Jev fit
analysis (`docs/GDC_JEV_FIT_ANALYSIS.md`); Phase 2 real open-access GDC evidence with deterministic
StatisticalStates, scoped to the single TCGA-LUAD cohort; Phase 3 single-cohort projection,
`wide-v3` judgments, deterministic eligibility, explicit Jev admission/abstention, rankings and
bounded candidate promotion; and the first Phase 4 deterministic slice (E0 → one explicitly
selected registered action → immutable E1), reachable only through an explicit operator selection.
**CURRENT:** the architecture is modular and `ResearchSpec`-driven; `LUAD_RESEARCH_V1` is the only
production research specification. **NEXT:** baseline-vs-Jev incremental-value evaluation, then
Deep Jev judgment over an E1 revision and the Python next-move policy. Phase 3 did **not**
demonstrate improved scientific decision quality, and the Phase 4 slice did not make any scientific
claim beyond evidence integrity. Later Phase 4+ work (Jev deep battery, hypotheses, next-candidate
iteration, dossiers) has no runtime implementation.

Phase 1 remains available and separate: `run --fixture demo` still produces the synthetic
dossier run with zero provider calls, and fixture and live records are never mixed.

## What exists (Phase 2 additions)

- **One GDC transport** (`cancerjev/gdc/transport.py`): fixed host `api.gdc.cancer.gov`, endpoint/method allowlist, no authentication by construction (no credential parameter, no token loader, no `Authorization`/`X-Auth-Token` path), no redirect following, `Accept-Encoding: identity` with compressed responses rejected, streamed reads with per-response (5 MiB), per-run byte (64 MiB), request (150), page (10/query), case-ID (250) and gene-ID (100) caps, bounded retries for safe GETs only, a persisted attempt ledger, raw-response publication with SHA-256, and a normalized request cache.
- **Strict parsers** (`cancerjev/gdc/parsers.py`) for the eleven admitted endpoints: required fields and types enforced, `warnings.fields` surfaced, aggregation completeness fields preserved, duplicates and unexpected identifiers rejected, NaN/Infinity rejected, TSV joined by returned labels.
- **Deterministic methods** (`cancerjev/science/methods.py`): `MUTATION_AFFECTED_CASE_COUNT_V1`, `PROJECT_SSM_COVERAGE_V1`, `EXPRESSION_LOG2_SUMMARY_V1`, `EXPRESSION_PROVIDER_SUMMARY_V1`, `PROJECT_DOMINANCE_V1`, each with the full declaration set (population, duplicate rule, estimator, missingness, limitations, provenance). No p-values, no effect sizes, no recurrence fraction, no biological direction.
- **Real StatisticalStates**: one per gene, covering per-project affected-case counts, SSM coverage, local `log2(UQFPKM+1)` summaries, provider summaries retained separately, per-project coverage metrics, cross-project descriptives, missingness, and full source provenance with scientific identity hashing.
- **Research specification + live orchestrator** (`cancerjev/research/specs.py`, `cancerjev/research/live.py`): one frozen production specification, `LUAD_RESEARCH_V1`, owns the reproducible domain/cohort/project and bounded acquisition parameters; deployment `Settings` remains operational only. The orchestrator consumes the specification, selects one exact project, acquires deterministic paginated case frames, batches expression requests within the 250-case endpoint cap, and never pools projects.
- **Contract-capture command** (`python -m cancerjev probe`) using the same transport, writing run-scoped capture directories with request metadata, hashes and an index.
- Persistence schema **4**: `gdc_attempts` (operational ledger), version-qualified `gdc_cache`, `jev_projections`, `jev_cache`, plus declared relational constraints for candidate/evidence/follow-up provenance; earlier schema directories fail with an actionable error instead of migrating.
- New registered events for the GDC lifecycle, scope selection, projections, rankings and evaluation failures; the reducer maintains real GDC request/byte/cache-hit and Jev token usage.

## TCGA-LUAD Phase 2 scientific foundation (2026-09-22)

The generic multi-project sweep was replaced by one explicitly defined cohort: **domain `lung cancer`, cohort `TCGA-LUAD`**. This changes evidence semantics, not the transport, budgets, persistence, artifacts, or Jev architecture.

- **Cohort contract (old → new):** old = "first 8 projects with 50–250 cases ordered by `(case_count, project_id)`", genes pooled across projects by recurrence plus round-robin. New = `TCGA-LUAD` selected by exact `project_id` from the open inventory; genes taken from the cohort's provider top-mutated ranking by provider rank. TCGA-LUAD and TCGA-LUSC are never pooled.
- **Population/missingness:** `Population` now separates `eligible_n` (cohort) from `examined_n` (returned frame); the generic `selected_n`/`observed_n` counts are removed. Each modality result carries explicit `examined_cases`, `assay_available_cases`, `returned_case_columns`, `valid_measurements` and `missing_measurements`. `EXPRESSION_LOG2_SUMMARY_V1` now folds the parser's `missing_case_ids` (examined case columns the provider did not return) into `n_missing`; a fully valid returned subset can no longer report zero missingness.
- **Mutation semantics:** `mutation.absence_semantics` states explicitly that an absent bucket is `NOT_OBSERVED`, not zero, wildtype or a callable negative; no recurrence fraction is computed. `affected_case_total` is `NOT_OBSERVED` (not `0`) when no project has an observed bucket.
- **Completeness:** `quality.acquisition_completeness` (were the requested responses acquired in full?) is now separate from `quality.scientific_sufficiency` (`SUFFICIENT`/`PARTIAL`/`INSUFFICIENT`), with definitions stored in the state.
- **Comparability:** `scope.comparability` carries explicit statuses. `within_cohort = UNVERIFIED` (harmonization/shared membership/empty incompatibility list prove nothing) and `cross_project = NOT_APPLICABLE` for one cohort. No `VERIFIED` status is fabricated.
- **Scientific identity:** discovery rank, provider `_score`, lane ordering, `examined_genes_ref`, the acquisition attempt link (`request_id`/`attempt_no`/`from_cache`) and response artifact ids/timestamps are excluded from `state_hash`; discovery provenance stays visible in `generation.discovery` and `provider_discovery_rank` but does not affect identity. `examined_genes_hash` is deliberately retained as tested-universe context, so a different examined gene set is a different state even when a reported measurement happens to match.
- **Bounded modular acquisition:** TCGA-LUAD remains the only production research specification, with a 1,000-case ceiling and 250-case pages/batches. Case pages fail closed on an over-limit total, inconsistent totals, premature empty pages, cross-page duplicate IDs, or unexpected project IDs. Local expression values and missingness merge by ID across batches. Provider batch medians/stddev are not aggregated; the provider summary is explicitly unavailable when the cohort needs multiple requests.

**Historical v1/v2 issue (resolved in the current implementation).** `wide-v2` and
`jev-state-projection-v1` used cross-project semantics that did not fit the single LUAD cohort.
Current runs use the single-cohort `jev-state-projection-v2` and `wide-v3` set; older records remain
immutable and readable with their original version metadata.

## What exists (Phase 3 additions)

- **Owned Jev contracts** (`cancerjev/jev/contracts.py`): normalized Noul/Choice/Score answers with fail-closed validation (missing/unknown questions, wrong primitive, out-of-range or non-finite probabilities, roster/distribution mismatch, invalid confidence/legend, non-summing distributions). No defaults are fabricated.
- **Versioned question set** (`wide-v3`, six Nouls plus `dominant_limitation` Choice): evidence quality, mutation/expression coherence, coverage confounding, unresolved uncertainty, and investigation value; code-owned applicability and a closed seven-option limitation roster. Canonical definitions are hashed. `wide-v2` is retained only for historical records.
- **Projection** (`jev-state-projection-v2`): compact deterministic JSON for exactly one project, built only from StatisticalState fields, with a single `cohort` block, included-field contract, hard byte cap, and projection hash used as inference identity. Multi-project input fails closed.
- **One adapter** (`cancerjev/jev/typesafe_adapter.py`): the only module that imports the TypeSafe SDK; converts provider objects to plain data immediately; records requested/resolved model, request id, usage and latency.
- **JevService** (`cancerjev/jev/service.py`): projection registration, cache identity (`projection hash + question hash + pinned model identity + adapter version`, policy version excluded), provider call, validation, persistence, and events; cache hits create a new evaluation with `cache_source_evaluation_id` and zero usage. Cache reuse is only attempted for a pinned/versioned model name whose provider resolution equals that name, so a mutable alias is always evaluated and a divergent resolution is never cached.
- **Deterministic ranking and admission** (`cancerjev/research/ranking.py`): `baseline-wide-v2` top-three comparison list has no admission authority. `wide-policy-v2` applies completeness/mutation/expression gates before judgments, then explicit thresholds; `ABSTAIN` with zero promotions is valid and `PROMOTION_LIMIT=3` is a maximum. Raw judgments, Choice distributions, applicability and exclusion reasons are persisted.
- **UI separation**: `DeterministicStatePanel` (measured facts with explicit availability, never a zero for `NOT_OBSERVED`), `WideRankingPanel` (comparison-only baseline and explicit Jev decision/thresholds/exclusions), `WideJudgment` (full judgment vectors with applicability, labeled “not a measurement”), plus the canonical event feed.

## Documentation pass (2026-09-22)

| Source | Revision examined | Use |
|---|---|---|
| Live GDC API (anonymous captures) | Data Release 46.0, API tag 8.5.0, commit `8f7c2a51…` | Deployed contract, 30 research captures + probe captures |
| `NCI-GDC/gdc-docs` | `157cef9dac084ce30720f0ad507cd54017263be7` | Published endpoint/field/pipeline contracts |
| `NCI-GDC/gdcdatamodel2` | `9c6a046b96c130ea131d2ce2c9160381edd2fcc1` (tag 4.0.3) | Current model design; README replacement statement |
| `NCI-GDC/gdcdictionary` | `88d66b0fe361aa638977850c180bd9130d705924` (tag 4.0.3 parent) | Targeted schema semantics; confirms `gene`/`ssm`/`cnv` are API-layer entities |
| `docs.typesafe.ai` (live docs) + installed `typesafe-sdk` 0.7.1 | fetched 2026-09-22 | Current primitives, HTTP/SDK contracts, models, limits |
| Official pipeline docs (expression, CNV, MAF) | fetched 2026-09-22 | FPKM-UQ definition, impact categories, pipeline semantics |

The fit analysis records every endpoint’s open-access review, live contract check and scientific-semantics review, and lists rejected/deferred sources with reasons (`docs/GDC_JEV_FIT_ANALYSIS.md`).

## Pre-Phase-3 readiness audit (2026-09-23)

Targeted audit of the implemented Phases 1–3 against the official GDC documentation repository
(`https://github.com/NCI-GDC/gdc-docs/tree/develop/docs`) and the live TypeSafe/Jev documentation
(`https://docs.typesafe.ai`). Full findings, authority order and the Jev opportunity assessment are
in `docs/SOURCE_REVIEW.md`.

- GDC endpoint/method, filter, pagination and expression shapes match the documentation; the
  analysis endpoints comply with the "no `format`/`fields`" rule; no credential path exists.
- TypeSafe primitives, same-state fan-out and model limits match the documentation.
- Hardening applied: `.env.local` loader + template; explicit `format: tsv` on the expression
  values request; UTF-8 BOM tolerance and access-missing fail-closed in parsers; import-time
  question-shape validation; typed provider-error classification.
- Jev opportunities (workflow/assay comparability, canonical file selection, gene-mention
  resolution, clinical label normalization) are documented as PLANNED; none is implemented and
  none may compute a measurement.
- No live GDC/Jev/LLM call was made for this audit; live behavior is from the retained
  2026-09-22 captures.

## Pre-Phase-4 hardening (2026-09-23)

Bounded hardening of Phases 1–3 ahead of the first Phase-4 slice; no Phase 4 runtime was added and
`wide-v3` semantics, thresholds and routing policy are unchanged.

- **Jev provider failure containment**: provider-response conversion now fails closed as
  `JevProviderError("PROVIDER_RESPONSE_MALFORMED")`, so a malformed provider response becomes a
  persisted failed evaluation, the state is deferred and the run continues. The conversion of
  `response.model` moved inside the guarded region (it previously escaped as a raw `AttributeError`).
- **GDC attempt finality**: once `gdc_attempt_start()` succeeds, every attempt reaches a terminal
  status. A publish/registration/persistence failure after the response body was read now finalizes
  the attempt as `FAILED` (with response hash and error detail) before the original error propagates.
- **Impossible provider counts fail closed**: a shared `_nonnegative_count` helper rejects negative
  project case/file counts, aggregation `doc_count`, SSM coverage counts, expression availability
  counts and provider totals.
- **Jev model/cache identity**: cache reuse requires a pinned/versioned model name
  (`is_pinned_model_identity`) and a resolution equal to it; a mutable alias is never treated as an
  already resolved model, and no cache row is written for a divergent resolution.
- **Semantic identities**: `question_set_hash()` now covers `applicability_rule`; `gdc_cache` is keyed
  by `<contract_version>:<canonical request hash>`, so a row written under an older transport contract
  can no longer block storing the current contract's entry.
- **Storage ownership restored**: all candidate/state/evaluation/hypothesis/follow-up/dossier SQL moved
  from `research/*` and `jev/*` into narrow `Repository` registration methods; `JevService` no longer
  touches `repository.database`. The atomic event + registrations transaction model is unchanged.
- **Acquisition provenance**: every `StatisticalState` source now carries `request_id`, `attempt_no` and
  `from_cache` from the transport response, linking the logical request, the current cache/network
  attempt, the retained response artifact and the scientific locator. Operational fields stay out of
  `state_hash`.
- **Expression availability merge**: a gene observed by any batch can no longer also appear in the
  merged `missing_genes` list.
- **Jev timeout validation**: `CANCERJEV_JEV_TIMEOUT_SECONDS` uses the existing bounded-seconds pattern;
  NaN, Infinity, `0`, negative values and values above the 30 s documented cap are rejected.
- **Relational integrity (schema 4)**: the declared candidate → evidence → follow-up/hypothesis/dossier
  provenance chain is enforced by foreign keys, so a dangling reference fails the event transaction.

## Phase 4 first deterministic slice (2026-09-23)

IMPLEMENTED, bounded and provider-free at rest. It covers exactly `Candidate → accepted immutable
evidence E0 → one explicitly selected registered deterministic action → immutable E1`, and nothing
beyond it.

- **Registered action contract** (`cancerjev/science/actions.py`): `ACTION_REGISTRY` holds
  `CHECK_EVIDENCE_INTEGRITY_V1` (method `EVIDENCE_INTEGRITY_V1` v1) with an explicit question,
  falsifiable interpretation, required evidence, unit and limitations. `eligible_actions()` is a
  deterministic, fail-closed prerequisite check; `execute()` returns five checks
  (`COHORT_FRAME_AGREEMENT`, `EXPRESSION_COVERAGE_ARITHMETIC`, `MUTATION_COUNT_SCOPE`,
  `TESTED_UNIVERSE_REPRODUCIBLE`, `RESPONSE_ARTIFACT_INTEGRITY`) each `VERIFIED`/`CONTRADICTED`/
  `NOT_OBSERVED`. It acquires no data, calls no model and computes no new biological quantity.
- **Deep slice runner** (`cancerjev/research/deep.py`): accepts E0 by verifying the retained state
  artifact hash and the recorded `state_hash`, records the baseline revision (iteration 0), emits
  `ELIGIBLE_ACTIONS_COMPUTED`, selects an action deterministically (explicit selection only),
  executes it and records E1 with the action/method refs, input artifact hashes, observed values,
  missingness, completeness and provenance. Revision ids and result ids are `uuid5`-deterministic so
  a replay is idempotent rather than duplicated.
- **Python-owned budgets and abstention**: `FOLLOWUP_LIMIT = 3`, `EVIDENCE_ITERATION_LIMIT = 2`
  (matching the `RunEvent.iteration` bound), one execution per (candidate, action, input evidence
  hash). Zero eligible actions, an ineligible requested action, an exhausted budget and an
  already-executed action are typed `FOLLOWUP_ABSTAINED`/`FOLLOWUP_SKIPPED` outcomes; a deterministic
  action failure is `FOLLOWUP_FAILED` with a `FAILED` execution row and no new revision.
- **Explicit selection only**: `run --live --jev --deep-candidate <gene-symbol|slot:N>` (optional
  `--deep-action <action_id>`). The selection rule is recorded in `RUN_STARTED`. Wide admission never
  dispatches a follow-up: an unmatched selection records `DEEP_SELECTION_UNAVAILABLE`. There is no
  autonomous candidate dispatch.
- **Immutability**: E0 is never rewritten; each revision's parent is the previous revision and
  `statistical_states`/`evidence_states`/`followup_executions` remain trigger-immutable. Evidence
  identity excludes operational ids, artifact ids, timestamps and attempt links.
- **Surface**: `GET /api/runs/{id}/evidence`, `GET /api/evidence/{id}`,
  `GET /api/runs/{id}/followups`, and the `DeepEvidencePanel` in run detail. New counters
  `followups_completed`, `followups_failed`, `evidence_revisions` reduce from the event stream.
- **Not implemented**: further registered actions, hypothesis generation/evaluation, multi-candidate
  iteration, automatic dispatch of a recorded next move, live dossiers and Deep Jev question
  revisions beyond `deep-v1`.

## Phase 4 dispatch stage: second action and one authorized follow-up (2026-09-23)

IMPLEMENTED. This closes the documented gap that a recorded `FOLLOW_UP` had nothing to dispatch.

- **Declared action input kinds**: `ActionDefinition.input_kind` is `STATISTICAL_STATE` or
  `EVIDENCE_STATE`; `eligible_actions(record, input_kind)` filters by it, so an action is only ever
  evaluated against the evidence kind it declares. Registry version is `2`.
- **Second registered action** `CHECK_REVISION_FAITHFULNESS_V1` (method `REVISION_FAITHFULNESS_V1` v1,
  input `EVIDENCE_STATE`, 4 checks): the revision restates every copied project-level metric exactly
  (`SOURCE_EVIDENCE_RESTATED`), keeps exactly the accepted provenance sources
  (`SOURCE_PROVENANCE_UNCHANGED`), binds a source artifact whose bytes and recomputed scientific
  identity match what it records (`SOURCE_STATE_IDENTITY_REPRODUCIBLE`), and cites a registered
  producing action at its recorded version with a parent and the accepted entity
  (`REVISION_CHAIN_LINKED`). It acquires nothing, recomputes no measurement and rewrites nothing.
- **One authorized dispatch per run**: `dispatch_recorded_move` acts only on a recorded `FOLLOW_UP`,
  only with explicit operator authorization (`--deep-followup`), at most once, on the
  sorted-first distinct eligible revision action, inside `FOLLOWUP_LIMIT = 3` and
  `EVIDENCE_ITERATION_LIMIT = 2`. Every refusal is recorded as `NEXT_MOVE_DISPATCHED` with a typed
  reason (`MOVE_NOT_FOLLOW_UP`, `DISPATCH_NOT_AUTHORIZED`, `NO_DISTINCT_ELIGIBLE_ACTION`,
  `FOLLOWUP_LIMIT_REACHED`, `EVIDENCE_ITERATION_LIMIT_REACHED`, `DISPATCH_ACTION_FAILED`,
  `INPUT_REVISION_MISSING`).
- **Revision chain**: a dispatched action produces iteration 2 (`E2`) whose parent is `E1`, which
  cites `CHECK_REVISION_FAITHFULNESS_V1`, keeps `source_statistical_state` pointing at the accepted
  state, and is judged again by the same `deep-v1` fan-out. Its producing action is excluded from its
  own eligible set, so the follow-on decision is `NO_FURTHER_REGISTERED_ACTION` — the loop stops
  honestly instead of repeating itself.
- **Boundary preserved**: the policy's recorded move is still never dispatched by the policy itself
  (`executed: false`); dispatch is a separate Python step gated by explicit authorization, and the
  new judgment is only an input to the follow-on decision.

## Phase 4 next stage: deep Jev fan-out and next-move policy (2026-09-23)

IMPLEMENTED for one revision at a time, after the deterministic slice.

- **Operator-approved candidate selection**: `--deep-candidate` accepts a promoted candidate
  (`slot:N`, gene symbol) and, when wide admission selected nothing, a *wide-evaluated state*
  (`<SYMBOL>`, `gene:<SYMBOL>`, `state:<STATE_ID>`). The operator's selection creates the candidate
  with `policy_version="operator-selection-v1"`, `reason=OPERATOR_APPROVED_SELECTION`,
  `auto_dispatched=false`, records the raw selection in `RUN_STARTED`/`CANDIDATE_PROMOTED`, and still
  respects `PROMOTION_LIMIT`. A state without a successful wide evaluation is refused
  (`STATE_NOT_EVALUATED`); wide admission still never dispatches a follow-up.
- **Deep Jev fan-out** (`deep-v1`, `jev-evidence-projection-v1`): one request over the immutable
  revision plus the eligible registered action set, with five atomic questions
  (`revision_reliable`, `evidence_sufficient_for_next_step`, `next_step_warranted`,
  `stopping_more_honest`, `dominant_limitation`) whose applicability is decided by code from the
  revision's recorded checks. Persisted as a normal evaluation row with
  `purpose="DEEP"`, `input_ref_kind="EVIDENCE_STATE"`, `input_ref_evidence_hash`, full answers,
  applicability and cache provenance; recorded by `JEV_DEEP_STARTED` and
  `JEV_DEEP_EVIDENCE_JUDGED`. A provider/validation failure is `JEV_EVALUATION_FAILED` and the
  revision stands.
- **Python next-move policy** (`deep-policy-v1`, `cancerjev/research/nextmove.py`): deterministic,
  named thresholds, records one typed move (`COMPLETE`/`FOLLOW_UP`/`ABSTAIN`) with its reason,
  dimensions and thresholds via `NEXT_MOVE_SELECTED`. It never dispatches: `executed` is always
  `false` and a warranted step without a distinct registered action is recorded as
  `NO_FURTHER_REGISTERED_ACTION`, not silently dropped. A contradicted check abstains before any
  judgment dimension is consulted.
- **Boundary preserved**: Jev judges; Python decides. No Jev output selects, authorizes or executes
  an action, and no measured field is written from a judgment.
- **Live evidence (2026-09-23, bounded, fresh data directory)**: run `a167190d` made 16 anonymous GDC
  requests (367,861 bytes) and 10 wide `jev-1.13.0` calls for 10 states → `ABSTAIN`, 0 promotions, one
  `INVALID_DISTRIBUTION` failure contained. A second bounded run selected `TP53` explicitly, produced
  E0/E1 with 5/5 checks verified, and made one deep `deep-v1` call (3,606 in / 174 out tokens,
  587 ms) → `revision_reliable 0.86`, `evidence_sufficient_for_next_step 0.83`,
  `next_step_warranted 0.41`, `stopping_more_honest 0.71`, `dominant_limitation SCOPE_LIMITS` (0.90)
  → next move `COMPLETE` / `INVESTIGATION_COMPLETE`. A further run reused 10/10 wide judgments and the
  deep judgment from cache with `jev_calls: 0`, confirming the identity fix below.

## Validation hardening (2026-09-23)

Parser, request-builder, pagination and `ResearchSpec` validation were hardened (commit
`60acf6b`), with focused regression coverage:
- GDC request builders validate sizes/offsets uniformly and reject non-integer and boolean values
  (`cases`, `files`, `projects`, `discovery`); `expression_file_sample_size` is bounded by the
  endpoint cap `MAX_FILES_PAGE = 5`.
- `parse_cases` preserves an explicit zero pagination count, rejects malformed/non-integer or
  negative pagination fields, and requires a consistent `from` offset and page count; the live
  orchestrator fails closed with `CASE_PAGE_OFFSET_INCONSISTENT` when the provider's reported
  offset does not match the requested offset, and `CASE_TOTAL_INCONSISTENT` when the page total
  disagrees with the inventory case count or changes across pages.
- Expression availability and gene selection reject unrequested identifiers
  (`UNEXPECTED_IDENTIFIER`); merged expression batches must cover the cohort case frame exactly.
- `AcquisitionSpec` rejects non-integer runtime values; `ResearchSpec.spec_id` must be a non-blank
  string.
- The documented per-response hard cap (5 MiB) now matches the code default; previously the code
  default was 8 MiB, above the documented cap.

## Phase 2 acceptance record (2026-09-22, historical — superseded by the single-cohort scope)

This run used the earlier multi-project sweep (8 projects) that was subsequently replaced by
`LUAD_RESEARCH_V1`; it is retained as historical evidence of the transport, parser and
deterministic-state path, not as the current cohort.

Acceptance run `51a1828f-33d8-47d9-baa3-583fec577b75` — **COMPLETED**, coverage `COMPLETE_FOR_SCOPE`:

- 8 projects selected deterministically (`CDDP_EAGLE-1`, `TCGA-CHOL`, `MP2PRT-WT`, `BEATAML1.0-CRENOLANIB`, `TCGA-UCS`, `RC-PTCL`, `TCGA-DLBC`, `MATCH-I`), release identity `Data Release 46.0 - August 10, 2026`.
- 49 ledger entries: 21 real network requests (87,353 bytes) + 28 cache hits from the earlier partial sweep; zero 401/403 outcomes.
- 10 real StatisticalStates (TP53, ARID1A, PRF3, BTG2, SPTA1, …) with per-project counts, `NOT_OBSERVED` preserved for absent buckets, provider ranking quarantined as `provider_discovery_rank`, coverage imbalance flagged, and explicit missingness.
- Zero Jev calls, zero LLM calls; state identity deterministic (two replay runs produced identical state hashes).

Failure-path evidence: an earlier run failed closed on a provider HTTP 400 (`gene_selection` when no examined case had expression values); the error body was captured, the guard was implemented, and a replay test proves the lane is skipped with `expression NOT_OBSERVED`.

## Phase 3 historical acceptance record (2026-09-22, `wide-v2`)

Acceptance run `36e09880-bd72-4a15-af2a-eb3abe6ef266` — **COMPLETED**:

- 10 projections (`jev-state-projection-v1`), 10 real Jev evaluations with model `jev-1.13.0`, question set `wide-v2`, 28,294 input / 2,020 output tokens, ~0.9–1.2 s per call, all six answers validated and all applicability flags recorded.
- Jev judgments were semantically coherent with the evidence: high `likely_fragile` (0.74–0.78) and `coverage_explains_apparent_difference` (0.79–0.85), `pattern_type = DATA_QUALITY_CONCERN` for all ten states — consistent with the actual coverage imbalance and provider-ranked selection.
- Both rankings persisted (10 baseline + 10 Jev entries); 3 candidates promoted (`TP53`, `PRPF3`, `TPTE`); zero LLM calls; zero deep analysis.
- Cache verification run `ea2067d8-48aa-40f0-ba5b-a8eb6da29999`: 0 GDC requests (49 cache hits), 0 Jev provider calls (10 cached evaluations with `cache_source_evaluation_id`), identical promotions.

This record is retained as immutable evidence for `wide-v2`; it does **not** establish improved
research decisions. Current semantics and admission results are recorded below.

## Phase 3 single-cohort acceptance record (2026-09-23)

Uncached live acceptance run `34e49ab0-0696-4caf-bd0a-bc37692d9a57` — **COMPLETED**:

- One exact cohort (`TCGA-LUAD`), 10 deterministic StatisticalStates, 10 v2 projections, and 10
  fresh `wide-v3` provider evaluations using model `jev-1.13.0` / SDK `typesafe-sdk` 0.7.1.
- 16 anonymous GDC requests completed without cache hits (359.2 KiB); no file downloads or GDC
  credentials. Ten Jev calls recorded 19,659 input tokens; provider cost is unavailable.
- Both v2 rankings persisted for the same 10 states. All ten states failed the explicit
  `warrants_deeper_investigation >= 0.60` admission threshold (observed probabilities 0.30–0.48);
  two additionally exceeded the coverage-confound threshold. The policy returned `ABSTAIN`,
  admitted/promoted zero candidates, and persisted per-state exclusion reasons.
- The integrated browser rendered the admission decision, thresholds, baseline comparison,
  per-state reasons, all ten raw judgment vectors and applicability records. No LLM calls or deep
  analysis occurred.

The zero-promotion result verifies the abstention path only. It is not a scientific conclusion and
does not establish whether the thresholds improve research decisions; threshold calibration and
baseline-vs-Jev incremental-value evaluation remain open work.

## Verification record

Verification performed 2026-09-23 (pre-Phase-4 hardening) on the hardened implementation:

| Gate | Command | Result |
|---|---|---|
| Python lint | `python -m ruff check cancerjev apps tests` | All checks passed |
| Offline suite | `python -m pytest -q` | **348 passed**, 0 failed; 2 opt-in live-marked tests deselected (350 collected) |
| Frontend typecheck | `npm run typecheck` | Passed |
| Frontend build | `npm run build` | Passed (all routes) |
| Browser E2E | `npm run test:e2e` (API 8010, web 3010; matching localhost origin) | **4 passed** |
| Live application | Integrated browser on the acceptance run | Rendered `ABSTAIN`, thresholds, exclusions, baseline and raw judgments; API responses 200 |
| Live GDC + Jev | `python -m cancerjev run --live --jev` with a fresh data directory and GDC cache disabled | **COMPLETED**, 16 fresh GDC requests, 10 Jev calls/evaluations, 10 states, 0 promotions, explicit `ABSTAIN` |
| Deep slice (Phase 4 first slice) | `tests/integration/test_deep_slice.py` with the replay transport and stub adapter, explicit `--deep-selection` equivalent | **COMPLETED**: E0 + E1 recorded, 5/5 checks verified, typed abstention/failure and idempotency branches covered; no provider call |
| Deep Jev + next move (next stage) | same suite | **COMPLETED**: operator-approved selection, `deep-v1` judgment persisted as `purpose=DEEP`/`input_ref_kind=EVIDENCE_STATE`, next-move decision recorded and never dispatched, deep provider-failure containment, usage accounting; no provider call |
| Dispatch stage | same suite | **COMPLETED**: second action with a declared `EVIDENCE_STATE` input kind; each of its four checks exercised as `VERIFIED`/`CONTRADICTED`/`NOT_OBSERVED`; an authorized `FOLLOW_UP` produces `E2` (parent `E1`) that is judged again and yields `NO_FURTHER_REGISTERED_ACTION`; unauthorized, `COMPLETE`, follow-up-cap and revision-cap refusals are recorded as typed `NEXT_MOVE_DISPATCHED` reasons; no provider call |
| Live deep validation | `run --live --jev --deep-candidate TP53` on the retained live directory | **COMPLETED**: wide `ABSTAIN`/0 promoted → operator-approved candidate → E0/E1 (5/5 verified) → one deep `deep-v1` call → `COMPLETE`; the following run reused 10/10 wide and the deep judgment from cache (`jev_calls: 0`) |
| Live dispatch validation | `run --live --jev --deep-candidate TP53 --deep-followup` on the retained live directory | **COMPLETED**: 16 GDC cache hits, 10/10 wide judgments reused, one deep `deep-v1` call (3,613/174 tokens) → judgment `next_step_warranted 0.53`, `stopping_more_honest 0.56` → move `COMPLETE`, so `NEXT_MOVE_DISPATCHED` recorded `dispatched: false`, `MOVE_NOT_FOLLOW_UP`, `authorized: true`; the revision-eligible set correctly included `CHECK_REVISION_FAITHFULNESS_V1`; 2 revisions and 1 execution remained, with no `E2` |
| GDC contract probe | `python -m cancerjev probe` | Historical probe: 14 captures, all HTTP 200, anonymous |

No live GDC, TypeSafe or LLM call was made by the pre-Phase-4 hardening pass, the Phase 4 first
slice, or their verification: the tests use loopback sockets, the injected fake SDK module, and the
replay transport. The deep slice acquires no evidence and calls no model by construction.

On Windows, pytest exited successfully with all 348 offline tests passing but emitted an ignored
`PermissionError` while cleaning its temporary `pytest-current` symlink at process exit.

The dispatch stage is verified offline end-to-end (replay transport + stub adapter, both the
authorized `FOLLOW_UP` path and every refusal branch). Its live acceptance is inherently limited: the
retained live `deep-v1` judgment records `COMPLETE`, so an authorized live run correctly records
`NEXT_MOVE_DISPATCHED` with `MOVE_NOT_FOLLOW_UP` and dispatches nothing — thresholds are not tuned to
force a dispatch.

A bounded live acceptance of the deep slice (`python -m cancerjev run --live --jev
--deep-candidate <slot:N>`) is a separately approved step and has not been run yet; the slice is
verified offline end-to-end.

## Provider-use record (cumulative through 2026-09-23)

- **GDC:** prior record 84 real anonymous network attempts (735,207 bytes) plus 158 cache hits; this task made 32 additional fresh requests across two runs (each 16 requests, about 359 KiB). All endpoints remained within the open-access allowlist; zero file downloads, controlled records, or authentication headers.
- **Jev / TypeSafe:** prior record 10 provider calls; the wide acceptance made 10 further calls on model `jev-1.13.0` for `wide-v3` (17,692 input / 2,070 output tokens); the deep-stage validation made 1 call for `deep-v1` (3,606 input / 174 output tokens), one further re-run made 9 wide + 1 deep calls before the identity fix (3,602/174), another made 3,605/174, and the dispatch-stage validation made 1 more deep call (3,613/174). A final re-run of each stage made 0 calls, reusing 10/10 wide and the deep judgment from cache. No cost field is available (unknown). The initial environment setup attempt made no provider calls because the project-declared SDK was not installed; the same bounded run succeeded after installing SDK 0.7.1.
- **LLM / OpenRouter:** 0.
- No GDC credential exists anywhere in the codebase or environment; the TypeSafe key is read only from `TYPESAFE_API_KEY` at call time and is never persisted or logged.

## Open-access and safety record

- Adversarial tests prove: no `Authorization`/`X-Auth-Token` literal in any non-docstring string; no GDC credential environment read; `/data`, `/manifest`, `/slicing` are not routable; file metadata requests always carry `access=open`; a returned `access=controlled` record fails closed; 401/403 become `UNAVAILABLE_ACCESS` with no retry and no credential lookup; a forged endpoint spec is rejected by the transport; loopback-only test hosts with the production host fixed.
- Live evidence: every captured request recorded `authentication_headers_sent: []`; no run produced a 401/403; the sweep scope contained only open-access projects.

## Known limitations

- Mutation evidence is **count-only**: `case_with_ssm` is not a callable-negative denominator, so no recurrence fraction is computed; absent buckets are `NOT_OBSERVED`.
- Provider expression `median`/`stddev` estimator conventions are undocumented; a live two-case capture is consistent with a population denominator and is recorded as `INFERRED_POPULATION_SD_UNVERIFIED`. Provider summaries never drive policy.
- The examined gene set is selection-biased: genes are taken from the cohort's provider top-mutated ranking by provider rank (no recurrence + round-robin pooling). The state records the bias and does not claim a genome-wide scan.
- Case-to-sample resolution for expression values is **UNVERIFIED**; no sample-matched cross-modal claim is made.
- GDC release atomicity across requests is **UNVERIFIED**; reproducibility means replay from retained responses and hashes.
- No seed/temperature control exists for Jev; repeated calls may differ. Cache identity binds projection bytes, question bytes, model and adapter version; policy version is excluded so policy experiments do not rerun inference. `wide-policy-v2` thresholds remain provisional and uncalibrated. `deep-policy-v1` thresholds are equally provisional and are not tuned to force a move.
- Live deep determinations rest on one recorded review: the retained run's deep judgment (and its `COMPLETE` next move) is one provider call, reused from cache afterwards. It is not evidence that the deep question set is calibrated.
- Operator-approved candidate selection consumes a promotion slot and is a recorded human decision, not a validated selection rule; the deep slice still requires `--live --jev` and cannot be reached from the fixture demo.
- The TypeSafe price page is documentation, not a contract; cost stays `null`/unknown because the API exposes no cost field.
- Schema 4 does not migrate schema 1–3 data directories; they must be moved or deleted. No stale
  database or acceptance directory is retained in the repository: the schema-3 live acceptance
  directory was deleted on 2026-09-23 and `data/` holds only its `.gitkeep`.
- A post-Phase-3 audit hardening pass fixed the documented safety/evidence defects (overridable GDC ceilings, nested aggregation truncation, cross-project SSM total, selection-artifact zero substitution, unenforced Jev state cap, cache-cap bypass, response byte accounting, page-advance counting, silent ranking-artifact loss, and live-vector UI rendering): `docs/CODEBASE_AUDIT_2026-09-23.md`. Remaining medium/low findings are listed there with severity and location and are not fixed.
- Local runs used Python 3.14.3 and Node 24.13.1 while CI pins Python 3.12 and Node 22. GitHub Actions run `35784234662` for commit `d1ab646` passed the Python, frontend, and browser jobs.

## Next implementation sequence

These are separate tasks; do not combine them.

1. Targeted pre-Phase-3 readiness audit. **DONE (2026-09-23)** — see `docs/SOURCE_REVIEW.md`.
2. TCGA-LUAD Wide Jev semantic/admission redesign. **DONE (2026-09-23)** — implementation and bounded live acceptance recorded above; design: `docs/PHASE_3_PLAN.md`.
3. Baseline-vs-Jev incremental-value evaluation. **NEXT** — separate validation task; do not infer quality from changed rankings.
4. One Phase-4 vertical slice: E0 → one registered follow-up → E1. **DONE (2026-09-23)** for the
   deterministic first slice with an explicit operator selection.
5. One Deep Jev fan-out over the new revision plus the Python next-move decision. **DONE
   (2026-09-23)**, bounded to one revision and one decision record; dispatch of a recorded move
   remains unimplemented.
6. A second registered deterministic action, so a recorded `FOLLOW_UP` can actually be dispatched.
   **DONE (2026-09-23)** — `CHECK_REVISION_FAITHFULNESS_V1` plus one explicitly authorized dispatch per
   run, producing `E2` and re-judging it.
7. Bounded next-candidate autonomous iteration.
8. Bounded LLM hypothesis generation + Jev hypothesis evaluation.

## Phase 4–7: plans only, not implemented

- **Phase 4 — deep deterministic evidence**: the first slice, the deep fan-out and one authorized
  dispatch are IMPLEMENTED as described above (`CHECK_EVIDENCE_INTEGRITY_V1` and
  `CHECK_REVISION_FAITHFULNESS_V1`, explicit/operator selection, immutable E0/E1/E2,
  `deep-policy-v1`, typed abstention/failure/dispatch refusals). Still not implemented: autonomous
  iteration beyond one authorized dispatch, bounded hypothesis generation, multi-candidate iteration
  and further registered actions. Additional follow-up IDs in `docs/PHASE_4_READINESS_PLAN.md` remain
  unapproved placeholders.
- **Phase 5 — dossiers for live candidates**: structured JSON + derived Markdown from real evidence revisions.
- **Phase 6 — generative hypotheses**: competing hypotheses may only be generated after deterministic evidence and Jev judgments exist; Jev critiques them; an LLM never writes a measured field. `hypothesis-v2` is documented.
- **Phase 7 — offline autoresearch**: labelled historical states, LLM-proposed candidate questions, Jev evaluation, classical usefulness tests, pruning and human review to version the production question set.

**Confirmation: no LLM hypothesis implementation and no generative model call exists in the codebase.** The only provider calls are the bounded anonymous GDC requests and the Jev evaluations recorded above. Deterministic follow-up execution exists only as the Phase 4 slices above: it is Python-controlled, acquires no data, is explicitly selected by an operator, and never dispatches itself from wide admission or from its own recorded next move.
