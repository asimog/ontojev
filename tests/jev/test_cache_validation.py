import pytest

from cancerjev.domain.events import canonical_json
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import _service, _state


@pytest.mark.parametrize("field,value", [
    ("answers", []), ("answers", {}), ("resolved_model", "wrong-1.0"),
    ("requested_model", "wrong-1.0"), ("question_hash", "0" * 64),
    ("projection_hash", "0" * 64), ("applicability", {}), ("adapter_version", "unknown"),
])
def test_invalid_cache_abstains_without_replacement_call(runtime, field, value):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    first = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    repository = context["repository"]
    row = repository.get_evaluation(first["evaluation_id"])
    vector = row["vector"]
    vector[field] = value
    # A coherently republished artifact exercises semantic validation, not just hash checks.
    artifact = context["artifacts"].publish("invalid-cache.json", canonical_json(vector), "application/json", "jev-evaluation")
    repository.register_artifact(artifact, context["run_id"])
    with repository.database.connect(write=True) as connection:
        # Emulate corrupt persisted data; production immutable triggers remain intact.
        connection.execute("DROP TRIGGER jev_evaluations_no_update")
        connection.execute("UPDATE jev_evaluations SET vector_json=?,artifact_id=? WHERE evaluation_id=?",
                           (canonical_json(vector).decode(), artifact.artifact_id, first["evaluation_id"]))
    second = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    assert second["error"]["code"] == "UNUSABLE_CACHE"
    assert second["answers"] == {}
    assert adapter.calls == 1
    cache_key = service._cache_key(projection_hash_value=first["projection_hash"],
                                   question_set_hash_value=first["question_hash"], requested_model=first["requested_model"])
    assert repository.jev_cache_get(cache_key) == first["evaluation_id"]
    assert repository.events(context["run_id"], 0, 100)["items"][-1]["data"]["provider_attempted"] is False


@pytest.mark.parametrize("target", ["questions", "projection", "evaluation"])
def test_missing_cache_artifact_never_calls_provider(runtime, target):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    first = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    if target == "questions":
        artifact_id = first["question_definitions_ref"]
    elif target == "projection":
        artifact_id = context["repository"].find_projection(_state()["state_id"], first["projection_version"])["artifact_id"]
    else:
        artifact_id = first["artifact_id"]
    metadata = context["repository"].artifact(artifact_id)
    (context["artifacts"].data_dir / metadata["relative_path"]).unlink()
    second = service.evaluate(run_id=context["run_id"], state=_state(), emit=context["emit"])
    assert second["error"]["code"] == "UNUSABLE_CACHE"
    assert adapter.calls == 1
