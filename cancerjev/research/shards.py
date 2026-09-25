"""Immutable publication of operational shard ledgers; never scientific state."""

from __future__ import annotations

import json
from typing import Any

from cancerjev.domain.shards import ShardLedger
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository


def publish_shard_ledger(artifacts: ArtifactStore, repository: Repository, run_id: str,
                         ledger: ShardLedger, *, relative_path: str) -> Any:
    """Persist one ledger bundle; the artifact carries no scientific identity."""
    document = {**ledger.payload(), "ledger_hash": ledger.ledger_hash()}
    artifact = artifacts.publish(
        relative_path,
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        "application/json", "shard-ledger",
    )
    repository.register_artifact(artifact, run_id)
    return artifact


def ledger_summary(ledger: ShardLedger) -> dict[str, Any]:
    """Operational event payload for one ledger; no measured field is derived here."""
    return {"kind": ledger.kind.value, "required": ledger.required,
            "completed": ledger.completed_count, "failed": ledger.failed_count,
            "terminal": ledger.terminal, "ledger_hash": ledger.ledger_hash()}
