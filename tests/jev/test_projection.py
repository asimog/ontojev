from __future__ import annotations

import pytest

from cancerjev.jev.projection import (
    INCLUDED_FIELDS,
    PROJECTION_BYTE_CAP,
    PROJECTION_VERSION,
    ProjectionError,
    build_projection,
    projection_hash,
)
from cancerjev.jev.questions import (
    WIDE_QUESTION_SET_VERSION,
    WIDE_QUESTIONS,
    applicability_map,
    question_set_hash,
    wide_question_set_hash,
)
from tests.science.test_methods import GENE, _build, _frame


def _state(**kwargs) -> dict:
    return _build([_frame("P1")], **kwargs)


def test_projection_is_deterministic_and_compact():
    state = _state()
    first = build_projection(state)
    second = build_projection(state)
    assert projection_hash(first) == projection_hash(second)
    assert first["projection_version"] == PROJECTION_VERSION
    assert first["entity"]["symbol"] == "TP53"
    assert first["entity"]["cancer_census"] is True
    assert first["scope"]["expression_unit"] == "log2(UQFPKM+1)"
    assert first["cohort"]["project_id"] == "P1"
    assert first["cohort"]["affected_cases"] == 10
    assert first["cohort"]["examined_cases"] == 60
    assert first["cohort"]["mutation_observed"] is True
    assert first["cohort"]["expression_observed"] is True
    assert first["cohort"]["coverage_imbalance"] is False
    assert first["eligible_followups"] == []
    assert len(str(first)) < PROJECTION_BYTE_CAP


def test_projection_contains_no_raw_or_operational_fields():
    state = _state()
    projection = build_projection(state)
    serialized = str(projection)
    for forbidden in ("artifact_id", "retrieved_at", "state_id", "request_hash", "_score",
                      "provider_discovery_rank", "response_sha256"):
        assert forbidden not in serialized
    cohort = projection["cohort"]
    assert set(cohort) == {
        "project_id", "examined_cases", "affected_cases", "mutation_observed",
        "mutation_coverage_complete", "ssm_coverage_cases", "expression_observed",
        "expression_median", "expression_sample_sd", "expression_n_finite", "expression_n_missing",
        "expression_provider_median", "expression_provider_stddev", "coverage_imbalance",
        "completeness", "scientific_sufficiency",
    }


def test_projection_preserves_missingness_and_limitations():
    state = _build([_frame("P1", missing_expression_cells=7)], counts={"P1": {GENE.gene_id: 4}})
    projection = build_projection(state)
    assert projection["cohort"]["affected_cases"] == 4
    assert projection["cohort"]["expression_n_missing"] == 7
    assert any("7 of 60" in entry for entry in projection["missingness"])
    assert any("no matched denominator" in limitation for limitation in projection["limitations"])


def test_projection_rejects_multiple_projects():
    with pytest.raises(ProjectionError) as exc:
        build_projection(_build([_frame("P1"), _frame("P2")]))
    assert exc.value.code == "MULTI_COHORT_STATE"


def test_projection_byte_cap_fails_closed(monkeypatch):
    state = _state()
    monkeypatch.setattr("cancerjev.jev.projection.PROJECTION_BYTE_CAP", 10)
    with pytest.raises(ProjectionError) as exc:
        build_projection(state)
    assert exc.value.code == "PROJECTION_TOO_LARGE"


def test_included_field_contract_is_declared():
    assert "cohort.affected_cases" in INCLUDED_FIELDS
    assert "missingness[]" in INCLUDED_FIELDS
    assert "eligible_followups[]" in INCLUDED_FIELDS


def test_applicability_rules_follow_the_evidence():
    projection = build_projection(_state())
    rules = applicability_map(projection)
    assert rules["warrants_deeper_investigation"]["applicable"] is True
    assert rules["mutation_evidence_coherent"]["applicable"] is True
    assert rules["expression_evidence_coherent"]["applicable"] is True
    assert rules["dominant_limitation"]["applicable"] is True

    expression_only = build_projection(_build(
        [_frame("P1")], counts={"P1": {}},
    ))
    assert expression_only["cohort"]["affected_cases"] is None
    assert expression_only["cohort"]["mutation_observed"] is False
    rules = applicability_map(expression_only)
    assert rules["mutation_evidence_coherent"]["applicable"] is False
    assert rules["expression_evidence_coherent"]["applicable"] is True

    mutation_only_state = _build([_frame("P1")])
    mutation_only_state["expression"]["project_results"][0]["local"]["median"]["availability"] = "INSUFFICIENT"
    mutation_only = build_projection(mutation_only_state)
    rules = applicability_map(mutation_only)
    assert rules["mutation_evidence_coherent"]["applicable"] is True
    assert rules["expression_evidence_coherent"]["applicable"] is False


def test_question_set_hash_changes_with_wording():
    baseline = wide_question_set_hash()
    assert len(baseline) == 64
    from cancerjev.jev.questions import QuestionDefinition

    altered = tuple(
        QuestionDefinition(**{**definition.__dict__, "instructions": definition.instructions + " "})
        for definition in WIDE_QUESTIONS
    )
    assert question_set_hash(altered, WIDE_QUESTION_SET_VERSION) != baseline


def test_every_question_has_full_semantics():
    for definition in WIDE_QUESTIONS:
        assert definition.instructions and len(definition.instructions) > 80
        assert definition.criteria
        assert definition.version >= 1
        assert definition.primitive in {"NOUL", "CHOICE", "SCORE"}
