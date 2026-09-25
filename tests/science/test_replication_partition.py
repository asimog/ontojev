"""Deterministic, method-specific, case-disjoint replication partitions."""

from __future__ import annotations

import pytest

from cancerjev.domain.measurements import ContractError
from cancerjev.research.replication import (
    REPLICATION_PARTITION_VERSION,
    ReplicationPartition,
    ReplicationUnavailable,
    build_replication_partition,
)

CASES = tuple(f"case-{index:03d}" for index in range(10))


def _build(case_ids=CASES, *, percent: int = 60, minimum: int = 8):
    return build_replication_partition(
        tuple(case_ids), method_id="TEST_METHOD_V1", discovery_share_percent=percent,
        minimum_cases=minimum, rationale="declared power rationale for this cohort")


def test_partition_is_deterministic_and_order_independent():
    first = _build()
    shuffled = _build(tuple(reversed(CASES)))

    assert isinstance(first, ReplicationPartition)
    assert isinstance(shuffled, ReplicationPartition)
    assert first == shuffled
    assert first.rule_version == REPLICATION_PARTITION_VERSION
    assert first.partition_hash() == shuffled.partition_hash()
    assert set(first.discovery_case_ids) | set(first.validation_case_ids) == set(CASES)
    assert not set(first.discovery_case_ids) & set(first.validation_case_ids)
    assert len(first.discovery_case_ids) == 6 and len(first.validation_case_ids) == 4
    assert first.rationale.startswith("declared power rationale")


def test_declared_share_is_required_and_keeps_both_partitions_non_empty():
    with pytest.raises(ContractError):
        _build(percent=100)
    with pytest.raises(ContractError):
        _build(percent=0)

    extreme = _build(percent=99)
    assert isinstance(extreme, ReplicationPartition)
    assert len(extreme.validation_case_ids) == 1


def test_insufficient_cases_report_unavailable_with_reason():
    outcome = _build(CASES[:3], minimum=8)

    assert isinstance(outcome, ReplicationUnavailable)
    assert outcome.reason == "INSUFFICIENT_CASES_FOR_DECLARED_MINIMUM"
    assert outcome.minimum_cases == 8


def test_partition_rule_cannot_silently_adopt_a_universal_ratio():
    with pytest.raises(ContractError):
        ReplicationPartition("M", REPLICATION_PARTITION_VERSION, 60, "", ("case-1",),
                             ("case-1",))

    with pytest.raises(ValueError):
        build_replication_partition(("case-1", "case-1", "case-2"), method_id="M",
                                    discovery_share_percent=60, minimum_cases=2,
                                    rationale="r")
