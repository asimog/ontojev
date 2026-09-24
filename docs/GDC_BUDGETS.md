# Budgets: implemented limits, observations and proposals

Baseline `42b05d40e6edafec0b8613e7dd154a60a46e4fee`; review 2026-09-24 UTC.
Limits below are application ceilings, not provider guarantees. No limit or dependency changed.

## IMPLEMENTED

| Resource | Bound | Enforcement / caveat |
|---|---:|---|
| GDC consumed body per response | 5 MiB | BudgetCaps/stream reader, error bodies included |
| GDC consumed bodies per run | 64 MiB | RunBudget shared byte accounting |
| GDC network attempts per run | 150 | reserve before dispatch; retries consume attempts |
| GDC logical page number | <=10 | request.page check; current case loop advances monotonically; not a general repartition-proof query planner |
| Explicit case/gene IDs per request | 250 /100 | fixed endpoint builders and transport validation |
| Safe GET retries | <=2 after initial | no POST retry, no401/403 retry; each attempt charged |
| GDC socket timeout | <=30 s | operation timeout, not a whole-campaign deadline |
| Cases/projects/files/discovery page size | 250 /100 /5 /20 | endpoint builder validation |
| Production cohort ceiling | 1000 | LUAD_RESEARCH_V1; general AcquisitionSpec must fit page_size x10 |
| Production gene selection | discovery 20, count limit 100, candidate 10 | current provider-ranked slice, not a 1000-gene universe |
| Wide states per invocation | Settings.jev_max_states<=1000 | capped prefix in run_wide_evaluation; not an underlying HTTP-attempt ledger |
| Promotion slots | 3 | ranking/operator selection share cap |
| Follow-ups per candidate | 3 | deep.FOLLOWUP_LIMIT; current two-action registry/revision cap is tighter |
| Evidence revision index | 0..2 | E0 plus at most E1/E2; deep.EVIDENCE_ITERATION_LIMIT and event schema |
| Hypotheses per candidate | 3 | hypotheses.MAX_HYPOTHESES, lifetime admission check |
| Jev request timeout setting | <=30 s | adapter passes SDK timeout; retries have separate behavior below |
| LLM timeout setting | <=120 s | config; adapter default 30 unless caller config supplied |
| OpenRouter response/completion | 32,768 bytes /6000 output tokens | bounded reader; reasoning shares completion budget |
| Event data / whole envelope | 65,536 /98,304 bytes | RunEvent validation |
| Jev projection | 65,536 bytes | projection fail-closed byte check; NOT a token-limit proof |

Settings.from_env rejects above-hard-cap values and supports lower limits. Direct construction of
internal objects is not a public arbitrary-budget authorization. GDC host/method/field allowlists,
anonymous access and no downloads remain fixed code. Physical network/TLS buffers and headers are
outside consumed-body accounting. Unexpected compression and redirects are refused.

Old proposals for 20 deep candidates, 6 hypotheses and 1420 evaluations are superseded, not enforced
runtime policy. Current three-candidate/two-revision/three-hypothesis bounds give at most
W + 3*(2 deep +3 hypothesis) = W+15 logical Jev evaluations for a single bounded arc, assuming one
review per generated hypothesis/revision. Current production W<=10, hence<=25; configured wider
invocation W<=1000 gives<=1015. These are derived logical-call envelopes, not guaranteed HTTP counts.
Early failures, abstentions, unavailable hypotheses and cache hits reduce work. At most one generation
stage per investigated candidate in the current loop: up to 3 logical generative calls when injected.

## SDK retries and resource-accounting gap

The installed typesafe-sdk 0.7.1 RetryPolicy defaults to 2 retries after initial, retryable
408/429/5xx plus connection/timeouts, backoff and a 30-second retry budget. The adapter does not supply
an explicit retry policy. The SDK's stop-before-next-delay rule is not a hard cancellation of an
already-running attempt. Application counters record adapter-level evaluations, not every SDK HTTP
attempt. A single logical evaluation can therefore attempt up to 3 HTTP calls; W+15 could become
3*(W+15) attempts in a conservative retry-count scenario. Actual billing of failed requests is unknown.

PLANNED before larger paid discovery: explicit no-hidden-retry policy (prefer 0 initially), shared
attempt/token/spend reservations, terminal usage including unknown values, bounded review/retry
authorization and cancellation tests. Do not claim current Jev/LLM dollar budgets are enforced.
Current GDC transport ledger does not cover model calls.

## Measured anonymous architecture campaign

69 attempts /6,093,958 bytes, all HTTP 200. Per-session maximum was 14 requests; largest session
2,523,861 bytes. Largest individual body 284,276 bytes. Campaign ceilings 150/64MiB, session 30/8MiB,
response 5MiB, genes 100/cases 250, pages 10, concurrency 1, timeout 30 s, no retries. Every attempted request
has a terminal entry. [Register](GDC_DISCOVERY_CAPTURES.md) and [workloads](GDC_STRATEGY.md) include
exact hashes, requests, measurements and the limited full-cohort extrapolation.

The campaign is not a production run and did not enter production data. HTTP 200 with incomplete search
pagination or missing scientific fields is not admitted evidence.

## Current documented TypeSafe price/limits (not account guarantees)

Official [models page](https://docs.typesafe.ai/models), checked 2026-09-24:
jev-1.13.0 input $0.042 per million tokens ($42/billion), output free; 64k tokens/request,
state plus longest question<=32k; 250,000 tokens/s and 1200 requests/min, explicitly subject to change.
Choice<=255 options and Score 2–10 levels are documented primitive limits and checked in current
question definitions. Byte limits do not imply token limits. No account price/quota or invoice was queried.

### Scenario arithmetic — ESTIMATED, not paid/benchmarked

Let N states, S state tokens, Q total question tokens, L one request latency. Shared-state fan-out:
input=N*(S+Q). Separate questions repeat S; k equal-size questions cost=N*(k*S+Q).
Price estimate=input/1,000,000*0.042. Add provider/tokenizer overhead and actual retries when measured.

| Scenario | Assumptions | Logical requests | Input tokens | Estimated input cost |
|---|---|---:|---:|---:|
| Wide100, seven-question fan-out | S1500, Q700 | 100 | 220,000 | $0.00924 |
| Wide1000 same workload | S1500, Q700 | 1000 | 2,200,000 | $0.09240 |
| Wide100, seven separate calls | each question100 tokens | 700 | 1,120,000 | $0.04704 |
| Survivor rerank10 | one profile1500 + rubric200 | 10 | 17,000 | $0.000714 |
| Deep3 candidates x2 revisions | state3000 + five questions500 | 6 | 21,000 | $0.000882 |
| Hypothesis reviews9 | state3000 + questions300 | 9 | 29,700 | $0.0012474 |
| Optional cascade100 | verifier1700 tokens each | 100 verifier calls | 170,000 | $0.00714 + UNKNOWN generator/escalation cost |

A 100-state batched stage takes roughly 100L sequentially, versus 700L for serial separate questions.
If L were 0.6s (assumption), these are 60s versus 420s; this is not a measured LUAD latency.
Batching different states into a giant context is not the same optimization as independent questions
over one shared state and can impair relevance/context budget. Keep concurrency 1 initially; fan-out
inside a provider request does not authorize application concurrency.

For cascade escalation fraction r, total cost=Ccheap+N*Cverify+r*N*Creasoning. Conditional latency is
Lcheap+Lverify plus Lreasoning for escalated cases; no generator price or r is established here.
Optional semantic stage followed by unchanged Wide adds both stages' costs. Cache hits avoid new
provider input charges but retain source usage provenance. Changing model/question/state invalidates
cache; changing only ranking weights need not. Worst-case three-attempt input estimates may be 3x;
actual failed-attempt billing remains unknown, not zero.

## Historical OntoJev observations (not new measurements)

From [dated status records](IMPLEMENTATION_STATUS.md), retained without re-running providers:

- 2026-09-22 wide-v2, projection-v1, jev-1.13.0: 10 calls, 28,294 input/2,020 output, about 0.9–1.2s/call.
- 2026-09-23 single-cohort wide-v3 acceptance: 10 calls, 19,659 reported input tokens; provider cost unknown.
- 2026-09-23 deep-v1 over E1, jev-1.13.0: 3,606 input/174 output, 587 ms for one call.
- Historical wide/deep cache replay reported zero fresh provider calls. A cache demonstration is not
  model reproducibility or scientific validation.

Do not mix historical question workloads or use their latency as a present guarantee.
