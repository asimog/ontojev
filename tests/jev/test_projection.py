"""Wide state projection contract: bounded typed fields, fail-closed identity."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from cancerjev.domain.discovery import CNV_RETAIN_REASON
from cancerjev.domain.measurements import ObservedCount
from cancerjev.domain.scientific import CnvProjectFinding
from cancerjev.jev.projection import (
    PROJECTION_BYTE_CAP,
    PROJECTION_VERSION,
    ProjectionError,
    build_projection,
    projection_hash,
)
from cancerjev.jev.questions import WIDE_QUESTIONS, applicability_map
from cancerjev.research.cutover import CUTOVER_UNION_BIAS, UNION_SELECTION_RULE_ID
from cancerjev.science.methods import MUTATION_COUNT_METHOD, MUTATION_DISTINCT_CASE_COUNT_METHOD
from tests.jev.test_service import GENE, PROJECT, state_record, statistical_state

COHORT_FIELDS = {
    "project_id", "examined_cases", "affected_cases", "mutation_observed",
    "mutation_coverage_complete", "ssm_coverage_cases", "expression_observed",
    "expression_median", "expression_sample_sd", "expression_n_finite", "expression_n_missing",
    "expression_provider_median", "expression_provider_stddev", "coverage_imbalance",
    "coverage_imbalance_reason",
    "cnv_observed", "cnv_positive_cases", "cnv_conflicting_cases", "cnv_categories",
    "cnv_callers", "completeness", "scientific_sufficiency",
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
    assert first["cohort"]["coverage_imbalance"] is False, \
        "a flag computed under the declared rule is forwarded, not nulled"
    assert first["cohort"]["coverage_imbalance_reason"] is None, \
        "an assessed summary carries no not-assessed reason"
    assert first["eligible_followups"] == [
        "CHECK_EVIDENCE_INTEGRITY_V1", "OCCURRENCE_DETAIL_EVIDENCE_V1",
        "SUMMARIZE_EXPRESSION_TAIL_V1"]
    assert len(str(first)) < PROJECTION_BYTE_CAP


def test_projection_field_contract_is_exact():
    projection = build_projection(state_record("state-1", statistical_state()))
    assert set(projection) == {
        "projection_version", "entity", "scope", "cohort", "missingness", "limitations",
        "eligible_followups",
    }
    assert set(projection["cohort"]) == COHORT_FIELDS
    rendered = str(projection)
    for forbidden in ("artifact_id", "retrieved_at", "state_id", "state_hash", "request_hash",
                      "response_sha256", "_score", "provider_discovery_rank"):
        assert forbidden not in rendered


def test_projection_preserves_missingness_and_limitations():
    state = statistical_state(counts={PROJECT: {GENE.gene_id: 4}}, missing_expression_cells=7)
    projection = build_projection(state_record("state-1", state))
    assert projection["cohort"]["affected_cases"] == 4
    assert projection["cohort"]["expression_n_missing"] == 7
    assert any("7 of 60" in entry for entry in projection["missingness"])
    assert any("matched denominator" in entry for entry in projection["limitations"])


def test_projection_rejects_multiple_projects():
    with pytest.raises(ProjectionError) as exc:
        build_projection(state_record("state-multi", statistical_state(projects=("P1", "P2"))))
    assert exc.value.code == "MULTI_COHORT_STATE"


def _canonical_shaped_state():
    """Legacy fixture relabelled with the canonical union selection context and V2 method.

    The projection reads limitations from exactly what is relabelled here: the state's own
    selection rule/bias, its mutation method identity, its lane presence, and the
    not-assessed coverage summary the union path writes. The full canonical union path is
    exercised by the integration suites.
    """
    state = statistical_state()
    project = state.projects[0]
    affected = project.mutation.affected_cases
    assert isinstance(affected, ObservedCount)
    mutation = replace(project.mutation,
                       affected_cases=replace(affected, method=MUTATION_DISTINCT_CASE_COUNT_METHOD))
    return replace(
        state,
        projects=(replace(project, mutation=mutation, provider_expression=None),),
        tested_context=replace(state.tested_context, selection_rule=UNION_SELECTION_RULE_ID,
                               selection_bias=CUTOVER_UNION_BIAS),
        cross_project=replace(state.cross_project, coverage_imbalance=False,
                              coverage_imbalance_definition="not applicable to one project"),
    )


def test_projection_limitations_follow_the_states_own_selection_and_method():
    canonical = build_projection(state_record("state-union", _canonical_shaped_state()))
    rendered = " ".join(canonical["limitations"])
    assert canonical["scope"]["selection_bias"] == CUTOVER_UNION_BIAS
    assert CUTOVER_UNION_BIAS in rendered, "the declared union bias must be visible in the limitations"
    assert all(entry in rendered for entry in MUTATION_DISTINCT_CASE_COUNT_METHOD.limitations)
    assert all(entry not in rendered for entry in MUTATION_COUNT_METHOD.limitations
               if "DEPRECATED" in entry), "a V2 measurement must never carry the V1 deprecation"
    assert "provider top-mutated ranking" not in rendered
    assert "provider-defined case counts" not in rendered
    assert "Provider expression median/stddev" not in rendered, \
        "the provider estimator limitation belongs only to states with provider expression data"

    legacy_state = statistical_state()
    legacy = build_projection(state_record("state-legacy", legacy_state))
    legacy_text = " ".join(legacy["limitations"])
    assert legacy_state.tested_context.selection_bias in legacy_text, \
        "a state must declare its own recorded selection bias"
    assert all(entry in legacy_text for entry in MUTATION_COUNT_METHOD.limitations), \
        "the declared V1 limitations must be forwarded verbatim"
    assert "Provider expression median/stddev" in legacy_text, \
        "a state with provider expression data must declare the estimator limitation"


def test_projection_forwards_recorded_coverage_imbalance_and_nulls_only_not_assessed():
    recorded = statistical_state()
    assert recorded.cross_project.coverage_imbalance is False
    assert build_projection(state_record("state-recorded", recorded))["cohort"]["coverage_imbalance"] \
        is False

    zero_expression = statistical_state(missing_expression_cells=60)
    assert zero_expression.cross_project.coverage_imbalance is True, \
        "the declared rule flags a project with zero observed expression values"
    assert build_projection(state_record("state-zero", zero_expression))["cohort"]["coverage_imbalance"] \
        is True

    canonical_state = _canonical_shaped_state()
    assert canonical_state.cross_project.coverage_imbalance_definition == "not applicable to one project"
    canonical = build_projection(state_record("state-union", canonical_state))
    assert canonical["cohort"]["coverage_imbalance"] is None, \
        "a summary that does not apply the declared rule projects NOT_ASSESSED, never false"
    assert canonical["cohort"]["coverage_imbalance_reason"] == "not applicable to one project", \
        "the state's recorded not-assessed reason is projected with the null"


def test_projection_declares_cnv_contextual_only_when_cnv_is_observed():
    state = statistical_state()
    project = state.projects[0]
    cases = tuple(sorted(project.population.frame.examined_ids[:2]))
    finding = CnvProjectFinding("RETAIN", CNV_RETAIN_REASON, None,
                                (("Amplification", cases),), ("ASCAT3",), (), 3)
    observed = replace(state, projects=(replace(project, cnv=finding),))

    projection = build_projection(state_record("state-cnv", observed))
    declarations = [entry for entry in projection["limitations"] if "no admission criterion" in entry]
    assert projection["cohort"]["cnv_observed"] is True
    assert len(declarations) == 1
    assert "no admission criterion or Python policy consumes CNV" in declarations[0]

    absent = build_projection(state_record("state-no-cnv", statistical_state()))
    assert absent["cohort"]["cnv_observed"] is False
    assert all("no admission criterion" not in entry for entry in absent["limitations"])


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
