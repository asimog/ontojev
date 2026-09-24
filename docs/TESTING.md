# Verification and prospective calibration

Stage 2 adds `test_scientific_reads.py`, `test_cache_validation.py` and
`test_hypothesis_contract.py`: corrupted bytes/metadata/bindings, unknown schemas, authoritative
latest revision refusal, unusable cache without provider fallback, and strict generated-text bounds.
Some tests deliberately disable immutable UPDATE triggers in isolated temporary databases to
simulate corruption beyond normal application writes. Production triggers remain unchanged.
Strict mypy now checks ten explicit domain/reader/answer modules. See [Stage 2](STAGE_02_HANDOFF.md).

Architecture baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`.
Default tests are offline, with outbound network blocked except loopback test servers. Existing
coverage uses replay GDC, stub Jev adapters, real temporary SQLite/artifacts, immutable event/identity
tests and strict malformed-provider cases. Stage 0–1 implementation at
`fb52305b3d42a39b05f6c269bbfa3d6213fd51d2` adds the verification described below.

## Stage 0–1 contract verification (IMPLEMENTED)

New offline tests:

- `tests/test_scientific_baseline.py`: fixed v1/v2 scientific hashes, canonical projection byte hash,
  Wide/Deep/hypothesis question hashes and the 71-event fixture type/stage ordering hash.
- `tests/unit/test_scientific_contracts.py`: invalid numeric/status/unit variants, immutable nested
  fields, entity/population binding, coverage accounting, minimum summary n, revision/check counts,
  v3 round trips, strict composition and operational/scientific identity separation.
- `tests/unit/test_versioned_readers.py`: all 12 v1 fixture patterns and revisions, v2 records,
  malformed schemas/values/populations, and offline v2 E0/E1/E2 replay with explicit event ordering.
  Existing fixture/replay helpers supply synthetic data; no public response is newly imported.

Run focused tests before the full suite. Python CI now also runs `python -m mypy`, configured in
pyproject.toml for seven explicit files: domain measurements/scientific/evidence/_json/codecs/
legacy_codecs and research/specs. Strict checking applies to that scope; `follow_imports = "silent"`
retains imported signatures without turning this into a whole-repository typing campaign. There are
no blanket ignore flags or new type assertions. Expand the checked file list when consumers transition.
Configuration follows the [official mypy guidance](https://mypy.readthedocs.io/en/stable/config_file.html).

The [Stage 0–1 handoff](STAGE_01_HANDOFF.md) records exact environment, commands and outcomes.
Storage checksum/binding, dossier/cache/hypothesis hardening and typed runtime lane tests remain
Stage 2/3 work. A standalone codec passing tests is not proof that every current consumer uses it.

## Historical verification available at the architecture baseline

The supplied audit at this SHA reports Ruff passed and pytest reached 100% with exit 0; pytest emitted
an ignored Windows temporary-directory cleanup PermissionError. This pass reuses that verification,
not a claim of newly running the full suite. It additionally exercised the null-observed metric and
empty-revision dossier paths offline, and ran existing count/expression parsers against the campaign:
ten count batches complete, twelve expression captures accepted with missingness retained.
See [Python review](PYTHON_CORE_REVIEW.md).

Relevant current tests: tests/contracts/test_parsers.py, tests/science/test_methods.py,
tests/science/test_actions.py, tests/science/test_nextmove.py, tests/jev/test_service.py,
tests/jev/test_evidence_projection.py, tests/integration/test_live_replay.py,
tests/integration/test_deep_slice.py, tests/integration/test_hypothesis_stage.py,
tests/test_persistence_guards.py and tests/llm/test_openrouter_adapter.py.
At that historical baseline CI ran Ruff/pytest only. The current scoped static gate is described above.

## PLANNED contract acceptance

| Change | Required focused verification |
|---|---|
| Measurement variants | Reject observed-null, bool counts, nonfinite, negative counts, unknown units/status, unavailable-with-value; genuine observed zero survives |
| Lane composition | Required frame/universe/method refs; disabled/missing/partial distinct; row order invariant; no semantic output in measurements |
| Versioned hydration | v1 fixture/v2 live preserved; v3 explicit; malformed/unknown versions typed failures; original hashes unchanged |
| Dossier hardening | Missing/truncated/wrong-hash/invalid revision cannot publish OBSERVED sections; valid earlier revision must not silently substitute for corrupt latest |
| Cached evaluations | Validate original roster/primitive/distribution/model/projection/version before reuse; invalid cache cannot influence admission |
| CNV parser | Requested ID membership, correct project/gene, paging/duplicates, Loss in five-category field, unknown label, missing sample ID, mixed/conflicting callers |
| Expression | Omitted rows/columns, multiple batches, duplicate case/sample relationships, n<2 SD, zero MAD/IQR, no aggregate provider batch summaries |
| Actions | Typed input kind, estimator eligibility, no failure promotion, deterministic results/identity, budget reserved before acquisition, authorized dispatch only |
| Seams | Injected narrow clients, offline replay, provider errors contained; no global SDK replacement needed for new tests |
| Static gate | Incremental type check of new domain/codecs/lanes and consumers, alongside Ruff/pytest; tool/dependency choice belongs to implementation |
| Resource accounting | Each provider HTTP attempt counted including SDK retries/timeouts; token/spend unknown preserved; no cap reset by repartition/restart |
| Identity | Operational IDs/times do not change science; population/method/units/universe changes do; semantic features never enter measured identity |

Keep fixture and live records separate. New public captures need immutable fixtures plus synthetic
malformed variants before endpoint admission. Tests must not call providers by default, weaken
scientific assertions, or infer correctness from HTTP 200. A later live acceptance requires explicit
authorization and frozen resource envelope; no paid calls are part of this pass.

## PLANNED prospective Jev incremental-value protocol

Objective: does a semantic stage improve *reviewable bounded research decisions* over deterministic
selection at matched workload, without increasing unsupported claims? This is not a clinical or
biological target-validation study. Existing evaluation.py reports overlap/label hits; it does not
implement this protocol or establish superiority.

### Corpus and labels

Freeze cohort release, candidate universe, acquisition manifest, deterministic methods and exact
candidate evidence before generating labels. Include rejected, missing, partial and no-signal cases,
not only promoted candidates. Keep a mutation-ranked historical comparator and the broad-slice arm
separate. Primary review unit is gene/evidence context; all revisions, duplicate profiles and
hypotheses of one gene stay together. Labels:

- Scientific input eligibility: readable, correctly scoped, adequate for the declared descriptive task.
- Material unresolved question: a named uncertainty not settled by supplied facts.
- Follow-up usefulness: an eligible bounded action could distinguish named interpretations.
- Unsupported assertion: numerical, population, mechanistic, causal or clinical overclaim.
- Disposition: investigate / stop / abstain / external evidence required, with written rationale.
- Hypothesis review: testable within declared evidence/action scope versus unsupported or ambiguous.

Two independent qualified reviewers see identical anonymized evidence and declared action contracts,
without method name, candidate rank, model answers or historical “known target” label. Adjudicate
disagreements with a third reviewer; retain raw labels, uncertainty, agreement and reasons.
Blinding cannot hide all recognizable biology; record that limitation. Known biology may inform
external evaluation strata/labels, never production selection features or a handpicked success set.

### Splits and leakage control

Pre-register approximately 60/20/20 train/development/held-out groups using deterministic seeded
assignment by gene family/related context where available; all same-gene revisions share a group.
Related genes/shared acquisition blocks must not be scattered merely to inflate sample count.
Freeze group assignments before prompt/policy tuning. Overlapping patients in a single LUAD cohort
limit independence: this evaluates decision support on this evidence, not independent patient-level
replication. Reserve a later external cohort/time-release evaluation for generalization claims.

Choose corpus size with reviewers and a precision/power calculation before evaluation; a small
pilot may test annotation feasibility but is not a powered value result. No fixed minimum case count
is evidence of inferential power. Held-out labels and errors are unavailable to question/feature
generation or iterative autoresearch; one locked final evaluation, then a new holdout for further tuning.

### Arms and ablations

| Arm | Purpose |
|---|---|
| A: current deterministic mutation-count baseline | Historical policy comparator, same accepted inputs |
| B: broad universe + deterministic lane/discovery features | Value of acquisition/feature change without Jev |
| C: B + optional separately stored semantic features/reranking | Incremental semantic ranking value |
| D: C + versioned Wide admission | Incremental admission/abstention value |
| E: D + current or separately versioned Deep judgment | Follow-up selection/stopping quality |
| F: full workflow with explicit uncertainty abstention | Coverage versus error tradeoff |

Evaluate current wide-v3/deep-v1 separately from proposed sets. Do not change acquisition and attribute
all improvement to Jev. Compare same universe, evidence access, maximum promotions, reviewer effort
and provider budget. Ablate each question, feature family, semantic stage, thresholds, optional
composite weights and hypothesis generation. Keep an always-stop and deterministic-eligibility-only
control to detect pointless follow-ups.

### Metrics and gates

Pre-register primary precision@3 for adjudicated useful investigations plus coverage/abstention.
Report recall within the labelled declared universe, shortlist recall, nDCG for ordinal usefulness,
unsupported-claim rate, wrong-population/matching errors, action utility, human minutes, calls/tokens,
actual/unknown spend and end-to-end latency p50/p95. Report paired differences with grouped bootstrap
confidence intervals and denominators. Correlated gene/patient evidence limits those intervals;
document grouping and sensitivity, not independent-observation fiction.

For labelled binary Noul propositions report Brier score/reliability curves; for Choice report
confusion and distribution calibration. Score expected level uses ordinal agreement, not a false
binary-probability interpretation. Measure risk-coverage curves and threshold-near repeat variability.
Service failures, unavailable inputs and schema failures are separate from model errors and count in
workflow coverage. Do not drop abstentions or failures from denominators.

Error taxonomy: acquisition incomplete; wrong entity/population/sample; parser/codec corruption;
deterministic method error; missingness misread; unsupported biological assertion; semantic
misclassification; uncalibrated policy; provider outage/retry accounting; reviewer disagreement.

Release gate: reviewers approve the protocol and safety tolerance before unblinding; demonstrate a
pre-specified useful paired improvement or non-inferiority/resource benefit with uncertainty, while
meeting the unsupported-claim tolerance. Otherwise retain baseline/experimental labeling or disable
the semantic stage. Changed rankings, cookbook accuracy, one plausible hypothesis or a low dollar
estimate are not incremental value. Clinical claims always require separate external validation.
