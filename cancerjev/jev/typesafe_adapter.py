"""The only module that knows the TypeSafe provider contract.

Uses the official ``typesafe-sdk``; provider objects are converted immediately
to plain application data. The API key is read from ``TYPESAFE_API_KEY`` by the
SDK or passed explicitly by the service; it is never logged or persisted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from cancerjev.jev.questions import QuestionDefinition

ADAPTER_VERSION = "typesafe-adapter-v1"


@dataclass(frozen=True)
class ProviderAnswerSet:
    requested_model: str
    resolved_model: str
    answers: dict[str, dict[str, Any]]
    usage: dict[str, int | None]
    latency_ms: int
    request_id: str | None


class JevProviderError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class TypeSafeAdapter:
    def __init__(self, *, model: str, timeout: float = 30.0, api_key: str | None = None) -> None:
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    def evaluate(self, state: dict[str, Any], definitions: tuple[QuestionDefinition, ...]) -> ProviderAnswerSet:
        try:
            from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise JevProviderError("ADAPTER_UNAVAILABLE", "typesafe-sdk is not installed") from exc

        questions: dict[str, Any] = {}
        for definition in definitions:
            criteria = definition.criteria
            if definition.primitive == "NOUL":
                questions[definition.question_id] = Noul(
                    instructions=definition.instructions,
                    criteria=criteria,
                )
            elif definition.primitive == "CHOICE":
                questions[definition.question_id] = Choice(
                    instructions=definition.instructions,
                    criteria=criteria,
                )
            elif definition.primitive == "SCORE":
                questions[definition.question_id] = Score(
                    instructions=definition.instructions,
                    criteria=list(criteria or []),
                )
            else:  # pragma: no cover - definitions are validated at import
                raise JevProviderError("INVALID_QUESTION", f"unknown primitive {definition.primitive}")

        started = time.monotonic()
        try:
            with TypeSafeClient(api_key=self.api_key, timeout=self.timeout, model=self.model) as client:
                response = client.system_one(state=state, questions=questions, model=self.model)
        except Exception as exc:  # noqa: BLE001 - provider failures become typed errors
            raise JevProviderError("PROVIDER_ERROR", f"{type(exc).__name__}: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        answers: dict[str, dict[str, Any]] = {}
        for question_id, answer in response.answers.items():
            kind = getattr(answer, "type", None)
            if kind == "noul":
                answers[question_id] = {"kind": "noul", "probability_yes": answer.noul}
            elif kind == "choice":
                answers[question_id] = {
                    "kind": "choice", "choice": answer.choice, "confidence": answer.confidence,
                    "probabilities": {str(key): value for key, value in dict(answer.probabilities).items()},
                }
            elif kind == "score":
                answers[question_id] = {
                    "kind": "score", "score": answer.score, "confidence": answer.confidence,
                    "probabilities": {str(key): value for key, value in dict(answer.probabilities).items()},
                    "legend": {str(key): value for key, value in dict(answer.legend).items()},
                }
            else:
                raise JevProviderError("UNKNOWN_ANSWER_KIND", f"{question_id}: {kind!r}")
        request_id = None
        raw_response = getattr(response, "raw_http_response", None)
        if raw_response is not None:
            request_id = raw_response.headers.get("x-typesafe-request-id")
        usage = {
            "input_tokens": getattr(response.usage, "input_tokens", None),
            "output_tokens": getattr(response.usage, "output_tokens", None),
        }
        return ProviderAnswerSet(
            requested_model=self.model,
            resolved_model=response.model,
            answers=answers,
            usage=usage,
            latency_ms=latency_ms,
            request_id=request_id,
        )
