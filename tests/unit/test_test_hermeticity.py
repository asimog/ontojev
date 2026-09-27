"""Guard: the default offline test suite stays hermetic.

A clean checkout must be able to run the collected suite without any ignored
developer runtime artifact under ``data/runs``. Only explicitly opt-in live
modules may read local runtime data. The autouse network guard (``tests/conftest.py``)
must also block the raw socket APIs and undeclared subprocesses, because either
would bypass the guarded ``socket.create_connection`` path.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[1]
NON_COLLECTED_MODULES = {"capture_reconciliation.py", "test_test_hermeticity.py"}
EXEMPT_DIRECTORIES = {"live"}
RUNTIME_DATA_PATTERNS = ('"data" / "runs"', "'data' / 'runs'", "data/runs", "data\\runs")


def test_no_collected_test_reads_ignored_runtime_data():
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        relative = path.relative_to(TESTS_ROOT)
        if path.name in NON_COLLECTED_MODULES or EXEMPT_DIRECTORIES & set(relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in RUNTIME_DATA_PATTERNS):
            offenders.append(str(relative))
    assert offenders == [], (
        "collected tests must not read ignored developer runtime data under data/runs: "
        f"{offenders}"
    )


def test_guard_blocks_create_connection_to_a_public_host():
    with pytest.raises(AssertionError, match="Outbound network is forbidden"):
        socket.create_connection(("example.com", 80), timeout=0.1)


def test_guard_blocks_raw_socket_connect_to_a_public_host():
    with pytest.raises(AssertionError, match="Outbound network is forbidden"):
        probe = socket.socket()
        try:
            probe.connect(("198.51.100.1", 80))  # TEST-NET-2, never routable
        finally:
            probe.close()


def test_guard_blocks_raw_connect_ex_to_a_public_host():
    with pytest.raises(AssertionError, match="Outbound network is forbidden"):
        probe = socket.socket()
        try:
            probe.connect_ex(("198.51.100.1", 80))
        finally:
            probe.close()


def test_guard_allows_loopback_connections():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        host, port = listener.getsockname()
        with socket.create_connection((host, port), timeout=1.0) as client:
            accepted, _ = listener.accept()
            accepted.close()
            assert client.getpeername()[1] == port
    finally:
        listener.close()


def test_guard_blocks_an_undeclared_subprocess():
    with pytest.raises(AssertionError, match="Subprocesses are forbidden"):
        subprocess.run([sys.executable, "-c", "print('escaped')"], check=False)


@pytest.mark.local_process
def test_guard_allows_a_declared_local_process():
    completed = subprocess.run([sys.executable, "-c", "print('local ok')"],
                               capture_output=True, text=True, check=True, timeout=60)
    assert completed.stdout.strip() == "local ok"
