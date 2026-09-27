"""Deterministic, permutation-invariant pre-Wide policy over measured evidence."""

from __future__ import annotations

from dataclasses import replace

from cancerjev.domain.envelopes import StateRecord
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
    assert first.reason_code == "CUT_AT_DECLARED_STRATA_POLICY"
    assert first.policy_version == PRE_WIDE_POLICY_VERSION
    assert first.payload()["ordering"] == PRE_WIDE_ORDERING_DESCRIPTION
    assert [entry["state_id"] for entry in first.excluded] == ["state-2", "state-1"]
    for expected_cases, entry in zip((6, 3), first.excluded, strict=True):
        assert entry["stratum"] == "mutation"
        assert entry["reason"] == "BELOW_DECLARED_STRATUM_ALLOCATION"
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
    strata = {entry["stratum"]: entry for entry in selection.strata}
    assert strata["mutation"] == {"stratum": "mutation", "quota": None,
                                  "considered": 4, "selected": 4}
    assert strata["expression"]["considered"] == 0


def test_declared_tie_break_resolves_equal_measured_keys_instead_of_aborting():
    records = [_record(f"state-{index}", 10) for index in range(4)]

    selection = select_pre_wide_states(list(records), ceiling=2)
    shuffled = select_pre_wide_states(list(reversed(records)), ceiling=2)

    assert selection.payload() == shuffled.payload()
    assert selection.reason_code == "CUT_AT_DECLARED_STRATA_POLICY"
    assert [record.state_id for record in selection.states] == ["state-0", "state-1"]
    assert all(entry["stratum"] == "mutation" for entry in selection.excluded)
    assert all(entry["reason"] == "BELOW_DECLARED_STRATUM_ALLOCATION"
               for entry in selection.excluded)


def test_cut_reserves_capacity_for_expression_stratum_states():
    """A cut must not let the mutation stratum consume every Wide slot (P1-03)."""
    mutation_state = _record("state-mutation", 40)
    records = [mutation_state, *(_record(f"state-expression-{index}", None) for index in range(8))]

    selection = select_pre_wide_states(records, ceiling=4)
    shuffled = select_pre_wide_states(list(reversed(records)), ceiling=4)

    assert selection.payload() == shuffled.payload()
    selected_ids = [record.state_id for record in selection.states]
    assert "state-mutation" in selected_ids
    assert sum(1 for state_id in selected_ids if state_id.startswith("state-expression")) == 3
    strata = {entry["stratum"]: entry for entry in selection.strata}
    assert strata["mutation"] == {"stratum": "mutation", "quota": 3,
                                  "considered": 1, "selected": 1}
    assert strata["expression"] == {"stratum": "expression", "quota": 1,
                                    "considered": 8, "selected": 3}
    assert len(selection.excluded) == 5
    assert all(entry["stratum"] == "expression" for entry in selection.excluded)
    assert all(entry["reason"] == "BELOW_DECLARED_STRATUM_ALLOCATION"
               for entry in selection.excluded)


def _nominated_record(state_id: str, affected: int | None, modality: str) -> StateRecord:
    record = _record(state_id, affected)
    return replace(record, state=replace(record.state, nominations=((modality, "RETAIN"),)))


def test_cut_reserves_capacity_for_nominated_expression_states():
    """Canonical expression nominations stratify there even with observed zero counts."""
    records = [
        _nominated_record("state-mutation", 40, "mutation"),
        *(_nominated_record(f"state-expression-{index}", 0, "expression") for index in range(8)),
    ]

    selection = select_pre_wide_states(records, ceiling=4)
    shuffled = select_pre_wide_states(list(reversed(records)), ceiling=4)

    assert selection.payload() == shuffled.payload()
    selected_ids = [record.state_id for record in selection.states]
    assert "state-mutation" in selected_ids
    assert sum(1 for state_id in selected_ids if state_id.startswith("state-expression")) == 3
    strata = {entry["stratum"]: entry for entry in selection.strata}
    assert strata["mutation"] == {"stratum": "mutation", "quota": 3,
                                  "considered": 1, "selected": 1}
    assert strata["expression"] == {"stratum": "expression", "quota": 1,
                                    "considered": 8, "selected": 3}


def test_spill_honors_reservations_before_early_leftovers():
    """Unused later-stratum reservations spill forward before early leftovers fill (P1-03)."""
    records = [
        *(_nominated_record(f"state-mutation-{index}", 60 - index, "mutation")
          for index in range(10)),
        *(_nominated_record(f"state-expression-{index}", 0, "expression") for index in range(2)),
        *(_nominated_record(f"state-cnv-{index}", 0, "cnv") for index in range(20)),
    ]

    selection = select_pre_wide_states(records, ceiling=10)

    strata = {entry["stratum"]: entry for entry in selection.strata}
    assert strata["mutation"]["selected"] == 6
    assert strata["expression"]["selected"] == 2
    assert strata["cnv"]["selected"] == 2, \
        "expression's unused reservation must flow to cnv, not back to mutation leftovers"


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
