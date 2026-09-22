"""Opt-in live Jev evaluation. Disabled by default: run with `pytest -m live_jev`.

Requires TYPESAFE_API_KEY in the environment. Evaluates exactly one deterministic
state with the pinned model and records real usage.
"""

from __future__ import annotations

import os

import pytest

from cancerjev.jev.questions import WIDE_QUESTIONS
from cancerjev.jev.service import JevService
from tests.science.test_methods import _build, _frame


@pytest.mark.live_jev
def test_real_jev_evaluation_of_one_state(runtime):
    if not os.getenv("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY is not set")
    settings, repository, artifacts = runtime
    service = JevService(settings, repository, artifacts)
    run_id = repository.create_run("live-jev", mode="LIVE", fixture_id=None, fixture_version=None)
    state = _build([_frame("P1"), _frame("P2"), _frame("P3")])
    evaluation = service.evaluate(run_id=run_id, state=state, emit=lambda *args, **kwargs: None)
    assert evaluation["error"] is None, evaluation.get("error")
    assert evaluation["resolved_model"] == settings.jev_model
    assert set(evaluation["answers"]) == {definition.question_id for definition in WIDE_QUESTIONS}
    assert evaluation["usage"]["input_tokens"] and evaluation["usage"]["input_tokens"] > 0
    assert evaluation["latency_ms"] and evaluation["latency_ms"] > 0
    assert evaluation["cache_source_evaluation_id"] is None
