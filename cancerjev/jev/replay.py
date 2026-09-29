"""Compare recorded bounded decisions without calling providers or altering science."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from cancerjev.jev.contracts import ChoiceAnswer, NoulAnswer, read_answers
from cancerjev.jev.decisions import (
    CONTRACTS,
    acquisition_choice_questions,
    acquisition_relevance_questions,
    uncertainty,
)
from cancerjev.jev.questions import (
    DEEP_QUESTIONS,
    HYPOTHESIS_QUESTIONS,
    WIDE_QUESTIONS,
    QuestionDefinition,
)


def evaluate_decisions(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Records include their actual allowed outputs, baseline and optional labels.

    Equivalent-state groups must be declared by the corpus author. Agreement
    measures consistency, never correctness. Brier score requires binary labels.
    """
    results: list[dict[str, Any]] = []
    brier: list[float] = []
    repeats: dict[tuple[str, str], list[str | None]] = {}
    known = {contract.contract_id: name for name, contract in CONTRACTS.items()}
    for record in records:
        if record["contract_id"] not in known:
            raise ValueError("unknown decision contract")
        questions = tuple(QuestionDefinition(**item) for item in record["questions"])
        name = known[record["contract_id"]]
        option_identities: dict[str, str] = {}
        if name == "LAB_CHOICE":
            offer_ids = record.get("offer_ids")
            if not isinstance(offer_ids, list) or any(not isinstance(i, str) or not i for i in offer_ids):
                raise ValueError("choice replay requires offer_ids")
            expected = acquisition_choice_questions(tuple(offer_ids))
            option_identities = {f"OPTION_{i}": "offer:" + identity for i, identity in enumerate(offer_ids)}
            option_identities["NONE"] = "NONE"
        elif name == "LAB_RELEVANCE":
            expected = acquisition_relevance_questions(len(questions))
        else:
            expected = {"WIDE": WIDE_QUESTIONS, "DEEP": DEEP_QUESTIONS,
                        "HYPOTHESIS": HYPOTHESIS_QUESTIONS}[name]
        if questions != expected:
            raise ValueError("incompatible question contract")
        answers = read_answers(questions, record["answers"])
        diagnostics = uncertainty(answers)
        selected = None
        for answer in answers.answers:
            if isinstance(answer, ChoiceAnswer):
                selected = answer.choice
            if isinstance(answer, NoulAnswer):
                label = record.get("labels", {}).get(answer.question_id)
                if label is not None:
                    if type(label) is not bool:
                        raise ValueError("binary calibration requires boolean labels")
                    brier.append((answer.probability_yes - float(label)) ** 2)
        latency = record.get("latency_ms")
        for field in ("latency_ms", "cost"):
            value = record.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                     or not math.isfinite(value) or value < 0):
                raise ValueError(f"invalid {field}")
        baseline = record.get("baseline_option")
        choice_questions = [q for q in questions if q.primitive == "CHOICE"]
        if baseline is not None and (len(choice_questions) != 1 or baseline not in (choice_questions[0].criteria or {})):
            raise ValueError("baseline option is not in the question contract")
        baseline_available = baseline is not None and selected is not None
        selected_identity = selected
        if name == "LAB_CHOICE" and selected is not None:
            selected_identity = option_identities[selected]
        results.append({"contract_id": record["contract_id"], "selected_option": selected,
                        "selected_identity": selected_identity,
                        "baseline_option": baseline,
                        "baseline_agreement": selected == baseline if baseline_available else None,
                        "uncertainty": diagnostics, "latency_ms": latency,
                        "cost": record.get("cost")})
        group = record.get("equivalent_state_id")
        if group and selected is not None:
            repeats.setdefault((record["contract_id"], group), []).append(selected_identity)
    comparable = [row for row in results if row["baseline_agreement"] is not None]
    repeat_groups = [choices for choices in repeats.values() if len(choices) > 1]
    return {"protocol": "jev-bounded-replay-v1", "records": results,
            "baseline_comparable": len(comparable),
            "baseline_agreement": sum(bool(r["baseline_agreement"]) for r in comparable) / len(comparable)
            if comparable else None,
            "binary_label_count": len(brier), "brier_score": sum(brier) / len(brier) if brier else None,
            "repeat_groups": len(repeat_groups),
            "stable_repeat_groups": sum(len(set(group)) == 1 for group in repeat_groups),
            "evaluation_status": "EXPERIMENTAL",
            "claim": "Descriptive replay only. Agreement and repeatability do not establish scientific accuracy or incremental value. No contract is automatically accepted."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    records = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("replay corpus must be an array")
    print(json.dumps(evaluate_decisions(records), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
