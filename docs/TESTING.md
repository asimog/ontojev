# Verification strategy

This is a test plan, not a report of executed application tests. Phase 0 has no application runtime. Use focused tests first, then the full relevant offline checks once a phase is implemented. No default test, build or CI command contacts GDC, TypeSafe or an LLM.

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

Acceptance requires all twelve Phase 1 criteria from the master specification, including worker-restart integrity and no Postgres/Redis/Docker dependency. Browser smoke is essential, not replaced by typecheck. Terminal status and dossier links must be tested under polling races.

Small CI after implementation: Python install, Ruff, offline pytest; frontend npm ci, TypeScript typecheck, production build. Browser test can run against local API/web fixtures; no provider credentials. Cache setup dependencies, not results that could hide missing integration. No live calls in ordinary CI.

## Later budget/contract tests

Adversarial loopback HTTP server: misleading/missing Content-Length, chunked body larger than5MiB, huge chunk declaration, partial JSON, exact-cap unknown length, compressed response despite identity request, abrupt disconnect, redirect, 401/403, 429, eligible5xx, slow trickle. Instrument actual transport read behavior; do not mock away read-ahead when testing physical limitations.

Test per-response cap-1/cap/cap+1; run64MiB cap under four concurrent reservations; request150 admitted and151 rejected; every retry/body failure charged; cache hit no network; no secret header; no larger-cap retry. Test request IDs split across groups, duplicates/aliases, project scope leakage, page11 refusal, retry page sharing, repeated cursor, reshaped query cannot reset page cap. Test cap reductions and forbidden increases. Large/incomplete responses never produce accepted evidence.

Saved documentation-shaped fixtures are labeled synthetic, not real captures. Later authorized bounded live captures retain request/provenance/hash. Endpoint parsers separately cover search hit envelopes, aggregation envelopes, expression TSV, omitted cases, SSM/CNV multiple observations and survival groups. Unknown fields may be retained for provenance; missing required scientific fields fail the method contract.

Jev fixtures prove correct primitive construction, one request with independent questions/state, Noul no invented confidence, full Choice/Score probabilities/legend, invalid keys/sums/ranges, missing question answers, resolved-model changes, cache separation and failure preservation. Never assume identical model output on repeated network calls.

LLM tests reject measured-number fields, unresolved factual refs, unsupported actions and generated executable content. Malicious prose cannot write evidence or run code. Schema validation is not proof of semantic truth: factual dossier rendering uses deterministic references/templates.

## Scientific tests when methods are introduced

Synthetic null and known effects; weak repeated effects; direction reversal; convergence/contradiction; missingness; small-project domination; assay incompatibility; duplicate keys; zero variance; finite filtering; multiple-testing family membership; row permutation invariance; identity changes with input/membership/unit/version/family. Validate method-specific confidence intervals and inferential assumptions, not just an API success path.

Reference current CancerJEV golden-test ideas without importing its runtime. Do not treat unrun reference tests as passed in this project.

Live tests stay separate behind explicit `live_gdc`, `live_jev`, `live_llm` opt-in and phase approval, with real resource ceilings. Phase 2 verifies one small API-first route before adding more endpoints; later phases verify each provider independently before enabling a combined loop.
