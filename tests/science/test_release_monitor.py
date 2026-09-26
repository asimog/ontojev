"""One bounded release observation with typed provenance; comparison is explicit."""

from __future__ import annotations

from dataclasses import replace

from cancerjev.domain.measurements import Acquisition, ScientificSource
from cancerjev.research.release_monitor import (
    RELEASE_MONITOR_VERSION,
    ReleaseObservation,
    observation_hash,
    observe_release,
    release_changed,
)
from tests.integration.replay import ReplayTransport


def _source() -> ScientificSource:
    return ScientificSource(
        endpoint="/status", request_hash="a" * 64, response_hash="b" * 64,
        parser_version="gdc-parser-v1", release="Data Release 46.0",
        acquisition=Acquisition.COMPLETE)


def _observation() -> ReleaseObservation:
    return ReleaseObservation("Data Release 46.0", "a" * 40, _source())


def test_observation_is_one_request_with_typed_provenance(runtime):
    _, repository, artifacts = runtime
    run_id = repository.create_run("release-monitor", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "RELEASE_MONITOR"})
    transport = ReplayTransport(artifacts, run_id, repository=repository)

    observation = observe_release(transport)

    assert RELEASE_MONITOR_VERSION == "release-monitor-v1"
    assert observation.release == "Data Release TEST - 2026-01-01"
    assert observation.release_commit == "0" * 40
    assert observation.source.endpoint == "/status"
    assert len(transport.requests) == 1


def test_release_change_detection_is_structural_only():
    base = _observation()

    assert release_changed(base, base) is False
    assert release_changed(base, replace(base, release_commit="c" * 40)) is True
    assert release_changed(base, replace(base, release="Data Release 47.0")) is True
    assert observation_hash(base) == observation_hash(_observation())
    assert observation_hash(base) != observation_hash(
        replace(base, release="Data Release 47.0"))
