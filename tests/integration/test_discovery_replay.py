"""Offline Stage 4 replay: the real systematic-discovery function over provider-shaped bytes.

``DiscoveryReplayTransport`` substitutes only the network boundary: every
response flows through the real builders, strict parsers, tested universe,
batched count acquisition, deterministic reducer, typed codec and the artifact +
event persistence path. The test reloads the persisted result through the
repository/artifact store and verifies the identity hash, and asserts the run
never touches Jev.
"""

from __future__ import annotations

import json
import math
from uuid import uuid4

from cancerjev.domain.codecs import discovery_identity, read_discovery
from cancerjev.domain.events import utc_now
from cancerjev.gdc.endpoints import GDCRequest
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.research.specs import (
    AcquisitionSpec,
    CohortSpec,
    DiscoverySpec,
    ResearchSpec,
    ScientificLimits,
)
from cancerjev.storage.artifacts import ArtifactStore

RELEASE = "Data Release 46.0 - August 10, 2026"
PROJECT = "TCGA-LUAD"
CASE_COUNT = 600
UNIVERSE = [
    ("ENSG00000000001", "S1", 50),
    ("ENSG00000000002", "S2", 50),
    ("ENSG00000000003", "S3", 30),
    ("ENSG00000000004", "S4", 0),
    ("ENSG00000000005", "S5", None),
    ("ENSG00000000006", "S6", 7),
]
PROVIDER_TOP = ["ENSG00000000006", "ENSG00000000001"]

SPEC = ResearchSpec(
    spec_id="TEST_DISCOVERY_V1",
    intent="bounded offline systematic discovery replay",
    cohort=CohortSpec(cohort_id=PROJECT, domain="lung cancer", project_id=PROJECT),
    discovery=DiscoverySpec(universe_method="GENE_ID_ASC_INDEXED_PREFIX_V1",
                            biotype="protein_coding", order="GENE_ID_ASC", offset=0,
                            universe_limit=6, mutation_batch_size=2),
    acquisition=AcquisitionSpec(case_page_size=250, case_batch_size=250, max_cohort_cases=1000,
                                discovery_gene_limit=20, count_gene_limit=100,
                                candidate_gene_limit=10, expression_file_sample_size=5),
    limits=ScientificLimits(),
    allowed_actions=("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
)


def _json(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _project_filter_value(request: GDCRequest) -> str:
    filters = json.loads(dict(request.params)["filters"])
    return filters["content"]["value"][0]


class DiscoveryReplayTransport:
    """Provider-shaped responses over real artifacts; no sockets, no Jev."""

    def __init__(self, artifacts: ArtifactStore, run_id: str, repository) -> None:
        self.artifacts = artifacts
        self.run_id = run_id
        self.repository = repository
        self.requests: list[GDCRequest] = []
        self._counter = 0

    def _respond(self, name: str, body: bytes, request: GDCRequest) -> GDCResponse:
        self._counter += 1
        artifact = self.artifacts.publish(
            f"replay/{self.run_id}/{name}-{self._counter}.body", body, "application/json",
            "gdc-response")
        self.repository.register_artifact(artifact, self.run_id)
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at=utc_now(), latency_ms=1, request_id=str(uuid4()),
            attempt_no=1)

    def request(self, request: GDCRequest) -> GDCResponse:
        self.requests.append(request)
        params = dict(request.params)
        name = request.endpoint.name
        if name == "status":
            return self._respond(name, _json({
                "commit": "0" * 40, "data_release": RELEASE, "status": "OK", "tag": "8.5.0"}), request)
        if name == "projects":
            if params["size"] == "1":
                hits = [{"project_id": PROJECT, "name": "Adenocarcinoma",
                         "program": {"name": "TCGA"}, "primary_site": ["Lung"],
                         "disease_type": ["Adenomas and Adenocarcinomas"],
                         "summary": {"case_count": CASE_COUNT, "file_count": 30,
                                     "data_categories": [{"data_category": "Sequencing Reads"}]}}]
            else:
                hits = []
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": len(hits), "size": int(params["size"]),
                "from": 0, "pages": 1}}}), request)
        if name == "cases":
            offset = int(params["from"])
            size = int(params["size"])
            all_ids = [f"{PROJECT}-case-{index:04d}" for index in range(CASE_COUNT)]
            page_ids = all_ids[offset:offset + size]
            hits = [{"case_id": case_id, "submitter_id": case_id.upper(),
                     "project": {"project_id": PROJECT},
                     "samples": [{"sample_type": "Primary Tumor"}]} for case_id in page_ids]
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": CASE_COUNT, "size": size, "from": offset,
                "pages": math.ceil(CASE_COUNT / size)}}}), request)
        if name == "genes":
            offset = int(params["from"])
            size = int(params["size"])
            page = UNIVERSE[offset:offset + size]
            hits = [{"gene_id": gene_id, "symbol": symbol, "biotype": "protein_coding"}
                    for gene_id, symbol, _ in page]
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": len(UNIVERSE), "size": size, "from": offset,
                "pages": math.ceil(len(UNIVERSE) / size)}}}), request)
        if name == "top_cases_counts_by_genes":
            requested = params["gene_ids"].split(",")
            counts = {gene_id: count for gene_id, _, count in UNIVERSE
                      if gene_id in requested and count is not None}
            incomplete = "ENSG00000000005" in requested
            gene_buckets = [{"key": gene_id, "doc_count": count}
                            for gene_id, count in sorted(counts.items())]
            return self._respond(name, _json({
                "took": 4, "timed_out": False, "_shards": {"total": 5, "successful": 5, "failed": 0},
                "sum_other_doc_count": 2 if incomplete else 0,
                "doc_count_error_upper_bound": 2 if incomplete else 0,
                "aggregations": {"projects": {"buckets": [{
                    "key": PROJECT, "doc_count": sum(counts.values()),
                    "genes": {"my_genes": {"gene_id": {"buckets": gene_buckets}}}}]}}}), request)
        if name == "mutated_cases_count_by_project":
            return self._respond(name, _json({
                "took": 3, "timed_out": False, "_shards": {"total": 5, "successful": 5, "failed": 0},
                "sum_other_doc_count": 0, "doc_count_error_upper_bound": 0,
                "aggregations": {"projects": {"buckets": [{
                    "key": PROJECT, "doc_count": CASE_COUNT,
                    "case_summary": {"case_with_ssm": {"doc_count": CASE_COUNT}}}]}}}), request)
        if name == "top_mutated_genes_by_project":
            assert _project_filter_value(request) == PROJECT
            hits = [{"gene_id": gene_id, "symbol": f"S{gene_id[-1]}", "_score": 100.0 - index}
                    for index, gene_id in enumerate(PROVIDER_TOP)]
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": len(hits), "size": 20, "from": 0, "pages": 1}}}), request)
        raise AssertionError(f"replay transport has no response for {name}")


def test_discovery_replay_persists_and_reloads_the_typed_result(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run("replay-worker", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "SYSTEMATIC_DISCOVERY"})
    events: list[dict] = []

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(run_id, event_type=event_type,
                                              idempotency_key=key, message=message, **kwargs))

    transport = DiscoveryReplayTransport(artifacts, run_id, repository)
    result = run_mutation_discovery(run_id, transport, repository, artifacts, emit, SPEC)

    # Universe contract: the complete bounded prefix, hash-bound.
    assert result.universe.ordered_ids == tuple(gene_id for gene_id, _, _ in UNIVERSE)
    assert result.universe.complete is True
    assert result.universe.requested_limit == 6
    assert result.universe.reported_total == 6
    assert result.universe.membership_hash

    # Batching: coverage once, one ≤100-gene request per batch, disjoint, universe order.
    count_requests = [request for request in transport.requests
                      if request.endpoint.name == "top_cases_counts_by_genes"]
    coverage_requests = [request for request in transport.requests
                         if request.endpoint.name == "mutated_cases_count_by_project"]
    assert len(coverage_requests) == 1
    requested_batches = [dict(request.params)["gene_ids"].split(",")
                         for request in count_requests]
    assert requested_batches == [
        ["ENSG00000000001", "ENSG00000000002"], ["ENSG00000000003", "ENSG00000000004"],
        ["ENSG00000000005", "ENSG00000000006"]]

    # Deterministic reduction: count desc, gene_id tie break, zero eligible, absence never zero.
    by_id = {entry.entity.gene_id: entry for entry in result.entries}
    assert result.survivor_ids == ("ENSG00000000001", "ENSG00000000002", "ENSG00000000003",
                                   "ENSG00000000004")
    ranks = {gene_id: entry.rank for gene_id, entry in by_id.items()}
    assert ranks == {"ENSG00000000001": 1, "ENSG00000000002": 2, "ENSG00000000003": 3,
                     "ENSG00000000004": 4, "ENSG00000000005": None, "ENSG00000000006": None}
    from cancerjev.domain.measurements import (
        ObservedCount,
        UnavailableMeasurement,
        UnavailableStatus,
    )
    zero = by_id["ENSG00000000004"].outcome.affected_cases
    assert isinstance(zero, ObservedCount) and zero.value == 0
    absent = by_id["ENSG00000000005"].outcome.affected_cases
    assert isinstance(absent, UnavailableMeasurement)
    assert absent.status is UnavailableStatus.UNAVAILABLE
    partial = by_id["ENSG00000000006"].outcome.affected_cases
    assert isinstance(partial, ObservedCount) and partial.value == 7
    totals: dict[str, int] = {}
    for entry in result.entries:
        totals[entry.disposition.value] = totals.get(entry.disposition.value, 0) + 1
    assert totals == {"RETAINED": 4, "MUTATION_AGGREGATION_PARTIAL": 2}
    assert len(result.entries) == len(UNIVERSE)

    # Labelled comparator: descriptive overlap only.
    assert result.comparator is not None
    assert result.comparator.provider_gene_ids == tuple(PROVIDER_TOP)
    assert result.comparator.survivor_overlap == ("ENSG00000000001",)

    # Persistence: one immutable artifact; reload verifies identity and content.
    completed = [event for event in events if event["type"] == "DISCOVERY_COMPLETED"]
    assert len(completed) == 1
    metadata = repository.artifact(completed[0]["data"]["artifact_id"])
    assert metadata["sha256"] == completed[0]["data"]["artifact_sha256"]
    raw = artifacts.read(metadata["relative_path"], metadata["sha256"])
    reloaded = read_discovery(raw, expected_hash=discovery_identity(result))
    assert reloaded == result

    # No Jev anywhere in this run's event stream.
    run_events = repository.events(run_id, 0, 500)["items"]
    assert not [event for event in run_events if event["type"].startswith("JEV")]
    assert [event["type"] for event in run_events if event["type"].startswith("DISCOVERY")] == [
        "DISCOVERY_STARTED", "DISCOVERY_UNIVERSE_ACQUIRED", "DISCOVERY_COMPLETED"]

    # Limitation sentences travel with the result.
    assert any("not the entire genome" in line for line in result.limitations)
    assert any("NOT_OBSERVED" in line for line in result.limitations)
