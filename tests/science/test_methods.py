from __future__ import annotations

import math

import pytest

from cancerjev.gdc.parsers import (
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    GeneRecord,
    ProjectCoverage,
    ProjectRecord,
    ProviderGene,
    ProviderSelection,
)
from cancerjev.science.methods import (
    METHODS,
    ProjectFrame,
    ScienceError,
    build_statistical_state,
    coverage_imbalance,
    expression_log2_summary,
    metric,
    project_dominance,
)

GENE = GeneRecord(gene_id="ENSG00000141510", symbol="TP53", name="tumor protein p53",
                  biotype="protein_coding", is_cancer_gene_census=True)


def _source(artifact_id: str, retrieved_at: str) -> dict:
    return {
        "request_id": None, "response_artifact_id": artifact_id, "response_sha256": "a" * 64,
        "endpoint": "/cases", "normalized_request_hash": "r" * 64, "retrieved_at": retrieved_at,
        "source_release": "Data Release 46.0", "release_status": "KNOWN", "parser_version": "gdc-parser-v1",
        "json_pointer_or_table_locator": "/cases", "completeness": "COMPLETE",
    }


def _frame(project_id: str, *, cases: int = 60, affected: bool = True, expression: bool = True,
           discovery: bool = True, missing_expression_cells: int = 0) -> ProjectFrame:
    case_records = [CaseRecord(case_id=f"case-{project_id}-{index}", submitter_id=f"S-{index}",
                               project_id=project_id, sample_types=["Primary Tumor"])
                    for index in range(cases)]
    coverage = ExpressionAvailability(
        cases={case.case_id: index < cases - missing_expression_cells for index, case in enumerate(case_records)},
        genes={GENE.gene_id: expression}, with_count=cases, without_count=0,
        missing_cases=[], missing_genes=[], warnings=[],
    ) if expression or missing_expression_cells else None
    values = ExpressionValues(
        values={GENE.gene_id: {case.case_id: (5.0 + index * 0.1 if index < cases - missing_expression_cells else None)
                               for index, case in enumerate(case_records)}},
        missing_case_ids=[], missing_gene_ids=[], nonfinite_values=0, warnings=[],
    ) if expression else None
    provider = ProviderSelection(
        genes={GENE.gene_id: ProviderGene(gene_id=GENE.gene_id, symbol="TP53", median=2.5, stddev=0.3)},
        missing_genes=[], warnings=[],
    ) if expression else None
    hits = {GENE.gene_id: DiscoveryHit(gene_id=GENE.gene_id, symbol="TP53", rank=1, score=100.0)} if discovery else {}
    return ProjectFrame(
        project_id=project_id,
        project_record=ProjectRecord(project_id=project_id, name=project_id, program_name="TCGA",
                                     primary_site=["Breast"], disease_type=["Ductal"],
                                     case_count=cases, file_count=100, data_categories=["Transcriptome Profiling"]),
        cases=case_records, frame_hash=f"frame-{project_id}", expression_coverage=coverage,
        provider_selection=provider, expression_values=values, workflows=["STAR - Counts"],
        strategies=["RNA-Seq"], discovery_hits=hits,
    )


def _build(frames: list[ProjectFrame], *, counts: dict[str, dict[str, int]] | None = None,
           coverage: dict[str, int] | None = None, sources: list[dict] | None = None,
           state_id: str = "state") -> dict:
    counts = counts if counts is not None else {frame.project_id: {GENE.gene_id: 10} for frame in frames}
    coverage = coverage if coverage is not None else {frame.project_id: 60 for frame in frames}
    return build_statistical_state(
        run_id="run", state_id=state_id, created_at="2026-09-22T00:00:00Z", gene=GENE, frames=frames,
        counts=GeneCaseCounts(projects=counts, hits_total=100, complete=True, partial_reasons=[], warnings=[]),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=True, partial_reasons=[], warnings=[]),
        sources=sources or [_source("artifact", "2026-09-22T00:00:00Z")],
        warnings=[], scope_meta={"gdc_release": "Data Release 46.0", "examined_case_frame": "ALL_CASES_SINGLE_PAGE"},
        discovery_meta={"examined_genes_ref": "ref", "examined_genes_hash": "hash", "examined_genes_n": 1,
                        "rank_in_lane": 1},
    )


def test_expression_log2_summary_matches_hand_computation():
    summary = expression_log2_summary({"a": 15.6455, "b": 9.9823})
    expected = sorted([math.log2(15.6455 + 1), math.log2(9.9823 + 1)])
    assert summary.median == pytest.approx(sum(expected) / 2, abs=1e-9)
    assert summary.sample_sd == pytest.approx(0.4243, abs=0.001)
    assert summary.minimum == pytest.approx(expected[0])
    assert summary.maximum == pytest.approx(expected[1])
    assert summary.n_finite == 2 and summary.n_missing == 0
    assert summary.availability == "OBSERVED"


def test_expression_log2_summary_missingness_and_small_n():
    partial = expression_log2_summary({"a": 4.0, "b": None})
    assert partial.n_finite == 1 and partial.n_missing == 1
    assert partial.sample_sd is None
    assert partial.availability == "INSUFFICIENT"
    empty = expression_log2_summary({"a": None})
    assert empty.median is None and empty.availability == "INSUFFICIENT"
    assert empty.n_finite == 0 and empty.n_missing == 1


def test_expression_log2_summary_rejects_negative_uqfpkm():
    with pytest.raises(ScienceError) as exc:
        expression_log2_summary({"a": -1.0})
    assert exc.value.code == "NEGATIVE_EXPRESSION"


def test_project_dominance_requires_two_observed_projects():
    share, availability = project_dominance({"A": 30, "B": 10})
    assert share == pytest.approx(0.75) and availability == "OBSERVED"
    assert project_dominance({"A": 5}) == (None, "NOT_APPLICABLE")
    assert project_dominance({"A": 0, "B": 0}) == (None, "NOT_APPLICABLE")


def test_coverage_imbalance_rules():
    balanced = [
        {"mutation_observed": True, "examined_cases": 100, "cases_with_expression": 80},
        {"mutation_observed": True, "examined_cases": 120, "cases_with_expression": 95},
    ]
    assert coverage_imbalance(balanced) is False
    missing_modality = [balanced[0], {**balanced[1], "mutation_observed": False}]
    assert coverage_imbalance(missing_modality) is True
    uneven = [balanced[0], {**balanced[1], "cases_with_expression": 30}]
    assert coverage_imbalance(uneven) is True
    zero_expression = [balanced[0], {**balanced[1], "cases_with_expression": 0}]
    assert coverage_imbalance(zero_expression) is True


def test_metric_rejects_inconsistent_or_nonfinite_values():
    with pytest.raises(ScienceError):
        metric("x", 5, "cases", availability="NOT_OBSERVED")
    with pytest.raises(ScienceError):
        metric("x", float("nan"), "cases")


def test_state_assembly_is_deterministic_and_input_sensitive():
    frames = [_frame("P1"), _frame("P2")]
    first = _build(frames)
    second = _build(frames)
    assert first["state_hash"] == second["state_hash"]
    changed = _build([_frame("P1"), _frame("P2")],
                     counts={"P1": {GENE.gene_id: 11}, "P2": {GENE.gene_id: 10}})
    assert changed["state_hash"] != first["state_hash"]
    reordered = _build(list(reversed(frames)))
    assert reordered["state_hash"] == first["state_hash"], "project order must not change scientific identity"


def test_state_identity_excludes_operational_source_fields():
    frames = [_frame("P1"), _frame("P2")]
    first = _build(frames, sources=[_source("artifact-a", "2026-09-22T00:00:00Z")])
    second = _build(frames, sources=[_source("artifact-b", "2026-09-23T10:00:00Z")])
    assert first["state_hash"] == second["state_hash"]


def test_absent_bucket_is_not_observed_never_zero():
    state = _build([_frame("P1"), _frame("P2")], counts={"P1": {GENE.gene_id: 4}})
    results = {result["project_id"]: result for result in state["mutation"]["project_results"]}
    assert results["P1"]["affected_case_count"]["value"] == 4
    assert results["P2"]["affected_case_count"]["value"] is None
    assert results["P2"]["affected_case_count"]["availability"] == "NOT_OBSERVED"
    assert state["cross_project"]["affected_case_total"]["value"] == 4
    assert state["cross_project"]["projects_with_mutation_observation"] == 1


def test_provider_ranking_is_quarantined_as_selection_metadata():
    state = _build([_frame("P1"), _frame("P2")])
    for result in state["mutation"]["project_results"]:
        rank = result["provider_discovery_rank"]
        assert rank["note"] == "selection metadata only"
        assert result["affected_case_count"]["unit"] == "cases"


def test_provider_and_local_expression_summaries_are_separate():
    state = _build([_frame("P1"), _frame("P2")])
    for result in state["expression"]["project_results"]:
        assert result["local"]["method_id"] == "EXPRESSION_LOG2_SUMMARY_V1"
        assert result["local"]["median"]["unit"] == "log2(UQFPKM+1)"
        assert result["provider"]["source"] == "GENE_SELECTION"
        assert result["provider"]["estimator_note"] == "INFERRED_POPULATION_SD_UNVERIFIED"
        assert result["provider"]["median"]["value"] == 2.5


def test_missing_expression_cells_are_counted_and_flagged():
    state = _build([_frame("P1", missing_expression_cells=7), _frame("P2")])
    p1 = {result["project_id"]: result for result in state["expression"]["project_results"]}["P1"]
    assert p1["local"]["n_missing"]["value"] == 7
    assert any("7 of 60" in entry for entry in state["quality"]["missingness"])
    assert state["cross_project"]["coverage_imbalance"] is False, "an 11.7% gap is below the declared 0.2 rule"
    uneven = _build([_frame("P1", missing_expression_cells=25), _frame("P2")])
    assert uneven["cross_project"]["coverage_imbalance"] is True


def test_cross_project_direction_is_not_examined():
    state = _build([_frame("P1"), _frame("P2")])
    assert state["cross_project"]["direction"] == "NOT_EXAMINED"


def test_method_registry_declares_required_contract_fields():
    for definition in METHODS.values():
        assert definition.method_id and definition.version and definition.purpose
        assert definition.analysis_unit and definition.population_semantics and definition.duplicate_rule
        assert definition.eligibility and definition.minimum_n and definition.sampling_rule
        assert definition.estimator and definition.missingness_handling
        assert definition.limitations and definition.provenance_requirements
        assert definition.effect_definition is None
        assert definition.null_hypothesis is None
        assert definition.correction_family is None


def test_no_recurrence_fraction_is_stored():
    state = _build([_frame("P1"), _frame("P2")])
    serialized = str(state)
    assert "observed_fraction" not in serialized
    assert "recurrence" not in serialized.lower() or "no recurrence fraction" in serialized.lower()
