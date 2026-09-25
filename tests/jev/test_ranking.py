"""Deterministic baseline ranking and bounded Jev admission over typed records."""

from __future__ import annotations

from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.jev.contracts import EvaluationRecord, QuestionApplicability, read_answers
from cancerjev.jev.questions import LIMITATION_ROSTER, WIDE_QUESTIONS
from cancerjev.research.ranking import (
    ADMISSION_MAX_CONFOUND,
    ADMISSION_MIN_QUALITY,
    ADMISSION_MIN_UNCERTAINTY,
    ADMISSION_MIN_WARRANTS,
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PROMOTION_LIMIT,
    baseline_ranking,
    jev_ranking,
)
from tests.jev.test_service import GENE, PROJECT, state_record, statistical_state


def _record(state_id: str, affected: int | None) -> StateRecord:
    counts = {PROJECT: {GENE.gene_id: affected}} if affected is not None else {PROJECT: {}}
    return state_record(state_id, statistical_state(counts=counts))


def _raw_answers(*, warrants: float = 0.9, uncertainty: float = 0.8, quality: float = 0.8,
                 confound: float = 0.2, inapplicable: tuple[str, ...] = ()) -> tuple[dict, dict]:
    probabilities = {
        option: (0.88 if option == "NONE" else 0.12 / (len(LIMITATION_ROSTER) - 1))
        for option in LIMITATION_ROSTER
    }
    answers = {
        "evidence_quality_adequate": {"kind": "noul", "probability_yes": quality},
        "mutation_evidence_coherent": {"kind": "noul", "probability_yes": 0.8},
        "expression_evidence_coherent": {"kind": "noul", "probability_yes": 0.8},
        "signal_explained_by_coverage": {"kind": "noul", "probability_yes": confound},
        "unresolved_uncertainty_material": {"kind": "noul", "probability_yes": uncertainty},
        "warrants_deeper_investigation": {"kind": "noul", "probability_yes": warrants},
        "dominant_limitation": {
            "kind": "choice", "choice": "NONE", "confidence": 0.8, "probabilities": probabilities,
        },
    }
    applicability = {
        question_id: {
            "applicable": question_id not in inapplicable,
            "reason": "TEST_RULE",
            "rule": "any_observation",
        }
        for question_id in answers
    }
    return answers, applicability


def _evaluation(record: StateRecord, *, error: dict | None = None, cache_source: str | None = None,
                **kwargs) -> EvaluationRecord:
    answers, applicability = _raw_answers(**kwargs)
    vector = {
        "evaluation_id": f"eval-{record.state_id}",
        "purpose": "WIDE",
        "input_ref_kind": "STATISTICAL_STATE",
        "input_ref_id": record.state_id,
        "answers": answers,
        "applicability": applicability,
        "cache_source_evaluation_id": cache_source,
        "error": error,
    }
    typed_applicability = tuple(
        QuestionApplicability(question_id, item["applicable"], item["reason"], item["rule"])
        for question_id, item in applicability.items()
    )
    if error is not None:
        return EvaluationRecord(
            evaluation_id="failed", input_ref_id=record.state_id, answers=None,
            error_code=error["code"], artifact_id="failed-artifact",
            serialized=canonical_json(vector), applicability=typed_applicability,
        )
    validated = read_answers(WIDE_QUESTIONS, answers)
    return EvaluationRecord(
        evaluation_id=f"eval-{record.state_id}", input_ref_id=record.state_id, answers=validated,
        error_code=None, artifact_id=f"artifact-{record.state_id}",
        serialized=canonical_json(vector), applicability=typed_applicability,
        cache_source_evaluation_id=cache_source,
    )


def test_baseline_is_deterministic_and_never_admission_authority():
    high = _record("state-high", 40)
    low = _record("state-low", 10)
    first = baseline_ranking([high, low])
    second = baseline_ranking([low, high])
    assert first["policy_version"] == BASELINE_POLICY_VERSION
    assert [entry["state_id"] for entry in first["entries"]] == ["state-high", "state-low"]
    assert [entry["state_id"] for entry in second["entries"]] == ["state-high", "state-low"]
    assert first["entries"][0]["dimensions"]["affected_cases"] == 40
    assert first["entries"][0]["rank"] == 1
    assert first["admitted_state_ids"] == []
    assert first["top_state_ids"] == [entry["state_id"] for entry in first["entries"]]


def test_baseline_preserves_zero_and_sorts_unobserved_mutation_last():
    unobserved = _record("state-unobserved", None)
    zero = _record("state-zero", 0)
    positive = _record("state-positive", 2)
    ranking = baseline_ranking([unobserved, zero, positive])
    assert [entry["state_id"] for entry in ranking["entries"]] == [
        "state-positive", "state-zero", "state-unobserved",
    ]
    dimensions = {entry["state_id"]: entry["dimensions"] for entry in ranking["entries"]}
    assert dimensions["state-zero"]["affected_cases"] == 0
    assert dimensions["state-zero"]["mutation_observed"] is True
    assert dimensions["state-unobserved"]["affected_cases"] is None
    assert dimensions["state-unobserved"]["mutation_observed"] is False


def test_rankings_do_not_collapse_a_multi_project_state_into_a_cohort():
    multi = state_record("state-multi", statistical_state(projects=("P1", "P2")))
    baseline = baseline_ranking([multi])
    assert baseline["entries"][0]["dimensions"]["affected_cases"] is None
    assert baseline["entries"][0]["dimensions"]["mutation_observed"] is False
    ranking = jev_ranking([multi], [])
    entry = ranking["entries"][0]
    assert ranking["admission"]["decision"] == "ABSTAIN"
    assert "MUTATION_NOT_OBSERVED" in entry["excluded_reason"]
    assert "EVALUATION_MISSING" in entry["excluded_reason"]


def test_jev_admission_uses_thresholds_and_ranks_qualified_states():
    high = _record("state-high", 40)
    low = _record("state-low", 10)
    evaluations = [
        _evaluation(high, warrants=0.9, uncertainty=0.9, quality=0.9, confound=0.1,
                    cache_source="cached-evaluation"),
        _evaluation(low, warrants=ADMISSION_MIN_WARRANTS, uncertainty=ADMISSION_MIN_UNCERTAINTY,
                    quality=ADMISSION_MIN_QUALITY, confound=ADMISSION_MAX_CONFOUND),
    ]
    ranking = jev_ranking([low, high], evaluations)
    assert ranking["policy_version"] == JEV_POLICY_VERSION
    assert [entry["state_id"] for entry in ranking["entries"]] == ["state-high", "state-low"]
    assert ranking["admission"]["decision"] == "ADMIT"
    assert ranking["admitted_state_ids"] == ["state-high", "state-low"]
    thresholds = ranking["admission"]["thresholds"]
    assert thresholds["warrants_deeper_investigation_min"] == ADMISSION_MIN_WARRANTS
    assert thresholds["unresolved_uncertainty_material_min"] == ADMISSION_MIN_UNCERTAINTY
    assert thresholds["evidence_quality_adequate_min"] == ADMISSION_MIN_QUALITY
    assert thresholds["signal_explained_by_coverage_max"] == ADMISSION_MAX_CONFOUND
    dimensions = ranking["entries"][0]["dimensions"]
    assert dimensions["warrants_deeper_investigation"] == 0.9
    assert dimensions["cache_source_evaluation_id"] == "cached-evaluation"
    assert dimensions["dominant_limitation"] == "NONE"
    assert dimensions["dominant_limitation_probabilities"] == \
        evaluations[0].boundary_representation()["answers"]["dominant_limitation"]["probabilities"]


def test_deterministic_eligibility_gate_overrides_favorable_judgments():
    incomplete = state_record("state-incomplete", statistical_state(acquisition_complete=False))
    expression_missing = state_record("state-expression-missing", statistical_state(expression=False))
    no_mutation = state_record("state-no-mutation", statistical_state(counts={PROJECT: {}}))
    states = [incomplete, expression_missing, no_mutation]
    evaluations = [_evaluation(state) for state in states]
    ranking = jev_ranking(states, evaluations)
    assert ranking["admission"]["decision"] == "ABSTAIN"
    exclusions = {entry["state_id"]: entry["excluded_reason"] for entry in ranking["entries"]}
    assert exclusions["state-incomplete"] == "INCOMPLETE_ACQUISITION"
    assert "MUTATION_NOT_OBSERVED" in exclusions["state-no-mutation"]
    assert "EXPRESSION_NOT_OBSERVED" in exclusions["state-expression-missing"]
    assert all(entry["qualified"] is False for entry in ranking["entries"])


def test_inapplicable_required_dimension_is_excluded_but_raw_answer_is_retained():
    state = _record("state-low", 10)
    evaluation = _evaluation(state, quality=0.99, inapplicable=("evidence_quality_adequate",))
    ranking = jev_ranking([state], [evaluation])
    entry = ranking["entries"][0]
    assert entry["qualified"] is False
    assert "JUDGMENT_UNAVAILABLE:evidence_quality_adequate" in entry["excluded_reason"]
    assert entry["dimensions"]["evidence_quality_adequate"] == 0.99
    assert entry["dimensions"]["applicability"]["evidence_quality_adequate"]["applicable"] is False


def test_inapplicable_coverage_confound_does_not_block_admission():
    state = _record("state-high", 40)
    evaluation = _evaluation(state, confound=0.99,
                             inapplicable=("signal_explained_by_coverage",))
    ranking = jev_ranking([state], [evaluation])
    assert ranking["admission"]["decision"] == "ADMIT"
    assert ranking["admitted_state_ids"] == ["state-high"]
    assert ranking["entries"][0]["dimensions"]["signal_explained_by_coverage"] == 0.99


def test_inapplicable_probabilities_do_not_change_order_but_remain_raw():
    state_a = state_record("state-a", statistical_state(expression=False, counts={PROJECT: {}}))
    state_b = state_record("state-b", statistical_state(expression=False, counts={PROJECT: {}}))
    inapplicable = ("warrants_deeper_investigation", "unresolved_uncertainty_material",
                    "evidence_quality_adequate", "signal_explained_by_coverage")
    first = jev_ranking([state_a, state_b], [
        _evaluation(state_a, confound=0.01, inapplicable=inapplicable),
        _evaluation(state_b, confound=0.99, inapplicable=inapplicable),
    ])
    swapped = jev_ranking([state_a, state_b], [
        _evaluation(state_a, confound=0.99, inapplicable=inapplicable),
        _evaluation(state_b, confound=0.01, inapplicable=inapplicable),
    ])
    assert [entry["state_id"] for entry in first["entries"]] == \
        [entry["state_id"] for entry in swapped["entries"]]
    assert [entry["dimensions"]["signal_explained_by_coverage"] for entry in first["entries"]] == \
        [0.01, 0.99]


def test_jev_promotion_limit_is_a_cap_and_failed_states_remain_auditable():
    states = [_record(f"state-{index}", 10 + index) for index in range(PROMOTION_LIMIT + 2)]
    evaluations = [_evaluation(state, warrants=0.9 - index * 0.01)
                   for index, state in enumerate(states)]
    failed_state = _record("missing-eval", 20)
    states.append(failed_state)
    evaluations.append(_evaluation(failed_state, error={"code": "PROVIDER_ERROR"}))
    ranking = jev_ranking(states, evaluations)
    assert ranking["admission"]["decision"] == "ADMIT"
    assert len(ranking["admitted_state_ids"]) == PROMOTION_LIMIT
    assert ranking["admitted_state_ids"] == [f"state-{index}" for index in range(PROMOTION_LIMIT)]
    failed = next(entry for entry in ranking["entries"] if entry["state_id"] == "missing-eval")
    assert failed["qualified"] is False
    assert failed["excluded_reason"] == "EVALUATION_FAILED"
    assert failed["evaluation_id"] == "failed"
    assert set(failed["dimensions"]) == {"affected_cases"}, \
        "a failed judgment carries no fabricated dimensions"


def test_admission_exclusion_reasons_are_named():
    confounded = _record("state-confound", 40)
    ranking = jev_ranking([confounded], [_evaluation(confounded, confound=ADMISSION_MAX_CONFOUND + 0.01)])
    assert ranking["admission"]["decision"] == "ABSTAIN"
    assert "ABOVE_ADMISSION_THRESHOLD:signal_explained_by_coverage" in \
        ranking["entries"][0]["excluded_reason"]

    low = _record("state-low", 10)
    ranking = jev_ranking([low], [_evaluation(low, warrants=0.59)])
    assert ranking["admission"]["decision"] == "ABSTAIN"
    assert ranking["admitted_state_ids"] == []
    assert "BELOW_ADMISSION_THRESHOLD:warrants_deeper_investigation" in \
        ranking["entries"][0]["excluded_reason"]
