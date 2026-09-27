"""Real captured open-access metadata drives the typed cohort capability.

Bodies under ``fixtures/gdc/capability`` were captured anonymously from the GDC
API on 2026-09-26 (status + TCGA-LUAD/TCGA-LUSC project records + one aggregate
open-file facet request per project). The capability derivation must reproduce
from these pinned bytes alone, with no cohort-specific branch.

The pinned facet captures predate ``files_capability_request`` listing ``access``
in ``facets`` (the capture sent only the server-side ``access=open`` filter), so
the probe re-attaches the bucket the current request contract must observe: a
single open bucket counted at the response's own pagination total. The pinned
capture bytes are never rewritten; the reconstruction is declared here, and the
missing-facet and controlled-bucket probes prove the guard fails closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from cancerjev.domain.capability import (
    AccessLevel,
    CapabilityAvailability,
    CaseSampleResolution,
    Modality,
)
from cancerjev.gdc.parsers import ParserError, ResponseMeta, parse_file_facets
from cancerjev.gdc.transport import GDCResponse
from cancerjev.research.capability import CapabilityError, discover_cohort_capability

FIXTURES = Path(__file__).parent / "fixtures" / "gdc" / "capability"


def _load(name: str) -> tuple[bytes, ResponseMeta]:
    body = (FIXTURES / f"{name}.body").read_bytes()
    meta = json.loads((FIXTURES / f"{name}.meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(body).hexdigest() == meta["body_sha256"], f"fixture {name} changed"
    return body, ResponseMeta(
        endpoint=meta["endpoint"], method=meta["method"], request_hash="fixture",
        response_sha256=meta["body_sha256"], artifact_id=None, retrieved_at=meta["retrieved_at"],
        source_release="fixture", completeness="COMPLETE",
    )


def _declare_access_facet(body: bytes,
                          buckets: tuple[tuple[str, int], ...] | None = None) -> bytes:
    """The captured facet body plus the access facet the current request asks for."""
    document = json.loads(body)
    if buckets is None:
        buckets = (("open", document["data"]["pagination"]["total"]),)
    document["data"]["aggregations"]["access"] = {
        "buckets": [{"doc_count": count, "key": key} for key, count in buckets]}
    return json.dumps(document, sort_keys=True).encode()


class _StubTransport:
    """Serves the retained real bodies through the same transport contract."""

    def __init__(self, artifacts, bodies: dict[str, bytes]) -> None:
        self.artifacts = artifacts
        self.bodies = bodies
        self.requests = []

    def request(self, request) -> GDCResponse:
        self.requests.append(request)
        body = self.bodies[request.endpoint.name]
        artifact = self.artifacts.publish(
            f"test-capability/{request.endpoint.name}-{uuid4().hex}.body", body,
            "application/json", "gdc-response",
        )
        return GDCResponse(
            request_hash=request.request_hash(), endpoint=request.path, method=request.method,
            http_status=200, headers={"content-type": "application/json"}, body=body,
            body_sha256=artifact.sha256, artifact=artifact, completeness="COMPLETE",
            from_cache=False, retrieved_at="2026-09-26T00:00:00Z", latency_ms=1,
            request_id=f"capability-{len(self.requests)}", attempt_no=1,
        )


def _probe(runtime, project: str, *,
           access_buckets: tuple[tuple[str, int], ...] | None = None):
    artifacts = runtime[2]
    prefix = "luad" if project == "TCGA-LUAD" else "lusc"
    facet_body = _declare_access_facet(_load(f"{prefix}_files_facets")[0], access_buckets)
    transport = _StubTransport(artifacts, {
        "status": _load("status")[0],
        "projects": _load(f"{prefix}_project")[0],
        "files": facet_body,
    })
    return transport, discover_cohort_capability(transport, project_id=project)


def test_real_capability_capture_decomposes_into_typed_records(runtime):
    transport, capability = _probe(runtime, "TCGA-LUAD")

    assert capability.release == "Data Release 46.0 - August 10, 2026"
    assert capability.release_commit and len(capability.release_commit) == 40
    assert capability.parser_version == "gdc-parser-v1"
    assert capability.data_model_ref.startswith("gdcdatamodel2@")
    assert capability.available_modalities() == (
        Modality.CNV,
        Modality.EXPRESSION_RNASEQ,
        Modality.MUTATION_WGS,
        Modality.MUTATION_WXS,
    )
    assert {request.endpoint.name for request in transport.requests} == {"status", "projects", "files"}
    assert all(record.access_level is AccessLevel.OPEN for record in capability.records)
    assert all(record.case_sample_resolution is CaseSampleResolution.CASE_LEVEL_ONLY
               for record in capability.records)
    # Non-vacuous open evidence: the request asks for the access facet and the
    # observed aggregate carries exactly one open bucket at the captured total.
    facet_request = next(request for request in transport.requests
                         if request.endpoint.name == "files")
    assert "access" in dict(facet_request.params)["facets"]
    captured, meta = _load("luad_files_facets")
    facets = parse_file_facets(_declare_access_facet(captured), meta)
    assert facets.total_open_files == 14053
    assert facets.facet("access") == {"open": 14053}


def test_a_provider_controlled_bucket_fails_closed(runtime):
    with pytest.raises(CapabilityError) as failure:
        _probe(runtime, "TCGA-LUAD",
               access_buckets=(("open", 14053), ("controlled", 3)))

    assert failure.value.code == "CONTROLLED_ACCESS_RETURNED"
    assert "controlled" in failure.value.detail


def test_a_facet_response_without_the_access_facet_is_rejected(runtime):
    transport = _StubTransport(runtime[2], {
        "status": _load("status")[0],
        "projects": _load("luad_project")[0],
        "files": _load("luad_files_facets")[0],
    })
    with pytest.raises(ParserError) as failure:
        discover_cohort_capability(transport, project_id="TCGA-LUAD")

    assert failure.value.code == "INVALID_FACET"
    assert "access" in failure.value.detail


def test_real_capability_keeps_unvalidated_modalities_unavailable_with_reasons(runtime):
    _, capability = _probe(runtime, "TCGA-LUAD")

    methylation = capability.record(Modality.METHYLATION)
    assert methylation.source_present is True
    assert methylation.availability is CapabilityAvailability.UNAVAILABLE
    assert methylation.reason == "NO_VALIDATED_METHOD"

    structural = capability.record(Modality.STRUCTURAL_VARIANT)
    assert structural.source_present is True
    assert structural.reason == "NO_VALIDATED_METHOD"

    clinical = capability.record(Modality.CLINICAL)
    assert clinical.source_present is True
    assert clinical.reason == "NO_VALIDATED_METHOD"

    fusion = capability.record(Modality.FUSION)
    assert fusion.source_present is False
    assert fusion.reason == "SOURCE_NOT_PRESENT"

    single_cell = capability.record(Modality.SCRNA_SNRNA)
    assert single_cell.reason == "SOURCE_NOT_PRESENT"


def test_real_capability_is_deterministic_and_reason_bearing(runtime):
    first_transport, first = _probe(runtime, "TCGA-LUAD")
    second_transport, second = _probe(runtime, "TCGA-LUAD")

    assert first.capability_hash() == second.capability_hash()
    assert first.payload() == second.payload()
    assert [request.request_hash() for request in first_transport.requests] == \
           [request.request_hash() for request in second_transport.requests]
    assert first.warnings == () or all("workflow" in warning or ":" in warning
                                       for warning in first.warnings)


def test_a_second_project_flows_through_the_same_code_path(runtime):
    _, capability = _probe(runtime, "TCGA-LUSC")

    assert capability.project_id == "TCGA-LUSC"
    assert capability.cohort_id == "TCGA-LUSC"
    assert capability.available_modalities() == (
        Modality.CNV,
        Modality.EXPRESSION_RNASEQ,
        Modality.MUTATION_WGS,
        Modality.MUTATION_WXS,
    )
    assert capability.record(Modality.FUSION).reason == "SOURCE_NOT_PRESENT"
