"""Deterministic scientific methods and real StatisticalState assembly.

Every measured number is produced here from normalized provider records. The
module never calls a provider, never reads raw response bytes, and never lets a
provider ranking score fill a scientific field. Descriptive methods only: no
p-value, no effect size, no biological direction.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.events import canonical_json
from cancerjev.domain.identity import content_hash, statistical_state_identity_payload
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

STATE_SCHEMA_VERSION = 2
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


class ScienceError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


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
        limitations=(
            "No matched denominator; no recurrence fraction.",
            "Provider case universe may change with data releases.",
            "Counts cannot distinguish mutation absence from unassayed cases.",
        ),
        provenance_requirements=("counts response artifact hash", "request hash", "parser version", "release identity"),
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
}


def metric(name: str, value: float | int | None, unit: str, *, availability: str = "OBSERVED",
           reason_code: str | None = None, observation_ref: str | None = None) -> dict[str, Any]:
    if value is not None and availability != "OBSERVED":
        raise ScienceError("INVALID_METRIC", f"{name}: value present with availability {availability}")
    if value is not None:
        number = float(value)
        if not math.isfinite(number):
            raise ScienceError("NONFINITE_METRIC", f"{name}: {value!r}")
        value = int(value) if float(value).is_integer() and unit in {"cases", "count"} else number
    return {
        "name": name, "value": value, "unit": unit, "availability": availability,
        "reason_code": reason_code, "observation_ref": observation_ref,
    }


@dataclass(frozen=True)
class Log2Summary:
    median: float | None
    sample_sd: float | None
    minimum: float | None
    maximum: float | None
    n_finite: int
    n_missing: int
    n_returned: int
    availability: str


def expression_log2_summary(row: dict[str, float | None], *, missing_case_columns: int = 0) -> Log2Summary:
    """Summarize one gene row over the examined case set.

    ``row`` holds only the case columns the provider returned. ``missing_case_columns``
    counts examined cases whose column was not returned at all; those remain visible in
    ``n_missing`` so a fully valid returned subset can never report zero missingness.
    """
    finite: list[float] = []
    missing_cells = 0
    for value in row.values():
        if value is None:
            missing_cells += 1
            continue
        if value < 0:
            raise ScienceError("NEGATIVE_EXPRESSION", f"UQFPKM must be nonnegative, saw {value!r}")
        finite.append(math.log2(value + 1.0))
    missing = missing_cells + max(0, missing_case_columns)
    if not finite:
        return Log2Summary(None, None, None, None, 0, missing, len(row), "INSUFFICIENT")
    median = statistics.median(finite)
    sample_sd = statistics.stdev(finite) if len(finite) >= 2 else None
    if len(finite) < 2:
        availability = "INSUFFICIENT"
    elif missing:
        availability = "PARTIAL"
    else:
        availability = "OBSERVED"
    return Log2Summary(median, sample_sd, min(finite), max(finite), len(finite), missing,
                       len(row), availability)


def scientific_sufficiency(rows: list[dict[str, Any]], acquisition_complete: bool) -> str:
    """See SCIENTIFIC_SUFFICIENCY_DEFINITION. Acquisition is a separate property."""
    if not rows:
        return "INSUFFICIENT"
    if not any(row["mutation_observed"] or row["expression_observed"] for row in rows):
        return "INSUFFICIENT"
    if not acquisition_complete:
        return "PARTIAL"
    if any((row["missing_measurements"] or 0) > 0 for row in rows):
        return "PARTIAL"
    if not all(row["mutation_observed"] for row in rows):
        return "PARTIAL"
    if not all(row["expression_observed"] for row in rows):
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


def coverage_imbalance(rows: list[dict[str, Any]]) -> bool:
    """Deterministic flag: see COVERAGE_IMBALANCE_DEFINITION."""
    mutation_observed = [row["mutation_observed"] for row in rows]
    if any(mutation_observed) and not all(mutation_observed):
        return True
    fractions = [
        row["cases_with_expression"] / row["examined_cases"]
        for row in rows if row["examined_cases"] and row["cases_with_expression"] is not None
    ]
    if any(row["cases_with_expression"] == 0 for row in rows if row["cases_with_expression"] is not None):
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


def _source_projection(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": source["endpoint"],
        "request_hash": source["normalized_request_hash"],
        "response_sha256": source["response_sha256"],
        "parser_version": source["parser_version"],
        "completeness": source["completeness"],
        "source_release": source["source_release"],
    }


def build_statistical_state(
    *,
    run_id: str,
    state_id: str,
    created_at: str,
    gene: GeneRecord,
    frames: list[ProjectFrame],
    counts: GeneCaseCounts,
    coverage: ProjectCoverage,
    sources: list[dict[str, Any]],
    warnings: list[str],
    scope_meta: dict[str, Any],
    discovery_meta: dict[str, Any],
) -> dict[str, Any]:
    ordered = sorted(frames, key=lambda frame: frame.project_id)
    populations: list[dict[str, Any]] = []
    mutation_results: list[dict[str, Any]] = []
    expression_results: list[dict[str, Any]] = []
    imbalance_rows: list[dict[str, Any]] = []
    sufficiency_rows: list[dict[str, Any]] = []
    missingness: list[str] = []
    observed_affected: dict[str, int] = {}

    for frame in ordered:
        population_id = f"POP-{gene.gene_id}-{frame.project_id}"
        examined = len(frame.cases)
        populations.append({
            "population_id": population_id,
            "definition": "All cases of the project as returned by the complete case frame.",
            "program": frame.project_record.program_name,
            "project": frame.project_id,
            "modality": "mutation+expression",
            "sample_type": None,
            "workflow": ",".join(frame.workflows) if frame.workflows else None,
            "pipeline_version": None,
            "eligible_n": frame.project_record.case_count,
            "examined_n": examined,
            "excluded_counts_by_reason": {},
            "case_set_artifact": None,
            "case_set_hash": frame.frame_hash,
            "sample_mapping_artifact": None,
            "selection_method": "ALL_CASES_PAGINATED",
            "selection_version": "1",
            "sweep_offset": None,
            "completeness": "COMPLETE",
            "harmonization_context": (
                f"{frame.project_id}|{','.join(frame.workflows) or 'UNKNOWN_WORKFLOW'}|UQFPKM"
            ),
        })

        project_counts = counts.projects.get(frame.project_id)
        affected: int | None = None
        mutation_availability = "NOT_OBSERVED"
        mutation_reason = "PROJECT_NOT_IN_AGGREGATION"
        if project_counts is not None:
            if gene.gene_id in project_counts:
                affected = project_counts[gene.gene_id]
                mutation_availability = "OBSERVED"
                mutation_reason = None
                observed_affected[frame.project_id] = affected
            else:
                mutation_reason = "GENE_BUCKET_ABSENT"
        if not counts.complete and mutation_availability != "OBSERVED":
            mutation_availability = "PARTIAL"
        discovery = frame.discovery_hits.get(gene.gene_id)
        mutation_results.append({
            "project_id": frame.project_id,
            "population_id": population_id,
            "examined_cases": metric("examined_cases", examined, "cases"),
            "affected_case_count": metric(
                "affected_case_count", affected, "cases", availability=mutation_availability,
                reason_code=mutation_reason,
            ),
            "project_case_with_ssm": metric(
                "project_case_with_ssm", coverage.case_with_ssm.get(frame.project_id), "cases",
                availability="OBSERVED" if frame.project_id in coverage.case_with_ssm else "NOT_OBSERVED",
                reason_code=None if frame.project_id in coverage.case_with_ssm else "PROJECT_NOT_IN_COVERAGE",
            ),
            "project_case_count": metric(
                "project_case_count", frame.project_record.case_count, "cases",
                availability="OBSERVED" if frame.project_record.case_count is not None else "NOT_OBSERVED",
                reason_code=None if frame.project_record.case_count is not None else "CASE_COUNT_ABSENT",
            ),
            "provider_discovery_rank": (
                {"rank": discovery.rank, "score": discovery.score,
                 "lane_id": "MUTATION_DISCOVERY_V1", "note": "selection metadata only"}
                if discovery is not None else None
            ),
        })

        cases_with_expression: int | None = None
        if frame.expression_coverage is not None:
            cases_with_expression = sum(
                1 for case in frame.cases if frame.expression_coverage.cases.get(case.case_id) is True
            )
            for case in frame.cases:
                if frame.expression_coverage.cases.get(case.case_id) is None:
                    missingness.append(f"{frame.project_id}: case {case.case_id} absent from expression availability")

        local_record: dict[str, Any] | None = None
        local_availability = "NOT_ACQUIRED"
        returned_case_columns: int | None = None
        valid_measurements: int | None = None
        missing_measurements: int | None = None
        if frame.expression_values is not None:
            missing_case_columns = list(frame.expression_values.missing_case_ids)
            row = frame.expression_values.values.get(gene.gene_id)
            if row is None:
                local_availability = "NOT_OBSERVED"
                returned_case_columns = 0
                valid_measurements = 0
                missing_measurements = examined
                missingness.append(f"{frame.project_id}: gene {gene.gene_id} absent from expression values")
            else:
                summary = expression_log2_summary(row, missing_case_columns=len(missing_case_columns))
                local_availability = summary.availability
                returned_case_columns = summary.n_returned
                valid_measurements = summary.n_finite
                missing_measurements = summary.n_missing
                local_record = {
                    "median": metric("expression_log2_median", summary.median, EXPRESSION_UNIT,
                                     availability="OBSERVED" if summary.median is not None else "INSUFFICIENT",
                                     reason_code=None if summary.median is not None else "NO_FINITE_VALUES"),
                    "sample_sd": metric("expression_log2_sample_sd", summary.sample_sd, EXPRESSION_UNIT,
                                        availability="OBSERVED" if summary.sample_sd is not None else "INSUFFICIENT",
                                        reason_code=None if summary.sample_sd is not None else "INSUFFICIENT_N"),
                    "minimum": metric("expression_log2_minimum", summary.minimum, EXPRESSION_UNIT,
                                      availability="OBSERVED" if summary.minimum is not None else "INSUFFICIENT"),
                    "maximum": metric("expression_log2_maximum", summary.maximum, EXPRESSION_UNIT,
                                      availability="OBSERVED" if summary.maximum is not None else "INSUFFICIENT"),
                    "n_finite": metric("expression_n_finite", summary.n_finite, "count"),
                    "n_missing": metric("expression_n_missing", summary.n_missing, "count"),
                    "n_returned": metric("expression_n_returned", summary.n_returned, "count"),
                    "n_missing_case_columns": metric("expression_n_missing_case_columns",
                                                     len(missing_case_columns), "count"),
                    "missing_case_ids": missing_case_columns,
                    "method_id": "EXPRESSION_LOG2_SUMMARY_V1",
                    "unit": EXPRESSION_UNIT,
                    "transformation": EXPRESSION_TRANSFORMATION,
                }
                if summary.n_missing:
                    absent_columns = len(missing_case_columns)
                    missingness.append(
                        f"{frame.project_id}: {summary.n_missing} of {examined} examined cases have no "
                        f"expression value ({absent_columns} case column(s) not returned by the provider)"
                    )
        provider_record: dict[str, Any] | None = None
        provider_gene = None
        if frame.provider_selection is not None:
            provider_gene = frame.provider_selection.genes.get(gene.gene_id)
            if provider_gene is None:
                missingness.append(
                    f"{frame.project_id}: gene {gene.gene_id} absent from provider gene selection "
                    "(below provider median threshold or not returned)"
                )
        if provider_gene is not None:
            provider_record = {
                "median": metric("provider_log2_uqfpkm_median", provider_gene.median, EXPRESSION_UNIT,
                                 availability="OBSERVED" if provider_gene.median is not None else "NOT_OBSERVED"),
                "stddev": metric("provider_log2_uqfpkm_stddev", provider_gene.stddev, EXPRESSION_UNIT,
                                 availability="OBSERVED" if provider_gene.stddev is not None else "NOT_OBSERVED"),
                "source": "GENE_SELECTION",
                "estimator_note": "INFERRED_POPULATION_SD_UNVERIFIED",
            }
        expression_availability = local_availability
        if local_availability in {"NOT_ACQUIRED", "NOT_OBSERVED"} and provider_record is not None:
            expression_availability = "PARTIAL"
        expression_results.append({
            "project_id": frame.project_id,
            "population_id": population_id,
            "unit": EXPRESSION_UNIT,
            "transformation": EXPRESSION_TRANSFORMATION,
            "availability": expression_availability,
            "local": local_record,
            "provider": provider_record,
            "provider_unavailable_reason": (
                frame.provider_summary_unavailable_reason if provider_record is None else None
            ),
            "coverage": {
                "examined_cases": metric("examined_cases", examined, "cases"),
                "assay_available_cases": metric(
                    "assay_available_cases", cases_with_expression, "cases",
                    availability="OBSERVED" if cases_with_expression is not None else "NOT_OBSERVED",
                    reason_code=None if cases_with_expression is not None else "AVAILABILITY_NOT_ACQUIRED",
                ),
                "cases_with_expression": metric(
                    "cases_with_expression", cases_with_expression, "cases",
                    availability="OBSERVED" if cases_with_expression is not None else "NOT_OBSERVED",
                    reason_code=None if cases_with_expression is not None else "AVAILABILITY_NOT_ACQUIRED",
                ),
                "returned_case_columns": metric(
                    "returned_case_columns", returned_case_columns, "cases",
                    availability="OBSERVED" if returned_case_columns is not None else "NOT_OBSERVED",
                    reason_code=None if returned_case_columns is not None else "VALUES_NOT_ACQUIRED",
                ),
                "valid_measurements": metric(
                    "valid_measurements", valid_measurements, "cases",
                    availability="OBSERVED" if valid_measurements is not None else "NOT_OBSERVED",
                    reason_code=None if valid_measurements is not None else "VALUES_NOT_ACQUIRED",
                ),
                "missing_measurements": metric(
                    "missing_measurements", missing_measurements, "cases",
                    availability="OBSERVED" if missing_measurements is not None else "NOT_OBSERVED",
                    reason_code=None if missing_measurements is not None else "VALUES_NOT_ACQUIRED",
                ),
            },
        })
        imbalance_rows.append({
            "project_id": frame.project_id,
            "mutation_observed": mutation_availability == "OBSERVED",
            "examined_cases": examined,
            "cases_with_expression": cases_with_expression,
        })
        sufficiency_rows.append({
            "project_id": frame.project_id,
            "mutation_observed": mutation_availability == "OBSERVED",
            "expression_observed": expression_availability == "OBSERVED",
            "missing_measurements": missing_measurements,
        })

    dominance, dominance_availability = project_dominance(observed_affected)
    acquisition_complete = counts.complete and coverage.complete
    sufficiency = scientific_sufficiency(sufficiency_rows, acquisition_complete)
    medians = [
        result["local"]["median"]["value"]
        for result in expression_results
        if result["local"] is not None and result["local"]["median"]["value"] is not None
    ]
    projects_with_mutation = sum(1 for result in mutation_results
                                 if result["affected_case_count"]["availability"] == "OBSERVED")
    projects_with_expression = sum(1 for result in expression_results
                                   if result["local"] is not None
                                   and result["local"]["median"]["availability"] == "OBSERVED")
    if not counts.complete:
        warnings = list(warnings) + [f"mutation counts partial: {', '.join(counts.partial_reasons)}"]
    if not coverage.complete:
        warnings = list(warnings) + [f"mutation coverage partial: {', '.join(coverage.partial_reasons)}"]

    state: dict[str, Any] = {
        "state_id": state_id,
        "schema_version": STATE_SCHEMA_VERSION,
        "mode": "LIVE",
        "run_id": run_id,
        "created_at": created_at,
        "entity": {
            "gene_id": gene.gene_id,
            "gene_symbol": gene.symbol,
            "biotype": gene.biotype,
            "is_cancer_gene_census": gene.is_cancer_gene_census,
            "genome_build": None,
            "genome_build_note": "not observed in admitted endpoints",
        },
        "scope": {
            "spec_id": scope_meta.get("spec_id"),
            "research_spec": scope_meta.get("research_spec"),
            "domain": scope_meta.get("domain"),
            "cohort": scope_meta.get("cohort"),
            "project_id": scope_meta.get("project_id"),
            "programs": sorted({frame.project_record.program_name for frame in ordered
                                if frame.project_record.program_name}),
            "projects": [frame.project_id for frame in ordered],
            "modalities": ["mutation_counts", "expression_summary"],
            "workflows": sorted({workflow for frame in ordered for workflow in frame.workflows}),
            "sample_types": sorted({sample_type for frame in ordered
                                    for sample_type in _sample_type_counts(frame.cases)}),
            "sample_type_counts_by_project": {
                frame.project_id: _sample_type_counts(frame.cases) for frame in ordered
            },
            "examined_case_frame": scope_meta.get("examined_case_frame", "ALL_CASES_PAGINATED"),
            "comparability": {
                "statuses": list(COMPARABILITY_STATUSES),
                "within_cohort": dict(WITHIN_COHORT_COMPARABILITY),
                "cross_project": dict(CROSS_PROJECT_COMPARABILITY),
            },
        },
        "generation": {
            "lane_ids": [
                "MUTATION_DISCOVERY_V1", "MUTATION_AFFECTED_CASE_COUNT_V1",
                "PROJECT_SSM_COVERAGE_V1", "EXPRESSION_LOG2_SUMMARY_V1",
                "EXPRESSION_PROVIDER_SUMMARY_V1", "PROJECT_DOMINANCE_V1",
            ],
            "lane_versions": {method_id: definition.version for method_id, definition in METHODS.items()},
            "discovery": discovery_meta,
            "rank_in_lane": discovery_meta.get("rank_in_lane"),
            "source_hit_refs": [source["response_sha256"] for source in sources],
        },
        "populations": populations,
        "mutation": {
            "availability": (
                "OBSERVED" if projects_with_mutation == len(ordered)
                else ("PARTIAL" if projects_with_mutation else "INSUFFICIENT")
            ),
            "absence_semantics": MUTATION_ABSENCE_SEMANTICS,
            "project_results": mutation_results,
            "coverage": {
                "case_with_ssm": metric(
                    "case_with_ssm_total", sum(coverage.case_with_ssm.values()),
                    "cases", availability="OBSERVED" if coverage.case_with_ssm else "NOT_OBSERVED",
                    reason_code=None if coverage.case_with_ssm else "NO_COVERAGE_RESPONSE",
                ),
                "coverage_complete": coverage.complete,
            },
        },
        "expression": {
            "availability": (
                "OBSERVED" if projects_with_expression == len(ordered)
                else ("PARTIAL" if projects_with_expression else "INSUFFICIENT")
            ),
            "project_results": expression_results,
            "coverage": {
                "cases_with_expression": metric(
                    "cases_with_expression_total",
                    sum(row["cases_with_expression"] for row in imbalance_rows
                        if row["cases_with_expression"] is not None),
                    "cases",
                    availability="OBSERVED" if any(row["cases_with_expression"] is not None
                                                   for row in imbalance_rows) else "NOT_OBSERVED",
                ),
                "examined_cases": metric("examined_cases_total", sum(row["examined_cases"] for row in imbalance_rows), "cases"),
            },
        },
        "cross_project": {
            "projects_with_mutation_observation": projects_with_mutation,
            "projects_with_expression_observation": projects_with_expression,
            "affected_case_total": metric(
                "affected_case_total", sum(observed_affected.values()) if observed_affected else None, "cases",
                availability="OBSERVED" if observed_affected else "NOT_OBSERVED",
                reason_code=None if observed_affected else "NO_OBSERVED_PROJECTS",
            ),
            "top_project_share": metric(
                "top_project_share", dominance, "share", availability=dominance_availability,
                reason_code=None if dominance is not None else "INSUFFICIENT_OBSERVED_PROJECTS",
            ),
            "expression_median_min": metric(
                "expression_median_min", min(medians) if medians else None, EXPRESSION_UNIT,
                availability="OBSERVED" if medians else "NOT_OBSERVED",
            ),
            "expression_median_max": metric(
                "expression_median_max", max(medians) if medians else None, EXPRESSION_UNIT,
                availability="OBSERVED" if medians else "NOT_OBSERVED",
            ),
            "coverage_imbalance": coverage_imbalance(imbalance_rows),
            "coverage_imbalance_definition": COVERAGE_IMBALANCE_DEFINITION,
            "dominance_definition": DOMINANCE_SHARE_DEFINITION,
            "direction": "NOT_EXAMINED",
            "comparability_status": "NOT_APPLICABLE",
            "notes": [],
        },
        "quality": {
            "api_warnings": warnings,
            "missingness": missingness,
            "duplicate_checks": "PASS",
            "finite_checks": "PASS",
            "truncation": "NONE",
            "completeness": "COMPLETE" if acquisition_complete else "PARTIAL",
            "acquisition_completeness": "COMPLETE" if acquisition_complete else "PARTIAL",
            "acquisition_completeness_definition": ACQUISITION_COMPLETENESS_DEFINITION,
            "scientific_sufficiency": sufficiency,
            "scientific_sufficiency_definition": SCIENTIFIC_SUFFICIENCY_DEFINITION,
        },
        "tested_context": {
            "examined_genes_ref": discovery_meta.get("examined_genes_ref"),
            "examined_genes_hash": discovery_meta.get("examined_genes_hash"),
            "discovery_method": "MUTATION_DISCOVERY_V1",
            "selection_bias": (
                "Genes are discovered from the provider top-mutated ranking for the single examined cohort "
                "and selected by provider rank; this is selection-biased and does not represent an unbiased "
                "genome-wide scan."
            ),
            "coverage": {"examined_genes_n": discovery_meta.get("examined_genes_n")},
        },
        "provenance": {
            "gdc_release": scope_meta.get("gdc_release"),
            "sources": sources,
            "methods": [definition.ref() for definition in METHODS.values()],
            "environment_hash": hashlib.sha256(canonical_json({
                "state_schema_version": STATE_SCHEMA_VERSION,
                "methods": {method_id: definition.version for method_id, definition in METHODS.items()},
                "parser_version": "gdc-parser-v1",
            })).hexdigest(),
        },
    }
    state["state_hash"] = content_hash(statistical_state_identity_payload(state))
    return state
