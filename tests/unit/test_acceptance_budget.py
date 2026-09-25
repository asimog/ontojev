from __future__ import annotations

import pytest

from cancerjev.config import (
    GDC_MAX_BYTES_HARD_CAP,
    GDC_MAX_REQUESTS_HARD_CAP,
    GDC_PER_RESPONSE_BYTES_HARD_CAP,
    GDC_TIMEOUT_SECONDS_HARD_CAP,
    JEV_MAX_STATES_HARD_CAP,
    JEV_TIMEOUT_SECONDS_HARD_CAP,
    LLM_TIMEOUT_SECONDS_HARD_CAP,
    Settings,
)
from cancerjev.gdc.transport import BudgetCaps
from cancerjev.jev.typesafe_adapter import JevProviderError, TypeSafeAdapter
from tests.live.acceptance import BudgetedAdapter, CallBudget, check_generated_text


def test_failed_jev_attempt_consumes_budget_without_retry(runtime, monkeypatch):
    settings, _, _ = runtime
    budget = CallBudget(jev_attempts=14)
    adapter = BudgetedAdapter(settings, budget)
    calls = 0

    def unavailable(self, state, definitions):
        nonlocal calls
        calls += 1
        raise JevProviderError("PROVIDER_AUTH", "no credential")

    monkeypatch.setattr(TypeSafeAdapter, "evaluate", unavailable)

    with pytest.raises(JevProviderError) as error:
        adapter.evaluate({}, ())
    assert error.value.code == "PROVIDER_AUTH"
    with pytest.raises(JevProviderError) as error:
        adapter.evaluate({}, ())
    assert error.value.code == "ACCEPTANCE_BUDGET_EXHAUSTED"
    assert calls == 1
    assert budget.jev_attempts == 15


def test_llm_attempt_is_reserved_once():
    budget = CallBudget()
    budget.reserve_llm()
    with pytest.raises(ValueError, match="one acceptance LLM attempt"):
        budget.reserve_llm()
    assert budget.llm_attempts == 1


def test_invalid_evidence_prevents_all_provider_calls(runtime, monkeypatch):
    settings, repository, artifacts = runtime
    calls: list[object] = []
    monkeypatch.setattr(TypeSafeAdapter, "evaluate", lambda *args, **kwargs: calls.append(args))
    budget = CallBudget()

    report = check_generated_text(
        settings, repository, artifacts, "missing-candidate", budget,
        generator=lambda request: calls.append(request),
    )

    assert report["status"] == "FAILED"
    assert report["error_code"] == "CANDIDATE_MISSING"
    assert report["notice"] == "NOT A PRODUCTION NEXT MOVE; GENERATED TEXT IS NOT EVIDENCE"
    assert report["attempts"] == {"jev_attempts": 0, "llm_attempts": 0}
    assert calls == []
    assert (settings.data_dir / report["report_path"]).is_file()


def test_documented_hard_caps_are_the_run_defaults():
    caps = BudgetCaps()
    assert caps.max_requests == GDC_MAX_REQUESTS_HARD_CAP == 150
    assert caps.max_bytes == GDC_MAX_BYTES_HARD_CAP == 256 * 1024 * 1024
    assert caps.per_response_bytes == GDC_PER_RESPONSE_BYTES_HARD_CAP == 5 * 1024 * 1024
    assert caps.timeout_seconds == GDC_TIMEOUT_SECONDS_HARD_CAP == 30.0
    assert caps.max_pages_per_query == 48
    assert caps.max_case_ids == 250
    assert caps.max_gene_ids == 100
    assert caps.max_retries == 2
    assert JEV_MAX_STATES_HARD_CAP == 1000
    assert JEV_TIMEOUT_SECONDS_HARD_CAP == 30.0
    assert LLM_TIMEOUT_SECONDS_HARD_CAP == 120.0


def test_settings_defaults_stay_at_the_original_operational_budgets():
    """The byte ceiling was enlarged for the occurrence scan only.

    General run settings keep the original 64 MiB default; the systematic
    discovery worker constructs the scan budget explicitly from the documented
    domain constants, and operational settings may never exceed the hard cap.
    """
    settings = Settings.from_env()
    assert settings.gdc_max_bytes == 64 * 1024 * 1024
    assert settings.gdc_max_bytes < GDC_MAX_BYTES_HARD_CAP
    assert settings.gdc_max_requests == 150
    assert settings.gdc_per_response_bytes == GDC_PER_RESPONSE_BYTES_HARD_CAP


def test_settings_refuse_values_above_the_documented_caps(tmp_path, monkeypatch):
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(tmp_path))
    above_cap = (
        ("CANCERJEV_GDC_MAX_REQUESTS", str(GDC_MAX_REQUESTS_HARD_CAP + 1)),
        ("CANCERJEV_GDC_MAX_BYTES", str(GDC_MAX_BYTES_HARD_CAP + 1)),
        ("CANCERJEV_GDC_PER_RESPONSE_BYTES", str(GDC_PER_RESPONSE_BYTES_HARD_CAP + 1)),
        ("CANCERJEV_GDC_TIMEOUT_SECONDS", str(GDC_TIMEOUT_SECONDS_HARD_CAP + 0.1)),
        ("CANCERJEV_JEV_MAX_STATES", str(JEV_MAX_STATES_HARD_CAP + 1)),
        ("CANCERJEV_JEV_TIMEOUT_SECONDS", str(JEV_TIMEOUT_SECONDS_HARD_CAP + 0.1)),
        ("CANCERJEV_LLM_TIMEOUT_SECONDS", str(LLM_TIMEOUT_SECONDS_HARD_CAP + 0.1)),
    )
    for name, value in above_cap:
        monkeypatch.setenv(name, value)
        with pytest.raises(ValueError, match="must not exceed the documented hard cap"):
            Settings.from_env()
        monkeypatch.delenv(name)

    settings = Settings.from_env()
    assert settings.gdc_max_requests == GDC_MAX_REQUESTS_HARD_CAP
    assert settings.gdc_max_bytes == 64 * 1024 * 1024
    assert settings.gdc_max_bytes < GDC_MAX_BYTES_HARD_CAP
    assert settings.gdc_per_response_bytes == GDC_PER_RESPONSE_BYTES_HARD_CAP
    assert settings.gdc_timeout_seconds == GDC_TIMEOUT_SECONDS_HARD_CAP
    assert settings.jev_max_states == JEV_MAX_STATES_HARD_CAP
    assert settings.jev_timeout_seconds == JEV_TIMEOUT_SECONDS_HARD_CAP
    assert settings.llm_timeout_seconds == LLM_TIMEOUT_SECONDS_HARD_CAP


def test_live_acceptance_markers_are_registered_and_excluded_by_default(pytestconfig):
    markers = {"live", "live_gdc", "live_jev", "live_llm", "live_acceptance"}
    registered = pytestconfig.getini("markers")
    assert all(any(entry.startswith(f"{marker}:") for entry in registered) for marker in markers)
    addopts = " ".join(pytestconfig.getini("addopts"))
    assert all(f"not {marker}" in addopts for marker in markers)
