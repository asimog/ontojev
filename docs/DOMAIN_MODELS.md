# Domain and data contracts

Proposed version `1`. These are application-owned schemas, not claims about provider fields. Strict validation rejects non-finite numbers, unknown executable actions, inconsistent foreign references, and unknown schema versions. UTC RFC3339 timestamps, UUID identifiers, nonnegative integer counts, SHA-256 lowercase hex digests. Optional fields are nullable with a reason; null is never silently converted to zero.

## Shared contracts

`EvidenceAvailability = OBSERVED | MISSING | NOT_EXAMINED | NOT_ACQUIRED | UNAVAILABLE_ACCESS | UNAVAILABLE_SOURCE | INSUFFICIENT | INCOMPATIBLE | FAILED | PARTIAL | UNSUPPORTED_IN_V1`.

`Metric = {name, value: finite number|null, unit, availability, reason_code|null, observation_ref|null}`. A measured zero requires OBSERVED and provenance. Inferential fields additionally require a method result reference.

`ArtifactRef = {artifact_id, sha256, size_bytes, media_type, purpose, schema_version}`. Relative filesystem paths are stored internally, never accepted as browser input.

`SourceRef = {request_id, response_artifact_id, response_sha256, endpoint, normalized_request_hash, retrieved_at, source_release: string|null, release_status: KNOWN|UNVERIFIED, parser_version, json_pointer_or_table_locator, completeness}`.

`Population = {population_id, definition, program, project, modality, sample_type, workflow, pipeline_version, eligible_n: int|null, selected_n, observed_n, excluded_counts_by_reason, case_set_artifact, case_set_hash, sample_mapping_artifact|null, selection_method, selection_version, sweep_offset, completeness, comparability_key}`. Unknown eligible population sizes stay null. Mapping absent from an API response is not inferred from a gene name or case match.

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
  cursor_before, selected_project_ids[0..12], scope_hash
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

## CandidateInvestigation

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

```text
StatisticalState
  state_id, schema_version, state_hash, created_at, run_id
  entity: {gene_id, gene_symbol?, genome_build?}
  scope: {programs[], projects[], modalities[], workflows[], sample_types[],
          comparability_groups[]}
  generation: {lane_ids[], lane_versions[], rank_in_lane?, selection_scope,
               diversity_stratum, source_hit_refs[]}
  populations: Population[]
  mutation: {availability, project_results: MutationSummary[], recurrence}
  expression: {availability, project_results: ExpressionSummary[], coverage}
  cnv: {availability, project_results: CNVSummary[]}
  cross_project: {compared_groups[], recurrence, direction_consistency,
                  exceptions[], noncomparable_groups[], coverage}
  quality: {invalid_projects[], insufficient_projects[], missingness[],
            warnings[], duplicate_checks, finite_checks}
  tested_context: {examined_genes_ref, examined_genes_hash, lanes[],
                   hypotheses_tested_ref?, selection_bias, coverage, truncation}
  provenance: {sources: SourceRef[], methods: MethodRef[], environment_hash}
```

`MutationSummary = {project_id, population_id, mutation_case_count: Metric, mutation_data_denominator: Metric, observed_fraction: Metric, consequence_filter, unique_case_rule, provider_rank_score: Metric|null}`. A provider ranking score is explicitly tagged as ranking metadata and cannot fill a count, p-value, or effect field. Frequencies require matched numerator and denominator filters.

`ExpressionSummary = {project_id, population_id, unit, transformation, stddev: Metric, median: Metric, rank: Metric, rank_universe_hash, percentile: Metric, selection_threshold, mapping_status}`. A top-k list cannot supply a genome-wide percentile without the full ranked universe. GDC-returned standard deviation is retained as a provider statistic; its exact estimator convention is UNVERIFIED unless documented.

`CNVSummary = {project_id, population_id, category_definition, amplification_count: Metric, deletion_count: Metric, denominator: Metric, categories_observed[], missing_n, ambiguous_mapping_n}`. Gain is not automatically amplification. Category-to-label mappings are explicit method policy.

Cross-project direction requires an actual signed, comparable measure. Mutation recurrence or expression variance alone has no up/down effect direction. Store NOT_EXAMINED instead of manufacturing a reversal feature.

## EvidenceState

```text
EvidenceState
  evidence_state_id, schema_version, evidence_hash, created_at
  run_id, candidate_id, entity, scope_hash
  source_statistical_state: {state_id, state_hash}
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
| FollowUpAction definition | action_id, version, typed parameters, required data/fields, eligibility, minimum n, method_id, limitations, worst-case request/byte reservation, executor function |
| FollowUpExecution | execution_id, candidate_id, action/version, input evidence hash, validated parameters, consumed slot, iteration, status, source requests, new result refs, failure/defer reason |
| DiscoveryCursor | version, inventory hash, sweep number, stable project order, next project offset, per-project lane/case/gene offsets, attempted/completed/skipped dispositions, freshness timestamp |
| GDCRequestAttempt | request_id, logical_query_id, run_id, attempt_no, method, endpoint, canonical request/hash, status, byte counts, reserved allowance, timestamps, HTTP status, response hash/ref, completeness, error |
| ResearchDossier | id, run/candidate refs, mode, schema_version, JSON artifact, derived Markdown artifact, evidence/judgment/hypothesis/follow-up refs, 25 sections from the master specification, created_at; unique candidate_id |

Content hashes exclude operational UUIDs/timestamps but include schema, scientific inputs, membership, units, context, method/parameters, correction universe and outputs. Keep timestamps separately. Canonical JSON sorts object keys and set-valued IDs, preserves meaningful array order, uses a versioned finite-number encoding, and rejects NaN/Infinity. Byte hashes additionally preserve exact source responses. Identical scientific state can be recognized across runs without conflating differently selected populations.

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
