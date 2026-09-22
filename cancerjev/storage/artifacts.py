from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class PublishedArtifact:
    artifact_id: str
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str
    purpose: str
    schema_version: int = 1

    def ref(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id, "sha256": self.sha256,
            "size_bytes": self.size_bytes, "media_type": self.media_type,
            "purpose": self.purpose, "schema_version": self.schema_version,
        }


class ArtifactStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    def publish(self, relative_path: str, content: bytes, media_type: str, purpose: str) -> PublishedArtifact:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(content).hexdigest()
        if target.exists():
            existing = target.read_bytes()
            if hashlib.sha256(existing).hexdigest() != digest:
                raise FileExistsError(f"immutable artifact collision: {relative_path}")
        else:
            descriptor, temporary = tempfile.mkstemp(prefix=".publish-", dir=target.parent)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return PublishedArtifact(str(uuid4()), relative_path.replace("\\", "/"), digest, len(content), media_type, purpose)

    def read(self, relative_path: str, expected_hash: str | None = None) -> bytes:
        content = self._resolve(relative_path).read_bytes()
        if expected_hash and hashlib.sha256(content).hexdigest() != expected_hash:
            raise OSError("artifact checksum mismatch")
        return content

    def _resolve(self, relative_path: str) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise ValueError("artifact path must be relative")
        resolved = (self.data_dir / raw).resolve()
        if not resolved.is_relative_to(self.data_dir):
            raise ValueError("artifact path escapes data directory")
        return resolved

