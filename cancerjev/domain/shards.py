"""Operational shard ledger: required/acquisition status, never scientific state.

Shards are operational partitions of one declared population (gene pages, scan
pages, gene batches). They cannot change the population, the ranking or the
testing family, and a reduction may finalize only when every required shard is
COMPLETED. The ledger is persisted as an immutable artifact and is deliberately
excluded from every scientific identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cancerjev.domain.measurements import count, digest, require, sha256, text


class ShardKind(StrEnum):
    UNIVERSE_PAGES = "UNIVERSE_PAGES"
    OCCURRENCE_SCAN_PAGES = "OCCURRENCE_SCAN_PAGES"
    EXPRESSION_GENE_BATCHES = "EXPRESSION_GENE_BATCHES"


class ShardStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ShardRecord:
    index: int
    status: ShardStatus
    item_count: int | None
    request_hash: str | None
    response_hash: str | None
    artifact_id: str | None
    detail: str | None

    def __post_init__(self) -> None:
        count(self.index, "shard index")
        require(isinstance(self.status, ShardStatus), "invalid shard status")
        if self.item_count is not None:
            count(self.item_count, "shard item count")
        for value in (self.request_hash, self.response_hash):
            if value is not None:
                sha256(value, "shard hash")
        for value in (self.artifact_id, self.detail):
            if value is not None:
                text(value, "shard text")
        if self.status is ShardStatus.COMPLETED:
            require(self.item_count is not None, "a completed shard records its item count")

    def payload(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "status": self.status.value,
            "item_count": self.item_count,
            "request_hash": self.request_hash,
            "response_hash": self.response_hash,
            "artifact_id": self.artifact_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ShardLedger:
    kind: ShardKind
    required: int
    records: tuple[ShardRecord, ...]

    def __post_init__(self) -> None:
        require(isinstance(self.kind, ShardKind), "invalid shard kind")
        count(self.required, "required shard count")
        require(self.required >= 1, "a ledger needs at least one required shard")
        require(type(self.records) is tuple
                and all(isinstance(record, ShardRecord) for record in self.records),
                "shard records must be an immutable tuple")
        indices = [record.index for record in self.records]
        require(len(indices) == len(set(indices)), "duplicate shard index")
        require(all(0 <= index < self.required for index in indices), "shard index out of range")
        require(indices == sorted(indices), "shard records must be ordered")

    @property
    def completed_count(self) -> int:
        return sum(1 for record in self.records if record.status is ShardStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for record in self.records if record.status is ShardStatus.FAILED)

    @property
    def terminal(self) -> bool:
        """True only when every required shard completed and none failed."""
        return (self.completed_count == self.required and self.failed_count == 0
                and len(self.records) == self.required)

    def payload(self) -> dict[str, Any]:
        return {
            "kind": "SHARD_LEDGER",
            "shard_kind": self.kind.value,
            "required": self.required,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "terminal": self.terminal,
            "records": [record.payload() for record in self.records],
        }

    def ledger_hash(self) -> str:
        return digest(self.payload())
