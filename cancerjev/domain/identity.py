from __future__ import annotations

import hashlib
from typing import Any

from cancerjev.domain.events import canonical_json
from cancerjev.domain.measurements import ContractError


def statistical_state_identity_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Scientific identity of a StatisticalState.

    Identity is deterministic scientific evidence plus scientifically meaningful
    tested context. Operational metadata and provider-ranking metadata are not
    scientific truth, so they are excluded:

    * state_id, run_id, created_at and every other clock value;
    * the acquisition attempt link (request_id, attempt_no, from_cache) and the
      retained response artifact id/retrieval time, because a cache hit and a
      network fetch of the same canonical request are the same evidence;
    * provider discovery rank and provider ``_score``, which stay quarantined as
      provider metadata in ``generation.discovery`` and
      ``mutation.project_results[].provider_discovery_rank``;
    * ``tested_context.examined_genes_ref``, an artifact id for the same context.

    Identity does change when a measurement, population, sample mapping, unit,
    method/version, missingness, scope or tested-universe context changes.
    ``tested_context.examined_genes_hash`` is deliberately retained: which genes
    the run examined (and what selection supplied them) is scientific tested
    context, so a different examined universe is a different state even when the
    reported measurement happens to match. Sources are projected to their
    scientific components only: endpoint, canonical request hash, response hash,
    parser version, completeness and release.
    """
    if type(state.get("schema_version")) is not int or state["schema_version"] not in (1, 2):
        raise ContractError("legacy state identity requires schema 1 or 2", "UNSUPPORTED_SCHEMA_VERSION")
    if state["schema_version"] == 2:
        provenance = state["provenance"]
        generation = {
            key: value for key, value in state["generation"].items()
            if key not in {"discovery", "rank_in_lane"}
        }
        mutation = dict(state["mutation"])
        mutation["project_results"] = [
            {key: value for key, value in result.items() if key != "provider_discovery_rank"}
            for result in state["mutation"]["project_results"]
        ]
        tested_context = {key: value for key, value in state["tested_context"].items()
                          if key != "examined_genes_ref"}
        return {
            "schema_version": 2,
            "entity": state["entity"],
            "scope": state["scope"],
            "generation": generation,
            "populations": state["populations"],
            "mutation": mutation,
            "expression": state["expression"],
            "cross_project": state["cross_project"],
            "quality": state["quality"],
            "tested_context": tested_context,
            "provenance": {
                "gdc_release": provenance["gdc_release"],
                "sources": [
                    {
                        "endpoint": source["endpoint"],
                        "request_hash": source["normalized_request_hash"],
                        "response_sha256": source["response_sha256"],
                        "parser_version": source["parser_version"],
                        "completeness": source["completeness"],
                        "source_release": source["source_release"],
                    }
                    for source in provenance["sources"]
                ],
                "methods": provenance["methods"],
                "environment_hash": provenance["environment_hash"],
            },
        }
    return {
        "schema_version": state["schema_version"],
        "fixture_notice": state["fixture_notice"],
        "entity": state["entity"],
        "scope": state["scope"],
        "pattern": state["pattern"],
        "quality": state["quality"],
        "tested_context": state["tested_context"],
        "provenance": state["provenance"],
    }


def evidence_state_identity_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    """Scientific identity of an EvidenceState.

    Identity is the deterministic evidence a revision records: entity, tested
    context, populations, observed values, units, missingness, method/version,
    action definition and revision number. Operational metadata is excluded:
    evidence_state_id, run_id, candidate_id, previous_evidence_state_id (the
    revision link, not the revision number), created_at, artifact ids and
    retrieval/attempt fields, and per-observation ``result_id``.

    For live deterministic evidence (schema 2) identity does change when an
    observed check outcome, input measurement, population, unit, action version
    or input artifact hash changes, and provenance is projected to scientific
    components (endpoint, canonical request hash, response hash, parser version,
    completeness, release, selection artifact hash). The source revision is bound
    by its scientific ``state_identity_hash`` only: the source artifact's byte hash
    is an operational record (its JSON carries run timestamps) and stays in
    provenance, so identical evidence keeps one identity across runs.
    """
    if type(evidence.get("schema_version")) is not int or evidence["schema_version"] not in (1, 2):
        raise ContractError("legacy evidence identity requires schema 1 or 2", "UNSUPPORTED_SCHEMA_VERSION")
    if evidence["schema_version"] == 2:
        provenance = evidence["provenance"]
        source = evidence["source_statistical_state"]
        return {
            "schema_version": 2,
            "mode": evidence["mode"],
            "iteration_number": evidence["iteration_number"],
            "entity": evidence["entity"],
            "source_statistical_state": {
                "state_identity_hash": source["state_identity_hash"],
            },
            "research_puzzle": evidence["research_puzzle"],
            "research_only_notice": evidence["research_only_notice"],
            "action": evidence["action"],
            "deterministic_observations": [
                {key: value for key, value in observation.items() if key != "result_id"}
                for observation in evidence["deterministic_observations"]
            ],
            "project_level_evidence": evidence["project_level_evidence"],
            "cross_project_patterns": evidence["cross_project_patterns"],
            "missing_evidence": evidence["missing_evidence"],
            "quality_and_fragility": evidence["quality_and_fragility"],
            "provenance": {
                "gdc_release": provenance["gdc_release"],
                "sources": [
                    {
                        "endpoint": entry["endpoint"],
                        "request_hash": entry["normalized_request_hash"],
                        "response_sha256": entry["response_sha256"],
                        "parser_version": entry["parser_version"],
                        "completeness": entry["completeness"],
                        "source_release": entry["source_release"],
                    }
                    for entry in provenance["sources"]
                ],
                "methods": provenance["methods"],
                "environment_hash": provenance["environment_hash"],
                "action_registry_version": provenance["action_registry_version"],
                "selection_artifact_sha256": provenance["selection_artifact_sha256"],
            },
        }
    return {
        "schema_version": evidence["schema_version"],
        "fixture_notice": evidence["fixture_notice"],
        "iteration_number": evidence["iteration_number"],
        "entity": evidence["entity"],
        "source_statistical_state": evidence["source_statistical_state"],
        "research_puzzle": evidence["research_puzzle"],
        "deterministic_observations": [
            {key: value for key, value in observation.items() if key != "result_id"}
            for observation in evidence["deterministic_observations"]
        ],
        "project_level_evidence": evidence["project_level_evidence"],
        "cross_project_patterns": evidence["cross_project_patterns"],
        "missing_evidence": evidence["missing_evidence"],
        "quality_and_fragility": evidence["quality_and_fragility"],
        "provenance": evidence["provenance"],
    }


def content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()
