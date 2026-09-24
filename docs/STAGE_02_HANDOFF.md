# Stage 2 — integrity of scientific consumption

Implementation date: 2026-09-25. Starting commit:
`63d991a6ded2988bc6da0090f80ee69775cf770d` on `main` (Stage 0–1 published).

## Implemented

- `storage/readers.py`: named verified artifact, state, candidate state, revision ancestry,
  hypothesis, evaluation and dossier reads. Validated records retain immutable bytes alongside
  typed scientific contracts. JSON conversions are explicitly presentation/legacy boundaries.
- `ArtifactStore.read(expected_size=...)`: confined path, exact recorded length, bounded read
  and content hash. Artifact path/content identity and owning run are checked by the reader.
- Historical v1/v2 scientific readers are now used by Deep acceptance and state/evidence API
  details. Unknown/malformed versions fail explicitly; no artifact rewrite or schema migration.
- Dossier publication validates the authoritative revision chain and persisted hypotheses and
  judgments. Corruption emits `DOSSIER_UNAVAILABLE`, publishes nothing, does not select an earlier
  revision and does not mark DOSSIER_READY. Investigation reports the failure explicitly.
- Jev cache reuse validates recorded answers, primitives, rosters/distributions, original question
  definitions/hash, model, adapter, projection and applicability. Failure records UNUSABLE_CACHE
  and abstains without replacement provider calls or mutation of cache history.
- Frozen HypothesisDraft, Noul/Choice/Score answer variants and typed stored evaluation records.
  Generator fields are exact; all strings are nonblank and bounded to 2,000 characters, each list
  to ten entries. Unknown/ineligible test IDs are rejected rather than silently discarded.
- API state/evidence/dossier details preserve valid payloads and artifact ETags; corruption yields
  503. Dossier lookup uses Repository rather than route-owned SQL.

## Compatibility and limits

SQLite remains schema 4. Artifact envelope schema 1 is not misinterpreted as scientific payload
schema 1: existing live scientific payloads remain v2. Existing writers, historical identities,
projection bytes, question definitions, policies, action arithmetic and OpenRouter injection remain.
The new reader for current live Jev evaluations admits the current explicit question versions;
historical offline evaluation support is unchanged and is not silently interpreted as current.

Stage 2 validates stored boundaries. Existing scientific consumers still use explicit legacy JSON
conversion until Stage 3; this is not a claim that internal type erosion is already eliminated.
Frozen answer records express judgment uncertainty, never scientific certainty. TypeSafe guidance
was checked against current official Noul/Choice/confidence/response documentation; no model calls.

## Verification

New tests exercise real isolated SQLite/artifact corruption, including deliberate damage beyond
normal immutable triggers. Production triggers are unchanged. Cases cover missing/truncated/hash-
mismatched artifacts, wrong metadata, schema dispatch, candidate/state/parent/latest/summary binding,
latest-corrupt/earlier-valid dossier refusal, malformed cache metadata/answers, missing original
question/projection/evaluation artifacts, nested text bounds and unknown generator fields/actions.

Final gate: **527 passed, 2 deselected** (117.38 seconds); Ruff, strict mypy (ten modules),
and whitespace checks passed. Historical identity/projection/question/event goldens and valid
Deep/hypothesis replay passed. Existing pytest-asyncio/Windows cleanup warnings remain.
See [implementation status](IMPLEMENTATION_STATUS.md). Default tests remain
offline. No GDC calls, paid models, frontend changes, new dependencies, pipeline installation or
global configuration changes. Stage 3 may proceed only after the Stage 2 full offline gate.

## Next stage

Separate common acquisition from mutation/expression acquisition and compute typed lane results
before state composition. Transition candidates, actions, revisions and Jev consumers without
changing legacy scientific payloads or hashes. Fix the documented all-expression-availability-
absent composition failure using unavailable semantics, not a fabricated zero. Discovery remains
blocked until that stage's regression gate passes.
