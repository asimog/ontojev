"""Application-owned Jev answer contracts with fail-closed validation.

Provider objects never leave the adapter; everything here is plain data. No
default is ever fabricated: a missing or malformed answer is an error, not a zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from cancerjev.jev.questions import QuestionDefinition

PROBABILITY_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class NoulAnswer:
    question_id: str
    probability_yes: float


@dataclass(frozen=True)
class ChoiceAnswer:
    question_id: str
    choice: str
    confidence: float
    probabilities: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ScoreAnswer:
    question_id: str
    score: float
    confidence: float
    probabilities: tuple[tuple[str, float], ...]
    legend: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ValidatedAnswers:
    answers: tuple[NoulAnswer | ChoiceAnswer | ScoreAnswer, ...]

    def boundary_representation(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for answer in self.answers:
            if isinstance(answer, NoulAnswer):
                value = {"kind": "noul", "probability_yes": answer.probability_yes}
            elif isinstance(answer, ChoiceAnswer):
                value = {"kind": "choice", "choice": answer.choice, "confidence": answer.confidence,
                         "probabilities": dict(answer.probabilities)}
            else:
                value = {"kind": "score", "score": answer.score, "confidence": answer.confidence,
                         "probabilities": dict(answer.probabilities), "legend": dict(answer.legend)}
            result[answer.question_id] = value
        return result


def read_answers(definitions: tuple[QuestionDefinition, ...], raw: Any) -> ValidatedAnswers:
    validated = validate_answers(definitions, raw)
    answers: list[NoulAnswer | ChoiceAnswer | ScoreAnswer] = []
    for key, value in validated.items():
        if value["kind"] == "noul":
            answers.append(NoulAnswer(key, value["probability_yes"]))
        elif value["kind"] == "choice":
            answers.append(ChoiceAnswer(key, value["choice"], value["confidence"],
                                        tuple(sorted(value["probabilities"].items()))))
        else:
            answers.append(ScoreAnswer(key, value["score"], value["confidence"],
                                       tuple(sorted(value["probabilities"].items())),
                                       tuple(sorted(value["legend"].items()))))
    return ValidatedAnswers(tuple(answers))


class JevContractError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _finite(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JevContractError("INVALID_NUMBER", f"{context}: not a number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise JevContractError("INVALID_NUMBER", f"{context}: out of finite range") from exc
    if not math.isfinite(number):
        raise JevContractError("INVALID_NUMBER", f"{context}: non-finite")
    return number


def _probability(value: Any, context: str) -> float:
    number = _finite(value, context)
    if not 0.0 <= number <= 1.0:
        raise JevContractError("INVALID_PROBABILITY", f"{context}: {number} outside [0,1]")
    return number


def _probability_map(raw: Any, expected_keys: list[str], context: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise JevContractError("INVALID_DISTRIBUTION", f"{context}: not a map")
    keys = sorted(str(key) for key in raw)
    if keys != sorted(expected_keys):
        raise JevContractError(
            "DISTRIBUTION_MISMATCH", f"{context}: keys {keys} != expected {sorted(expected_keys)}"
        )
    probabilities = {str(key): _probability(value, f"{context}.{key}") for key, value in raw.items()}
    total = sum(probabilities.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise JevContractError("INVALID_DISTRIBUTION", f"{context}: probabilities sum to {total}")
    return probabilities


def validate_answer(definition: QuestionDefinition, raw: dict[str, Any]) -> dict[str, Any]:
    context = definition.question_id
    if not isinstance(raw, dict):
        raise JevContractError("MALFORMED_ANSWER", f"{context}: answer is not an object")
    kind = raw.get("kind")
    if kind != definition.primitive.lower():
        raise JevContractError("INVALID_PRIMITIVE", f"{context}: {kind} != {definition.primitive.lower()}")
    if definition.primitive == "NOUL":
        return {"kind": "noul", "probability_yes": _probability(raw.get("probability_yes"), context)}
    if definition.primitive == "CHOICE":
        roster = list((definition.criteria or {}).keys())
        choice = raw.get("choice")
        if choice not in roster:
            raise JevContractError("INVALID_CHOICE", f"{context}: {choice!r} not in roster")
        probabilities = _probability_map(raw.get("probabilities"), roster, f"{context}.probabilities")
        confidence = _probability(raw.get("confidence"), f"{context}.confidence")
        return {"kind": "choice", "choice": choice, "confidence": confidence, "probabilities": probabilities}
    if definition.primitive == "SCORE":
        levels = list(definition.criteria or [])
        if len(levels) < 2:
            raise JevContractError("INVALID_QUESTION", f"{context}: Score requires at least two levels")
        level_keys = [str(index) for index in range(len(levels))]
        score = _finite(raw.get("score"), f"{context}.score")
        if not 0.0 <= score <= len(levels) - 1:
            raise JevContractError("INVALID_SCORE_LEVEL", f"{context}: {score} outside 0..{len(levels) - 1}")
        probabilities = _probability_map(raw.get("probabilities"), level_keys, f"{context}.probabilities")
        legend_raw = raw.get("legend")
        if not isinstance(legend_raw, dict):
            raise JevContractError("INVALID_LEGEND", f"{context}: legend is not a map")
        legend = {str(key): str(value) for key, value in legend_raw.items()}
        if sorted(legend) != sorted(level_keys):
            raise JevContractError("INVALID_LEGEND", f"{context}: legend keys do not match levels")
        confidence = _probability(raw.get("confidence"), f"{context}.confidence")
        return {"kind": "score", "score": score, "confidence": confidence,
                "probabilities": probabilities, "legend": legend}
    raise JevContractError("INVALID_PRIMITIVE", f"{context}: unknown primitive {definition.primitive}")


def validate_answers(definitions: tuple[QuestionDefinition, ...],
                     raw_answers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_answers, dict):
        raise JevContractError("MALFORMED_ANSWER", "answers must be an object")
    expected = {definition.question_id for definition in definitions}
    unknown = sorted(set(raw_answers) - expected)
    if unknown:
        raise JevContractError("UNKNOWN_QUESTION", f"provider returned unknown answers: {unknown}")
    validated: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        if definition.question_id not in raw_answers:
            raise JevContractError("MISSING_ANSWER", f"no answer for {definition.question_id}")
        validated[definition.question_id] = validate_answer(definition, raw_answers[definition.question_id])
    return validated
