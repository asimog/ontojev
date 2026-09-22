# Domain and data contracts

Proposed version `1`. These are application-owned schemas, not claims about provider fields. Strict validation rejects non-finite numbers, unknown executable actions, inconsistent foreign references, and unknown schema versions. UTC RFC3339 timestamps, UUID identifiers, nonnegative integer counts, SHA-256 lowercase hex digests. Optional fields are nullable with a reason; null is never silently converted to zero.

Status labels: **IMPLEMENTED** contracts are precise and match code. **PROVISIONAL** (Phase 4+)
shapes describe intent only; they are not required to be implemented exactly, and the smallest
representation compatible with the existing repository should be chosen when that phase begins.
A future refresh is normally just another bounded `ResearchRun`, not a permanent cycle subsystem.

## Shared contracts

`EvidenceAvailability = OBSERVED | MISSING | NOT_EXAMINED | NOT_ACQUIRED | UNAVAILABLE_ACCESS | UNAVAILABLE_SOURCE | INSUFFICIENT | INCOMPATIBLE | FAILED | PARTIAL | UNSUPPORTED_IN_V1`.

`Metric = {name, value: finite number|null, unit, availability, reason_code|null, observation_ref|null}`. A measured zero requires OBSERVED and provenance. Inferential fields additionally require a method result reference.

`ArtifactRef = {artifact_id, sha256, size_bytes, media_type, purpose, schema_version}`. Relative filesystem paths are stored internally, never accepted as browser input.

`SourceRef = {request_id, response_artifact_id, response_sha256, endpoint, normalized_request_hash, retrieved_at, source_release: string|null, release_status: KNOWN|UNVERIFIED, parser_version, json_pointer_or_table_locator, completeness}`.

`Population = {population_id, definition, program, project, modality, sample_type, workflow, pipeline_version, eligible_n: int|null, examined_n, excluded_counts_by_reason, case_set_artifact, case_set_hash, sample_mapping_artifact|null, selection_method, selection_version, sweep_offset, completeness, harmonization_context}`. `eligible_n` is the cohort case count, `examined_n` is the case frame actually returned; they are distinct. Per-modality counts (assay-available, returned, valid, missing) live on the modality result, not on one generic population count. Unknown eligible population sizes stay null. Mapping absent from an API response is not inferred from a gene name or case match.

## ResearchRun

```text
ResearchRun
  run_id, schema_version, mode: FAKE|LIVE
  fixture_id?, fixture_version?
  status: PENDING|RUNNING|COMPLETED|FAILED|STOPPED
  current_stage?, active_candidate_id?, last_sequence
  created_at, started_at?, ended_at?
  worker_id, worker_version, code_revision?, environment_hash
  config_snapshot_artifact, config_hash, routing_policy_version
  cursor_before, selected_project_ids[] (one project for a single-cohort spec), scope_hash
  counts: projects_attempted, projects_completed, states_generated,
    states_valid, states_selected, states_evaluated, candidates_promoted,
    hypotheses_created, followups_started, dossiers_created,
    candidates_failed, candidates_deferred
  budget_snapshot: configured_caps, requests_started, body_bytes_read,
    outstanding_byte_reservations, cache_hits, limit_reasons[]
  provider_usage: jev{calls,input_tokens?,output_tokens?,cost?}, llm{...}
  stop_requested, outcome_reason?, coverage: COMPLETE_FOR_SCOPE|PARTIAL
```

Counters refer to real actions. Fake runs use zero external calls/bytes and separately labeled simulated activity. COMPLETED means the bounded run ended normally, not that all candidates succeeded or that all GDC was covered. Configuration is frozen at creation.

## CandidateInvestigation (PROVISIONAL, Phase 4+)

A candidate gene is not itself a scientific investigation: an investigation is the candidate plus
its cohort/population and research question. The shape below is intent, not a required table.

```text
CandidateInvestigation
  candidate_id, run_id, schema_version
  entity: {gene_id, gene_symbol?, genome_build?}
  source_state_id, source_state_hash, scope_hash
  status: NEW|WIDE_EVALUATED|DEEP_ANALYZED|HYPOTHESIZED|FOLLOWUP|
          DOSSIER_READY|TERMINATED|DEFERRED|FAILED
  current_stage, promoted_at?, promotion_slot: 1..20|null
  wide_evaluation_id, latest_evidence_state_id?
  iteration: 0..2, followup_count: 0..3, hypothesis_count: 0..6
  promotion_reason, routing_decisions[], terminal_reason?
  dossier_id?, created_at, updated_at
```

A candidate row is created only when selected for deep admission; its NEW → WIDE_EVALUATED transitions reference the already-computed wide answer. Unpromoted states retain evaluations and selection dispositions, without creating thousands of candidate rows. Promotion slots never return to the pool when a candidate fails.

## StatisticalState

Phase 2 implements **schema version 2** (real GDC). The Phase 0 planning shape above is superseded; CNV fields and any recurrence fraction are deliberately absent because no valid open-access measure exists yet.

```text
StatisticalState v2 (mode LIVE)
  state_id, schema_version: 2, state_hash, created_at, run_id
  entity: {gene_id, gene_symbol, biotype, is_cancer_gene_census, genome_build|null}
  scope: {spec_id, research_spec: {cohort, acquisition}, domain, cohort, project_id, programs[], projects[],
          modalities: ["mutation_counts", "expression_summary"],
          workflows[], sample_types[], examined_case_frame,
          comparability: {statuses[], within_cohort: {status, reason},
                          cross_project: {status, reason}}}
  generation: {lane_ids[], lane_versions[], discovery: {method_id, examined_genes_n,
               selection_bias}, rank_in_lane, source_hit_refs[]}
  populations: Population[]
  mutation: {availability, absence_semantics, project_results: MutationSummary[],
             coverage: {case_with_ssm: Metric, project_case_count: Metric}}
  expression: {availability, project_results: ExpressionSummary[],
               coverage: {cases_with_expression: Metric, examined_cases: Metric}}
  cross_project: {projects_with_mutation_observation, projects_with_expression_observation,
                  affected_case_total: Metric, top_project_share: Metric,
                  expression_median_min: Metric, expression_median_max: Metric,
                  coverage_imbalance: bool, direction: "NOT_EXAMINED",
                  comparability_status: "NOT_APPLICABLE", notes[]}
  quality: {api_warnings[], missingness[], duplicate_checks, finite_checks,
            truncation, completeness, acquisition_completeness,
            scientific_sufficiency, acquisition_completeness_definition,
            scientific_sufficiency_definition}
  tested_context: {examined_genes_ref, examined_genes_hash, discovery_method,
                   selection_bias, coverage}
  provenance: {gdc_release, sources: SourceRef[], methods: MethodRef[], environment_hash}
```

`domain`/`cohort` name the single explicitly examined cohort (Phase 2: `lung cancer` / `TCGA-LUAD`). `comparability` carries explicit statuses; GDC harmonization, common project membership and an empty incompatibility list do **not** establish comparability, so `within_cohort` stays `UNVERIFIED` and `cross_project` is `NOT_APPLICABLE` for one cohort. `acquisition_completeness` describes only whether requested provider responses were acquired in full; `scientific_sufficiency` separately describes whether the acquired evidence is sufficient (`SUFFICIENT`/`PARTIAL`/`INSUFFICIENT`).

`MutationSummary = {project_id, population_id, examined_cases: Metric, affected_case_count: Metric(unit "cases"), project_case_with_ssm: Metric, project_case_count: Metric, provider_discovery_rank: {rank, score, lane_id}|null}`. A provider ranking score is explicitly tagged as selection metadata, is excluded from scientific identity, and cannot fill a count, fraction, p-value or effect field. An absent project bucket is `NOT_OBSERVED`, never zero, wildtype or a callable negative. No recurrence fraction is stored because no matched denominator exists (see SCIENTIFIC_INVARIANTS).

`ExpressionSummary = {project_id, population_id, unit: "log2(UQFPKM+1)", transformation: "log2(x+1)", local: {median, sample_sd, minimum, maximum, n_finite, n_missing, n_returned, n_missing_case_columns: Metric, missing_case_ids[], method_id}, provider: {median, stddev: Metric, source: "GENE_SELECTION", estimator_note}|null, provider_unavailable_reason|null, coverage: {examined_cases, assay_available_cases, cases_with_expression, returned_case_columns, valid_measurements, missing_measurements: Metric}}`. The local summary is the primary evidence; `n_missing` includes examined case columns the provider did not return, so a fully valid returned subset never reports zero missingness. The provider summary is retained verbatim as corroborating context with its estimator convention marked unverified only when it covers the whole cohort in one admitted request. Batch medians or standard deviations are never combined; batched cohorts record `BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE`.

Cross-project direction is `NOT_EXAMINED`: mutation counts and expression dispersion carry no signed, comparable up/down effect. CNV summaries and recurrence fractions are Phase 4+ targets requiring their own methods; the Phase 0 planning shape is preserved only in this paragraph as intent.

Phase 4+ target shapes (documented, not implemented): `CNVSummary = {project_id, population_id, category_definition, amplification_count: Metric, deletion_count: Metric, denominator: Metric, categories_observed[], missing_n, ambiguous_mapping_n}` — Gain is not automatically amplification and category-to-label mappings are explicit method policy; `MutationSummary` gains a matched `observed_fraction` only if a denominator with identical source/filter semantics is established.

## JevStateProjection (Phase 3)

```text
JevStateProjection
  projection_id, projection_version: "jev-state-projection-v1", run_id, state_id
  source_state_hash, projection_hash, artifact_id, included_fields[]
  payload: {entity, scope, project_observations[], cross_project, missingness[],
            limitations[], eligible_followups[]}
```

`project_observations[] = {project_id, cases_examined, cases_with_ssm, cases_with_expression, affected_cases|null, expression_local|null, expression_provider|null}`. Every field derives from deterministic StatisticalState fields; nothing is recomputed from raw responses at projection time. `eligible_followups` is empty until Phase 4 registers executable actions. The projection hash covers the canonical payload bytes and is the cache identity component for inference; routing-policy version is excluded.

## Wide ranking records (Phase 3)

```text
WideRanking (artifact + event)
  ranking_id, run_id, policy_version, kind: "BASELINE"|"JEV"
  entries: [{state_id, state_hash, rank, dimensions{}, admission}]
  admitted_candidate_ids[], baseline_ranking_ref?, created_at
```

The baseline ranking is always computed from deterministic dimensions; the Jev ranking is computed from persisted raw judgment vectors. Both are retained so Phase 3 can compare baseline vs baseline+Jev on the same states. Jev never replaces the baseline.

## EvidenceState (PROVISIONAL, Phase 4+)

Evidence revisions are immutable (`E0 → E1 → E2`). The exact fields below are provisional; choose
the smallest representation compatible with the existing repository when Phase 4 begins.

```text
EvidenceState
  evidence_state_id, schema_version, evidence_hash, created_at
  run_id, candidate_id, entity, scope_hash
  source_statistical_state: {state_identity_hash}
  previous_evidence_state_id?, iteration_number: 0..2
  research_puzzle: {observed_pattern_refs[], unresolved_questions[],
                    origin: DETERMINISTIC_TEMPLATE}
  deterministic_observations: MethodResult[]
  project_level_evidence: {project_id, result_refs[], population_refs[]}[]
  cross_project_patterns: {result_refs[], limitations[]}
  cross_modal_patterns: {result_refs[], mapping_status, limitations[]}
  contradictory_evidence: {observation_refs[], comparison_rule_id, reason}[]
  missing_evidence: {needed_evidence, availability, reason}[]
  unavailable_evidence: {needed_evidence, availability, reason}[]
  quality_and_fragility: {sample_sizes, missingness, dominance,
                          sensitivity_results[], warnings[]}
  methods_used: MethodRef[]
  provenance: {sources: SourceRef[], input_artifact_hashes[], environment_hash}
  tested_context: {families[], selection_history_ref, exploratory: true}
```

`MethodResult = {result_id, method_id, method_version, parameters, population_refs[], input_artifact_refs[], eligibility, n_effective, exclusions, observations: Metric[], effect:{name,value,unit}|null, interval:{method,level,lower,upper}|null, p_value|null, q_value|null, inference_status, family_id|null, limitations[], provenance, result_hash}`. Missing CI or unavailable inference has a reason; it is not replaced by 0 or a model estimate.

`CorrectionFamily = {family_id, definition, method_id, tested_hypotheses_ref, tested_universe_hash, attempted_n, testable_n, excluded_reasons, adjustment_method, selection_history, locked_at}`. A follow-up family is a new recorded family, not a silent recomputation that overwrites old q-values.

EvidenceState has no writable Jev answer or hypothesis fields. A Jev request envelope may contain separately named `deterministic_evidence`, `prior_semantic_judgment`, and `generated_hypothesis`; default deep evaluation sends evidence alone.

## Other records

| Model | Required fields and constraints |
|---|---|
| JevEvaluation | evaluation_id, run/candidate/state refs and hashes, purpose, exact question-set artifact/hash/version, requested/resolved model, adapter version, typed full answers, latency, usage, cache provenance, error, routing policy version; see JEV_DESIGN |
| Hypothesis | id, candidate_id, evidence_state_id, statement, proposed_mechanism, predictions[], contradicted_if[], distinguishing_tests[], required_evidence[], unsupported_assumptions[], proposed_action_ids[], factual_observation_refs[], generation_id; never a measured result |
| HypothesisEvaluation | evaluation_id, one hypothesis_id, one evidence_state_id, judgment vector; no sibling hypotheses or sibling verdicts in provider input |
| FollowUpAction definition (PROVISIONAL) | action_id, version, typed parameters, required data/fields, eligibility, minimum n, method_id, limitations, worst-case request/byte reservation, executor function |
| FollowUpExecution (PROVISIONAL) | execution_id, candidate_id, action/version, input evidence hash, validated parameters, consumed slot, iteration, status, source requests, new result refs, failure/defer reason |
| DiscoveryCursor (PROVISIONAL, not required) | version, inventory hash, sweep number, stable project order, next project offset, per-project lane/case/gene offsets, attempted/completed/skipped dispositions, freshness timestamp |
| GDCRequestAttempt | request_id, logical_query_id, run_id, attempt_no, method, endpoint, canonical request/hash, status, byte counts, reserved allowance, timestamps, HTTP status, response hash/ref, completeness, error |
| ResearchDossier | id, run/candidate refs, mode, schema_version, JSON artifact, derived Markdown artifact, evidence/judgment/hypothesis/follow-up refs, 25 sections from the master specification, created_at; unique candidate_id |

`DiscoveryCursor` is **not required architecture**. With the current single-cohort bounded sweep a
refresh can simply be another `ResearchRun` (the API reports `cursor.present = false`). No
persisted `NextResearchMove` exists or is planned; a next move is a plain Python result
(`FOLLOW_UP`, `GENERATE_HYPOTHESES`, `TEST_HYPOTHESIS`, `NEXT_CANDIDATE`, `COMPLETE`, `ABSTAIN`).
The PROVISIONAL Phase 4+ shapes must not be scaffolded before their phase is approved.

Content hashes exclude operational UUIDs/timestamps but include schema, scientific inputs, membership, units, context, method/parameters, correction universe and outputs. Keep timestamps separately. Canonical JSON sorts object keys and set-valued IDs, preserves meaningful array order, uses a versioned finite-number encoding, and rejects NaN/Infinity. Byte hashes additionally preserve exact source responses. Identical scientific state can be recognized across runs without conflating differently selected populations.

Phase 1 implements this rule with two explicit identity projections in `cancerjev/domain/identity.py`: `statistical_state_identity_payload` (entity, scope/projects, pattern measurement and unit, quality/missingness, tested context, provenance/methods) and `evidence_state_identity_payload` (entity, source-state content hash, puzzle, observations without operational result ids, project membership, missingness, method/version, limitations, revision). Phase 2 extends `statistical_state_identity_payload` to the v2 real-GDC fields (entity identity, project frame, examined populations, mutation counts and coverage, local/provider expression summaries, cross-project descriptives, missingness, discovery/selection context, method versions, source hashes) with the same exclusion rule. Operational `run_id`/`state_id`/`candidate_id`/`evidence_state_id`/`previous_evidence_state_id`, timestamps and provider selection scores are excluded. Artifact byte SHA-256 is separate and always hashes the exact serialized artifact bytes.


## Authoritative dossier sections

The dossier JSON has fixed section keys, each holding typed references and optional labeled narrative. Markdown and web views derive from this JSON. These are the 25 required sections, in order:

1. `research_puzzle`
2. `candidate_entity`
3. `investigation_rationale`
4. `initial_broad_evidence`
5. `jev_wide_judgments`
6. `deterministic_deep_evidence`
7. `project_evidence`
8. `cross_project_evidence`
9. `cross_modal_evidence`
10. `contradictory_evidence`
11. `missing_unavailable_evidence`
12. `jev_deep_judgments`
13. `competing_hypotheses`
14. `hypothesis_jev_reviews`
15. `deterministic_followups_performed`
16. `followup_results`
17. `remaining_uncertainty`
18. `proposed_wet_lab_experiment`
19. `predictions_by_hypothesis`
20. `falsification_criteria`
21. `gdc_provenance`
22. `method_versions`
23. `jev_model_question_versions`
24. `llm_provider_model_metadata`
25. `research_only_notice`

Unavailable sections remain present with availability/reason rather than invented content. Proposed experiments and predictions are explicitly unmeasured. The readiness validator requires at least two distinct competing explanations for a dossier; an inability to produce them can defer the candidate without manufacturing alternatives. Fixture mode uses clearly synthetic observations and fixture model identifiers.
