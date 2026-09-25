"""Retained provider bodies must survive checkout without newline conversion."""

import hashlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "gdc"


@pytest.mark.parametrize("body", sorted(FIXTURES.glob("*.body")), ids=lambda path: path.stem)
def test_retained_capture_bytes_match_recorded_digest(body):
    metadata = json.loads(body.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(body.read_bytes()).hexdigest() == metadata["body_sha256"]
