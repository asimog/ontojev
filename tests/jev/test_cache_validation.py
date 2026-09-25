"""Cache-origin validation: a corrupted or foreign origin is refused, never re-called."""

from __future__ import annotations

import hashlib

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.jev.projection import PROJECTION_VERSION
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import (
    GENE,
    PROJECT,
    register_state,
    service_context,
    state_record,
    statistical_state,
)

INVALID_CACHE_MUTATIONS = [
    ("answers", []),
    ("answers", {}),
    ("resolved_model", "wrong-model-1.0"),
    ("requested_model", "wrong-model-1.0"),
    ("question_hash", "0" * 64),
    ("projection_hash", "0" * 64),
    ("applicability", {}),
    ("adapter_version", "unknown-adapter"),
]


def _replace_vector(context, evaluation, mutate) -> None:
    """Republish a mutated vector and point the immutable row at it (test-only surgery)."""
    repository = context["repository"]
    row = repository.get_evaluation(evaluation.evaluation_id)
    vector = row["vector"]
    mutate(vector)
    encoded = canonical_json(vector)
    artifact = context["artifacts"].publish(
        f"invalid-cache/{hashlib.sha256(encoded).hexdigest()[:16]}.json", encoded,
        "application/json", "jev-evaluation",
    )
    repository.register_artifact(artifact, context["run_id"])
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER jev_evaluations_no_update")
        connection.execute(
            "UPDATE jev_evaluations SET vector_json=?, artifact_id=? WHERE evaluation_id=?",
            (encoded.decode(), artifact.artifact_id, evaluation.evaluation_id),
        )


def _cache_key(service, evaluation) -> str:
    vector = evaluation.boundary_representation()
    return service._cache_key(projection_hash_value=vector["projection_hash"],
                              question_set_hash_value=vector["question_hash"],
                              requested_model=vector["requested_model"])


@pytest.mark.parametrize(("field", "value"), INVALID_CACHE_MUTATIONS)
def test_invalid_cache_is_refused_without_a_replacement_provider_call(runtime, field, value):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    first = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                    emit=context["emit"])
    _replace_vector(context, first, lambda vector: vector.__setitem__(field, value))

    second = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                     emit=context["emit"])
    assert second.error_code == "UNUSABLE_CACHE"
    assert second.answers is None
    assert second.boundary_representation()["answers"] == {}
    assert second.boundary_representation()["error"]["code"] == "UNUSABLE_CACHE"
    assert adapter.calls == 1, "an invalid cache origin must never trigger a replacement call"
    repository = context["repository"]
    assert repository.jev_cache_get(_cache_key(service, first)) == first.evaluation_id, \
        "the original cache entry must stay intact"
    events = repository.events(context["run_id"], 0, 200)["items"]
    assert events[-1]["type"] == "JEV_EVALUATION_FAILED"
    assert events[-1]["data"]["provider_attempted"] is False


@pytest.mark.parametrize("target", ["questions", "projection", "evaluation"])
def test_missing_cache_artifact_never_calls_provider(runtime, target):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    first = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                    emit=context["emit"])
    repository = context["repository"]
    vector = first.boundary_representation()
    if target == "questions":
        artifact_id = vector["question_definitions_ref"]
    elif target == "projection":
        artifact_id = repository.find_projection(context["state"].state_id,
                                                 PROJECTION_VERSION)["artifact_id"]
    else:
        artifact_id = first.artifact_id
    metadata = repository.artifact(artifact_id)
    (context["artifacts"].data_dir / metadata["relative_path"]).unlink()

    second = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                     emit=context["emit"])
    assert second.error_code == "UNUSABLE_CACHE"
    assert second.answers is None
    assert adapter.calls == 1, "a missing artifact must never trigger a replacement call"


def test_foreign_cache_origin_is_refused_without_a_provider_call(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    repository = context["repository"]
    other = state_record("state-2", statistical_state(counts={PROJECT: {GENE.gene_id: 7}}))
    register_state(repository, context["artifacts"], context["run_id"], other)
    other_evaluation = service.evaluate_record(run_id=context["run_id"], state=other,
                                               emit=context["emit"])
    first = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                    emit=context["emit"])
    cache_key = _cache_key(service, first)
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER jev_cache_no_update")
        connection.execute("UPDATE jev_cache SET evaluation_id=? WHERE cache_key=?",
                           (other_evaluation.evaluation_id, cache_key))

    second = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                     emit=context["emit"])
    assert second.error_code == "UNUSABLE_CACHE"
    assert second.answers is None
    assert adapter.calls == 2, "two first-time evaluations only; the foreign origin is refused"
