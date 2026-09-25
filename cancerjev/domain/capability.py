"""Typed assay capability and scientific-readiness records.

Capability is derived from open GDC metadata (project data categories plus one
bounded aggregate ``/files`` facet response); it is never inferred from a cancer
name and never asserted without a recorded reason. A modality without provider
source data is UNAVAILABLE with a reason, never a negative result; a modality
whose source data exists but has no validated OntoJev method is also UNAVAILABLE
and names that limitation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cancerjev.domain.measurements import ScientificSource, digest, require, strings, text


class Modality(StrEnum):
    MUTATION_WXS = "MUTATION_WXS"
    MUTATION_WGS = "MUTATION_WGS"
    EXPRESSION_RNASEQ = "EXPRESSION_RNASEQ"
    CNV = "CNV"
    STRUCTURAL_VARIANT = "STRUCTURAL_VARIANT"
    FUSION = "FUSION"
    METHYLATION = "METHYLATION"
    MIRNA = "MIRNA"
    RPPA = "RPPA"
    SCRNA_SNRNA = "SCRNA_SNRNA"
    CLINICAL = "CLINICAL"
    SURVIVAL = "SURVIVAL"


class CapabilityAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class AccessLevel(StrEnum):
    OPEN = "OPEN"


class CaseSampleResolution(StrEnum):
    CASE_LEVEL_ONLY = "CASE_LEVEL_ONLY"
    CASE_ALIQUOT_LEVEL = "CASE_ALIQUOT_LEVEL"
    DONOR_LEVEL = "DONOR_LEVEL"
    UNRESOLVED = "UNRESOLVED"


class ScientificReadiness(StrEnum):
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATED_FOR_REPLAY = "VALIDATED_FOR_REPLAY"
    VALIDATED_FOR_AUTONOMOUS_USE = "VALIDATED_FOR_AUTONOMOUS_USE"


READINESS_ORDER = (
    ScientificReadiness.EXPERIMENTAL,
    ScientificReadiness.VALIDATED_FOR_REPLAY,
    ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE,
)


def readiness_rank(readiness: ScientificReadiness) -> int:
    return READINESS_ORDER.index(readiness)


@dataclass(frozen=True)
class CapabilityRecord:
    """One modality's typed availability for one cohort at one pinned release."""

    modality: Modality
    availability: CapabilityAvailability
    source_present: bool
    mechanism: str | None
    experimental_strategies: tuple[str, ...]
    workflow_types: tuple[str, ...]
    case_sample_resolution: CaseSampleResolution
    access_level: AccessLevel
    limitations: tuple[str, ...]
    reason: str | None

    def __post_init__(self) -> None:
        require(isinstance(self.modality, Modality), "invalid capability modality")
        require(isinstance(self.availability, CapabilityAvailability),
                "invalid capability availability")
        require(isinstance(self.source_present, bool), "source_present must be a boolean")
        require(isinstance(self.case_sample_resolution, CaseSampleResolution),
                "invalid case/sample resolution")
        require(isinstance(self.access_level, AccessLevel), "invalid access level")
        if self.mechanism is not None:
            text(self.mechanism, "capability mechanism")
        strings(self.experimental_strategies, "capability strategies")
        strings(self.workflow_types, "capability workflows")
        strings(self.limitations, "capability limitations")
        if self.reason is not None:
            text(self.reason, "capability unavailability reason")
        if self.availability is CapabilityAvailability.AVAILABLE:
            require(self.source_present, "an available modality requires provider source data")
            require(bool(self.mechanism), "an available modality requires a named mechanism")
            require(self.reason is None, "an available modality carries no unavailability reason")
        else:
            require(bool(self.reason), "an unavailable modality requires a recorded reason")
        if not self.source_present:
            require(not self.experimental_strategies,
                    "absent provider source data carries no strategies")

    def payload(self) -> dict[str, Any]:
        return {
            "modality": self.modality.value,
            "availability": self.availability.value,
            "source_present": self.source_present,
            "mechanism": self.mechanism,
            "experimental_strategies": list(self.experimental_strategies),
            "workflow_types": list(self.workflow_types),
            "case_sample_resolution": self.case_sample_resolution.value,
            "access_level": self.access_level.value,
            "limitations": list(self.limitations),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CohortCapability:
    """Immutable capability record for one cohort at one pinned source context."""

    cohort_id: str
    project_id: str
    release: str
    release_commit: str | None
    parser_version: str
    data_model_ref: str
    records: tuple[CapabilityRecord, ...]
    sources: tuple[ScientificSource, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.cohort_id, "capability cohort id")
        text(self.project_id, "capability project id")
        text(self.release, "capability release")
        text(self.parser_version, "capability parser version")
        text(self.data_model_ref, "capability data-model reference")
        if self.release_commit is not None:
            text(self.release_commit, "capability release commit")
        require(type(self.records) is tuple
                and all(isinstance(record, CapabilityRecord) for record in self.records),
                "capability records must be an immutable tuple")
        modalities = [record.modality for record in self.records]
        require(len(modalities) == len(set(modalities)), "capability modalities must be unique")
        require(modalities == sorted(modalities, key=lambda modality: modality.value),
                "capability modalities must be sorted")
        require(type(self.sources) is tuple
                and all(isinstance(source, ScientificSource) for source in self.sources),
                "capability sources must be typed scientific sources")
        strings(tuple(self.warnings), "capability warnings")

    def record(self, modality: Modality) -> CapabilityRecord:
        for record in self.records:
            if record.modality is modality:
                return record
        raise KeyError(f"no capability record for {modality.value}")

    def available_modalities(self) -> tuple[Modality, ...]:
        return tuple(record.modality for record in self.records
                     if record.availability is CapabilityAvailability.AVAILABLE)

    def payload(self) -> dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "project_id": self.project_id,
            "release": self.release,
            "release_commit": self.release_commit,
            "parser_version": self.parser_version,
            "data_model_ref": self.data_model_ref,
            "records": [record.payload() for record in self.records],
            "sources": [
                {
                    "endpoint": source.endpoint,
                    "request_hash": source.request_hash,
                    "response_hash": source.response_hash,
                    "parser_version": source.parser_version,
                    "release": source.release,
                    "acquisition": source.acquisition.value,
                }
                for source in self.sources
            ],
            "warnings": list(self.warnings),
        }

    def capability_hash(self) -> str:
        return digest(self.payload())
