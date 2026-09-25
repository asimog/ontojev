"""Real captured extended-fields occurrence page: composition derives from bytes alone.

The body under ``fixtures/gdc/mutation_composition`` was captured anonymously
from the GDC API on 2026-09-26 for TCGA-LUAD (200 records, ascending
occurrence ids, canonical consequence-type fields requested). The provider
exposes transcript ``is_canonical``/``consequence_type``/``transcript_id`` but no
protein-position field, so positions stay unavailable and are never negative.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cancerjev.gdc.parsers import ResponseMeta, parse_ssm_occurrence_page
from cancerjev.science.mutation import mutation_descriptive_evidence

FIXTURES = Path(__file__).parent / "fixtures" / "gdc" / "mutation_composition"
GENE = "ENSG00000168477"
PROJECT = "TCGA-LUAD"


def _load() -> tuple[bytes, ResponseMeta]:
    body = (FIXTURES / "luad_ssm_occurrence_page.body").read_bytes()
    meta = json.loads((FIXTURES / "luad_ssm_occurrence_page.meta.json").read_text("utf-8"))
    assert hashlib.sha256(body).hexdigest() == meta["body_sha256"], "fixture changed"
    return body, ResponseMeta(
        endpoint=meta["endpoint"], method=meta["method"], request_hash="fixture",
        response_sha256=meta["body_sha256"], artifact_id=None, retrieved_at=meta["retrieved_at"],
        source_release="fixture", completeness="COMPLETE",
    )


def _independent_term_counts(body: bytes) -> dict[str, dict[str, int]]:
    """Independent recount: per gene, each occurrence contributes each canonical term once."""
    counts: dict[str, dict[str, int]] = {}
    for hit in json.loads(body)["data"]["hits"]:
        per_gene: dict[str, set[str]] = {}
        for consequence in (hit.get("ssm", {}) or {}).get("consequence", []) or []:
            transcript = consequence.get("transcript") or {}
            gene_id = (transcript.get("gene") or {}).get("gene_id")
            term = transcript.get("consequence_type")
            if transcript.get("is_canonical") is True and gene_id and term:
                per_gene.setdefault(gene_id, set()).add(term)
        for gene_id, terms in per_gene.items():
            for term in terms:
                counts.setdefault(gene_id, {})
                counts[gene_id][term] = counts[gene_id].get(term, 0) + 1
    return counts


def test_real_capture_parses_canonical_rows_without_protein_positions():
    body, meta = _load()
    page = parse_ssm_occurrence_page(body, meta, expected_project=PROJECT, expected_offset=0,
                                     expected_size=200)

    assert len(page.records) == 200
    canonical_rows = [row for record in page.records for row in record.canonical_rows]
    assert canonical_rows
    assert all(row.transcript_id for row in canonical_rows)
    assert all(row.consequence for row in canonical_rows)
    assert all(row.protein_start is None for row in canonical_rows)


def test_composition_matches_an_independent_recount_of_the_pinned_bytes():
    body, _ = _load()
    independent = _independent_term_counts(body)
    expected = tuple(sorted(independent[GENE].items()))

    evidence = mutation_descriptive_evidence(
        distinct_cases=2, occurrence_docs=2,
        consequences=independent[GENE], positions={},
        transcript_counts={"ENST00000000001": 1, "ENST00000000002": 1})

    assert evidence.consequence_composition == expected
    assert dict(expected)["missense_variant"] >= 1
    assert evidence.protein_position_top == ()
    assert evidence.hotspot_descriptor is None
    assert any("protein-position" in limitation for limitation in evidence.limitations)
