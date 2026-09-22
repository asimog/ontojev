from __future__ import annotations

import json
from pathlib import Path

from cancerjev.gdc.capture import CaptureSink
from cancerjev.gdc.endpoints import status_request
from cancerjev.gdc.transport import GDCResponse
from cancerjev.storage.artifacts import PublishedArtifact


def _response(body: bytes) -> GDCResponse:
    artifact = PublishedArtifact(artifact_id="a", relative_path="p", sha256="s", size_bytes=len(body),
                                 media_type="application/json", purpose="gdc-response")
    return GDCResponse(request_hash="r", endpoint="/status", method="GET", http_status=200,
                       headers={"content-type": "application/json"}, body=body, body_sha256="s",
                       artifact=artifact, completeness="COMPLETE", from_cache=False,
                       retrieved_at="2026-09-22T00:00:00Z", latency_ms=3)


def test_capture_sink_writes_body_metadata_and_index(tmp_path: Path):
    sink = CaptureSink(tmp_path / "captures")
    sink.record("status", status_request(), _response(b'{"status":"OK"}'))
    directory = tmp_path / "captures"
    assert (directory / "status.body").read_bytes() == b'{"status":"OK"}'
    meta = json.loads((directory / "status.meta.json").read_text(encoding="utf-8"))
    assert meta["authentication_headers_sent"] == []
    assert meta["request_headers_sent"]["Accept-Encoding"] == "identity"
    assert meta["method"] == "GET" and meta["endpoint"] == "/status"
    assert meta["body_bytes_read"] == 15
    index = sink.finalize()
    assert index["probe_count"] == 1
    assert index["authentication"] == "NONE (anonymous)"
    on_disk = json.loads((directory / "INDEX.json").read_text(encoding="utf-8"))
    assert on_disk["captures"][0]["probe_name"] == "status"
