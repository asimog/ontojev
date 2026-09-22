"""Versioned Jev question definitions and deterministic applicability rules.

Question IDs exist only in application records; the full meaning lives in the
instructions and criteria. Changing wording, criteria or the roster changes the
question-set hash. Applicability is decided by code from the projection, never by
the model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.events import canonical_json

WIDE_QUESTION_SET_VERSION = "wide-v2"

NOUL_TRUE_CRITERION = (
    "The stated proposition is supported by the supplied observations and their stated quality context."
)
NOUL_FALSE_CRITERION = (
    "The stated proposition is not supported by the supplied observations, or the observations are too "
    "incomplete to support it."
)

PATTERN_ROSTER = {
    "WIDESPREAD_RECURRENCE": "Comparable projects show recurring mutation counts without a dominant exception.",
    "PROJECT_SPECIFIC_EXCEPTION": "One observed comparable project departs from the majority pattern.",
    "WEAK_DISTRIBUTED_SIGNAL": "Individually moderate mutation counts recur across projects.",
    "NO_COHERENT_PATTERN": "Usable observations show no coherent cross-project pattern.",
    "DATA_QUALITY_CONCERN": "Coverage, missingness or mapping problems dominate interpretation.",
    "INSUFFICIENT_EVIDENCE": "Available observations cannot distinguish the patterns.",
}


@dataclass(frozen=True)
class QuestionDefinition:
    question_id: str
    primitive: str
    version: int
    instructions: str
    criteria: dict[str, Any] | None
    applicability_rule: str

    def provider_spec(self) -> dict[str, Any]:
        spec: dict[str, Any] = {"type": self.primitive.lower(), "instructions": self.instructions}
        if self.criteria is not None:
            spec["criteria"] = self.criteria
        return spec


WIDE_QUESTIONS: tuple[QuestionDefinition, ...] = (
    QuestionDefinition(
        question_id="warrants_deeper_investigation",
        primitive="NOUL",
        version=1,
        instructions=(
            "You are reviewing a compact deterministic profile of one gene across several cancer projects. "
            "It contains per-project counts of cases with a somatic mutation in this gene "
            "(`project_observations[].affected_cases`), examined-case and mutation-data coverage, and "
            "per-project expression summaries in log2(UQFPKM+1), with missingness stated explicitly. Decide "
            "whether this profile warrants a bounded deterministic follow-up investigation. A follow-up is a "
            "small registered computation over held data or a small bounded public-data query, not a clinical "
            "action; biological novelty is not required."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="any_observation",
    ),
    QuestionDefinition(
        question_id="mutation_project_exception",
        primitive="NOUL",
        version=1,
        instructions=(
            "Compare the supplied per-project affected-case counts (`project_observations[].affected_cases`). "
            "Does at least one project depart materially from the dominant cross-project pattern of these "
            "counts, beyond what the stated coverage and case counts would explain? A project with no mutation "
            "observation is not an exception."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="three_mutation_observations",
    ),
    QuestionDefinition(
        question_id="expression_project_exception",
        primitive="NOUL",
        version=1,
        instructions=(
            "Compare the supplied per-project expression summaries (`project_observations[].expression_local`). "
            "Does at least one project depart materially from the dominant cross-project pattern of expression "
            "median or dispersion, beyond what the stated missing-expression counts would explain?"
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="three_expression_observations",
    ),
    QuestionDefinition(
        question_id="coverage_explains_apparent_difference",
        primitive="NOUL",
        version=1,
        instructions=(
            "The supplied profile states per-project examined-case counts, mutation-data coverage and "
            "expression coverage. Is the apparent cross-project difference plausibly explained by unequal "
            "coverage or missingness rather than by a biological difference?"
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="coverage_imbalance",
    ),
    QuestionDefinition(
        question_id="likely_fragile",
        primitive="NOUL",
        version=1,
        instructions=(
            "Using the supplied dominance context (`cross_project.top_project_share`) and coverage/missingness, "
            "does the apparent cross-project pattern look fragile - dependent on one project or on incomplete "
            "coverage?"
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="two_observations",
    ),
    QuestionDefinition(
        question_id="pattern_type",
        primitive="CHOICE",
        version=1,
        instructions=(
            "Which supplied pattern description best fits the observed evidence? The options describe "
            "cross-project patterns of mutation counts and expression summaries; choose the single "
            "best-fitting description, or the insufficient-evidence option when the observations cannot "
            "distinguish the patterns."
        ),
        criteria=dict(PATTERN_ROSTER),
        applicability_rule="any_observation",
    ),
)

WIDE_QUESTIONS_BY_ID = {definition.question_id: definition for definition in WIDE_QUESTIONS}


def question_set_hash(definitions: tuple[QuestionDefinition, ...] = WIDE_QUESTIONS) -> str:
    payload = {
        "version": WIDE_QUESTION_SET_VERSION,
        "questions": [
            {
                "question_id": definition.question_id,
                "primitive": definition.primitive,
                "version": definition.version,
                "instructions": definition.instructions,
                "criteria": definition.criteria,
            }
            for definition in definitions
        ],
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _observations(projection: dict[str, Any]) -> list[dict[str, Any]]:
    return projection.get("project_observations", [])


def _has_any_observation(observation: dict[str, Any]) -> bool:
    return observation.get("affected_cases") is not None or observation.get("expression_local") is not None


def _mutation_observations(projection: dict[str, Any]) -> int:
    return sum(1 for observation in _observations(projection) if observation.get("affected_cases") is not None)


def _expression_observations(projection: dict[str, Any]) -> int:
    return sum(1 for observation in _observations(projection)
               if (observation.get("expression_local") or {}).get("median") is not None)


def applicability(definition: QuestionDefinition, projection: dict[str, Any]) -> tuple[bool, str]:
    observations = _observations(projection)
    rule = definition.applicability_rule
    if rule == "any_observation":
        usable = any(_has_any_observation(observation) for observation in observations)
        return usable, "USABLE_OBSERVATIONS_PRESENT" if usable else "NO_USABLE_OBSERVATIONS"
    if rule == "two_observations":
        count = sum(1 for observation in observations if _has_any_observation(observation))
        return count >= 2, f"OBSERVED_PROJECTS={count}"
    if rule == "three_mutation_observations":
        count = _mutation_observations(projection)
        return count >= 3, f"MUTATION_OBSERVATIONS={count}"
    if rule == "three_expression_observations":
        count = _expression_observations(projection)
        return count >= 3, f"EXPRESSION_OBSERVATIONS={count}"
    if rule == "coverage_imbalance":
        flagged = bool(projection.get("cross_project", {}).get("coverage_imbalance"))
        return flagged, f"COVERAGE_IMBALANCE={flagged}"
    raise ValueError(f"unknown applicability rule {rule}")


def applicability_map(projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        definition.question_id: {
            "applicable": applicable,
            "reason": reason,
            "rule": definition.applicability_rule,
        }
        for definition, applicable, reason in (
            (definition, *applicability(definition, projection)) for definition in WIDE_QUESTIONS
        )
    }
