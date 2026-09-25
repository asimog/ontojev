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

The primary product is a **system-owned autonomous research program** made of bounded,
independently reproducible campaigns: bounded campaign → multi-modal target discovery →
target investigation → Stage 8 finalization → campaign complete → next bounded campaign.
Never describe or build this as one infinite run.

Researchers are an optional, isolated future route (Researcher Lab): researcher-run state,
evidence, candidates, hypotheses and results are isolated from the autonomous program at
runtime. Testable rule: researcher activity cannot influence the system-owned autonomous
program at runtime; any influence on future autonomous behavior must occur through an explicit
versioned code/scientific change outside runtime. This does not claim humans can never
influence the project.

Today's CLI operator controls (deep-candidate selection, follow-up authorization, hypothesis
generation) are explicit, recorded manual paths. The autonomous-program target is a runtime
that requires no human control of candidate selection, Jev promotion, follow-up selection,
hypothesis approval, iteration authorization or candidate completion, with manual CLI controls
remaining only as debug overrides. That reorientation is the provisional Stage 9 direction,
subject to the source-grounded Stage 9 design reviews.

## Source-of-truth hierarchy

Facts flow downward; never restate a fact from a higher level in a lower level, and never
hardcode mutable facts (schema numbers, projection/question-set versions, policy versions,
action counts, registry versions, test counts, "Stage X is next") in prose outside their owning
level:

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

- After an authorized version change: change the code constant, run
  `python tests/repository_facts.py render`, commit.
- Label claims IMPLEMENTED, PLANNED or UNVERIFIED. Do not publish unverified live claims or
  claim scientific readiness from a demonstration. Changed ranking is not evidence that Jev
  improved a research decision.
- Historical plans are evidence only, not active implementation instructions (git history is
  the archive). Do not import prior-project architecture into OntoJev.

## Architecture rules (do not rebuild)

- One typed runtime chain (structure owned by [ARCHITECTURE.md](docs/ARCHITECTURE.md)):
  GDC open-access API → strict parsers → typed records → canonical `StatisticalState` → Wide
  Jev → Python admission → `Candidate` → immutable `EvidenceState` E0 → registered deterministic
  action → revision E1/E2 → Deep Jev → Python next-move policy → optional bounded hypothesis
  generation → Jev hypothesis critique → Stage 8 finalization (`FinalCandidateResult`, read-only
  no-Jev-baseline comparison, authoritative dossier) → `CANDIDATE_COMPLETE` → next candidate →
  run completes when the queue is exhausted. Current schema/projection/question-set/policy
  identities live in `docs/REPOSITORY_FACTS.md`; do not restate them here.
- Systematic pre-Wide discovery is separately invoked bounded commands (`discover`,
  `discover-expression`, `discover-cnv`) over a fixed release-bound indexed universe, each
  persisting one immutable typed result; a cutover step composes one canonical state per
  survivor. No provider rank, Jev, LLM, census status or hidden biological knowledge enters any
  reduction; the provider top-mutated ranking is a labelled comparator.
- Python domain names are unsuffixed (`StatisticalState`, `EvidenceState`, `ResearchSpec`,
  `Candidate`, `HypothesisDraft`). Operational ids/hashes travel in `StateRecord` /
  `EvidenceRecord` / `HypothesisRecord` envelopes and never enter scientific identity.
- Serialization is versioned and fail-closed: older/unknown schemas are rejected; there are no
  migrations and no legacy readers. Historical databases and artifacts are retained, not
  rewritten.
- Question sets are versioned and must not be silently changed; a new question set requires a
  separate versioned task and validation. Registered actions have explicit contracts and a
  declared input kind; they acquire no data, call no model, compute no new biological quantity
  and never rewrite the evidence they read; an action failure is a typed outcome that promotes
  nothing. New actions require a concrete operation, not foresight. Roster and registry version
  live in `docs/REPOSITORY_FACTS.md`.
- Bounded candidate arc: follow-up attempts, evidence revisions and hypotheses are capped; the
  deep policy records exactly one typed move (`COMPLETE` / `FOLLOW_UP` / `GENERATE_HYPOTHESES` /
  `ABSTAIN`) and never dispatches it. Dispatch is a separate Python step requiring explicit
  authorization; with several eligible actions it fails closed rather than choosing silently.
- `run --fixture demo` runs the same shared `LiveOrchestrator` offline with `FixtureTransport`
  and `FixtureJevAdapter`. There is no second execution engine.
- One canonical `ResearchSpec`, `LUAD_RESEARCH_V1` (single explicit TCGA-LUAD cohort): bounded
  acquisition, implemented composition (systematic mutation discovery, expression summary,
  survivor CNV discovery, cutover, investigation, finalization). TCGA-LUAD and TCGA-LUSC are
  never pooled. Unsupported configurations are rejected or not representable: indexed
  genome-wide universe, broad CNV acquisition and pooled cohorts are not implemented.
- Deleted architecture (git history is the archive; do not reintroduce): legacy codecs,
  dictionary scientific identity payloads, state/computed summaries, legacy artifacts/metrics,
  schema-1/2/3 readers, an independent fixture engine, fake actions, ResearchSpecV2/lane/universe
  composition contracts, and the retired handoff/plan/audit documents.
- Still absent: offline autoresearch (needs a labelled historical corpus and human review), the
  provisional Stage 9 target skeleton, and any incremental-value result.

## Ownership boundaries

- `ResearchSpec` owns reproducible research configuration; `Settings` owns operational
  configuration (paths, timeouts, transport budgets, cache, provider/model). Never mix the two.
- GDC stays generic and bounded: it may know project/case/gene IDs, sizes, offsets and endpoint
  contracts; never lung-cancer policy, LUAD biology or Jev routing. Endpoint allowlists, allowed
  fields, open-access enforcement, parsers and absolute safety caps live in code, not in
  `ResearchSpec`. No runtime-configurable arbitrary GDC queries.
- Deterministic code owns measurements (populations, counts, missingness, transforms,
  eligibility, budgets). Jev owns narrow atomic semantic judgment and never computes a
  measurement. Generated hypotheses never write measured fields.
- Python owns loops, routing, state transitions, budgets, side effects, action eligibility,
  stopping, abstention and campaign progression. A Jev judgment never selects, authorizes or
  executes an action, and a recorded next move is never dispatched by the policy that recorded it.
- `storage` is the only layer that writes SQL; `research` and `jev` register records through
  narrow `Repository` methods inside the same event + registrations transaction. No ORM, DAO
  hierarchy or second repository.
- Jev cache reuse requires a pinned/versioned model identity whose provider resolution equals
  it; a mutable model alias is always evaluated and never treated as already resolved. TypeSafe
  SDK retries are explicitly disabled (`RetryPolicy(max_retries=0)`). A total paid-model spend
  gate is still absent.

## Safety and evidence

- Public anonymous official GDC API only. No token, credential seeking, bulk acquisition or
  file download. `/data`, manifests and slicing are outside the allowlist. Respect the caps in
  `docs/GDC_BUDGETS.md`; never enlarge a limit to finish work.
- GDC never authenticates. Exactly one allow-listed module (`cancerjev/llm/openrouter.py`) may
  carry a provider authorization header for generated hypothesis text: the credential is
  environment-only, never persisted or logged, and its output is bounded, validated and never
  evidence. Any other module adding an authorization header fails the guard test. The current
  identity-check gap on that construction is tracked in
  [implementation status](docs/IMPLEMENTATION_STATUS.md).
- Preserve source requests, response hashes, examined populations, sample/workflow context,
  tested families, method versions and missingness. Evidence is immutable; revisions are new
  states. Provider ranking metadata never fills a measured field.
- Every GDC attempt that started reaches a terminal ledger status, and a `StatisticalState`
  source links to the attempt that supplied its response. Operational attempt/cache/artifact ids
  and timestamps never enter scientific identity.
- One canonical RunEvent stream. CLI and UI consume committed records; no second status
  authority and no console-text parsing.
- Stage 8 candidate finalization is deterministic and requires no human review; dossier refusal
  leaves a candidate failed, never complete. A dossier is not proof of adequate scientific
  evidence.

## Engineering

- Ordinary Python, standard library first. KISS, DRY, YAGNI. Prefer small explicit functions
  and narrow adapters. Before each abstraction ask: "Is there a simpler design?"
- Do not scaffold future phases without a current requirement: no agent frameworks, planner
  objects, graph/workflow engines, plugin systems, distributed queues or new repositories for
  concepts that a Python function or a new bounded `ResearchRun` can express.
- Default tests are offline and must not contact GDC, TypeSafe/Jev or an LLM. Run focused tests
  before broader checks. Never weaken a scientific test to obtain a pass.
- Generated hypothesis text is never evidence and never writes a measured field. The generator
  seam defaults to deterministic behavior; the CLI may inject `OpenRouterHypothesisGenerator`
  using its environment-only credential. Provider failure or invalid required output is a typed
  `UNAVAILABLE` outcome. Unknown-field rejection and nested text/list bounds are enforced for
  hypothesis drafts.

## Testing

- Before writing an isolated test, state the realistic failure mode it protects. Do not write a
  unit test after implementing code merely to restate that code.
- Prefer behavioral integration/replay tests through real current subsystem boundaries for
  complex features. Mock only genuine external network seams (GDC, TypeSafe/Jev, OpenRouter).
  Do not mock an internal function just to assert another internal function called it.
- For complex work, define the important failure modes before implementation and test those
  contracts. Keep focused tests for scientific/provider/persistence invariants that E2E cannot
  localize or exhaustively protect (missing ≠ zero, NOT_ACQUIRED ≠ absence, fail-closed
  refusals, wrong state/candidate/revision binding, malformed provider payloads, terminal
  ledger states).
- Do not test private implementation structure, trivial wrappers, getters/setters, obvious
  constants or internal call order without semantic importance. A harmless refactor must not
  require widespread test rewrites.
- Prefer a few durable end-to-end/replay artifacts (state hash, revision chain, event sequence,
  final dossier, persisted policy result) over many implementation-coupled assertions.
- Default tests are offline. Live GDC/Jev/LLM verification is explicit, bounded and opt-in via
  the `live*` markers. Test count and coverage percentage are not quality objectives.
- Gates: FAST `python -m pytest -m fast`; OFFLINE FULL `python -m pytest`;
  BROWSER `cd tests/browser && npx playwright test`;
  LIVE `python -m pytest -m "live or live_gdc or live_jev or live_llm or live_acceptance"`;
  DOC FACTS `python tests/repository_facts.py check` (pytest-enforced).

## Development skills

- GDC is the sole scientific runtime data source, including evidence supplied to hypothesis
  models. No non-GDC scientific source is admitted (no PubMed/bioRxiv, cBioPortal, Reactome,
  STRING, UniProt, Open Targets, GTEx or similar) for runtime evidence, hypothesis inputs or
  any other OntoJev runtime path.
- OpenAI NGS/Life Science skills are development references, not production dependencies or
  acquisition authority; load only what the current task needs. Use relevant NGS guidance for
  mutation, expression, CNV, QC and scientific-action design/review; actual GDC contracts and
  admitted methods override generic bioinformatics workflow assumptions.
- Do not install or run scientific pipelines, acquire raw sequencing files, or query external
  scientific databases merely because a skill describes those steps.
- Life Science Research and its router are explicit-request, reference-only resources; their
  database/literature routing steps are not for OntoJev.
- Use the official TypeSafe skill and current live documentation for Jev work. If deterministic
  code or classical statistics can answer exactly, do not use Jev.
- These are project instructions, not technical network restrictions or global plugin settings.

## Documentation

- Maintain the source-of-truth hierarchy above. `docs/IMPLEMENTATION_STATUS.md` is the factual
  record of what is implemented and verified; `docs/ARCHITECTURE.md` owns the structural
  description; `docs/DISCOVERY_ROADMAP.md` owns stage ordering and deferred work; specialized
  docs own their topics. `docs/REPOSITORY_FACTS.md` is the machine-checked facts table — never
  duplicate its values elsewhere.
- Stage 9 (autonomous multi-modal target discovery) is provisional pending source-grounded
  design reviews; do not freeze its contracts into implementation guides before those reviews.
