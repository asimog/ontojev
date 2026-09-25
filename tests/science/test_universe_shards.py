"""Complete-universe enumeration and operational shard-ledger gates."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cancerjev.domain.discovery import (
    COMPLETE_UNIVERSE_METHOD,
    DISCOVERY_UNIVERSE_METHOD,
    DiscoverySpec,
)
from cancerjev.domain.shards import ShardKind, ShardLedger, ShardRecord, ShardStatus
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.discovery import UNIVERSE_PAGE_SIZE, acquire_gene_universe

PAGE = UNIVERSE_PAGE_SIZE


def _gene(index: int) -> dict:
    return {"gene_id": f"ENSG{index:011d}", "symbol": f"G{index}", "biotype": "protein_coding"}


def _page_body(*, total: int, offset: int, count: int, size: int = PAGE) -> bytes:
    hits = [_gene(index) for index in range(offset, offset + count)]
    pages = (total + size - 1) // size if total else 0
    return json.dumps({"data": {"hits": hits, "pagination": {
        "total": total, "count": count, "size": size, "from": offset, "pages": pages}},
    }).encode()


class _Transport:
    """Serves synthetic gene pages through the real response contract."""

    def __init__(self, artifacts, handler) -> None:
        self.artifacts = artifacts
        self.handler = handler
        self.requests = []

    def request(self, request) -> GDCResponse:
        self.requests.append(request)
        params = dict(request.params)
        body = self.handler(int(params["from"]), int(params["size"]))
        artifact = self.artifacts.publish(f"universe-test/{uuid4().hex}.body", body,
                                          "application/json", "gdc-response")
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at="2026-09-26T00:00:00Z", latency_ms=1,
            request_id=f"universe-{len(self.requests)}", attempt_no=1,
        )


def _complete_spec(ceiling: int = 100_000) -> DiscoverySpec:
    return DiscoverySpec(COMPLETE_UNIVERSE_METHOD, "protein_coding", "GENE_ID_ASC", 0, ceiling, 5000)


def _multi_page(total: int):
    def handler(offset: int, size: int) -> bytes:
        count = min(size, max(0, total - offset))
        return _page_body(total=total, offset=offset, count=count, size=size)
    return handler


def test_complete_method_enumerates_multi_page_universe_to_a_stable_total(runtime):
    transport = _Transport(runtime[2], _multi_page(205))

    acquired = acquire_gene_universe(transport, _complete_spec(), "Data Release TEST")

    universe = acquired.universe
    assert universe.complete is True
    assert universe.source == "GDC_GENES_INDEXED_COMPLETE"
    assert universe.reported_total == 205
    assert len(universe.ordered_ids) == 205
    assert list(universe.ordered_ids) == sorted(universe.ordered_ids)
    assert acquired.page_count == 3
    assert acquired.ledger.kind is ShardKind.UNIVERSE_PAGES
    assert acquired.ledger.required == 3
    assert acquired.ledger.terminal is True
    assert [record.item_count for record in acquired.ledger.records] == [100, 100, 5]
    assert all(record.response_hash for record in acquired.ledger.records)

    replay = acquire_gene_universe(_Transport(runtime[2], _multi_page(205)),
                                   _complete_spec(), "Data Release TEST")
    assert replay.universe.membership_hash == universe.membership_hash


def test_duplicate_gene_across_pages_fails_closed(runtime):
    def handler(offset: int, size: int) -> bytes:
        if offset == 0:
            return _page_body(total=205, offset=0, count=100)
        hits = [_gene(index) for index in range(offset - 1, offset - 1 + 100)]
        return json.dumps({"data": {"hits": hits, "pagination": {
            "total": 205, "count": 100, "size": size, "from": offset, "pages": 3}}}).encode()

    with pytest.raises(LiveRunError) as failure:
        acquire_gene_universe(_Transport(runtime[2], handler), _complete_spec(), None)

    assert failure.value.code == "DUPLICATE_UNIVERSE_GENE"


def test_total_change_across_pages_fails_closed(runtime):
    def handler(offset: int, size: int) -> bytes:
        total = 205 if offset == 0 else 204
        count = min(size, max(0, total - offset))
        return _page_body(total=total, offset=offset, count=count, size=size)

    with pytest.raises(LiveRunError) as failure:
        acquire_gene_universe(_Transport(runtime[2], handler), _complete_spec(), None)

    assert failure.value.code == "UNIVERSE_TOTAL_CHANGED"


def test_short_page_before_the_reported_total_fails_closed(runtime):
    def handler(offset: int, size: int) -> bytes:
        count = 50 if offset == 0 else min(size, 205 - offset)
        return _page_body(total=205, offset=offset, count=count, size=size)

    with pytest.raises(LiveRunError) as failure:
        acquire_gene_universe(_Transport(runtime[2], handler), _complete_spec(), None)

    assert failure.value.code == "UNIVERSE_SLICE_INCOMPLETE"


def test_defect_ceiling_exceeded_fails_closed_instead_of_sampling(runtime):
    with pytest.raises(LiveRunError) as failure:
        acquire_gene_universe(_Transport(runtime[2], _multi_page(205)), _complete_spec(200), None)

    assert failure.value.code == "UNIVERSE_DEFECT_CEILING_EXCEEDED"


def test_prefix_method_keeps_its_declared_slice(runtime):
    spec = DiscoverySpec(DISCOVERY_UNIVERSE_METHOD, "protein_coding", "GENE_ID_ASC", 0, 200, 5000)

    acquired = acquire_gene_universe(_Transport(runtime[2], _multi_page(205)), spec, None)

    assert acquired.universe.source == "GDC_GENES_INDEXED_PREFIX"
    assert acquired.universe.complete is True
    assert len(acquired.universe.ordered_ids) == 200
    assert acquired.ledger.terminal is True


def test_ledger_terminal_requires_every_required_shard():
    completed = ShardRecord(index=0, status=ShardStatus.COMPLETED, item_count=100,
                            request_hash="a" * 64, response_hash="b" * 64,
                            artifact_id="artifact-0", detail=None)
    failed = ShardRecord(index=1, status=ShardStatus.FAILED, item_count=None,
                         request_hash="c" * 64, response_hash=None,
                         artifact_id=None, detail="page failed")

    assert ShardLedger(ShardKind.UNIVERSE_PAGES, 1, (completed,)).terminal is True
    assert ShardLedger(ShardKind.UNIVERSE_PAGES, 2, (completed, failed)).terminal is False
    assert ShardLedger(ShardKind.UNIVERSE_PAGES, 2, (completed,)).terminal is False
