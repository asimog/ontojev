"""Deterministic stub adapter for offline Jev tests. No network, no SDK."""

from __future__ import annotations

from typing import Any

from cancerjev.jev.questions import LIMITATION_ROSTER, QuestionDefinition
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
        limitation = "COVERAGE" if state["cohort"]["coverage_imbalance"] else "NONE"
        probabilities = {
            option: (0.88 if option == limitation else 0.12 / (len(LIMITATION_ROSTER) - 1))
            for option in LIMITATION_ROSTER
        }
        answers = {
            "evidence_quality_adequate": {"kind": "noul", "probability_yes": 0.85},
            "mutation_evidence_coherent": {"kind": "noul", "probability_yes": 0.82},
            "expression_evidence_coherent": {"kind": "noul", "probability_yes": 0.80},
            "signal_explained_by_coverage": {"kind": "noul", "probability_yes": 0.10},
            "unresolved_uncertainty_material": {"kind": "noul", "probability_yes": 0.85},
            "warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.90},
            "dominant_limitation": {
                "kind": "choice", "choice": limitation, "confidence": 0.88,
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
