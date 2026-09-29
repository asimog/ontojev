"""Portfolio, provider failure and evidence admission at the durable run boundary."""

import json

import pytest
from pydantic import ValidationError

from cancerjev.domain.laboratory import DirectorIdentity, LabState, ResearchDecision
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.llm.ontocodex import CodexDirector, DirectorError
from cancerjev.research.lab_runtime import ContinueNextRun, RunClock, run_block
from cancerjev.research.laboratory import apply_decision, load_lab


def decision(action="CREATE_QUESTION", **fields):
    payload = dict(action=action, rationale="Resolve uncertainty in lung cancer.",
                   question_id=None, question=None, priority=None, offer_id=None,
                   interpretation=None, next_action="Inspect available evidence.")
    if action == "CREATE_QUESTION":
        payload["question"] = dict(question_id="q1", question="Which CNV patterns need replication?",
                                   rationale="Characterize released positive calls.",
                                   project_id="TCGA-LUAD", priority=60, status="ACTIVE",
                                   uncertainty=["Caller compatibility is unverified."],
                                   next_action="Preflight open CNV occurrences.")
    return ResearchDecision.model_validate({**payload, **fields})


class ReplayDirector:
    identity = DirectorIdentity(harness_version="replay", provider="replay", model="replay",
                                base_url="replay://offline", configuration_hash="replay-v1")

    def __init__(self, result):
        self.result = result

    def decide(self, projection, *, timeout):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class NoAcquisition:
    def preflight(self, state, clock):
        return ()

    def execute(self, offer, clock):
        raise AssertionError("no offered acquisition exists")

    def cleanup(self):
        return {"status": "CLEAN", "bytes_deleted": 0}


def block(runtime, director):
    _, repository, artifacts = runtime
    run_id = repository.create_run("lab-test", scope={"purpose": "LAB"})
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start",
                            message="Offline research block.")
    result = run_block(repository, artifacts, run_id, director, NoAcquisition(), RunClock())
    return run_id, result


def test_portfolio_survives_restart_without_researcher_contamination(runtime):
    _, repository, artifacts = runtime
    first_run, first = block(runtime, ReplayDirector(decision()))
    original = artifacts.read(f"runs/{first_run}/lab/portfolio.json")
    researcher = repository.create_run("researcher", ownership=ExecutionOwnership.RESEARCHER_RUN)
    poison = artifacts.publish(f"runs/{researcher}/poison.json", b"{}", "application/json",
                               "research-portfolio")
    repository.register_artifact(poison, researcher)
    assert load_lab(repository, artifacts) == first
    second_run, second = block(runtime, ReplayDirector(
        decision("PRIORITIZE", question_id="q1", priority=90)))
    assert second.revision == 2 and second.questions[0].priority == 90
    assert second.previous_artifact_id == repository.artifact_at_path(
        f"runs/{first_run}/lab/portfolio.json")["artifact_id"]
    assert artifacts.read(f"runs/{first_run}/lab/portfolio.json") == original
    assert load_lab(repository, artifacts).last_run_id == second_run


def test_provider_failure_retains_science_and_stops_repeated_failure(runtime):
    _, repository, artifacts = runtime
    _, initial = block(runtime, ReplayDirector(decision()))
    for _ in range(3):
        run_id, result = block(runtime, ReplayDirector(DirectorError("DIRECTOR_TIMEOUT")))
    assert result.operational_state == "NO_PROGRESS"
    assert result.questions == initial.questions
    assert result.evidence_ids == () and result.interpretations == ()
    assert load_lab(repository, artifacts) == result
    assert {e["type"] for e in repository.events(run_id, 0, 20)["items"]} >= {
        "ONTOCODEX_UNAVAILABLE", "LAB_RAW_CLEANUP", "LAB_PORTFOLIO_REVISED"}


def test_director_cannot_invent_evidence_or_bypass_preflight():
    state = apply_decision(LabState(), decision())
    with pytest.raises(ValueError, match="unknown evidence"):
        apply_decision(state, decision("INTERPRET", question_id="q1", interpretation={
            "question_id": "q1", "evidence_ids": ["invented"], "conclusion": "Unsupported.",
            "uncertainty": ["Unverified."],
        }))
    with pytest.raises(ValueError, match="preflight"):
        apply_decision(state, decision("ACQUIRE", question_id="q1", offer_id="invented"))
    payload = decision().model_dump()
    payload["observed_count"] = 42
    with pytest.raises(ValidationError):
        ResearchDecision.model_validate(payload)
    with pytest.raises(ValidationError):
        decision("ACQUIRE", question_id="q1", offer_id="x", priority=99)


def test_run_reserves_finalization_and_rejects_invalid_estimates():
    clock = RunClock(seconds=21)
    with pytest.raises(ContinueNextRun):
        clock.reserve(2)
    for estimate in (float("nan"), float("inf"), -1):
        with pytest.raises(ValueError):
            clock.reserve(estimate)
    with pytest.raises(ValueError):
        RunClock(seconds=601)


def test_harness_protocol_is_isolated_and_validated(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-inherited")
    observed = {}

    def invoke(command, **kwargs):
        observed.update(kwargs)
        from pathlib import Path
        from subprocess import CompletedProcess

        Path(command[command.index("--output-last-message") + 1]).write_text(
            decision().model_dump_json(), encoding="utf-8")
        assert "--output-schema" in command
        return CompletedProcess(command, 0)

    monkeypatch.setattr("cancerjev.llm.ontocodex.subprocess.run", invoke)
    director = CodexDirector("codex", "configured-model", "https://openrouter.ai/api/v1", "test")
    result = director.decide({"domain": "lung cancer"}, timeout=5)
    assert result.action == "CREATE_QUESTION"
    assert "OPENAI_API_KEY" not in observed["env"]
    assert observed["timeout"] == 5
    assert json.loads(observed["input"].split("STATE:\n")[1]) == {"domain": "lung cancer"}

    def invalid(command, **kwargs):
        from pathlib import Path
        from subprocess import CompletedProcess

        Path(command[command.index("--output-last-message") + 1]).write_text('{"observed":42}')
        return CompletedProcess(command, 0)

    monkeypatch.setattr("cancerjev.llm.ontocodex.subprocess.run", invalid)
    with pytest.raises(DirectorError, match="INVALID_OR_UNAVAILABLE"):
        director.decide({}, timeout=5)
