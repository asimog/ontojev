from __future__ import annotations

import hashlib
from typing import Any

from cancerjev.domain.events import canonical_json


def statistical_state_identity_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Scientific identity of a StatisticalState.

    Operational identity (state_id, run_id) and timestamps are excluded so the
    same scientific fixture content receives the same content hash in any run.
    """
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

    Excludes evidence_state_id, run_id, candidate_id, previous_evidence_state_id
    and per-result operational result ids. Retains entity, project/population
    membership, units, measurements, missingness, method/version, context,
    limitations and revision number.
    """
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
