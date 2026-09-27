"""Strict reader and evidence builder for the adopted Reactome membership snapshot.

Declared reader, no production caller: the snapshot is external deterministic data
read from disk, and nothing in the runtime attaches pathway evidence until a named
scientific consumer exists (audit section 34). This module never performs network
access, never mutates membership and never computes enrichment.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cancerjev.domain.measurements import ContractError, require
from cancerjev.domain.pathway import (
    PATHWAY_MEMBERSHIP_LIMITATIONS,
    PathwayEvidence,
    PathwayMembership,
    pathway_membership_method,
)

if TYPE_CHECKING:
    pass

REACTOME_SOURCE = "Reactome"
REACTOME_LICENSE_REF = "CC-BY-4.0"
REACTOME_MAPPING_METHOD = "Ensembl gene id to Reactome stable id (top-level pathways)"

_GENE_ID = re.compile(r"^ENSG\d{11}$")
_PATHWAY_ID = re.compile(r"^R-HSA-\d+$")
_EXPECTED_SPECIES = "Homo sapiens"


def parse_reactome_mapping(text: str, *, source_version: str, snapshot_sha256: str,
                           ) -> PathwayMembership:
    """Strict parse of the filtered `Ensembl2Reactome` table.

    Exactly six tab-separated fields per row; human rows only; duplicate
    (gene, pathway) pairs, malformed identifiers and conflicting pathway names
    are rejected. Identical input always yields an identical membership hash.
    """
    if not isinstance(text, str) or not text:
        raise ContractError("reactome mapping must be non-empty text", "EMPTY_PATHWAY_SNAPSHOT")
    pathways_by_gene: dict[str, set[str]] = {}
    names_by_pathway: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            raise ContractError(f"reactome row must have six fields: {line[:80]}",
                                "MALFORMED_PATHWAY_ROW")
        gene_id, pathway_id, _url, name, evidence_code, species = fields
        if species != _EXPECTED_SPECIES:
            raise ContractError(f"reactome row is not {_EXPECTED_SPECIES}: {line[:80]}",
                                "UNEXPECTED_PATHWAY_SPECIES")
        if not _GENE_ID.match(gene_id):
            raise ContractError(f"reactome gene id is invalid: {gene_id}", "INVALID_GENE_ID")
        if not _PATHWAY_ID.match(pathway_id):
            raise ContractError(f"reactome pathway id is invalid: {pathway_id}",
                                "INVALID_PATHWAY_ID")
        if not name.strip() or not evidence_code.strip():
            raise ContractError("reactome row is missing its name or evidence code",
                                "MALFORMED_PATHWAY_ROW")
        known_name = names_by_pathway.setdefault(pathway_id, name)
        if known_name != name:
            raise ContractError(f"conflicting name for {pathway_id}", "CONFLICTING_PATHWAY_NAME")
        pathways_by_gene.setdefault(gene_id, set()).add(pathway_id)
    if not pathways_by_gene:
        raise ContractError("reactome mapping carries no usable rows", "EMPTY_PATHWAY_SNAPSHOT")
    return PathwayMembership(
        source=REACTOME_SOURCE, source_version=source_version, license_ref=REACTOME_LICENSE_REF,
        mapping_method=REACTOME_MAPPING_METHOD, snapshot_sha256=snapshot_sha256,
        member_pathways_by_gene=tuple(
            (gene_id, tuple(sorted(pathways)))
            for gene_id, pathways in sorted(pathways_by_gene.items())),
        pathway_names=tuple(sorted(names_by_pathway.items())),
    )


def pathway_evidence(membership: PathwayMembership, gene_id: str, *,
                     universe_ids: tuple[str, ...],
                     universe_mapped_genes: int | None = None) -> PathwayEvidence:
    """Descriptive membership for one gene plus universe coverage counts.

    Coverage scanning walks the whole membership table, so callers attaching evidence
    for several states over one universe should compute the mapped count once and pass
    it via ``universe_mapped_genes``.
    """
    if gene_id not in universe_ids:
        raise ContractError(f"{gene_id} is outside the declared universe",
                            "PATHWAY_GENE_OUTSIDE_UNIVERSE")
    if universe_mapped_genes is None:
        mapped, _unmapped = membership.coverage(universe_ids)
    else:
        mapped = universe_mapped_genes
    require(0 <= mapped <= len(universe_ids), "pathway evidence mapped universe size out of range")
    return PathwayEvidence(
        gene_id=gene_id, member_of=membership.pathways_for(gene_id),
        universe_mapped_genes=mapped, universe_size=len(universe_ids),
        method=pathway_membership_method(membership.snapshot_sha256),
        limitations=PATHWAY_MEMBERSHIP_LIMITATIONS,
    )
