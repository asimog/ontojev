"""Offline Stage 4 replay: the real systematic-discovery function over provider-shaped bytes.

``DiscoveryReplayTransport`` substitutes only the network boundary: every
response flows through the real builders, strict parsers, tested universe,
complete occurrence-scan acquisition, deterministic reducer, typed codec and
the artifact + event persistence path. The synthetic occurrence corpus encodes
documented semantics: a case with two mutations in one gene counts once
(distinct cases), a record annotated to two genes contributes its case to both,
and a gene absent from the corpus is an observed zero. The test reloads the
persisted result through the repository/artifact store and verifies the
identity hash, and asserts the run never touches Jev.
"""

from __future__ import annotations

import json
import math
from uuid import uuid4

from cancerjev.domain.codecs import discovery_identity, read_discovery
from cancerjev.domain.events import utc_now
from cancerjev.domain.measurements import ObservedCount
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
SCAN_PAGE_SIZE = 40
G1, G2, G3, G4, G5, G6 = (f"ENSG0000000000{index}" for index in range(1, 7))
UNIVERSE = [(G1, "S1"), (G2, "S2"), (G3, "S3"), (G4, "S4"), (G5, "S5"), (G6, "S6")]
PROVIDER_TOP = [G6, G1]

SPEC = ResearchSpec(
    spec_id="TEST_DISCOVERY_V2",
    intent="bounded offline systematic discovery replay over the occurrence scan",
    cohort=CohortSpec(cohort_id=PROJECT, domain="lung cancer", project_id=PROJECT),
    discovery=DiscoverySpec(universe_method="GENE_ID_ASC_INDEXED_PREFIX_V1",
                            biotype="protein_coding", order="GENE_ID_ASC", offset=0,
                            universe_limit=6, occurrence_scan_page_size=SCAN_PAGE_SIZE),
    acquisition=AcquisitionSpec(case_page_size=250, case_batch_size=250, max_cohort_cases=1000,
                                discovery_gene_limit=20, count_gene_limit=100,
                                candidate_gene_limit=10, expression_file_sample_size=5),
    limits=ScientificLimits(),
    allowed_actions=("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
)


def _synthetic_occurrences() -> list[dict]:
    """Deterministic released-occurrence corpus with distinct-case semantics.

    G1: 50 distinct cases across 51 documents (case 0000 carries two mutations).
    G2: 51 distinct cases (50 own plus one shared document with G6).
    G3: 30 distinct cases. G4: absent (observed zero). G5: 2 distinct cases.
    G6: 7 distinct cases (one document shared with G2).
    """
    records: list[dict] = []

    def add(occ_id: str, case_id: str, gene_ids: list[str]) -> None:
        records.append({"occ_id": occ_id, "case_id": case_id, "gene_ids": sorted(gene_ids)})

    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"occ-{counter:06d}"

    for index in range(50):
        add(next_id(), f"{PROJECT}-case-{index:04d}", [G1])
    add(next_id(), f"{PROJECT}-case-0000", [G1])
    for index in range(50):
        add(next_id(), f"{PROJECT}-case-{index:04d}", [G2])
    add(next_id(), f"{PROJECT}-case-0050", [G2, G6])
    for index in range(30):
        add(next_id(), f"{PROJECT}-case-{index:04d}", [G3])
    add(next_id(), f"{PROJECT}-case-0000", [G5])
    add(next_id(), f"{PROJECT}-case-0001", [G5])
    for index in range(51, 57):
        add(next_id(), f"{PROJECT}-case-{index:04d}", [G6])
    records.sort(key=lambda record: record["occ_id"])
    return records


OCCURRENCES = _synthetic_occurrences()


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
                    for gene_id, symbol in page]
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": len(UNIVERSE), "size": size, "from": offset,
                "pages": math.ceil(len(UNIVERSE) / size)}}}), request)
        if name == "ssm_occurrences":
            offset = int(params["from"])
            size = int(params["size"])
            page = OCCURRENCES[offset:offset + size]
            hits = [{
                "ssm_occurrence_id": record["occ_id"],
                "case": {"case_id": record["case_id"], "project": {"project_id": PROJECT}},
                "ssm": {"consequence": [
                    {"transcript": {"gene": {"gene_id": gene_id}}} for gene_id in record["gene_ids"]
                ]},
            } for record in page]
            return self._respond(name, _json({"data": {"hits": hits, "pagination": {
                "count": len(hits), "total": len(OCCURRENCES), "size": size, "from": offset,
                "pages": math.ceil(len(OCCURRENCES) / size)}}}), request)
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
    assert result.universe.ordered_ids == tuple(gene_id for gene_id, _ in UNIVERSE)
    assert result.universe.complete is True
    assert result.universe.requested_limit == 6
    assert result.universe.reported_total == 6
    assert result.universe.membership_hash

    # Occurrence scan: complete deterministic paging, one coverage request.
    scan_requests = [request for request in transport.requests
                     if request.endpoint.name == "ssm_occurrences"]
    coverage_requests = [request for request in transport.requests
                         if request.endpoint.name == "mutated_cases_count_by_project"]
    assert len(coverage_requests) == 1
    assert len(scan_requests) == 4
    assert [int(dict(request.params)["from"]) for request in scan_requests] == [0, 40, 80, 120]
    assert all(int(dict(request.params)["size"]) == SCAN_PAGE_SIZE for request in scan_requests)
    assert _project_filter_value(scan_requests[0]) == PROJECT
    count_requests = [request for request in transport.requests
                      if request.endpoint.name == "top_cases_counts_by_genes"]
    assert count_requests == []

    # Deterministic reduction: distinct affected cases desc, gene_id tie break, observed zeros.
    by_id = {entry.entity.gene_id: entry for entry in result.entries}
    assert result.survivor_ids == (G2, G1, G3, G6, G5, G4)
    ranks = {gene_id: entry.rank for gene_id, entry in by_id.items()}
    assert ranks == {G2: 1, G1: 2, G3: 3, G6: 4, G5: 5, G4: 6}
    values = {gene_id: entry.outcome.affected_cases.value for gene_id, entry in by_id.items()}
    assert values == {G1: 50, G2: 51, G3: 30, G4: 0, G5: 2, G6: 7}
    assert all(isinstance(entry.outcome.affected_cases, ObservedCount)
               for entry in result.entries)
    totals: dict[str, int] = {}
    for entry in result.entries:
        totals[entry.disposition.value] = totals.get(entry.disposition.value, 0) + 1
    assert totals == {"RETAINED": 6}

    # The affected measurement cites the immutable scan bundle, not an aggregation bucket.
    first_source = by_id[G1].outcome.affected_cases.sources[0]
    assert first_source.endpoint == "/ssm_occurrences/scan"

    # Labelled comparator: descriptive overlap only.
    assert result.comparator is not None
    assert result.comparator.provider_gene_ids == tuple(PROVIDER_TOP)
    assert result.comparator.survivor_overlap == (G1, G6)

    # Persistence: one immutable result artifact plus the immutable scan bundle.
    completed = [event for event in events if event["type"] == "DISCOVERY_COMPLETED"]
    assert len(completed) == 1
    assert completed[0]["data"]["occurrence_scan"]["pages"] == 4
    assert completed[0]["data"]["occurrence_scan"]["total_occurrences"] == len(OCCURRENCES)
    scan_metadata = repository.artifact(completed[0]["data"]["occurrence_scan"]["artifact_id"])
    assert scan_metadata["sha256"] == completed[0]["data"]["occurrence_scan"]["artifact_sha256"]
    metadata = repository.artifact(completed[0]["data"]["artifact_id"])
    assert metadata["sha256"] == completed[0]["data"]["artifact_sha256"]
    raw = artifacts.read(metadata["relative_path"], metadata["sha256"])
    reloaded = read_discovery(raw, expected_hash=discovery_identity(result))
    assert reloaded == result

    # No Jev anywhere in this run's event stream.
    run_events = repository.events(run_id, 0, 500)["items"]
    assert not [event for event in run_events if event["type"].startswith("JEV")]
    assert [event["type"] for event in run_events if event["type"].startswith("DISCOVERY")] == [
        "DISCOVERY_STARTED", "DISCOVERY_UNIVERSE_ACQUIRED", "DISCOVERY_OCCURRENCE_SCAN_ACQUIRED",
        "DISCOVERY_COMPLETED"]

    # Limitation sentences travel with the result.
    assert any("not the entire genome" in line for line in result.limitations)
    assert any("observed zero" in line for line in result.limitations)
