from dataclasses import FrozenInstanceError

import pytest

from cancerjev.domain.hypotheses import DRAFT_FIELDS, read_hypothesis_draft
from cancerjev.research.hypotheses import HypothesisUnavailable, validate_generated_drafts


def _draft():
    return {"statement": "A hypothesis.", "proposed_mechanism": "Hypothetical only.",
            **{key: [] for key in DRAFT_FIELDS[2:]}}


@pytest.mark.parametrize("field,value", [
    ("predictions", ["x" * 2001]), ("contradicted_if", [""]),
    ("required_evidence", ["x"] * 11), ("distinguishing_tests", ["UNKNOWN_ACTION"]),
    ("measured_value", 10), ("statement", True),
])
def test_generated_fields_fail_closed(field, value):
    draft = _draft()
    draft[field] = value
    with pytest.raises(HypothesisUnavailable, match="GENERATOR_RESPONSE_MALFORMED"):
        validate_generated_drafts([draft], eligible_action_ids=[])


def test_draft_is_immutable_and_empty_test_list_remains_valid():
    draft = read_hypothesis_draft(_draft(), allowed_action_ids=frozenset())
    assert draft.distinguishing_tests == ()
    with pytest.raises(FrozenInstanceError):
        draft.statement = "changed"
