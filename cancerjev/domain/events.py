from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cancerjev.domain.states import STAGES

DATA_LIMIT = 65_536
EVENT_LIMIT = 96 * 1024


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    event_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    sequence: int = Field(ge=1)
    timestamp: str = Field(default_factory=utc_now)
    stage: str | None = None
    type: str
    level: str = "info"
    message: str = Field(max_length=2048)
    candidate_id: UUID | None = None
    iteration: int | None = Field(default=None, ge=0, le=2)
    data: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=16)
    idempotency_key: str = Field(min_length=1, max_length=255)

    @field_validator("stage")
    @classmethod
    def valid_stage(cls, value: str | None) -> str | None:
        if value is not None and value not in STAGES:
            raise ValueError("unknown stage")
        return value

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        if value not in {"debug", "info", "warning", "error"}:
            raise ValueError("unknown level")
        return value

    @field_validator("data")
    @classmethod
    def data_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(canonical_json(value)) > DATA_LIMIT:
            raise ValueError("event data exceeds 65,536 UTF-8 JSON bytes")
        return value

    def checked_json(self) -> str:
        text = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(text.encode()) > EVENT_LIMIT:
            raise ValueError("whole RunEvent exceeds 96 KiB")
        return text


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

