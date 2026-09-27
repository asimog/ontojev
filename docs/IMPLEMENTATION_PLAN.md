# OntoJev Implementation Plan

Repair and evidence program derived from `docs/FULL_REPOSITORY_AUDIT.md`. This document replaces the previous refactor plan (baseline `b595a3a`) and starts from the verified audit, not from older plan text. Planning only: no code, tests, schemas or artifacts are changed by this document.

## 1. Baseline and inputs

| Item | Value |
|---|---|
| Repository | `https://github.com/asimog/ontojev` |
| Plan baseline | `main` @ `7469c4a` (2026-09-27); working tree clean except the known `.pytest-tmp/` ACL warning |
| Audit target | `84c6b37` (frozen SHA). `7469c4a` adds only `docs/FULL_REPOSITORY_AUDIT.md` (verified `git show --stat`), so every audit code finding applies unchanged to the plan baseline |
| Audit source | `docs/FULL_REPOSITORY_AUDIT.md` (sections 7–25 findings, 29–30 P0/P1, 33 recommended order, 34 deferred work) |
| Current facts authority | Code. Audit line numbers are inspection aids; re-verify every citation at the then-current HEAD before editing |
| Method | One bounded change per unit; repair → verify → generate evidence; no architecture redesign |

Findings cited below use the audit IDs (`OJ-AUD-P0-01`, `OJ-AUD-P1-01`..`-17`; lane IDs such as `D-01`, `L-01` are aliases recorded in the audit).

## 2. Rules of engagement

- **Dependency order is the phase order.** Do not start a phase until the previous phase's exit criteria hold. Phases 1–3 are Gate 1 (semantic correctness) and must precede any live Campaign. Phase 7 must precede Phases 8–9 claims about scientific value.
- **No redesign.** Extend existing typed contracts (`StatisticalState`, projections, policies, registries). No new framework, DAG, microservice, event sourcing, plugin layer, database replacement or scientific DSL (audit §34).
- **One bounded change per unit.** Do not implement a whole phase in one commit. Each unit leaves the repository verified.
- **Versions only on proven incompatibility.** Bump method identity, policy version, projection version or schema only in the unit that changes the semantics; never rewrite frozen evidence (`tests/reconciliation/`, `data/invalidations/`, historical artifacts) to fit new code.
- **Fail-closed stays fail-closed.** Aborts that currently kill legitimate data (out-of-universe CNV, pre-Wide ties) are replaced by declared, recorded outcomes. Corrupt or genuinely invalid input still aborts.
- **Verification after every unit** (from the project environment): `python -m ruff check .`, `python -m mypy` (strict, project list), `python -m tests.repository_facts check`, full default offline `python -m pytest`; `npm run typecheck` + `npm run build` in `apps/web` only when frontend is touched. Focused tests listed per phase are the minimum in addition.
- **Fix together, verify together.** Findings that share a function, a version bump or a test fixture are scheduled in the same unit, as noted per phase.

## 3. Phase overview

| Phase | Kind | Contents | Gate |
|---|---|---|---|
| 1 | Repair (semantic) | P0-01 + projection payload co-fixes (B02, H2-06, P1-16, V-12) | Gate 1 |
| 2 | Repair (canonical-run blockers) | P1-01, P1-02, P1-03 + D-03 | Gate 1 |
| 3 | Repair (provenance) | P1-04, P1-05, P1-06 + L-02 | Gate 1 |
| 4 | Verification hardening | P1-07, P1-15, R1-01/C-01, R4-05, A-04, R3-03, Q-16 | Gate 2 |
| 5 | Repair (durable-run crash windows) | O-01/O-02, N-01/N-02/N-03/N-10, L-03/L-04/J-03/J-04/J-05, P-02/W-19 | Gate 2 |
| 6 | Cleanup / ambiguity removal | Dead + test-only surfaces, V1 declaration, P1-09 decision, doc drift | Gate 3 |
| 7 | Operations (evidence) | One live `VALIDATION_RUN` (P1-14, P-12 precondition) | Gate 4 |
| 8 | **Scientific method** | Expression expected-tail model (P1-17, part of P1-08) | Gate 5 |
| 9 | **Scientific method (calibration)** | Threshold calibration + Jev incremental-value preregistration (P1-11, P1-10, L-09) | Gate 6 |

Phases 1–6 are architecture/repair/cleanup. Phases 8–9 are scientific-method work and are deliberately separate from the repair gates. Phase 7 is an operational evidence step, not a code change.

---

## 4. Phase 1 — Correct the Wide projection payload (P0)

**Findings:** `OJ-AUD-P0-01` (= G-01, B01, H-01/H2-01, W-02, R3-04, V-10). Fixed together: `H-02/H2-02` (B02 stale count wording), `H2-06` (provider expression estimator on states that never acquire it), `OJ-AUD-P1-16` (CNV projected with no declared consumer), `V-12/H-05` (`coverage_imbalance` NOT_ASSESSED projected as `false`).

**Why first:** every Wide projection currently tells Jev the gene set came from the provider top-mutated ranking and that mutation counts are provider bucket counts, contradicting the union `selection_bias` in the same payload. This is the input to the admission-gating judgment (`unresolved_uncertainty_material`, `evidence_quality_adequate`). No other phase may run a Wide evaluation before this is corrected.

**Files / modules:**
- `cancerjev/jev/projection.py`: `_limitations` (currently `:85-100`), payload injection (`:210`), `PROJECTION_VERSION` (`:32`), CNV/coverage fields (`:64-69`, `:200-205`).
- `cancerjev/science/methods.py`: declared V1/V2 method limitations (`:154-185`, `MUTATION_DISTINCT_CASE_COUNT_METHOD` at `:424-426`); reuse the registry, do not duplicate text.
- `cancerjev/domain/scientific.py`: `TestedContext.selection_rule` / `selection_bias` (`:485-503`) and `CrossProjectSummary` (only if a typed not-assessed confound is needed; prefer no schema change).
- `cancerjev/research/cutover.py`: union `selection_bias`/`selection_rule` origin (`:55-66`, `:230-233`) — context only.
- Tests: `tests/jev/test_projection.py`, `tests/jev/test_evidence_projection.py`, `tests/jev/test_typed_flow.py`, canonical state fixtures from `tests/science/test_modality_union.py`.

**Change:**
1. Derive limitations from the state, not from literals: mutation limitation text from the actual measurement identity (`MUTATION_AFFECTED_CASE_COUNT_V2` → complete-scan distinct cases, absent-gene-is-observed-zero, no callable denominator; V1 wording only if a V1 value is present); selection limitation from `state.tested_context.selection_rule`/`selection_bias` (the union bias text is already projected as `scope.selection_bias`).
2. Delete the two stale hard-coded strings (`provider top-mutated ranking`, `provider-defined case counts`) and the provider-expression-estimator item when the state carries no provider expression data.
3. Declare CNV contextual-only in the limitations ("CNV fields are ambient provider-labelled positives; no admission criterion or policy consumes them") unless and until Phase 8 adds a versioned CNV criterion. Do not add questions now (audit §34).
4. Project the single-project coverage confound as not-assessed (`null`/reason) rather than `false`, so Wide's coverage-confound question cannot read "observed absence".
5. Bump `PROJECTION_VERSION` v4 → v5. Cache keys include the projection version/hash, so stale evaluations cannot be reused. No question-set change, no schema change.

**Verification:** unit tests building projections from a canonical union state fixture assert: no stale provider-ranking/bucket wording; the state's own selection bias is present; a historical V1 state still gets V1 limitations; a CNV-positive canonical state carries the declared contextual-only limitation; single-project coverage confound is not `false`; partial completeness still appends the partial wording. Then the full command set (§2).

**Exit criteria:** no canonical Wide projection can contain text contradicting `scope.selection_bias` or the state's own mutation method identity; no test pins the stale strings.

---

## 5. Phase 2 — Make the canonical discovery path complete without aborts

**Findings:** `OJ-AUD-P1-01` (= D-01/R3-02), `OJ-AUD-P1-02` (= F-01/G-06/W-04), `OJ-AUD-P1-03` (= G-02/V-04/W-03). Fixed together: `D-03` (P2, same function and test as P1-01).

**Why second:** three independent fail-closed aborts kill a complete-universe canonical Campaign on realistic data: the mutation review-trigger contract disagreement, the CNV out-of-universe union abort, and the pre-Wide ceiling/tie abort. All three must land before any live run.

**Files / modules:**
- Mutation contract: `cancerjev/research/discovery.py` (`build_discovery_entries` `:228-301`, survivor append `:273-282`, eligibility gate `:249-267`, call site `:460-463`); `cancerjev/domain/discovery.py` (`MutationDiscoveryResult.__post_init__` `:474-498`); `cancerjev/science/methods.py` (`scanned_mutation_result` `:556-572`, `_coverage_measurement` `:541-553`).
- CNV universe scoping: `cancerjev/research/cnv_discovery.py` (`run_cnv_shard_merge` `:512+`, aggregation path `:441-496`); `cancerjev/research/cutover.py` (`_compose_union_states` `:115-160`, especially the `UNION_OUTSIDE_UNIVERSE` raise at `:156-160`).
- Pre-Wide policy: `cancerjev/research/wide.py` (`select_pre_wide_states` `:62-107`, `PreWideSelection` `:40-59`); `cancerjev/research/ranking.py` (ordering key `:75-83`, `PRE_WIDE_POLICY_VERSION` `:20`); `cancerjev/config.py` (`JEV_MAX_STATES_HARD_CAP` `:19`, default `:84,108`); `cancerjev/research/systematic.py` (`:218`); `cancerjev/cli/main.py` (`:505`); `cancerjev/research/specs.py` / `cancerjev/research/campaign.py` if the declared policy belongs to the campaign profile.
- Tests: `tests/science/test_discovery_reduction.py` (firing ratio trigger), `tests/science/test_occurrence_scan.py` (D-03), `tests/science/test_cnv_project_scan.py` (universe scoping), `tests/science/test_pre_wide_selection.py` (declared policy), `tests/science/test_modality_union.py`, `tests/integration/test_systematic_campaign.py` (out-of-universe CNV fixture, >1000-state fixture, selection determinism).

**Change:**
1. **P1-01 + D-03:** append only `RETAINED` entries to `survivor_ids`; `JEV_REVIEW` entries stay typed entries with disposition and rank but are not survivors, and `MutationDiscoveryResult` keeps its invariant unchanged. Stop gating survivor eligibility on the legacy provider `coverage.complete` flag: the V2 scan is the measurement (it aborts if incomplete), coverage remains context (`ssm_coverage_cases`) and only affects sufficiency wording. Add a reducer test with a firing occurrence-per-case ratio so the abort cannot return.
2. **P1-02:** scope CNV nominations to the tested universe. Pass the release-bound universe membership into the CNV shard merge (available from the mutation result on the canonical path) so out-of-universe genes are dropped from the persisted evidence with a recorded warning/count; downgrade the `UNION_OUTSIDE_UNIVERSE` raise in `_compose_union_states` to the same recorded drop as defense. The invariant "every nomination is inside the universe" is preserved; the failure mode becomes declared, not fatal.
3. **P1-03:** declare a pre-Wide selection policy `pre-wide-policy-v2` in `PreWideSelection`: the complete union stays persisted; the Wide population is chosen by declared strata with per-modality quotas (mutation-present / expression-nominated / cnv-nominated with declared priority), measured ordering within each stratum, and `state_hash` as the declared deterministic tie-break. Persist per-stratum considered/selected counts and every excluded state with its reason. Keep the ceiling declared (default and hard cap unchanged unless the profile unit proves otherwise); fail closed only on invalid policy configuration, never on ties. Do not raise a hard cap as a substitute for a policy.

**Verification:** the three new regression fixtures above (fail-before/pass-after evidence), plus equivalents across shard layouts, plus `tests/integration/test_systematic_campaign.py::test_pre_wide_boundary_cuts_by_measured_evidence_and_never_truncates` extended for the declared policy and rewritten determinism assertions; then the full command set (§2).

**Exit criteria:** a complete-universe campaign reaches Wide with no `ContractError`, no `UNION_OUTSIDE_UNIVERSE`, no `PRE_WIDE_ORDERING_AMBIGUOUS`; the Wide population is reproducible from the persisted selection payload; no modality is structurally excluded by the cut.

---

## 6. Phase 3 — Evidence and judgment provenance

**Findings:** `OJ-AUD-P1-04` (= W-08), `OJ-AUD-P1-05` (= H-04/J-11), `OJ-AUD-P1-06` (= L-01). Fixed together: `L-02` (same function as P1-06).

**Files / modules:**
- `cancerjev/research/deep.py`: E0 baseline observation builder (`:271-278`), next-move call (`:976-980`).
- `cancerjev/science/methods.py`: V1/V2 definitions and `MUTATION_DISTINCT_CASE_COUNT_METHOD` (`:154-191`, `:424-431`).
- `cancerjev/research/nextmove.py`: `DeepJudgment.from_evaluation` (`:43-53`), `decide_next_move` (`:89-166`), legacy `next_move` (`:72-86`).
- `cancerjev/jev/contracts.py`: `EvaluationRecord.is_applicable` (`:46-48`, `:106`).
- `cancerjev/research/finalize.py`: `derive_stage8` (`:226-250`), `_investigation_comparison` (`:143-169`), status literals (`:172-180`).
- Tests: `tests/integration/test_deep_slice.py`, `tests/science/test_nextmove.py`, `tests/integration/test_stage8_finalize.py`, `tests/jev/test_evidence_projection.py`, `tests/unit/test_scientific_contracts.py`.

**Change:**
1. **P1-04:** derive the E0 mutation baseline observation identity from `project.mutation.affected_cases` (its `ObservedCount` method identity), not the `MUTATION_AFFECTED_CASE_COUNT_V1` literal. The V1 definition is used only when a V1 value is actually present. Add a reader test binding E0 rows to the state's own method identities.
2. **P1-05:** make `DeepJudgment.from_evaluation` consult `evaluation.is_applicable(question_id)` and treat inapplicable answers as unavailable (declared ABSTAIN path), mirroring `ranking.py`'s `_applicable`. Apply the same rule to the legacy dict boundary until Phase 6 removes it. Add a test with an inapplicable-but-answered `revision_reliable`.
3. **P1-06 + L-02:** compute the no-Jev investigation baseline from the revision its declared rule produces — the first action revision (E1) — not `chain[-1]`; keep the observed leg on the final revision; record in the comparison payload which revision id/hash the baseline consumed. In the same function, declare the `DIFFERENT`/`PARTIALLY_COMPARABLE` status literals and make the comparison flags non-tautological (or remove them with a declared reason).

**Verification:** the three new cases above plus multi-follow-up Stage 8 fixture asserting the baseline leg is computed from E1; then the full command set (§2).

**Exit criteria:** Deep Jev can never see a V2 measurement labelled with V1 provenance; no inapplicable answer can change the trajectory; the Stage 8 comparison is computed from the revision its rule declares.

---

## 7. Phase 4 — Verification hardening (Gate 2)

**Findings:** `OJ-AUD-P1-07` (= R2-01/R2-02/R2-05), `OJ-AUD-P1-15` (= R4-01/A-02/B13), `R1-01` + `C-01`, `R4-05`, `A-04`, `R3-03`, `Q-16`.

**Files / modules:** `tests/acceptance/test_final_acceptance.py`, `tests/integration/test_systematic_campaign.py`, `tests/science/test_modality_union.py`, `tests/jev/stub_adapter.py`, `pyproject.toml`, `tests/repository_facts.py`, `.github/workflows/ci.yml`, `tests/contracts/test_capability_contracts.py`, `cancerjev/research/capability.py`, `cancerjev/gdc/parsers.py`, `tests/conftest.py`, `tests/unit/test_test_hermeticity.py`, `apps/web/tests/` and `apps/web/playwright.config.ts` (routing only).

**Change:**
1. **P1-07:** add at least one acceptance test that drives `run_systematic_campaign` end-to-end (ReplayTransport + StubAdapter) and asserts exact union membership and nominations by porting `tests/science/test_modality_union.py` assertions onto the canonical campaign result; include the corrupted-union probe (drop all non-mutation nominations) as a must-fail regression; retitle the legacy `LiveOrchestrator` tests honestly as comparator-path tests (they are not autonomous evidence).
2. **P1-15:** add a repository-facts check that the strict-mypy `files` list covers `git ls-files 'cancerjev/**/*.py'` minus an explicit, documented exclusion list; add the currently escaped production modules (`hypothesis_policy.py`, and the `__init__.py`/`__main__.py` decision); CI already runs `python -m tests.repository_facts check`. Re-verify the `follow_imports` choice in the same unit.
3. **R1-01 + C-01:** enforce the access facet in the capability/parser path and add the controlled-access negative test; make the "open" assertion non-vacuous.
4. **R4-05:** complete the hermeticity guard (`socket.connect`, subprocess) and extend the guard's own test.
5. **A-04:** include `deploy/` in the CI ruff target.
6. **R3-03:** make the stub adapter honor `definitions` and add at least one Jev service test over a canonical union state.
7. **Q-16:** route the browser job at the maintained specs and delete/repair the stale unrouted `apps/web/tests` files so CI cannot stay green while browser coverage drifts.

**Verification:** new tests must fail against the pre-fix probes (corrupted union, controlled-access capability) and pass after; then the full command set (§2), plus `npm run typecheck`/`build` if web files move.

**Exit criteria:** acceptance evidence is attributable to the canonical executor; the union guarantee is asserted at the canonical boundary; no production module escapes the strict type list; CI covers deploy lint and the routed browser specs.

---

## 8. Phase 5 — Durable-run repair paths (Gate 2, P2 cluster)

**Findings:** `O-01`/`O-02`; `N-01`, `N-02`, `N-03`, `N-10`; `L-03`, `L-04`/`J-04`; `J-03`, `J-05`; `P-02`/`W-19`.

Independent bounded units; each may land as its own commit with its own tests.

**Files / modules:** `cancerjev/storage/doctor.py`, `cancerjev/storage/database.py`, `cancerjev/research/program.py`, `cancerjev/cli/main.py`, `cancerjev/research/release_monitor.py`, `cancerjev/research/campaign_selection.py`, `cancerjev/research/finalize.py`, `cancerjev/research/dossier.py`, `cancerjev/research/investigation.py`, `cancerjev/research/live.py`, `cancerjev/domain/states.py`, `cancerjev/domain/program.py`, `cancerjev/domain/events.py`, `cancerjev/storage/repositories.py`. Tests: `tests/test_storage_doctor.py`, `tests/integration/test_autonomous_campaign_dispatch.py`, `tests/science/test_program_loop.py`, `tests/unit/test_campaign_dispatch.py`, `tests/integration/test_stage8_finalize.py`, `tests/integration/test_deep_slice.py`, `tests/test_ownership_recovery.py`, `tests/test_candidate_state_machine.py`, `tests/science/test_campaign_program.py`, `tests/science/test_release_monitor.py`, `tests/unit/test_versioned_readers.py`, `tests/helpers.py`.

**Units:**
1. **Doctor semantics (O-01/O-02):** a missing database reports "not found" without creating it and crashing; a corrupt/non-SQLite file returns a typed failure, not an uncaught `DatabaseError`.
2. **Dispatch ledger (N-01/N-10):** catch `ScienceError`/`JevContractError` in the campaign dispatch path so a FAILED run increments the attempt ledger; close the completed-but-unregistered redispatch window by registering program state atomically with completion (or by an idempotent recovery check).
3. **Release gates (N-02/N-03):** release inequality gates a redispatch only on a valid, orderable release; `UNVERIFIED_RELEASE` fails closed instead of dispatching a full Campaign.
4. **Crash repair (L-03/L-04/J-03/J-04/J-05):** dossier retry after a crash between file write and `DOSSIER_CREATED` cannot raise an unhandled `FileExistsError`; a `DOSSIER_READY` orphan is either re-driven to completion or explicitly terminal (not silently preserved forever); the operator path records a terminal failure for a selected candidate; candidate dedup resolves aliases consistently with candidate resolution.
5. **Worker behavior (P-02/W-19):** lock contention defers the cycle with a bounded retry instead of exiting the durable worker. W-19 is narrowed to the verified state at HEAD: the cycle run already persists `RUN_FAILED` through `_started_run`, so this unit adds the deferral and a regression test proving a failed cycle is persisted, not print-only.

**Verification:** targeted new/updated cases in the files above (doctor missing/corrupt DB; completed-campaign crash window; uncaught exception types; release downgrade/UNVERIFIED; dossier retry collision; orphan `DOSSIER_READY`; alias dedup; lock contention); then the full command set (§2).

**Exit criteria:** no known crash window silently loses, duplicates or permanently strands a durable run, campaign or candidate.

---

## 9. Phase 6 — Remove ambiguity (Gate 3)

**Findings:** dead/test-only surfaces from audit §24 (`T-01`, `T-02`, `T-03`, `next_move` dict, `domain/actions.py` helpers, `attach_pathway_evidence`, `file_admission`, `select_next_campaign`, `release_changed`, `release_compare`, `live.py` re-export); `D-04`/`D-12`/`T-11` (V1 declared in every canonical method environment); `OJ-AUD-P1-09` (= B09/J-01/K-01) decision; doc drift from §25 (`S-01`..`S-07`, `A-09`, `A-10`).

**Change:**
1. **Delete DEAD surfaces and their tests:** `research/release_compare.py`, `release_monitor.release_changed`, `nextmove.next_move` dict boundary, `domain/actions.py` unused helpers (`summarise`, `outcome_kind`, `boundary_representation`), `live._merge_expression_availability` re-export.
2. **Delete TEST_ONLY surfaces and their tests:** `parse_files_provenance`/`FilesProvenance` (keep any versioned reader needed for historical artifacts), `run_cnv_discovery` + `CnvDiscoveryResult/Entry` producers (keep readers for historical artifacts), `_compose_legacy_survivor_states` and the legacy branch of `compose_discovery_states`, `attach_pathway_evidence` (keep `domain/pathway.py` types referenced by codecs/readers), `file_admission.evaluate_file_admission`, `campaign_selection.select_next_campaign`. Keep `research/prospective.py` (needed by Phase 9) and `domain/functional.py` decision record with an explicit "not wired" banner; keep `research/replication.py` only with an explicit "declared prerequisite, no production caller" banner (re-assess with the P1-12 trigger after Phase 8), otherwise delete it with its tests.
3. **V1 declaration removal (D-04/D-12/T-11):** after Phase 3 removes its last live reference, stop declaring `MUTATION_AFFECTED_CASE_COUNT_V1` in canonical state method environments; keep the `MethodDefinition` for historical replay so old artifacts still read.
4. **P1-09 decision:** remove the unreachable `TEST_HYPOTHESIS` branch/dispatch and keep `KEEP_HYPOTHESIS`/`NO_EVIDENCE_PRODUCING_TEST` as the declared, tested outcome, documenting the boundary in the hypothesis policy and docs. Do not register a filler action (audit §34); registering an EVIDENCE_STATE-input evidence-producing action requires a named hypothesis with a declared discriminating measurement and belongs to a future science track.
5. **Doc drift:** correct README/ARCHITECTURE/DATA_STRATEGY/BUGFIX_PLAN/TEST_AUDIT/PATHWAY_SOURCES/FUNCTIONAL_SOURCES/DEPLOYMENT claims per audit §25; keep `docs/REPOSITORY_FACTS.md` regenerated through its renderer whenever a constant changes.

**Verification:** full suite green after deletions (code and tests deleted together, `mypy`/`ruff` catch dangling imports); repository-facts check; each corrected doc claim re-checked against code in the same commit.

**Exit criteria:** no surface is reachable only from tests; the hypothesis outcome space is exactly what can happen; every doc claim matches code; no V1 method is declared where no V1 value exists.

---

## 10. Phase 7 — One bounded live validation run (Gate 4)

**Findings:** `OJ-AUD-P1-14` (= B17, baseline OJ-P0-002, N-17, T-15, W-18), precondition `P-12`.

**Preconditions:** Phases 1–3 merged and green; Phase 4 canonical acceptance test passing; the required Jev provider credential (`TYPESAFE_API_KEY`) checked before dispatch so a live preflight does not consume a durable attempt (`P-12`, `cli/main.py`); the optional generated-text key (`OPENROUTER_API_KEY`) only enables the labelled LLM hypothesis generator and is never required. Use the operator route `python -m cancerjev campaign --validation`; the autonomous worker intentionally still refuses the EXPERIMENTAL profile and no readiness is implied by this run.

**Run:** exactly one `VALIDATION_RUN` on live open-access GDC data over the declared LUAD cohort, through the identical canonical spine.

**Record (run artifacts, not a new doc):** cost (requests/bytes/attempts), completeness, union size and per-modality counts (open audit question 1), the persisted pre-Wide selection payload, admissions, Wide/Deep judgments, evidence revisions, Stage 8 comparison, dossiers, and how many `JEV_REVIEW` states occurred (feeds P1-10). Do not promote readiness merely because the run completes.

**Verification:** `doctor`, `show`, artifact/hash inspection, API rendering, and a manual conformance check against the declared invariants (incomplete acquisition never labelled complete; no result without its dossier).

**Exit criteria:** one complete canonical run exists with inspectable artifacts; every defect found becomes a new bounded unit, never a silent patch.

**Execution record (operator-directed bounded variant; Gate 4 not yet satisfied).** The full 24-shard live Campaign was stopped by operator decision ("no disk space; process shard by shard") after two live attempts, and replaced by a declared disk-bounded streaming pipeline plus a 5-shard live end-to-end test:
- Defect units found live and fixed before the bounded run: `02942cf` (the open-access filter is proven by response total vs the open bucket; dual-access live capture pinned), `fa9217e` (P-12: provider credentials checked before the preflight and before any durable attempt).
- Feature units: `bb0154e` (streaming shard scan: pages are parsed/aggregated while later pages download; a committed shard's raw pages are evicted; derived shard evidence retained), `766372a` (file-only eviction; immutable cache index rows; an evicted payload reads as a cache miss and refetches live), `f63b9f0` (schema-8 append-only `gdc_artifact_evictions`; doctor reports `ARTIFACT_EVICTED` as INFO; API returns 410; evictions register before deletion).
- Bounded 5-shard live e2e (run `14786a0e`, `VALIDATION_RUN`, `cnv-shard-stream-test`): 24 shards declared, 5 processed (25 cases each); per-shard wall time 829–1,854 s; totals **4,022 GDC attempts / 468.6 MB read / 449 cache hits**; **3,991 raw page payloads (524.5 MB) evicted**, every one registered before deletion (`raw_absent_without_record = 0`); derived evidence **108.8 MB** for 5 shards (~22 MB/shard, 19,009–19,014 genes, 185k–207k records each); the `gdc` cache directory stayed bounded at 306.8 MB with no per-shard accumulation; `doctor` returns `ok: true` (schema 8).
- Corpus as a whole (PARTIAL, never labelled complete): mutation lane 19,843 genes / 10 survivors / 0 review; expression lane 19,843 measured / 14,998 `RETAIN` + 1,942 `JEV_REVIEW` under the pre-Phase-8 policy and 4,969 `RETAIN` under `expression-dispositions-v3` (Phase 9 measurement); CNV coverage is **5 of the declared 24 case shards**, so the declared terminal merge intentionally does not run, no emissive union/Wide/Deep/Stage 8 exists for CNV, and the run is recorded as incomplete CNV acquisition. The earlier stopped Campaign run `a4a23f89` is recovered `STOPPED` with the mutation and expression artifacts intact.
- Retention options for the lane artifacts remain **open** (the 4.3 GB expression and 1.5 GB mutation results embed raw per-gene arrays; compacting them requires a derived-summary redesign and is not done silently). No retention unit is scheduled yet; the decision is unresolved, not recorded elsewhere.
- Operator decision (2026-09-27, superseding the initial 10×60-case declaration): the Phase 7 CNV verification is executed as **small-shard systematic processes** — declared 8-case operational shards (`--case-shard-size 8`) covering the complete 585-case frame as **74 shards**, one complete `discover-cnv` run (a separate bounded process) per shard, then a terminal `cnv-merge` over every shard. Each process is bounded end-to-end (≈4–10 min at the measured 33–74 s/case live cost); there is no cap on the shard count, no sampling and no population limit — the merge still requires every declared shard and a partial frame is never labelled complete, and no hard limit was introduced. The operational case-shard size setting (`Settings.cnv_case_shard_size`, default 25) is unchanged; the 8-case size is declared per command. The canonical Campaign spine (union/Wide/Deep/Stage 8) cannot be chunked this way and remains a separate later run.
- Continuation unit (bounded-process rules): `cancerjev/research/resumed_evidence.py` plus `campaign --validation --resume-mutation-run/--resume-expression-run/--resume-cnv-run` resume the union/admission spine from the published lane artifacts of terminal runs. Identities (spec, cohort, project, release) are cross-checked, the merged CNV result must cover every declared shard exactly once, out-of-universe CNV calls are dropped by the same `scope_cnv_scan_to_universe` function the fresh merge uses, and the consumed artifact ids/hashes are recorded in the run (`EVIDENCE_RESUMED`). Resume is validation-only and re-acquires no lane evidence. Under the bounded rules, Gate 4 evidence is therefore: the complete declared-frame CNV shard set + terminal merge, plus the continuation run's union, pre-Wide selection payload, Wide/Deep judgments, admissions, Stage 8 comparison and dossier — all inspectable under one `VALIDATION_RUN` continuation.

---

## 11. Phase 8 — Scientific method: expression expected-tail model (Gate 5)

**Findings:** `OJ-AUD-P1-17` (= V-01); makes `OJ-AUD-P1-08`'s `STATISTICALLY_SUPPORTED` attainable for one claim family.

**Why separate:** this is the first scientific-method change, not repair. It changes nomination semantics and must not be entangled with the repair gates.

**Files / modules:** `cancerjev/science/descriptors.py` (`expression_tail_descriptor`, `expression_lane_disposition` `:119-146`), `cancerjev/domain/discovery.py` (expression constants/reasons `:63`, `:117-140`, `:218-219`), `cancerjev/science/methods.py` (method identity/version/limitations), `cancerjev/research/expression_discovery.py` (persist the null expectation), `cancerjev/domain/codecs.py` only if the descriptor payload cannot carry the new fields under the current schema, `cancerjev/domain/maturity.py` (prerequisite text after the method exists), `cancerjev/jev/projection.py`/`questions.py` only if a new field is projected (avoid question-set churn).

**Change:** declare and persist a per-gene expected-tail/null expectation (for example binomial exceedance given n and the empirical within-gene distribution) and require a declared excess over the null with an effect size before `RETAIN`; version the expression tail method and the disposition policy (v2 each), update declared limitations, and re-run the frozen expression fixture. Keep mutation inference deferred (MutSigCV-class) and leave a CNV background/permutation model as the next candidate for a later gate.

**Alternative considered:** rename `RETAIN` to a measurement state excluded from the nomination union. Rejected for now because it changes the union and candidate contracts; the null-model path keeps descriptive honesty and is calibratable.

**Verification:** frozen expression fixture asserting nomination counts against the declared null (before/after on the same fixture); union-size measurement against the Phase 2 quota policy; full command set (§2). `STATISTICALLY_SUPPORTED` stays blocked until Phase 9 records calibration artifacts.

**Landed record (implementation complete; `5391c19`, `a90a5b6`).**
- Null declared and persisted: `EXPRESSION_EXPECTED_TAIL_V2` (`GENOME_WIDE_EMPIRICAL_FENCE_EXCEEDANCE_V1`, excess `>= 3.0` binomial null SD), per-gene `null_lower_rate`/`null_upper_rate` and `expected_*_case_count` persisted in the schema-2 descriptor; pooled rates are computed over every observed tail in the run. The retired `EXPRESSION_TUKEY_TAIL_V1` stays defined for historical replay and is excluded from new state method environments (environment hash changes once, as a declared method-identity change).
- Disposition policy `expression-dispositions-v3`: `RETAIN` requires the declared excess on at least one side; within-null tails `DROP` with `TAIL_CASES_WITHIN_NULL_EXPECTATION`; a missing null fails closed with `NULL_EXPECTATION_UNAVAILABLE`; the asymmetry review trigger is unchanged. Historical schema-1 artifacts keep a strict reader (frozen fixture `tests/unit/fixtures/expression_discovery_result_v1.json`).
- Measured on the frozen DR46 live corpus (the Phase 7 `expression-discovery-result`, same fixture before/after): 19,843 genes, 17,338 observed tails, 8,981,084 valid values; pooled rates 0.396% lower / 3.325% upper. Nominations before: 14,998 `RETAIN` + 1,942 `JEV_REVIEW`; after: **4,969 `RETAIN`** + 1,942 `JEV_REVIEW`, with 10,029 within the null and 398 no-tail drops. The screen is roughly three times more selective and removes chance tail membership; the expression nominations still exceed the pre-Wide hard cap of 1,000, so `pre-wide-policy-v2` quotas remain the selection mechanism and the calibration of the `3.0` effect size belongs to Phase 9.
- Sharding compatibility: Phase 8 touches only expression discovery/domain/codecs/methods; the streaming CNV shard pipeline (raw-page eviction, schema-8 eviction records, doctor/API semantics) is untouched, and the full suite including the shard, eviction and merge tests stays green. The only cross-phase effect is the declared method-environment hash change, which the Phase 5 durable program handles as a `METHOD_CHANGED` redispatch identity.

---

## 12. Phase 9 — Calibration and Jev incremental-value measurement (Gate 6)

**Findings:** `OJ-AUD-P1-11` (= B05/V-06), `OJ-AUD-P1-10` (= B08/G-03), `L-09`, `L-08` if the evaluation reuses it.

**Change (measurement and design, minimal code):**
1. Preregister a calibration/sensitivity design for every declared threshold: mutation top-10 and ratio 4, hotspot 20/0.25, expression n≥20/1.5 IQR/asymmetry 5.0 and the Phase 8 null effect size, CNV 5/5, Wide 0.60/0.50/0.40/0.50, Deep 0.5/0.5/0.6/0.5, hypothesis 0.60/0.50. Record calibration artifacts per policy version; do not present thresholds as scientifically meaningful before this exists.
2. Fix `research/prospective.py` defects (`L-09`: dropped resamples, ABSTAIN/STOP conflation, precision@3 denominator, missing arm-output hash) before the evaluator is used for any claim.
3. From the Phase 7 run, quantify `JEV_REVIEW` states and the veto's recall cost (`P1-10`) and record the decision on whether a narrow Arm-Jev triage is justified. No Arm-Jev implementation now.
4. Preregister a Jev-vs-no-Jev evaluation with frozen policies, held-out labels where they exist, and failure/abstention analysis, after Gates 1–5.

**Exit criteria:** every admission/stopping threshold has a reproducible calibration record; the Jev incremental-value question is testable under a preregistered design; the review-veto decision is data-backed.

**Landed record (implementation complete; `19673d5`, `09428bd`).**
- Preregistered calibration design: `research/calibration.py` binds all 21 declared thresholds to the code constants and owning policy versions (`calibration-design-v1`), with machine-checked status semantics (`UNCALIBRATED` / `CALIBRATED` / `STALE_POLICY_VERSION`) and a strict calibration-record reader; `docs/CALIBRATION_DESIGN.md` declares the metric, frozen corpus, sensitivity grid and record schema for each. At HEAD the four mutation-family thresholds are `CALIBRATED` from the frozen DR46 reconciliation panel (`python -m cancerjev calibrate`; records in `data/calibration/`, `held_out: false`) and the other 17 stay `UNCALIBRATED`; `STATISTICALLY_SUPPORTED` stays blocked until records exist for a selected claim family.
- Prospective harness repaired (`L-09`): all arms share the identical paired bootstrap replicate set, `precision_at_3` divides by the declared K = 3 (never the returned list length, so abstain/stop-heavy arms score 0.0 instead of disappearing), `coverage`/`abstention_rate`/`stop_rate`/`investigate_rate`/`external_evidence_rate` are reported separately instead of conflating ABSTAIN with STOP, and the report binds `arm_output_hash` alongside `protocol_hash`.
- P1-10 quantified from the Phase 7 DR46 corpus (expression lane): 19,843 measured genes, **1,942 `JEV_REVIEW`** (all two-sided asymmetry, ratio min 5.0, median 8.0) — 9.8% of measured genes, 11.5% of non-dropped nominations under the old policy and 28.1% under the Phase 8 policy; the mutation lane produced 10 survivors and 0 review triggers, and TP53 is both a mutation survivor and an expression review state. The veto (`ranking.py:175-180`) excludes every review state unconditionally. **Decision:** the recall cost is material and now measured, but no Arm-Jev triage is implemented; a narrow semantic-only triage requires the preregistered evaluation with held-out labels first.
- Jev-vs-no-Jev preregistered design recorded in `docs/CALIBRATION_DESIGN.md` §3 (frozen policies, blinded grouped labels, paired metrics, mandatory failure/abstention analysis, `HUMAN_REVIEW_REQUIRED` decision rule) and proven testable by `tests/unit/test_prospective.py::test_jev_vs_no_jev_design_is_evaluable_under_the_preregistered_contract`.
- Sharding pipeline compatibility pinned: `tests/integration/test_systematic_campaign.py::test_raw_shard_eviction_never_changes_what_jev_and_the_engine_see` runs the evicting shard scan through the terminal merge, modality union, Wide Jev and pre-Wide selection, asserting the derived shard evidence survives while raw pages are registered and evicted; the canonical campaign test already covers the full spine with eviction on by default.
- Calibration record generation landed (2026-09-27; `2f26cd7`): `research/calibration_records.py` plus `python -m cancerjev calibrate` compute the declared mutation metrics on the frozen DR46 reconciliation panel with a deterministic 200-replicate gene bootstrap (seed `20260927`) and write strict records to `data/calibration/`. Four of 21 thresholds are `CALIBRATED` with `held_out: false`; the other 17 stay `UNCALIBRATED` because their declared corpus/metric is not yet computed, and the Wide admission family additionally requires blinded held-out labels (`reviewer_count >= 2`, `adjudicated`) — a data/labelling prerequisite, not a code unit. `STATISTICALLY_SUPPORTED` therefore stays blocked until records exist for a selected claim family. The Jev-review design rehearsal is recorded separately (`docs/JEV_REVIEW_REHEARSAL.md`).

---

## 13. Deferred and deleted register

**Deferred with explicit triggers (not in this repair program):**

| Item | Trigger to start |
|---|---|
| `OJ-AUD-P1-12` internal replication wiring | After Phase 8 inference exists and a case-disjoint partition can be predeclared inside the Campaign; add only through the canonical path |
| `OJ-AUD-P1-13` external/functional/targetability evidence | Only with a named source decision, licence, evidence adapter and maturity mapping |
| Arm Jev triage | After Phase 9 records the `JEV_REVIEW` materiality decision |
| Additional modalities, open-file/`gdc-client` acquisition, pathway wiring, survival/differential-expression methods, question-set expansion, frontend redesign | Only with a named scientific consumer; audit §34 forbids building them speculatively |
| Purity/ploidy and arm-level CNV correction (`V-13`), matched sample resolution (`EXPRESSION_ALIQUOT_IDENTITY_STATUS`), MutSigCV-class mutation inference | Science track after Gate 5; each needs its declared null/model |
| Remaining P2/P3 backlog: mutation `B-15`/`B-05`; expression `E-01`..`E-07`; CNV `F-03`..`F-07`; integration `G-04`/`G-09`/`G-11`/`G-12`/`G-14`; Jev `H-02` residual/`H2-04`..`H2-12`/`H-06`..`H-13`/`J-11`; deep `I-01`..`I-11`; hypothesis `K-02`..`K-15`; Stage 8 `L-05`..`L-11`; program `N-04`..`N-12`; persistence `O-03`..`O-26`; GDC `C-02`..`C-16`; API `P-03`..`P-18`; frontend `Q-01`..`Q-21`; security `U-01`..`U-13`; test-quality `R1-02`..`R1-12`, `R2-06`..`R2-14`, `R3-04`..`R3-11`, `R4-06`..`R4-14` | Separate backlog after Phase 7; schedule by risk, one bounded unit at a time. None blocks Gates 1–3; Gate 4–6 evidence depends on the Phase 7 continuation run and on calibration records |

**Deleted as unnecessary (Phase 6):** the dead and test-only surfaces listed in §24 of the audit, with versioned readers retained only where historical artifacts require them. Additionally, never attempt to make the V1 provider bucket work again, and do not add a framework/DAG/plugin/event-sourcing/database/scientific-DSL layer (audit §34).

**Deferred-trigger assessment (post-Phase-9):**
- `OJ-AUD-P1-12` (internal replication): trigger **not met**. Phase 8 landed a declared descriptive screen, not inference; `STATISTICALLY_SUPPORTED` remains blocked and no method declares a discovery share. Wiring a partition now would be speculative infrastructure with no consumer, which audit §34 forbids.
- Arm Jev triage: trigger **exercised** by the Phase 9 materiality decision; outcome is "no triage until the preregistered evaluation has held-out labels". Re-open only by recording that evaluation, never by a silent threshold change. A synthetic design rehearsal (`docs/JEV_REVIEW_REHEARSAL.md`, report in `data/calibration/`) exercises the harness end-to-end under the frozen policies and returns `HUMAN_REVIEW_REQUIRED` with a [0.0, 0.0] rehearsal interval; it is explicitly never incremental-value evidence.
- `OJ-AUD-P1-13`, extra modalities, open-file acquisition, pathway wiring, survival/DE methods, question-set expansion, frontend redesign: triggers **unmet** for wiring (no adapter/consumer). The named-candidate licence states are now verified and recorded with evidence (`docs/FUNCTIONAL_SOURCES.md`, verification 2026-09-27): Open Targets CC0 1.0 (per-source terms), ChEMBL CC BY-SA 3.0, UniProt CC BY 4.0 remain adoptable candidates; DepMap (CC BY 4.0 plus a commercial-use restriction), Sanger CGC/COSMIC (registered non-commercial licence) and DrugBank (CC BY-NC 4.0) carry licence barriers. All decisions remain `DEFER`; nothing is wired.
- Backlog scheduling started at the highest-risk items that need no new data: `F-02` (CNV category spelling double-count, fixed `1747cfd`) and `I-01`/`I-02` (deep revision-chain gap and recomputed parent hash). Science-policy items that change nomination semantics (`E-02` one-sided asymmetry review) are blocked on the Phase 9 calibration records, not silently re-tuned.

**Provider contract verification (landed 2026-09-27, operator head-slice run).** `python -m cancerjev probe` now also captures the declared LUAD occurrence scan shallow (`from=0`, 1,000 records) and deep (`from=150,000`, 1,000 records) pages, compares every capture's release header against the first observed value, and returns the totals in the summary; the transport emits `GDC_RELEASE_DRIFT` when a header changes. Live evidence (16 requests, 2.36 MB): TCGA-LUAD occurrence total **177,330** on both pages, deep page HTTP 200 returning 1,000 hits with a 1,141,712-byte body, and stable `x-gdc-data_release = "Data Release 46.0 - August 10, 2026"` / `x-gdc-commit = 8f7c2a51…` headers across all captures. This closes `C-04` (deep `from/size` provider behavior verified live) and `C-03` (per-response release comparison now implemented and observed stable).

**Consciously not scheduled:** any acquisition expansion is deferred until a run or method requires it.

---

## 14. Finding → phase crosswalk (P0 and P1)

| Finding | Audit severity | Phase | Disposition |
|---|---|---|---|
| `OJ-AUD-P0-01` Wide projection false legacy context | P0 | 1 | Fix (with B02, H2-06, P1-16, V-12 co-fixes) |
| `OJ-AUD-P1-01` mutation `JEV_REVIEW` abort | P1 | 2 | Fix (with D-03) |
| `OJ-AUD-P1-02` CNV out-of-universe abort | P1 | 2 | Fix |
| `OJ-AUD-P1-03` pre-Wide ceiling/tie abort | P1 | 2 | Fix (declared `pre-wide-policy-v2`) |
| `OJ-AUD-P1-04` E0 V1 method mislabel | P1 | 3 | Fix |
| `OJ-AUD-P1-05` Deep applicability bypass | P1 | 3 | Fix |
| `OJ-AUD-P1-06` Stage 8 baseline revision | P1 | 3 | Fix (with L-02) |
| `OJ-AUD-P1-07` canonical verification gap | P1 | 4 | Fix |
| `OJ-AUD-P1-08` no inferential method | P1 (declared) | 8 | Partial: one family (expression) becomes attainable; rest deferred |
| `OJ-AUD-P1-09` hypothesis test structurally impossible | P1 (readiness) | 6 | Decision: remove unreachable branch, declare boundary |
| `OJ-AUD-P1-10` `JEV_REVIEW` veto recall cost | P1 (readiness) | 9 (data from 7) | Quantify then decide; no Arm-Jev now |
| `OJ-AUD-P1-11` uncalibrated thresholds | P1 (readiness) | 9 | Preregister calibration; no scientific meaning until recorded |
| `OJ-AUD-P1-12` replication unwired | P1 (declared) | — | Deferred, trigger after Phase 8 |
| `OJ-AUD-P1-13` external/functional deferred | P1 (declared) | — | Deferred, named-consumer trigger |
| `OJ-AUD-P1-14` no live canonical Campaign | P1 (readiness) | 7 | Bounded-process route: declared small-shard CNV runs + terminal merge + validation continuation (`resumed_evidence.py`) produce the union/Wide/Deep/Stage 8/dossier evidence under one `VALIDATION_RUN` |
| `OJ-AUD-P1-15` mypy coverage escape | P1 | 4 | Fix (repository-facts invariant) |
| `OJ-AUD-P1-16` CNV projected without consumer | P1 | 1 | Declare contextual-only (or versioned criterion later) |
| `OJ-AUD-P1-17` expression nomination near-universal | P1 (readiness) | 8 | Expected-tail/null model + version bump |

Scheduled P2s: `D-03` (2), `L-02` (3), `C-01`/`R1-01` (4), `O-01`/`O-02`, `N-01`/`N-02`/`N-03`/`N-10`, `L-03`/`L-04`, `J-03`/`J-04`/`J-05`, `P-02`/`W-19` (5), `P-12` and `L-09` (7/9). Everything else is in the deferred backlog (§13).

## 15. Stop conditions

- Do not run any live Campaign before Phases 1–3 are merged and verified (Gate 1).
- Do not promote `LUAD_CAMPAIGN_V1` readiness before Phase 7 produces a complete run and Phase 9 produces its calibration record.
- Do not let a phase grow beyond its listed findings; new defects discovered during implementation become new bounded units recorded here, not silent additions.
- Do not rewrite frozen evidence, historical artifacts or recorded defects to make a phase pass.
