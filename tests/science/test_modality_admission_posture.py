"""Additional modalities stay unadmitted: three lanes only, reasons preserved.

P18 is conditional: no cohort/question currently justifies a fourth modality, so
nothing is implemented. These tests prove the posture cannot drift silently.
"""

from __future__ import annotations

from cancerjev.domain.capability import CapabilityAvailability, Modality
from cancerjev.domain.scientific import Lane
from tests.contracts.test_capability_contracts import _probe

UNADMITTED = (
    Modality.STRUCTURAL_VARIANT,
    Modality.FUSION,
    Modality.METHYLATION,
    Modality.MIRNA,
    Modality.RPPA,
    Modality.SCRNA_SNRNA,
    Modality.CLINICAL,
    Modality.SURVIVAL,
)
DECLARED_REASONS = {"NO_VALIDATED_METHOD", "SOURCE_NOT_PRESENT",
                    "REQUIRED_PROVIDER_DATA_NOT_PRESENT"}


def test_state_lanes_remain_the_three_validated_lanes():
    assert {lane.value for lane in Lane} == {"MUTATION", "EXPRESSION", "CNV"}


def test_every_unadmitted_modality_stays_unavailable_with_a_reason(runtime):
    _, capability = _probe(runtime, "TCGA-LUAD")

    for modality in UNADMITTED:
        record = capability.record(modality)
        assert record.availability is CapabilityAvailability.UNAVAILABLE
        assert record.reason in DECLARED_REASONS
        assert record.limitations or record.reason

    assert Modality.MUTATION_WXS in capability.available_modalities()
    assert Modality.EXPRESSION_RNASEQ in capability.available_modalities()
    assert Modality.CNV in capability.available_modalities()
