"""Focused regression tests for the TCGA-LUAD Phase 2 scientific foundation.

These tests pin the new single-cohort contract: explicit populations, preserved
expression missingness, non-negative mutation semantics, separated acquisition vs
scientific completeness, explicit unverified comparability, and scientific
identity that ignores discovery rank/score.
"""

from __future__ import annotations

from dataclasses import replace

from cancerjev.domain.identity import statistical_state_identity_payload
from cancerjev.gdc.parsers import (
    DiscoveryHit,
    GeneCaseCounts,
    ProjectCoverage,
)
from cancerjev.science.methods import (
    COMPARABILITY_STATUSES,
    MUTATION_ABSENCE_SEMANTICS,
    build_statistical_state,
)
from tests.science.test_methods import GENE, _frame, _source

LUAD = "TCGA-LUAD"


def _state(frames, *, counts=None, coverage=None, counts_complete=True, coverage_complete=True,
           scope_meta=None, discovery_meta=None):
    counts = counts if counts is not None else {frame.project_id: {GENE.gene_id: 10} for frame in frames}
    coverage = coverage if coverage is not None else {frame.project_id: 60 for frame in frames}
    return build_statistical_state(
        run_id="run", state_id="state", created_at="2026-09-22T00:00:00Z", gene=GENE, frames=frames,
        counts=GeneCaseCounts(projects=counts, hits_total=100, complete=counts_complete,
                              partial_reasons=[] if counts_complete else ["timed_out"], warnings=[]),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=coverage_complete,
                                 partial_reasons=[] if coverage_complete else ["timed_out"], warnings=[]),
        sources=[_source("artifact", "2026-09-22T00:00:00Z")], warnings=[],
        scope_meta=scope_meta or {"gdc_release": "Data Release 46.0", "domain": "lung cancer",
                                  "cohort": LUAD, "examined_case_frame": "ALL_CASES_SINGLE_PAGE"},
        discovery_meta=discovery_meta or {"examined_genes_ref": "ref", "examined_genes_hash": "hash",
                                          "examined_genes_n": 1, "rank_in_lane": 1},
    )


def _frame_with_missing_case_columns(project_id: str, *, cases: int = 50, returned: int = 48):
    frame = _frame(project_id, cases=cases)
    case_ids = [case.case_id for case in frame.cases]
    values = replace(
        frame.expression_values,
        values={GENE.gene_id: {case_id: 5.0 for case_id in case_ids[:returned]}},
        missing_case_ids=case_ids[returned:],
    )
    return replace(frame, expression_values=values)


def _project_expression(state: dict, project_id: str) -> dict:
    return next(row for row in state["expression"]["project_results"] if row["project_id"] == project_id)


def test_missing_case_columns_stay_visible_when_returned_cells_are_valid():
    frame = _frame_with_missing_case_columns(LUAD, cases=50, returned=48)
    state = _state([frame])
    local = _project_expression(state, LUAD)["local"]
    assert local["n_finite"]["value"] == 48, "all 48 returned cells are valid"
    assert local["n_returned"]["value"] == 48
    assert local["n_missing_case_columns"]["value"] == 2
    assert local["n_missing"]["value"] == 2, "missing must not collapse to zero when returned cells are valid"
    assert local["missing_case_ids"] == frame.expression_values.missing_case_ids
    assert _project_expression(state, LUAD)["availability"] == "PARTIAL"


def test_population_contract_separates_examined_assay_returned_valid_missing():
    frame = _frame_with_missing_case_columns(LUAD, cases=50, returned=48)
    state = _state([frame])
    population = state["populations"][0]
    assert population["examined_n"] == 50
    assert "selected_n" not in population and "observed_n" not in population
    coverage = _project_expression(state, LUAD)["coverage"]
    assert coverage["examined_cases"]["value"] == 50
    assert coverage["assay_available_cases"]["value"] == 50
    assert coverage["returned_case_columns"]["value"] == 48
    assert coverage["valid_measurements"]["value"] == 48
    assert coverage["missing_measurements"]["value"] == 2
    assert coverage["missing_measurements"]["value"] != coverage["returned_case_columns"]["value"]


def test_absent_mutation_bucket_is_not_zero_wildtype_or_negative():
    state = _state([_frame(LUAD)], counts={LUAD: {"ENSG-OTHER": 3}})
    result = state["mutation"]["project_results"][0]
    assert result["affected_case_count"]["value"] is None
    assert result["affected_case_count"]["availability"] == "NOT_OBSERVED"
    assert result["affected_case_count"]["reason_code"] == "GENE_BUCKET_ABSENT"
    assert state["cross_project"]["affected_case_total"]["availability"] == "NOT_OBSERVED"
    assert state["mutation"]["absence_semantics"] == MUTATION_ABSENCE_SEMANTICS
    assert "not wildtype" in state["mutation"]["absence_semantics"]
    assert "not a callable negative" in state["mutation"]["absence_semantics"]
    assert not any(
        row["affected_case_count"]["value"] == 0
        and row["affected_case_count"]["availability"] == "OBSERVED"
        for row in state["mutation"]["project_results"]
    )


def test_acquisition_completeness_is_distinct_from_scientific_sufficiency():
    sufficient = _state([_frame(LUAD)])
    assert sufficient["quality"]["acquisition_completeness"] == "COMPLETE"
    assert sufficient["quality"]["scientific_sufficiency"] == "SUFFICIENT"

    missing_columns = _state([_frame_with_missing_case_columns(LUAD, cases=50, returned=48)])
    assert missing_columns["quality"]["acquisition_completeness"] == "COMPLETE"
    assert missing_columns["quality"]["scientific_sufficiency"] == "PARTIAL"

    partial_acquisition = _state([_frame(LUAD)], counts_complete=False)
    assert partial_acquisition["quality"]["acquisition_completeness"] == "PARTIAL"
    assert partial_acquisition["quality"]["scientific_sufficiency"] == "PARTIAL"
    assert "acquisition" in partial_acquisition["quality"]["scientific_sufficiency_definition"].lower()


def test_comparability_is_explicit_and_never_fabricated():
    state = _state([_frame(LUAD)])
    comparability = state["scope"]["comparability"]
    assert comparability["within_cohort"]["status"] == "UNVERIFIED"
    assert comparability["cross_project"]["status"] == "NOT_APPLICABLE"
    assert set(comparability["statuses"]) == set(COMPARABILITY_STATUSES)
    used = {comparability["within_cohort"]["status"], comparability["cross_project"]["status"]}
    assert "VERIFIED" not in used
    assert "comparability_groups" not in state["scope"]
    assert "noncomparable_groups" not in state["cross_project"]
    assert state["cross_project"]["comparability_status"] == "NOT_APPLICABLE"


def test_discovery_rank_and_score_do_not_change_scientific_identity():
    base = _frame(LUAD)
    reranked = replace(
        base,
        discovery_hits={GENE.gene_id: DiscoveryHit(gene_id=GENE.gene_id, symbol="TP53", rank=7, score=999.0)},
    )
    first = _state([base], discovery_meta={"examined_genes_ref": "ref", "examined_genes_hash": "hash",
                                           "examined_genes_n": 1, "rank_in_lane": 1})
    second = _state([reranked], discovery_meta={"examined_genes_ref": "ref", "examined_genes_hash": "hash",
                                                "examined_genes_n": 1, "rank_in_lane": 9})
    assert first["state_hash"] == second["state_hash"]
    assert first["mutation"]["project_results"][0]["provider_discovery_rank"]["rank"] == 1
    assert second["mutation"]["project_results"][0]["provider_discovery_rank"]["rank"] == 7
    payload = statistical_state_identity_payload(first)
    assert "discovery" not in payload["generation"]
    assert "rank_in_lane" not in payload["generation"]
    assert all("provider_discovery_rank" not in row for row in payload["mutation"]["project_results"])


def test_luad_only_scope_is_recorded_without_pooling():
    state = _state([_frame(LUAD)])
    assert state["scope"]["domain"] == "lung cancer"
    assert state["scope"]["cohort"] == LUAD
    assert state["scope"]["projects"] == [LUAD]
    assert "TCGA-LUSC" not in state["scope"]["projects"]
