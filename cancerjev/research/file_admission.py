"""Open-file admission gate: no GDC file is acquired without a named method consumer.

The project prohibits automatic multi-gigabyte acquisition, raw-sequencing
fallbacks and token-bearing downloads. This module is the admission surface: it
turns a would-be file product into a typed ADMITTED / DEFERRED / REJECTED
decision before any downloader exists. The declared consumer table is empty
today, so every candidate defers with NO_NAMED_CONSUMER; activation requires a
scientific unit to name a consumer method and its exact product, with a complete
open-access preflight manifest. This module performs no I/O and creates no
downloader.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cancerjev.domain.measurements import count, digest, require, text

FILE_ADMISSION_VERSION = "1"
MAX_SINGLE_PRODUCT_FILE_BYTES = 2 * 1024 * 1024 * 1024
NAMED_FILE_CONSUMERS: Mapping[str, str] = {}


class FileAccess(str, Enum):
    OPEN = "OPEN"


class AdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


GRANTED_REASON = "OPEN_FILE_ADMISSION_GRANTED"


@dataclass(frozen=True)
class FileAdmissionDecision:
    consumer_method: str | None
    product_kind: str
    project_id: str
    file_count: int | None
    total_bytes: int | None
    access: FileAccess
    status: AdmissionStatus
    reason: str

    def __post_init__(self) -> None:
        if self.consumer_method is not None:
            text(self.consumer_method, "file-admission consumer method")
        text(self.product_kind, "file-admission product kind")
        text(self.project_id, "file-admission project id")
        if self.file_count is not None:
            count(self.file_count, "file-admission file count")
        if self.total_bytes is not None:
            count(self.total_bytes, "file-admission total bytes")
        require(isinstance(self.access, FileAccess), "invalid file access")
        require(isinstance(self.status, AdmissionStatus), "invalid admission status")
        text(self.reason, "file-admission reason")
        if self.status is AdmissionStatus.ADMITTED:
            require(self.reason == GRANTED_REASON, "an admitted file product records the grant reason")
            require(self.file_count is not None and self.total_bytes is not None,
                    "an admitted file product records its preflight manifest")
        else:
            require(self.reason != GRANTED_REASON, "a non-admitted file product carries its reason")

    def payload(self) -> dict[str, Any]:
        return {
            "version": FILE_ADMISSION_VERSION,
            "consumer_method": self.consumer_method,
            "product_kind": self.product_kind,
            "project_id": self.project_id,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "access": self.access.value,
            "status": self.status.value,
            "reason": self.reason,
        }

    def decision_hash(self) -> str:
        return digest(self.payload())


def evaluate_file_admission(
    *,
    product_kind: str,
    project_id: str,
    consumer_method: str | None = None,
    file_count: int | None = None,
    total_bytes: int | None = None,
    access: FileAccess = FileAccess.OPEN,
    consumers: Mapping[str, str] | None = None,
) -> FileAdmissionDecision:
    """Typed decision for one candidate open-file product; no acquisition happens here."""
    declared = NAMED_FILE_CONSUMERS if consumers is None else consumers
    if access is not FileAccess.OPEN:
        status, reason = AdmissionStatus.REJECTED, "CONTROLLED_ACCESS_PROHIBITED"
    elif consumer_method is None or consumer_method not in declared:
        status, reason = AdmissionStatus.DEFERRED, "NO_NAMED_CONSUMER"
    elif declared[consumer_method] != product_kind:
        status, reason = AdmissionStatus.REJECTED, "PRODUCT_NOT_DECLARED_FOR_CONSUMER"
    elif file_count is None or total_bytes is None:
        status, reason = AdmissionStatus.DEFERRED, "PREFLIGHT_INCOMPLETE"
    elif total_bytes > MAX_SINGLE_PRODUCT_FILE_BYTES:
        status, reason = (AdmissionStatus.REJECTED,
                          "MULTI_GB_AUTOMATIC_ACQUISITION_PROHIBITED")
    elif file_count <= 0 or total_bytes <= 0:
        status, reason = AdmissionStatus.REJECTED, "NO_ELIGIBLE_FILES"
    else:
        status, reason = AdmissionStatus.ADMITTED, GRANTED_REASON
    return FileAdmissionDecision(
        consumer_method=consumer_method, product_kind=product_kind, project_id=project_id,
        file_count=file_count, total_bytes=total_bytes, access=access, status=status,
        reason=reason,
    )
