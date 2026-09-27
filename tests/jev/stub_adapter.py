"""Deterministic stub adapter for offline Jev tests. No network, no SDK.

The stub answers exactly the questions it is handed: each ``QuestionDefinition``
supplies the primitive and, for Choice, the option roster, while declared
per-question defaults supply the probability or the chosen option. A question id
with no declared default fails closed, so a changed question set can never be
silently answered by a stale projection-version vector.
"""

from __future__ import annotations

from typing import Any

from cancerjev.jev.questions import QuestionDefinition
from cancerjev.jev.typesafe_adapter import ProviderAnswerSet

NOUL_DEFAULTS: dict[str, float] = {
    "evidence_quality_adequate": 0.85,
    "mutation_evidence_coherent": 0.82,
    "expression_evidence_coherent": 0.80,
    "signal_explained_by_coverage": 0.10,
    "unresolved_uncertainty_material": 0.85,
    "warrants_deeper_investigation": 0.90,
    "revision_reliable": 0.90,
    "evidence_sufficient_for_next_step": 0.70,
    "next_step_warranted": 0.20,
    "stopping_more_honest": 0.80,
    "hypothesis_testable": 0.80,
    "hypothesis_exceeds_recorded_evidence": 0.35,
}
CHOICE_DEFAULTS: dict[str, tuple[str, float]] = {
    "dominant_limitation": ("NONE", 0.88),
    "hypothesis_dominant_unsupported_assumption": ("NONE", 0.70),
}
COVERAGE_OPTION = "COVERAGE"


def _coverage_imbalance(state: dict[str, Any]) -> bool:
    cohort = state.get("cohort")
    return bool(isinstance(cohort, dict) and cohort.get("coverage_imbalance"))


class StubAdapter:
    def __init__(self, *, model: str = "jev-1.13.0", resolved_model: str | None = None,
                 fail: bool = False, override: dict[str, dict[str, Any]] | None = None,
                 deep_override: dict[str, dict[str, Any]] | None = None) -> None:
        self.model = model
        self.resolved_model = resolved_model or model
        self.fail = fail
        self.override = override or {}
        self.deep_override = deep_override or {}
        self.calls = 0
        self.last_state: dict[str, Any] | None = None

    def evaluate(self, state: dict[str, Any], definitions: tuple[QuestionDefinition, ...]) -> ProviderAnswerSet:
        from cancerjev.jev.typesafe_adapter import JevProviderError

        self.calls += 1
        self.last_state = state
        if self.fail:
            raise JevProviderError("PROVIDER_ERROR", "stub provider failure")
        answers = {definition.question_id: self._answer(definition, state)
                   for definition in definitions}
        for declared in (self.override, self.deep_override):
            answers.update({key: value for key, value in declared.items() if key in answers})
        return ProviderAnswerSet(
            requested_model=self.model,
            resolved_model=self.resolved_model,
            answers=answers,
            usage={"input_tokens": 1200, "output_tokens": 60},
            latency_ms=250,
            request_id="stub-request-id",
        )

    def _answer(self, definition: QuestionDefinition,
                state: dict[str, Any]) -> dict[str, Any]:
        if definition.primitive == "NOUL":
            probability = NOUL_DEFAULTS.get(definition.question_id)
            if probability is None:
                raise AssertionError(
                    "StubAdapter has no declared Noul default for question "
                    f"{definition.question_id!r}")
            return {"kind": "noul", "probability_yes": probability}
        if definition.primitive == "CHOICE":
            return self._choice_answer(definition, state)
        raise AssertionError(
            f"StubAdapter cannot answer primitive {definition.primitive!r} for question "
            f"{definition.question_id!r}")

    def _choice_answer(self, definition: QuestionDefinition,
                       state: dict[str, Any]) -> dict[str, Any]:
        options = tuple((definition.criteria or {}).keys())
        declared = CHOICE_DEFAULTS.get(definition.question_id)
        if declared is None:
            raise AssertionError(
                "StubAdapter has no declared Choice default for question "
                f"{definition.question_id!r}")
        limitation, confidence = declared
        if COVERAGE_OPTION in options and _coverage_imbalance(state):
            limitation = COVERAGE_OPTION
        if limitation not in options:
            raise AssertionError(
                f"StubAdapter default {limitation!r} is not an option of "
                f"{definition.question_id!r}")
        remainder = (1.0 - confidence) / (len(options) - 1) if len(options) > 1 else 0.0
        probabilities = {
            option: (confidence if option == limitation else remainder) for option in options}
        return {"kind": "choice", "choice": limitation, "confidence": confidence,
                "probabilities": probabilities}
