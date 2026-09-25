"""Typed lane and state results; constructing these records admits no new provider capability.

The canonical ``StatisticalState`` is the sole runtime scientific object. Its
serialized schema-5 form is a boundary representation produced and read only by
``domain.codecs``; operational ids, attempt/cache links and provider ranking
metadata are carried in the operational envelope and never fill a measured field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cancerjev.domain.measurements import (
    Acquisition,
    CountMeasurement,
    Coverage,
    EntityRef,
    MethodIdentityRef,
    MetricRecord,
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
    count,
    finite,
    require,
    sha256,
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
    coverage_complete: bool
    frame: PopulationFrame
    quality: Quality
    entity: EntityRef

    def __post_init__(self) -> None:
        require(isinstance(self.frame, PopulationFrame) and self.frame.unit == PopulationUnit.CASE,
                "mutation indexed count requires a case frame")
        require(isinstance(self.quality, Quality), "invalid mutation quality")
        require(isinstance(self.entity, EntityRef), "invalid mutation entity")
        require(type(self.coverage_complete) is bool, "coverage completeness must be bool")
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
        return cnv_category(self.raw_category)


def cnv_category(raw_category: str) -> CnvCategory:
    """Explicit observed spellings only. Unknown labels never mean neutral."""
    return {
        "Loss": CnvCategory.LOSS_UNSPECIFIED,
        "loss": CnvCategory.LOSS_UNSPECIFIED,
        "Gain": CnvCategory.GAIN,
        "gain": CnvCategory.GAIN,
        "Amplification": CnvCategory.AMPLIFICATION,
        "amplification": CnvCategory.AMPLIFICATION,
        "Homozygous Deletion": CnvCategory.HOMOZYGOUS_DELETION,
        "homozygous deletion": CnvCategory.HOMOZYGOUS_DELETION,
    }.get(raw_category, CnvCategory.UNSUPPORTED_CATEGORY)


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


# ------------------------------------------------------------------ state context


@dataclass(frozen=True)
class GeneAnnotation:
    biotype: str | None
    cancer_census: bool | None
    genome_build: str | None
    genome_build_note: str

    def __post_init__(self) -> None:
        if self.biotype is not None:
            text(self.biotype, "biotype")
        require(self.cancer_census is None or type(self.cancer_census) is bool, "cancer census must be bool/null")
        if self.genome_build is not None:
            text(self.genome_build, "genome build")
        text(self.genome_build_note, "genome build note")


@dataclass(frozen=True)
class AcquisitionScope:
    """The bounded acquisition configuration the state was produced under."""

    case_page_size: int
    case_batch_size: int
    max_cohort_cases: int
    discovery_gene_limit: int
    count_gene_limit: int
    candidate_gene_limit: int
    expression_file_sample_size: int

    def __post_init__(self) -> None:
        for name in ("case_page_size", "case_batch_size", "max_cohort_cases", "discovery_gene_limit",
                     "count_gene_limit", "candidate_gene_limit", "expression_file_sample_size"):
            value = getattr(self, name)
            require(type(value) is int and value >= 1, f"{name} must be a positive integer")
        require(self.candidate_gene_limit <= self.count_gene_limit, "candidate limit exceeds counted genes")


@dataclass(frozen=True)
class ResearchState:
    """Research configuration and deterministic scope carried by every state."""

    spec_id: str
    domain: str
    cohort: str
    project_id: str
    cohort_selection_rule: str
    gene_selection_rule: str
    examined_case_frame: str
    acquisition: AcquisitionScope
    modalities: tuple[str, ...]
    programs: tuple[str, ...]
    projects: tuple[str, ...]
    workflows: tuple[str, ...]
    sample_types: tuple[str, ...]
    sample_type_counts: tuple[tuple[str, tuple[tuple[str, int], ...]], ...]
    comparability_statuses: tuple[str, ...]
    within_cohort_status: str
    within_cohort_reason: str
    cross_project_status: str
    cross_project_reason: str

    def __post_init__(self) -> None:
        for name in ("spec_id", "domain", "cohort", "project_id", "cohort_selection_rule",
                     "gene_selection_rule", "examined_case_frame", "within_cohort_status",
                     "within_cohort_reason", "cross_project_status", "cross_project_reason"):
            text(getattr(self, name), name)
        require(isinstance(self.acquisition, AcquisitionScope), "invalid acquisition scope")
        for name in ("programs", "projects", "workflows", "sample_types", "comparability_statuses", "modalities"):
            strings(getattr(self, name), name)
        require(self.projects == tuple(sorted(self.projects)), "research projects must be sorted")
        require(type(self.sample_type_counts) is tuple, "sample type counts must be immutable")
        seen: set[str] = set()
        for project_id, counts in self.sample_type_counts:
            text(project_id, "sample type project")
            require(project_id not in seen, "duplicate sample type project")
            seen.add(project_id)
            strings(tuple(name for name, _ in counts), f"sample types for {project_id}")
            for _, value in counts:
                count(value, "sample type count")
        require(seen <= set(self.projects), "sample types for a project outside scope")


@dataclass(frozen=True)
class PopulationRecord:
    population_id: str
    frame: PopulationFrame
    program: str | None
    provider_reported_cases: int | None
    frame_hash: str
    workflows: tuple[str, ...]
    sample_types: tuple[tuple[str, int], ...]
    selection_method: str
    selection_version: str
    harmonization_context: str
    excluded_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        text(self.population_id, "population id")
        require(isinstance(self.frame, PopulationFrame), "invalid population frame")
        if self.program is not None:
            text(self.program, "program")
        if self.provider_reported_cases is not None:
            count(self.provider_reported_cases, "provider reported cases")
        sha256(self.frame_hash, "frame hash")
        strings(self.workflows, "population workflows")
        strings(tuple(name for name, _ in self.sample_types), "population sample types")
        for _, value in self.sample_types:
            count(value, "sample type count")
        for name in ("selection_method", "selection_version", "harmonization_context"):
            text(getattr(self, name), name)
        strings(tuple(reason for reason, _ in self.excluded_counts), "excluded reasons")
        for _, value in self.excluded_counts:
            count(value, "excluded count")


@dataclass(frozen=True)
class ProviderDiscoveryMetadata:
    """Provider selection metadata; never a measured field and never in identity."""

    rank: int
    score: float | None
    lane_id: str
    note: str

    def __post_init__(self) -> None:
        count(self.rank, "provider rank")
        require(self.rank >= 1, "provider rank must be positive")
        if self.score is not None:
            finite(self.score, "provider score")
            object.__setattr__(self, "score", float(self.score))
        text(self.lane_id, "discovery lane")
        text(self.note, "discovery note")


@dataclass(frozen=True)
class ProviderExpressionSummary:
    """Provider-computed expression summary, kept separate from local measurements."""

    median: float | None
    stddev: float | None
    source: str
    estimator_note: str
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.median is not None:
            finite(self.median, "provider expression summary")
            object.__setattr__(self, "median", float(self.median))
        if self.stddev is not None:
            finite(self.stddev, "provider expression summary")
            object.__setattr__(self, "stddev", float(self.stddev))
        text(self.source, "provider summary source")
        text(self.estimator_note, "provider estimator note")
        if self.unavailable_reason is not None:
            text(self.unavailable_reason, "provider summary reason")


@dataclass(frozen=True)
class ProjectState:
    population: PopulationRecord
    mutation: MutationCountResult
    expression: ExpressionSummaryResult | UnavailableLane
    provider_expression: ProviderExpressionSummary | None
    discovery: ProviderDiscoveryMetadata | None
    cnv: CnvOccurrenceResult | UnavailableLane = UnavailableLane(
        Lane.CNV, False, UnavailableStatus.NOT_ACQUIRED, "CNV_NOT_ACQUIRED")

    def __post_init__(self) -> None:
        require(isinstance(self.population, PopulationRecord), "invalid project population")
        frame = self.population.frame
        require(isinstance(self.mutation, MutationCountResult), "wrong mutation result type")
        require(self.mutation.frame == frame, "mutation/population frame mismatch")
        require(isinstance(self.expression, (ExpressionSummaryResult, UnavailableLane)),
                "wrong expression result type")
        if isinstance(self.expression, UnavailableLane):
            require(self.expression.lane == Lane.EXPRESSION, "unavailable lane in wrong slot")
        else:
            require(self.expression.coverage.frame == frame, "expression/population frame mismatch")
        if self.provider_expression is not None:
            require(isinstance(self.provider_expression, ProviderExpressionSummary),
                    "invalid provider expression summary")
            require(self.provider_expression.unavailable_reason is None or self.provider_expression.median is None,
                    "unavailable provider summary cannot carry a median")
        if self.discovery is not None:
            require(isinstance(self.discovery, ProviderDiscoveryMetadata), "invalid provider discovery metadata")
        require(isinstance(self.cnv, (CnvOccurrenceResult, UnavailableLane)), "wrong CNV result type")
        if isinstance(self.cnv, UnavailableLane):
            require(self.cnv.lane == Lane.CNV, "unavailable lane in wrong CNV slot")
        else:
            require(self.cnv.frame == frame, "CNV/population frame mismatch")
            require(self.cnv.entity == self.mutation.entity, "CNV/mutation entity mismatch")


@dataclass(frozen=True)
class TestedContext:
    """The bounded tested-gene context the state was selected under."""

    examined_genes_hash: str
    examined_genes_n: int
    rank_in_lane: int
    selection_rule: str
    selection_bias: str
    discovered_in_project_count: int
    selection_artifact_id: str | None = None

    def __post_init__(self) -> None:
        sha256(self.examined_genes_hash, "examined genes hash")
        count(self.examined_genes_n, "examined genes count")
        require(self.examined_genes_n >= 1, "examined genes must be nonempty")
        count(self.rank_in_lane, "rank in lane")
        require(self.rank_in_lane >= 1, "rank in lane must be positive")
        text(self.selection_rule, "gene selection rule")
        text(self.selection_bias, "selection bias")
        count(self.discovered_in_project_count, "discovered project count")
        if self.selection_artifact_id is not None:
            text(self.selection_artifact_id, "selection artifact id")


@dataclass(frozen=True)
class CrossProjectSummary:
    """Deterministic cross-project description; no direction claim is made."""

    projects_with_mutation_observation: int
    projects_with_expression_observation: int
    affected_case_total: MetricRecord
    top_project_share: MetricRecord
    expression_median_min: MetricRecord
    expression_median_max: MetricRecord
    coverage_imbalance: bool
    dominance_definition: str
    coverage_imbalance_definition: str
    direction: str
    comparability_status: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        count(self.projects_with_mutation_observation, "projects with mutation observation")
        count(self.projects_with_expression_observation, "projects with expression observation")
        require(all(isinstance(value, MetricRecord) for value in (
            self.affected_case_total, self.top_project_share, self.expression_median_min,
            self.expression_median_max)), "cross-project values must be typed metrics")
        require(self.top_project_share.unit == "share", "dominance share must use the share unit")
        for value in (self.expression_median_min, self.expression_median_max):
            require(value.unit in (None, "log2(UQFPKM+1)"), "expression range must use the expression unit")
        require(type(self.coverage_imbalance) is bool, "coverage imbalance must be bool")
        for name in ("dominance_definition", "coverage_imbalance_definition", "direction", "comparability_status"):
            text(getattr(self, name), name)
        strings(self.notes, "cross-project notes")


@dataclass(frozen=True)
class StatisticalState:
    """The sole canonical scientific state object of a research run."""

    entity: EntityRef
    annotation: GeneAnnotation
    research: ResearchState
    universe: TestedUniverse
    tested_context: TestedContext
    projects: tuple[ProjectState, ...]
    cross_project: CrossProjectSummary
    quality: Quality
    warnings: tuple[str, ...]
    missingness: tuple[str, ...]
    methods: tuple[MethodIdentityRef, ...]
    environment_hash: str
    sources: tuple[ScientificSource, ...]
    operational_sources: tuple[OperationalSource, ...] = ()

    def __post_init__(self) -> None:
        require(isinstance(self.entity, EntityRef) and isinstance(self.annotation, GeneAnnotation)
                and isinstance(self.research, ResearchState) and isinstance(self.universe, TestedUniverse)
                and isinstance(self.tested_context, TestedContext)
                and isinstance(self.cross_project, CrossProjectSummary) and isinstance(self.quality, Quality),
                "invalid state context")
        require(self.entity.gene_id in self.universe.ordered_ids, "state entity outside universe")
        require(self.entity.release == self.universe.release, "state/universe release mismatch")
        require(type(self.projects) is tuple and bool(self.projects)
                and all(isinstance(p, ProjectState) for p in self.projects), "state requires typed project results")
        project_ids = tuple(p.population.frame.project_id for p in self.projects)
        require(project_ids == tuple(sorted(project_ids)), "state projects must be sorted")
        require(len(set(project_ids)) == len(project_ids), "duplicate state project")
        require(project_ids == self.research.projects, "state projects do not match the research scope")
        require(self.tested_context.examined_genes_n >= len(self.universe.ordered_ids),
                "examined gene count below the universe slice")
        require(type(self.sources) is tuple and all(isinstance(s, ScientificSource) for s in self.sources),
                "state sources must be immutable records")
        require(all(s.release == self.entity.release for s in self.sources), "mixed state/source releases")
        require(type(self.operational_sources) is tuple
                and all(isinstance(s, OperationalSource) for s in self.operational_sources), "invalid operational sources")
        require(all(s.source in self.sources for s in self.operational_sources), "unbound operational source")
        strings(self.warnings, "state warnings")
        strings(self.missingness, "state missingness")
        require(type(self.methods) is tuple
                and all(isinstance(m, MethodIdentityRef) for m in self.methods), "state methods must be typed")
        strings(tuple(m.method_id for m in self.methods), "state method ids")
        sha256(self.environment_hash, "state environment hash")
        for project in self.projects:
            for lane_result in (project.mutation, project.expression, project.cnv):
                if isinstance(lane_result, UnavailableLane):
                    continue
                if isinstance(lane_result, MutationCountResult):
                    require(lane_result.entity == self.entity, "mutation entity/state mismatch")
                    for value in (lane_result.affected_cases, lane_result.ssm_coverage_cases):
                        if isinstance(value, ObservedCount):
                            require(set(value.sources) <= set(self.sources), "unbound mutation sources")
                elif isinstance(lane_result, ExpressionSummaryResult):
                    require(lane_result.entity == self.entity, "expression entity/state mismatch")
                    require(set(lane_result.sources) <= set(self.sources), "unbound expression sources")
                else:
                    require(lane_result.entity == self.entity, "CNV entity/state mismatch")
                    require(set(lane_result.sources) <= set(self.sources), "unbound CNV sources")

    @property
    def gene_symbol(self) -> str | None:
        return self.entity.symbol

    def project_ids(self) -> tuple[str, ...]:
        return tuple(project.population.frame.project_id for project in self.projects)


__all__ = [
    "AcquisitionScope",
    "CnvCategory",
    "CnvOccurrence",
    "CnvOccurrenceResult",
    "CrossProjectSummary",
    "ExpressionSummaryResult",
    "ExpressionValue",
    "GeneAnnotation",
    "Lane",
    "MutationCountResult",
    "PopulationRecord",
    "ProjectState",
    "ProviderDiscoveryMetadata",
    "ProviderExpressionSummary",
    "ResearchState",
    "StatisticalState",
    "TestedContext",
    "UnavailableLane",
    "UnavailableStatus",
]
