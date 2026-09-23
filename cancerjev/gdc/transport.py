"""The only module allowed to open a network connection to GDC.

Open-access only: the transport has no credential parameter and never constructs
an ``Authorization`` or ``X-Auth-Token`` header. Host, paths and methods are
allowlisted; redirects are refused; every response is bounded and retained.
"""

from __future__ import annotations

import http.client
import ssl
import threading
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.gdc.endpoints import ENDPOINTS, EndpointSpec, GDCRequest
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.repositories import Repository

GDC_HOST = "api.gdc.cancer.gov"
GDC_USER_AGENT = "CancerJEV/0.2 (public open-access research; anonymous)"
TRANSPORT_CONTRACT_VERSION = "gdc-transport-v1"

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class TransportErrorCode(StrEnum):
    UNSUPPORTED_ENDPOINT = "UNSUPPORTED_ENDPOINT"
    UNSUPPORTED_METHOD = "UNSUPPORTED_METHOD"
    INVALID_REQUEST = "INVALID_REQUEST"
    REDIRECT_REFUSED = "REDIRECT_REFUSED"
    UNAVAILABLE_ACCESS = "UNAVAILABLE_ACCESS"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_CONTENT_ENCODING = "INVALID_CONTENT_ENCODING"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    RESPONSE_TRUNCATED = "RESPONSE_TRUNCATED"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT = "TIMEOUT"
    REQUEST_BUDGET_EXHAUSTED = "REQUEST_BUDGET_EXHAUSTED"
    BYTE_BUDGET_EXHAUSTED = "BYTE_BUDGET_EXHAUSTED"
    PAGE_BUDGET_EXHAUSTED = "PAGE_BUDGET_EXHAUSTED"


class TransportError(Exception):
    def __init__(self, code: TransportErrorCode, detail: str, *, http_status: int | None = None,
                 retryable: bool = False, bytes_read: int = 0) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.http_status = http_status
        self.retryable = retryable
        self.bytes_read = bytes_read


@dataclass(frozen=True)
class BudgetCaps:
    max_requests: int = 150
    max_bytes: int = 64 * 1024 * 1024
    per_response_bytes: int = 5 * 1024 * 1024
    max_pages_per_query: int = 10
    max_case_ids: int = 250
    max_gene_ids: int = 100
    max_retries: int = 2
    timeout_seconds: float = 30.0


@dataclass
class RunBudget:
    caps: BudgetCaps = field(default_factory=BudgetCaps)
    requests_started: int = 0
    bytes_read: int = 0
    pages_by_query: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reserve(self, request: GDCRequest) -> None:
        with self._lock:
            if self.requests_started + 1 > self.caps.max_requests:
                raise TransportError(
                    TransportErrorCode.REQUEST_BUDGET_EXHAUSTED,
                    f"request cap {self.caps.max_requests} reached",
                )
            if request.page > self.caps.max_pages_per_query:
                raise TransportError(
                    TransportErrorCode.PAGE_BUDGET_EXHAUSTED,
                    f"page {request.page} exceeds page cap {self.caps.max_pages_per_query} "
                    f"for {request.logical_query_id}",
                )
            self.pages_by_query[request.logical_query_id] = max(
                self.pages_by_query.get(request.logical_query_id, 0), request.page,
            )
            if self.bytes_read >= self.caps.max_bytes:
                raise TransportError(
                    TransportErrorCode.BYTE_BUDGET_EXHAUSTED,
                    f"byte cap {self.caps.max_bytes} already reached",
                )
            self.requests_started += 1

    def charge(self, count: int) -> None:
        with self._lock:
            self.bytes_read += max(0, count)

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.caps.max_bytes - self.bytes_read)


@dataclass(frozen=True)
class GDCResponse:
    request_hash: str
    endpoint: str
    method: str
    http_status: int
    headers: dict[str, str]
    body: bytes
    body_sha256: str
    artifact: PublishedArtifact
    completeness: str
    from_cache: bool
    retrieved_at: str
    latency_ms: int
    request_id: str = ""
    attempt_no: int = 0


class GDCTransport:
    def __init__(
        self,
        repository: Repository,
        artifacts: ArtifactStore,
        budget: RunBudget,
        run_id: str,
        emit: Callable[..., Any],
        *,
        cache_enabled: bool = True,
        host: str = GDC_HOST,
        port: int = 443,
        connection_factory: Callable[[], http.client.HTTPConnection] | None = None,
    ) -> None:
        if host != GDC_HOST and host not in {"127.0.0.1", "localhost"}:
            raise TransportError(TransportErrorCode.UNSUPPORTED_ENDPOINT, f"host not allowed: {host}")
        if connection_factory is not None and host == GDC_HOST:
            raise TransportError(
                TransportErrorCode.UNSUPPORTED_ENDPOINT,
                "a connection factory may only target a loopback test server",
            )
        self.repository = repository
        self.artifacts = artifacts
        self.budget = budget
        self.run_id = run_id
        self.emit = emit
        self.cache_enabled = cache_enabled
        self.host = host
        self.port = port
        self.connection_factory = connection_factory

    def request(self, request: GDCRequest) -> GDCResponse:
        spec = request.endpoint
        if ENDPOINTS.get((spec.method, spec.path)) is not spec:
            raise TransportError(
                TransportErrorCode.UNSUPPORTED_ENDPOINT,
                f"endpoint not allowlisted: {spec.method} {spec.path}",
            )
        if request.body is not None:
            canonical_json(request.body)
        request_hash = request.request_hash()
        if self.cache_enabled:
            cached = self._cache_get(request_hash, spec, request.logical_query_id)
            if cached is not None:
                return cached
        return self._dispatch_with_retries(spec, request, request_hash)

    # ---------------------------------------------------------------- cache

    def _cache_get(self, request_hash: str, spec: EndpointSpec,
                   logical_query_id: str) -> GDCResponse | None:
        row = self.repository.gdc_cache_get(request_hash, TRANSPORT_CONTRACT_VERSION)
        if row is None:
            return None
        if row.get("completeness") != "COMPLETE":
            return None
        if row.get("contract_version") != TRANSPORT_CONTRACT_VERSION:
            return None
        cached_size = int(row.get("size_bytes") or 0)
        if cached_size > self.budget.caps.per_response_bytes:
            return None
        metadata = self.repository.artifact(row["response_artifact_id"])
        if metadata is None:
            return None
        try:
            body = self.artifacts.read(metadata["relative_path"], row["response_hash"])
        except (OSError, ValueError):
            return None
        if len(body) != cached_size:
            return None
        request_id = str(uuid4())
        now = utc_now()
        self.repository.gdc_attempt_start(
            request_id=request_id, run_id=self.run_id, logical_query_id=logical_query_id,
            attempt_no=1, method=spec.method, endpoint=spec.path, request_hash=request_hash,
            reserved_bytes=0, started_at=now,
        )
        self.repository.gdc_attempt_finish(
            request_id=request_id, status="CACHE_HIT", bytes_read=0, http_status=None,
            response_artifact_id=row["response_artifact_id"], response_hash=row["response_hash"],
            completeness=row["completeness"], error=None, finished_at=now,
        )
        self.emit(
            "GDC_CACHE_HIT", f"gdc-cache:{request_hash}", f"GDC cache hit for {spec.path}.",
            stage=None, data={
                "request_id": request_id, "request_hash": request_hash, "endpoint": spec.path,
                "response_artifact_id": row["response_artifact_id"], "response_sha256": row["response_hash"],
                "body_bytes": len(body), "cache": True,
            },
            artifact_refs=[{
                "artifact_id": row["response_artifact_id"], "sha256": row["response_hash"],
                "size_bytes": len(body), "media_type": metadata["media_type"],
                "purpose": metadata["purpose"], "schema_version": metadata["schema_version"],
            }],
        )
        return GDCResponse(
            request_hash=request_hash, endpoint=spec.path, method=spec.method, http_status=200,
            headers={}, body=body, body_sha256=row["response_hash"],
            artifact=PublishedArtifact(
                artifact_id=row["response_artifact_id"], relative_path=metadata["relative_path"],
                sha256=row["response_hash"], size_bytes=len(body),
                media_type=metadata["media_type"], purpose=metadata["purpose"],
            ),
            completeness=row["completeness"], from_cache=True, retrieved_at=now, latency_ms=0,
            request_id=request_id, attempt_no=1,
        )

    # ------------------------------------------------------------- dispatch

    def _dispatch_with_retries(self, spec: EndpointSpec, request: GDCRequest, request_hash: str) -> GDCResponse:
        attempt_no = 0
        while True:
            attempt_no += 1
            try:
                return self._attempt(spec, request, request_hash, attempt_no)
            except TransportError as exc:
                if exc.retryable and spec.retryable and attempt_no <= self.budget.caps.max_retries:
                    time.sleep(0.5 * attempt_no)
                    continue
                raise

    def _attempt(self, spec: EndpointSpec, request: GDCRequest, request_hash: str, attempt_no: int) -> GDCResponse:
        self.budget.reserve(request)
        request_id = str(uuid4())
        started_at = utc_now()
        self.repository.gdc_attempt_start(
            request_id=request_id, run_id=self.run_id, logical_query_id=request.logical_query_id,
            attempt_no=attempt_no, method=spec.method, endpoint=spec.path,
            request_hash=request_hash, reserved_bytes=self.budget.caps.per_response_bytes,
            started_at=started_at,
        )
        self.emit(
            "GDC_REQUEST_STARTED", f"gdc:{request_id}:started",
            f"GDC {spec.method} {spec.path} started (attempt {attempt_no}).",
            stage=None, data={
                "request_id": request_id, "logical_query_id": request.logical_query_id,
                "endpoint": spec.path, "method": spec.method, "attempt_no": attempt_no,
                "request_hash": request_hash, "reserved_bytes": self.budget.caps.per_response_bytes,
                "cache": False,
            },
        )
        started = time.monotonic()
        try:
            status, headers, body = self._perform(spec, request)
        except TransportError as exc:
            self.budget.charge(exc.bytes_read)
            latency = int((time.monotonic() - started) * 1000)
            self.repository.gdc_attempt_finish(
                request_id=request_id, status="FAILED", bytes_read=exc.bytes_read,
                http_status=exc.http_status, response_artifact_id=None, response_hash=None,
                completeness="FAILED", error=str(exc), finished_at=utc_now(),
            )
            self.emit(
                "GDC_REQUEST_FAILED", f"gdc:{request_id}:failed",
                f"GDC {spec.method} {spec.path} failed: {exc.code}.",
                stage=None, level="error", data={
                    "request_id": request_id, "endpoint": spec.path, "method": spec.method,
                    "attempt_no": attempt_no, "error_code": str(exc.code), "detail": exc.detail,
                    "http_status": exc.http_status, "bytes_read": exc.bytes_read,
                    "latency_ms": latency,
                    "requests_total": self.budget.requests_started,
                    "bytes_total": self.budget.bytes_read,
                },
            )
            raise
        except Exception as exc:
            self.repository.gdc_attempt_finish(
                request_id=request_id, status="FAILED", bytes_read=0, http_status=None,
                response_artifact_id=None, response_hash=None, completeness="FAILED",
                error=f"{type(exc).__name__}: {exc}", finished_at=utc_now(),
            )
            raise
        latency = int((time.monotonic() - started) * 1000)
        body_sha = _sha256(body)
        artifact: PublishedArtifact | None = None
        try:
            artifact = self.artifacts.publish(
                f"gdc/{request_hash}/{body_sha}.body", body,
                "application/json" if request.accept == "application/json" else "text/tab-separated-values",
                "gdc-response",
            )
            self.budget.charge(len(body))
            self.repository.register_artifact(artifact, self.run_id)
        except Exception as exc:
            self._finalize_unstored_response(
                request_id=request_id, spec=spec, attempt_no=attempt_no, http_status=status,
                bytes_read=len(body), response_hash=body_sha, artifact=artifact,
                latency_ms=latency, exc=exc,
            )
            raise
        self.repository.gdc_attempt_finish(
            request_id=request_id, status="COMPLETED", bytes_read=len(body), http_status=status,
            response_artifact_id=artifact.artifact_id, response_hash=body_sha,
            completeness="COMPLETE", error=None, finished_at=utc_now(),
        )
        self.repository.gdc_cache_put(
            request_hash=request_hash, method=spec.method, endpoint=spec.path,
            response_artifact_id=artifact.artifact_id, response_hash=body_sha,
            size_bytes=len(body), completeness="COMPLETE",
            contract_version=TRANSPORT_CONTRACT_VERSION, created_at=utc_now(),
        )
        self.emit(
            "GDC_REQUEST_COMPLETED", f"gdc:{request_id}:completed",
            f"GDC {spec.method} {spec.path} completed with {len(body)} bytes.",
            stage=None, data={
                "request_id": request_id, "endpoint": spec.path, "method": spec.method,
                "attempt_no": attempt_no, "http_status": status, "bytes_read": len(body),
                "response_artifact_id": artifact.artifact_id, "response_sha256": body_sha,
                "latency_ms": latency, "requests_total": self.budget.requests_started,
                "bytes_total": self.budget.bytes_read, "cache": False,
            },
            artifact_refs=[artifact.ref()],
        )
        return GDCResponse(
            request_hash=request_hash, endpoint=spec.path, method=spec.method, http_status=status,
            headers=headers, body=body, body_sha256=body_sha, artifact=artifact,
            completeness="COMPLETE", from_cache=False, retrieved_at=started_at, latency_ms=latency,
            request_id=request_id, attempt_no=attempt_no,
        )

    def _finalize_unstored_response(self, *, request_id: str, spec: EndpointSpec, attempt_no: int,
                                    http_status: int, bytes_read: int, response_hash: str,
                                    artifact: PublishedArtifact | None, latency_ms: int,
                                    exc: Exception) -> None:
        """Make an attempt terminal when its received body could not be stored.

        The ledger write happens first, so an attempt can never remain RESERVED
        after a successful read. Emitting the failure event is best effort: the
        original storage error is re-raised by the caller and must not be replaced
        by a second storage failure during failure reporting.
        """
        self.repository.gdc_attempt_finish(
            request_id=request_id, status="FAILED", bytes_read=bytes_read, http_status=http_status,
            response_artifact_id=artifact.artifact_id if artifact is not None else None,
            response_hash=response_hash, completeness="FAILED",
            error=f"RESPONSE_STORAGE_FAILED: {type(exc).__name__}: {exc}", finished_at=utc_now(),
        )
        try:
            self.emit(
                "GDC_REQUEST_FAILED", f"gdc:{request_id}:failed",
                f"GDC {spec.method} {spec.path} response could not be stored.",
                stage=None, level="error", data={
                    "request_id": request_id, "endpoint": spec.path, "method": spec.method,
                    "attempt_no": attempt_no, "error_code": "RESPONSE_STORAGE_FAILED",
                    "detail": f"{type(exc).__name__}: {exc}", "http_status": http_status,
                    "bytes_read": bytes_read, "latency_ms": latency_ms,
                    "requests_total": self.budget.requests_started,
                    "bytes_total": self.budget.bytes_read,
                },
            )
        except Exception:
            return

    def _connection(self) -> http.client.HTTPConnection:
        if self.connection_factory is not None:
            return self.connection_factory()
        return http.client.HTTPSConnection(
            self.host, self.port, timeout=self.budget.caps.timeout_seconds,
            context=ssl.create_default_context(),
        )

    def _perform(self, spec: EndpointSpec, request: GDCRequest) -> tuple[int, dict[str, str], bytes]:
        url = spec.path
        if request.params:
            url = f"{url}?{urllib.parse.urlencode(sorted(request.params))}"
        payload: bytes | None = None
        headers = {
            "Accept": request.accept,
            "Accept-Encoding": "identity",
            "User-Agent": GDC_USER_AGENT,
        }
        if request.body is not None:
            payload = canonical_json(request.body)
            headers["Content-Type"] = "application/json"
        connection = self._connection()
        bytes_read = 0
        try:
            connection.request(spec.method, url, body=payload, headers=headers)
            response = connection.getresponse()
            status = response.status
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if 300 <= status < 400:
                raise TransportError(
                    TransportErrorCode.REDIRECT_REFUSED,
                    f"redirect to {response_headers.get('location', 'unknown')} refused",
                    http_status=status,
                )
            if status in (401, 403):
                raise TransportError(
                    TransportErrorCode.UNAVAILABLE_ACCESS,
                    f"HTTP {status}: anonymous access unavailable; no credential lookup is performed",
                    http_status=status,
                )
            if status != 200:
                detail = f"HTTP {status}"
                error_bytes = 0
                if status in (400, 404, 405, 422):
                    error_allowance = min(
                        self.budget.caps.per_response_bytes, self.budget.remaining_bytes,
                    )
                    error_limit = max(0, min(65536, error_allowance))
                    try:
                        error_body = response.read(error_limit) if error_limit else b""
                    except (OSError, http.client.HTTPException):
                        error_body = b""
                    error_bytes = len(error_body)
                    if error_body:
                        detail = f"HTTP {status}: {error_body.decode('utf-8', 'replace')[:2000]}"
                raise TransportError(
                    TransportErrorCode.PROVIDER_ERROR, detail,
                    http_status=status, retryable=status in RETRYABLE_STATUSES, bytes_read=error_bytes,
                )
            encoding = response_headers.get("content-encoding", "").lower()
            if encoding not in ("", "identity"):
                raise TransportError(
                    TransportErrorCode.INVALID_CONTENT_ENCODING,
                    f"unexpected content-encoding {encoding}",
                )
            declared = response_headers.get("content-length")
            if declared is not None:
                try:
                    declared_n = int(declared)
                except ValueError as exc:
                    raise TransportError(TransportErrorCode.PROVIDER_ERROR, "invalid content-length") from exc
                if declared_n > self.budget.caps.per_response_bytes:
                    raise TransportError(
                        TransportErrorCode.RESPONSE_TOO_LARGE,
                        f"declared {declared_n} exceeds per-response cap {self.budget.caps.per_response_bytes}",
                    )
            allowance = min(self.budget.caps.per_response_bytes, self.budget.remaining_bytes)
            if allowance <= 0:
                raise TransportError(
                    TransportErrorCode.BYTE_BUDGET_EXHAUSTED,
                    f"run byte cap {self.budget.caps.max_bytes} reached",
                )
            chunks: list[bytes] = []
            while bytes_read < allowance:
                chunk = response.read(min(65536, allowance - bytes_read))
                if not chunk:
                    break
                chunks.append(chunk)
                bytes_read += len(chunk)
            body = b"".join(chunks)
            if bytes_read >= allowance:
                probe = response.read(1)
                if probe:
                    bytes_read += len(probe)
                    raise TransportError(
                        TransportErrorCode.RESPONSE_TRUNCATED,
                        f"response exceeds cap {allowance}",
                        bytes_read=bytes_read,
                    )
            return status, response_headers, body
        except TransportError as exc:
            if exc.bytes_read == 0 and bytes_read:
                exc.bytes_read = bytes_read
            raise
        except TimeoutError as exc:
            raise TransportError(TransportErrorCode.TIMEOUT, str(exc) or "timeout", retryable=True,
                                 bytes_read=bytes_read) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise TransportError(TransportErrorCode.CONNECTION_ERROR, f"{type(exc).__name__}: {exc}",
                                 retryable=True, bytes_read=bytes_read) from exc
        finally:
            connection.close()


def _sha256(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()
