from dataclasses import FrozenInstanceError, replace
from itertools import product

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.gdc.parsers import (
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    ProjectCoverage,
)
from cancerjev.jev.projection import build_projection
from cancerjev.research.acquisition import _merge_expression_availability, _merge_expression_values
from cancerjev.science.expression import expression_log2_summary, expression_observation
from cancerjev.science.mutation import mutation_observation
from tests.science.test_methods import GENE, _build, _frame


def test_unacquired_expression_availability_is_not_zero():
    frame = replace(_frame("P1"), expression_coverage=None, expression_values=None, provider_selection=None)
    state = _build([frame])
    count = state["expression"]["coverage"]["cases_with_expression"]
    assert count["value"] is None
    assert count["availability"] == "NOT_OBSERVED"
    assert state["mutation"]["project_results"][0]["affected_case_count"]["availability"] == "OBSERVED"


def test_mutation_missing_bucket_and_explicit_zero_remain_distinct():
    coverage = ProjectCoverage({"P1": 10}, True, [], [])
    observed = mutation_observation("P1", GENE.gene_id, GeneCaseCounts({"P1": {GENE.gene_id: 0}}, 0, True, [], []), coverage)
    absent = mutation_observation("P1", GENE.gene_id, GeneCaseCounts({"P1": {}}, 0, True, [], []), coverage)
    assert observed.affected_cases == 0 and observed.availability == "OBSERVED"
    assert absent.affected_cases is None and absent.reason == "GENE_BUCKET_ABSENT"


def test_expression_is_independent_of_mutation_acquisition():
    frame = _frame("P1")
    result = expression_observation(project_id="P1", gene_id=GENE.gene_id,
                                    case_ids=tuple(c.case_id for c in frame.cases),
                                    coverage=frame.expression_coverage, values=frame.expression_values,
                                    provider=frame.provider_selection)
    assert result.local.median is not None
    assert result.provider is not None


def test_expression_row_permutation_preserves_local_arithmetic():
    row = {"a": 4.0, "b": 16.0, "c": None, "d": 8.0}
    assert expression_log2_summary(row) == expression_log2_summary(dict(reversed(list(row.items()))))


@pytest.mark.parametrize("missing", ["values", "provider", "coverage"])
def test_lane_missingness_is_explicit(missing):
    frame = _frame("P1")
    result = expression_observation(project_id="P1", gene_id=GENE.gene_id,
                                    case_ids=tuple(c.case_id for c in frame.cases),
                                    coverage=None if missing == "coverage" else frame.expression_coverage,
                                    values=None if missing == "values" else frame.expression_values,
                                    provider=None if missing == "provider" else frame.provider_selection)
    if missing == "values":
        assert result.local is None and result.local_availability == "NOT_ACQUIRED"
    elif missing == "coverage":
        assert result.cases_with_expression is None
    else:
        assert result.provider is None


@pytest.mark.parametrize("mutation,values,provider", list(product([False, True], repeat=3)))
def test_typed_summary_matches_legacy_projection_for_independent_lanes(mutation, values, provider):
    frame = _frame("TCGA-LUAD")
    frame = replace(frame, expression_values=frame.expression_values if values else None,
                    provider_selection=frame.provider_selection if provider else None)
    state = _build([frame], counts={frame.project_id: {GENE.gene_id: 10} if mutation else {}}, typed=True)
    assert canonical_json(build_projection(state.summary)) == canonical_json(build_projection(state.boundary_representation()))
    assert state.summary.scientific_hash == state.boundary_representation()["state_hash"]


def test_computed_summary_and_boundary_copy_do_not_share_mutable_state():
    state = _build([_frame("TCGA-LUAD")], typed=True)
    original = state.serialized
    copy = state.boundary_representation()
    copy["mutation"]["project_results"][0]["affected_case_count"]["value"] = 999
    assert state.summary.projects[0].affected_cases == 10
    assert state.serialized == original
    with pytest.raises(FrozenInstanceError):
        state.summary.projects[0].affected_cases = 999


def test_expression_batch_permutation_preserves_merged_values_and_local_result():
    gene = GENE.gene_id
    parts = [(["a", "b"], ExpressionValues({gene: {"a": 4., "b": None}}, [], [], 0, [])),
             (["c", "d"], ExpressionValues({gene: {"c": 8.}}, ["d"], [], 0, []))]
    first = _merge_expression_values(["a", "b", "c", "d"], [gene], parts)
    second = _merge_expression_values(["a", "b", "c", "d"], [gene], list(reversed(parts)))
    assert first == second
    assert expression_log2_summary(first.values[gene], missing_case_columns=1) == expression_log2_summary(second.values[gene], missing_case_columns=1)
    availability = [(["a"], ExpressionAvailability({"a": True}, {gene: True}, 1, 0, [], [], [])),
                    (["b"], ExpressionAvailability({"b": False}, {gene: False}, 0, 1, [], [], []))]
    assert _merge_expression_availability(["a", "b"], [gene], availability) == _merge_expression_availability(["a", "b"], [gene], list(reversed(availability)))


def test_reordered_trusted_rows_preserve_identity_but_changed_source_hash_does_not():
    from tests.science.test_methods import _source

    frame = _frame("TCGA-LUAD")
    values = frame.expression_values
    reordered = replace(frame, cases=list(reversed(frame.cases)), expression_values=replace(
        values, values={gene: dict(reversed(list(row.items()))) for gene, row in values.values.items()}))
    first = _build([frame], typed=True)
    second = _build([reordered], typed=True)
    assert first.summary == second.summary
    assert first.serialized == second.serialized
    source = _source("artifact", "2026-09-22T00:00:00Z")
    source["response_sha256"] = "b" * 64
    changed = _build([frame], sources=[source], typed=True)
    assert changed.summary.projects == first.summary.projects
    assert changed.summary.scientific_hash != first.summary.scientific_hash
