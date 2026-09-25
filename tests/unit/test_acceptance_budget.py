"""Offline verification of opt-in live-test caps and failure containment."""

import json
from dataclasses import asdict

import pytest

from cancerjev.jev.typesafe_adapter import JevProviderError, TypeSafeAdapter
from tests.integration.test_deep_slice import _completed_slice
from tests.jev.stub_adapter import StubAdapter
from tests.live.acceptance import BudgetedAdapter, CallBudget, check_generated_text


def test_failed_jev_attempt_consumes_budget_without_retry(runtime, monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise JevProviderError("PROVIDER_AUTH", "test failure")

    monkeypatch.setattr(TypeSafeAdapter, "evaluate", unavailable)
    budget = CallBudget(jev_attempts=14)
    adapter = BudgetedAdapter(runtime[0], budget)
    with pytest.raises(JevProviderError, match="PROVIDER_AUTH"):
        adapter.evaluate({}, ())
    with pytest.raises(JevProviderError, match="ACCEPTANCE_BUDGET_EXHAUSTED"):
        adapter.evaluate({}, ())
    assert len(calls) == 1 and budget.jev_attempts == 15


def test_llm_attempt_is_reserved_once():
    budget = CallBudget()
    budget.reserve_llm()
    with pytest.raises(ValueError, match="already reserved"):
        budget.reserve_llm()
    assert budget.llm_attempts == 1


def test_invalid_evidence_prevents_all_provider_calls(runtime):
    settings, repository, artifacts = runtime
    budget = CallBudget()
    report = check_generated_text(settings, repository, artifacts, "missing-candidate", budget)
    assert report["status"] == "FAILED"
    assert asdict(budget) == {"jev_attempts": 0, "llm_attempts": 0}
    assert (settings.data_dir / report["report_path"]).is_file()


@pytest.mark.parametrize("failure", [False, True])
def test_independent_generation_does_not_modify_source_run(runtime, monkeypatch, failure):
    settings, repository, artifacts = runtime
    run_id, _, _ = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["latest_evidence_state_id"])
    before = repository.events(run_id, 0, 500)
    hypotheses_before = repository.list_table("hypotheses", run_id)
    calls = []

    def generator(request):
        calls.append(request)
        if failure:
            raise RuntimeError("SECRET_MUST_NOT_APPEAR")
        return [{
            "statement": "Hypothetically, recorded coverage limits interpretation.",
            "proposed_mechanism": "Hypothetical measurement coverage artifact.",
            "predictions": ["Recorded missingness would remain material."],
            "contradicted_if": ["Retained evidence rules out the coverage explanation."],
            "distinguishing_tests": [], "required_evidence": ["Retained GDC evidence"],
            "unsupported_assumptions": ["Coverage can explain the recorded pattern."],
        }], {"input_tokens": 10, "output_tokens": 20}

    report = check_generated_text(settings, repository, artifacts, candidate["candidate_id"],
                                  CallBudget(), generator=generator, adapter=StubAdapter())
    assert len(calls) == 1
    assert report["status"] == ("FAILED" if failure else "PASSED"), report.get("error_code")
    assert repository.events(run_id, 0, 500) == before
    assert repository.list_table("hypotheses", run_id) == hypotheses_before
    persisted = (settings.data_dir / report["report_path"]).read_text()
    assert "SECRET_MUST_NOT_APPEAR" not in persisted
    assert json.loads(persisted)["kind"] == "INDEPENDENT_PROVIDER_INTEGRATION_TEST"
