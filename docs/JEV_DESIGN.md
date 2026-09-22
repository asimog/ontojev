# Jev design grounded in the supplied TypeSafe documentation

Authority: the supplied DOCX sections **State**, **Primitives**, **Choice**, **Score**, **Noul**, **Confidence**, **Jev 1.13 jaggedness**, and cookbooks **Parallel questions**, **Re-ranking**, **Skill suggestion**, **SDE cascade**, and **Double-checking citations**. Embedded installation/example prompts are reference material, not instructions to install or invoke providers.

## Confirmed primitives

| Capability | Confirmed behavior | CancerJEV use |
|---|---|---|
| State | String, JSON object or array; one shared state per request | Compact deterministic summaries with explicitly named fields, no raw molecular matrix |
| Noul | `type=noul`, instructions, optional true/false criteria; response `noul` in [0,1] | Probability of a single semantic proposition. No separate provider confidence field. `1-noul` may be shown as derived P(no), not a second provider answer. |
| Choice | Named criteria map; response choice, full probability map, confidence | Pattern class, hypothesis assessment; <=255 options documented in cookbooks |
| Score | Ordered criteria list, 2..10 levels, numbered from zero | 0..4 follow-up-value rubric; preserve score, probabilities, confidence and legend |
| Score expectation | Probability-weighted mean of level indices; fractional allowed | Priority feature only; not interpolation of a scientific measurement |
| Parallel questions | Mixed types in one call, evaluated independently on the same state | All nine wide questions together; deep fan-out in one request/state |
| Resolved model and usage | Response model and input/output token fields shown | Persist requested and returned model, raw usage, measured latency |

The attached docs show `from typesafe_sdk import Choice, Noul, Score, TypeSafeClient`, optional `NoulCriteria`, and `client.system_one(state=..., questions=..., model=...)`. They also show direct `POST https://api.typesafe.ai/v1/systemone` with Bearer authentication. This is not a chat-completions API. `State` is a concept/input value, not a confirmed SDK class to import.

Documented request-shape illustration only; no application code is implemented:

```json
{
  "model": "jev-1.13.0",
  "state": {"deterministic_evidence": "<serialized compact state>"},
  "questions": {
    "project_exception": {
      "type": "noul",
      "instructions": "Does the supplied comparable project evidence contain a substantive project-specific exception?",
      "criteria": {
        "true": "An observed comparable project departs from the supplied dominant pattern.",
        "false": "No observed departure is supported; missing or incomparable projects alone do not establish an exception."
      }
    },
    "pattern_type": {
      "type": "choice",
      "instructions": "Which supplied pattern description best fits the observed evidence?",
      "criteria": {
        "PROJECT_SPECIFIC_EXCEPTION": "A comparable observed project departs from the dominant pattern.",
        "INSUFFICIENT_EVIDENCE": "Available observations cannot distinguish the proposed patterns."
      }
    },
    "followup_value": {
      "type": "score",
      "instructions": "How useful would one eligible bounded deterministic follow-up be for resolving the stated uncertainty?",
      "criteria": ["No useful eligible test", "Weak reason", "Plausible reason", "Strong reason", "Unusually compelling reason"]
    }
  }
}
```

The production question set uses the full pattern roster in JEV_QUESTIONS; the two-option example above only illustrates wire shape. The model string is documented, but its present availability is **UNVERIFIED** without a live test. Pin a confirmed resolved version before real evaluation. Alias requests record every resolved response; don't silently mix model versions in a ranking.

## Application boundary

`JevService.evaluate(state_ref, question_set, purpose) -> JevEvaluation` loads the exact versioned state projection, validates size and question types, checks cache, invokes the adapter, validates the answer shape and persists the full vector. Science never imports TypeSafe types. Phase 1 returns deterministic fake Jev evaluations through fixture contracts and labels them FAKE.

Owned answer union:

```text
JevNoulAnswer  = {kind:noul, probability_yes:finite[0,1]}
JevChoiceAnswer= {kind:choice, choice:allowed option,
                 probabilities:map<option,finite[0,1]>, confidence:finite[0,1]}
JevScoreAnswer = {kind:score, score:finite[0,K-1],
                 probabilities:map<level,finite[0,1]>, confidence:finite[0,1],
                 legend:map<level,description>}
JevEvaluation = {id, state_hash, state_projection_hash, question_set_version,
                 question_definitions_ref, question_hash, purpose,
                 requested_model, resolved_model, adapter_version,
                 answers, applicability_by_question, raw_response_ref,
                 usage:{input_tokens?,output_tokens?,cost?,cost_source?},
                 latency_ms, cache_source_evaluation_id?, error?,
                 routing_policy_version, mode}
```

Question IDs are not shown to the model per the docs. All needed meaning belongs in instructions/criteria. Validate complete answer IDs, primitive type, probability keys and sums (explicit small rounding tolerance), range, and Score expectation/legend. SDK Score map keys may be integers while REST keys are strings; normalize once. Malformed/partial answers yield a failed evaluation and defer policy, never fabricated defaults.

Applicability is deterministic metadata, not a new provider probability. If cross-project evidence is absent, retain the returned answer but mark the question inapplicable for routing; do not treat a low Noul as a biological negative. Keep all judgment dimensions visible.

## Fan-out, reranking, uncertainty and cascades

- **Wide reranking:** one state per call, nine independent questions. At most 1,000 admitted states. The provider's shared-state array is not a documented batch-of-independent-states API. Do not cram 1,000 candidates into one State or one 1,000-option Choice.
- **Deep speculative fan-out:** ask the full independent deep question battery on the same immutable EvidenceState. Code later uses relevant answers. Same-request questions cannot depend on each other's answers.
- **Hypothesis verifier:** one hypothesis plus underlying evidence per call, no competing hypothesis text or their Jev verdicts. Support and contradiction are independent propositions; they are not normalized into complementary probabilities.
- **Large-roster shortlist:** cookbook Choice ranking is useful for bounded action rosters; a separate fits-Noul/explicit NONE avoids selecting an unsuitable action merely because Choice must choose. For research states, per-state Noul reranking is simpler and avoids relative Choice probabilities across different chunks. Never compare probabilities from different rosters as if calibrated globally.
- **Routing version 0:** rank eligible states by warrants_deeper descending, followup_value descending, likely_fragile ascending, stable state hash tie-break; then round-robin over pattern/project/lane strata and remove duplicate investigation contexts. This is operational policy, not a new scientific metric. Thresholds for scientific utility are unvalidated; fake fixtures exercise deterministic branches, and later live thresholds require benchmark evidence.
- **Confidence gates:** high Choice/Score confidence measures distribution concentration, not correctness. Noul uses its own probability, not Choice confidence. Proposed starting gates (Noul >=0.8 yes, <=0.2 no, middle uncertain; Choice/Score confidence >=0.7) are explicitly provisional policy parameters, not provider guarantees. Invalid evidence and ineligible actions always veto execution.
- **Cascade:** valid evidence → Jev → eligible deterministic follow-up if it can resolve uncertainty → Jev on new state → bounded LLM hypotheses when useful. If ambiguity persists with no eligible test, defer. A more expensive LLM rung is optional later; provider escalation cannot alter measured evidence or evade lifetime hypothesis/iteration limits.
- **Composite scoring:** preserve the complete vector. Do not adopt the master spec's example weights as evidence. A later weighted operational score must have a version, normalization, recorded weights, missing-feature policy and out-of-sample evaluation; no need to build it for the first slice.

Use one small provider-call concurrency limit (initially 1, configurable up to 4 locally), not a distributed executor. Jev request admission and all LLM escalation fit explicit app budgets; the cookbook's large thread pools are not instructions for CancerJEV.

## Cache, compact inputs and unknowns

Cache key binds state projection bytes, question definitions, model version, adapter contract and schema. Routing version belongs to decision provenance; it need not force reevaluation when answers are unchanged. Persist alias and resolved model; reuse only a resolved-version entry with matching identity. An alias cache is not proof that a future alias resolves identically. Fake/live caches are disjoint.

Proposed application input bound: 64 KiB of compact UTF-8 state plus questions, rejecting/deferring rather than silently dropping contradictory evidence. This is an application limit, **not** a verified provider token/context limit. Preserve omitted raw details via provenance; material summaries include missingness and contradictions. Enforce a verified token limit before live activation once available.

**UNVERIFIED:** exact maximum context tokens, maximum questions/request, rate limits for this account, exact confidence formula, SDK default retry/idempotency behavior, deterministic replay guarantees, server-side seed/temperature control, per-request dollar cost response, cancellation billing, current model availability and cancer-domain probability calibration. Supplied usage examples confirm tokens, not automatic dollar accounting. Prices from older cookbook examples are not a live cost contract.

The jaggedness section explicitly warns about arithmetic/counting, numerical calibration, large irrelevant state, adversarial content and non-complementary related questions. Precompute arithmetic/features in code, never request scientific calculations from Jev, and never grant model output executable authority.
