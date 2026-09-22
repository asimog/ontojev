"""Adversarial open-access tests: authentication must be impossible, not optional."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cancerjev.gdc.endpoints import (
    FORBIDDEN_PATHS,
    EndpointError,
    files_expression_request,
    resolve_endpoint,
    status_request,
)
from cancerjev.gdc.parsers import ResponseMeta, parse_files_provenance
from cancerjev.gdc.transport import BudgetCaps, TransportError, TransportErrorCode

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_HEADER_NAMES = {"authorization", "x-auth-token", "proxy-authorization"}
FORBIDDEN_ENV_PATTERN = ("GDC_TOKEN", "X_AUTH_TOKEN", "GDC_AUTH", "GDC_API_KEY")


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


def _env_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            target = None
            if isinstance(node.func, ast.Attribute):
                target = node.func.attr
            if target in {"getenv", "get"}:
                value = node.args[0].value
                if isinstance(value, str):
                    names.append(value)
    return names


def test_no_source_file_uses_an_authentication_header_literal():
    offenders: list[str] = []
    for path in (REPO_ROOT / "cancerjev").rglob("*.py"):
        for value in _string_constants(path):
            if value.strip().lower() in FORBIDDEN_HEADER_NAMES:
                offenders.append(f"{path.name}: {value!r}")
    assert offenders == [], f"authentication header literals found: {offenders}"


def test_no_gdc_credential_environment_variable_is_read():
    offenders: list[str] = []
    for path in list((REPO_ROOT / "cancerjev").rglob("*.py")) + list((REPO_ROOT / "apps").rglob("*.py")):
        for name in _env_reads(path):
            if any(pattern in name.upper() for pattern in FORBIDDEN_ENV_PATTERN):
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"GDC credential env reads found: {offenders}"


def test_settings_expose_no_credential_fields(runtime):
    settings, _, _ = runtime
    fields = set(vars(settings).keys())
    assert not {field for field in fields if "token" in field.lower() or "credential" in field.lower()}


def test_forbidden_paths_are_not_routable():
    for path in ("/data", "/manifest", "/slicing"):
        assert path in FORBIDDEN_PATHS
        with pytest.raises(EndpointError):
            resolve_endpoint("GET", path)
        with pytest.raises(EndpointError):
            resolve_endpoint("POST", path)


def test_file_metadata_requests_always_require_open_access():
    request = files_expression_request("TCGA-BRCA")
    filters = json.loads(dict(request.params)["filters"])
    access_filters = [
        item for item in filters["content"]
        if item.get("content", {}).get("field") == "access"
    ]
    assert access_filters == [{"op": "in", "content": {"field": "access", "value": ["open"]}}]


def test_controlled_records_are_detected_and_never_admitted():
    body = json.dumps({"data": {"hits": [
        {"file_id": "f1", "access": "open", "analysis": {"workflow_type": "STAR - Counts"}},
        {"file_id": "f2", "access": "controlled", "analysis": {"workflow_type": "STAR - Counts"}},
    ]}}).encode()
    meta = ResponseMeta(endpoint="/files", method="GET", request_hash="h", response_sha256="s",
                        artifact_id=None, retrieved_at="t", source_release=None, completeness="COMPLETE")
    provenance = parse_files_provenance(body, meta)
    assert provenance.non_open_records == 1


def test_token_environment_variables_do_not_change_transport_headers(loopback, transport_builder,
                                                                     monkeypatch):
    monkeypatch.setenv("GDC_TOKEN", "should-never-be-read")
    monkeypatch.setenv("X_AUTH_TOKEN", "should-never-be-read")
    monkeypatch.setenv("GDC_API_KEY", "should-never-be-read")
    loopback.json("/status", b'{"status":"OK"}')
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=100_000))
    transport.request(status_request())
    recorded = loopback.requests[0]
    assert "authorization" not in recorded.headers
    assert "x-auth-token" not in recorded.headers
    assert "proxy-authorization" not in recorded.headers


def test_access_failure_is_terminal_and_never_retried_with_credentials(loopback, transport_builder,
                                                                       runtime):
    _, repository, _ = runtime
    loopback.raw("/status", lambda request: (401, {"Content-Type": "application/json"}, b"{}"))
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=100_000, max_retries=3))
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert exc.value.code == TransportErrorCode.UNAVAILABLE_ACCESS
    assert len(loopback.requests) == 1
