"""Adversarial open-access tests: authentication must be impossible, not optional."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from cancerjev.gdc.endpoints import files_expression_request

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_HEADER_NAMES = {"authorization", "x-auth-token", "proxy-authorization"}
FORBIDDEN_ENV_PATTERN = ("GDC_TOKEN", "X_AUTH_TOKEN", "GDC_AUTH", "GDC_API_KEY")
# The GDC boundary must never authenticate. Exactly one module may carry a provider authorization
# header: the opt-in OpenRouter hypothesis adapter, which is injected by the caller, reads its
# credential from the environment, persists nothing and produces text that is never evidence.
# Any other offender still fails, so authentication cannot spread beyond this single seam.
PROVIDER_AUTH_ALLOWLIST = {"openrouter.py"}


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


def test_only_the_opt_in_provider_module_may_authenticate():
    authenticated = [
        path.name for path in (REPO_ROOT / "cancerjev").rglob("*.py")
        if any(value.strip().lower() in FORBIDDEN_HEADER_NAMES for value in _string_constants(path))
    ]
    assert sorted(authenticated) == sorted(PROVIDER_AUTH_ALLOWLIST), (
        "a provider authorization header may exist only in the allow-listed adapter"
    )
    gdc_modules = [path.name for path in (REPO_ROOT / "cancerjev" / "gdc").rglob("*.py")
                   if any(value.strip().lower() in FORBIDDEN_HEADER_NAMES
                          for value in _string_constants(path))]
    assert gdc_modules == [], "the GDC boundary must stay anonymous"


def test_no_gdc_credential_environment_variable_is_read():
    offenders: list[str] = []
    for path in list((REPO_ROOT / "cancerjev").rglob("*.py")) + list((REPO_ROOT / "apps").rglob("*.py")):
        for name in _env_reads(path):
            if any(pattern in name.upper() for pattern in FORBIDDEN_ENV_PATTERN):
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"GDC credential env reads found: {offenders}"


def test_file_metadata_requests_always_require_open_access():
    request = files_expression_request("TCGA-BRCA")
    filters = json.loads(dict(request.params)["filters"])
    access_filters = [
        item for item in filters["content"]
        if item.get("content", {}).get("field") == "access"
    ]
    assert access_filters == [{"op": "in", "content": {"field": "access", "value": ["open"]}}]
