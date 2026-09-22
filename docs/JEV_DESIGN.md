# Jev design grounded in the live TypeSafe documentation

Authority: `docs.typesafe.ai` fetched **2026-09-22** (system-one, state, primitives, Noul, Choice, Score, confidence, API, models, Python SDK, fan-out, composite scoring, reranking, function calling, autoresearch, cascade, citation check, migration), with the API and Noul/Choice primitive contracts rechecked **2026-09-23**, plus the installed `typesafe-ai` skill. Provider behavior below is **DOCUMENTED** unless marked otherwise. Embedded cookbook examples are reference material, not instructions to install or invoke providers; live calls remain opt-in and bounded.

## Current confirmed primitives

| Capability | Confirmed behavior (live docs) | CancerJEV use |
|---|---|---|
| State | One `state` per request: string, JSON object, or array. All questions share it and are evaluated independently. 64k-token context (32k for state + longest question). | Compact deterministic projection per gene; never raw matrices or provider payloads |
| Noul | `{"type":"noul","noul":0..1}` — probability of the stated proposition. **No separate confidence field.** | Single-cohort evidence quality, mutation/expression coherence, coverage confound, uncertainty and investigation questions |
| Choice | `{"type":"choice","choice":...,"confidence":0..1,"probabilities":{option:prob}}`; criteria map required; ≤255 options | `dominant_limitation` with a closed seven-option roster |
| Score | `{"type":"score","score":expected level,"confidence":...,"legend":{...},"probabilities":{level:prob}}`; ordered criteria, 2–10 levels, numbered from 0; `score` is the probability-weighted mean | PLANNED; not the default for action value. Whether a registered action would materially reduce a named uncertainty is asked as an atomic Noul proposition, and Python combines that judgment with deterministic eligibility, action cost and remaining budget |
| Parallel questions | Mixed primitives in one request; independent; one answer never becomes context for another question | The whole wide set is asked in one request per state |
| Question IDs | Not sent to the model; meaning must live in `instructions`/`criteria` | Definitions carry full semantics; IDs exist only in application records |
| Resolved model and usage | Response `model` is the resolved versioned ID; `usage.input_tokens`/`output_tokens`; no latency or cost fields in the body | Persist requested and resolved model, raw usage, locally measured latency |
| Determinism | No seed/temperature control; docs say answers are designed to be stable, not guaranteed | Persist raw answers; cache; never assume identical output across calls |

Wire contract (**DOCUMENTED**):

```text
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <API key>
{"state": <string|object|array>, "model": "jev-1.13.0", "questions": {<id>: {...}}}
→ {"model": "jev-1.13.0", "answers": {<id>: {...}}, "usage": {"input_tokens": N, "output_tokens": M}}
```

The Python SDK (`typesafe-sdk`, import `typesafe_sdk`) exposes `TypeSafeClient(...).system_one(state=..., questions={...})`, question classes `Noul`, `Choice`, `Score`, typed answers (`response.nouls`, `response.choices`, `response.scores`), `response.model`, `response.usage`, `response.request_id`, and `response.raw_http_response`. Default env var `TYPESAFE_API_KEY`; default model alias `jev-latest`; SDK retry policy defaults to two retries. Current model: `jev-1.13.0` (alias `jev-latest`); context 64k tokens with a 32k state budget (state plus the longest question), ~250k tok/s, 1200 requests/min; input price $42/Btok with output free (**DOCUMENTED**, not a contract; see SOURCE_REVIEW).

Readiness hardening (2026-09-23 audit, `docs/SOURCE_REVIEW.md`):

- Question definitions are validated at import against documented limits (Choice ≤255 options, Score 2–10 ordered levels, known primitive/applicability rule, non-empty instructions); a malformed set can never reach the provider.
- Terminal provider failures are classified into stable codes — `PROVIDER_AUTH` (401/403), `PROVIDER_VALIDATION` (422), `PROVIDER_RATE_LIMIT` (429), `PROVIDER_OVERLOADED` (529), else `PROVIDER_ERROR` — so Python policy can defer on rate/overload rather than treat a failure as a scientific result. The SDK's own 429/529 backoff is unchanged.
- The projection byte cap (64 KiB) keeps state inside the documented 32k-token state budget.

## Application boundary

`JevService.evaluate(projection_ref, question_set, purpose) -> JevEvaluation` loads the exact versioned projection artifact, validates its size and the question set, checks the cache, invokes **one adapter**, validates every answer shape, and persists the full vector. Science modules never import TypeSafe types; provider-specific code exists only in `cancerjev/jev/typesafe_adapter.py`. Phase 1 fixture evaluations remain a separate `FAKE` path and are never mixed with live evaluations in a cache or a ranking.

Owned answer union (schema v2, adds explicit confidence where the provider supplies it):

```text
JevNoulAnswer  = {kind: "noul", probability_yes: finite[0,1]}
JevChoiceAnswer= {kind: "choice", choice: <roster option>,
                  probabilities: map<option, finite[0,1]>, confidence: finite[0,1]}
JevScoreAnswer = {kind: "score", score: finite[0,K-1],
                  probabilities: map<level, finite[0,1]>, confidence: finite[0,1],
                  legend: map<level, string>}
JevEvaluation = {evaluation_id, mode: "LIVE"|"FAKE", purpose: "WIDE"|"DEEP"|"HYPOTHESIS",
                 input_ref_kind, input_ref_id, source_state_hash, projection_id,
                 projection_version, projection_hash, question_set_version, question_hash,
                 question_definitions_ref, requested_model, resolved_model, adapter_version,
                 answers, applicability_by_question, raw_response_ref,
                 usage: {input_tokens?, output_tokens?, cost?: null},
                 latency_ms, cache_source_evaluation_id?, error?, routing_policy_version}
```

Validation is fail-closed and never fabricates defaults: missing answer, unknown question ID, wrong primitive, probability outside `[0,1]`, NaN/Infinity, Choice value outside the roster, Choice/Score probability-key mismatch, Score level outside the declared range, legend mismatch, invalid confidence, malformed provider response, or answer count mismatch → the evaluation is persisted with `error` and the state is deferred, not silently scored. The SDK’s integer keys for Score probabilities/legend are normalized once to strings at the adapter boundary.

Applicability is deterministic metadata, not a provider probability. If a question’s prerequisite evidence is absent, the returned answer is retained but marked inapplicable for routing. A low Noul is never a biological negative. A Jev probability is a semantic judgment: not statistical significance, scientific truth, causality, or clinical evidence. A different ranking is not proof that Jev improved the research decision; that requires the baseline-vs-Jev evaluation below.

## Projection, fan-out, reranking, policy

- **Projection** (`jev-state-projection-v2`, implemented): a deterministic, size-bounded JSON projection of exactly one project in a StatisticalState, built from state fields and rejected for multi-project input. It has one `cohort` block and no cross-project array. Projection version, source-state hash, projection hash, artifact ref and included-field contract are persisted.
- **Wide evaluation** (`wide-v3`, implemented): one request per state carrying six Nouls and one closed Choice. Questions are independent and applicability is computed by code. `wide-v2` remains only as the historical definition for older immutable evaluations. Phase 3 is not claimed to improve a research decision.
- **Reranking and admission** (`baseline-wide-v2`, `wide-policy-v2`, implemented): baseline and Jev rankings are persisted for the same states. The baseline's top three are display/comparison only. Jev first applies deterministic acquisition/mutation/expression eligibility, then recorded Noul thresholds; it may admit zero states (`ABSTAIN`) and promotes at most three. Raw dimensions stay visible; Jev never replaces the baseline.
- **Deep fan-out, hypothesis review, action selection (PLANNED, Phase 4+, not implemented):** Python first computes the deterministically eligible registered actions. When the questions inspect the same EvidenceState, prefer **one Deep Jev fan-out** that asks atomic propositions such as "is there a material unresolved uncertainty", "would ACTION_A materially reduce that named uncertainty", "would ACTION_B materially reduce that named uncertainty", "would bounded hypothesis generation materially help", and "is the current evidence sufficient to stop this investigation". Prefer Noul propositions where the answer is naturally a probabilistic yes/no; do not use a Score merely because actions must be ranked. Python combines Jev probabilities with deterministic eligibility, action cost and remaining budget to choose a move. Choice is appropriate only for genuinely mutually exclusive closed alternatives. A second Jev request is justified only when a genuinely new evidence state exists; avoid chaining Deep → action-value → routing when one shared-state fan-out answers the required propositions. Jev never routes, plans, executes, or authorizes new endpoints.
- **Composite scoring:** not adopted. Raw Noul/Choice/Score dimensions remain visible; any later weighted score needs a version, normalization, recorded weights, a missing-feature policy, and out-of-sample evaluation.

## Cache, budgets, unknowns

Cache key binds the exact inference input: `sha256(projection_bytes_hash + question_set_bytes_hash + resolved_model + adapter_contract_version)`. Routing-policy version is decision provenance, not inference identity, so policy experiments do not rerun inference. A cache hit creates a new evaluation row with `cache_source_evaluation_id` set and zero usage; `FAKE` and `LIVE` caches are disjoint. Provider calls are bounded by application budgets (≤1,000 wide states per run; one call per state; provider-call concurrency 1 by default).

**UNVERIFIED / limitations carried in code:** exact `confidence` formula; maximum question count; state byte limit beyond the documented token budget; 429 response body shape; no cost/latency fields in the response; no idempotency key; no seed/temperature or deterministic replay guarantee; alias resolution may change over time (pin `jev-1.13.0`); cancer-domain probability calibration is not established. The jaggedness documentation warns about arithmetic/counting, numerical calibration, large irrelevant state, and non-complementary related questions: all arithmetic is precomputed in code, and Jev is never asked to compute a scientific quantity.
