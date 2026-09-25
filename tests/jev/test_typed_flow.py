"""The typed handoff: state -> projection -> answers -> admission, revision -> judgment."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cancerjev.domain.envelopes import HypothesisRecord, StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.hypotheses import HypothesisDraft
from cancerjev.jev.contracts import EvaluationRecord, ValidatedAnswers
from cancerjev.jev.projection import PROJECTION_VERSION, build_projection, projection_hash
from cancerjev.research import deep
from cancerjev.research.nextmove import DEEP_POLICY_VERSION
from cancerjev.research.ranking import baseline_ranking, jev_ranking
from cancerjev.science.actions import ACTION_REGISTRY
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import deep_context, service_context


def test_typed_state_reaches_projection_answers_and_admission(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    record = context["state"]
    assert isinstance(record, StateRecord)

    first = service.evaluate_record(run_id=context["run_id"], state=record, emit=context["emit"])
    second = service.evaluate_record(run_id=context["run_id"], state=record, emit=context["emit"])
    assert isinstance(first, EvaluationRecord)
    assert isinstance(first.answers, ValidatedAnswers)
    assert first.error_code is None and second.error_code is None
    assert first.boundary_representation()["projection_version"] == PROJECTION_VERSION
    assert first.boundary_representation()["projection_hash"] == \
        projection_hash(build_projection(record))
    assert adapter.calls == 1, "the second typed handoff must reuse the recorded judgment"
    assert second.answers == first.answers
    assert second.cache_source_evaluation_id == first.evaluation_id

    ranking = jev_ranking([record], [first])
    assert ranking["admission"]["decision"] == "ADMIT"
    assert ranking["admitted_state_ids"] == [record.state_id]
    entry = ranking["entries"][0]
    assert entry["qualified"] is True
    assert entry["dimensions"]["warrants_deeper_investigation"] == 0.90
    baseline = baseline_ranking([record])
    assert baseline["entries"][0]["state_id"] == record.state_id
    assert baseline["admitted_state_ids"] == []

    boundary = first.boundary_representation()
    boundary["answers"].clear()
    assert first.boundary_representation()["answers"], "the boundary must be decoded fresh"
    with pytest.raises(FrozenInstanceError):
        first.answers.answers = ()


def test_evidence_revision_reaches_deep_judgment_and_one_recorded_move(runtime):
    adapter = StubAdapter()
    context = deep_context(runtime, adapter)
    assert context["evidence"].revision.revision_index == 1
    outcome = deep.judge_evidence_revision(
        run_id=context["run_id"], candidate=context["candidate_evidence"],
        result=context["result"], jev_service=context["service"], emit=context["emit"],
    )
    assert outcome["deep_error_code"] is None
    assert outcome["deep_question_set_version"] == "deep-v1"
    assert outcome["deep_judgment_vector"]["revision_reliable"]["probability_yes"] == 0.90
    assert outcome["deep_judgment_vector"]["dominant_limitation"]["choice"] == "NONE"
    assert outcome["next_move"]["policy_version"] == DEEP_POLICY_VERSION
    assert outcome["next_move"]["move"] == "COMPLETE"
    assert outcome["next_move"]["reason_code"] == "INVESTIGATION_COMPLETE"
    assert outcome["next_move"]["executed"] is False
    assert adapter.calls == 1

    row = context["repository"].get_evaluation(outcome["deep_evaluation_id"])
    assert row["purpose"] == "DEEP"
    assert row["input_ref_kind"] == "EVIDENCE_STATE"
    assert row["input_ref_id"] == context["evidence"].evidence_state_id
    events = [event["type"] for event in
              context["repository"].events(context["run_id"], 0, 400)["items"]]
    assert "JEV_DEEP_EVIDENCE_JUDGED" in events
    assert "NEXT_MOVE_SELECTED" in events
    assert "NEXT_MOVE_DISPATCHED" not in events, "the policy never dispatches the move it records"


def test_generated_draft_reaches_hypothesis_review_without_becoming_evidence(runtime):
    adapter = StubAdapter()
    context = deep_context(runtime, adapter)
    draft = HypothesisDraft(
        label="GENERATED HYPOTHESIS — NOT EVIDENCE", generator="deterministic-template-v1",
        generator_model=None, statement="A bounded generated statement.",
        proposed_mechanism="A proposed mechanism.", predictions=("prediction",),
        contradicted_if=("contradiction",), distinguishing_tests=(),
        required_evidence=("required",), unsupported_assumptions=("assumption",),
    )
    hypothesis = HypothesisRecord("00000000-0000-0000-0000-000000000002",
                                  context["candidate"]["candidate_id"], draft)
    evaluation = context["service"].evaluate_hypothesis_record(
        run_id=context["run_id"], hypothesis=hypothesis, evidence=context["evidence"],
        eligible_actions=[ACTION_REGISTRY["CHECK_REVISION_FAITHFULNESS_V1"].payload()],
        emit=context["emit"],
    )
    assert evaluation.error_code is None
    assert evaluation.answers.probability("hypothesis_testable") == 0.80
    assert evaluation.answers.probability("hypothesis_exceeds_recorded_evidence") == 0.35
    vector = evaluation.boundary_representation()
    assert vector["purpose"] == "HYPOTHESIS"
    assert vector["input_ref_kind"] == "HYPOTHESIS"
    assert draft.statement not in canonical_json(vector).decode()
    assert draft.label not in canonical_json(vector).decode()
    assert adapter.calls == 1


def test_service_entrypoints_reject_legacy_dict_scientific_models(runtime):
    adapter = StubAdapter()
    service, context = service_context(runtime, adapter)
    assert not hasattr(service, "evaluate")
    assert not hasattr(service, "evaluate_evidence")
    assert not hasattr(service, "evaluate_hypothesis")

    legacy_state = {
        "state_id": "state-1", "state_hash": "a" * 64,
        "entity": {"gene_id": "ENSG00000141510", "symbol": "TP53"},
    }
    with pytest.raises((AttributeError, TypeError)):
        service.evaluate_record(run_id=context["run_id"], state=legacy_state,
                                emit=context["emit"])

    deep_ready = deep_context(runtime, adapter)
    with pytest.raises((AttributeError, TypeError)):
        deep_ready["service"].evaluate_evidence_record(
            run_id=deep_ready["run_id"],
            evidence={"evidence_state_id": "evidence-1", "evidence_hash": "f" * 64},
            eligible_actions=[], emit=deep_ready["emit"],
        )
    with pytest.raises((AttributeError, TypeError)):
        deep_ready["service"].evaluate_hypothesis_record(
            run_id=deep_ready["run_id"],
            hypothesis={"hypothesis_id": "hypothesis-1", "candidate_id": "candidate-1"},
            evidence=deep_ready["evidence"],
            eligible_actions=[ACTION_REGISTRY["CHECK_REVISION_FAITHFULNESS_V1"].payload()],
            emit=deep_ready["emit"],
        )
