"""Wide state projection contract: bounded typed fields, fail-closed identity."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

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
from tests.jev.test_service import GENE, PROJECT, state_record, statistical_state

COHORT_FIELDS = {
    "project_id", "examined_cases", "affected_cases", "mutation_observed",
    "mutation_coverage_complete", "ssm_coverage_cases", "expression_observed",
    "expression_median", "expression_sample_sd", "expression_n_finite", "expression_n_missing",
    "expression_provider_median", "expression_provider_stddev", "coverage_imbalance",
    "completeness", "scientific_sufficiency",
}


def test_projection_is_deterministic_and_compact():
    record = state_record("state-1", statistical_state())
    first = build_projection(record)
    second = build_projection(record)
    assert first == second
    assert projection_hash(first) == projection_hash(second)
    assert first["projection_version"] == PROJECTION_VERSION
    assert first["entity"]["symbol"] == "TP53"
    assert first["entity"]["cancer_census"] is True
    assert first["scope"]["domain"] == "lung cancer"
    assert first["scope"]["projects"] == [PROJECT]
    assert first["scope"]["expression_unit"] == "log2(UQFPKM+1)"
    assert first["cohort"]["project_id"] == PROJECT
    assert first["cohort"]["affected_cases"] == 10
    assert first["cohort"]["examined_cases"] == 60
    assert first["cohort"]["mutation_observed"] is True
    assert first["cohort"]["expression_observed"] is True
    assert first["cohort"]["coverage_imbalance"] is False
    assert first["eligible_followups"] == []
    assert len(str(first)) < PROJECTION_BYTE_CAP


def test_projection_contains_no_raw_or_operational_fields():
    projection = build_projection(state_record("state-1", statistical_state()))
    rendered = str(projection)
    for forbidden in ("artifact_id", "retrieved_at", "state_id", "state_hash", "request_hash",
                      "response_sha256", "_score", "provider_discovery_rank"):
        assert forbidden not in rendered


def test_projection_field_contract_is_exact():
    projection = build_projection(state_record("state-1", statistical_state()))
    assert set(projection) == {
        "projection_version", "entity", "scope", "cohort", "missingness", "limitations",
        "eligible_followups",
    }
    assert set(projection["cohort"]) == COHORT_FIELDS


def test_included_field_contract_is_declared():
    assert "cohort.affected_cases" in INCLUDED_FIELDS
    assert "missingness[]" in INCLUDED_FIELDS
    assert "eligible_followups[]" in INCLUDED_FIELDS


def test_projection_preserves_missingness_and_limitations():
    state = statistical_state(counts={PROJECT: {GENE.gene_id: 4}}, missing_expression_cells=7)
    projection = build_projection(state_record("state-1", state))
    assert projection["cohort"]["affected_cases"] == 4
    assert projection["cohort"]["expression_n_missing"] == 7
    assert any("7 of 60" in entry for entry in projection["missingness"])
    assert any("no matched denominator" in entry for entry in projection["limitations"])


def test_projection_rejects_multiple_projects():
    with pytest.raises(ProjectionError) as exc:
        build_projection(state_record("state-multi", statistical_state(projects=("P1", "P2"))))
    assert exc.value.code == "MULTI_COHORT_STATE"


def test_projection_byte_cap_fails_closed(monkeypatch):
    monkeypatch.setattr("cancerjev.jev.projection.PROJECTION_BYTE_CAP", 10)
    with pytest.raises(ProjectionError) as exc:
        build_projection(state_record("state-1", statistical_state()))
    assert exc.value.code == "PROJECTION_TOO_LARGE"


def test_projection_hash_is_stable_across_operational_ids_and_discovery_metadata():
    state = statistical_state()
    baseline = build_projection(state_record("state-a", state))
    renamed = build_projection(state_record("state-b", state))
    assert projection_hash(baseline) == projection_hash(renamed)
    reranked = statistical_state(discovery=False)
    assert projection_hash(build_projection(state_record("state-c", reranked))) == projection_hash(baseline)
    altered_artifacts = statistical_state(artifacts_by_endpoint={
        "/analysis/top_cases_counts_by_genes": SimpleNamespace(
            sha256="d" * 64, artifact_id="other-artifact"),
    })
    assert projection_hash(build_projection(state_record("state-d", altered_artifacts))) == \
        projection_hash(baseline)


def test_applicability_rules_follow_the_evidence():
    baseline = applicability_map(build_projection(state_record("state-1", statistical_state())),
                                 WIDE_QUESTIONS)
    assert baseline["warrants_deeper_investigation"]["applicable"] is True
    assert baseline["mutation_evidence_coherent"]["applicable"] is True
    assert baseline["expression_evidence_coherent"]["applicable"] is True
    assert baseline["dominant_limitation"]["applicable"] is True

    expression_only_projection = build_projection(
        state_record("state-expression", statistical_state(counts={PROJECT: {}})))
    assert expression_only_projection["cohort"]["affected_cases"] is None
    assert expression_only_projection["cohort"]["mutation_observed"] is False
    expression_only = applicability_map(expression_only_projection, WIDE_QUESTIONS)
    assert expression_only["mutation_evidence_coherent"]["applicable"] is False
    assert expression_only["expression_evidence_coherent"]["applicable"] is True

    mutation_only_projection = build_projection(
        state_record("state-mutation", statistical_state(expression=False)))
    assert mutation_only_projection["cohort"]["expression_observed"] is False
    mutation_only = applicability_map(mutation_only_projection, WIDE_QUESTIONS)
    assert mutation_only["expression_evidence_coherent"]["applicable"] is False
    assert mutation_only["mutation_evidence_coherent"]["applicable"] is True


def test_question_set_hash_changes_with_wording():
    assert WIDE_QUESTION_SET_VERSION == "wide-v3"
    assert len(wide_question_set_hash()) == 64
    altered = tuple(
        replace(definition, instructions=definition.instructions + " ")
        for definition in WIDE_QUESTIONS
    )
    assert question_set_hash(altered, WIDE_QUESTION_SET_VERSION) != wide_question_set_hash()


def test_every_question_has_full_semantics():
    for definition in WIDE_QUESTIONS:
        assert len(definition.instructions) > 80
        assert definition.criteria
        assert definition.applicability_rule
