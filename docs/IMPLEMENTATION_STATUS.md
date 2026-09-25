# Implementation status

Factual source of truth for the current repository state after the Stage 3 hard cutover
(2026-09-25). Every claim is labeled IMPLEMENTED, PLANNED or UNVERIFIED. Historical stage
narratives, handoff documents and audit journals are retired (git history is the archive of
record); they are not current instructions or current capability claims.

## Current architecture — IMPLEMENTED

One typed runtime chain:

```text
GDC open-access API -> strict parsers -> typed acquisition/lane records
 -> canonical typed StatisticalState
 -> deterministic Wide Jev projection (jev-state-projection-v3)
 -> validated typed answers -> Python admission (wide-policy-v2) -> Candidate
 -> immutable typed EvidenceState E0
 -> registered deterministic action -> immutable revision E1/E2
 -> Deep Jev (jev-evidence-projection-v2, question set deep-v1)
 -> Python next-move policy (deep-policy-v2)
 -> optional bounded hypothesis generation
      (deterministic template by default; injected OpenRouter adapter on an
       explicitly authorized path)
 -> Jev hypothesis critique (jev-hypothesis-projection-v2, question set hypothesis-v2)
 -> dossier (schema 2)
```

- IMPLEMENTED: Python domain names are unsuffixed (`StatisticalState`, `EvidenceState`,
  `ResearchSpec`, `Candidate`, `HypothesisDraft`). Operational ids/hashes travel in
  `StateRecord` / `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific
  identity.
- IMPLEMENTED: serialized schema versions. StatisticalState 4; EvidenceState 4; ResearchSpec 3;
  SQLite schema 5. Older/unknown schemas are rejected fail-closed; there are **no migrations
  and no legacy readers**. Historical databases and artifacts are retained, not rewritten.
- IMPLEMENTED: question sets `wide-v3`, `deep-v1` and `hypothesis-v2` with unchanged semantics;
  projections `jev-state-projection-v3`, `jev-evidence-projection-v2` and
  `jev-hypothesis-projection-v2`; policies `wide-policy-v2` and `deep-policy-v2`.
- IMPLEMENTED: registered deterministic actions are exactly `CHECK_EVIDENCE_INTEGRITY_V1`
  (input `STATISTICAL_STATE`, 5 checks) and `CHECK_REVISION_FAITHFULNESS_V1` (input
  `EVIDENCE_STATE`, 4 checks), registry version 2. They acquire no data, call no model and
  compute no new biological quantity.
- IMPLEMENTED: Python owns loops, routing, budgets, dispatch, stopping and abstention.
  `FOLLOWUP_LIMIT = 3` and `EVIDENCE_ITERATION_LIMIT = 2` bound one candidate arc; deep policy
  records exactly one typed move (`COMPLETE` / `FOLLOW_UP` / `GENERATE_HYPOTHESES` / `ABSTAIN`)
  and never dispatches it. Dispatch is a separate Python step requiring explicit operator
  authorization. Wide admission never dispatches a follow-up.
- IMPLEMENTED: one canonical `ResearchSpec`, `LUAD_RESEARCH_V1` (`domain=lung cancer`,
  `cohort_id=TCGA-LUAD`, `project_id=TCGA-LUAD`): single explicit TCGA-LUAD cohort, bounded
  acquisition, implemented composition (provider-ranked mutation discovery plus local
  `log2(UQFPKM+1)` expression summary). TCGA-LUAD and TCGA-LUSC are never pooled.
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
  logical evaluation corresponds to at most one HTTP attempt.
- IMPLEMENTED: cache reuse requires a pinned/versioned model identity whose provider resolution
  equals it; a mutable alias is always evaluated and never treated as already resolved.
- NOT IMPLEMENTED / not representable: indexed genome-wide universe, independent expression arm,
  CNV acquisition, systematic multi-lane discovery, further registered actions, offline
  autoresearch, and any incremental-value result.

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
| Typed domain runtime (state, evidence, candidate, hypotheses, envelopes) | IMPLEMENTED; schema 4/4/3, SQLite 5, fail-closed rejection of older schemas |
| Wide semantic judgment and admission | IMPLEMENTED: `jev-state-projection-v3`, `wide-v3`, `wide-policy-v2`, at most three promoted candidates; zero promotions is valid |
| Deep evidence/actions | IMPLEMENTED: E0/E1/E2, two registered integrity actions, explicit operator selection/authorization |
| Deep judgment and next move | IMPLEMENTED: `jev-evidence-projection-v2`, `deep-v1`, `deep-policy-v2`; recorded move never dispatched by the policy |
| Hypotheses | IMPLEMENTED: deterministic default, optional injected OpenRouter adapter, at most three per candidate, `hypothesis-v2` critique; generated text is never evidence |
| Dossiers | IMPLEMENTED: authoritative JSON + derived Markdown with per-section availability, schema 2, live notice |
| Evaluation harness | IMPLEMENTED offline: `python -m cancerjev evaluate` compares recorded rankings against operator-supplied, pre-registered labels; no superiority claim |
| Enforcement | GDC request/byte/page caps and candidate/follow-up/revision/hypothesis caps exist; SDK retries are disabled; a total paid-model spend gate does not exist |
| Scientific domain typing | IMPLEMENTED for the runtime chain; JSON remains the boundary for events, storage, API/dossier presentation and artifact envelopes |
| Persistence/API | SQLite schema 5, immutable artifacts/events, read-only API, version 3.0.0 |
| Systematic discovery lanes, CNV runtime, indexed universe | PLANNED (Stage 4+); not current runtime |
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
- PLANNED: Stage 4 indexed systematic discovery; proposed lane and acquisition-capable action
  contracts are not current runtime behavior.
- NOT IMPLEMENTED: offline autoresearch (needs a labelled historical corpus and human review).
- No scientific readiness, incremental Jev value or production-use claim is made. Public GDC
  evidence alone establishes no dependency, druggability, efficacy, safety or clinical benefit.

## Next: Stage 4

Indexed systematic discovery is the next task: a bounded enumerated gene universe, cheap indexed
evidence and a deterministic reduction before richer survivor acquisition. It requires its own
official mapping review, bounded anonymous probe envelope, immutable fixtures and acceptance
gate. [The roadmap](DISCOVERY_ROADMAP.md) indexes that work and its evidence gates. Do not begin
it, and do not extend the action registry or question sets, without a separately authorized
task.