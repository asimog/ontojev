# Remaining implementation plan

Current plan, 2026-09-29. Baseline: `da1120449c5ade6c578571047b66c442206fc30c` plus the local changes identified in the [code audit](CODE_AUDIT.md). This replaces the old repair-phase plan; historical phases remain in Git history. Writing this plan completes no implementation milestone.

## Already implemented

The default lab supervisor dispatches seven capabilities into the existing mutation/expression/CNV → StatisticalState → Wide → Candidate → EvidenceState → Stage 8/dossier spine. Hash-bound receipts, raw-workspace cleanup, director decisions, a read-only lab page and a Codex-equipped image exist. Replay reaches a dossier. Preserve these owners rather than rebuilding the scientific pipeline.

## Milestones and order

| Milestone | Priority | Dependency | Exit outcome |
|---|---|---|---|
| M1. Offer correctness and durable recovery | P1, first | Bridge | Failures/restarts preserve eligible work without duplicate science. |
| M2. Bounded resumable science | P1 | M1 | Large lanes and Candidate arcs progress across runs with unchanged populations. |
| M3. Director context and Campaign lifecycle | P1 | M2 | Scientific summaries support decisions; questions, Campaigns and runs share explicit identity. |
| M4. Capability engineering | P1 for requested autonomy | M1–M3 | A gap produces a verified isolated change, activation and question resumption. |
| M5. Deployment and Observatory | P1 operational | M1–M4 for full acceptance | Persistent restart and worker failures are demonstrated and visible. |
| M6. Live evidence and independent evaluation | Evidence gate | M1–M3 and M5 runtime readiness | Retained evidence supports declared operational and scientific claims. |

Each numbered unit below should be implemented and verified separately. Worker supervision repair can land after M1 while later capabilities remain unfinished; that alone does not close M5. No P0 is asserted by this audit. Newly reproduced integrity failures take precedence.

## M1 — Offer correctness and durable recovery

1. Review/integrate existing `research/lab_worker.py` recovery-lock, child-admission and exit-status fixes with `tests/integration/test_lab_supervisor.py`. Review the local expression-only method change separately; do not mix scientific semantics into recovery repair.
2. Fix A01/A02 in `research/lab_stages.py`, `research/wide.py` and typed outcomes in `domain/laboratory.py`: filter questions before limiting; distinguish failed/deferred Wide work from scientifically completed no-admission outcomes; retry unfinished states only.
3. Fix A03 in `lab_runtime.py`, `lab_stages.py`, `lab_worker.py`, `lab_acquisition.py` and `storage/repositories.py`. Persist operation identity, validated inputs and publication outcome; reconcile outputs before retry. Reuse events/artifacts, introducing a migration only for a demonstrated persistence need.

**Acceptance:** owner-boundary regressions reproduce terminal-question starvation, transient Wide failure followed by success, and interruption after promotion, scientific output, receipt registration and portfolio publication. Restart retains one result per operation, complete provenance and truthful status. Failed cleanup retries without deleting canonical evidence. Extend `tests/integration/test_lab_capabilities.py`, supervisor and existing storage-recovery tests; follow the test-audit gate instead of duplicating helper-call assertions.

## M2 — Bounded resumable science

1. Extend existing mutation/expression executors and typed shard contracts: `research/discovery.py`, `expression_discovery.py`, `shards.py`, `resumed_evidence.py`, `lab_capabilities.py`. Checkpoint pinned release, cohort/universe, method, cursor/shard identity, verified derived partials and reacquisition provenance. Merge only all required units. Distinguish declared allowances from measured estimates. Changed releases/specs start separate experiments.
2. Split the whole Candidate operation into resumable actions over `research/investigation.py`, `deep.py`, existing follow-up/hypothesis owners, `dossier.py` and `finalize.py`. Preserve Candidate identity, accepted state and revision chain; finalize from the complete validated cross-run history. Reuse M1 publication/recovery.
3. Define explicit refusal/migration for mixed historical CNV partitions. Never silently merge overlapping shards or relabel old evidence.

**Acceptance:** an intentionally oversized replay finishes across fresh processes without reacquiring verified completed units. Compare canonical measurements/universe with an uninterrupted reference. Exercise drift, corrupt/missing partials and termination at durable boundaries. The dossier includes prior revisions/judgments exactly once; partial coverage never becomes complete or observed zero. Extend existing discovery, resumed-evidence and investigation integration tests at their owning boundaries.

## M3 — Director context and Campaign lifecycle

1. Extend `research/laboratory.py`, `domain/laboratory.py`, `llm/ontocodex.py` with bounded Candidate/state summaries: measurements, Jev dimensions, uncertainty, evidence gaps, maturity and references. Persist omissions/page identity; the scientific director should not require arbitrary file/shell access.
2. Bind questions/operations to existing Campaign/spec/release identity. Reconcile `research/program.py`, `campaign.py`, `cli/main.py` and portfolio persistence. Explicitly migrate/deprecate legacy dispatch; preserve researcher/validation isolation and avoid two independent agenda selectors.
3. If retained, separately verify and wire the local question-selected expression constructor as a typed capability. A complete declared panel is not genome-wide discovery or evidence of mutation absence.

**Acceptance:** different evidence gaps/Candidates produce inspectable, scientifically useful model inputs and eligible decisions. Large portfolios stay within the byte limit with visible omissions. Restart preserves Campaign/question identity; legacy/lab entrypoints have one authority model. Extend projection, ownership and bridge tests. Model prose cannot create measured evidence.

## M4 — Capability engineering

Add a small engineering runner beside `research/lab_worker.py` and typed gap/proposal/verification/activation records in existing storage. Use an isolated Git worktree and separate engineering Codex configuration. Require an adopted source/method contract before activating new science. Verify the exact proposed tree, retain diff/check identity, activate only that version and resume the originating question. Failed verification preserves current runtime and immutable evidence. Ordinary capability changes must not bypass ownership/access/activation checks.

**Acceptance:** one fixture gap creates a real isolated patch, passes project checks, activates and resumes. Negative cases cover failed checks, changed tree after verification, interrupted activation and rollback. Package the checkout, tests and build dependencies needed for this path; the current runtime image is insufficient. No generic agent framework or parallel scientific-state architecture.

## M5 — Deployment and Observatory

Repair worker liveness/restart ownership in `deploy/serve.py` and the existing supervisor. Define/test the total deadline including finalization and recovery. Exercise Docker and volume restore using one explicit CLI/API data root. Extend `apps/api/routes.py` and existing `apps/web` lab/run views with worker failure, reconciliation and activation status plus a navigable question → Campaign → run → evidence/Candidate → dossier chain.

**Acceptance:** terminate worker/director mid-run and restart with a retained volume. One writer resumes; canonical science is neither lost nor duplicated. Readiness reports worker death even when API health is green. Test slow cleanup/provider hangs. Frontend typecheck/build and browser flows verify navigation and responsive overflow. Record image/configuration identity; a local image test is not a Railway deployment. Update the runbook with observed results.

## M6 — Live evidence and scientific evaluation

Run a declared open-access live scope after runtime gates pass. Retain release/versions, budgets, requests/bytes, failures, restart evidence and readable dossier. Carry forward independent preregistered calibration and Jev incremental-value work in `research/calibration.py`, `calibration_records.py`, `jev/replay.py`, [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md) and [JEV_DECISIONS.md](JEV_DECISIONS.md). Evaluate consequential director/control changes against recorded baselines. Do not promote scientific maturity or Campaign readiness merely because a run completes.

**Acceptance:** retained reproducible artifacts support operational claims; held-out/calibration evidence supports scientific or consequential-judgment claims. Negative/abstaining outcomes remain valid. A dossier is a completed computational case for review, not proof of a therapeutic target.

## Verification and deferrals

Paths above are under `cancerjev/` unless explicitly prefixed otherwise. Per implementation unit: focused fixture/replay checks, then project-environment `python -m ruff check .`, `python -m mypy`, `python -m tests.repository_facts check`, full default `python -m pytest`. Run frontend checks when it changes. Update current docs with each verified milestone; versions belong in code/generated facts.

Defer new survival/co-occurrence/fusion adapters, generalized external/functional replication, selected-file downloads, inferential methods and wider cohorts until each has an adopted source/method contract and independent validation. Existing pathway/functional/replication modules remain reusable; deferral does not mean they are absent. No microservices, generic DAG engine or model-generated GDC queries. Historical calibration/live-validation obligations remain open unless fresh evidence explicitly closes them.
