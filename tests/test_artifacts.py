from __future__ import annotations

import hashlib

import pytest


def test_atomic_artifact_publication_hash_and_corruption(runtime):
    settings, _, artifacts = runtime
    published = artifacts.publish("runs/demo/value.json", b'{"ok":true}', "application/json", "test")
    assert published.sha256 == hashlib.sha256(b'{"ok":true}').hexdigest()
    assert published.size_bytes == 11
    assert artifacts.read(published.relative_path, published.sha256) == b'{"ok":true}'
    (settings.data_dir / published.relative_path).write_bytes(b"corrupt")
    with pytest.raises(OSError, match="checksum"):
        artifacts.read(published.relative_path, published.sha256)


def test_artifact_paths_are_confined(runtime):
    _, _, artifacts = runtime
    with pytest.raises(ValueError, match="relative"):
        artifacts.publish("C:/escape.json", b"x", "application/json", "test")
    with pytest.raises(ValueError, match="escapes"):
        artifacts.publish("../escape.json", b"x", "application/json", "test")

