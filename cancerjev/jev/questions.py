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

WIDE_QUESTION_SET_VERSION = "wide-v3"
DEEP_QUESTION_SET_VERSION = "deep-v1"

NOUL_TRUE_CRITERION = (
    "The stated proposition is supported by the supplied observations and their stated quality context."
)
NOUL_FALSE_CRITERION = (
    "The stated proposition is not supported by the supplied observations, or the observations are too "
    "incomplete to support it."
)

LIMITATION_ROSTER = {
    "COVERAGE": "Incomplete or unequal mutation/expression coverage limits interpretation.",
    "MISSINGNESS": "Missing measurements or absent columns dominate the evidence.",
    "MUTATION_ABSENCE": "No mutation observation exists for this cohort; an absent bucket is not a callable negative.",
    "EXPRESSION_SPARSITY": "Too few finite expression values exist to characterize the gene.",
    "PARTIAL_AGGREGATION": "A provider aggregation was incomplete.",
    "NONE": "No listed limitation dominates.",
    "OTHER": "A limitation outside the listed options dominates.",
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
        question_id="evidence_quality_adequate",
        primitive="NOUL",
        version=1,
        instructions=(
            "You are reviewing a compact deterministic profile of one gene in one TCGA-LUAD cohort. It states "
            "the examined-case count, the number of cases with a somatic mutation in this gene, the number of "
            "cases with an observed SSM (mutation-data coverage), the number of cases with gene expression "
            "values, and the local log2(UQFPKM+1) expression summary, with missingness and acquisition "
            "completeness stated explicitly. Decide whether this evidence is adequate to make a bounded "
            "investigation decision for this candidate. Adequacy means the measurements cover enough of the "
            "examined cohort and the stated missingness is small enough that deeper investigation would rest on "
            "observed evidence rather than on absent data. Biological novelty is not required."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="any_observation",
    ),
    QuestionDefinition(
        question_id="mutation_evidence_coherent",
        primitive="NOUL",
        version=1,
        instructions=(
            "Using the supplied mutation evidence (`cohort.affected_cases`, `cohort.ssm_coverage_cases`, "
            "`cohort.examined_cases`) and the stated partial-aggregation and missingness context, decide whether "
            "the mutation counts support a coherent interpretation for this cohort, rather than being an "
            "artifact of absent gene buckets, partial aggregation or incomplete mutation-data coverage. An "
            "observed zero is a valid observation; an absent bucket is not."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="mutation_observed",
    ),
    QuestionDefinition(
        question_id="expression_evidence_coherent",
        primitive="NOUL",
        version=1,
        instructions=(
            "Using the supplied local expression summary (`cohort.expression_median`, "
            "`cohort.expression_sample_sd`, `cohort.expression_n_finite`, `cohort.expression_n_missing`) and "
            "the stated missing-expression context, decide whether the expression evidence is coherent and "
            "interpretable for this cohort, rather than being dominated by missing values or too few finite "
            "measurements to characterize the gene."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="expression_observed",
    ),
    QuestionDefinition(
        question_id="signal_explained_by_coverage",
        primitive="NOUL",
        version=1,
        instructions=(
            "The profile states examined cases, mutation-data coverage and expression coverage for this cohort. "
            "Decide whether the apparent candidate signal (mutation count and/or expression level) is "
            "plausibly explained by unequal or incomplete coverage or by missing data, rather than by a "
            "candidate-relevant pattern in the observed cases."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="any_observation",
    ),
    QuestionDefinition(
        question_id="unresolved_uncertainty_material",
        primitive="NOUL",
        version=1,
        instructions=(
            "Given the stated evidence and its named limitations, decide whether a material, specific uncertainty "
            "about this candidate remains unresolved - one that a bounded registered follow-up over held or "
            "small public data could reduce. Do not count uncertainty that is merely 'more data would be nice'; "
            "the uncertainty must be specific and addressable."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="any_observation",
    ),
    QuestionDefinition(
        question_id="warrants_deeper_investigation",
        primitive="NOUL",
        version=1,
        instructions=(
            "Decide whether spending bounded follow-up budget on a deeper investigation of this candidate is "
            "justified now. Consider the stated evidence quality, the coherence of the mutation and expression "
            "evidence, whether coverage or missingness plausibly explains the apparent signal, and whether a "
            "material uncertainty remains. A follow-up is a small registered computation over held data or a "
            "small bounded public-data query, not a clinical action; biological novelty is not required."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="any_observation",
    ),
    QuestionDefinition(
        question_id="dominant_limitation",
        primitive="CHOICE",
        version=1,
        instructions=(
            "Which single limitation most dominates the interpretation of this candidate's evidence? Choose the "
            "one best-fitting option, or NONE when no listed limitation dominates."
        ),
        criteria=dict(LIMITATION_ROSTER),
        applicability_rule="any_observation",
    ),
)

WIDE_QUESTIONS_BY_ID = {definition.question_id: definition for definition in WIDE_QUESTIONS}

DEEP_LIMITATION_ROSTER = {
    "EVIDENCE_GAPS": "The revision records missing or unobserved evidence that limits the next step.",
    "SCOPE_LIMITS": "The single-cohort scope or the selection-biased examined gene set limits what this revision can support.",
    "INTEGRITY_CONCERNS": "A recorded integrity or reproducibility check was contradicted, or could not be observed from retained artifacts.",
    "NO_FURTHER_ACTION": "No further registered deterministic action is available for this evidence revision.",
    "NONE": "No listed limitation dominates.",
    "OTHER": "A limitation outside the listed options dominates.",
}

DEEP_QUESTIONS: tuple[QuestionDefinition, ...] = (
    QuestionDefinition(
        question_id="revision_reliable",
        primitive="NOUL",
        version=1,
        instructions=(
            "You are reviewing one immutable deterministic evidence revision for a single gene in one "
            "TCGA-LUAD cohort. The revision states which registered deterministic action produced it, the "
            "per-check outcome (VERIFIED, CONTRADICTED or NOT_OBSERVED) of each integrity/reproducibility "
            "check with the numbers it used, the project-level evidence it copied, its missing evidence, and "
            "the response-artifact provenance counts. Decide whether this revision can be relied on as the "
            "basis for one further bounded deterministic step. Rely on it only when the checks that could be "
            "observed are consistent, no check was contradicted, and any not-observed check does not remove "
            "the evidence the next step would rest on. A contradiction means the recorded numbers cannot all "
            "hold and must not be worked around."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="integrity_observed",
    ),
    QuestionDefinition(
        question_id="evidence_sufficient_for_next_step",
        primitive="NOUL",
        version=1,
        instructions=(
            "Using the revision's observed check numbers and its copied project-level evidence, decide whether "
            "the evidence actually held in this revision is sufficient to support one further bounded "
            "deterministic step, rather than stopping for lack of usable observations. Sufficiency means the "
            "step would rest on observed measurements with stated missingness, not on absent or unobserved "
            "data. Biological novelty is not required."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="revision_evidence_present",
    ),
    QuestionDefinition(
        question_id="next_step_warranted",
        primitive="NOUL",
        version=1,
        instructions=(
            "Decide whether spending further bounded budget on one more deterministic step for this candidate "
            "is justified now, given what this revision already establishes, the eligible registered actions "
            "listed in the revision, and the limitations it records. A further step is a small registered "
            "computation over already-retained evidence, not a clinical action and not a new data acquisition "
            "strategy. A low value here should not be read as biological irrelevance; it means the next "
            "deterministic step is not the best use of the remaining budget."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="revision_evidence_present",
    ),
    QuestionDefinition(
        question_id="stopping_more_honest",
        primitive="NOUL",
        version=1,
        instructions=(
            "Decide whether stopping this candidate's deterministic investigation here would be the more "
            "scientifically honest choice than continuing it, because the remaining uncertainty cannot be "
            "reduced by any further registered deterministic step over the retained evidence. Treat a "
            "candidate that has already established a verified, self-consistent revision as legitimately "
            "complete; do not demand more work merely for completeness."
        ),
        criteria={"true": NOUL_TRUE_CRITERION, "false": NOUL_FALSE_CRITERION},
        applicability_rule="revision_evidence_present",
    ),
    QuestionDefinition(
        question_id="dominant_limitation",
        primitive="CHOICE",
        version=1,
        instructions=(
            "Which single limitation most dominates the interpretation of this evidence revision? Choose the "
            "one best-fitting option, or NONE when no listed limitation dominates."
        ),
        criteria=dict(DEEP_LIMITATION_ROSTER),
        applicability_rule="revision_evidence_present",
    ),
)

DEEP_QUESTIONS_BY_ID = {definition.question_id: definition for definition in DEEP_QUESTIONS}

_PRIMITIVES = frozenset({"NOUL", "CHOICE", "SCORE"})
_APPLICABILITY_RULES = frozenset({
    "any_observation", "mutation_observed", "expression_observed",
    "revision_evidence_present", "integrity_observed",
})


def validate_definitions(definitions: tuple[QuestionDefinition, ...]) -> None:
    """Fail closed on question shapes the provider contract cannot accept.

    Mirrors the documented TypeSafe limits: Choice accepts at most 255 options,
    Score accepts 2-10 ordered levels, and Noul criteria are optional
    ``true``/``false`` descriptions. Called at import so a malformed question set
    can never reach the provider.
    """
    seen: set[str] = set()
    for definition in definitions:
        if not definition.question_id or definition.question_id in seen:
            raise ValueError(f"invalid or duplicate question id {definition.question_id!r}")
        seen.add(definition.question_id)
        if definition.primitive not in _PRIMITIVES:
            raise ValueError(f"{definition.question_id}: unknown primitive {definition.primitive!r}")
        if not isinstance(definition.instructions, str) or not definition.instructions.strip():
            raise ValueError(f"{definition.question_id}: instructions must be non-empty text")
        if not isinstance(definition.version, int) or definition.version < 1:
            raise ValueError(f"{definition.question_id}: version must be a positive integer")
        if definition.applicability_rule not in _APPLICABILITY_RULES:
            raise ValueError(f"{definition.question_id}: unknown applicability rule")
        criteria = definition.criteria
        if definition.primitive == "CHOICE":
            if not isinstance(criteria, dict) or not criteria:
                raise ValueError(f"{definition.question_id}: Choice requires option criteria")
            if len(criteria) > 255:
                raise ValueError(f"{definition.question_id}: Choice exceeds 255 options")
            if not all(isinstance(key, str) and key for key in criteria):
                raise ValueError(f"{definition.question_id}: Choice option keys must be non-empty strings")
        elif definition.primitive == "SCORE":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise ValueError(f"{definition.question_id}: Score requires 2-10 ordered levels")
        elif criteria is not None:
            if not isinstance(criteria, dict) or set(criteria) - {"true", "false"}:
                raise ValueError(f"{definition.question_id}: Noul criteria accept only true/false")


validate_definitions(WIDE_QUESTIONS)
validate_definitions(DEEP_QUESTIONS)


def question_set_hash(definitions: tuple[QuestionDefinition, ...], version: str) -> str:
    """Semantic identity of a question set.

    Covers the set version plus wording, criteria, primitive, version and
    applicability rule, because a changed applicability rule changes which
    judgments a stored evaluation holds. The version is explicit so two sets can
    never share an identity by accident.
    """
    if not version:
        raise ValueError("question_set_hash requires an explicit question-set version")
    payload = {
        "version": version,
        "questions": [
            {
                "question_id": definition.question_id,
                "primitive": definition.primitive,
                "version": definition.version,
                "instructions": definition.instructions,
                "criteria": definition.criteria,
                "applicability_rule": definition.applicability_rule,
            }
            for definition in definitions
        ],
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def wide_question_set_hash() -> str:
    return question_set_hash(WIDE_QUESTIONS, WIDE_QUESTION_SET_VERSION)


def deep_question_set_hash() -> str:
    return question_set_hash(DEEP_QUESTIONS, DEEP_QUESTION_SET_VERSION)


def applicability(definition: QuestionDefinition, projection: dict[str, Any]) -> tuple[bool, str]:
    cohort = projection.get("cohort", {})
    revision = projection.get("revision", {})
    mutation_observed = cohort.get("mutation_observed") is True
    expression_observed = cohort.get("expression_observed") is True
    rule = definition.applicability_rule
    if rule == "any_observation":
        usable = mutation_observed or expression_observed
        return usable, "USABLE_OBSERVATIONS_PRESENT" if usable else "NO_USABLE_OBSERVATIONS"
    if rule == "mutation_observed":
        return mutation_observed, f"MUTATION_OBSERVED={mutation_observed}"
    if rule == "expression_observed":
        return expression_observed, f"EXPRESSION_OBSERVED={expression_observed}"
    if rule == "revision_evidence_present":
        present = revision.get("evidence_present") is True
        return present, f"EVIDENCE_PRESENT={present}"
    if rule == "integrity_observed":
        observed = revision.get("integrity_observed") is True
        return observed, f"INTEGRITY_OBSERVED={observed}"
    raise ValueError(f"unknown applicability rule {rule}")


def applicability_map(projection: dict[str, Any],
                      definitions: tuple[QuestionDefinition, ...] = WIDE_QUESTIONS,
                      ) -> dict[str, dict[str, Any]]:
    return {
        definition.question_id: {
            "applicable": applicable,
            "reason": reason,
            "rule": definition.applicability_rule,
        }
        for definition, applicable, reason in (
            (definition, *applicability(definition, projection)) for definition in definitions
        )
    }
