"""Ownership-gated autonomous campaign dispatch: readiness and capability gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1, CampaignActivationError
from cancerjev.research.program import dispatch_validated_campaign
from tests.helpers import canned_capability

VALIDATED = replace(LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_V2",
                    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)


def test_experimental_profile_is_never_dispatched():
    called: list[object] = []

    with pytest.raises(CampaignActivationError) as failure:
        dispatch_validated_campaign(profile=LUAD_CAMPAIGN_V1, capability=canned_capability(),
                                    run_campaign=lambda profile: called.append(profile) or True)

    assert failure.value.code == "PROFILE_NOT_VALIDATED_FOR_AUTONOMOUS_USE"
    assert called == []


def test_missing_capability_record_blocks_with_a_typed_error():
    called: list[object] = []

    with pytest.raises(CampaignActivationError) as failure:
        dispatch_validated_campaign(profile=VALIDATED, capability=None,
                                    run_campaign=lambda profile: called.append(profile) or True)

    assert failure.value.code == "CAPABILITY_RECORD_MISSING"
    assert called == []


def test_capability_without_an_enabled_modality_blocks():
    called: list[object] = []

    with pytest.raises(CampaignActivationError) as failure:
        dispatch_validated_campaign(profile=VALIDATED, capability=canned_capability(complete=False),
                                    run_campaign=lambda profile: called.append(profile) or True)

    assert failure.value.code == "CAPABILITY_UNAVAILABLE"
    assert called == []


def test_validated_and_capable_campaign_dispatches_exactly_once():
    called: list[object] = []

    result = dispatch_validated_campaign(
        profile=VALIDATED, capability=canned_capability(),
        run_campaign=lambda profile: called.append(profile) or True)

    assert result is True
    assert called == [VALIDATED]
