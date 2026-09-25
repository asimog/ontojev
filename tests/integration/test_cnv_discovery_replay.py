"""Offline Stage 6 replay through fixed requests, strict parsing and persistence."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cancerjev.domain.codecs import cnv_discovery_identity, read_cnv_discovery
from cancerjev.domain.events import utc_now
from cancerjev.domain.scientific import CnvOccurrenceResult, UnavailableLane
from cancerjev.gdc.endpoints import GDCRequest
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.cnv_discovery import run_cnv_discovery
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.storage.artifacts import ArtifactStore
from tests.integration.test_discovery_replay import (
    PROJECT,
    RELEASE,
    SPEC,
    DiscoveryReplayTransport,
)


def _json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


class CnvReplayTransport:
    def __init__(self, artifacts: ArtifactStore, run_id: str, repository, *,
                 over_cap_gene: str | None = None, release: str = RELEASE) -> None:
        self.artifacts = artifacts
        self.run_id = run_id
        self.repository = repository
        self.over_cap_gene = over_cap_gene
        self.release = release
        self.requests: list[GDCRequest] = []
        self._counter = 0

    def _respond(self, request: GDCRequest, body: bytes) -> GDCResponse:
        self._counter += 1
        artifact = self.artifacts.publish(
            f"replay/{self.run_id}/cnv-{self._counter}.body", body, "application/json",
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
        if request.endpoint.name == "status":
            return self._respond(request, _json({
                "commit": "0" * 40, "data_release": self.release,
                "status": "OK", "tag": "8.5.0"}))
        assert request.endpoint.name == "cnv_occurrences"
        params = dict(request.params)
        filters = json.loads(params["filters"])
        gene_id = filters["content"][1]["content"]["value"][0]
        size = int(params["size"])
        offset = int(params["from"])
        if gene_id == self.over_cap_gene:
            total = 2501
            records = [
                self._hit(gene_id, index, "Loss", "ASCAT3", sample=None)
                for index in range(size)
            ]
        elif gene_id.endswith("2"):
            total = 3
            records = [
                self._hit(gene_id, 0, "Loss", "ASCAT3", sample=None),
                self._hit(gene_id, 1, "Gain", "ASCAT2", sample="sample-1", case_index=0),
                self._hit(gene_id, 2, "Amplification", "AscatNGS", sample=None),
            ]
        elif gene_id.endswith("1"):
            total = 1
            records = [self._hit(gene_id, 0, "Homozygous Deletion", "ASCAT3", sample=None)]
        else:
            total = 0
            records = []
        records = records[offset:offset + size]
        return self._respond(request, _json({"data": {"hits": records, "pagination": {
            "count": len(records), "total": total, "size": size, "from": offset,
            "page": (offset // size) + 1, "pages": (total + size - 1) // size,
        }}, "warnings": {}}))

    @staticmethod
    def _hit(gene_id: str, index: int, category: str, caller: str, *,
             sample: str | None, case_index: int | None = None) -> dict:
        occurrence_id = f"occ-{index:03d}-{gene_id}"
        observation = {
            "copy_number": float(index + 1), "src_file_id": f"file-{index}",
            "variant_calling": {"variant_caller": caller},
        }
        if sample is not None:
            observation["sample"] = {"tumor_sample_uuid": sample}
        return {
            "cnv_occurrence_id": occurrence_id,
            "case": {"case_id": f"{PROJECT}-case-{case_index if case_index is not None else index:04d}",
                     "project": {"project_id": PROJECT}, "observation": [observation]},
            "cnv": {"cnv_id": f"cnv-{index}",
                    "cnv_change": "Gain" if category in {"Gain", "Amplification"} else "Loss",
                    "cnv_change_5_category": category,
                    "consequence": [{"gene": {"gene_id": gene_id}}]},
        }


def _stage4(runtime):
    _, repository, artifacts = runtime
    run_id = repository.create_run(
        "stage4-for-cnv", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "SYSTEMATIC_DISCOVERY"})

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)

    result = run_mutation_discovery(
        run_id, DiscoveryReplayTransport(artifacts, run_id, repository),
        repository, artifacts, emit, SPEC)
    return repository, artifacts, result


def test_cnv_discovery_replay_binds_stage4_and_preserves_conflicts(runtime):
    repository, artifacts, mutation_result = _stage4(runtime)
    run_id = repository.create_run(
        "cnv-replay", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "CNV_DISCOVERY"})
    events: list[dict] = []

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs))

    transport = CnvReplayTransport(artifacts, run_id, repository)
    result = run_cnv_discovery(
        run_id, transport, repository, artifacts, emit, SPEC, mutation_result)

    assert result.survivor_ids == mutation_result.survivor_ids
    assert result.mutation_discovery_hash
    assert [request.endpoint.name for request in transport.requests].count("cnv_occurrences") == 6
    first = result.entries[0]
    assert isinstance(first.outcome, CnvOccurrenceResult)
    assert [item.raw_category for item in first.categories] == ["Amplification", "Gain", "Loss"]
    assert first.conflicting_case_ids == (f"{PROJECT}-case-0000",)
    assert first.callers == ("ASCAT2", "ASCAT3", "AscatNGS")
    assert len(first.missing_sample_occurrence_ids) == 2
    assert result.entries[2].categories == (), "complete absence is not converted to neutral"
    assert not any(isinstance(entry.outcome, UnavailableLane) for entry in result.entries)

    completed = [event for event in events if event["type"] == "CNV_DISCOVERY_COMPLETED"]
    metadata = repository.artifact(completed[0]["data"]["artifact_id"])
    raw = artifacts.read(metadata["relative_path"], metadata["sha256"])
    assert read_cnv_discovery(raw, expected_hash=cnv_discovery_identity(result)) == result
    assert not [event for event in repository.events(run_id, 0, 100)["items"]
                if event["type"].startswith("JEV")]


def test_cnv_discovery_marks_over_cap_gene_unavailable_without_partial_rows(runtime):
    repository, artifacts, mutation_result = _stage4(runtime)
    run_id = repository.create_run("cnv-cap-replay", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "CNV_DISCOVERY"})

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)

    result = run_cnv_discovery(
        run_id, CnvReplayTransport(
            artifacts, run_id, repository, over_cap_gene=mutation_result.survivor_ids[0]),
        repository, artifacts, emit, SPEC, mutation_result)
    first = result.entries[0]
    assert isinstance(first.outcome, UnavailableLane)
    assert first.outcome.reason == "CNV_OCCURRENCE_PAGE_CAP_EXCEEDED"
    assert first.categories == ()


def test_cnv_discovery_rejects_release_drift(runtime):
    repository, artifacts, mutation_result = _stage4(runtime)
    run_id = repository.create_run("cnv-release-replay", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "CNV_DISCOVERY"})

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)

    with pytest.raises(LiveRunError, match="CNV_RELEASE_MISMATCH"):
        run_cnv_discovery(
            run_id, CnvReplayTransport(
                artifacts, run_id, repository, release="Data Release NEXT"),
            repository, artifacts, emit, SPEC, mutation_result)
