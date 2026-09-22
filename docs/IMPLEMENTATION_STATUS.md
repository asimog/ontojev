# Implementation status

**DONE:** Phase 0 design, Phase 1 offline synthetic vertical slice (verified), the GDC × Jev fit analysis (`docs/GDC_JEV_FIT_ANALYSIS.md`), Phase 2 real open-access GDC evidence with deterministic StatisticalStates (now scoped to the single TCGA-LUAD cohort), and Phase 3 real Jev wide evaluation over those states. **CURRENT:** locally verified Phase 2 and Phase 3 against the live public GDC API and the live TypeSafe API. **NEXT:** nothing without explicit approval; Phase 4+ is documented only. Phase 3 questions are stale for the single-cohort state and are not redesigned here.

Phase 1 remains available and separate: `run --fixture demo` still produces the 71-event synthetic dossier run with zero provider calls, and fixture and live records are never mixed.

## What exists (Phase 2 additions)

- **One GDC transport** (`cancerjev/gdc/transport.py`): fixed host `api.gdc.cancer.gov`, endpoint/method allowlist, no authentication by construction (no credential parameter, no token loader, no `Authorization`/`X-Auth-Token` path), no redirect following, `Accept-Encoding: identity` with compressed responses rejected, streamed reads with per-response (8 MiB), per-run byte (64 MiB), request (150), page (10/query), case-ID (250) and gene-ID (100) caps, bounded retries for safe GETs only, a persisted attempt ledger, raw-response publication with SHA-256, and a normalized request cache.
- **Strict parsers** (`cancerjev/gdc/parsers.py`) for the eleven admitted endpoints: required fields and types enforced, `warnings.fields` surfaced, aggregation completeness fields preserved, duplicates and unexpected identifiers rejected, NaN/Infinity rejected, TSV joined by returned labels.
- **Deterministic methods** (`cancerjev/science/methods.py`): `MUTATION_AFFECTED_CASE_COUNT_V1`, `PROJECT_SSM_COVERAGE_V1`, `EXPRESSION_LOG2_SUMMARY_V1`, `EXPRESSION_PROVIDER_SUMMARY_V1`, `PROJECT_DOMINANCE_V1`, each with the full declaration set (population, duplicate rule, estimator, missingness, limitations, provenance). No p-values, no effect sizes, no recurrence fraction, no biological direction.
- **Real StatisticalStates**: one per gene, covering per-project affected-case counts, SSM coverage, local `log2(UQFPKM+1)` summaries, provider summaries retained separately, per-project coverage metrics, cross-project descriptives, missingness, and full source provenance with scientific identity hashing.
- **Research specification + live orchestrator** (`cancerjev/research/specs.py`, `cancerjev/research/live.py`): one frozen production specification, `LUAD_RESEARCH_V1`, owns the reproducible domain/cohort/project and bounded acquisition parameters; deployment `Settings` remains operational only. The orchestrator consumes the specification, selects one exact project, acquires deterministic paginated case frames, batches expression requests within the 250-case endpoint cap, and never pools projects.
- **Contract-capture command** (`python -m cancerjev probe`) using the same transport, writing run-scoped capture directories with request metadata, hashes and an index.
- Persistence schema **3**: `gdc_attempts` (operational ledger), `gdc_cache`, `jev_projections`, `jev_cache`; earlier schema directories fail with an actionable error instead of migrating.
- New registered events for the GDC lifecycle, scope selection, projections, rankings and evaluation failures; the reducer maintains real GDC request/byte/cache-hit and Jev token usage.

## TCGA-LUAD Phase 2 scientific foundation (2026-09-22)

The generic multi-project sweep was replaced by one explicitly defined cohort: **domain `lung cancer`, cohort `TCGA-LUAD`**. This changes evidence semantics, not the transport, budgets, persistence, artifacts, or Jev architecture.

- **Cohort contract (old → new):** old = "first 8 projects with 50–250 cases ordered by `(case_count, project_id)`", genes pooled across projects by recurrence plus round-robin. New = `TCGA-LUAD` selected by exact `project_id` from the open inventory; genes taken from the cohort's provider top-mutated ranking by provider rank. TCGA-LUAD and TCGA-LUSC are never pooled.
- **Population/missingness:** `Population` now separates `eligible_n` (cohort) from `examined_n` (returned frame); the generic `selected_n`/`observed_n` counts are removed. Each modality result carries explicit `examined_cases`, `assay_available_cases`, `returned_case_columns`, `valid_measurements` and `missing_measurements`. `EXPRESSION_LOG2_SUMMARY_V1` now folds the parser's `missing_case_ids` (examined case columns the provider did not return) into `n_missing`; a fully valid returned subset can no longer report zero missingness.
- **Mutation semantics:** `mutation.absence_semantics` states explicitly that an absent bucket is `NOT_OBSERVED`, not zero, wildtype or a callable negative; no recurrence fraction is computed. `affected_case_total` is `NOT_OBSERVED` (not `0`) when no project has an observed bucket.
- **Completeness:** `quality.acquisition_completeness` (were the requested responses acquired in full?) is now separate from `quality.scientific_sufficiency` (`SUFFICIENT`/`PARTIAL`/`INSUFFICIENT`), with definitions stored in the state.
- **Comparability:** `scope.comparability` carries explicit statuses. `within_cohort = UNVERIFIED` (harmonization/shared membership/empty incompatibility list prove nothing) and `cross_project = NOT_APPLICABLE` for one cohort. No `VERIFIED` status is fabricated.
- **Scientific identity:** discovery rank, provider `_score`, lane ordering and `examined_genes_ref` are excluded from `state_hash`; discovery provenance stays visible in `generation.discovery` and `provider_discovery_rank` but does not affect identity.
- **Bounded modular acquisition:** TCGA-LUAD remains the only production research specification, with a 1,000-case ceiling and 250-case pages/batches. Case pages fail closed on an over-limit total, inconsistent totals, premature empty pages, cross-page duplicate IDs, or unexpected project IDs. Local expression values and missingness merge by ID across batches. Provider batch medians/stddev are not aggregated; the provider summary is explicitly unavailable when the cohort needs multiple requests.

**Phase 3 assumptions now stale (not redesigned here).** `wide-v2` was designed for cross-project evidence. Under a single LUAD state: `mutation_project_exception` and `expression_project_exception` (need ≥3 project observations), `likely_fragile` (needs `top_project_share`, which is `NOT_APPLICABLE` with one project) and `coverage_explains_apparent_difference` (needs a cross-project coverage imbalance) become inapplicable or ungrounded; `pattern_type`'s roster is cross-project and is semantically stale. Phase 2 stays functional and Phase 3 still runs, but the question set and the projection's `cross_project` framing must be revisited before Phase 3 is treated as scientifically meaningful for this cohort. No replacement is invented yet.

## What exists (Phase 3 additions)

- **Owned Jev contracts** (`cancerjev/jev/contracts.py`): normalized Noul/Choice/Score answers with fail-closed validation (missing/unknown questions, wrong primitive, out-of-range or non-finite probabilities, roster/distribution mismatch, invalid confidence/legend, non-summing distributions). No defaults are fabricated.
- **Versioned question set** (`wide-v2`, six questions): warrants, mutation exception, expression exception, coverage explanation, fragility (Noul) and pattern type (Choice, closed six-option roster); deterministic applicability rules; hash over canonical definitions. `multimodal_convergence`, `direction_reversal` and `followup_value` are deliberately excluded because the real state cannot ground them.
- **Projection** (`jev-state-projection-v1`): compact deterministic JSON built only from state fields, with included-field contract, hard byte cap, and a projection hash used as the inference identity.
- **One adapter** (`cancerjev/jev/typesafe_adapter.py`): the only module that imports the TypeSafe SDK; converts provider objects to plain data immediately; records requested/resolved model, request id, usage and latency.
- **JevService** (`cancerjev/jev/service.py`): projection registration, cache identity (`projection hash + question hash + pinned model + adapter version`, policy version excluded), provider call, validation, persistence, and events; cache hits create a new evaluation with `cache_source_evaluation_id` and zero usage.
- **Deterministic ranking** (`cancerjev/research/ranking.py`): baseline policy (`baseline-wide-v1`) and Jev policy (`wide-policy-v1`) over persisted raw dimensions; both rankings are retained for the same states; bounded promotion (top 3) as `WIDE_EVALUATED` candidates; no deep analysis, hypotheses, follow-ups or LLM.
- **UI separation**: `DeterministicStatePanel` (measured facts with explicit availability, never a zero for `NOT_OBSERVED`), `WideRankingPanel` (baseline vs Jev side by side), `WideJudgment` (full judgment vectors with applicability, labeled “not a measurement”), plus GDC lifecycle events in the feed.

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

## Phase 2 acceptance record (2026-09-22)

Acceptance run `51a1828f-33d8-47d9-baa3-583fec577b75` — **COMPLETED**, coverage `COMPLETE_FOR_SCOPE`:

- 8 projects selected deterministically (`CDDP_EAGLE-1`, `TCGA-CHOL`, `MP2PRT-WT`, `BEATAML1.0-CRENOLANIB`, `TCGA-UCS`, `RC-PTCL`, `TCGA-DLBC`, `MATCH-I`), release identity `Data Release 46.0 - August 10, 2026`.
- 49 ledger entries: 21 real network requests (87,353 bytes) + 28 cache hits from the earlier partial sweep; zero 401/403 outcomes.
- 10 real StatisticalStates (TP53, ARID1A, PRF3, BTG2, SPTA1, …) with per-project counts, `NOT_OBSERVED` preserved for absent buckets, provider ranking quarantined as `provider_discovery_rank`, coverage imbalance flagged, and explicit missingness.
- Zero Jev calls, zero LLM calls; state identity deterministic (two replay runs produced identical state hashes).

Failure-path evidence: an earlier run failed closed on a provider HTTP 400 (`gene_selection` when no examined case had expression values); the error body was captured, the guard was implemented, and a replay test proves the lane is skipped with `expression NOT_OBSERVED`.

## Phase 3 acceptance record (2026-09-22)

Acceptance run `36e09880-bd72-4a15-af2a-eb3abe6ef266` — **COMPLETED**:

- 10 projections (`jev-state-projection-v1`), 10 real Jev evaluations with model `jev-1.13.0`, question set `wide-v2`, 28,294 input / 2,020 output tokens, ~0.9–1.2 s per call, all six answers validated and all applicability flags recorded.
- Jev judgments were semantically coherent with the evidence: high `likely_fragile` (0.74–0.78) and `coverage_explains_apparent_difference` (0.79–0.85), `pattern_type = DATA_QUALITY_CONCERN` for all ten states — consistent with the actual coverage imbalance and provider-ranked selection.
- Both rankings persisted (10 baseline + 10 Jev entries); 3 candidates promoted (`TP53`, `PRPF3`, `TPTE`); zero LLM calls; zero deep analysis.
- Cache verification run `ea2067d8-48aa-40f0-ba5b-a8eb6da29999`: 0 GDC requests (49 cache hits), 0 Jev provider calls (10 cached evaluations with `cache_source_evaluation_id`), identical promotions.

## Verification record — 2026-09-22

| Gate | Command | Result |
|---|---|---|
| Python lint | `.venv\Scripts\python -m ruff check cancerjev apps tests` | All checks passed |
| Offline suite | `python -m pytest` (live markers excluded by default) | **189 passed**, 0 failed (2 live-marked tests deselected) |
| Live markers | `pytest -m live_gdc` / `-m live_jev` | opt-in; the GDC probe passed in a manual run (14 captures, all 200); the Jev live test skips without a key |
| Frontend typecheck | `npm run typecheck` | Passed |
| Frontend build | `npm run build` | Passed (all routes) |
| Browser acceptance | `npm run test:e2e` (API 8010, web 3010) | 4 passed (1.2 m) |
| Live browser inspection | live run detail in the integrated browser | Deterministic panel, candidate admission, baseline vs Jev ranking, 10 judgment panels; 0 console errors |
| Phase 2 live run | `python -m cancerjev run --live` | COMPLETED, 10 real states, 0 Jev/LLM |
| Phase 3 live run | `python -m cancerjev run --live --jev` | COMPLETED, 10 real Jev calls, 3 promotions |
| Cache verification | second `run --live --jev` | 0 provider calls, identical rankings/promotions |
| Contract probe | `python -m cancerjev probe` | 14 captures, all HTTP 200, anonymous |

## Provider-use record (cumulative, 2026-09-22)

- **GDC:** 84 real anonymous network attempts (735,207 bytes ≈ 718 KiB) plus 158 cache hits; all open-access metadata/analysis endpoints; zero file downloads; zero controlled records admitted; zero authentication headers.
- **Jev / TypeSafe:** 10 real provider calls (one Phase 3 run), model `jev-1.13.0`, 28,294 input + 2,020 output tokens, no cost field available (unknown).
- **LLM / OpenRouter:** 0.
- No GDC credential exists anywhere in the codebase or environment; the TypeSafe key is read only from `TYPESAFE_API_KEY` at call time and is never persisted or logged.

## Open-access and safety record

- Adversarial tests prove: no `Authorization`/`X-Auth-Token` literal in any non-docstring string; no GDC credential environment read; `/data`, `/manifest`, `/slicing` are not routable; file metadata requests always carry `access=open`; a returned `access=controlled` record fails closed; 401/403 become `UNAVAILABLE_ACCESS` with no retry and no credential lookup; a forged endpoint spec is rejected by the transport; loopback-only test hosts with the production host fixed.
- Live evidence: every captured request recorded `authentication_headers_sent: []`; no run produced a 401/403; the sweep scope contained only open-access projects.

## Known limitations

- Mutation evidence is **count-only**: `case_with_ssm` is not a callable-negative denominator, so no recurrence fraction is computed; absent buckets are `NOT_OBSERVED`.
- Provider expression `median`/`stddev` estimator conventions are undocumented; a live two-case capture is consistent with a population denominator and is recorded as `INFERRED_POPULATION_SD_UNVERIFIED`. Provider summaries never drive policy.
- The examined gene set is selection-biased (provider top-mutated ranking with a recurrence + round-robin rule); the state records the bias and does not claim a genome-wide scan.
- Case-to-sample resolution for expression values is **UNVERIFIED**; no sample-matched cross-modal claim is made.
- GDC release atomicity across requests is **UNVERIFIED**; reproducibility means replay from retained responses and hashes.
- No seed/temperature control exists for Jev; repeated calls may differ. Cache identity binds projection bytes, question bytes, model and adapter version; policy version is excluded so policy experiments do not rerun inference.
- The TypeSafe price page is documentation, not a contract; cost stays `null`/unknown because the API exposes no cost field.
- Schema 3 does not migrate schema 1/2 data directories; they must be moved or deleted (the pre-Phase-2 schema-2 database was preserved as `data/cancerjev.schema2.db.bak`).
- Hosted CI was not executed locally; the local runs used Python 3.14.3 and Node 24.13.1 while CI pins Python 3.12 and Node 22. **UNVERIFIED:** hosted CI status.

## Phase 4–7: documented only, not implemented

- **Phase 4 — deep deterministic evidence**: `EvidenceState` revisions, registered deterministic follow-ups (`STRATIFY_BY_PROJECT_V1`, `LEAVE_ONE_PROJECT_OUT_V1`, `CHECK_MISSINGNESS_V1`, `OUTLIER_SENSITIVITY_V1`, `COMPARE_MODALITIES_V1`), and a reduced `deep-v2` Jev battery (`docs/JEV_QUESTIONS.md`). No follow-up executes until its scientific contract exists; Jev may rank eligible actions but never invent them.
- **Phase 5 — dossiers for live candidates**: structured JSON + derived Markdown from real evidence revisions.
- **Phase 6 — generative hypotheses**: competing hypotheses may only be generated after deterministic evidence and Jev judgments exist; Jev critiques them; an LLM never writes a measured field. `hypothesis-v2` is documented.
- **Phase 7 — offline autoresearch**: labelled historical states, LLM-proposed candidate questions, Jev evaluation, classical usefulness tests, pruning and human review to version the production question set.

**Confirmation: no LLM hypothesis implementation, no generative model call, and no deep/follow-up execution exists in the codebase.** The only provider calls are the bounded anonymous GDC requests and the Phase 3 Jev evaluations recorded above.
