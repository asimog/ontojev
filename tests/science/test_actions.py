"""Registered deterministic action contract tests. Offline and provider-free."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.domain.identity import content_hash, statistical_state_identity_payload
from cancerjev.science.actions import (
    ACTION_REGISTRY,
    CHECK_CONTRADICTED,
    CHECK_NOT_OBSERVED,
    CHECK_VERIFIED,
    ActionError,
    eligible_actions,
    execute,
)
from tests.science.test_methods import GENE, _build, _frame

ACTION_ID = "CHECK_EVIDENCE_INTEGRITY_V1"
SELECTION_REF = "selection-artifact"
RESPONSE_REF = "response-artifact"
SELECTION_PAYLOAD = {"selected_gene_ids": [GENE.gene_id], "provider_ranked_genes": [GENE.gene_id]}
RESPONSE_BYTES = b'{"data":{"hits":[]}}'


def _live_state(**overrides) -> dict:
    state = _build([_frame("TCGA-LUAD")], state_id="state-live")
    state["tested_context"]["examined_genes_ref"] = SELECTION_REF
    state["tested_context"]["examined_genes_hash"] = hashlib.sha256(canonical_json(SELECTION_PAYLOAD)).hexdigest()
    state["tested_context"]["coverage"]["examined_genes_n"] = 1
    state["provenance"]["sources"] = [
        {
            **(state["provenance"]["sources"][0]),
            "response_artifact_id": RESPONSE_REF,
            "response_sha256": hashlib.sha256(RESPONSE_BYTES).hexdigest(),
            "request_id": "request-1",
        },
    ]
    state.update(overrides)
    state["state_hash"] = content_hash(statistical_state_identity_payload(state))
    return state


def _reader(*, selection: bytes | None, response: bytes | None):
    def read(artifact_id: str) -> bytes | None:
        if artifact_id == SELECTION_REF:
            return selection
        if artifact_id == RESPONSE_REF:
            return response
        return None

    return read


def _checks(outcome) -> dict:
    return {check["check_id"]: check["outcome"] for check in outcome.checks}


def test_registered_action_has_an_explicit_contract():
    definition = ACTION_REGISTRY[ACTION_ID]
    assert definition.version == "1"
    assert definition.question and definition.interpretation
    assert definition.required_evidence and definition.limitations
    assert definition.ref()["method_id"] == "EVIDENCE_INTEGRITY_V1"


def test_eligible_live_state_passes_every_integrity_check():
    state = _live_state()
    decision = eligible_actions(state, "STATISTICAL_STATE")[0]
    assert decision.eligible is True and decision.reasons == ()
    outcome = execute(ACTION_ID, state, read_artifact=_reader(selection=canonical_json(SELECTION_PAYLOAD),
                                                             response=RESPONSE_BYTES))
    assert outcome.status == "COMPLETED"
    assert _checks(outcome) == {
        "COHORT_FRAME_AGREEMENT": CHECK_VERIFIED,
        "EXPRESSION_COVERAGE_ARITHMETIC": CHECK_VERIFIED,
        "MUTATION_COUNT_SCOPE": CHECK_VERIFIED,
        "TESTED_UNIVERSE_REPRODUCIBLE": CHECK_VERIFIED,
        "RESPONSE_ARTIFACT_INTEGRITY": CHECK_VERIFIED,
    }
    assert outcome.contradictions == 0 and outcome.verified == 5 and outcome.not_observed == 0


def test_fixture_or_partial_snapshot_is_ineligible():
    decision = eligible_actions({"schema_version": 1, "mode": "FAKE"}, "STATISTICAL_STATE")[0]
    assert decision.eligible is False
    assert "SNAPSHOT_NOT_LIVE_SCIENTIFIC_EVIDENCE" in decision.reasons
    assert "PROVENANCE_SOURCES_MISSING" in decision.reasons


def test_missing_provenance_sources_block_eligibility():
    state = _live_state()
    state["provenance"]["sources"] = []
    decision = eligible_actions(state, "STATISTICAL_STATE")[0]
    assert decision.eligible is False
    assert "PROVENANCE_SOURCES_MISSING" in decision.reasons


def test_ineligible_action_refuses_to_execute():
    with pytest.raises(ActionError) as exc:
        execute(ACTION_ID, {"schema_version": 1, "mode": "FAKE"}, read_artifact=lambda _: None)
    assert exc.value.code == "ACTION_INELIGIBLE"


def _affected_count_exceeds_ssm_coverage(state: dict) -> None:
    state["mutation"]["project_results"][0]["affected_case_count"]["value"] = 999


def _expression_coverage_arithmetic_breaks(state: dict) -> None:
    state["expression"]["project_results"][0]["coverage"]["cases_with_expression"]["value"] = 5


def _lane_examined_frame_disagrees(state: dict) -> None:
    state["expression"]["project_results"][0]["coverage"]["examined_cases"]["value"] = 59


@pytest.mark.parametrize(
    ("mutate", "expected_check"),
    [
        (_affected_count_exceeds_ssm_coverage, "MUTATION_COUNT_SCOPE"),
        (_expression_coverage_arithmetic_breaks, "EXPRESSION_COVERAGE_ARITHMETIC"),
        (_lane_examined_frame_disagrees, "COHORT_FRAME_AGREEMENT"),
    ],
)
def test_inconsistent_recorded_evidence_is_contradicted(mutate, expected_check):
    state = _live_state()
    mutate(state)
    outcome = execute(ACTION_ID, state, read_artifact=_reader(selection=canonical_json(SELECTION_PAYLOAD),
                                                             response=RESPONSE_BYTES))
    outcomes = _checks(outcome)
    assert outcomes[expected_check] == CHECK_CONTRADICTED
    assert outcome.contradictions >= 1


def test_tampered_selection_artifact_is_contradicted():
    state = _live_state()
    outcome = execute(ACTION_ID, state, read_artifact=_reader(selection=b"{}", response=RESPONSE_BYTES))
    assert _checks(outcome)["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_CONTRADICTED


def test_absent_retained_bytes_are_not_observed_never_a_silent_pass():
    state = _live_state()
    outcome = execute(ACTION_ID, state, read_artifact=_reader(selection=None, response=None))
    outcomes = _checks(outcome)
    assert outcomes["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_NOT_OBSERVED
    assert outcomes["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_NOT_OBSERVED
    assert outcomes["COHORT_FRAME_AGREEMENT"] == CHECK_VERIFIED
    assert outcome.not_observed == 2


def test_unlinked_source_attempts_are_not_observed():
    state = _live_state()
    state["provenance"]["sources"][0]["request_id"] = None
    outcome = execute(ACTION_ID, state, read_artifact=_reader(selection=canonical_json(SELECTION_PAYLOAD),
                                                             response=RESPONSE_BYTES))
    assert _checks(outcome)["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_NOT_OBSERVED


def test_gene_absent_from_retained_selection_is_contradicted():
    state = _live_state()
    outcome = execute(
        ACTION_ID, state,
        read_artifact=_reader(selection=canonical_json({"selected_gene_ids": ["OTHER-GENE"]}),
                              response=RESPONSE_BYTES),
    )
    assert _checks(outcome)["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_CONTRADICTED


def test_execution_is_deterministic_and_leaves_the_snapshot_untouched():
    state = _live_state()
    before = copy.deepcopy(state)
    reader = _reader(selection=canonical_json(SELECTION_PAYLOAD), response=RESPONSE_BYTES)
    first = execute(ACTION_ID, state, read_artifact=reader)
    second = execute(ACTION_ID, state, read_artifact=reader)
    assert list(first.checks) == list(second.checks)
    assert json.dumps(first.checks, sort_keys=True) == json.dumps(second.checks, sort_keys=True)
    assert state == before, "a deterministic action must never rewrite the evidence it reads"


REVISION_ACTION_ID = "CHECK_REVISION_FAITHFULNESS_V1"
SOURCE_STATE_REF = "source-state-artifact"


def _metric_block(metric: dict) -> dict:
    return {"value": metric.get("value"), "unit": metric.get("unit", "cases"),
            "availability": metric.get("availability"), "reason_code": metric.get("reason_code")}


def _revision_from(source: dict, **overrides) -> dict:
    mutation = source["mutation"]["project_results"][0]
    coverage = source["expression"]["project_results"][0]["coverage"]
    rows = [{
        "project_id": mutation["project_id"],
        "affected_case_count": _metric_block(mutation["affected_case_count"]),
        "examined_cases": _metric_block(mutation["examined_cases"]),
        "project_case_with_ssm": _metric_block(mutation["project_case_with_ssm"]),
        "cases_with_expression": _metric_block(coverage["cases_with_expression"]),
        "missing_measurements": _metric_block(coverage["missing_measurements"]),
    }]
    definition = ACTION_REGISTRY[ACTION_ID]
    revision = {
        "schema_version": 2, "mode": "LIVE", "evidence_state_id": "revision-1", "run_id": "run-1",
        "candidate_id": "candidate-1", "created_at": "2026-09-23T00:00:00Z",
        "previous_evidence_state_id": "baseline-0", "iteration_number": 1,
        "entity": source["entity"],
        "source_statistical_state": {
            "state_id": source["state_id"], "state_identity_hash": source["state_hash"],
            "state_artifact_id": SOURCE_STATE_REF,
            "state_artifact_sha256": hashlib.sha256(canonical_json(source)).hexdigest(),
        },
        "research_puzzle": {"origin": "DETERMINISTIC_ACTION_REGISTRY", "question": "q",
                            "interpretation": "i", "proposed_action_ids": [ACTION_ID]},
        "research_only_notice": "REAL OPEN-ACCESS GDC EVIDENCE",
        "action": {**definition.ref(), "title": definition.title, "unit": definition.unit,
                   "required_evidence": list(definition.required_evidence),
                   "limitations": list(definition.limitations)},
        "deterministic_observations": [],
        "project_level_evidence": rows,
        "cross_project_patterns": {"status": "NOT_APPLICABLE", "limitations": []},
        "missing_evidence": [],
        "quality_and_fragility": {"checks_total": 5, "checks_verified": 5, "checks_contradicted": 0,
                                  "checks_not_observed": 0, "warnings": []},
        "provenance": {**source["provenance"], "input_artifacts": []},
    }
    revision.update(overrides)
    return revision


def _source_reader(source: dict | None):
    def read(artifact_id: str) -> bytes | None:
        return canonical_json(source) if artifact_id == SOURCE_STATE_REF and source is not None else None

    return read


def test_revision_action_is_eligible_only_for_a_revision():
    source = _live_state()
    revision = _revision_from(source)
    revision_decisions = eligible_actions(revision, "EVIDENCE_STATE")
    assert [item.action_id for item in revision_decisions] == [REVISION_ACTION_ID]
    assert revision_decisions[0].eligible is True and revision_decisions[0].reasons == ()
    assert [item.action_id for item in eligible_actions(revision, "STATISTICAL_STATE")] == [ACTION_ID]
    assert eligible_actions(source, "EVIDENCE_STATE")[0].eligible is False
    assert eligible_actions(source, "STATISTICAL_STATE")[0].eligible is True


def test_revision_action_has_an_explicit_contract():
    definition = ACTION_REGISTRY[REVISION_ACTION_ID]
    assert definition.input_kind == "EVIDENCE_STATE"
    assert definition.version == "1" and definition.method_id == "REVISION_FAITHFULNESS_V1"
    assert definition.question and definition.interpretation and definition.limitations
    assert definition.ref()["action_id"] == REVISION_ACTION_ID


def test_faithful_revision_passes_every_check():
    source = _live_state()
    revision = _revision_from(source)
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    assert outcome.status == "COMPLETED"
    assert _checks(outcome) == {
        "SOURCE_EVIDENCE_RESTATED": CHECK_VERIFIED,
        "SOURCE_PROVENANCE_UNCHANGED": CHECK_VERIFIED,
        "SOURCE_STATE_IDENTITY_REPRODUCIBLE": CHECK_VERIFIED,
        "REVISION_CHAIN_LINKED": CHECK_VERIFIED,
    }
    assert outcome.contradictions == 0 and outcome.verified == 4
    assert any(entry["kind"] == "SOURCE_STATE_ARTIFACT" and entry["verified"] is True
               for entry in outcome.inputs)


def test_restated_metric_mismatch_is_contradicted():
    source = _live_state()
    revision = _revision_from(source)
    revision["project_level_evidence"][0]["affected_case_count"]["value"] = 999
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    assert _checks(outcome)["SOURCE_EVIDENCE_RESTATED"] == CHECK_CONTRADICTED


def test_provenance_substitution_is_contradicted():
    source = _live_state()
    revision = _revision_from(source)
    revision["provenance"]["sources"] = revision["provenance"]["sources"] + [
        {"endpoint": "/cases", "normalized_request_hash": "injected", "response_sha256": "0" * 64},
    ]
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    assert _checks(outcome)["SOURCE_PROVENANCE_UNCHANGED"] == CHECK_CONTRADICTED


def test_tampered_source_artifact_is_contradicted():
    source = _live_state()
    revision = _revision_from(source)
    tampered = {**source, "state_hash": "f" * 64}
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(tampered))
    assert _checks(outcome)["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == CHECK_CONTRADICTED


def test_unknown_producing_action_version_is_contradicted():
    source = _live_state()
    revision = _revision_from(source)
    revision["action"]["version"] = "99"
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    assert _checks(outcome)["REVISION_CHAIN_LINKED"] == CHECK_CONTRADICTED


def test_unavailable_source_artifact_is_not_observed():
    revision = _revision_from(_live_state())
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(None))
    outcomes = _checks(outcome)
    assert outcomes["SOURCE_EVIDENCE_RESTATED"] == CHECK_NOT_OBSERVED
    assert outcomes["SOURCE_PROVENANCE_UNCHANGED"] == CHECK_NOT_OBSERVED
    assert outcomes["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == CHECK_NOT_OBSERVED
    assert outcome.not_observed >= 3 and outcome.contradictions == 0


def test_revision_without_parent_is_ineligible():
    source = _live_state()
    revision = _revision_from(source, previous_evidence_state_id=None)
    decision = eligible_actions(revision, "EVIDENCE_STATE")[0]
    assert decision.eligible is False
    assert "REVISION_PARENT_MISSING" in decision.reasons
    with pytest.raises(ActionError):
        execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))


def test_revision_action_is_deterministic_and_leaves_the_revision_untouched():
    source = _live_state()
    revision = _revision_from(source)
    before = copy.deepcopy(revision)
    first = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    second = execute(REVISION_ACTION_ID, revision, read_artifact=_source_reader(source))
    assert json.dumps(first.checks, sort_keys=True) == json.dumps(second.checks, sort_keys=True)
    assert revision == before
