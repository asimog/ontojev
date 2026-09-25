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

