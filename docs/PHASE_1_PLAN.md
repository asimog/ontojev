# Phase 1 implementation plan — approval required

Goal: one fully observable fake autonomous loop with durable event history and a fake dossier. No live GDC, Jev or LLM. No production implementation has begun.

1. **Scaffold only the Phase 1 tree.** Pin Python/frontend dependencies; configure data directory, fake-only modes and hard work limits. Add `.gitignore`, `.env.example`, packaging entry point and minimal offline CI. Validate installation and module entry point from outside the repository.
2. **Implement domain contracts and one event writer.** Run/candidate transitions, payload union, immutable state contracts, lifetime budgets, strict serialization, SQLite bootstrap/WAL and projection reducer. Prove event transaction rollback, sequence allocation, idempotency and state hash invariants.
3. **Add local artifacts and process ownership.** Atomic publish ordering, checksums, narrow repositories, lock, heartbeat and interrupted-run reconciliation. Test with actual separate processes and induced failure boundaries.
4. **Connect the fake research loop and CLI.** One fixture-driven run traverses all stages, preserves fake Jev vectors, generates competing fixture hypotheses, performs one registered deterministic fixture action, appends new evidence, publishes JSON/Markdown dossier. Render console output from committed events. Add bounded repeated fake worker mode and graceful Ctrl+C.
5. **Expose the read API.** Implement the exact API contract with bounded pagination, consistent high-water marks, summary counters, artifact access, system status and redaction. A started API never starts a research run.
6. **Build App Router UI.** Overview, run feed/detail, dossiers and system; shared polling hook; cards, stage occurrences, typed events, candidate views, Jev probabilities and provenance. Fake mode remains visibly labeled. No deployment SDKs or extra state framework.
7. **Prove the complete local story.** Run focused tests then Ruff/offline pytest/typecheck/build; start local API and web; trigger CLI demo; verify card, live events/stages, dossier, refresh, API restart, researcher crash/restart and canonical-event consistency in a browser. Report exclusions honestly.
8. **Update phase report and stop.** Record files, decisions, scientific scope, tests/results, external calls and actual GDC/Jev/LLM usage (all zero), limitations and next phase. Phase 2 is a separate approval boundary.

Acceptance matrix:

| Master criterion | Planned evidence |
|---|---|
| Local FastAPI and Next.js start | Process health plus browser load |
| `python -m cancerjev run --fixture demo` works | Installed entry point integration test |
| Run card appears automatically | Browser waits for newly created run ID |
| Live stages and log progress | Multiple nonterminal event batches observed |
| CLI and UI share RunEvents | Compare stored event IDs/sequences through both interfaces |
| Fake dossier under /dossiers | JSON and readable view, synthetic label |
| Refresh preserves state | Reload during run and after completion |
| API restart preserves state | Restart server and reread identical durable history |
| Worker restart cannot corrupt history | Kill owner, restart, preserve old run + create new run |
| No forbidden infrastructure | Clean local dependency/process inventory |

Do not build real endpoint adapters, production scientific methods, provider SDK integrations, generated-prose dossiers, advanced composite ranking or the Jev value benchmark during Phase 1. Their contracts exist so fixtures test the right boundaries; their real behavior comes in later approved phases.
