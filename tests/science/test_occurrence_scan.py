"""Complete occurrence-scan acquisition contracts.

Realistic failure modes protected: a page cap violation, a provider total that
changes mid-scan, duplicate occurrence records across pages, non-ascending
ordering across pages, and an empty project. Distinct-case derivation must
count a case once per gene even when one record carries two annotations of the
same gene or two annotations of different genes.
"""

from __future__ import annotations

import json
import math
from uuid import uuid4

import pytest

from cancerjev.gdc.endpoints import SSM_OCCURRENCE_FIELDS, ssm_occurrence_page_request
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import (
    LiveRunError,
    acquire_project_mutation_occurrence_scan,
)
from cancerjev.storage.artifacts import ArtifactStore

RELEASE = "Data Release 46.0 - August 10, 2026"
PROJECT = "TCGA-LUAD"


def _record(occ_id: str, case_id: str, gene_ids: list[str]) -> dict:
    return {
        "ssm_occurrence_id": occ_id,
        "case": {"case_id": case_id, "project": {"project_id": PROJECT}},
        "ssm": {"consequence": [
            {"transcript": {"gene": {"gene_id": gene_id}}} for gene_id in gene_ids
        ]},
    }


def _body(records: list[dict], total: int, size: int, offset: int) -> bytes:
    return json.dumps({"data": {"hits": records, "pagination": {
        "count": len(records), "total": total, "size": size, "from": offset,
        "pages": math.ceil(total / size) if total else 0}}}, separators=(",", ":")).encode()


def _page_transport(artifacts: ArtifactStore, pages: list[bytes]) -> object:
    class _Transport:
        def __init__(self) -> None:
            self.calls = 0

        def request(self, request):
            params = dict(request.params)
            assert request.endpoint.name == "ssm_occurrences"
            offset = int(params["from"])
            size = int(params["size"])
            assert offset == self.calls * size, "unexpected page offset"
            self.calls += 1
            body = pages[self.calls - 1]
            artifact = artifacts.publish(
                f"fixture-scan/{uuid4()}.body", body, "application/json", "gdc-response")
            return GDCResponse(
                request_hash=request.request_hash(), endpoint=request.path, method=request.method,
                http_status=200, headers={"content-type": "application/json"}, body=body,
                body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
                from_cache=False, retrieved_at="now", latency_ms=1, request_id=str(uuid4()),
                attempt_no=1)

    return _Transport()


def _r(occ_id: str, case_id: str, gene_ids: list[str]) -> dict:
    return _record(occ_id, case_id, gene_ids)


def test_scan_derives_distinct_cases_per_gene_with_dedup(runtime):
    _, _, artifacts = runtime
    size = 2
    pages = [
        _body([_r("occ-1", "case-A", ["G1", "G1"]), _r("occ-2", "case-A", ["G1", "G2"])],
              4, size, 0),
        _body([_r("occ-3", "case-B", ["G2"]), _r("occ-4", "case-C", ["G2"])], 4, size, 2),
    ]
    transport = _page_transport(artifacts, pages)
    scan = acquire_project_mutation_occurrence_scan(transport, PROJECT, size, RELEASE)
    assert scan.total_occurrences == 4
    assert scan.page_count == 2
    assert scan.counts_for("G1") == (1, 2)
    assert scan.counts_for("G2") == (3, 3)
    assert scan.counts_for("G9") == (0, 0)
    assert scan.distinct_cases_per_gene == {"G1": 1, "G2": 3}
    assert scan.occurrence_docs_per_gene == {"G1": 2, "G2": 3}


def test_scan_of_an_empty_project_is_complete_with_all_zeroes(runtime):
    _, _, artifacts = runtime
    transport = _page_transport(artifacts, [_body([], 0, 2, 0)])
    scan = acquire_project_mutation_occurrence_scan(transport, PROJECT, 2, RELEASE)
    assert scan.total_occurrences == 0
    assert scan.page_count == 1
    assert scan.distinct_cases_per_gene == {}


def test_scan_fails_closed_on_page_cap_exceeded(runtime, monkeypatch):
    from cancerjev.research import acquisition as acquisition_module

    monkeypatch.setattr(acquisition_module, "OCCURRENCE_SCAN_MAX_PAGES", 2)
    _, _, artifacts = runtime
    size = 1
    pages = [_body([_r(f"occ-{index}", "case-A", ["G1"])], 3, size, index - 1) for index in (1, 2, 3)]
    transport = _page_transport(artifacts, pages)
    with pytest.raises(LiveRunError, match="OCCURRENCE_SCAN_PAGE_CAP_EXCEEDED"):
        acquire_project_mutation_occurrence_scan(transport, PROJECT, size, RELEASE)


def test_scan_fails_closed_on_changed_total(runtime):
    _, _, artifacts = runtime
    size = 1
    pages = [
        _body([_r("occ-1", "case-A", ["G1"])], 3, size, 0),
        _body([_r("occ-2", "case-B", ["G1"])], 4, size, 1),
    ]
    transport = _page_transport(artifacts, pages)
    with pytest.raises(LiveRunError, match="OCCURRENCE_SCAN_TOTAL_CHANGED"):
        acquire_project_mutation_occurrence_scan(transport, PROJECT, size, RELEASE)


def test_scan_fails_closed_on_duplicate_across_pages(runtime):
    _, _, artifacts = runtime
    size = 1
    pages = [
        _body([_r("occ-1", "case-A", ["G1"])], 2, size, 0),
        _body([_r("occ-1", "case-A", ["G1"])], 2, size, 1),
    ]
    transport = _page_transport(artifacts, pages)
    with pytest.raises(LiveRunError, match="DUPLICATE_OCCURRENCE_ACROSS_PAGES"):
        acquire_project_mutation_occurrence_scan(transport, PROJECT, size, RELEASE)


def test_scan_fails_closed_on_order_violation_across_pages(runtime):
    _, _, artifacts = runtime
    size = 1
    pages = [
        _body([_r("occ-2", "case-A", ["G1"])], 2, size, 0),
        _body([_r("occ-1", "case-B", ["G1"])], 2, size, 1),
    ]
    transport = _page_transport(artifacts, pages)
    with pytest.raises(LiveRunError, match="OCCURRENCE_SCAN_ORDER_VIOLATION"):
        acquire_project_mutation_occurrence_scan(transport, PROJECT, size, RELEASE)


def test_scan_request_builder_is_fixed():
    request = ssm_occurrence_page_request(PROJECT, offset=10000, size=5000)
    params = dict(request.params)
    assert params["size"] == "5000"
    assert params["from"] == "10000"
    assert params["sort"] == "ssm_occurrence_id:asc"
    assert json.loads(params["filters"]) == {
        "op": "in", "content": {"field": "case.project.project_id", "value": [PROJECT]}}
    assert params["fields"].split(",") == list(SSM_OCCURRENCE_FIELDS)
    assert request.logical_query_id == f"ssm-occurrence-scan:{PROJECT}"
    assert request.page == 3
    with pytest.raises(Exception, match="SSM occurrence size"):
        ssm_occurrence_page_request(PROJECT, size=10001)
    with pytest.raises(Exception, match="SSM occurrence offset"):
        ssm_occurrence_page_request(PROJECT, offset=-1)
