"""Independent CNV case-shard scan, shard persistence and merged project calls."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cancerjev.domain.codecs import (
    ContractError,
    cnv_project_scan_identity,
    cnv_shard_identity,
    read_cnv_project_scan,
    read_cnv_shard_evidence,
    write_cnv_project_scan,
    write_cnv_shard_evidence,
)
from cancerjev.domain.discovery import CnvDisposition
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.cnv_discovery import run_cnv_shard_merge, run_cnv_shard_scan
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.integration.replay import cases_body, projects_body, status_body

PROJECT = "TCGA-LUAD"
CASES = 30
TP53, EGFR, BRCA1, KRAS, ABSENT = (
    "ENSG00000000001", "ENSG00000000002", "ENSG00000000003", "ENSG00000000004",
    "ENSG00000000009",
)


def _row(occurrence_id: str, case_id: str, gene_id: str, category: str,
         caller: str = "ASCAT3") -> dict:
    return {
        "cnv_occurrence_id": occurrence_id,
        "cnv": {"cnv_id": f"cnv-{occurrence_id}", "cnv_change": category,
                "cnv_change_5_category": category,
                "consequence": [{"gene": {"gene_id": gene_id}}]},
        "case": {"case_id": case_id, "project": {"project_id": PROJECT},
                 "observation": [{"copy_number": 1.0, "src_file_id": "file-1",
                                  "sample": {"tumor_sample_uuid": "sample-1"},
                                  "variant_calling": {"variant_caller": caller}}]},
    }


def _shard_rows(shard_index: int, prefix: str) -> list[dict]:
    def case_id(index: int) -> str:
        return f"{prefix}-case-{index:04d}"

    if shard_index == 0:
        rows = [
            _row(f"occ-t-{index}", case_id(index), TP53, "Amplification")
            for index in range(5)
        ]
        rows += [
            _row(f"occ-e-{index}", case_id(index), EGFR, "Amplification")
            for index in range(3)
        ]
        rows += [
            _row(f"occ-b-{index}", case_id(index), BRCA1, "Amplification")
            for index in range(5)
        ]
        rows.append(_row("occ-b-conflict", case_id(0), BRCA1, "Gain", caller="ASCAT2"))
        rows.append(_row("occ-k-0", case_id(0), KRAS, "Gain"))
        return rows
    rows = [
        _row(f"occ-e2-{index}", case_id(25 + index), EGFR, "Amplification")
        for index in range(3)
    ]
    rows.append(_row("occ-absent-free", case_id(25), KRAS, "Gain"))
    return rows


class _Transport:
    """Serves status/project/cases plus one page per CNV case shard."""

    def __init__(self, artifacts, repository, run_id: str) -> None:
        self.artifacts = artifacts
        self.repository = repository
        self.run_id = run_id
        self.requests = []

    def request(self, request) -> GDCResponse:
        self.requests.append(request)
        name = request.endpoint.name
        params = dict(request.params)
        if name == "status":
            body = status_body()
        elif name == "projects":
            body = projects_body({PROJECT: CASES}, PROJECT)
        elif name == "cases":
            body = cases_body(PROJECT, {PROJECT: CASES}, size=int(params["size"]),
                              offset=int(params["from"]))
        elif name == "cnv_occurrences":
            case_ids = json.loads(params["filters"])["content"][1]["content"]["value"]
            prefix = str(case_ids[0]).rsplit("-case-", 1)[0]
            shard_index = 0 if any(str(case_id).endswith("-case-0000")
                                   for case_id in case_ids) else 1
            rows = sorted(
                (row for row in _shard_rows(shard_index, prefix)
                 if row["case"]["case_id"] in case_ids),
                key=lambda row: row["cnv_occurrence_id"],
            )
            size = int(params["size"])
            offset = int(params["from"])
            page = rows[offset:offset + size]
            body = json.dumps({"data": {"hits": page, "pagination": {
                "total": len(rows), "count": len(page), "size": size, "from": offset,
                "pages": (len(rows) + size - 1) // size if rows else 0,
            }}}).encode()
        else:
            raise AssertionError(f"unexpected endpoint {name}")
        artifact = self.artifacts.publish(f"cnv-scan-fixture/{uuid4().hex}.body", body,
                                          "application/json", "gdc-response")
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at="2026-09-26T00:00:00Z", latency_ms=1,
            request_id=f"cnv-{len(self.requests)}", attempt_no=1,
        )


def _prepare(runtime):
    _, repository, artifacts = runtime
    run_id = repository.create_run("cnv-shard-scan", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "CNV_SCAN"})
    events: list[dict] = []

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs))
    transport = _Transport(artifacts, repository, run_id)
    return run_id, repository, artifacts, transport, emit, events


def test_two_shards_merge_into_project_calls_with_declared_dispositions(runtime):
    run_id, repository, artifacts, transport, emit, events = _prepare(runtime)

    for index in (0, 1):
        evidence = run_cnv_shard_scan(run_id, transport, repository, artifacts, emit,
                                      LUAD_RESEARCH_V1, shard_index=index)
        assert evidence.shard_index == index
        assert read_cnv_shard_evidence(write_cnv_shard_evidence(evidence),
                                       expected_hash=cnv_shard_identity(evidence)) == evidence

    result = run_cnv_shard_merge(run_id, repository, artifacts, emit, LUAD_RESEARCH_V1,
                                 expected_shards=2)

    by_gene = {call.evidence.gene_id: call for call in result.calls}
    assert by_gene[TP53].disposition is CnvDisposition.RETAIN
    assert by_gene[EGFR].disposition is CnvDisposition.RETAIN
    assert len(by_gene[EGFR].evidence.categories[0].case_ids) == 6
    assert by_gene[BRCA1].disposition is CnvDisposition.JEV_REVIEW
    assert by_gene[BRCA1].evidence.conflicting_case_ids == ("TCGA-LUAD-case-0000",)
    assert by_gene[KRAS].disposition is CnvDisposition.DROP
    assert ABSENT not in by_gene, "absence is never a CNV call"
    assert result.retained_ids == (TP53, EGFR)
    assert result.jev_review_ids == (BRCA1,)
    assert result.shard_count == 2

    stored = read_cnv_project_scan(write_cnv_project_scan(result),
                                   expected_hash=cnv_project_scan_identity(result))
    assert stored.calls == result.calls
    completed = [event for event in events if event["type"] == "CNV_PROJECT_SCAN_COMPLETED"]
    assert len(completed) == 1


def test_merge_refuses_until_every_required_shard_exists(runtime):
    run_id, repository, artifacts, transport, emit, _ = _prepare(runtime)
    run_cnv_shard_scan(run_id, transport, repository, artifacts, emit, LUAD_RESEARCH_V1,
                       shard_index=0)

    from cancerjev.research.acquisition import LiveRunError

    with pytest.raises(LiveRunError) as failure:
        run_cnv_shard_merge(run_id, repository, artifacts, emit, LUAD_RESEARCH_V1,
                            expected_shards=2)
    assert failure.value.code == "CNV_SHARDS_NOT_TERMINAL"


def test_shard_evidence_tampering_fails_the_binding(runtime):
    run_id, repository, artifacts, transport, emit, _ = _prepare(runtime)
    evidence = run_cnv_shard_scan(run_id, transport, repository, artifacts, emit,
                                  LUAD_RESEARCH_V1, shard_index=0)
    payload = json.loads(write_cnv_shard_evidence(evidence))
    payload["records"] = payload["records"] + 1

    with pytest.raises(ContractError):
        read_cnv_shard_evidence(json.dumps(payload).encode(),
                                expected_hash=cnv_shard_identity(evidence))
