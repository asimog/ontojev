"""Deterministic projection of canonical scientific objects into compact Jev input.

Only fields that already exist in the typed state, revision, hypothesis draft or
action registry are copied; nothing is recomputed from raw responses. The
projection hash covers canonical payload bytes and is the inference-identity
component. A projection that would exceed the hard byte cap fails closed.
"""

from __future__ import annotations

import hashlib
from typing import Any

from cancerjev.domain.envelopes import EvidenceRecord, StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import EvidenceState
from cancerjev.domain.hypotheses import HypothesisDraft
from cancerjev.domain.measurements import (
    Acquisition,
    MetricAvailability,
    ObservedCount,
    ObservedScalar,
)
from cancerjev.domain.scientific import (
    ExpressionSummaryResult,
    StatisticalState,
)
from cancerjev.science.actions import ACTION_REGISTRY

PROJECTION_VERSION = "jev-state-projection-v3"
EVIDENCE_PROJECTION_VERSION = "jev-evidence-projection-v2"
HYPOTHESIS_PROJECTION_VERSION = "jev-hypothesis-projection-v2"
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


def _limitations(completeness: str) -> list[str]:
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
    if completeness != "COMPLETE":
        limitations.append("Some provider aggregations were partial; totals may be incomplete.")
    return limitations


def _observed_count(measurement: Any) -> int | None:
    return measurement.value if isinstance(measurement, ObservedCount) else None


def _observed_scalar(measurement: Any) -> float | None:
    return measurement.value if isinstance(measurement, ObservedScalar) else None


def build_projection(record: StateRecord) -> dict[str, Any]:
    state: StatisticalState = record.state
    project_ids = list(state.research.projects)
    if len(project_ids) != 1:
        raise ProjectionError(
            "MULTI_COHORT_STATE",
            f"single-cohort projection requires exactly one project, received {len(project_ids)}",
        )
    project_id = state.research.project_id or project_ids[0]
    if project_id != project_ids[0]:
        raise ProjectionError("COHORT_PROJECT_MISMATCH", "scope project_id does not match its project list")
    if len(state.projects) != 1:
        raise ProjectionError("MULTI_COHORT_STATE", "typed state does not hold exactly one project frame")
    project = state.projects[0]
    mutation = project.mutation
    expression = project.expression
    if isinstance(expression, ExpressionSummaryResult):
        expression_median = _observed_scalar(expression.median)
        expression_sample_sd = _observed_scalar(expression.sample_sd)
        expression_n_finite = len(expression.values)
        expression_n_missing = (len(expression.coverage.frame.examined_ids)
                                - len(expression.coverage.valid_ids))
    else:
        expression_median = None
        expression_sample_sd = None
        expression_n_finite = None
        expression_n_missing = None
    provider = project.provider_expression
    missingness = list(state.missingness)
    for warning in state.warnings:
        if warning not in missingness:
            missingness.append(warning)
    completeness = "COMPLETE" if state.quality.acquisition is Acquisition.COMPLETE else "PARTIAL"
    projection = {
        "projection_version": PROJECTION_VERSION,
        "entity": {
            "gene_id": state.entity.gene_id,
            "symbol": state.entity.symbol,
            "biotype": state.annotation.biotype,
            "cancer_census": state.annotation.cancer_census,
        },
        "scope": {
            "cohort": state.research.cohort or project_id,
            "domain": state.research.domain,
            "projects": project_ids,
            "modalities": list(state.research.modalities),
            "expression_unit": "log2(UQFPKM+1)",
            "workflow": ",".join(state.research.workflows) if state.research.workflows else None,
            "examined_case_frame": state.research.examined_case_frame,
            "selection_bias": state.tested_context.selection_bias,
        },
        "cohort": {
            "project_id": project_id,
            "examined_cases": len(project.population.frame.examined_ids),
            "affected_cases": _observed_count(mutation.affected_cases),
            "mutation_observed": isinstance(mutation.affected_cases, ObservedCount),
            "mutation_coverage_complete": mutation.coverage_complete,
            "ssm_coverage_cases": _observed_count(mutation.ssm_coverage_cases),
            "expression_observed": expression_median is not None,
            "expression_median": expression_median,
            "expression_sample_sd": expression_sample_sd,
            "expression_n_finite": expression_n_finite,
            "expression_n_missing": expression_n_missing,
            "expression_provider_median": provider.median if provider is not None else None,
            "expression_provider_stddev": provider.stddev if provider is not None else None,
            "coverage_imbalance": state.cross_project.coverage_imbalance,
            "completeness": completeness,
            "scientific_sufficiency": state.quality.sufficiency.value,
        },
        "missingness": missingness,
        "limitations": _limitations(completeness),
        "eligible_followups": [],
    }
    encoded = canonical_json(projection)
    if len(encoded) > PROJECTION_BYTE_CAP:
        raise ProjectionError("PROJECTION_TOO_LARGE", f"{len(encoded)} bytes exceeds cap {PROJECTION_BYTE_CAP}")
    return projection


HYPOTHESIS_INCLUDED_FIELDS = (
    "projection_version",
    "hypothesis.label",
    "hypothesis.generator",
    "hypothesis.generator_model",
    "hypothesis.statement",
    "hypothesis.proposed_mechanism",
    "hypothesis.predictions",
    "hypothesis.contradicted_if",
    "hypothesis.distinguishing_tests",
    "hypothesis.required_evidence",
    "hypothesis.unsupported_assumptions",
    "revision.iteration",
    "revision.source_state_hash",
    "revision.evidence_hash",
    "observations[]",
    "project_evidence[]",
    "missing_evidence[]",
    "eligible_actions[]",
    "limitations[]",
)


def _observations(evidence: EvidenceState) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for observation in evidence.baseline_observations:
        observations.append({
            "check_id": observation.method_id,
            "method_id": observation.method_id,
            "method_version": observation.method_version,
            "outcome": None,
            "availability": observation.availability,
            "n_effective": observation.n_effective,
            "observed": None,
            "missingness": {"count": observation.missingness_count,
                            "reason": observation.missingness_reason},
            "notes": list(observation.notes),
            "limitations": list(observation.limitations),
        })
    for check in evidence.checks:
        observations.append({
            "check_id": check.check_id,
            "method_id": check.method_id,
            "method_version": check.method_version,
            "outcome": str(check.outcome),
            "availability": check.availability,
            "n_effective": check.n_effective,
            "observed": check.boundary_representation()["observed"],
            "expected": check.boundary_representation()["expected"],
            "missingness": {"count": check.missing_count, "reason": check.missing_reason},
            "notes": list(check.notes),
            "limitations": list(check.limitations),
        })
    return observations


def _revision_quality(evidence: EvidenceState) -> dict[str, Any]:
    if evidence.action is None:
        return {"checks_total": 0, "checks_verified": 0, "checks_contradicted": 0,
                "checks_not_observed": 0, "warnings": list(evidence.warnings)}
    summary = evidence.summary
    return {
        "checks_total": summary.total, "checks_verified": summary.verified,
        "checks_contradicted": summary.contradicted, "checks_not_observed": summary.not_observed,
        "warnings": list(evidence.warnings),
    }


def _project_evidence(evidence: EvidenceState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in evidence.project_evidence:
        entry: dict[str, Any] = {"project_id": row.project_id}
        for key, metric in row.metrics():
            entry[key] = metric.value
            entry[f"{key}_availability"] = metric.availability.value
        rows.append(entry)
    return rows


def _missing_evidence(evidence: EvidenceState) -> list[dict[str, Any]]:
    return [
        {"needed_evidence": item.needed_evidence, "availability": item.availability.value}
        for item in evidence.missing_evidence
    ]


def _action_block(evidence: EvidenceState) -> dict[str, Any] | None:
    if evidence.action is None:
        return None
    definition = ACTION_REGISTRY.get(evidence.action.action_id)
    if definition is None:
        return {"action_id": evidence.action.action_id, "version": evidence.action.version}
    return {
        **definition.ref(),
        "title": definition.title,
        "unit": definition.unit,
        "input_kind": definition.input_kind,
        "required_evidence": list(definition.required_evidence),
        "limitations": list(definition.limitations),
    }


def _action_payloads(eligible_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "action_id": action.get("action_id"),
            "version": action.get("version"),
            "title": action.get("title"),
            "question": action.get("question"),
            "unit": action.get("unit"),
            "input_kind": action.get("input_kind"),
            "required_evidence": list(action.get("required_evidence", [])),
        }
        for action in eligible_actions
    ]


def _revision_core(evidence: EvidenceState, evidence_hash: str) -> dict[str, Any]:
    observations = _observations(evidence)
    evidence_present = any(observation["availability"] == "OBSERVED" for observation in observations)
    integrity_observed = any(
        observation["check_id"] in {"RESPONSE_ARTIFACT_INTEGRITY", "TESTED_UNIVERSE_REPRODUCIBLE"}
        and observation["availability"] == "OBSERVED"
        for observation in observations
    )
    for row in evidence.project_evidence:
        for _key, metric in row.metrics():
            if metric.availability is MetricAvailability.OBSERVED:
                evidence_present = True
    quality = _revision_quality(evidence)
    return {
        "revision": {
            "iteration": evidence.revision_index,
            "source_state_hash": evidence.source_state.state_identity_hash,
            "evidence_present": bool(evidence_present),
            "integrity_observed": bool(integrity_observed),
            "verified_checks": quality["checks_verified"],
            "contradicted_checks": quality["checks_contradicted"],
            "not_observed_checks": quality["checks_not_observed"],
            "evidence_hash": evidence_hash,
        },
        "action": _action_block(evidence),
        "observations": observations,
        "project_evidence": _project_evidence(evidence),
        "missing_evidence": _missing_evidence(evidence),
        "quality": quality,
        "provenance": {
            "gdc_release": evidence.provenance.gdc_release,
            "response_source_count": len(evidence.provenance.sources),
            "selection_artifact_sha256": evidence.provenance.selection_artifact_sha256,
            "input_artifacts_total": len(evidence.provenance.input_artifacts),
            "input_artifacts_verified": sum(1 for item in evidence.provenance.input_artifacts
                                            if item.verified is True),
            "action_registry_version": evidence.provenance.action_registry_version,
        },
    }


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
    "action.input_kind",
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


def build_evidence_projection(record: EvidenceRecord,
                              eligible_actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Project one immutable EvidenceState revision plus the eligible action set.

    Only fields that already exist in the revision and in the action registry are
    copied; nothing is recomputed and no operational id (revision id, run id,
    candidate id, artifact id, timestamp, request id) enters the projection, so the
    same revision content projects to the same bytes and can reuse inference.
    """
    evidence = record.revision
    action_block = _action_block(evidence)
    projection = {
        "projection_version": EVIDENCE_PROJECTION_VERSION,
        "entity": {"gene_id": evidence.entity.gene_id, "symbol": evidence.entity.symbol},
        **_revision_core(evidence, record.evidence_hash),
        "eligible_actions": _action_payloads(eligible_actions),
        "limitations": (
            list((action_block or {}).get("limitations", []))
            + [
                "The revision is deterministic evidence about recorded GDC evidence, not biological evidence.",
                "A single cohort is examined and the examined gene set is selection-biased.",
            ]
        ),
    }
    encoded = canonical_json(projection)
    if len(encoded) > PROJECTION_BYTE_CAP:
        raise ProjectionError("PROJECTION_TOO_LARGE", f"{len(encoded)} bytes exceeds cap {PROJECTION_BYTE_CAP}")
    return projection


def build_hypothesis_projection(draft: HypothesisDraft, record: EvidenceRecord, *,
                                eligible_actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Project one generated hypothesis together with the revision it came from.

    The hypothesis text is carried verbatim and labelled with its generator; the
    projection never presents generated text as evidence, never recomputes anything
    and never includes operational ids — in particular the run-specific hypothesis
    id is excluded, so identical generated text over identical evidence reuses its
    review across runs.
    """
    evidence = record.revision
    projection = {
        "projection_version": HYPOTHESIS_PROJECTION_VERSION,
        "hypothesis": {
            "label": draft.label,
            "generator": draft.generator,
            "generator_model": draft.generator_model,
            "statement": draft.statement,
            "proposed_mechanism": draft.proposed_mechanism,
            "predictions": list(draft.predictions),
            "contradicted_if": list(draft.contradicted_if),
            "distinguishing_tests": list(draft.distinguishing_tests),
            "required_evidence": list(draft.required_evidence),
            "unsupported_assumptions": list(draft.unsupported_assumptions),
        },
        "revision": {
            "iteration": evidence.revision_index,
            "source_state_hash": evidence.source_state.state_identity_hash,
            "evidence_hash": record.evidence_hash,
        },
        "observations": _observations(evidence),
        "project_evidence": _project_evidence(evidence),
        "missing_evidence": _missing_evidence(evidence),
        "eligible_actions": _action_payloads(eligible_actions),
        "limitations": [
            "The hypothesis text is generated, not measured; it is not evidence.",
            "Judgments about the statement are inputs to Python policy and never execute anything.",
            "A single cohort is examined and the examined gene set is selection-biased.",
        ],
    }
    encoded = canonical_json(projection)
    if len(encoded) > PROJECTION_BYTE_CAP:
        raise ProjectionError("PROJECTION_TOO_LARGE", f"{len(encoded)} bytes exceeds cap {PROJECTION_BYTE_CAP}")
    return projection


def projection_hash(projection: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(projection)).hexdigest()


__all__ = [
    "EVIDENCE_INCLUDED_FIELDS",
    "EVIDENCE_PROJECTION_VERSION",
    "HYPOTHESIS_INCLUDED_FIELDS",
    "HYPOTHESIS_PROJECTION_VERSION",
    "INCLUDED_FIELDS",
    "PROJECTION_BYTE_CAP",
    "PROJECTION_VERSION",
    "ProjectionError",
    "build_evidence_projection",
    "build_hypothesis_projection",
    "build_projection",
    "projection_hash",
]
