# Codebase Audit and Bug Report

Audit date: 2026-09-23  
Audited base commit: `d1ab646` (`main`, pushed to `origin/main`)  
Hardening pass: the first hardening pass fixed AUD-01 through AUD-11 below with provider-free
regression tests; those changes are committed. A second, pre-Phase-4 hardening pass then fixed the
provider-containment, attempt-finality, provenance, cache-identity, storage-ownership and
tested-universe items recorded as AUD-12 through AUD-19. The findings still listed under
**Remaining Findings (not fixed)** remain open, with the deliberately deferred items named.

## Executive Summary

Phase 3 is **implementation-complete**: the single-cohort projection, versioned Wide Jev set,
deterministic eligibility/admission, abstention, bounded promotion, persisted rankings, and UI are
implemented. It is **not scientifically validated**. The only retained live Phase 3 acceptance run
admitted zero of ten states; that verifies abstention, not calibration or incremental research
value. The `wide-policy-v2` thresholds remain provisional.

The audit reproduced one policy-ordering defect (`AUD-01`) and identified higher-priority
safety/science defects in operational cap enforcement, aggregation completeness, evidence scoping,
and cache/byte accounting, plus UI defects in the live judgment/ranking path. This pass fixes those
items and records the remaining medium/low findings for later work. No measurements, GDC request
policy, schema, or external provider behavior were changed; the fixes tighten fail-closed behavior.

## Fixed Findings

### AUD-01: Inapplicable Jev probabilities affected displayed ranking order

- **Severity:** Low (policy integrity; no measured-value corruption).
- **Location:** `cancerjev/research/ranking.py` (applicability-aware sort helpers and Jev ordering).
- **Fix:** Ranking keys now read Noul probabilities only when their persisted applicability flag is
  true. Raw probabilities and applicability records remain unchanged and visible.
- **Regression coverage:** `test_inapplicable_probabilities_do_not_change_order_but_remain_raw`.

### AUD-02: Operational settings could raise documented GDC/Jev hard caps

- **Severity:** High (safety boundary).
- **Location:** `cancerjev/config.py`.
- **Fix:** `Settings.from_env` now rejects above-default `CANCERJEV_GDC_MAX_REQUESTS`,
  `CANCERJEV_GDC_MAX_BYTES`, `CANCERJEV_GDC_PER_RESPONSE_BYTES`, `CANCERJEV_GDC_TIMEOUT_SECONDS`,
  and `CANCERJEV_JEV_MAX_STATES`; lowering remains allowed and effective.
- **Regression coverage:** `test_above_hard_cap_settings_are_rejected`,
  `test_lowering_hard_caps_is_allowed_and_effective`.

### AUD-03: Nested aggregation truncation could be marked complete

- **Severity:** High (evidence integrity).
- **Location:** `cancerjev/gdc/parsers.py` (counts and coverage aggregations).
- **Fix:** `parse_gene_case_counts` and `parse_mutated_cases_count` now inspect the nested terms
  aggregation nodes (`aggregations.projects`, per-project gene terms, `case_summary.case_with_ssm`)
  for `timed_out`, failed shards, `sum_other_doc_count`, and `doc_count_error_upper_bound`, and fail
  closed to PARTIAL.
- **Regression coverage:** `test_nested_terms_truncation_is_not_treated_as_complete`.

### AUD-04: A single-cohort state contained a cross-project SSM total

- **Severity:** High (evidence scope).
- **Location:** `cancerjev/science/methods.py`.
- **Fix:** `mutation.coverage.case_with_ssm` is now summed only over the state's examined projects;
  when no in-scope bucket exists it is `NOT_OBSERVED` rather than a global total.
- **Regression coverage:** `test_coverage_ssm_total_is_scoped_to_examined_projects`,
  `test_coverage_ssm_total_is_not_observed_when_no_in_scope_bucket`.

### AUD-05: Missing mutation-count buckets became zero in the selection artifact

- **Severity:** Medium (missingness semantics).
- **Location:** `cancerjev/research/live.py` (`_fast_search`).
- **Fix:** `affected_totals_in_scope` preserves absence (`None`) instead of substituting `0`, while
  an observed zero bucket remains a real value.
- **Regression coverage:** `test_selection_totals_preserve_absence_instead_of_zero`.

### AUD-06: The configured Jev state cap was not enforced

- **Severity:** Medium (provider work bound).
- **Location:** `cancerjev/research/wide.py`, `cancerjev/research/live.py`.
- **Fix:** `run_wide_evaluation` accepts `max_states`; the live path passes
  `Settings.jev_max_states`, evaluates only the capped prefix, emits
  `JEV_WIDE_STATE_CAP_ENFORCED` with the skipped state IDs, and the uncapped states appear as
  `EVALUATION_MISSING` in the ranking rather than silently disappearing.
- **Regression coverage:** `test_run_wide_evaluation_enforces_configured_state_cap`;
  `JEV_WIDE_STATE_CAP_ENFORCED` added to the registered event vocabulary.

### AUD-07: A GDC cache hit bypassed the current response cap and contract check

- **Severity:** Medium (safety boundary).
- **Location:** `cancerjev/gdc/transport.py` (`_cache_get`).
- **Fix:** Cache entries are ignored when incomplete, when the stored transport `contract_version`
  differs, when the stored size exceeds the current `per_response_bytes`, or when the stored size
  disagrees with the artifact body.
- **Regression coverage:** `test_cache_hit_respects_current_response_cap`.

### AUD-08: Error and truncated responses broke byte accounting

- **Severity:** Medium (budget accounting).
- **Location:** `cancerjev/gdc/transport.py` (`_perform`, `_attempt`).
- **Fix:** Error bodies are bounded by the response and run allowance; the truncation sentinel byte
  is counted in `bytes_read` and charged exactly once instead of double-charging the allowance.
- **Regression coverage:** `test_error_body_is_bounded_by_response_and_run_allowance`,
  `test_oversized_body_sentinel_is_charged_once`.

### AUD-09: The per-query page cap counted page numbers, not advances

- **Severity:** Medium (page budget).
- **Location:** `cancerjev/gdc/endpoints.py` (`cases_request`), `cancerjev/research/live.py`.
- **Fix:** `cases_request` accepts an explicit `page`; the case-frame loop passes its monotonic
  `page_number`, so short pages still consume one page-advance each against the ten-page cap.
- **Regression coverage:** `test_cases_page_advance_can_exceed_offset_derived_page`.

### AUD-10: Corrupt or missing ranking artifacts were silently reported as “no ranking”

- **Severity:** High (UI/audit visibility).
- **Location:** `apps/api/routes.py` (`/api/runs/{run_id}/rankings`).
- **Fix:** A ranking artifact row that cannot be read now returns `503` instead of `null`, so a
  corrupt admission decision is surfaced rather than hidden. A run with no ranking rows still
  reports `null`.
- **Regression coverage:** `test_corrupt_ranking_artifact_surfaces_an_error`.

### AUD-11: Live judgment vectors were rendered as fixture vectors; no visible join

- **Severity:** Medium (UI correctness).
- **Location:** `apps/web/components/EventFeed.tsx`, `JudgmentVector.tsx`, `WideJudgment.tsx`,
  `WideRanking.tsx`, `RunDetail.tsx`.
- **Fix:** `EventFeed.isJudgmentVector` accepts only fixture-shaped vectors (`noul`/`choice`/`score`),
  so live event payloads are no longer labeled as fixture responses. `WideJudgment` now shows the
  gene, state ID, and evaluation ID; the ranking table shows `state_id`/`evaluation_id` rows; and
  fixture vectors render inside a `data-testid="fixture-judgment-vector"` wrapper. The event-page
  continuation loop commits each page before advancing its cursor, so a later-page failure no
  longer skips earlier pages.

## Fixed Findings (pre-Phase-4 hardening pass, 2026-09-23)

Dispositions below are verified against current `HEAD` (each item was reproduced first).

### AUD-12: A malformed TypeSafe response could abort the whole live run

- **Severity:** Medium (run containment). **Disposition:** CONFIRMED → fixed.
- **Root cause:** response-to-answer conversion (including `response.model`) ran outside the guarded
  region, so a shape mismatch escaped as a raw `AttributeError`/`TypeError` instead of a typed
  provider error.
- **Smallest fix:** conversion and envelope extraction moved into `_convert_answers`/`_convert_envelope`
  behind a `JevProviderError` boundary; a malformed shape raises
  `PROVIDER_RESPONSE_MALFORMED`, which `JevService` already persists as a failed evaluation and
  `run_wide_evaluation` already defers. Unrelated programming defects are not converted.
- **Regression coverage:** `test_malformed_provider_responses_become_typed_provider_errors`,
  `test_malformed_provider_response_is_a_persisted_failure_not_an_abort`,
  `test_one_malformed_provider_response_does_not_abort_the_run`.

### AUD-13: A storage failure after a received body left the attempt unresolved

- **Severity:** Medium (ledger integrity). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `publish()`/`register_artifact()` ran before `gdc_attempt_finish`, so a failure
  there left the attempt `RESERVED` with no failure event.
- **Smallest fix:** the post-body region is wrapped; a failure finalizes the attempt as `FAILED` with
  the response hash, bytes read and error detail before the original storage error propagates, and
  emits `GDC_REQUEST_FAILED`. A generic guard also finalizes any other post-reserve exception. No
  lease or job framework was added.
- **Regression coverage:** `test_received_body_storage_failure_leaves_no_reserved_attempt`;
  `test_usage_counters_update_from_transport_events` asserts the response names its own attempt.

### AUD-14: Impossible negative provider counts were accepted

- **Severity:** Medium (evidence integrity). **Disposition:** CONFIRMED → fixed.
- **Root cause:** count fields were validated only for type, not for sign.
- **Smallest fix:** one shared `_nonnegative_count` helper (`_optional_count`/`_required_count`)
  applied to project case/file counts, aggregation `doc_count`, `hits.total.value`, SSM coverage
  counts and expression availability counts. An observed zero stays valid.
- **Regression coverage:** `test_negative_provider_counts_fail_closed`,
  `test_observed_zero_counts_are_still_accepted`.

### AUD-15: Jev cache identity treated a requested model alias as resolved

- **Severity:** Medium (reproducibility). **Disposition:** CONFIRMED → fixed.
- **Root cause:** the cache key was computed from the configured model name before the provider was
  called, so a mutable alias could reuse an earlier resolution's judgments.
- **Smallest fix:** cache reuse requires a pinned/versioned model identity
  (`is_pinned_model_identity`) and a provider resolution equal to it; nothing is cached otherwise.
  Requested and resolved model identity stay distinct in the persisted evaluation.
- **Regression coverage:** `test_only_pinned_model_identities_are_cache_eligible`,
  `test_mutable_model_alias_is_never_treated_as_a_resolved_identity`,
  `test_divergent_provider_resolution_is_not_cached_under_the_requested_identity`.

### AUD-16: `question_set_hash()` ignored the applicability rule

- **Severity:** Medium (semantic identity). **Disposition:** CONFIRMED → fixed.
- **Root cause:** the hash covered wording, criteria, primitive and version only, so a changed
  applicability rule left cached judgments semantically stale.
- **Smallest fix:** `applicability_rule` added to the question-set hash payload (wide-v3 wording and
  question IDs are unchanged; only the cache identity moves).
- **Regression coverage:** `test_question_set_hash_covers_semantics`.

### AUD-17: An old `contract_version` cache row permanently blocked new storage

- **Severity:** Medium (cache correctness). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `gdc_cache` was keyed by request hash alone with `ON CONFLICT DO NOTHING`, so a row
  written under an older transport contract could never be replaced, making the request a permanent
  cache miss.
- **Smallest fix:** the cache key is `<contract_version>:<canonical request hash>` (schema 4), so an
  older entry stays immutable while the current contract's entry stores normally.
- **Regression coverage:** `test_stale_contract_version_cache_row_cannot_block_a_new_entry`.

### AUD-18: Persistence leaked out of `storage`

- **Severity:** Medium (ownership). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `research/*` and `jev/*` contained raw INSERT/UPDATE/SELECT statements, and
  `JevService` read `repository.database` directly.
- **Smallest fix:** narrow `Repository` registration/lookup methods for states, candidates, evidence
  states, hypotheses, follow-up executions, dossiers, Jev evaluations/cache and projections; callers
  register records inside the existing event + registrations transaction. No ORM/DAO/service layer
  and no second repository was introduced.
- **Regression coverage:** `test_research_and_jev_modules_own_no_persistence_sql`.

### AUD-19: StatisticalState sources could not identify their acquisition; tested-universe identity undocumented

- **Severity:** Medium (provenance). **Disposition:** CONFIRMED → fixed (documented and tested).
- **Root cause:** every source carried `request_id: None` and omitted cache status; the identity rule
  covering attempt/cache fields and `examined_genes_hash` was implicit.
- **Smallest fix:** `GDCResponse` carries `request_id`/`attempt_no`; sources now record
  `request_id`, `attempt_no` and `from_cache` alongside the logical request hash, response artifact,
  response hash and scientific locator. `docs/` and `statistical_state_identity_payload` now state the
  identity rule explicitly: scientific evidence plus tested context define identity; an observed
  measurement, population/method/unit change and a changed examined gene universe change it, while
  attempt links, artifact ids, timestamps, provider rank and provider `_score` do not.
- **Regression coverage:** `test_live_replay_links_scientific_sources_to_the_responses_that_supplied_them`,
  `test_state_identity_excludes_attempt_and_cache_link_fields`,
  `test_state_identity_excludes_provider_ranking_metadata`,
  `test_state_identity_tracks_measurement_and_tested_context_changes`.

Additionally fixed in the same pass (no prior audit entry):

- **Expression availability merge** could list a gene as both observed and missing after merging
  batches (`cancerjev/research/live.py`); merged observed and missing genes are now disjoint, with
  the per-batch parse → merge path covered by
  `test_expression_availability_merge_keeps_observed_and_missing_genes_disjoint`.
- **`CANCERJEV_JEV_TIMEOUT_SECONDS`** bypassed the bounded-seconds pattern
  (`cancerjev/config.py`); NaN, Infinity, `0`, negative values and values above the 30 s cap are now
  rejected (`test_impossible_jev_timeouts_are_rejected`,
  `test_lowered_jev_timeout_is_accepted_and_effective`).
- **Dangling candidate/evidence/follow-up/hypothesis provenance** was accepted
  (`cancerjev/storage/database.py`); schema 4 declares the relational constraints, covered by
  `test_dangling_candidate_evidence_and_followup_provenance_is_rejected`.

## Remaining Findings (not fixed)

- **Medium — RunEvent payload shape is not validated per event type** (`cancerjev/domain/events.py`):
  a registered event can be persisted with `data={}`; `message` uses character count, not UTF-8
  bytes. Deferred: no current correctness defect requires per-event typed payload classes.
- **Medium — default Playwright origin conflicts with the default API CORS origin**
  (`apps/web/playwright.config.ts`, `cancerjev/config.py`, `apps/api/main.py`). Deferred:
  local-development polish; the verified E2E procedure uses matching `localhost` origins.
- **Low — repeated identical GDC cache hits collapse into one RunEvent**
  (`cancerjev/gdc/transport.py`): idempotency key uses only the request hash.
- **Low — `show --events` silently stops at 500 events** (`cancerjev/cli/main.py`). Deferred:
  CLI event pagination.
- **Low — artifact responses omit `X-Artifact-Id`/`X-Artifact-SHA256`** (`apps/api/routes.py`).
  Deferred: generic response-header polish.
- **Low — wrongly typed cursor fields can produce a storage 503 instead of a 422**
  (`cancerjev/storage/repositories.py`). Deferred: cursor-validation edge cleanup.
- **Low — OpenAPI metadata version disagrees with `/api/system` and omits response DTOs**
  (`apps/api/main.py`). Deferred: OpenAPI cleanup.
- **Low — a Playwright process-exit wait can miss the `close` event**
  (`apps/web/tests/phase1.spec.ts`). Deferred: Playwright test harness polish.
- **RISK — whole-attempt deadlines are not implemented** (`cancerjev/gdc/transport.py`): a peer
  sending data before the socket timeout can keep an attempt alive for a long time. Deferred: no
  concrete correctness defect requires whole-request deadlines yet; the per-attempt terminal ledger
  status and per-response byte caps bound the damage.

## Environment and Non-Bug Findings

- GitHub Actions run `35784234662` for `d1ab646` succeeded for the Python, frontend, and browser
  jobs. This validates the pushed base commit; the two hardening passes were verified locally
  (Ruff, offline pytest, frontend typecheck/build, Playwright against a local fixture API) with no
  live provider call.
- `npm audit --omit=dev --audit-level=moderate` found zero production frontend vulnerabilities.
- `python -m pip check` reports that the shared interpreter's unrelated `hermes-agent 0.7.0`
  requires `pydantic>=2.12.5`, while `pydantic 2.12.4` is installed. This is not a repository
  dependency failure; do not upgrade the shared interpreter as part of this repository fix.
- Windows pytest emits an ignored `PermissionError` at exit while cleaning its temporary
  `pytest-current` symlink. The test process exits successfully.

## Phase 3 Status

- **Implemented:** one-project projection, `wide-v3` questions, applicability, deterministic
  evidence gates, `wide-policy-v2` admission/abstention, separate baseline ranking, maximum-three
  promotion, event/artifact persistence, and UI.
- **Verified:** offline regression, browser E2E, successful GitHub CI for the base commit, and one
  bounded live GDC + TypeSafe run.
- **Still unverified:** question quality, threshold calibration, decision usefulness, and
  baseline-vs-Jev incremental value.

## Audit pass 3 (2026-09-23, Phase 4 deep Jev fan-out)

Performed while implementing and live-validating the next stage (operator-approved candidate
selection → E0/E1 → one Deep Jev fan-out → Python next-move decision). Two of the five defects below
were found only by the bounded live run; each is fixed with regression coverage.

### AUD-20: the deep judgment's provider call was missing from provider usage

- **Severity:** Medium (usage accounting). **Disposition:** CONFIRMED live → fixed.
- **Root cause:** the usage reducer counted `JEV_WIDE_STATE_EVALUATED`, `JEV_DEEP_COMPLETED` and
  `JEV_EVALUATION_FAILED`; the live deep fan-out records `JEV_DEEP_EVIDENCE_JUDGED`, so the live deep
  call and its tokens never reached `provider_usage` (the retained run showed `jev_calls: 1` for two
  provider calls; the deep tokens were visible only inside the run's `deep` summary).
- **Smallest fix:** add `JEV_DEEP_EVIDENCE_JUDGED` to the counted set
  (`cancerjev/storage/repositories.py`).
- **Regression coverage:** the operator-selection integration test asserts
  `provider_usage["jev_calls"] == wide + 1` and `jev_input_tokens` includes the deep usage.

### AUD-21: EvidenceState identity bound the source state's artifact byte hash

- **Severity:** Medium (identity and cache correctness). **Disposition:** CONFIRMED live → fixed.
- **Root cause:** the schema-2 evidence identity payload included
  `source_statistical_state.state_artifact_sha256`. That hash covers the StatisticalState artifact
  *bytes*, which contain run timestamps, so two runs with identical scientific state produced
  different E1 identities (live: `bdad32c4…` vs `7f1a042f…`) and the deep projection therefore missed
  its cache. It also contradicted the documented rule that timestamps never define identity.
- **Smallest fix:** bind the source revision by its scientific `state_identity_hash` only; the
  artifact byte hash stays in E1 provenance as an operational record
  (`cancerjev/domain/identity.py`).
- **Live confirmation:** the same content then produced one identity, and a subsequent bounded run
  reused 10/10 wide judgments *and* the deep judgment with `jev_calls: 0`.
- **Regression coverage:** `test_evidence_identity_excludes_operational_fields_and_tracks_outcomes`
  now mutates `state_artifact_sha256` too; `test_projection_is_deterministic_and_operational_id_free`
  asserts revision-content projections hash equally.

### AUD-22: `--deep-action` without `--deep-candidate` was silently ignored

- **Severity:** Low (operator interface). **Disposition:** CONFIRMED (reproduced) → fixed.
- **Root cause:** the action id was validated against the registry, but the deep slice only runs for
  an explicit candidate, so the flag had no effect.
- **Smallest fix:** `--deep-action` now requires `--deep-candidate` (`cancerjev/cli/main.py`).
- **Regression coverage:** exercised by the CLI validation path (the flag combination now exits with a
  typed message).

### AUD-23: acceptance input artifact recorded `verified: None`

- **Severity:** Low (evidence provenance clarity). **Disposition:** CONFIRMED (code reading) → fixed.
- **Root cause:** `execute()` recorded the StatisticalState input artifact with `verified: None`
  although E0 acceptance verifies the artifact hash and the recorded `state_hash` before use.
- **Smallest fix:** record `verified: True` for that verified input (`cancerjev/science/actions.py`),
  so a reader can distinguish verified from unverifiable inputs.

### AUD-24: duplicate reducer mapping would have shadowed a counter

- **Severity:** Medium (would have been a regression). **Disposition:** CONFIRMED during the change →
  fixed before commit.
- **Root cause:** adding `JEV_WIDE_STATE_EVALUATED → jev_evaluations` to the increments map created a
  second key for the same event type, shadowing `states_evaluated` (later keys win) and
  double-counting wide evaluations with the existing special-case increment.
- **Smallest fix:** keep one mapping per event type and let `JEV_DEEP_EVIDENCE_JUDGED` be the single
  deep-evaluation record (`cancerjev/storage/repositories.py`); the live deep fan-out stops emitting
  the fixture-lane `JEV_DEEP_COMPLETED` summary so no evaluation is counted twice.

### Observations (not defects)

- `states_evaluated` counts successful wide evaluations while `jev_evaluations` counts every
  evaluation record (including failures and deep judgments). The names are intentional: a failed
  judgment leaves a state without a judgment. Live run `a167190d` showed `states_evaluated: 9` with
  `jev_evaluations: 10` for exactly this reason.
- The wide projection's `eligible_followups` field is always empty; the deep projection supplies the
  real eligible action set. Populating it in the wide projection would change `wide-v3` inputs and
  therefore requires a new versioned question/projection task.
- Deep projections are published as immutable artifacts and recorded by `JEV_PROJECTION_CREATED`, but
  are not rows in `jev_projections` (that table indexes `(state_id, projection_version)` for wide
  reuse). Adding an `input_ref` pair there is a schema change deferred until another change requires
  one; the cache, not the table, provides deep reuse.
- Live provider behaviour: one `wide-v3` judgment failed validation with
  `INVALID_DISTRIBUTION` (a Choice distribution summed to 0.99). Containment worked: the state was
  deferred, the failure persisted, and the run continued to `ABSTAIN`. The identical request
  succeeded on a later run, so this is provider variance, not a deterministic defect.

### AUD-25: CLI opened the database and lock before refusing a missing Jev key

- **Severity:** Low (hygiene; no correctness impact). **Disposition:** CONFIRMED (reproduced: an
  empty schema-4 database and a zero-byte `research.lock` were created in the default data directory
  by a refused `--live --jev` invocation) → fixed.
- **Root cause:** flag validation ran after `Settings.from_env()`, `Database.bootstrap()` and lock
  acquisition, so a run that could never proceed still created state (and the key check was duplicated
  inside the lock scope).
- **Smallest fix:** all flag requirements (including the `TYPESAFE_API_KEY` requirement) are validated
  before any service is constructed (`cancerjev/cli/main.py`); `show`/`probe` keep their behaviour and
  the duplicate check is removed.
- **Verification:** the same refused invocation now leaves `data/` untouched.

### AUD-26: moving flag validation earlier stopped `.env.local` from loading before the Jev key check

- **Severity:** High for the live path (regression introduced by the AUD-25 fix). **Disposition:**
  CONFIRMED live → fixed.
- **Root cause:** `load_local_env()` is called inside `Settings.from_env()`; AUD-25 moved the
  `TYPESAFE_API_KEY` requirement ahead of `Settings.from_env()`, so a configured key was no longer
  loaded when the check ran and every `--jev` run with `.env.local` refused to start. Offline tests
  could not catch it because they disable dotenv and set the key explicitly.
- **Smallest fix:** call `load_local_env()` at the start of `main()` before any flag validation
  (`cancerjev/cli/main.py`); `Settings.from_env()` keeps its idempotent call since process-environment
  values still win.
- **Live confirmation:** the bounded dispatch validation then ran end-to-end (16 GDC cache hits,
  10/10 wide judgments reused, one deep provider call).

## Audit pass 4 (2026-09-23, post-dispatch-stage review)

Read-only, provider-free review of the dispatch stage plus targeted probes of the API and the
dispatched-run chain. Eight findings, seven fixed with regression coverage; refuted candidates are
recorded so the checks are visible.

### AUD-27: a retired action version was reported as a contradiction

- **Severity:** Medium (false contradiction). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `REVISION_CHAIN_LINKED` treated any mismatch between the version a revision cites and
  the registry's current version as `CONTRADICTED`. Once an action's version is bumped, every
  historical revision would be flagged as untrustworthy even though nothing was wrong with it.
- **Smallest fix:** distinguish an unregistered action id (still `CONTRADICTED`) from a registered
  action whose cited version the registry no longer holds (now `NOT_OBSERVED` with an explicit note);
  registered in the check's limitations.
- **Regression coverage:** `test_unregistered_producing_action_is_contradicted`,
  `test_revision_without_a_citing_action_is_contradicted`,
  `test_retired_producing_action_version_is_not_observed_not_contradicted`,
  `test_baseline_revision_is_ineligible_for_the_revision_action`.

### AUD-28: a failed follow-up attempt did not consume follow-up budget

- **Severity:** Medium (budget honesty). **Disposition:** CONFIRMED → fixed.
- **Root cause:** the dispatch cap counted only `COMPLETED` executions, so a failed action attempt was
  free and could be retried in a later run without consuming the candidate's follow-up budget.
- **Smallest fix:** count every attempted execution (`cancerjev/research/deep.py`), with the reason
  detail stating that a failed attempt consumes budget too; documented in `SCIENTIFIC_INVARIANTS.md`.
- **Regression coverage:** `test_a_failed_attempt_consumes_follow_up_budget` (inserts a `FAILED`
  execution row and asserts the refusal that the old completed-only rule would not have produced).

### AUD-29: the run metric labelled operator-approved candidates as wide candidates

- **Severity:** Low (misleading presentation). **Disposition:** CONFIRMED by probe → fixed.
- **Evidence:** a live probe run with an abstaining policy and an operator selection recorded
  `candidates_promoted: 1` while `JEV_WIDE_COMPLETED` recorded `admission_decision: ABSTAIN` and
  `promoted: 0`, so the card read "Wide candidates 1" for a candidate wide admission never admitted.
- **Smallest fix:** the metric now reads "Candidates promoted"; `UI_SPEC.md` states that an operator
  selection counts as a promotion and consumes a slot.

### AUD-30: a failed or empty deep judgment rendered as a blank judgment

- **Severity:** Low (UI honesty). **Disposition:** CONFIRMED (code reading) → fixed.
- **Root cause:** the panel built its label from answer dimensions only, so a persisted failed
  evaluation (`answers: {}`) rendered as "deep judgment: " with no indication that the judgment failed.
- **Smallest fix:** `judgmentLabel` renders `deep judgment failed: <code> (the revision stands)` or
  "deep judgment recorded with no usable answers"; the wide judgment panel still excludes deep rows.

### AUD-31: the dispatch summary could not name the dispatched revision's judgment

- **Severity:** Low (reporting completeness). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `DispatchResult.summary()` returned the new move but omitted the second deep
  evaluation's identifiers, so the operator-facing run summary could not trace the dispatched
  revision's judgment even though the event and DB rows carried it.
- **Smallest fix:** the summary now includes `result_status` and the judgment summary
  (evaluation id, model, usage, error, question-set version) minus the full vector.

### AUD-32: operator selection silently truncated its state index

- **Severity:** Low (robustness). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `_deep_state_index` used the default 200-row limit for both states and wide
  evaluations, so a larger run's evaluated states could be missing from the index and an operator
  selection would be refused with "no statistical state has that gene symbol".
- **Smallest fix:** query with the documented 1,000-state ceiling for both.

### AUD-33: provenance comparison ignored the parser version

- **Severity:** Low (audit strictness). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `SOURCE_PROVENANCE_UNCHANGED` compared endpoint, canonical request hash and response
  hash only, so a revision whose provenance recorded a different `parser_version` for the same bytes
  still passed.
- **Smallest fix:** the comparison now includes the parser version, and the check's claim states it.

### AUD-34: undeclared query parameters are silently ignored (documented, not fixed)

- **Severity:** Low (API contract). **Disposition:** CONFIRMED by probe → **deferred**.
- **Evidence:** `GET /api/runs/{id}/evidence?status=FAILED` returns `200` with unfiltered rows because
  FastAPI ignores parameters a route does not declare; the same holds for every list endpoint.
- **Why not fixed here:** rejecting undeclared parameters is a repository-wide API-contract change
  (strict parameter handling plus client audit) that belongs with the already-deferred OpenAPI
  cleanup, and no current client sends undeclared parameters. Recorded so it is not mistaken for a
  working filter.

### Refuted candidates (checked, no defect)

- **Repeated stage names collapse:** `_stage` keys each event with a `uuid4` suffix; the dispatched
  probe recorded four `FOLLOWUP` stage occurrences (two started/two completed) and 50 distinct
  idempotency keys across 50 events.
- **Duplicate idempotency keys re-run registrations:** `append_event` returns the existing event and
  skips registrations, which is the intended idempotency contract.
- **Interrupted live candidates are lost:** `recover_interrupted` selects by terminal-status negation,
  so `DEEP_ANALYSIS`/`DEEP_ANALYZED` candidates are deferred correctly.
- **Deep cache identity leaks run state:** the evidence projection excludes revision/run/candidate
  ids, timestamps and artifact ids; a probe of two runs showed the same content reusing the judgment.
- **Dead code:** the unused `DeepPlan.eligible_action_ids` property was removed, and
  `nextmove.MOVES` is now asserted by a test so the declared move vocabulary is load-bearing.

## Audit pass 5 (2026-09-23, combined-repo review after Phase 4–6 completion)

Review of the whole repository after the bounded arc, live dossier, hypothesis engine and evaluation
harness landed, with a focus on the new code paths and their interaction with existing invariants.

### AUD-35: a dispatched revision was judged twice and the second decision was silently dropped

- **Severity:** High (correctness, cost and recorded-stream integrity). **Disposition:** CONFIRMED by
  probe → fixed.
- **Root cause:** `dispatch_recorded_move` judged the revision it had just produced, and the
  investigation loop judged the same revision again on its next step. The duplicate judgment wasted a
  provider call whenever the cache did not absorb it, appended a duplicate step to the arc summary,
  and emitted `JEV_DEEP_STARTED`/`NEXT_MOVE_SELECTED` with identical idempotency keys which
  `append_event` silently de-duplicated — so the recorded event stream no longer matched the intended
  loop (probe: three `JEV_DEEP_EVIDENCE_JUDGED` events, two `NEXT_MOVE_SELECTED`).
- **Smallest fix:** dispatch decides and executes only; the caller judges each revision exactly once
  (`cancerjev/research/deep.py`, `cancerjev/research/investigation.py`). `DispatchResult` no longer
  carries a judgment; the arc summary exposes the successful dispatch as `dispatch` and the final
  refusal as `last_dispatch`.
- **Regression coverage:** `test_authorized_follow_up_dispatches_one_revision_and_rejudges_it`
  asserts exactly two steps for two revisions, one judgment per step, two `NEXT_MOVE_DISPATCHED`
  records (one success plus the closing refusal) and no duplicate `NEXT_MOVE_SELECTED`.

### AUD-36: an in-repo LLM HTTP call violated the open-access and credential boundary

- **Severity:** High (safety boundary). **Disposition:** CONFIRMED by the existing guard test → fixed.
- **Root cause:** the first Phase 6 implementation called OpenRouter directly with a bearer
  authorization header and read a provider key from the environment. The repository's guard test
  (`test_no_source_file_uses_an_authentication_header_literal`) correctly failed, and the change
  contradicted the documented rule that this tool uses *only* anonymous public GDC access with no
  token or credential handling.
- **Smallest fix:** the HTTP path, provider URL, key lookup and provider contract were removed.
  Generation is deterministic by default; an LLM is only ever a **generator injected by the caller**,
  and its output is validated strictly (schema, non-empty statement, distinguishing tests restricted
  to eligible registered actions) with a typed `UNAVAILABLE` outcome on any deviation. Nothing in the
  repository performs a model request or holds a provider credential.
- **Regression coverage:** `test_configured_llm_generation_is_labelled_bound_and_uses_its_own_usage`,
  `test_malformed_llm_response_is_a_typed_unavailability`,
  `test_malformed_generator_output_is_rejected_without_storing_anything`.

### AUD-37: the rankings API route read SQL directly

- **Severity:** Low (ownership consistency). **Disposition:** CONFIRMED → fixed.
- **Root cause:** `/api/runs/{id}/rankings` queried `artifacts` through `repository.database`,
  bypassing the narrow-method rule this repository enforces for `research`/`jev`.
- **Smallest fix:** added `Repository.ranking_artifacts(run_id)` and used it in the route and in the
  evaluation harness, so no layer outside `storage` reads the database directly.
- **Regression coverage:** the existing API contract tests plus `test_deep_slice_is_visible_through_the_api`.

### AUD-38: the live hypotheses panel was unreachable and mislabelled

- **Severity:** Low (presentation). **Disposition:** CONFIRMED → fixed.
- **Root cause:** the hypotheses section rendered only inside the fixture branch, so live hypotheses
  were fetched but never shown, and its eyebrow read "GENERATED FIXTURE HYPOTHESES" for any run.
- **Smallest fix:** live runs render their own labelled section ("GENERATED HYPOTHESES — NOT EVIDENCE")
  with the generator, statement, hypothetical mechanism and falsification criteria; the fixture branch
  keeps its own wording. The dossier callout distinguishes live from synthetic dossiers.

### Reviewed and refuted

- **Loop termination:** the bounded arc terminates because `dispatch_recorded_move` refuses at
  `FOLLOWUP_LIMIT`/`EVIDENCE_ITERATION_LIMIT` and a `MAX_INVESTIGATION_STEPS` guard bounds the loop
  independently; the authorized test reaches exactly two steps and stops on `MOVE_NOT_FOLLOW_UP`.
- **Duplicate stage events for repeated stage names:** `_stage` keys each event with a `uuid4`
  suffix, so repeated `FOLLOWUP`/`JEV_DEEP` stages are all recorded (probe: 4 `FOLLOWUP` occurrences).
- **Hypothesis applicability and validation:** the `hypothesis_present` rule and strict draft
  validation reject ineligible-question answers and unknown action ids (exercised by the stub adapter
  failing closed on a mixed answer set during development).
- **Dossier completeness:** every `DOSSIER_SECTIONS` key is present with an explicit
  availability/reason, so the renderer never prints an undefined section, and a live dossier carries
  no synthetic warning.
- **Evaluation harness:** it refuses a missing baseline/Jev ranking pair, bounds `k` to 1..3, requires
  a pre-registered protocol/rationale/declaration/source/limitations, and states no superiority claim.

## Audit pass 6 (2026-09-23, audit findings fixed and re-verified)

The pass-5 findings were fixed with regression coverage. Each entry names the fix and the test that now
holds it.

- **AUD-35 (double judgment)** — dispatch decides and executes only; the loop judges each revision
  exactly once. `test_authorized_follow_up_dispatches_one_revision_and_rejudges_it` asserts two steps,
  one judgment per step and no duplicate `NEXT_MOVE_SELECTED`.
- **AUD-36 (in-repo LLM call)** — the HTTP path, provider URL, key lookup and provider contract were
  removed; generation is deterministic by default and an LLM is only ever an injected generator whose
  output is validated strictly. `LLM_GENERATOR` was renamed `INJECTED_GENERATOR`, and the inert
  `CANCERJEV_LLM_MODEL`/`CANCERJEV_LLM_TIMEOUT_SECONDS` settings were deleted (nothing consumes them;
  asserting they cannot exist is now a test).
- **AUD-37 (rankings SQL in the API)** — `/api/runs/{id}/rankings` uses `Repository.ranking_artifacts`.
- **AUD-38 (unreachable live hypotheses panel)** — live runs render their own labelled section.
- **AUD-39 (NEW, fixed): live hypothesis reviews were recorded as `JEV_DEEP_EVIDENCE_JUDGED`.**
  `_persist_evaluation` overwrote the caller's `event_type`, so `evaluate_hypothesis`'s
  `HYPOTHESIS_EVALUATED` never reached the stream while the evaluation row and the message looked
  correct; the reducer's `HYPOTHESIS_EVALUATED` mapping was dead for live runs and any per-revision
  judgment count over-counted. Fixed by honouring the passed event type; covered by
  `test_live_hypothesis_review_is_recorded_as_hypothesis_evaluated` (2 reviews, one deep judgment per
  step, revision and generator named in the data).
- **AUD-40 (NEW, fixed): hypothesis reviews were never reused across runs.** The hypothesis projection
  carried the run-specific `hypothesis_id`, so the cache key changed every run and each identical
  review cost another provider call. The id is excluded from the projection (the record keeps it);
  covered by `test_hypothesis_projection_excludes_the_run_specific_id` and
  `test_identical_generated_text_reuses_its_review_across_runs`.
- **AUD-41 (NEW, fixed): oversized or non-list generated output could fail a run or be stored as
  garbage.** A 70 KB statement raised `ProjectionError` out of the run, and a string `predictions` field
  was exploded into characters. Generated text is now bounded (`MAX_TEXT_CHARS`, `MAX_LIST_ITEMS`) with
  all list fields required to be lists of strings, and a projection failure is a persisted typed failure
  rather than a run abort; covered by `test_oversized_or_malformed_generated_output_is_rejected_typed`.
- **AUD-42 (NEW, fixed): one candidate's dossier listed another candidate's hypothesis reviews.**
  The dossier stage filtered hypothesis evaluations only by purpose; it now filters by candidate and by
  the candidate's own hypothesis ids, and it reports the deep judgment's real question-set version and
  model instead of a literal and `n/a`; covered by
  `test_multi_candidate_dossiers_keep_their_own_reviews_and_model`.
- **AUD-43 (NEW, fixed): the hypothesis bound was silent and template text could quote unobserved
  numbers.** Reaching `MAX_HYPOTHESES` now records `HYPOTHESES_GENERATED` with
  `outcome=NO_NEW_HYPOTHESES`, and template statements phrase an unobserved metric as "not observed"
  instead of printing `None`; covered by `test_hypothesis_bound_is_recorded_when_already_reached` and
  `test_template_phrasing_never_quotes_an_unobserved_metric`.
- **AUD-44 (NEW, fixed): duplicate selections were silently absorbed.** Selections are de-duplicated in
  order and each dropped duplicate records `DEEP_SELECTION_UNAVAILABLE` with
  `reason_code=DUPLICATE_SELECTION`; covered by
  `test_duplicate_selection_is_de_duplicated_with_a_typed_notice`.
- **AUD-45 (NEW, fixed): the loop guard bound the cap at import time.** The guard now reads
  `FOLLOWUP_LIMIT` at call time, so reconfiguring the cap cannot leave a stale backstop.

## Audit pass 7 (2026-09-23, live OpenRouter provider testing)

The owner requested live generated-text testing through OpenRouter with `deepseek/deepseek-v4.1-flash`.
The work below was driven by what the live provider actually did; each item has a regression test or a
recorded rationale.

### AUD-46: the open-access authentication guard needed a deliberate, single-module seam

- **Disposition:** deliberate narrowing, documented and asserted. The guard test previously failed any
  `Authorization` header literal anywhere in `cancerjev/`. The GDC boundary stays strictly anonymous and
  is now asserted separately (`test_only_the_opt_in_provider_module_may_authenticate` asserts the GDC
  tree has zero auth literals), while exactly one allow-listed module may carry a provider header.
- **Why:** an LLM provider is a different provider from GDC; the owner authorised it, and the credential
  stays environment-only, is never persisted, never logged and never enters a request body or any record.
  Any other module adding an auth header still fails the test.

### AUD-47: an unbounded reasoning completion hung the request for ten minutes

- **Severity:** High (hang/cost). **Disposition:** CONFIRMED live → fixed.
- **Root cause:** the adapter sent no `max_tokens`. A reasoning model streams reasoning tokens before
  emitting content, so the socket timeout (which bounds one read) never fired and the whole call hung;
  with a small budget the same model returned `content: None` while reporting consumed tokens.
- **Fix:** bounded completion (`MAX_OUTPUT_TOKENS = 6000`), a whole-request deadline checked between
  chunk reads (`LLM_DEADLINE_EXCEEDED`), `reasoning.effort = low`, and a typed `LLM_EMPTY_CONTENT` that
  reports `finish_reason` and the reasoning length instead of a confusing JSON error.
- **Coverage:** `test_request_bounds_the_completion_and_enforces_a_whole_request_deadline`.

### AUD-48: fenced JSON output was rejected as malformed

- **Severity:** Medium (availability). **Disposition:** CONFIRMED live (same request parsed cleanly on a
  repeat) → fixed.
- **Fix:** a bounded single markdown-fence extraction before failing; the extracted payload is still
  parsed as JSON and every draft is still strictly validated afterwards, so no text is trusted.

### AUD-49: the 120 s LLM timeout was rejected by a 30 s cap

- **Disposition:** DELIBERATE change with rationale: the LLM timeout cap is now 120 s (default 120 s,
  setting may be lowered only), documented in `docs/GDC_BUDGETS.md`, because a reasoning model spends
  part of its bounded completion on reasoning. This is an operational provider setting, not a measured
  evidence limit, and the change is recorded rather than made to finish work.

### AUD-50: operator-requested hypothesis generation

- **Disposition:** implemented. Live `deep-v1` judgments recorded `COMPLETE` for every candidate tried
  (`next_step_warranted ~0.53`, `stopping_more_honest ~0.58`), so the policy never asks for hypotheses.
  The thresholds were **not** tuned. Instead `--deep-hypotheses` lets an operator request bounded
  generation for the current revision; the recorded move is never rewritten, the request is recorded as
  `requested_reason = OPERATOR_REQUESTED_HYPOTHESES`, and all existing bounds still apply.
- **Coverage:** `test_operator_request_generates_hypotheses_without_rewriting_the_move`.

### AUD-51: the provider name was reported as the generic default

- **Severity:** Low (provenance). **Disposition:** CONFIRMED by test → fixed: `GeneratedHypotheses`
  carried `injected-generator-v1` while the stored records carried `openrouter-chat-v1`. The name now
  comes from the injected generator (`getattr(generator, "name", …)`), and a failure reports the
  provider that failed.

### AUD-52: the dossier printed `None:` for hypothesis reviews

- **Severity:** Low (presentation). **Disposition:** CONFIRMED live → fixed: the review narrative read a
  `label` field the evaluation vector does not carry; it now names the hypothesis id, generator and
  question-set version, plus testable and exceeds-evidence probabilities.

### Live result (run `204e57b8`, retained in `data/live-e2e-20260923/`)

16 GDC cache hits, 10 wide judgments reused, 1 deep judgment, **1 OpenRouter call** (315 in / 3,364 out
tokens, `deepseek/deepseek-v4.1-flash`) producing two competing, falsifiable hypotheses that quote only
recorded numbers (393 of 585 examined, 518 expression cases, 67 missing); each was reviewed by
`hypothesis-v2` (testable 0.68/0.66, exceeds-recorded-evidence 0.79/0.77, dominant unsupported
assumption `OTHER`) and both reviews were recorded as `HYPOTHESIS_EVALUATED` (AUD-39 fix verified live).
The dossier carried the LLM notice and `OBSERVED` sections for competing hypotheses, reviews, provider
metadata and falsification criteria. The recorded move stayed `COMPLETE`.

## Recommended Follow-Up

1. Complete the baseline-vs-Jev evaluation with a predefined labeled/decision-quality protocol;
   do not lower thresholds merely to obtain promotions.
2. ~~Work the remaining medium findings (attempt finalization, source provenance, TypeSafe failure
   containment, resolved-model cache identity) before Phase 4~~ **DONE (2026-09-23)**: AUD-12 through
   AUD-19 fixed attempt finalization, source provenance, provider-failure containment, pinned cache
   identity, tested-universe identity, cache versioning, impossible counts and storage ownership.
3. Keep Phase 4 execution gated on a cohort-applicable deterministic method contract and immutable
   evidence provenance. See `docs/PHASE_4_READINESS_PLAN.md`.