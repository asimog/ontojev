"""Small registry of consequential Jev boundaries and replay diagnostics.

Registry status is an evaluation claim, not a claim that a boundary is unused.
Legacy scientific contracts remain experimental until comparative evidence
establishes value. No acceptance is inferred from passing software tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from cancerjev.domain.measurements import digest
from cancerjev.jev.contracts import ChoiceAnswer, NoulAnswer, ScoreAnswer, ValidatedAnswers
from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTION_SET_VERSION,
    WIDE_QUESTION_SET_VERSION,
    QuestionDefinition,
)

DIAGNOSTIC_VERSION = "jev-uncertainty-v1"
# Operational diagnostics only. These do not alter historical scientific gates.
NEAR_TIE_MARGIN = 0.05
LOW_CHOICE_CONFIDENCE = 0.5
NOUL_UNCERTAIN_LOW = 0.4
NOUL_UNCERTAIN_HIGH = 0.6


@dataclass(frozen=True)
class JevDecisionContract:
    contract_id: str
    role: Literal["RESEARCH_CONTROL", "SCIENTIFIC_EVALUATION"]
    question_set_version: str
    projection: str
    baseline: str
    failure: str
    semantics: str
    evaluation_status: Literal["EXPERIMENTAL", "ACCEPTED", "REJECTED"]
    evaluation: str
    audit: str

    def payload(self, questions: tuple[QuestionDefinition, ...]) -> dict[str, Any]:
        return {**asdict(self), "questions": [
            {"id": q.question_id, "version": q.version, "primitive": q.primitive,
             "instructions": q.instructions, "allowed_outputs": q.criteria
             if q.primitive != "NOUL" else {"probability_yes": "finite [0,1]"}}
            for q in questions], "question_hash": digest([q.provider_spec() for q in questions])}


CONTRACTS = {
    "WIDE": JevDecisionContract(
        "WIDE_ADMISSION_V1", "SCIENTIFIC_EVALUATION", WIDE_QUESTION_SET_VERSION,
        "Canonical StatisticalState projection after deterministic narrowing",
        "baseline-wide-v2; existing labelled ranking comparison",
        "Unavailable/inapplicable answers cannot qualify; preserve exclusions",
        "Nouls are proposition probabilities, not target quality or evidence maturity",
        "EXPERIMENTAL", "Offline contract tests and descriptive baseline replay; superiority unestablished",
        "Useful but poorly formulated: warrants_deeper_investigation combines several judgments; retain versioned behavior pending comparative evaluation"),
    "DEEP": JevDecisionContract(
        "DEEP_REVISION_V1", "SCIENTIFIC_EVALUATION", DEEP_QUESTION_SET_VERSION,
        "Selected Candidate EvidenceState plus eligible registered actions",
        "Stage 8 deterministic no-Jev replay",
        "Abstain on unavailable judgment; Python independently rejects contradicted checks",
        "Probabilities concern bounded follow-up, never biological truth or maturity",
        "EXPERIMENTAL", "Offline next-move replay; incremental scientific value unestablished",
        "revision_reliable partly duplicates deterministic checks; next_step_warranted and stopping_more_honest overlap; do not bypass Python integrity checks"),
    "HYPOTHESIS": JevDecisionContract(
        "HYPOTHESIS_CRITIQUE_V1", "SCIENTIFIC_EVALUATION", HYPOTHESIS_QUESTION_SET_VERSION,
        "One generated hypothesis linked to immutable EvidenceState",
        "Deterministic availability of a registered discriminating test",
        "Abstain; never manufacture a test or promote the hypothesis to evidence",
        "Testability and overreach are semantic judgments, not confirmation",
        "EXPERIMENTAL", "Replay contracts; no established biological accuracy",
        "Appropriate bounded critique; test dispatchability is already deterministic"),
    "LAB_RELEVANCE": JevDecisionContract(
        "ACQUISITION_RELEVANCE_V1", "RESEARCH_CONTROL", "lab-control-v1",
        "Question uncertainties and Python-preflighted acquisition offers",
        "OntoCodex direct decision over the identical state",
        "Abstain and use OntoCodex direct decision",
        "Independent Noul relevance probabilities are not a comparative ranking",
        "EXPERIMENTAL", "Live callable; no measured advantage over direct OntoCodex",
        "Useful but unevaluated; pointwise probabilities must not imply a total order"),
    "LAB_CHOICE": JevDecisionContract(
        "NEXT_ACQUISITION_CHOICE_V1", "RESEARCH_CONTROL", "lab-choice-v1",
        "Bounded eligible offers, question uncertainties, deterministic costs and remaining time",
        "OntoCodex direct decision and ACQUISITION_RELEVANCE_V1",
        "Abstain on failure, low confidence, or near tie; direct OntoCodex chooses",
        "Choice distribution compares offered alternatives, including NONE; no evidence maturity meaning",
        "EXPERIMENTAL", "Replay comparison available; not accepted for canonical control",
        "Appropriate competition boundary; experimental shadow evaluation only"),
}


def uncertainty(answers: ValidatedAnswers) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for answer in answers.answers:
        if isinstance(answer, NoulAnswer):
            diagnostics[answer.question_id] = {
                "uncertain": NOUL_UNCERTAIN_LOW <= answer.probability_yes <= NOUL_UNCERTAIN_HIGH,
                "probability_yes": answer.probability_yes,
            }
        elif isinstance(answer, (ChoiceAnswer, ScoreAnswer)):
            probabilities = sorted((p for _, p in answer.probabilities), reverse=True)
            margin = probabilities[0] - probabilities[1] if len(probabilities) > 1 else 1.0
            diagnostics[answer.question_id] = {
                "near_tie": margin <= NEAR_TIE_MARGIN,
                "top_two_margin": margin,
                "low_confidence": answer.confidence < LOW_CHOICE_CONFIDENCE,
                "confidence": answer.confidence,
            }
    return {"version": DIAGNOSTIC_VERSION, "thresholds": {
        "near_tie_margin": NEAR_TIE_MARGIN, "low_choice_confidence": LOW_CHOICE_CONFIDENCE,
        "noul_uncertain_interval": [NOUL_UNCERTAIN_LOW, NOUL_UNCERTAIN_HIGH],
    }, "questions": diagnostics}


def acquisition_choice_questions(offer_ids: tuple[str, ...]) -> tuple[QuestionDefinition, ...]:
    if not offer_ids or len(offer_ids) > 6 or len(set(offer_ids)) != len(offer_ids):
        raise ValueError("comparative decision requires 1..6 distinct offers")
    return (QuestionDefinition(
        "next_acquisition", "CHOICE", 1,
        "Which offered experiment would most directly reduce a stated decision-relevant uncertainty "
        "in its associated question? Consider existing evidence and opportunity cost. Choose NONE "
        "if none addresses the question. Use only supplied operational facts; never infer absent "
        "measurements. The offers are feasibility-filtered by Python. This is a research-control judgment.",
        {**{f"OPTION_{index}": f"Acquire offer {identity}" for index, identity in enumerate(offer_ids)},
         "NONE": "None offers a justified next acquisition; direct scientific reasoning is needed."},
        "eligible_preflight_offers",
    ),)
