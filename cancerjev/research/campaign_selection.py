"""Named deterministic Campaign selection policy; no hidden ordering, ever.

Eligibility is readiness-gated (only profiles validated for autonomous use) and
status-gated (PENDING). Order is the declared tuple: readiness gate, then the
profile's declared priority (higher first), then campaign_id ascending. Registry,
filesystem or lexical accident never chooses a campaign.
"""

from __future__ import annotations

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import CampaignStatus
from cancerjev.research.campaign import CampaignProfile

CAMPAIGN_SELECTION_POLICY_VERSION = "campaign-selection-v1"
SELECTED_REASON = "CAMPAIGN_SELECTED"
IDLE_REASON = "PROGRAM_IDLE"


def eligible_campaigns(profiles: tuple[CampaignProfile, ...]) -> tuple[CampaignProfile, ...]:
    """Profiles that may run now, in declared priority then campaign-id order."""
    eligible = [profile for profile in profiles
                if profile.readiness is ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE
                and profile.status is CampaignStatus.PENDING]
    eligible.sort(key=lambda profile: (-profile.priority, profile.profile_id))
    return tuple(eligible)


def select_next_campaign(profiles: tuple[CampaignProfile, ...],
                         ) -> tuple[CampaignProfile | None, str]:
    """Return the next eligible campaign, or (None, PROGRAM_IDLE)."""
    eligible = eligible_campaigns(profiles)
    if not eligible:
        return None, IDLE_REASON
    return eligible[0], SELECTED_REASON
