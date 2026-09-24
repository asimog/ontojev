# Stage 3 — typed lane composition and consumer handoffs

IMPLEMENTED and offline-verified, 2026-09-25. Starting HEAD:
`7f13f611c89fe2db190ecd2f798f68aa4f2b0871` on `main` (Stage 2 published).
This is the second requested continuation stage. Stop here; discovery is not implemented.

## Implemented flow

```text
bounded GDC transport -> existing strict provider parsers
 -> common cohort / mutation counts / expression acquisition
 -> MutationObservation + ExpressionObservation / Log2Summary
 -> ProjectEvidence + StateSummary + immutable v2 serialization
 -> typed Wide projection -> validated typed answers -> unchanged Python admission
 -> verified legacy candidate source -> typed integrity checks / immutable revision
 -> typed Deep answers + CheckSummary -> unchanged next-move policy
```

- `research/acquisition.py`: concrete cohort pagination, mutation-count/coverage acquisition,
  expression batching and common-frame composition. Selection policy stays in research/live;
  endpoint contracts and absolute caps stay in GDC. AcquisitionTransport is one narrow request seam.
- `science/mutation.py`, `science/expression.py`: existing arithmetic and missingness semantics
  return frozen lane records before serialization. ProviderGene summaries remain separate from
  local Log2Summary. Batch medians/SDs are never combined into cohort statistics.
- `science/methods.py`: composes typed lane results, ProjectEvidence and typed state summaries.
  Cross-lane sufficiency/count/median calculations use typed results rather than extracting their
  own serialized metrics. The method registry, versions, units and arithmetic are unchanged.
- `domain/state_summary.py`: immutable ProjectSummary, StateSummary and ComputedStatisticalState
  retain the fields consumed by current Wide projection/admission. Serialized legacy bytes are an
  archival boundary, not a new v3 artifact. `build_statistical_state` remains a compatibility writer;
  live execution uses `compute_statistical_state` and retains its typed result through Wide.
- `domain/actions.py`, `science/actions.py`, `research/deep.py`: immutable IntegrityCheck and
  ComputedEvidenceRevision carry check outcomes through E1/E2 and derive CheckSummary. FollowUpResult
  checks revision/action/hash/count bindings. CandidateEvidence retains the validated LegacyArtifact,
  not a mutable state dictionary. Unsupported v3 execution fails explicitly in this still-v2 runtime.
- `jev/contracts.py`, `jev/service.py`: EvaluationRecord retains ValidatedAnswers and typed
  applicability through provider/cache handling and policy. Successful validation is not repeated
  merely to pass answers between internal functions. Legacy JSON-returning service entrypoints remain.
- `research/ranking.py`, `nextmove.py`, `wide.py`, `investigation.py`: typed state/answer/check
  consumers with unchanged admission, action authorization, caps, stopping and event ordering.
- `research/seams.py`: a result-preserving StageRunner callback and declared artifact-publisher /
  untrusted generator signatures. Existing Repository, ArtifactStore and JevService dependencies
  are named directly; no dependency-injection framework or second execution engine.

## Deliberately retained boundaries and limits

This is a v2-compatible transition, **not a fully v3 production runtime**. Stage 1 v3 contracts and
readers remain standalone. Historical v1/v2 bytes and identities are not rewritten or relabelled.
SQLite remains schema 4. Projection/question/policy versions remain unchanged, including wide-v3,
deep-v1, hypothesis-v2 and mutation-required wide-policy-v2.

JSON remains for events, storage, API/dossier presentation, generated-text requests, legacy
projection/replay adapters and artifact provenance envelopes. The two existing integrity actions
intentionally inspect serialized records and retained bytes: fidelity of that representation is
their actual subject. Their diagnostic payloads and prerequisite descriptions remain boundary
dictionaries, not new biological measurements. Hypothesis templates and historical projection
serializers still format validated v2 records; they are not new typed scientific computations.
Existing provider identifier maps and ProjectFrame are retained; no parser/Repository split.

One documented failure is corrected: when expression availability is wholly unacquired, the
aggregate is now `value=None, availability=NOT_OBSERVED`, not the invalid zero/unavailable pair.
Previously that pair raised INVALID_METRIC; there is no claim of previously published false-zero
science. The metric guard and historical reader still reject malformed unavailable-with-value data.
Valid existing measurement, identity, projection and policy goldens are unchanged.

## Verification

- Focused replay/goldens: 25 passed; revised historical reader and typed-flow tests: 40 passed.
- New lane tests: 18 cases, including independent mutation/expression/provider presence, missing
  availability, explicit mutation zero versus absent bucket, row/batch permutation, boundary-copy
  isolation and typed/legacy projection equality. Reordered trusted rows preserve identity; changed
  retained response hashes appropriately change source identity without changing numeric results.
- Typed-flow tests cover cache hydration without a second adapter call, typed/legacy ranking bytes,
  immutable answers, revision bindings and check-summary disagreement.
- Full offline gate: **547 passed, 2 deselected**, 96.46 seconds. Ruff passed. Strict mypy passed
  on **19 explicit modules**; scope expanded to new domain/lane/acquisition/policy/seam modules.
  This is not whole-repository static checking; no blanket ignores were added.
- Historical v1/v2 hashes, canonical Wide projection hash, all current question-set hashes,
  fixture event sequence, live replay ordering, Deep E0/E1/E2, hypothesis/dossier, cache refusal,
  SQLite transactions and corruption tests pass. Existing pytest-asyncio deprecation and Windows
  pytest-current cleanup warnings remain; test process exits successfully.

Commands: `python -m ruff check cancerjev apps/api tests`, `python -m pytest`,
`.venv/Scripts/python -m mypy`, `git diff --check`; 67 local links across 12 changed documents checked.
The virtual environment supplies the already-authorized development-only mypy dependency.

No new scientific API/provider calls, paid models, public captures or live discovery acceptance.
No dependency changes in this stage, frontend changes, pipeline installation or global plugin edits.
The NGS skills informed assay/missingness/provider-summary distinctions; TypeSafe guidance informed
typed answers and deterministic policy. Neither supplied scientific evidence or acquisition authority.

## Commit, chat and timing handoff verification

Rechecked on 2026-09-25 after the implementation chat was supplied for verification:

- The chat's three publication claims match Git history in order: Stage 0–1 is
  `63d991a6ded2988bc6da0090f80ee69775cf770d`, Stage 2 is
  `7f13f611c89fe2db190ecd2f798f68aa4f2b0871`, and Stage 3 is
  `756becacbbc35d7d361a55165a3a59fa3e332a3c`.
- Local `main`, remote-tracking `origin/main`, `origin/HEAD`, and GitHub's queried
  `refs/heads/main` all resolved to the Stage 3 commit before this documentation handoff.
- A fresh `python -m pytest --durations=30` run on local Python 3.14.3 completed with
  **547 passed, 2 deselected, 1 warning in 109.80 seconds**. Live GDC, Jev and provider tests were
  excluded by the default markers; outbound non-loopback network is blocked by the test fixtures.
- The run was slow, not hung. The suite repeatedly creates temporary SQLite databases and artifact
  stores and executes full replay, cache, API, corruption, Deep and hypothesis paths. The slowest
  individual test took 3.54 seconds, so most wall time is distributed across the large offline suite.
  For about the first 30 seconds a delegated diagnostic accidentally ran a second pytest process;
  that process was stopped, so 109.80 seconds is not a clean regression comparison with 96.46 seconds.
- Browser acceptance is a separate sequential gate. One real-time UI scenario requests a 2.5-second
  delay for each fixture stage and Playwright is configured for one worker; that intentional pacing is
  independent of the offline Python result above.
- At the user's stop request, no pytest run remained and two dormant Playwright `test-server`
  helpers were stopped. No further test was started for this documentation-only handoff.

## Next authorized unit must be explicit

Stage 4 is PLANNED: bounded ordered universe and indexed mutation reduction, with its own official
mapping review, minimal anonymous probe envelope, immutable fixtures and acceptance gate. No broad
discovery, independent expression arm, CNV acquisition, new action or default cutover is included here.
Stages 5–7 and the labelled prospective-corpus requirement remain as in the
[roadmap](DISCOVERY_ROADMAP.md). Passing these engineering gates does not establish scientific Jev value.
