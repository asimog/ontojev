"""Functional/external posture: record and code agree and nothing is adopted."""

from __future__ import annotations

from pathlib import Path

from cancerjev.domain.functional import (
    AXIS_SEPARATION_LIMITATION,
    EVIDENCE_AXES,
    FUNCTIONAL_SOURCE_DECISION_RECORD_PATH,
    FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION,
    FUNCTIONAL_SOURCE_DECISIONS,
    SourceDecision,
)
from cancerjev.domain.maturity import EvidenceLevel, derive_evidence_maturity
from cancerjev.research.cutover import compose_discovery_states
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.science.test_modality_union import _cnv_result, _lanes

ROOT = Path(__file__).resolve().parents[2]


def test_decision_record_matches_the_typed_posture():
    record = (ROOT / FUNCTIONAL_SOURCE_DECISION_RECORD_PATH).read_text(encoding="utf-8")

    assert FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION == "1"
    assert "functional-sources-v1" in record
    assert FUNCTIONAL_SOURCE_DECISIONS
    assert all(decision is SourceDecision.DEFER
               for decision in FUNCTIONAL_SOURCE_DECISIONS.values())
    for source_id in ("DEPMAP_CRISPR", "SANGER_CGC", "TARGETABILITY_RESOURCES",
                      "INDEPENDENT_COHORT_REPLICATION"):
        assert source_id in FUNCTIONAL_SOURCE_DECISIONS
        assert source_id in record
    assert "**not** Sanger CGC licensing" in record


def test_axes_are_declared_separate_and_no_functional_adapter_exists():
    assert len(EVIDENCE_AXES) == len(set(EVIDENCE_AXES)) == 7
    assert "FUNCTIONAL_DEPENDENCY" in EVIDENCE_AXES and "TARGETABILITY" in EVIDENCE_AXES
    assert "never cohort-specific support" in AXIS_SEPARATION_LIMITATION

    module_root = ROOT / "cancerjev"
    assert not list(module_root.rglob("functional_adapter*.py"))
    assert not list((module_root / "research").glob("depmap*.py"))


def test_functionally_supported_stays_unattainable_without_a_contract(runtime):
    mutation, expression = _lanes(runtime)
    states = compose_discovery_states(mutation, expression, _cnv_result(mutation, ()),
                                      LUAD_RESEARCH_V1)

    maturity = derive_evidence_maturity(states[0])

    assert maturity.level is not EvidenceLevel.FUNCTIONALLY_SUPPORTED
    assert any(level == "FUNCTIONALLY_SUPPORTED" and "P17" in reason
               for level, reason in maturity.unattained)
