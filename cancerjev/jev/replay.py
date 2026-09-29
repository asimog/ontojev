"""Compare recorded bounded decisions without calling providers or altering science."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from cancerjev.jev.contracts import ChoiceAnswer, NoulAnswer, read_answers
from cancerjev.jev.decisions import CONTRACTS, uncertainty
from cancerjev.jev.questions import QuestionDefinition


def evaluate_decisions(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Records include their actual allowed outputs, baseline and optional labels.

    Equivalent-state groups must be declared by the corpus author. Agreement
    measures consistency, never correctness. Brier score requires binary labels.
    """
    results: list[dict[str, Any]] = []
    brier: list[float] = []
    repeats: dict[tuple[str, str], list[str | None]] = {}
    known = {contract.contract_id for contract in CONTRACTS.values()}
    for record in records:
        if record["contract_id"] not in known:
            raise ValueError("unknown decision contract")
        questions = tuple(QuestionDefinition(**item) for item in record["questions"])
        answers = read_answers(questions, record["answers"])
        diagnostics = uncertainty(answers)
        selected = record.get("selected_option")
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
        if latency is not None and (isinstance(latency, bool) or not isinstance(latency, (int, float))
                                    or not math.isfinite(latency) or latency < 0):
            raise ValueError("invalid latency")
        baseline = record.get("baseline_option")
        baseline_available = baseline is not None and selected is not None
        results.append({"contract_id": record["contract_id"], "selected_option": selected,
                        "baseline_option": baseline,
                        "baseline_agreement": selected == baseline if baseline_available else None,
                        "uncertainty": diagnostics, "latency_ms": latency,
                        "cost": record.get("cost")})
        group = record.get("equivalent_state_id")
        if group:
            repeats.setdefault((record["contract_id"], group), []).append(selected)
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
