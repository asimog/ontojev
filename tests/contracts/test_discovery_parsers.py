"""Strict universe-enumeration /genes page parsing: malformed provider output fails closed."""

from __future__ import annotations

import json

import pytest

from cancerjev.gdc.parsers import (
    GENES_UNIVERSE_BIOTYPE,
    ResponseMeta,
    parse_genes_page,
)

RELEASE = "Data Release 46.0 - August 10, 2026"


def _meta() -> ResponseMeta:
    return ResponseMeta(endpoint="/genes", method="GET", request_hash="0" * 64,
                        response_sha256="1" * 64, artifact_id=None, retrieved_at="now",
                        source_release=RELEASE, completeness="COMPLETE")


def _gene_id(index: int) -> str:
    return f"ENSG{index:011d}"


def _hit(index: int) -> dict[str, str]:
    return {"gene_id": _gene_id(index), "symbol": f"SYM{index}", "biotype": GENES_UNIVERSE_BIOTYPE}


def _body(hits: list[dict[str, str]], *, total: int = 19_843, count: int | None = None,
          size: int = 100, offset: int = 0, pages: int | None = None) -> bytes:
    pagination: dict[str, int | None] = {"count": len(hits) if count is None else count,
                                         "total": total, "size": size, "from": offset,
                                         "pages": pages}
    return json.dumps({"data": {"hits": hits, "pagination": pagination}}).encode()


def test_valid_page_parses_with_pagination_fields():
    page = parse_genes_page(_body([_hit(3), _hit(5)], total=19_843, size=100, offset=0, pages=9922),
                            _meta(), expected_offset=0, expected_size=100)
    assert [gene.gene_id for gene in page.genes] == [_gene_id(3), _gene_id(5)]
    assert page.total == 19_843
    assert page.count == 2
    assert page.size == 100
    assert page.offset == 0
    assert page.pages == 9922


def test_page_rejects_duplicate_identifier():
    with pytest.raises(Exception, match="DUPLICATE_ID"):
        parse_genes_page(_body([_hit(3), _hit(3)]), _meta(),
                         expected_offset=0, expected_size=100)


def test_page_rejects_ordering_regression():
    with pytest.raises(Exception, match="UNEXPECTED_ORDER"):
        parse_genes_page(_body([_hit(5), _hit(3)]), _meta(),
                         expected_offset=0, expected_size=100)


def test_page_rejects_wrong_biotype():
    hit = {"gene_id": _gene_id(3), "symbol": "SYM3", "biotype": "lncRNA"}
    with pytest.raises(Exception, match="UNEXPECTED_BIOTYPE"):
        parse_genes_page(_body([hit]), _meta(), expected_offset=0, expected_size=100)


def test_page_rejects_non_ensembl_identifier():
    hit = {"gene_id": "GENE3", "symbol": "SYM3", "biotype": GENES_UNIVERSE_BIOTYPE}
    with pytest.raises(Exception, match="INVALID_FIELD"):
        parse_genes_page(_body([hit]), _meta(), expected_offset=0, expected_size=100)


def test_page_rejects_offset_echo_mismatch():
    with pytest.raises(Exception, match="INVALID_PAGINATION"):
        parse_genes_page(_body([_hit(3)], offset=7), _meta(),
                         expected_offset=0, expected_size=100)


def test_page_rejects_missing_total():
    body = json.dumps({"data": {"hits": [_hit(3)],
                                "pagination": {"count": 1, "size": 100, "from": 0}}}).encode()
    with pytest.raises(Exception, match="MISSING_FIELD"):
        parse_genes_page(body, _meta(), expected_offset=0, expected_size=100)


def test_page_rejects_count_record_mismatch():
    with pytest.raises(Exception, match="INVALID_PAGINATION"):
        parse_genes_page(_body([_hit(3)], count=2), _meta(),
                         expected_offset=0, expected_size=100)


def test_page_rejects_nonnegative_violations():
    with pytest.raises(Exception, match="INVALID_PAGINATION"):
        parse_genes_page(_body([_hit(3)], total=-1), _meta(),
                         expected_offset=0, expected_size=100)


def test_page_rejects_incomplete_response():
    meta = _meta()
    object.__setattr__(meta, "completeness", "TRUNCATED")
    with pytest.raises(Exception, match="INCOMPLETE_RESPONSE"):
        parse_genes_page(_body([_hit(3)]), meta, expected_offset=0, expected_size=100)
