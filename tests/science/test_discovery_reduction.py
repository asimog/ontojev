"""Stage 4 deterministic reduction and universe-loop contracts.

Realistic failure modes protected: a tie that resolves nondeterministically, a
survivor cap that leaks, a complete-scan zero treated as unavailable, partial
project coverage promoting a survivor, and a truncated universe accepted as
complete. The mutation quantity source is the complete occurrence scan; an
absent gene in a complete scan is an observed zero by construction, so the
legacy NOT_OBSERVED bucket semantics cannot reappear.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cancerjev.domain.measurements import (
    Acquisition,
    ObservedCount,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    ScientificSource,
    UnavailableMeasurement,
)
from cancerjev.gdc.endpoints import genes_universe_request
from cancerjev.gdc.parsers import GeneRecord, ProjectCoverage
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import MutationOccurrenceScan
from cancerjev.research.discovery import (
    UNIVERSE_PAGE_SIZE,
    acquire_gene_universe,
    build_discovery_entries,
)
from cancerjev.research.specs import DiscoverySpec
from cancerjev.storage.artifacts import ArtifactStore

RELEASE = "Data Release 46.0 - August 10, 2026"
PROJECT = "TCGA-LUAD"


def _gene_id(index: int) -> str:
    return f"ENSG{index:011d}"


def _genes(ids: list[str]) -> dict[str, GeneRecord]:
    return {gene_id: GeneRecord(gene_id, f"S{gene_id[-1]}", None, "protein_coding", None)
            for gene_id in ids}


def _frame() -> PopulationFrame:
    return PopulationFrame(PROJECT, PROJECT, PopulationUnit.CASE,
                           tuple(f"CASE-{index:03d}" for index in range(600)), None,
                           "ALL_CASES_PAGINATED")


def _source(endpoint: str) -> OperationalSource:
    return OperationalSource(
        ScientificSource(endpoint, "0" * 64, "1" * 64, "gdc-parser-v1", RELEASE, Acquisition.COMPLETE),
        "attempt:1", "artifact:1", "now", 128, 1, 200, False)


def _scan(distinct: dict[str, int], docs: dict[str, int] | None = None) -> MutationOccurrenceScan:
    docs_map = dict(docs) if docs is not None else dict(distinct)
    return MutationOccurrenceScan(
        project_id=PROJECT, page_size=40, page_count=1, total_occurrences=sum(docs_map.values()),
        bytes_read=0, distinct_cases_per_gene=dict(distinct), occurrence_docs_per_gene=docs_map,
        sources=(_source("/ssm_occurrences"),), warnings=())


def _coverage(value: int = 580, *, complete: bool = True) -> ProjectCoverage:
    return ProjectCoverage(case_with_ssm={PROJECT: value}, complete=complete,
                           partial_reasons=[] if complete else ["failed_shards=1"], warnings=[])


def _ids(*indexes: int) -> tuple[str, ...]:
    return tuple(_gene_id(index) for index in indexes)


def _entries_for(ids: tuple[str, ...], scan: MutationOccurrenceScan, *,
                 coverage: ProjectCoverage | None = None, coverage_complete: bool = True,
                 max_survivors: int = 10):
    coverage_value = coverage if coverage is not None else _coverage()
    return build_discovery_entries(
        PROJECT, _genes(list(ids)), ids, scan, RELEASE, _frame(), coverage_value,
        _source("/analysis/mutated_cases_count_by_project"), coverage_complete,
        _source("/ssm_occurrences/scan"), max_survivors)


def test_counts_descending_with_gene_id_tie_break_and_cap():
    ids = _ids(1, 2, 3, 4)
    scan = _scan({_gene_id(1): 40, _gene_id(2): 50, _gene_id(3): 50, _gene_id(4): 20},
                 {_gene_id(1): 55, _gene_id(2): 50, _gene_id(3): 62, _gene_id(4): 21})
    entries, survivors = _entries_for(ids, scan, max_survivors=2)
    by_id = {entry.entity.gene_id: entry for entry in entries}
    assert survivors == (_gene_id(2), _gene_id(3))
    assert by_id[_gene_id(2)].disposition.value == "RETAINED"
    assert by_id[_gene_id(2)].rank == 1
    assert by_id[_gene_id(3)].disposition.value == "RETAINED"
    assert by_id[_gene_id(3)].rank == 2
    assert by_id[_gene_id(1)].disposition.value == "BELOW_SURVIVOR_CUTOFF"
    assert by_id[_gene_id(1)].rank == 3
    assert by_id[_gene_id(4)].disposition.value == "BELOW_SURVIVOR_CUTOFF"
    assert by_id[_gene_id(4)].rank == 4
    assert [entry.entity.gene_id for entry in entries] == list(ids)
    assert by_id[_gene_id(1)].outcome.affected_cases.value == 40


def test_counts_for_returns_distinct_and_doc_counts():
    scan = _scan({_gene_id(1): 50, _gene_id(2): 7}, {_gene_id(1): 51, _gene_id(2): 7})
    assert scan.counts_for(_gene_id(1)) == (50, 51)
    assert scan.counts_for(_gene_id(2)) == (7, 7)
    assert scan.counts_for(_gene_id(99)) == (0, 0)


def test_complete_scan_zero_and_absent_gene_are_observed_zeroes():
    ids = _ids(4, 5)
    scan = _scan({_gene_id(4): 0})
    entries, survivors = _entries_for(ids, scan)
    by_id = {entry.entity.gene_id: entry for entry in entries}
    zero = by_id[_gene_id(4)]
    assert isinstance(zero.outcome.affected_cases, ObservedCount)
    assert zero.outcome.affected_cases.value == 0
    assert zero.disposition.value == "RETAINED" and zero.rank == 1
    absent = by_id[_gene_id(5)]
    assert isinstance(absent.outcome.affected_cases, ObservedCount)
    assert absent.outcome.affected_cases.value == 0
    assert absent.disposition.value == "RETAINED" and absent.rank == 2
    assert survivors == (_gene_id(4), _gene_id(5))


def test_partial_coverage_blocks_eligibility_for_complete_scan():
    ids = _ids(8)
    scan = _scan({_gene_id(8): 12})
    entries, survivors = _entries_for(ids, scan, coverage=_coverage(complete=False),
                                      coverage_complete=False)
    assert survivors == ()
    assert entries[0].disposition.value == "MUTATION_AGGREGATION_PARTIAL"
    assert entries[0].reason == "MUTATION_COVERAGE_PARTIAL"


def test_project_absent_from_coverage_keeps_complete_scan_eligible():
    """A missing coverage bucket is context, not the measurement.

    The affected-case quantity derives from the complete occurrence scan; the
    project SSM coverage aggregation is availability context only, so its
    absence cannot demote an observed distinct-case count.
    """
    ids = _ids(9)
    scan = _scan({_gene_id(9): 5})
    empty_coverage = ProjectCoverage(case_with_ssm={}, complete=True, partial_reasons=[], warnings=[])
    entries, survivors = _entries_for(ids, scan, coverage=empty_coverage)
    assert survivors == (_gene_id(9),)
    assert entries[0].disposition.value == "RETAINED"
    assert isinstance(entries[0].outcome.ssm_coverage_cases, UnavailableMeasurement)


def test_every_requested_gene_receives_exactly_one_disposition():
    ids = _ids(1, 2, 3, 4, 5, 6)
    scan = _scan({_gene_id(1): 50, _gene_id(2): 50, _gene_id(3): 30, _gene_id(4): 0})
    entries, survivors = _entries_for(ids, scan)
    assert len(entries) == len(ids)
    assert {entry.entity.gene_id for entry in entries} == set(ids)
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.disposition.value] = totals.get(entry.disposition.value, 0) + 1
    assert sum(totals.values()) == len(ids)
    assert totals == {"RETAINED": 6}


class _UniverseTransport:
    """Provider-shaped /genes pages over real artifacts; no sockets."""

    def __init__(self, artifacts: ArtifactStore, pages: list[list[tuple[str, str]]],
                 totals: list[int]) -> None:
        self.artifacts = artifacts
        self.pages = pages
        self.totals = totals
        self.calls = 0

    def request(self, request):
        assert request.endpoint.name == "genes"
        params = dict(request.params)
        assert params["sort"] == "gene_id:asc"
        offset = int(params["from"])
        size = int(params["size"])
        index = offset // size
        assert index < len(self.pages), "unexpected extra universe page"
        page_ids = self.pages[index]
        total = self.totals[index]
        hits = [{"gene_id": gene_id, "symbol": symbol, "biotype": "protein_coding"}
                for gene_id, symbol in page_ids]
        payload = {"data": {"hits": hits, "pagination": {
            "count": len(hits), "total": total, "size": size, "from": offset,
            "pages": (total + size - 1) // size}}}
        body = json.dumps(payload).encode()
        self.calls += 1
        artifact = self.artifacts.publish(
            f"fixture-universe/{uuid4()}.body", body, "application/json", "gdc-response")
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at="now", latency_ms=1, request_id=str(uuid4()),
            attempt_no=1)


def _discovery(limit: int, page_size: int) -> DiscoverySpec:
    return DiscoverySpec("GENE_ID_ASC_INDEXED_PREFIX_V1", "protein_coding", "GENE_ID_ASC", 0,
                         limit, page_size)


def _pages(*page_specs: tuple[list[tuple[str, str]], int]) -> tuple[list[list[tuple[str, str]]], list[int]]:
    pages = [spec[0] for spec in page_specs]
    totals = [spec[1] for spec in page_specs]
    return pages, totals


def test_universe_loop_builds_complete_multi_page_universe(runtime, monkeypatch):
    from cancerjev.research import discovery as discovery_module

    monkeypatch.setattr(discovery_module, "UNIVERSE_PAGE_SIZE", 2)
    _, _, artifacts = runtime
    ids = [_gene_id(index) for index in (1, 2, 3, 4)]
    pages, totals = _pages(
        ([(ids[0], "S1"), (ids[1], "S2")], 4), ([(ids[2], "S3"), (ids[3], "S4")], 4))
    transport = _UniverseTransport(artifacts, pages, totals)
    acquired = acquire_gene_universe(transport, _discovery(4, 2), RELEASE)
    assert acquired.universe.ordered_ids == tuple(ids)
    assert acquired.universe.complete is True
    assert acquired.universe.reported_total == 4
    assert acquired.page_count == 2
    assert transport.calls == 2


def test_universe_loop_fails_closed_on_changed_total(runtime, monkeypatch):
    from cancerjev.research import discovery as discovery_module

    monkeypatch.setattr(discovery_module, "UNIVERSE_PAGE_SIZE", 2)
    _, _, artifacts = runtime
    pages, totals = _pages(
        ([(_gene_id(1), "S1"), (_gene_id(2), "S2")], 4),
        ([(_gene_id(3), "S3"), (_gene_id(4), "S4")], 5))
    transport = _UniverseTransport(artifacts, pages, totals)
    with pytest.raises(Exception, match="UNIVERSE_TOTAL_CHANGED"):
        acquire_gene_universe(transport, _discovery(4, 2), RELEASE)


def test_universe_loop_fails_closed_on_duplicate_across_pages(runtime, monkeypatch):
    from cancerjev.research import discovery as discovery_module

    monkeypatch.setattr(discovery_module, "UNIVERSE_PAGE_SIZE", 2)
    _, _, artifacts = runtime
    pages, totals = _pages(
        ([(_gene_id(1), "S1"), (_gene_id(2), "S2")], 4),
        ([(_gene_id(2), "S2"), (_gene_id(3), "S3")], 4))
    transport = _UniverseTransport(artifacts, pages, totals)
    with pytest.raises(Exception, match="DUPLICATE_UNIVERSE_GENE"):
        acquire_gene_universe(transport, _discovery(4, 2), RELEASE)


def test_universe_loop_fails_closed_on_short_page_before_declared_limit(runtime, monkeypatch):
    from cancerjev.research import discovery as discovery_module

    monkeypatch.setattr(discovery_module, "UNIVERSE_PAGE_SIZE", 2)
    _, _, artifacts = runtime
    pages, totals = _pages(([_gene_pair(1), _gene_pair(2)], 5), ([_gene_pair(3)], 5))
    transport = _UniverseTransport(artifacts, pages, totals)
    with pytest.raises(Exception, match="UNIVERSE_SLICE_INCOMPLETE"):
        acquire_gene_universe(transport, _discovery(4, 2), RELEASE)


def test_universe_shorter_than_limit_is_a_complete_smaller_prefix(runtime, monkeypatch):
    from cancerjev.research import discovery as discovery_module

    monkeypatch.setattr(discovery_module, "UNIVERSE_PAGE_SIZE", 2)
    _, _, artifacts = runtime
    pages, totals = _pages(([_gene_pair(1), _gene_pair(2)], 3), ([_gene_pair(3)], 3))
    transport = _UniverseTransport(artifacts, pages, totals)
    acquired = acquire_gene_universe(transport, _discovery(4, 2), RELEASE)
    assert len(acquired.universe.ordered_ids) == 3
    assert acquired.universe.complete is True
    assert acquired.universe.reported_total == 3


def _gene_pair(index: int) -> tuple[str, str]:
    return _gene_id(index), f"S{index}"


def test_full_page_size_default_is_the_endpoint_max():
    assert UNIVERSE_PAGE_SIZE == 100


def test_universe_request_builder_is_fixed():
    request = genes_universe_request(100, 100)
    params = dict(request.params)
    assert params["from"] == "100"
    assert params["size"] == "100"
    assert params["sort"] == "gene_id:asc"
    assert json.loads(params["filters"]) == {
        "op": "in", "content": {"field": "biotype", "value": ["protein_coding"]}}
    assert request.logical_query_id == "genes:universe"
    with pytest.raises(Exception, match="genes universe offset"):
        genes_universe_request(-1, 100)
    with pytest.raises(Exception, match="genes universe page size"):
        genes_universe_request(0, 101)
