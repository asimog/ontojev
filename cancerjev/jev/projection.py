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
EVIDENCE_PROJECTION_VERSION = "jev-evidence-projection-v1"
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


EVIDENCE_INCLUDED_FIELDS = (
    "projection_version",
    "entity.gene_id",
    "entity.symbol",
    "revision.iteration",
    "revision.source_state_hash",
    "revision.evidence_present",
    "revision.integrity_observed",
    "revision.verified_checks",
    "revision.contradicted_checks",
    "revision.not_observed_checks",
    "action.action_id",
    "action.version",
    "action.method_id",
    "action.method_version",
    "action.title",
    "action.unit",
    "action.required_evidence",
    "action.limitations",
    "observations[].check_id",
    "observations[].outcome",
    "observations[].availability",
    "observations[].n_effective",
    "observations[].missingness.count",
    "observations[].notes",
    "project_evidence[]",
    "missing_evidence[]",
    "quality",
    "provenance",
    "eligible_actions[]",
    "limitations[]",
)


def build_evidence_projection(evidence: dict[str, Any], eligible_actions: list[dict[str, Any]], *,
                              evidence_hash: str) -> dict[str, Any]:
    """Project one immutable EvidenceState revision plus the eligible action set.

    Only fields that already exist in the revision and in the action registry are
    copied; nothing is recomputed and no operational id (revision id, run id,
    candidate id, artifact id, timestamp, request id) enters the projection, so the
    same revision content projects to the same bytes and can reuse inference.
    """
    if evidence.get("schema_version") != 2:
        raise ProjectionError("UNSUPPORTED_EVIDENCE_SCHEMA", f"schema {evidence.get('schema_version')!r}")
    observations = []
    integrity_observed = False
    evidence_present = False
    for observation in evidence.get("deterministic_observations", []):
        check_id = observation.get("check_id")
        availability = observation.get("availability")
        observed = availability == "OBSERVED"
        evidence_present = evidence_present or observed
        if check_id in {"RESPONSE_ARTIFACT_INTEGRITY", "TESTED_UNIVERSE_REPRODUCIBLE"} and observed:
            integrity_observed = True
        observations.append({
            "check_id": check_id or observation.get("method_id"),
            "method_id": observation.get("method_id"),
            "method_version": observation.get("method_version"),
            "outcome": observation.get("outcome"),
            "availability": availability,
            "n_effective": observation.get("n_effective"),
            "observed": observation.get("observed"),
            "missingness": observation.get("missingness"),
            "notes": list(observation.get("notes", [])),
            "limitations": list(observation.get("limitations", [])),
        })
    project_evidence = []
    for row in evidence.get("project_level_evidence", []):
        entry = {"project_id": row.get("project_id")}
        for key in ("affected_case_count", "examined_cases", "project_case_with_ssm",
                    "cases_with_expression", "missing_measurements"):
            metric = row.get(key) or {}
            entry[key] = metric.get("value")
            entry[f"{key}_availability"] = metric.get("availability")
        project_evidence.append(entry)
        evidence_present = evidence_present or entry.get("affected_case_count_availability") == "OBSERVED"
        evidence_present = evidence_present or entry.get("cases_with_expression_availability") == "OBSERVED"
    quality = evidence.get("quality_and_fragility", {})
    provenance = evidence.get("provenance", {})
    input_artifacts = provenance.get("input_artifacts", [])
    projection = {
        "projection_version": EVIDENCE_PROJECTION_VERSION,
        "entity": {
            "gene_id": (evidence.get("entity") or {}).get("gene_id"),
            "symbol": (evidence.get("entity") or {}).get("gene_symbol"),
        },
        "revision": {
            "iteration": evidence.get("iteration_number"),
            "source_state_hash": (evidence.get("source_statistical_state") or {}).get("state_identity_hash"),
            "evidence_present": bool(evidence_present),
            "integrity_observed": bool(integrity_observed),
            "verified_checks": quality.get("checks_verified"),
            "contradicted_checks": quality.get("checks_contradicted"),
            "not_observed_checks": quality.get("checks_not_observed"),
        },
        "action": evidence.get("action"),
        "observations": observations,
        "project_evidence": project_evidence,
        "missing_evidence": [
            {"needed_evidence": item.get("needed_evidence"), "availability": item.get("availability")}
            for item in evidence.get("missing_evidence", [])
        ],
        "quality": {
            "checks_total": quality.get("checks_total"),
            "checks_verified": quality.get("checks_verified"),
            "checks_contradicted": quality.get("checks_contradicted"),
            "checks_not_observed": quality.get("checks_not_observed"),
            "warnings": list(quality.get("warnings", [])),
        },
        "provenance": {
            "gdc_release": provenance.get("gdc_release"),
            "response_source_count": len(provenance.get("sources", [])),
            "selection_artifact_sha256": provenance.get("selection_artifact_sha256"),
            "input_artifacts_total": len(input_artifacts),
            "input_artifacts_verified": sum(1 for item in input_artifacts if item.get("verified") is True),
            "action_registry_version": provenance.get("action_registry_version"),
        },
        "eligible_actions": [
            {
                "action_id": action.get("action_id"),
                "version": action.get("version"),
                "title": action.get("title"),
                "question": action.get("question"),
                "unit": action.get("unit"),
                "required_evidence": list(action.get("required_evidence", [])),
            }
            for action in eligible_actions
        ],
        "limitations": (
            list((evidence.get("action") or {}).get("limitations", []))
            + [
                "The revision is deterministic evidence about recorded GDC evidence, not biological evidence.",
                "A single cohort is examined and the examined gene set is selection-biased.",
            ]
        ),
    }
    projection["revision"]["evidence_hash"] = evidence_hash
    encoded = canonical_json(projection)
    if len(encoded) > PROJECTION_BYTE_CAP:
        raise ProjectionError("PROJECTION_TOO_LARGE", f"{len(encoded)} bytes exceeds cap {PROJECTION_BYTE_CAP}")
    return projection
