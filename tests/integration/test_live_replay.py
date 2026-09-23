from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.domain.events import canonical_json
from cancerjev.gdc.parsers import ResponseMeta, parse_expression_availability
from cancerjev.jev.service import JevService
from cancerjev.jev.typesafe_adapter import JevProviderError
from cancerjev.research.live import LiveOrchestrator, _merge_expression_availability
from cancerjev.research.specs import LUAD_RESEARCH_V1, AcquisitionSpec, CohortSpec, ResearchSpec
from cancerjev.research.wide import run_wide_evaluation
from cancerjev.science.methods import METHODS
from tests.integration.replay import GENES, ReplayTransport, availability_body
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import _register_state
from tests.science.test_methods import _build, _frame


def _orchestrator(runtime, monkeypatch, *, jev_adapter=None, research_spec=None,
                  deep_selection=None, deep_action_id=None, **replay_options):
    settings, repository, artifacts = runtime
    monkeypatch.setenv("CANCERJEV_DATA_DIR", str(settings.data_dir))
    holder: dict[str, ReplayTransport] = {}

    def factory(repo, artifact_store, budget, run_id, emit):
        transport = ReplayTransport(artifact_store, run_id, repository=repo, **replay_options)
        holder["transport"] = transport
        return transport

    service = None
    if jev_adapter is not None:
        service = JevService(settings, repository, artifacts, adapter_factory=lambda: jev_adapter)
    orchestrator = LiveOrchestrator(settings, repository, artifacts, lambda event: None,
                                    jev_service=service, transport_factory=factory,
                                    research_spec=research_spec or LUAD_RESEARCH_V1,
                                    deep_selection=deep_selection, deep_action_id=deep_action_id)
    return orchestrator, holder, repository


def _test_spec(project_id="TCGA-LUAD", *, page_size=200, batch_size=200, max_cases=600):
    return ResearchSpec(
        spec_id=f"TEST_{project_id}_V1",
        cohort=CohortSpec(cohort_id=project_id, domain="test lung cancer", project_id=project_id),
        acquisition=AcquisitionSpec(
            case_page_size=page_size, case_batch_size=batch_size, max_cohort_cases=max_cases,
            discovery_gene_limit=2, count_gene_limit=2, candidate_gene_limit=2,
            expression_file_sample_size=3,
        ),
    )


def test_default_live_research_spec_is_luad(runtime):
    settings, repository, artifacts = runtime
    orchestrator = LiveOrchestrator(settings, repository, artifacts)
    assert orchestrator.research_spec is LUAD_RESEARCH_V1
    assert orchestrator.research_spec.cohort.project_id == "TCGA-LUAD"


def test_alternate_research_spec_selects_only_its_project(runtime, monkeypatch):
    artifacts = runtime[2]
    spec = _test_spec("TCGA-LUSC", page_size=80, batch_size=80, max_cases=100)
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch, research_spec=spec)
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["spec_id"] == spec.spec_id
    assert run["selected_project_ids"] == ["TCGA-LUSC"]
    assert run["project_id"] == "TCGA-LUSC"
    assert run["acquisition"] == spec.as_dict()["acquisition"]
    states = repository.list_table("statistical_states", run_id)
    for row in states:
        state = json.loads(artifacts.read(repository.artifact(row["artifact_id"])["relative_path"]))
        assert state["scope"]["projects"] == ["TCGA-LUSC"]
        assert state["scope"]["research_spec"] == spec.as_dict()
        assert "TCGA-LUAD" not in state["scope"]["projects"]
    scientific_requests = [
        request for request in holder["transport"].requests
        if request.endpoint.name in {"top_mutated_genes_by_project", "cases", "files"}
    ]
    assert scientific_requests
    assert all("TCGA-LUSC" in str(request.params) for request in scientific_requests)


def test_large_cohort_is_paged_batched_and_merged_deterministically(runtime, monkeypatch):
    artifacts = runtime[2]
    spec = _test_spec()
    replay_options = {"project_case_counts": {"TCGA-LUAD": 520}, "drop_value_columns": 1}
    first, first_holder, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec, **replay_options,
    )
    first_run = first.run()
    second, _, _ = _orchestrator(runtime, monkeypatch, research_spec=spec, **replay_options)
    second_run = second.run()
    assert repository.get_run(first_run)["status"] == "COMPLETED"
    requests = first_holder["transport"].requests
    case_requests = [request for request in requests if request.endpoint.name == "cases"]
    assert [dict(request.params)["from"] for request in case_requests] == ["0", "200", "400"]
    expression_requests = [
        request for request in requests
        if request.endpoint.name in {"gene_expression_availability", "gene_expression_values"}
    ]
    assert len(expression_requests) == 6
    assert all(len(request.body["case_ids"]) <= 200 for request in expression_requests)
    assert not any(request.endpoint.name == "gene_expression_gene_selection" for request in requests)

    first_states = repository.list_table("statistical_states", first_run)
    second_states = repository.list_table("statistical_states", second_run)
    assert sorted(row["state_hash"] for row in first_states) == sorted(row["state_hash"] for row in second_states)
    state = json.loads(artifacts.read(repository.artifact(first_states[0]["artifact_id"])["relative_path"]))
    expression = state["expression"]["project_results"][0]
    assert expression["local"]["n_returned"]["value"] == 517
    assert expression["local"]["n_missing"]["value"] == 3
    assert expression["coverage"]["examined_cases"]["value"] == 520
    assert expression["provider"] is None
    assert expression["provider_unavailable_reason"] == "BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE"


@pytest.mark.parametrize(
    ("spec", "replay_options", "reason"),
    [
        (_test_spec(max_cases=300), {}, "COHORT_CASE_LIMIT_EXCEEDED"),
        (_test_spec(), {"duplicate_case_across_pages": True}, "DUPLICATE_CASE_ID"),
        (_test_spec(), {"inconsistent_case_total_after_first": True}, "CASE_TOTAL_INCONSISTENT"),
        (_test_spec(), {"inconsistent_case_offset_after_first": True}, "CASE_PAGE_OFFSET_INCONSISTENT"),
    ],
)
def test_invalid_case_pagination_fails_closed(runtime, monkeypatch, spec, replay_options, reason):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, research_spec=spec,
        project_case_counts={"TCGA-LUAD": 520}, **replay_options,
    )
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["outcome_reason"] == reason


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
    assert all(row["projection_version"] == "jev-state-projection-v2" for row in projections)
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
            "evidence_quality_adequate", "mutation_evidence_coherent", "expression_evidence_coherent",
            "signal_explained_by_coverage", "unresolved_uncertainty_material",
            "warrants_deeper_investigation", "dominant_limitation",
        }
        assert vector["applicability"]["dominant_limitation"]["applicable"] is True

    rankings = client.get(f"/api/runs/{run_id}/rankings").json()
    assert rankings["baseline"]["policy_version"] == "baseline-wide-v2"
    assert rankings["jev"]["policy_version"] == "wide-policy-v2"
    assert len(rankings["baseline"]["entries"]) == 2
    assert len(rankings["jev"]["entries"]) == 2
    assert rankings["jev"]["admitted_state_ids"]
    assert rankings["jev"]["admission"]["decision"] == "ADMIT"
    assert rankings["baseline"]["admitted_state_ids"] == []

    candidates = client.get(f"/api/runs/{run_id}/candidates").json()["items"]
    assert len(candidates) == 2
    assert all(candidate["status"] == "WIDE_EVALUATED" for candidate in candidates)
    assert all(candidate["summary"]["wide_evaluation_id"] for candidate in candidates)

    events = [event["type"] for event in repository.events(run_id, 0, 500)["items"]]
    for event_type in ("JEV_PROJECTION_CREATED", "JEV_WIDE_STARTED", "JEV_WIDE_STATE_EVALUATED",
                       "WIDE_RANKING_COMPLETED", "JEV_WIDE_COMPLETED", "CANDIDATE_PROMOTED"):
        assert event_type in events
    ranking_event = next(
        event for event in repository.events(run_id, 0, 500)["items"]
        if event["type"] == "WIDE_RANKING_COMPLETED"
    )
    assert ranking_event["data"]["admission_decision"] == "ADMIT"
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
    assert run["selected_project_ids"] == ["TCGA-LUAD"], "only the explicit LUAD cohort may be selected"
    assert "TCGA-LUSC" not in run["selected_project_ids"], "LUAD and LUSC are never pooled"
    assert run["counts"]["states_generated"] == 2
    assert run["provider_usage"]["jev_calls"] == 0
    assert run["provider_usage"]["llm_calls"] == 0

    states = repository.list_table("statistical_states", run_id)
    assert len(states) == 2
    assert all(row["disposition"] == "GENERATED" for row in states)
    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"] for row in states}
    gene_one = summaries[GENES[0]]
    assert gene_one["affected_case_total"]["value"] == 20
    assert gene_one["top_project_share"]["availability"] == "NOT_APPLICABLE"
    assert gene_one["top_project_share"]["value"] is None
    assert gene_one["projects_with_mutation_observation"] == 1
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
    assert body["scope"]["domain"] == "lung cancer"
    assert body["scope"]["cohort"] == "TCGA-LUAD"
    assert body["scope"]["projects"] == ["TCGA-LUAD"]
    assert body["scope"]["comparability"]["within_cohort"]["status"] == "UNVERIFIED"
    assert body["scope"]["comparability"]["cross_project"]["status"] == "NOT_APPLICABLE"
    assert body["cross_project"]["direction"] == "NOT_EXAMINED"
    assert body["cross_project"]["comparability_status"] == "NOT_APPLICABLE"
    assert body["provenance"]["gdc_release"] == "Data Release TEST - 2026-01-01"
    assert len(body["provenance"]["methods"]) == len(METHODS)
    assert body["quality"]["duplicate_checks"] == "PASS"
    assert body["quality"]["acquisition_completeness"] == "COMPLETE"
    assert body["quality"]["scientific_sufficiency"] in {"PARTIAL", "SUFFICIENT"}
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
    assert names.count("cases") == 1
    assert names.count("gene_expression_values") == 1
    assert len(names) <= 20, "replay sweep must stay bounded"


def test_missing_value_columns_stay_visible_in_state(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, drop_value_columns=2)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    states = repository.list_table("statistical_states", run_id)
    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"] for row in states}
    assert summaries[GENES[0]]["expression_availability"] == "OBSERVED"

    client = TestClient(create_app())
    state = client.get(f"/api/states/{states[0]['state_id']}").json()
    expression = {row["project_id"]: row for row in state["expression"]["project_results"]}["TCGA-LUAD"]
    assert expression["availability"] == "PARTIAL", "two missing case columns must keep the lane PARTIAL"
    assert expression["local"]["n_missing"]["value"] == 2
    assert expression["local"]["n_returned"]["value"] == 98
    assert expression["coverage"]["returned_case_columns"]["value"] == 98
    assert expression["coverage"]["valid_measurements"]["value"] == 98
    assert expression["coverage"]["missing_measurements"]["value"] == 2
    assert len(expression["local"]["missing_case_ids"]) == 2
    assert state["quality"]["acquisition_completeness"] == "COMPLETE"
    assert state["quality"]["scientific_sufficiency"] == "PARTIAL"
    assert any("not returned" in entry for entry in state["quality"]["missingness"])


def test_project_without_expression_values_skips_expression_calls(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch,
                                                     empty_expression_projects={"TCGA-LUAD"})
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    assert run["coverage"] == "COMPLETE_FOR_SCOPE", "an observed absence of expression data is not a partial retrieval"
    states = repository.list_table("statistical_states", run_id)
    summaries = {row["summary"]["entity"]["gene_id"]: row["summary"] for row in states}
    assert summaries[GENES[0]]["expression_availability"] == "INSUFFICIENT"
    assert summaries[GENES[0]]["coverage_imbalance"] is True, "zero expression values for the cohort is flagged"
    names = [request.endpoint.name for request in holder["transport"].requests]
    assert names.count("gene_expression_availability") == 1
    assert names.count("gene_expression_gene_selection") == 0
    assert names.count("gene_expression_values") == 0


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
    assert run["outcome_reason"] == "CASE_TOTAL_INCONSISTENT"
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
    states = [_build([_frame("TCGA-LUAD")])]
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


def test_run_wide_evaluation_enforces_configured_state_cap(runtime):
    settings, repository, artifacts = runtime
    adapter = StubAdapter()
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("wide-state-cap", mode="LIVE", fixture_id=None, fixture_version=None)
    states = [_build([_frame("TCGA-LUAD")], state_id="state-a"),
              _build([_frame("TCGA-LUAD")], state_id="state-b")]
    for state in states:
        _register_state(artifacts, repository, run_id, state)
    emitted: list[str] = []

    def emit(event_run_id, event_type, key, message, **kwargs):
        emitted.append(event_type)
        return repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    def publish_json(pub_run_id, relative_path, payload, purpose):
        return artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE",
        repository=repository, jev_service=service, emit=emit, publish_json=publish_json,
        max_states=1,
    )
    assert adapter.calls == 1, "the configured Jev state cap must bound provider work"
    assert "JEV_WIDE_STATE_CAP_ENFORCED" in emitted
    cap_event = next(
        event for event in repository.events(run_id, 0, 100)["items"]
        if event["type"] == "JEV_WIDE_STATE_CAP_ENFORCED"
    )
    assert cap_event["data"]["cap"] == 1
    assert cap_event["data"]["skipped_state_ids"] == ["state-b"]
    skipped_entry = next(entry for entry in result["jev"]["entries"] if entry["state_id"] == "state-b")
    assert skipped_entry["excluded_reason"] == "EVALUATION_MISSING"


def test_run_wide_evaluation_abstains_and_defers_provider_failures(runtime):
    settings, repository, artifacts = runtime
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: StubAdapter(fail=True))
    run_id = repository.create_run("wide-provider-failure", mode="LIVE", fixture_id=None, fixture_version=None)
    state = _build([_frame("TCGA-LUAD")])
    states = [state]
    _register_state(artifacts, repository, run_id, state)

    def emit(event_run_id, event_type, key, message, **kwargs):
        return repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    def publish_json(pub_run_id, relative_path, payload, purpose):
        return artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE",
        repository=repository, jev_service=service, emit=emit, publish_json=publish_json,
    )
    assert result["jev"]["admission"]["decision"] == "ABSTAIN"
    assert result["jev"]["entries"][0]["excluded_reason"] == "EVALUATION_FAILED"
    assert result["promoted"] == []
    ranking_event = next(
        event for event in repository.events(run_id, 0, 100)["items"]
        if event["type"] == "WIDE_RANKING_COMPLETED"
    )
    assert ranking_event["data"]["deferred_state_ids"] == [state["state_id"]]
    assert ranking_event["data"]["admission_decision"] == "ABSTAIN"


class _MalformedFirstStateAdapter(StubAdapter):
    """One state gets a malformed provider response; the rest evaluate normally."""

    def evaluate(self, state, definitions):
        if self.calls == 0:
            self.calls += 1
            raise JevProviderError("PROVIDER_RESPONSE_MALFORMED",
                                   "provider response could not be converted to owned answers")
        return super().evaluate(state, definitions)


def test_one_malformed_provider_response_does_not_abort_the_run(runtime):
    settings, repository, artifacts = runtime
    adapter = _MalformedFirstStateAdapter()
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("wide-malformed", mode="LIVE", fixture_id=None, fixture_version=None)
    states = [_build([_frame("TCGA-LUAD")], state_id="state-a"),
              _build([_frame("TCGA-LUAD")], state_id="state-b")]
    for state in states:
        _register_state(artifacts, repository, run_id, state)

    def emit(event_run_id, event_type, key, message, **kwargs):
        return repository.append_event(event_run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    def publish_json(pub_run_id, relative_path, payload, purpose):
        return artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    result = run_wide_evaluation(
        run_id=run_id, states=states, coverage="COMPLETE_FOR_SCOPE",
        repository=repository, jev_service=service, emit=emit, publish_json=publish_json,
    )
    evaluations = repository.page_child("jev_evaluations", run_id, 10, None, {"purpose": "WIDE"})["items"]
    by_state = {row["input_ref_id"]: row["vector"] for row in evaluations}
    assert sorted(by_state) == ["state-a", "state-b"], "both states must be evaluated"
    failed_state = "state-a" if by_state["state-a"]["error"] else "state-b"
    healthy_state = "state-b" if failed_state == "state-a" else "state-a"
    assert by_state[failed_state]["error"]["code"] == "PROVIDER_RESPONSE_MALFORMED"
    assert by_state[healthy_state]["error"] is None
    assert len(by_state[healthy_state]["answers"]) == 7

    types = [event["type"] for event in repository.events(run_id, 0, 200)["items"]]
    assert types.count("JEV_EVALUATION_FAILED") == 1
    assert types.count("JEV_WIDE_STATE_EVALUATED") == 1
    assert "WIDE_RANKING_COMPLETED" in types and "JEV_WIDE_COMPLETED" in types
    assert result["jev"]["admission"]["decision"] == "ADMIT"
    assert [promotion["state_id"] for promotion in result["promoted"]] == [healthy_state]
    run = repository.get_run(run_id)
    assert run["status"] != "FAILED", "the run must continue after one deferred state"
    assert run["provider_usage"]["jev_calls"] == 2, "a failed provider attempt is still a provider call"


def test_live_replay_links_scientific_sources_to_the_responses_that_supplied_them(runtime, monkeypatch):
    artifacts = runtime[2]
    orchestrator, holder, repository = _orchestrator(runtime, monkeypatch)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    issued = {request.request_hash() for request in holder["transport"].requests}
    received = {artifact.sha256 for artifact in holder["transport"].published}
    assert issued and received

    checked = 0
    for row in repository.list_table("statistical_states", run_id):
        state = json.loads(artifacts.read(repository.artifact(row["artifact_id"])["relative_path"]))
        for source in state["provenance"]["sources"]:
            assert source["request_id"], "every scientific source must link to its acquisition attempt"
            assert source["attempt_no"] >= 1
            assert source["from_cache"] is False
            assert source["normalized_request_hash"] in issued, "the logical request must be a request the run issued"
            assert source["response_sha256"] in received, "the source must name a response the run received"
            checked += 1
    assert checked >= len(repository.list_table("statistical_states", run_id))


def _response_meta(endpoint: str) -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="POST", request_hash="h", response_sha256="s",
                        artifact_id=None, retrieved_at="2026-09-23T00:00:00Z", source_release=None,
                        completeness="COMPLETE")


def test_expression_availability_merge_keeps_observed_and_missing_genes_disjoint():
    case_ids = ["P1-case-1", "P1-case-2"]
    gene_ids = list(GENES)
    first = parse_expression_availability(
        availability_body(case_ids[:1], gene_ids), _response_meta("/gene_expression/availability"),
        expected_cases=case_ids[:1], expected_genes=gene_ids,
    )
    second = parse_expression_availability(
        availability_body(case_ids[1:], gene_ids, omit_genes=True),
        _response_meta("/gene_expression/availability"),
        expected_cases=case_ids[1:], expected_genes=gene_ids,
    )
    assert second.missing_genes == gene_ids, "the second batch omitted every gene detail"

    merged = _merge_expression_availability(case_ids, gene_ids,
                                            [(case_ids[:1], first), (case_ids[1:], second)])
    assert merged.genes == {gene_id: True for gene_id in gene_ids}
    assert merged.missing_genes == [], "a gene observed by any batch is not a missing gene"
    assert set(merged.genes) & set(merged.missing_genes) == set()
    assert merged.missing_cases == []

    absent = parse_expression_availability(
        availability_body(case_ids, gene_ids, omit_genes=True),
        _response_meta("/gene_expression/availability"),
        expected_cases=case_ids, expected_genes=gene_ids,
    )
    merged_absent = _merge_expression_availability(case_ids, gene_ids, [(case_ids, absent)])
    assert merged_absent.genes == {}
    assert merged_absent.missing_genes == gene_ids, "a gene absent from every batch stays missing"
