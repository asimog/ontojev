# Hard budgets and exact enforcement design

These are application limits, not GDC service guarantees. Real enforcement ships and is
adversarially tested; a code/document mismatch is resolved toward the stricter safe value. Lowering
limits is allowed. This design rejects above-default limits in V1; it deliberately does not
implement an optional expanded-budget override. Freeze validated effective limits in every run.

## Implemented caps (code is authoritative)

| Constant | Hard cap | Enforcement point |
|---|---:|---|
| MAX_GDC_RESPONSE_BYTES | 5,242,880 (5 MiB) | `BudgetCaps.per_response_bytes`; stream reader and header preflight |
| MAX_GDC_TOTAL_BYTES_PER_RUN | 67,108,864 (64 MiB) | `BudgetCaps.max_bytes`; shared run ledger reserves bytes before dispatch; all bodies, including failures, count |
| MAX_GDC_REQUESTS_PER_RUN | 150 | `BudgetCaps.max_requests`; atomic attempt reservation immediately before every actual dispatch; retries count |
| MAX_GDC_PAGES_PER_QUERY | 10 | `BudgetCaps.max_pages_per_query`; logical-query page ledger, preserved across smaller-page retries and partitions |
| MAX_CASE_IDS_PER_REQUEST | 250 | `MAX_CASE_IDS` in the request builder plus `BudgetCaps.max_case_ids`; validated request builder and final encoded filter/body inspection |
| MAX_GENE_IDS_PER_REQUEST | 100 | `MAX_GENE_IDS` in the request builder plus `BudgetCaps.max_gene_ids`; same inspection for gene IDs |
| MAX_GDC_RETRIES | 2 | `BudgetCaps.max_retries`; bounded retries for safe GETs only |
| GDC_SOCKET_TIMEOUT | 30 s | `BudgetCaps.timeout_seconds`; one socket timeout for connect/read |
| MAX_CASES_PAGE | 250 | `cases_request` size validation |
| MAX_FILES_PAGE | 5 | `files_expression_request` size validation |
| MAX_PROJECTS_PAGE | 100 | `projects_request` size validation |
| MAX_DISCOVERY_HITS | 20 | `top_mutated_genes_request` size validation |
| MAX_COHORT_CASES | `case_page_size × 10` (≤2,500) | `AcquisitionSpec`: the ten-page query budget |
| MAX_JEV_WIDE_STATES_PER_RUN | 1,000 | `Settings.jev_max_states`; persist distinct state admissions before cache/provider evaluation; reevaluation cannot reset admission budget |
| MAX_EVENT_DATA_BYTES | 65,536 | `domain.events.DATA_LIMIT`; UTF-8 serialized payload validation before event commit |
| MAX_PROJECTION_BYTES | 65,536 | `jev.projection.PROJECTION_BYTE_CAP`; fail-closed projection size |
| WIDE_PROMOTION_LIMIT | 3 | `research.ranking.PROMOTION_LIMIT`; top-K wide admission (a maximum, not a quota) |

The per-response cap was previously documented as 5 MiB while the code defaulted to 8 MiB; the
code was lowered to the documented 5 MiB (a regression test asserts the default). Case/gene limits
count the combined supplied identifiers, not 250 for each subgroup. Reject repeated IDs in raw
user-like inputs to avoid count ambiguity; generated queries use canonical deduplicated lists.
Arbitrary filter input is not accepted; unknown ID-bearing fields fail closed. A project filter is
not an explicit case ID list, but its response remains subject to all other caps.

## Planned Phase 4 caps (documented, not enforced)

| Constant | Planned cap | Note |
|---|---:|---|
| MAX_DEEP_CANDIDATES | 20 | Deep promotion slots; not implemented |
| MAX_FOLLOWUPS_PER_CANDIDATE | 3 | Execution slots; not implemented |
| MAX_RESEARCH_ITERATIONS_PER_CANDIDATE | 2 | Evidence-changing rounds after baseline iteration 0; not implemented |
| MAX_HYPOTHESES_PER_CANDIDATE | 6 | Lifetime candidate count; not implemented |

The old `MAX_PROJECTS_PER_RUN = 12` and `MAX_GDC_CONCURRENCY = 4` rows are removed: the current
specification selects exactly one project, and the transport is a single sequential process
(concurrency 1, no semaphore). The old `MAX_WIDE_HITS_PER_PROJECT_LANE = 100` is covered by
`MAX_GENE_IDS` and the `ResearchSpec` candidate-gene limit.

## Sole transport path

Every GDC operation, including inventory, mapping queries, errors, retries and contract probes,
goes through `GDCTransport.request(run_budget, validated_request)`. No science, Jev, LLM, API route
or helper creates its own network client. Fixed HTTPS host `api.gdc.cancer.gov`, allowlisted
paths/methods, no GDC Authorization/X-Auth-Token, no redirect following, no automatic library
retries. `/data`, manifests, BAM slicing and archive downloads are absent from the allowlist. The
contract-capture probe is the same transport with a capture sink; it cannot reach endpoints the
runtime allowlist excludes, and its own budgets are bounded per invocation.

Steps:

1. Validate frozen scope, endpoint contract, final ID counts, requested fields, format, and
   logical-query page allowance. Normalize request identity without changing filter semantics.
2. Check cache and hash/size/contract validity. A fresh valid hit has zero network bytes/calls,
   still records the source request and consumes logical page/state work allowances. Never use a
   cached body larger than the run's configured response cap.
3. Reserve one attempt under the ledger mutex; refuse when the request cap is reached, when the
   requested page exceeds the per-query page cap, or when the run byte cap is already reached.
   Persist attempt start and reservation before sending.
4. Send with `Accept-Encoding: identity`; disable automatic decompression, redirect following and
   retry. Header preflight rejects a Content-Length above the allowance before intentional body
   reads. An unexpected content encoding is rejected; do not decompress an unbounded payload.
5. Read incrementally, each requested read size ≤ `min(64 KiB, allowance - bytes_read)`. Charge
   every yielded body byte before buffering/parsing or publishing. No `response.content`, eager
   `.json()`, or download-then-check code path. Check cancellation between reads.
6. At the allowance boundary, accept only when protocol framing has already established complete
   body termination. Otherwise close and classify as size-limit/incomplete, without reading an
   extra sentinel byte. An aborted/truncated JSON/TSV body never becomes evidence or a cache entry.
7. On close, persist charged consumption and release unused reservation. Validate status, framing,
   response schema and completeness; hash and publish only accepted results. Error response bytes
   and partial failed attempts remain charged. If a fatal process crash prevents final accounting,
   retire the run rather than resume/reuse its budget.

Reservation is pessimistic; actual consumption is counted separately. A dispatch reservation may
remain conservatively charged when it is impossible to determine whether a send reached GDC. Never
refund an uncertain attempt and retry past the cap. Cache hits do not receive network reservations.
An exhausted run can continue over cached/held evidence and finish/defer dossiers.

**Physical-network limitation:** an application cannot guarantee zero extra bytes arrive in OS/TLS
buffers after it cancels a request. The hard guarantee here is a maximum response-body consumption
at the controlled reader and maximum persisted/admitted data, with immediate cancellation. It is
not a packet-level ISP billing guarantee and excludes HTTP/TLS headers. Literal total NIC-byte
enforcement remains **RISK**, not silently declared solved. No extra infrastructure is proposed to
hide this limitation.

## Retry, pagination and exhaustion

Implemented: one socket timeout of 30 s and at most two retries after the initial safe read
request, only for connection resets/timeouts, 429 and selected transient 500/502/503/504 responses;
every retry reserves another request and bytes. Never retry 401/403; record `UNAVAILABLE_ACCESS`.
Never automatically retry oversized responses with a larger cap. Separate connect deadlines,
whole-attempt deadlines, exponential backoff with jitter and Retry-After handling are **PLANNED**
refinements, not implemented.

Pagination identity is `(endpoint, science scope, semantic filters, fields, format, units,
lane/query purpose)`, excluding cursor and page-size mechanics. Track requested page advances
separately from network attempts: retrying a failed page consumes request budget but not a second
successful-page slot. Reducing page size or splitting the same query shares the original ≤10
advance slots. Detect repeated cursors/pages, duplicates, inconsistent totals and empty pages; stop
PARTIAL rather than loop. The implemented case-frame path additionally fails closed on an
inconsistent provider `from` offset (`CASE_PAGE_OFFSET_INCONSISTENT`), a total that disagrees with
the inventory or changes across pages (`CASE_TOTAL_INCONSISTENT`), premature empty pages,
cross-page duplicate IDs and unexpected project IDs.

GDC budget exhaustion emits `GDC_REQUEST_BUDGET_EXHAUSTED` or `GDC_RUN_BYTE_BUDGET_EXHAUSTED`;
response rejection emits `GDC_RESPONSE_LIMIT_EXCEEDED`. Page/ID/work limits use typed reason codes
in a policy event. A blocked candidate becomes DEFERRED with reason `DEFERRED_BUDGET`, not FAILED
or a negative scientific result. Retrieval stops immediately; already-held data can still be
judged/rendered.

## Current single-cohort envelope

Caps are ceilings, not quotas. One `LUAD_RESEARCH_V1` slice is roughly 15–25 requests and well
under 2 MiB: 1 `/status`, 1 `/projects`, 1 `top_mutated_genes_by_project`, 1
`top_cases_counts_by_genes`, 1 `mutated_cases_count_by_project`, 1 `/genes`, ⌈N/250⌉ `/cases`
pages, 1 `/files`, ⌈N/250⌉ `gene_expression/availability` batches and ⌈N/250⌉
`gene_expression/values` batches, plus one `gene_selection` only when the whole cohort fits one
≤250-case request. With `max_cohort_cases ≤1,000`, each paginated lane is ≤4 requests. Bytes always
override the request ceiling. The contract-verification probe is a separate bounded invocation
(≤30 requests, ≤8 MiB) reproducible through the `probe` command; probe captures are written under
`data/gdc-contract-captures-<date>/` with per-request metadata and hashes.

Jev's 1,000-state cap is not a 1,000-question cap: the implemented `wide-v2` set has six questions
(up to 6,000 judgments), and the **PLANNED** `wide-v3` set has seven (up to 7,000 judgments; see
`docs/PHASE_3_PLAN.md`). **PLANNED** Phase 4 bounds are separate and not enforced: at most three
evidence versions, ≤60 deep evaluations, and six hypotheses × three versions × 20 candidates ≤360
additional calls; total planned Jev evaluations ≤1,420 before any retries. No live retries until a
separate provider call/token/spend policy is frozen. The TypeSafe documentation (see
`docs/SOURCE_REVIEW.md`) states `jev-1.13.0` at 64k context (32k state budget), ~250k tok/s, 1200
requests/min, and $42/Btok input with output free; those are **DOCUMENTED**, not a contract, and
actual prices, quotas and cancellation billing for the intended live configuration remain
**UNVERIFIED**. Display unknown cost as unknown, never $0.
