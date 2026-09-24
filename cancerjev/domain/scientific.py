"""Typed lane results; constructing these records admits no new provider capability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import (
    Acquisition,
    CountMeasurement,
    Coverage,
    EntityRef,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    Quality,
    ScalarMeasurement,
    ScientificSource,
    TestedUniverse,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
    finite,
    require,
    strings,
    text,
)


class Lane(StrEnum):
    MUTATION = "MUTATION"
    EXPRESSION = "EXPRESSION"
    CNV = "CNV"


@dataclass(frozen=True)
class UnavailableLane:
    lane: Lane
    enabled: bool
    status: UnavailableStatus
    reason: str

    def __post_init__(self) -> None:
        require(isinstance(self.lane, Lane), "invalid lane")
        require(type(self.enabled) is bool, "enabled must be bool")
        require(isinstance(self.status, UnavailableStatus), "invalid lane status")
        require(self.enabled or self.status == UnavailableStatus.NOT_ACQUIRED,
                "disabled lane must be NOT_ACQUIRED")
        text(self.reason, "unavailable lane reason")


def _measurement(value: CountMeasurement | ScalarMeasurement, unit: Unit,
                 frame: PopulationFrame) -> None:
    require(isinstance(value, (ObservedCount, ObservedScalar, UnavailableMeasurement)), "invalid measurement")
    actual_unit = value.expected_unit if isinstance(value, UnavailableMeasurement) else value.unit
    require(actual_unit == unit and value.population == frame, "measurement unit/frame mismatch")
    if unit == Unit.CASES:
        require(not isinstance(value, ObservedScalar), "case count cannot be a scalar")
    else:
        require(not isinstance(value, ObservedCount), "expression summary cannot be a count")


@dataclass(frozen=True)
class MutationCountResult:
    affected_cases: CountMeasurement
    ssm_coverage_cases: CountMeasurement
    frame: PopulationFrame
    quality: Quality
    entity: EntityRef

    def __post_init__(self) -> None:
        require(isinstance(self.frame, PopulationFrame) and self.frame.unit == PopulationUnit.CASE,
                "mutation indexed count requires a case frame")
        require(isinstance(self.quality, Quality), "invalid mutation quality")
        require(isinstance(self.entity, EntityRef), "invalid mutation entity")
        _measurement(self.affected_cases, Unit.CASES, self.frame)
        _measurement(self.ssm_coverage_cases, Unit.CASES, self.frame)
        for value in (self.affected_cases, self.ssm_coverage_cases):
            if isinstance(value, ObservedCount):
                require(value.value <= len(self.frame.examined_ids), "count exceeds examined case frame")
                require(all(s.release == self.entity.release for s in value.sources), "mutation/source release mismatch")


@dataclass(frozen=True)
class ExpressionValue:
    case_id: str
    uqfpkm: float

    def __post_init__(self) -> None:
        text(self.case_id, "case_id")
        finite(self.uqfpkm, "UQFPKM")
        object.__setattr__(self, "uqfpkm", float(self.uqfpkm))
        require(self.uqfpkm >= 0, "negative UQFPKM")


@dataclass(frozen=True)
class ExpressionSummaryResult:
    values: tuple[ExpressionValue, ...]
    coverage: Coverage
    median: ScalarMeasurement
    sample_sd: ScalarMeasurement
    minimum: ScalarMeasurement
    maximum: ScalarMeasurement
    quality: Quality
    sources: tuple[ScientificSource, ...]
    entity: EntityRef

    def __post_init__(self) -> None:
        require(isinstance(self.coverage, Coverage), "invalid expression coverage")
        require(self.coverage.frame.unit == PopulationUnit.CASE, "expression requires case-labelled values")
        require(type(self.values) is tuple and all(isinstance(v, ExpressionValue) for v in self.values),
                "values must be immutable typed records")
        ids = tuple(v.case_id for v in self.values)
        strings(ids, "expression case IDs")
        require(ids == tuple(sorted(self.coverage.valid_ids)), "values must exactly cover sorted valid IDs")
        require(isinstance(self.quality, Quality), "invalid expression quality")
        require(isinstance(self.entity, EntityRef), "invalid expression entity")
        require(type(self.sources) is tuple and all(isinstance(s, ScientificSource) for s in self.sources),
                "invalid expression sources")
        require(not self.values or bool(self.sources), "expression values require sources")
        require(all(s.release == self.entity.release for s in self.sources), "expression/source release mismatch")
        require(not self.values or all(s.acquisition in (Acquisition.COMPLETE, Acquisition.PARTIAL) for s in self.sources),
                "failed/unacquired source cannot support values")
        for value in (self.median, self.sample_sd, self.minimum, self.maximum):
            _measurement(value, Unit.LOG2_UQFPKM_PLUS_ONE, self.coverage.frame)
            if isinstance(value, ObservedScalar):
                require(set(value.sources) <= set(self.sources), "unbound summary sources")
        for value in (self.median, self.minimum, self.maximum):
            require(bool(self.values) or isinstance(value, UnavailableMeasurement), "empty summary cannot be observed")
        require(len(self.values) >= 2 or isinstance(self.sample_sd, UnavailableMeasurement),
                "sample SD needs at least two values")
        if isinstance(self.minimum, ObservedScalar) and isinstance(self.maximum, ObservedScalar):
            require(self.minimum.value <= self.maximum.value, "minimum exceeds maximum")
            if isinstance(self.median, ObservedScalar):
                require(self.minimum.value <= self.median.value <= self.maximum.value, "median outside range")


class CnvCategory(StrEnum):
    LOSS_UNSPECIFIED = "LOSS_UNSPECIFIED"
    GAIN = "GAIN"
    AMPLIFICATION = "AMPLIFICATION"
    HOMOZYGOUS_DELETION = "HOMOZYGOUS_DELETION"
    UNSUPPORTED_CATEGORY = "UNSUPPORTED_CATEGORY"


@dataclass(frozen=True)
class CnvOccurrence:
    occurrence_id: str
    cnv_id: str
    case_id: str
    gene_id: str
    raw_category: str
    source_file_id: str | None
    caller: str | None
    sample_id: str | None
    copy_number: float | None

    def __post_init__(self) -> None:
        for value in (self.occurrence_id, self.cnv_id, self.case_id, self.gene_id, self.raw_category):
            text(value, "CNV identity/category")
        for optional_value in (self.source_file_id, self.caller, self.sample_id):
            if optional_value is not None:
                text(optional_value, "CNV optional context")
        if self.copy_number is not None:
            finite(self.copy_number, "provider copy number")
            object.__setattr__(self, "copy_number", float(self.copy_number))

    @property
    def category(self) -> CnvCategory:
        # Explicit observed spellings only. Unknown labels never mean neutral.
        return {
            "Loss": CnvCategory.LOSS_UNSPECIFIED,
            "loss": CnvCategory.LOSS_UNSPECIFIED,
            "Gain": CnvCategory.GAIN,
            "gain": CnvCategory.GAIN,
            "Amplification": CnvCategory.AMPLIFICATION,
            "amplification": CnvCategory.AMPLIFICATION,
            "Homozygous Deletion": CnvCategory.HOMOZYGOUS_DELETION,
            "homozygous deletion": CnvCategory.HOMOZYGOUS_DELETION,
        }.get(self.raw_category, CnvCategory.UNSUPPORTED_CATEGORY)


@dataclass(frozen=True)
class CnvOccurrenceResult:
    entity: EntityRef
    frame: PopulationFrame
    occurrences: tuple[CnvOccurrence, ...]
    sources: tuple[ScientificSource, ...]
    quality: Quality

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef) and isinstance(self.frame, PopulationFrame), "invalid CNV context")
        require(self.frame.unit == PopulationUnit.CASE, "CNV requires case frame")
        require(type(self.occurrences) is tuple and all(isinstance(o, CnvOccurrence) for o in self.occurrences),
                "occurrences must be immutable records")
        strings(tuple(o.occurrence_id for o in self.occurrences), "CNV occurrence IDs")
        require(all(o.gene_id == self.entity.gene_id and o.case_id in self.frame.examined_ids
                    for o in self.occurrences), "CNV outside gene/case frame")
        require(type(self.sources) is tuple and bool(self.sources)
                and all(isinstance(s, ScientificSource) for s in self.sources), "CNV requires sources")
        require(isinstance(self.quality, Quality), "invalid CNV quality")
        require(all(s.release == self.entity.release for s in self.sources), "CNV/source release mismatch")
        require(not self.occurrences or all(s.acquisition in (Acquisition.COMPLETE, Acquisition.PARTIAL) for s in self.sources),
                "failed/unacquired source cannot support occurrences")


@dataclass(frozen=True)
class StatisticalStateV3:
    entity: EntityRef
    frame: PopulationFrame
    universe: TestedUniverse
    mutation: MutationCountResult | UnavailableLane
    expression: ExpressionSummaryResult | UnavailableLane
    cnv: CnvOccurrenceResult | UnavailableLane
    quality: Quality
    sources: tuple[ScientificSource, ...]
    operational_sources: tuple[OperationalSource, ...] = ()

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef) and isinstance(self.frame, PopulationFrame)
                and isinstance(self.universe, TestedUniverse) and isinstance(self.quality, Quality), "invalid state context")
        require(self.entity.gene_id in self.universe.ordered_ids, "state entity outside universe")
        require(self.entity.release == self.universe.release, "state/universe release mismatch")
        require(type(self.sources) is tuple and all(isinstance(s, ScientificSource) for s in self.sources),
                "state sources must be immutable records")
        require(all(s.release == self.entity.release for s in self.sources), "mixed state/source releases")
        require(type(self.operational_sources) is tuple
                and all(isinstance(s, OperationalSource) for s in self.operational_sources), "invalid operational sources")
        require(all(s.source in self.sources for s in self.operational_sources), "unbound operational source")
        for lane, result, expected in (
            (Lane.MUTATION, self.mutation, MutationCountResult),
            (Lane.EXPRESSION, self.expression, ExpressionSummaryResult),
            (Lane.CNV, self.cnv, CnvOccurrenceResult),
        ):
            require(isinstance(result, (expected, UnavailableLane)), f"wrong {lane} result type")
            if isinstance(result, UnavailableLane):
                require(result.lane == lane, "unavailable lane in wrong slot")
            elif isinstance(result, ExpressionSummaryResult):
                require(result.coverage.frame == self.frame and result.entity == self.entity, "expression/state context mismatch")
                require(set(result.sources) <= set(self.sources), "unbound expression value sources")
                for value in (result.median, result.sample_sd, result.minimum, result.maximum):
                    if isinstance(value, ObservedScalar):
                        require(set(value.sources) <= set(self.sources), "unbound expression sources")
            elif isinstance(result, MutationCountResult):
                require(result.frame == self.frame and result.entity == self.entity, "mutation/state context mismatch")
                for count_value in (result.affected_cases, result.ssm_coverage_cases):
                    if isinstance(count_value, ObservedCount):
                        require(set(count_value.sources) <= set(self.sources), "unbound mutation sources")
            elif isinstance(result, CnvOccurrenceResult):
                require(result.frame == self.frame and result.entity == self.entity, "CNV/state context mismatch")
                require(set(result.sources) <= set(self.sources), "unbound CNV sources")
