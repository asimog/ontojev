"""One program step: select an eligible Campaign, run it, record its status.

The program is operational coordination only. It never promotes readiness, never
acquires data itself and never continues a campaign whose profile is not
validated for autonomous use; with no eligible campaign it records PROGRAM_IDLE.
Statuses returned are the caller's to persist within the P14 ownership scope.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cancerjev.domain.measurements import require
from cancerjev.domain.program import CampaignStatus, ProgramState
from cancerjev.research.campaign import CampaignProfile
from cancerjev.research.campaign_selection import (
    IDLE_REASON,
    SELECTED_REASON,
    select_next_campaign,
)

PROGRAM_LOOP_VERSION = "program-loop-v1"
COMPLETED_REASON = "CAMPAIGN_COMPLETED"
BLOCKED_REASON = "CAMPAIGN_BLOCKED"


@dataclass(frozen=True)
class ProgramRunOutcome:
    state: ProgramState
    selected_profile_id: str | None
    reason_code: str
    campaign_statuses: tuple[tuple[str, CampaignStatus], ...]

    def __post_init__(self) -> None:
        require(isinstance(self.state, ProgramState), "invalid program state")
        if self.selected_profile_id is not None:
            require(bool(self.selected_profile_id), "selected profile id must be non-empty")
        require(self.reason_code in {SELECTED_REASON, IDLE_REASON, COMPLETED_REASON, BLOCKED_REASON},
                "undeclared program reason")
        for profile_id, status in self.campaign_statuses:
            require(bool(profile_id) and isinstance(status, CampaignStatus),
                    "invalid campaign status row")


def run_program_once(*, profiles: tuple[CampaignProfile, ...],
                     run_campaign: Callable[[CampaignProfile], bool]) -> ProgramRunOutcome:
    """Select and run at most one Campaign; the callback owns the actual run."""
    require(type(profiles) is tuple
            and all(isinstance(profile, CampaignProfile) for profile in profiles),
            "program profiles must be immutable campaign profiles")
    profile, reason = select_next_campaign(profiles)
    if profile is None:
        return ProgramRunOutcome(
            state=ProgramState.PROGRAM_IDLE, selected_profile_id=None, reason_code=reason,
            campaign_statuses=tuple((item.profile_id, item.status)
                                    for item in sorted(profiles, key=lambda item: item.profile_id)))
    succeeded = bool(run_campaign(profile))
    updated = CampaignStatus.CAMPAIGN_COMPLETE if succeeded else CampaignStatus.BLOCKED
    statuses = tuple(
        (item.profile_id, updated if item.profile_id == profile.profile_id else item.status)
        for item in sorted(profiles, key=lambda item: item.profile_id))
    return ProgramRunOutcome(
        state=ProgramState.CAMPAIGN_COMPLETE if succeeded else ProgramState.BLOCKED_NOT_READY,
        selected_profile_id=profile.profile_id,
        reason_code=COMPLETED_REASON if succeeded else BLOCKED_REASON,
        campaign_statuses=statuses,
    )
