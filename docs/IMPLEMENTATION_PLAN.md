# ONTOJEV REFACTORED IMPLEMENTATION PLAN

**Current HEAD:** `26988040fb7c8afbb121c3774a6b510285db7ba9`, branch `main`, inspected 2026-09-26. Initial tracked working tree was clean; full status reported no changes but warned that `.pytest-tmp/` was inaccessible. This is a documentation-only change against that recovery point.

**Current architecture:** typed GDC requests/parsers and bounded transport; deterministic mutation/expression/CNV lanes; one canonical `StatisticalState`; Wide judgment and Python admission; candidate-specific immutable `EvidenceState` revisions; Deep judgment and Python policies; bounded hypotheses and critique; Stage 8 final results, authoritative dossiers and deterministic no-Jev comparisons. Systematic discovery and the older provider-ranked live path coexist. Neither is a continuous autonomous Program.

**Current scientific limitations:** systematic discovery uses a declared, biased first 1,000 protein-coding genes; expression describes that same prefix; CNV and integrated state composition are mutation-survivor-only. Mutation occurrence counting is reconciled for Stage 4, but the older live path still consumes the invalidated analysis bucket as an affected-case measurement. Current expression tails and CNV categories are descriptive. Assay eligibility, sample matching, inferential methods, scientific readiness and complete-universe autonomy remain work. Census status reaches Wide and needs an explicit information-role contract.

**Already satisfied supplied prompts:** preserve the existing typed state/control spine; hypothesis-is-not-evidence boundary; bounded candidate finalization, dossiers and no-Jev comparison; strict versioned readers; Stage 4 occurrence-count correction; local upstream reference workspace. These are implementation findings, not a claim that all scientific validation has passed.

**Partially satisfied supplied prompts:** source context, cohort framing, universe provenance, bounded acquisition, mutation/expression/CNV science, integrated discovery, Jev failure handling, deterministic follow-up, validation leakage controls and run ownership.

**Required supplied prompts:** complete-universe global reduction; assay/capability and readiness contracts; independent modality nomination and union; justified open-file acquisition; method-specific inference/replication; evidence maturity and external-information roles; autonomous Campaign selection/release monitoring and researcher isolation.

**Superseded supplied prompts:** rebuilding Wide/Deep/Stage 8, replacing `ResearchSpec`, and creating a second scientific-state system. Treating a prefix as genome-wide, CNV as independent discovery today, or LUAD as already validated for autonomous scientific use is contradicted by the inspected implementation. Arm Jev and extra modalities are conditional, not mandatory infrastructure.

**Hard scientific gates:** independently reconciled selection-critical measurements; complete declared population before global finalization; explicit assay/missingness semantics; workflow/unit comparability; no validation-label leakage; method-specific statistical support; immutable source/results; autonomous-readiness evidence; fail-closed semantic and persistence boundaries.

**Recommended execution order:** P01 → P02 → P03; P04 only when a method needs files; then P05/P06/P07 independently under their declared source contracts → P08 → P09/P10 → P11 → P12 → P13 → P14 → P15. P16 is an optional, separately scoped modality gate. Each numbered unit is a separate bounded change; do not implement this entire document in one pass.

## Scope and interpretation

The user's request authorizes saving the plan and updating repository documentation. The two pasted documents supply planning requirements and inspection limits; their “only output is the plan” language does not cancel the user's explicit documentation request. The six supplied Markdown files are design inputs, not evidence of running functionality. No separately numbered implementation prompts were supplied; the units below consolidate their requirements and the master document rather than inventing historical prompts. No history, deleted plans, unrelated UI audit, runtime changes, tests, schemas, migrations or scientific acquisition were needed for this task.

The source of truth is current code for implementation and authoritative upstream material for scientific semantics. Tests were read, not run. Commands under verification are for later explicitly authorized implementation/verification tasks; repository policy skips tests unless requested. No live Jev calls or campaign-scale GDC requests were made.

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
| Entry points | `cli/main.py`, `research/live.py`, `research/orchestrator.py` | Existing CLI/live/demo runners; no `cancerjev/orchestration/` package to redesign. |

All paths in this table are relative to the repository root. Schema/action/policy constants remain owned by code and indexed in [REPOSITORY_FACTS.md](REPOSITORY_FACTS.md).

## Upstream evidence inspected

Existing untracked `.upstream/gdc/` clones were reused. Their checked-out SHAs matched remote `HEAD` on 2026-09-26; no checkout, installation or bulk download was required. `.upstream/SOURCES.lock.json` records clone dates/roles and an older OntoJev inspection HEAD; that older HEAD is not this plan's baseline.

| Ref | Repository and exact inspected SHA | Inspected evidence / role |
|---|---|---|
| U1 | [gdc-docs](https://github.com/NCI-GDC/gdc-docs) `157cef9dac084ce30720f0ad507cd54017263be7` | `docs/API/Users_Guide/Data_Analysis.md`; expression, DNA variant and CNV pipeline docs. Current scientific documentation reference. |
| U2 | [gdcdatamodel2](https://github.com/NCI-GDC/gdcdatamodel2) `9c6a046b96c130ea131d2ce2c9160381edd2fcc1` | `src/gdcdatamodel2/models/sample.py`, `aliquot.py`, `file.py` and the partial dictionary: identity relationships and experimental-strategy/workflow fields. Data-model authority, not imported runtime machinery. |
| U3 | [gdc-workflow-overview](https://github.com/NCI-GDC/gdc-workflow-overview) `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e` | README production/provenance map; some current WGS implementations are not public. Older WXS caller listing must be reconciled with U1. |
| U4 | [gdc-client](https://github.com/NCI-GDC/gdc-client) `0602ecbccb9f31e37d720347e58ea3eaef981f85` | README and download client source. Reference for a future selected-open-file adapter; no OntoJev adapter found. |
| U5 | [gdc-rnaseq-cwl](https://github.com/NCI-GDC/gdc-rnaseq-cwl) `05460f7dfca5a900d7635ccae0e1b28cf764a02f` | README input/output and annotation contract; source reference only. |
| U6 | [gdc-rnaseq-tool](https://github.com/NCI-GDC/gdc-rnaseq-tool) `9a0fccece9b7f59c046c664d94dea2cb42dbcb08` | Pin verified; tool implementation inspection deferred until a normalization consumer requires it. |
| U7 | [gdc-somatic-variant-calling-workflow](https://github.com/NCI-GDC/gdc-somatic-variant-calling-workflow) `6634b4f8313b7fa662d2dec380a7ea67cf631f0a` | Pin verified; source details deferred to P05's method needs, not assumed current from repository existence. |

Current expression documentation describes STAR counts and FPKM/FPKM-UQ/TPM transforms, unstranded harmonization and GENCODE v36 from release 32; historical HTSeq is not the current default. CNV products from ASCAT, ABSOLUTE, DNAcopy and GATK4 require distinct provenance. U1 documents SomaticSniper deprecation at release 35 and current Pindel usage; U3's older WXS list does not override that. These facts inform compatibility checks, not permission to rerun harmonization.

The [NCI GDAN overview](https://www.cancer.gov/ccg/research/computational-genomics/genomic-data-analysis-network) was inspected for the established-methods context. It does not validate any specific OntoJev method. Selecting a statistical method still requires its primary methodological reference and input validation.

Official [TypeSafe documentation index](https://docs.typesafe.ai/llms.txt) and [autoresearch feature-discovery cookbook](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) were inspected on 2026-09-26. The cookbook uses labelled text, semantic features and supervised evaluation; it is not evidence that model-generated cancer hypotheses are genomic measurements. The index confirms typed primitives and fan-out/routing patterns. Direct `.md` primitive/pattern page retrieval failed; recheck exact SDK/API behavior before implementing new batching/routing. GDC web API-page retrieval also failed; its pinned U1 source was readable and used instead.

## Requirements disposition

Master sections 1–2 and 31, 34–37 govern this planning output. Sections 3–6 and 8 map to P02/P03/P08/P13; 7 and 21–24 to P02/P04; 9–12 and 19–20 to P11/P12; 13–18 and 25–26 to P05–P10/P15; 27 to P13; 28 to P14; 29–30 to the cutover/verification rules below; 32–33 apply to every unit. The supplied Product Scope, Architecture, Data Strategy, Jev Design and Scientific Invariants overlap; their common requirements are merged here rather than implemented repeatedly.

**SATISFIED — control-spine preservation.** Current evidence: canonical `StatisticalState`, frozen evidence contracts, projection/service boundary, Python Wide/next-move policies, hypothesis contracts and Stage 8 files above. Relevant existing checks include `tests/integration/test_stage8_finalize.py`, `test_hypothesis_stage.py`, `tests/jev/test_typed_flow.py`. Remaining gap: NONE for retaining these components. Broader scientific inputs and autonomy are separate units.

**SATISFIED — Stage 4 distinct released-case measurement.** Current evidence: `acquire_project_mutation_occurrence_scan`, `build_discovery_entries`, `tests/science/test_occurrence_scan.py`, `tests/reconciliation/independent_counts.py`, frozen `reconciliation_dr46/MANIFEST.json`. Remaining gap: NONE for replacing the Stage 4 bucket measurement. This does not satisfy the older path, callable denominators, complete universe or driver inference.

**SATISFIED — immutable finalization and comparator existence.** Current evidence: `derive_stage8`, `run_stage8_finalize`, dossier renderer and `test_stage8_finalize.py` cases for immutable baseline replay, per-candidate finalization and authoritative dossier. Remaining gap: NONE for their existence; extend only when scientific contracts change.

**SUPERSEDED — unconditional Arm Jev, broad tool installation and rebuilding the engine.** Existing types/control are reusable; semantic necessity and method-specific acquisition decide whether optional work exists. Do not introduce a generic DAG, plugin framework, separate state model or tool-selection agent.

## Shared implementation rules

Each unit below names its persistence impact; no versions are bumped now. Before any incompatible cutover, record the then-current recovery HEAD/tag, preserve representative old artifacts, enumerate incompatibilities, update producers/readers/projections/consumers together and reject unsupported versions. Do not migrate historical evidence into new scientific meaning. Use explicit supersession for invalid results.

For acquisition units, let G be eligible genes, C cohort cases, E released event records, B a bounded request batch, P a page size and F selected files. These are planning variables, not measured live counts. No honest current file-count/byte estimate exists for an unselected future method. Its acquisition preflight must materialize counts and `sum(file_size)`, or bounded-response size estimates, before execution. Budget exhaustion produces incomplete/unavailable status, never a smaller scientific population labelled complete. Multi-GB plans require source reconsideration; raw sequencing is not an automatic fallback. Retain source IDs, hashes, manifests, method versions and derived results; retain replay bytes when necessary, with explicit cache/retention policy.

### P01 — Close the remaining invalid mutation-measurement path

**STATUS:** PARTIAL. **OBJECTIVE:** prevent the older live path from publishing an analysis bucket as distinct affected cases.

**WHY THIS WORK REMAINS:** `_fast_search` calls `acquire_mutation_counts`; `mutation_observation` still transfers bucket values to `affected_cases`. Stage 4 already has the correction. The frozen reconciliation demonstrates that bucket values are not released distinct-case counts.

**CURRENT CODE TO REUSE:** occurrence scan and Stage 4 derivation; reconciliation manifest/independent counts; strict scope binding in `research/cutover.py` and immutable artifact registration.

**CURRENT CODE TO CHANGE:** `research/live.py`, `research/acquisition.py`, `science/mutation.py`, affected `science/methods.py` consumers and method identities. Keep a labelled provider-ranking comparator separate.

**UPSTREAM SOURCES TO USE:** U1 API analysis semantics, U2 identity; frozen reconciliation is direct source evidence.

**SCIENTIFIC CONTRACT:** one cohort/release; distinct released case IDs per gene across a complete scan. No occurrence means zero released occurrences only; neither wild type nor a callable-negative denominator. Consumer: existing state composition/admission.

**IMPLEMENTATION STEPS:** 1. Trace legacy bucket consumers. 2. Route scientific measurements through the existing corrected scan or make that legacy measurement unavailable. 3. Label preserved comparator metadata explicitly. 4. Supersede affected scientific outputs without rewriting them.

**DATA / ACQUISITION PLAN:** replay first; existing `/ssm_occurrences` scan, approximately ceil(E/P) requests if later live verification is authorized; no files, no new population.

**SCHEMA / PERSISTENCE IMPACT:** changed measurement meaning requires method/provenance cutover; change schema only if the existing typed output cannot represent it.

**VERIFICATION:** later `python -m pytest tests/reconciliation tests/science/test_occurrence_scan.py tests/integration/test_live_replay.py`; extend cases for legacy routing, duplicate events and incomplete scans.

**ACCEPTANCE CRITERIA:** no admitted affected-case field derives from the invalidated bucket; Stage 4 and legacy paths agree on the frozen source population.

**STOP BOUNDARY:** no new mutation statistics or universe expansion. **DEFERRED WORK:** P03/P05. **CANONICAL DOC UPDATE:** current measurement limitation in README/Architecture; Data Strategy source caveat.

### P02 — Bind source, assay capability and scientific readiness

**STATUS:** PARTIAL. **OBJECTIVE:** turn recorded run scope into an explicit immutable scientific context with capability/readiness gates.

**WHY THIS WORK REMAINS:** `ResearchSpec`, release inventory and `PopulationFrame` exist; a validated method/profile gate and precise per-modality assay populations do not.

**CURRENT CODE TO REUSE:** `CohortSpec`, `ResearchSpec`, `PopulationFrame`, `ScientificSource`, existing inventory and metadata parsers.

**CURRENT CODE TO CHANGE:** `research/specs.py`, `research/live.py` inventory, `research/acquisition.py`, `gdc/endpoints.py`, `gdc/parsers.py`, `domain/measurements.py`, `domain/codecs.py`, `storage/readers.py`.

**UPSTREAM SOURCES TO USE:** U1 API/search and pipeline pages; U2 case/sample/aliquot/file/workflow relationships; U3 production provenance.

**SCIENTIFIC CONTRACT:** all declared cohort cases, explicit assay-eligible subsets and reasoned unknowns; case overlap never establishes matched aliquots. Source/method/profile identity is immutable. Experimental, replay-validated and autonomous-validated readiness needs attributable evidence; LUAD starts with only the readiness actually supported.

**IMPLEMENTATION STEPS:** 1. Extend `ResearchSpec` with the smallest source/method/validation bindings. 2. Derive capabilities from bounded inventory and assay/workflow metadata. 3. Keep acquisition completeness separate from assay availability. 4. Bind readiness to reconciliation/replay evidence and reject unsupported method/profile activation.

**DATA / ACQUISITION PLAN:** `/status`, exact project, paged cases and filtered `/files` metadata; ceil(C/P) case requests plus metadata pages. No assay downloads; estimate remaining metadata requests before launch and cache source hashes. Recheck source context at completion rather than silently mixing release changes.

**SCHEMA / PERSISTENCE IMPACT:** coordinated `ResearchSpec` and source/population contract extension; no duplicate permanent state model.

**VERIFICATION:** later `python -m pytest tests/unit/test_research_specs.py tests/contracts/test_parsers.py tests/integration/test_scientific_reads.py`; add mixed-release, ambiguous aliquot, assay-unavailable and unvalidated-profile cases.

**ACCEPTANCE CRITERIA:** every enabled method can explain its eligible population/source and readiness; unknown coverage never becomes negative evidence.

**STOP BOUNDARY:** no continuous scheduler or scientific inference. **DEFERRED WORK:** P13. **CANONICAL DOC UPDATE:** Architecture current source/capability behavior; Product Scope readiness; Data Strategy provenance.

### P03 — Complete universe and operational shards

**STATUS:** PARTIAL. **OBJECTIVE:** replace the scientific prefix limit with full eligible membership and global reduction.

**WHY THIS WORK REMAINS:** `MAX_UNIVERSE_LIMIT`, fixed prefix method and page budgets bound scientific scope; `TestedUniverse` already carries membership provenance.

**CURRENT CODE TO REUSE:** `TestedUniverse`, `acquire_gene_universe`, fail-closed occurrence pagination, expression batch merging, artifact store.

**CURRENT CODE TO CHANGE:** `domain/discovery.py`, `domain/measurements.py`, `research/specs.py`, `research/discovery.py`, `research/acquisition.py`, `research/expression_discovery.py`, codecs and strict readers.

**UPSTREAM SOURCES TO USE:** U1 `/genes` pagination/filter semantics; U2 gene/source identity where applicable.

**SCIENTIFIC CONTRACT:** every eligible release-bound protein-coding gene unless a different universe is explicitly justified. Operational gene/case/file shards cannot change population, ranking or testing family. Failed required shards block complete global results.

**IMPLEMENTATION STEPS:** 1. Enumerate to verified total with uniqueness/order checks. 2. Persist universe hash and required shard identities/status/source hashes. 3. Support restart from verified shard artifacts. 4. Accumulate mathematically valid sufficient statistics. 5. Finalize global ranking only after required data completes. 6. Keep historical prefix results honestly labelled.

**DATA / ACQUISITION PLAN:** approximately ceil(G/P) gene pages, ceil(E/P) mutation pages and expression batches proportional to ceil(G/Bg) × ceil(C/Bc). Order-of-magnitude gene count is tens of thousands, not a hardcoded biological total. API bytes must be estimated from bounded responses; no file download required by this unit. Cache completed immutable shards.

**SCHEMA / PERSISTENCE IMPACT:** universe/completion contract and result readers change together; operational shard manifests are not a second scientific state.

**VERIFICATION:** later `python -m pytest tests/integration/test_discovery_replay.py tests/integration/test_expression_discovery_replay.py tests/science/test_discovery_reduction.py`; add shuffled shard boundaries, retries, missing/duplicate pages, changed totals and budget exhaustion.

**ACCEPTANCE CRITERIA:** equivalent membership/measurements/ranks across shard layouts; no per-shard top-k union masquerades as global discovery.

**STOP BOUNDARY:** retain existing descriptive methods. **DEFERRED WORK:** inference and new modalities. **CANONICAL DOC UPDATE:** README current universe; Architecture/Data Strategy completion semantics.

### P04 — Selected open harmonized files, only when needed

**STATUS:** REQUIRED, conditional on a named scientific consumer. **OBJECTIVE:** add one narrow open-file path when API evidence cannot answer the chosen method.

**WHY THIS WORK REMAINS:** metadata access exists; no runtime `gdc-client` acquisition adapter was found. An upstream clone is not an installed integration.

**CURRENT CODE TO REUSE:** transport bounds, strict parsers, `ArtifactStore`, `ScientificSource` and source hashes.

**CURRENT CODE TO CHANGE:** `gdc/endpoints.py`, `gdc/parsers.py`, `research/acquisition.py`; add a narrow `gdc/open_files.py` adapter only for the selected product; bind provenance in existing contracts/readers.

**UPSTREAM SOURCES TO USE:** U1 search/retrieval and selected pipeline; U2 file/aliquot/workflow fields; U4 manifest/download implementation.

**SCIENTIFIC CONTRACT:** deterministic selection of open, compatible high-level files for the declared assay population; UUID, release, workflow, size and checksum bind parsed evidence. Ambiguous or incomplete selection is unavailable, not an arbitrary first file.

**IMPLEMENTATION STEPS:** 1. Document why API summaries fail the method. 2. Produce an exact metadata manifest and byte estimate. 3. Enforce access/product/budget allowlists. 4. Invoke bounded `gdc-client` without GDC tokens, validate checksum and parse one product. 5. Register immutable source identity and explicit retention.

**DATA / ACQUISITION PLAN:** F and bytes are unknown until product/population selection; preflight must fill both. Shard by file; completion requires all selected files or scientifically justified explicit exclusions. Compare API request cost against high-level files; reconsider multi-GB plans. Do not fetch BAM/FASTQ by default.

**SCHEMA / PERSISTENCE IMPACT:** file-source/manifest reference extension if existing sources are insufficient; never embed raw files in Jev projections.

**VERIFICATION:** later `python -m pytest tests/contracts/test_open_access.py tests/contracts/test_transport_bounds.py`; add manifest replay, controlled-access refusal, checksum mismatch, interrupted download, duplicate/ambiguous files and parser rejection.

**ACCEPTANCE CRITERIA:** reproducible selected evidence from verified open files within declared budgets. **STOP BOUNDARY:** one product only, no general downloader or harmonization system. **DEFERRED WORK:** other file formats. **CANONICAL DOC UPDATE:** Data Strategy implemented file product and limits.

### P05 — Mutation scientific-method gate

**STATUS:** PARTIAL. **OBJECTIVE:** extend reconciled recurrence only with a specifically justified mutation method.

**WHY THIS WORK REMAINS:** distinct released-case counts are valid descriptive evidence; caller-aware consequence, hotspot/background models and inferential driver support are not established by those counts.

**CURRENT CODE TO REUSE:** Stage 4 counts, strict occurrence parser, `MethodIdentityRef`, existing discovery result and reconciliation fixtures.

**CURRENT CODE TO CHANGE:** `gdc/endpoints.py`, `gdc/parsers.py`, `science/mutation.py`, `science/methods.py`, `domain/discovery.py`, `research/discovery.py`; extend scientific output/codecs only for the selected evidence.

**UPSTREAM SOURCES TO USE:** U1 DNA/WGS semantics, U3/U7 provenance; relevant pinned MAF/annotation source only if needed. Select and inspect a primary GDAN/TCGA mutation-method reference before inferential implementation; no method is approved solely by this plan.

**SCIENTIFIC CONTRACT:** explicit mutation assay population, complete tested genes, variant/record deduplication, consequences and caller context; callable denominator cannot be inferred from indexed positives. Statistical support additionally requires a feasible background model and global multiple-testing family.

**IMPLEMENTATION STEPS:** 1. Declare the exact method and required inputs. 2. Reconcile event/consequence semantics. 3. Implement one deterministic method with source/version/limitations. 4. Preserve unavailable inference when required background/callability is absent. Split descriptive enrichment from inferential driver testing if they need different validation gates.

**DATA / ACQUISITION PLAN:** detailed `/ssms`/occurrences or selected open MAF only after API-versus-file comparison. Request/file/byte estimates depend on chosen method; produce a preflight over the full eligible population, not only known drivers. Reuse cached records.

**SCHEMA / PERSISTENCE IMPACT:** additive typed method evidence and coordinated reader/projection changes where semantics differ.

**VERIFICATION:** later `python -m pytest tests/reconciliation tests/science/test_discovery_reduction.py`; method-specific independent expected results for duplicate events, multi-variant cases, annotation mismatch, missing callability and global correction.

**ACCEPTANCE CRITERIA:** descriptive and inferential outputs are separately labelled; no model judgment or recurrence rank creates driver significance.

**STOP BOUNDARY:** one mutation method, no pipeline rebuilding. **DEFERRED WORK:** other mutation models and functional validation. **CANONICAL DOC UPDATE:** Architecture mutation capability; Data Strategy selected source; Scientific Invariants only if clarification is needed.

### P06 — Expression provenance, QC and method gate

**STATUS:** PARTIAL. **OBJECTIVE:** validate the expression product/population and introduce a comparison only when its design is defensible.

**WHY THIS WORK REMAINS:** existing log2(UQFPKM+1) summaries/Tukey tails are descriptive case-labelled observations, not raw-count differential expression or matched tumor-normal evidence.

**CURRENT CODE TO REUSE:** `ExpressionSummaryResult`, coverage/availability merging, `run_expression_discovery`, tail descriptors and batch-permutation checks.

**CURRENT CODE TO CHANGE:** `research/expression_discovery.py`, `research/acquisition.py`, `science/expression.py`, `science/descriptors.py`, relevant parser/domain output and codecs.

**UPSTREAM SOURCES TO USE:** U1 expression pipeline/API; U2 identity; U5, and U6 only for a needed calculation. A future DE method requires its own primary reference and predeclared design.

**SCIENTIFIC CONTRACT:** RNA-eligible cases/samples/aliquots, explicit unit/transform, workflow/reference annotation, duplicate assay rule and QC/confounding. No missing assay becomes zero. Do not treat normalized UQFPKM as integer-count input to a count model.

**IMPLEMENTATION STEPS:** 1. Reconcile API values and transforms against frozen real data. 2. Bind workflow/assay identity and eligibility. 3. Validate descriptive features globally. 4. Separately authorize a contrast/design with adequate replicates, covariates and compatible measurements before DE.

**DATA / ACQUISITION PLAN:** API batches over G and RNA population for descriptive summaries; high-level STAR count files only if the chosen model requires them. Preflight ceil(G/Bg) × ceil(Crna/Bc) API batches versus F count files and actual bytes. Store identity/QC exclusions and reusable validated data.

**SCHEMA / PERSISTENCE IMPACT:** richer provenance/QC/effect outputs need explicit typed fields and reader updates; tails keep their descriptive meaning.

**VERIFICATION:** later `python -m pytest tests/integration/test_expression_discovery_replay.py tests/science/test_descriptors.py tests/science/test_lane_composition.py`; independent transform reconciliation, missing assay, duplicate aliquots, confounded design and batch-invariant global results.

**ACCEPTANCE CRITERIA:** every expression claim names its population/unit/design; insufficient design reports unavailable inference.

**STOP BOUNDARY:** do not add DE just because expression exists. **DEFERRED WORK:** replication and cross-modal association. **CANONICAL DOC UPDATE:** Architecture expression status and Data Strategy product choice.

### P07 — Independent CNV discovery

**STATUS:** PARTIAL. **OBJECTIVE:** remove mutation-survivor gating for a validated CNV nomination method.

**WHY THIS WORK REMAINS:** current `CNV_SELECTION_RULE` and result binding admit only Stage 4 survivors; observed categories cannot establish neutral states or continuous dosage comparability.

**CURRENT CODE TO REUSE:** `CnvOccurrenceResult`, category mapping/conflict preservation, strict paged parser, `run_cnv_discovery`.

**CURRENT CODE TO CHANGE:** `domain/discovery.py`, `research/specs.py`, `research/cnv_discovery.py`, `gdc/endpoints.py`, parsers/codecs and subsequent composition boundary.

**UPSTREAM SOURCES TO USE:** U1 CNV pipeline, U2 workflow/file identity, U3 WGS production status; evaluate a published recurrent-CNV method only after defining compatible input requirements.

**SCIENTIFIC CONTRACT:** complete eligible universe and CNV assay population; caller/platform-specific positive categories remain distinct from continuous copy number, ploidy, focality and neutral coverage. A gene can nominate without mutation evidence.

**IMPLEMENTATION STEPS:** 1. Replace mutation-survivor scope binding with explicit universe/source/population binding. 2. Compare per-gene API scans with compatible high-level gene/segment files. 3. Validate one descriptive or established recurrent-event nomination rule. 4. Preserve conflicts/unknowns and reduce globally.

**DATA / ACQUISITION PLAN:** naïve API scale is sum over G of ceil(events(g)/P), potentially tens of thousands of requests even before extra pages. Estimate against F selected compatible files with actual bytes before choosing; do not silently retain survivor-only sampling to save cost.

**SCHEMA / PERSISTENCE IMPACT:** CNV result scope semantics change; coordinated cutover and old-result rejection from independent-discovery consumers.

**VERIFICATION:** later `python -m pytest tests/contracts/test_cnv_discovery_contracts.py tests/integration/test_cnv_discovery_replay.py`; add CNV-only nomination, unavailable assay versus absent event, mixed callers, overlapping categories and global shard equivalence.

**ACCEPTANCE CRITERIA:** a CNV-only eligible gene can reach P08; positive-only data never imply a neutral denominator.

**STOP BOUNDARY:** no SV/fusion or automatic cross-caller pooling. **DEFERRED WORK:** dosage-expression association. **CANONICAL DOC UPDATE:** README/Architecture CNV status and Data Strategy acquisition.

### P08 — Deterministic modality union and integrated baseline

**STATUS:** PARTIAL. **OBJECTIVE:** allow independently nominated genes into the existing canonical state and Wide path.

**WHY THIS WORK REMAINS:** `compose_discovery_states` loops over mutation survivors; acquiring expression independently is not independent expression admission.

**CURRENT CODE TO REUSE:** `compose_discovery_states`, `StatisticalState`, `UnavailableLane`, `research/ranking.py`, Wide policies and Stage 8 comparator.

**CURRENT CODE TO CHANGE:** `research/cutover.py`, expression/CNV discovery result nomination fields, `domain/discovery.py`, `domain/scientific.py` if necessary, `research/ranking.py`, codecs, projections and finalization consumer where provenance changes.

**UPSTREAM SOURCES TO USE:** validated P05–P07 method contracts; no new provider capability required.

**SCIENTIFIC CONTRACT:** union of globally derived per-modality nominations with exact release/cohort/universe compatibility; one state per gene; unavailable modalities remain explicit. Preserve per-modality ranks and nomination reasons without an opaque weighted score.

**IMPLEMENTATION STEPS:** 1. Specify deterministic retain/drop criteria for each validated modality. 2. Build sorted deduplicated union with provenance. 3. Compose evidence for every union member, allowing legitimate missing lanes. 4. Bind the same pre-Jev evidence to the baseline and Wide. 5. Keep operational candidate caps explicit and separate from universe membership.

**DATA / ACQUISITION PLAN:** cached validated lane results; missing follow-up lane acquisition requires its own bounded declared contract, not implicit network access during composition.

**SCHEMA / PERSISTENCE IMPACT:** nomination/union provenance and baseline semantics change; coordinate results, state projection, policy identities and strict readers.

**VERIFICATION:** later `python -m pytest tests/integration/test_cutover.py tests/science/test_lane_composition.py tests/jev/test_ranking.py tests/integration/test_stage8_finalize.py`; add expression-only/CNV-only genes, mixed releases, duplicate union membership and unavailable lanes.

**ACCEPTANCE CRITERIA:** all nominated modalities can contribute; baseline/Wide share evidence identity; no second integrated state.

**STOP BOUNDARY:** no mandatory Arm Jev or new statistical method. **DEFERRED WORK:** P11. **CANONICAL DOC UPDATE:** Architecture current union and Jev Design comparator provenance.

### P09 — Evidence maturity, information roles and honest validation

**STATUS:** PARTIAL. **OBJECTIVE:** prevent semantic prioritization and evaluation labels from becoming scientific validation.

**WHY THIS WORK REMAINS:** typed quality/missingness and optional blinded evaluation exist, but scientific maturity/role contracts are absent; `build_projection` includes cancer-census status.

**CURRENT CODE TO REUSE:** `GeneAnnotation`, typed measurements/methods, `research/prospective.py` grouped blinded evaluation, immutable evidence, Stage 8 limitations.

**CURRENT CODE TO CHANGE:** `domain/scientific.py`, `domain/evidence.py`, `jev/projection.py`, `research/specs.py`, `research/finalize.py`, dossier contracts and codecs; extend offline evaluation separately from runtime.

**UPSTREAM SOURCES TO USE:** primary references for the selected method/validation design; current external source/version/licensing before any labels are adopted. No external source is approved here.

**SCIENTIFIC CONTRACT:** classify information as discovery input, validation label or orthogonal follow-up. If census labels evaluate discovery, exclude them from feature construction, thresholds and semantic admission. Evidence levels require deterministic supporting artifacts; Jev never promotes them. Scientific holdouts are case-disjoint and predeclared, unlike operational shards or reviewer-label group splits.

**IMPLEMENTATION STEPS:** 1. Bind information roles to profile and projection eligibility. 2. Remove evaluation-only labels from discovery projections. 3. Derive maturity from attributable measurement/statistical/replication/functional evidence. 4. Declare a power-appropriate holdout or report validation unavailable. 5. Freeze thresholds before holdout evaluation.

**DATA / ACQUISITION PLAN:** existing evidence initially; no new acquisition until a validation source/design is chosen. Split manifests hash membership and preserve seed/rule; never use a universal 70/30 default.

**SCHEMA / PERSISTENCE IMPACT:** explicit maturity/roles and validation references with coordinated readers/projections/final results; preserve old interpretations as historical.

**VERIFICATION:** later `python -m pytest tests/jev/test_projection.py tests/unit/test_prospective.py tests/integration/test_stage8_finalize.py`; add label-exclusion, same-case leakage, unavailable replication and Jev-output-invariance of evidence level.

**ACCEPTANCE CRITERIA:** every claimed level has deterministic evidence; validation labels cannot influence the evaluated discovery path.

**STOP BOUNDARY:** no functional dataset or automatic inferential promotion. **DEFERRED WORK:** P15. **CANONICAL DOC UPDATE:** Product Scope, Jev Design and Architecture implemented maturity/roles.

### P10 — One deterministic pathway or cross-modal method

**STATUS:** REQUIRED, conditional on scientific eligibility. **OBJECTIVE:** add a justified relationship-level evidence method without fabricated pathway scores.

**WHY THIS WORK REMAINS:** integrated lane display is not pathway analysis or sample-matched association.

**CURRENT CODE TO REUSE:** `StatisticalState`, population/source/method identities, deterministic method conventions and missingness.

**CURRENT CODE TO CHANGE:** `science/methods.py` plus one narrow method module, `domain/scientific.py`, `research/cutover.py`, codecs and bounded projection if a semantic consumer is justified.

**UPSTREAM SOURCES TO USE:** selected primary GDAN/TCGA-compatible analysis method and current pathway provider version/licensing/identifier mapping; U2 for sample/aliquot relationships. Selection of that source/method is a prerequisite, not a fabricated completed decision.

**SCIENTIFIC CONTRACT:** pathway membership is external deterministic data; enrichment background is the actual tested/mapped universe. Cross-modal analysis instead requires a declared compatible assay intersection, sample mapping, effect/null and multiple-testing family. Split these into separate implementation prompts when both are desired.

**IMPLEMENTATION STEPS:** 1. Choose one question/source/method and prove eligibility. 2. Freeze mapping and population. 3. Calculate deterministic effects/statistics globally. 4. Persist exclusions, uncertainty and limitations. 5. Project only summaries with an actual Wide/Deep consumer.

**DATA / ACQUISITION PLAN:** versioned membership table or cached compatible modality evidence; quantify file count/bytes/licensing before ingestion. No raw sequencing. Retain source/mapping hashes and universe membership.

**SCHEMA / PERSISTENCE IMPACT:** one typed evidence extension; synchronized codecs/projection only if consumed.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_methods.py tests/jev/test_projection.py` plus method-specific independent reference cases for mapping loss, wrong background, incompatible assay matching and global FDR.

**ACCEPTANCE CRITERIA:** reproducible source-grounded relationship evidence; unavailable when matching or method inputs fail.

**STOP BOUNDARY:** no generic pathway engine or weighted target score. **DEFERRED WORK:** other relationship methods. **CANONICAL DOC UPDATE:** Architecture supported method and Data Strategy source.

### P11 — Revalidate Jev questions and conditional Arm review

**STATUS:** PARTIAL; Arm itself is optional. **OBJECTIVE:** preserve the semantic boundary while exposing only useful new validated evidence.

**WHY THIS WORK REMAINS:** typed primitives/validation exist; richer evidence and information-role restrictions need corresponding bounded questions. New batching/Arm behavior cannot be assumed already supported.

**CURRENT CODE TO REUSE:** `TypeSafeAdapter`, `JevService`, question definitions, applicability, projections and answer validation; Python Wide/next-move consumers.

**CURRENT CODE TO CHANGE:** `jev/questions.py`, `projection.py`, `contracts.py`, `service.py`, `typesafe_adapter.py` only for necessary adapter gaps; discovery disposition only if Arm is adopted.

**UPSTREAM SOURCES TO USE:** current official TypeSafe primitives/SDK/pattern docs and feature-discovery cookbook cited above; recheck failed direct page retrieval before new API use.

**SCIENTIFIC CONTRACT:** a semantic question interprets under-ranking/coherence/uncertainty that deterministic arithmetic cannot decide exactly. Input is one bounded typed target/revision; output cannot change facts, maturity or select arbitrary tools. Optional Arm consumes only `JEV_REVIEW`; deterministic retain/drop bypass it.

**IMPLEMENTATION STEPS:** 1. Record input/question/primitive/applicability/failure/Python-consumer for each proposed change. 2. Keep current valid questions. 3. Add only justified dimensions after P08/P09. 4. If Arm has no concrete residual semantic question, mark it unnecessary. 5. Extend the shared failure corpus before any operational batching.

**DATA / ACQUISITION PLAN:** immutable typed evidence only; replay/stub responses first. Provider call budget follows eligible review targets, never raw genomic row count.

**SCHEMA / PERSISTENCE IMPACT:** change question/projection/cache identity only when semantics change; no preemptive version bump.

**VERIFICATION:** later `python -m pytest tests/jev tests/integration/test_deep_slice.py tests/integration/test_hypothesis_stage.py`; explicitly cover timeout, transport/empty/malformed responses, wrong types/questions/versions, missing/extra fields, non-finite/range values, duplicate answers, partial batch, target/revision mismatch and invalid applicability. Failure cannot silently retain/admit/advance a target or imply scientific completion; operational finalization may still record ABSTAIN/failure.

**ACCEPTANCE CRITERIA:** each question has a semantic need and deterministic consumer; invalid output has typed failure; evidence level is unchanged by judgments.

**STOP BOUNDARY:** no autonomous question evolution, label-tuned runtime, model tool selection or mandatory Arm layer. **DEFERRED WORK:** optional performance changes until measured need. **CANONICAL DOC UPDATE:** Jev Design implemented questions and failure contract.

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

### P12 — One real follow-up and deterministic dispatch policy

**STATUS:** PARTIAL. **OBJECTIVE:** add one evidence-producing investigation step and an explicit Python selection rule where existing ambiguity blocks autonomous progress.

**WHY THIS WORK REMAINS:** current actions check integrity/faithfulness or summarize existing expression/CNV evidence. `decide_next_move` can request follow-up, while multiple eligible dispatch choices may require explicit selection. This is not unrestricted autonomous scientific experimentation.

**CURRENT CODE TO REUSE:** `science/actions.py`, `domain/actions.py`, `research/deep.py`, `nextmove.py`, `investigation.py`, immutable revisions, hypotheses and Stage 8.

**CURRENT CODE TO CHANGE:** existing registry/eligibility/dispatch functions and `research/specs.py`; one method adapter and typed evidence/action output; finalization summaries only if required.

**UPSTREAM SOURCES TO USE:** primary source/method for the selected follow-up from P05–P10 or P15, not every GDC repository.

**SCIENTIFIC CONTRACT:** one candidate, explicit remaining question, bounded deterministic method/population and evidence output. Python resolves eligibility, cost, choice and stopping; unresolved choice abstains. Untestable hypotheses remain NOT_EVIDENCE.

**IMPLEMENTATION STEPS:** 1. Choose one validated follow-up. 2. Register typed inputs/output, budget and eligibility. 3. Specify attributable deterministic action choice with scientific rationale, never alphabetical registry order. 4. Dispatch once against the exact revision. 5. Produce a new immutable revision, rejudge and finalize through existing Stage 8.

**DATA / ACQUISITION PLAN:** reuse cached evidence where sufficient; otherwise bounded candidate/method-specific API/file preflight under P04. Persist source and action budgets; no arbitrary URL or generated query.

**SCHEMA / PERSISTENCE IMPACT:** registered action/method and evidence payload extension; preserve old chain and unsupported-version rejection.

**VERIFICATION:** later `python -m pytest tests/science/test_actions.py tests/science/test_nextmove.py tests/integration/test_deep_slice.py tests/integration/test_hypothesis_stage.py tests/integration/test_stage8_finalize.py`; exercise duplicate action, ambiguous choice, unavailable method, stale revision, budget stop and replay.

**ACCEPTANCE CRITERIA:** action produces independently attributable evidence and per-candidate revision; no repeated unbounded loop or model-selected tool.

**STOP BOUNDARY:** one action and its necessary policy change. **DEFERRED WORK:** broad action catalogue. **CANONICAL DOC UPDATE:** Architecture investigation behavior; Jev Design action-value role; regenerate Repository Facts only after actual code constants change.

### P13 — Bounded Campaigns within an autonomous Program

**STATUS:** REQUIRED. **OBJECTIVE:** sequence validated reproducible Campaigns using explicit persisted Python policy.

**WHY THIS WORK REMAINS:** runs and candidate completion exist; Program/Campaign selection and release comparison contracts do not. The current LUAD spec is not an autonomous validation certificate.

**CURRENT CODE TO REUSE:** `ResearchSpec`, current runners, run transitions, repository/artifact/event infrastructure and candidate finalization.

**CURRENT CODE TO CHANGE:** `research/specs.py`, `research/live.py`/`orchestrator.py` entry boundaries, `domain/runs.py`, repository/database/readers, `cli/main.py`; add small `research/program.py` and `research/campaign_selection.py` modules only for missing long-lived coordination.

**UPSTREAM SOURCES TO USE:** U1 release/status semantics; P02 validated source/method bindings. No new scientific method.

**SCIENTIFIC CONTRACT:** one Campaign = coherent cohort + pinned source release + versioned method profile. Program continuation is operational; scientific Campaigns and candidate chains remain bounded. New releases never mutate prior results.

**IMPLEMENTATION STEPS:** 1. Bind Campaign identity/readiness to existing spec. 2. Persist candidate queue and completion. 3. Define named/versioned deterministic campaign priority and scientifically justified ties. 4. Resume idempotently or enter PROGRAM_IDLE when none are eligible. 5. Add bounded release checks with new source contexts. 6. Compare only compatible results; report source/method changes or NOT_COMPARABLE separately from biological interpretation.

**DATA / ACQUISITION PLAN:** release metadata polling only at declared intervals; discovery delegates to the selected Campaign's preflight. No new bulk acquisition in scheduler logic. Release polling is a future runtime feature, not a Codex automation created by this task.

**SCHEMA / PERSISTENCE IMPACT:** Program/Campaign/selection-event identities and durable progress in existing storage; separate from scientific state, no distributed queue/DAG.

**VERIFICATION:** later `python -m pytest tests/test_ownership_recovery.py tests/test_domain_events.py tests/integration/test_stage8_finalize.py` plus new focused cases for restart, unvalidated profile exclusion, deterministic ties, idle, duplicate release and incomparable source/method changes.

**ACCEPTANCE CRITERIA:** validated Campaign → independently finalized candidates → completion → attributable next Campaign/idle; a non-LUAD fixture proves generic architecture only. A second real cancer needs its own validation.

**STOP BOUNDARY:** no Researcher Lab/UI or uncontrolled infinite acquisition. **DEFERRED WORK:** P14 and second-cancer scientific validation. **CANONICAL DOC UPDATE:** README/Product Scope actual autonomy; Architecture progression and release comparisons.

### P14 — Researcher run ownership isolation

**STATUS:** PARTIAL infrastructure, REQUIRED product boundary. **OBJECTIVE:** let optional researcher runs reuse science without affecting autonomous runtime state.

**WHY THIS WORK REMAINS:** `ResearchOwnership` is an exclusive directory lock; it does not encode SYSTEM_AUTONOMOUS versus RESEARCHER_RUN ownership. Operator selection paths require ownership checks before being exposed alongside a Program.

**CURRENT CODE TO REUSE:** repository run IDs, artifact paths, exclusive lock, strict readers and immutable source caches.

**CURRENT CODE TO CHANGE:** `storage/ownership.py`, `repositories.py`, `database.py`, `research/specs.py`, `research/live.py` operator-selection boundary and CLI/API mutation entry points actually exposing researcher runs.

**UPSTREAM SOURCES TO USE:** NONE; local ownership contract.

**SCIENTIFIC CONTRACT:** same methods/populations can be used in different owner contexts, but specs, admission, queues, actions, evidence, hypotheses, dossiers and future Campaign progression are isolated. Shared immutable source bytes are acceptable with exact provenance.

**IMPLEMENTATION STEPS:** 1. Bind owner context at run creation. 2. Scope all writable/readback scientific relations. 3. Reject cross-owner mutation and selection. 4. Share only verified immutable cache entries. 5. Require later explicit versioned code/science changes for researcher findings to influence autonomy.

**DATA / ACQUISITION PLAN:** NONE beyond existing run sources; cache ownership metadata does not authorize new acquisition.

**SCHEMA / PERSISTENCE IMPACT:** run ownership/storage contract; preserve historical runs, do not guess their owner or rewrite evidence.

**VERIFICATION:** later `python -m pytest tests/test_ownership_recovery.py tests/test_persistence_guards.py tests/test_api.py`; add adversarial cross-owner references, shared-cache corruption, operator selection and concurrent-write cases.

**ACCEPTANCE CRITERIA:** researcher activity cannot mutate any autonomous scientific/control state or selection input.

**STOP BOUNDARY:** no Lab UI redesign or approval loops. **DEFERRED WORK:** optional researcher interface. **CANONICAL DOC UPDATE:** Product Scope and Architecture implemented isolation.

### P15 — One orthogonal functional or external replication source

**STATUS:** REQUIRED only for claims needing that evidence. **OBJECTIVE:** add one independently sourced evidence axis after genomic discovery is valid.

**WHY THIS WORK REMAINS:** no inspected contract establishes functional dependency, targetability, clinical evidence or independent-cohort replication.

**CURRENT CODE TO REUSE:** method/source identities, information-role contract from P09, registered actions, evidence revisions and dossier.

**CURRENT CODE TO CHANGE:** one narrow source adapter, `domain/evidence.py`, `science/actions.py`, `research/specs.py`, codecs and Stage 8 dossier consumer.

**UPSTREAM SOURCES TO USE:** current official selected source (for example DepMap, a cancer-gene catalogue, targetability resource or independent compatible cohort) and its primary methodology. Access, version, licensing and mapping remain unresolved until source selection; no provider is implicitly approved by its mention here.

**SCIENTIFIC CONTRACT:** dependency, known-cancer context, replication, targetability and clinical evidence remain distinct axes. Dependency is not therapeutic efficacy; known-gene status is not proof of a target in this cohort. Predeclare discovery/validation/follow-up role.

**IMPLEMENTATION STEPS:** 1. Choose one question/source and verify lawful usable access/version. 2. Validate identifier mapping and population comparability. 3. Implement one deterministic interpretation. 4. Attach evidence with limitations; promote only the supported axis/level. 5. Keep labels out of prior evaluated discovery.

**DATA / ACQUISITION PLAN:** selected high-level table or bounded API, exact file count/bytes and retention decided in source preflight; never full external mirrors by default.

**SCHEMA / PERSISTENCE IMPACT:** one typed external evidence contract, source/method binding and strict readers.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_actions.py tests/integration/test_stage8_finalize.py` plus independent source reconciliation, ambiguous mapping, incompatible populations and unavailable external data cases.

**ACCEPTANCE CRITERIA:** attributable orthogonal evidence with honest claim limits; no Jev-created functional support.

**STOP BOUNDARY:** one source and evidence axis; no composite druggability score. **DEFERRED WORK:** other sources/clinical claims. **CANONICAL DOC UPDATE:** Product Scope supported evidence and Data Strategy access/provenance.

### P16 — Additional modality admission, individually justified

**STATUS:** REQUIRED only when a selected cohort/question needs another modality. **OBJECTIVE:** admit one of SV/fusion, methylation, miRNA, RPPA/protein, single-cell or clinical/outcome evidence with its own scientific contract.

**WHY THIS WORK REMAINS:** current `Lane` contains mutation, expression and CNV; an upstream endpoint list does not implement additional science.

**CURRENT CODE TO REUSE:** P02 capability gate, P03 universe/shards, existing typed lane pattern, sources, missingness, P08 union and P09 maturity.

**CURRENT CODE TO CHANGE:** only the selected endpoint/parser or file adapter, a narrow deterministic method module, `domain/scientific.py`, codecs and necessary composition/projection consumer. Do not widen every lane in advance.

**UPSTREAM SOURCES TO USE:** relevant current U1 pipeline page, U2 identity/workflow, and the public workflow/tool linked there if needed. Inspect and pin those specific sources at implementation time; unrelated modality internals were intentionally not audited here.

**SCIENTIFIC CONTRACT:** declare feature universe, assay population, measurement unit, QC, method/version, missingness, deterministic output and actual policy consumer. Single-cell donor/cell nesting, survival censoring or platform-specific probes require their own contracts and cannot inherit gene-level assumptions silently.

**IMPLEMENTATION STEPS:** 1. Establish a concrete cohort capability and scientific question. 2. Select an established method and verify source semantics. 3. Preflight source/scale. 4. Implement one validated lane. 5. Admit it through existing union/state only after independent reconciliation.

**DATA / ACQUISITION PLAN:** unknown until modality selection; endpoint/product, scientific population, shard unit, expected requests/files/bytes and retention must all be resolved before acquisition. Prefer indexed/high-level evidence; no raw-data fallback by default.

**SCHEMA / PERSISTENCE IMPACT:** one explicitly versioned lane extension, not a generic plugin architecture.

**VERIFICATION:** later `python -m pytest tests/unit/test_scientific_contracts.py tests/science/test_lane_composition.py tests/integration/test_cutover.py` plus source-specific real-response reconciliation and missingness/completeness checks.

**ACCEPTANCE CRITERIA:** one scientifically validated modality with reproducible outputs and bounded integration. **STOP BOUNDARY:** no simultaneous modality expansion. **DEFERRED WORK:** every other modality. **CANONICAL DOC UPDATE:** Architecture capability status and Data Strategy selected source.

## Documentation outcome and handoff

The six supplied documents are now the canonical product/design set, adapted to distinguish target requirements from current implementation. README provides the entry point; Architecture owns the current map and target flow; Product Scope owns claims; Scientific Invariants owns stable rules; Data Strategy owns acquisition constraints; Jev Design owns semantic boundaries. This plan owns remaining implementation work. Repository Facts retains its generated block unchanged; AGENTS.md retains the existing task rules.

The next implementation prompt should request P01 alone against the then-current HEAD. Reinspect that bounded path before changing it; do not treat this dated plan as proof that future code still has the same gaps.
