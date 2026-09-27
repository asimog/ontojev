"""The durable program step: observe release, select, run, persist, retry.

The program is operational coordination only. It never promotes readiness, never
acquires data itself and never continues a campaign whose profile is not
validated for autonomous use; with no eligible campaign it records PROGRAM_IDLE.

Durable state is an append-only immutable artifact (`program-state`) whose latest
instance is resolved by the registering run's creation order. A completed
campaign is redispatched only when the observed release identity, the method
identity or the profile identity changed; a failed campaign is retried only after
its bounded deterministic backoff elapses and stops at the declared attempt cap.
Historical Program/Campaign evidence is never mutated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from cancerjev.domain.capability import CohortCapability
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import digest, require
from cancerjev.domain.program import CampaignRecord, CampaignStatus, ProgramState
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
    MAX_CAMPAIGN_ATTEMPTS,
    RETRY_EXHAUSTED_REASON,
    SELECTED_REASON,
    select_next_campaign_with_state,
)
from cancerjev.research.release_monitor import (
    ReleaseObservation,
    observation_hash,
    release_identity,
)
from cancerjev.research.seams import PublishJson
from cancerjev.science.methods import method_environment_hash
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

PROGRAM_LOOP_VERSION = "program-loop-v2"
PROGRAM_STATE_PURPOSE = "program-state"
PROGRAM_STATE_PATH_PREFIX = "program/state/state-"
COMPLETED_REASON = "CAMPAIGN_COMPLETED"
BLOCKED_REASON = "CAMPAIGN_BLOCKED"
RETRY_REASON = "CAMPAIGN_RETRY_SCHEDULED"
RECOVERY_REASON = "CAMPAIGN_COMPLETION_RECOVERED"
PRECONDITION_UNMET_REASON = "CAMPAIGN_PRECONDITION_UNMET"
RETRY_BASE_SECONDS = 300
RETRY_MAX_SECONDS = 3600
RECOVERY_SCAN_LIMIT = 20
RECOVERY_EVENT_LIMIT = 500

PROGRAM_REASON_CODES = frozenset({
    SELECTED_REASON, IDLE_REASON, COMPLETED_REASON, BLOCKED_REASON, RETRY_REASON,
    PRECONDITION_UNMET_REASON,
})


class CampaignPreconditionError(Exception):
    """A dispatch precondition failed before any work; never a durable attempt.

    Raised by the dispatch boundary (for example a missing provider credential)
    before any live probe or campaign run, so the campaign record stays PENDING
    with its attempt count unchanged and is retried unpenalized once the
    precondition is fixed.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class ProgramStateError(RuntimeError):
    """Unsupported or unreadable durable program state; fail closed."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class ProgramRunOutcome:
    state: ProgramState
    selected_profile_id: str | None
    reason_code: str
    campaign_statuses: tuple[tuple[str, CampaignStatus], ...]
    records: tuple[CampaignRecord, ...]
    reasons_by_profile: dict[str, str]

    def __post_init__(self) -> None:
        require(isinstance(self.state, ProgramState), "invalid program state")
        if self.selected_profile_id is not None:
            require(bool(self.selected_profile_id), "selected profile id must be non-empty")
        require(self.reason_code in PROGRAM_REASON_CODES, "undeclared program reason")
        for profile_id, status in self.campaign_statuses:
            require(bool(profile_id) and isinstance(status, CampaignStatus),
                    "invalid campaign status row")
        require(type(self.records) is tuple
                and all(isinstance(record, CampaignRecord) for record in self.records),
                "program outcome records must be immutable campaign records")
        for record in self.records:
            require(record.profile_id in self.reasons_by_profile,
                    "every campaign record needs a recorded decision reason")


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


def campaign_identity_components(
        profile: CampaignProfile, *, observation: ReleaseObservation | None,
        method_identity: str | None) -> tuple[str | None, str | None, str | None]:
    """Declared identity of one campaign dispatch: profile, release, method.

    The release component is the declared release identity (label plus pinned
    commit); the status response hash is provenance and never part of identity.
    """
    profile_identity = str(digest(profile.payload()))
    release = release_identity(observation) if observation is not None else None
    return profile_identity, release, method_identity


def initial_record(profile: CampaignProfile) -> CampaignRecord:
    return CampaignRecord(
        profile_id=profile.profile_id, status=CampaignStatus.PENDING,
        profile_identity=None, release_identity=None, method_identity=None,
        attempts=0, next_attempt_at=None, reason_code=None, last_cycle_run_id=None,
    )


def durable_records(state: dict[str, Any] | None,
                    profiles: tuple[CampaignProfile, ...],
                    ) -> dict[str, CampaignRecord]:
    """Decode the persisted campaign records; unknown profiles get an initial record.

    A record written before release labels were persisted is upgraded from the
    state's own top-level release exactly when its identity matches that release;
    otherwise its labels stay absent and release ordering fails closed.
    """
    records = {profile.profile_id: initial_record(profile) for profile in profiles}
    payload = state or {}
    campaigns = payload.get("campaigns")
    if campaigns is None:
        return records
    require(isinstance(campaigns, list), "program state campaigns must be a list")
    baseline_identity = payload.get("release_identity")
    baseline_release = payload.get("release")
    baseline_commit = payload.get("release_commit")
    for entry in campaigns:
        if isinstance(entry, dict) and entry.get("profile_id") in records:
            record = CampaignRecord.from_payload(entry)
            if (record.release is None and record.release_identity is not None
                    and record.release_identity == baseline_identity
                    and baseline_release is not None):
                record = replace(record, release=baseline_release,
                                 release_commit=baseline_commit)
            records[str(entry["profile_id"])] = record
    return records


def retry_delay_seconds(attempts: int) -> int:
    """Declared bounded exponential backoff; deterministic given the attempt count."""
    require(attempts >= 1, "retry attempts must be positive")
    delay: int = min(RETRY_BASE_SECONDS * (2 ** (attempts - 1)), RETRY_MAX_SECONDS)
    return delay


def recover_completed_campaign(
        *, repository: Repository, profiles: tuple[CampaignProfile, ...],
        durable: dict[str, Any] | None, observation: ReleaseObservation | None,
        method_identity: str | None, current_run_id: str,
        scan_limit: int = RECOVERY_SCAN_LIMIT) -> dict[str, CampaignRecord]:
    """Adopt a recorded completion whose program-state registration was interrupted.

    A crash between the campaign's completion event and the durable state publish
    leaves the stored record behind, so the next cycle would redispatch work that
    already finished. The event log is the idempotency source: when a recent program
    cycle recorded a ``CAMPAIGN_COMPLETED`` event whose full identity equals this
    cycle's identity, that completion is adopted as the durable record instead of
    running the campaign again. No identity match means no adoption.
    """
    records = durable_records(durable, profiles)
    unresolved = {profile.profile_id for profile in profiles
                  if records[profile.profile_id].status is not CampaignStatus.CAMPAIGN_COMPLETE}
    if not unresolved:
        return {}
    identities = {
        profile.profile_id: campaign_identity_components(
            profile, observation=observation, method_identity=method_identity)
        for profile in profiles
    }
    recovered: dict[str, CampaignRecord] = {}
    recent = repository.list_runs(scan_limit, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    for run in recent:
        if run["run_id"] == current_run_id or run.get("purpose") != "PROGRAM":
            continue
        for profile_id, record in _recovered_records(
                repository=repository, run_id=str(run["run_id"]), profile_ids=unresolved,
                identities=identities):
            recovered[profile_id] = record
            unresolved.discard(profile_id)
        if not unresolved:
            break
    return recovered


def _recovered_records(
        *, repository: Repository, run_id: str, profile_ids: set[str],
        identities: dict[str, tuple[str | None, str | None, str | None]],
) -> list[tuple[str, CampaignRecord]]:
    events = repository.events(run_id, 0, RECOVERY_EVENT_LIMIT)["items"]
    recorded_profiles: dict[str, str] = {}
    selected: dict[str, dict[str, Any]] = {}
    completed: set[str] = set()
    for event in events:
        data = event.get("data") or {}
        profile_id = data.get("profile_id")
        if event["type"] == "PROGRAM_RUN_STARTED":
            for entry in data.get("campaigns") or []:
                if isinstance(entry, dict) and entry.get("profile_id") in profile_ids:
                    recorded_profiles[str(entry["profile_id"])] = str(digest(entry))
        elif event["type"] == "CAMPAIGN_SELECTED" and profile_id in profile_ids:
            selected[str(profile_id)] = data
        elif event["type"] == "CAMPAIGN_COMPLETED" and profile_id in profile_ids:
            completed.add(str(profile_id))
    recovered: list[tuple[str, CampaignRecord]] = []
    for profile_id in sorted(completed):
        selection = selected.get(profile_id)
        if selection is None or recorded_profiles.get(profile_id) != identities[profile_id][0]:
            continue
        if (selection.get("release_identity"), selection.get("method_identity")) \
                != identities[profile_id][1:]:
            continue
        recovered.append((profile_id, CampaignRecord(
            profile_id=profile_id, status=CampaignStatus.CAMPAIGN_COMPLETE,
            profile_identity=identities[profile_id][0],
            release_identity=identities[profile_id][1],
            method_identity=identities[profile_id][2],
            attempts=0, next_attempt_at=None, reason_code=COMPLETED_REASON,
            last_cycle_run_id=run_id,
        )))
    return recovered


def retry_after(now: datetime, attempts: int) -> str:
    return (now + timedelta(seconds=retry_delay_seconds(attempts))) \
        .isoformat().replace("+00:00", "Z")


def run_program_once(*, profiles: tuple[CampaignProfile, ...],
                     run_campaign: Callable[[CampaignProfile], bool],
                     durable: dict[str, Any] | None = None,
                     recovered: dict[str, CampaignRecord] | None = None,
                     observation: ReleaseObservation | None = None,
                     method_identity: str | None = None,
                     now: datetime | None = None,
                     cycle_run_id: str | None = None) -> ProgramRunOutcome:
    """Select and run at most one Campaign; the callback owns the actual run.

    ``recovered`` carries completions whose durable registration was interrupted;
    they are adopted as complete records and are never redispatched.
    """
    require(type(profiles) is tuple
            and all(isinstance(profile, CampaignProfile) for profile in profiles),
            "program profiles must be immutable campaign profiles")
    moment = now if now is not None else datetime.now(UTC)
    records = durable_records(durable, profiles)
    for profile_id, record in (recovered or {}).items():
        if profile_id in records \
                and records[profile_id].status is not CampaignStatus.CAMPAIGN_COMPLETE:
            records[profile_id] = record
    identities = {
        profile.profile_id: campaign_identity_components(
            profile, observation=observation, method_identity=method_identity)
        for profile in profiles
    }
    release = observation.release if observation is not None else None
    release_commit = observation.release_commit if observation is not None else None
    releases = {profile.profile_id: release for profile in profiles}
    profile, reason, reasons_by_profile = select_next_campaign_with_state(
        profiles, records=records, identities=identities, releases=releases, now=moment)
    if profile is None:
        return ProgramRunOutcome(
            state=ProgramState.PROGRAM_IDLE, selected_profile_id=None, reason_code=reason,
            campaign_statuses=tuple(sorted(
                ((record.profile_id, record.status) for record in records.values()),
                key=lambda item: item[0])),
            records=tuple(sorted(records.values(), key=lambda record: record.profile_id)),
            reasons_by_profile=reasons_by_profile,
        )
    base = records[profile.profile_id]
    identity = identities[profile.profile_id]
    try:
        succeeded = bool(run_campaign(profile))
    except CampaignPreconditionError:
        # A precondition refusal is not a campaign failure: no work happened, the
        # record stays PENDING with its attempt count unchanged, and the next cycle
        # retries unpenalized once the precondition is fixed.
        reasons_by_profile[profile.profile_id] = PRECONDITION_UNMET_REASON
        return ProgramRunOutcome(
            state=ProgramState.PROGRAM_IDLE, selected_profile_id=profile.profile_id,
            reason_code=PRECONDITION_UNMET_REASON,
            campaign_statuses=tuple(sorted(
                ((record.profile_id, record.status) for record in records.values()),
                key=lambda item: item[0])),
            records=tuple(sorted(records.values(), key=lambda record: record.profile_id)),
            reasons_by_profile=reasons_by_profile,
        )
    if succeeded:
        updated = replace(
            base, status=CampaignStatus.CAMPAIGN_COMPLETE,
            profile_identity=identity[0], release_identity=identity[1], method_identity=identity[2],
            attempts=0, next_attempt_at=None, reason_code=COMPLETED_REASON,
            last_cycle_run_id=cycle_run_id, release=release, release_commit=release_commit,
        )
        state = ProgramState.CAMPAIGN_COMPLETE
        reason_code = COMPLETED_REASON
    else:
        attempts = base.attempts + 1
        exhausted = attempts >= MAX_CAMPAIGN_ATTEMPTS
        updated = replace(
            base, status=CampaignStatus.BLOCKED,
            profile_identity=identity[0], release_identity=identity[1], method_identity=identity[2],
            attempts=attempts,
            next_attempt_at=None if exhausted else retry_after(moment, attempts),
            reason_code=RETRY_EXHAUSTED_REASON if exhausted else RETRY_REASON,
            last_cycle_run_id=cycle_run_id, release=release, release_commit=release_commit,
        )
        state = ProgramState.BLOCKED_NOT_READY
        reason_code = BLOCKED_REASON if exhausted else RETRY_REASON
    records[profile.profile_id] = updated
    return ProgramRunOutcome(
        state=state, selected_profile_id=profile.profile_id, reason_code=reason_code,
        campaign_statuses=tuple(sorted(
            ((record.profile_id, record.status) for record in records.values()),
            key=lambda item: item[0])),
        records=tuple(sorted(records.values(), key=lambda record: record.profile_id)),
        reasons_by_profile=reasons_by_profile,
    )


def program_state_payload(outcome: ProgramRunOutcome, profiles: tuple[CampaignProfile, ...],
                          *, observation: ReleaseObservation | None,
                          method_identity: str | None) -> dict[str, Any]:
    """Persisted durable program state: decisions, identities, retries, statuses."""
    records = {record.profile_id: record for record in outcome.records}
    return {
        "version": PROGRAM_LOOP_VERSION,
        "state": outcome.state.value,
        "selected_profile_id": outcome.selected_profile_id,
        "reason_code": outcome.reason_code,
        "policy_version": CAMPAIGN_SELECTION_POLICY_VERSION,
        "release": observation.release if observation is not None else None,
        "release_commit": observation.release_commit if observation is not None else None,
        "release_identity": (release_identity(observation)
                             if observation is not None else None),
        "method_identity": method_identity,
        "campaign_decisions": dict(outcome.reasons_by_profile),
        "campaigns": [
            {**profile.payload(),
             **(records.get(profile.profile_id) or initial_record(profile)).payload()}
            for profile in sorted(profiles, key=lambda item: item.profile_id)
        ],
    }


def load_program_state(*, repository: Repository,
                       artifacts: ArtifactStore) -> dict[str, Any] | None:
    """Read the latest durable program state; absent state is None, never inferred."""
    row = repository.latest_artifact_by_purpose(PROGRAM_STATE_PURPOSE)
    if row is None:
        return None
    body = artifacts.read(str(row["relative_path"]), str(row["sha256"]))
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ProgramStateError("PROGRAM_STATE_UNREADABLE", "program state is not an object")
    version = payload.get("version")
    if version != PROGRAM_LOOP_VERSION:
        raise ProgramStateError(
            "PROGRAM_STATE_VERSION_UNSUPPORTED",
            f"program state version {version!r} is not {PROGRAM_LOOP_VERSION}")
    return cast(dict[str, Any], payload)


def run_program_worker(*, run_id: str, repository: Repository, artifacts: ArtifactStore,
                       emit: Callable[..., Any], publish_json: PublishJson,
                       profiles: tuple[CampaignProfile, ...],
                       run_campaign: Callable[[CampaignProfile], bool],
                       observe: Callable[[], ReleaseObservation] | None = None,
                       method_identity: str | None = None,
                       now: datetime | None = None,
                       ) -> tuple[ProgramRunOutcome, Any]:
    """One owner-checked durable program cycle: observe, load, select, run, persist.

    The release is observed once per cycle through the injected bounded callback;
    the method identity defaults to the admitted method environment hash. State is
    published append-only, so restarting the process cannot redispatch the same
    completed campaign for the same identities; a completion whose state publish was
    interrupted is adopted from the recorded events instead of being rerun.
    """
    repository.require_run_ownership(run_id, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    durable = load_program_state(repository=repository, artifacts=artifacts)
    emit(run_id, "PROGRAM_RUN_STARTED", f"program:{run_id}:started",
         "Autonomous program cycle started.", stage="PROGRAM",
         data={"campaigns": [profile.payload() for profile in profiles],
               "policy_version": CAMPAIGN_SELECTION_POLICY_VERSION,
               "durable_state_version": (durable or {}).get("version")})
    observation = observe() if observe is not None else None
    if observation is not None:
        emit(run_id, "RELEASE_OBSERVED", f"program:{run_id}:release-observed",
             f"Observed GDC release {observation.release}.", stage="PROGRAM",
             data={"release": observation.release, "release_commit": observation.release_commit,
                   "release_identity": release_identity(observation),
                   "observation_hash": observation_hash(observation),
                   "response_hash": observation.source.response_hash})
    method = method_identity if method_identity is not None else method_environment_hash()
    recovered = recover_completed_campaign(
        repository=repository, profiles=profiles, durable=durable, observation=observation,
        method_identity=method, current_run_id=run_id)
    for profile_id, record in sorted(recovered.items()):
        emit(run_id, "CAMPAIGN_COMPLETION_RECOVERED", f"program:{run_id}:recovered:{profile_id}",
             f"Campaign {profile_id} completed in an interrupted cycle; re-registering the "
             "recorded completion instead of rerunning it.",
             stage="PROGRAM", level="warning",
             data={"profile_id": profile_id, "recovered_run_id": record.last_cycle_run_id,
                   "reason_code": RECOVERY_REASON,
                   "release_identity": record.release_identity,
                   "method_identity": record.method_identity})
    outcome = run_program_once(
        profiles=profiles, run_campaign=run_campaign, durable=durable, recovered=recovered,
        observation=observation, method_identity=method, now=now, cycle_run_id=run_id)
    if outcome.reason_code == PRECONDITION_UNMET_REASON:
        emit(run_id, "CAMPAIGN_PRECONDITION_UNMET",
             f"program:{run_id}:precondition:{outcome.selected_profile_id}",
             f"Campaign {outcome.selected_profile_id} was not dispatched: a declared "
             "precondition is unmet; no attempt was consumed.",
             stage="PROGRAM", level="warning",
             data={"profile_id": outcome.selected_profile_id,
                   "reason_code": PRECONDITION_UNMET_REASON,
                   "attempts": next(item.attempts for item in outcome.records
                                    if item.profile_id == outcome.selected_profile_id),
                   "campaign_decisions": dict(outcome.reasons_by_profile)})
    elif outcome.selected_profile_id is None:
        emit(run_id, "PROGRAM_IDLE", f"program:{run_id}:idle",
             "No eligible campaign; the program is idle.", stage="PROGRAM",
             data={"reason_code": outcome.reason_code,
                   "campaign_decisions": dict(outcome.reasons_by_profile)})
    else:
        record = next(item for item in outcome.records
                      if item.profile_id == outcome.selected_profile_id)
        emit(run_id, "CAMPAIGN_SELECTED",
             f"program:{run_id}:selected:{outcome.selected_profile_id}",
             f"Campaign {outcome.selected_profile_id} selected by the declared policy.",
             stage="PROGRAM", data={"profile_id": outcome.selected_profile_id,
                                    "reason_code": outcome.reasons_by_profile[record.profile_id],
                                    "attempt": record.attempts,
                                    "release_identity": record.release_identity,
                                    "method_identity": record.method_identity})
        emit(run_id, "CAMPAIGN_COMPLETED" if outcome.state is ProgramState.CAMPAIGN_COMPLETE
             else "CAMPAIGN_BLOCKED", f"program:{run_id}:finished:{outcome.selected_profile_id}",
             f"Campaign {outcome.selected_profile_id} finished with {outcome.state.value}.",
             stage="PROGRAM", data={"profile_id": outcome.selected_profile_id,
                                    "state": outcome.state.value,
                                    "reason_code": outcome.reason_code,
                                    "attempts": record.attempts,
                                    "next_attempt_at": record.next_attempt_at})
    payload = program_state_payload(outcome, profiles, observation=observation,
                                    method_identity=method)
    body = canonical_json(payload)
    artifact = publish_json(
        run_id, f"{PROGRAM_STATE_PATH_PREFIX}{hashlib.sha256(body).hexdigest()[:16]}.json",
        body, PROGRAM_STATE_PURPOSE)
    repository.register_artifact(artifact, run_id)
    return outcome, artifact
