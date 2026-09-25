"""Capability derivation and campaign-activation gates on synthetic metadata."""

from __future__ import annotations

import pytest

from cancerjev.domain.capability import (
    CapabilityAvailability,
    Modality,
    ScientificReadiness,
)
from cancerjev.gdc.parsers import FileFacets
from cancerjev.research.campaign import (
    LUAD_CAMPAIGN_V1,
    CampaignActivationError,
    require_autonomous_activation,
    require_capability,
)
from cancerjev.research.capability import CapabilityError, build_cohort_capability


def _facets(*, strategies: dict[str, int] | None = None, workflows: dict[str, int] | None = None,
            data_types: dict[str, int] | None = None) -> FileFacets:
    return FileFacets(
        total_open_files=sum((strategies or {}).values()),
        counts={
            "experimental_strategy": strategies or {},
            "analysis.workflow_type": workflows or {},
            "data_type": data_types or {},
        },
        warnings=[],
    )


def _capability(*, strategies, workflows=None, data_types=None, categories=(), project="TCGA-LUAD"):
    return build_cohort_capability(
        cohort_id=project, project_id=project, release="Data Release TEST",
        release_commit="0" * 40, data_categories=tuple(categories),
        facets=_facets(strategies=strategies, workflows=workflows, data_types=data_types),
        sources=(), warnings=(),
    )


def test_unknown_experimental_strategy_fails_closed():
    with pytest.raises(CapabilityError) as failure:
        _capability(strategies={"WXS": 5, "Frobnication": 1})

    assert failure.value.code == "UNKNOWN_EXPERIMENTAL_STRATEGY"
    assert "Frobnication" in failure.value.detail


def test_required_provider_data_type_gates_availability():
    capability = _capability(
        strategies={"RNA-Seq": 10, "WXS": 5},
        workflows={"STAR - Counts": 10},
        data_types={"Isoform Expression Quantification": 10},
    )

    expression = capability.record(Modality.EXPRESSION_RNASEQ)
    assert expression.source_present is True
    assert expression.availability is CapabilityAvailability.UNAVAILABLE
    assert expression.reason == "REQUIRED_PROVIDER_DATA_NOT_PRESENT"

    mutation = capability.record(Modality.MUTATION_WXS)
    assert mutation.source_present is True
    assert mutation.reason == "REQUIRED_PROVIDER_DATA_NOT_PRESENT"


def test_unmapped_workflow_type_is_recorded_never_silently_dropped():
    capability = _capability(
        strategies={"WXS": 5},
        workflows={"Some Future Aggregation": 5},
        data_types={"Masked Somatic Mutation": 5},
    )

    assert any("Some Future Aggregation" in warning for warning in capability.warnings)
    assert capability.record(Modality.MUTATION_WXS).workflow_types == ()


def test_capability_derivation_reaches_available_for_the_enabled_lanes():
    capability = _capability(
        strategies={"WXS": 5, "RNA-Seq": 5, "Genotyping Array": 5},
        workflows={"Aliquot Ensemble Somatic Variant Merging and Masking": 5,
                   "STAR - Counts": 5, "ASCAT2": 5},
        data_types={"Masked Somatic Mutation": 5, "Gene Expression Quantification": 5,
                    "Gene Level Copy Number": 5},
        categories=("Clinical",),
    )

    require_capability(LUAD_CAMPAIGN_V1, capability)
    assert capability.available_modalities() == (
        Modality.CNV,
        Modality.EXPRESSION_RNASEQ,
        Modality.MUTATION_WXS,
    )


def test_capability_gate_refuses_an_enabled_modality_without_source():
    capability = _capability(
        strategies={"WXS": 5},
        workflows={"Aliquot Ensemble Somatic Variant Merging and Masking": 5},
        data_types={"Masked Somatic Mutation": 5},
    )

    with pytest.raises(CampaignActivationError) as failure:
        require_capability(LUAD_CAMPAIGN_V1, capability)

    assert failure.value.code == "CAPABILITY_UNAVAILABLE"
    assert "CNV" in failure.value.detail


def test_capability_gate_refuses_a_different_project():
    capability = _capability(
        strategies={"WXS": 5, "RNA-Seq": 5, "Genotyping Array": 5},
        workflows={"Aliquot Ensemble Somatic Variant Merging and Masking": 5,
                   "STAR - Counts": 5, "ASCAT2": 5},
        data_types={"Masked Somatic Mutation": 5, "Gene Expression Quantification": 5,
                    "Gene Level Copy Number": 5},
        project="TCGA-LUSC",
    )

    with pytest.raises(CampaignActivationError) as failure:
        require_capability(LUAD_CAMPAIGN_V1, capability)

    assert failure.value.code == "CAPABILITY_PROJECT_MISMATCH"


def test_experimental_profile_is_refused_for_autonomous_activation():
    assert LUAD_CAMPAIGN_V1.readiness is ScientificReadiness.EXPERIMENTAL

    with pytest.raises(CampaignActivationError) as failure:
        require_autonomous_activation(LUAD_CAMPAIGN_V1)

    assert failure.value.code == "PROFILE_NOT_VALIDATED_FOR_AUTONOMOUS_USE"
