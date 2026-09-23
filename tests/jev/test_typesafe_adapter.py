"""Provider-response conversion tests. Offline: a fake SDK module is injected."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from cancerjev.jev.questions import WIDE_QUESTIONS
from cancerjev.jev.typesafe_adapter import JevProviderError, TypeSafeAdapter


class _Question:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _NullAnswer:
    type = "noul"


class _Client:
    def __init__(self, response: Any, recorder: dict[str, Any]):
        self.response = response
        self.recorder = recorder

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def system_one(self, *, state: Any, questions: Any, model: str) -> Any:
        self.recorder["model"] = model
        return self.response


def _install_sdk(monkeypatch, response: Any, recorder: dict[str, Any]) -> None:
    module = types.ModuleType("typesafe_sdk")
    module.Choice = _Question
    module.Noul = _Question
    module.Score = _Question
    module.TypeSafeClient = lambda **kwargs: _Client(response, recorder)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", module)


class _OkNoul:
    type = "noul"
    noul = 0.8


class _OkResponse:
    model = "jev-1.13.0"
    answers = {"evidence_quality_adequate": _OkNoul()}
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)
    raw_http_response = types.SimpleNamespace(headers={"x-typesafe-request-id": "req-1"})


class _MissingModelResponse:
    answers = {"evidence_quality_adequate": _OkNoul()}
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)


class _NullAnswersResponse:
    model = "jev-1.13.0"
    answers = None
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)


class _MissingAnswerFieldResponse:
    model = "jev-1.13.0"
    answers = {"evidence_quality_adequate": _NullAnswer()}
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)


class _UnknownKindResponse:
    model = "jev-1.13.0"
    answers = {"evidence_quality_adequate": types.SimpleNamespace(type="mystery")}
    usage = types.SimpleNamespace(input_tokens=10, output_tokens=2)


def test_well_formed_response_converts_to_owned_answers(monkeypatch):
    recorder: dict[str, Any] = {}
    _install_sdk(monkeypatch, _OkResponse(), recorder)
    answer_set = TypeSafeAdapter(model="jev-1.13.0").evaluate({"state": "x"}, WIDE_QUESTIONS)
    assert answer_set.resolved_model == "jev-1.13.0"
    assert answer_set.answers == {"evidence_quality_adequate": {"kind": "noul", "probability_yes": 0.8}}
    assert answer_set.request_id == "req-1"
    assert answer_set.usage == {"input_tokens": 10, "output_tokens": 2}
    assert recorder["model"] == "jev-1.13.0"


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (_MissingModelResponse(), "PROVIDER_RESPONSE_MALFORMED"),
        (_NullAnswersResponse(), "PROVIDER_RESPONSE_MALFORMED"),
        (_MissingAnswerFieldResponse(), "PROVIDER_RESPONSE_MALFORMED"),
        (_UnknownKindResponse(), "UNKNOWN_ANSWER_KIND"),
    ],
)
def test_malformed_provider_responses_become_typed_provider_errors(monkeypatch, response, expected_code):
    _install_sdk(monkeypatch, response, {})
    with pytest.raises(JevProviderError) as exc:
        TypeSafeAdapter(model="jev-1.13.0").evaluate({"state": "x"}, WIDE_QUESTIONS)
    assert exc.value.code == expected_code
