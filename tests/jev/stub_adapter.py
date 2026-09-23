"""Deterministic stub adapter for offline Jev tests. No network, no SDK."""

from __future__ import annotations

from typing import Any

from cancerjev.jev.questions import (
    DEEP_LIMITATION_ROSTER,
    HYPOTHESIS_UNSUPPORTED_ROSTER,
    LIMITATION_ROSTER,
    QuestionDefinition,
)
from cancerjev.jev.typesafe_adapter import ProviderAnswerSet

DEEP_ANSWERS = {
    "revision_reliable": {"kind": "noul", "probability_yes": 0.90},
    "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": 0.70},
    "next_step_warranted": {"kind": "noul", "probability_yes": 0.20},
    "stopping_more_honest": {"kind": "noul", "probability_yes": 0.80},
}


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
        if state.get("projection_version") == "jev-evidence-projection-v1":
            answers = self._deep_answers()
            answers.update(self.deep_override)
        elif state.get("projection_version") == "jev-hypothesis-projection-v1":
            answers = self._hypothesis_answers()
        else:
            answers = self._wide_answers(state)
            answers.update(self.override)
        return ProviderAnswerSet(
            requested_model=self.model,
            resolved_model=self.resolved_model,
            answers=answers,
            usage={"input_tokens": 1200, "output_tokens": 60},
            latency_ms=250,
            request_id="stub-request-id",
        )

    def _deep_answers(self) -> dict[str, dict[str, Any]]:
        limitation = "NONE"
        probabilities = {
            option: (0.88 if option == limitation else 0.12 / (len(DEEP_LIMITATION_ROSTER) - 1))
            for option in DEEP_LIMITATION_ROSTER
        }
        return {
            **DEEP_ANSWERS,
            "dominant_limitation": {
                "kind": "choice", "choice": limitation, "confidence": 0.88,
                "probabilities": probabilities,
            },
        }

    def _hypothesis_answers(self) -> dict[str, dict[str, Any]]:
        probabilities = {
            option: (0.70 if option == "NONE" else 0.30 / (len(HYPOTHESIS_UNSUPPORTED_ROSTER) - 1))
            for option in HYPOTHESIS_UNSUPPORTED_ROSTER
        }
        return {
            "hypothesis_testable": {"kind": "noul", "probability_yes": 0.80},
            "hypothesis_exceeds_recorded_evidence": {"kind": "noul", "probability_yes": 0.35},
            "hypothesis_dominant_unsupported_assumption": {
                "kind": "choice", "choice": "NONE", "confidence": 0.70, "probabilities": probabilities,
            },
        }

    def _wide_answers(self, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        limitation = "COVERAGE" if state["cohort"]["coverage_imbalance"] else "NONE"
        probabilities = {
            option: (0.88 if option == limitation else 0.12 / (len(LIMITATION_ROSTER) - 1))
            for option in LIMITATION_ROSTER
        }
        return {
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
