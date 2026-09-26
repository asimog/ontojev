# Test Audit — discovery report

> **Resolution update (2026-09-26, after the autonomous-pipeline convergence).**
> The audit below remains the discovery record at `60c638c`; these statements are
> now superseded by current HEAD behavior:
>
> - `compose_discovery_states` **is production-wired**: `research/systematic.py`
>   is the canonical Campaign executor and reaches the modality union on every
>   autonomous dispatch; the integration tests cover that spine.
> - `Repository.list_runs(ownership=…)` now has production callers (program-loop
>   tests and worker dispatch checks), not only tests.
> - The legacy `_compose_legacy_survivor_states` / `run_cnv_discovery` branch and
>   the dead `parse_files_provenance` parser remain test-only historical seams;
>   they are not part of the canonical path and their deletion is still a
>   maintainer decision under the retention rules below.
> - The P12b pathway attach layer (`attach_pathway_evidence` / `pathway_evidence`)
>   remains unwired and deferred; Arm Jev remains deferred.
> - New audit-relevant surfaces since `60c638c`: `tests/unit/test_run_lifecycle.py`,
>   `tests/unit/test_test_hermeticity.py`, `tests/integration/test_systematic_campaign.py`,
>   `tests/integration/test_autonomous_candidate_queue.py`,
>   `tests/jev/test_pre_wide_selection.py`, `tests/science/test_program_loop.py`,
>   `tests/test_schema_migrations.py`, `tests/test_storage_doctor.py`,
>   `tests/test_observability.py`.

Read-only test-surface audit of OntoJev at `main` SHA `60c638c`, run with the
openclaw `test-audit` skill (SKILL.md + CAMPAIGN.md, installed for Kilo and
Codex). Discovery only: no files were edited and no test suite was executed for
this report. Candidates below are not yet deleted; each carries the keeper
(stronger remaining owner-boundary proof) that must survive any edit batch.

Scope: all 95 pytest files under `tests/` (~12k lines) plus the two Playwright
specs under `apps/web/tests`, split into eight read-only discovery lanes along
production-owner boundaries (storage/domain/API/CLI, unit research, contracts,
science A/B, jev, integration, live/reconciliation/web). Seven lanes completed;
the science lane covering `test_mutation_composition.py`,
`test_expression_dispositions.py`, `test_expression_coverage.py`,
`test_cnv_shard_scan.py`, `test_cnv_project_scan.py`, `test_cnv_dispositions.py`,
`test_descriptors.py`, `test_methods.py`, and `test_luad_foundation.py` was
aborted and is an open gap. Retained false positives were recorded per lane;
source-inspection architecture guards (cancer-agnostic core, no-credential
transport, no-persistence-SQL layering, fixture-byte digests, transport/config
default pins) are retained under the skill's retention bar.

## Delete candidates

Each entry names the exact test, the failure it actually detects, and the
stronger proof that remains.

- `tests/test_domain_events.py::test_registered_vocabulary_contains_every_phase1_type`
  [line 57] — copies a historical vocabulary; two listed names
  (`EVIDENCE_BUILD_COMPLETED`, `JEV_DEEP_COMPLETED`) have no producers.
  Keepers: append-time unknown-type rejection and real orchestrator emissions.
  Unlocks dead names in `cancerjev/domain/events.py`.
- `tests/contracts/test_parsers.py::test_real_files_provenance_capture` [252]
  and `::test_files_record_without_explicit_open_access_is_not_open` [373] —
  the owner `parse_files_provenance` has zero production callers (orphaned by
  P04). Keepers: expression-coverage fail-closed and the open-access request
  filter. Unlocks `parse_files_provenance`, `FilesProvenance`, and the orphaned
  `/files` expression-workflow capture fixture.
- `tests/science/test_discovery_reduction.py::test_counts_for_returns_distinct_and_doc_counts`
  [115] — hand-built scan; keeper asserts the same accessor on real pages in
  `tests/science/test_occurrence_scan.py`.
- `tests/science/test_actions.py::test_revision_binding_matches_the_accepted_state`
  [567] — identity copier (test builds the record it then recomputes).
  Keepers: faithful-revision provenance and tampered-artifact contradiction.
- `tests/science/test_pathway_persistence.py::test_tp53_fixture_records_its_mapped_membership`
  [109] — fixture inventory only; keeper: real TP53 mapping in the pathway
  membership contracts.
- `tests/science/test_pathway_persistence.py::test_declared_consumer_attaches_descriptive_membership_and_round_trips`
  [51] (+ sibling [76]) — `attach_pathway_evidence` / `pathway_evidence` have
  no production caller (P12b declared but unwired). Product decision: may
  unlock the whole attach layer (`research/pathways.py`, `domain/pathway.py`,
  `StatisticalState.pathway_evidence`, codec and finalize branches).
- `tests/jev/test_measured_observation.py::test_measured_observation_is_typed_and_boundary_decodable`
  [26] — constructor echo, no decode path. Keepers: deep-slice real
  action-produced observation; sibling validation test in the same file.
- `tests/jev/test_service.py::test_shared_worker_service_has_no_cross_run_cost_quota`
  [542] — the named quota cannot occur (no service-level counter; the real cap
  is enforced per run). Keepers: cache-reuse usage assertions and the state-cap
  tests.
- `tests/integration/test_cnv_discovery_replay.py` [129], [184] — legacy
  `run_cnv_discovery` path with no non-test callers. Keepers:
  `tests/science/test_cnv_project_scan.py`, `tests/science/test_cnv_dispositions.py`.
- `tests/integration/test_cutover.py` [84], [130] — legacy
  `_compose_legacy_survivor_states` branch. Keepers:
  `tests/science/test_modality_union.py`, acceptance union path. Maintainer
  decision: branch is documented "for historical artifacts"; deleting these
  tests makes legacy CNV/cutover production fully dead (codecs, domain types
  and the legacy function are unlocked with them).
- `tests/integration/test_stage8_finalize.py::test_action_registry_bounds_the_dispatch_decision`
  [292] — duplicate orchestrator slice plus fake-id negatives nothing can
  offer. Keepers: `tests/integration/test_deep_slice.py` [154] and [446].
- `tests/leakage/test_no_leakage.py::test_disposition_and_admission_code_never_reads_the_census_field`
  [72] — set-dominated by the census-confinement scan in the same file [53],
  and weakened by an `exists()` skip.
- `tests/acceptance/test_final_acceptance.py` [32], [42], [112], [127] —
  frozen-corpus presence, union state tautologies, duplicate ownership gate,
  and capability-flag restatement. Keepers: reconciliation manifest/hash and
  parser-vs-derivation suites, `tests/science/test_modality_union.py`,
  `tests/test_execution_ownership.py`,
  `tests/integration/test_live_replay.py::test_alternate_research_spec_selects_only_its_project`.
  Before deleting [72], carry its dossier claim phrases into
  `tests/integration/test_stage8_finalize.py`.
- `tests/reconciliation/test_reconciliation.py::test_sentinels_are_present_and_derived_independently`
  [60] — MANIFEST self-consistency only; keeper: production parser vs
  independent derivation over frozen bytes [88].

## Repair candidates

Real contract, but the assertion cannot fail for the named reason.

- `tests/unit/test_prospective.py::test_grouped_bootstrap_follows_the_declared_seed`
  [109] — HOLDOUT has one group, so every replicate is identical and seed
  handling is untested. Rewrite with a multi-group fixture asserting seed
  sensitivity, or delete as a duplicate of the determinism test.
- `tests/contracts/test_capability_contracts.py::test_real_capability_is_deterministic_and_reason_bearing`
  [118] — both probe runs use identical bytes and identical stub metadata;
  assert an independently derived canonical payload/digest instead.
- `tests/contracts/test_mutation_composition_contracts.py::test_composition_matches_an_independent_recount_of_the_pinned_bytes`
  [66] — the "independent recount" feeds the helper directly. Drive the pinned
  page through `parse_ssm_occurrence_page` / the real scan and compare.
- `tests/science/test_evidence_maturity.py` [36] — self-comparison of a value
  the owner just derived; assert the literal level instead.
- `tests/science/test_campaign_program.py` [129] — asserts a frozen snapshot
  against its own literal; drop the line, keep the cross-campaign rejection.
- `tests/science/test_replication_partition.py` [58] — the expected raise fires
  from the empty `rationale` guard before the disjointness rule; use a valid
  rationale so the intended guard is what raises.
- `tests/science/test_functional_posture.py` [23] — substring presence in a
  decision record cannot detect DEFER→ADOPT drift; parse the decision rows and
  compare to the typed map.
- `tests/science/test_modality_union.py` [139] — accepts either error code; the
  named `UNION_OUTSIDE_UNIVERSE` branch is unreachable through this input.
  Assert the reachable `UNION_EVIDENCE_MISSING`, or delete the unreachable
  branch with a domain-invariant note.
- `tests/science/test_lane_composition.py` [263] — order-independence asserted
  between two private-helper outputs; carry the assertion into a real
  multi-batch `run_expression_discovery` / `acquire_batched_expression` path.
- `tests/integration/test_stage8_finalize.py` [119] — `baseline_next_move(0) ==
  baseline_next_move(0)` self-comparison; replace with a real recompute or drop.
- `tests/llm/test_openrouter_adapter.py` [150] — compares the request to the
  module's own `MAX_OUTPUT_TOKENS`; pin an explicit literal/hard upper bound.
- `tests/leakage/test_no_leakage.py` [60] — the import scan walks
  `ast.ImportFrom` only; `import X` forms bypass it. Extend the scan.
- `tests/reconciliation/test_reconciliation.py` [165] — reads an untracked
  `data/runs/.../result.json`; on a fresh clone this errors instead of
  skipping. Needs a hermetic committed slice (or hash-pinned IDs).
- `apps/web/tests/phase1.spec.ts` — not routed by CI; the durable story is
  owned more strongly by `tests/browser/current.spec.ts`. Carry the unique
  auto-follow / client-router run-switch assertions into the CI-routed suite,
  then retire the duplicate.

## Consolidate candidates

Move the assertion to the named owner; no contract lost.

- `tests/test_persistence_guards.py` [232] → `tests/test_artifacts.py` +
  `tests/integration/test_scientific_reads.py`.
- `tests/test_ownership_recovery.py` [17] → exclusivity keeper plus the
  cross-process test in the same file.
- `tests/test_api.py` canned-demo fixtures → shared `tests/helpers.py`
  (same leftover copy in `tests/test_fixtures.py`).
- `tests/unit/test_acceptance_budget.py` [68] → transport-bounds defaults +
  `test_config_env.py` (drop tautological cross-constant equalities).
- `tests/unit/test_capability.py` [128] → `test_campaign_program.py` +
  `test_campaign_dispatch.py`.
- Three universe-loop fail-closed cases in `test_discovery_reduction.py`
  [266]–[292] → `tests/science/test_universe_shards.py`.
- `tests/science/test_actions.py` [255] → fold the type-mismatch row into the
  existing wrong-input-kind matrix.
- `tests/science/test_modality_admission_posture.py` [31] → capability
  contract suite (carry MIRNA/RPPA/SURVIVAL reason rows).
- `tests/jev/test_questions_validation.py` [101] → adapter owner suite, driven
  through `TypeSafeAdapter.evaluate` with a failing fake client.
- `tests/integration/test_cutover.py` [111] → port descriptor-action execution
  onto the canonical union state before deleting the legacy file.
- `tests/integration/test_live_replay.py` [654] → `test_lane_composition.py`;
  unlocks the test-only `cancerjev/research/live.py` re-exports.

## Cross-cutting signals

- Test-only seams: `Repository.list_runs(ownership=…)` has no non-test callers
  (three suites); `compose_discovery_states` has no production caller;
  `research/nextmove.py::next_move` and the `*_BY_ID` question maps are dead
  exports.
- The lanes recorded retained false positives explicitly, e.g. the
  cancer-agnostic source grep, credential/scan guards, config-default pins,
  fixture digest pins, and legacy duplicate-count parser contracts.

## Status and next steps

- Proof run: none (read-only discovery). Validation plan at edit time:
  focused `python -m pytest <node ids>`, then `python -m ruff check .`, strict
  mypy from the project environment, and the full default offline `pytest`
  suite before any commit, per `AGENTS.md`.
- Next: one coherent edit batch (dead parser + legacy CNV/cutover deletions
  with keeper ports), then a full campaign on one subsystem.
- Open gap: rerun the aborted science lane (mutation/expression/CNV,
  descriptors, methods, LUAD foundation) before a whole-subsystem campaign.
- Maintainer decisions: legacy CNV/cutover branch retention vs deletion; P12b
  pathway attach layer wiring vs removal.
