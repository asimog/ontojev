from __future__ import annotations

import math

import pytest

from cancerjev.jev.contracts import JevContractError, validate_answers
from cancerjev.jev.questions import WIDE_QUESTIONS, WIDE_QUESTIONS_BY_ID


def _valid_answers() -> dict:
    return {
        "evidence_quality_adequate": {"kind": "noul", "probability_yes": 0.8},
        "mutation_evidence_coherent": {"kind": "noul", "probability_yes": 0.6},
        "expression_evidence_coherent": {"kind": "noul", "probability_yes": 0.7},
        "signal_explained_by_coverage": {"kind": "noul", "probability_yes": 0.2},
        "unresolved_uncertainty_material": {"kind": "noul", "probability_yes": 0.75},
        "warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.8},
        "dominant_limitation": {
            "kind": "choice", "choice": "COVERAGE", "confidence": 0.75,
            "probabilities": {
                "COVERAGE": 0.75, "MISSINGNESS": 0.05, "MUTATION_ABSENCE": 0.05,
                "EXPRESSION_SPARSITY": 0.05, "PARTIAL_AGGREGATION": 0.05, "NONE": 0.025,
                "OTHER": 0.025,
            },
        },
    }


def test_valid_answers_pass_and_are_normalized():
    validated = validate_answers(WIDE_QUESTIONS, _valid_answers())
    assert validated["warrants_deeper_investigation"] == {"kind": "noul", "probability_yes": 0.8}
    assert validated["dominant_limitation"]["choice"] == "COVERAGE"
    assert set(validated) == {definition.question_id for definition in WIDE_QUESTIONS}


def test_missing_answer_fails_closed():
    answers = _valid_answers()
    del answers["dominant_limitation"]
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "MISSING_ANSWER"


def test_unknown_question_id_fails_closed():
    answers = _valid_answers()
    answers["extra_question"] = {"kind": "noul", "probability_yes": 0.5}
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "UNKNOWN_QUESTION"


def test_wrong_primitive_fails_closed():
    answers = _valid_answers()
    answers["warrants_deeper_investigation"] = {"kind": "choice", "choice": "WIDESPREAD_RECURRENCE",
                                                "confidence": 0.9, "probabilities": {"WIDESPREAD_RECURRENCE": 1.0}}
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "INVALID_PRIMITIVE"


@pytest.mark.parametrize("value", [1.2, -0.1, float("nan"), float("inf"), "0.5", None, True])
def test_invalid_noul_probability_fails_closed(value):
    answers = _valid_answers()
    answers["warrants_deeper_investigation"] = {"kind": "noul", "probability_yes": value}
    with pytest.raises(JevContractError):
        validate_answers(WIDE_QUESTIONS, answers)


def test_choice_outside_roster_fails_closed():
    answers = _valid_answers()
    answers["dominant_limitation"]["choice"] = "MADE_UP_LIMITATION"
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "INVALID_CHOICE"


def test_choice_distribution_mismatch_fails_closed():
    answers = _valid_answers()
    answers["dominant_limitation"]["probabilities"] = {"COVERAGE": 1.0}
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "DISTRIBUTION_MISMATCH"


def test_choice_distribution_must_sum_to_one():
    answers = _valid_answers()
    answers["dominant_limitation"]["probabilities"] = {
        "COVERAGE": 0.5, "MISSINGNESS": 0.5, "MUTATION_ABSENCE": 0.5,
        "EXPRESSION_SPARSITY": 0.0, "PARTIAL_AGGREGATION": 0.0, "NONE": 0.0, "OTHER": 0.0,
    }
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "INVALID_DISTRIBUTION"


def test_invalid_confidence_fails_closed():
    answers = _valid_answers()
    answers["dominant_limitation"]["confidence"] = math.nan
    with pytest.raises(JevContractError) as exc:
        validate_answers(WIDE_QUESTIONS, answers)
    assert exc.value.code == "INVALID_NUMBER"


def test_score_validation_rules():
    definition = WIDE_QUESTIONS_BY_ID["dominant_limitation"]
    score_definition = type(definition)(
        question_id="test_score", primitive="SCORE", version=1, instructions="test",
        criteria=["none", "low", "medium", "high"], applicability_rule="any_observation",
    )
    good = {"kind": "score", "score": 2.4, "confidence": 0.6,
            "probabilities": {"0": 0.0, "1": 0.2, "2": 0.4, "3": 0.4},
            "legend": {"0": "none", "1": "low", "2": "medium", "3": "high"}}
    validated = validate_answers((score_definition,), {"test_score": good})
    assert validated["test_score"]["score"] == 2.4
    for mutation, code in (
        ({"score": 4.2}, "INVALID_SCORE_LEVEL"),
        ({"probabilities": {"0": 0.0, "1": 0.2, "2": 0.4, "3": 0.3}}, "INVALID_DISTRIBUTION"),
        ({"legend": {"0": "none", "1": "low", "2": "medium"}}, "INVALID_LEGEND"),
        ({"confidence": 2.0}, "INVALID_PROBABILITY"),
    ):
        broken = {**good, **mutation}
        with pytest.raises(JevContractError) as exc:
            validate_answers((score_definition,), {"test_score": broken})
        assert exc.value.code == code
