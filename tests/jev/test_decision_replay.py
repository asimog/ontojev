from dataclasses import asdict

import pytest

from cancerjev.jev.contracts import JevContractError
from cancerjev.jev.decisions import acquisition_choice_questions, acquisition_relevance_questions
from cancerjev.jev.replay import evaluate_decisions


def choice_record(probabilities, *, baseline="OPTION_0", group="same-science"):
    return {
        "contract_id": "NEXT_ACQUISITION_CHOICE_V1", "offer_ids": ["small", "large"],
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
    question = asdict(acquisition_relevance_questions(1)[0])
    records = [{"contract_id": "ACQUISITION_RELEVANCE_V1", "questions": [question],
                "answers": {"offer_0": {"kind": "noul", "probability_yes": p}},
                "labels": {"offer_0": label}}
               for p, label in ((0.8, True), (0.4, False))]
    report = evaluate_decisions(records)
    assert report["brier_score"] == pytest.approx(0.1)
    assert report["baseline_agreement"] is None
    records[0]["labels"]["offer_0"] = "true"
    with pytest.raises(ValueError, match="boolean"):
        evaluate_decisions(records)


def test_replay_rejects_contract_substitution():
    record = choice_record({"OPTION_0": 0.6, "OPTION_1": 0.3, "NONE": 0.1})
    record["offer_ids"] = ["small", "large"]
    record["questions"][0]["instructions"] = "Which offer maximizes clinical benefit?"
    with pytest.raises(ValueError, match="question contract"):
        evaluate_decisions([record])


def test_repeatability_compares_offers_instead_of_option_positions():
    first = choice_record({"OPTION_0": 0.6, "OPTION_1": 0.3, "NONE": 0.1})
    second = choice_record({"OPTION_0": 0.6, "OPTION_1": 0.3, "NONE": 0.1})
    second["offer_ids"] = ["large", "small"]
    second["questions"] = [asdict(q) for q in acquisition_choice_questions(("large", "small"))]
    report = evaluate_decisions([first, second])
    assert report["stable_repeat_groups"] == 0
    assert report["records"][0]["selected_identity"] == "offer:small"
    assert report["records"][1]["selected_identity"] == "offer:large"
