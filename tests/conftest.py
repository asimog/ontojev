from __future__ import annotations

import socket

import pytest

from cancerjev.config import Settings
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


@pytest.fixture(autouse=True)
def block_network(monkeypatch, request):
    if any(request.node.get_closest_marker(marker) for marker in (
        "live", "live_gdc", "live_jev", "live_llm", "live_acceptance",
    )):
        return
    real_create_connection = socket.create_connection

    def guarded(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host in {"127.0.0.1", "localhost", "::1"}:
            return real_create_connection(address, *args, **kwargs)
        raise AssertionError("Outbound network is forbidden in offline tests")

    monkeypatch.setattr(socket, "create_connection", guarded)


@pytest.fixture
def runtime(tmp_path):
    settings = Settings(tmp_path, 0, 60, "http://localhost:3000")
    database = Database(settings.database_path)
    database.bootstrap()
    return settings, Repository(database), ArtifactStore(tmp_path)


# The everyday gate: focused contract/invariant tests plus one core offline replay.
# Run with ``python -m pytest -m fast``. Everything else (heavy multi-run integration,
# browser acceptance and live providers) stays available through the full/offline commands.
_FAST_PREFIXES = ("tests/contracts/", "tests/science/", "tests/jev/", "tests/unit/",
                  "tests/reconciliation/")
_FAST_FILES = {
    "tests/test_identity.py",
    "tests/test_fixtures.py",
    "tests/test_domain_events.py",
    "tests/test_persistence_guards.py",
}


def pytest_collection_modifyitems(items):
    for item in items:
        node_id = item.nodeid.replace("\\", "/")
        if node_id.startswith(_FAST_PREFIXES) or node_id.split("::", 1)[0] in _FAST_FILES:
            item.add_marker(pytest.mark.fast)

