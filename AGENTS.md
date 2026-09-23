# Repository rules

OntoJev is a bounded, deterministic-first research tool for public open-access GDC
evidence with narrow Jev semantic judgment. Work from `main`. The user's current
instructions override implementation steps embedded in reference documents.

## Current state (do not rebuild)

- Phase 1 offline synthetic fixture slice exists (`run --fixture demo`).
- Phase 2 real open-access GDC evidence and deterministic StatisticalStates exist.
- Phase 3 single-cohort Wide Jev integration exists: `jev-state-projection-v2`, `wide-v3`,
  deterministic admission/abstention, baseline/Jev rankings, and bounded candidate promotion.
- The Phase 4 first deterministic slice exists: `CHECK_EVIDENCE_INTEGRITY_V1` on a promoted
  candidate's accepted StatisticalState E0 produces an immutable EvidenceState revision E1. It is
  reachable only through an explicit operator selection (`run --live --jev --deep-candidate
  <gene|gene:SYM|state:ID|slot:N>`); wide admission never dispatches a follow-up, and the slice
  acquires no evidence and calls no model.
- One Deep Jev fan-out over E1 exists (`deep-v1`, `jev-evidence-projection-v1`), followed by the
  deterministic Python next-move policy (`deep-policy-v2`) which records exactly one typed move
  (`COMPLETE`/`FOLLOW_UP`/`ABSTAIN`) and never dispatches it. Jev judges; Python decides.
- A recorded `FOLLOW_UP` can be dispatched as at most one further immutable revision (`E2`), and only
  when the operator authorizes it explicitly (`run --live --jev --deep-candidate <sel> --deep-followup`);
  a second registered action (`CHECK_REVISION_FAITHFULNESS_V1`, input kind `EVIDENCE_STATE`) makes that
  dispatch possible, the existing follow-up/revision caps still apply, and the new revision is judged
  again by the same deep fan-out.
- A bounded investigation arc exists: after E1 the same run may dispatch further distinct eligible
  revision actions while an operator authorization is in force and the follow-up/revision caps allow,
  judging each new revision exactly once. Generated hypotheses follow the same rule: deterministic by
  default, bounded, labelled, judged under `hypothesis-v2`, and produced by an injected generator only;
  this repository performs no model request and holds no provider credential. Each investigated
  candidate ends with a live dossier.
- Still absent: Phase 7 offline autoresearch (needs a labelled historical corpus and human review), a
  concrete LLM provider adapter, and any incremental-value result.
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
  stopping and abstention. Jev/LLM outputs are inputs to Python policy, never control flow. A Jev
  judgment never selects, authorizes or executes an action, and a recorded next move is never
  dispatched by the policy that recorded it.
- Deterministic follow-up actions are registered in code with an explicit contract (question,
  falsifiable interpretation, method/version, unit, required evidence, limitations) and a declared
  input kind (`STATISTICAL_STATE` or `EVIDENCE_STATE`). They acquire no data, call no model, compute no
  new biological quantity and never rewrite the evidence they read; an action failure is a typed
  outcome that promotes nothing. New actions require a concrete operation, not foresight.
- `storage` is the only layer that writes SQL. `research` and `jev` register records through
  narrow `Repository` methods inside the same event + registrations transaction; they must not
  contain raw SQL or touch `repository.database`. No ORM, DAO hierarchy or second repository.
- Jev cache reuse requires a pinned/versioned model identity whose provider resolution equals
  it; a mutable model alias is always evaluated and never treated as already resolved.

## Safety and evidence

- Public anonymous official GDC API only. No token, credential seeking, bulk acquisition or
  file download. `/data`, manifests and slicing are outside the allowlist.
- GDC never authenticates. Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may carry a
  provider authorization header for generated hypothesis text: the credential is environment-only,
  never persisted or logged, the model must be a pinned identity, and its output is bounded, validated
  strictly and never evidence. Any other module adding an authorization header fails the guard test.
- Respect the caps in `docs/GDC_BUDGETS.md`. Never enlarge a limit to finish work.
- Missing is not negative; unavailable mutation evidence is not wild type; a missing
  expression column is not zero. Never hide partial retrieval.
- Preserve source requests, response hashes, examined populations, sample/workflow context,
  tested families, method versions and missingness. Evidence is immutable; revisions are new
  states. Provider ranking metadata never fills a measured field.
- Every GDC attempt that started reaches a terminal ledger status, and a
  `StatisticalState` source links to the attempt that supplied its response. Operational
  attempt/cache/artifact ids and timestamps never enter scientific identity.
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
- Generated hypothesis text is never evidence and never writes a measured field. This repository
  performs no model request and holds no provider credential: a model is only ever reached through a
  generator injected by the caller, and its output is validated strictly or rejected as a typed
  `UNAVAILABLE` outcome.

## Documentation

- `docs/IMPLEMENTATION_STATUS.md` is the factual source of truth. Keep it accurate.
- Label claims IMPLEMENTED, PLANNED or UNVERIFIED. Do not publish unverified live claims or
  claim scientific readiness from a demonstration. Changed ranking is not evidence that Jev
  improved a research decision.
