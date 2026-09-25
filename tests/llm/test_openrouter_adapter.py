"""OpenRouter adapter tests: offline, injected transport, typed failures. No network call."""

from __future__ import annotations

import json
import time
from urllib import error as urlerror

import pytest

from cancerjev.llm.openrouter import (
    DEFAULT_MODEL,
    GENERATOR_NAME,
    MAX_OUTPUT_TOKENS,
    MAX_RESPONSE_BYTES,
    LlmProviderError,
    OpenRouterGenerator,
)

REQUEST = {"recorded_facts": {"symbol": "TP53"}, "eligible_registered_actions": ["CHECK_EVIDENCE_FIDELITY_V1"]}


class _Response:
    """A streaming double whose reads advance, like a real HTTP response."""

    def __init__(self, body: bytes, *, delay: float = 0.0) -> None:
        self._body = body
        self._offset = 0
        self._delay = delay

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        if self._delay:
            time.sleep(self._delay)
        if size < 0:
            chunk = self._body[self._offset:]
            self._offset = len(self._body)
            return chunk
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


def _envelope(entries: list[dict], usage: dict | None = None) -> bytes:
    payload = {"choices": [{"message": {"content": json.dumps({"hypotheses": entries})}}]}
    if usage is not None:
        payload["usage"] = usage
    return json.dumps(payload).encode()


def _entry() -> dict:
    return {
        "statement": "S", "proposed_mechanism": "M", "predictions": ["p"], "contradicted_if": ["c"],
        "distinguishing_tests": [], "required_evidence": ["r"], "unsupported_assumptions": ["a"],
    }


def test_generator_identity_is_pinned_and_named():
    generator = OpenRouterGenerator()
    assert generator.model == DEFAULT_MODEL == "deepseek/deepseek-v4.1-flash"
    assert generator.name == GENERATOR_NAME == "openrouter-chat-v1"


def test_generator_repr_does_not_expose_injected_credential():
    assert "test-secret" not in repr(OpenRouterGenerator(api_key="test-secret"))


def test_successful_completion_returns_entries_and_usage(monkeypatch):
    captured: dict = {}

    def opener(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.headers.items()}
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return _Response(_envelope([_entry()], {"prompt_tokens": 321, "completion_tokens": 45}))

    generator = OpenRouterGenerator(api_key="test-key", opener=opener)
    entries, usage = generator(REQUEST)
    assert entries == [_entry()]
    assert usage == {"input_tokens": 321, "output_tokens": 45}
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert captured["body"]["temperature"] == 0
    assert "test-key" not in json.dumps(captured["body"]), "the credential never enters the request body"


def test_missing_credential_is_typed_and_makes_no_request(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    calls = {"count": 0}

    def opener(request, timeout=None):
        calls["count"] += 1
        return _Response(_envelope([_entry()]))

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key=None, opener=opener)(REQUEST)
    assert exc.value.code == "LLM_KEY_MISSING"
    assert calls["count"] == 0, "no request without a credential"


def test_http_error_is_typed_with_the_status_and_never_leaks_the_key(monkeypatch):
    def opener(request, timeout=None):
        raise urlerror.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="secret-key", opener=opener)(REQUEST)
    assert exc.value.code == "LLM_HTTP_401"
    assert "secret-key" not in exc.value.detail


def test_transport_and_malformed_responses_are_typed():
    def timeout_opener(request, timeout=None):
        raise TimeoutError("provider timed out")

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="k", opener=timeout_opener)(REQUEST)
    assert exc.value.code == "LLM_PROVIDER_ERROR"

    def bad_json(request, timeout=None):
        return _Response(b"not json")

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="k", opener=bad_json)(REQUEST)
    assert exc.value.code == "LLM_RESPONSE_MALFORMED"

    def empty(request, timeout=None):
        return _Response(_envelope([]))

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="k", opener=empty)(REQUEST)
    assert exc.value.code == "LLM_RESPONSE_MALFORMED"


def test_oversized_response_is_rejected_without_parsing():
    def huge(request, timeout=None):
        return _Response(b"x" * (MAX_RESPONSE_BYTES + 1))

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="k", opener=huge)(REQUEST)
    assert exc.value.code == "LLM_RESPONSE_TOO_LARGE"


def test_request_bounds_the_completion_and_enforces_a_whole_request_deadline():
    captured: dict = {}

    def opener(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        return _Response(_envelope([_entry()]))

    OpenRouterGenerator(api_key="k", opener=opener)(REQUEST)
    assert captured["body"]["max_tokens"] == MAX_OUTPUT_TOKENS, (
        "a reasoning model needs a bounded completion or it streams indefinitely"
    )

    def slow(request, timeout=None):
        return _Response(_envelope([_entry()]), delay=0.05)

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(api_key="k", timeout=0.01, opener=slow)(REQUEST)
    assert exc.value.code == "LLM_DEADLINE_EXCEEDED"


def test_blank_model_is_rejected_before_any_request():
    def opener(request, timeout=None):
        raise AssertionError("must not be called")

    with pytest.raises(LlmProviderError) as exc:
        OpenRouterGenerator(model="   ", api_key="k", opener=opener)(REQUEST)
    assert exc.value.code == "LLM_MODEL_MISSING"
