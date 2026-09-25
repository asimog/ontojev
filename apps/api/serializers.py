"""Current presentation serializers for the HTTP API.

Internal scientific models stay canonical typed objects; the browser-facing
payloads are derived here, at the API boundary, and never become the scientific
model. Source artifact identity (id/hash) is reported separately from the response
ETag so presentation changes do not masquerade as evidence changes.
"""

from __future__ import annotations

import hashlib
from typing import Any

from cancerjev.domain.envelopes import EvidenceRecord, StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import EvidenceState
from cancerjev.domain.measurements import MetricRecord, ObservedCount, ObservedScalar
from cancerjev.science.actions import ACTION_REGISTRY

PRESENTATION_SCHEMA_VERSION = 4


def metric_view(metric: MetricRecord | None) -> dict[str, Any] | None:
    if metric is None:
        return None
    return {"value": metric.value, "unit": metric.unit,
            "availability": metric.availability.value, "reason_code": metric.reason_code}


def _measurement_view(measurement: Any) -> dict[str, Any] | None:
    if isinstance(measurement, (ObservedCount, ObservedScalar)):
        return {"value": measurement.value, "unit": measurement.unit.value,
                "availability": "OBSERVED", "reason_code": None}
    if measurement is None:
        return None
    return {"value": None, "unit": getattr(measurement, "expected_unit", None) and
            measurement.expected_unit.value, "availability": measurement.status.value,
            "reason_code": getattr(measurement, "reason", None)}


def state_detail(record: StateRecord) -> dict[str, Any]:
    """Readable current view of one registered StatisticalState."""
    state = record.state
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "kind": "STATISTICAL_STATE_PRESENTATION",
        "state_id": record.state_id,
        "state_hash": record.state_hash,
        "entity": {"gene_id": state.entity.gene_id, "symbol": state.entity.symbol,
                   "release": state.entity.release},
        "annotation": {"biotype": state.annotation.biotype,
                       "cancer_census": state.annotation.cancer_census,
                       "genome_build_note": state.annotation.genome_build_note},
        "research": {"spec_id": state.research.spec_id, "domain": state.research.domain,
                     "cohort": state.research.cohort, "project_id": state.research.project_id,
                     "projects": list(state.research.projects),
                     "modalities": list(state.research.modalities),
                     "workflows": list(state.research.workflows),
                     "examined_case_frame": state.research.examined_case_frame},
        "universe": {"order": state.universe.order, "source": state.universe.source,
                     "requested_limit": state.universe.requested_limit,
                     "reported_total": state.universe.reported_total,
                     "ordered_ids": list(state.universe.ordered_ids)},
        "tested_context": {"examined_genes_n": state.tested_context.examined_genes_n,
                           "rank_in_lane": state.tested_context.rank_in_lane,
                           "selection_bias": state.tested_context.selection_bias,
                           "examined_genes_hash": state.tested_context.examined_genes_hash},
        "projects": [
            {
                "project_id": project.population.frame.project_id,
                "examined_cases": len(project.population.frame.examined_ids),
                "frame_hash": project.population.frame_hash,
                "affected_cases": _measurement_view(project.mutation.affected_cases),
                "ssm_coverage_cases": _measurement_view(project.mutation.ssm_coverage_cases),
                "mutation_coverage_complete": project.mutation.coverage_complete,
                "expression": _expression_view(project.expression),
                "provider_expression_median": project.provider_expression.median
                if project.provider_expression else None,
            }
            for project in state.projects
        ],
        "cross_project": {
            "projects_with_mutation_observation": state.cross_project.projects_with_mutation_observation,
            "projects_with_expression_observation": state.cross_project.projects_with_expression_observation,
            "affected_case_total": metric_view(state.cross_project.affected_case_total),
            "top_project_share": metric_view(state.cross_project.top_project_share),
            "coverage_imbalance": state.cross_project.coverage_imbalance,
        },
        "quality": {"acquisition": state.quality.acquisition.value,
                    "sufficiency": state.quality.sufficiency.value,
                    "compatibility": state.quality.compatibility.value,
                    "reasons": list(state.quality.reasons)},
        "warnings": list(state.warnings),
        "missingness": list(state.missingness),
        "methods": [{"method_id": method.method_id, "version": method.version,
                     "parameters_hash": method.parameters_hash} for method in state.methods],
        "sources": [{"endpoint": source.endpoint, "response_hash": source.response_hash,
                     "parser_version": source.parser_version, "release": source.release,
                     "acquisition": source.acquisition.value} for source in state.sources],
    }


def _expression_view(expression: Any) -> dict[str, Any]:
    from cancerjev.domain.scientific import ExpressionSummaryResult, UnavailableLane

    if isinstance(expression, UnavailableLane):
        return {"status": expression.status.value, "reason": expression.reason}
    if not isinstance(expression, ExpressionSummaryResult):
        return {"status": "NOT_OBSERVED", "reason": "expression lane not present"}
    return {
        "status": "OBSERVED",
        "median": _measurement_view(expression.median),
        "sample_sd": _measurement_view(expression.sample_sd),
        "n_finite": len(expression.values),
        "n_examined": len(expression.coverage.frame.examined_ids),
        "n_missing": len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids),
    }


def _evidence_observations(evidence: EvidenceState) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for index, observation in enumerate(evidence.baseline_observations):
        observations.append({
            "result_id": f"baseline-{index}",
            "check_id": observation.method_id,
            "method_id": observation.method_id,
            "method_version": observation.method_version,
            "outcome": None,
            "availability": observation.availability,
            "n_effective": observation.n_effective,
            "observed": observation.boundary_representation()["observed"],
            "notes": list(observation.notes),
            "claim": None,
        })
    for check in evidence.checks:
        boundary = check.boundary_representation()
        observations.append({
            "result_id": check.check_id,
            "check_id": check.check_id,
            "method_id": check.method_id,
            "method_version": check.method_version,
            "outcome": check.outcome.value,
            "availability": check.availability,
            "n_effective": check.n_effective,
            "observed": boundary["observed"],
            "notes": list(check.notes),
            "claim": check.claim,
        })
    return observations


def evidence_detail(record: EvidenceRecord) -> dict[str, Any]:
    """Readable current view of one immutable EvidenceState revision."""
    evidence = record.revision
    definition = ACTION_REGISTRY.get(evidence.action.action_id) if evidence.action else None
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "kind": "EVIDENCE_STATE_PRESENTATION",
        "evidence_state_id": record.evidence_state_id,
        "evidence_hash": record.evidence_hash,
        "entity": {"gene_id": evidence.entity.gene_id, "symbol": evidence.entity.symbol},
        "iteration_number": evidence.revision_index,
        "parent_evidence_hash": evidence.parent_evidence_hash,
        "action": None if evidence.action is None else {
            "action_id": evidence.action.action_id,
            "version": evidence.action.version,
            "title": definition.title if definition else None,
            "unit": definition.unit if definition else None,
        },
        "research_puzzle": None if evidence.puzzle is None else {
            "origin": evidence.puzzle.origin, "question": evidence.puzzle.question,
            "interpretation": evidence.puzzle.interpretation,
        },
        "deterministic_observations": _evidence_observations(evidence),
        "project_level_evidence": [
            {"project_id": row.project_id,
             **{key: metric_view(metric) for key, metric in row.metrics()}}
            for row in evidence.project_evidence
        ],
        "quality_and_fragility": {
            "checks_total": evidence.summary.total,
            "checks_verified": evidence.summary.verified,
            "checks_contradicted": evidence.summary.contradicted,
            "checks_not_observed": evidence.summary.not_observed,
            "warnings": list(evidence.warnings),
        },
        "missing_evidence": [
            {"needed_evidence": item.needed_evidence, "availability": item.availability.value,
             "reason": item.reason}
            for item in evidence.missing_evidence
        ],
        "provenance": {
            "gdc_release": evidence.provenance.gdc_release,
            "response_source_count": len(evidence.provenance.sources),
            "selection_artifact_sha256": evidence.provenance.selection_artifact_sha256,
            "action_registry_version": evidence.provenance.action_registry_version,
            "input_artifacts": [
                {"kind": item.kind, "ref": item.ref, "sha256": item.sha256, "verified": item.verified}
                for item in evidence.provenance.input_artifacts
            ],
        },
    }


def response_etag(payload: dict[str, Any]) -> str:
    """ETag over the actual response bytes, not the source artifact."""
    return hashlib.sha256(canonical_json(payload)).hexdigest()
