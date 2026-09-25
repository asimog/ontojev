"""Independent derivation of the mutation affected-case quantity from raw bytes.

This module intentionally shares no code with ``cancerjev.gdc.parsers``: the
reconciliation expected values must be derived by a second, independent
implementation reading the raw public GDC records, so a shared parser defect
cannot make both sides agree.

Expected-value rule (SCIENTIFIC_RECONCILIATION_FIXTURE contract):

* ``distinct_cases_per_gene`` is derived from unique ``case.case_id`` values of
  ``/ssm_occurrences`` records for the project/gene filter.
* The top-cases-counts response value is extracted independently as the
  project bucket ``doc_count`` for the gene; it is recorded for comparison only
  and is never used to produce an expected value.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _load(body: bytes) -> dict:
    document = json.loads(body.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("response is not a JSON object")
    return document


@dataclass(frozen=True)
class DerivedCounts:
    """Independent expected values for one gene and one capture batch."""

    gene_id: str
    project_id: str
    distinct_cases: int
    total_occurrences: int
    case_ids: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> dict:
        return {
            "gene_id": self.gene_id,
            "project_id": self.project_id,
            "distinct_cases": self.distinct_cases,
            "total_occurrences": self.total_occurrences,
        }


def count_from_top_cases_response(body: bytes, project_id: str, gene_id: str) -> int | None:
    """Read the project/gene bucket count independently from a raw response.

    Returns ``None`` when the project bucket or the gene bucket is absent, which
    is exactly the bucket-absence semantics the production parser reports as
    NOT_OBSERVED. A present bucket always yields an integer (zero included).
    """
    document = _load(body)
    projects = document.get("aggregations") or {}
    projects = projects.get("projects") or {}
    buckets = projects.get("buckets") or []
    for bucket in buckets:
        if not isinstance(bucket, dict) or bucket.get("key") != project_id:
            continue
        genes = ((bucket.get("genes") or {}).get("my_genes") or {}).get("gene_id") or {}
        gene_buckets = genes.get("buckets") or []
        for gene_bucket in gene_buckets:
            if isinstance(gene_bucket, dict) and gene_bucket.get("key") == gene_id:
                return int(gene_bucket["doc_count"])
        return None
    return None


def derive_from_occurrence_pages(body_pages: list[bytes], project_id: str, gene_id: str) -> DerivedCounts:
    """Independent distinct-case derivation from raw /ssm_occurrences pages.

    Reads every record of every page, collects the unique ``case.case_id``
    values, and reports the distinct-case count and the total record count. The
    filter that produced the pages is part of the frozen capture; this module
    never re-issues requests.
    """
    case_ids: set[str] = set()
    total_records = 0
    for body in body_pages:
        document = _load(body)
        hits = ((document.get("data") or {}).get("hits")) or []
        if not isinstance(hits, list):
            raise ValueError("occurrence page has no hits list")
        for hit in hits:
            if not isinstance(hit, dict):
                raise ValueError("occurrence record is not an object")
            case = hit.get("case") or {}
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise ValueError("occurrence record has no case.case_id")
            case_ids.add(case_id)
            total_records += 1
    ordered = tuple(sorted(case_ids))
    return DerivedCounts(
        gene_id=gene_id, project_id=project_id,
        distinct_cases=len(ordered), total_occurrences=total_records, case_ids=ordered,
    )


def project_occurrence_derivation(body_pages: list[bytes]) -> dict[str, DerivedCounts]:
    """Independent distinct-case derivation per gene across project-wide pages.

    Each record contributes its case to every gene annotated on its
    consequences; a gene absent from a complete scan has an observed zero.
    Used by the reconciliation to prove the distinct-case source semantics on
    real records for the panel genes (the production scan uses the same rule).
    """
    cases_per_gene: dict[str, set[str]] = {}
    docs_per_gene: dict[str, int] = {}
    for body in body_pages:
        document = _load(body)
        hits = ((document.get("data") or {}).get("hits")) or []
        for hit in hits:
            case_id = ((hit.get("case") or {}).get("case_id"))
            if not isinstance(case_id, str) or not case_id:
                raise ValueError("occurrence record has no case.case_id")
            doc_genes: set[str] = set()
            for consequence in hit.get("ssm", {}).get("consequence") or []:
                gene = ((consequence.get("transcript") or {}).get("gene") or {})
                gene_id = gene.get("gene_id")
                if isinstance(gene_id, str) and gene_id:
                    doc_genes.add(gene_id)
            for gene_id in doc_genes:
                cases_per_gene.setdefault(gene_id, set()).add(case_id)
                docs_per_gene[gene_id] = docs_per_gene.get(gene_id, 0) + 1
    return {
        gene_id: DerivedCounts(
            gene_id=gene_id, project_id="*",
            distinct_cases=len(case_ids),
            total_occurrences=docs_per_gene.get(gene_id, 0),
            case_ids=tuple(sorted(case_ids)),
        )
        for gene_id, case_ids in cases_per_gene.items()
    }
