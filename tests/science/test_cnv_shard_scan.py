"""Case-sharded CNV occurrence scan: request contract and strict page parsing."""

from __future__ import annotations

import json

import pytest

from cancerjev.gdc.endpoints import (
    MAX_CNV_CASE_SHARD_SIZE,
    MAX_CNV_OCCURRENCES_PAGE,
    EndpointError,
    cnv_occurrence_shard_page_request,
)
from cancerjev.gdc.parsers import ParserError, ResponseMeta, parse_cnv_occurrence_scan_page

CASES = ["case-0001", "case-0002"]
META = ResponseMeta(endpoint="/cnv_occurrences", method="GET", request_hash="0" * 64,
                    response_sha256="0" * 64, artifact_id=None, retrieved_at="fixture",
                    source_release="fixture", completeness="COMPLETE")


def _hit(occurrence_id: str, case_id: str, gene_ids: tuple[str, ...], *,
         category: str = "Loss", caller: str = "ASCAT3") -> dict:
    return {
        "cnv_occurrence_id": occurrence_id,
        "cnv": {"cnv_id": f"cnv-{occurrence_id}", "cnv_change": category,
                "cnv_change_5_category": category,
                "consequence": [{"gene": {"gene_id": gene_id}} for gene_id in gene_ids]},
        "case": {"case_id": case_id, "project": {"project_id": "TCGA-LUAD"},
                 "observation": [{"copy_number": 1.0, "src_file_id": "file-1",
                                  "sample": {"tumor_sample_uuid": "sample-1"},
                                  "variant_calling": {"variant_caller": caller}}]},
    }


def _body(hits: list[dict], *, total: int | None = None, offset: int = 0,
          size: int = 2) -> bytes:
    row_total = total if total is not None else len(hits)
    return json.dumps({"data": {"hits": hits, "pagination": {
        "total": row_total, "count": len(hits), "size": size, "from": offset,
        "pages": (row_total + size - 1) // size if row_total else 0,
    }}}).encode()


def _parse(body: bytes, *, offset: int = 0, size: int = 2):
    return parse_cnv_occurrence_scan_page(
        body, META, expected_project="TCGA-LUAD", expected_cases=set(CASES),
        expected_offset=offset, expected_size=size)


def test_shard_request_is_fixed_and_bounded():
    request = cnv_occurrence_shard_page_request("TCGA-LUAD", CASES, offset=250, size=250)
    params = dict(request.params)
    assert params["sort"] == "cnv_occurrence_id:asc"
    assert params["from"] == "250" and params["size"] == "250"
    assert params["fields"].split(",")[0] == "cnv_occurrence_id"
    filters = json.loads(params["filters"])
    assert filters["op"] == "and"
    assert request.logical_query_id == "cnv-shard-scan:TCGA-LUAD"
    assert request.page == 2

    with pytest.raises(EndpointError):
        cnv_occurrence_shard_page_request(
            "TCGA-LUAD", [f"case-{index:04d}" for index in range(MAX_CNV_CASE_SHARD_SIZE + 1)])
    with pytest.raises(EndpointError):
        cnv_occurrence_shard_page_request("TCGA-LUAD", CASES, size=MAX_CNV_OCCURRENCES_PAGE + 1)


def test_multi_gene_row_becomes_one_record_per_gene():
    page = _parse(_body([_hit("occ-1", "case-0001", ("ENSG00000000001", "ENSG00000000002"))],
                        size=2))

    assert page.count == 1 and page.total == 1
    assert [record.gene_id for record in page.occurrences] == [
        "ENSG00000000001", "ENSG00000000002"]
    assert {record.occurrence_id for record in page.occurrences} == {"occ-1"}
    assert page.occurrences[0].caller == "ASCAT3"


def test_case_outside_the_declared_shard_is_rejected():
    with pytest.raises(ParserError) as failure:
        _parse(_body([_hit("occ-1", "case-9999", ("ENSG00000000001",))]))

    assert failure.value.code == "UNEXPECTED_IDENTIFIER"


def test_row_id_regression_and_duplicate_pairs_are_rejected():
    with pytest.raises(ParserError) as failure:
        _parse(_body([_hit("occ-2", "case-0001", ("ENSG00000000001",)),
                      _hit("occ-1", "case-0002", ("ENSG00000000001",))], size=2))
    assert failure.value.code == "UNEXPECTED_ORDER"

    with pytest.raises(ParserError) as failure:
        _parse(_body([_hit("occ-1", "case-0001", ("ENSG00000000001",)),
                      _hit("occ-1", "case-0001", ("ENSG00000000001",))], size=2))
    assert failure.value.code == "DUPLICATE_ID"


def test_gene_less_row_and_short_page_fail_closed():
    with pytest.raises(ParserError) as failure:
        _parse(_body([_hit("occ-1", "case-0001", ())], size=2))
    assert failure.value.code == "MALFORMED_JSON"

    with pytest.raises(ParserError) as failure:
        _parse(_body([_hit("occ-1", "case-0001", ("ENSG00000000001",))], total=10, size=2))
    assert failure.value.code == "INVALID_PAGINATION"
