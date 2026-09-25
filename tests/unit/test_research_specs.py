from __future__ import annotations

import json

import pytest

from cancerjev.research import specs as specs_module
from cancerjev.research.specs import (
    IMPLEMENTED_ACTIONS,
    IMPLEMENTED_DEEP_POLICY,
    IMPLEMENTED_WIDE_POLICY,
    LUAD_RESEARCH_V1,
    RESEARCH_SPEC_SCHEMA_VERSION,
    AcquisitionSpec,
    CohortSpec,
    ResearchSpec,
    ScientificLimits,
    research_spec_from_dict,
)


def _acquisition(**overrides) -> AcquisitionSpec:
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


def _spec(**overrides) -> ResearchSpec:
    values = {
        "spec_id": "TEST_RESEARCH_V1",
        "intent": "Bounded test intent.",
        "cohort": CohortSpec(cohort_id="TEST-COHORT", domain="test domain",
                             project_id="TEST-PROJECT"),
        "acquisition": _acquisition(),
        "limits": ScientificLimits(),
        "allowed_actions": ("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
    }
    values.update(overrides)
    return ResearchSpec(**values)


@pytest.mark.parametrize("field,value", [
    ("case_page_size", True),
    ("case_batch_size", 1.5),
    ("max_cohort_cases", "1000"),
    ("discovery_gene_limit", False),
    ("count_gene_limit", "100"),
    ("candidate_gene_limit", None),
    ("expression_file_sample_size", 2.0),
])
def test_acquisition_spec_rejects_non_integer_runtime_values(field, value):
    with pytest.raises(ValueError, match=f"{field} must be an integer"):
        _acquisition(**{field: value})


@pytest.mark.parametrize("overrides,message", [
    ({"case_page_size": 251}, "case_page_size must be 1..250"),
    ({"case_batch_size": 251}, "case_batch_size must be 1..250"),
    ({"max_cohort_cases": 2_501}, "max_cohort_cases must fit within the ten-page query budget"),
    ({"discovery_gene_limit": 21}, "discovery_gene_limit must be 1..20"),
    ({"count_gene_limit": 101}, "count_gene_limit must be 1..100"),
    ({"candidate_gene_limit": 101}, "candidate_gene_limit must be 1..count_gene_limit"),
    ({"expression_file_sample_size": 6}, "expression_file_sample_size must be 1..5"),
    ({"case_page_size": 0}, "case_page_size must be 1..250"),
])
def test_acquisition_spec_rejects_values_above_admitted_endpoint_bounds(overrides, message):
    with pytest.raises(ValueError, match=message):
        _acquisition(**overrides)


def test_luad_spec_round_trips_through_schema_three():
    emitted = LUAD_RESEARCH_V1.as_dict()
    assert emitted["schema_version"] == RESEARCH_SPEC_SCHEMA_VERSION == 3
    assert emitted["kind"] == "RESEARCH_SPEC"
    assert set(emitted) == {
        "schema_version", "kind", "spec_id", "intent", "cohort", "acquisition", "limits",
        "allowed_actions", "wide_policy", "deep_policy",
    }
    payload = json.loads(json.dumps(emitted))
    restored = research_spec_from_dict(payload)
    assert restored == LUAD_RESEARCH_V1
    assert restored.as_dict() == emitted
    assert isinstance(restored.allowed_actions, tuple)


def test_reader_rejects_legacy_unknown_and_extra_fields():
    payload = LUAD_RESEARCH_V1.as_dict()

    for legacy in (
        {**payload, "schema_version": 2},
        {**payload, "schema_version": 4},
        {**payload, "schema_version": 1},
    ):
        with pytest.raises(ValueError, match="unsupported research spec version/kind"):
            research_spec_from_dict(legacy)
    with pytest.raises(ValueError, match="unsupported research spec version/kind"):
        research_spec_from_dict({**payload, "kind": "RESEARCH_SPEC_V2"})
    with pytest.raises(ValueError, match="unexpected/missing fields"):
        research_spec_from_dict({**payload, "gene_universe": []})
    with pytest.raises(ValueError, match="unexpected/missing fields"):
        research_spec_from_dict({**payload, "mutation_lane": {"enabled": True}})
    with pytest.raises(ValueError, match="unexpected/missing fields"):
        research_spec_from_dict({k: v for k, v in payload.items() if k != "wide_policy"})
    with pytest.raises(ValueError, match="unexpected/missing fields"):
        research_spec_from_dict({**payload, "acquisition": {**payload["acquisition"], "cnv": True}})
    with pytest.raises(ValueError, match="unexpected/missing fields"):
        research_spec_from_dict({**payload, "cohort": {**payload["cohort"], "extra": 1}})
    with pytest.raises(ValueError, match="expected JSON object"):
        research_spec_from_dict("not a research spec")


def test_spec_rejects_unsupported_composition():
    with pytest.raises(ValueError, match="action requires a registered implementation"):
        _spec(allowed_actions=("CNV_LANE_V1",))
    with pytest.raises(ValueError, match="at least one allowed action"):
        _spec(allowed_actions=())
    with pytest.raises(ValueError, match="new policy semantics require a versioned task"):
        _spec(wide_policy="wide-v3")
    with pytest.raises(ValueError, match="new policy semantics require a versioned task"):
        _spec(deep_policy="deep-v3")
    with pytest.raises(ValueError, match="unsupported scientific limits"):
        _spec(limits=ScientificLimits(max_survivors=9))
    with pytest.raises(ValueError, match="invalid cohort spec"):
        _spec(cohort={"cohort_id": "TEST-COHORT"})
    with pytest.raises(ValueError, match="invalid acquisition spec"):
        _spec(acquisition={"case_page_size": 1})
    with pytest.raises(ValueError, match="invalid scientific limits"):
        _spec(limits={"max_survivors": 10})


def test_scientific_limits_have_supported_bounds():
    with pytest.raises(ValueError, match="scientific limit outside supported bounds"):
        ScientificLimits(max_survivors=11)
    with pytest.raises(ValueError, match="scientific limit outside supported bounds"):
        ScientificLimits(max_promotions=4)
    with pytest.raises(ValueError, match="scientific limit outside supported bounds"):
        ScientificLimits(max_revisions=3)
    with pytest.raises(ValueError, match="promotion limit exceeds survivors"):
        ScientificLimits(max_survivors=1, max_promotions=2)


def test_spec_requires_identity_and_intent():
    with pytest.raises(ValueError, match="spec_id must be nonblank text"):
        _spec(spec_id="   ")
    with pytest.raises(ValueError, match="research intent must be nonblank text"):
        _spec(intent="  ")


def test_selection_rules_name_the_explicit_cohort_and_bounded_provider_ranking():
    cohort_rule = LUAD_RESEARCH_V1.cohort_selection_rule()
    assert "single explicit cohort" in cohort_rule
    assert "domain=lung cancer" in cohort_rule
    assert "TCGA-LUAD" in cohort_rule
    assert "project_id" in cohort_rule
    assert "no cross-project pooling" in cohort_rule
    assert "no case-count window" in cohort_rule

    gene_rule = LUAD_RESEARCH_V1.gene_selection_rule()
    assert "provider top-mutated ranking" in gene_rule
    assert "TCGA-LUAD" in gene_rule
    assert str(LUAD_RESEARCH_V1.acquisition.discovery_gene_limit) in gene_rule
    assert str(LUAD_RESEARCH_V1.acquisition.candidate_gene_limit) in gene_rule
    assert "_score" in gene_rule
    assert "provider selection metadata" in gene_rule
    assert "never a mutation count" in gene_rule


def test_no_indexed_universe_or_cnv_composition_is_representable():
    for name in ("ResearchSpecV2", "GeneUniverseSpec", "MutationLaneSpec",
                 "ExpressionLaneSpec", "CnvLaneSpec"):
        assert not hasattr(specs_module, name)
    for field in ("gene_universe", "indexed_universe", "mutation_lane", "expression_lane",
                  "cnv_lane", "cnv"):
        assert not hasattr(ResearchSpec, field)
        assert field not in LUAD_RESEARCH_V1.as_dict()
    assert set(LUAD_RESEARCH_V1.allowed_actions) <= IMPLEMENTED_ACTIONS
    assert LUAD_RESEARCH_V1.wide_policy == IMPLEMENTED_WIDE_POLICY
    assert LUAD_RESEARCH_V1.deep_policy == IMPLEMENTED_DEEP_POLICY
    assert "TCGA-LUSC" not in json.dumps(LUAD_RESEARCH_V1.as_dict())


def test_luad_is_the_single_production_spec():
    assert LUAD_RESEARCH_V1.spec_id == "LUAD_RESEARCH_V1"
    assert LUAD_RESEARCH_V1.cohort.cohort_id == "TCGA-LUAD"
    assert LUAD_RESEARCH_V1.cohort.project_id == "TCGA-LUAD"
    assert LUAD_RESEARCH_V1.cohort.domain == "lung cancer"
    assert set(LUAD_RESEARCH_V1.allowed_actions) == set(IMPLEMENTED_ACTIONS)
    assert LUAD_RESEARCH_V1.limits == ScientificLimits()
