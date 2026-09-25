# Repository rules

OntoJev is a bounded, deterministic-first research tool for public open-access GDC
evidence with narrow Jev semantic judgment. Work from `main`. The user's current
instructions override implementation steps embedded in reference documents.

## Current architecture (do not rebuild)

- One typed runtime chain: GDC open-access API → strict parsers → typed acquisition/lane
  records → canonical typed `StatisticalState` → deterministic Wide Jev projection
  (`jev-state-projection-v3`) → validated typed answers → Python admission (`wide-policy-v2`)
  → `Candidate` → immutable typed `EvidenceState` E0 → registered deterministic action →
  immutable revision E1/E2 → Deep Jev (`jev-evidence-projection-v2`, question set `deep-v1`)
  → Python next-move policy (`deep-policy-v2`) → optional bounded hypothesis generation
  (deterministic template by default; injected OpenRouter adapter on an explicitly authorized
  path) → Jev hypothesis critique (`jev-hypothesis-projection-v2`, question set `hypothesis-v2`)
  → dossier (schema 2).
- Systematic pre-Wide funnel (Stage 4, IMPLEMENTED): `research/discovery.py` +
  `python -m cancerjev discover --live` — fixed release-bound 1,000-gene protein-coding
  gene-id-asc `/genes` prefix (≤10 strict pages), ≤100-gene indexed mutation-count batches with
  coverage acquired once, one typed outcome/disposition per requested gene, deterministic
  `MUTATION_LUAD_AFFECTED_COUNT_DESC_V1` reduction (≤10 survivors), one immutable persisted
  `MutationDiscoveryResult` (schema 1). No provider rank, Jev, LLM, census status or hidden
  biological knowledge enters the reduction; the provider top-mutated ranking is a labelled
  comparator; Stage 4 terminates at the survivor result.
- Python domain names are unsuffixed: `StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`. Operational ids/hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialized schema versions: StatisticalState 4; EvidenceState 4; ResearchSpec 4;
  MutationDiscoveryResult 1; SQLite schema 5. Older/unknown schemas are rejected fail-closed;
  there are no migrations and no legacy readers.
- Question sets remain `wide-v3`, `deep-v1` and `hypothesis-v2`. Do not silently change their
  semantics; a new question set requires a separate versioned task and validation.
- Registered actions are exactly `CHECK_EVIDENCE_INTEGRITY_V1` (input `STATISTICAL_STATE`) and
  `CHECK_REVISION_FAITHFULNESS_V1` (input `EVIDENCE_STATE`), registry version 2. They acquire
  no data, call no model and compute no new biological quantity. `FOLLOWUP_LIMIT = 3` and
  `EVIDENCE_ITERATION_LIMIT = 2` bound one candidate arc; deep policy records exactly one typed
  move (`COMPLETE` / `FOLLOW_UP` / `GENERATE_HYPOTHESES` / `ABSTAIN`) and never dispatches it.
  Dispatch is a separate Python step requiring explicit operator authorization.
- `run --fixture demo` runs the same shared `LiveOrchestrator` offline with `FixtureTransport`
  and `FixtureJevAdapter` (mode `FIXTURE`, synthetic notice in the dossier). There is no second
  execution engine and no independent Phase-1 engine.
- One canonical `ResearchSpec`, `LUAD_RESEARCH_V1` (`domain=lung cancer`, `cohort_id=TCGA-LUAD`,
  `project_id=TCGA-LUAD`): single explicit TCGA-LUAD cohort, bounded acquisition, implemented
  composition (provider-ranked mutation discovery plus local `log2(UQFPKM+1)` expression
  summary). TCGA-LUAD and TCGA-LUSC are never pooled. Unsupported configurations are rejected
  or not representable: indexed genome-wide universe, independent expression arm and CNV
  acquisition are not implemented.
- Deleted architecture (git history is the archive): `legacy_codecs.py`, dictionary scientific
  identity payloads, `state_summary.py` / `ComputedStatisticalState` / `StateSummary`,
  `LegacyArtifact` / `LegacyMetric` / `LegacyPopulation`, `build_statistical_state`,
  schema-1/2/3 readers, the `DemoOrchestrator` independent engine (the surviving name is only
  a fixture-mode wrapper that constructs `LiveOrchestrator` with `FixtureTransport` +
  `FixtureJevAdapter`) and fake actions
  (`DROP_INFLUENTIAL_FIXTURE_POINTS_V1`), `ResearchSpecV2`/lane/universe composition contracts,
  and the retired handoff/plan/audit documents. Do not reintroduce them.
- Still absent: offline autoresearch (needs a labelled historical corpus and human review), a
  systematic multi-lane discovery architecture, and any incremental-value result. The
  independent expression arm is the next Stage 5 task in [the roadmap](docs/DISCOVERY_ROADMAP.md).

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
  measurement. Generated hypotheses never write measured fields.
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
- TypeSafe SDK retries are explicitly disabled (`RetryPolicy(max_retries=0)`), so application
  evaluation counters correspond to at most one HTTP attempt per logical evaluation. A total
  paid-model spend gate is still absent.

## Safety and evidence

- Public anonymous official GDC API only. No token, credential seeking, bulk acquisition or
  file download. `/data`, manifests and slicing are outside the allowlist.
- GDC never authenticates. Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may carry a
  provider authorization header for generated hypothesis text: the credential is environment-only,
  never persisted or logged, and its output is bounded, validated and never evidence. Pinned model
  identity is the policy requirement; current OpenRouter construction checks only non-blank identity,
  not immutability. Tightening that check is planned, not an implemented guarantee. Any other module
  adding an authorization header fails the guard test.
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
- Generated hypothesis text is never evidence and never writes a measured field. The generator seam
  defaults to deterministic behavior; the CLI may inject `OpenRouterHypothesisGenerator` using its
  environment-only credential. Provider failure or invalid required output is a typed `UNAVAILABLE`
  outcome. Unknown-field rejection and nested text/list bounds are IMPLEMENTED for hypothesis
  drafts.

## Testing

- Before writing an isolated test, state the realistic failure mode it protects. Do not write a
  unit test after implementing code merely to restate that code.
- Prefer behavioral integration/replay tests through real current subsystem boundaries for complex
  features. Mock only genuine external network seams (GDC, TypeSafe/Jev, OpenRouter). Do not mock
  an internal function just to assert another internal function called it.
- For complex work, define the important failure modes before implementation and test those
  contracts. Keep focused tests for scientific/provider/persistence invariants that E2E cannot
  localize or exhaustively protect (missing ≠ zero, NOT_ACQUIRED ≠ absence, fail-closed refusals,
  wrong state/candidate/revision binding, malformed provider payloads, terminal ledger states).
- Do not test private implementation structure, trivial wrappers, getters/setters, obvious
  constants or internal call order without semantic importance. A harmless refactor must not
  require widespread test rewrites.
- Prefer a few durable end-to-end/replay artifacts (state hash, revision chain, event sequence,
  final dossier, persisted policy result) over many implementation-coupled assertions.
- Default tests are offline. Live GDC/Jev/LLM verification is explicit, bounded and opt-in via the
  `live*` markers. Test count and coverage percentage are not quality objectives.
- Gates: FAST everyday `python -m pytest -m fast`; OFFLINE FULL `python -m pytest`;
  BROWSER `cd tests/browser && npx playwright test`;
  LIVE `python -m pytest -m "live or live_gdc or live_jev or live_llm or live_acceptance"`.

## Development skills

- GDC is the sole scientific runtime data source, including evidence supplied to hypothesis models.
- OpenAI NGS/Life Science skills are development references, not production dependencies or
  acquisition authority. Load only the skills relevant to the current task; KISS/YAGNI still govern.
- Use relevant NGS guidance for mutation, expression, CNV, QC and scientific-action design/review.
  Actual GDC contracts and admitted methods override generic bioinformatics workflow assumptions.
- Do not install or run scientific pipelines, acquire raw sequencing files, or query external
  scientific databases merely because a skill describes those steps. No external scientific
  retrieval may be added to hypothesis generation or other OntoJev runtime paths.
- Life Science Research and its router are explicit-request, reference-only resources, never a
  default project workflow. Database/literature skills must not make scientific API requests for
  OntoJev; their availability is not permission to retrieve evidence.
- Use the official TypeSafe skill and current live documentation for Jev projections, questions,
  judgments, hypothesis critique, semantic features, reranking, confidence routing and calibration.
  If deterministic code or classical statistics can answer exactly, do not use Jev.
- These are project instructions, not technical network restrictions or global plugin settings.
  The core/on-demand stage map and verification record are in [development skills](docs/DEVELOPMENT_SKILLS.md).

## Documentation

- `docs/IMPLEMENTATION_STATUS.md` is the factual source of truth. Keep it accurate.
- `docs/DISCOVERY_ROADMAP.md` indexes the next Stage 5 discovery work and evidence gates. Proposed
  lane, typed-state and acquisition-capable action contracts are not current runtime behavior.
  Historical plans are evidence only, not active implementation instructions. Do not import
  prior-project architecture into OntoJev.
- Label claims IMPLEMENTED, PLANNED or UNVERIFIED. Do not publish unverified live claims or
  claim scientific readiness from a demonstration. Changed ranking is not evidence that Jev
  improved a research decision.