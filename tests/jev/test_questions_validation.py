from __future__ import annotations

import pytest

from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    DEEP_QUESTIONS,
    WIDE_QUESTION_SET_VERSION,
    WIDE_QUESTIONS,
    QuestionDefinition,
    deep_question_set_hash,
    question_set_hash,
    validate_definitions,
    wide_question_set_hash,
)
from cancerjev.jev.typesafe_adapter import _provider_error_code


def _definition(**overrides):
    base = dict(
        question_id="q", primitive="NOUL", version=1, instructions="Decide.",
        criteria={"true": "yes", "false": "no"}, applicability_rule="any_observation",
    )
    base.update(overrides)
    return QuestionDefinition(**base)


def test_current_question_sets_are_valid():
    validate_definitions(WIDE_QUESTIONS)
    validate_definitions(DEEP_QUESTIONS)
    assert wide_question_set_hash() and deep_question_set_hash()
    assert wide_question_set_hash() != deep_question_set_hash()


def test_question_set_hash_requires_an_explicit_version():
    with pytest.raises(ValueError):
        question_set_hash((_definition(),), "")


def test_question_set_hash_is_stable_for_identical_definitions():
    assert question_set_hash((_definition(),), "v1") == question_set_hash((_definition(),), "v1")


def test_question_set_hash_covers_the_set_version():
    assert question_set_hash((_definition(),), "v1") != question_set_hash((_definition(),), "v2")
    assert question_set_hash(WIDE_QUESTIONS, WIDE_QUESTION_SET_VERSION) == wide_question_set_hash()
    assert question_set_hash(DEEP_QUESTIONS, DEEP_QUESTION_SET_VERSION) == deep_question_set_hash()


@pytest.mark.parametrize(
    "overrides",
    [
        {"applicability_rule": "mutation_observed"},
        {"instructions": "Decide something else."},
        {"version": 2},
        {"criteria": {"true": "yes", "false": "maybe"}},
    ],
)
def test_question_set_hash_covers_semantics(overrides):
    assert question_set_hash((_definition(),), "v1") != question_set_hash((_definition(**overrides),), "v1")


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
