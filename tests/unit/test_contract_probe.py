"""Offline coverage of the contract probe's deep-pagination and release summary."""

from __future__ import annotations

import json
from types import SimpleNamespace

from cancerjev.gdc.capture import CaptureSink, run_contract_probe


class FakeTransport:
    """Deterministic canned responses; no network and no transport internals."""

    def __init__(self, *, total: int = 177_000, header: str | None = "Data Release 46.0",
                 switch_after: int | None = None) -> None:
        self.total = total
        self.header = header
        self.switch_after = switch_after
        self.calls = 0

    def _body(self, path: str, params: dict) -> bytes:
        if path == "/status":
            return json.dumps({"release": "Data Release 46.0"}).encode()
        if path == "/cases":
            return json.dumps({"data": {"hits": [{"case_id": "case-1"},
                                                 {"case_id": "case-2"}]}}).encode()
        if path == "/ssm_occurrences":
            return json.dumps({"data": {
                "hits": [{"case_id": "case-deep"}],
                "pagination": {"total": self.total, "from": params.get("from", 0),
                               "size": params.get("size", 1)},
            }}).encode()
        return json.dumps({"data": {"hits": []}}).encode()

    def request(self, request):
        self.calls += 1
        header = self.header
        if self.switch_after is not None and self.calls > self.switch_after:
            header = "Data Release 47.0"
        headers = {"x-gdc-data_release": header} if header else {}
        return SimpleNamespace(
            body=self._body(request.path, dict(request.params)), headers=headers,
            http_status=200, retrieved_at="2026-09-27T00:00:00Z", latency_ms=5,
            body_sha256="0" * 64, completeness="COMPLETE", from_cache=False,
        )


def test_probe_summarizes_deep_pagination_and_stable_release_headers(tmp_path):
    sink = CaptureSink(tmp_path / "captures")

    summary = run_contract_probe(FakeTransport(), sink, release=None)

    assert summary["captures"] == 16
    assert summary["occurrence_project"] == "TCGA-LUAD"
    assert summary["occurrence_total"] == 177_000
    assert summary["deep_offset"] == 150_000
    assert summary["deep_hits"] == 1
    assert summary["deep_total_matches"] is True
    assert summary["release_header_stable"] is True
    assert all(value == "Data Release 46.0" for value in summary["release_headers"].values())
    assert (tmp_path / "captures" / "occurrence_deep.meta.json").is_file()


def test_probe_reports_release_header_drift(tmp_path):
    sink = CaptureSink(tmp_path / "captures")

    summary = run_contract_probe(FakeTransport(switch_after=15), sink, release=None)

    assert summary["release_header_stable"] is False


def test_probe_reports_missing_release_headers_as_unobserved(tmp_path):
    sink = CaptureSink(tmp_path / "captures")

    summary = run_contract_probe(FakeTransport(header=None), sink, release=None)

    assert summary["release_header_stable"] is True, \
        "no observed header is not drift; the capture metadata records the absence"
    assert all(value is None for value in summary["release_headers"].values())
