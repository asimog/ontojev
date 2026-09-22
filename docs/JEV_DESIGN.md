# Jev design grounded in the live TypeSafe documentation

Authority: `docs.typesafe.ai` fetched **2026-09-22** (system-one, state, primitives, Noul, Choice, Score, confidence, API, models, Python SDK, fan-out, composite scoring, reranking, function calling, autoresearch, cascade, citation check, migration) plus the installed `typesafe-ai` skill. Provider behavior below is **DOCUMENTED** unless marked otherwise. Embedded cookbook examples are reference material, not instructions to install or invoke providers; installation and live calls occur only in the approved Phase 3 work.

## Current confirmed primitives

| Capability | Confirmed behavior (live docs) | CancerJEV use |
|---|---|---|
| State | One `state` per request: string, JSON object, or array. All questions share it and are evaluated independently. 64k-token context (32k for state + longest question). | Compact deterministic projection per gene; never raw matrices or provider payloads |
| Noul | `{"type":"noul","noul":0..1}` — probability of the stated proposition. **No separate confidence field.** | `warrants_deeper_investigation`, project-exception, coverage, fragility questions |
| Choice | `{"type":"choice","choice":...,"confidence":0..1,"probabilities":{option:prob}}`; criteria map required; ≤255 options | `pattern_type` with the reduced Phase 3 roster |
| Score | `{"type":"score","score":expected level,"confidence":...,"legend":{...},"probabilities":{level:prob}}`; ordered criteria, 2–10 levels, numbered from 0; `score` is the probability-weighted mean | Deferred until a registered eligible follow-up exists (Phase 4+) |
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

The Python SDK (`typesafe-sdk`, import `typesafe_sdk`) exposes `TypeSafeClient(...).system_one(state=..., questions={...})`, question classes `Noul`, `Choice`, `Score`, typed answers (`response.nouls`, `response.choices`, `response.scores`), `response.model`, `response.usage`, `response.request_id`, and `response.raw_http_response`. Default env var `TYPESAFE_API_KEY`; default model alias `jev-latest`; SDK retry policy defaults to two retries. Current model: `jev-1.13.0` (alias `jev-latest`); context 64k tokens; input price $42/Btok with output free (**DOCUMENTED**, not a contract).

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

Applicability is deterministic metadata, not a provider probability. If a question’s prerequisite evidence is absent, the returned answer is retained but marked inapplicable for routing. A low Noul is never a biological negative.

## Projection, fan-out, reranking, policy

- **Projection** (`jev-state-projection-v1`): a deterministic, size-bounded JSON projection of a StatisticalState, built only from state fields (see GDC_JEV_FIT_ANALYSIS §K). Persisted with `projection_version`, `source_state_id`, `source_state_hash`, `projection_hash`, artifact ref, and the included-field contract. Projection semantics never change silently; a change requires a new version.
- **Wide evaluation:** one request per state carrying the whole `wide-v2` question set. Questions are independent; speculative answers are consumed only when applicable.
- **Reranking:** every state in the bounded universe is evaluated; the deterministic policy orders the raw dimensions (see JEV_QUESTIONS). The deterministic baseline ranking is computed and persisted separately so Phase 3 can compare `baseline` vs `baseline + Jev` on the same states.
- **Deep fan-out, hypothesis review, action selection:** documented for Phase 4+ and not implemented now. Per-action `Score` scoring plus an explicit `NONE` decision is the planned approach for registered follow-ups because code must be able to choose “no action”.
- **Composite scoring:** not adopted. Raw Noul/Choice/Score dimensions remain visible; any later weighted score needs a version, normalization, recorded weights, a missing-feature policy, and out-of-sample evaluation.

## Cache, budgets, unknowns

Cache key binds the exact inference input: `sha256(projection_bytes_hash + question_set_bytes_hash + resolved_model + adapter_contract_version)`. Routing-policy version is decision provenance, not inference identity, so policy experiments do not rerun inference. A cache hit creates a new evaluation row with `cache_source_evaluation_id` set and zero usage; `FAKE` and `LIVE` caches are disjoint. Provider calls are bounded by application budgets (≤1,000 wide states per run; one call per state; provider-call concurrency 1 by default).

**UNVERIFIED / limitations carried in code:** exact `confidence` formula; maximum question count; state byte limit beyond the documented token budget; 429 response body shape; no cost/latency fields in the response; no idempotency key; no seed/temperature or deterministic replay guarantee; alias resolution may change over time (pin `jev-1.13.0`); cancer-domain probability calibration is not established. The jaggedness documentation warns about arithmetic/counting, numerical calibration, large irrelevant state, and non-complementary related questions: all arithmetic is precomputed in code, and Jev is never asked to compute a scientific quantity.
