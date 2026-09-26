# ONTOJEV REFACTORED IMPLEMENTATION PLAN

**Plan baseline:** `b595a3a9bbfcd7736debd9787cc8e537ae648d23`, branch `main`. This plan is the merged implementation set derived from the master-plan document set, the six design documents and the earlier 17-prompt refactor plan (written against `26988040fb7c8afbb121c3774a6b510285db7ba9`). `b595a3a` changed documentation only, so the earlier plan's runtime findings remain applicable at this baseline; every unit must still re-inspect the then-current HEAD and re-verify its own citations before changing code.

**Pinned source context:** GDC Data Release 46.0 (2026-08-10), verified against `gdc-docs@157cef9dac084ce30720f0ad507cd54017263be7`. `.upstream/SOURCES.lock.json` v1 pins 40 repositories at exact SHAs — 30 `CURRENT_REFERENCE`, 7 `HISTORICAL_REFERENCE`, 2 `DOCUMENTATION_ONLY`, 1 `EXECUTABLE_TOOL` — with `gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1` as the data-model authority. The workspace is untracked local evidence, not a runtime dependency.

**Implementation status (2026-09-25):** P01–P08 are implemented, verified and pushed — P01 `ac2468d`, P02 `e3ce5fd`, P03 `a1c6274` (+fixture attributes `90482bd`), P04 `4a5d14a`, P05 `94d3f63` (live: 19,843 genes / 199 terminal shards), P06 `02f42fb` (recorded deferral), P07 `324ca68` (live: 71 scan pages / 204.8 MB, TP53 composition), P08 `d900eda` (live full-universe expression: 19,843 genes, 15,396 RETAIN, 1,942 JEV_REVIEW, 1,406 requests, universe membership hash matching the mutation lane). Tooling baseline `9bb4508`/`95bd9d1`: ruff, strict mypy (46 modules) and the full offline suite are green. P09 is in progress: shard request/parser (`333b4fe`, live probe: 4,358,062 rows / 2.19 GB), merged-evidence recurrence dispositions (`676fd21`), sharded scan/merge (`fc80fd3`) and CLI workers (`88171d8`) are landed; the 24-shard live run is executing. P10 is complete (`e2e9a65`/`9630122`/`19f835a`): one canonical state per union member with typed nominations. P11 is complete (`0ad43da`/`f00ab96` + dossier fix): deterministic evidence maturity persisted on states, knowledge roles, method-specific replication partitions and a machine-checked leakage guard. P12 is complete for its declared decision and membership layer: Reactome top-level membership adopted (CC-BY-4.0, filtered human snapshot `c35b05d6…`, 381,765 rows / 53.1 MB, real TP53 identifier-set contract), with enrichment and cross-modal analysis explicitly deferred; persisting pathway evidence onto states awaits a declared semantic consumer. P13 is complete (`docs/TYPESAFE_DECISIONS.md`, `typesafe-decisions-v1`): current Jev questions kept and re-validated by a real provider call on 2026-09-25 (the live test now uses the real event-emitting callback so registrations persist), and **Arm Jev is DEFERRED** — deterministic dispositions plus typed pending-semantic-review carrying cover admission, so `JEV_REVIEW` entries are never admitted and never silently dropped. P14 is complete: every run records `execution_ownership` (`SYSTEM_AUTONOMOUS` / `RESEARCHER_RUN`, SQLite schema 6), operator deep flags are rejected on autonomous runs before any work, cross-owner guards fail closed in both directions, and researcher runs keep their own typed scope. P15 is complete: the deep-action selection is the declared deterministic `deep-action-policy-v1` (evidence-producing → check → summary tiers, ambiguity abstains with a typed reason, executed actions are filtered, operator override preserved), and the first evidence-producing action `OCCURRENCE_DETAIL_EVIDENCE_V1` (registry v4) measures canonical occurrence composition from bounded per-gene detail pages into a typed `MeasuredObservation` on the new immutable revision — proven end-to-end in replay: a candidate completes with a measured revision without the operator naming the action, and over-cap/transport failure yields a typed unavailable observation. Ownership-gated autonomous auto-dispatch wiring lands with the P16 program consumer. P16 is partially landed: `campaign-selection-v1` (readiness-gated, priority-then-campaign-id deterministic order), `program-loop-v1` (one bounded Campaign per step, `PROGRAM_IDLE` when none eligible), `release-comparison-v1` (declared classes with method changes `NOT_COMPARABLE`) and `release-monitor-v1` (a single bounded `/status` observation with typed provenance, comparison kept separate) are implemented with tests; the owner-checked program worker with artifact-backed step state and the bounded `program` CLI step (owner-checked, idle until a campaign is validated) are implemented as well. Autonomous auto-dispatch wiring remains tracked until a validated campaign exists to exercise it. P17 is complete as its declared conditional outcome: `docs/FUNCTIONAL_SOURCES.md` (`functional-sources-v1`) records DepMap CRISPR, Sanger CGC, targetability resources and independent-cohort replication as **DEFERRED** with access/licensing reasons, keeps the seven evidence axes distinct, and leaves `FUNCTIONALLY_SUPPORTED` unattainable — machine-checked, with no adapter or download added. P18 is not activated: no cohort/question currently justifies a fourth modality, the lane vocabulary remains exactly mutation/expression/CNV, and every unadmitted modality stays UNAVAILABLE with a declared reason under a guard test. P19 is complete: `tests/acceptance/test_final_acceptance.py` ties the gates together end-to-end offline — frozen reconciliation corpus read-only, union states with levels/nominations/workflow coverage, no forbidden or controlled-access request paths, an autonomous run completing with a policy-selected measured revision, byte-identical deterministic replay, bilateral ownership fail-closed, claim boundary in every dossier, and a non-LUAD fixture that proves generic architecture only. Tracked remaining: P16b persistence/`/status` polling/`program` worker, and the live 24-shard CNV merge (running in the background). Systematic complete-universe discovery is the canonical path; `GDC_FAST_SEARCH` is transitional/compatibility behavior retained as a labelled comparator.

**Current architecture:** typed GDC requests/parsers and bounded transport; deterministic mutation/expression/CNV lanes; one canonical `StatisticalState`; Wide judgment and Python admission; candidate-specific immutable `EvidenceState` revisions; Deep judgment and Python policies; bounded hypotheses and critique; Stage 8 final results, authoritative dossiers and deterministic no-Jev comparisons. Systematic discovery and the older provider-ranked live path coexist. Neither is a continuous autonomous Program.

**Current scientific limitations:** systematic discovery uses a declared, biased first-1,000 protein-coding genes (`GENE_ID_ASC_INDEXED_PREFIX_V1`, `MAX_UNIVERSE_LIMIT=1000`, `UNIVERSE_PAGE_CAP=10`); expression describes that same prefix; CNV and integrated state composition are mutation-survivor-only, so no lane except mutation can nominate and there is no modality candidate union. Mutation occurrence counting is reconciled for Stage 4, but the older provider-ranked live path still consumes the invalidated analysis bucket as an affected-case measurement. Expression tails and CNV categories are descriptive; there is no per-modality disposition, no evidence-level ladder, no replication design and no declared inference contract. Assay eligibility, sample matching, scientific readiness, campaign selection, workflow provenance and complete-universe autonomy remain work. Census status reaches Wide without a declared information role. Shared scientific/Jev code still contains LUAD/TCGA literals; persisted sources do not carry typed workflow identity, and expression workflow coverage is a five-file sample. No external functional/targetability axis exists; runs do not encode `SYSTEM_AUTONOMOUS` versus `RESEARCHER_RUN` ownership; no final acceptance suite ties the gates together.

**Already satisfied supplied prompts:** typed state/control spine; hypothesis-is-not-evidence boundary; bounded candidate finalization, dossiers and no-Jev comparison; strict versioned readers; Stage 4 occurrence-count correction and its frozen reconciliation corpus; local upstream reference workspace; documentation convergence at `b595a3a` (README and Architecture distinguish current from target behavior); durable rules already present in `AGENTS.md`. These are implementation findings, not a claim that scientific validation has passed.

**Partially satisfied supplied prompts:** source context, cohort framing, universe provenance, bounded acquisition, mutation/expression/CNV science, integrated discovery, Jev failure handling, deterministic follow-up, validation leakage controls, run ownership, and the cancer-agnostic contract (four literal-coupling sites remain).

**Required supplied prompts:** complete-universe global reduction; typed workflow provenance; assay/capability and readiness contracts; independent modality nomination and union; justified open-file acquisition; method-specific inference/replication; evidence maturity and external-information roles; autonomous Campaign selection/release monitoring; researcher isolation; end-to-end acceptance.

**Superseded supplied prompts:** rebuilding Wide/Deep/Stage 8, replacing `ResearchSpec`, and creating a second scientific-state system. Treating a prefix as genome-wide, CNV as independent discovery today, or LUAD as already validated for autonomous scientific use is contradicted by the inspected implementation. Arm Jev and extra modalities are conditional, not mandatory infrastructure.

**Hard scientific gates:** independently reconciled selection-critical measurements (the frozen reconciliation corpus is read-only evidence, never recomputed or rewritten); complete declared population and terminal required shards before any global finalization or ranking claim; explicit assay/missingness semantics; typed workflow/unit comparability before any cross-workflow comparison; cancer-name literals confined to campaign profiles, fixtures and labelled comparators, never shared science; no validation-label leakage; declared population/null/FDR contract for every inferential claim (descriptive outputs carry no p/q values); method-specific statistical support and replication with no universal split ratio; immutable source/results and one coordinated cutover for incompatible persisted state; attributable autonomous-readiness evidence; fail-closed semantic and persistence boundaries; Jev may never promote evidence level; researcher ownership can never mutate autonomous state.

**Recommended execution order:** P01 → P02 → … → P19: the unit numbers are the execution order. P06 (open files) runs only when a named file consumer exists; P18 (additional modality) is optional and scheduled only when a named modality is justified; P19 runs last, after every adopted unit. P14 precedes P15 and P16 by construction: P15's autonomous dispatch requires the run-level ownership flag P14 delivers, and P16's persistence is owner-aware from its first implementation rather than retrofitted. Each numbered unit is one bounded change; do not implement this entire document in one pass.

**Merge and split decisions:**

- The earlier plan's prompt 12 is split: evidence levels and the replication contract (P11) versus pathway source and pathway evidence (P12), because licensing, versioning and identifier mapping are independent gates.
- The earlier plan's prompt 3 is a small standalone unit (P02); the campaign-limited science it must not touch is corrected in P05 (universe), P08 (expression) and P09 (CNV).
- The earlier plan's prompt 17 is split: ownership isolation (P14) versus end-to-end acceptance (P19).
- Workflow provenance (P04, earlier prompt 8) is separated from open-file acquisition (P06, earlier prompt 7) so that comparability is fixed before any new file source arrives.
- The per-gene occurrence-detail builder is implemented once in P07 and consumed by the P15 follow-up action; no duplicate science.
- The legacy provider-ranked path is retained only as a clearly labelled comparator, never as a measurement.

## Scope and interpretation

This document merges the master instruction, inspection limits, six design documents and the 17-prompt refactor plan into the repository's implementation plan. They are design inputs, not evidence of running functionality. The later plan was written against `2698804`; its current-code findings remain applicable because `b595a3a` changed documentation only, but every implementation unit must re-inspect the then-current HEAD. No history, deleted plans, unrelated UI audit, runtime changes, tests, schemas, migrations or scientific acquisition were needed for this merge.

The source of truth is current code for implementation and authoritative upstream material for scientific semantics. Tests were read, not run. Commands under verification are for later explicitly authorized implementation/verification tasks; repository policy skips tests unless requested. No live Jev calls or campaign-scale GDC requests were made.

Line numbers and module/type names quoted from either plan (for example `SourceContext`, `CampaignProfile`, `AcquisitionShard`, `domain/evidence_level.py`) are inspection snapshots and candidate shapes, not pre-approved layouts or version commitments. Each unit re-derives them from the then-current code and assigns concrete schema, action, projection, question-set and policy versions only when it proves a semantic incompatibility.

## Current implementation map

| Capability | Current evidence | Consequence |
|---|---|---|
| Cohort/run configuration | `cancerjev/research/specs.py`: `CohortSpec`, `ResearchSpec`, `LUAD_RESEARCH_V1`, strict `research_spec_from_dict` | Extend this configuration; no replacement registry/framework. |
| Universe | `domain/discovery.py`: `DiscoverySpec`, prefix limit; `domain/measurements.py`: `TestedUniverse`; `research/discovery.py`: `acquire_gene_universe` | Provenance exists; whole eligible universe and durable shard completion do not. |
| Mutation | `research/acquisition.py`: `acquire_project_mutation_occurrence_scan`; `research/discovery.py`: `build_discovery_entries`, `run_mutation_discovery` | Reuse complete-scan distinct-case counting; recurrence remains descriptive. |
| Older live path | `research/live.py`: `_fast_search`; `science/mutation.py`: `mutation_observation` | Bucket-to-affected-case semantics still exist outside Stage 4; P01 blocks scientific admission from them. |
| Expression | `research/expression_discovery.py`: `run_expression_discovery`; `science/expression.py`, `science/descriptors.py` | Case-labelled UQFPKM and log-transformed summaries/tails; no matched differential-expression claim. |
| CNV | `research/cnv_discovery.py`: `run_cnv_discovery`; `domain/discovery.py`: `CNV_SELECTION_RULE` | Positive indexed categories only on Stage 4 survivors; no neutral denominator. |
| Composition | `research/cutover.py`: `compose_discovery_states` | One state per mutation survivor, strict shared scope/frame binding; no independent modality union. |
| State/control | `domain/scientific.py`, `domain/evidence.py`, `research/wide.py`, `research/ranking.py`, `research/deep.py`, `research/nextmove.py`, `research/investigation.py` | Preserve canonical state and bounded control spine. Multiple eligible follow-ups can be refused without explicit selection. |
| Jev boundary | `jev/projection.py`, `questions.py`, `contracts.py`, `service.py`, `typesafe_adapter.py` | Existing Noul/Choice/Score, applicability, typed failures and cache checks; census annotation is included in Wide projection. |
| Finalization | `research/finalize.py`: `derive_stage8`, `run_stage8_finalize`; `research/dossier.py`, `domain/dossier.py`, `dossier/renderer.py` | Final result and dossier already exist; no-Jev deltas are not superiority evidence. |
| Persistence/ownership | `domain/codecs.py`, `storage/readers.py`, `storage/repositories.py`, `storage/artifacts.py`, `storage/ownership.py` | Strict readers/artifacts and exclusive directory lock; lock is not autonomous-versus-researcher isolation. |
| Evaluation | `research/prospective.py`, `research/evaluation.py` | Optional blinded/grouped evaluation exists; it is not a genomic holdout contract or a runtime human-approval gate. |
| Reconciliation | `tests/reconciliation/fixtures/reconciliation_dr46/MANIFEST.json`, `tests/reconciliation/independent_counts.py`; `data/invalidations/2026-09-25-mutation-affected-case-count-v1.json` | The frozen corpus is read-only evidence for the V1 defect and the V2 correction; never recomputed to fit new code. |
| Upstream workspace | `.upstream/SOURCES.lock.json` v1 (40 pinned repositories); `.upstream/envs/gdc-client-install-contract.txt` | References only; `gdc-client` is pinned but not installed, and no runtime dependency exists. |
| Entry points | `cli/main.py`, `research/live.py`, `research/orchestrator.py` | Existing CLI/live/demo runners; no `cancerjev/orchestration/` package to redesign. |

All paths in this table are relative to the repository root. Schema/action/policy constants remain owned by code and indexed in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## Upstream evidence inspected

Existing untracked `.upstream/gdc/` clones were reused. Their checked-out SHAs matched remote `HEAD` on 2026-09-26; no checkout, installation or bulk download was required. `.upstream/SOURCES.lock.json` records clone dates/roles and an older OntoJev inspection HEAD; that older HEAD is not this plan's baseline. The lock's role classification (30 current, 7 historical, 2 documentation-only, 1 executable tool) is the current-versus-historical authority and is not re-derived in code.

| Ref | Repository and exact inspected SHA | Inspected evidence / role |
|---|---|---|
| U1 | [gdc-docs](https://github.com/NCI-GDC/gdc-docs) `157cef9dac084ce30720f0ad507cd54017263be7` | `docs/API/Users_Guide/Data_Analysis.md`; expression, DNA variant and CNV pipeline docs. Current scientific documentation reference. |
| U2 | [gdcdatamodel2](https://github.com/NCI-GDC/gdcdatamodel2) `9c6a046b96c130ea131d2ce2c9160381edd2fcc1` | `src/gdcdatamodel2/models/sample.py`, `aliquot.py`, `file.py` and the partial dictionary: identity relationships and experimental-strategy/workflow fields. Data-model authority, not imported runtime machinery. |
| U3 | [gdc-workflow-overview](https://github.com/NCI-GDC/gdc-workflow-overview) `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e` | README production/provenance map; some current WGS implementations are not public. Older WXS caller listing must be reconciled with U1. |
| U4 | [gdc-client](https://github.com/NCI-GDC/gdc-client) `0602ecbccb9f31e37d720347e58ea3eaef981f85` | README and download client source. Reference for a future selected-open-file adapter; no OntoJev adapter found. |
| U5 | [gdc-rnaseq-cwl](https://github.com/NCI-GDC/gdc-rnaseq-cwl) `05460f7dfca5a900d7635ccae0e1b28cf764a02f` | README input/output and annotation contract; source reference only. |
| U6 | [gdc-rnaseq-tool](https://github.com/NCI-GDC/gdc-rnaseq-tool) `9a0fccece9b7f59c046c664d94dea2cb42dbcb08` | Pin verified; tool implementation inspection deferred until a normalization consumer requires it. |
| U7 | [gdc-somatic-variant-calling-workflow](https://github.com/NCI-GDC/gdc-somatic-variant-calling-workflow) `6634b4f8313b7fa662d2dec380a7ea67cf631f0a` | Pin verified; source details deferred to P07's method needs, not assumed current from repository existence. |

Current expression documentation describes STAR counts and FPKM/FPKM-UQ/TPM transforms, unstranded harmonization and GENCODE v36 from release 32; historical HTSeq is not the current default. CNV products from ASCAT, ABSOLUTE, DNAcopy and GATK4 require distinct provenance. U1 documents SomaticSniper deprecation at release 35 and current Pindel usage; U3's older WXS list does not override that. These facts inform compatibility checks, not permission to rerun harmonization.

The [NCI GDAN overview](https://www.cancer.gov/ccg/research/computational-genomics/genomic-data-analysis-network) was inspected for the established-methods context. It does not validate any specific OntoJev method. Selecting a statistical method still requires its primary methodological reference and input validation.

Official [TypeSafe documentation index](https://docs.typesafe.ai/llms.txt) and [autoresearch feature-discovery cookbook](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) were inspected on 2026-09-26. The cookbook uses labelled text, semantic features and supervised evaluation; it is not evidence that model-generated cancer hypotheses are genomic measurements. The index confirms typed primitives and fan-out/routing patterns. Direct `.md` primitive/pattern page retrieval failed; recheck exact SDK/API behavior before implementing new batching/routing. GDC web API-page retrieval also failed; its pinned U1 source was readable and used instead.

## Requirements disposition

Master sections 1–2 and 31, 34–37 govern this planning output. Sections 3–6 and 8 map to P02/P04/P05/P07; 7 and 21–24 to P03/P05/P06/P08; 9–12 and 19–20 to P11/P12; 13–18 and 25–26 to P07–P10/P13/P17; 27 to P13; 28 to P19; 29–30 to the cutover/verification rules below; 32–33 apply to every unit. The supplied Product Scope, Architecture, Data Strategy, Jev Design and Scientific Invariants overlap; their common requirements are merged here rather than implemented repeatedly.

### Later-plan traceability

The 17-prompt refactor plan is merged as follows. `SATISFIED` means no runtime unit is created; documentation may still record the finding. This table is the authoritative prompt-to-unit mapping.

| Later prompt | Disposition in this plan | Reason |
|---|---|---|
| 1 — documentation convergence | SATISFIED at `b595a3a` | README and Architecture distinguish current and target behavior. |
| 2 — durable agent context | SATISFIED | `AGENTS.md` already contains the required stable rules. |
| 3 — cancer-agnostic contracts | P02 | Concrete LUAD/TCGA literals remain in shared question, cutover, reducer and dossier code. |
| 4 — source/capability/readiness | P03 | Typed source context, capability discovery and one readiness vocabulary are missing. |
| 5 — mutation reconciliation | SATISFIED for Stage 4; P01 for the legacy path | The corrected occurrence scan exists; `_fast_search` still exposes invalid bucket semantics. |
| 6 — complete universe/shards | P05 | Prefix limit and page caps still bound scientific scope; no shard ledger. |
| 7 — controlled data plane | P06 | New endpoints or open files land only with their named method consumer. |
| 8 — workflow provenance | P04 | Separated as a prerequisite before any lane comparison. |
| 9 — mutation lane | P07 | Descriptive enrichment and dispositions only after source/universe foundations. |
| 10 — expression lane | P08 for identity/QC/disposition; P10 for union | Independent nomination needs the union contract as well as the lane contract. |
| 11 — CNV/SV/modalities | P09 for CNV; P18 for every other modality; capability records in P03 | CNV becomes independent; SV is not collapsed into CNV; unvalidated modalities stay UNAVAILABLE with reasons. |
| 12A — evidence levels/replication | P11 | Uses a method-specific validation design; no universal split ratio. |
| 12B — pathway evidence | P12 | Kept separate because source, licensing, mapping and inference are independent gates. |
| 13 — TypeSafe/Arm/Wide | P13 | Arm remains conditional on a real residual semantic question. |
| 14 — ActionPolicy/follow-up | P15 | One evidence-producing action, shared builder with P07, attributable deterministic selection. |
| 15 — functional evidence | P11 for roles/leakage; P17 for source adoption | Classification precedes any external data integration. |
| 16 — campaigns/releases | P16 | Campaign selection and release comparison follow readiness gates. |
| 17 — researcher isolation/acceptance | P14 (ownership) + P19 (acceptance) | Ownership enforcement and layered final acceptance are separate bounded units. |

**SATISFIED — documentation convergence and durable agent context.** Current evidence: README "Current implementation"/"Target architecture" split, Architecture "Current implementation boundary" table, and `AGENTS.md` rules. Remaining gap: NONE for their existence; they are updated only when their owning behavior changes.

**SATISFIED — control-spine preservation.** Current evidence: canonical `StatisticalState`, frozen evidence contracts, projection/service boundary, Python Wide/next-move policies, hypothesis contracts and Stage 8 files above. Relevant existing checks include `tests/integration/test_stage8_finalize.py`, `test_hypothesis_stage.py`, `tests/jev/test_typed_flow.py`. Remaining gap: NONE for retaining these components. Broader scientific inputs and autonomy are separate units.

**SATISFIED — Stage 4 distinct released-case measurement.** Current evidence: `acquire_project_mutation_occurrence_scan`, `build_discovery_entries`, `tests/science/test_occurrence_scan.py`, `tests/reconciliation/independent_counts.py`, frozen `reconciliation_dr46/MANIFEST.json`. Remaining gap: NONE for replacing the Stage 4 bucket measurement. This does not satisfy the older path, callable denominators, complete universe or driver inference.

**SATISFIED — immutable finalization and comparator existence.** Current evidence: `derive_stage8`, `run_stage8_finalize`, dossier renderer and `test_stage8_finalize.py` cases for immutable baseline replay, per-candidate finalization and authoritative dossier. Remaining gap: NONE for their existence; extend only when scientific contracts change.

**SUPERSEDED — unconditional Arm Jev, broad tool installation and rebuilding the engine.** Existing types/control are reusable; semantic necessity and method-specific acquisition decide whether optional work exists. Do not introduce a generic DAG, plugin framework, separate state model or tool-selection agent.

## Shared implementation rules

Each unit below names its persistence impact; no versions are bumped now. Before any incompatible cutover, record the then-current recovery HEAD/tag, preserve representative old artifacts, enumerate incompatibilities, update producers/readers/projections/consumers together and reject unsupported versions. Do not migrate historical evidence into new scientific meaning. Use explicit supersession for invalid results.

Names such as `SourceContext`, `CampaignProfile`, `AcquisitionShard` and new database tables describe missing contracts, not pre-approved modules or storage layouts. First test whether the existing `ScientificSource`, `OperationalSource`, `ResearchState`, artifact and repository contracts can be extended cleanly. Assign concrete schema, action, projection, question-set and policy versions only in the implementation unit that proves a semantic incompatibility.

Frozen evidence (the reconciliation corpus, invalidations record and historical run artifacts) is read-only. A unit may consume or reference it; a unit may never recompute it, rewrite it or soften its recorded defect to make new code pass.

For acquisition units, let G be eligible genes, C cohort cases, E released event records, B a bounded request batch, P a page size and F selected files. These are planning variables, not measured live counts. No honest current file-count/byte estimate exists for an unselected future method. Its acquisition preflight must materialize counts and `sum(file_size)`, or bounded-response size estimates, before execution. Budget exhaustion produces incomplete/unavailable status, never a smaller scientific population labelled complete. Multi-GB plans require source reconsideration; raw sequencing is not an automatic fallback. Retain source IDs, hashes, manifests, method versions and derived results; retain replay bytes when necessary, with explicit cache/retention policy.

Verification must test scientific contracts and observable behavior. Do not make a known biological winner, a particular gene rank, source-code token scanning or a monolithic end-to-end test the sole acceptance criterion. Use layered contract, replay, integration and bounded live checks. Commands below are specifications for later authorized implementation verification; this plan does not execute them.

### P01 — Close the remaining invalid mutation-measurement path

**STATUS:** PARTIAL. **OBJECTIVE:** prevent the older live path from publishing an analysis bucket as distinct affected cases.

**WHY THIS WORK REMAINS:** `research/live.py:_fast_search` calls `research/acquisition.py:acquire_mutation_counts`, and `science/mutation.py:mutation_observation` still transfers bucket values to `affected_cases`. Stage 4 already uses the corrected complete `/ssm_occurrences` scan. The frozen reconciliation corpus proves the defect on captured real bodies: for its TP53/TCGA-LUAD capture the analysis bucket is 393, released occurrences are 299 and distinct cases are 281, and a gene with no released occurrences can still carry a nonzero bucket. `data/invalidations/2026-09-25-mutation-affected-case-count-v1.json` records the supersession and must not be rewritten.

**CURRENT CODE TO REUSE:** occurrence scan and Stage 4 derivation; reconciliation manifest/independent counts; strict scope binding in `research/cutover.py` and immutable artifact registration.

**CURRENT CODE TO CHANGE:** `research/live.py`, `research/acquisition.py`, `science/mutation.py`, affected `science/methods.py` consumers and method identities; `config.py` comments/limits that reference the corrected scan. Keep a labelled provider-ranking comparator separate.

**UPSTREAM SOURCES TO USE:** U1 API analysis semantics, U2 identity; frozen reconciliation is direct source evidence.

**SCIENTIFIC CONTRACT:** one cohort/release; distinct released case IDs per gene across a complete scan. No occurrence means zero released occurrences only; neither wild type nor a callable-negative denominator. Consumer: existing state composition/admission.

**IMPLEMENTATION STEPS:** 1. Trace legacy bucket consumers. 2. Route scientific measurements through the existing corrected scan or make that legacy measurement unavailable. 3. Label preserved comparator metadata explicitly. 4. Supersede affected scientific outputs without rewriting them. 5. Add a routing test proving no admitted affected-case field can derive from the bucket.

**DATA / ACQUISITION PLAN:** replay first; existing `/ssm_occurrences` scan is approximately ceil(E/P) requests (measured LUAD-scale scan and replay corpus: ~36 pages, ~104 MB) if later live verification is authorized; no files, no new population.

**SCHEMA / PERSISTENCE IMPACT:** changed measurement meaning requires method/provenance cutover; change schema only if the existing typed output cannot represent it.

**VERIFICATION:** later `python -m pytest tests/reconciliation tests/science/test_occurrence_scan.py tests/integration/test_live_replay.py`; extend cases for legacy routing, duplicate events and incomplete scans. Fixture bucket/occurrence/case numbers are assertions about captured source semantics, never current live counts.

**ACCEPTANCE CRITERIA:** no admitted affected-case field derives from the invalidated bucket; Stage 4 and legacy paths agree on the frozen source population.

**STOP BOUNDARY:** no new mutation statistics or universe expansion. **DEFERRED WORK:** P05/P07. **CANONICAL DOC UPDATE:** current measurement limitation in README/Architecture; Data Strategy source caveat.

### P02 — Cancer-agnostic core contracts and method identity

**STATUS:** PARTIAL. **OBJECTIVE:** remove the remaining cancer-specific literals from shared scientific/Jev code while keeping `LUAD_RESEARCH_V1` a legitimate campaign profile.

**WHY THIS WORK REMAINS:** the generic contract is nearly complete — no `project_id == "TCGA-LUAD"` branch exists in `cancerjev/`, and `CohortSpec`/`ResearchSpec` are structurally generic — but four literal-coupling sites remain at the merge baseline:

- `jev/questions.py` (Wide at 61, Deep at 172, hypothesis at 257): instructions hardcode "one TCGA-LUAD cohort";
- `research/cutover.py` (111, 122): `PopulationRecord.program="TCGA"` and `programs=("TCGA",)` are hardcoded;
- `domain/discovery.py:52` (`REDUCER_METHOD_ID`) and `research/cutover.py` (119, 166): the method identity `MUTATION_LUAD_AFFECTED_COUNT_DESC_V1` names a cancer;
- `research/dossier.py:188`: the reason text says "LUAD is never pooled with another cohort".

The projection already carries cohort identity (`jev/projection.py`: `scope.cohort`, `cohort.project_id`), and `ProjectRecord.program_name` is already parsed by `parse_projects` and used by `science/methods.py`, so steps 2–3 need no new contract. Line numbers here are inspection aids; symbols are the contract.

**CURRENT CODE TO REUSE:** `ResearchSpec`/`CohortSpec`, the state/evidence/hypothesis projections, `parse_projects` `program_name`, `MethodIdentityRef` discipline, frozen fixtures.

**CURRENT CODE TO CHANGE:** `jev/questions.py`, `research/cutover.py`, `domain/discovery.py`, `research/dossier.py`, `science/methods.py` consumers of the reducer identity, and the Repository Facts renderer input.

**UPSTREAM SOURCES TO USE:** none; local contract cleanup.

**SCIENTIFIC CONTRACT:** method identity describes the computation, not a cancer; Jev instructions receive cohort identity from the typed projection and never hardcode it; campaign literals live only in campaign profile constants, fixtures and explicitly labelled comparators.

**IMPLEMENTATION STEPS:** 1. Rename the reducer to a cancer-free identity (for example `MUTATION_AFFECTED_CASE_COUNT_DESC_V1`) under one coordinated method-rename cutover: bump the method identity/version, re-render Repository Facts, preserve old artifacts, never rewrite historical results. 2. Derive program fields from the project record (`program_name`) or `CohortSpec`; remove `"TCGA"`. 3. Parameterize question instructions from the projected cohort identity (`{cohort}`), not a literal. 4. Replace the dossier reason with the recorded cohort/project reason. 5. Add a guard test that the named core modules contain no cancer literal outside campaign profiles, fixtures and labelled comparators — a literal guard, never a substitute for behaviour tests.

**DATA / ACQUISITION PLAN:** none.

**SCHEMA / PERSISTENCE IMPACT:** the reducer method identity changes; discovery artifacts keep their old identity and are never rewritten; new runs record the new identity.

**VERIFICATION:** later `python -m pytest tests/unit/test_research_specs.py tests/science tests/jev`; frozen-fixture discovery counts must be identical after the rename; literal-guard test green.

**ACCEPTANCE CRITERIA:** shared scientific/Jev modules carry no cancer literal; the LUAD profile still produces identical counts on the frozen fixtures; a second project id flows through the same code path.

**STOP BOUNDARY:** do not touch the prefix universe, CNV conditioning or expression identity here. **DEFERRED WORK:** campaign-limited science → P05/P08/P09. **CANONICAL DOC UPDATE:** REPOSITORY_FACTS (method id via renderer); README unchanged.

### P03 — Bind source, assay capability and scientific readiness

**STATUS:** PARTIAL. **OBJECTIVE:** turn recorded run scope into an explicit immutable scientific context with typed capability records and one readiness vocabulary.

**WHY THIS WORK REMAINS:** `ResearchSpec`, release inventory and `PopulationFrame` exist; a validated method/profile gate and precise per-modality assay populations do not. There is no `SourceContext` binding release + source identity + `gdcdatamodel2` revision + method versions, no capability record derived from GDC metadata, and no readiness vocabulary anywhere in code. `ProjectRecord` already carries `data_categories` (from `parse_projects`), and `ProjectRecord.program_name` is already parsed, so the discovery input for capability derivation exists.

**CURRENT CODE TO REUSE:** `CohortSpec`, `ResearchSpec`, `PopulationFrame`, `ScientificSource`, `ProjectRecord.data_categories`/`program_name`, existing inventory and metadata parsers, `.upstream/SOURCES.lock.json`.

**CURRENT CODE TO CHANGE:** `research/specs.py`, `research/live.py` inventory, `research/acquisition.py`, `gdc/endpoints.py`, `gdc/parsers.py`, `domain/measurements.py`, `domain/codecs.py`, `storage/readers.py`; a new capability module only if extension fails.

**UPSTREAM SOURCES TO USE:** U1 API/search and pipeline pages; U2 case/sample/aliquot/file/workflow relationships; U3 production provenance; DR46.0 release pin.

**SCIENTIFIC CONTRACT:** all declared cohort cases, explicit assay-eligible subsets and reasoned unknowns; case overlap never establishes matched aliquots. Source/method/profile identity is immutable. Capability is derived from GDC data (project/file metadata), never from cancer-name constants. Every capability record names its modality, mechanism, experimental strategies, workflow types, case/sample resolution, access level and limitations; a missing modality is UNAVAILABLE with a reason, never a negative result. Readiness vocabulary is exactly `EXPERIMENTAL` → `VALIDATED_FOR_REPLAY` → `VALIDATED_FOR_AUTONOMOUS_USE`, attributable to evidence, with LUAD starting at the readiness actually supported (today `EXPERIMENTAL`).

Candidate modality vocabulary to derive: `MUTATION_WXS`, `MUTATION_WGS`, `EXPRESSION_RNASEQ`, `CNV`, `STRUCTURAL_VARIANT`, `FUSION`, `METHYLATION`, `MIRNA`, `RPPA`, `SCRNA_SNRNA`, `CLINICAL`, `SURVIVAL`. None beyond today's three lanes is available yet.

**IMPLEMENTATION STEPS:** 1. Extend `ResearchSpec` with the smallest source/method/validation bindings, or add a sibling profile type if the run spec would bloat. 2. Derive capabilities from `/projects` metadata plus bounded per-strategy `/files` aggregate counts (no per-file listing, unknown strategy fails closed). 3. Keep acquisition completeness separate from assay availability. 4. Bind readiness to reconciliation/replay evidence and reject unsupported method/profile activation. 5. Optionally expose a bounded `capability` CLI (one project request plus a capped number of files requests) that must work for TCGA-LUAD and a non-LUAD fixture project id with no cancer-specific branch.

**DATA / ACQUISITION PLAN:** `/status`, exact project, paged cases and filtered `/files` metadata; ceil(C/P) case requests plus metadata pages (capability derivation itself: ~1 project request + ≤12 files requests per cohort). No assay downloads; estimate remaining metadata requests before launch and cache source hashes. Recheck source context at completion rather than silently mixing release changes.

**SCHEMA / PERSISTENCE IMPACT:** coordinated `ResearchSpec` and source/population contract extension plus capability artifacts; no duplicate permanent state model; campaign-profile persistence only when P16 needs it.

**VERIFICATION:** later `python -m pytest tests/unit/test_research_specs.py tests/contracts/test_parsers.py tests/integration/test_scientific_reads.py`; add mixed-release, ambiguous aliquot, assay-unavailable, unknown-strategy fail-closed and unvalidated-profile cases, plus a non-LUAD fixture project.

**ACCEPTANCE CRITERIA:** every enabled method can explain its eligible population/source and readiness; unknown coverage never becomes negative evidence; one CLI/function emits typed capability for LUAD and a non-LUAD project id with no cancer-specific branches.

**STOP BOUNDARY:** no continuous scheduler or scientific inference; no mutation-method or Wide/Deep redesign; no controlled-access data. **DEFERRED WORK:** P16; autonomous promotion to `VALIDATED_FOR_AUTONOMOUS_USE` requires the P05/P11 gates. **CANONICAL DOC UPDATE:** Architecture current source/capability behavior; Product Scope readiness; Data Strategy provenance.

### P04 — Workflow provenance and comparability

**STATUS:** PARTIAL. **OBJECTIVE:** put typed workflow identity into the evidence plane so values from different workflows are never silently compared, without building an ontology.

**WHY THIS WORK REMAINS:** documentation facts are complete (Architecture workflow section and the pinned upstream table here), but the data plane is not: `ScientificSource` has no workflow/caller/strategy/annotation fields; the mutation occurrence scan fetches only occurrence/case/gene identity; expression workflow identity comes from a single `/files` request capped by `expression_file_sample_size=5` (`research/specs.py`), so it cannot cover the cohort.

**CURRENT CODE TO REUSE:** `parse_files_provenance`, `CnvOccurrence.caller`, `ScientificSource`/`OperationalSource`, `.upstream/SOURCES.lock.json` role classification, the expression files query builder.

**CURRENT CODE TO CHANGE:** `domain/measurements.py` (additive optional workflow fields), `research/acquisition.py` (aggregate full-coverage workflow query), `research/discovery.py` (record the occurrence-scan field-set identity), `gdc/parsers.py` (strict handling of new optional fields), affected codecs/readers/tests.

**UPSTREAM SOURCES TO USE:** U1 current pipeline documentation, U2 workflow/strategy field authority, U3 production provenance; the lock's current/historical classification is consumed, not re-derived.

**SCIENTIFIC CONTRACT:** workflow identity is provenance, never a measured field; cross-workflow comparison is forbidden by default (`Compatibility.UNVERIFIED` stays until a declared comparability contract exists); unknown workflow becomes a recorded `UNKNOWN_WORKFLOW` limitation, never silently dropped; missing workflow coverage keeps the lane PARTIAL, never a silent full-coverage claim.

**IMPLEMENTATION STEPS:** 1. Extend `ScientificSource` additively (candidate optional fields: `workflow_family`, `caller_family`, `strategy`, `annotation_context`); version the codec/reader only if semantics require. 2. Replace the 5-file expression workflow sample with a deterministic aggregate rule (for example `facets=analysis.workflow_type,experimental_strategy`, or paged distinct-field aggregation) covering all cohort expression files, recording per-workflow counts. 3. Record the occurrence scan's field-set identity in the scan document so a later field extension cannot be confused with reconciled V2 semantics. 4. Add strict parser support plus fixtures. 5. Re-render Repository Facts only if a code constant changes.

**DATA / ACQUISITION PLAN:** +1 aggregate `/files` request per cohort; no byte-heavy change. Any scan field extension is decided in P07 with its measured byte gate.

**SCHEMA / PERSISTENCE IMPACT:** additive optional fields; discovery-result schema only if the scan document gains fields; old artifacts remain readable under strict unsupported-version rejection.

**VERIFICATION:** later `python -m pytest tests/contracts/test_parsers.py tests/integration/test_expression_discovery_replay.py tests/reconciliation`; add aggregate workflow parsing, coverage-below-full-population (lane PARTIAL) and unknown-workflow cases; replay bytes unchanged.

**ACCEPTANCE CRITERIA:** every persisted source answers "which workflow/caller family produced this value" where GDC exposes it; expression workflow coverage is complete for the cohort before any comparability claim.

**STOP BOUNDARY:** no ontology, no pipeline re-runs, no ASCAT-vs-ABSOLUTE value comparison. **DEFERRED WORK:** per-occurrence MAF caller attribution (needs P06 open-file path). **CANONICAL DOC UPDATE:** Architecture workflow-pointer; Data Strategy §12; REPOSITORY_FACTS keys if constants change.

### P05 — Complete universe and operational shards

**STATUS:** PARTIAL. **OBJECTIVE:** replace the scientific prefix limit with full eligible membership, durable shard status and global reduction.

**WHY THIS WORK REMAINS:** `DISCOVERY_UNIVERSE_METHOD = "GENE_ID_ASC_INDEXED_PREFIX_V1"`, `UNIVERSE_PAGE_CAP = 10` and `MAX_UNIVERSE_LIMIT = 1000` bound scientific scope; the occurrence scan is already all-or-nothing (its single project-global scan is correct shard semantics for one shard) but there is no shard ledger, no resumable universe sweep and no terminal gate shared with Stage 4 reduction. `TestedUniverse` already carries `ordered_ids`, `source`, `release`, `filter_description`, `order`, `offset`, `requested_limit`, `reported_total`, `complete` and `membership_hash`, so the identity plumbing exists.

**CURRENT CODE TO REUSE:** `TestedUniverse`, `acquire_gene_universe` (keep its duplicate/order/total-stability checks), fail-closed occurrence pagination, expression batch merging, artifact store.

**CURRENT CODE TO CHANGE:** `domain/discovery.py`, `domain/measurements.py`, `research/specs.py`, `research/discovery.py`, `research/acquisition.py`, `research/expression_discovery.py`, codecs and strict readers; a small shard-ledger module only if existing artifact contracts cannot express required/completed/failed status.

**UPSTREAM SOURCES TO USE:** U1 `/genes` pagination/filter semantics; U2 gene/source identity where applicable.

**SCIENTIFIC CONTRACT:** every eligible release-bound protein-coding gene unless a different universe is explicitly justified, ordered by ascending gene_id. Universe identity = (release, biotype, order, ordered IDs membership hash, reported total, complete=true). Operational gene/case/file shards cannot change population, ranking or testing family. A required shard that failed blocks complete global results — no partial universe reduction is ever persisted as complete. Historical prefix results stay honestly labelled.

**IMPLEMENTATION STEPS:** 1. Introduce a complete-universe method value (candidate `GENE_ID_ASC_INDEXED_COMPLETE_V1`), remove the scientific 1,000-gene cap and keep only a defect guard ceiling (for example 100,000) that is a sanity check, not a sampler. 2. Enumerate to the verified total with uniqueness/order checks; persist the universe hash. 3. Persist required shard identities/status/source hashes and per-page artifacts so a failed sweep resumes without re-reading cached pages. 4. Accumulate mathematically valid sufficient statistics. 5. Add the terminal-all-required gate before Stage 4 reduction, Stage 5 reduction and the future Stage 6 scan may finalize. 6. Finalize global ranking only after required data completes. 7. Keep historical prefix results labelled.

**DATA / ACQUISITION PLAN:** approximately ceil(G/P) gene pages — order of magnitude 195–200 pages of 100 genes, ≈10 MB — plus the unchanged occurrence scan (~36 pages, ~104 MB measured) and expression batches proportional to ceil(G/Bg) × ceil(C/Bc). Full-universe expression is the byte-risk case: roughly 800–1,200 values/availability requests and ~150–250 MB worst case for a LUAD-scale cohort; publish a data-volume precheck artifact (population, expected requests/bytes, shard plan, cache, retention) before the first full-universe expression run, and split expression into gene-shards reduced incrementally if the projection exceeds ~1 GB. API bytes must be estimated from bounded responses; no file download required by this unit. Cache completed immutable shards.

**SCHEMA / PERSISTENCE IMPACT:** universe/completion contract, spec `shard_size` and result readers change together; operational shard manifests are not a second scientific state.

**VERIFICATION:** later `python -m pytest tests/integration/test_discovery_replay.py tests/integration/test_expression_discovery_replay.py tests/science/test_discovery_reduction.py`; add a synthetic multi-page completeness driver, shard-size invariance (for example 100 vs 250 gene batches on the same frozen scans), shard-order invariance, shuffled shard boundaries, retries, missing/duplicate pages, changed totals, failed-required-shard fail-closed (no reduction published) and budget exhaustion. Known drivers may be inspected as a sanity signal but are never acceptance criteria.

**ACCEPTANCE CRITERIA:** equivalent membership/measurements/ranks across shard layouts; a complete universe artifact with membership hash; Stage 4 survivor ordering runs over the full eligible universe; no run can complete discovery with a required shard missing; no per-shard top-k union masquerades as global discovery.

**STOP BOUNDARY:** retain existing descriptive methods; do not change V2 measurement semantics, CNV/expression methods or add endpoints. **DEFERRED WORK:** CNV project-wide shards (P09); full-universe expression execution may be sequenced as its own follow-on run after mutation uses the complete universe; inference and new modalities. **CANONICAL DOC UPDATE:** README current universe; Architecture/Data Strategy completion semantics; REPOSITORY_FACTS (universe method + spec schema) via renderer.

### P06 — Selected open harmonized files, only when needed

**STATUS:** REQUIRED, conditional on a named scientific consumer. **OBJECTIVE:** add one narrow open-file path when API evidence cannot answer the chosen method.

**WHY THIS WORK REMAINS:** metadata access exists; no runtime `gdc-client` acquisition adapter was found. An upstream clone is not an installed integration; `.upstream/envs/gdc-client-install-contract.txt` records that `gdc-client@0602ecb` is pinned but not installed. The endpoint allowlist excludes `/data`, `/manifest`, `/slicing`, `/files/versions` and `/submissions`; segment-CNV and survival endpoints are not allowlisted because no validated consumer exists yet.

**CURRENT CODE TO REUSE:** transport bounds, strict parsers, `ArtifactStore`, `ScientificSource` and source hashes, `FORBIDDEN_PATHS` discipline.

**CURRENT CODE TO CHANGE:** `gdc/endpoints.py`, `gdc/parsers.py`, `research/acquisition.py`; add a narrow `gdc/open_files.py` adapter only for the selected product; bind provenance in existing contracts/readers. Segment endpoints land only with P09's declared focal-event method; `/analysis/survival` only inside a declared inferential comparison contract.

**UPSTREAM SOURCES TO USE:** U1 search/retrieval and selected pipeline; U2 file/aliquot/workflow fields; U4 manifest/download implementation.

**SCIENTIFIC CONTRACT:** deterministic selection of open, compatible high-level files for the declared assay population; UUID, release, workflow, size and checksum bind parsed evidence. Ambiguous or incomplete selection is unavailable, not an arbitrary first file. Every new endpoint or file source is admitted only by a named method contract; multi-GB automatic acquisition is prohibited (redesign around indexed/higher-level data first). No GDC token, no controlled access.

**IMPLEMENTATION STEPS:** 1. Document why API summaries fail the method. 2. Produce an exact metadata manifest and byte estimate (population, file count, `sum(file_size)`, API alternative, retention). 3. Enforce access/product/budget allowlists. 4. Invoke bounded `gdc-client` without GDC tokens against the pinned clone/contract, validate checksum and parse one product; every stage emits typed events. 5. Register immutable source identity and explicit retention.

**DATA / ACQUISITION PLAN:** F and bytes are unknown until product/population selection; preflight must fill both. Shard by file; completion requires all selected files or scientifically justified explicit exclusions. Compare API request cost against high-level files; reconsider multi-GB plans. Do not fetch BAM/FASTQ by default.

**SCHEMA / PERSISTENCE IMPACT:** file-source/manifest reference extension if existing sources are insufficient; never embed raw files in Jev projections.

**VERIFICATION:** later `python -m pytest tests/contracts/test_open_access.py tests/contracts/test_transport_bounds.py`; add manifest replay, controlled-access refusal, checksum mismatch, interrupted download, duplicate/ambiguous files and parser rejection. Until a real consumer exists, an open-file dry run tests metadata and access checks only (no download).

**ACCEPTANCE CRITERIA:** reproducible selected evidence from verified open files within declared budgets; every new endpoint has a named consumer method and a fixture-backed parser test. **STOP BOUNDARY:** one product only, no general downloader, endpoint construction, `/files/versions`, `/submissions` or `/slicing`. **DEFERRED WORK:** other file formats and modalities until their own contracts. **CANONICAL DOC UPDATE:** Data Strategy implemented file product and limits; Architecture endpoint list when changed.

### P07 — Mutation scientific-method gate

**STATUS:** PARTIAL. **OBJECTIVE:** extend reconciled recurrence only with a specifically justified mutation method.

**WHY THIS WORK REMAINS:** distinct released-case counts are valid descriptive evidence; caller-aware consequence, hotspot/background models and inferential driver support are not established by those counts. The scan currently fetches only occurrence/case/gene identity, so consequence composition and protein-position recurrence are unavailable, and there is no disposition vocabulary beyond retained/cutoff/unavailable.

**CURRENT CODE TO REUSE:** Stage 4 counts, strict occurrence parser, `MethodIdentityRef`, existing discovery result and reconciliation fixtures, the frozen C-derivation contract in `tests/reconciliation`.

**CURRENT CODE TO CHANGE:** `gdc/endpoints.py`, `gdc/parsers.py`, `science/mutation.py`, `science/methods.py`, `domain/discovery.py`, `research/discovery.py`; extend scientific output/codecs only for the selected evidence.

**UPSTREAM SOURCES TO USE:** U1 DNA/WGS semantics, U3/U7 provenance; relevant pinned MAF/annotation source only if needed. Select and inspect a primary GDAN/TCGA mutation-method reference before inferential implementation; no method is approved solely by this plan.

**SCIENTIFIC CONTRACT:** explicit mutation assay population, complete tested genes, variant/record deduplication, consequences and caller context; callable denominator cannot be inferred from indexed positives. Descriptive outputs (counts, composition, positions, hotspot descriptors) carry no p/q values. Inferring driver significance additionally requires a feasible background model and a global multiple-testing family, which the API-only plane does not currently supply. Transcript duplication is protected by restricting composition to canonical rows; missing consequence is NOT_OBSERVED, never negative.

**IMPLEMENTATION STEPS:** 1. Declare the exact method and required inputs. 2. Reconcile event/consequence semantics against the frozen fixtures. 3. Candidate descriptive enrichment: extend the occurrence page builder with canonical consequence fields (`ssm.consequence.transcript.consequence`, `is_canonical`, `protein_start`, `transcript_id`), accumulate per-gene canonical-consequence composition (deduplicate occurrence × consequence pairs under the canonical restriction) and a protein-position histogram under a named method such as `MUTATION_CANONICAL_COMPOSITION_V1`. 4. Measure the scan byte delta on the frozen pages; if enrichment more than roughly doubles current scan bytes (~104 MB → >200 MB), move it to per-gene detail shards (the shared P15 builder) instead of the systematic scan. 5. Add dispositions `RETAIN`/`DROP`/`JEV_REVIEW` with named, versioned trigger constants (DROP = zero observed affected cases; RETAIN = survivor band; JEV_REVIEW = declared trigger such as extreme occurrence-per-case ratio or hotspot concentration). 6. Record the GDAN inferential decision: background-model driver testing (MutSigCV-class) needs patient covariate inputs not obtainable from the API-only plane, so it is `DEFER_WITH_JUSTIFICATION` unless P06 validates the inputs. Split descriptive enrichment from inferential driver testing if they need different validation gates.

**DATA / ACQUISITION PLAN:** detailed `/ssms`/occurrences or selected open MAF only after API-versus-file comparison. The field extension reuses the existing endpoint with a measured byte gate; request/file/byte estimates depend on the chosen method; produce a preflight over the full eligible population, not only known drivers. Reuse cached records.

**SCHEMA / PERSISTENCE IMPACT:** additive typed method evidence and coordinated reader/projection changes where semantics differ; discovery-result schema only if the scan document gains fields.

**VERIFICATION:** later `python -m pytest tests/reconciliation tests/science/test_discovery_reduction.py`; composition equals an independent derivation from the frozen C pages for the panel genes; transcript-duplication guard (canonical rows counted once per occurrence); disposition determinism under shard reordering; no p-values anywhere in the result artifact; method-specific independent expected results for duplicate events, multi-variant cases, annotation mismatch, missing callability and global correction.

**ACCEPTANCE CRITERIA:** every Stage 4 entry carries typed descriptive evidence under the named method; dispositions include an explicit `JEV_REVIEW` path; descriptive and inferential outputs are separately labelled; no model judgment or recurrence rank creates driver significance.

**STOP BOUNDARY:** no weighted mutation score, no significance without the declared contract, no method redesign of V2 counts. **DEFERRED WORK:** inferential driver testing (MutSigCV-class) until inputs exist via P06; other mutation models and functional validation. **CANONICAL DOC UPDATE:** Architecture mutation capability; Data Strategy selected source; REPOSITORY_FACTS (method id) via renderer; Scientific Invariants only if clarification is needed.

### P08 — Expression provenance, QC and disposition gate

**STATUS:** PARTIAL. **OBJECTIVE:** make the expression lane complete-universe, identity-honest and dispositioned, and introduce a comparison only when its design is defensible.

**WHY THIS WORK REMAINS:** existing log2(UQFPKM+1) summaries/Tukey tails run over the Stage 4 universe with a ≤150-request plan gate (`EXPRESSION_REQUEST_PLAN_EXCEEDS_CAP`), minimum tail size 20 and gene batches of 100; they are descriptive case-labelled observations, not raw-count differential expression or matched tumor-normal evidence. They carry no per-modality disposition and cannot nominate: the candidate union is mutation survivors only. Workflow identity is a five-file sample (P04 fixes coverage).

**CURRENT CODE TO REUSE:** `ExpressionSummaryResult`, coverage/availability merging, `run_expression_discovery`, tail descriptors (`EXPRESSION_TAIL_METHOD_ID`, `EXPRESSION_LIMITATIONS`), batch-permutation checks, the P05 shard ledger, `UnavailableLane`.

**CURRENT CODE TO CHANGE:** `research/expression_discovery.py`, `research/acquisition.py`, `science/expression.py`, `science/descriptors.py`, relevant parser/domain output and codecs; `research/cutover.py` union logic lives in P10.

**UPSTREAM SOURCES TO USE:** U1 expression pipeline/API; U2 identity; U5, and U6 only for a needed calculation. A future DE method requires its own primary reference and predeclared design.

**SCIENTIFIC CONTRACT:** RNA-eligible cases/samples/aliquots, explicit unit/transform, workflow/reference annotation, duplicate assay rule and QC/confounding. No missing assay becomes zero. Do not treat normalized UQFPKM as integer-count input to a count model. Units stay distinct (UQFPKM primary; raw counts only if a declared method needs them); Tukey/IQR tails remain descriptive; there is no batch correction (a correction requires a versioned declared justification — none today). Case-labelled values never support matched cross-modal claims without an aliquot contract. Dispositions: RETAIN = observed tail with `valid_n ≥ minimum_tail_n` in the eligible set; DROP = no observed values or `valid_n < minimum_tail_n`; JEV_REVIEW = named conflict/extreme-tail triggers, versioned constants.

**IMPLEMENTATION STEPS:** 1. Consume the complete universe and shard ledger from P05; publish an expression shard terminal gate before reduction. 2. Add the disposition vocabulary plus independent nomination. 3. Hand per-modality candidate sets to P10's union. 4. Check aliquot identity feasibility against U2 and the API fields (extend the availability matrix or add a bounded deterministic `/files` join); if aliquot identity is not API-derivable, keep the recorded limitation — never fake matching. 5. Publish the data-volume precheck artifact before the full-universe run. 6. Reconcile API values and transforms against frozen real data; bind workflow/assay identity and eligibility; validate descriptive features globally. 7. Authorize a contrast/design separately only with adequate replicates, covariates and compatible measurements.

**DATA / ACQUISITION PLAN:** API batches over G and the RNA population for descriptive summaries; high-level STAR count files only if the chosen model requires them. Preflight ceil(G/Bg) × ceil(Crna/Bc) API batches versus F count files and actual bytes (see P05 for the LUAD-scale expression estimate and gene-shard fallback). Store identity/QC exclusions and reusable validated data.

**SCHEMA / PERSISTENCE IMPACT:** richer provenance/QC/disposition outputs need explicit typed fields and reader updates; tails keep their descriptive meaning; expression discovery result schema only when fields change.

**VERIFICATION:** later `python -m pytest tests/integration/test_expression_discovery_replay.py tests/science/test_descriptors.py tests/science/test_lane_composition.py`; independent transform reconciliation, missing assay, duplicate aliquots, confounded design, batch-invariant global results, disposition determinism, a no-batch-correction assertion (no corrected field exists) and an expression-only candidate entering the union without mutation-survivor status.

**ACCEPTANCE CRITERIA:** every expression claim names its population/unit/design; the lane nominates candidates independently with typed dispositions over the complete universe; cross-modal claims still require the aliquot contract; insufficient design reports unavailable inference.

**STOP BOUNDARY:** do not add DE just because expression exists; no differential-expression claims without a declared comparison design. **DEFERRED WORK:** replication (P11) and cross-modal association (P12); subgroup effects; PCA/batch structure analysis. **CANONICAL DOC UPDATE:** Architecture expression status and Data Strategy product choice; REPOSITORY_FACTS (expression result schema) via renderer.

### P09 — Independent CNV discovery

**STATUS:** PARTIAL. **OBJECTIVE:** remove mutation-survivor gating for a validated CNV nomination method.

**WHY THIS WORK REMAINS:** `CNV_SELECTION_RULE = "STAGE4_MUTATION_SURVIVORS_ONLY"`, `MAX_CNV_SURVIVORS=10`, `CNV_PAGE_SIZE=250`, `MAX_CNV_PAGES_PER_GENE=10` and `REQUEST_PLAN_MAX=101` admit only Stage 4 survivors; observed categories cannot establish neutral states or continuous dosage comparability. `/segment_cnvs` and `/segment_cnv_occurrences` are not allowlisted, and no SV representation exists anywhere.

**CURRENT CODE TO REUSE:** `CnvOccurrenceResult`, category mapping/conflict preservation (`scientific.py` five-category mapping), strict paged parser, `run_cnv_discovery`, `CNV_LIMITATIONS`, P03 capability types and P05 shard ledger.

**CURRENT CODE TO CHANGE:** `domain/discovery.py`, `research/specs.py`, `research/cnv_discovery.py`, `gdc/endpoints.py`, parsers/codecs and the composition boundary (P10).

**UPSTREAM SOURCES TO USE:** U1 CNV pipeline, U2 workflow/file identity, U3 WGS production status; evaluate a published recurrent-CNV method only after defining compatible input requirements.

**SCIENTIFIC CONTRACT:** complete eligible universe and CNV assay population; caller/platform-specific positive categories remain distinct from continuous copy number, ploidy, focality and neutral coverage. Caller context is mandatory per record. A gene can nominate without mutation evidence. Absence of an occurrence is never diploid/neutral. Never compare ASCAT vs ABSOLUTE vs DNAcopy values; SV never collapses into CNV; no SV ranking before a validated source/method contract.

**IMPLEMENTATION STEPS:** 1. Add a project-scoped `/cnv_occurrences` page builder (deterministic ascending `cnv_occurrence_id`, bounded shards) for a project-wide scan mode (candidate `CNV_PROJECT_OCCURRENCE_SCAN_V1`), deriving per-gene case sets, categories and callers locally; keep the per-gene query mode for follow-up depth. 2. Implement the shard scan with the P05 ledger and terminal gate; per-gene reduction deduplicates distinct cases per exact provider category (`UNIQUE_CASE_WITHIN_EXACT_PROVIDER_CATEGORY`), and conflicts are retained rather than summed or resolved. 3. Replace mutation-survivor scope binding with explicit universe/source/population binding and per-gene dispositions (named recurrent amplification/deletion case-count thresholds — constants, not p-values). 4. Let the union (P10) include independent CNV RETAIN sets. 5. Record SV as a separate future lane: capability UNAVAILABLE with the documented reason (SvABA/Manta WGS SV is current, but production repositories are not public and no validated API-only method exists yet). 6. Compare per-gene API scans with compatible high-level gene/segment files before committing; adopt segment endpoints only if the declared focal-event method requires segment context.

**DATA / ACQUISITION PLAN:** run a probe request to measure LUAD `/cnv_occurrences` row count before committing; if projected >~500 MB or >~3,000 pages, split by case_id ascending shards and reduce incrementally. The naïve per-gene API scale is sum over G of ceil(events(g)/P) — potentially tens of thousands of requests — so estimate against F selected compatible files with actual bytes before choosing; do not silently retain survivor-only sampling to save cost.

**SCHEMA / PERSISTENCE IMPACT:** CNV result scope semantics change; coordinated cutover and old-result rejection from independent-discovery consumers; CNV discovery result schema only when fields change.

**VERIFICATION:** later `python -m pytest tests/contracts/test_cnv_discovery_contracts.py tests/integration/test_cnv_discovery_replay.py`; add multi-page fixture scans, shard invariance, conflicts retained, caller coverage, CNV-only nomination (evidence for a non-mutation-survivor gene), absence ≠ diploid, mixed callers, overlapping categories, global shard equivalence and release-mismatch fail-closed.

**ACCEPTANCE CRITERIA:** the CNV lane produces complete project-wide typed evidence with dispositions over its own population; a CNV-only eligible gene can reach P10; positive-only data never imply a neutral denominator; SV and other modalities carry honest capability records.

**STOP BOUNDARY:** no SV/CNV ranking fusion; no methylation/miRNA/RPPA/fusion/scRNA methods until each has its own contract; no plugin framework; no automatic cross-caller pooling. **DEFERRED WORK:** allele-specific/LOH/purity-ploidy context (requires segment/ABSOLUTE products via P06); dosage-expression association. **CANONICAL DOC UPDATE:** README/Architecture CNV status and Data Strategy acquisition; REPOSITORY_FACTS (cnv result schema) via renderer.

### P10 — Deterministic modality union and integrated baseline

**STATUS:** PARTIAL. **OBJECTIVE:** allow independently nominated genes into the existing canonical state and Wide path.

**WHY THIS WORK REMAINS:** `compose_discovery_states` loops over mutation survivors; acquiring expression independently is not independent expression admission. There is no per-modality candidate set and no typed place for a pending-semantic-review entry.

**CURRENT CODE TO REUSE:** `compose_discovery_states`, `StatisticalState`, `UnavailableLane`, `research/ranking.py`, Wide policies and Stage 8 comparator.

**CURRENT CODE TO CHANGE:** `research/cutover.py`, expression/CNV discovery result nomination fields, `domain/discovery.py`, `domain/scientific.py` if necessary, `research/ranking.py`, codecs, projections and finalization consumer where provenance changes.

**UPSTREAM SOURCES TO USE:** validated P07–P09 method contracts; no new provider capability required.

**SCIENTIFIC CONTRACT:** union of globally derived per-modality nominations with exact release/cohort/universe compatibility; one state per gene; unavailable modalities remain explicit. Candidate union = RETAIN(mutation) ∪ RETAIN(expression) ∪ RETAIN(cnv) ∪ preserved `JEV_REVIEW` sets. Until Arm Jev exists (P13), `JEV_REVIEW` entries are carried as typed pending-semantic-review, never silently dropped and never admitted. Preserve per-modality ranks and nomination reasons without an opaque weighted score.

**IMPLEMENTATION STEPS:** 1. Specify deterministic retain/drop criteria for each validated modality. 2. Build a sorted deduplicated union with provenance. 3. Compose evidence for every union member, allowing legitimate missing lanes. 4. Bind the same pre-Jev evidence to the baseline and Wide. 5. Keep operational candidate caps explicit and separate from universe membership.

**DATA / ACQUISITION PLAN:** cached validated lane results; missing follow-up lane acquisition requires its own bounded declared contract, not implicit network access during composition.

**SCHEMA / PERSISTENCE IMPACT:** nomination/union provenance and baseline semantics change; coordinate results, state projection, policy identities and strict readers.

**VERIFICATION:** later `python -m pytest tests/integration/test_cutover.py tests/science/test_lane_composition.py tests/jev/test_ranking.py tests/integration/test_stage8_finalize.py`; add expression-only/CNV-only genes, mixed releases, duplicate union membership and unavailable lanes.

**ACCEPTANCE CRITERIA:** all nominated modalities can contribute; baseline/Wide share evidence identity; no second integrated state. **STOP BOUNDARY:** no mandatory Arm Jev or new statistical method. **DEFERRED WORK:** P11/P13. **CANONICAL DOC UPDATE:** Architecture current union and Jev Design comparator provenance.

### P11 — Evidence maturity, information roles and honest validation

**STATUS:** PARTIAL. **OBJECTIVE:** prevent semantic prioritization and evaluation labels from becoming scientific validation.

**WHY THIS WORK REMAINS:** typed quality/missingness and optional blinded evaluation exist, but scientific maturity/role contracts are absent; `build_projection` includes cancer-census status and no test forbids that annotation from reaching discovery inputs. There is no evidence-level field and no deterministic replication design.

**CURRENT CODE TO REUSE:** `GeneAnnotation`, typed measurements/methods, `research/prospective.py` grouped blinded evaluation, immutable evidence, Stage 8 limitations.

**CURRENT CODE TO CHANGE:** `domain/scientific.py`, `domain/evidence.py`, `jev/projection.py`, `research/specs.py`, `research/finalize.py`, dossier contracts and codecs; extend offline evaluation separately from runtime; add a new evidence-level/role module only if extension fails.

**UPSTREAM SOURCES TO USE:** primary references for the selected method/validation design; current external source/version/licensing before any labels are adopted. No external source is approved here.

**SCIENTIFIC CONTRACT:** classify information as `DISCOVERY_INPUT`, `VALIDATION_LABEL`, `ORTHOGONAL_FOLLOW_UP` or `KNOWN_CANCER_CONTEXT`. If census labels evaluate discovery, exclude them from feature construction, thresholds and semantic admission. Evidence levels `MEASURED` → `DESCRIPTIVE_CANDIDATE` → `STATISTICALLY_SUPPORTED` → `INTERNALLY_REPLICATED` → `EXTERNALLY_REPLICATED` → `FUNCTIONALLY_SUPPORTED` are pure deterministic functions of persisted typed evidence; Jev never promotes them and invalid judgment fails closed. Scientific holdouts are case-disjoint and predeclared, unlike operational shards or reviewer-label group splits. `FUNCTIONALLY_SUPPORTED` stays unattainable until the P17 contract exists.

**IMPLEMENTATION STEPS:** 1. Bind information roles to profile and projection eligibility; tag `GeneAnnotation.cancer_census` as `KNOWN_CANCER_CONTEXT`. 2. Remove evaluation-only labels from discovery projections. 3. Derive maturity from attributable measurement/statistical/replication/functional evidence. 4. Add a versioned deterministic replication partition (hash-sorted case IDs, one case in exactly one partition, no universal 60/40 or 70/30 default — ratio and power rationale are named per method; insufficient N reports replication unavailable with reason) and persist the partition as an immutable artifact. 5. Freeze thresholds before any holdout evaluation. 6. Add a machine-checked leakage guard: no validation label, `KNOWN_CANCER_CONTEXT` annotation or `ExternalKnowledgeRef` with a non-follow-up role may be reachable from feature construction, disposition triggers, Arm/Wide projections or admission.

**DATA / ACQUISITION PLAN:** existing evidence initially; no new acquisition until a validation source/design is chosen. Split manifests hash membership and preserve seed/rule.

**SCHEMA / PERSISTENCE IMPACT:** explicit maturity/roles and validation references with coordinated readers/projections/final results; preserve old interpretations as historical; state schema only when the codec changes.

**VERIFICATION:** later `python -m pytest tests/jev/test_projection.py tests/unit/test_prospective.py tests/integration/test_stage8_finalize.py` plus the new leakage guard; add derivation-table tests for each level's exact preconditions, partition disjointness/determinism, label-exclusion, same-case leakage, unavailable replication and Jev-output-invariance of evidence level.

**ACCEPTANCE CRITERIA:** every claimed level has deterministic evidence; validation labels cannot influence the evaluated discovery path; unavailable replication is explicit.

**STOP BOUNDARY:** no functional dataset or automatic inferential promotion. **DEFERRED WORK:** `EXTERNALLY_REPLICATED` (requires a separately validated independent campaign/cohort; P16 provides only the campaign-selection machinery) and `FUNCTIONALLY_SUPPORTED` (needs P17). **CANONICAL DOC UPDATE:** Product Scope, Jev Design and Architecture implemented maturity/roles; REPOSITORY_FACTS (state schema) via renderer.

### P12 — One deterministic pathway or cross-modal method

**STATUS:** REQUIRED, conditional on scientific eligibility. **OBJECTIVE:** add a justified relationship-level evidence method without fabricated pathway scores.

**WHY THIS WORK REMAINS:** integrated lane display is not pathway analysis or sample-matched association.

**CURRENT CODE TO REUSE:** `StatisticalState`, population/source/method identities, deterministic method conventions and missingness.

**CURRENT CODE TO CHANGE:** `science/methods.py` plus one narrow method module, `domain/scientific.py`, `research/cutover.py`, codecs and bounded projection if a semantic consumer is justified.

**UPSTREAM SOURCES TO USE:** selected primary GDAN/TCGA-compatible analysis method and current pathway provider version/licensing/identifier mapping; U2 for sample/aliquot relationships. Selection of that source/method is a prerequisite, not a fabricated completed decision. Candidate sources to evaluate against (license, versioning, Ensembl gene-id mapping fidelity, GDAN/TCGA precedent): MSigDB (downloadable snapshot, academic license, symbol mapping needed), Reactome (CC-BY, stable identifiers, public API — current default candidate, mapped to Ensembl gene ids and stored as a hashed versioned snapshot), GO (CC-BY, large). The selection record is itself a deliverable.

**SCIENTIFIC CONTRACT:** pathway membership is external deterministic data with recorded source, version, license reference, mapping method and hash; enrichment background is the actual tested/mapped universe; no membership mutation at runtime; no-membership ≠ negative. Enrichment inference is implemented only under the declared background/FDR contract with named constants; otherwise membership plus coverage only. Cross-modal analysis instead requires a declared compatible assay intersection, sample mapping, effect/null and multiple-testing family. Split these into separate implementation prompts when both are desired.

**IMPLEMENTATION STEPS:** 1. Choose one question/source/method and prove eligibility; record the decision before code. 2. Freeze mapping and population. 3. Calculate deterministic effects/statistics globally. 4. Persist exclusions, uncertainty and limitations. 5. Project only summaries with an actual Wide/Deep consumer.

**DATA / ACQUISITION PLAN:** versioned membership table or cached compatible modality evidence; one-time snapshot (tens of MB or API pagination) retained immutable and re-fetched only on version change; quantify file count/bytes/licensing before ingestion. No raw sequencing. Retain source/mapping hashes and universe membership.

**SCHEMA / PERSISTENCE IMPACT:** one typed evidence extension; synchronized codecs/projection only if consumed; shared state-schema change only with P11's if both alter the same codec.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_methods.py tests/jev/test_projection.py` plus method-specific independent reference cases for mapping loss, wrong background, incompatible assay matching and global FDR; mapping round-trip tests on known genes (for example TP53 to expected pathways) and a no-membership ≠ negative assertion; deterministic recomputation hash test.

**ACCEPTANCE CRITERIA:** reproducible source-grounded relationship evidence naming source/version/hash; unavailable when matching or method inputs fail.

**STOP BOUNDARY:** no generic pathway engine, omnibus scores or weighted target score. **DEFERRED WORK:** enrichment significance without the declared family/FDR contract; other relationship methods. **CANONICAL DOC UPDATE:** Architecture supported method and Data Strategy source.

### P13 — Revalidate Jev questions and conditional Arm review

**STATUS:** PARTIAL; Arm itself is optional. **OBJECTIVE:** preserve the semantic boundary while exposing only useful new validated evidence.

**WHY THIS WORK REMAINS:** typed primitives/validation exist; richer evidence (P07–P12) and information-role restrictions need corresponding bounded questions. New batching/Arm behavior cannot be assumed already supported. No committed capability decision record exists outside this plan's table, and no Arm question set or `JEV_REVIEW` consumer exists.

**CURRENT CODE TO REUSE:** `TypeSafeAdapter`, `JevService`, question definitions, applicability, projections and answer validation; Python Wide/next-move consumers.

**CURRENT CODE TO CHANGE:** `jev/questions.py`, `projection.py`, `contracts.py`, `service.py`, `typesafe_adapter.py` only for necessary adapter gaps; discovery disposition only if Arm is adopted; a persisted decision record only if the unit changes capability posture.

**UPSTREAM SOURCES TO USE:** current official TypeSafe primitives/SDK/pattern docs and feature-discovery cookbook cited above; recheck failed direct page retrieval before new API use.

**SCIENTIFIC CONTRACT:** a semantic question interprets under-ranking/coherence/uncertainty that deterministic arithmetic cannot decide exactly. Input is one bounded typed target/revision; output cannot change facts, maturity or select arbitrary tools. Optional Arm consumes only `JEV_REVIEW` entries — strong deterministic RETAIN and clear DROP bypass it — and its outcome is preserve-or-drop semantic only; it may not alter measured facts, evidence level or admission (admission stays Python). A fail-closed Arm leaves the entry unpreserved, recorded as such, never admitted and never silently dropped. Candidate arm question: one bounded question per modality, "does this structured within-modality evidence contain a potentially important pattern that conventional ranking underrepresents?", as Noul plus at most one Choice dominant-pattern answer, with a named question-set version (`arm-v1` candidate).

**IMPLEMENTATION STEPS:** 1. Record input/question/primitive/applicability/failure/Python-consumer for each proposed change, including why deterministic code cannot answer it. 2. Keep current valid questions. 3. Add only justified dimensions after P10/P11. 4. If Arm has no concrete residual semantic question, mark it unnecessary — evaluate against the current Wide question set before adding a new question. 5. Add bounded per-lane arm projections (mutation composition / expression tail / CNV categories). 6. Wire Arm after deterministic disposition and before union (P10), with ranking/admission untouched. 7. Extend the shared failure corpus before any operational batching.

**DATA / ACQUISITION PLAN:** immutable typed evidence only; replay/stub responses first. Provider call budget follows eligible review targets (≤ `JEV_REVIEW` population per run), never raw genomic row count. Cache reused.

**SCHEMA / PERSISTENCE IMPACT:** change question/projection/cache identity only when semantics change; no preemptive version bump. A new Arm evaluation purpose and registered question-set artifact only if adopted.

**VERIFICATION:** later `python -m pytest tests/jev tests/integration/test_deep_slice.py tests/integration/test_hypothesis_stage.py`; explicitly cover timeout, transport/empty/malformed responses, wrong types/questions/versions, missing/extra fields, non-finite/range values, duplicate answers, partial batch, target/revision mismatch and invalid applicability; Arm-may-not-alter-facts test; union test (RETAIN ∪ preserved JEV_REVIEW). Failure cannot silently retain/admit/advance a target or imply scientific completion; operational finalization may still record ABSTAIN/failure.

**ACCEPTANCE CRITERIA:** each question has a semantic need and deterministic consumer; invalid output has typed failure; evidence level is unchanged by judgments; Arm runs only on `JEV_REVIEW` entries.

**STOP BOUNDARY:** no autonomous question evolution, label-tuned runtime, model tool selection, mandatory Arm layer or admission-threshold change; no Wide question-set bump unless a field genuinely cannot be projected from the current state. **DEFERRED WORK:** optional performance changes until measured need; cascades/confidence routing until a concrete consumer exists. **CANONICAL DOC UPDATE:** Jev Design implemented questions and failure contract; REPOSITORY_FACTS (arm question set) via renderer if adopted.

Capability decisions for this plan (design choices, not new provider guarantees):

| Capability | Decision | Rationale |
|---|---|---|
| Noul / Choice / Score | KEEP | Existing adapter and owned validation; select primitive per bounded question. |
| Multiple questions per target | KEEP | Existing `system_one` question map. |
| Multiple-target batching / speculative fan-out | DEFER | Revalidate SDK behavior, identity association, applicability and partial failure first. |
| Semantic reranking | KEEP existing Python-owned ranking; DEFER new schemes | Semantic outputs remain policy inputs; evidence facts do not change. |
| Confidence routing | DEFER expansion | Requires held-out calibration and declared Python thresholds; confidence is not genomic significance. |
| Semantic feature discovery | DEFER to offline study | Cookbook is a labelled supervised experiment, not runtime scientific validation. |
| Uncertainty / action-value judgment / hypothesis critique | KEEP bounded existing roles | Extend only where a registered action and validated evidence make the question meaningful. |
| Cascades | DEFER | Add only for measured cost/quality benefit with fixed stop/failure semantics. |
| Model-controlled actions, measurements or maturity | REJECT | Violates deterministic scientific and control ownership. |

### P14 — Researcher run ownership isolation

**STATUS:** PARTIAL infrastructure, REQUIRED product boundary. **OBJECTIVE:** let optional researcher runs reuse science without affecting autonomous runtime state.

**WHY THIS WORK REMAINS:** `ResearchOwnership` is an exclusive directory lock; it does not encode `SYSTEM_AUTONOMOUS` versus `RESEARCHER_RUN` ownership, and operator flags currently feed the same run scope. Operator selection paths require ownership checks before being exposed alongside a Program.

**CURRENT CODE TO REUSE:** repository run IDs, artifact paths, exclusive lock, strict readers and immutable source caches (GDC cache rows carry request hashes and Jev cache entries are hash-bound, so provenance-exact sharing is already safe).

**CURRENT CODE TO CHANGE:** `storage/ownership.py`, `repositories.py`, `database.py`, `research/specs.py`, `research/live.py` operator-selection boundary and CLI/API mutation entry points actually exposing researcher runs.

**UPSTREAM SOURCES TO USE:** NONE; local ownership contract.

**SCIENTIFIC CONTRACT:** same methods/populations can be used in different owner contexts, but specs, admission, queues, actions, evidence, hypotheses, dossiers and future Campaign progression are isolated. A researcher run may never write into the autonomous scope and vice versa (enforced bilaterally at the registration layer and by test). Shared immutable source bytes are acceptable only with exact provenance. The program worker is always `SYSTEM_AUTONOMOUS`; operator deep flags on an autonomous run are rejected.

**IMPLEMENTATION STEPS:** 1. Bind owner context at run creation (`execution_ownership` in the run contract). 2. Scope all writable/readback scientific relations. 3. Reject cross-owner mutation and selection in both directions. 4. Share only verified immutable cache entries. 5. Expose researcher CLI mode; reject autonomous-run deep overrides. 6. Require later explicit versioned code/science changes for researcher findings to influence autonomy.

**DATA / ACQUISITION PLAN:** NONE beyond existing run sources; cache ownership metadata does not authorize new acquisition.

**SCHEMA / PERSISTENCE IMPACT:** run ownership/storage contract; preserve historical runs, do not guess their owner or rewrite evidence; if P16 later alters the same codec, land one coordinated cutover rather than two.

**VERIFICATION:** later `python -m pytest tests/test_ownership_recovery.py tests/test_persistence_guards.py tests/test_api.py`; add adversarial cross-owner references (both directions), shared-cache corruption, operator selection and concurrent-write cases.

**ACCEPTANCE CRITERIA:** researcher activity cannot mutate any autonomous scientific/control state or selection input.

**STOP BOUNDARY:** no Lab UI redesign, multi-tenant server or approval loops. **DEFERRED WORK:** optional researcher interface. **CANONICAL DOC UPDATE:** Product Scope and Architecture implemented isolation.

### P15 — One real follow-up and deterministic dispatch policy

**STATUS:** PARTIAL. **OBJECTIVE:** add one evidence-producing investigation step and an explicit Python selection rule where existing ambiguity blocks autonomous progress.

**WHY THIS WORK REMAINS:** current actions check integrity/faithfulness or summarize existing expression/CNV evidence; registered actions create no new measured evidence. `decide_next_move` can request follow-up, selection policy is literally `EXPLICIT_SELECTION_ONLY` (`research/deep.py`), and multiple eligible dispatch choices can require explicit operator selection. This is not unrestricted autonomous scientific experimentation.

**CURRENT CODE TO REUSE:** `science/actions.py`, `domain/actions.py`, `research/deep.py` (`FOLLOWUP_LIMIT=3`, `EVIDENCE_ITERATION_LIMIT=2`), `nextmove.py`, `investigation.py`, immutable revisions, hypotheses and Stage 8; the P07 per-gene occurrence-detail builder (shared contract — implement once in P07, reuse here).

**CURRENT CODE TO CHANGE:** existing registry/eligibility/dispatch functions and `research/specs.py`; one method adapter and typed evidence/action output; finalization summaries only if required.

**UPSTREAM SOURCES TO USE:** primary source/method for the selected follow-up from P07–P12 or P17, not every GDC repository.

**SCIENTIFIC CONTRACT:** one candidate, explicit remaining question, bounded deterministic method/population and evidence output. A candidate action (for example `OCCURRENCE_DETAIL_EVIDENCE_V1`) asks a fixed scientific question — canonical consequence composition and protein-position recurrence for this gene in this cohort — over bounded per-gene `/ssm_occurrences` pages with the P07 composition method identity. Python resolves eligibility, cost, choice and stopping; unresolved choice abstains. Selection switches from `EXPLICIT_SELECTION_ONLY` to a named versioned deterministic policy (candidate `deep-action-policy-v1`) with a declared priority table (for example: not-yet-executed evidence-producing actions whose eligibility holds first; integrity checks on a contradicted revision second; ABSTAIN when none resolve), operator override preserved. Autonomous dispatch is gated by the run-level ownership flag (P14): `SYSTEM_AUTONOMOUS` runs may auto-dispatch inside the existing caps; researcher runs are unchanged. Untestable hypotheses remain NOT_EVIDENCE.

**IMPLEMENTATION STEPS:** 1. Choose one validated follow-up. 2. Register typed inputs/output, budget and eligibility; a measured observation payload (not a synthetic "VERIFIED" check) enters a new immutable revision; a typed unavailable observation with reason on failure. 3. Specify attributable deterministic action choice with scientific rationale, never alphabetical registry order. 4. Dispatch once against the exact revision. 5. Produce a new immutable revision, rejudge and finalize through existing Stage 8. 6. Keep the CLI deep-action path as an override.

**DATA / ACQUISITION PLAN:** reuse cached evidence where sufficient; otherwise bounded candidate/method-specific API/file preflight under P06. Per candidate: ≤40 pages of 250 records. The retained TP53 occurrence fixture contains one 521,746-byte page (~522 kB); linear scaling of that retained page to the 40-page action cap would be ~20.9 MB per candidate before protocol/cache overhead. That is an illustrative fixture-based bound, not a measured campaign-wide page-size distribution; the action preflight must estimate or measure its actual request volume before execution. Persist source and action budgets; page-cap overrun = unavailable observation, never a truncated claim. No arbitrary URL or generated query.

**SCHEMA / PERSISTENCE IMPACT:** registered action/method and evidence payload extension; coordinated reader/projection/finalization changes; preserve old chain and unsupported-version rejection. Bump the evidence schema only when the codec changes.

**VERIFICATION:** later `python -m pytest tests/science/test_actions.py tests/science/test_nextmove.py tests/integration/test_deep_slice.py tests/integration/test_hypothesis_stage.py tests/integration/test_stage8_finalize.py`; exercise duplicate action, ambiguous choice, unavailable method, stale revision, budget stop, policy determinism (same evidence → same action; unresolvable → ABSTAIN), E0 immutability under action execution, composition equals the P07 reducer output, bounded acquisition and replay.

**ACCEPTANCE CRITERIA:** action produces independently attributable evidence and a per-candidate revision; the policy can complete a candidate whose investigation includes one genuinely new measured revision without operator naming; no repeated unbounded loop or model-selected tool.

**STOP BOUNDARY:** one action and its necessary policy change; no cross-modal follow-ups until the aliquot contract exists (P08 records it). **DEFERRED WORK:** broad action catalogue. **CANONICAL DOC UPDATE:** Architecture investigation behavior; Jev Design action-value role; regenerate Repository Facts only after actual code constants change.

### P16 — Bounded Campaigns within an autonomous Program

**STATUS:** REQUIRED. **OBJECTIVE:** sequence validated reproducible Campaigns using explicit persisted Python policy, with release-change classification.

**WHY THIS WORK REMAINS:** runs and candidate completion exist; Program/Campaign selection and release comparison contracts do not. The current LUAD spec is not an autonomous validation certificate, and no eligibility ordering prevents schedule drift.

**CURRENT CODE TO REUSE:** `ResearchSpec`, current runners, run transitions, repository/artifact/event infrastructure and candidate finalization; P03 campaign profile/readiness, P05 universe identity and P14 ownership scoping (this unit builds on the owner-aware run scope rather than retrofitting it).

**CURRENT CODE TO CHANGE:** `research/specs.py`, `research/live.py`/`orchestrator.py` entry boundaries, `domain/runs.py`, repository/database/readers, `cli/main.py`; add small `research/program.py` and `research/campaign_selection.py` modules only for missing long-lived coordination.

**UPSTREAM SOURCES TO USE:** U1 release/status semantics; P03 validated source/method bindings. No new scientific method.

**SCIENTIFIC CONTRACT:** one Campaign = coherent cohort + pinned source release + versioned method profile. Only profiles with readiness `VALIDATED_FOR_AUTONOMOUS_USE` participate; promotion is code/test-owned and recorded per profile, never runtime-inferred, and never automatic. Program continuation is operational; scientific Campaigns and candidate chains remain bounded. New releases never mutate prior results. Campaign selection is named, versioned, deterministic and testable (declared ordering: readiness first, then a priority constant, then campaign_id ascending — never lexical/registry/filesystem order); no eligible campaign records `PROGRAM_IDLE`. Program state vocabulary: `PENDING`, `RUNNING`, `CAMPAIGN_COMPLETE`, `BLOCKED_NOT_READY`, `PROGRAM_IDLE`. Release comparison uses a declared vocabulary — `NEW_CANDIDATE`, `LOST_CANDIDATE`, `RANK_CHANGED`, `EVIDENCE_STRENGTHENED`, `EVIDENCE_WEAKENED`, `MODALITY_CHANGED`, `SOURCE_CHANGED`, `METHOD_CHANGED`, `NOT_COMPARABLE` — computed from persisted artifacts only; source/method changes are never attributed to biology.

**IMPLEMENTATION STEPS:** 1. Bind Campaign identity/readiness to the existing spec (P03). 2. Persist candidate queue and completion within the P14 ownership scope. 3. Implement the selection policy and the program loop with `PROGRAM_IDLE`. 4. Add the release-comparison classifier over persisted artifacts. 5. Resume idempotently or idle when none are eligible. 6. Compare only compatible results; report source/method changes or `NOT_COMPARABLE` separately from biological interpretation.

**DATA / ACQUISITION PLAN:** release metadata polling only at declared intervals (one `/status` request per interval, `config.run_interval_minutes`); comparison runs only when a new release differs; discovery delegates to the selected Campaign's preflight. No new bulk acquisition in scheduler logic. Release polling is a future runtime feature, not an automation created by this task.

**SCHEMA / PERSISTENCE IMPACT:** Program/Campaign/selection-event identities and durable progress in existing storage, owner-aware from its first implementation (P14 precedes this unit); separate from scientific state, no distributed queue/DAG.

**VERIFICATION:** later `python -m pytest tests/test_ownership_recovery.py tests/test_domain_events.py tests/integration/test_stage8_finalize.py` plus new focused cases for restart, unvalidated profile exclusion, selection determinism (ties, ineligible, empty registry → `PROGRAM_IDLE`), duplicate release, incomparable source/method changes and campaign immutability under a release bump (old artifacts untouched).

**ACCEPTANCE CRITERIA:** validated Campaign → independently finalized candidates → completion → attributable next Campaign/idle with no hidden ordering; a new release produces a typed comparison without rewriting prior campaigns; a non-LUAD fixture proves generic architecture only. A second real cancer needs its own validation.

**STOP BOUNDARY:** no Researcher Lab/UI, no uncontrolled infinite acquisition, no second-cancer validation here, no pooling, no auto-promotion of readiness. **DEFERRED WORK:** second real cancer campaign; release-diff automation beyond classification. **CANONICAL DOC UPDATE:** README/Product Scope actual autonomy; Architecture progression and release comparisons; REPOSITORY_FACTS (policy version, schema) via renderer.

### P17 — One orthogonal functional or external replication source

**STATUS:** REQUIRED only for claims needing that evidence. **OBJECTIVE:** add one independently sourced evidence axis after genomic discovery is valid.

**WHY THIS WORK REMAINS:** no inspected contract establishes functional dependency, targetability, clinical evidence or independent-cohort replication. `FUNCTIONALLY_SUPPORTED` exists in the level vocabulary but has no attainable contract.

**CURRENT CODE TO REUSE:** method/source identities, information-role contract from P11, registered actions, evidence revisions and dossier.

**CURRENT CODE TO CHANGE:** one narrow source adapter, `domain/evidence.py`, `science/actions.py`, `research/specs.py`, codecs and Stage 8 dossier consumer.

**UPSTREAM SOURCES TO USE:** current official selected source (for example DepMap, a cancer-gene catalogue, targetability resource or independent compatible cohort) and its primary methodology. Access, version, licensing and mapping remain unresolved until source selection; no provider is implicitly approved by its mention here. A decision record must verify current terms before any adoption (for example DepMap bulk files require registration; a GDC-derived `is_cancer_gene_census` flag is not Sanger CGC licensing). Default outcome for this cycle: DEFER all adoptions, keep the recorded classification only.

**SCIENTIFIC CONTRACT:** dependency, known-cancer context, replication, targetability and clinical evidence remain distinct axes; pan-cancer dependency is never cohort-specific support. Dependency is not therapeutic efficacy; known-gene status is not proof of a target in this cohort. Predeclare discovery/validation/follow-up role. Jev may interpret functional evidence but never manufacture it.

**IMPLEMENTATION STEPS:** 1. Choose one question/source and verify lawful usable access/version. 2. Validate identifier mapping and population comparability. 3. Implement one deterministic interpretation. 4. Attach evidence with limitations; promote only the supported axis/level. 5. Keep labels out of prior evaluated discovery. 6. Document the `FUNCTIONALLY_SUPPORTED` precondition in the derivation.

**DATA / ACQUISITION PLAN:** selected high-level table or bounded API, exact file count/bytes and retention decided in source preflight; never full external mirrors by default; no download this cycle.

**SCHEMA / PERSISTENCE IMPACT:** one typed external evidence contract, source/method binding and strict readers; `GeneAnnotation`-style metadata only additively.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_actions.py tests/integration/test_stage8_finalize.py` plus independent source reconciliation, ambiguous mapping, incompatible populations and unavailable external data cases.

**ACCEPTANCE CRITERIA:** attributable orthogonal evidence with honest claim limits; no Jev-created functional support; classification renderable in dossier limitations.

**STOP BOUNDARY:** one source and evidence axis; no composite druggability score; no DepMap/CGC/targetability download or integration before a verified contract. **DEFERRED WORK:** other sources/clinical claims. **CANONICAL DOC UPDATE:** Product Scope supported evidence and Data Strategy access/provenance; README claim-boundary sentence.

### P18 — Additional modality admission, individually justified

**STATUS:** REQUIRED only when a selected cohort/question needs another modality. **OBJECTIVE:** admit one of SV/fusion, methylation, miRNA, RPPA/protein, single-cell or clinical/outcome evidence with its own scientific contract.

**WHY THIS WORK REMAINS:** current `Lane` contains mutation, expression and CNV; an upstream endpoint list does not implement additional science. Capability records for `STRUCTURAL_VARIANT`, `FUSION`, `METHYLATION`, `MIRNA`, `RPPA`, `SCRNA_SNRNA`, `CLINICAL` and `SURVIVAL` are UNAVAILABLE with reasons until each has a contract.

**CURRENT CODE TO REUSE:** P03 capability gate, P05 universe/shards, existing typed lane pattern, sources, missingness, P10 union and P11 maturity.

**CURRENT CODE TO CHANGE:** only the selected endpoint/parser or file adapter, a narrow deterministic method module, `domain/scientific.py`, codecs and necessary composition/projection consumer. Do not widen every lane in advance.

**UPSTREAM SOURCES TO USE:** relevant current U1 pipeline page, U2 identity/workflow, and the public workflow/tool linked there if needed. Inspect and pin those specific sources at implementation time; unrelated modality internals were intentionally not audited here.

**SCIENTIFIC CONTRACT:** declare feature universe, assay population, measurement unit, QC, method/version, missingness, deterministic output and actual policy consumer. Single-cell donor/cell nesting, survival censoring or platform-specific probes require their own contracts and cannot inherit gene-level assumptions silently. One modality at a time; each is admitted only after independent reconciliation.

**IMPLEMENTATION STEPS:** 1. Establish a concrete cohort capability and scientific question. 2. Select an established method and verify source semantics. 3. Preflight source/scale. 4. Implement one validated lane. 5. Admit it through existing union/state.

**DATA / ACQUISITION PLAN:** unknown until modality selection; endpoint/product, scientific population, shard unit, expected requests/files/bytes and retention must all be resolved before acquisition. Prefer indexed/high-level evidence; no raw-data fallback by default.

**SCHEMA / PERSISTENCE IMPACT:** one explicitly versioned lane extension, not a generic plugin architecture.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_lane_composition.py tests/integration/test_cutover.py` plus source-specific real-response reconciliation and missingness/completeness checks.

**ACCEPTANCE CRITERIA:** one scientifically validated modality with reproducible outputs and bounded integration. **STOP BOUNDARY:** no simultaneous modality expansion. **DEFERRED WORK:** every other modality. **CANONICAL DOC UPDATE:** Architecture capability status and Data Strategy selected source.

### P19 — End-to-end acceptance and final gates

**STATUS:** REQUIRED as the closing unit. **OBJECTIVE:** prove the whole architecture end-to-end under one layered acceptance checklist, including enforcement of the ownership boundary.

**WHY THIS WORK REMAINS:** ownership isolation is a product boundary (P14) and the existing suites are per-unit; there is no committed end-to-end acceptance suite or cross-ownership rejection test.

**CURRENT CODE TO REUSE:** `tests/integration/replay.py`, `research/fixtures.py`, Stage 8 finalize, dossier renderer, the `tests/live` gated-live pattern, existing unit/replay/integration suites, the ownership lock.

**CURRENT CODE TO CHANGE:** tests and fixtures only, plus the ownership-scoping code required by P14; no new scientific code.

**UPSTREAM SOURCES TO USE:** none beyond the already pinned sources.

**SCIENTIFIC CONTRACT:** acceptance tests observable behaviour and scientific contracts, not a known biological winner, a particular rank or a single monolithic test; a non-LUAD fixture proves generic architecture only and is never cited as validation; frozen reconciliation remains read-only evidence.

**IMPLEMENTATION STEPS:** 1. Build the checklist as executable layered tests: pinned release/source context → capability → complete universe with terminal shards → validated lanes and dispositions → union → baseline + Wide → admission → E0 → deterministic policy action → E1 → Deep → terminal → Stage 8 → dossier → no-Jev comparison → CANDIDATE_COMPLETE. 2. Gate checks: frozen reconciliation intact; workflow provenance present; evidence levels justified and Jev-immutable; leakage guard green; deterministic replay (byte-identical reruns from cache); fail-closed Jev corpus; no controlled-access endpoint used; declared acquisition budgets respected; claim-boundary text in every dossier. 3. Cross-ownership write attempts fail closed in both directions. 4. Add a non-LUAD fixture run path that labels itself non-validated. 5. Wire the offline suite into CI; keep live checks behind the existing opt-in/gated marker.

**DATA / ACQUISITION PLAN:** offline fixtures by default; live acceptance only within the validated LUAD campaign budgets.

**SCHEMA / PERSISTENCE IMPACT:** none beyond P14's ownership scoping; acceptance consumes existing artifacts.

**VERIFICATION:** later `python -m pytest tests/integration` plus the new acceptance cases; live acceptance only by explicit opt-in, as `tests/live` today.

**ACCEPTANCE CRITERIA:** the acceptance suite passes end-to-end offline, every gate is individually observable, and the claim boundary is verifiable in every produced dossier.

**STOP BOUNDARY:** no multi-tenant server architecture, no UI work beyond displaying ownership. **DEFERRED WORK:** portal-style cohort-context features and SDK adoption. **CANONICAL DOC UPDATE:** README autonomy/researcher section, Architecture ownership section, REPOSITORY_FACTS only if constants change.

## Documentation outcome and handoff

The six supplied documents are the canonical product/design set, adapted to distinguish target requirements from current implementation. README provides the entry point; Architecture owns the current map and target flow; Product Scope owns claims; Scientific Invariants owns stable rules; Data Strategy owns acquisition constraints; Jev Design owns semantic boundaries. This plan owns remaining implementation work, including the units added during the merge (P02 cancer-agnostic contracts, P04 workflow provenance, P19 acceptance) and the prompt-to-unit traceability. Repository Facts retains its generated block; AGENTS.md retains the existing task rules.

The next implementation prompt should request P01 alone against the then-current HEAD, followed by P02 as the small standalone contract cleanup. Reinspect each bounded path before changing it; do not treat this dated plan as proof that future code still has the same gaps.
