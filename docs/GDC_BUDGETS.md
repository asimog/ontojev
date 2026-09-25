# Budgets: implemented limits, observations and proposals

Current after the Stage 3 hard cutover (2026-09-25). Limits below are application ceilings, not
provider guarantees. No limit or dependency changed in the cutover. Offline replay is not a live
workload or cost measurement.

## IMPLEMENTED

| Resource | Bound | Enforcement / caveat |
|---|---:|---|
| GDC consumed body per response | 5 MiB | `BudgetCaps`/stream reader, error bodies included |
| GDC consumed bodies per run | 64 MiB | `RunBudget` shared byte accounting |
| GDC network attempts per run | 150 | reserve before dispatch; retries consume attempts |
| GDC logical page number | ≤10 | request page check; the case loop advances monotonically; not a general repartition-proof query planner |
| Explicit case/gene IDs per request | 250 / 100 | fixed endpoint builders and transport validation |
| Safe GET retries | ≤2 after initial | no POST retry, no 401/403 retry; each attempt charged |
| GDC socket timeout | ≤30 s | operation timeout, not a whole-campaign deadline |
| Cases/projects/files/discovery page size | 250 / 100 / 5 / 20 | endpoint builder validation |
| Production cohort ceiling | 1,000 | `LUAD_RESEARCH_V1`; a general `AcquisitionSpec` must fit `page_size × 10` |
| Production gene selection | discovery 20, count limit 100, candidate 10 | provider-ranked slice: labelled baseline/comparator path, unchanged |
| Stage 4 systematic discovery | 10 `/genes` pages ×100 (gene_id asc, protein_coding) + 1 coverage + 10 count batches ×100 + 1 comparator | fixed `LUAD_DISCOVERY_V1` contract; 27 attempts / 2,817,301 bytes measured live (2026-09-25); no cap enlarged |
| Stage 5 independent expression | status + project + ≤4 cohort pages + 10 `/genes` pages + 1 file-provenance request + up to 10 gene batches × 4 case batches × (availability + values) = ≤97 requests | fixed `ExpressionDiscoverySpec`; unchanged 150-request/64-MiB caps; **live: 61 attempts / 5,007,079 bytes, 1,000 genes, 946 observed + 54 typed unavailable (2026-09-25)** |
| Stage 6 survivor-only CNV | status + ≤10 Stage 4 survivors × ≤10 `/cnv_occurrences` pages of 250 rows = ≤101 requests | fixed `CnvDiscoverySpec`; exact Stage 4 artifact/release/frame binding; an over-cap gene becomes typed unavailable with no partial evidence; unchanged 150-request/64-MiB caps; **live: 20 attempts / 1,860,737 bytes, 10/10 survivors complete (2026-09-25)** |
| Wide states per invocation | `Settings.jev_max_states` ≤1,000 | capped prefix in `run_wide_evaluation`; not an underlying HTTP-attempt ledger |
| Promotion slots | 3 | ranking and operator selection share the cap |
| Follow-ups per candidate | 3 | `deep.FOLLOWUP_LIMIT`; the current registry/revision cap is tighter |
| Evidence revision index | 0..2 | E0 plus at most E1/E2; `deep.EVIDENCE_ITERATION_LIMIT` and event schema |
| Hypotheses per candidate | 3 | `hypotheses.MAX_HYPOTHESES`, lifetime admission check |
| Jev request timeout setting | ≤30 s | adapter passes SDK timeout |
| LLM timeout setting | ≤120 s | hard cap equals the default; operational settings may lower it only. The adapter enforces a whole-request deadline between streamed reads, so a slow stream becomes a typed failure. |
| OpenRouter response/completion | 32,768 bytes / 6,000 output tokens | bounded reader; reasoning shares the completion budget |
| Event data / whole envelope | 65,536 / 98,304 bytes (96 KiB) | `RunEvent` validation |
| Jev projection | 65,536 bytes | projection fail-closed byte check; NOT a token-limit proof |

`Settings.from_env` rejects above-hard-cap values and supports lower limits. Direct construction of
internal objects is not a public arbitrary-budget authorization. GDC host/method/field allowlists,
anonymous access and no downloads remain fixed code. Physical network/TLS buffers and headers are
outside consumed-body accounting. Unexpected compression and redirects are refused.

Old proposals for 20 deep candidates, 6 hypotheses and 1,420 evaluations are superseded, not
enforced runtime policy. The current three-candidate/two-revision/three-hypothesis bounds give at
most `W + 3×(2 deep + 3 hypothesis) = W + 15` logical Jev evaluations for a single bounded arc,
assuming one review per generated hypothesis/revision. Current production `W ≤ 10`, hence ≤25;
a configured wider invocation `W ≤ 1,000` gives ≤1,015. These are derived logical-call envelopes,
not guaranteed HTTP counts. Early failures, abstentions, unavailable hypotheses and cache hits
reduce work.

## SDK retries and accounting — explicit no-retry

IMPLEMENTED: `cancerjev/jev/typesafe_adapter.py` constructs the client with
`RetryPolicy(max_retries=0)`, so a logical Jev evaluation corresponds to at most one HTTP attempt;
application counters are not inflated or hidden by automatic SDK retries.

- The installed typesafe-sdk version documents configurable retries; this project explicitly
  disables them. A future change to retry behavior requires its own recorded decision and must
  update the counter semantics rather than silently multiplying provider attempts.
- IMPLEMENTED (Stage 7): explicit Jev provider attempt and input-token envelopes.
  `CANCERJEV_JEV_MAX_ATTEMPTS` (default 25, hard cap 1,015) and `CANCERJEV_JEV_MAX_INPUT_TOKENS`
  (default 1,600,000; each attempt reserves 64,000 input tokens before any provider call) refuse
  further work with typed `JEV_ATTEMPT_BUDGET_EXHAUSTED` / `JEV_INPUT_TOKEN_BUDGET_EXHAUSTED`
  outcomes.
- PLANNED before larger paid discovery: shared spend reservations across arms, terminal usage
  including unknown values, bounded review/retry authorization and cancellation tests. A total
  paid-model spend gate does not exist, and current Jev/LLM dollar budgets are not enforced.
- The GDC transport ledger covers GDC attempts only; model calls are not in it.
- Actual billing of failed provider requests remains unknown, not zero.

## Measured anonymous architecture campaign (historical evidence)

69 attempts / 6,093,958 bytes, all HTTP 200. Per-session maximum was 14 requests; largest session
2,523,861 bytes. Largest individual body 284,276 bytes. Campaign ceilings 150/64 MiB, session
30/8 MiB, response 5 MiB, genes 100/cases 250, pages 10, concurrency 1, timeout 30 s, no retries.
Every attempted request has a terminal entry. [Register](GDC_DISCOVERY_CAPTURES.md) and
[workloads](GDC_STRATEGY.md) include exact hashes, requests, measurements and the limited
full-cohort extrapolation. The campaign is not a production run and did not enter production
data. HTTP 200 with incomplete search pagination or missing scientific fields is not admitted
evidence.

## Documented TypeSafe price/limits (not account guarantees)

Official [models page](https://docs.typesafe.ai/models), checked 2026-09-24: `jev-1.13.0` input
$0.042 per million tokens ($42/billion), output free; 64k tokens/request, state plus longest
question ≤32k; 250,000 tokens/s and 1,200 requests/min, explicitly subject to change. Choice ≤255
options and Score 2–10 levels are documented primitive limits checked in current question
definitions. Byte limits do not imply token limits. No account price/quota or invoice was queried.

### Scenario arithmetic — ESTIMATED, not paid/benchmarked

Let N states, S state tokens, Q total question tokens, L one request latency. Shared-state
fan-out: `input = N×(S+Q)`. Separate questions repeat S; k equal-size questions cost
`N×(k×S+Q)`. Price estimate = `input/1,000,000 × 0.042`. Add provider/tokenizer overhead and
actual retries when measured.

| Scenario | Assumptions | Logical requests | Input tokens | Estimated input cost |
|---|---|---:|---:|---:|
| Wide100, seven-question fan-out | S1500, Q700 | 100 | 220,000 | $0.00924 |
| Wide1000 same workload | S1500, Q700 | 1,000 | 2,200,000 | $0.09240 |
| Wide100, seven separate calls | each question 100 tokens | 700 | 1,120,000 | $0.04704 |
| Survivor rerank10 | one profile 1500 + rubric 200 | 10 | 17,000 | $0.000714 |
| Deep3 candidates ×2 revisions | state 3000 + five questions 500 | 6 | 21,000 | $0.000882 |
| Hypothesis reviews9 | state 3000 + questions 300 | 9 | 29,700 | $0.0012474 |
| Optional cascade100 | verifier 1,700 tokens each | 100 verifier calls | 170,000 | $0.00714 + UNKNOWN generator/escalation cost |

A 100-state batched stage takes roughly 100L sequentially, versus 700L for serial separate
questions. If L were 0.6 s (assumption), these are 60 s versus 420 s; this is not a measured LUAD
latency. Batching different states into a giant context is not the same optimization as
independent questions over one shared state and can impair relevance/context budget. Keep
concurrency 1 initially; fan-out inside a provider request does not authorize application
concurrency.

For cascade escalation fraction r, total cost `= Ccheap + N×Cverify + r×N×Creasoning`.
Conditional latency is `Lcheap + Lverify` plus `Lreasoning` for escalated cases; no generator
price or r is established here. An optional semantic stage followed by unchanged Wide adds both
stages' costs. Cache hits avoid new provider input charges but retain source usage provenance.
Changing model/question/state invalidates cache; changing only ranking weights need not.

## Historical OntoJev observations (retained, not current measurements)

From dated records, retained without re-running providers:

- 2026-09-22 `wide-v2`, projection v1, `jev-1.13.0`: 10 calls, 28,294 input/2,020 output,
  about 0.9–1.2 s/call.
- 2026-09-23 single-cohort `wide-v3` acceptance: 10 calls, 19,659 reported input tokens; provider
  cost unknown.
- 2026-09-23 `deep-v1` over E1, `jev-1.13.0`: 3,606 input/174 output, 587 ms for one call.
- Historical wide/deep cache replay reported zero fresh provider calls. A cache demonstration is
  not model reproducibility or scientific validation.
- 2026-09-25 Stage 3 live acceptance, `jev-1.13.0`: fresh sweep 16 GDC attempts / 367,862 bytes
  with 10 live `wide-v3` calls; explicit operator follow-up and one `deep-v1` call over the
  retained cache (16/16 GDC cache hits, 0 new bytes); one OpenRouter generation
  (`deepseek/deepseek-v4.1-flash`, 316 input / 3,501 output) and 2 `hypothesis-v2` critiques;
  14 total Jev attempts of the 15-attempt budget. One live answer set failed strict validation
  (`INVALID_DISTRIBUTION`) and was recorded fail-closed. Provider invoiced cost remains unknown.
- OpenRouter acceptance is now IMPLEMENTED and PASSED for the bounded 2026-09-25 case; it is not
  a reproducibility or scientific-value demonstration.

Do not mix historical question workloads or use their latency as a present guarantee.
