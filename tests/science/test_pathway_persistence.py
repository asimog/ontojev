"""Declared-consumer persistence of descriptive pathway evidence onto states (P12b)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cancerjev.domain.codecs import read_state, state_identity, write_state
from cancerjev.domain.measurements import ContractError
from cancerjev.domain.pathway import PATHWAY_MEMBERSHIP_LIMITATIONS
from cancerjev.research.finalize import _limitations
from cancerjev.research.pathways import (
    PATHWAY_EVIDENCE_CONSUMERS,
    attach_pathway_evidence,
    parse_reactome_mapping,
    pathway_evidence,
)
from cancerjev.storage.readers import read_state_record
from tests.helpers import build_canned_demo, copy_canned_demo

FIXTURES = Path(__file__).parent.parent / "contracts" / "fixtures" / "reactome"
TP53 = "ENSG00000141510"


def _membership():
    body = (FIXTURES / "tp53_ensembl2reactome.tsv").read_bytes()
    return parse_reactome_mapping(
        body.decode("utf-8"), source_version="current@2026-09-25",
        snapshot_sha256=hashlib.sha256(body).hexdigest())


@pytest.fixture(scope="module")
def _canned_demo(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pathway-demo")
    build_canned_demo(data_dir)
    return data_dir


@pytest.fixture
def demo(tmp_path, _canned_demo):
    return copy_canned_demo(_canned_demo, tmp_path / "data")


def _states(repository, artifacts, run_id):
    return tuple(read_state_record(repository, artifacts, row["state_id"]).state
                 for row in repository.list_table("statistical_states", run_id))


def test_declared_consumer_attaches_descriptive_membership_and_round_trips(demo):
    _, repository, artifacts = demo
    run_id = repository.list_runs()[0]["run_id"]
    states = _states(repository, artifacts, run_id)
    assert states and all(state.pathway_evidence is None for state in states)

    attached = attach_pathway_evidence(states, _membership(),
                                       consumer_method="DOSSIER_DESCRIPTIVE_MEMBERSHIP_V1")

    for original, state in zip(states, attached, strict=True):
        evidence = state.pathway_evidence
        assert evidence is not None
        assert evidence.gene_id == state.entity.gene_id
        assert evidence.universe_size == len(state.universe.ordered_ids)
        assert evidence.limitations == PATHWAY_MEMBERSHIP_LIMITATIONS
        restored = read_state(write_state(state), expected_hash=state_identity(state))
        assert restored == state
        assert restored.pathway_evidence is not None
        assert original.pathway_evidence is None, "attachment never mutates the original state"

    untouched = read_state(write_state(states[0]), expected_hash=state_identity(states[0]))
    assert untouched == states[0]
    assert untouched.pathway_evidence is None


def test_undeclared_consumer_is_refused_and_states_stay_clean(demo):
    _, repository, artifacts = demo
    run_id = repository.list_runs()[0]["run_id"]
    states = _states(repository, artifacts, run_id)

    with pytest.raises(ContractError) as failure:
        attach_pathway_evidence(states, _membership(), consumer_method="UNDECLARED_CONSUMER",
                                consumers={})

    assert failure.value.code == "PATHWAY_CONSUMER_NOT_DECLARED"
    assert all(state.pathway_evidence is None for state in states)
    assert "DOSSIER_DESCRIPTIVE_MEMBERSHIP_V1" in PATHWAY_EVIDENCE_CONSUMERS


def test_unmapped_gene_is_not_a_negative_and_is_rendered_in_limitations(demo):
    _, repository, artifacts = demo
    run_id = repository.list_runs()[0]["run_id"]
    states = _states(repository, artifacts, run_id)
    attached = attach_pathway_evidence(states, _membership(),
                                       consumer_method="DOSSIER_DESCRIPTIVE_MEMBERSHIP_V1")

    state = attached[0]
    assert state.pathway_evidence is not None
    assert state.pathway_evidence.member_of == ()
    assert state.pathway_evidence.universe_mapped_genes == 0

    limitations = _limitations(state, {}, {})
    assert all(limitation in limitations for limitation in PATHWAY_MEMBERSHIP_LIMITATIONS)
    assert any("universe genes mapped" in limitation for limitation in limitations)
    assert not any("NO_PATHWAY_MEMBERSHIP_OBSERVED" in limitation
                   for limitation in _limitations(states[0], {}, {}))


def test_tp53_fixture_records_its_mapped_membership():
    membership = _membership()
    evidence = pathway_evidence(membership, TP53, universe_ids=(TP53,))

    assert evidence.member_of == membership.pathways_for(TP53)
    assert len(evidence.member_of) > 1
    assert evidence.universe_mapped_genes == 1 and evidence.universe_size == 1
