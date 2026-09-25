"""Opt-in live Jev evaluation. Disabled by default: run with `pytest -m live_jev`.

Requires TYPESAFE_API_KEY in the environment. Evaluates exactly one typed state
produced by the offline replay pipeline with the pinned model and records real usage.
"""

from __future__ import annotations

import os

import pytest

from cancerjev.config import load_local_env
from cancerjev.jev.questions import WIDE_QUESTIONS
from cancerjev.jev.service import JevService
from tests.integration.test_live_replay import _live_state_records


@pytest.mark.live_jev
def test_real_jev_evaluation_of_one_state(runtime, monkeypatch):
    load_local_env()
    if not os.getenv("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY is not set")
    settings, repository, artifacts = runtime
    run_id, _, records = _live_state_records(runtime, monkeypatch)
    service = JevService(settings, repository, artifacts)
    evaluation = service.evaluate_record(run_id=run_id, state=records[0],
                                         emit=lambda *args, **kwargs: None)
    assert evaluation.error_code is None
    vector = evaluation.boundary_representation()
    assert vector["resolved_model"] == settings.jev_model
    assert set(vector["answers"]) == {definition.question_id for definition in WIDE_QUESTIONS}
    assert vector["usage"]["input_tokens"] and vector["usage"]["input_tokens"] > 0
    assert vector["latency_ms"] and vector["latency_ms"] > 0
    assert vector["cache_source_evaluation_id"] is None
