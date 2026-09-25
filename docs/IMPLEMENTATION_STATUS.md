# Implementation status

Factual source of truth for the current repository state after the Stage 3 hard cutover and the
Stage 6/7/8 discovery, cutover-action and prospective-protocol implementations (2026-09-25). Every
claim is labeled IMPLEMENTED, PLANNED or UNVERIFIED. Historical stage narratives, handoff documents
and audit journals are retired (git history is the archive of record); they are not current
instructions or current capability claims.

## Current architecture — IMPLEMENTED

One typed runtime chain:

```text
GDC open-access API -> strict parsers -> typed acquisition/lane records
 -> canonical typed StatisticalState
 -> deterministic Wide Jev projection (jev-state-projection-v4)
 -> validated typed answers -> Python admission (wide-policy-v2) -> Candidate
 -> immutable typed EvidenceState E0
 -> operator-authorized registered action (explicit deep action id)
     -> immutable revision E1/E2
 -> Deep Jev (jev-evidence-projection-v2, question set deep-v1)
 -> Python next-move policy (deep-policy-v2)
 -> optional bounded hypothesis generation
      (deterministic template by default; injected OpenRouter adapter on an
       explicitly authorized path)
 -> Jev hypothesis critique (jev-hypothesis-projection-v2, question set hypothesis-v2)
 -> dossier (schema 2)

Systematic pre-Wide mutation funnel (Stage 4, python -m cancerjev discover --live):
 GDC release/project inventory -> cohort case frame
 -> indexed /genes universe enumeration (fixed protein_coding gene_id-asc prefix, <=10 pages)
 -> <=100-gene indexed mutation-count batches (coverage acquired once)
 -> per-gene typed outcome -> deterministic count-descending reduction (<=10 survivors)
 -> immutable persisted MutationDiscoveryResult (schema 1)

Independent expression arm (Stage 5, python -m cancerjev discover-expression --live):
 same release/project/case frame and fixed indexed 1,000-gene universe
 -> <=100-gene x <=250-case availability/value batches (UQFPKM)
 -> typed local log2(UQFPKM+1) summaries with complete missingness accounting
 -> n>=20 within-gene Tukey 1.5xIQR tails, or explicit insufficient/degenerate outcome
 -> immutable persisted ExpressionDiscoveryResult (schema 1); no Jev or cross-lane inference

Survivor-only CNV arm (Stage 6, python -m cancerjev discover-cnv --live --stage4-run RUN_ID):
 Stage 4 release, cohort frame and <=10 survivor IDs
 -> fixed /cnv_occurrences pages (<=250 rows, <=10 pages per survivor)
 -> strict occurrence parsing with category, caller/source and missing-sample context
 -> unique positive cases per provider category, explicit conflicts and no neutral inference
 -> immutable persisted CnvDiscoveryResult (schema 1); no Jev or cross-lane inference

Stage 7 cutover and descriptive actions (`research/cutover.py`, `science/descriptors.py`,
`science/actions.py` registry version 3):
 Stages 4-6 artifacts bound exactly (spec, release, cohort, universe, frame, survivors, entities)
 -> one canonical schema-5 StatisticalState per Stage 4 survivor
 -> registered held-data descriptive actions SUMMARIZE_EXPRESSION_TAIL_V1 and
    SUMMARIZE_CNV_CATEGORIES_V1 (zero acquisition, zero model calls); several eligible actions
    require one explicitly operator-requested action id; deep dispatch never auto-selects

Stage 8 prospective protocol (`research/prospective.py`, offline operator tool):
 declared blinded grouped labels (>=2 reviewers, adjudicated, no split/group leakage)
 -> arm outputs bound to the protocol and covering every item
 -> grouped-bootstrap precision@3 differences by fixed seed; report always says
    HUMAN_REVIEW_REQUIRED and makes no value/superiority claim
```

- IMPLEMENTED: Python domain names are unsuffixed (`StatisticalState`, `EvidenceState`,
  `ResearchSpec`, `Candidate`, `HypothesisDraft`). Operational ids/hashes travel in
  `StateRecord` / `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific
  identity.
- IMPLEMENTED: serialized schema versions. StatisticalState 5; EvidenceState 4; ResearchSpec 7;
  MutationDiscoveryResult 1; ExpressionDiscoveryResult 1; CnvDiscoveryResult 1; SQLite schema 5.
  Older/unknown schemas are rejected fail-closed;
  there are **no migrations and no legacy readers**. Historical databases and artifacts are
  retained, not rewritten.
- IMPLEMENTED: question sets `wide-v3`, `deep-v1` and `hypothesis-v2` with unchanged semantics;
  projections `jev-state-projection-v4`, `jev-evidence-projection-v2` and
  `jev-hypothesis-projection-v2`; policies `wide-policy-v2` and `deep-policy-v2`. The v4 state
  projection adds the observed CNV fields and the Python-computed `eligible_followups` list; it
  introduces no new semantic question.
- IMPLEMENTED: registered deterministic actions are exactly `CHECK_EVIDENCE_INTEGRITY_V1`
  (input `STATISTICAL_STATE`, 5 checks), `CHECK_REVISION_FAITHFULNESS_V1` (input
  `EVIDENCE_STATE`, 4 checks), `SUMMARIZE_EXPRESSION_TAIL_V1` (input `STATISTICAL_STATE`,
  held-data Tukey tail) and `SUMMARIZE_CNV_CATEGORIES_V1` (input `STATISTICAL_STATE`, held-data
  positive-case category summary), registry version 3. They acquire no data, call no model and
  compute no new biological quantity; the two descriptor actions only restate held case-labelled
  values with the fixed predeclared methods.
- IMPLEMENTED: Python owns loops, routing, budgets, dispatch, stopping and abstention.
  `FOLLOWUP_LIMIT = 3` and `EVIDENCE_ITERATION_LIMIT = 2` bound one candidate arc; deep policy
  records exactly one typed move (`COMPLETE` / `FOLLOW_UP` / `GENERATE_HYPOTHESES` / `ABSTAIN`)
  and never dispatches it. Dispatch is a separate Python step requiring explicit operator
  authorization; with several eligible actions the run refuses `EXPLICIT_ACTION_REQUIRED` unless
  the operator named one action id. Wide admission never dispatches a follow-up.
- IMPLEMENTED: bounded Jev provider envelopes. `CANCERJEV_JEV_MAX_ATTEMPTS` (default 25, hard cap
  1,015) counts provider attempts and `CANCERJEV_JEV_MAX_INPUT_TOKENS` (default 1,600,000, hard
  cap 1,015 × 64,000) reserves 64,000 input tokens per attempt before any provider call; both are
  typed `JEV_*_BUDGET_EXHAUSTED` outcomes, never silent continuation. A total paid-model spend
  gate remains absent.
- IMPLEMENTED: one canonical `ResearchSpec`, `LUAD_RESEARCH_V1` (`domain=lung cancer`,
  `cohort_id=TCGA-LUAD`, `project_id=TCGA-LUAD`): single explicit TCGA-LUAD cohort, bounded
  acquisition, implemented composition (provider-ranked mutation discovery, local
  `log2(UQFPKM+1)` expression summary and Stage-4-survivor CNV occurrence discovery) and the fixed `DiscoverySpec` systematic-discovery
  configuration (protein_coding, `GENE_ID_ASC`, offset 0, universe limit 1,000, batch size 100).
  TCGA-LUAD and TCGA-LUSC are never pooled.
- IMPLEMENTED: Stage 4 systematic mutation discovery (`research/discovery.py`,
  `python -m cancerjev discover --live`): release-bound first-1,000 protein-coding gene-id-asc
  prefix over `/genes` (≤10 strictly validated pages), indexed affected-case counts in ≤100-gene
  batches with project SSM coverage acquired once, exactly one typed outcome + disposition per
  requested gene, deterministic `MUTATION_LUAD_AFFECTED_COUNT_DESC_V1` reduction to at most
  `ScientificLimits.max_survivors` (10) survivors, and one immutable persisted
  `MutationDiscoveryResult` artifact. The provider top-mutated ranking is a labelled comparator
  only. No provider rank, `_score`, Jev, LLM, census status or hidden biological knowledge enters
  the reduction. Stage 4 terminates at the survivor result: no StatisticalState, Wide candidate or
  Jev evaluation is generated by the discovery path. The provider-ranked `run` path is unchanged
  and remains the labelled baseline/comparator configuration.
- IMPLEMENTED and offline-verified: Stage 5 independent expression discovery
  (`research/expression_discovery.py`, `python -m cancerjev discover-expression --live`) over the
  same release-bound indexed universe. It uses fixed two-dimensional request batching, retains
  case-labelled UQFPKM values and explicit missing rows/columns, computes only local
  `log2(UQFPKM+1)` summaries and the predeclared within-gene empirical-tail descriptor, and
  persists one immutable schema-1 result. The worst-case request plan is 97 under the unchanged
  150-request cap. It performs no mutation selection, Jev/model work, differential expression,
  tumor-normal comparison or cross-lane association. Live Stage 5 acceptance is UNVERIFIED.
- IMPLEMENTED and offline-verified: Stage 6 survivor-only CNV discovery
  (`research/cnv_discovery.py`, `python -m cancerjev discover-cnv --live --stage4-run RUN_ID`).
  It binds a completed Stage 4 artifact, exact release and cohort case frame; queries only its
  at-most-10 survivors with fixed 250-row pages and at most 10 pages per gene; preserves provider
  five-category labels, callers, source/sample context and explicit category conflicts; and
  persists one immutable schema-1 result. The worst-case request plan is 101. A bounded anonymous
  endpoint-shape probe verified generic `Loss`, missing tumor-sample IDs and mixed ASCAT callers;
  the full Stage 6 live workload remains UNVERIFIED. Absence is never neutral, overlapping case
  categories are not summed, and no Jev/model or cross-lane inference occurs.
- IMPLEMENTED: Stage 7 cutover and descriptive actions (`research/cutover.py`,
  `science/descriptors.py`, registry version 3). `compose_discovery_states` binds Stages 4-6
  artifacts exactly — spec, release, cohort/project, universe membership, population frame,
  survivor list and per-gene entities — and composes one schema-5 `StatisticalState` per Stage 4
  survivor with the mutation, expression and CNV lanes and the selection-bias limitation recorded
  in `TestedContext`. Any cross-stage drift is a typed `CutoverError` refusal. The shared
  deterministic descriptors (`science/descriptors.py`) back both Stage 5/6 discovery and the
  registered `SUMMARIZE_*` actions. Stage 7 is offline-verified; it performs no acquisition and
  no model call.
- IMPLEMENTED and offline-verified: Stage 8 prospective protocol validation
  (`research/prospective.py`). It is an offline operator tool: declared blinded grouped labels
  (at least two independent reviewers, adjudicated, no split/group leakage), arm outputs strictly
  bound to the protocol and covering every item, per-arm metrics over a fixed split, and a
  grouped-bootstrap precision@3 difference against the required baseline arm using the declared
  seed. The report always records `HUMAN_REVIEW_REQUIRED` and makes no incremental-value or
  superiority claim. It runs on supplied documents only; no historical corpus exists and no live
  protocol has been executed.
- IMPLEMENTED: `run --fixture demo` runs the **same shared `LiveOrchestrator`** offline with
  `FixtureTransport` + `FixtureJevAdapter` (mode `FIXTURE`, synthetic notice in the dossier).
  There is no second execution engine.
- IMPLEMENTED: hypothesis generation defaults to a deterministic template; the CLI can inject
  `OpenRouterHypothesisGenerator` (`cancerjev/llm/openrouter.py`, environment-only
  `OPENROUTER_API_KEY`, bounded validated output, never evidence) only on an explicitly
  authorized deep-candidate path. Draft validation rejects unknown fields and applies text/list
  bounds.
- IMPLEMENTED: API version 3.0.0. `apps/api/serializers.py` produces the current presentation
  payloads for `/api/states/{id}` and `/api/evidence/{id}`; the ETag is computed from the
  response bytes, while `X-Artifact-Id` / `X-Artifact-SHA256` retain source artifact identity.
- IMPLEMENTED: TypeSafe SDK retries are explicitly disabled (`RetryPolicy(max_retries=0)`), so a
  logical evaluation corresponds to at most one HTTP attempt per logical evaluation, inside the
  configured attempt/token envelopes above.
- IMPLEMENTED: cache reuse requires a pinned/versioned model identity whose provider resolution
  equals it; a mutable alias is always evaluated and never treated as already resolved.
- NOT IMPLEMENTED / not representable: universe enumeration beyond the fixed deterministic
  prefix (no full-genome scan, no random sample, no caller-controlled filters), broad-universe
  CNV acquisition, combined cross-lane discovery/reduction, further registered actions beyond
  registry version 3, offline autoresearch, and any incremental-value result.

## Removed architecture (git history is the archive; do not reintroduce)

`legacy_codecs.py`; dictionary scientific identity payloads; `state_summary.py` /
`ComputedStatisticalState` / `StateSummary`; `LegacyArtifact` / `LegacyMetric` /
`LegacyPopulation`; `build_statistical_state`; schema-1/2/3 readers; the `DemoOrchestrator`
independent Phase-1 engine (the surviving name is only a 63-line fixture-mode wrapper that
constructs `LiveOrchestrator` with `FixtureTransport` + `FixtureJevAdapter`; there is no
second execution engine) and fake actions (`DROP_INFLUENTIAL_FIXTURE_POINTS_V1`);
`ResearchSpecV2` and lane/universe composition contracts; the retired handoff/plan/audit
documents (`STAGE_01_HANDOFF`, `STAGE_02_HANDOFF`, `STAGE_03_HANDOFF`, `PHASE_3_PLAN`,
`PHASE_4_READINESS_PLAN`, `PYTHON_CORE_REVIEW`, `CODEBASE_AUDIT_2026-09-23`,
`GDC_JEV_FIT_ANALYSIS`).

## Capability table

| Capability | Status |
|---|---|
| Anonymous bounded GDC acquisition + deterministic measurements | IMPLEMENTED; one production LUAD ResearchSpec; LUAD/LUSC never pooled |
| Typed domain runtime (state, evidence, candidate, hypotheses, envelopes) | IMPLEMENTED; state/evidence 5/4, ResearchSpec 7, mutation/expression/CNV discovery results 1/1/1, SQLite 5, fail-closed rejection of older schemas |
| Wide semantic judgment and admission | IMPLEMENTED: `jev-state-projection-v4`, `wide-v3`, `wide-policy-v2`, at most three promoted candidates; zero promotions is valid |
| Deep evidence/actions | IMPLEMENTED: E0/E1/E2, four registered actions (two integrity, two held-data descriptors), explicit operator selection/authorization; several eligible actions require one explicit action id |
| Deep judgment and next move | IMPLEMENTED: `jev-evidence-projection-v2`, `deep-v1`, `deep-policy-v2`; recorded move never dispatched by the policy |
| Hypotheses | IMPLEMENTED: deterministic default, optional injected OpenRouter adapter, at most three per candidate, `hypothesis-v2` critique; generated text is never evidence |
| Dossiers | IMPLEMENTED: authoritative JSON + derived Markdown with per-section availability, schema 2, live notice |
| Evaluation harness | IMPLEMENTED offline: `python -m cancerjev evaluate` compares recorded rankings against operator-supplied, pre-registered labels; no superiority claim |
| Enforcement | GDC request/byte/page caps and candidate/follow-up/revision/hypothesis caps exist; SDK retries are disabled; a total paid-model spend gate does not exist |
| Scientific domain typing | IMPLEMENTED for the runtime chain; JSON remains the boundary for events, storage, API/dossier presentation and artifact envelopes |
| Persistence/API | SQLite schema 5, immutable artifacts/events, read-only API, version 3.0.0 |
| Systematic mutation discovery (bounded indexed prefix) | IMPLEMENTED (Stage 4): 1,000-gene protein-coding prefix, ≤100-gene batches, deterministic ≤10 survivors, persisted result; prefix-biased by construction |
| Independent expression arm | IMPLEMENTED and offline-verified (Stage 5); live acceptance UNVERIFIED |
| Survivor-only CNV arm | IMPLEMENTED and offline-verified (Stage 6); bounded live shape probe passed, full live acceptance UNVERIFIED |
| Discovery cutover to canonical states | IMPLEMENTED and offline-verified (Stage 7): exact Stage 4-6 binding, one schema-5 state per survivor, fail-closed refusals |
| Held-data descriptive actions | IMPLEMENTED and offline-verified (Stage 7): `SUMMARIZE_EXPRESSION_TAIL_V1`, `SUMMARIZE_CNV_CATEGORIES_V1`; zero acquisition, zero model calls |
| Prospective protocol evaluation | IMPLEMENTED and offline-verified (Stage 8): blinded grouped labels, grouped bootstrap by declared seed, `HUMAN_REVIEW_REQUIRED` always; no protocol executed yet |
| Combined multi-lane reduction and inferential extensions | PLANNED (Stage 9+); not current runtime |
| Offline autoresearch and demonstrated Jev incremental value | NOT IMPLEMENTED / UNVERIFIED |

## Verification performed in this environment (2026-09-25)

| Gate | Command | Result |
|---|---|---|
| Python lint | `python -m ruff check cancerjev apps tests` | Clean (IMPLEMENTED) |
| Offline suite | `python -m pytest` | All offline tests pass; `tests/live` opt-in markers excluded (IMPLEMENTED) |
| Static check | `python -m mypy` | Scoped strict check over the explicit `pyproject.toml` file list passes (IMPLEMENTED) |
| Whitespace | `git diff --check` | Clean (IMPLEMENTED) |
| Browser acceptance | `tests/browser/` (own Playwright config/package) | Suite exists and CI runs it as a separate job; **not executed in this environment — UNVERIFIED** |
| Live GDC / TypeSafe-Jev / OpenRouter acceptance | `python -m pytest -m live_acceptance tests/live/test_provider_acceptance.py` | **PASSED (2026-09-25)** with real providers; see the recorded evidence below |

Recorded live-acceptance evidence (bounded by the documented caps; no result was retried to
obtain a favorable outcome):

- Fresh LUAD sweep: 16 GDC attempts, 367,862 bytes, zero cache hits; 10 canonical typed states;
  10 real `wide-v3` judgments against `jev-1.13.0`. The provider returned one answer set that
  failed strict validation (`INVALID_DISTRIBUTION`), which was recorded fail-closed as a failed
  evaluation and promoted nothing. `wide-policy-v2` then recorded its natural **ABSTAIN**.
- Explicit operator selection and authorized follow-up over the retained cache: 16/16 GDC cache
  hits (0 new bytes) and one operator-selected candidate with an E0→E1 revision from
  `CHECK_EVIDENCE_INTEGRITY_V1`, one real `deep-v1` judgment, and a ready dossier.
- Separate labelled generation check: exactly one OpenRouter request
  (`deepseek/deepseek-v4.1-flash`, 316 input / 3,501 output tokens) and 2 of at most 3
  `hypothesis-v2` critiques, all resolved as `jev-1.13.0`. The check appended nothing to the
  production run's events.
- Replay with sockets refused: 16/16 cache hits, no new Jev provider calls, identical state
  hashes to the explicit-selection run (14 total Jev attempts, within the 15-attempt cap).

No scientific-readiness or incremental-Jev-value claim follows from this demonstration. No
provider invoice, account quota or cost field is measured. Bayesian/model reproducibility remains
UNVERIFIED: no seed or temperature control exists, and one live answer set failed validation, so
repeated judgments may differ.

## Known limitations and open gaps

- IMPLEMENTED limitation: mutation evidence is count-only. `case_with_ssm` is not a
  callable-negative denominator, so no recurrence fraction is computed; absent buckets are
  `NOT_OBSERVED`, not zero.
- IMPLEMENTED limitation: the provider-ranked examined gene set is selection-biased. State records
  the bias and does not claim a genome-wide scan.
- IMPLEMENTED limitation: the Stage 4 systematic universe is the first deterministic 1,000-gene
  prefix of the indexed protein-coding universe by ascending gene_id. It is reproducible but
  prefix-biased, not the entire genome and not an unbiased random sample; survivors are ranking
  evidence, not validated targets.
- UNVERIFIED: provider expression `median`/`stddev` estimator conventions. A historical live
  two-case capture is consistent with a population denominator and is recorded as
  `INFERRED_POPULATION_SD_UNVERIFIED`; provider summaries never drive policy.
- IMPLEMENTED limitation: the examined gene set is selection-biased (provider top-mutated
  ranking). State records the bias and does not claim a genome-wide scan.
- UNVERIFIED: case-to-sample resolution for expression values; no sample-matched cross-modal
  claim is made.
- UNVERIFIED: GDC release atomicity across requests; reproducibility means replay from retained
  responses and hashes.
- UNVERIFIED / provisional: no seed or temperature control exists for Jev, so repeated calls may
  differ. `wide-policy-v2` and `deep-policy-v2` thresholds are provisional and uncalibrated; they
  have not been tuned to force a promotion, follow-up or hypothesis request.
- VERIFIED in the 2026-09-25 live acceptance: the live wide sweep, explicit operator selection,
  authorized deterministic dispatch, one real deep judgment, the separate LLM generation check and
  the cache-only replay all completed through the current typed architecture. The natural
  `wide-policy-v2` decision was ABSTAIN; admission was not forced. Live coverage remains a single
  bounded LUAD arc, not a calibrated evaluation of value.
- PLANNED: OpenRouter construction checks only non-blank model identity, not immutable
  resolution; tightening that check is planned, not an implemented guarantee.
- PLANNED: a total paid-model spend gate and whole-request GDC deadlines are not implemented.
- NOT IMPLEMENTED: offline autoresearch (needs a labelled historical corpus and human review).
- No scientific readiness, incremental Jev value or production-use claim is made. Public GDC
  evidence alone establishes no dependency, druggability, efficacy, safety or clinical benefit.

## Stage 4 systematic discovery — IMPLEMENTED (2026-09-25)

- IMPLEMENTED: `python -m cancerjev discover --live` executed one bounded anonymous Stage 4 run
  (run `e2035487-cb7e-47b2-83d4-0cee31153143`, status `COMPLETED`). GDC release **46.0 (August 10,
  2026)**; provider-reported protein-coding total **19,843**; universe requested/returned
  **1,000/1,000**, complete; universe membership hash
  `965dc709942f7f6cf2a4133d3bffa718e0021adc6e9a8522504c008e8e69ba06`; 10 strictly validated
  `/genes` pages; 10 indexed mutation-count batches of 100 genes; **27 GDC attempts,
  2,817,301 bytes**, zero cache hits, no retries.
- IMPLEMENTED outcome (all natural; no limit was enlarged and nothing was retried): every one of
  the 1,000 requested genes has exactly one typed outcome and disposition — 1,000 complete
  observed affected-case counts (no explicit zeros, no absent buckets, no partial or unavailable
  outcomes in this prefix) — and 10 survivors under `MUTATION_LUAD_AFFECTED_COUNT_DESC_V1`
  (count descending, gene_id ascending tie break): USH2A 402, ASPM 371, INSRR 365, PLEKHO1 363,
  MTMR11 361, ATP1A2 360, SLAMF7 359, SH2D2A 359, SELE 357, FMO1 357 (gene IDs in the persisted
  result). Disposition totals: 10 `RETAINED`, 990 `BELOW_SURVIVOR_CUTOFF`.
- IMPLEMENTED: labelled comparator only — overlap between the 10 systematic survivors and the
  provider top-20 baseline is USH2A and ASPM (2 of 20). Overlap is descriptive and never entered
  survivor selection.
- The persisted result artifact (`runs/<run>/discovery/result.json`, schema 1) reconstructs the
  exact spec identity, GDC release, universe (source/filter/order/offset/membership hash), all
  mutation batches, per-gene outcomes and dispositions, the reducer identity, survivor IDs,
  warnings and limitations. No Jev, TypeSafe, OpenRouter or provider-ranked input participated.

## Next: Stage 9

Conditional inferential extensions (matched mutation-expression / CNV-expression association,
survival) are the next separately authorized work and remain deferred behind their source,
matching, reference, censoring and statistical-review gates. Stages 5-7 are complete offline but
their full live GDC acceptance remains UNVERIFIED; Stage 8 has no executed protocol or labelled
corpus. Do not convert any of that into a scientific-readiness claim.
[The roadmap](DISCOVERY_ROADMAP.md) indexes the remaining evidence gates. Do not extend the action
registry or question sets without a separately authorized task.
