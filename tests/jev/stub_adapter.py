"""Deterministic stub adapter for offline Jev tests. No network, no SDK."""

from __future__ import annotations

from typing import Any

from cancerjev.jev.questions import PATTERN_ROSTER, QuestionDefinition
from cancerjev.jev.typesafe_adapter import ProviderAnswerSet


class StubAdapter:
    def __init__(self, *, model: str = "jev-1.13.0", resolved_model: str | None = None,
                 fail: bool = False, override: dict[str, dict[str, Any]] | None = None) -> None:
        self.model = model
        self.resolved_model = resolved_model or model
        self.fail = fail
        self.override = override or {}
        self.calls = 0
        self.last_state: dict[str, Any] | None = None

    def evaluate(self, state: dict[str, Any], definitions: tuple[QuestionDefinition, ...]) -> ProviderAnswerSet:
        from cancerjev.jev.typesafe_adapter import JevProviderError

        self.calls += 1
        self.last_state = state
        if self.fail:
            raise JevProviderError("PROVIDER_ERROR", "stub provider failure")
        affected = sum(observation["affected_cases"] or 0 for observation in state["project_observations"])
        projects = len(state["project_observations"])
        warrants = min(0.99, affected / 500.0)
        fragile = state["cross_project"]["top_project_share"]
        fragile = 0.5 if fragile is None else min(0.99, fragile)
        pattern = "WIDESPREAD_RECURRENCE" if projects >= 3 else "INSUFFICIENT_EVIDENCE"
        probabilities = {option: (1.0 - 0.05) if option == pattern else 0.05 / (len(PATTERN_ROSTER) - 1)
                         for option in PATTERN_ROSTER}
        answers = {
            "warrants_deeper_investigation": {"kind": "noul", "probability_yes": warrants},
            "mutation_project_exception": {"kind": "noul", "probability_yes": 0.4},
            "expression_project_exception": {"kind": "noul", "probability_yes": 0.3},
            "coverage_explains_apparent_difference": {
                "kind": "noul",
                "probability_yes": 0.8 if state["cross_project"]["coverage_imbalance"] else 0.1,
            },
            "likely_fragile": {"kind": "noul", "probability_yes": fragile},
            "pattern_type": {
                "kind": "choice", "choice": pattern, "confidence": 0.9,
                "probabilities": probabilities,
            },
        }
        answers.update(self.override)
        return ProviderAnswerSet(
            requested_model=self.model,
            resolved_model=self.resolved_model,
            answers=answers,
            usage={"input_tokens": 1200, "output_tokens": 60},
            latency_ms=250,
            request_id="stub-request-id",
        )
