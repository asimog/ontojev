# Hard budgets and exact enforcement design

These are application limits, not GDC service guarantees. Phase 1 simulates budget events without network traffic; real enforcement ships and is adversarially tested in Phase 2. Lowering limits is allowed. This design rejects above-default limits in V1; it deliberately does not implement the optional expanded-budget override. Freeze validated effective limits in every run.

| Constant | Hard cap | Enforcement point |
|---|---:|---|
| MAX_GDC_RESPONSE_BYTES | 5,242,880 | Stream reader before each read and header preflight |
| MAX_GDC_TOTAL_BYTES_PER_RUN | 67,108,864 | Shared run ledger reserves bytes before dispatch; all bodies, including failures, count |
| MAX_CASE_IDS_PER_REQUEST | 250 | Validated request builder plus recursive inspection of final encoded filter/body, across all groups and aliases |
| MAX_GENE_IDS_PER_REQUEST | 100 | Same inspection for gene IDs across query/body/filter; reject duplicates or normalize first, with aggregate cap |
| MAX_GDC_REQUESTS_PER_RUN | 150 | Atomic attempt reservation immediately before every actual dispatch; retries count |
| MAX_DEEP_CANDIDATES | 20 | Transactionally consume permanent promotion slot; count every admission including failures |
| MAX_PROJECTS_PER_RUN | 12 | Frozen scientific scope; every scientific request's project/case mapping must belong to it |
| MAX_GDC_CONCURRENCY | 4 | One shared semaphore spanning request start through stream close; default start with 1 |
| MAX_GDC_PAGES_PER_QUERY | 10 | Logical-query page ledger, preserved across smaller-page retries and partitions |
| MAX_WIDE_HITS_PER_PROJECT_LANE | 100 | Endpoint selection_size/size where supported and deterministic collection cap |
| MAX_JEV_WIDE_STATES_PER_RUN | 1,000 | Persist distinct state admissions before cache/provider evaluation; reevaluation cannot reset admission budget |
| MAX_FOLLOWUPS_PER_CANDIDATE | 3 | Consume execution slot before action start; failure and repeat attempt still use slots |
| MAX_RESEARCH_ITERATIONS_PER_CANDIDATE | 2 | Maximum two evidence-changing follow-up rounds after baseline iteration 0 |
| MAX_HYPOTHESES_PER_CANDIDATE | 6 | Lifetime candidate count, not per round; new/replacement hypotheses consume remaining slots |
| MAX_EVENT_DATA_BYTES | 65,536 | UTF-8 serialized payload validation before event commit |

Case/gene limits count the combined supplied identifiers, not 250 for each subgroup. Reject repeated IDs in raw user-like inputs to avoid count ambiguity; generated queries use canonical deduplicated lists. Count UUIDs and submitter IDs using typed field manifests. Arbitrary filter input is not accepted; unknown ID-bearing fields fail closed. A project filter is not an explicit case ID list, but its response remains subject to all other caps.

## Sole transport path

Every GDC operation, including inventory, mapping queries, errors and retries, goes through `GDCClient.request(run_budget, validated_request)`. No science, Jev, LLM, API route or helper creates its own network client. Fixed HTTPS host `api.gdc.cancer.gov`, allowlisted paths/methods, no GDC Authorization/X-Auth-Token, no redirect following, no automatic library retries. `/data`, manifests, BAM slicing and archive downloads are absent from the allowlist.

Steps:

1. Validate frozen scope, endpoint contract, final ID counts, requested fields, format, and logical-query page allowance. Normalize request identity without changing filter semantics.
2. Check cache and hash/size/contract validity. A fresh valid hit has zero network bytes/calls, still records the source request and consumes logical page/state work allowances. Never use a cached body larger than the run's configured response cap.
3. Acquire the shared semaphore. Under a ledger mutex and short SQLite transaction, require `attempts < cap`; reserve one attempt and `allowance = min(response_cap, run_cap - consumed - reserved)`. Refuse if allowance is zero. Persist attempt start and reservation before sending. Worst-case reservations make four concurrent streams safe without each believing it owns the same remaining bytes.
4. Send with `Accept-Encoding: identity`; disable automatic decompression, redirect following and retry. Header preflight rejects a Content-Length above the allowance before intentional body reads. An unexpected content encoding is rejected; do not decompress an unbounded payload. Header sizes/timeouts also receive modest independent transport limits.
5. Read incrementally, each requested read size <= `min(16 KiB, allowance - bytes_read)`. Charge every yielded body byte before buffering/parsing or publishing. No `response.content`, eager `.json()`, or download-then-check code path. Save to a bounded temporary file. Check cancellation between reads.
6. At the allowance boundary, accept only when protocol framing has already established complete body termination. Otherwise close and classify as size-limit/incomplete, without reading an extra sentinel byte. This deliberately may reject an exactly-at-limit unknown-length response. An aborted/truncated JSON/TSV body never becomes evidence or a cache entry.
7. On close, persist charged consumption and release unused reservation. Validate status, framing, response schema and completeness; hash and publish only accepted results. Error response bytes and partial failed attempts remain charged. If a fatal process crash prevents final accounting, retire the run rather than resume/reuse its budget.

Reservation is pessimistic; actual consumption is counted separately. A dispatch reservation may remain conservatively charged when it is impossible to determine whether a send reached GDC. Never refund an uncertain attempt and retry past the cap. Cache hits do not receive network reservations. An exhausted run can continue over cached/held evidence and finish/defer dossiers.

**Physical-network limitation:** an application cannot guarantee zero extra bytes arrive in OS/TLS buffers after it cancels a request. The hard guarantee here is a maximum response-body consumption at the controlled reader and maximum persisted/admitted data, with immediate cancellation. It is not a packet-level ISP billing guarantee and excludes HTTP/TLS headers. Transport read-ahead must be measured in Phase 2; a stock high-level iterator may prefetch more than its yielded chunk size. Do not call an iterator `chunk_size` a proof of a wire-byte cap. Literal total NIC-byte enforcement remains **RISK**, not silently declared solved. No extra infrastructure is proposed to hide this limitation.

## Retry, pagination and exhaustion

Connect timeout 10 seconds; read timeout 30 seconds; proposed whole-attempt deadline 60 seconds prevents a slow trickle from running indefinitely. At most two retries after the initial safe read request, only for connection resets/timeouts, 429 and selected transient 500/502/503/504 responses. Exponential backoff with jitter, bounded Retry-After handling; every retry reserves another request and bytes. Unknown POST safety means no automatic retry until the endpoint's read-only behavior is confirmed. Never retry 401/403; record UNAVAILABLE_ACCESS. Never automatically retry oversized responses with a larger cap.

Pagination identity is `(endpoint, science scope, semantic filters, fields, format, units, lane/query purpose)`, excluding cursor and page-size mechanics. Track requested page advances separately from network attempts: retrying a failed page consumes request budget but not a second successful-page slot. Reducing page size or splitting the same query shares the original <=10 advance slots. Detect repeated cursors/pages, duplicates, inconsistent totals and empty pages; stop PARTIAL rather than loop. Standard search uses offset plus returned count and metadata consistency, not a guessed universal page token.

GDC budget exhaustion emits `GDC_REQUEST_BUDGET_EXHAUSTED` or `GDC_RUN_BYTE_BUDGET_EXHAUSTED`; response rejection emits `GDC_RESPONSE_LIMIT_EXCEEDED`. Page/project/ID/work limits use typed reason codes in a policy event. A blocked candidate becomes DEFERRED with reason `DEFERRED_BUDGET`, not FAILED or a negative scientific result. Retrieval stops immediately; already-held data can still be judged/rendered.

## Feasibility and cost visibility

Caps are ceilings, not quotas. A proposed planning envelope is 10 inventory/metadata calls, up to 4 wide calls ×12 projects (48), up to 3 initial deep calls ×20 candidates (60), leaving 32 of 150 for retries and selected follow-ups. This is not a promise that every endpoint or candidate fits. Worst-case responses would exceed 64 MiB long before the request ceiling; bytes always override this plan. Fair admission may result in fewer than 12 projects or 20 candidates.

Jev's 1,000-state cap is not a 1,000-question cap: nine wide questions mean up to 9,000 judgments. With at most three evidence versions, deep evaluations are <=60 and six independently reviewed hypotheses ×three versions ×20 candidates are <=360 additional calls; total planned Jev evaluations <=1,420 before any retries. No live retries until separate provider call/token/spend policy is frozen. LLM generation occurs at most twice/candidate with total six hypotheses, and template dossiers avoid an extra model call. Actual provider prices, service quotas and cancellation billing are **UNVERIFIED** from supplied material for the intended live configuration. Display unknown cost as unknown, never $0.
