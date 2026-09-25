"""Deterministic case-disjoint replication partitions.

A scientific holdout is predeclared, case-disjoint and versioned; it is not an
operational shard and not a reviewer-label split. There is no universal ratio:
each method declares its discovery share and power rationale, and insufficient
cases report replication unavailable with a reason rather than a silent split.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cancerjev.domain.measurements import digest, require, strings, text

REPLICATION_PARTITION_VERSION = "hash-sorted-case-partition-v1"
REPLICATION_ORDER_SEED = "ontojev-replication-v1"
MINIMUM_DISCOVERY_CASES = 2


@dataclass(frozen=True)
class ReplicationPartition:
    method_id: str
    rule_version: str
    discovery_share_percent: int
    rationale: str
    discovery_case_ids: tuple[str, ...]
    validation_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.method_id, "replication method id")
        require(self.rule_version == REPLICATION_PARTITION_VERSION,
                "unsupported replication rule version")
        require(1 <= self.discovery_share_percent <= 99,
                "discovery share must be a declared 1..99 percentage")
        text(self.rationale, "replication rationale")
        for values, name in ((self.discovery_case_ids, "discovery"),
                             (self.validation_case_ids, "validation")):
            strings(values, f"replication {name} case ids")
            require(bool(values) and values == tuple(sorted(values))
                    and len(set(values)) == len(values),
                    f"replication {name} case ids must be non-empty, sorted and unique")
        require(not set(self.discovery_case_ids) & set(self.validation_case_ids),
                "replication partitions must be case-disjoint")

    @property
    def all_case_ids(self) -> tuple[str, ...]:
        return tuple(sorted((*self.discovery_case_ids, *self.validation_case_ids)))

    def payload(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "rule_version": self.rule_version,
            "discovery_share_percent": self.discovery_share_percent,
            "rationale": self.rationale,
            "discovery_case_ids": list(self.discovery_case_ids),
            "validation_case_ids": list(self.validation_case_ids),
        }

    def partition_hash(self) -> str:
        return digest(self.payload())


@dataclass(frozen=True)
class ReplicationUnavailable:
    reason: str
    minimum_cases: int

    def __post_init__(self) -> None:
        text(self.reason, "replication unavailable reason")
        require(self.minimum_cases >= MINIMUM_DISCOVERY_CASES,
                "declared minimum must require at least two cases")


def build_replication_partition(
    case_ids: tuple[str, ...],
    *,
    method_id: str,
    discovery_share_percent: int,
    minimum_cases: int,
    rationale: str,
) -> ReplicationPartition | ReplicationUnavailable:
    """Deterministic hash-sorted split at the method's declared share.

    Order is a stable digest of seed, method id and case id, so the split never
    depends on input order, filesystem order or reviewer grouping.
    """
    text(method_id, "replication method id")
    text(rationale, "replication rationale")
    require(isinstance(minimum_cases, int) and not isinstance(minimum_cases, bool)
            and minimum_cases >= MINIMUM_DISCOVERY_CASES,
            "declared minimum must be an integer of at least two cases")
    ordered = tuple(sorted(set(case_ids)))
    if len(ordered) != len(case_ids):
        raise ValueError("replication case ids must be unique")
    if len(ordered) < minimum_cases:
        return ReplicationUnavailable("INSUFFICIENT_CASES_FOR_DECLARED_MINIMUM", minimum_cases)
    ranked = sorted(ordered, key=lambda case_id: digest(
        {"seed": REPLICATION_ORDER_SEED, "method_id": method_id, "case_id": case_id}))
    split = max(1, min(len(ranked) - 1, round(len(ranked) * discovery_share_percent / 100)))
    return ReplicationPartition(
        method_id=method_id, rule_version=REPLICATION_PARTITION_VERSION,
        discovery_share_percent=discovery_share_percent, rationale=rationale,
        discovery_case_ids=tuple(sorted(ranked[:split])),
        validation_case_ids=tuple(sorted(ranked[split:])),
    )
