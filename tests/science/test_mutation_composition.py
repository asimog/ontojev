"""Canonical-consequence composition, declared review triggers, duplication guards."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cancerjev.domain.measurements import ContractError
from cancerjev.gdc.parsers import ResponseMeta, parse_ssm_occurrence_page
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.acquisition import acquire_project_mutation_occurrence_scan
from cancerjev.science.mutation import mutation_descriptive_evidence

PROJECT = "TCGA-LUAD"
GENE = "ENSG00000141510"


def _occurrence(occurrence_id: str, consequences: list[dict]) -> dict:
    return {
        "ssm_occurrence_id": occurrence_id,
        "case": {"case_id": f"case-{occurrence_id}", "project": {"project_id": PROJECT}},
        "ssm": {"consequence": consequences},
    }


def _page_body(hits: list[dict]) -> bytes:
    return json.dumps({"data": {"hits": hits, "pagination": {
        "total": len(hits), "count": len(hits), "size": 40, "from": 0, "pages": 1,
    }}}).encode()


def _meta(artifacts) -> ResponseMeta:
    body = b"{}"
    artifact = artifacts.publish(f"composition-test/{uuid4().hex}.body", body,
                                 "application/json", "gdc-response")
    return ResponseMeta(endpoint="/ssm_occurrences", method="GET", request_hash="0" * 64,
                        response_sha256=artifact.sha256, artifact_id=None,
                        retrieved_at="2026-09-26T00:00:00Z", source_release="test",
                        completeness="COMPLETE")


class _ScanTransport:
    def __init__(self, artifacts, body: bytes) -> None:
        self.artifacts = artifacts
        self.body = body
        self.requests = []

    def request(self, request) -> GDCResponse:
        self.requests.append(request)
        artifact = self.artifacts.publish(f"composition-test/{uuid4().hex}.body", self.body,
                                          "application/json", "gdc-response")
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=self.body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at="2026-09-26T00:00:00Z", latency_ms=1,
            request_id=f"composition-{len(self.requests)}", attempt_no=1,
        )


CANONICAL_TERMS = [
    {"transcript": {"gene": {"gene_id": GENE}, "is_canonical": True, "transcript_id": "T1",
                    "consequence_type": "missense_variant", "protein_start": 100}},
    {"transcript": {"gene": {"gene_id": GENE}, "is_canonical": True, "transcript_id": "T2",
                    "consequence_type": ["missense_variant", "splice_region_variant"],
                    "protein_start": 100}},
    {"transcript": {"gene": {"gene_id": GENE}, "is_canonical": False, "transcript_id": "T3",
                    "consequence_type": "stop_gained", "protein_start": 200}},
]


def _scan(runtime, hits: list[dict]):
    transport = _ScanTransport(runtime[2], _page_body(hits))
    scan = acquire_project_mutation_occurrence_scan(transport, PROJECT, 40, "test-release")
    return transport, scan


def test_transcript_duplication_cannot_inflate_composition(runtime):
    _, scan = _scan(runtime, [_occurrence("occ-1", CANONICAL_TERMS)])

    assert scan.consequences_per_gene[GENE] == {"missense_variant": 1,
                                                "splice_region_variant": 1}
    assert scan.protein_positions_per_gene[GENE] == {100: 1}
    assert scan.canonical_transcript_counts_per_gene[GENE] == {"T1": 1, "T2": 1}
    assert "stop_gained" not in scan.consequences_per_gene[GENE]


def test_records_without_canonical_rows_are_not_observed_never_negative(runtime):
    _, scan = _scan(runtime, [
        _occurrence("occ-1", CANONICAL_TERMS),
        _occurrence("occ-2", [
            {"transcript": {"gene": {"gene_id": GENE}, "is_canonical": False,
                            "consequence_type": "intron_variant"}},
        ]),
    ])

    assert scan.records_without_canonical_rows == 1
    assert scan.consequences_per_gene[GENE] == {"missense_variant": 1,
                                                "splice_region_variant": 1}
    assert any("canonical" in warning for warning in scan.warnings)


def test_boolean_protein_start_is_rejected(runtime):
    hits = [_occurrence("occ-1", [
        {"transcript": {"gene": {"gene_id": GENE}, "is_canonical": True,
                        "consequence_type": "missense_variant", "protein_start": True}},
    ])]

    with pytest.raises(Exception) as failure:
        parse_ssm_occurrence_page(_page_body(hits), _meta(runtime[2]), expected_project=PROJECT,
                                  expected_offset=0, expected_size=40)

    assert getattr(failure.value, "code", "") == "INVALID_FIELD"


def test_declared_triggers_and_descriptive_limits():
    ratio = mutation_descriptive_evidence(
        distinct_cases=2, occurrence_docs=9, consequences={"missense_variant": 5},
        positions={100: 9}, transcript_counts={"T1": 1})
    assert ratio.review_trigger == "OCCURRENCE_PER_CASE_RATIO_GT_4"

    hotspot = mutation_descriptive_evidence(
        distinct_cases=30, occurrence_docs=30, consequences={"missense_variant": 30},
        positions={100: 8, 200: 6, 300: 5, 400: 4, 500: 3, 600: 2, 700: 1, 800: 1},
        transcript_counts={"T1": 1})
    assert hotspot.hotspot_descriptor == "HOTSPOT_PROTEIN_START_100"
    assert hotspot.review_trigger == "HOTSPOT_CONCENTRATION"
    assert len(hotspot.protein_position_top) == 5
    assert hotspot.protein_position_top[0] == (100, 8)

    quiet = mutation_descriptive_evidence(
        distinct_cases=30, occurrence_docs=30, consequences={"missense_variant": 30},
        positions={100: 1}, transcript_counts={"T1": 1})
    assert quiet.review_trigger is None and quiet.hotspot_descriptor is None

    payload = ratio.payload()
    assert not any("p_value" in key or "q_value" in key or "significance" in key
                   for key in payload)
    assert any("no p-values" in limitation for limitation in ratio.limitations)
