"""Declared pathway-membership evidence: external, versioned, membership-only.

Membership is deterministic external data (source, version, licence, mapping
method and snapshot hash). No membership is never a negative result, no
enrichment or p/q-value claim is representable here, and no runtime network call
or membership mutation exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cancerjev.domain.measurements import (
    MethodIdentityRef,
    count,
    digest,
    require,
    sha256,
    strings,
    text,
)

REACTOME_MEMBERSHIP_METHOD_ID = "REACTOME_TOP_LEVEL_ENSEMBL_V1"
REACTOME_MEMBERSHIP_VERSION = "1"
PATHWAY_MEMBERSHIP_LIMITATIONS = (
    "Pathway membership is external versioned data (source, version, licence, mapping "
    "method and snapshot hash recorded); it is descriptive membership only.",
    "An unmapped gene is NO_PATHWAY_MEMBERSHIP_OBSERVED, never a negative or absent result, "
    "and no enrichment, p-value or q-value claim is representable.",
)


def pathway_membership_method(snapshot_sha256: str) -> MethodIdentityRef:
    sha256(snapshot_sha256, "pathway snapshot hash")
    return MethodIdentityRef(
        REACTOME_MEMBERSHIP_METHOD_ID, REACTOME_MEMBERSHIP_VERSION,
        digest({"source": "Reactome", "granularity": "top-level", "species": "Homo sapiens",
                "mapping": "Ensembl gene id to Reactome stable id", "snapshot": snapshot_sha256}),
    )


@dataclass(frozen=True)
class PathwayMembership:
    """One versioned pathway-membership table over Ensembl gene ids."""

    source: str
    source_version: str
    license_ref: str
    mapping_method: str
    snapshot_sha256: str
    member_pathways_by_gene: tuple[tuple[str, tuple[str, ...]], ...]
    pathway_names: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        for value in (self.source, self.source_version, self.license_ref, self.mapping_method):
            text(value, "pathway membership identity")
        sha256(self.snapshot_sha256, "pathway snapshot hash")
        require(type(self.member_pathways_by_gene) is tuple, "invalid pathway membership table")
        genes = [gene_id for gene_id, _ in self.member_pathways_by_gene]
        require(genes == sorted(genes) and len(set(genes)) == len(genes),
                "pathway membership genes must be sorted and unique")
        for gene_id, pathways in self.member_pathways_by_gene:
            text(gene_id, "pathway membership gene id")
            strings(pathways, "pathway membership ids")
            require(bool(pathways) and pathways == tuple(sorted(pathways))
                    and len(set(pathways)) == len(pathways),
                    "pathway membership ids must be non-empty, sorted and unique")
        pathway_ids = [pathway_id for pathway_id, _ in self.pathway_names]
        require(pathway_ids == sorted(pathway_ids) and len(set(pathway_ids)) == len(pathway_ids),
                "pathway names must be sorted and unique")

    @property
    def gene_count(self) -> int:
        return len(self.member_pathways_by_gene)

    @property
    def pathway_count(self) -> int:
        return len(self.pathway_names)

    def pathways_for(self, gene_id: str) -> tuple[str, ...]:
        for candidate, pathways in self.member_pathways_by_gene:
            if candidate == gene_id:
                return pathways
        return ()

    def coverage(self, universe_ids: tuple[str, ...]) -> tuple[int, int]:
        """(mapped genes, unmapped genes) over the declared universe; never a negative claim."""
        mapped = sum(1 for gene_id in universe_ids if self.pathways_for(gene_id))
        return mapped, len(universe_ids) - mapped

    def payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_version": self.source_version,
            "license_ref": self.license_ref,
            "mapping_method": self.mapping_method,
            "snapshot_sha256": self.snapshot_sha256,
            "member_pathways_by_gene": [[gene_id, list(pathways)]
                                        for gene_id, pathways in self.member_pathways_by_gene],
            "pathway_names": [[pathway_id, name] for pathway_id, name in self.pathway_names],
        }

    def membership_hash(self) -> str:
        return digest(self.payload())


@dataclass(frozen=True)
class PathwayEvidence:
    """One gene's descriptive pathway membership under the declared method."""

    gene_id: str
    member_of: tuple[str, ...]
    universe_mapped_genes: int
    universe_size: int
    method: MethodIdentityRef
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.gene_id, "pathway evidence gene id")
        strings(self.member_of, "pathway evidence membership")
        require(self.member_of == tuple(sorted(self.member_of))
                and len(set(self.member_of)) == len(self.member_of),
                "pathway evidence membership must be sorted and unique")
        count(self.universe_mapped_genes, "pathway evidence mapped universe size")
        count(self.universe_size, "pathway evidence universe size")
        require(0 <= self.universe_mapped_genes <= self.universe_size,
                "mapped universe size out of range")
        require(self.limitations == PATHWAY_MEMBERSHIP_LIMITATIONS,
                "pathway evidence limitations changed")
