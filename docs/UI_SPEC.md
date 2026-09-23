# Next.js App Router UI

CancerHawk references were inspected at commit `b87e98c76c4264acc28fa9ae920b5d3eab2637dd`. It uses Pages Router in the requested files. Carry over interaction ideas, not its routing code or backend. Source links and observations are in SOURCE_REVIEW.

Useful ideas: clickable persistent run cards; readable status badges/time/goal; frequent active-run polling; expandable stage events; model/usage context alongside judgments; visible errors with retry; final result link; filtering event categories. Improve on the reference by retaining existing cards during refresh, stable event IDs/sequences, cursor fetching, and explicit unknown-vs-zero values.

Do not carry over wallets, pay.sh, token/market/prize logic, competitive agents, publication batches, validator-role substring heuristics, full embedded log downloads, capped history, speculative fallback block fetches, forced scrolling on every event, or Pages Router static-generation APIs.

Use current stable Next.js/React/TypeScript pinned at Phase 1 implementation time. App Router owns navigation. Layout/pages are server components for shell/initial data; polling and interactive disclosure/filter controls are small client components. This follows the [official server/client component boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components). No Vercel-specific APIs are needed.

| Route | Components and behavior |
|---|---|
| `/` | SystemStatus, active RunCard, recent RunFeed, BudgetSummary, recent dossier links; includes worker stale/offline state |
| `/runs` | RunFeed → RunCard; initial loading/empty/error states; 8-second polling while visible; every autonomous run appears without a start button; cursor "Load more runs" keeps all durable history reachable |
| `/runs/[runId]` | RunDetail, Pipeline, BudgetSummary, DeterministicStatePanel, DeepEvidencePanel, WideRanking, CandidateList, EventFeed, JudgmentVector; run header with version/time/status/mode (`FAKE`/`LIVE`); candidate and iteration filters; run-scoped state remounts when the routed run changes |
| `/dossiers` | Paginated archive; entity, puzzle, creation time, run/candidate, prominent synthetic badge in fake mode; the load-more control disappears permanently once the final page reports no cursor |
| `/dossiers/[dossierId]` | DossierView separating observed facts, Jev judgments and generated hypotheses; provenance references (artifact id and served SHA-256) and downloadable authoritative JSON/derived Markdown |
| `/system` | Worker heartbeat, data path summary, version, provider modes, effective GDC/Jev budget limits, real usage counters, cursor and cache summary (entries, bytes, hit rate); poll every 15 seconds |

RunCard shows all required counters: projects, requests, bytes, generated/valid/evaluated states, deep candidates, Jev calls, LLM calls, hypotheses, follow-ups, dossiers; secondary counters can expand to keep the card readable. Never label a model probability as scientific confidence. Unknown cost uses “unknown”; genuine zero uses 0. A live run’s GDC request/byte counters come from the attempt ledger projection, not from parsing console text.

## Deterministic facts vs Jev judgments (Phase 2/3)

The run detail keeps the two record families visually and structurally separate, and the API never merges them:

- **DeterministicStatePanel** renders real StatisticalState v2 fields from the state artifact: entity identity, project scope, examined/observed populations, mutation counts and coverage, local and provider expression summaries, cross-project descriptives, missingness and method/source refs. Availability is always rendered: `OBSERVED` with a number, `NOT_OBSERVED`, `PARTIAL`, `NOT_ACQUIRED`, or `INSUFFICIENT`. A `NOT_OBSERVED` mutation count renders as “not observed”, never as 0. Provider `_score` is shown only inside a clearly labeled “selection metadata” chip.
- **WideRanking** shows the deterministic baseline ranking and the Jev ranking side by side for the same states, with the policy version, each state’s raw dimensions, and which candidates were admitted. The two rankings are never merged into one opaque score.
- **JudgmentVector** renders each primitive against its contract: Noul probability in [0,1] with the proposition text; Choice with the chosen option from the question roster, the full probability map and `confidence`; Score against its declared rubric with the selected level, the distribution over levels, the probability-weighted expected value and the legend. Applicability is shown per question; an inapplicable answer is marked and visually de-emphasized, not hidden.
- Jev panels carry a persistent “JEV JUDGMENT — not a measurement” label; deterministic panels carry “DETERMINISTIC — measured”. A Jev probability is never rendered with units, error bars, p-values or a scientific-confidence label.

JudgmentVector and the ranking panel consume only persisted evaluation records and ranking artifacts; the UI recomputes nothing and never invokes a provider. EventFeed additionally renders the GDC request lifecycle (endpoint, status, bytes, cache hit, budget-limit events) and the projection/ranking events with artifact refs.

JudgmentVector renders each primitive against its contract: Noul probability in [0,1]; Choice with the chosen option from the question roster and the full probability map; Score against the 0..4 rubric with the selected level shown as `selected / 4`, the distribution over the rubric levels, the probability-weighted expected value and the selected level's legend text.

Detail polling every 2 seconds while PENDING/RUNNING, using a completion-scheduled timeout so requests do not overlap. Fetch new events after the last accepted sequence; immediately drain continuation pages. Refresh summary in the same cycle. On terminal summary, drain through terminal sequence before stopping active polls. Abort on unmount/route change; pause hidden-tab polling, refresh on visibility restoration; bounded backoff on errors with last-good data and last-success time visible.

EventFeed renders time, stage, type, message and typed detail: GDC endpoint/bytes; state quality; Jev full answer vector; method/N/effect/p/q with unknown markers; hypothesis refs; follow-up action/outcome; dossier link. Payload expansion is lazy and bounded. Default recent-window display may retain only rendered rows for performance, but older durable events remain reachable. Use event_id keys, not array index or timestamp. Each rendered event also carries its durable `event_id` as a `data-event-id` attribute so browser tests and debugging can compare the rendered feed with the API record.

Auto-follow only when the user is already at the bottom; otherwise show a new-events affordance. `aria-live=polite` announces brief updates, not whole provider dumps. Keyboard-accessible details and controls; color plus text status indicators; readable dark palette, strong typography, responsive card stack. Use system fonts initially so build does not fetch remote fonts.

Pipeline displays run-wide discovery stages and selected candidate stage occurrences. It must represent skipped, incomplete, repeated and deferred work; a stage seen once is not automatically complete for every candidate. UI never reproduces lifecycle transition logic. Structured API state drives badges and counters.

No standalone `/autonomous-logs` is needed: EventFeed within run detail provides the useful behavior from that reference without
duplicating a product surface. Global event search, `/candidates`, `/evaluations`, animations and extensive charting are deferred. Deep evidence,
hypotheses and dossier panels remain available for fixture runs; for live runs the deep evidence panel is populated only when an operator
explicitly selected a candidate (`--deep-candidate`), and the hypothesis/dossier panels stay empty until later phases are approved.

**DeepEvidencePanel** lists the run's immutable evidence revisions (iteration, parent revision, action, per-check verified/contradicted/not-observed
counts, evidence hash, and the deep Jev judgment attached to each revision) and expands one revision through `/api/evidence/{id}` to show each
deterministic check outcome, its claim, its `n_effective` and its availability. Wide and deep judgments are separated by `purpose`, so a deep
judgment is never rendered in the wide judgment panel, and no judgment is rendered as a measurement. A check outcome is never displayed as a
probability or confidence, `NOT_OBSERVED` is displayed explicitly rather than as a zero, and the panel states that the deep judgment is an input
to the Python next-move policy (recorded in the event stream as `NEXT_MOVE_SELECTED`) and that wide admission never dispatches a follow-up itself.
