from __future__ import annotations

from copy import deepcopy

from cancerjev.jev.questions import LIMITATION_ROSTER
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
from tests.science.test_methods import GENE, _build, _frame


def _state(state_id: str, affected: int | None) -> dict:
    counts = {"P1": {GENE.gene_id: affected}} if affected is not None else {"P1": {}}
    return _build([_frame("P1")], counts=counts, state_id=state_id)


def _states() -> list[dict]:
    return [_state("state-low", 10), _state("state-high", 40)]


def _evaluation(state: dict, *, warrants: float = 0.9, uncertainty: float = 0.8,
                quality: float = 0.8, confound: float = 0.2,
                inapplicable: tuple[str, ...] = ()) -> dict:
    limitation_probabilities = {
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
            "kind": "choice", "choice": "NONE", "confidence": 0.88,
            "probabilities": limitation_probabilities,
        },
    }
    applicability = {
        question_id: {"applicable": question_id not in inapplicable, "reason": "test"}
        for question_id in answers
    }
    return {
        "evaluation_id": f"eval-{state['state_id']}",
        "input_ref_id": state["state_id"],
        "error": None,
        "answers": answers,
        "applicability": applicability,
        "cache_source_evaluation_id": "cached-evaluation" if state["state_id"] == "state-high" else None,
    }


def test_baseline_ranking_is_deterministic_and_not_an_admission_authority():
    states = _states()
    first = baseline_ranking(states)
    second = baseline_ranking(list(reversed(states)))
    assert first["policy_version"] == BASELINE_POLICY_VERSION
    assert [entry["state_id"] for entry in first["entries"]] == [entry["state_id"] for entry in second["entries"]]
    assert first["entries"][0]["state_id"] == "state-high"
    assert first["entries"][0]["dimensions"]["affected_cases"] == 40
    assert first["admitted_state_ids"] == []
    assert first["top_state_ids"] == [entry["state_id"] for entry in first["entries"]]
    assert first["entries"][0]["rank"] == 1


def test_baseline_preserves_zero_and_sorts_unobserved_mutation_last():
    states = [_state("unobserved", None), _state("zero", 0), _state("positive", 2)]
    ranking = baseline_ranking(states)
    assert [entry["state_id"] for entry in ranking["entries"]] == ["positive", "zero", "unobserved"]
    assert ranking["entries"][1]["dimensions"]["affected_cases"] == 0
    assert ranking["entries"][1]["dimensions"]["mutation_observed"] is True
    assert ranking["entries"][2]["dimensions"]["affected_cases"] is None
    assert ranking["entries"][2]["dimensions"]["mutation_observed"] is False


def test_rankings_do_not_collapse_a_multi_project_state_to_the_first_project():
    state = _build([_frame("P1"), _frame("P2")])
    baseline = baseline_ranking([state])
    jev = jev_ranking([state], [])
    assert baseline["entries"][0]["dimensions"]["affected_cases"] is None
    assert baseline["entries"][0]["dimensions"]["mutation_observed"] is False
    assert jev["admission"]["decision"] == "ABSTAIN"
    assert "MUTATION_NOT_OBSERVED" in jev["entries"][0]["excluded_reason"]
    assert "EVALUATION_MISSING" in jev["entries"][0]["excluded_reason"]


def test_jev_admission_uses_thresholds_and_ranks_qualified_states():
    low, high = _states()
    evaluations = [
        _evaluation(low, warrants=ADMISSION_MIN_WARRANTS, uncertainty=ADMISSION_MIN_UNCERTAINTY,
                    quality=ADMISSION_MIN_QUALITY, confound=ADMISSION_MAX_CONFOUND),
        _evaluation(high, warrants=0.9, uncertainty=0.9),
    ]
    ranking = jev_ranking([low, high], evaluations)
    assert ranking["policy_version"] == JEV_POLICY_VERSION
    assert ranking["entries"][0]["state_id"] == high["state_id"]
    assert ranking["admission"]["decision"] == "ADMIT"
    assert ranking["admitted_state_ids"] == [entry["state_id"] for entry in ranking["entries"]]
    assert ranking["admission"]["thresholds"]["warrants_deeper_investigation_min"] == ADMISSION_MIN_WARRANTS
    assert ranking["entries"][0]["dimensions"]["dominant_limitation_probabilities"] == evaluations[1]["answers"]["dominant_limitation"]["probabilities"]
    assert ranking["entries"][0]["dimensions"]["cache_source_evaluation_id"] == "cached-evaluation"


def test_deterministic_eligibility_gate_overrides_favorable_judgments():
    incomplete = deepcopy(_states()[1])
    incomplete["quality"]["completeness"] = "PARTIAL"
    expression_missing = deepcopy(_states()[0])
    expression_missing["expression"]["availability"] = "INSUFFICIENT"
    no_mutation = _state("no-mutation", None)
    evaluations = [_evaluation(state) for state in (incomplete, expression_missing, no_mutation)]
    ranking = jev_ranking([incomplete, expression_missing, no_mutation], evaluations)
    assert ranking["admission"]["decision"] == "ABSTAIN"
    exclusions = {entry["state_id"]: entry["excluded_reason"] for entry in ranking["entries"]}
    assert exclusions[incomplete["state_id"]] == "INCOMPLETE_ACQUISITION"
    assert "EXPRESSION_NOT_OBSERVED" in exclusions[expression_missing["state_id"]]
    assert "MUTATION_NOT_OBSERVED" in exclusions[no_mutation["state_id"]]
    assert ranking["admitted_state_ids"] == []


def test_inapplicable_required_dimension_is_excluded_but_raw_answer_is_retained():
    state = _states()[0]
    evaluation = _evaluation(state, quality=0.99, inapplicable=("evidence_quality_adequate",))
    ranking = jev_ranking([state], [evaluation])
    entry = ranking["entries"][0]
    assert entry["qualified"] is False
    assert "JUDGMENT_UNAVAILABLE:evidence_quality_adequate" in entry["excluded_reason"]
    assert entry["dimensions"]["evidence_quality_adequate"] == 0.99
    assert entry["dimensions"]["applicability"]["evidence_quality_adequate"]["applicable"] is False


def test_inapplicable_coverage_confound_does_not_block_admission():
    state = _states()[0]
    evaluation = _evaluation(state, confound=0.99, inapplicable=("signal_explained_by_coverage",))
    ranking = jev_ranking([state], [evaluation])
    assert ranking["admission"]["decision"] == "ADMIT"
    assert ranking["entries"][0]["dimensions"]["signal_explained_by_coverage"] == 0.99


def test_jev_promotion_limit_is_a_cap_and_failed_states_remain_auditable():
    states = [_state(f"state-{index}", 10 + index) for index in range(PROMOTION_LIMIT + 2)]
    evaluations = [_evaluation(state, warrants=0.9 - index * 0.01) for index, state in enumerate(states)]
    evaluations.append({"input_ref_id": "missing-eval", "evaluation_id": "failed", "error": {"code": "PROVIDER_ERROR"}})
    states.append(_state("missing-eval", 20))
    ranking = jev_ranking(states, evaluations)
    assert ranking["admission"]["decision"] == "ADMIT"
    assert len(ranking["admitted_state_ids"]) == PROMOTION_LIMIT
    failed = next(entry for entry in ranking["entries"] if entry["state_id"] == "missing-eval")
    assert failed["excluded_reason"] == "EVALUATION_FAILED"
    assert failed["evaluation_id"] == "failed"


def test_no_qualifiers_produce_explicit_abstention():
    state = _states()[0]
    ranking = jev_ranking([state], [_evaluation(state, warrants=0.59)])
    assert ranking["admission"]["decision"] == "ABSTAIN"
    assert ranking["admitted_state_ids"] == []
    assert "BELOW_ADMISSION_THRESHOLD:warrants_deeper_investigation" in ranking["entries"][0]["excluded_reason"]
