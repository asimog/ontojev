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
    WIDE_QUESTIONS,
    applicability_map,
    question_set_hash,
)
from tests.science.test_methods import GENE, _build, _frame


def _state(**kwargs) -> dict:
    return _build([_frame("P1"), _frame("P2")], **kwargs)


def test_projection_is_deterministic_and_compact():
    state = _state()
    first = build_projection(state)
    second = build_projection(state)
    assert projection_hash(first) == projection_hash(second)
    assert first["projection_version"] == PROJECTION_VERSION
    assert first["entity"]["symbol"] == "TP53"
    assert first["entity"]["cancer_census"] is True
    assert first["scope"]["expression_unit"] == "log2(UQFPKM+1)"
    assert len(first["project_observations"]) == 2
    assert first["cross_project"]["coverage_imbalance"] is False
    assert first["eligible_followups"] == []
    assert len(str(first)) < PROJECTION_BYTE_CAP


def test_projection_contains_no_raw_or_operational_fields():
    state = _state()
    projection = build_projection(state)
    serialized = str(projection)
    for forbidden in ("artifact_id", "retrieved_at", "state_id", "request_hash", "_score",
                      "provider_discovery_rank", "response_sha256"):
        assert forbidden not in serialized
    observation = projection["project_observations"][0]
    assert set(observation) == {
        "project_id", "cases_examined", "cases_with_ssm", "cases_with_expression",
        "affected_cases", "expression_local", "expression_provider",
    }


def test_projection_preserves_missingness_and_limitations():
    state = _build([_frame("P1", missing_expression_cells=7), _frame("P2")],
                   counts={"P1": {GENE.gene_id: 4}})
    projection = build_projection(state)
    p2 = next(item for item in projection["project_observations"] if item["project_id"] == "P2")
    assert p2["affected_cases"] is None, "not observed must stay null, never zero"
    assert any("7 of 60" in entry for entry in projection["missingness"])
    assert any("no matched denominator" in limitation for limitation in projection["limitations"])
    assert any("NOT_EXAMINED" in limitation for limitation in projection["limitations"])


def test_projection_byte_cap_fails_closed(monkeypatch):
    state = _state()
    monkeypatch.setattr("cancerjev.jev.projection.PROJECTION_BYTE_CAP", 10)
    with pytest.raises(ProjectionError) as exc:
        build_projection(state)
    assert exc.value.code == "PROJECTION_TOO_LARGE"


def test_included_field_contract_is_declared():
    assert "project_observations[].affected_cases" in INCLUDED_FIELDS
    assert "missingness[]" in INCLUDED_FIELDS
    assert "eligible_followups[]" in INCLUDED_FIELDS


def test_applicability_rules_follow_the_evidence():
    projection = build_projection(_state())
    rules = applicability_map(projection)
    assert rules["warrants_deeper_investigation"]["applicable"] is True
    assert rules["mutation_project_exception"]["applicable"] is False, "only two projects observed"
    assert rules["expression_project_exception"]["applicable"] is False
    assert rules["coverage_explains_apparent_difference"]["applicable"] is False
    assert rules["likely_fragile"]["applicable"] is True

    three = build_projection(_build([_frame("P1"), _frame("P2"), _frame("P3")]))
    rules = applicability_map(three)
    assert rules["mutation_project_exception"]["applicable"] is True
    assert rules["expression_project_exception"]["applicable"] is True

    imbalanced = build_projection(_build([_frame("P1", missing_expression_cells=25), _frame("P2")]))
    assert applicability_map(imbalanced)["coverage_explains_apparent_difference"]["applicable"] is True


def test_question_set_hash_changes_with_wording():
    baseline = question_set_hash()
    assert len(baseline) == 64
    from cancerjev.jev.questions import QuestionDefinition

    altered = tuple(
        QuestionDefinition(**{**definition.__dict__, "instructions": definition.instructions + " "})
        for definition in WIDE_QUESTIONS
    )
    assert question_set_hash(altered) != baseline


def test_every_question_has_full_semantics():
    for definition in WIDE_QUESTIONS:
        assert definition.instructions and len(definition.instructions) > 80
        assert definition.criteria
        assert definition.version >= 1
        assert definition.primitive in {"NOUL", "CHOICE", "SCORE"}
