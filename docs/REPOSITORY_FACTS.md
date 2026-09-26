# Repository facts

Machine-checked table of the mutable repository-wide facts (schema versions,
dossier/final-result versions, action registry, Jev projection and question-set
identities, policy versions, API and SQLite versions). Facts are collected from
the code constants that own them (`tests/repository_facts.py`); the generated
block below is verified against that code by the offline test suite
(`tests/test_repository_facts.py`), so this document cannot silently drift.

Commands (run from the repository root):

- check: `python tests/repository_facts.py check` (also enforced by `pytest`)
- re-render after an authorized version change: `python tests/repository_facts.py render`

Other documentation must not restate these values. When a fact legitimately
changes, change the code constant, run the renderer, and update only the prose
that describes behavior (see the source-of-truth hierarchy in
[AGENTS.md](../AGENTS.md)).

<!-- repository-facts:begin (generated; python tests/repository_facts.py render) -->
```json
{
  "action_registry_version": "4",
  "api_version": "3.0.0",
  "arm_jev_decision": "DEFER",
  "campaign_selection_policy": "campaign-selection-v2",
  "cnv_discovery_result_schema_version": 1,
  "cnv_disposition_policy": "cnv-dispositions-v1",
  "deep_action_policy": "deep-action-policy-v1",
  "deep_next_move_policy": "deep-policy-v2",
  "deep_question_set": "deep-v1",
  "dossier_schema_version": 3,
  "evidence_maturity_policy": "evidence-maturity-v1",
  "evidence_producing_action_ids": [
    "OCCURRENCE_DETAIL_EVIDENCE_V1"
  ],
  "evidence_projection_version": "jev-evidence-projection-v2",
  "evidence_state_schema_version": 4,
  "execution_ownership_values": "SYSTEM_AUTONOMOUS,RESEARCHER_RUN,VALIDATION_RUN",
  "expression_aliquot_identity": "NOT_API_DERIVABLE",
  "expression_discovery_result_schema_version": 1,
  "expression_disposition_policy": "expression-dispositions-v2",
  "final_candidate_result_schema_version": 1,
  "functional_source_decision": "DEFER",
  "functional_sources_record": "1",
  "gdc_budget_policy": "gdc-adaptive-v1",
  "gdc_data_model_reference": "gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1",
  "gdc_initial_pages_per_query": 48,
  "gdc_initial_requests": 150,
  "gdc_max_pages_per_query": 10000,
  "gdc_max_requests": 10000,
  "gdc_run_download_bytes": 805306368,
  "gdc_shard_download_bytes": 536870912,
  "hypothesis_policy": "hypothesis-policy-v1",
  "hypothesis_projection_version": "jev-hypothesis-projection-v2",
  "hypothesis_question_set": "hypothesis-v2",
  "jev_context_guard": "jev-context-bytes-v1",
  "luad_campaign_readiness": "EXPERIMENTAL",
  "mutation_composition_method": "MUTATION_CANONICAL_COMPOSITION_V1 v1",
  "mutation_discovery_result_schema_version": 1,
  "mutation_inference_decision": "DEFER_WITH_JUSTIFICATION v1",
  "mutation_reduction_method": "MUTATION_AFFECTED_CASE_COUNT_DESC_V1 v3",
  "no_jev_baseline_version": "no-jev-baseline-v1",
  "open_file_admission_version": "1",
  "package_version": "0.2.0",
  "pathway_membership_method": "REACTOME_TOP_LEVEL_ENSEMBL_V1 v1",
  "pre_wide_selection_policy": "pre-wide-policy-v1",
  "presentation_payload_schema_version": 4,
  "program_loop_version": "program-loop-v2",
  "registered_action_ids": [
    "CHECK_EVIDENCE_INTEGRITY_V1",
    "CHECK_REVISION_FAITHFULNESS_V1",
    "OCCURRENCE_DETAIL_EVIDENCE_V1",
    "SUMMARIZE_CNV_CATEGORIES_V1",
    "SUMMARIZE_EXPRESSION_TAIL_V1"
  ],
  "release_comparison_policy": "release-comparison-v1",
  "release_monitor_version": "release-monitor-v1",
  "research_spec_schema_version": 8,
  "run_event_schema_version": 1,
  "sqlite_schema_version": 7,
  "state_projection_version": "jev-state-projection-v4",
  "statistical_state_schema_version": 5,
  "systematic_universe_method": "GENE_ID_ASC_INDEXED_COMPLETE_V1",
  "typesafe_decision_record": "1",
  "wide_admission_policy": "wide-policy-v2",
  "wide_baseline_policy": "baseline-wide-v2",
  "wide_question_set": "wide-v3"
}
```
<!-- repository-facts:end -->
