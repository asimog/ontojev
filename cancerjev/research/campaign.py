"""Campaign profiles and scientific-readiness gates.

A campaign profile is the smallest binding that lets a validated cohort be
activated: one run spec, one cohort/project, the enabled modalities and the
recorded readiness level with its reason. Readiness is code/test-owned: the
autonomous program may only select profiles that are validated for autonomous
use, and a profile may only enable modalities that the cohort capability records
as AVAILABLE.
"""

from __future__ import annotations

from dataclasses import dataclass

from cancerjev.domain.capability import (
    CapabilityAvailability,
    CohortCapability,
    Modality,
    ScientificReadiness,
    readiness_rank,
)
from cancerjev.domain.measurements import count, require, text
from cancerjev.domain.program import CampaignStatus


class CampaignActivationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CampaignProfile:
    profile_id: str
    spec_id: str
    cohort_id: str
    project_id: str
    enabled_modalities: tuple[Modality, ...]
    readiness: ScientificReadiness
    readiness_reason: str
    priority: int = 0
    status: CampaignStatus = CampaignStatus.PENDING

    def __post_init__(self) -> None:
        text(self.profile_id, "campaign profile id")
        text(self.spec_id, "campaign spec id")
        text(self.cohort_id, "campaign cohort id")
        text(self.project_id, "campaign project id")
        text(self.readiness_reason, "campaign readiness reason")
        require(isinstance(self.readiness, ScientificReadiness), "invalid campaign readiness")
        count(self.priority, "campaign priority")
        require(isinstance(self.status, CampaignStatus), "invalid campaign status")
        require(type(self.enabled_modalities) is tuple
                and all(isinstance(modality, Modality) for modality in self.enabled_modalities),
                "enabled modalities must be an immutable modality tuple")
        require(len(set(self.enabled_modalities)) == len(self.enabled_modalities),
                "enabled modalities must be unique")
        require(list(self.enabled_modalities) == sorted(self.enabled_modalities,
                                                        key=lambda modality: modality.value),
                "enabled modalities must be sorted")

    def payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "spec_id": self.spec_id,
            "cohort_id": self.cohort_id,
            "project_id": self.project_id,
            "enabled_modalities": [modality.value for modality in self.enabled_modalities],
            "readiness": self.readiness.value,
            "readiness_reason": self.readiness_reason,
            "priority": self.priority,
            "status": self.status.value,
        }


LUAD_CAMPAIGN_V1 = CampaignProfile(
    profile_id="LUAD_CAMPAIGN_V1",
    spec_id="LUAD_RESEARCH_V1",
    cohort_id="TCGA-LUAD",
    project_id="TCGA-LUAD",
    enabled_modalities=(
        Modality.CNV,
        Modality.EXPRESSION_RNASEQ,
        Modality.MUTATION_WXS,
    ),
    readiness=ScientificReadiness.EXPERIMENTAL,
    readiness_reason=(
        "the canonical systematic spine (complete-universe mutation discovery, independent "
        "expression discovery, complete CNV case-shard scan with terminal merge, deterministic "
        "modality union, measured-evidence pre-Wide policy and the autonomous candidate queue) "
        "is implemented, production-wired and offline-verified, but no full live campaign with "
        "real Wide/Deep Jev has completed and no dossier has been reviewed; promotion requires "
        "that reviewed live evidence"
    ),
)


def require_autonomous_activation(profile: CampaignProfile) -> None:
    """Refuse autonomous activation until the profile is validated for it."""
    if readiness_rank(profile.readiness) < readiness_rank(
            ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE):
        raise CampaignActivationError(
            "PROFILE_NOT_VALIDATED_FOR_AUTONOMOUS_USE",
            f"{profile.profile_id} readiness is {profile.readiness.value}: "
            f"{profile.readiness_reason}",
        )


def require_validation_activation(profile: CampaignProfile) -> None:
    """Validation runs apply only to profiles below autonomous readiness.

    The validation route executes the identical canonical spine under
    VALIDATION_RUN ownership so an EXPERIMENTAL profile can produce the live
    evidence its promotion requires, without weakening the autonomous gate: the
    Program still refuses the same profile, and readiness can only change by an
    explicit code/config edit after review.
    """
    if readiness_rank(profile.readiness) >= readiness_rank(
            ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE):
        raise CampaignActivationError(
            "PROFILE_ALREADY_AUTONOMOUS_READY",
            f"{profile.profile_id} readiness is {profile.readiness.value}; validation runs "
            "apply only below autonomous readiness",
        )


def require_capability(profile: CampaignProfile, capability: CohortCapability) -> None:
    """Refuse activation when an enabled modality is not AVAILABLE for the cohort."""
    if capability.project_id != profile.project_id:
        raise CampaignActivationError(
            "CAPABILITY_PROJECT_MISMATCH",
            f"{profile.profile_id} targets {profile.project_id} but the capability record is for "
            f"{capability.project_id}",
        )
    for modality in profile.enabled_modalities:
        record = capability.record(modality)
        if record.availability is not CapabilityAvailability.AVAILABLE:
            raise CampaignActivationError(
                "CAPABILITY_UNAVAILABLE",
                f"{profile.profile_id} enables {modality.value} but the cohort capability records "
                f"{record.availability.value} ({record.reason})",
            )
