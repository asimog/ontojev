"""EvaluationRecord and read_evaluation_record binding validation fails closed on mismatch."""

from __future__ import annotations

import hashlib

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.jev.contracts import ValidatedAnswers
from cancerjev.jev.projection import build_projection, projection_hash
from cancerjev.jev.questions import applicability_map, wide_question_set_hash
from cancerjev.storage.readers import ScientificReadError, read_evaluation_record
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import service_context


def _wide_evaluation(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    evaluation = service.evaluate_record(run_id=context["run_id"], state=context["state"],
                                         emit=context["emit"])
    return context, evaluation


def _republish_vector(context, evaluation, mutate) -> None:
    repository = context["repository"]
    row = repository.get_evaluation(evaluation.evaluation_id)
    vector = row["vector"]
    mutate(vector)
    encoded = canonical_json(vector)
    artifact = context["artifacts"].publish(
        f"replayed/{hashlib.sha256(encoded).hexdigest()[:16]}.json", encoded,
        "application/json", "jev-evaluation",
    )
    repository.register_artifact(artifact, context["run_id"])
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER jev_evaluations_no_update")
        connection.execute(
            "UPDATE jev_evaluations SET vector_json=?, artifact_id=? WHERE evaluation_id=?",
            (encoded.decode(), artifact.artifact_id, evaluation.evaluation_id),
        )


def test_read_evaluation_record_rehydrates_the_original_binding(runtime):
    context, evaluation = _wide_evaluation(runtime)
    stored = read_evaluation_record(context["repository"], context["artifacts"],
                                    evaluation.evaluation_id)
    assert stored.error_code is None
    assert isinstance(stored.answers, ValidatedAnswers)
    assert stored.answers.probability("warrants_deeper_investigation") == 0.90
    bound = stored.artifact.boundary_representation()
    record = context["state"]
    assert bound["resolved_model"] == "jev-1.13.0"
    assert bound["question_hash"] == wide_question_set_hash()
    assert bound["projection_hash"] == projection_hash(build_projection(record))
    assert bound["applicability"] == applicability_map(build_projection(record))


@pytest.mark.parametrize(("field", "value"), [
    ("resolved_model", "wrong-model-1.0"),
    ("question_hash", "0" * 64),
    ("projection_hash", "0" * 64),
    ("applicability", {}),
])
def test_binding_mismatch_fails_closed(runtime, field, value):
    context, evaluation = _wide_evaluation(runtime)
    _republish_vector(context, evaluation, lambda vector: vector.__setitem__(field, value))
    with pytest.raises(ScientificReadError) as exc:
        read_evaluation_record(context["repository"], context["artifacts"],
                               evaluation.evaluation_id)
    assert exc.value.code in {"RECORD_BINDING_MISMATCH", "INVALID_EVALUATION"}


def test_model_column_mismatch_fails_closed(runtime):
    context, evaluation = _wide_evaluation(runtime)
    repository = context["repository"]
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER jev_evaluations_no_update")
        connection.execute("UPDATE jev_evaluations SET model=? WHERE evaluation_id=?",
                           ("swapped-model-2.0", evaluation.evaluation_id))
    with pytest.raises(ScientificReadError) as exc:
        read_evaluation_record(repository, context["artifacts"], evaluation.evaluation_id)
    assert exc.value.code == "RECORD_BINDING_MISMATCH"


def test_failed_evaluation_cannot_carry_answers(runtime):
    context, evaluation = _wide_evaluation(runtime)
    row = context["repository"].get_evaluation(evaluation.evaluation_id)
    answers = row["vector"]["answers"]

    def mutate(vector):
        vector["error"] = {"code": "PROVIDER_ERROR", "detail": "synthetic"}
        vector["answers"] = answers

    _republish_vector(context, evaluation, mutate)
    with pytest.raises(ScientificReadError) as exc:
        read_evaluation_record(context["repository"], context["artifacts"],
                               evaluation.evaluation_id)
    assert exc.value.code == "RECORD_BINDING_MISMATCH"
