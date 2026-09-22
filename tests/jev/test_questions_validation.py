from __future__ import annotations

import pytest

from cancerjev.jev.questions import (
    WIDE_QUESTIONS,
    QuestionDefinition,
    question_set_hash,
    validate_definitions,
)
from cancerjev.jev.typesafe_adapter import _provider_error_code


def _definition(**overrides):
    base = dict(
        question_id="q", primitive="NOUL", version=1, instructions="Decide.",
        criteria={"true": "yes", "false": "no"}, applicability_rule="any_observation",
    )
    base.update(overrides)
    return QuestionDefinition(**base)


def test_current_wide_questions_are_valid():
    validate_definitions(WIDE_QUESTIONS)
    assert question_set_hash()


@pytest.mark.parametrize(
    "overrides",
    [
        {"question_id": ""},
        {"primitive": "MAGIC"},
        {"version": 0},
        {"instructions": "  "},
        {"applicability_rule": "unknown_rule"},
        {"primitive": "CHOICE", "criteria": {}},
        {"primitive": "CHOICE", "criteria": {str(index): "x" for index in range(256)}},
        {"primitive": "SCORE", "criteria": ["only-one"]},
        {"primitive": "SCORE", "criteria": [str(index) for index in range(11)]},
        {"criteria": {"maybe": "x"}},
    ],
)
def test_malformed_question_definitions_fail_closed(overrides):
    with pytest.raises(ValueError):
        validate_definitions((_definition(**overrides),))


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "PROVIDER_AUTH"),
        (403, "PROVIDER_AUTH"),
        (422, "PROVIDER_VALIDATION"),
        (429, "PROVIDER_RATE_LIMIT"),
        (529, "PROVIDER_OVERLOADED"),
        (500, "PROVIDER_ERROR"),
        (None, "PROVIDER_ERROR"),
    ],
)
def test_provider_errors_are_classified(status, expected):
    exc = Exception("boom")
    if status is not None:
        exc.status_code = status
    assert _provider_error_code(exc) == expected


def test_provider_error_code_reads_nested_response_status():
    class Response:
        status_code = 429

    exc = Exception("boom")
    exc.response = Response()
    assert _provider_error_code(exc) == "PROVIDER_RATE_LIMIT"
