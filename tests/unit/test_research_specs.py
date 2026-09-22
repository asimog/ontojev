from __future__ import annotations

import pytest

from cancerjev.research.specs import AcquisitionSpec, CohortSpec, ResearchSpec


def _acquisition(**overrides):
    values = {
        "case_page_size": 250,
        "case_batch_size": 250,
        "max_cohort_cases": 1_000,
        "discovery_gene_limit": 20,
        "count_gene_limit": 100,
        "candidate_gene_limit": 10,
        "expression_file_sample_size": 5,
    }
    values.update(overrides)
    return AcquisitionSpec(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_page_size", True),
        ("case_batch_size", 1.5),
        ("max_cohort_cases", "1000"),
        ("discovery_gene_limit", False),
    ],
)
def test_acquisition_spec_rejects_non_integer_runtime_values(field, value):
    with pytest.raises(ValueError, match=f"{field} must be an integer"):
        _acquisition(**{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"case_page_size": 251},
        {"case_batch_size": 251},
        {"max_cohort_cases": 2_501},
        {"discovery_gene_limit": 21},
        {"count_gene_limit": 101},
        {"candidate_gene_limit": 101},
        {"expression_file_sample_size": 6},
    ],
)
def test_acquisition_spec_rejects_values_above_admitted_endpoint_bounds(overrides):
    with pytest.raises(ValueError):
        _acquisition(**overrides)


def test_research_spec_rejects_blank_identity():
    with pytest.raises(ValueError, match="spec_id"):
        ResearchSpec(
            spec_id="   ",
            cohort=CohortSpec(cohort_id="TEST", domain="test", project_id="TEST"),
            acquisition=_acquisition(),
        )
