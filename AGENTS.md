# OntoJev

OntoJev is an autonomous computational cancer target-discovery system.

## Core rules

- Human bounds the lung-cancer domain; OntoCodex directs research and synthesis.
- Python computes measurements, validates proposed actions and executes within hard limits.
- Jev supplies bounded typed judgments, never measurements. Research-control judgments are not biological evidence; consequential uses require independent evaluation.
- GDC/GDAN evidence → strict parsing → validated deterministic methods → typed evidence → bounded judgment/synthesis → immutable scientific revisions.
- Missing != negative. Hypothesis != evidence. Never send uncontrolled raw genomics to Jev or OntoCodex.
- Prefer established GDC/GDAN/TCGA/NCI methods. Core science stays cancer-agnostic; LUAD is a Campaign profile.
- Preserve the existing Program/Campaign/StatisticalState/Candidate/EvidenceState/Stage 8/dossier spine; no parallel scientific-state architecture.
- Research Runs are bounded execution units, normally <=10 minutes. Campaigns may span many runs.
- Persist and verify derived evidence plus reacquisition provenance before successful raw-shard cleanup; recover failed/interrupted workspace cleanup.
- Researcher runs cannot influence autonomous state at runtime.
- No generic agent framework, DAG engine, microservices or model-generated GDC queries.
- Verify each implementation unit before commit: project-environment `python -m ruff check .`, strict `python -m mypy`, `python -m tests.repository_facts check`, and full default offline `python -m pytest`; use focused fixture/replay checks before live calls. Update affected canonical docs with each milestone.

## Operational limits

- GDC file-download limits and API request/byte limits are test controls, not sacred scientific constants. They may be raised or lowered for testing and declared runs through documented constants — never ad hoc, never silently, and never as per-response caps.
- Adjusting a limit must not change failure semantics: exhausted budgets still report incomplete or unavailable, never a smaller population labelled complete.
- Only open-access data may ever be used. Never use controlled-access or restricted data, and never add GDC credentials or tokens.

## Sources

For GDC work, inspect current upstream sources first:

- https://github.com/NCI-GDC/gdc-docs
- https://github.com/NCI-GDC/gdcdatamodel2
- https://github.com/NCI-GDC/gdc-workflow-overview
- relevant NCI-GDC tool/workflow repositories

Use `gdcdatamodel2` as the GDC data-model authority.

Clone upstream references into an untracked `.upstream/` workspace and record exact SHAs.

## Before changing code

1. Record current HEAD.
2. Inspect the current implementation independently.
3. Verify prompt assumptions against code and upstream sources.
4. Rewrite the implementation plan if the prompt is stale.
5. Make one bounded scientific change.
6. Prefer fixture/replay verification before live dependencies.
7. Keep current, planned and target behavior distinct.

Mutable schema/action/version facts belong in code, not here.
