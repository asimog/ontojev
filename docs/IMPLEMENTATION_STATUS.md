# Implementation status

Factual source of truth for the current repository state: the Stage 3 hard cutover plus the
Stage 4-8 implementations (systematic discovery, cutover, the full investigation loop, and
candidate finalization with the no-Jev comparison; 2026-09-25). Every claim is labeled
IMPLEMENTED, PLANNED or UNVERIFIED. Current schema, projection, question-set, policy and
registry identities are the machine-checked values in
[REPOSITORY_FACTS.md](REPOSITORY_FACTS.md) and are not restated here. Historical stage
narratives, handoff documents and audit journals are retired (git history is the archive of
record); they are not current instructions or current capability claims.

**Stage 8 recovery point:** the annotated tag `stage8-pre-stage9-cutover-9fb9192` (commit
`9fb9192`, verified Stage 8 baseline) marks the recovery point before any future fail-closed
schema cutover; there are no migrations, so recovery is a checkout of that tag, not a data
migration. See [CHANGELOG.md](../CHANGELOG.md).

## Current architecture — IMPLEMENTED

One typed runtime chain:

```text
GDC open-access API -> strict parsers -> typed acquisition/lane records
 -> canonical typed StatisticalState
 -> deterministic Wide Jev projection
 -> validated typed answers -> Python admission -> Candidate
 -> immutable typed EvidenceState E0
 -> operator-authorized registered action (explicit deep action id)
     -> immutable revision E1/E2
 -> Deep Jev (jev-evidence-projection-v2, question set deep-v1)
 -> Python next-move policy (deep-policy-v2)
 -> optional bounded hypothesis generation
      (deterministic template by default; injected OpenRouter adapter on an
       explicitly authorized path)
 -> Jev hypothesis critique (jev-hypothesis-projection-v2, question set hypothesis-v2)
 -> dossier (schema 3)

Systematic pre-Wide mutation funnel (Stage 4, python -m cancerjev discover --live):
 GDC release/project inventory -> cohort case frame
 -> indexed /genes universe enumeration (fixed protein_coding gene_id-asc prefix, <=10 pages)
 -> <=100-gene indexed mutation-count batches (coverage acquired once)
 -> per-gene typed outcome -> deterministic count-descending reduction (<=10 survivors)
 -> immutable persisted MutationDiscoveryResult

Independent expression arm (Stage 5, python -m cancerjev discover-expression --live):
 same release/project/case frame and fixed indexed 1,000-gene universe
 -> <=100-gene x <=250-case availability/value batches (UQFPKM)
 -> typed local log2(UQFPKM+1) summaries with complete missingness accounting
 -> n>=20 within-gene Tukey 1.5xIQR tails, or explicit insufficient/degenerate outcome
 -> immutable persisted ExpressionDiscoveryResult; no Jev or cross-lane inference

Survivor-only CNV arm (Stage 6, python -m cancerjev discover-cnv --live --stage4-run RUN_ID):
 Stage 4 release, cohort frame and <=10 survivor IDs
 -> fixed /cnv_occurrences pages (<=250 rows, <=10 pages per survivor)
 -> strict occurrence parsing with category, caller/source and missing-sample context
 -> unique positive cases per provider category, explicit conflicts and no neutral inference
 -> immutable persisted CnvDiscoveryResult; no Jev or cross-lane inference

Stage 7 cutover and descriptive actions (`research/cutover.py`, `science/descriptors.py`,
`science/actions.py`):
 Stages 4-6 artifacts bound exactly (spec, release, cohort, universe, frame, survivors, entities)
 -> one canonical typed StatisticalState per Stage 4 survivor
 -> registered held-data descriptive actions SUMMARIZE_EXPRESSION_TAIL_V1 and
    SUMMARIZE_CNV_CATEGORIES_V1 (zero acquisition, zero model calls); several eligible actions
    require one explicitly operator-requested action id; deep dispatch never auto-selects

Stage 8 finalization (`research/finalize.py`, `research/investigation.py`):
 terminal recorded move (COMPLETE/ABSTAIN/GENERATE_HYPOTHESES) ends the arc with its
 actual policy reason (never routed through the follow-up dispatcher)
 -> FinalCandidateResult derived deterministically from the recorded run state
 -> no-jev-baseline-v1 read-only deterministic comparison (observed Jev path vs declared
    baseline replay; NOT_COMPARABLE where unsupported; read-only, no model call)
 -> authoritative JSON dossier (schema 3) embedding result and comparison; Markdown derived
 -> DOSSIER_READY -> CANDIDATE_COMPLETE -> next candidate -> RUN_COMPLETED

Optional evaluation harness (outside the numbered runtime stages; never invoked by the runtime):
 `research/prospective.py` blinded grouped labels + grouped-bootstrap arm comparison and
 `research/evaluation.py` label-based ranking overlap; operator-supplied documents only
```

- IMPLEMENTED: Python domain names are unsuffixed (`StatisticalState`, `EvidenceState`,
  `ResearchSpec`, `Candidate`, `HypothesisDraft`). Operational ids/hashes travel in
  `StateRecord` / `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific
  identity.
- IMPLEMENTED: versioned fail-closed serialization; current schema versions are the
  machine-checked values in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md). Older/unknown schemas
  are rejected fail-closed; there are **no migrations and no legacy readers**. Historical
  databases and artifacts are retained, not rewritten.
- IMPLEMENTED: versioned question sets, projections and policies (current identities in
  [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)) with unchanged semantics. The current state
  projection adds the observed CNV fields and the Python-computed `eligible_followups` list; it
  introduces no new semantic question.
- IMPLEMENTED: registered deterministic actions (current roster and registry version in
  [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)): the integrity actions verify recorded evidence
  from retained response artifacts; the held-data descriptor actions restate held case-labelled
  values with fixed predeclared methods. They acquire no data, call no model and compute no new
  biological quantity; an action failure is a typed outcome that promotes nothing.
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
- IMPLEMENTED and live-verified: Stage 5 independent expression discovery
  (`research/expression_discovery.py`, `python -m cancerjev discover-expression --live`). It uses fixed two-dimensional request batching, retains
  case-labelled UQFPKM values and explicit missing rows/columns, computes only local
  `log2(UQFPKM+1)` summaries and the predeclared within-gene empirical-tail descriptor, and
  persists one immutable typed result. The recorded request plan stays 97 under the unchanged
  150-request/64-MiB run caps. It performs no mutation selection, Jev/model work, differential expression,
  tumor-normal comparison or cross-lane association.
- IMPLEMENTED and live-verified: Stage 6 survivor-only CNV discovery
  (`research/cnv_discovery.py`, `python -m cancerjev discover-cnv --live --stage4-run RUN_ID`).
  It binds a completed Stage 4 artifact, exact release and cohort case frame; queries only its
  at-most-10 survivors with fixed 250-row pages and at most 10 pages per gene; preserves provider
  five-category labels, callers, source/sample context and explicit category conflicts; and
  persists one immutable typed result. Absence is never neutral, overlapping case
  categories are not summed, and no Jev/model or cross-lane inference occurs.
- IMPLEMENTED and live-verified: Stage 7 cutover and descriptive actions (`research/cutover.py`,
  `science/descriptors.py`). `compose_discovery_states` binds Stages 4-6
  artifacts exactly — spec, release, cohort/project, universe membership, population frame,
  survivor list and per-gene entities — and composes one canonical `StatisticalState` per Stage 4
  survivor with the mutation, expression and CNV lanes and the selection-bias limitation recorded
  in `TestedContext`. Any cross-stage drift is a typed `CutoverError` refusal. The shared
  deterministic descriptors (`science/descriptors.py`) back both Stage 5/6 discovery and the
  registered `SUMMARIZE_*` actions. Cutover performed no acquisition and no model call.
- IMPLEMENTED and offline-verified: Stage 8 candidate finalization (`research/finalize.py`,
  `research/investigation.py`). For every candidate whose evidence was accepted, Stage 8 derives
  one deterministic `FinalCandidateResult` from the recorded run state (final revision, actual
  policy reason, evidence sufficiency, remaining uncertainty, hypothesis status, limitations,
  full provenance), computes the `no-jev-baseline-v1` comparison as a read-only deterministic
  replay over the same evidence (never mutating EvidenceState, never executing actions, never
  generating hypotheses, calling no model; unsupported dimensions are `NOT_COMPARABLE`, never
  invented), persists the authoritative dossier (schema 3, Markdown derived from the same
  structured payload) and the final result artifact, records `DOSSIER_READY`, and marks the
  candidate `CANDIDATE_COMPLETE` only after both are persisted. Terminal moves stop the arc with
  their actual reason (`INVESTIGATION_COMPLETE`, `DEEP_JUDGMENT_UNAVAILABLE`, ...); several
  eligible actions fail closed with `EXPLICIT_ACTION_REQUIRED`; admission provenance comes from
  the persisted candidate record (`wide-policy-v2` vs `operator-selection-v1`); no human review
  participates; the candidate loop continues automatically and the run completes only after the
  candidate queue is exhausted. Dossier refusal (`DOSSIER_UNAVAILABLE`) leaves the candidate
  failed, never complete.
- IMPLEMENTED and offline-verified: OPTIONAL evaluation/calibration harness, outside the numbered
  runtime stages and never invoked by them (`research/prospective.py`, `research/evaluation.py`).
  The prospective validator fail-closes on unblinded, unreviewed or duplicate labels, on any
  group crossing fixed splits, and on arm outputs that do not bind the protocol; it computes
  per-arm metrics and a grouped-bootstrap precision@3 difference by declared seed and always
  records `HUMAN_REVIEW_REQUIRED`. It is an operator-supplied document tool for future blinded
  studies, not a Stage 8 dependency; candidate completion never reads it. No protocol has been
  executed and no labelled corpus exists.
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
  the current roster, offline autoresearch, and any incremental-value result.

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
| Typed domain runtime (state, evidence, candidate, hypotheses, envelopes) | IMPLEMENTED; versioned fail-closed schemas (current versions in REPOSITORY_FACTS.md); fail-closed rejection of older schemas |
| Wide semantic judgment and admission | IMPLEMENTED: state projection + wide question set + admission policy (identities in REPOSITORY_FACTS.md), at most three promoted candidates; zero promotions is valid |
| Deep evidence/actions | IMPLEMENTED: E0/E1/E2, four registered actions (two integrity, two held-data descriptors), explicit operator selection/authorization; several eligible actions require one explicit action id |
| Deep judgment and next move | IMPLEMENTED: evidence projection + deep question set + deep next-move policy (identities in REPOSITORY_FACTS.md); recorded move never dispatched by the policy |
| Hypotheses | IMPLEMENTED: deterministic default, optional injected OpenRouter adapter, at most three per candidate, Jev critique; generated text is never evidence |
| Dossiers | IMPLEMENTED: authoritative JSON + derived Markdown with per-section availability (dossier schema in REPOSITORY_FACTS.md), embedding the Stage 8 final result and no-Jev comparison, live notice |
| Evaluation harness | IMPLEMENTED offline: `python -m cancerjev evaluate` compares recorded rankings against operator-supplied, pre-registered labels; no superiority claim |
| Enforcement | GDC request/byte/page caps and candidate/follow-up/revision/hypothesis caps exist; SDK retries are disabled; a total paid-model spend gate does not exist |
| Scientific domain typing | IMPLEMENTED for the runtime chain; JSON remains the boundary for events, storage, API/dossier presentation and artifact envelopes |
| Persistence/API | Versioned SQLite schema (REPOSITORY_FACTS.md), immutable artifacts/events, read-only API (API version in REPOSITORY_FACTS.md) |
| Systematic mutation discovery (bounded indexed prefix) | IMPLEMENTED (Stage 4): 1,000-gene protein-coding prefix, ≤100-gene batches, deterministic ≤10 survivors, persisted result; prefix-biased by construction |
| Independent expression arm | IMPLEMENTED and live-verified (Stage 5): live acceptance PASSED (2026-09-25) |
| Survivor-only CNV arm | IMPLEMENTED and live-verified (Stage 6): full live workload completed, all 10 survivors |
| Discovery cutover to canonical states | IMPLEMENTED and live-verified (Stage 7): exact Stage 4-6 binding over the live persisted artifacts, one canonical state per survivor |
| Held-data descriptive actions | IMPLEMENTED and live-verified (Stage 7): `SUMMARIZE_EXPRESSION_TAIL_V1`, `SUMMARIZE_CNV_CATEGORIES_V1` VERIFIED over the composed live states; zero acquisition, zero model calls |
| Stage 8 candidate finalization | IMPLEMENTED and offline-verified: FinalCandidateResult + authoritative dossier + `no-jev-baseline-v1` comparison; DOSSIER_READY -> CANDIDATE_COMPLETE per candidate; no human review; multi-candidate loop + queue-exhausted RUN_COMPLETED |
| Jev-vs-No-Jev runtime comparison | IMPLEMENTED and offline-verified: read-only deterministic replay of `no-jev-baseline-v1` over the same evidence; decision deltas only, never a superiority claim |
| Prospective protocol evaluation | OPTIONAL evaluation/calibration harness (`research/prospective.py`, `research/evaluation.py`), outside the numbered runtime stages and never invoked by the runtime; no protocol executed (no labelled corpus exists) |
| Combined multi-lane reduction and inferential extensions | DEFERRED behind source/matching/reference/censoring/statistical gates; not current runtime |
| Multi-modal Stage 9 target skeleton (Arm Jev, candidate union, integrated states) | PROVISIONAL PLANNED, pending source-grounded Stage 9 design reviews; not current runtime |
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

No scientific-readiness or incremental-Jev-value claim follows from any demonstration. No
provider invoice, account quota or cost field is measured. Bayesian/model reproducibility remains
UNVERIFIED: no seed or temperature control exists, and one live answer set failed validation, so
repeated judgments may differ.

## Stage 5-7 live acceptance and Stage 7 budget gate — VERIFIED (2026-09-25)

All runs anonymous public open-access GDC, TypeSafe key from `.env.local` only, caps unchanged,
no limit enlarged, no result retried for a favorable outcome:

- Stage 5 live (run `80848609-2caf-4ca2-9cbc-2dccdce2ea3e`): 61 live attempts, 5,007,079 bytes;
  release 46.0, 1,000/1,000 universe genes (membership hash identical to the Stage 4 run);
  585-case cohort frame; workflows `STAR - Counts` / `RNA-Seq`. Per-gene outcomes: 946
  `ExpressionSummaryResult`, 54 typed `UnavailableLane(PROVIDER_SUMMARY_NOT_REQUESTED_IN_STAGE_5)`
  (never zero), 941 OBSERVED tails, 5 `DEGENERATE_REFERENCE` tails; missing case columns retained
  per gene (e.g. USH2A: 67 of 585 cases).
- Stage 6 live (run `6303faff-6025-407f-9eff-32e0b3feee6c`, bound to Stage 4 run
  `e2035487`): 20 live attempts, 1,860,737 bytes; all 10 survivors complete with two strict
  250-row pages each; provider categories Gain/Amplification/Loss with caller and
  sample-source context; no category summed across overlapping cases.
- Stage 7 cutover over the live persisted artifacts: 10 canonical states composed with exact
  spec/release/universe/frame/survivor/entity binding; USH2A rank 1 (402 affected cases, 339 CNV
  occurrences, explicit missingness); `SUMMARIZE_EXPRESSION_TAIL_V1` and
  `SUMMARIZE_CNV_CATEGORIES_V1` executed VERIFIED (n=518 expression values, n=339 occurrences).
- Stage 7 Jev budget gate live (run `a3680ada-642b-46a9-af1d-a11ddc23b694`, 8 live attempts /
  180,008 bytes; `CANCERJEV_JEV_MAX_ATTEMPTS=1`): 10 real states projected under
  `jev-state-projection-v4`; exactly one real TypeSafe judgment; the other nine evaluations
  failed closed with `JEV_ATTEMPT_BUDGET_EXHAUSTED` and promoted nothing; wide admission recorded
  its natural ABSTAIN. Paid spend was bounded to one evaluation by configuration.

No incremental-value or scientific-readiness claim follows: these are bounded acceptance runs of
the implemented contracts, and the optional blinded evaluation has no executed protocol.

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

## Next: Stage 9 (provisional, pending source-grounded design reviews)

The provisional Stage 9 direction reorients the completed Stage 8 infrastructure toward the
core scientific objective: the autonomous multi-modal target-discovery loop described in
[ARCHITECTURE.md](ARCHITECTURE.md) (PROVISIONAL TARGET ARCHITECTURE, SUBJECT TO THE
SOURCE-GROUNDED STAGE 9 DESIGN REVIEWS). No part of that skeleton — Arm Jev, the candidate
union, the integrated-gene-state generalization or the campaign-selection policy — is
implemented; no Stage 9 contract is frozen. When scientific follow-up work is separately
authorized, the first sequence stays narrow and sequential (provisional):
`BUILD_MATCHED_ASSAY_FRAME_V1` → `ACQUIRE_CANDIDATE_SSM_CASES_V1` →
`MUTATION_EXPRESSION_ASSOCIATION_V1`. CNV-expression, survival, pathway and scRNA analyses
are explicitly deferred, not simultaneous. Conditional inferential extensions remain deferred
behind their source, matching, reference, censoring and statistical-review gates.

Stages 4-7 live acceptance is VERIFIED as of 2026-09-25; Stage 8 finalization is
offline-verified and requires no human review; the optional blinded evaluation harness has no
executed protocol or labelled corpus. Do not convert any of that into a scientific-readiness
claim. [The roadmap](DISCOVERY_ROADMAP.md) indexes the remaining evidence gates. Do not extend
the action registry or question sets without a separately authorized task.
