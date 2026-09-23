# Verification strategy

This is the test plan for the implemented phases. Phase 1 (offline fixture slice), Phase 2 (real open GDC evidence), Phase 3 (real Jev wide evaluation) and the Phase 4 deterministic first slice, deep Jev fan-out, next-move decision record and one authorized dispatch are implemented; the rest of Phase 4+ remains a plan. Use focused tests first, then the full relevant offline checks. No default test, build or CI command contacts GDC, TypeSafe or an LLM. Executed results live in IMPLEMENTATION_STATUS.md.

## Default offline boundary

The autouse test guard denies every outbound socket connection whose host is not loopback. Loopback is permitted only so transport tests can run adversarial local HTTP servers; GDC's host is never reachable from the default suite. Tests marked `live_gdc` or `live_jev` are opt-in, disabled by default, and each has explicit per-test budgets. Fixture mode must not construct a live provider even if credentials happen to be present in the environment.

## Phase 1 gates

| Layer | Required proof |
|---|---|
| Domain | Legal/illegal transitions; null vs zero; finite numbers; immutable state identity; counts and lifetime caps |
| Event/storage | Ordered contiguous per-run sequences; idempotent append; invalid payload rollback; projection equivalence; oversized data moves to artifacts; no truncated history |
| Artifacts | Same bytes/hash; path confinement; write/rename failure; crash after rename before DB commit leaves only unreferenced file; corrupted/missing artifact reports an error |
| Orchestration | Demo traverses every stage and one fixture follow-up changes evidence; old state remains unchanged; at most one dossier/candidate; defer/fail/no-result branches |
| Ownership/recovery | Second research process refused; abrupt kill leaves history intact; next owner records interruption without replaying side effects; Ctrl+C is coherent; API restart doesn't mark runs stopped |
| API | Correct list/event cursor semantics during concurrent writes, 404/422/503, no secret leakage, terminal events drained, actual usage zero in fake mode |
| Browser | Start CLI while /runs open, card appears, detail progresses, events append without full-log refetch, fake dossier opens, browser refresh and API restart preserve results; API disconnect retains stale data with explicit error |
| CLI/UI consistency | Compare event IDs/sequences from committed store, captured CLI JSON rendering, and API; both renderers consume identical records |
| Offline boundary | Deny outbound provider/network calls in tests; fixture mode cannot construct a live provider even if credentials happen to be in environment |

## Phase 2 gates (real GDC)

| Layer | Required proof |
|---|---|
| Transport | Host and endpoint allowlists; GET/POST method allowlist; no redirect following; per-response cap at cap−1/cap/cap+1; run byte cap under concurrent reservations; request cap at limit and limit+1; page cap; case/gene ID caps; attempt ledger charges every retry and body failure; every attempt that started reaches a terminal status (`COMPLETED`/`FAILED`/`CACHE_HIT`) even when publishing or registering the received body fails; the cache key is qualified by transport contract version so an older-version row cannot replay as current or block storing the current entry; cache hit performs no network I/O; no larger-cap retry after a limit breach |
| Open access | No `Authorization`, no `X-Auth-Token`, no token env var read, no credential loader, no `/data` route, `access=controlled` result rejected and never admitted, 401/403 become `UNAVAILABLE_ACCESS` with no credential lookup or retry |
| Adversarial server | Misleading/missing `Content-Length`, chunked body over cap, huge chunk declaration, partial JSON, compressed response despite identity request, abrupt disconnect, redirect, 401/403, 429 accounting, slow trickle; instrument real read behavior, never mock away read-ahead |
| Parsers | Real captured response fixtures (from `data/gdc-contract-captures-2026-09-22/`, copied into `tests/contracts/fixtures/` with provenance); unknown/missing fields; changed schema; duplicate IDs; missing cases; nonfinite values; impossible negative provider counts (project case/file counts, aggregation `doc_count`, SSM coverage counts, expression availability counts, provider totals) fail closed while an observed zero stays valid; UTF-8 BOM tolerated before the TSV header; a `/files` record without an explicit `access` fails closed as non-open; `warnings.fields` surfaced; aggregation completeness fields preserved; absent bucket stays `NOT_OBSERVED` |
| Science | Duplicate-case handling; matched numerator/denominator rules (never divide unmatched); units; missingness; partial populations; eligibility; estimator definitions; same scientific input → same state hash; changed input/membership/unit/version → changed hash; row permutation invariance; merged expression batches keep observed and missing genes disjoint and a gene omitted by one batch never becomes a reported missing gene |
| Orchestration | Exact single-cohort project selection from `ResearchSpec`; bounded paginated case frame with offset/total/duplicate fail-closed checks; deterministic expression batching merged by identifier; real StatisticalStates from the live loop against a replay transport; partial response never treated as complete; budget exhaustion stops admission with a typed event |
| API/UI | State list and full-state route expose v2 fields with explicit availability; `NOT_OBSERVED` never rendered as zero; zero Jev and zero LLM calls in a Phase 2 run |

## Phase 3 gates (real Jev)

| Layer | Required proof |
|---|---|
| Projection | Deterministic bytes from a fixed state; projection hash stable; version and included-field contract persisted; no field recomputed from raw responses |
| Questions | Definition hash covers wording/criteria/roster/applicability rule; question IDs never sent; applicability computed deterministically; excluded questions absent; malformed definitions fail at import (Choice >255, Score outside 2–10, unknown primitive/applicability, empty instructions) |
| Contracts | Noul probability range; Choice chosen value in roster; Choice/Score probability keys match roster/levels and sum to 1; Score level within declared range; confidence range; NaN/Infinity rejected; missing answer, unknown ID, wrong primitive and malformed provider payload all fail closed |
| Adapter | Provider wire/SDK confined to the adapter; owned contracts everywhere else; requested vs resolved model persisted; usage and latency recorded; provider errors/timeouts preserved without fabricated defaults; a response whose shape does not match the owned contract (missing `model`, null `answers`, missing answer field) becomes `JevProviderError(PROVIDER_RESPONSE_MALFORMED)` and a persisted failed evaluation instead of aborting the run; one malformed state defers while other states evaluate and the run continues; terminal statuses map to `PROVIDER_AUTH`/`PROVIDER_VALIDATION`/`PROVIDER_RATE_LIMIT`/`PROVIDER_OVERLOADED` (nested `response.status_code` included), else `PROVIDER_ERROR` |
| Config | `.env.local` loads only names absent from the real environment; comments, blanks, `export`, quoted values and invalid names handled; blank values inert; `CANCERJEV_NO_DOTENV=1` disables; missing file inert; values never logged |
| Cache | Identity binds projection bytes + question bytes + `question_set_hash` (wording, criteria, primitive, version and applicability rule) + pinned model identity + adapter version; policy version excluded; reuse requires a pinned/versioned model name whose provider resolution equals that name, so a mutable alias is always evaluated and a divergent resolution is never cached; cache hit creates an evaluation with `cache_source_evaluation_id` and zero usage; `FAKE` and `LIVE` caches disjoint |
| Ranking | Baseline and Jev rankings persisted for the same states; policy deterministic for identical stored evaluations; raw dimensions preserved; promotion bounded; a Jev error defers the state rather than scoring it |
| Deterministic actions (Phase 4 first slice) | Registered action contract complete (question, interpretation, method/version, unit, required evidence, limitations); eligibility is fail-closed with explicit reasons; each integrity check is exercised as `VERIFIED`, `CONTRADICTED` and `NOT_OBSERVED`; tampered selection bytes, unlinked attempts and absent retained artifacts never pass; execution is deterministic and leaves the input snapshot byte-identical; an ineligible action refuses to execute |
| Deep slice | E0 acceptance verifies the retained artifact hash and recorded `state_hash`; the baseline revision (iteration 0) and E1 (parent E0) are recorded with deterministic ids; the selected action, input artifact hashes, checks, missingness and provenance are persisted; replaying the same evidence records `FOLLOWUP_SKIPPED` and creates no duplicate revision; a selection matching no promoted candidate records `DEEP_SELECTION_UNAVAILABLE`; a requested ineligible action, exhausted follow-up limit and exhausted revision limit record typed `FOLLOWUP_ABSTAINED`; an action failure records `FOLLOWUP_FAILED`, writes a `FAILED` execution row, creates no revision and leaves the candidate and E0 unchanged; wide admission never dispatches a follow-up |
| Operator-approved selection | `slot:N`/gene symbol resolve only to policy-promoted candidates; a wide-evaluated state can be named by `<SYMBOL>`, `gene:<SYMBOL>` or `state:<STATE_ID>`; the created candidate records `operator-selection-v1`, `OPERATOR_APPROVED_SELECTION`, the raw selection and `auto_dispatched: false`; an unevaluated state is refused as `STATE_NOT_EVALUATED`; the promotion cap is enforced; an ambiguous gene symbol is refused; wide admission still selects nothing on its own |
| Deep Jev fan-out | The evidence projection is deterministic and free of operational ids, tracks check outcomes/evidence hashes and rejects other evidence schemas; deep applicability follows the recorded checks; one evaluation per revision is persisted with `purpose=DEEP`/`input_ref_kind=EVIDENCE_STATE` plus full answers/applicability; a second run with identical revision content reuses the judgment from cache; a provider or validation failure is a persisted `JEV_EVALUATION_FAILED` that leaves the revision intact; `provider_usage` counts the deep provider call exactly once and adds its tokens |
| Next-move policy | One typed move per revision with named thresholds and `executed: false`; contradicted checks, an unreliable revision, a failed judgment and a warranted step without a distinct action each produce their named reason; a conservative fallback abstains; the policy is deterministic and echoes its dimensions |
| Dispatch stage | Action input kinds are declared and eligibility follows them (a state action is ineligible for a revision and the reverse); the second action's restatement, provenance, source-artifact-identity and chain checks are each exercised as `VERIFIED`/`CONTRADICTED`/`NOT_OBSERVED`; an authorized `FOLLOW_UP` dispatches exactly one new revision (`E2`, parent `E1`, citing its producing action) that is judged again and yields `NO_FURTHER_REGISTERED_ACTION`; unauthorized, `COMPLETE`, follow-up-cap and iteration-cap attempts are refused with typed reasons and create no revision; execution records the input revision's identity hash and stays deterministic and non-mutating |
| Owning boundary | `research/*` and `jev/*` contain no persistence SQL and `JevService` never touches `repository.database`; every persistence write goes through a narrow `Repository` method inside the atomic event + registrations transaction; dangling candidate/evidence/follow-up/hypothesis provenance fails the event transaction; a `StatisticalState` source links to the attempt that supplied the response while operational attempt/cache/artifact fields never change scientific identity |
| UI | Deterministic facts and Jev judgments visibly separated; judgment vectors render full probabilities; no LLM content exists anywhere in the run |

Implemented `wide-v3` / `wide-policy-v2` gates (specification in `docs/PHASE_3_PLAN.md` §6):
projection v2 is single-cohort with no `cross_project` payload and copies deterministic state
fields; `wide-v3` validates at import and applicability matches observed/absent mutation and
expression; an out-of-roster `dominant_limitation` is rejected; the admission gate excludes
incomplete/unobserved states; threshold misses yield `ABSTAIN` with zero promotions; promotion is
capped by `PROMOTION_LIMIT`; raw answers, full Choice distribution, applicability and exclusion
reasons are retained; and failed evaluations remain auditable but cannot be promoted.

CI after implementation: Python install, Ruff, offline pytest; frontend npm ci, TypeScript typecheck, production build. Browser smoke against a local API with fixture runs; no provider credentials. Cache setup dependencies, not results that could hide missing integration. No live calls in ordinary CI. Never weaken scientific tests to obtain a pass; document any scientific method change and exclusion.

Live tests stay separate behind explicit `live_gdc` and `live_jev` opt-in markers with real
resource ceilings: `live_gdc` performs the small bounded contract probe (≤30 requests, ≤8 MiB);
`live_jev` evaluates one state with the pinned model and records usage. A full live acceptance run
uses the existing `python -m cancerjev run --live --jev` bounded LUAD path, which exercises the
anonymous GDC API and the configured Jev provider together. The Phase 4 deterministic deep slice
adds no provider and therefore no live marker: it is verified offline end-to-end with the replay
transport and stub adapter, and an optional operator-selected live acceptance
(`--deep-candidate`) is a separately approved run, not part of CI. `live_llm` is reserved for
Phase 6 and is not implemented.

## Later budget/contract tests

Adversarial loopback HTTP server: misleading/missing Content-Length, chunked body larger than 5 MiB, huge chunk declaration, partial JSON, exact-cap unknown length, compressed response despite identity request, abrupt disconnect, redirect, 401/403, 429, eligible 5xx, slow trickle. Instrument actual transport read behavior; do not mock away read-ahead when testing physical limitations.

Test per-response cap−1/cap/cap+1 against the documented 5 MiB default; run 64 MiB cap under concurrent reservations; request 150 admitted and 151 rejected; every retry/body failure charged; cache hit no network; no secret header; no larger-cap retry. Test request IDs split across groups, duplicates/aliases, project scope leakage, page 11 refusal, retry page sharing, repeated cursor, reshaped query cannot reset page cap. Test cap reductions and forbidden increases. Large/incomplete responses never produce accepted evidence.

Saved documentation-shaped fixtures are labeled synthetic, not real captures. Later authorized bounded live captures retain request/provenance/hash. Endpoint parsers separately cover search hit envelopes, aggregation envelopes, expression TSV, omitted cases, SSM/CNV multiple observations and survival groups. Unknown fields may be retained for provenance; missing required scientific fields fail the method contract.

Jev fixtures prove correct primitive construction, one request with independent questions/state, Noul no invented confidence, full Choice/Score probabilities/legend, invalid keys/sums/ranges, missing question answers, resolved-model changes, cache separation and failure preservation. Never assume identical model output on repeated network calls.

LLM tests reject measured-number fields, unresolved factual refs, unsupported actions and generated executable content. Malicious prose cannot write evidence or run code. Schema validation is not proof of semantic truth: factual dossier rendering uses deterministic references/templates.

## Scientific tests when methods are introduced

Synthetic null and known effects; weak repeated effects; direction reversal; convergence/contradiction; missingness; small-project domination; assay incompatibility; duplicate keys; zero variance; finite filtering; multiple-testing family membership; row permutation invariance; identity changes with input/membership/unit/version/family. Validate method-specific confidence intervals and inferential assumptions, not just an API success path.

Reference current CancerJEV golden-test ideas without importing its runtime. Do not treat unrun reference tests as passed in this project.

Live tests stay separate behind explicit `live_gdc`, `live_jev`, `live_llm` opt-in and phase approval, with real resource ceilings. Phase 2 verifies one small API-first route before adding more endpoints; later phases verify each provider independently before enabling a combined loop.
