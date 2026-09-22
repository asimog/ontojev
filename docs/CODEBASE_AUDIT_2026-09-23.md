# Codebase Audit and Bug Report

Audit date: 2026-09-23  
Audited base commit: `d1ab646` (`main`, pushed to `origin/main`)  
Hardening pass: safety/science and UI defects below are fixed in the working tree with
provider-free regression tests; the remaining findings are listed with severity and location and
are **not** fixed.

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

## Remaining Findings (not fixed)

- **Medium — a storage failure after a received body leaves the attempt unresolved**
  (`cancerjev/gdc/transport.py`): `publish()`/persistence errors after a successful read are outside
  the typed failure path, so the attempt can remain `RESERVED` with no failure event.
- **Medium — StatisticalState sources cannot identify the request or cache origin**
  (`cancerjev/research/live.py`): every source has `request_id: None` and omits cache status and the
  original acquisition time.
- **Medium — a malformed TypeSafe response can abort the whole live run**
  (`cancerjev/jev/typesafe_adapter.py`, `research/wide.py`): conversion errors outside the provider
  call are not converted to a persisted per-state failure/deferral.
- **Medium — Jev cache identity uses the requested model string, not the resolved model**
  (`cancerjev/jev/service.py`): a mutable alias can reuse judgments from an earlier resolution.
- **Medium — RunEvent payload shape is not validated per event type** (`cancerjev/domain/events.py`):
  a registered event can be persisted with `data={}`; `message` uses character count, not UTF-8
  bytes.
- **Medium — database does not enforce documented candidate/evidence relationships**
  (`cancerjev/storage/database.py`): dangling references are accepted.
- **Medium — default Playwright origin conflicts with the default API CORS origin**
  (`apps/web/playwright.config.ts`, `cancerjev/config.py`, `apps/api/main.py`).
- **Low — repeated identical GDC cache hits collapse into one RunEvent**
  (`cancerjev/gdc/transport.py`): idempotency key uses only the request hash.
- **Low — `show --events` silently stops at 500 events** (`cancerjev/cli/main.py`).
- **Low — artifact responses omit `X-Artifact-Id`/`X-Artifact-SHA256`** (`apps/api/routes.py`).
- **Low — wrongly typed cursor fields can produce a storage 503 instead of a 422**
  (`cancerjev/storage/repositories.py`).
- **Low — OpenAPI metadata version disagrees with `/api/system` and omits response DTOs**
  (`apps/api/main.py`).
- **Low — a Playwright process-exit wait can miss the `close` event**
  (`apps/web/tests/phase1.spec.ts`).
- **RISK — whole-attempt deadlines are not implemented** (`cancerjev/gdc/transport.py`): a peer
  sending data before the socket timeout can keep an attempt alive for a long time.

## Environment and Non-Bug Findings

- GitHub Actions run `35784234662` for `d1ab646` succeeded for the Python, frontend, and browser
  jobs. This validates the pushed base, not this uncommitted hardening pass.
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

## Recommended Follow-Up

1. Complete the baseline-vs-Jev evaluation with a predefined labeled/decision-quality protocol;
   do not lower thresholds merely to obtain promotions.
2. Work the remaining medium findings (attempt finalization, source provenance, TypeSafe failure
   containment, resolved-model cache identity) before Phase 4 introduces action side effects.
3. Keep Phase 4 execution gated on a cohort-applicable deterministic method contract and immutable
   evidence provenance. See `docs/PHASE_4_READINESS_PLAN.md`.