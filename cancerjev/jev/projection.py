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

PROJECTION_VERSION = "jev-state-projection-v1"
PROJECTION_BYTE_CAP = 65_536

INCLUDED_FIELDS = (
    "projection_version",
    "entity.gene_id",
    "entity.symbol",
    "entity.biotype",
    "entity.cancer_census",
    "scope.projects",
    "scope.modalities",
    "scope.expression_unit",
    "scope.workflow",
    "scope.examined_case_frame",
    "scope.selection_bias",
    "project_observations[].project_id",
    "project_observations[].cases_examined",
    "project_observations[].cases_with_ssm",
    "project_observations[].cases_with_expression",
    "project_observations[].affected_cases",
    "project_observations[].expression_local.median",
    "project_observations[].expression_local.sample_sd",
    "project_observations[].expression_local.n_finite",
    "project_observations[].expression_local.n_missing",
    "project_observations[].expression_provider.median",
    "project_observations[].expression_provider.stddev",
    "cross_project.projects_with_mutation_observation",
    "cross_project.projects_with_expression_observation",
    "cross_project.affected_total",
    "cross_project.top_project_share",
    "cross_project.expression_median_range",
    "cross_project.coverage_imbalance",
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
    if state["cross_project"]["direction"] == "NOT_EXAMINED":
        limitations.append("No signed, comparable effect direction exists in this state; direction is NOT_EXAMINED.")
    if state["quality"]["completeness"] != "COMPLETE":
        limitations.append("Some provider aggregations were partial; totals may be incomplete.")
    return limitations


def build_projection(state: dict[str, Any]) -> dict[str, Any]:
    populations = {population["project"]: population for population in state["populations"]}
    mutations = {result["project_id"]: result for result in state["mutation"]["project_results"]}
    expressions = {result["project_id"]: result for result in state["expression"]["project_results"]}
    observations: list[dict[str, Any]] = []
    for project_id in sorted(mutations):
        mutation = mutations[project_id]
        expression = expressions.get(project_id, {})
        local = expression.get("local")
        provider = expression.get("provider")
        coverage = expression.get("coverage") or {}
        population = populations.get(project_id, {})
        observations.append({
            "project_id": project_id,
            "cases_examined": population.get("examined_n"),
            "cases_with_ssm": _metric_value(mutation["project_case_with_ssm"]),
            "cases_with_expression": _metric_value(coverage.get("cases_with_expression")),
            "affected_cases": _metric_value(mutation["affected_case_count"]),
            "expression_local": (
                {
                    "median": _metric_value(local["median"]),
                    "sample_sd": _metric_value(local["sample_sd"]),
                    "n_finite": _metric_value(local["n_finite"]),
                    "n_missing": _metric_value(local["n_missing"]),
                }
                if local else None
            ),
            "expression_provider": (
                {
                    "median": _metric_value(provider["median"]),
                    "stddev": _metric_value(provider["stddev"]),
                }
                if provider else None
            ),
        })
    missingness = list(state["quality"]["missingness"])
    for warning in state["quality"]["api_warnings"]:
        if warning not in missingness:
            missingness.append(warning)
    medians = [observation["expression_local"]["median"] for observation in observations
               if observation["expression_local"] and observation["expression_local"]["median"] is not None]
    projection = {
        "projection_version": PROJECTION_VERSION,
        "entity": {
            "gene_id": state["entity"]["gene_id"],
            "symbol": state["entity"]["gene_symbol"],
            "biotype": state["entity"]["biotype"],
            "cancer_census": state["entity"]["is_cancer_gene_census"],
        },
        "scope": {
            "projects": list(state["scope"]["projects"]),
            "modalities": list(state["scope"]["modalities"]),
            "expression_unit": "log2(UQFPKM+1)",
            "workflow": ",".join(state["scope"]["workflows"]) if state["scope"]["workflows"] else None,
            "examined_case_frame": state["scope"]["examined_case_frame"],
            "selection_bias": state["tested_context"]["selection_bias"],
        },
        "project_observations": observations,
        "cross_project": {
            "projects_with_mutation_observation": state["cross_project"]["projects_with_mutation_observation"],
            "projects_with_expression_observation": state["cross_project"]["projects_with_expression_observation"],
            "affected_total": _metric_value(state["cross_project"]["affected_case_total"]),
            "top_project_share": _metric_value(state["cross_project"]["top_project_share"]),
            "expression_median_range": [
                _metric_value(state["cross_project"]["expression_median_min"]),
                _metric_value(state["cross_project"]["expression_median_max"]),
            ] if medians else None,
            "coverage_imbalance": state["cross_project"]["coverage_imbalance"],
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
