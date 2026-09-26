"""Conservative request-size guard; independent of costs and run length.

Jev 1.13: 64k tokens for state + all questions; 32k for state + longest
question (https://docs.typesafe.ai/models, inspected 2026-09-26).
No official tokenizer is available here. Count serialized UTF-8 bytes as a
conservative proxy, leaving 2,000 units for provider formatting. This is a
local byte guard, NOT an exact tokenizer or a promise of provider acceptance.
Never truncate scientific input to fit.
"""
from typing import Any

from cancerjev.domain.events import canonical_json
from cancerjev.jev.questions import QuestionDefinition, instruction_text

CONTEXT_GUARD_VERSION = "jev-context-bytes-v1"
STATE_AND_LONGEST_QUESTION_BYTES = 30_000
TOTAL_REQUEST_CONTEXT_BYTES = 62_000


def validate_context(state: dict[str, Any], definitions: tuple[QuestionDefinition, ...]) -> None:
    from cancerjev.jev.typesafe_adapter import JevProviderError

    state_bytes = len(canonical_json(state))
    questions = [len(canonical_json({**definition.provider_spec(),
                                    "instructions": instruction_text(definition, state)}))
                 for definition in definitions]
    if (state_bytes + max(questions, default=0) > STATE_AND_LONGEST_QUESTION_BYTES
            or state_bytes + sum(questions) > TOTAL_REQUEST_CONTEXT_BYTES):
        raise JevProviderError(
            "JEV_CONTEXT_LIMIT_EXCEEDED",
            "state and questions exceed the conservative per-request context guard; no input was truncated",
        )
