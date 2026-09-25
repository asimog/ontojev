"""Stage 6 fixed request and fail-closed CNV occurrence parser contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cancerjev.gdc.endpoints import EndpointError, cnv_occurrences_request
from cancerjev.gdc.parsers import ParserError, ResponseMeta, parse_cnv_occurrences_page

FIXTURE = Path(__file__).parent / "fixtures" / "gdc" / "cnv_occurrences_tp53.body"
GENE = "ENSG00000141510"
PROJECT = "TCGA-LUAD"
CASES = {"cbfef004-b437-4d51-9d88-a2db50aa6481",
         "205759a6-6391-491b-9857-0080c3a5871e"}


def _meta() -> ResponseMeta:
    return ResponseMeta("/cnv_occurrences", "GET", "request", "response", None, "now",
                        "Data Release 46.0 - August 10, 2026", "COMPLETE")


def _parse(body: bytes):
    return parse_cnv_occurrences_page(
        body, _meta(), expected_project=PROJECT, expected_gene=GENE,
        expected_cases=CASES, expected_offset=0, expected_size=2)


def test_cnv_request_is_fixed_to_one_project_gene_and_bounded_page():
    request = cnv_occurrences_request(PROJECT, GENE, offset=250, size=250)
    params = dict(request.params)
    filters = json.loads(params["filters"])
    assert request.path == "/cnv_occurrences" and request.page == 2
    assert filters["content"][0]["content"]["value"] == [PROJECT]
    assert filters["content"][1]["content"]["value"] == [GENE]
    assert params["sort"] == "cnv_occurrence_id:asc"
    assert "cnv.cnv_change_5_category" in params["fields"]
    with pytest.raises(EndpointError):
        cnv_occurrences_request(PROJECT, GENE, size=251)


def test_cnv_parser_rejects_wrong_case_gene_and_project_membership():
    for path, value in (
        (("case", "case_id"), "outside-case"),
        (("case", "project", "project_id"), "TCGA-LUSC"),
        (("cnv", "consequence", 0, "gene", "gene_id"), "ENSG00000000001"),
    ):
        document = json.loads(FIXTURE.read_bytes())
        node = document["data"]["hits"][0]
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(ParserError, match="UNEXPECTED_IDENTIFIER"):
            _parse(json.dumps(document).encode())


def test_cnv_parser_rejects_duplicates_ambiguous_observations_and_bad_pagination():
    duplicate = json.loads(FIXTURE.read_bytes())
    duplicate["data"]["hits"][1]["cnv_occurrence_id"] = duplicate["data"]["hits"][0][
        "cnv_occurrence_id"]
    with pytest.raises(ParserError, match="DUPLICATE_ID"):
        _parse(json.dumps(duplicate).encode())

    ambiguous = json.loads(FIXTURE.read_bytes())
    ambiguous["data"]["hits"][0]["case"]["observation"].append(
        ambiguous["data"]["hits"][0]["case"]["observation"][0])
    with pytest.raises(ParserError, match="AMBIGUOUS_OBSERVATION"):
        _parse(json.dumps(ambiguous).encode())

    pagination = json.loads(FIXTURE.read_bytes())
    pagination["data"]["pagination"]["total"] = 2
    with pytest.raises(ParserError, match="INVALID_PAGINATION"):
        _parse(json.dumps(pagination).encode())


def test_cnv_parser_rejects_short_nonfinal_page():
    document = json.loads(FIXTURE.read_bytes())
    document["data"]["hits"] = document["data"]["hits"][:1]
    document["data"]["pagination"].update({"count": 1, "total": 3, "pages": 2})
    with pytest.raises(ParserError, match="short page"):
        _parse(json.dumps(document).encode())
