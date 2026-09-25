from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cancerjev.domain.states import STAGES

DATA_LIMIT = 65_536
EVENT_LIMIT = 96 * 1024
SUPPORTED_SCHEMA_VERSION = 1

# Registered vocabulary: every type any orchestrator or storage path may commit.
# An unknown type is a compatibility error.
REGISTERED_EVENT_TYPES = frozenset({
    "RUN_CREATED", "RUN_STARTED", "RUN_COMPLETED", "RUN_FAILED", "RUN_STOPPED",
    "STAGE_STARTED", "STAGE_COMPLETED",
    "INVENTORY_STARTED", "INVENTORY_COMPLETED",
    "PROJECT_SCOPE_SELECTED",
    "GDC_REQUEST_STARTED", "GDC_REQUEST_COMPLETED", "GDC_REQUEST_FAILED",
    "GDC_CACHE_HIT", "GDC_RESPONSE_LIMIT_EXCEEDED",
    "GDC_REQUEST_BUDGET_EXHAUSTED", "GDC_RUN_BYTE_BUDGET_EXHAUSTED",
    "DISCOVERY_STARTED", "DISCOVERY_UNIVERSE_ACQUIRED", "DISCOVERY_OCCURRENCE_SCAN_ACQUIRED",
    "DISCOVERY_COMPLETED",
    "EXPRESSION_DISCOVERY_STARTED", "EXPRESSION_UNIVERSE_ACQUIRED", "EXPRESSION_RUN_PLANNED",
    "EXPRESSION_SHARDS_COMPLETED",
    "EXPRESSION_DISCOVERY_COMPLETED",
    "CNV_DISCOVERY_STARTED", "CNV_DISCOVERY_COMPLETED",
    "CNV_SHARD_SCAN_COMPLETED", "CNV_PROJECT_SCAN_COMPLETED",
    "WIDE_SCAN_STARTED", "WIDE_SCAN_COMPLETED",
    "STATISTICAL_STATE_CREATED", "WIDE_STATE_DEFERRED", "PREFILTER_REJECTED",
    "JEV_PROJECTION_CREATED",
    "JEV_WIDE_STARTED", "JEV_WIDE_COMPLETED", "JEV_WIDE_STATE_EVALUATED",
    "JEV_WIDE_STATE_CAP_ENFORCED",
    "JEV_EVALUATION_FAILED", "WIDE_RANKING_COMPLETED",
    "CANDIDATE_PROMOTED", "CANDIDATE_DEFERRED",
    "EVIDENCE_STATE_CREATED", "EVIDENCE_BUILD_COMPLETED", "JEV_DEEP_STARTED", "JEV_DEEP_COMPLETED",
    "JEV_DEEP_EVIDENCE_JUDGED", "NEXT_MOVE_SELECTED", "NEXT_MOVE_DISPATCHED",
    "HYPOTHESES_GENERATED", "HYPOTHESIS_EVALUATED",
    "FOLLOWUP_STARTED", "FOLLOWUP_COMPLETED", "DOSSIER_CREATED", "DOSSIER_UNAVAILABLE",
    "FINAL_CANDIDATE_RESULT_RECORDED", "CANDIDATE_COMPLETED", "CANDIDATE_NOT_COMPLETED",
    "ELIGIBLE_ACTIONS_COMPUTED", "FOLLOWUP_ABSTAINED", "FOLLOWUP_SKIPPED", "FOLLOWUP_FAILED",
    "DEEP_SELECTION_UNAVAILABLE",
})


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = SUPPORTED_SCHEMA_VERSION
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

    @field_validator("schema_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"unsupported RunEvent schema_version {value}")
        return value

    @field_validator("type")
    @classmethod
    def registered_type(cls, value: str) -> str:
        if value not in REGISTERED_EVENT_TYPES:
            raise ValueError(f"unknown RunEvent type {value}")
        return value

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

