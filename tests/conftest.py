from __future__ import annotations

import socket

import pytest

from cancerjev.config import Settings
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Outbound network is forbidden in Phase 1 tests")

    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def runtime(tmp_path):
    settings = Settings(tmp_path, 0, 60, "http://localhost:3000")
    database = Database(settings.database_path)
    database.bootstrap()
    return settings, Repository(database), ArtifactStore(tmp_path)

