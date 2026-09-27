"""Campaign selection, bounded program step and release-change classification."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import (
    CampaignStatus,
    ProgramState,
)
from cancerjev.research.campaign import (
    LUAD_CAMPAIGN_V1,
    CampaignActivationError,
    require_autonomous_activation,
)
from cancerjev.research.campaign_selection import (
    IDLE_REASON,
    SELECTED_REASON,
    eligible_campaigns,
    release_successor,
    select_next_campaign,
)
from cancerjev.research.program import run_program_once

VALIDATED = replace(LUAD_CAMPAIGN_V1, readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)


def test_experimental_campaigns_never_run_autonomously():
    assert LUAD_CAMPAIGN_V1.readiness is ScientificReadiness.EXPERIMENTAL

    profile, reason = select_next_campaign((LUAD_CAMPAIGN_V1,))
    assert profile is None and reason == IDLE_REASON
    with pytest.raises(CampaignActivationError):
        require_autonomous_activation(LUAD_CAMPAIGN_V1)


def test_selection_order_is_priority_then_campaign_id_never_registry_order():
    low = replace(VALIDATED, profile_id="CAMPAIGN_C", priority=1)
    high_a = replace(VALIDATED, profile_id="CAMPAIGN_A", priority=5)
    high_b = replace(VALIDATED, profile_id="CAMPAIGN_B", priority=5)

    assert [item.profile_id for item in eligible_campaigns((low, high_b, high_a))] == [
        "CAMPAIGN_A", "CAMPAIGN_B", "CAMPAIGN_C"]
    selected, reason = select_next_campaign((low, high_b, high_a))
    assert selected is high_a and reason == SELECTED_REASON


def test_program_once_runs_one_campaign_then_idles_or_blocks():
    calls: list[str] = []

    def succeed(profile) -> bool:
        calls.append(profile.profile_id)
        return True

    outcome = run_program_once(profiles=(VALIDATED,), run_campaign=succeed)
    assert calls == [VALIDATED.profile_id]
    assert outcome.state is ProgramState.CAMPAIGN_COMPLETE
    assert outcome.reason_code == "CAMPAIGN_COMPLETED"
    assert outcome.campaign_statuses == ((VALIDATED.profile_id, CampaignStatus.CAMPAIGN_COMPLETE),)

    completed = (replace(VALIDATED, status=CampaignStatus.CAMPAIGN_COMPLETE),)
    idle = run_program_once(profiles=completed, run_campaign=lambda profile: True)
    assert idle.state is ProgramState.PROGRAM_IDLE and idle.selected_profile_id is None

    blocked = run_program_once(profiles=(VALIDATED,), run_campaign=lambda profile: False)
    assert blocked.state is ProgramState.BLOCKED_NOT_READY
    assert blocked.campaign_statuses == ((VALIDATED.profile_id, CampaignStatus.BLOCKED),)


def test_release_order_is_strict_and_only_the_declared_label_is_orderable():
    assert release_successor("Data Release 39.0", "Data Release 47.0") is True
    assert release_successor("Data Release 47.0", "Data Release 39.0") is False
    assert release_successor("Data Release 47.0", "Data Release 47.0") is False
    assert release_successor("Data Release 47.1", "Data Release 47.2") is True
    assert release_successor("Data Release TEST", "Data Release 47.0") is None
    assert release_successor(None, "Data Release 47.0") is None
    assert release_successor("Data Release 47.0", "UNVERIFIED_RELEASE") is None
