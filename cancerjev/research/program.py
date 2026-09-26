"""One program step: select an eligible Campaign, run it, record its status.

The program is operational coordination only. It never promotes readiness, never
acquires data itself and never continues a campaign whose profile is not
validated for autonomous use; with no eligible campaign it records PROGRAM_IDLE.
Statuses returned are the caller's to persist within the P14 ownership scope.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from cancerjev.domain.capability import CohortCapability
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import require
from cancerjev.domain.program import CampaignStatus, ProgramState
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.research.campaign import (
    CampaignActivationError,
    CampaignProfile,
    require_autonomous_activation,
    require_capability,
)
from cancerjev.research.campaign_selection import (
    CAMPAIGN_SELECTION_POLICY_VERSION,
    IDLE_REASON,
    SELECTED_REASON,
    select_next_campaign,
)
from cancerjev.research.seams import PublishJson
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

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


def dispatch_validated_campaign(*, profile: CampaignProfile,
                                capability: CohortCapability | None,
                                run_campaign: Callable[[CampaignProfile], bool]) -> bool:
    """Ownership-gated autonomous dispatch: validated profile plus recorded capability.

    A profile that is not validated for autonomous use and a capability that does not
    cover the profile's enabled modalities are refused loudly; a missing capability
    record blocks dispatch rather than being fabricated. No operator flags exist here,
    so an autonomously dispatched campaign can never carry a researcher override.
    """
    require_autonomous_activation(profile)
    if capability is None:
        raise CampaignActivationError(
            "CAPABILITY_RECORD_MISSING",
            f"{profile.profile_id} has no recorded cohort capability for {profile.project_id}")
    require_capability(profile, capability)
    return bool(run_campaign(profile))


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


PROGRAM_STATE_ARTIFACT_PATH = "runs/{run_id}/program/state.json"


def program_state_payload(outcome: ProgramRunOutcome, profiles: tuple[CampaignProfile, ...],
                          ) -> dict[str, Any]:
    """Persisted program state: outcome plus each campaign's recorded status."""
    statuses = {profile_id: status.value for profile_id, status in outcome.campaign_statuses}
    return {
        "version": PROGRAM_LOOP_VERSION,
        "state": outcome.state.value,
        "selected_profile_id": outcome.selected_profile_id,
        "reason_code": outcome.reason_code,
        "campaigns": [
            {**profile.payload(),
             "status": statuses.get(profile.profile_id, profile.status.value)}
            for profile in sorted(profiles, key=lambda item: item.profile_id)
        ],
    }


def run_program_worker(*, run_id: str, repository: Repository, artifacts: ArtifactStore,
                       emit: Callable[..., Any], publish_json: PublishJson,
                       profiles: tuple[CampaignProfile, ...],
                       run_campaign: Callable[[CampaignProfile], bool],
                       ) -> tuple[ProgramRunOutcome, Any]:
    """One owner-checked program step, with artifact-backed durable state."""
    repository.require_run_ownership(run_id, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    emit(run_id, "PROGRAM_RUN_STARTED", f"program:{run_id}:started",
         "Autonomous program step started.", stage="PROGRAM",
         data={"campaigns": [profile.payload() for profile in profiles],
               "policy_version": CAMPAIGN_SELECTION_POLICY_VERSION})
    outcome = run_program_once(profiles=profiles, run_campaign=run_campaign)
    if outcome.selected_profile_id is None:
        emit(run_id, "PROGRAM_IDLE", f"program:{run_id}:idle",
             "No eligible campaign; the program is idle.", stage="PROGRAM",
             data={"reason_code": outcome.reason_code})
    else:
        emit(run_id, "CAMPAIGN_SELECTED",
             f"program:{run_id}:selected:{outcome.selected_profile_id}",
             f"Campaign {outcome.selected_profile_id} selected by the declared policy.",
             stage="PROGRAM", data={"profile_id": outcome.selected_profile_id,
                                    "reason_code": outcome.reason_code})
        emit(run_id, "CAMPAIGN_COMPLETED" if outcome.state is ProgramState.CAMPAIGN_COMPLETE
             else "CAMPAIGN_BLOCKED", f"program:{run_id}:finished:{outcome.selected_profile_id}",
             f"Campaign {outcome.selected_profile_id} finished with {outcome.state.value}.",
             stage="PROGRAM", data={"profile_id": outcome.selected_profile_id,
                                    "state": outcome.state.value})
    artifact = publish_json(run_id, PROGRAM_STATE_ARTIFACT_PATH.format(run_id=run_id),
                            canonical_json(program_state_payload(outcome, profiles)),
                            "program-state")
    repository.register_artifact(artifact, run_id)
    return outcome, artifact


def load_program_state(*, run_id: str, repository: Repository,
                       artifacts: ArtifactStore) -> dict[str, Any] | None:
    """Read back one step's persisted state; absent state is None, never inferred."""
    row = repository.artifact_at_path(PROGRAM_STATE_ARTIFACT_PATH.format(run_id=run_id))
    if row is None:
        return None
    body = artifacts.read(str(row["relative_path"]), str(row["sha256"]))
    payload = json.loads(body)
    require(isinstance(payload, dict) and payload.get("version") == PROGRAM_LOOP_VERSION,
            "program state artifact is unsupported")
    return cast(dict[str, Any], payload)
