# Phase 4 Readiness Plan

Status: **CONDITIONAL READINESS PLAN; Phase 4 is not implemented or approved for live execution.**
This document sequences one bounded deterministic follow-up vertical slice. It does not authorize
new endpoints, expand budgets, or create a runtime workflow framework.

## Completion Status

Phase 3 implementation is complete: `jev-state-projection-v2`, `wide-v3`, deterministic
eligibility, `wide-policy-v2`, `ABSTAIN`, baseline/Jev rankings, and bounded promotion are present
and tested. One live run made ten `wide-v3` evaluations and admitted no states. This verifies the
abstention path; it does not validate the question set, calibrate its thresholds, or show
incremental value over the deterministic baseline. See `docs/IMPLEMENTATION_STATUS.md`.

Phase 4 may proceed to method-contract design, but must not use Jev admission as an autonomous
execution authority until Phase 3's thresholds and incremental value have been evaluated.

## Proposed First Slice

Build only `E0 -> one registered deterministic follow-up -> E1` for one explicitly selected
candidate and the existing `TCGA-LUAD` cohort. Python owns input validation, eligibility, execution,
budgets, stopping, persistence, and failure handling. Jev may judge supplied evidence only after a
valid `E1` exists; it does not select arbitrary computations or write measured fields.

Candidate action contracts currently named in the repository include `STRATIFY_BY_PROJECT_V1`,
`LEAVE_ONE_PROJECT_OUT_V1`, `CHECK_MISSINGNESS_V1`, `OUTLIER_SENSITIVITY_V1`, and
`COMPARE_MODALITIES_V1`. These are proposals, not registered executable actions. Because the only
production scope is one project (`TCGA-LUAD`), project-stratification and leave-one-project-out
actions are **NOT APPLICABLE** to the current cohort and must not be selected as the first slice.

`CHECK_MISSINGNESS_V1` is a candidate for contract review, not yet approved. Before selecting it,
verify which retained response artifacts and case/gene mappings permit an independently
reproducible check beyond the missingness already recorded in `StatisticalState`. Do not add a
ratio, imputation, new measurement, or follow-up merely to make the action appear novel. If no
non-redundant test is supportable from held evidence, stop and revise the candidate action before
implementation.

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
   whose inputs are already retained and whose output is not redundant.
2. Write and approve its scientific method contract and deterministic eligibility tests.
3. Implement one small registered function, immutable evidence revision persistence, and the
   minimal RunEvent transitions required to record it.
4. Verify offline fixture/API/UI behavior, idempotency, and all stop/failure paths.
5. Reassess Phase 3 threshold calibration and baseline-vs-Jev incremental value before enabling any
   live automatic candidate selection.
6. Run a separately approved bounded live check only if it is needed to validate a GDC contract.

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
