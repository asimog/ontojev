"""Expression workflow-coverage gating: incomplete coverage is never a silent full claim."""

from __future__ import annotations

import pytest

from cancerjev.gdc.parsers import FileFacets
from cancerjev.research.acquisition import (
    LiveRunError,
    _expression_annotation,
    _expression_workflow_coverage,
)


def _facets(*, total: int, access: dict[str, int], workflows: dict[str, int],
            strategies: dict[str, int] | None = None) -> FileFacets:
    return FileFacets(
        total_open_files=total,
        counts={
            "access": access,
            "analysis.workflow_type": workflows,
            "experimental_strategy": strategies or {"RNA-Seq": total},
            "data_type": {"Gene Expression Quantification": total},
        },
        warnings=[],
    )


def test_missing_workflow_type_keeps_coverage_incomplete_and_withholds_annotation():
    facets = _facets(total=10, access={"open": 10},
                     workflows={"STAR - Counts": 7, "_missing": 3})

    workflows, counts, strategies, complete, warnings = _expression_workflow_coverage(
        "TCGA-LUAD", facets)
    assert workflows == ("STAR - Counts",)
    assert counts == (("STAR - Counts", 7),)
    assert complete is False
    assert any("incomplete" in warning for warning in warnings)

    annotation, notes = _expression_annotation("TCGA-LUAD", workflows, strategies, complete)
    assert annotation == {}
    assert any("coverage is incomplete" in note for note in notes)


def test_mixed_named_workflows_get_no_single_annotation_context():
    facets = _facets(total=10, access={"open": 10},
                     workflows={"STAR - Counts": 6, "HTSeq - Counts": 4})

    workflows, counts, strategies, complete, warnings = _expression_workflow_coverage(
        "TCGA-LUAD", facets)
    assert workflows == ("HTSeq - Counts", "STAR - Counts")
    assert complete is True
    assert warnings == ()

    annotation, notes = _expression_annotation("TCGA-LUAD", workflows, strategies, complete)
    assert annotation == {}
    assert any("mixed" in note for note in notes)


def test_non_open_aggregate_bucket_fails_closed():
    facets = _facets(total=10, access={"open": 9, "controlled": 1},
                     workflows={"STAR - Counts": 10})

    with pytest.raises(LiveRunError) as failure:
        _expression_workflow_coverage("TCGA-LUAD", facets)

    assert failure.value.code == "CONTROLLED_RECORD_RETURNED"


def test_missing_strategy_is_recorded_without_blocking_coverage():
    facets = _facets(total=10, access={"open": 10},
                     workflows={"STAR - Counts": 10}, strategies={"RNA-Seq": 8, "_missing": 2})

    _, _, strategies, complete, warnings = _expression_workflow_coverage("TCGA-LUAD", facets)
    assert strategies == ("RNA-Seq",)
    assert complete is True
    assert any("no experimental strategy" in warning for warning in warnings)
