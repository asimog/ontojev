"""Opt-in live GDC contract probe. Disabled by default: run with `pytest -m live_gdc`.

Bounded to the admitted endpoint surface (~14 requests, <=8 MiB) and anonymous.
"""

from __future__ import annotations

import pytest

from cancerjev.gdc.capture import CaptureSink, run_contract_probe
from cancerjev.gdc.transport import BudgetCaps, GDCTransport, RunBudget


@pytest.mark.live_gdc
def test_bounded_anonymous_contract_probe(runtime, tmp_path):
    settings, repository, artifacts = runtime
    caps = BudgetCaps(max_requests=30, max_bytes=8 * 1024 * 1024, per_response_bytes=8 * 1024 * 1024)
    run_id = repository.create_run("live-contract-probe", mode="LIVE", fixture_id=None, fixture_version=None,
                                   scope={"purpose": "CONTRACT_PROBE"})
    transport = GDCTransport(
        repository, artifacts, RunBudget(caps=caps), run_id,
        lambda *args, **kwargs: None, cache_enabled=False,
    )
    sink = CaptureSink(tmp_path / "captures")
    summary = run_contract_probe(transport, sink, release=None)
    assert summary["captures"] >= 10
    assert summary["bytes"] < 8 * 1024 * 1024
    index = sink.finalize()
    assert all(entry["http_status"] == 200 for entry in index["captures"])
    assert all(entry["authentication_headers_sent"] == [] for entry in sink.entries)
    assert all(entry["completeness"] == "COMPLETE" for entry in sink.entries)
