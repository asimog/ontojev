# Repository rules

OntoJev is a bounded, deterministic-first research tool for public open-access GDC
evidence with narrow Jev semantic judgment. Work from `main`. The user's current
instructions override implementation steps embedded in reference documents.

## Current state (do not rebuild)

- Phase 1 offline synthetic fixture slice exists (`run --fixture demo`).
- Phase 2 real open-access GDC evidence and deterministic StatisticalStates exist.
- Phase 3 single-cohort Wide Jev integration exists: `jev-state-projection-v2`, `wide-v3`,
  deterministic admission/abstention, baseline/Jev rankings, and bounded candidate promotion.
- `LUAD_RESEARCH_V1` (`domain=lung cancer`, `cohort_id=TCGA-LUAD`, `project_id=TCGA-LUAD`)
  is the only production `ResearchSpec`. TCGA-LUAD and TCGA-LUSC are never pooled.
- `wide-v2` is retained only for historical evaluations. Do not silently change `wide-v3` semantics;
  a new question set requires a separate versioned task and validation.

## Ownership boundaries

- `ResearchSpec` owns reproducible research configuration (domain, cohort, project, bounded
  page/batch sizes, cohort ceiling, discovery/candidate limits).
- `Settings` owns operational configuration (paths, timeouts, transport budgets, cache,
  provider/model). Never mix the two.
- GDC stays generic and bounded: it may know project/case/gene IDs, sizes, offsets and
  endpoint contracts; it must not know lung-cancer policy, LUAD biology or Jev routing.
  Endpoint allowlists, allowed fields, open-access enforcement, parsers and absolute safety
  caps live in code, not in `ResearchSpec`. No runtime-configurable arbitrary GDC queries.
- Deterministic code owns measurements: populations, counts, missingness, transforms,
  eligibility, budgets. Jev owns narrow atomic semantic judgment and never computes a
  measurement. LLM hypothesis generation is future work and never writes measured fields.
- Python owns loops, routing, state transitions, budgets, side effects, action eligibility,
  stopping and abstention. Jev/LLM outputs are inputs to Python policy, never control flow.

## Safety and evidence

- Public anonymous official GDC API only. No token, credential seeking, bulk acquisition or
  file download. `/data`, manifests and slicing are outside the allowlist.
- Respect the caps in `docs/GDC_BUDGETS.md`. Never enlarge a limit to finish work.
- Missing is not negative; unavailable mutation evidence is not wild type; a missing
  expression column is not zero. Never hide partial retrieval.
- Preserve source requests, response hashes, examined populations, sample/workflow context,
  tested families, method versions and missingness. Evidence is immutable; revisions are new
  states. Provider ranking metadata never fills a measured field.
- One canonical RunEvent stream. CLI and UI consume committed records; no second status
  authority and no console-text parsing.

## Engineering

- Ordinary Python, standard library first. KISS, DRY, YAGNI. Prefer small explicit functions
  and narrow adapters. Before each abstraction ask: "Is there a simpler design?"
- Do not scaffold future phases without a current requirement: no agent frameworks, planner
  objects, graph/workflow engines, plugin systems, distributed queues or new repositories for
  concepts that a Python function or a new bounded `ResearchRun` can express.
- Default tests are offline and must not contact GDC, TypeSafe/Jev or an LLM. Run focused
  tests before broader checks. Never weaken a scientific test to obtain a pass.

## Documentation

- `docs/IMPLEMENTATION_STATUS.md` is the factual source of truth. Keep it accurate.
- Label claims IMPLEMENTED, PLANNED or UNVERIFIED. Do not publish unverified live claims or
  claim scientific readiness from a demonstration. Changed ranking is not evidence that Jev
  improved a research decision.
