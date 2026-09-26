"""Read-only storage doctor: report integrity problems, never repair evidence.

The doctor distinguishes authoritative evidence (registered artifacts, run events
and scientific tables) from disposable operational files (temporary files). It
only reads: the single justified maintenance operation is ``prune_stale_temp``,
which deletes recognized stale temporary files and nothing else. Canonical
scientific outputs are never deleted or rewritten by either operation.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cancerjev.config import Settings
from cancerjev.storage.database import MIGRATIONS, SCHEMA_VERSION, Database
from cancerjev.storage.ownership import OwnershipError, ResearchOwnership
from cancerjev.storage.repositories import Repository

DOCTOR_VERSION = "storage-doctor-v1"
TEMP_ARTIFACT_MAX_AGE_SECONDS = 24 * 3600
STALE_HEARTBEAT_SECONDS = 300
MIN_FREE_DISK_BYTES = 512 * 1024 * 1024
UNREGISTERED_REPORT_LIMIT = 20

TEMP_SUFFIXES = (".tmp", ".partial")
DECLARED_OPERATIONAL_PREFIXES = ("cancerjev.db", "gdc-contract-captures-")
DECLARED_OPERATIONAL_FILES = ("research.lock",)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    detail: str
    path: str | None = None

    def payload(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "detail": self.detail,
                "path": self.path}


@dataclass(frozen=True)
class DoctorReport:
    findings: tuple[Finding, ...]
    counts: dict[str, int]
    schema_version: int | None
    expected_schema_version: int
    data_dir: str

    def ok(self) -> bool:
        return not any(finding.severity == "ERROR" for finding in self.findings)

    def payload(self) -> dict[str, Any]:
        return {
            "version": DOCTOR_VERSION,
            "ok": self.ok(),
            "data_dir": self.data_dir,
            "schema_version": self.schema_version,
            "expected_schema_version": self.expected_schema_version,
            "counts": dict(sorted(self.counts.items())),
            "findings": [finding.payload() for finding in self.findings],
        }


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _registered_paths(repository: Repository) -> dict[str, dict[str, Any]]:
    return {str(row["relative_path"]): row for row in repository.all_artifacts()}


def _is_declared_operational(relative: str) -> bool:
    name = Path(relative).name
    if relative in DECLARED_OPERATIONAL_FILES or name in DECLARED_OPERATIONAL_FILES:
        return True
    return any(part.startswith(DECLARED_OPERATIONAL_PREFIXES) for part in Path(relative).parts)


def run_doctor(settings: Settings) -> DoctorReport:
    """Read-only integrity report over one data directory."""
    findings: list[Finding] = []
    database = Database(settings.database_path)
    schema_version: int | None = None
    if settings.database_path.is_file():
        schema_version = database._probe_version()
        if schema_version is not None and schema_version > SCHEMA_VERSION:
            findings.append(Finding(
                "SCHEMA_INCOMPATIBLE", "ERROR",
                f"database schema {schema_version} is newer than this build's {SCHEMA_VERSION}"))
        elif schema_version is not None and schema_version < SCHEMA_VERSION \
                and schema_version not in MIGRATIONS:
            findings.append(Finding(
                "SCHEMA_INCOMPATIBLE", "ERROR",
                f"database schema {schema_version} has no declared migration path to "
                f"{SCHEMA_VERSION}"))
    else:
        findings.append(Finding("DATABASE_MISSING", "ERROR",
                                f"database {settings.database_path} does not exist"))

    repository = Repository(database)
    registered = _registered_paths(repository)

    for relative, row in sorted(registered.items()):
        target = settings.data_dir / relative
        if not target.is_file():
            findings.append(Finding("ARTIFACT_MISSING", "ERROR",
                                    f"registered artifact {row['artifact_id']} is missing on disk",
                                    relative))
            continue
        actual = _digest_file(target)
        if actual != row["sha256"]:
            findings.append(Finding(
                "ARTIFACT_HASH_MISMATCH", "ERROR",
                f"registered artifact {row['artifact_id']} content hash differs from its record",
                relative))

    if settings.data_dir.is_dir():
        now = time.time()
        orphaned: list[str] = []
        stale_temp: list[str] = []
        for candidate in sorted(settings.data_dir.rglob("*")):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(settings.data_dir).as_posix()
            if relative in registered:
                continue
            if candidate.suffix in TEMP_SUFFIXES:
                if now - candidate.stat().st_mtime > TEMP_ARTIFACT_MAX_AGE_SECONDS:
                    stale_temp.append(relative)
                continue
            if _is_declared_operational(relative):
                continue
            orphaned.append(relative)
        if orphaned:
            findings.append(Finding(
                "ARTIFACT_UNREGISTERED", "WARNING",
                f"{len(orphaned)} file(s) on disk have no artifact registration: "
                f"{', '.join(orphaned[:UNREGISTERED_REPORT_LIMIT])}"
                + (" ..." if len(orphaned) > UNREGISTERED_REPORT_LIMIT else ""),
                orphaned[0]))
        for relative in stale_temp:
            findings.append(Finding(
                "TEMP_ARTIFACT_STALE", "WARNING",
                f"temporary file is older than {TEMP_ARTIFACT_MAX_AGE_SECONDS}s", relative))

        free = shutil.disk_usage(settings.data_dir).free
        if free < MIN_FREE_DISK_BYTES:
            findings.append(Finding(
                "DISK_SPACE_LOW", "WARNING",
                f"only {free} free bytes remain (declared minimum {MIN_FREE_DISK_BYTES})"))

    if settings.lock_path.exists():
        try:
            with ResearchOwnership(settings.lock_path):
                findings.append(Finding(
                    "OWNERSHIP_LOCK_STALE", "WARNING",
                    "research.lock exists but no process currently holds it"))
        except OwnershipError:
            pass

    worker = None
    if schema_version is not None and schema_version <= SCHEMA_VERSION:
        with database.read() as connection:
            row = connection.execute("SELECT * FROM worker_status WHERE singleton=1").fetchone()
            worker = dict(row) if row else None
    if worker is not None and worker.get("heartbeat_at"):
        beat = datetime.fromisoformat(str(worker["heartbeat_at"]).replace("Z", "+00:00"))
        age = (datetime.now(UTC) - beat).total_seconds()
        if age > STALE_HEARTBEAT_SECONDS:
            findings.append(Finding(
                "WORKER_HEARTBEAT_STALE", "WARNING",
                f"worker {worker.get('owner_id')} last heartbeated {int(age)}s ago"))

    counts = dict(Counter(finding.code for finding in findings))
    return DoctorReport(tuple(findings), counts, schema_version, SCHEMA_VERSION,
                        str(settings.data_dir))


def prune_stale_temp_artifacts(
        settings: Settings, *,
        max_age_seconds: int = TEMP_ARTIFACT_MAX_AGE_SECONDS) -> tuple[str, ...]:
    """Delete only stale temporary files; never a registered artifact or evidence."""
    repository = Repository(Database(settings.database_path))
    registered = _registered_paths(repository)
    removed: list[str] = []
    now = time.time()
    if not settings.data_dir.is_dir():
        return ()
    with ResearchOwnership(settings.lock_path):
        for candidate in sorted(settings.data_dir.rglob("*")):
            if not candidate.is_file() or candidate.suffix not in TEMP_SUFFIXES:
                continue
            relative = candidate.relative_to(settings.data_dir).as_posix()
            if relative in registered:
                continue
            if now - candidate.stat().st_mtime <= max_age_seconds:
                continue
            candidate.unlink()
            removed.append(relative)
    return tuple(removed)
