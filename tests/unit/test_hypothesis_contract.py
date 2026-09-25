from dataclasses import FrozenInstanceError

import pytest

from cancerjev.domain.hypotheses import DRAFT_FIELDS, read_hypothesis_draft
from cancerjev.domain.measurements import ContractError
from cancerjev.research.hypotheses import HypothesisUnavailable, validate_generated_drafts

ACTION_ID = "CHECK_EVIDENCE_INTEGRITY_V1"


def _draft():
    return {"statement": "A hypothesis.", "proposed_mechanism": "Hypothetical only.",
            **{key: [] for key in DRAFT_FIELDS[2:]}}


@pytest.mark.parametrize("field,value", [
    ("predictions", ["x" * 2001]),
    ("distinguishing_tests", ["UNKNOWN_ACTION"]),
    ("measured_value", 10),
])
def test_generated_fields_fail_closed(field, value):
    draft = _draft()
    draft[field] = value
    with pytest.raises(HypothesisUnavailable, match="GENERATOR_RESPONSE_MALFORMED"):
        validate_generated_drafts([draft], eligible_action_ids=[])


def test_draft_is_immutable_and_empty_test_list_remains_valid():
    draft = read_hypothesis_draft(_draft(), allowed_action_ids=frozenset(), label="FIXTURE LABEL",
                                  generator="deterministic-template-v1")
    assert draft.distinguishing_tests == ()
    assert draft.generator_model is None
    assert draft.label == "FIXTURE LABEL"
    with pytest.raises(FrozenInstanceError):
        draft.statement = "changed"


def test_reader_rejects_an_action_that_is_not_eligible():
    draft = _draft()
    draft["distinguishing_tests"] = [ACTION_ID]
    with pytest.raises(ContractError):
        read_hypothesis_draft(draft, allowed_action_ids=frozenset(), label="LABEL",
                              generator="generator")


def test_validated_drafts_carry_generator_identity_and_bounded_lists():
    entry = _draft()
    entry["distinguishing_tests"] = [ACTION_ID]
    entry["predictions"] = ["a bounded prediction"]
    drafts, error = validate_generated_drafts(
        [entry], eligible_action_ids=[ACTION_ID], generator="injected-generator-v1",
        generator_model="model-x")
    assert error is None
    assert drafts[0].generator == "injected-generator-v1"
    assert drafts[0].generator_model == "model-x"
    assert drafts[0].predictions == ("a bounded prediction",)
    assert drafts[0].distinguishing_tests == (ACTION_ID,)


def test_generation_response_is_bounded_and_never_empty():
    with pytest.raises(HypothesisUnavailable, match="GENERATOR_RESPONSE_MALFORMED"):
        validate_generated_drafts([], eligible_action_ids=[])
    with pytest.raises(HypothesisUnavailable, match="GENERATOR_RESPONSE_MALFORMED"):
        validate_generated_drafts([_draft()] * 4, eligible_action_ids=[])
