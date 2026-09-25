# Next.js App Router UI

This is a presentation specification, not an independent scientific-status authority.
`apps/web/` consumes the versioned read API (current API version in
[REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)); the API/record contract it consumes is
IMPLEMENTED, while the renderer behavior described here is the specified target and is
UNVERIFIED in this environment except where the browser acceptance suite exercises it. The UI
is an observatory over committed records only: it never initiates research, never writes
through the research path, and never influences the system-owned autonomous program at
runtime. OntoJev does not inherit prior-project architecture.

Useful behaviors: clickable persistent run cards; readable status badges/time/goal; frequent
active-run polling; expandable stage events; model/usage context alongside judgments; visible
errors with retry; final result link; filtering event categories. Retain existing cards during
refresh, stable event IDs/sequences, cursor fetching, and explicit unknown-versus-zero values.

Do not carry over wallets, pay.sh, token/market/prize logic, competitive agents, publication
batches, validator-role substring heuristics, full embedded log downloads, capped history,
speculative fallback block fetches, forced scrolling on every event, or Pages Router
static-generation APIs.

Use current stable Next.js/React/TypeScript pinned at implementation time. App Router owns
navigation. Layout/pages are server components for shell/initial data; polling and interactive
disclosure/filter controls are small client components, following the
[official server/client component boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components).
No Vercel-specific APIs are needed.

| Route | Components and behavior |
|---|---|
| `/` | SystemStatus, active RunCard, recent RunFeed, BudgetSummary, recent dossier links; includes worker stale/offline state |
| `/runs` | RunFeed → RunCard; initial loading/empty/error states; 8-second polling while visible; every autonomous run appears without a start button; cursor “Load more runs” keeps all durable history reachable |
| `/runs/[runId]` | RunDetail, Pipeline, BudgetSummary, DeterministicStatePanel, DeepEvidencePanel, WideRanking, CandidateList, EventFeed, JudgmentVector; run header with version/time/status/mode (`FIXTURE`/`LIVE`); candidate and iteration filters; run-scoped state remounts when the routed run changes |
| `/dossiers` | Paginated archive; entity, puzzle, creation time, run/candidate, prominent synthetic badge in fixture mode; the load-more control disappears permanently once the final page reports no cursor |
| `/dossiers/[dossierId]` | DossierView separating observed facts, Jev judgments and generated hypotheses; provenance references (artifact id and served SHA-256) and downloadable authoritative JSON/derived Markdown |
| `/system` | Worker heartbeat, data path summary, version, provider modes, effective GDC/Jev budget limits, real usage counters, cursor and cache summary; poll every 15 seconds |

RunCard shows all required counters: projects, requests, bytes, generated/valid/evaluated
states, deep candidates, Jev calls, LLM calls, hypotheses, follow-ups, dossiers; secondary
counters can expand to keep the card readable. Never label a model probability as scientific
confidence. Unknown cost uses “unknown”; genuine zero uses 0. A live run's GDC request/byte
counters come from the attempt ledger projection, not from parsing console text.

## Deterministic facts vs Jev judgments

The run detail keeps the two record families visually and structurally separate, and the API
never merges them:

- **DeterministicStatePanel** renders the typed `StatisticalState` presentation payload
  (versioned presentation schema; current version in
  [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md)): entity identity, project scope,
  examined/observed populations,
  mutation counts and coverage, local and provider expression summaries, missingness and
  method/source refs. Availability is always rendered: `OBSERVED` with a number, `NOT_OBSERVED`,
  `PARTIAL`, `NOT_ACQUIRED`, or `INSUFFICIENT`. A `NOT_OBSERVED` mutation count renders as “not
  observed”, never as 0. Provider `_score` is shown only inside a clearly labeled “selection
  metadata” chip.
- **WideRanking** shows the deterministic baseline ranking and the Jev ranking side by side for
  the same states, with the policy version, each state's raw dimensions, and which candidates
  were admitted. The two rankings are never merged into one opaque score.
- **JudgmentVector** renders each primitive against its contract: Noul probability in [0,1] with
  the proposition text; Choice with the chosen option from the question roster, the full
  probability map and `confidence`; Score (when a future question set uses it) against its
  declared rubric with the selected level shown as `selected / N`, the distribution over levels,
  the probability-weighted expected value and the legend. Applicability is shown per question;
  an inapplicable answer is marked and visually de-emphasized, not hidden.
- Jev panels carry a persistent “JEV JUDGMENT — not a measurement” label; deterministic panels
  carry “DETERMINISTIC — measured”. A Jev probability is never rendered with units, error bars,
  p-values or a scientific-confidence label.

JudgmentVector and the ranking panel consume only persisted evaluation records and ranking
artifacts; the UI recomputes nothing and never invokes a provider. EventFeed additionally renders
the GDC request lifecycle (endpoint, status, bytes, cache hit, budget-limit events) and
projection/ranking events with artifact refs.

Detail polling every 2 seconds while PENDING/RUNNING, using a completion-scheduled timeout so
requests do not overlap. Fetch new events after the last accepted sequence and immediately drain
continuation pages. Refresh the summary in the same cycle. On terminal summary, drain through the
terminal sequence before stopping active polls. Abort on unmount/route change; pause hidden-tab
polling and refresh on visibility restoration; use bounded backoff on errors with last-good data
and last-success time visible.

EventFeed renders time, stage, type, message and typed detail: GDC endpoint/bytes; state quality;
Jev full answer vector; method/N/effect/p/q with unknown markers; hypothesis refs; follow-up
action/outcome; dossier link. Payload expansion is lazy and bounded. Use `event_id` keys, not
array index or timestamp. Each rendered event carries its durable `event_id` as a
`data-event-id` attribute so browser tests and debugging can compare the rendered feed with the
API record.

Auto-follow only when the user is already at the bottom; otherwise show a new-events affordance.
`aria-live=polite` announces brief updates, not whole provider dumps. Keyboard-accessible details
and controls; color plus text status indicators; readable dark palette, strong typography,
responsive card stack. Use system fonts initially so the build does not fetch remote fonts.

Pipeline displays run-wide discovery stages and selected candidate stage occurrences. It must
represent skipped, incomplete, repeated and deferred work; a stage seen once is not automatically
complete for every candidate. The UI never reproduces lifecycle transition logic. Structured API
state drives badges and counters.

No standalone `/autonomous-logs` is needed: EventFeed within run detail provides that behavior
without duplicating a product surface. Global event search, `/candidates`, `/evaluations`,
animations and extensive charting are deferred. Deep evidence, hypotheses and dossier panels
remain available for fixture runs. Live evidence requires an operator-selected candidate
(`--deep-candidate`); authorized investigation arcs can produce hypotheses and live dossiers.
Render their recorded availability, not a blanket assumption that later stages are absent.

**Live hypotheses and dossier**: for a live run, generated statements render in their own
section labelled “GENERATED HYPOTHESES — NOT EVIDENCE” with the generator, statement,
hypothetical mechanism and falsification criteria, and never inside the wide judgment panel; a
live dossier renders as a “DOSSIER READY” callout linking to `/dossiers/{id}`, whose
authoritative JSON carries the live notice and a per-section availability.

## Researcher Lab boundary (future, isolated)

The researcher-facing UI is an observatory/configuration surface only, separate from the
autonomous backend loop. An optional future Researcher Lab may let researchers compose and run
isolated investigations on the same scientific engine; its state, evidence, candidates,
hypotheses and results are stored and rendered separately from the system-owned autonomous
program at runtime, and researcher activity cannot influence the autonomous program at
runtime (influence on future autonomous behavior occurs only through an explicit versioned
code/scientific change outside runtime). Researcher Lab surfaces must therefore never share
candidate queues, promotion slots, evidence revisions or dossiers with autonomous runs, and
must never acquire authority to start, stop or shape the autonomous loop. Researcher initiation
is never required for autonomous operation.

## Known stale runtime labels (documented, not fixed here)

Small presentation/runtime text mismatches exist and are recorded rather than silently
ignored; fixing them is a separate UI/API task, not this documentation contract: the
`/api/system` payload still reports a historical `phase: 3` field, the site header renders
“PHASE 3 · OPEN GDC + JEV”, and the site footer still says “no LLM hypotheses” although
bounded generated hypotheses exist on the explicitly authorized path. API consumers must not
treat these labels as capability discovery (see [API contract](API_CONTRACT.md)).

**DeepEvidencePanel** lists the run's immutable evidence revisions (iteration, parent revision,
action, per-check verified/contradicted/not-observed counts, evidence hash, and the deep Jev
judgment attached to each revision) and expands one revision through `/api/evidence/{id}` to show
each deterministic check outcome, its claim, its `n_effective` and its availability. A dispatched
action simply appears as one more revision whose parent is the previous one, so no new surface is
required. Wide and deep judgments are separated by `purpose`, so a deep judgment is never
rendered in the wide judgment panel, and no judgment is rendered as a measurement. A check
outcome is never displayed as a probability or confidence, `NOT_OBSERVED` is displayed
explicitly rather than as a zero, and the panel states that the deep judgment is an input to the
Python next-move policy (recorded as `NEXT_MOVE_SELECTED`, with dispatch attempts recorded as
`NEXT_MOVE_DISPATCHED`) and that wide admission never dispatches a follow-up itself.