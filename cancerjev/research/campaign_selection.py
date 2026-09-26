"""Named deterministic Campaign selection policy; no hidden ordering, ever.

Eligibility is readiness-gated (only profiles validated for autonomous use) and
status-gated (PENDING). Order is the declared tuple: readiness gate, then the
profile's declared priority (higher first), then campaign_id ascending. Registry,
filesystem or lexical accident never chooses a campaign.

With durable program state, readiness and profile status stay the first gates and
the persisted record adds exactly two more: a completed campaign with an
unchanged profile/release/method identity is never redispatched, and a failed
campaign is retried only after its bounded backoff elapses, stopping at the
declared attempt cap. Identity changes are declared per component.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import CampaignRecord, CampaignStatus
from cancerjev.research.campaign import CampaignProfile

CAMPAIGN_SELECTION_POLICY_VERSION = "campaign-selection-v2"
SELECTED_REASON = "CAMPAIGN_SELECTED"
IDLE_REASON = "PROGRAM_IDLE"

ALREADY_COMPLETE_REASON = "CAMPAIGN_ALREADY_COMPLETE_FOR_IDENTITY"
RELEASE_CHANGED_REASON = "RELEASE_CHANGED"
METHOD_CHANGED_REASON = "METHOD_CHANGED"
PROFILE_CHANGED_REASON = "PROFILE_CHANGED"
RETRY_ELIGIBLE_REASON = "CAMPAIGN_RETRY_ELIGIBLE"
RETRY_BACKOFF_REASON = "RETRY_BACKOFF_ACTIVE"
RETRY_EXHAUSTED_REASON = "RETRY_ATTEMPTS_EXHAUSTED"
NOT_VALIDATED_REASON = "NOT_VALIDATED_FOR_AUTONOMOUS_USE"
PROFILE_STATUS_REASON = "PROFILE_STATUS_NOT_PENDING"

MAX_CAMPAIGN_ATTEMPTS = 5


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


def identity_change_reason(
        record: CampaignRecord,
        identity: tuple[str | None, str | None, str | None]) -> str | None:
    """The declared per-component identity change, or None when unchanged."""
    profile_identity, release_identity, method_identity = identity
    if record.release_identity != release_identity:
        return RELEASE_CHANGED_REASON
    if record.method_identity != method_identity:
        return METHOD_CHANGED_REASON
    if record.profile_identity != profile_identity:
        return PROFILE_CHANGED_REASON
    return None


def _backoff_active(next_attempt_at: str | None, now: datetime) -> bool:
    if next_attempt_at is None:
        return False
    deadline = datetime.fromisoformat(next_attempt_at.replace("Z", "+00:00"))
    return now < deadline


def durable_decision(record: CampaignRecord, *,
                     identity: tuple[str | None, str | None, str | None],
                     now: datetime) -> tuple[bool, str]:
    """Whether a durable record allows a dispatch now, and the declared reason."""
    if record.status is CampaignStatus.CAMPAIGN_COMPLETE:
        change = identity_change_reason(record, identity)
        return (change is not None), (change or ALREADY_COMPLETE_REASON)
    if record.status is CampaignStatus.BLOCKED:
        change = identity_change_reason(record, identity)
        if change is not None:
            return True, change
        if record.attempts >= MAX_CAMPAIGN_ATTEMPTS:
            return False, RETRY_EXHAUSTED_REASON
        if _backoff_active(record.next_attempt_at, now):
            return False, RETRY_BACKOFF_REASON
        return True, RETRY_ELIGIBLE_REASON
    if record.status is CampaignStatus.RUNNING:
        return False, "CAMPAIGN_IN_FLIGHT"
    return True, SELECTED_REASON


def select_next_campaign_with_state(
        profiles: tuple[CampaignProfile, ...], *,
        records: Mapping[str, CampaignRecord] | None = None,
        identities: Mapping[str, tuple[str | None, str | None, str | None]] | None = None,
        now: datetime | None = None,
) -> tuple[CampaignProfile | None, str, dict[str, str]]:
    """Durable-aware selection; returns the choice, aggregate reason and per-profile reasons."""
    records = records if records is not None else MappingProxyType({})
    identities = identities if identities is not None else MappingProxyType({})
    moment = now if now is not None else datetime.now(UTC)
    ordered = sorted(profiles, key=lambda profile: (-profile.priority, profile.profile_id))
    reasons: dict[str, str] = {}
    selected: CampaignProfile | None = None
    for profile in ordered:
        if profile.readiness is not ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE:
            reasons[profile.profile_id] = NOT_VALIDATED_REASON
            continue
        if profile.status is not CampaignStatus.PENDING:
            reasons[profile.profile_id] = PROFILE_STATUS_REASON
            continue
        record = records.get(profile.profile_id)
        if record is None:
            reasons[profile.profile_id] = SELECTED_REASON
            if selected is None:
                selected = profile
            continue
        allowed, reason = durable_decision(
            record, identity=identities.get(profile.profile_id, (None, None, None)), now=moment)
        reasons[profile.profile_id] = reason
        if allowed and selected is None:
            selected = profile
    if selected is None:
        return None, IDLE_REASON, reasons
    return selected, reasons[selected.profile_id], reasons
