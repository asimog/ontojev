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


def test_rewording_and_reprioritizing_do_not_reset_progress(runtime):
    block(runtime, ReplayDirector(decision()))
    for index in range(3):
        _, result = block(runtime, ReplayDirector(decision(
            "PRIORITIZE", question_id="q1", priority=70 + index,
            next_action=f"Review the same evidence again, attempt {index}.")))
    assert result.operational_state == "NO_PROGRESS"
    assert result.consecutive_no_progress == 3


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


def test_sequential_ephemeral_shards_preserve_evidence_and_reacquisition(runtime):
    from cancerjev.domain.codecs import read_cnv_shard_evidence
    from cancerjev.research.lab_acquisition import CnvLabAcquisition, ShardArtifactStore
    from tests.science.test_cnv_project_scan import _Transport

    _, repository, artifacts = runtime
    block(runtime, ReplayDirector(decision()))

    class SelectShard(ReplayDirector):
        def decide(self, projection, *, timeout):
            offer = next(o for o in projection["offers"] if len(o["cases"]) == 5)
            return decision("ACQUIRE", question_id="q1", offer_id=offer["offer_id"])

    class RegisteredReplay(_Transport):
        def request(self, request):
            response = super().request(request)
            repository.register_artifact(response.artifact, self.run_id)
            return response

    acquired = []
    for _ in range(2):
        run_id = repository.create_run("lab-test", scope={"purpose": "LAB"})
        repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start", message="Run.")
        shard_store = ShardArtifactStore(artifacts.data_dir, run_id)
        transport = RegisteredReplay(shard_store, repository, run_id)
        clock = RunClock()
        acquisition = CnvLabAcquisition(repository, artifacts, run_id, transport, clock)
        result = run_block(repository, artifacts, run_id, SelectShard(None), acquisition, clock)
        row = repository.artifact(result.evidence_ids[-1])
        evidence = read_cnv_shard_evidence(artifacts.read(row["relative_path"], row["sha256"]))
        acquired.append(evidence)
        assert not (artifacts.data_dir / "shards" / run_id).exists()
        provenance_row = repository.artifact_at_path(f"runs/{run_id}/lab/acquisition.json")
        provenance = json.loads(artifacts.read(provenance_row["relative_path"], provenance_row["sha256"]))
        assert provenance["offer"]["cases"] == list(evidence.case_ids)
        assert provenance["release"] == evidence.release
        assert any(r["endpoint"] == "/cnv_occurrences" and "filters" in r["params"]
                   for r in provenance["requests"])
        events = repository.events(run_id, 0, 100)["items"]
        assert next(e["sequence"] for e in events if e["type"] == "LAB_PORTFOLIO_REVISED") < next(
            e["sequence"] for e in events if e["type"] == "LAB_RAW_CLEANUP")
    assert not set(acquired[0].case_ids) & set(acquired[1].case_ids)
    restored = load_lab(repository, artifacts)
    assert len(restored.evidence_ids) == 2
    first = repository.artifact(restored.evidence_ids[0])
    assert read_cnv_shard_evidence(artifacts.read(first["relative_path"], first["sha256"])) == acquired[0]
    coverage_row = repository.artifact_at_path(f"runs/{restored.last_run_id}/lab/coverage.json")
    assert coverage_row is not None
    coverage = json.loads(artifacts.read(coverage_row["relative_path"], coverage_row["sha256"]))["groups"][0]
    assert coverage["queried_cases"] == 10
    assert coverage["cohort_cases"] > 10
    assert coverage["coverage"] == "PARTIAL"
    assert set(coverage["evidence_ids"]) == set(restored.evidence_ids)
    from cancerjev.research.laboratory import coverage_summaries

    duplicate = artifacts.publish(f"runs/{restored.last_run_id}/duplicate.json",
        artifacts.read(first["relative_path"], first["sha256"]), "application/json", "cnv-shard-evidence")
    repository.register_artifact(duplicate, restored.last_run_id)
    with pytest.raises(ValueError, match="overlapping"):
        coverage_summaries(repository, artifacts, restored.model_copy(update={
            "evidence_ids": (*restored.evidence_ids, duplicate.artifact_id)}))
    other = decision().question.model_copy(update={"question_id": "q2", "project_id": "TCGA-LUSC"})
    _, before = block(runtime, ReplayDirector(decision(question=other)))
    with pytest.raises(ValueError, match="another cohort"):
        block(runtime, ReplayDirector(decision("INTERPRET", question_id="q2", interpretation={
            "question_id": "q2", "evidence_ids": [restored.evidence_ids[0]],
            "conclusion": "This describes a different cohort.", "uncertainty": ["Unverified."],
        })))
    assert load_lab(repository, artifacts) == before


@pytest.mark.local_process
def test_supervisor_terminates_overdue_execution():
    import sys
    import time

    from cancerjev.research.lab_worker import supervise

    started = time.monotonic()
    assert supervise([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2) == 124
    assert time.monotonic() - started < 5


def test_jev_control_retains_purpose_provenance_and_abstains(runtime):
    from cancerjev.domain.laboratory import AcquisitionOffer
    from cancerjev.jev.service import JevService
    from cancerjev.jev.typesafe_adapter import ProviderAnswerSet

    settings, repository, artifacts = runtime
    state = apply_decision(LabState(), decision())
    offer = AcquisitionOffer(offer_id="offer", question_id="q1", project_id="TCGA-LUAD",
        method="CNV_POSITIVE_CASE_SHARD_V1", modality="CNV", cases=("case-1",),
        expected_bytes=100, maximum_bytes=1000, estimated_seconds=1,
        evidence_provided="Positive CNV counts", limitations=("Not neutral calls",))

    class Provider:
        probability = 0.8

        def evaluate(self, projection, definitions):
            return ProviderAnswerSet("jev-1.13.0", "jev-1.13.0",
                {"offer_0": {"kind": "noul", "probability_yes": self.probability}},
                {"input_tokens": 10, "output_tokens": 1}, 1, "replay-request")

    provider = Provider()
    for expected_status, probability in (("COMPLETE", 0.8), ("ABSTAINED", float("nan"))):
        provider.probability = probability
        run_id = repository.create_run("lab-test")
        result = JevService(settings, repository, artifacts, lambda: provider).evaluate_lab_control(
            run_id, state, (offer,))
        row = repository.artifact(result["artifact_id"])
        stored = json.loads(artifacts.read(row["relative_path"], row["sha256"]))
        assert stored["purpose"] == "RESEARCH_CONTROL"
        assert stored["source_kind"] == "JEV_CONTROL_JUDGMENT"
        assert stored["projection"]["offers"][0]["offer_id"] == "offer"
        assert stored["question_set_version"] == "lab-control-v1"
        assert stored["source_state_hash"]
        assert stored["status"] == expected_status
        assert not repository.list_table("statistical_states", run_id)
        assert load_lab(repository, artifacts).evidence_ids == ()


def test_observatory_reads_canonical_portfolio_and_decision(runtime, monkeypatch):
    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    settings, _, _ = runtime
    run_id, state = block(runtime, ReplayDirector(decision()))
    monkeypatch.setenv("CANCERJEV_NO_DOTENV", "1")
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    with TestClient(create_app()) as client:
        response = client.get("/api/lab")
        assert response.status_code == 200
        assert response.json() == state.model_dump(mode="json")
        story = client.get(f"/api/runs/{run_id}/lab").json()
        documents = {item["purpose"]: item["document"] for item in story["documents"]}
        assert documents["research-portfolio"] == state.model_dump(mode="json")
        assert documents["ontocodex-decision"]["decision"]["action"] == "CREATE_QUESTION"
        run = client.get(f"/api/runs/{run_id}").json()
        assert run["lab"]["cleanup_status"] == "CLEAN"
        assert run["lab"]["revision"] == state.revision
