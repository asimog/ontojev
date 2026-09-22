# Next.js App Router UI

CancerHawk references were inspected at commit `b87e98c76c4264acc28fa9ae920b5d3eab2637dd`. It uses Pages Router in the requested files. Carry over interaction ideas, not its routing code or backend. Source links and observations are in SOURCE_REVIEW.

Useful ideas: clickable persistent run cards; readable status badges/time/goal; frequent active-run polling; expandable stage events; model/usage context alongside judgments; visible errors with retry; final result link; filtering event categories. Improve on the reference by retaining existing cards during refresh, stable event IDs/sequences, cursor fetching, and explicit unknown-vs-zero values.

Do not carry over wallets, pay.sh, token/market/prize logic, competitive agents, publication batches, validator-role substring heuristics, full embedded log downloads, capped history, speculative fallback block fetches, forced scrolling on every event, or Pages Router static-generation APIs.

Use current stable Next.js/React/TypeScript pinned at Phase 1 implementation time. App Router owns navigation. Layout/pages are server components for shell/initial data; polling and interactive disclosure/filter controls are small client components. This follows the [official server/client component boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components). No Vercel-specific APIs are needed.

| Route | Components and behavior |
|---|---|
| `/` | SystemStatus, active RunCard, recent RunFeed, BudgetSummary, recent dossier links; includes worker stale/offline state |
| `/runs` | RunFeed → RunCard; initial loading/empty/error states; 8-second polling while visible; every autonomous run appears without a start button |
| `/runs/[runId]` | RunDetail, Pipeline, BudgetSummary, CandidateList, EventFeed, JudgmentVector; run header with version/time/status/mode; candidate and iteration filters |
| `/dossiers` | Paginated archive; entity, puzzle, creation time, run/candidate, prominent synthetic badge in fake mode |
| `/dossiers/[dossierId]` | DossierView separating observed facts, Jev judgments and generated hypotheses; provenance references and downloadable authoritative JSON/derived Markdown |
| `/system` | Worker heartbeat, data path summary, version, provider modes, budget defaults, cursor and cache summary; poll every 15 seconds |

RunCard shows all required counters: projects, requests, bytes, generated/valid/evaluated states, deep candidates, Jev calls, LLM calls, hypotheses, follow-ups, dossiers; secondary counters can expand to keep the card readable. Never label a model probability as scientific confidence. Unknown cost uses “unknown”; genuine zero uses 0.

Detail polling every 2 seconds while PENDING/RUNNING, using a completion-scheduled timeout so requests do not overlap. Fetch new events after the last accepted sequence; immediately drain continuation pages. Refresh summary in the same cycle. On terminal summary, drain through terminal sequence before stopping active polls. Abort on unmount/route change; pause hidden-tab polling, refresh on visibility restoration; bounded backoff on errors with last-good data and last-success time visible.

EventFeed renders time, stage, type, message and typed detail: GDC endpoint/bytes; state quality; Jev full answer vector; method/N/effect/p/q with unknown markers; hypothesis refs; follow-up action/outcome; dossier link. Payload expansion is lazy and bounded. Default recent-window display may retain only rendered rows for performance, but older durable events remain reachable. Use event_id keys, not array index or timestamp.

Auto-follow only when the user is already at the bottom; otherwise show a new-events affordance. `aria-live=polite` announces brief updates, not whole provider dumps. Keyboard-accessible details and controls; color plus text status indicators; readable dark palette, strong typography, responsive card stack. Use system fonts initially so build does not fetch remote fonts.

Pipeline displays run-wide discovery stages and selected candidate stage occurrences. It must represent skipped, incomplete, repeated and deferred work; a stage seen once is not automatically complete for every candidate. UI never reproduces lifecycle transition logic. Structured API state drives badges and counters.

No standalone `/autonomous-logs` is needed in Phase 1: EventFeed within run detail provides the useful behavior from that reference without duplicating a product surface. Global event search, `/candidates`, `/evaluations`, animations and extensive charting are deferred.
