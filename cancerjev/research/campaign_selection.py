"""Named deterministic Campaign selection policy; no hidden ordering, ever.

Eligibility is readiness-gated (only profiles validated for autonomous use) and
status-gated (PENDING). Order is the declared tuple: readiness gate, then the
profile's declared priority (higher first), then campaign_id ascending. Registry,
filesystem or lexical accident never chooses a campaign.

With durable program state, readiness and profile status stay the first gates and
the persisted record adds exactly two more: a completed campaign with an
unchanged profile/release/method identity is never redispatched, and a failed
campaign is retried only after its bounded backoff elapses, stopping at the
declared attempt cap. Identity changes are declared per component; a release
change gates a redispatch only when the observed label is a valid, orderable
successor of the recorded one, and an unverified release fails closed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import CampaignRecord, CampaignStatus
from cancerjev.research.campaign import CampaignProfile
from cancerjev.research.release_monitor import UNVERIFIED_RELEASE

CAMPAIGN_SELECTION_POLICY_VERSION = "campaign-selection-v2"
SELECTED_REASON = "CAMPAIGN_SELECTED"
IDLE_REASON = "PROGRAM_IDLE"

ALREADY_COMPLETE_REASON = "CAMPAIGN_ALREADY_COMPLETE_FOR_IDENTITY"
RELEASE_CHANGED_REASON = "RELEASE_CHANGED"
RELEASE_UNVERIFIED_REASON = "RELEASE_UNVERIFIED"
RELEASE_NOT_SUCCESSOR_REASON = "RELEASE_NOT_ORDERABLE"
METHOD_CHANGED_REASON = "METHOD_CHANGED"
PROFILE_CHANGED_REASON = "PROFILE_CHANGED"
RETRY_ELIGIBLE_REASON = "CAMPAIGN_RETRY_ELIGIBLE"
RETRY_BACKOFF_REASON = "RETRY_BACKOFF_ACTIVE"
RETRY_EXHAUSTED_REASON = "RETRY_ATTEMPTS_EXHAUSTED"
NOT_VALIDATED_REASON = "NOT_VALIDATED_FOR_AUTONOMOUS_USE"
PROFILE_STATUS_REASON = "PROFILE_STATUS_NOT_PENDING"

MAX_CAMPAIGN_ATTEMPTS = 5

_RELEASE_LABEL = re.compile(r"^Data Release (\d+)\.(\d+)$")


def _release_rank(release: str | None) -> tuple[int, int] | None:
    if release is None:
        return None
    match = _RELEASE_LABEL.match(release)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def release_successor(previous: str | None, current: str | None) -> bool | None:
    """Whether ``current`` is a valid, strictly newer release than ``previous``.

    Only the declared GDC ``Data Release <major>.<minor>`` label shape is
    orderable; anything else (including the unverified sentinel) returns None so
    callers fail closed instead of guessing.
    """
    older = _release_rank(previous)
    newer = _release_rank(current)
    if older is None or newer is None:
        return None
    return newer > older


def identity_change_reason(
        record: CampaignRecord,
        identity: tuple[str | None, str | None, str | None]) -> str | None:
    """The declared profile/method identity change, or None when unchanged."""
    profile_identity, _, method_identity = identity
    if record.method_identity != method_identity:
        return METHOD_CHANGED_REASON
    if record.profile_identity != profile_identity:
        return PROFILE_CHANGED_REASON
    return None


def _release_decision(record: CampaignRecord, identity_release: str | None,
                      current_release: str | None) -> tuple[bool, str | None]:
    """Whether the recorded release permits a dispatch, and the declared reason.

    An unverified observation fails closed for every record, including a first
    dispatch. A changed release permits a redispatch only when the observed label
    is a valid, strictly newer release than the recorded one.
    """
    if current_release == UNVERIFIED_RELEASE:
        return False, RELEASE_UNVERIFIED_REASON
    if record.release_identity is None or record.release_identity == identity_release:
        return False, None
    if current_release is None or identity_release is None:
        return False, RELEASE_UNVERIFIED_REASON
    if release_successor(record.release, current_release) is True:
        return True, RELEASE_CHANGED_REASON
    return False, RELEASE_NOT_SUCCESSOR_REASON


def _backoff_active(next_attempt_at: str | None, now: datetime) -> bool:
    if next_attempt_at is None:
        return False
    deadline = datetime.fromisoformat(next_attempt_at.replace("Z", "+00:00"))
    return now < deadline


def durable_decision(record: CampaignRecord, *,
                     identity: tuple[str | None, str | None, str | None],
                     release: str | None = None,
                     now: datetime) -> tuple[bool, str]:
    """Whether a durable record allows a dispatch now, and the declared reason.

    ``release`` is the observed GDC data-release label for this cycle.
    """
    release_allowed, release_reason = _release_decision(record, identity[1], release)
    if record.status is CampaignStatus.CAMPAIGN_COMPLETE:
        if release_reason is not None:
            return release_allowed, release_reason
        change = identity_change_reason(record, identity)
        return (change is not None), (change or ALREADY_COMPLETE_REASON)
    if record.status is CampaignStatus.BLOCKED:
        if release_reason == RELEASE_UNVERIFIED_REASON:
            return False, release_reason
        if release_allowed and release_reason is not None:
            return True, release_reason
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
    if release_reason is not None:
        return release_allowed, release_reason
    return True, SELECTED_REASON


def select_next_campaign_with_state(
        profiles: tuple[CampaignProfile, ...], *,
        records: Mapping[str, CampaignRecord] | None = None,
        identities: Mapping[str, tuple[str | None, str | None, str | None]] | None = None,
        releases: Mapping[str, str | None] | None = None,
        now: datetime | None = None,
) -> tuple[CampaignProfile | None, str, dict[str, str]]:
    """Durable-aware selection; returns the choice, aggregate reason and per-profile reasons."""
    records = records if records is not None else MappingProxyType({})
    identities = identities if identities is not None else MappingProxyType({})
    releases = releases if releases is not None else MappingProxyType({})
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
            record, identity=identities.get(profile.profile_id, (None, None, None)),
            release=releases.get(profile.profile_id), now=moment)
        reasons[profile.profile_id] = reason
        if allowed and selected is None:
            selected = profile
    if selected is None:
        return None, IDLE_REASON, reasons
    return selected, reasons[selected.profile_id], reasons
