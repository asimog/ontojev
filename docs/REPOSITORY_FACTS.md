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
  "action_registry_version": "3",
  "api_version": "3.0.0",
  "cnv_discovery_result_schema_version": 1,
  "deep_next_move_policy": "deep-policy-v2",
  "deep_question_set": "deep-v1",
  "dossier_schema_version": 3,
  "evidence_projection_version": "jev-evidence-projection-v2",
  "evidence_state_schema_version": 4,
  "expression_discovery_result_schema_version": 1,
  "final_candidate_result_schema_version": 1,
  "gdc_data_model_reference": "gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1",
  "hypothesis_projection_version": "jev-hypothesis-projection-v2",
  "hypothesis_question_set": "hypothesis-v2",
  "mutation_composition_method": "MUTATION_CANONICAL_COMPOSITION_V1 v1",
  "mutation_discovery_result_schema_version": 1,
  "mutation_inference_decision": "DEFER_WITH_JUSTIFICATION v1",
  "mutation_reduction_method": "MUTATION_AFFECTED_CASE_COUNT_DESC_V1 v3",
  "no_jev_baseline_version": "no-jev-baseline-v1",
  "open_file_admission_version": "1",
  "presentation_payload_schema_version": 4,
  "registered_action_ids": [
    "CHECK_EVIDENCE_INTEGRITY_V1",
    "CHECK_REVISION_FAITHFULNESS_V1",
    "SUMMARIZE_CNV_CATEGORIES_V1",
    "SUMMARIZE_EXPRESSION_TAIL_V1"
  ],
  "research_spec_schema_version": 8,
  "run_event_schema_version": 1,
  "sqlite_schema_version": 5,
  "state_projection_version": "jev-state-projection-v4",
  "statistical_state_schema_version": 5,
  "systematic_universe_method": "GENE_ID_ASC_INDEXED_COMPLETE_V1",
  "wide_admission_policy": "wide-policy-v2",
  "wide_baseline_policy": "baseline-wide-v2",
  "wide_question_set": "wide-v3"
}
```
<!-- repository-facts:end -->
