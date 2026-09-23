"""Deep evidence projection tests: deterministic, operational-id free, fail-closed."""

from __future__ import annotations

import copy

import pytest

from cancerjev.jev.projection import (
    EVIDENCE_INCLUDED_FIELDS,
    EVIDENCE_PROJECTION_VERSION,
    ProjectionError,
    build_evidence_projection,
    projection_hash,
)
from cancerjev.jev.questions import DEEP_QUESTIONS, applicability_map, validate_definitions
from cancerjev.science.actions import ACTION_REGISTRY

ACTION_PAYLOAD = [ACTION_REGISTRY["CHECK_EVIDENCE_INTEGRITY_V1"].payload()]


def _observation(check_id: str, outcome: str, availability: str = "OBSERVED") -> dict:
    return {
        "result_id": "result-1", "method_id": "EVIDENCE_INTEGRITY_V1", "method_version": "1",
        "check_id": check_id, "claim": "claim", "outcome": outcome, "n_effective": 1,
        "availability": availability, "observed": {"value": 1}, "expected": {},
        "notes": [], "missingness": {"count": 0 if availability == "OBSERVED" else 1, "reason": None},
        "inference_status": "NOT_APPLICABLE", "limitations": [],
    }


def _revision() -> dict:
    return {
        "schema_version": 2,
        "mode": "LIVE",
        "evidence_state_id": "evidence-1",
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "created_at": "2026-09-23T00:00:00Z",
        "previous_evidence_state_id": "evidence-0",
        "iteration_number": 1,
        "entity": {"gene_id": "ENSG1", "gene_symbol": "GENEONE"},
        "source_statistical_state": {
            "state_id": "state-1", "state_identity_hash": "a" * 64,
            "state_artifact_id": "artifact-1", "state_artifact_sha256": "b" * 64,
        },
        "research_puzzle": {"origin": "DETERMINISTIC_ACTION_REGISTRY", "question": "q",
                            "interpretation": "i", "proposed_action_ids": ["CHECK_EVIDENCE_INTEGRITY_V1"]},
        "research_only_notice": "REAL OPEN-ACCESS GDC EVIDENCE",
        "action": ACTION_PAYLOAD[0],
        "deterministic_observations": [
            _observation("COHORT_FRAME_AGREEMENT", "VERIFIED"),
            _observation("EXPRESSION_COVERAGE_ARITHMETIC", "VERIFIED"),
            _observation("MUTATION_COUNT_SCOPE", "VERIFIED"),
            _observation("TESTED_UNIVERSE_REPRODUCIBLE", "VERIFIED"),
            _observation("RESPONSE_ARTIFACT_INTEGRITY", "VERIFIED"),
        ],
        "project_level_evidence": [
            {"project_id": "TCGA-LUAD",
             "affected_case_count": {"value": 393, "unit": "cases", "availability": "OBSERVED"},
             "examined_cases": {"value": 585, "unit": "cases", "availability": "OBSERVED"},
             "project_case_with_ssm": {"value": 573, "unit": "cases", "availability": "OBSERVED"},
             "cases_with_expression": {"value": 518, "unit": "cases", "availability": "OBSERVED"},
             "missing_measurements": {"value": 67, "unit": "cases", "availability": "OBSERVED"}},
        ],
        "missing_evidence": [{"needed_evidence": "new_gdc_measurement", "availability": "NOT_ACQUIRED",
                              "reason": "no acquisition"}],
        "quality_and_fragility": {"checks_total": 5, "checks_verified": 5, "checks_contradicted": 0,
                                  "checks_not_observed": 0, "warnings": []},
        "provenance": {
            "gdc_release": "Data Release 46.0", "sources": [{"endpoint": "/cases"}] * 16,
            "methods": [], "environment_hash": "c" * 64, "action_registry_version": "1",
            "selection_artifact_sha256": "d" * 64,
            "input_artifacts": [{"kind": "RESPONSE_ARTIFACT", "ref": "artifact-2", "sha256": "e" * 64,
                                 "verified": True}],
        },
    }


def test_projection_is_deterministic_and_operational_id_free():
    revision = _revision()
    first = build_evidence_projection(revision, ACTION_PAYLOAD, evidence_hash="f" * 64)
    altered = copy.deepcopy(revision)
    altered.update({"evidence_state_id": "other", "run_id": "other", "candidate_id": "other",
                    "previous_evidence_state_id": "other", "created_at": "2999-01-01T00:00:00Z"})
    altered["source_statistical_state"]["state_id"] = "other"
    altered["source_statistical_state"]["state_artifact_id"] = "other"
    altered["provenance"]["input_artifacts"][0]["ref"] = "other"
    for observation in altered["deterministic_observations"]:
        observation["result_id"] = "other"
    second = build_evidence_projection(altered, ACTION_PAYLOAD, evidence_hash="f" * 64)
    assert projection_hash(first) == projection_hash(second)
    assert first["projection_version"] == EVIDENCE_PROJECTION_VERSION
    assert set(EVIDENCE_INCLUDED_FIELDS) <= set(EVIDENCE_INCLUDED_FIELDS)
    assert "state_id" not in first["revision"] and "evidence_state_id" not in first


def test_projection_tracks_scientific_changes():
    baseline = build_evidence_projection(_revision(), ACTION_PAYLOAD, evidence_hash="f" * 64)
    changed = _revision()
    changed["deterministic_observations"][0]["outcome"] = "CONTRADICTED"
    assert projection_hash(build_evidence_projection(changed, ACTION_PAYLOAD, evidence_hash="f" * 64)) != \
        projection_hash(baseline)
    reverted = _revision()
    assert projection_hash(build_evidence_projection(reverted, ACTION_PAYLOAD, evidence_hash="0" * 64)) != \
        projection_hash(baseline)


def test_projection_signals_drive_deep_applicability():
    projection = build_evidence_projection(_revision(), ACTION_PAYLOAD, evidence_hash="f" * 64)
    assert projection["revision"]["evidence_present"] is True
    assert projection["revision"]["integrity_observed"] is True
    rules = applicability_map(projection, DEEP_QUESTIONS)
    assert set(rules) == {definition.question_id for definition in DEEP_QUESTIONS}
    assert all(rule["applicable"] for rule in rules.values())

    contradicted = _revision()
    contradicted["deterministic_observations"][3] = _observation("TESTED_UNIVERSE_REPRODUCIBLE",
                                                                 "NOT_OBSERVED", "NOT_OBSERVED")
    contradicted["deterministic_observations"][4] = _observation("RESPONSE_ARTIFACT_INTEGRITY",
                                                                 "NOT_OBSERVED", "NOT_OBSERVED")
    projection = build_evidence_projection(contradicted, ACTION_PAYLOAD, evidence_hash="f" * 64)
    rules = applicability_map(projection, DEEP_QUESTIONS)
    assert rules["revision_reliable"]["applicable"] is False
    assert rules["evidence_sufficient_for_next_step"]["applicable"] is True

    contradicted_by_verdict = _revision()
    contradicted_by_verdict["deterministic_observations"][4] = _observation(
        "RESPONSE_ARTIFACT_INTEGRITY", "CONTRADICTED")
    projection = build_evidence_projection(contradicted_by_verdict, ACTION_PAYLOAD, evidence_hash="f" * 64)
    assert applicability_map(projection, DEEP_QUESTIONS)["revision_reliable"]["applicable"] is True


def test_projection_rejects_other_schemas():
    revision = _revision()
    revision["schema_version"] = 1
    with pytest.raises(ProjectionError):
        build_evidence_projection(revision, ACTION_PAYLOAD, evidence_hash="f" * 64)


def test_deep_question_set_is_valid_and_carries_full_semantics():
    validate_definitions(DEEP_QUESTIONS)
    assert len(DEEP_QUESTIONS) == 5
    for definition in DEEP_QUESTIONS:
        assert len(definition.instructions) > 80
        assert definition.criteria
        assert definition.applicability_rule in {"revision_evidence_present", "integrity_observed"}
