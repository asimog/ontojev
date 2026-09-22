from __future__ import annotations

import json

import pytest

from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.research.fixtures import evidence, statistical_states


def _state(run_id: str, make_id):
    state = statistical_states(run_id, make_id)[0]
    state["state_hash"] = content_hash(statistical_state_identity_payload(state))
    return state


def _clone(document: dict) -> dict:
    return json.loads(json.dumps(document))


def test_state_identity_ignores_operational_ids():
    first = _state("run-a", lambda name: f"a:{name}")
    second = _state("run-b", lambda name: f"b:{name}")
    assert first["state_id"] != second["state_id"]
    assert first["run_id"] != second["run_id"]
    assert content_hash(statistical_state_identity_payload(first)) == content_hash(statistical_state_identity_payload(second))


def test_state_identity_tracks_scientific_content():
    state = _state("run-a", lambda name: name)
    baseline = content_hash(statistical_state_identity_payload(state))
    changes = {
        "measurement": ("pattern", "effect_like_descriptive_value", 0.99),
        "unit": ("pattern", "unit", "other-unit"),
        "pattern shape": ("pattern", "shape", "other-shape"),
        "entity": ("entity", "gene_symbol", "OTHER"),
        "population membership": ("scope", "projects", ["SYNTHETIC-DEMO-A"]),
        "method": ("provenance", "methods", ["OTHER_METHOD_V1"]),
    }
    for label, (section, key, value) in changes.items():
        changed = _clone(state)
        changed[section][key] = value
        assert content_hash(statistical_state_identity_payload(changed)) != baseline, label


def test_evidence_identity_ignores_operational_ids():
    state = _state("run-a", lambda name: f"a:{name}")
    first = evidence("run-a", "candidate-a", state, lambda name: f"a:{name}")
    second = evidence("run-b", "candidate-b", state, lambda name: f"b:{name}")
    assert first["evidence_state_id"] != second["evidence_state_id"]
    assert first["candidate_id"] != second["candidate_id"]
    assert first["deterministic_observations"][0]["result_id"] != second["deterministic_observations"][0]["result_id"]
    assert content_hash(evidence_state_identity_payload(first)) == content_hash(evidence_state_identity_payload(second))


def test_evidence_identity_tracks_scientific_content():
    state = _state("run-a", lambda name: name)
    baseline_evidence = evidence("run-a", "candidate-a", state, lambda name: name)
    baseline = content_hash(evidence_state_identity_payload(baseline_evidence))
    changes = [
        ("measurement", ("deterministic_observations", 0, "effect", "value"), 0.42),
        ("unit", ("deterministic_observations", 0, "effect", "unit"), "other-unit"),
        ("sample size", ("deterministic_observations", 0, "n_effective"), 99),
        ("method version", ("deterministic_observations", 0, "method_version"), "2"),
        ("missingness", ("deterministic_observations", 0, "missingness", "count"), 7),
        ("project membership", ("project_level_evidence", 0, "project_id"), "OTHER-PROJECT"),
        ("limitations", ("deterministic_observations", 0, "limitations"), ["changed"]),
        ("revision", ("iteration_number",), 1),
    ]
    for label, path, value in changes:
        changed = _clone(baseline_evidence)
        cursor = changed
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        assert content_hash(evidence_state_identity_payload(changed)) != baseline, label


def test_content_hash_rejects_non_finite_numbers():
    with pytest.raises(ValueError):
        content_hash({"value": float("nan")})
    with pytest.raises(ValueError):
        content_hash({"value": float("inf")})
