from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.domain.events import canonical_json
from cancerjev.jev.service import JevService
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.wide import run_wide_evaluation
from cancerjev.science.methods import METHODS
from tests.integration.replay import GENES, ReplayTransport
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import _register_state
from tests.science.test_methods import _build, _frame


def _orchestrator(runtime, monkeypatch, *, jev_adapter=None, **replay_options):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    holder: dict[str, ReplayTransport] = {}

    def factory(repo, artifact_store, budget, run_id, emit):
        transport = ReplayTransport(artifact_store, run_id, **replay_options)
        holder["transport"] = transport
        return transport

    service = None
    if jev_adapter is not None:
        service = JevService(settings, repository, artifacts, adapter_factory=lambda: jev_adapter)
    orchestrator = LiveOrchestrator(settings, repository, artifacts, lambda event: None,
                                    jev_service=service, transport_factory=factory)
    return orchestrator, holder, repository


def test_live_replay_with_jev_wide_evaluation(runtime, monkeypatch):
    adapter = StubAdapter()
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["counts"]["states_generated"] == 2
    assert run["counts"]["states_evaluated"] == 2
    assert run["counts"]["candidates_promoted"] == 2
    assert run["counts"]["jev_evaluations"] == 2
    assert run["provider_usage"]["jev_calls"] == 2
    assert run["provider_usage"]["jev_input_tokens"] == 2400
    assert run["provider_usage"]["jev_output_tokens"] == 120
    assert run["provider_usage"]["llm_calls"] == 0
    assert adapter.calls == 2

    client = TestClient(create_app())
    projections = client.get(f"/api/runs/{run_id}/projections").json()["items"]
    assert len(projections) == 2
    assert all(row["projection_version"] == "jev-state-projection-v1" for row in projections)
    assert all(row["source_state_hash"] and row["projection_hash"] for row in projections)

    evaluations = client.get(f"/api/runs/{run_id}/evaluations?purpose=WIDE").json()["items"]
    assert len(evaluations) == 2
    for row in evaluations:
        assert row["input_ref_kind"] == "STATISTICAL_STATE"
        vector = row["vector"]
        assert vector["error"] is None
        assert vector["resolved_model"] == "jev-1.13.0"
        assert vector["cache_source_evaluation_id"] is None
        assert set(vector["answers"]) == {
            "warrants_deeper_investigation", "mutation_project_exception",
            "expression_project_exception", "coverage_explains_apparent_difference",
            "likely_fragile", "pattern_type",
        }
        assert vector["applicability"]["pattern_type"]["applicable"] is True

    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    assert rankings["baseline"]["policy_version"] == "baseline-wide-v1"
    assert rankings["jev"]["policy_version"] == "wide-policy-v1"
    assert len(rankings["baseline"]["entries"]) == 2
    assert len(rankings["jev"]["entries"]) == 2
    assert rankings["jev"]["admitted_state_ids"]

    candidates = client.get(f"/api/runs/{run_id}/candidates").json()["items"]
    assert len(candidates) == 2
    assert all(candidate["status"] == "WIDE_EVALUATED" for candidate in candidates)
    assert all(candidate["summary"]["wide_evaluation_id"] for candidate in candidates)

    events = [event["type"] for event in repository.events(run_id, 0, 500)["items"]]
    for event_type in ("JEV_PROJECTION_CREATED", "JEV_WIDE_STARTED", "JEV_WIDE_STATE_EVALUATED",
                       "WIDE_RANKING_COMPLETED", "JEV_WIDE_COMPLETED", "CANDIDATE_PROMOTED"):
        assert event_type in events
    assert not any(event_type.startswith("HYPOTHESES") or event_type.startswith("FOLLOWUP") for event_type in events)


def test_jev_cache_reuses_judgments_across_runs(runtime, monkeypatch):
    adapter = StubAdapter()
    first, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    first_run = first.run()
    second, _, _ = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    second_run = second.run()
    assert adapter.calls == 2, "the second run must be served entirely from cache"
    second_usage = repository.get_run(second_run)["provider_usage"]
    assert second_usage["jev_calls"] == 0
    evaluations = repository.page_child("jev_evaluations", second_run, 10, None, {"purpose": "WIDE"})["items"]
    assert len(evaluations) == 2
    assert all(row["vector"]["cache_source_evaluation_id"] for row in evaluations)
    assert repository.get_run(first_run)["provider_usage"]["jev_calls"] == 2


def test_live_replay_produces_real_states_without_jev(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["mode"] == "LIVE"
    assert run["coverage"] == "COMPLETE_FOR_SCOPE"
    assert run["selected_project_ids"] == ["TEST-B", "TEST-A"] or set(run["selected_project_ids"]) == {"TEST-A", "TEST-B"}
    assert "TEST-C" not in run["selected_project_ids"], "project below the case floor is excluded"
    assert run["counts"]["states_generated"] == 2
    assert run["provider_usage"]["jev_calls"] == 0
    assert run["provider_usage"]["llm_calls"] == 0

    states = repository.list_table("statistical_states", run_id)
    assert len(states) == 2
    assert all(row["disposition"] == "GENERATED" for row in states)
    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"] for row in states}
    gene_one = summaries[GENES[0]]
    assert gene_one["affected_case_total"]["value"] == 32
    assert gene_one["top_project_share"]["value"] == 0.625
    assert gene_one["projects_with_mutation_observation"] == 2
    gene_two = summaries[GENES[1]]
    assert gene_two["affected_case_total"]["value"] == 5
    assert gene_two["projects_with_mutation_observation"] == 1

    client = TestClient(create_app())
    listed = client.get(f"/api/runs/{run_id}/states").json()["items"]
    assert len(listed) == 2
    state_id = listed[0]["state_id"]
    detail = client.get(f"/api/states/{state_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["schema_version"] == 2
    assert body["mode"] == "LIVE"
    assert body["cross_project"]["direction"] == "NOT_EXAMINED"
    assert body["provenance"]["gdc_release"] == "Data Release TEST - 2026-01-01"
    assert len(body["provenance"]["methods"]) == len(METHODS)
    assert body["quality"]["duplicate_checks"] == "PASS"
    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    assert rankings == {"baseline": None, "jev": None}
    projections = client.get(f"/api/runs/{run_id}/projections").json()["items"]
    assert projections == []

    events = repository.events(run_id, 0, 500)["items"]
    types = [event["type"] for event in events]
    assert "PROJECT_SCOPE_SELECTED" in types
    assert "STATISTICAL_STATE_CREATED" in types
    assert not any(event_type.startswith("JEV") for event_type in types), "Phase 2 must not emit Jev events"
    assert all(event["level"] != "error" for event in events)

    transport = holder["transport"]
    names = [request.endpoint.name for request in transport.requests]
    assert names.count("cases") == 2
    assert names.count("gene_expression_values") == 2
    assert len(names) <= 20, "replay sweep must stay bounded"


def test_project_without_expression_values_skips_expression_calls(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch,
                                                     empty_expression_projects={"TEST-B"})
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["coverage"] == "COMPLETE_FOR_SCOPE", "an observed absence of expression data is not a partial retrieval"
    states = repository.list_table("statistical_states", run_id)
    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"] for row in states}
    assert summaries[GENES[0]]["expression_availability"] == "PARTIAL"
    assert summaries[GENES[0]]["coverage_imbalance"] is True
    names = [request.endpoint.name for request in holder["transport"].requests]
    assert names.count("gene_expression_availability") == 2
    assert names.count("gene_expression_gene_selection") == 1
    assert names.count("gene_expression_values") == 1


def test_controlled_file_record_fails_closed(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, controlled_files=True)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "FAILED"
    assert run["outcome_reason"] == "CONTROLLED_RECORD_RETURNED"
    assert repository.list_table("statistical_states", run_id) == []


def test_incomplete_case_frame_fails_closed(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, incomplete_frame=True)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "FAILED"
    assert run["outcome_reason"] == "CASE_FRAME_INCOMPLETE"
    assert repository.list_table("statistical_states", run_id) == []


def test_live_replay_is_deterministic_for_same_inputs(runtime, monkeypatch):
    first_orchestrator, _, repository = _orchestrator(runtime, monkeypatch)
    first_run = first_orchestrator.run()
    second_orchestrator, _, _ = _orchestrator(runtime, monkeypatch)
    second_run = second_orchestrator.run()
    hashes = []
    for run_id in (first_run, second_run):
        states = repository.list_table("statistical_states", run_id)
        hashes.append(sorted(row["state_hash"] for row in states))
    assert hashes[0] == hashes[1], "identical scientific inputs must produce identical state hashes"


WIDE_LIFECYCLE_EVENTS = {
    "JEV_WIDE_STARTED", "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
    "WIDE_RANKING_COMPLETED", "CANDIDATE_PROMOTED", "JEV_WIDE_COMPLETED",
}


def _wide_summary(client: TestClient, repository, run_id: str) -> dict:
    states = repository.list_table("statistical_states", run_id)
    state_hashes = {row["state_id"]: row["state_hash"] for row in states}
    evaluations = repository.page_child("jev_evaluations", run_id, 10, None, {"purpose": "WIDE"})["items"]
    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    candidates = repository.list_table("candidates", run_id)
    events = repository.events(run_id, 0, 500)["items"]
    return {
        "evaluated_state_hashes": sorted(state_hashes[row["input_ref_id"]] for row in evaluations),
        "baseline": [
            (entry["rank"], entry["state_hash"], entry["gene_symbol"],
             {key: value for key, value in entry["dimensions"].items()
              if key != "cache_source_evaluation_id"})
            for entry in rankings["baseline"]["entries"]
        ],
        "jev": [
            (entry["rank"], entry["state_hash"], entry["gene_symbol"],
             {key: value for key, value in entry["dimensions"].items()
              if key != "cache_source_evaluation_id"})
            for entry in rankings["jev"]["entries"]
        ],
        "admitted_state_hashes": sorted(
            state_hashes[state_id] for state_id in rankings["jev"]["admitted_state_ids"]
        ),
        "promoted": [
            (row["promotion_slot"], state_hashes[row["source_state_id"]], row["status"],
             row["summary"]["policy_version"], row["summary"]["promotion_reason"])
            for row in sorted(candidates, key=lambda row: row["promotion_slot"])
        ],
        "wide_events": [
            event["type"] for event in events if event["type"] in WIDE_LIFECYCLE_EVENTS
        ],
    }


def test_wide_phase_evaluations_rankings_promotions_and_events_are_stable(runtime, monkeypatch):
    adapter = StubAdapter()
    first_orchestrator, _, repository = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    first_run = first_orchestrator.run()
    second_orchestrator, _, _ = _orchestrator(runtime, monkeypatch, jev_adapter=adapter)
    second_run = second_orchestrator.run()

    client = TestClient(create_app())
    first = _wide_summary(client, repository, first_run)
    second = _wide_summary(client, repository, second_run)

    assert len(first["evaluated_state_hashes"]) == 2, "every generated state is evaluated"
    assert first["evaluated_state_hashes"] == second["evaluated_state_hashes"]
    assert first["baseline"] == second["baseline"], "baseline rankings must be stable for identical inputs"
    assert first["jev"] == second["jev"], "Jev rankings must be stable for identical inputs"
    assert first["admitted_state_hashes"] == second["admitted_state_hashes"]
    assert first["promoted"] == second["promoted"], "identical inputs must promote the same candidates"
    assert len(first["promoted"]) == 2
    assert first["wide_events"] == second["wide_events"]
    assert first["wide_events"] == [
        "JEV_WIDE_STARTED", "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
        "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
        "WIDE_RANKING_COMPLETED", "CANDIDATE_PROMOTED", "CANDIDATE_PROMOTED", "JEV_WIDE_COMPLETED",
    ]


def test_run_wide_evaluation_takes_explicit_collaborators(runtime):
    settings, repository, artifacts = runtime
    adapter = StubAdapter()
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("wide-decoupled", mode="LIVE", fixture_id=None, fixture_version=None)
    states = [_build([_frame("P1"), _frame("P2"), _frame("P3")])]
    _register_state(artifacts, repository, run_id, states[0])
    emitted: list[str] = []
    published: list[str] = []

    def emit(event_run_id, event_type, key, message, **kwargs):
        emitted.append(event_type)
        return repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    def publish_json(pub_run_id, relative_path, payload, purpose):
        published.append(relative_path)
        return artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE",
        repository=repository, jev_service=service, emit=emit, publish_json=publish_json,
    )
    assert adapter.calls == 1
    assert [promotion["state_id"] for promotion in result["promoted"]] == [states[0]["state_id"]]
    assert result["jev"]["admitted_state_ids"] == [states[0]["state_id"]]
    assert published == [
        f"runs/{run_id}/wide/baseline_ranking.json",
        f"runs/{run_id}/wide/jev_ranking.json",
    ]
    assert emitted == [
        "JEV_WIDE_STARTED", "JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED",
        "WIDE_RANKING_COMPLETED", "CANDIDATE_PROMOTED", "JEV_WIDE_COMPLETED",
    ]
