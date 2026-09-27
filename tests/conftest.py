from __future__ import annotations

import socket
import subprocess

import pytest

from cancerjev.config import Settings
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository

LIVE_MARKERS = ("live", "live_gdc", "live_jev", "live_llm", "live_acceptance")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _is_loopback(address: object) -> bool:
    host = address[0] if isinstance(address, tuple) and address else str(address)
    return host in LOOPBACK_HOSTS


@pytest.fixture(autouse=True)
def block_network(monkeypatch, request):
    """Keep every non-live test hermetic: no outbound sockets, no subprocesses.

    ``socket.create_connection``, raw ``socket.connect``/``connect_ex`` and
    ``subprocess.Popen`` are all guarded, because a child process would
    otherwise bypass the in-process socket guard. A test that genuinely needs a
    declared local process (file locks, git plumbing) marks itself with
    ``@pytest.mark.local_process``; the marker never grants network access.
    """
    if any(request.node.get_closest_marker(marker) for marker in LIVE_MARKERS):
        return
    real_create_connection = socket.create_connection
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_popen = subprocess.Popen

    def guarded_create_connection(address, *args, **kwargs):
        if _is_loopback(address):
            return real_create_connection(address, *args, **kwargs)
        raise AssertionError("Outbound network is forbidden in offline tests")

    def guarded_connect(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError("Outbound network is forbidden in offline tests")

    def guarded_connect_ex(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect_ex(self, address, *args, **kwargs)
        raise AssertionError("Outbound network is forbidden in offline tests")

    def guarded_popen(*args, **kwargs):
        if request.node.get_closest_marker("local_process"):
            return real_popen(*args, **kwargs)
        raise AssertionError(
            "Subprocesses are forbidden in offline tests; a test that needs a "
            "declared local process must use @pytest.mark.local_process")

    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)


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

