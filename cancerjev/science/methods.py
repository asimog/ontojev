"""Deterministic scientific methods and real StatisticalState assembly.

Every measured number is produced here from normalized provider records. The
module never calls a provider, never reads raw response bytes, and never lets a
provider ranking score fill a scientific field. Descriptive methods only: no
p-value, no effect size, no biological direction.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

from cancerjev.domain.codecs import STATE_SCHEMA_VERSION
from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    CountMeasurement,
    Coverage,
    EntityRef,
    MethodIdentityRef,
    MethodParameters,
    MethodRef,
    MetricAvailability,
    MetricRecord,
    MissingGroup,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    Quality,
    ScalarMeasurement,
    ScientificSource,
    Sufficiency,
    TestedUniverse,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
)
from cancerjev.domain.scientific import (
    AcquisitionScope,
    CrossProjectSummary,
    ExpressionSummaryResult,
    ExpressionValue,
    GeneAnnotation,
    Lane,
    MutationCountResult,
    PopulationRecord,
    ProjectState,
    ProviderDiscoveryMetadata,
    ProviderExpressionSummary,
    ResearchState,
    StatisticalState,
    TestedContext,
    UnavailableLane,
)
from cancerjev.gdc.parsers import (
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    GeneRecord,
    ProjectCoverage,
    ProjectRecord,
    ProviderSelection,
)
from cancerjev.science.errors import ScienceError as ScienceError
from cancerjev.science.expression import (
    ExpressionObservation,
    expression_observation,
)
from cancerjev.science.expression import (
    Log2Summary as Log2Summary,
)
from cancerjev.science.expression import (
    expression_log2_summary as expression_log2_summary,
)
from cancerjev.science.mutation import MutationObservation, mutation_observation

EXPRESSION_UNIT = "log2(UQFPKM+1)"
EXPRESSION_TRANSFORMATION = "log2(x+1)"
DOMINANCE_SHARE_DEFINITION = "max(affected_case_count) / sum(affected_case_count) over observed projects"
COVERAGE_IMBALANCE_DEFINITION = (
    "true if any project lacks a mutation observation while another has one, or the range of "
    "per-project expression coverage fractions (cases_with_expression / examined_cases) exceeds 0.2, "
    "or any project has zero expression values observed"
)
MUTATION_ABSENCE_SEMANTICS = (
    "An absent project/gene aggregation bucket is NOT_OBSERVED. It is not zero mutation prevalence, "
    "not wildtype, and not a callable negative; no recurrence fraction is computed without a valid "
    "gene-specific denominator."
)
ACQUISITION_COMPLETENESS_DEFINITION = (
    "COMPLETE when every requested provider response for the requested scope was acquired in full; "
    "PARTIAL when any requested aggregation or page was incomplete. This is an acquisition property only."
)
SCIENTIFIC_SUFFICIENCY_DEFINITION = (
    "SUFFICIENT only when acquisition of the requested scope completed and every examined project has an "
    "observed mutation bucket and a fully valid expression measurement set with no missing measurements; "
    "PARTIAL when some requested evidence is missing, unavailable or incomplete; INSUFFICIENT when no "
    "examined project has any observed measurement. Acquisition completeness does not imply sufficiency."
)
COMPARABILITY_STATUSES = ("VERIFIED", "PARTIAL", "UNVERIFIED", "INCOMPATIBLE", "NOT_APPLICABLE")
WITHIN_COHORT_COMPARABILITY = {
    "status": "UNVERIFIED",
    "reason": (
        "GDC harmonization, shared project membership and an empty incompatibility list do not establish "
        "scientific comparability; no cross-workflow or cross-sample comparability has been verified in "
        "this phase."
    ),
}
CROSS_PROJECT_COMPARABILITY = {
    "status": "NOT_APPLICABLE",
    "reason": "A single cohort is examined; no cross-project comparison is made.",
}


@dataclass(frozen=True)
class MethodDefinition:
    method_id: str
    version: str
    purpose: str
    analysis_unit: str
    population_semantics: str
    duplicate_rule: str
    eligibility: str
    minimum_n: str
    sampling_rule: str
    estimator: str
    effect_definition: str | None
    interval_method: str | None
    null_hypothesis: str | None
    correction_family: str | None
    missingness_handling: str
    unsupported_states: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance_requirements: tuple[str, ...]

    def ref(self, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        parameters = parameters or {}
        return {
            "method_id": self.method_id,
            "version": self.version,
            "parameters_hash": hashlib.sha256(canonical_json(parameters)).hexdigest(),
        }


METHODS: dict[str, MethodDefinition] = {
    "MUTATION_AFFECTED_CASE_COUNT_V1": MethodDefinition(
        method_id="MUTATION_AFFECTED_CASE_COUNT_V1", version="1",
        purpose="Per-project count of cases with an SSM in the gene.",
        analysis_unit="case",
        population_semantics=(
            "All cases of the project in the provider mutation-index universe; not a callable-negative "
            "population and not a matched denominator for the gene."
        ),
        duplicate_rule=(
            "Provider-computed unique-case bucket count; local re-derivation requires occurrence rows, "
            "which this phase does not acquire."
        ),
        eligibility="A present aggregation bucket for the project/gene pair.",
        minimum_n="n>=0; a present bucket with doc_count 0 is an observed zero",
        sampling_rule="Complete provider aggregation over the queried gene set; no sampling.",
        estimator="Provider bucket doc_count for the gene within the project.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling=(
            "An absent project or gene bucket is NOT_OBSERVED, never zero, wildtype or a callable negative."
        ),
        unsupported_states=("PARTIAL", "NOT_OBSERVED"),
        provenance_requirements=("counts response artifact hash", "request hash", "parser version", "release identity"),
        limitations=(
            "No matched denominator; no recurrence fraction.",
            "Provider case universe may change with data releases.",
            "Counts cannot distinguish mutation absence from unassayed cases.",
            "DEPRECATED FOR SCIENTIFIC USE: external reconciliation (SCIENTIFIC_RECONCILIATION_FIXTURE "
            "reconciliation_dr46, Data Release 46.0) proved the provider bucket is not a distinct-case "
            "count and not derivable from released occurrence records; retained only for replay of "
            "historical artifacts superseded by MUTATION_AFFECTED_CASE_COUNT_V2.",
        ),
    ),
    "MUTATION_AFFECTED_CASE_COUNT_V2": MethodDefinition(
        method_id="MUTATION_AFFECTED_CASE_COUNT_V2", version="2",
        purpose=(
            "Per-project count of distinct cases with at least one released indexed somatic mutation "
            "affecting the gene, derived from the complete released occurrence record set."
        ),
        analysis_unit="case",
        population_semantics=(
            "All cases of the project appearing in the released occurrence records; occurrence "
            "records are one document per (mutation, case) pair with consequence-annotated genes."
        ),
        duplicate_rule=(
            "Distinct case_id per gene derived locally from validated occurrence records: each record "
            "contributes its case once per distinct annotated gene; occurrence ids are validated for "
            "global uniqueness across the scan and pages are validated as complete before derivation."
        ),
        eligibility="Complete occurrence scan for the declared project (all pages, no short pages).",
        minimum_n="n>=0; a gene absent from a complete scan is an observed zero",
        sampling_rule="Complete deterministic scan of the project's occurrence index; no sampling.",
        estimator="Cardinality of the distinct case_id set annotated to the gene in the complete scan.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling=(
            "An incomplete scan is never persisted; an absent gene in a complete scan is an observed "
            "zero, not NOT_OBSERVED."
        ),
        unsupported_states=("PARTIAL", "NOT_ACQUIRED"),
        limitations=(
            "No matched denominator; no recurrence fraction.",
            "Population is the released occurrence corpus; it excludes variants absent from released "
            "records and may change with data releases.",
            "Counts cannot distinguish mutation absence from unassayed cases.",
        ),
        provenance_requirements=("occurrence page artifact hashes", "request hashes", "parser version",
                                 "release identity"),
    ),
    "PROJECT_SSM_COVERAGE_V1": MethodDefinition(
        method_id="PROJECT_SSM_COVERAGE_V1", version="1",
        purpose="Retain per-project mutation-data availability context.",
        analysis_unit="project",
        population_semantics="All cases in the project's SSM pipeline output.",
        duplicate_rule="One value per project bucket.",
        eligibility="Project present in the unfiltered aggregation.",
        minimum_n="not applicable",
        sampling_rule="Complete unfiltered provider aggregation.",
        estimator="case_with_ssm doc_count and project case count retained separately.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling="Absent project is NOT_OBSERVED; a zero is an observed zero for pipeline availability.",
        unsupported_states=("NOT_OBSERVED",),
        limitations=(
            "Not whole-genome callability.",
            "case_with_ssm is never divided into a callability or recurrence claim.",
        ),
        provenance_requirements=("coverage response artifact hash", "projects response artifact hash", "release identity"),
    ),
    "EXPRESSION_LOG2_SUMMARY_V1": MethodDefinition(
        method_id="EXPRESSION_LOG2_SUMMARY_V1", version="1",
        purpose="Local location and dispersion of per-case expression on the exact examined case set.",
        analysis_unit="case",
        population_semantics="The exact case frame requested from the provider; missing columns are counted, never imputed.",
        duplicate_rule="One value per case column; duplicate rows or columns are parser errors.",
        eligibility="At least one finite value for median/min/max; at least two for sample SD.",
        minimum_n="median n>=1; sample SD n>=2",
        sampling_rule="All cases of the examined frame for the project; no subsampling.",
        estimator="median, sample standard deviation (n-1), minimum and maximum of log2(UQFPKM+1).",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling=(
            "Missing or non-finite cells are excluded from n_finite and counted in n_missing; examined case "
            "columns that the provider did not return are also counted in n_missing and never become zero."
        ),
        unsupported_states=("NOT_OBSERVED", "NOT_ACQUIRED", "INSUFFICIENT"),
        limitations=(
            "Case-level values may reflect a provider-chosen sample per case; sample resolution is UNVERIFIED.",
            "log2(x+1) is a local transform; provider units are UQFPKM.",
        ),
        provenance_requirements=("values TSV artifact hash", "request hash", "parser version", "unit parameter"),
    ),
    "EXPRESSION_PROVIDER_SUMMARY_V1": MethodDefinition(
        method_id="EXPRESSION_PROVIDER_SUMMARY_V1", version="1",
        purpose="Retain the provider's expression median/stddev verbatim as corroborating context.",
        analysis_unit="gene within provider-selected case set",
        population_semantics="Provider-defined set of requested cases with values; exact membership not returned.",
        duplicate_rule="One entry per gene; duplicates are parser errors.",
        eligibility="Gene present in the provider selection response.",
        minimum_n="provider-defined",
        sampling_rule="Provider selection with the documented default min_median_log2_uqfpkm threshold.",
        estimator="Provider log2_uqfpkm_median and log2_uqfpkm_stddev, unchanged.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling="Absent gene is NOT_OBSERVED; the provider may omit genes below its median threshold.",
        unsupported_states=("NOT_OBSERVED",),
        limitations=(
            "Estimator convention is not documented; a live two-case capture is consistent with a population denominator.",
            "Provider summary never drives eligibility, thresholds or policy.",
        ),
        provenance_requirements=("gene_selection response artifact hash", "request hash", "release identity"),
    ),
    "PROJECT_DOMINANCE_V1": MethodDefinition(
        method_id="PROJECT_DOMINANCE_V1", version="1",
        purpose="Descriptive concentration of affected cases across observed projects.",
        analysis_unit="project set",
        population_semantics="Only projects with an observed affected-case count.",
        duplicate_rule="One count per project.",
        eligibility="At least two observed projects and a positive total.",
        minimum_n=">=2 observed projects",
        sampling_rule="All observed projects in scope.",
        estimator=DOMINANCE_SHARE_DEFINITION,
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling="NOT_APPLICABLE when eligibility fails; no extrapolation to unobserved projects.",
        unsupported_states=("NOT_APPLICABLE",),
        limitations=(
            "Dominance can be produced by coverage imbalance and implies no mechanism.",
            "A share is descriptive and is not an effect size.",
        ),
        provenance_requirements=("counts response artifact hash", "scope project list"),
    ),
    "EXPRESSION_TUKEY_TAIL_V1": MethodDefinition(
        method_id="EXPRESSION_TUKEY_TAIL_V1", version="1",
        purpose="Describe within-gene held expression observations outside fixed Tukey fences.",
        analysis_unit="case", population_semantics="Finite case-labelled values in the exact held frame.",
        duplicate_rule="One retained value per case; duplicate columns are parser errors.",
        eligibility="At least 20 finite values and positive IQR.", minimum_n="n>=20",
        sampling_rule="All finite retained values; no resampling.",
        estimator="Q1/Q3 by h=(n-1)p linear interpolation; fences Q1/Q3 +/- 1.5xIQR.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling="Missing values are enumerated and never imputed.",
        unsupported_states=("INSUFFICIENT", "DEGENERATE_REFERENCE", "NOT_OBSERVED"),
        limitations=("Within-gene descriptive tail only; not differential expression or a p-value.",),
        provenance_requirements=("expression value sources", "population frame", "fixed parameters"),
    ),
    "CNV_INDEXED_POSITIVE_CASES_V1": MethodDefinition(
        method_id="CNV_INDEXED_POSITIVE_CASES_V1", version="1",
        purpose="Count distinct positive cases per exact provider CNV category.",
        analysis_unit="case", population_semantics="Cases with a returned positive indexed occurrence.",
        duplicate_rule="Unique case within exact raw category; retain cross-category conflicts.",
        eligibility="Complete fixed project/gene occurrence query.", minimum_n="n>=0",
        sampling_rule="All rows in the complete bounded survivor query.",
        estimator="Cardinality of the case-id set for each exact provider category.",
        effect_definition=None, interval_method=None, null_hypothesis=None, correction_family=None,
        missingness_handling="Absence is not neutral or negative; missing sample IDs stay explicit.",
        unsupported_states=("PARTIAL", "UNAVAILABLE"),
        limitations=("Category sets may overlap and are not summed; caller scales are not pooled.",),
        provenance_requirements=("CNV occurrence sources", "population frame", "caller context"),
    ),
}


@dataclass(frozen=True)
class ProjectEvidence:
    project_id: str
    mutation_observed: bool
    expression_observed: bool
    examined_cases: int
    cases_with_expression: int | None
    missing_measurements: int | None


def scientific_sufficiency(rows: list[ProjectEvidence], acquisition_complete: bool) -> str:
    """See SCIENTIFIC_SUFFICIENCY_DEFINITION. Acquisition is a separate property."""
    if not rows:
        return "INSUFFICIENT"
    if not any(row.mutation_observed or row.expression_observed for row in rows):
        return "INSUFFICIENT"
    if not acquisition_complete:
        return "PARTIAL"
    if any(row.missing_measurements is not None and row.missing_measurements > 0 for row in rows):
        return "PARTIAL"
    if not all(row.mutation_observed for row in rows):
        return "PARTIAL"
    if not all(row.expression_observed for row in rows):
        return "PARTIAL"
    return "SUFFICIENT"


def project_dominance(counts: dict[str, int]) -> tuple[float | None, str]:
    observed = {project: count for project, count in counts.items() if count is not None}
    if len(observed) < 2:
        return None, "NOT_APPLICABLE"
    total = sum(observed.values())
    if total <= 0:
        return None, "NOT_APPLICABLE"
    return max(observed.values()) / total, "OBSERVED"


def coverage_imbalance(rows: list[ProjectEvidence]) -> bool:
    """Deterministic flag: see COVERAGE_IMBALANCE_DEFINITION."""
    mutation_observed = [row.mutation_observed for row in rows]
    if any(mutation_observed) and not all(mutation_observed):
        return True
    fractions = [
        row.cases_with_expression / row.examined_cases
        for row in rows if row.examined_cases and row.cases_with_expression is not None
    ]
    if any(row.cases_with_expression == 0 for row in rows if row.cases_with_expression is not None):
        return True
    if fractions and (max(fractions) - min(fractions)) > 0.2:
        return True
    return False


@dataclass(frozen=True)
class ProjectFrame:
    project_id: str
    project_record: ProjectRecord
    cases: list[CaseRecord]
    frame_hash: str
    expression_coverage: ExpressionAvailability | None
    provider_selection: ProviderSelection | None
    expression_values: ExpressionValues | None
    workflows: list[str]
    strategies: list[str]
    discovery_hits: dict[str, DiscoveryHit]
    provider_summary_unavailable_reason: str | None = None


def _sample_type_counts(cases: list[CaseRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for sample_type in set(case.sample_types):
            counts[sample_type] = counts.get(sample_type, 0) + 1
    return dict(sorted(counts.items()))


# ------------------------------------------------------- typed method identity


def _parameters_dict(parameters: MethodParameters | None) -> dict[str, Any]:
    if parameters is None:
        return {}
    return {key: value for key, value in asdict(parameters).items() if value is not None}


def _method_ref(method_id: str, unit: Unit, *, parameters: MethodParameters | None = None,
                transform: str = "identity") -> MethodRef:
    definition = METHODS[method_id]
    return MethodRef(method_id, definition.version, unit, parameters or MethodParameters(),
                     definition.duplicate_rule, transform, definition.estimator,
                     definition.missingness_handling, definition.limitations)


MUTATION_COUNT_METHOD = _method_ref("MUTATION_AFFECTED_CASE_COUNT_V1", Unit.CASES)
MUTATION_DISTINCT_CASE_COUNT_METHOD = _method_ref(
    "MUTATION_AFFECTED_CASE_COUNT_V2", Unit.CASES)
MUTATION_SCAN_SEMANTICS = (
    "Affected-case counts are derived locally from the complete per-project released occurrence "
    "scan: each validated record contributes its case once per distinct annotated gene, and a gene "
    "absent from a complete scan is an observed zero, not NOT_OBSERVED and not a callable negative; "
    "no recurrence fraction is computed without a valid gene-specific denominator."
)
SSM_COVERAGE_METHOD = _method_ref("PROJECT_SSM_COVERAGE_V1", Unit.CASES)
EXPRESSION_SD_METHOD = _method_ref("EXPRESSION_LOG2_SUMMARY_V1", Unit.LOG2_UQFPKM_PLUS_ONE,
                                   parameters=MethodParameters(ddof=1, pseudocount=1.0),
                                   transform=EXPRESSION_TRANSFORMATION)


def _state_methods() -> tuple[MethodIdentityRef, ...]:
    return tuple(
        MethodIdentityRef(ref["method_id"], ref["version"], ref["parameters_hash"])
        for ref in (definition.ref() for definition in METHODS.values())
    )


def _environment_hash() -> str:
    return hashlib.sha256(canonical_json({
        "state_schema_version": STATE_SCHEMA_VERSION,
        "methods": {method_id: definition.version for method_id, definition in METHODS.items()},
        "parser_version": "gdc-parser-v1",
    })).hexdigest()


# ------------------------------------------------------------ typed assembly


def _unique_sources(sources: tuple[OperationalSource, ...]) -> tuple[ScientificSource, ...]:
    result: list[ScientificSource] = []
    for operational in sources:
        if operational.source not in result:
            result.append(operational.source)
    return tuple(result)


def _endpoint_sources(sources: tuple[OperationalSource, ...], endpoint: str) -> tuple[ScientificSource, ...]:
    return _unique_sources(tuple(s for s in sources if s.source.endpoint == endpoint))


def _entity(gene: GeneRecord, release: str) -> EntityRef:
    return EntityRef(gene.gene_id, gene.symbol, release)


def _population_frame(frame: ProjectFrame, cohort: str) -> PopulationFrame:
    return PopulationFrame(
        cohort_id=cohort, project_id=frame.project_id, unit=PopulationUnit.CASE,
        examined_ids=tuple(sorted(case.case_id for case in frame.cases)),
        eligible_ids=None, selection_rule="ALL_CASES_PAGINATED",
    )


def _population(frame: ProjectFrame, population_frame: PopulationFrame, gene_id: str) -> PopulationRecord:
    return PopulationRecord(
        population_id=f"POP-{gene_id}-{frame.project_id}",
        frame=population_frame,
        program=frame.project_record.program_name,
        provider_reported_cases=frame.project_record.case_count,
        frame_hash=frame.frame_hash,
        workflows=tuple(sorted(frame.workflows)),
        sample_types=tuple(_sample_type_counts(frame.cases).items()),
        selection_method="ALL_CASES_PAGINATED",
        selection_version="1",
        harmonization_context=(
            f"{frame.project_id}|{','.join(frame.workflows) or 'UNKNOWN_WORKFLOW'}|UQFPKM"
        ),
        excluded_counts=(),
    )


MUTATION_INFERENCE_DECISION_ID = "DEFER_WITH_JUSTIFICATION"
MUTATION_INFERENCE_DECISION_VERSION = "1"
MUTATION_INFERENCE_DECISION = (
    "Background-model driver testing (MutSigCV-class) requires patient covariate inputs "
    "(mutation-rate, replication-timing and expression covariates) that the API-only plane does "
    "not supply and the open-file admission gate does not currently admit; descriptive "
    "composition and recurrence are reported without p/q values."
)


def _mutation_quality(observation: MutationObservation) -> Quality:
    acquisition = Acquisition.COMPLETE if observation.acquisition_complete else Acquisition.PARTIAL
    if observation.affected_cases is not None:
        sufficiency = Sufficiency.SUFFICIENT if acquisition == Acquisition.COMPLETE else Sufficiency.PARTIAL
    elif observation.ssm_coverage_cases is not None:
        sufficiency = Sufficiency.PARTIAL
    else:
        sufficiency = Sufficiency.INSUFFICIENT
    return Quality(acquisition, sufficiency, Compatibility.UNVERIFIED,
                   (MUTATION_ABSENCE_SEMANTICS, ACQUISITION_COMPLETENESS_DEFINITION))


@dataclass(frozen=True)
class ScannedMutationCounts:
    """Corrected V2 distinct-case counts for one project from a complete occurrence scan.

    Only observed occurrence genes appear in the map; a gene absent from a
    complete scan is an observed zero, never NOT_OBSERVED and never a callable
    negative. ``source`` is the aggregate immutable scan source; no aggregation
    bucket value contributes to any count.
    """

    project_id: str
    distinct_cases_per_gene: Mapping[str, int]
    source: OperationalSource


def _coverage_measurement(project_id: str, population_frame: PopulationFrame,
                          coverage: ProjectCoverage,
                          coverage_source: ScientificSource | None,
                          coverage_complete: bool) -> CountMeasurement:
    raw_coverage = coverage.case_with_ssm.get(project_id)
    if raw_coverage is None:
        return UnavailableMeasurement(UnavailableStatus.NOT_OBSERVED, "PROJECT_NOT_IN_COVERAGE",
                                      Unit.CASES, population_frame)
    if raw_coverage == 0 and not coverage_complete:
        return UnavailableMeasurement(UnavailableStatus.UNAVAILABLE, "PARTIAL_AGGREGATION",
                                      Unit.CASES, population_frame)
    sources = () if coverage_source is None else (coverage_source,)
    return ObservedCount(raw_coverage, Unit.CASES, population_frame, SSM_COVERAGE_METHOD, sources)


def scanned_mutation_result(*, project_id: str, gene: GeneRecord,
                            population_frame: PopulationFrame, distinct_cases: int, release: str,
                            coverage: ProjectCoverage, coverage_source: ScientificSource,
                            coverage_complete: bool,
                            scan_source: OperationalSource) -> MutationCountResult:
    """V2 mutation outcome from a complete occurrence scan (the scientific path)."""
    affected: CountMeasurement = ObservedCount(
        distinct_cases, Unit.CASES, population_frame, MUTATION_DISTINCT_CASE_COUNT_METHOD,
        (scan_source.source,))
    ssm = _coverage_measurement(project_id, population_frame, coverage, coverage_source,
                                coverage_complete)
    quality = Quality(
        Acquisition.COMPLETE,
        Sufficiency.SUFFICIENT if coverage_complete else Sufficiency.PARTIAL,
        Compatibility.UNVERIFIED, (MUTATION_SCAN_SEMANTICS, ACQUISITION_COMPLETENESS_DEFINITION))
    return MutationCountResult(affected, ssm, coverage_complete, population_frame, quality,
                               _entity(gene, release))


def _mutation_result(frame: ProjectFrame, population_frame: PopulationFrame, gene: GeneRecord,
                     counts: GeneCaseCounts | None, coverage: ProjectCoverage,
                     sources: tuple[OperationalSource, ...], release: str,
                     scan_counts: ScannedMutationCounts | None = None) -> MutationCountResult:
    """One mutation lane outcome from either the V2 scan or the legacy bucket contract.

    Exactly one input is supplied per state. The scan path is the scientific
    path; the bucket path is the documented V1 contract retained for contract
    tests and never admits an affected-case value in a live run.
    """
    coverage_sources = _endpoint_sources(sources, "/analysis/mutated_cases_count_by_project")
    coverage_source = coverage_sources[0] if coverage_sources else None
    if scan_counts is not None:
        if coverage_source is None:
            raise ScienceError("MISSING_COVERAGE_SOURCE",
                               "scan-derived mutation result requires the coverage source")
        return scanned_mutation_result(
            project_id=frame.project_id, gene=gene, population_frame=population_frame,
            distinct_cases=scan_counts.distinct_cases_per_gene.get(gene.gene_id, 0),
            release=release, coverage=coverage, coverage_source=coverage_source,
            coverage_complete=coverage.complete, scan_source=scan_counts.source)
    if counts is None:
        raise ScienceError("MISSING_COUNTS_INPUT", "the bucket contract requires counts")
    observation = mutation_observation(frame.project_id, gene.gene_id, counts, coverage)
    count_sources = _endpoint_sources(sources, "/analysis/top_cases_counts_by_genes")
    if observation.affected_cases is None:
        status = (UnavailableStatus.UNAVAILABLE if observation.availability == "PARTIAL"
                  else UnavailableStatus.NOT_OBSERVED)
        affected: CountMeasurement = UnavailableMeasurement(
            status, observation.reason or "GENE_BUCKET_ABSENT", Unit.CASES, population_frame)
    elif observation.affected_cases == 0 and not counts.complete:
        affected = UnavailableMeasurement(
            UnavailableStatus.UNAVAILABLE, "PARTIAL_AGGREGATION", Unit.CASES, population_frame)
    else:
        affected = ObservedCount(observation.affected_cases, Unit.CASES, population_frame,
                                 MUTATION_COUNT_METHOD, count_sources)
    ssm = _coverage_measurement(frame.project_id, population_frame, coverage, coverage_source,
                                coverage.complete)
    return MutationCountResult(affected, ssm, coverage.complete, population_frame,
                               _mutation_quality(observation), _entity(gene, release))


def _expression_quality(observation: ExpressionObservation) -> Quality:
    acquisition = (Acquisition.COMPLETE if observation.returned_case_columns is not None
                   else Acquisition.NOT_ACQUIRED)
    if observation.local_availability == "OBSERVED":
        sufficiency = Sufficiency.SUFFICIENT
    elif observation.local_availability == "PARTIAL":
        sufficiency = Sufficiency.PARTIAL
    else:
        sufficiency = Sufficiency.INSUFFICIENT
    return Quality(acquisition, sufficiency, Compatibility.UNVERIFIED,
                   (EXPRESSION_SD_METHOD.missingness_rule, EXPRESSION_SD_METHOD.limitations[0]))


def expression_result(frame: ProjectFrame, population_frame: PopulationFrame, gene: GeneRecord,
                      observation: ExpressionObservation, release: str,
                      sources: tuple[OperationalSource, ...],
                      ) -> ExpressionSummaryResult | UnavailableLane:
    if observation.local is None:
        status = (UnavailableStatus.NOT_ACQUIRED if observation.local_availability == "NOT_ACQUIRED"
                  else UnavailableStatus.NOT_OBSERVED)
        reason = observation.provider_unavailable_reason or (
            "EXPRESSION_VALUES_NOT_ACQUIRED" if status == UnavailableStatus.NOT_ACQUIRED
            else "GENE_ABSENT_FROM_VALUES"
        )
        return UnavailableLane(Lane.EXPRESSION, True, status, reason)
    summary = observation.local
    values_row = frame.expression_values.values.get(gene.gene_id) if frame.expression_values else None
    if values_row is None:
        return UnavailableLane(Lane.EXPRESSION, True, UnavailableStatus.NOT_OBSERVED, "GENE_ABSENT_FROM_VALUES")
    expression_sources = _endpoint_sources(sources, "/gene_expression/values")
    returned_ids = tuple(sorted(values_row))
    valid_ids = tuple(sorted(case_id for case_id, value in values_row.items() if value is not None))
    missing: list[MissingGroup] = []
    not_returned = tuple(sorted(set(population_frame.examined_ids) - set(returned_ids)))
    if not_returned:
        missing.append(MissingGroup("CASE_COLUMN_NOT_RETURNED", not_returned))
    missing_cells = tuple(sorted(case_id for case_id, value in values_row.items() if value is None))
    if missing_cells:
        missing.append(MissingGroup("VALUE_MISSING_OR_NONFINITE", missing_cells))
    assay_available = tuple(
        sorted(case_id for case_id in population_frame.examined_ids
               if frame.expression_coverage is not None
               and frame.expression_coverage.cases.get(case_id) is True)
    )
    coverage_record = Coverage(population_frame, returned_ids, valid_ids, tuple(missing), assay_available)
    values = tuple(ExpressionValue(case_id, float(value))
                   for case_id, value in sorted(values_row.items()) if value is not None)

    def measurement(value: float | None, reason: str) -> ScalarMeasurement:
        if value is None:
            return UnavailableMeasurement(UnavailableStatus.INSUFFICIENT, reason,
                                          Unit.LOG2_UQFPKM_PLUS_ONE, population_frame)
        return ObservedScalar(value, Unit.LOG2_UQFPKM_PLUS_ONE, population_frame,
                              EXPRESSION_SD_METHOD, expression_sources)

    return ExpressionSummaryResult(
        values, coverage_record,
        measurement(summary.median, "NO_FINITE_VALUES"),
        measurement(summary.sample_sd, "INSUFFICIENT_N"),
        measurement(summary.minimum, "NO_FINITE_VALUES"),
        measurement(summary.maximum, "NO_FINITE_VALUES"),
        _expression_quality(observation), expression_sources, _entity(gene, release),
    )


def _provider_expression(observation: ExpressionObservation) -> ProviderExpressionSummary | None:
    if observation.provider is not None:
        return ProviderExpressionSummary(observation.provider.median, observation.provider.stddev,
                                         "GENE_SELECTION", "INFERRED_POPULATION_SD_UNVERIFIED", None)
    if observation.provider_unavailable_reason is not None:
        return ProviderExpressionSummary(None, None, "GENE_SELECTION",
                                         "INFERRED_POPULATION_SD_UNVERIFIED",
                                         observation.provider_unavailable_reason)
    return None


def _metric_record(value: float | int | None, unit: str, availability: str,
                   reason: str | None = None) -> MetricRecord:
    if availability == "OBSERVED":
        # Call sites mark a metric OBSERVED only with a present value; MetricRecord
        # validates that an observed metric carries a numeric value.
        return MetricRecord.observed_value(cast(float | int, value), unit)
    return MetricRecord.unavailable(unit, MetricAvailability(availability), reason)


def _acquisition_scope(scope_meta: dict[str, Any]) -> AcquisitionScope:
    acquisition = (scope_meta.get("research_spec") or {}).get("acquisition") or {}
    return AcquisitionScope(
        case_page_size=int(acquisition["case_page_size"]),
        case_batch_size=int(acquisition["case_batch_size"]),
        max_cohort_cases=int(acquisition["max_cohort_cases"]),
        discovery_gene_limit=int(acquisition["discovery_gene_limit"]),
        count_gene_limit=int(acquisition["count_gene_limit"]),
        candidate_gene_limit=int(acquisition["candidate_gene_limit"]),
        expression_file_sample_size=int(acquisition["expression_file_sample_size"]),
    )


SELECTION_BIAS = (
    "Genes are discovered from the provider top-mutated ranking for the single examined cohort "
    "and selected by provider rank; this is selection-biased and does not represent an unbiased "
    "genome-wide scan."
)


def compute_statistical_state(
    *,
    gene: GeneRecord,
    frames: list[ProjectFrame],
    coverage: ProjectCoverage,
    sources: tuple[OperationalSource, ...],
    warnings: list[str],
    scope_meta: dict[str, Any],
    discovery_meta: dict[str, Any],
    counts: GeneCaseCounts | None = None,
    scan_counts_by_project: Mapping[str, ScannedMutationCounts] | None = None,
) -> StatisticalState:
    """Assemble the sole canonical StatisticalState from typed lane results.

    Provider responses, request/response hashes, parser version and operational
    attempt/artifact links arrive as typed source records. No provider ranking
    score and no operational id fills a measured field or scientific identity.

    Exactly one mutation-count input is required: corrected V2 per-project scan
    counts (the scientific path) or the legacy indexed bucket contract retained
    for its contract tests.
    """
    if (counts is None) == (scan_counts_by_project is None):
        raise ScienceError("INVALID_MUTATION_INPUT",
                           "exactly one of counts or scan_counts_by_project is required")
    ordered = sorted(frames, key=lambda frame: frame.project_id)
    if not ordered:
        raise ScienceError("EMPTY_COHORT_FRAME", "statistical state requires at least one project frame")
    project_ids = tuple(frame.project_id for frame in ordered)
    if len(set(project_ids)) != len(project_ids):
        raise ScienceError("DUPLICATE_PROJECT_FRAME", "duplicate project frame in statistical state")
    release = scope_meta["gdc_release"]
    cohort = scope_meta["cohort"]
    entity = _entity(gene, release)

    project_states: list[ProjectState] = []
    evidence_rows: list[ProjectEvidence] = []
    medians: list[float] = []
    projects_with_expression = 0
    missingness: list[str] = []
    observed_affected: dict[str, int] = {}
    for frame in ordered:
        population_frame = _population_frame(frame, cohort)
        population = _population(frame, population_frame, gene.gene_id)
        scan_counts = (None if scan_counts_by_project is None
                       else scan_counts_by_project.get(frame.project_id))
        if scan_counts_by_project is not None and scan_counts is None:
            raise ScienceError("MISSING_SCAN_COUNTS",
                               f"no occurrence-scan counts for project {frame.project_id}")
        mutation_result = _mutation_result(frame, population_frame, gene, counts, coverage,
                                           sources, release, scan_counts)
        observation = expression_observation(
            project_id=frame.project_id, gene_id=gene.gene_id,
            case_ids=tuple(case.case_id for case in frame.cases),
            coverage=frame.expression_coverage, values=frame.expression_values,
            provider=frame.provider_selection,
            provider_unavailable_reason=frame.provider_summary_unavailable_reason,
        )
        missingness.extend(observation.missingness)
        expression_summary = expression_result(
            frame, population_frame, gene, observation, release, sources)
        if observation.local is not None and observation.local.median is not None:
            medians.append(observation.local.median)
            projects_with_expression += 1
        affected = mutation_result.affected_cases
        if isinstance(affected, ObservedCount):
            observed_affected[frame.project_id] = affected.value
        hit = frame.discovery_hits.get(gene.gene_id)
        discovery = (ProviderDiscoveryMetadata(hit.rank, hit.score, "MUTATION_DISCOVERY_V1",
                                               "selection metadata only")
                     if hit is not None else None)
        project_states.append(ProjectState(population, mutation_result, expression_summary,
                                           _provider_expression(observation), discovery))
        evidence_rows.append(ProjectEvidence(
            frame.project_id, isinstance(affected, ObservedCount),
            observation.availability == "OBSERVED", len(frame.cases),
            observation.cases_with_expression, observation.missing_measurements,
        ))

    dominance, dominance_availability = project_dominance(observed_affected)
    state_warnings = list(warnings)
    if scan_counts_by_project is not None:
        acquisition_complete = coverage.complete
    else:
        assert counts is not None
        acquisition_complete = counts.complete and coverage.complete
        if not counts.complete:
            state_warnings.append(f"mutation counts partial: {', '.join(counts.partial_reasons)}")
    sufficiency = scientific_sufficiency(evidence_rows, acquisition_complete)
    projects_with_mutation = len(observed_affected)
    if not coverage.complete:
        state_warnings.append(f"mutation coverage partial: {', '.join(coverage.partial_reasons)}")

    acquisition_scope = _acquisition_scope(scope_meta)
    selected_ids = tuple(discovery_meta["selected_gene_ids"])
    if not selected_ids:
        raise ScienceError("MISSING_TESTED_UNIVERSE", "discovery metadata has no selected genes")
    universe = TestedUniverse(
        ordered_ids=selected_ids, source="GDC_MUTATION_DISCOVERY", release=release,
        filter_description=discovery_meta["ranking_rule"], order="PROVIDER_RANK_ASC",
        offset=0, requested_limit=acquisition_scope.candidate_gene_limit,
        reported_total=len(selected_ids), complete=True,
    )
    tested_context = TestedContext(
        examined_genes_hash=discovery_meta["examined_genes_hash"],
        examined_genes_n=discovery_meta["examined_genes_n"],
        rank_in_lane=discovery_meta["rank_in_lane"],
        selection_rule=discovery_meta["ranking_rule"], selection_bias=SELECTION_BIAS,
        discovered_in_project_count=discovery_meta["observed_in_project_count"],
        selection_artifact_id=discovery_meta.get("examined_genes_ref"),
    )
    research = ResearchState(
        spec_id=scope_meta["spec_id"], domain=scope_meta["domain"], cohort=cohort,
        project_id=scope_meta["project_id"],
        cohort_selection_rule=scope_meta["cohort_selection_rule"],
        gene_selection_rule=scope_meta["gene_selection_rule"],
        examined_case_frame=scope_meta.get("examined_case_frame", "ALL_CASES_PAGINATED"),
        acquisition=acquisition_scope,
        modalities=("mutation_counts", "expression_summary"),
        programs=tuple(sorted({frame.project_record.program_name for frame in ordered
                               if frame.project_record.program_name})),
        projects=project_ids,
        workflows=tuple(sorted({workflow for frame in ordered for workflow in frame.workflows})),
        sample_types=tuple(sorted({sample_type for frame in ordered
                                   for sample_type in _sample_type_counts(frame.cases)})),
        sample_type_counts=tuple(
            (frame.project_id, tuple(_sample_type_counts(frame.cases).items())) for frame in ordered
        ),
        comparability_statuses=COMPARABILITY_STATUSES,
        within_cohort_status=WITHIN_COHORT_COMPARABILITY["status"],
        within_cohort_reason=WITHIN_COHORT_COMPARABILITY["reason"],
        cross_project_status=CROSS_PROJECT_COMPARABILITY["status"],
        cross_project_reason=CROSS_PROJECT_COMPARABILITY["reason"],
    )
    cross_project = CrossProjectSummary(
        projects_with_mutation_observation=projects_with_mutation,
        projects_with_expression_observation=projects_with_expression,
        affected_case_total=_metric_record(
            sum(observed_affected.values()) if observed_affected else None, "cases",
            "OBSERVED" if observed_affected else "NOT_OBSERVED",
            None if observed_affected else "NO_OBSERVED_PROJECTS",
        ),
        top_project_share=_metric_record(dominance, "share", dominance_availability,
                                         None if dominance is not None else "INSUFFICIENT_OBSERVED_PROJECTS"),
        expression_median_min=_metric_record(min(medians) if medians else None, EXPRESSION_UNIT,
                                             "OBSERVED" if medians else "NOT_OBSERVED"),
        expression_median_max=_metric_record(max(medians) if medians else None, EXPRESSION_UNIT,
                                             "OBSERVED" if medians else "NOT_OBSERVED"),
        coverage_imbalance=coverage_imbalance(evidence_rows),
        dominance_definition=DOMINANCE_SHARE_DEFINITION,
        coverage_imbalance_definition=COVERAGE_IMBALANCE_DEFINITION,
        direction="NOT_EXAMINED", comparability_status="NOT_APPLICABLE", notes=(),
    )
    quality = Quality(
        Acquisition.COMPLETE if acquisition_complete else Acquisition.PARTIAL,
        Sufficiency(sufficiency), Compatibility.UNVERIFIED,
        (ACQUISITION_COMPLETENESS_DEFINITION, SCIENTIFIC_SUFFICIENCY_DEFINITION,
         WITHIN_COHORT_COMPARABILITY["reason"]),
    )
    return StatisticalState(
        entity=entity,
        annotation=GeneAnnotation(gene.biotype, gene.is_cancer_gene_census, None,
                                  "not observed in admitted endpoints"),
        research=research, universe=universe, tested_context=tested_context,
        projects=tuple(project_states), cross_project=cross_project, quality=quality,
        warnings=tuple(state_warnings), missingness=tuple(missingness),
        methods=_state_methods(), environment_hash=_environment_hash(),
        sources=_unique_sources(sources), operational_sources=sources,
    )
