"""OpenRouter hypothesis generator: the only place in this repository that authenticates.

The generator is injected into the research layer by the caller; ``research`` never imports
this module, ``Settings`` never holds the credential, and nothing here is persisted. It sends
only the bounded generation request the research layer builds (recorded numbers and eligible
registered action ids), reads its credential from ``OPENROUTER_API_KEY`` at call time, caps the
response body, and raises a typed error for every failure so the caller records a typed
``UNAVAILABLE`` outcome instead of trusting partial text.

The GDC boundary is unchanged: GDC is accessed anonymously and this repository holds no GDC
credential. This adapter is a separate, explicitly configured provider for generated text, which
is never evidence.

A deliberately pinned model identity is used (for example ``deepseek/deepseek-v4.1-flash``) so a
review of generated text can be reused only for the same provider model.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from cancerjev.domain.events import canonical_json

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
GENERATOR_NAME = "openrouter-chat-v1"
MAX_RESPONSE_BYTES = 131_072
# Live observation (2026-09-26): current reasoning models return their reasoning payload in the
# response body, which exceeded the previous 32 KiB cap while the generated content stayed small;
# the cap bounds transport bytes only and the scientific content bound remains MAX_OUTPUT_TOKENS.
# Reasoning models spend output tokens before emitting content, so the request must bound the
# completion itself; without this the model can stream indefinitely and no socket timeout fires.
# Live observation: reasoning used ~1,850-2,000 tokens before ~2,200 characters of content, so the
# bound leaves headroom and an empty-content answer stays a typed failure rather than a retry loop.
MAX_OUTPUT_TOKENS = 6_000
DEFAULT_REASONING_EFFORT = "low"
READ_CHUNK_BYTES = 4_096
CREDENTIAL_ENV = "OPENROUTER_API_KEY"

_SYSTEM_PROMPT = (
    "You produce falsifiable hypothesis text only. Text you produce is never evidence, never a "
    "measurement and never a clinical claim. Answer with JSON only."
)


class LlmProviderError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class OpenRouterGenerator:
    """Injected hypothesis generator backed by one OpenRouter chat completion."""

    model: str = DEFAULT_MODEL
    timeout: float = 30.0
    api_key: str | None = field(default=None, repr=False)
    opener: Callable[..., Any] | None = field(default=None, repr=False)
    name: str = GENERATOR_NAME
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT

    def __call__(self, request: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
        key = self.api_key if self.api_key is not None else os.getenv(CREDENTIAL_ENV)
        if not key:
            raise LlmProviderError("LLM_KEY_MISSING", f"{CREDENTIAL_ENV} is not set")
        if not self.model.strip():
            raise LlmProviderError("LLM_MODEL_MISSING", "no model identity is configured")
        body_payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": canonical_json(request).decode()},
            ],
        }
        if self.reasoning_effort:
            body_payload["reasoning"] = {"effort": self.reasoning_effort}
        body = canonical_json(body_payload)
        http_request = urlrequest.Request(
            OPENROUTER_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        send = self.opener or urlrequest.urlopen
        deadline = time.monotonic() + self.timeout
        try:
            with send(http_request, timeout=self.timeout) as response:
                raw = _read_bounded(response, deadline)
        except LlmProviderError:
            raise
        except urlerror.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(500).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - the status alone is enough to be typed
                detail = ""
            raise LlmProviderError(f"LLM_HTTP_{exc.code}", detail[:300]) from exc
        except Exception as exc:  # noqa: BLE001 - every transport failure is a typed outcome
            raise LlmProviderError("LLM_PROVIDER_ERROR", f"{type(exc).__name__}: {exc}") from exc
        entries, usage = _parse_envelope(raw)
        return entries, usage


def _read_bounded(response: Any, deadline: float) -> bytes:
    """Read at most ``MAX_RESPONSE_BYTES`` while enforcing a whole-request deadline.

    The socket timeout bounds one read; a continuously streaming provider would never hit
    it, so the deadline is checked between chunks and a slow stream becomes a typed failure.
    """
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_RESPONSE_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LlmProviderError("LLM_DEADLINE_EXCEEDED",
                                   "no complete response within the request budget")
        chunk = response.read(min(READ_CHUNK_BYTES, MAX_RESPONSE_BYTES + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    raw = b"".join(chunks)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise LlmProviderError("LLM_RESPONSE_TOO_LARGE", f"{len(raw)} bytes")
    return raw


def _parse_fenced(content: str) -> Any | None:
    """Parse a single markdown-fenced JSON block, or return None.

    Reasoning providers occasionally wrap an object in ```json fences even when JSON was
    requested. Only the fenced block is extracted, it is still parsed as JSON, and every
    draft remains subject to strict validation afterwards.
    """
    stripped = content.strip()
    if not stripped.startswith("```"):
        return None
    body = stripped[3:]
    newline = body.find("\n")
    if newline == -1:
        return None
    body = body[newline + 1:]
    closing = body.rfind("```")
    if closing == -1:
        return None
    try:
        return json.loads(body[:closing].strip())
    except (TypeError, ValueError):
        return None


def _parse_envelope(raw: bytes) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    """Extract hypothesis entries and usage from one chat-completion envelope."""
    try:
        envelope = json.loads(raw.decode("utf-8"))
        choice = envelope["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise LlmProviderError("LLM_RESPONSE_MALFORMED", f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(content, str) or not content.strip():
        reasoning = choice["message"].get("reasoning")
        raise LlmProviderError(
            "LLM_EMPTY_CONTENT",
            f"the provider returned no content (finish_reason={choice.get('finish_reason')!r}, "
            f"reasoning_chars={len(reasoning) if isinstance(reasoning, str) else 0}); "
            "the completion budget was likely consumed by reasoning",
        )
    try:
        payload = json.loads(content)
    except (TypeError, ValueError) as exc:
        payload = _parse_fenced(content)
        if payload is None:
            head = content.strip()[:200].replace("\n", " ")
            raise LlmProviderError(
                "LLM_RESPONSE_MALFORMED",
                f"the content is not JSON and carries no fenced JSON block; head={head!r}",
            ) from exc
    if isinstance(payload, dict):
        entries = payload.get("hypotheses")
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = None
    if not isinstance(entries, list) or not entries:
        raise LlmProviderError("LLM_RESPONSE_MALFORMED", "the response carries no hypotheses list")
    usage: dict[str, int | None] = {"input_tokens": None, "output_tokens": None}
    reported = envelope.get("usage")
    if isinstance(reported, dict):
        # OpenRouter reports prompt_tokens/completion_tokens; accept input/output spellings too.
        usage = {
            "input_tokens": reported.get("prompt_tokens", reported.get("input_tokens")),
            "output_tokens": reported.get("completion_tokens", reported.get("output_tokens")),
        }
    return entries, usage
