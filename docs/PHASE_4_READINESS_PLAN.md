# Phase 4 Readiness Plan

> Historical record; superseded for current status and implementation instructions on 2026-09-24.
> Original dates, results and proposals below are preserved, not newly verified claims.
> Use [implementation status](IMPLEMENTATION_STATUS.md), [architecture](ARCHITECTURE.md),
> [GDC strategy](GDC_STRATEGY.md) and [discovery roadmap](DISCOVERY_ROADMAP.md).
> Existing question versions remain unchanged; historical proposals do not authorize new behavior.

Status: **PHASE 4–6 CORE IMPLEMENTED (2026-09-23): bounded multi-step arc, live dossier, bounded
hypothesis engine with `hypothesis-v2`, and an offline evaluation harness. Phase 7 is deliberately
not implemented.** This document sequences bounded deterministic follow-up work. It does not
authorize new endpoints, expand budgets, or create a runtime workflow framework.

## Completion Status

Phase 3 implementation is complete: `jev-state-projection-v2`, `wide-v3`, deterministic
eligibility, `wide-policy-v2`, `ABSTAIN`, baseline/Jev rankings, and bounded promotion are present
and tested. One live run made ten `wide-v3` evaluations and admitted no states. This verifies the
abstention path; it does not validate the question set, calibrate its thresholds, or show
incremental value over the deterministic baseline. See `docs/IMPLEMENTATION_STATUS.md`.

Phase 4 may proceed to method-contract design, but must not use Jev admission as an autonomous
execution authority until Phase 3's thresholds and incremental value have been evaluated.

## First slice implemented (2026-09-23)

The blockers recorded above are resolved for one narrow vertical slice, and only that slice is
implemented: `Candidate → accepted immutable evidence E0 → one explicitly selected registered
deterministic action → immutable E1`.

- **Blocker (a) no approved deterministic method contract** — RESOLVED for one action:
  `CHECK_EVIDENCE_INTEGRITY_V1` (`EVIDENCE_INTEGRITY_V1` v1) is registered with an explicit question,
  falsifiable interpretation, analysis unit, required evidence, missingness rule and limitations
  (`cancerjev/science/actions.py`). It is an evidence-integrity/reproducibility check, not a new
  biological measurement: it produces `VERIFIED`/`CONTRADICTED`/`NOT_OBSERVED` per check and no
  effect estimate, interval or p-value.
- **Blocker (b) provisional `wide-policy-v2` must not dispatch** — RESOLVED by construction: wide
  admission never selects a follow-up. The operator names one promoted candidate explicitly
  (`run --live --jev --deep-candidate <gene-symbol|slot:N>`, optional `--deep-action`), the rule is
  recorded in `RUN_STARTED`, and an unmatched selection records `DEEP_SELECTION_UNAVAILABLE` instead
  of falling back to policy.
- **Blocker (c) baseline-vs-Jev incremental value unverified** — NOT a blocker for this slice and
  still open: the slice makes no scientific superiority claim and does not depend on Jev admission.
  Keep the evaluation as a separate task.
- **Gates 2–4** are satisfied: E0 is verified against the retained artifact hash and recorded
  `state_hash`; E1 records action/method refs, input artifact hashes, source requests/hashes,
  examined population, observed values, missingness and completeness; budgets
  (`FOLLOWUP_LIMIT = 3`, `EVIDENCE_ITERATION_LIMIT = 2`), idempotency, typed abstention and typed
  failure are Python-owned and event-reduced.
- **Gate 6** is satisfied offline: end-to-end tests cover E0 → eligibility → action → E1, immutability,
  idempotency, failure, abstention and the API/UI representation with zero provider calls.

Still required before the next step, unchanged by this pass: Deep Jev over an E1 revision requires
its own versioned question set (a new versioned task, never a conditional subset of `wide-v3`), and
the Python next-move policy requires an approved selection rule. `CHECK_MISSINGNESS_V1`,
`STRATIFY_BY_PROJECT_V1`, `OUTLIER_SENSITIVITY_V1` and the other documented follow-up IDs remain
unapproved placeholders; a second registered action should be added only when a concrete need
exists.

## Next stage: deep fan-out and next-move decision (IMPLEMENTED 2026-09-23)

After E1, one Deep Jev fan-out judges the revision plus the eligible registered action set with the
versioned `deep-v1` question set, and the Python next-move policy (`deep-policy-v2`) records one typed
move. Implemented and live-validated as described in `docs/IMPLEMENTATION_STATUS.md`; the operator
may also name a wide-evaluated state explicitly when the provisional policy selects nothing
(`gene:<SYMBOL>`/`state:<STATE_ID>`), which creates the candidate with recorded
`operator-selection-v1` provenance and consumes a promotion slot.

Still open for a later slice, unchanged in intent:

- a **second registered deterministic action**, so a recorded `FOLLOW_UP` has something to dispatch
  (today every warranted step with no distinct action is recorded as `NO_FURTHER_REGISTERED_ACTION`);
- dispatching a recorded move, which must stay an explicit operator/later-phase decision and must
  respect the existing `followup_count ≤ 3` / `iteration ≤ 2` caps;
- judging further revisions, multi-candidate iteration and hypothesis generation;
- a separately approved bounded live acceptance for any new action, plus the still-open
  baseline-vs-Jev incremental-value evaluation.

`deep-policy-v2` thresholds are provisional. Do not lower them to force a `FOLLOW_UP`.

## Dispatch stage implemented (2026-09-23)

A recorded `FOLLOW_UP` now has something to dispatch, under explicit operator control:

- `CHECK_REVISION_FAITHFULNESS_V1` (input kind `EVIDENCE_STATE`) verifies that a revision restates the
  accepted evidence exactly, keeps its provenance, binds a matching source artifact and cites a
  registered producing action; the registry now declares an input kind per action and the eligible set
  is computed against the revision it would run on.
- `--deep-followup` authorizes at most **one** dispatch per run for the named candidate; it obeys
  `followup_count ≤ 3` and `iteration ≤ 2`, executes the sorted-first distinct eligible revision
  action, records `E2` with parent `E1`, and re-judges `E2` with the same `deep-v1` fan-out. Every
  refusal (move not `FOLLOW_UP`, not authorized, no distinct action, either cap, action failure) is a
  typed `NEXT_MOVE_DISPATCHED` record.
- The dispatch is a Python step, not a policy side effect: the recorded move still carries
  `executed: false`, and the follow-on decision for `E2` is `NO_FURTHER_REGISTERED_ACTION` because its
  producing action is excluded from its own eligible set.

Still open for a later slice: autonomous iteration beyond one authorized dispatch, a third registered
action, multi-candidate iteration, hypothesis generation, and the separately approved bounded live
acceptance plus the baseline-vs-Jev incremental-value evaluation. `deep-policy-v2` thresholds remain
provisional; do not lower them to force a `FOLLOW_UP`.

## Phase 4–6 completion (IMPLEMENTED 2026-09-23)

- **Bounded arc** (Phase 4): `run_candidate_investigation` composes plan → execute → judge → dispatch
  → judge … bounded by `FOLLOWUP_LIMIT = 3`, `EVIDENCE_ITERATION_LIMIT = 2` and a loop guard; one
  judgment per revision; every refusal typed. `--deep-candidate` is repeatable, so several explicitly
  selected candidates are investigated in order, each within its own caps.
- **Live dossier** (Phase 5): authoritative JSON + derived Markdown over the recorded chain,
  hypotheses and next moves, with per-section availability, the live notice and `DOSSIER_READY`.
- **Hypothesis engine** (Phase 6): the `GENERATE_HYPOTHESES` policy move, bounded generation with
  strict validation, `hypothesis-v2` Jev review, labels naming the generator, and an injected-generator
  boundary — this repository performs no model request and holds no provider credential.
- **Evaluation harness**: `python -m cancerjev evaluate --run <id> --labels <file>` compares recorded
  baseline/Jev tops against an operator-supplied pre-registered label set and reports descriptive
  metrics with an explicit no-superiority claim. It produces no biology labels and no value claim.

Still open after this pass:

- further registered actions (a longer arc needs a second revision action to be informative);
- the opt-in OpenRouter adapter exists and is live-validated; extending it (other providers, budgets,
  cost accounting) stays a separate, explicitly configured change;
- the **incremental-value result**: the harness exists, but a pre-registered protocol over held-out
  labelled cohorts is a scientific task, not a code change, and remains undone;
- Phase 7 offline autoresearch, which needs a labelled historical corpus and human review before any
  question-set versioning engine is justified.

`deep-policy-v2` thresholds remain provisional. Do not lower them to force a `FOLLOW_UP` or a
`GENERATE_HYPOTHESES`.

## Pre-Phase-4 structural check (2026-09-23)

The bounded pre-Phase-4 hardening pass removed the engineering blockers that would otherwise be
baked into Phase 4 and left the provenance chain ready for the first slice:

- Schema 4 declares the relational constraints the slice depends on:
  `statistical_states → candidates.source_state_id`, `candidates → evidence_states.candidate_id`
  (with `previous_evidence_state_id` for revisions), and
  `followup_executions.candidate_id`/`output_evidence_state_id`. A dangling provenance reference now
  fails the event transaction instead of persisting.
- Attempts always reach a terminal ledger status, provider failures are contained per state, and
  `JevService`/`research` no longer own SQL, so an implementing slice inherits the existing atomic
  event + registrations transaction.
- `StatisticalState` provenance links each source to its acquisition attempt without putting
  operational ids into scientific identity.

Still required before implementation of anything further, unchanged by this pass: an approved
deterministic method contract for any *second* follow-up action (the documented IDs are candidates,
not approved), and the separate baseline-vs-Jev incremental-value evaluation. The first slice itself
uses an explicitly selected candidate rather than provisional `wide-policy-v2` admission.

## Proposed First Slice

Build only `E0 -> one registered deterministic follow-up -> E1` for one explicitly selected
candidate and the existing `TCGA-LUAD` cohort. Python owns input validation, eligibility, execution,
budgets, stopping, persistence, and failure handling. Jev may judge supplied evidence only after a
valid `E1` exists; it does not select arbitrary computations or write measured fields.

This slice was implemented as described in "First slice implemented" above, with
`CHECK_EVIDENCE_INTEGRITY_V1` as the one registered action. The action IDs named below remain
proposals for later actions.

Candidate action contracts currently named in the repository include `STRATIFY_BY_PROJECT_V1`,
`LEAVE_ONE_PROJECT_OUT_V1`, `CHECK_MISSINGNESS_V1`, `OUTLIER_SENSITIVITY_V1`, and
`COMPARE_MODALITIES_V1`. These are proposals, not registered executable actions. Because the only
production scope is one project (`TCGA-LUAD`), project-stratification and leave-one-project-out
actions are **NOT APPLICABLE** to the current cohort and must not be selected as the first slice.

`CHECK_MISSINGNESS_V1` is a candidate for contract review, not yet approved; its intended
non-redundant form (recomputing case-level missingness from retained responses and reconciling it
against the recorded state) is partly covered today by the `EXPRESSION_COVERAGE_ARITHMETIC` check of
the implemented `CHECK_EVIDENCE_INTEGRITY_V1`. Before registering it separately, verify which
retained response artifacts and case/gene mappings permit an independently reproducible check beyond
the missingness already recorded in `StatisticalState`. Do not add a ratio, imputation, new
measurement, or follow-up merely to make the action appear novel. If no non-redundant test is
supportable from held evidence, stop and revise the candidate action before implementation.

## Readiness Gates

1. **Scientific contract**
   - Name the question and falsifiable interpretation the follow-up can address.
   - Specify the cohort, examined population, analysis unit, source fields/artifacts, inclusion and
     missingness rules, transformation, estimator, parameters, output units, and method version.
   - Identify the tested family and any multiplicity correction; if none is defined, keep the action
     descriptive and do not emit inferential claims.
   - State explicitly what an absent value means. Missing evidence is not a negative result.

2. **Applicability and held inputs**
   - Define a deterministic eligibility predicate in Python for the selected `ResearchSpec` and
     `StatisticalState`.
   - Prove that every required input is present in immutable retained artifacts or can be acquired
     through an already-allowlisted bounded GDC request.
   - Do not assume project-level replication or sample matching that the one-cohort state does not
     establish. Do not read `/data`, manifests, or download files.

3. **Action and evidence versioning**
   - Register one fixed action ID and a narrow typed argument schema in code. Reject unknown action
     IDs and arguments; no runtime-configurable query or endpoint.
   - Persist an immutable `EvidenceState` revision with parent `E0`, action/method version,
     parameters, input artifact hashes, source request/hash, examined population, result values,
     missingness, and completeness. `E0` remains unchanged when `E1` is created.
   - Keep measured outputs deterministic and independently recomputable. Jev/provider metadata
     cannot fill or alter them.

4. **Lifecycle, budgets, and failure behavior**
   - Add only the required events to the existing canonical RunEvent stream; do not create a second
     status authority. Use idempotency keys and let the existing reducer own run state/counters.
   - Enforce the Phase 4 request, byte, evaluation, candidate, and follow-up caps in Python before
     side effects. Existing values in `docs/GDC_BUDGETS.md` are planned, not runtime-enforced; do
     not enlarge them to complete a run.
   - Define typed outcomes for ineligible, unavailable, partial, failed, completed, and stopped
     actions. Failure consumes the reserved budget, cannot promote a candidate, and leaves the
     prior evidence revision intact.
   - Do not add retries until provider-call, byte, latency, and spend behavior are separately
     specified and tested.

5. **Jev boundary and candidate control**
   - Do not let `wide-policy-v2` dispatch a follow-up: its thresholds are provisional and the live
     run admitted zero states. Until calibration exists, Phase 4 acceptance uses an explicitly
     selected fixture candidate; any live candidate requires a separate recorded human-approved
     selection rule.
   - If Deep Jev is later included, supply only eligible registered actions and the new immutable
     `EvidenceState`. Record full answers/applicability. Python decides whether to continue, stop,
     or abstain; Jev does not execute or authorize the action.
   - Keep LLM hypothesis generation, clinical interpretation, and additional GDC modalities out of
     this slice.

6. **Verification and release**
   - Add provider-free tests for eligibility, deterministic outputs, hashes, immutable revisions,
     idempotency, every failure/partial branch, budget exhaustion, event reduction, and no promotion
     after failure.
   - Add an end-to-end fixture run that produces `E0`, the registered action event, `E1`, and the
     UI/API representation using committed records only. Assert zero network/provider calls.
   - Run focused Python tests, full offline suite, Ruff, frontend typecheck/build, and Playwright
     browser tests before any live acceptance.
   - Only after all gates pass may a separately approved, single bounded live check exercise GDC.
     Use anonymous allowlisted requests, record the caps/population/missingness, and do not promote
     based on a demonstration result.

## Implementation Sequence

1. Review the candidate action against the current single-cohort evidence and choose one action
   whose inputs are already retained and whose output is not redundant. **DONE:** `CHECK_EVIDENCE_INTEGRITY_V1`.
2. Write and approve its scientific method contract and deterministic eligibility tests. **DONE.**
3. Implement one small registered function, immutable evidence revision persistence, and the
   minimal RunEvent transitions required to record it. **DONE.**
4. Verify offline fixture/API/UI behavior, idempotency, and all stop/failure paths. **DONE** for the
   first action; repeat for any later action.
5. Reassess Phase 3 threshold calibration and baseline-vs-Jev incremental value before enabling any
   live automatic candidate selection. **OPEN.**
6. Run a separately approved bounded live check only if it is needed to validate a GDC contract.
   **NOT RUN** for the deep slice; it is provider-free and verified offline.

## Exit Criteria

- One action is scientifically specified, cohort-applicable, deterministic, and reproducible from
  retained source artifacts.
- `E0` and `E1` are immutable, linked, content-addressed revisions with source, method, population,
  completeness, and missingness provenance.
- Python rejects invalid/ineligible actions before side effects and enforces every operational cap.
- All success, partial, unavailable, budget-exhausted, and failure branches are represented by
  canonical events and covered offline.
- Fixture E2E passes through API/UI using only committed records; no external calls occur.
- No Phase 4 behavior depends on an uncalibrated Jev threshold, and no scientific-readiness claim
  is inferred from a changed ranking or demonstration run.
