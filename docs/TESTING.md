# Verification and prospective calibration

Current verification contract after the Stage 3 hard cutover (2026-09-25). Claims are labeled
IMPLEMENTED, PLANNED or UNVERIFIED.

## IMPLEMENTED: default gates

| Gate | Command | Scope |
|---|---|---|
| Python lint | `python -m ruff check cancerjev apps tests` | Whole Python tree |
| Offline suite | `python -m pytest` | `tests/`; live markers excluded by `pyproject.toml` `addopts` |
| Static check | `python -m mypy` | Scoped strict check over the explicit `[tool.mypy] files` list in `pyproject.toml` (28 modules); `follow_imports = "silent"`; not whole-repository typing |
| Whitespace | `git diff --check` | Changed files only |

- Default tests are offline and must not contact GDC, TypeSafe/Jev, OpenRouter or any LLM. The
  shared test fixture blocks outbound non-loopback network connections except loopback test
  servers. No default test needs Docker, PostgreSQL, Redis, provider credentials or secrets.
- In this environment (2026-09-25): **652 offline pytest tests pass** (live opt-in markers
  excluded); Ruff is clean; the scoped strict mypy check passes. These are the current verified
  Python results.
- Fixture runs use the same shared `LiveOrchestrator` with `FixtureTransport` and
  `FixtureJevAdapter`; a browser scenario deliberately uses 2.5-second fixture-stage delays to
  make progress observable, so browser timing is independent of the Python suite.
- Tests may deliberately damage temporary SQLite databases beyond normal immutable triggers to
  simulate corruption; production triggers are unchanged.

## Opt-in provider checks — live acceptance PASSED (2026-09-25)

`tests/live` contains opt-in acceptance code; markers are `live`, `live_gdc`, `live_jev`,
`live_llm` and `live_acceptance`. They are excluded from ordinary pytest and CI.

- `python -m pytest -m live_acceptance` first ran one fresh bounded LUAD sweep with real GDC
  (16 attempts, 367,862 bytes, zero cache hits) and real `wide-v3` judgments against
  `jev-1.13.0` (10 states; one provider answer set failed strict validation and was recorded
  fail-closed as `INVALID_DISTRIBUTION`). `wide-policy-v2` recorded its natural ABSTAIN.
- The operator then explicitly selected the baseline top gene and authorized one follow-up over
  the retained cache: 16/16 GDC cache hits, an E0→E1 revision from `CHECK_EVIDENCE_INTEGRITY_V1`,
  one real `deep-v1` judgment and a ready dossier.
- A separately labelled check used exactly one OpenRouter request
  (`deepseek/deepseek-v4.1-flash`, 316 input / 3,501 output tokens) and 2 of at most 3
  `hypothesis-v2` critiques, all resolved as `jev-1.13.0`; it appended nothing to the run.
- Replay then ran with sockets refused: 16/16 cache hits, no new Jev calls, identical state
  hashes. The combined check used 14 of at most 15 Jev attempts and one LLM attempt; no policy
  threshold was changed and no result was retried.

Missing credentials skip these tests before any acquisition or provider call (`TYPESAFE_API_KEY`,
`OPENROUTER_API_KEY`, a pinned `CANCERJEV_JEV_MODEL`, optionally `CANCERJEV_LLM_MODEL` from
`.env.local` or the process environment; never put keys in commands or reports). Acceptance
reports live under `acceptance/` in the test store, identify themselves as integration test
results, and retain exact projections, question hashes, usage and resolved Jev identity;
provider error bodies are omitted.

**Still UNVERIFIED:** model reproducibility (no seed or temperature control; one live answer set
failed validation), OpenRouter immutable-model resolution (the adapter checks only non-blank
identity; tightening is PLANNED), and any incremental Jev value. The harness does not establish
scientific readiness or production use.

## Browser acceptance — IMPLEMENTED, UNVERIFIED here

Current browser acceptance lives in `tests/browser/` with its own Playwright configuration and
`package.json` (for example `current.spec.ts`). CI runs it as a separate job: it boots the API
and the web app on loopback, waits for `/health` and `/runs`, then runs `npx playwright test`
with `CANCERJEV_WEB_URL`. **It was not executed in this environment: UNVERIFIED.** It is not a
substitute for the Python offline suite and vice versa.

## IMPLEMENTED coverage highlights

- Fixed historical scientific goldens: state/evidence hashes, canonical projection bytes, all
  current question-set hashes and the fixture event type/order hash.
- Typed contracts: invalid numeric/status/unit variants, immutable nested fields,
  entity/population binding, coverage accounting, minimum summary n, revision/check counts,
  strict composition and operational/scientific identity separation.
- Versioned readers: schema-4 state/evidence round trips and Versioned research-spec readers,
  malformed schemas/values/populations, corruption refusal and offline E0/E1/E2 replay with
  explicit event ordering.
- Lane composition and typed flow: independent lane availability, explicit zero versus absent
  bucket, row/batch permutation invariance, provider-summary separation, typed/legacy projection
  equality, typed cache reuse, revision binding and check-summary consistency.
- Storage/cache/dossier hardening: corrupted bytes/metadata/bindings, unknown schemas,
  authoritative-latest refusal (no earlier-revision fallback), unusable cache without provider
  fallback, and strict generated-text bounds (unknown fields and unknown action IDs rejected).
- Provider containment: malformed provider responses become typed persisted failures, a failed
  GDC attempt always reaches a terminal ledger status, and cache identity respects pinned model
  resolution.
- Open-access guards: no authentication literals outside the single allow-listed OpenRouter
  module; `/data`, `/manifest` and `/slicing` are not routable; file metadata requests always
  carry `access=open`; a controlled or access-missing record fails closed; 401/403 become
  `UNAVAILABLE_ACCESS` with no retry or credential lookup.

## PLANNED: prospective Jev incremental-value protocol

Objective: does a semantic stage improve *reviewable bounded research decisions* over
deterministic selection at matched workload, without increasing unsupported claims? This is not a
clinical or biological target-validation study. `python -m cancerjev evaluate` reports overlap
and labelled hits against operator-supplied labels; it does not implement this protocol or
establish superiority.

### Corpus and labels

Freeze cohort release, candidate universe, acquisition manifest, deterministic methods and exact
candidate evidence before generating labels. Include rejected, missing, partial and no-signal
cases, not only promoted candidates. Keep a mutation-ranked historical comparator and the
broad-slice arm separate. Primary review unit is gene/evidence context; all revisions, duplicate
profiles and hypotheses of one gene stay together. Labels:

- Scientific input eligibility: readable, correctly scoped, adequate for the declared descriptive
  task.
- Material unresolved question: a named uncertainty not settled by supplied facts.
- Follow-up usefulness: an eligible bounded action could distinguish named interpretations.
- Unsupported assertion: numerical, population, mechanistic, causal or clinical overclaim.
- Disposition: investigate / stop / abstain / external evidence required, with written rationale.
- Hypothesis review: testable within declared evidence/action scope versus unsupported or
  ambiguous.

Two independent qualified reviewers see identical anonymized evidence and declared action
contracts, without method name, candidate rank, model answers or historical “known target” label.
Adjudicate disagreements with a third reviewer; retain raw labels, uncertainty, agreement and
reasons. Blinding cannot hide all recognizable biology; record that limitation. Known biology may
inform external evaluation strata/labels, never production selection features or a handpicked
success set.

### Splits and leakage control

Pre-register approximately 60/20/20 train/development/held-out groups using deterministic seeded
assignment by gene family/related context where available; all same-gene revisions share a group.
Related genes/shared acquisition blocks must not be scattered merely to inflate sample count.
Freeze group assignments before prompt/policy tuning. Overlapping patients in a single LUAD
cohort limit independence: this evaluates decision support on this evidence, not independent
patient-level replication. Reserve a later external cohort/time-release evaluation for
generalization claims.

Choose corpus size with reviewers and a precision/power calculation before evaluation; a small
pilot may test annotation feasibility but is not a powered value result. No fixed minimum case
count is evidence of inferential power. Held-out labels and errors are unavailable to
question/feature generation or iterative autoresearch; one locked final evaluation, then a new
holdout for further tuning.

### Arms and ablations

| Arm | Purpose |
|---|---|
| A: current deterministic mutation-count baseline | Historical policy comparator, same accepted inputs |
| B: broad universe + deterministic lane/discovery features | Value of acquisition/feature change without Jev |
| C: B + optional separately stored semantic features/reranking | Incremental semantic ranking value |
| D: C + versioned Wide admission | Incremental admission/abstention value |
| E: D + current or separately versioned Deep judgment | Follow-up selection/stopping quality |
| F: full workflow with explicit uncertainty abstention | Coverage versus error tradeoff |

Evaluate current `wide-v3`/`deep-v1` separately from proposed sets. Do not change acquisition and
attribute all improvement to Jev. Compare same universe, evidence access, maximum promotions,
reviewer effort and provider budget. Ablate each question, feature family, semantic stage,
thresholds, optional composite weights and hypothesis generation. Keep an always-stop and
deterministic-eligibility-only control to detect pointless follow-ups.

### Metrics and gates

Pre-register primary precision@3 for adjudicated useful investigations plus coverage/abstention.
Report recall within the labelled declared universe, shortlist recall, nDCG for ordinal
usefulness, unsupported-claim rate, wrong-population/matching errors, action utility, human
minutes, calls/tokens, actual/unknown spend and end-to-end latency p50/p95. Report paired
differences with grouped bootstrap confidence intervals and denominators. Correlated
gene/patient evidence limits those intervals; document grouping and sensitivity, not
independent-observation fiction.

For labelled binary Noul propositions report Brier score/reliability curves; for Choice report
confusion and distribution calibration. Score expected level uses ordinal agreement, not a false
binary-probability interpretation. Measure risk-coverage curves and threshold-near repeat
variability. Service failures, unavailable inputs and schema failures are separate from model
errors and count in workflow coverage. Do not drop abstentions or failures from denominators.

Error taxonomy: acquisition incomplete; wrong entity/population/sample; parser/codec corruption;
deterministic method error; missingness misread; unsupported biological assertion; semantic
misclassification; uncalibrated policy; provider outage/retry accounting; reviewer disagreement.

Release gate: reviewers approve the protocol and safety tolerance before unblinding; demonstrate
a pre-specified useful paired improvement or non-inferiority/resource benefit with uncertainty,
while meeting the unsupported-claim tolerance. Otherwise retain baseline/experimental labeling or
disable the semantic stage. Changed rankings, cookbook accuracy, one plausible hypothesis or a
low dollar estimate are not incremental value. Clinical claims always require separate external
validation.

## PLANNED contract acceptance for future work

| Change | Required focused verification |
|---|---|
| Broad-universe lane | Unique IDs/totals/page guards; absence not zero; all selection/rejection reasons retained; within existing request/byte caps |
| Expression arm | Complete declared population/missingness; not tumor-normal/causal; no sample-matching claim; lane-specific recall/coverage |
| CNV lane | Requested ID membership, correct project/gene, paging/duplicates, Loss in the five-category field, unknown label, missing sample ID, mixed/conflicting callers |
| New actions | Typed input kind, estimator eligibility, no failure promotion, deterministic results/identity, budget reserved before acquisition, authorized dispatch only |
| Strict cursor/API | Decoded scalar type/length validation; undeclared-parameter rejection; OpenAPI metadata cleanup |
| Resource accounting | Each provider HTTP attempt counted including timeouts; token/spend unknown preserved; no cap reset by repartition/restart; explicit spend gate |
| Identity | Operational IDs/times never change science; population/method/units/universe changes do; semantic features never enter measured identity |

Keep fixture and live records separate. New public captures need immutable fixtures plus synthetic
malformed variants before endpoint admission. Tests must not call providers by default, weaken
scientific assertions, or infer correctness from HTTP 200. Live acceptance requires explicit
authorization and a frozen resource envelope.