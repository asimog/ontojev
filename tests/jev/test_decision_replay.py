from dataclasses import asdict

import pytest

from cancerjev.jev.contracts import JevContractError
from cancerjev.jev.decisions import acquisition_choice_questions
from cancerjev.jev.replay import evaluate_decisions


def choice_record(probabilities, *, baseline="OPTION_0", group="same-science"):
    return {
        "contract_id": "NEXT_ACQUISITION_CHOICE_V1",
        "questions": [asdict(q) for q in acquisition_choice_questions(("small", "large"))],
        "answers": {"next_acquisition": {"kind": "choice", "choice": "OPTION_0",
            "confidence": 0.1, "probabilities": probabilities}},
        "baseline_option": baseline, "equivalent_state_id": group, "latency_ms": 200,
    }


def test_replay_reports_ties_without_claiming_accuracy_or_acceptance():
    first = choice_record({"OPTION_0": 0.49, "OPTION_1": 0.48, "NONE": 0.03})
    second = choice_record({"NONE": 0.03, "OPTION_1": 0.48, "OPTION_0": 0.49}, baseline="NONE")
    report = evaluate_decisions([first, second])
    assert report["baseline_agreement"] == 0.5
    assert report["stable_repeat_groups"] == 1
    diagnostic = report["records"][0]["uncertainty"]["questions"]["next_acquisition"]
    assert diagnostic["near_tie"] and diagnostic["low_confidence"]
    assert report["binary_label_count"] == 0 and report["brier_score"] is None
    assert report["evaluation_status"] == "EXPERIMENTAL"
    invalid = choice_record({"OPTION_0": 0.9, "OPTION_1": 0.9, "NONE": 0.03})
    with pytest.raises(JevContractError, match="INVALID_DISTRIBUTION"):
        evaluate_decisions([invalid])


def test_binary_calibration_uses_independent_labels_only():
    question = dict(question_id="relevant", primitive="NOUL", version=1,
                    instructions="Does this offer address the uncertainty?", criteria=None,
                    applicability_rule="offered_experiment")
    records = [{"contract_id": "ACQUISITION_RELEVANCE_V1", "questions": [question],
                "answers": {"relevant": {"kind": "noul", "probability_yes": p}},
                "labels": {"relevant": label}}
               for p, label in ((0.8, True), (0.4, False))]
    report = evaluate_decisions(records)
    assert report["brier_score"] == pytest.approx(0.1)
    assert report["baseline_agreement"] is None
    records[0]["labels"]["relevant"] = "true"
    with pytest.raises(ValueError, match="boolean"):
        evaluate_decisions(records)
