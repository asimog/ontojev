"""Deterministic projection of a StatisticalState into compact Jev input.

Only fields that already exist in the deterministic state are copied; nothing is
recomputed from raw responses. The projection hash covers canonical payload
bytes and is the inference-identity component. A projection that would exceed
the hard byte cap fails closed.
"""

from __future__ import annotations

import hashlib
from typing import Any

from cancerjev.domain.events import canonical_json

PROJECTION_VERSION = "jev-state-projection-v2"
PROJECTION_BYTE_CAP = 65_536

INCLUDED_FIELDS = (
    "projection_version",
    "entity.gene_id",
    "entity.symbol",
    "entity.biotype",
    "entity.cancer_census",
    "scope.cohort",
    "scope.domain",
    "scope.projects",
    "scope.modalities",
    "scope.expression_unit",
    "scope.workflow",
    "scope.examined_case_frame",
    "scope.selection_bias",
    "cohort.project_id",
    "cohort.examined_cases",
    "cohort.affected_cases",
    "cohort.mutation_observed",
    "cohort.mutation_coverage_complete",
    "cohort.ssm_coverage_cases",
    "cohort.expression_observed",
    "cohort.expression_median",
    "cohort.expression_sample_sd",
    "cohort.expression_n_finite",
    "cohort.expression_n_missing",
    "cohort.expression_provider_median",
    "cohort.expression_provider_stddev",
    "cohort.coverage_imbalance",
    "cohort.completeness",
    "cohort.scientific_sufficiency",
    "missingness[]",
    "limitations[]",
    "eligible_followups[]",
)


class ProjectionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _metric_value(metric: dict[str, Any] | None) -> Any:
    if metric is None or metric.get("availability") != "OBSERVED":
        return None
    return metric.get("value")


def _limitations(state: dict[str, Any]) -> list[str]:
    limitations = [
        "Mutation counts are provider-defined case counts with no matched denominator; a project with no "
        "observation is not a biological negative.",
        "Expression summaries are computed locally as log2(UQFPKM+1) on the exact examined case set; "
        "case-to-sample resolution is not established.",
        "Provider expression median/stddev estimator conventions are not documented (live evidence suggests a "
        "population denominator).",
        "The examined gene set is selected from the provider top-mutated ranking and is not an unbiased "
        "genome-wide scan.",
    ]
    if state["quality"]["completeness"] != "COMPLETE":
        limitations.append("Some provider aggregations were partial; totals may be incomplete.")
    return limitations


def build_projection(state: dict[str, Any]) -> dict[str, Any]:
    project_ids = state["scope"]["projects"]
    if len(project_ids) != 1:
        raise ProjectionError(
            "MULTI_COHORT_STATE",
            f"single-cohort projection requires exactly one project, received {len(project_ids)}",
        )
    project_id = state["scope"].get("project_id") or project_ids[0]
    if project_id != project_ids[0]:
        raise ProjectionError("COHORT_PROJECT_MISMATCH", "scope project_id does not match its project list")

    population = next((item for item in state["populations"] if item["project"] == project_id), {})
    mutation = next(
        (item for item in state["mutation"]["project_results"] if item["project_id"] == project_id),
        {},
    )
    expression = next(
        (item for item in state["expression"]["project_results"] if item["project_id"] == project_id),
        {},
    )
    local = expression.get("local") or {}
    provider = expression.get("provider") or {}
    affected = mutation.get("affected_case_count")
    expression_median = local.get("median")
    missingness = list(state["quality"]["missingness"])
    for warning in state["quality"]["api_warnings"]:
        if warning not in missingness:
            missingness.append(warning)
    projection = {
        "projection_version": PROJECTION_VERSION,
        "entity": {
            "gene_id": state["entity"]["gene_id"],
            "symbol": state["entity"]["gene_symbol"],
            "biotype": state["entity"]["biotype"],
            "cancer_census": state["entity"]["is_cancer_gene_census"],
        },
        "scope": {
            "cohort": state["scope"].get("cohort") or project_id,
            "domain": state["scope"].get("domain"),
            "projects": list(state["scope"]["projects"]),
            "modalities": list(state["scope"]["modalities"]),
            "expression_unit": expression.get("unit"),
            "workflow": ",".join(state["scope"]["workflows"]) if state["scope"]["workflows"] else None,
            "examined_case_frame": state["scope"]["examined_case_frame"],
            "selection_bias": state["tested_context"]["selection_bias"],
        },
        "cohort": {
            "project_id": project_id,
            "examined_cases": population.get("examined_n"),
            "affected_cases": _metric_value(affected),
            "mutation_observed": bool(affected and affected.get("availability") == "OBSERVED"),
            "mutation_coverage_complete": state["mutation"]["coverage"]["coverage_complete"],
            "ssm_coverage_cases": _metric_value(mutation.get("project_case_with_ssm")),
            "expression_observed": bool(
                expression_median and expression_median.get("availability") == "OBSERVED"
            ),
            "expression_median": _metric_value(expression_median),
            "expression_sample_sd": _metric_value(local.get("sample_sd")),
            "expression_n_finite": _metric_value(local.get("n_finite")),
            "expression_n_missing": _metric_value(local.get("n_missing")),
            "expression_provider_median": _metric_value(provider.get("median")),
            "expression_provider_stddev": _metric_value(provider.get("stddev")),
            "coverage_imbalance": state["cross_project"]["coverage_imbalance"],
            "completeness": state["quality"]["completeness"],
            "scientific_sufficiency": state["quality"]["scientific_sufficiency"],
        },
        "missingness": missingness,
        "limitations": _limitations(state),
        "eligible_followups": [],
    }
    encoded = canonical_json(projection)
    if len(encoded) > PROJECTION_BYTE_CAP:
        raise ProjectionError("PROJECTION_TOO_LARGE", f"{len(encoded)} bytes exceeds cap {PROJECTION_BYTE_CAP}")
    return projection


def projection_hash(projection: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(projection)).hexdigest()
