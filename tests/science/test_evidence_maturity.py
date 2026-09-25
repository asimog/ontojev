"""Deterministic evidence maturity: pure derivation and known-cancer context roles."""

from __future__ import annotations

from dataclasses import replace

from cancerjev.domain.discovery import CNV_RETAIN_REASON, CnvDisposition
from cancerjev.domain.maturity import (
    CANCER_CENSUS_KNOWLEDGE_ROLE,
    EVIDENCE_MATURITY_POLICY_VERSION,
    EvidenceLevel,
    KnowledgeRole,
    derive_evidence_maturity,
)
from cancerjev.domain.scientific import GeneAnnotation
from cancerjev.research.cutover import compose_discovery_states
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.science.test_modality_union import _call, _cnv_result, _lanes


def _states(runtime):
    mutation, expression = _lanes(runtime)
    cases = expression.population.examined_ids[:5]
    cnv = _cnv_result(mutation, (
        _call(mutation.survivor_ids[0], "Amplification", cases,
              disposition=CnvDisposition.RETAIN, reason=CNV_RETAIN_REASON),
    ))
    return compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)


def test_nominated_state_is_a_descriptive_candidate_with_declared_prerequisites(runtime):
    state = _states(runtime)[0]

    maturity = derive_evidence_maturity(state)

    assert state.evidence_level == maturity.level.value
    assert maturity.level is EvidenceLevel.DESCRIPTIVE_CANDIDATE
    assert any("nominated by validated modality" in reason for reason in maturity.reasons)
    assert [level for level, _ in maturity.unattained] == [
        "STATISTICALLY_SUPPORTED", "INTERNALLY_REPLICATED", "EXTERNALLY_REPLICATED",
        "FUNCTIONALLY_SUPPORTED",
    ]
    assert all(reason for _, reason in maturity.unattained)
    assert EVIDENCE_MATURITY_POLICY_VERSION == "evidence-maturity-v1"
    assert CANCER_CENSUS_KNOWLEDGE_ROLE is KnowledgeRole.KNOWN_CANCER_CONTEXT


def test_measured_state_and_census_invariance(runtime):
    state = _states(runtime)[0]
    measured = replace(state, nominations=())
    assert derive_evidence_maturity(measured).level is EvidenceLevel.MEASURED

    census_true = replace(state, annotation=GeneAnnotation(None, True, None, "note"))
    census_false = replace(state, annotation=GeneAnnotation(None, False, None, "note"))
    assert derive_evidence_maturity(census_true) == derive_evidence_maturity(census_false)
    assert derive_evidence_maturity(census_true) == derive_evidence_maturity(state)


def test_evidence_level_is_not_a_jev_input(runtime):
    import json

    from cancerjev.jev.projection import build_projection
    from tests.jev.test_service import state_record

    state = _states(runtime)[0]
    baseline = build_projection(state_record("union-1", state))
    altered = build_projection(
        state_record("union-1", replace(state, evidence_level="FUNCTIONALLY_SUPPORTED")))

    assert altered == baseline
    assert "evidence_level" not in json.dumps(baseline)
