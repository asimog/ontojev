"""Deterministic, permutation-invariant pre-Wide policy over measured evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.ranking import (
    PRE_WIDE_ORDERING_DESCRIPTION,
    PRE_WIDE_POLICY_VERSION,
    measured_ordering_key,
)
from cancerjev.research.wide import select_pre_wide_states
from tests.jev.test_ranking import _record
from tests.jev.test_service import GENE, PROJECT, state_record, statistical_state


def test_permutation_invariance_with_explicit_counts_and_reasons():
    records = [_record(f"state-{index}", index * 3) for index in range(1, 6)]

    first = select_pre_wide_states(list(records), ceiling=3)
    second = select_pre_wide_states(list(reversed(records)), ceiling=3)

    assert first.payload() == second.payload(), "shuffling identical states changes nothing"
    assert [record.state_id for record in first.states] == ["state-5", "state-4", "state-3"]
    assert first.considered == 5
    assert first.ceiling == 3
    assert first.reason_code == "CUT_AT_MEASURED_ORDERING"
    assert first.policy_version == PRE_WIDE_POLICY_VERSION
    assert first.payload()["ordering"] == PRE_WIDE_ORDERING_DESCRIPTION
    assert [entry["state_id"] for entry in first.excluded] == ["state-2", "state-1"]
    for expected_cases, entry in zip((6, 3), first.excluded, strict=True):
        assert entry["reason"] == "BELOW_PRE_WIDE_CUTOFF"
        assert entry["affected_cases"] == expected_cases
        assert entry["mutation_observed"] is True


def test_within_ceiling_keeps_the_complete_population():
    records = [_record(f"state-{index}", index) for index in range(4)]
    selection = select_pre_wide_states(records, ceiling=10)
    assert selection.reason_code == "WITHIN_CEILING"
    assert [record.state_id for record in selection.states] == [
        "state-3", "state-2", "state-1", "state-0"]
    assert selection.excluded == ()
    assert selection.considered == 4


def test_boundary_tie_fails_closed_instead_of_truncating():
    records = [_record(f"state-{index}", 10) for index in range(4)]
    with pytest.raises(LiveRunError) as failure:
        select_pre_wide_states(records, ceiling=2)
    assert failure.value.code == "PRE_WIDE_ORDERING_AMBIGUOUS"


def test_measured_evidence_decides_not_input_order_or_identity():
    low = _record("state-low", 1)
    high = _record("state-high", 40)
    selection = select_pre_wide_states([low, high], ceiling=1)
    assert [record.state_id for record in selection.states] == ["state-high"]

    ordinary_state = statistical_state(counts={PROJECT: {GENE.gene_id: 10}})
    sentinel_entity = replace(ordinary_state.entity, gene_id="ENSG00000141510", symbol="TP53")
    sentinel_state = replace(ordinary_state, entity=sentinel_entity)
    assert measured_ordering_key(state_record("state-a", ordinary_state)) == \
        measured_ordering_key(state_record("state-b", sentinel_state)), \
        "entity identity and validation names never enter the pre-Wide key"
