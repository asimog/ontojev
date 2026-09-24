"""Historical preservation and strict scientific boundary failures."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from cancerjev.domain.codecs import read_evidence, read_state
from cancerjev.domain.events import canonical_json
from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.domain.legacy_codecs import LegacyArtifact, _metric
from cancerjev.domain.measurements import ContractError
from cancerjev.research.fixtures import evidence, statistical_states
from tests.integration.test_deep_slice import _dispatched_slice
from tests.science.test_methods import _build, _frame


@pytest.mark.parametrize("index", range(12))
def test_every_fixture_v1_remains_original_bytes_and_identity(index):
    state = statistical_states("fixture", lambda name: name)[index]
    state["state_hash"] = content_hash(statistical_state_identity_payload(state))
    raw = json.dumps(state, indent=2).encode()
    result = read_state(raw, expected_hash=state["state_hash"])
    assert isinstance(result, LegacyArtifact)
    assert result.schema_version == 1 and result.original_bytes == raw
    assert result.boundary_representation() == state
    presentation = result.boundary_representation()
    presentation["entity"]["gene_id"] = "CHANGED"
    assert result.boundary_representation() == state
    for followup in (False, True):
        revision = evidence("fixture", "candidate", state, lambda name: name, followup=followup)
        content = canonical_json(revision)
        parsed = read_evidence(content, expected_hash=content_hash(evidence_state_identity_payload(revision)))
        assert parsed.original_bytes == content and parsed.schema_version == 1


@pytest.mark.parametrize("expression", [False, True])
def test_live_v2_retains_legacy_units_statuses_and_identity(expression):
    frame = _frame("TCGA-LUAD")
    if not expression:
        frame = replace(frame, expression_values=None, provider_selection=None)
    state = _build([frame])
    result = read_state(canonical_json(state), expected_hash=state["state_hash"])
    assert isinstance(result, LegacyArtifact)
    assert result.schema_version == 2
    assert result.boundary_representation() == state
    assert any(m.availability == "NOT_APPLICABLE" for m in result.metrics)
    assert any(m.unit == "cases" for m in result.metrics)
    if not expression:
        assert result.boundary_representation()["expression"]["project_results"][0]["availability"] == "NOT_ACQUIRED"
        assert any(m.availability == "NOT_OBSERVED" and m.reason == "VALUES_NOT_ACQUIRED" for m in result.metrics)


def test_missing_availability_is_unavailable_and_false_zero_artifacts_still_fail():
    # Stage 3 fixes the recorded Stage 1 composition failure, not the parser guard.
    state = _build([_frame("TCGA-LUAD", expression=False)])
    measurement = state["expression"]["coverage"]["cases_with_expression"]
    assert measurement["availability"] == "NOT_OBSERVED"
    assert measurement["value"] is None
    assert read_state(canonical_json(state)).scientific_hash == state["state_hash"]
    measurement["value"] = 0
    state["state_hash"] = content_hash(statistical_state_identity_payload(state))
    with pytest.raises(ContractError, match="unavailable metric has a value"):
        read_state(canonical_json(state))


def test_legacy_reader_cannot_retain_a_mutable_input_buffer():
    data = bytearray(canonical_json(_build([_frame("TCGA-LUAD")])))
    with pytest.raises(ContractError, match="immutable bytes"):
        read_state(data)


def test_legacy_count_parser_preserves_integer_precision():
    value = 2 ** 53 + 1
    parsed = _metric({"availability": "OBSERVED", "value": value, "unit": "count"}, "count")
    assert parsed.value == value


@pytest.mark.parametrize("mutation", ["null", "bool", "unavailable_value", "count", "schema", "population", "deleted", "identity"])
def test_malformed_historical_state_rejected_without_rewriting(mutation):
    state = _build([_frame("TCGA-LUAD")])
    metric = state["mutation"]["project_results"][0]["affected_case_count"]
    if mutation == "null":
        metric["value"] = None
    elif mutation == "bool":
        metric["value"] = True
    elif mutation == "unavailable_value":
        metric["availability"] = "NOT_OBSERVED"
    elif mutation == "count":
        metric["value"] = -1
    elif mutation == "schema":
        state["schema_version"] = 1
    elif mutation == "population":
        state["populations"][0]["examined_n"] = 61
    elif mutation == "deleted":
        del state["expression"]["project_results"][0]["coverage"]
    else:
        state["state_hash"] = "0" * 64
    raw = canonical_json(state)
    with pytest.raises(ContractError):
        read_state(raw)
    assert raw == canonical_json(state)


@pytest.mark.parametrize("identity_function", [statistical_state_identity_payload, evidence_state_identity_payload])
@pytest.mark.parametrize("schema", [None, True, "2", 2.0, 3, 99])
def test_legacy_identity_does_not_fall_through_unknown_versions(identity_function, schema):
    with pytest.raises(ContractError, match="UNSUPPORTED_SCHEMA_VERSION"):
        identity_function({"schema_version": schema})


def test_v2_deep_replay_readers_and_existing_event_order(runtime, monkeypatch):
    run_id, _, repository = _dispatched_slice(runtime, monkeypatch, authorized=True)
    artifacts = runtime[2]
    for row in repository.list_table("statistical_states", run_id):
        raw = artifacts.read(repository.artifact(row["artifact_id"])["relative_path"])
        parsed = read_state(raw, expected_hash=row["state_hash"])
        assert parsed.original_bytes == raw
    candidate = next(c for c in repository.list_table("candidates", run_id) if c["entity"]["gene_symbol"] == "GENEONE")
    revisions = repository.evidence_revisions(candidate["candidate_id"])
    assert [r["iteration"] for r in revisions] == [0, 1, 2]
    for row in revisions:
        raw = artifacts.read(repository.artifact(row["artifact_id"])["relative_path"])
        result = read_evidence(raw, expected_hash=row["evidence_hash"])
        assert result.original_bytes == raw and result.schema_version == 2
        assert result.check_summary.total == (0, 5, 4)[row["iteration"]]
        if row["iteration"]:
            broken = deepcopy(result.boundary_representation())
            broken["quality_and_fragility"]["checks_verified"] -= 1
            with pytest.raises(ContractError):
                read_evidence(canonical_json(broken))
    event_types = [e["type"] for e in repository.events(run_id, 0, 700)["items"]]
    selected = [e for e in event_types if e in {
        "EVIDENCE_STATE_CREATED", "FOLLOWUP_STARTED", "FOLLOWUP_COMPLETED", "NEXT_MOVE_SELECTED",
        "NEXT_MOVE_DISPATCHED", "JEV_DEEP_EVIDENCE_JUDGED", "DOSSIER_CREATED", "RUN_COMPLETED",
    }]
    assert selected == [
        "EVIDENCE_STATE_CREATED", "FOLLOWUP_STARTED", "EVIDENCE_STATE_CREATED", "FOLLOWUP_COMPLETED",
        "JEV_DEEP_EVIDENCE_JUDGED", "NEXT_MOVE_SELECTED", "FOLLOWUP_STARTED", "EVIDENCE_STATE_CREATED",
        "FOLLOWUP_COMPLETED", "NEXT_MOVE_DISPATCHED", "JEV_DEEP_EVIDENCE_JUDGED", "NEXT_MOVE_SELECTED",
        "NEXT_MOVE_DISPATCHED", "DOSSIER_CREATED", "RUN_COMPLETED",
    ]
