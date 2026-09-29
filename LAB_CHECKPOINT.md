# Autonomous laboratory checkpoint

- Baseline HEAD: `c8e03b2a0c2e3ba8c59f13c44ab062806e255c99`.
- Objective: evolve the existing Program/Campaign system into the autonomous lung-cancer laboratory described in the supplied specification.
- Completed implementation: typed OntoCodex protocol, isolated Codex/OpenRouter adapter, immutable portfolio revisions in existing storage, ownership filtering, bounded control block, failure/no-progress handling.
- Last pushed milestone: `da3379c` (cumulative coverage and no-progress detection).
- Current milestone: measured acquisition estimates and autonomous Program ownership isolation; all 897 offline tests, Ruff and strict mypy pass.
- Decisions: models cannot write measurements; interpretations cite Python-registered evidence. No historical `data/` was inspected. Provider/model configuration reuses the existing configured model and supports an OntoCodex override. The installed harness is `codex-cli 0.157.1`.
- Verification: repository ruff and strict mypy passed (110 modules); full offline suite 894 passed, 4 deselected; frontend typecheck and production build passed; repository facts current. Real Codex 0.157.1/OpenRouter/configured DeepSeek returned a validated CREATE_QUESTION. Initial malformed live outputs were safely rejected; explicit action rules and schema in the prompt resolved the failures.
- Upstream references fetched: gdc-docs `157cef9dac084ce30720f0ad507cd54017263be7`; gdcdatamodel2 `9c6a046b96c130ea131d2ce2c9160381edd2fcc1`; gdc-workflow-overview `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e`.
- Live verification: real Codex/OpenRouter/DeepSeek and Jev control calls succeeded; run `4b9cd955-3148-4829-913c-a50253a86d93` acquired one complete CNV shard in 140 seconds, 7,045,161 GDC bytes, persisted evidence/provenance and removed its raw workspace. Prior run stopped at the 48-page transport default; the declared lab page budget and preflight admission now agree. API and Observatory visually verified on ports 8100/3100.
- Jev refinement attachment integrated: compact decision registry, scientific/control roles, experimental evaluation status, uncertainty/tie diagnostics, opt-in Noul/Choice shadow acquisition experiments, baseline replay evaluator. Wide/Deep questions are preserved pending comparative evidence; shortcomings are explicitly recorded, not called validated. New experimental answers do not influence direct OntoCodex baseline.
- Blockers: none external. Full requested transformation and Jev refinement are not complete.
- Next: bounded scientific-method integration and portfolio linkage to the existing Program/Campaign workflow.
- Continuation evidence: run `4a1f0121-6561-43ce-a84e-8a4ef4a83c43` acquired a second disjoint shard after restart. One live Choice replay agreed with direct OntoCodex (485 ms); no independent labels or repeat measurements, so no accuracy or superiority claim. Replay files are local in `.lab/replays/`.
- Live continuation `28007d68-92cc-4891-9a32-235a202df3a6` interpreted both retained shards, persisted cumulative coverage (2/585 cases, PARTIAL) and updated uncertainty at revision 8 without further acquisition.
- Live rate verification: run `56ac1052-93d8-4a1c-8e73-526028d846af` acquired a third disjoint shard (174,528 bytes / 10.656 seconds); run `39a65209-aa30-4fae-afd4-0f353dde51cc` used that measurement in preflight and interpreted the new evidence at revision 10.


## 2026-09-29: laboratory / Campaign bridge milestone

- Started from `b14bd645d55f2fa9352534f658d5641454ef8d86`; assessed code without using existing docs or `.upstream` as implementation evidence.
- Director-selected capabilities now reach canonical mutation/expression, ephemeral CNV shards, complete merge, StatisticalState composition, Wide/Candidate admission, and Candidate investigation/Stage 8 across Research Runs.
- `worker --live` now invokes the lab supervisor. The 600-second ceiling and shadow control Jev remain.
- Docker build succeeded; a network-isolated container invoked the installed Codex CLI through a local Responses replay and produced a typed director decision. Default provider/model identity was verified as OpenRouter / `deepseek/deepseek-v4.1-flash`. This was not a live provider or scientific validation.
- Working-tree verification: Ruff, strict mypy, repository facts, full offline pytest (907 passed, 4 deselected), frontend typecheck/build. The strengthened cross-run binding regression is also checked separately.
- Existing user modifications were preserved and are excluded from this milestone's commit.
- Remaining: fine-grained mutation/expression checkpoints, separately selected Candidate substeps, isolated capability-gap engineering and activation, replication adapters, exhaustive interrupted-publication recovery, and live scientific/deployment validation. See `docs/LAB_CAMPAIGN_BRIDGE.md`.
