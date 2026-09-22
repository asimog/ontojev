from __future__ import annotations

import hashlib
import os

import pytest

from cancerjev.storage.artifacts import artifact_id_for


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
    settings, _, artifacts = runtime
    traversal = ["../escape.json", "runs/../../escape.json", "runs/nested/../../../escape.json"]
    if os.name == "nt":
        traversal += ["..\\escape.json", "C:/escape.json", "//server/share/escape.json"]
    for path in traversal:
        with pytest.raises(ValueError):
            artifacts.publish(path, b"x", "application/json", "test")
    native_absolute = str((settings.data_dir.parent / "escape.json").resolve())
    with pytest.raises(ValueError, match="relative"):
        artifacts.publish(native_absolute, b"x", "application/json", "test")
    assert not (settings.data_dir.parent / "escape.json").exists()


def test_legitimate_nested_relative_paths_are_allowed(runtime):
    settings, _, artifacts = runtime
    published = artifacts.publish("runs/demo/nested/value.json", b'{"ok":true}', "application/json", "test")
    assert published.relative_path == "runs/demo/nested/value.json"
    assert (settings.data_dir / published.relative_path).is_file()


def test_artifact_republish_is_idempotent_and_collisions_fail(runtime):
    _, repository, artifacts = runtime
    first = artifacts.publish("runs/demo/value.json", b'{"ok":true}', "application/json", "test")
    repeat = artifacts.publish("runs/demo/value.json", b'{"ok":true}', "application/json", "test")
    assert repeat.artifact_id == first.artifact_id == artifact_id_for("runs/demo/value.json", first.sha256)
    with pytest.raises(FileExistsError, match="collision"):
        artifacts.publish("runs/demo/value.json", b'{"ok":false}', "application/json", "test")


def test_artifact_registration_recovers_when_file_exists_but_row_is_missing(runtime):
    _, repository, artifacts = runtime
    published = artifacts.publish("runs/demo/recovery.json", b'{"ok":true}', "application/json", "test")
    run_id = repository.create_run("test")
    repository.append_event(run_id, event_type="RUN_CREATED", idempotency_key="created", message="created")
    assert repository.artifact(published.artifact_id) is None
    repository.append_event(
        run_id, event_type="RUN_STARTED", idempotency_key="started", message="started",
        registrations=[repository.artifact_registration(published, run_id)],
    )
    assert repository.artifact(published.artifact_id) is not None
    repository.append_event(
        run_id, event_type="STAGE_STARTED", idempotency_key="stage", message="stage", stage="INVENTORY",
        registrations=[repository.artifact_registration(published, run_id)],
    )
    with repository.database.read() as connection:
        rows = connection.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_id=?", (published.artifact_id,)).fetchone()[0]
    assert rows == 1
    assert artifacts.read(published.relative_path, published.sha256) == b'{"ok":true}'
