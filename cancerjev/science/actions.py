"""Registered deterministic follow-up actions over immutable statistical evidence.

An action is a bounded, reproducible computation over evidence that already exists.
It never acquires data, never calls a model, never computes a new biological
quantity and never rewrites the evidence it reads. Eligibility is a deterministic
prerequisite check: what cannot be verified from retained evidence is NOT_OBSERVED,
never a silent pass.

Result ids, persistence and selection policy are owned by ``research``; this module
owns the action contract, eligibility and the deterministic computation.

Two inputs are admitted: the canonical ``StatisticalState`` and an immutable
``EvidenceState`` revision. Revision checks decode the retained source artifact
through the current schema-4 codec; they never reconstruct a legacy model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, cast

from cancerjev.domain._json import decode
from cancerjev.domain.actions import IntegrityCheck, IntegrityOutcome
from cancerjev.domain.codecs import read_state, state_identity
from cancerjev.domain.discovery import (
    MUTATION_CANONICAL_COMPOSITION_METHOD_ID,
    MUTATION_CANONICAL_COMPOSITION_VERSION,
    ExpressionDiscoverySpec,
)
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import EvidenceState, InputArtifactRef, MeasuredObservation
from cancerjev.domain.measurements import (
    MetricAvailability,
    MetricRecord,
    ObservedCount,
    ObservedScalar,
)
from cancerjev.domain.scientific import (
    CnvOccurrenceResult,
    ExpressionSummaryResult,
    MutationCountResult,
    StatisticalState,
    UnavailableLane,
)
from cancerjev.science.descriptors import cnv_category_summaries, expression_tail_descriptor

CHECK_VERIFIED: IntegrityOutcome = "VERIFIED"
CHECK_CONTRADICTED: IntegrityOutcome = "CONTRADICTED"
CHECK_NOT_OBSERVED: IntegrityOutcome = "NOT_OBSERVED"

OUTCOME_COMPLETED = "COMPLETED"

# The only registered actions that may carry measured observations into a new
# evidence revision. A hypothesis can only be tested by an action in this set:
# integrity and summary actions describe or verify existing evidence and cannot
# discriminate between competing explanations.
EVIDENCE_PRODUCING_ACTION_IDS = frozenset({"OCCURRENCE_DETAIL_EVIDENCE_V1"})


class ActionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    version: str
    title: str
    question: str
    interpretation: str
    method_id: str
    method_version: str
    unit: str
    required_evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    input_kind: str = "STATISTICAL_STATE"
    changes_evidence: bool = True

    def ref(self, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "version": self.version,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "parameters_hash": hashlib.sha256(canonical_json(parameters or {})).hexdigest(),
        }

    def payload(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id, "version": self.version, "title": self.title,
            "question": self.question, "interpretation": self.interpretation,
            "method_id": self.method_id, "method_version": self.method_version,
            "unit": self.unit, "required_evidence": list(self.required_evidence),
            "input_kind": self.input_kind,
            "limitations": list(self.limitations), "changes_evidence": self.changes_evidence,
        }


ACTION_REGISTRY_VERSION = "4"

ACTION_REGISTRY: dict[str, ActionDefinition] = {
    "CHECK_EVIDENCE_INTEGRITY_V1": ActionDefinition(
        action_id="CHECK_EVIDENCE_INTEGRITY_V1", version="1",
        title="Check candidate evidence integrity",
        question=(
            "Is the candidate's recorded measured evidence reproducible from its own retained response "
            "artifacts and internally consistent across its lanes?"
        ),
        interpretation=(
            "Each check is a falsifiable claim over recorded evidence. A CONTRADICTED check means the "
            "recorded numbers cannot all hold, so the candidate must not be advanced on them; a "
            "NOT_OBSERVED check means the recorded evidence does not permit verification and stays "
            "explicit rather than passing by default."
        ),
        method_id="EVIDENCE_INTEGRITY_V1", method_version="1",
        unit="checks",
        required_evidence=(
            "POPULATION_FRAME", "MUTATION_COUNTS", "EXPRESSION_COVERAGE", "TESTED_UNIVERSE_SELECTION",
            "RESPONSE_ARTIFACTS",
        ),
        limitations=(
            "Verifies recorded evidence and retained response bytes; it does not re-derive provider "
            "aggregations and does not acquire new GDC evidence.",
            "A verified check is provenance and consistency evidence, not biological evidence.",
            "A single cohort is examined; no cross-project comparison is made.",
        ),
        input_kind="STATISTICAL_STATE",
    ),
    "CHECK_REVISION_FAITHFULNESS_V1": ActionDefinition(
        action_id="CHECK_REVISION_FAITHFULNESS_V1", version="1",
        title="Check evidence-revision faithfulness",
        question=(
            "Does this evidence revision restate the accepted source evidence exactly, keep the same "
            "retained response provenance, and bind the source revision it claims, so a later step can "
            "rely on the revision chain?"
        ),
        interpretation=(
            "A CONTRADICTED check means the revision and the accepted evidence disagree (or the source "
            "artifact is not the state it claims), so no further step may rest on this revision; a "
            "NOT_OBSERVED check means the retained source artifact does not permit verification and is "
            "reported rather than assumed."
        ),
        method_id="REVISION_FAITHFULNESS_V1", method_version="1",
        unit="checks",
        required_evidence=(
            "SOURCE_STATE_ARTIFACT", "REVISION_PROJECT_EVIDENCE", "REVISION_PROVENANCE", "REVISION_CHAIN",
        ),
        limitations=(
            "Verifies that the revision restates the accepted evidence and keeps its provenance; it "
            "re-derives no provider aggregation and computes no new biological quantity.",
            "A verified check is evidence-chain integrity, not biological evidence.",
            "Source artifacts are read by the artifact id recorded in the revision; a missing artifact "
            "is reported as NOT_OBSERVED.",
        ),
        input_kind="EVIDENCE_STATE",
    ),
    "SUMMARIZE_EXPRESSION_TAIL_V1": ActionDefinition(
        action_id="SUMMARIZE_EXPRESSION_TAIL_V1", version="1",
        title="Summarize the held within-gene expression tail",
        question=(
            "Which held case-labelled observations fall outside the fixed Tukey 1.5xIQR fences "
            "for this gene's log2(UQFPKM+1) distribution?"
        ),
        interpretation=(
            "The result is a within-gene descriptive tail over the retained cohort frame. It is "
            "not differential expression, a p-value, a diagnosis or a causal effect."
        ),
        method_id="EXPRESSION_TUKEY_TAIL_V1", method_version="1", unit="cases",
        required_evidence=("CASE_LABELLED_EXPRESSION_VALUES", "COMPLETE_POPULATION_FRAME"),
        limitations=(
            "Requires at least 20 finite held values and a positive IQR.",
            "Selected on the same cohort; no confirmatory or tumor-normal claim is supported.",
            "Acquires no data and calls no model.",
        ),
        input_kind="STATISTICAL_STATE",
    ),
    "SUMMARIZE_CNV_CATEGORIES_V1": ActionDefinition(
        action_id="SUMMARIZE_CNV_CATEGORIES_V1", version="1",
        title="Summarize held provider-labelled CNV categories",
        question=(
            "How many distinct positive cases occur in each exact provider CNV category, while "
            "retaining cases assigned multiple categories and caller context?"
        ),
        interpretation=(
            "Counts are positive occurrence descriptors only. Absence is never neutral or negative, "
            "and overlapping category case sets are not summed."
        ),
        method_id="CNV_INDEXED_POSITIVE_CASES_V1", method_version="1", unit="cases",
        required_evidence=("COMPLETE_CNV_OCCURRENCES", "PROVIDER_CATEGORY", "COHORT_CASE_FRAME"),
        limitations=(
            "Generic Loss remains distinct from Homozygous Deletion.",
            "Numerical copy-number values are not compared across callers.",
            "Acquires no data and calls no model.",
        ),
        input_kind="STATISTICAL_STATE",
    ),
    "OCCURRENCE_DETAIL_EVIDENCE_V1": ActionDefinition(
        action_id="OCCURRENCE_DETAIL_EVIDENCE_V1", version="1",
        title="Measure canonical occurrence detail for one candidate gene",
        question=(
            "What is this gene's canonical-transcript consequence composition and transcript "
            "context in this cohort, measured from its complete bounded released-occurrence "
            "detail pages?"
        ),
        interpretation=(
            "A descriptive canonical-only composition over the declared project/gene occurrence "
            "detail pages produced by the shared MUTATION_CANONICAL_COMPOSITION_V1 reducer. It is "
            "not driver significance, not a p-value and not a causal claim."
        ),
        method_id=MUTATION_CANONICAL_COMPOSITION_METHOD_ID,
        method_version=MUTATION_CANONICAL_COMPOSITION_VERSION, unit="occurrences",
        required_evidence=("MUTATION_CANONICAL_OCCURRENCE_DETAIL", "COHORT_CASE_FRAME"),
        limitations=(
            "Bounded per-gene detail pages under a declared page cap; over-cap yields an "
            "unavailable observation with its reason, never a truncated claim.",
            "Protein-position recurrence is not exposed by the occurrence endpoint and stays "
            "unavailable here.",
            "Composition is descriptive only; no p-value, q-value or driver-significance claim "
            "is representable.",
        ),
        input_kind="STATISTICAL_STATE",
    ),
}


@dataclass(frozen=True)
class ActionEligibility:
    action_id: str
    eligible: bool
    reasons: tuple[str, ...]
    prerequisites: dict[str, Any]


@dataclass(frozen=True)
class ActionOutcome:
    action_id: str
    status: str
    checks: tuple[IntegrityCheck, ...]
    inputs: tuple[InputArtifactRef, ...]
    contradictions: int
    unavailable_reason: str | None
    definition: ActionDefinition
    observations: tuple[MeasuredObservation, ...] = ()

    def __post_init__(self) -> None:
        if self.contradictions != sum(check.outcome == CHECK_CONTRADICTED for check in self.checks):
            raise ActionError("INVALID_CHECK_SUMMARY", "contradiction count disagrees with checks")
        if type(self.inputs) is not tuple or not all(isinstance(i, InputArtifactRef) for i in self.inputs):
            raise ActionError("INVALID_ACTION_INPUTS", "action inputs must be typed artifact references")
        if type(self.observations) is not tuple \
                or not all(isinstance(o, MeasuredObservation) for o in self.observations):
            raise ActionError("INVALID_OBSERVATIONS", "observations must be typed measured records")
        if self.observations and self.action_id not in EVIDENCE_PRODUCING_ACTION_IDS:
            raise ActionError("UNEXPECTED_OBSERVATIONS",
                              f"{self.action_id} is not a measured-evidence-producing action")

    @property
    def verified(self) -> int:
        return sum(1 for check in self.checks if check.outcome == CHECK_VERIFIED)

    @property
    def not_observed(self) -> int:
        return sum(1 for check in self.checks if check.outcome == CHECK_NOT_OBSERVED)


def _observed_count(measurement: Any) -> int | None:
    return measurement.value if isinstance(measurement, ObservedCount) else None


def _observed_scalar(measurement: Any) -> float | None:
    return measurement.value if isinstance(measurement, ObservedScalar) else None


def _metric_value(record: Any) -> float | int | None:
    """Observed value of a typed measurement or metric record, else None."""
    if isinstance(record, MetricRecord):
        return record.value if record.availability is MetricAvailability.OBSERVED else None
    if isinstance(record, (ObservedCount, ObservedScalar)):
        return record.value
    if type(record) in (int, float):
        # The exact type check admits only plain int/float values.
        return cast(float | int, record)
    return None


def _metric_availability(measurement: Any) -> str:
    return "OBSERVED" if isinstance(measurement, (ObservedCount, ObservedScalar)) else "NOT_OBSERVED"


def _check(check_id: str, claim: str, outcome: IntegrityOutcome, *, observed: dict[str, Any],
           expected: dict[str, Any] | None = None, notes: tuple[str, ...] = (),
           limitations: tuple[str, ...] = (), n_effective: int | None = None) -> IntegrityCheck:
    return IntegrityCheck(check_id, claim, outcome, canonical_json(observed), canonical_json(expected or {}),
                          n_effective, notes, limitations)


def _examined_ids(state: StatisticalState) -> list[str]:
    return list(state.projects[0].population.frame.examined_ids) if state.projects else []


def _state_prerequisites(state: StatisticalState) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    prerequisites: dict[str, Any] = {
        "gene_id": state.entity.gene_id,
        "examined_genes_n": state.tested_context.examined_genes_n,
        "source_count": len(state.sources),
        "mutation_projects": len(state.projects),
        "expression_projects": len(state.projects),
        "examined_n": len(_examined_ids(state)),
    }
    if not state.projects:
        reasons.append("EVIDENCE_SECTION_MISSING:projects")
    if not _examined_ids(state):
        reasons.append("EXAMINED_POPULATION_EMPTY")
    if not state.sources:
        reasons.append("PROVENANCE_SOURCES_MISSING")
    if not state.projects:
        reasons.append("MUTATION_LANE_MISSING")
        reasons.append("EXPRESSION_LANE_MISSING")
    return reasons, prerequisites


def _revision_prerequisites(revision: EvidenceState) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    prerequisites: dict[str, Any] = {
        "evidence_state_id": revision.source_state.state_id,
        "iteration_number": revision.revision_index,
        "gene_id": revision.entity.gene_id,
        "source_count": len(revision.sources),
    }
    if revision.revision_index < 1:
        reasons.append("REVISION_ITERATION_INVALID")
    if revision.parent_evidence_hash is None:
        reasons.append("REVISION_PARENT_MISSING")
    if not revision.project_evidence:
        reasons.append("REVISION_PROJECT_EVIDENCE_MISSING")
    if not revision.sources:
        reasons.append("PROVENANCE_SOURCES_MISSING")
    return reasons, prerequisites


def eligibility(record: StatisticalState | EvidenceState, definition: ActionDefinition) -> ActionEligibility:
    """Deterministic prerequisites for one action on its declared input kind."""
    if definition.input_kind == "STATISTICAL_STATE":
        if not isinstance(record, StatisticalState):
            raise ActionError("WRONG_INPUT_KIND", f"{definition.action_id} requires a StatisticalState")
        reasons, prerequisites = _state_prerequisites(record)
        if definition.action_id == "SUMMARIZE_EXPRESSION_TAIL_V1":
            expression = next((project.expression for project in record.projects
                               if isinstance(project.expression, ExpressionSummaryResult)), None)
            if expression is None:
                reasons.append("EXPRESSION_VALUES_NOT_OBSERVED")
            else:
                descriptor = expression_tail_descriptor(expression, ExpressionDiscoverySpec())
                prerequisites["expression_valid_n"] = descriptor.valid_n
                prerequisites["tail_availability"] = descriptor.availability.value
                if descriptor.availability is not MetricAvailability.OBSERVED:
                    reasons.append(descriptor.reason or "EXPRESSION_TAIL_UNAVAILABLE")
        elif definition.action_id == "SUMMARIZE_CNV_CATEGORIES_V1":
            cnv = next((project.cnv for project in record.projects
                        if isinstance(project.cnv, CnvOccurrenceResult)), None)
            if cnv is None:
                reasons.append("CNV_OCCURRENCES_NOT_OBSERVED")
            else:
                prerequisites["cnv_occurrences"] = len(cnv.occurrences)
        elif definition.action_id == "OCCURRENCE_DETAIL_EVIDENCE_V1":
            mutation = next((project.mutation for project in record.projects
                             if isinstance(project.mutation, MutationCountResult)), None)
            if mutation is None or not isinstance(mutation.affected_cases, ObservedCount):
                reasons.append("MUTATION_MEASUREMENT_NOT_OBSERVED")
            else:
                prerequisites["affected_cases"] = mutation.affected_cases.value
    elif definition.input_kind == "EVIDENCE_STATE":
        if not isinstance(record, EvidenceState):
            raise ActionError("WRONG_INPUT_KIND", f"{definition.action_id} requires an EvidenceState")
        reasons, prerequisites = _revision_prerequisites(record)
    else:
        raise ActionError("UNKNOWN_INPUT_KIND", f"{definition.action_id}: {definition.input_kind!r}")
    return ActionEligibility(action_id=definition.action_id, eligible=not reasons,
                             reasons=tuple(reasons), prerequisites=prerequisites)


def eligible_actions(record: StatisticalState | EvidenceState, input_kind: str,
                     registry: dict[str, ActionDefinition] | None = None) -> tuple[ActionEligibility, ...]:
    """Eligibility of every registered action that declares the given input kind."""
    definitions = registry or ACTION_REGISTRY
    return tuple(
        eligibility(record, definitions[action_id])
        for action_id in sorted(definitions)
        if definitions[action_id].input_kind == input_kind
    )


def _check_frame_agreement(state: StatisticalState) -> IntegrityCheck:
    examined_n = len(_examined_ids(state))
    mutation_examined = [
        len(project.mutation.frame.examined_ids)
        for project in state.projects
    ]
    expression_examined = [len(project.population.frame.examined_ids) for project in state.projects]
    observed = {
        "eligible_n": None,
        "examined_n": examined_n,
        "mutation_examined_cases": sorted(mutation_examined),
        "expression_examined_cases": sorted(expression_examined),
    }
    values = [examined_n, *mutation_examined, *expression_examined]
    if examined_n <= 0 or not mutation_examined or not expression_examined:
        return _check(
            "COHORT_FRAME_AGREEMENT",
            "Every lane examined the same recorded cohort case frame.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=None,
            notes=("a lane does not record an examined-case count",),
        )
    outcome = CHECK_VERIFIED if set(values) == {examined_n} else CHECK_CONTRADICTED
    return _check(
        "COHORT_FRAME_AGREEMENT",
        "Every lane examined the same recorded cohort case frame.",
        outcome, observed=observed, expected={"examined_n": examined_n}, n_effective=examined_n,
        notes=() if outcome == CHECK_VERIFIED else ("lanes disagree on the examined case frame",),
    )


def _expression_coverage_entry(project: Any) -> dict[str, Any]:
    expression = project.expression
    if isinstance(expression, UnavailableLane):
        return {
            "project_id": project.population.frame.project_id, "examined_cases": None,
            "cases_with_expression": None, "missing_measurements": None,
            "returned_case_columns": None, "valid_measurements": None, "n_missing": None,
            "n_missing_case_columns": None, "missing_case_ids_n": None, "n_returned": None,
            "n_finite": None,
        }
    coverage = expression.coverage
    examined = len(coverage.frame.examined_ids)
    valid = len(coverage.valid_ids)
    missing_columns = sum(len(group.ids) for group in coverage.missing
                          if group.reason == "CASE_COLUMN_NOT_RETURNED")
    return {
        "project_id": project.population.frame.project_id,
        "examined_cases": examined,
        "cases_with_expression": valid,
        "missing_measurements": examined - valid,
        "returned_case_columns": len(coverage.returned_ids),
        "valid_measurements": valid,
        "n_missing": examined - valid,
        "n_missing_case_columns": missing_columns,
        "missing_case_ids_n": missing_columns,
        "n_returned": len(coverage.returned_ids),
        "n_finite": len(expression.values),
    }


def _check_expression_coverage(state: StatisticalState) -> IntegrityCheck:
    observed: dict[str, Any] = {"projects": []}
    contradictions: list[str] = []
    unverifiable: list[str] = []
    for project in state.projects:
        entry = _expression_coverage_entry(project)
        observed["projects"].append(entry)
        required = (entry["examined_cases"], entry["cases_with_expression"],
                    entry["missing_measurements"], entry["n_missing"],
                    entry["n_missing_case_columns"], entry["missing_case_ids_n"])
        if any(value is None for value in required):
            unverifiable.append(f"{entry['project_id']}: coverage fields not observed")
            continue
        if entry["cases_with_expression"] + entry["missing_measurements"] != entry["examined_cases"]:
            contradictions.append(f"{entry['project_id']}: cases_with_expression + missing != examined")
        if entry["missing_measurements"] != entry["n_missing"]:
            contradictions.append(f"{entry['project_id']}: recorded total missingness disagrees")
        if entry["n_missing_case_columns"] != entry["missing_case_ids_n"]:
            contradictions.append(f"{entry['project_id']}: recorded unreturned-column counts disagree")
        if entry["n_returned"] is not None and entry["n_missing_case_columns"] is not None \
                and entry["n_returned"] + entry["n_missing_case_columns"] != entry["examined_cases"]:
            contradictions.append(
                f"{entry['project_id']}: returned case columns + unreturned columns != examined"
            )
        if entry["valid_measurements"] is not None and entry["n_returned"] is not None \
                and entry["valid_measurements"] > entry["n_returned"]:
            contradictions.append(f"{entry['project_id']}: valid_measurements exceeds returned columns")
        if entry["valid_measurements"] is not None and entry["n_finite"] is not None \
                and entry["valid_measurements"] != entry["n_finite"]:
            contradictions.append(f"{entry['project_id']}: valid_measurements != finite values")
    if contradictions:
        outcome = CHECK_CONTRADICTED
    elif unverifiable or not state.projects:
        outcome = CHECK_NOT_OBSERVED
    else:
        outcome = CHECK_VERIFIED
    notes = tuple(contradictions[:3] + unverifiable[:3])
    return _check(
        "EXPRESSION_COVERAGE_ARITHMETIC",
        "Recorded expression coverage and missingness agree per project and against the examined frame.",
        outcome, observed=observed,
        expected={"cases_with_expression + missing_measurements": "examined_cases",
                  "returned case columns + unreturned columns": "examined_cases"},
        n_effective=len(state.projects), notes=notes,
    )


def _check_mutation_scope(state: StatisticalState) -> IntegrityCheck:
    scope_projects = list(state.research.projects)
    observed: dict[str, Any] = {"projects": [], "scope_projects": scope_projects}
    contradictions: list[str] = []
    unverifiable: list[str] = []
    for project in state.projects:
        project_id = project.population.frame.project_id
        mutation = project.mutation
        affected = _observed_count(mutation.affected_cases)
        with_ssm = _observed_count(mutation.ssm_coverage_cases)
        examined = len(mutation.frame.examined_ids)
        observed["projects"].append({
            "project_id": project_id, "affected_case_count": affected,
            "project_case_with_ssm": with_ssm, "examined_cases": examined,
        })
        if project_id not in scope_projects:
            contradictions.append(f"{project_id}: mutation result outside the recorded scope")
        if affected is None:
            unverifiable.append(f"{project_id}: affected case count not observed")
            continue
        if affected > examined:
            contradictions.append(f"{project_id}: affected count exceeds the examined frame")
        if with_ssm is None:
            unverifiable.append(f"{project_id}: project SSM coverage not observed")
            continue
        if affected > with_ssm:
            contradictions.append(f"{project_id}: affected count exceeds project SSM-positive cases")
    if contradictions:
        outcome = CHECK_CONTRADICTED
    elif unverifiable or not state.projects:
        outcome = CHECK_NOT_OBSERVED
    else:
        outcome = CHECK_VERIFIED
    return _check(
        "MUTATION_COUNT_SCOPE",
        "The recorded per-gene affected count is scoped to the examined project and stays within its SSM coverage.",
        outcome, observed=observed,
        expected={"affected_case_count <= project_case_with_ssm": True, "project in scope": True},
        n_effective=len(state.projects), notes=tuple(contradictions[:3] + unverifiable[:3]),
        limitations=(
            "Provider counts cannot distinguish mutation absence from unassayed cases.",
            "No recurrence fraction is computed; the count has no matched denominator.",
        ),
    )


def _read_bytes(read_artifact: Callable[[str], bytes | None], artifact_id: Any) -> bytes | None:
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    try:
        return read_artifact(artifact_id)
    except (OSError, ValueError, KeyError):
        return None


def _check_tested_universe(state: StatisticalState,
                           read_artifact: Callable[[str], bytes | None],
                           ) -> tuple[IntegrityCheck, list[InputArtifactRef]]:
    ref = state.tested_context.selection_artifact_id
    recorded_hash = state.tested_context.examined_genes_hash
    examined_genes_n = state.tested_context.examined_genes_n
    gene_id = state.entity.gene_id
    content = _read_bytes(read_artifact, ref)
    observed: dict[str, Any] = {
        "recorded_hash": recorded_hash, "recomputed_hash": None,
        "selected_gene_ids_n": None, "gene_in_selected_ids": None, "examined_genes_n": examined_genes_n,
    }
    inputs = [InputArtifactRef("SELECTION_ARTIFACT", ref, recorded_hash, False)] if ref else []
    if content is None:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=("retained selection artifact is unavailable",),
        ), inputs
    recomputed = hashlib.sha256(content).hexdigest()
    observed["recomputed_hash"] = recomputed
    input_entry = InputArtifactRef("SELECTION_ARTIFACT", ref, recomputed, recomputed == recorded_hash)
    if recomputed != recorded_hash:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_CONTRADICTED, observed=observed, expected={"examined_genes_hash": recorded_hash},
            n_effective=1,
            notes=("retained selection bytes do not hash to the recorded examined-genes hash",),
        ), [input_entry]
    try:
        payload = canonical_payload(content)
    except ValueError as exc:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=(f"selection artifact is not canonical JSON: {exc}",),
        ), [input_entry]
    selected = payload.get("selected_gene_ids") if isinstance(payload, dict) else None
    selected_ids = selected if isinstance(selected, list) else None
    observed["selected_gene_ids_n"] = len(selected_ids) if selected_ids is not None else None
    observed["gene_in_selected_ids"] = gene_id in selected_ids if selected_ids is not None else None
    if selected_ids is None:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=("selection artifact does not record the selected gene ids",),
        ), [input_entry]
    contradictions = []
    if gene_id not in selected_ids:
        contradictions.append("candidate gene is absent from the retained selected gene ids")
    if examined_genes_n != len(selected_ids):
        contradictions.append("examined_genes_n disagrees with the retained selected gene ids")
    outcome = CHECK_CONTRADICTED if contradictions else CHECK_VERIFIED
    return _check(
        "TESTED_UNIVERSE_REPRODUCIBLE",
        "The recorded examined gene universe is reproducible from its retained selection artifact.",
        outcome, observed=observed, expected={"examined_genes_n": len(selected_ids)},
        n_effective=len(selected_ids), notes=tuple(contradictions),
    ), [input_entry]


def _check_response_integrity(state: StatisticalState,
                              read_artifact: Callable[[str], bytes | None],
                              ) -> tuple[IntegrityCheck, list[InputArtifactRef]]:
    verified = 0
    mismatched: list[str] = []
    unavailable: list[str] = []
    attempts_unlinked: list[str] = []
    inputs: list[InputArtifactRef] = []
    for operational in state.operational_sources:
        source = operational.source
        ref = operational.artifact_id
        recorded = source.response_hash
        endpoint = source.endpoint
        if not operational.attempt_id:
            attempts_unlinked.append(endpoint)
        content = _read_bytes(read_artifact, ref)
        if content is None:
            unavailable.append(ref)
            inputs.append(InputArtifactRef("RESPONSE_ARTIFACT", ref, recorded, False))
            continue
        recomputed = hashlib.sha256(content).hexdigest()
        matched = recomputed == recorded
        verified += int(matched)
        if not matched:
            mismatched.append(f"{endpoint}: retained bytes do not hash to the recorded response hash")
        inputs.append(InputArtifactRef("RESPONSE_ARTIFACT", ref, recomputed, matched))
    sources = len(state.operational_sources)
    observed = {
        "sources": sources, "verified": verified, "mismatched": len(mismatched),
        "unavailable": len(unavailable), "without_attempt_link": len(attempts_unlinked),
    }
    if mismatched:
        outcome = CHECK_CONTRADICTED
    elif not sources or unavailable or attempts_unlinked:
        outcome = CHECK_NOT_OBSERVED
    else:
        outcome = CHECK_VERIFIED
    notes: list[str] = list(mismatched[:2])
    if unavailable:
        notes.append(f"{len(unavailable)} retained response artifact(s) unavailable")
    if attempts_unlinked:
        notes.append(f"{len(attempts_unlinked)} source(s) without an acquisition attempt link")
    return _check(
        "RESPONSE_ARTIFACT_INTEGRITY",
        "Every recorded source response is retained, hashes to its recorded response hash, and names its acquisition attempt.",
        outcome, observed=observed, expected={"verified": sources}, n_effective=sources,
        notes=tuple(notes),
    ), inputs


def canonical_payload(content: bytes) -> Any:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def _source_metrics(state: StatisticalState, project_id: str) -> dict[str, Any]:
    project = next((item for item in state.projects
                    if item.population.frame.project_id == project_id), None)
    if project is None:
        return {}
    mutation = project.mutation
    expression = project.expression
    if isinstance(expression, ExpressionSummaryResult):
        cases_with_expression: Any = len(expression.coverage.valid_ids)
        missing_measurements: Any = len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids)
    else:
        cases_with_expression = None
        missing_measurements = None
    return {
        "affected_case_count": mutation.affected_cases,
        "examined_cases": len(mutation.frame.examined_ids),
        "project_case_with_ssm": mutation.ssm_coverage_cases,
        "cases_with_expression": cases_with_expression,
        "missing_measurements": missing_measurements,
    }


def _check_source_evidence_restated(revision: EvidenceState, state: StatisticalState | None,
                                    ) -> IntegrityCheck:
    observed: dict[str, Any] = {"projects": []}
    contradictions: list[str] = []
    unverifiable: list[str] = []
    for row in revision.project_evidence:
        project_id = row.project_id
        source = _source_metrics(state, project_id) if state is not None else {}
        entry: dict[str, Any] = {"project_id": project_id}
        for key, record in row.metrics():
            entry[key] = record.value
            entry[f"{key}_availability"] = record.availability.value
            original = source.get(key)
            copied_value = _metric_value(record)
            original_value = _metric_value(original)
            if copied_value is None or original_value is None:
                unverifiable.append(f"{project_id}:{key}")
            elif copied_value != original_value:
                contradictions.append(
                    f"{project_id}:{key} restated {copied_value} but the accepted evidence records "
                    f"{original_value}"
                )
        observed["projects"].append(entry)
    notes: tuple[str, ...]
    if state is None:
        outcome = CHECK_NOT_OBSERVED
        notes = ("the accepted source artifact is unavailable, so restatement cannot be checked",)
    elif contradictions:
        outcome = CHECK_CONTRADICTED
        notes = tuple(contradictions[:3])
    elif unverifiable or not revision.project_evidence:
        outcome = CHECK_NOT_OBSERVED
        notes = (f"{len(unverifiable)} copied metric(s) not observed on both sides",)
    else:
        outcome = CHECK_VERIFIED
        notes = ()
    return _check(
        "SOURCE_EVIDENCE_RESTATED",
        "Every copied project-level metric equals the accepted source evidence it restates.",
        outcome, observed=observed, expected={"copied metrics": "equal to the accepted state"},
        n_effective=len(revision.project_evidence), notes=notes,
        limitations=("Restatement compares recorded values only; it re-derives no provider aggregation.",),
    )


def _source_triples(sources: tuple[Any, ...]) -> set[tuple[Any, Any, Any, Any]]:
    return {
        (source.endpoint, source.request_hash, source.response_hash, source.parser_version)
        for source in sources
    }


def _check_source_provenance_unchanged(revision: EvidenceState, state: StatisticalState | None,
                                       ) -> IntegrityCheck:
    revision_triples = _source_triples(revision.sources)
    state_triples = _source_triples(state.sources) if state is not None else set()
    added = sorted(revision_triples - state_triples)
    removed = sorted(state_triples - revision_triples)
    observed = {
        "revision_sources": len(revision_triples), "source_sources": len(state_triples),
        "added": len(added), "removed": len(removed),
    }
    if state is None:
        outcome = CHECK_NOT_OBSERVED
        notes: tuple[str, ...] = ("the accepted source artifact is unavailable, so provenance cannot be compared",)
    elif not state_triples:
        outcome = CHECK_NOT_OBSERVED
        notes = ("the accepted evidence records no provenance sources",)
    elif added or removed:
        outcome = CHECK_CONTRADICTED
        notes = (f"{len(added)} source(s) appear only in the revision and {len(removed)} only in the accepted evidence",)
    else:
        outcome = CHECK_VERIFIED
        notes = ()
    return _check(
        "SOURCE_PROVENANCE_UNCHANGED",
        "The revision keeps exactly the accepted evidence's retained response provenance "
        "(endpoint, canonical request hash, response hash and parser version) and substitutes nothing.",
        outcome, observed=observed, expected={"revision sources": len(state_triples)},
        n_effective=len(revision_triples), notes=notes,
    )


def _check_source_identity_reproducible(revision: EvidenceState, state: StatisticalState | None,
                                        artifact_hash: str | None,
                                        ) -> tuple[IntegrityCheck, list[InputArtifactRef]]:
    recorded_artifact = revision.source_state.state_artifact_sha256
    recorded_identity = revision.source_state.state_identity_hash
    ref = revision.source_state.state_artifact_id
    inputs = [InputArtifactRef("SOURCE_STATE_ARTIFACT", ref,
                               artifact_hash or recorded_artifact, False)]
    observed = {
        "recorded_artifact_sha256": recorded_artifact, "recomputed_artifact_sha256": artifact_hash,
        "recorded_state_identity_hash": recorded_identity, "recomputed_state_identity_hash": None,
    }
    if state is None or artifact_hash is None:
        return _check(
            "SOURCE_STATE_IDENTITY_REPRODUCIBLE",
            "The retained source artifact is the state the revision binds and its scientific identity matches.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=("the retained source artifact is unavailable",),
        ), inputs
    recomputed_identity = state_identity(state)
    observed["recomputed_state_identity_hash"] = recomputed_identity
    contradictions = []
    if artifact_hash != recorded_artifact:
        contradictions.append("retained source bytes do not hash to the recorded artifact hash")
    if recomputed_identity != recorded_identity:
        contradictions.append("recomputed state identity does not match the recorded state identity hash")
    outcome = CHECK_CONTRADICTED if contradictions else CHECK_VERIFIED
    inputs = [InputArtifactRef("SOURCE_STATE_ARTIFACT", ref, artifact_hash, outcome == CHECK_VERIFIED)]
    return _check(
        "SOURCE_STATE_IDENTITY_REPRODUCIBLE",
        "The retained source artifact is the state the revision binds and its scientific identity matches.",
        outcome, observed=observed, expected={"state_identity_hash": recorded_identity},
        n_effective=1, notes=tuple(contradictions),
        limitations=("Identity is recomputed from the retained artifact with the domain identity rule.",),
    ), inputs


def _check_revision_chain_linked(revision: EvidenceState, state: StatisticalState | None) -> IntegrityCheck:
    action = revision.action
    definition = ACTION_REGISTRY.get(action.action_id) if action is not None else None
    state_gene_id = state.entity.gene_id if state is not None else None
    observed = {
        "action_id": action.action_id if action is not None else None,
        "action_version": action.version if action is not None else None,
        "registered_version": definition.version if definition is not None else None,
        "iteration_number": revision.revision_index,
        "has_parent": revision.parent_evidence_hash is not None,
        "gene_id": revision.entity.gene_id, "source_gene_id": state_gene_id,
    }
    contradictions: list[str] = []
    unverifiable: list[str] = []
    if action is None:
        contradictions.append("the revision does not cite a producing action")
    elif definition is None:
        contradictions.append("the revision cites an action the registry does not hold")
    elif action.version != definition.version:
        unverifiable.append(
            "the registry holds a different version of the producing action, so the cited version "
            "cannot be verified"
        )
    if revision.parent_evidence_hash is None:
        contradictions.append("the revision records no parent revision")
    if state_gene_id is not None and revision.entity.gene_id != state_gene_id:
        contradictions.append("the revision entity is not the accepted state's entity")
    if contradictions:
        outcome = CHECK_CONTRADICTED
        notes = tuple(contradictions[:3])
    elif unverifiable or state is None:
        outcome = CHECK_NOT_OBSERVED
        notes = tuple(unverifiable) or ("the revision or the retained source artifact does not permit a chain check",)
    else:
        outcome = CHECK_VERIFIED
        notes = ()
    return _check(
        "REVISION_CHAIN_LINKED",
        "The revision cites a registered producing action at its recorded version, records its parent, and keeps the accepted entity.",
        outcome, observed=observed, expected={"registered producing action": True, "parent present": True},
        n_effective=1, notes=notes,
        limitations=("A producing action version retired from the registry is reported as not observed, not as a contradiction.",),
    )


def _revision_checks(revision: EvidenceState, read_artifact: Callable[[str], bytes | None],
                     ) -> tuple[tuple[IntegrityCheck, ...], list[InputArtifactRef]]:
    content = _read_bytes(read_artifact, revision.source_state.state_artifact_id)
    artifact_hash = hashlib.sha256(content).hexdigest() if content is not None else None
    state: StatisticalState | None = None
    if content is not None:
        try:
            state = read_state(content)
        except Exception:
            state = None
    restated = _check_source_evidence_restated(revision, state)
    provenance = _check_source_provenance_unchanged(revision, state)
    identity, identity_inputs = _check_source_identity_reproducible(revision, state, artifact_hash)
    chain = _check_revision_chain_linked(revision, state)
    return (restated, provenance, identity, chain), identity_inputs


def execute(action_id: str, record: StatisticalState | EvidenceState, *,
            read_artifact: Callable[[str], bytes | None],
            observations: tuple[MeasuredObservation, ...] = ()) -> ActionOutcome:
    """Run one registered deterministic action over its declared immutable input kind."""
    definition = ACTION_REGISTRY.get(action_id)
    if definition is None:
        raise ActionError("UNKNOWN_ACTION", f"{action_id} is not a registered action")
    decision = eligibility(record, definition)
    if not decision.eligible:
        raise ActionError("ACTION_INELIGIBLE", ";".join(decision.reasons))
    checks: tuple[IntegrityCheck, ...]
    if isinstance(record, StatisticalState) and action_id == "SUMMARIZE_EXPRESSION_TAIL_V1":
        expression = next(project.expression for project in record.projects
                          if isinstance(project.expression, ExpressionSummaryResult))
        descriptor = expression_tail_descriptor(expression, ExpressionDiscoverySpec())
        observed = asdict(descriptor)
        observed["availability"] = descriptor.availability.value
        observed["method"] = asdict(descriptor.method)
        checks = (_check(
            "EXPRESSION_TAIL_SUMMARY",
            "The fixed Tukey descriptor is computed from the complete held case-labelled values.",
            CHECK_VERIFIED, observed=observed,
            expected={"minimum_n": 20, "iqr_multiplier": 1.5, "input_unit": "UQFPKM"},
            n_effective=descriptor.valid_n, limitations=definition.limitations,
        ),)
        inputs = [InputArtifactRef("STATISTICAL_STATE_ARTIFACT", record.entity.gene_id,
                                   state_identity(record), True)]
    elif isinstance(record, StatisticalState) and action_id == "SUMMARIZE_CNV_CATEGORIES_V1":
        cnv = next(project.cnv for project in record.projects
                   if isinstance(project.cnv, CnvOccurrenceResult))
        categories, conflicts = cnv_category_summaries(cnv)
        observed = {
            "categories": [
                {"raw_category": item.raw_category, "category": item.category.value,
                 "case_ids": list(item.case_ids), "unique_case_count": len(item.case_ids)}
                for item in categories
            ],
            "conflicting_case_ids": list(conflicts),
            "callers": sorted({occurrence.caller for occurrence in cnv.occurrences
                               if occurrence.caller is not None}),
            "missing_sample_occurrence_ids": sorted(
                occurrence.occurrence_id for occurrence in cnv.occurrences
                if occurrence.sample_id is None),
        }
        checks = (_check(
            "CNV_CATEGORY_SUMMARY",
            "Distinct positive cases are grouped by exact provider category with conflicts retained.",
            CHECK_VERIFIED, observed=observed,
            expected={"absence_means_neutral": False, "overlap_is_summed": False},
            n_effective=len({occurrence.case_id for occurrence in cnv.occurrences}),
            limitations=definition.limitations,
        ),)
        inputs = [InputArtifactRef("STATISTICAL_STATE_ARTIFACT", record.entity.gene_id,
                                   state_identity(record), True)]
    elif isinstance(record, StatisticalState) and action_id == "OCCURRENCE_DETAIL_EVIDENCE_V1":
        if not observations:
            raise ActionError("MEASURED_OBSERVATION_MISSING",
                              "the detail action requires its measured observation")
        observation = observations[0]
        checks = (_check(
            "OCCURRENCE_DETAIL_COMPOSITION",
            "The canonical occurrence-detail composition is measured from the bounded gene detail "
            "pages under the declared composition method.",
            CHECK_VERIFIED if observation.availability == "OBSERVED" else CHECK_NOT_OBSERVED,
            observed=decode(observation.observed),
            expected={"method_id": definition.method_id,
                      "availability": observation.availability,
                      "population_hash": observation.population_hash,
                      "reason": observation.reason},
            limitations=definition.limitations, n_effective=observation.n_effective),)
        inputs = [InputArtifactRef("STATISTICAL_STATE_ARTIFACT", record.entity.gene_id,
                                   state_identity(record), True)]
    elif isinstance(record, StatisticalState):
        frame = _check_frame_agreement(record)
        coverage = _check_expression_coverage(record)
        scope = _check_mutation_scope(record)
        universe, universe_inputs = _check_tested_universe(record, read_artifact)
        integrity, response_inputs = _check_response_integrity(record, read_artifact)
        checks = (frame, coverage, scope, universe, integrity)
        inputs = [InputArtifactRef("STATISTICAL_STATE_ARTIFACT", record.entity.gene_id,
                                   state_identity(record), True)]
        inputs += universe_inputs + response_inputs
    else:
        checks, inputs = _revision_checks(record, read_artifact)
    return ActionOutcome(
        action_id=definition.action_id, status=OUTCOME_COMPLETED, checks=checks,
        inputs=tuple(inputs),
        contradictions=sum(1 for check in checks if check.outcome == CHECK_CONTRADICTED),
        unavailable_reason=None, definition=definition, observations=observations,
    )


__all__ = [
    "ACTION_REGISTRY",
    "ACTION_REGISTRY_VERSION",
    "CHECK_CONTRADICTED",
    "CHECK_NOT_OBSERVED",
    "CHECK_VERIFIED",
    "EVIDENCE_PRODUCING_ACTION_IDS",
    "OUTCOME_COMPLETED",
    "ActionDefinition",
    "ActionEligibility",
    "ActionError",
    "ActionOutcome",
    "eligible_actions",
    "eligibility",
    "execute",
]
