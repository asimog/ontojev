from __future__ import annotations

import dataclasses

import cancerjev.jev.service as service_module
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.jev.projection import build_projection, projection_hash
from cancerjev.jev.questions import applicability_map
from cancerjev.jev.service import JevService
from tests.jev.stub_adapter import StubAdapter
from tests.science.test_methods import _build, _frame

EVALUATION_FIELDS = (
    "evaluation_id", "mode", "purpose", "input_ref_kind", "input_ref_id", "source_state_hash",
    "projection_id", "projection_version", "projection_hash", "question_set_version", "question_hash",
    "question_definitions_ref", "requested_model", "resolved_model", "adapter_version", "answers",
    "applicability", "raw_answers_hash", "request_id", "usage", "latency_ms",
    "cache_source_evaluation_id", "error", "routing_policy_version", "artifact_id",
)


def _state() -> dict:
    return _build([_frame("P1"), _frame("P2"), _frame("P3")])


def _register_state(artifacts, repository, run_id: str, state: dict) -> None:
    artifact = artifacts.publish(f"runs/{run_id}/statistical_states/{state['state_id']}.json",
                                 canonical_json(state), "application/json", "statistical-state")
    repository.append_event(
        run_id, event_type="STATISTICAL_STATE_CREATED", idempotency_key=f"state:{state['state_id']}",
        message="test state", stage="STATE_GENERATION",
        data={"state_id": state["state_id"], "state_hash": state["state_hash"]},
        registrations=[
            repository.artifact_registration(artifact, run_id),
            ("INSERT INTO statistical_states(state_id,run_id,state_hash,artifact_id,disposition,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
             (state["state_id"], run_id, state["state_hash"], artifact.artifact_id, "GENERATED",
              canonical_json({"entity": state["entity"]}).decode(), utc_now())),
        ],
    )


def _service(runtime, adapter: StubAdapter) -> tuple[JevService, dict]:
    settings, repository, artifacts = runtime
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    run_id = repository.create_run("jev-test", mode="LIVE", fixture_id=None, fixture_version=None)
    _register_state(artifacts, repository, run_id, _state())

    def emit(run_id_arg, event_type, key, message, **kwargs):
        return repository.append_event(run_id_arg, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)

    return service, {"run_id": run_id, "repository": repository, "artifacts": artifacts, "emit": emit}


def test_evaluate_persists_projection_evaluation_and_events(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    state = _state()
    evaluation = service.evaluate(run_id=context["run_id"], state=state, emit=context["emit"])
    assert evaluation["error"] is None
    assert evaluation["resolved_model"] == "jev-1.13.0"
    assert evaluation["requested_model"] == "jev-1.13.0"
    assert evaluation["projection_hash"] == projection_hash(build_projection(state))
    assert evaluation["answers"]["pattern_type"]["choice"] == "WIDESPREAD_RECURRENCE"
    assert evaluation["usage"] == {"input_tokens": 1200, "output_tokens": 60}
    assert evaluation["latency_ms"] == 250
    assert evaluation["cache_source_evaluation_id"] is None
    assert evaluation["question_set_version"] == "wide-v2"
    assert adapter.calls == 1

    repository = context["repository"]
    row = repository.get_evaluation(evaluation["evaluation_id"])
    assert row is not None and row["model"] == "jev-1.13.0"
    assert row["vector"]["applicability"]["warrants_deeper_investigation"]["applicable"] is True
    projections = repository.page_projections(context["run_id"], 10, None)
    assert len(projections["items"]) == 1
    events = [event["type"] for event in repository.events(context["run_id"], 0, 100)["items"]]
    assert "JEV_PROJECTION_CREATED" in events
    assert "JEV_WIDE_STATE_EVALUATED" in events


def test_cache_hit_reuses_judgment_without_provider_call(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    first = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    second = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    assert adapter.calls == 1
    assert second["cache_source_evaluation_id"] == first["evaluation_id"]
    assert second["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert second["latency_ms"] == 0
    assert second["answers"] == first["answers"]
    assert second["evaluation_id"] != first["evaluation_id"]
    repository = context["repository"]
    events = repository.events(context["run_id"], 0, 100)["items"]
    evaluated = [event for event in events if event["type"] == "JEV_WIDE_STATE_EVALUATED"]
    assert evaluated[-1]["data"]["cache"] is True
    assert evaluated[-1]["data"]["provider_attempted"] is False
    run = repository.get_run(context["run_id"])
    assert run["provider_usage"]["jev_calls"] == 1, "a cache hit must not count as a provider call"


def test_cache_is_shared_across_runs_but_not_across_models(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    second_run = context["repository"].create_run("jev-test-2", mode="LIVE", fixture_id=None,
                                                  fixture_version=None)
    reused = service.evaluate(run_id=second_run, state=_state(), emit=context["emit"])
    assert reused["cache_source_evaluation_id"] is not None
    assert adapter.calls == 1

    settings, repository, artifacts = runtime
    other = StubAdapter(model="jev-1.12.0")
    other_settings = dataclasses.replace(settings, jev_model="jev-1.12.0")
    other_service = JevService(other_settings, repository, artifacts, adapter_factory=lambda: other)
    fresh = other_service.evaluate(run_id=second_run, state=_state(), emit=context["emit"])
    assert fresh["cache_source_evaluation_id"] is None
    assert other.calls == 1


def test_provider_failure_fails_closed_without_fabricated_defaults(runtime):
    adapter = StubAdapter(fail=True)
    service, context = _service(runtime, adapter)
    evaluation = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    assert evaluation["error"]["code"] == "PROVIDER_ERROR"
    assert evaluation["answers"] == {}
    assert evaluation["usage"] == {"input_tokens": None, "output_tokens": None}
    assert evaluation["latency_ms"] is None
    assert evaluation["resolved_model"] is None
    repository = context["repository"]
    assert repository.jev_cache_get.__self__ is repository
    events = [event["type"] for event in repository.events(context["run_id"], 0, 100)["items"]]
    assert "JEV_EVALUATION_FAILED" in events
    assert "JEV_WIDE_STATE_EVALUATED" not in events


def test_invalid_provider_answer_fails_closed(runtime):
    adapter = StubAdapter(override={
        "warrants_deeper_investigation": {"kind": "noul", "probability_yes": 1.5},
    })
    service, context = _service(runtime, adapter)
    evaluation = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    assert evaluation["error"]["code"] == "INVALID_PROBABILITY"


def test_projection_is_registered_once_per_state_and_version(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    state = _state()
    service.evaluate(run_id=context["run_id"], state=state, emit=context["emit"])
    service.evaluate(run_id=context["run_id"], state=state, emit=context["emit"])
    projections = context["repository"].page_projections(context["run_id"], 10, None)
    assert len(projections["items"]) == 1
    assert projections["items"][0]["projection_version"] == "jev-state-projection-v1"


def test_evaluation_record_and_event_contract_is_unchanged(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    state = _state()
    evaluation = service.evaluate(run_id=context["run_id"], state=state, emit=context["emit"])
    assert set(evaluation) == set(EVALUATION_FIELDS)
    assert evaluation["applicability"] == applicability_map(build_projection(state))
    repository = context["repository"]
    assert repository.get_evaluation(evaluation["evaluation_id"])["vector"] == {
        key: value for key, value in evaluation.items() if key != "artifact_id"
    }
    events = repository.events(context["run_id"], 0, 100)["items"]
    jev_events = [event for event in events if event["type"].startswith("JEV_")]
    assert [event["type"] for event in jev_events] == ["JEV_PROJECTION_CREATED", "JEV_WIDE_STATE_EVALUATED"]
    assert jev_events[0]["idempotency_key"] == f"projection:{evaluation['projection_id']}"
    assert jev_events[1]["idempotency_key"] == f"jev-wide:{evaluation['evaluation_id']}"
    assert jev_events[1]["data"]["applicability"] == evaluation["applicability"]
    assert jev_events[1]["data"]["judgment_vector"] == evaluation["answers"]


def test_failure_recording_reuses_the_projection_without_rebuilding_it(runtime, monkeypatch):
    adapter = StubAdapter(fail=True)
    service, context = _service(runtime, adapter)
    state = _state()
    calls: list[str] = []
    original = service_module.build_projection

    def counting_build_projection(state_argument):
        calls.append(state_argument["state_id"])
        return original(state_argument)

    monkeypatch.setattr(service_module, "build_projection", counting_build_projection)
    evaluation = service.evaluate(run_id=context["run_id"], state=state, emit=context["emit"])
    assert calls == [state["state_id"]], "failure recording must not rebuild the projection"
    assert evaluation["error"]["code"] == "PROVIDER_ERROR"
    assert set(evaluation) == set(EVALUATION_FIELDS)
    assert evaluation["applicability"] == applicability_map(original(state))
    repository = context["repository"]
    assert repository.get_evaluation(evaluation["evaluation_id"])["vector"] == {
        key: value for key, value in evaluation.items() if key != "artifact_id"
    }
    events = repository.events(context["run_id"], 0, 100)["items"]
    jev_events = [event for event in events if event["type"].startswith("JEV_")]
    assert [event["type"] for event in jev_events] == ["JEV_PROJECTION_CREATED", "JEV_EVALUATION_FAILED"]
    assert jev_events[1]["idempotency_key"] == f"jev-wide:{evaluation['evaluation_id']}:failed"
