"""Stage 4 deterministic reduction and universe-loop contracts.

Realistic failure modes protected: a tie that resolves nondeterministically, a
survivor cap that leaks, an absent bucket treated as zero or wildtype, an
incomplete aggregation promoting a survivor, and a truncated universe accepted
as complete.
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
    UnavailableStatus,
)
from cancerjev.gdc.endpoints import genes_universe_request
from cancerjev.gdc.parsers import GeneCaseCounts, GeneRecord, ProjectCoverage
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import (
    BatchedMutationCounts,
    MutationCountBatch,
    TransportError,
    TransportErrorCode,
)
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


def _counts(gene_counts: dict[str, int], *, complete: bool = True) -> GeneCaseCounts:
    return GeneCaseCounts(projects={PROJECT: dict(gene_counts)}, hits_total=sum(gene_counts.values()),
                          complete=complete, partial_reasons=[] if complete else ["timed_out"],
                          warnings=[])


def _coverage(value: int = 580, *, complete: bool = True) -> ProjectCoverage:
    return ProjectCoverage(case_with_ssm={PROJECT: value}, complete=complete,
                           partial_reasons=[] if complete else ["failed_shards=1"], warnings=[])


def _batched(batches: list[tuple[tuple[str, ...], GeneCaseCounts]], coverage: ProjectCoverage,
             *, requested: int | None = None, exhausted: int | None = None) -> BatchedMutationCounts:
    typed = tuple(MutationCountBatch(index, ids, counts, _source("/analysis/top_cases_counts_by_genes"), ())
                  for index, (ids, counts) in enumerate(batches))
    return BatchedMutationCounts(typed, coverage, _source("/analysis/mutated_cases_count_by_project"),
                                 requested if requested is not None else len(batches), exhausted, ())


def _ids(*indexes: int) -> tuple[str, ...]:
    return tuple(_gene_id(index) for index in indexes)


def _entries_for(ids: tuple[str, ...], batched: BatchedMutationCounts, *, max_survivors: int = 10):
    return build_discovery_entries(PROJECT, _genes(list(ids)), ids, batched, _frame(), RELEASE,
                                   max_survivors)


def test_counts_descending_with_gene_id_tie_break_and_cap():
    ids = _ids(1, 2, 3, 4)
    batched = _batched([(ids, _counts({_gene_id(1): 40, _gene_id(2): 50, _gene_id(3): 50,
                                       _gene_id(4): 20}))], _coverage())
    entries, survivors = _entries_for(ids, batched, max_survivors=2)
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


def test_explicit_zero_is_eligible_but_absent_bucket_is_not():
    ids = _ids(4, 5)
    batched = _batched([(ids, _counts({_gene_id(4): 0}))], _coverage())
    entries, survivors = _entries_for(ids, batched)
    by_id = {entry.entity.gene_id: entry for entry in entries}
    zero = by_id[_gene_id(4)]
    assert isinstance(zero.outcome.affected_cases, ObservedCount)
    assert zero.outcome.affected_cases.value == 0
    assert zero.disposition.value == "RETAINED" and zero.rank == 1
    assert survivors == (_gene_id(4),)
    absent = by_id[_gene_id(5)]
    assert isinstance(absent.outcome.affected_cases, UnavailableMeasurement)
    assert absent.outcome.affected_cases.status is UnavailableStatus.NOT_OBSERVED
    assert absent.outcome.affected_cases.reason == "GENE_BUCKET_ABSENT"
    assert absent.disposition.value == "MUTATION_BUCKET_NOT_OBSERVED"
    assert absent.rank is None and absent.entity.gene_id not in survivors


def test_incomplete_aggregation_never_promotes_a_survivor():
    ids = _ids(6, 7)
    batched = _batched([(ids, _counts({_gene_id(6): 90, _gene_id(7): 0}, complete=False))],
                       _coverage())
    entries, survivors = _entries_for(ids, batched)
    by_id = {entry.entity.gene_id: entry for entry in entries}
    assert survivors == ()
    for gene_id in ids:
        assert by_id[gene_id].disposition.value == "MUTATION_AGGREGATION_PARTIAL"
    assert isinstance(by_id[_gene_id(7)].outcome.affected_cases, UnavailableMeasurement)
    assert by_id[_gene_id(7)].outcome.affected_cases.status is UnavailableStatus.UNAVAILABLE


def test_partial_coverage_blocks_eligibility_for_complete_counts():
    ids = _ids(8)
    batched = _batched([(ids, _counts({_gene_id(8): 12}))], _coverage(complete=False))
    entries, survivors = _entries_for(ids, batched)
    assert survivors == ()
    assert entries[0].disposition.value == "MUTATION_AGGREGATION_PARTIAL"
    assert entries[0].reason == "MUTATION_COVERAGE_PARTIAL"


def test_budget_exhaustion_marks_remaining_genes_unavailable():
    ids = _ids(1, 2, 3, 4, 5, 6)
    batch0_ids = _ids(1, 2, 3)
    batched = _batched(
        [(batch0_ids, _counts({_gene_id(1): 10, _gene_id(2): 9, _gene_id(3): 8}))], _coverage(),
        requested=2, exhausted=1)
    entries, survivors = _entries_for(ids, batched, max_survivors=1)
    by_id = {entry.entity.gene_id: entry for entry in entries}
    assert survivors == (_gene_id(1),)
    assert by_id[_gene_id(2)].disposition.value == "BELOW_SURVIVOR_CUTOFF"
    assert by_id[_gene_id(3)].disposition.value == "BELOW_SURVIVOR_CUTOFF"
    for gene_id in _ids(4, 5, 6):
        assert by_id[gene_id].disposition.value == "ACQUISITION_UNAVAILABLE"
        assert by_id[gene_id].reason == "MUTATION_COUNT_BUDGET_EXHAUSTED"
        assert isinstance(by_id[gene_id].outcome.affected_cases, UnavailableMeasurement)
        assert by_id[gene_id].outcome.affected_cases.status is UnavailableStatus.NOT_ACQUIRED


def test_every_requested_gene_receives_exactly_one_disposition():
    ids = _ids(1, 2, 3, 4, 5, 6)
    batched = _batched([(ids, _counts({_gene_id(1): 50, _gene_id(2): 50, _gene_id(3): 30,
                                       _gene_id(4): 0}))], _coverage())
    entries, survivors = _entries_for(ids, batched)
    assert len(entries) == len(ids)
    assert {entry.entity.gene_id for entry in entries} == set(ids)
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.disposition.value] = totals.get(entry.disposition.value, 0) + 1
    assert sum(totals.values()) == len(ids)
    assert totals == {"RETAINED": 4, "MUTATION_BUCKET_NOT_OBSERVED": 2}


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


def _discovery(limit: int, batch: int) -> DiscoverySpec:
    return DiscoverySpec("GENE_ID_ASC_INDEXED_PREFIX_V1", "protein_coding", "GENE_ID_ASC", 0,
                         limit, batch)


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


def test_transport_budget_error_code_is_recognized_for_batch_absorption():
    error = TransportError(TransportErrorCode.REQUEST_BUDGET_EXHAUSTED, "cap reached")
    assert error.code in (TransportErrorCode.REQUEST_BUDGET_EXHAUSTED,
                          TransportErrorCode.BYTE_BUDGET_EXHAUSTED)


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
