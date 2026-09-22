from __future__ import annotations

import http.client
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from cancerjev.gdc.transport import BudgetCaps, GDCTransport, RunBudget


@dataclass
class RecordedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class LoopbackServer:
    responses: dict[str, Callable[[RecordedRequest], tuple[int, dict[str, str], bytes]]] = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)
    _server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    def start(self) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                recorded = RecordedRequest(
                    method=self.command,
                    path=self.path,
                    headers={key.lower(): value for key, value in self.headers.items()},
                    body=body,
                )
                outer.requests.append(recorded)
                responder = outer.responses.get(self.path.split("?")[0])
                if responder is None:
                    status, headers, payload = 404, {"Content-Type": "application/json"}, b'{"message":"not found"}'
                else:
                    status, headers, payload = responder(recorded)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                chunked = headers.get("Transfer-Encoding", "").lower() == "chunked"
                if "Content-Length" not in headers and not chunked:
                    self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if chunked:
                    for index in range(0, len(payload), 4096):
                        chunk = payload[index:index + 4096]
                        self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                else:
                    self.wfile.write(payload)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.server_address[1]

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def json(self, path: str, payload: bytes, status: int = 200) -> None:
        self.responses[path] = lambda request: (status, {"Content-Type": "application/json"}, payload)

    def raw(self, path: str, responder: Callable[[RecordedRequest], tuple[int, dict[str, str], bytes]]) -> None:
        self.responses[path] = responder


@pytest.fixture
def loopback():
    server = LoopbackServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def transport_builder(runtime, loopback):
    settings, repository, artifacts = runtime

    def build(*, caps: BudgetCaps | None = None, cache_enabled: bool = True,
              emit: Callable[..., Any] | None = None) -> GDCTransport:
        effective = caps or BudgetCaps(max_requests=50, max_bytes=1_000_000)
        budget = RunBudget(caps=effective)
        run_id = repository.create_run("transport-test")
        return GDCTransport(
            repository, artifacts, budget, run_id,
            emit or (lambda *args, **kwargs: None),
            cache_enabled=cache_enabled,
            host="127.0.0.1",
            connection_factory=lambda: http.client.HTTPConnection(
                "127.0.0.1", loopback.port, timeout=effective.timeout_seconds,
            ),
        )

    return build
