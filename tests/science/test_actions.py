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
    decision = eligible_actions(state)[0]
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
    decision = eligible_actions({"schema_version": 1, "mode": "FAKE"})[0]
    assert decision.eligible is False
    assert "SNAPSHOT_NOT_LIVE_SCIENTIFIC_EVIDENCE" in decision.reasons
    assert "PROVENANCE_SOURCES_MISSING" in decision.reasons


def test_missing_provenance_sources_block_eligibility():
    state = _live_state()
    state["provenance"]["sources"] = []
    decision = eligible_actions(state)[0]
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
