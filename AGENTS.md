# Repository rules

OntoJev is an autonomous computational-genomics target-discovery system composed of bounded,
reproducible research campaigns over public open-access GDC evidence: deterministic genomic
analysis creates structured evidence, Jev makes narrow semantic judgments about potentially
interesting patterns, bounded LLM-generated hypotheses are proposed where useful and critiqued
by Jev, and Python controls all execution and evidence creation. Work from `main`. The user's
current instructions override implementation steps embedded in reference documents.

## Scientific invariants (never negotiable)

- Raw genomics never goes to Jev: `raw genomics → strict parsing → deterministic
  computational genomics → typed genomic features → Jev`.
- `Jev judges. Python decides. Python executes.` Jev/LLM outputs are inputs to Python policy,
  never control flow; they never compute measurements, select or execute actions, authorize
  acquisition, or create evidence.
- Missing is not negative; unavailable mutation evidence is not wild type; a missing
  expression column is not zero; absence is not a neutral result. Never hide partial retrieval.
- Discovery is not mutation-conditioned: each modality (mutation, expression, CNV)
  independently preserves genes; a gene need not be mutation-significant for expression or CNV
  evidence to contribute.
- The system discovers **potential importance** of target candidates; it does not establish
  biological significance, dependency, druggability, efficacy or clinical value.

## Primary execution model

- The primary product is a **system-owned autonomous research program** made of bounded,
  independently reproducible campaigns: bounded campaign → multi-modal target discovery →
  target investigation → Stage 8 finalization → campaign complete → next bounded campaign.
  Never describe or build this as one infinite run.
- Researchers are an optional, isolated future route (Researcher Lab). Researcher-run state,
  evidence, candidates, hypotheses and results are isolated from the autonomous program at
  runtime. Testable rule: researcher activity cannot influence the system-owned autonomous
  program at runtime; any influence on future autonomous behavior must occur through an
  explicit versioned code/scientific change outside runtime. This does not claim humans can
  never influence the project.
- Today's CLI operator controls (deep-candidate selection, follow-up authorization,
  hypothesis generation) are explicit, recorded manual paths. The autonomous-program target
  is a runtime that requires no human control of candidate selection, Jev promotion,
  follow-up selection, hypothesis approval, iteration authorization or candidate completion,
  with manual CLI controls remaining only as debug overrides. That reorientation is the
  provisional Stage 9 direction, subject to the source-grounded Stage 9 design reviews.

## Source-of-truth hierarchy

Facts flow downward; never restate a fact from a higher level in a lower level, and never
hardcode mutable facts (schema numbers, projection/question-set versions, policy versions,
action counts, registry versions, "Stage X is next") in prose outside their owning level:

```text
code / constants / registries
        ↓
docs/REPOSITORY_FACTS.md (machine-checked by tests/test_repository_facts.py)
        ↓
docs/IMPLEMENTATION_STATUS.md (factual claims: what is IMPLEMENTED / PLANNED / UNVERIFIED)
        ↓
docs/ARCHITECTURE.md (structural description)
        ↓
docs/DISCOVERY_ROADMAP.md (stage ordering, gates, deferred work)
        ↓
specialized docs
```

- The repository facts table is checked against code constants by
  `python tests/repository_facts.py check` (also enforced in pytest). After an authorized
  version change: change the constant, run `python tests/repository_facts.py render`, commit.
- Label claims IMPLEMENTED, PLANNED or UNVERIFIED. Do not publish unverified live claims or
  claim scientific readiness from a demonstration. Changed ranking is not evidence that Jev
  improved a research decision.

## Current architecture (do not rebuild)

- One typed runtime chain: GDC open-access API → strict parsers → typed acquisition/lane
  records → canonical typed `StatisticalState` → deterministic Wide Jev projection → validated
  typed answers → Python wide admission → `Candidate` → immutable typed `EvidenceState` E0 →
  registered deterministic action → immutable revision E1/E2 → Deep Jev evidence projection →
  Python next-move policy → optional bounded hypothesis generation (deterministic template by
  default; injected OpenRouter adapter on an explicitly authorized path) → Jev hypothesis
  critique → Stage 8 finalization: deterministic `FinalCandidateResult`, read-only
  no-Jev-baseline comparison, authoritative dossier (JSON + derived Markdown) →
  `CANDIDATE_COMPLETE` → next candidate → run completes when the queue is exhausted.
  Current schema/projection/question-set/policy identities live in
  `docs/REPOSITORY_FACTS.md`; do not restate them here.
- Systematic pre-Wide discovery is implemented as separately invoked bounded commands:
  `discover` (release-bound indexed protein-coding universe prefix → indexed mutation-count
  batches → deterministic count-descending reduction to ≤10 survivors → immutable
  `MutationDiscoveryResult`), `discover-expression` (same release-bound universe → batched
  case-labelled UQFPKM values → local `log2` summaries and within-gene Tukey tails → immutable
  `ExpressionDiscoveryResult`) and `discover-cnv` (Stage 4 survivors only → bounded complete
  CNV occurrences with provider categories/callers → immutable `CnvDiscoveryResult`). A
  cutover step composes one canonical `StatisticalState` per survivor with exact cross-stage
  binding, and held-data descriptor actions restate those values on demand. No provider rank,
  Jev, LLM, census status or hidden biological knowledge enters any reduction; the provider
  top-mutated ranking is a labelled comparator.
- Python domain names are unsuffixed: `StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`. Operational ids/hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialization is versioned and fail-closed: older/unknown schemas are rejected; there are
  no migrations and no legacy readers. Historical databases and artifacts are retained, not
  rewritten.
- Question sets are versioned and must not be silently changed; a new question set requires a
  separate versioned task and validation. Registered actions have explicit contracts (question,
  falsifiable interpretation, method/version, unit, required evidence, limitations) and a
  declared input kind; they acquire no data, call no model, compute no new biological quantity
  and never rewrite the evidence they read; an action failure is a typed outcome that promotes
  nothing. New actions require a concrete operation, not foresight. The current action roster
  and registry version live in `docs/REPOSITORY_FACTS.md`.
- Bounded candidate arc: follow-up attempts and evidence revisions are capped, hypotheses are
  capped, the deep policy records exactly one typed move (`COMPLETE` / `FOLLOW_UP` /
  `GENERATE_HYPOTHESES` / `ABSTAIN`) and never dispatches it. Dispatch is a separate Python
  step requiring explicit authorization; with several eligible actions it fails closed rather
  than choosing silently.
- `run --fixture demo` runs the same shared `LiveOrchestrator` offline with `FixtureTransport`
  and `FixtureJevAdapter` (mode `FIXTURE`, synthetic notice in the dossier). There is no second
  execution engine.
- One canonical `ResearchSpec`, `LUAD_RESEARCH_V1` (`domain=lung cancer`, `cohort_id=TCGA-LUAD`,
  `project_id=TCGA-LUAD`): single explicit TCGA-LUAD cohort, bounded acquisition, implemented
  composition (systematic mutation discovery, expression summary, survivor CNV discovery,
  cutover, investigation, finalization). TCGA-LUAD and TCGA-LUSC are never pooled. Unsupported
  configurations are rejected or not representable: indexed genome-wide universe, broad CNV
  acquisition and pooled cohorts are not implemented.
- Deleted architecture (git history is the archive): `legacy_codecs.py`, dictionary scientific
  identity payloads, `state_summary.py` / `ComputedStatisticalState` / `StateSummary`,
  `LegacyArtifact` / `LegacyMetric` / `LegacyPopulation`, `build_statistical_state`,
  schema-1/2/3 readers, the `DemoOrchestrator` independent engine (the surviving name is only
  a fixture-mode wrapper that constructs `LiveOrchestrator` with `FixtureTransport` +
  `FixtureJevAdapter`), fake actions (`DROP_INFLUENTIAL_FIXTURE_POINTS_V1`),
  `ResearchSpecV2`/lane/universe composition contracts, and the retired handoff/plan/audit
  documents. Do not reintroduce them.
- Still absent: offline autoresearch (needs a labelled historical corpus and human review),
  the multi-modal Stage 9 target skeleton described in
  [the roadmap](docs/DISCOVERY_ROADMAP.md), and any incremental-value result.

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
  stopping, abstention and campaign progression. Jev/LLM outputs are inputs to Python policy,
  never control flow. A Jev judgment never selects, authorizes or executes an action, and a
  recorded next move is never dispatched by the policy that recorded it.
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
- GDC never authenticates. Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may
  carry a provider authorization header for generated hypothesis text: the credential is
  environment-only, never persisted or logged, and its output is bounded, validated and never
  evidence. Any other module adding an authorization header fails the guard test. The current
  identity-check gap on that construction is tracked in
  [implementation status](docs/IMPLEMENTATION_STATUS.md).
- Respect the caps in `docs/GDC_BUDGETS.md`. Never enlarge a limit to finish work.
- Preserve source requests, response hashes, examined populations, sample/workflow context,
  tested families, method versions and missingness. Evidence is immutable; revisions are new
  states. Provider ranking metadata never fills a measured field.
- Every GDC attempt that started reaches a terminal ledger status, and a
  `StatisticalState` source links to the attempt that supplied its response. Operational
  attempt/cache/artifact ids and timestamps never enter scientific identity.
- One canonical RunEvent stream. CLI and UI consume committed records; no second status
  authority and no console-text parsing.
- Stage 8 candidate finalization is deterministic and requires no human review; dossier
  refusal leaves a candidate failed, never complete. A dossier is not proof of adequate
  scientific evidence.

## Engineering

- Ordinary Python, standard library first. KISS, DRY, YAGNI. Prefer small explicit functions
  and narrow adapters. Before each abstraction ask: "Is there a simpler design?"
- Do not scaffold future phases without a current requirement: no agent frameworks, planner
  objects, graph/workflow engines, plugin systems, distributed queues or new repositories for
  concepts that a Python function or a new bounded `ResearchRun` can express.
- Default tests are offline and must not contact GDC, TypeSafe/Jev or an LLM. Run focused
  tests before broader checks. Never weaken a scientific test to obtain a pass.
- Generated hypothesis text is never evidence and never writes a measured field. The generator
  seam defaults to deterministic behavior; the CLI may inject `OpenRouterHypothesisGenerator`
  using its environment-only credential. Provider failure or invalid required output is a typed
  `UNAVAILABLE` outcome. Unknown-field rejection and nested text/list bounds are enforced for
  hypothesis drafts.

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
  LIVE `python -m pytest -m "live or live_gdc or live_jev or live_llm or live_acceptance"`;
  DOC FACTS `python tests/repository_facts.py check` (pytest-enforced).

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

- Maintain the source-of-truth hierarchy above. `docs/IMPLEMENTATION_STATUS.md` is the factual
  record of what is implemented and verified; `docs/ARCHITECTURE.md` owns the structural
  description; `docs/DISCOVERY_ROADMAP.md` owns stage ordering and deferred work; specialized
  docs own their topics. `docs/REPOSITORY_FACTS.md` is the machine-checked facts table —
  never duplicate its values elsewhere.
- Stage 9 (autonomous multi-modal target discovery) is provisional pending source-grounded
  design reviews; do not freeze its contracts into implementation guides before those reviews.
- Historical plans are evidence only, not active implementation instructions. Do not import
  prior-project architecture into OntoJev.
