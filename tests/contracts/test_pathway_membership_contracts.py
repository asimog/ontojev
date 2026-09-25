"""Real Reactome fixtures: mapping fidelity, no-membership semantics, strict parsing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cancerjev.domain.measurements import ContractError
from cancerjev.research.pathways import parse_reactome_mapping, pathway_evidence

FIXTURES = Path(__file__).parent / "fixtures" / "reactome"
GENE = "ENSG00000141510"
ABSENT = "ENSG00000000009"


def _membership():
    body = (FIXTURES / "tp53_ensembl2reactome.tsv").read_bytes()
    return parse_reactome_mapping(
        body.decode("utf-8"), source_version="current@2026-09-25",
        snapshot_sha256=hashlib.sha256(body).hexdigest())


def test_real_tp53_rows_match_the_live_content_service_mapping():
    membership = _membership()
    api_ids = {entry["stId"] for entry in json.loads(
        (FIXTURES / "tp53_pathways.json").read_text(encoding="utf-8"))}

    assert set(membership.pathways_for(GENE)) == api_ids
    assert membership.pathway_count >= len(api_ids)
    assert membership.membership_hash() == _membership().membership_hash()
    assert membership.source == "Reactome" and membership.license_ref == "CC-BY-4.0"


def test_unmapped_gene_is_not_a_negative_result():
    membership = _membership()
    evidence = pathway_evidence(membership, ABSENT, universe_ids=(GENE, ABSENT))

    assert evidence.member_of == ()
    assert evidence.universe_mapped_genes == 1 and evidence.universe_size == 2
    assert any("never a negative" in limitation for limitation in evidence.limitations)

    with pytest.raises(ContractError):
        pathway_evidence(membership, "ENSG00000000099", universe_ids=(GENE, ABSENT))


def test_snapshot_parsing_is_strict_and_deterministic():
    row = "ENSG00000141510\tR-HSA-1\thttps://reactome.org/x\tName\tIEA\tHomo sapiens\n"
    membership = parse_reactome_mapping(row, source_version="test@v1",
                                        snapshot_sha256="a" * 64)
    assert membership.gene_count == 1
    assert membership.pathways_for(GENE) == ("R-HSA-1",)

    with pytest.raises(ContractError):
        parse_reactome_mapping(row + row.replace("\tName\t", "\tOther Name\t"),
                               source_version="test@v1", snapshot_sha256="a" * 64)
    with pytest.raises(ContractError):
        parse_reactome_mapping(row.replace("Homo sapiens", "Mus musculus"),
                               source_version="test@v1", snapshot_sha256="a" * 64)
    with pytest.raises(ContractError):
        parse_reactome_mapping("ENSG00000141510\tR-HSA-1\turl\tname\tIEA\n",
                               source_version="test@v1", snapshot_sha256="a" * 64)
