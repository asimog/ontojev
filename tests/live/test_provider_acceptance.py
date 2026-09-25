"""Explicit live tests. Ordinary pytest and CI never select these markers."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import replace

import pytest

from cancerjev.config import Settings
from cancerjev.jev.service import JevService, is_pinned_model_identity
from cancerjev.research.live import LiveOrchestrator
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.readers import read_state_record
from cancerjev.storage.repositories import Repository
from tests.live.acceptance import BudgetedAdapter, CallBudget, check_generated_text


def _settings() -> Settings:
    settings = Settings.from_env()
    missing = [name for name in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY") if not os.getenv(name)]
    if missing:
        pytest.skip("Live acceptance requires " + ", ".join(missing) + " in root .env.local or the environment")
    if not is_pinned_model_identity(settings.jev_model):
        pytest.fail("Live acceptance requires a pinned Jev model identity before making provider calls")
    return settings


@pytest.mark.live_llm
def test_llm_and_jev_critique_of_retained_evidence(record_property):
    settings = _settings()
    candidate_id = os.getenv("CANCERJEV_ACCEPTANCE_CANDIDATE_ID")
    if not candidate_id:
        pytest.skip("Set CANCERJEV_ACCEPTANCE_CANDIDATE_ID to a retained live candidate with an action revision")
    if not settings.database_path.is_file():
        pytest.fail("Retained evidence database is absent; no acquisition is performed by this test")
    repository = Repository(Database(settings.database_path))
    report = check_generated_text(settings, repository, ArtifactStore(settings.data_dir), candidate_id, CallBudget())
    record_property("acceptance_report", str(settings.data_dir / report["report_path"]))
    assert report["status"] == "PASSED", report.get("error_code")
    assert report["attempts"]["llm_attempts"] == 1
    assert 1 <= report["attempts"]["jev_attempts"] <= 3


def _baseline_top_symbol(repository, artifacts, run_id) -> str:
    """Deterministic operator choice: the baseline ranking's first gene symbol."""
    artifact = next(item for item in repository.ranking_artifacts(run_id)
                    if item["relative_path"].endswith("baseline_ranking.json"))
    ranking = json.loads(artifacts.read(artifact["relative_path"]).decode())
    symbol = ranking["entries"][0]["gene_symbol"]
    assert symbol, "the baseline ranking must name its first gene"
    return symbol


@pytest.mark.live_acceptance
def test_bounded_live_run_and_separate_generation(tmp_path, monkeypatch, record_property):
    configured = _settings()
    settings = replace(configured, data_dir=tmp_path / "live-acceptance", fixture_stage_delay_ms=0,
                       gdc_cache_enabled=False, jev_max_states=min(configured.jev_max_states, 10))
    database = Database(settings.database_path)
    database.bootstrap()
    repository = Repository(database)
    artifacts = ArtifactStore(settings.data_dir)
    budget = CallBudget()

    def service(configuration):
        return JevService(configuration, repository, artifacts,
                          adapter_factory=lambda: BudgetedAdapter(configuration, budget))

    # 1. Fresh bounded live sweep with real GDC and Jev. Admission is the policy's
    #    natural decision (ADMIT or ABSTAIN); nothing is retried for a favorable result.
    sweep_id = LiveOrchestrator(settings, repository, artifacts, jev_service=service(settings)).run()
    record_property("sweep_run_id", sweep_id)
    assert repository.get_run(sweep_id)["status"] == "COMPLETED"
    totals = repository.gdc_run_totals(sweep_id)
    assert 0 < totals["attempts"] <= 150
    assert totals["cache_hits"] == 0
    assert totals["bytes"] <= settings.gdc_max_bytes
    symbol = _baseline_top_symbol(repository, artifacts, sweep_id)
    record_property("operator_symbol", symbol)

    # 2. The operator explicitly selects one wide-evaluated state; every GDC response
    #    comes from the retained cache and every wide judgment from the verified Jev cache.
    cached = replace(settings, gdc_cache_enabled=True)
    run_id = LiveOrchestrator(
        cached, repository, artifacts, jev_service=service(cached),
        deep_selection=f"gene:{symbol}", deep_followup_authorized=True,
    ).run()
    record_property("source_run_id", run_id)
    record_property("data_directory", str(settings.data_dir))
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    replay_totals = repository.gdc_run_totals(run_id)
    assert replay_totals["attempts"] == replay_totals["cache_hits"]
    candidates = [row for row in repository.list_table("candidates", run_id)
                  if row["latest_evidence_state_id"]]
    assert len(candidates) == 1, "one explicit candidate must have a completed action revision"
    candidate = candidates[0]
    deep = repository.page_child("jev_evaluations", run_id, 20, None, {"purpose": "DEEP"})["items"]
    assert deep and all((row["vector"].get("error") or {}).get("code") is None for row in deep)

    # 3. One separate, labelled LLM generation request and at most three Jev critiques.
    before = repository.events(run_id, 0, 500)
    report = check_generated_text(settings, repository, artifacts, candidate["candidate_id"], budget)
    record_property("acceptance_report", str(settings.data_dir / report["report_path"]))
    assert repository.events(run_id, 0, 500) == before, "the integration check must not rewrite production history"
    assert report["status"] == "PASSED", report.get("error_code")
    assert budget.llm_attempts == 1 and budget.jev_attempts <= 15

    # 4. Replay only from retained responses/inference. A cache miss must fail this
    #    verification instead of silently spending another provider request.
    def refuse_network(*args, **kwargs):
        raise AssertionError("acceptance replay cannot contact providers")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    monkeypatch.setattr(socket.socket, "connect", refuse_network)
    calls_before = budget.jev_attempts
    replay_settings = replace(settings, gdc_cache_enabled=True)
    replay_id = LiveOrchestrator(
        replay_settings, repository, artifacts, jev_service=service(replay_settings),
        deep_selection=f"gene:{symbol}", deep_followup_authorized=True,
    ).run()
    assert repository.get_run(replay_id)["status"] == "COMPLETED"
    final_totals = repository.gdc_run_totals(replay_id)
    assert final_totals["attempts"] == final_totals["cache_hits"]
    assert budget.jev_attempts == calls_before, "all replay judgments must come from verified cache"
    original_hashes = sorted(read_state_record(repository, artifacts, row["state_id"]).state_hash
                             for row in repository.list_table("statistical_states", run_id))
    replay_hashes = sorted(read_state_record(repository, artifacts, row["state_id"]).state_hash
                           for row in repository.list_table("statistical_states", replay_id))
    assert original_hashes == replay_hashes
