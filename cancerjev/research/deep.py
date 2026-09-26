"""Deep evidence: deterministic revisions for one explicitly selected candidate.

Sequence for one explicitly selected candidate: accept the candidate's immutable
StatisticalState evidence E0, compute the eligible registered deterministic
actions in Python, execute exactly one selected action, and persist the result as
a new immutable EvidenceState revision E1 whose parent is E0.

Python owns selection, budgets, side effects, stopping and abstention. The action
itself is deterministic science and never acquires data or calls a model. A
follow-up never rewrites E0 and never promotes or advances a candidate on its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from cancerjev.domain.actions import IntegrityCheck
from cancerjev.domain.codecs import evidence_identity, write_evidence
from cancerjev.domain.envelopes import EvidenceRecord, StateRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.evidence import (
    ActionRef,
    BaselineObservation,
    CheckOutcome,
    EvidenceCheck,
    EvidenceProvenance,
    EvidenceState,
    InputArtifactRef,
    MeasuredObservation,
    MethodIdentityRef,
    MissingEvidence,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    EntityRef,
    MetricAvailability,
    MetricRecord,
    ObservedCount,
    ObservedScalar,
    UnavailableMeasurement,
)
from cancerjev.domain.scientific import (
    ExpressionSummaryResult,
    StatisticalState,
    UnavailableLane,
)
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import AcquisitionTransport
from cancerjev.research.followup import measure_occurrence_detail, unavailable_observation
from cancerjev.research.nextmove import DEEP_POLICY_VERSION, DeepJudgment, decide_next_move
from cancerjev.research.seams import PublishJson
from cancerjev.science.actions import (
    ACTION_REGISTRY,
    ACTION_REGISTRY_VERSION,
    ActionDefinition,
    ActionEligibility,
    ActionError,
    ActionOutcome,
    eligible_actions,
    execute,
)
from cancerjev.science.methods import METHODS
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.readers import ScientificReadError, read_candidate_state, read_revision_chain
from cancerjev.storage.repositories import Repository

DEEP_ACTION_POLICY_VERSION = "deep-action-policy-v1"
EVIDENCE_PRODUCING_ACTIONS: tuple[str, ...] = ("OCCURRENCE_DETAIL_EVIDENCE_V1",)
CHECK_ACTION_ORDER = ("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1")
SUMMARY_ACTION_ORDER = ("SUMMARIZE_EXPRESSION_TAIL_V1", "SUMMARIZE_CNV_CATEGORIES_V1")


def _policy_select(eligible_ids: tuple[str, ...],
                   executed_ids: frozenset[str]) -> tuple[str | None, str | None, str | None]:
    """Declared priority table; ambiguity abstains and never falls back to registry order."""
    tiers = (
        ("EVIDENCE_PRODUCING", EVIDENCE_PRODUCING_ACTIONS),
        ("CHECK", CHECK_ACTION_ORDER),
        ("SUMMARY", SUMMARY_ACTION_ORDER),
    )
    for tier_name, tier in tiers:
        candidates = [action_id for action_id in eligible_ids
                      if action_id in tier and action_id not in executed_ids]
        if len(candidates) == 1:
            return candidates[0], None, f"POLICY_SELECTED_{tier_name}_ACTION"
        if len(candidates) > 1:
            return None, "POLICY_AMBIGUOUS_TIER", (
                f"{len(candidates)} eligible {tier_name} actions remain: {','.join(candidates)}")
    return None, "POLICY_ABSTAINED_NO_PRIORITY", "no declared policy tier resolves an action"

FOLLOWUP_LIMIT = 3
EVIDENCE_ITERATION_LIMIT = 2
LIVE_RESEARCH_NOTICE = (
    "REAL OPEN-ACCESS GDC EVIDENCE — DETERMINISTIC RESEARCH ONLY, NOT CLINICAL OR DIAGNOSTIC USE"
)

_METRIC_AVAILABILITY = {
    "NOT_OBSERVED": MetricAvailability.NOT_OBSERVED,
    "NOT_ACQUIRED": MetricAvailability.NOT_ACQUIRED,
    "PARTIAL": MetricAvailability.PARTIAL,
    "UNAVAILABLE": MetricAvailability.UNAVAILABLE,
    "INSUFFICIENT": MetricAvailability.INSUFFICIENT,
    "INCOMPATIBLE": MetricAvailability.UNAVAILABLE,
    "INVALID": MetricAvailability.UNAVAILABLE,
    "NOT_APPLICABLE": MetricAvailability.NOT_APPLICABLE,
}


class DeepError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def stable_id(run_id: str, label: str) -> str:
    """Deterministic identifier so a replayed slice is idempotent, not duplicated."""
    return str(uuid5(uuid5(NAMESPACE_URL, run_id), label))


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    entity: EntityRef
    promotion_slot: int
    state_id: str
    record: StateRecord | None
    state_artifact_id: str
    state_artifact_sha256: str


@dataclass(frozen=True)
class DeepPlan:
    candidate: CandidateEvidence
    baseline_evidence_id: str
    baseline_evidence_hash: str
    baseline_already_present: bool
    eligibilities: tuple[ActionEligibility, ...]
    selected_action_id: str | None
    abstain_reason: str | None
    abstain_detail: str | None
    iteration_number: int | None
    execution_id: str | None
    evidence_state_id: str | None


@dataclass(frozen=True)
class FollowUpResult:
    status: str
    action_id: str
    evidence_state_id: str | None
    evidence_hash: str | None
    iteration: int
    checks_total: int
    checks_verified: int
    checks_contradicted: int
    checks_not_observed: int
    error_code: str | None
    revision: EvidenceRecord | None

    def __post_init__(self) -> None:
        if self.revision is not None:
            summary = self.revision.revision.summary
            if (self.evidence_state_id, self.evidence_hash, self.iteration, self.action_id) != (
                self.revision.evidence_state_id, self.revision.evidence_hash,
                self.revision.revision.revision_index,
                self.revision.revision.action.action_id if self.revision.revision.action else None,
            ) or (self.checks_total, self.checks_verified, self.checks_contradicted,
                  self.checks_not_observed) != (summary.total, summary.verified,
                                               summary.contradicted, summary.not_observed):
                raise DeepError("INVALID_REVISION", "revision binding or check summary mismatch")

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status, "action_id": self.action_id,
            "evidence_state_id": self.evidence_state_id, "evidence_hash": self.evidence_hash,
            "iteration": self.iteration, "checks_total": self.checks_total,
            "checks_verified": self.checks_verified, "checks_contradicted": self.checks_contradicted,
            "checks_not_observed": self.checks_not_observed, "error_code": self.error_code,
        }


def _observed_count(measurement: Any) -> int | None:
    return measurement.value if isinstance(measurement, ObservedCount) else None


def _observed_scalar(measurement: Any) -> float | None:
    return measurement.value if isinstance(measurement, ObservedScalar) else None


def _observation_availability(measurement: Any) -> str:
    if isinstance(measurement, (ObservedCount, ObservedScalar)):
        return "OBSERVED"
    if isinstance(measurement, UnavailableMeasurement):
        return measurement.status.value
    return "NOT_OBSERVED"


def _metric_record(measurement: Any, unit: str, default_reason: str | None = None) -> MetricRecord:
    if isinstance(measurement, (ObservedCount, ObservedScalar)):
        return MetricRecord.observed_value(measurement.value, unit)
    status = _observation_availability(measurement)
    reason = measurement.reason if isinstance(measurement, UnavailableMeasurement) else default_reason
    return MetricRecord.unavailable(unit, _METRIC_AVAILABILITY.get(status, MetricAvailability.UNAVAILABLE),
                                    reason)


def _provenance(state: StatisticalState, *, action_method: MethodIdentityRef | None = None,
                input_artifacts: tuple[InputArtifactRef, ...] = ()) -> EvidenceProvenance:
    methods = state.methods + ((action_method,) if action_method is not None else ())
    return EvidenceProvenance(
        gdc_release=state.entity.release,
        sources=state.sources,
        methods=methods,
        environment_hash=state.environment_hash,
        action_registry_version=ACTION_REGISTRY_VERSION,
        selection_artifact_sha256=state.tested_context.examined_genes_hash,
        input_artifacts=input_artifacts,
    )


def _project_level_evidence(state: StatisticalState) -> tuple[ProjectEvidenceRow, ...]:
    rows: list[ProjectEvidenceRow] = []
    for project in state.projects:
        mutation = project.mutation
        expression = project.expression
        if isinstance(expression, ExpressionSummaryResult):
            examined = len(expression.coverage.frame.examined_ids)
            valid = len(expression.coverage.valid_ids)
            cases_with_expression = MetricRecord.observed_value(valid, "cases")
            missing_measurements = MetricRecord.observed_value(examined - valid, "cases")
        else:
            reason = expression.reason if isinstance(expression, UnavailableLane) else None
            availability = _METRIC_AVAILABILITY.get(
                expression.status.value if isinstance(expression, UnavailableLane) else "NOT_OBSERVED",
                MetricAvailability.NOT_OBSERVED,
            )
            cases_with_expression = MetricRecord.unavailable("cases", availability, reason)
            missing_measurements = MetricRecord.unavailable("cases", availability, reason)
        rows.append(ProjectEvidenceRow(
            project_id=project.population.frame.project_id,
            affected_case_count=_metric_record(mutation.affected_cases, "cases"),
            examined_cases=MetricRecord.observed_value(len(mutation.frame.examined_ids), "cases"),
            project_case_with_ssm=_metric_record(mutation.ssm_coverage_cases, "cases"),
            cases_with_expression=cases_with_expression,
            missing_measurements=missing_measurements,
        ))
    return tuple(rows)


def _baseline_observations(state: StatisticalState) -> tuple[BaselineObservation, ...]:
    observations: list[BaselineObservation] = []

    def add(method_id: str, *, availability: str, value: Any, unit: str, n_effective: Any,
            missingness_count: Any, missingness_reason: str | None,
            notes: tuple[str, ...] = ()) -> None:
        definition = METHODS[method_id]
        observations.append(BaselineObservation(
            method_id=definition.method_id, method_version=definition.version,
            observed=canonical_json({"value": value, "unit": unit}),
            availability=availability, n_effective=n_effective,
            missingness_count=missingness_count, missingness_reason=missingness_reason,
            notes=notes, limitations=tuple(definition.limitations),
        ))

    for project in state.projects:
        project_id = project.population.frame.project_id
        mutation = project.mutation
        add("MUTATION_AFFECTED_CASE_COUNT_V1",
            availability=_observation_availability(mutation.affected_cases),
            value=_observed_count(mutation.affected_cases), unit="cases",
            n_effective=len(mutation.frame.examined_ids),
            missingness_count=0, missingness_reason=None, notes=(f"project {project_id}",))
    ssm_values = [
        _observed_count(project.mutation.ssm_coverage_cases)
        for project in state.projects
    ]
    ssm_values = [value for value in ssm_values if value is not None]
    examined_n = len(state.projects[0].population.frame.examined_ids) if state.projects else None
    add("PROJECT_SSM_COVERAGE_V1",
        availability="OBSERVED" if ssm_values else "NOT_OBSERVED",
        value=sum(ssm_values) if ssm_values else None, unit="cases",
        n_effective=examined_n, missingness_count=0, missingness_reason=None)
    for project in state.projects:
        project_id = project.population.frame.project_id
        expression = project.expression
        if isinstance(expression, ExpressionSummaryResult):
            n_missing: Any = len(expression.coverage.frame.examined_ids) - len(expression.coverage.valid_ids)
            add("EXPRESSION_LOG2_SUMMARY_V1",
                availability=_observation_availability(expression.median),
                value=_observed_scalar(expression.median), unit="log2(UQFPKM+1)",
                n_effective=len(expression.values), missingness_count=n_missing,
                missingness_reason="EXAMINED_CASES_WITHOUT_RETURNED_VALUE" if n_missing else None,
                notes=(f"project {project_id}",))
        else:
            add("EXPRESSION_LOG2_SUMMARY_V1",
                availability=_observation_availability(expression),
                value=None, unit="log2(UQFPKM+1)",
                n_effective=None, missingness_count=None, missingness_reason=None,
                notes=(f"project {project_id}",))
    return tuple(observations)


def _baseline_evidence(record: StateRecord, candidate: CandidateEvidence, *, run_id: str,
                       eligible_ids: list[str]) -> EvidenceState:
    state = record.state
    population = state.projects[0].population if state.projects else None
    return EvidenceState(
        entity=state.entity,
        accepted_state_hash=record.state_hash,
        source_state=SourceStateBinding(candidate.state_id, record.state_hash,
                                        candidate.state_artifact_id, candidate.state_artifact_sha256),
        parent_evidence_hash=None,
        revision_index=0,
        action=None,
        puzzle=ResearchPuzzle(
            origin="STATISTICAL_STATE_BASELINE",
            question=(
                f"What does the recorded evidence for {state.entity.symbol} support, and what "
                "follow-up computation is eligible on it?"
            ),
            interpretation=(
                "The baseline revision is the accepted current evidence of the candidate, not a Jev judgment "
                "and not a new measurement."
            ),
            proposed_action_ids=tuple(eligible_ids),
        ),
        checks=(),
        baseline_observations=_baseline_observations(state),
        project_evidence=_project_level_evidence(state),
        missing_evidence=(
            MissingEvidence(
                needed_evidence="population_exclusions",
                availability=(MetricAvailability.OBSERVED if population is not None and population.excluded_counts
                              else MetricAvailability.NOT_OBSERVED),
                reason=(None if population is not None and population.excluded_counts
                        else "the recorded population does not list excluded cases"),
            ),
        ),
        quality=state.quality,
        warnings=state.missingness,
        provenance=_provenance(state),
    )


def _observation(result: IntegrityCheck, definition: ActionDefinition,
                 accepted_state_hash: str) -> EvidenceCheck:
    outcome = CheckOutcome(result.outcome)
    if outcome == CheckOutcome.VERIFIED:
        reason = None
        missing_count = 0
        missing_reason = None
    elif outcome == CheckOutcome.NOT_OBSERVED:
        reason = "RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION"
        missing_count = 1
        missing_reason = "RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION"
    else:
        reason = "RECORDED_EVIDENCE_CONTRADICTS_THE_CLAIM"
        missing_count = 0
        missing_reason = None
    return EvidenceCheck(
        check_id=result.check_id, method_id=definition.method_id,
        method_version=definition.method_version, outcome=outcome, claim=result.claim,
        input_hashes=(accepted_state_hash,), reason=reason, n_effective=result.n_effective,
        observed=result.observed_json, expected=result.expected_json, notes=result.notes,
        limitations=result.limitations or tuple(definition.limitations),
        missing_count=missing_count, missing_reason=missing_reason,
    )


def _followup_evidence(outcome: ActionOutcome, candidate: CandidateEvidence, record: StateRecord, *,
                       run_id: str, iteration: int, previous_evidence_id: str,
                       previous_evidence_hash: str) -> EvidenceState:
    definition = outcome.definition
    state = record.state
    missing_evidence = [
        MissingEvidence(
            needed_evidence=check.check_id,
            availability=MetricAvailability.NOT_OBSERVED,
            reason="recorded evidence does not permit verification",
        )
        for check in outcome.checks if check.outcome == "NOT_OBSERVED"
    ]
    if outcome.observations:
        missing_evidence.append(MissingEvidence(
            needed_evidence="downstream_inference",
            availability=MetricAvailability.NOT_OBSERVED,
            reason=("descriptive measurement only; no declared inferential population/null/FDR "
                    "contract exists"),
        ))
    else:
        missing_evidence.append(MissingEvidence(
            needed_evidence="new_gdc_measurement",
            availability=MetricAvailability.NOT_ACQUIRED,
            reason="this deterministic action acquires no new GDC evidence",
        ))
    return EvidenceState(
        entity=state.entity,
        accepted_state_hash=record.state_hash,
        source_state=SourceStateBinding(candidate.state_id, record.state_hash,
                                        candidate.state_artifact_id, candidate.state_artifact_sha256),
        parent_evidence_hash=previous_evidence_hash,
        revision_index=iteration,
        action=ActionRef(definition.action_id, definition.version),
        puzzle=ResearchPuzzle(
            origin="DETERMINISTIC_ACTION_REGISTRY",
            question=definition.question,
            interpretation=definition.interpretation,
            proposed_action_ids=(definition.action_id,),
        ),
        checks=tuple(_observation(check, definition, record.state_hash) for check in outcome.checks),
        baseline_observations=(),
        project_evidence=_project_level_evidence(state),
        missing_evidence=tuple(missing_evidence),
        quality=state.quality,
        warnings=tuple(
            f"CONTRADICTED check {check.check_id}" for check in outcome.checks
            if check.outcome == "CONTRADICTED"
        ),
        provenance=_provenance(
            state,
            action_method=MethodIdentityRef(definition.method_id, definition.method_version,
                                            definition.ref()["parameters_hash"]),
            input_artifacts=outcome.inputs,
        ),
        measured_observations=outcome.observations,
    )


def load_candidate_evidence(repository: Repository, artifacts: ArtifactStore,
                            candidate: dict[str, Any]) -> CandidateEvidence:
    """Accept the candidate's immutable StatisticalState evidence, or fail closed."""
    try:
        stored = read_candidate_state(repository, artifacts, candidate["candidate_id"])
        if repository.evidence_revisions(candidate["candidate_id"]):
            read_revision_chain(repository, artifacts, candidate["candidate_id"])
    except ScientificReadError as exc:
        raise DeepError(exc.code, exc.detail) from exc
    return CandidateEvidence(
        candidate_id=candidate["candidate_id"], entity=stored.state.entity,
        promotion_slot=candidate["promotion_slot"], state_id=stored.state_id, record=stored.record,
        state_artifact_id=stored.artifact.artifact_id, state_artifact_sha256=stored.artifact.sha256,
    )


def _resolve_requested_action(eligibilities: tuple[ActionEligibility, ...],
                              requested_action_id: str | None) -> tuple[str | None, str | None, str | None]:
    eligible_ids = [item.action_id for item in eligibilities if item.eligible]
    if not eligible_ids:
        reasons = ";".join(
            f"{item.action_id}:{','.join(item.reasons)}" for item in eligibilities if item.reasons
        )
        return None, "NO_ELIGIBLE_ACTION", reasons or "no registered action is eligible"
    if requested_action_id is None:
        if len(eligible_ids) == 1:
            return eligible_ids[0], None, None
        return None, "EXPLICIT_ACTION_REQUIRED", "an explicit action is required when several are eligible"
    if requested_action_id not in eligible_ids:
        return None, "SELECTED_ACTION_NOT_ELIGIBLE", f"{requested_action_id} is not eligible for this evidence"
    return requested_action_id, None, None


def plan_deep_slice(*, run_id: str, candidate: dict[str, Any], repository: Repository,
                    artifacts: ArtifactStore, emit: Callable[..., Any], publish_json: PublishJson,
                    requested_action_id: str | None = None) -> DeepPlan:
    """Accept E0, create the baseline revision, and compute eligible actions."""
    try:
        evidence = load_candidate_evidence(repository, artifacts, candidate)
    except DeepError as exc:
        baseline_id = stable_id(run_id, f"evidence:{candidate['candidate_id']}:0")
        emit(
            run_id, "FOLLOWUP_ABSTAINED", f"deep:{candidate['candidate_id']}:acceptance-failed",
            f"Deep evidence acceptance failed for candidate {candidate['candidate_id']}: {exc.code}.",
            stage="DEEP_ANALYSIS", level="error", candidate_id=candidate["candidate_id"],
            data={"candidate_id": candidate["candidate_id"], "reason_code": "EVIDENCE_ACCEPTANCE_FAILED",
                  "error_code": exc.code, "detail": exc.detail},
        )
        return DeepPlan(candidate=CandidateEvidence(
            candidate_id=candidate["candidate_id"], entity=EntityRef(
                candidate["entity"]["gene_id"], candidate["entity"].get("gene_symbol"), ""),
            promotion_slot=candidate["promotion_slot"], state_id=candidate["source_state_id"],
            record=None, state_artifact_id="", state_artifact_sha256=""),
            baseline_evidence_id=baseline_id, baseline_evidence_hash="",
            baseline_already_present=False, eligibilities=(), selected_action_id=None,
            abstain_reason="EVIDENCE_ACCEPTANCE_FAILED", abstain_detail=exc.detail,
            iteration_number=None, execution_id=None, evidence_state_id=None)

    if evidence.record is None:
        raise DeepError("EVIDENCE_ACCEPTANCE_FAILED", "accepted state missing")
    state = evidence.record.state
    eligibilities = eligible_actions(state, "STATISTICAL_STATE")
    eligible_ids = [item.action_id for item in eligibilities if item.eligible]

    baseline_id = stable_id(run_id, f"evidence:{candidate['candidate_id']}:0")
    existing_revisions = repository.evidence_revisions(candidate["candidate_id"])
    baseline_present = any(row["evidence_state_id"] == baseline_id for row in existing_revisions)
    baseline_evidence = _baseline_evidence(evidence.record, evidence, run_id=run_id,
                                           eligible_ids=eligible_ids)
    baseline_hash = evidence_identity(baseline_evidence)
    if not baseline_present:
        artifact = publish_json(run_id, f"runs/{run_id}/evidence/{baseline_id}.json",
                                write_evidence(baseline_evidence), "evidence-state")
        emit(
            run_id, "EVIDENCE_STATE_CREATED", f"evidence:{baseline_id}:created",
            f"Accepted baseline evidence E0 for {state.entity.symbol} (iteration 0).",
            stage="DEEP_ANALYSIS", candidate_id=candidate["candidate_id"], iteration=0,
            data={"evidence_state_id": baseline_id, "evidence_hash": baseline_hash,
                  "iteration": 0, "previous_evidence_state_id": None,
                  "candidate_id": candidate["candidate_id"],
                  "state_id": evidence.state_id, "origin": "STATISTICAL_STATE_BASELINE"},
            artifact_refs=[artifact.ref()],
            registrations=[
                repository.artifact_registration(artifact, run_id),
                repository.evidence_state_registration(
                    evidence_state_id=baseline_id, run_id=run_id, candidate_id=candidate["candidate_id"],
                    previous_evidence_state_id=None, iteration=0, evidence_hash=baseline_hash,
                    artifact_id=artifact.artifact_id,
                    summary_json=canonical_json({
                        "entity": {"gene_id": evidence.entity.gene_id,
                                   "gene_symbol": evidence.entity.symbol},
                        "iteration": 0, "origin": "STATISTICAL_STATE_BASELINE",
                        "state_id": evidence.state_id,
                    }).decode(),
                    created_at=utc_now(),
                ),
                repository.candidate_status_registration(
                    candidate_id=candidate["candidate_id"], status="DEEP_ANALYZED",
                    current_stage="DEEP_ANALYSIS", updated_at=utc_now(),
                    latest_evidence_state_id=baseline_id,
                ),
            ],
        )

    emit(
        run_id, "ELIGIBLE_ACTIONS_COMPUTED", f"deep:{candidate['candidate_id']}:eligibility",
        f"Python computed {len(eligible_ids)} eligible registered action(s) for candidate "
        f"{candidate['candidate_id']}.",
        stage="DEEP_ANALYSIS", candidate_id=candidate["candidate_id"], iteration=0,
        data={"candidate_id": candidate["candidate_id"], "input_evidence_state_id": baseline_id,
              "input_evidence_hash": evidence.record.state_hash, "eligible_action_ids": eligible_ids,
              "ineligible": [
                  {"action_id": item.action_id, "reasons": list(item.reasons)}
                  for item in eligibilities if not item.eligible
              ],
              "selection_policy": ("EXPLICIT_ACTION" if requested_action_id
                                   else DEEP_ACTION_POLICY_VERSION),
              "registry_version": ACTION_REGISTRY_VERSION},
    )

    eligible_ids_tuple = tuple(item.action_id for item in eligibilities if item.eligible)
    input_evidence_hash = evidence.record.state_hash
    completed = [row for row in repository.followup_executions_for(candidate["candidate_id"])
                 if row["status"] == "COMPLETED"]
    action_id: str | None
    abstain_reason: str | None
    abstain_detail: str | None
    if requested_action_id is None:
        if not eligible_ids_tuple:
            reasons_text = ";".join(
                f"{item.action_id}:{','.join(item.reasons)}"
                for item in eligibilities if item.reasons)
            action_id, abstain_reason, abstain_detail = (
                None, "NO_ELIGIBLE_ACTION", reasons_text or "no registered action is eligible")
        else:
            executed_for_input = frozenset(
                row["action_id"] for row in completed
                if row["input_evidence_hash"] == input_evidence_hash)
            action_id, abstain_reason, abstain_detail = _policy_select(
                eligible_ids_tuple, executed_for_input)
    else:
        action_id, abstain_reason, abstain_detail = _resolve_requested_action(
            eligibilities, requested_action_id)
    if action_id is None:
        emit(
            run_id, "FOLLOWUP_ABSTAINED", f"deep:{candidate['candidate_id']}:abstained:{abstain_reason}",
            f"No follow-up executed for candidate {candidate['candidate_id']}: {abstain_reason}.",
            stage="FOLLOWUP", level="warning", candidate_id=candidate["candidate_id"],
            data={"candidate_id": candidate["candidate_id"], "reason_code": abstain_reason,
                  "detail": abstain_detail, "input_evidence_state_id": baseline_id},
        )
        return DeepPlan(candidate=evidence, baseline_evidence_id=baseline_id,
                        baseline_evidence_hash=baseline_hash, baseline_already_present=baseline_present,
                        eligibilities=eligibilities, selected_action_id=None,
                        abstain_reason=abstain_reason, abstain_detail=abstain_detail,
                        iteration_number=None, execution_id=None, evidence_state_id=None)

    completed = [row for row in repository.followup_executions_for(candidate["candidate_id"])
                 if row["status"] == "COMPLETED"]
    input_evidence_hash = evidence.record.state_hash
    if any(row["action_id"] == action_id and row["input_evidence_hash"] == input_evidence_hash
           for row in completed):
        emit(
            run_id, "FOLLOWUP_SKIPPED", f"deep:{candidate['candidate_id']}:skipped:{action_id}",
            f"{action_id} was already executed for this exact evidence; no new revision created.",
            stage="FOLLOWUP", candidate_id=candidate["candidate_id"],
            data={"candidate_id": candidate["candidate_id"], "action_id": action_id,
                  "reason_code": "ALREADY_EXECUTED_FOR_THIS_EVIDENCE",
                  "input_evidence_hash": input_evidence_hash},
        )
        return DeepPlan(candidate=evidence, baseline_evidence_id=baseline_id,
                        baseline_evidence_hash=baseline_hash, baseline_already_present=baseline_present,
                        eligibilities=eligibilities, selected_action_id=None,
                        abstain_reason="ALREADY_EXECUTED_FOR_THIS_EVIDENCE",
                        abstain_detail=f"{action_id} already ran on this evidence",
                        iteration_number=None, execution_id=None, evidence_state_id=None)
    if len(completed) >= FOLLOWUP_LIMIT:
        return _abstain(run_id, emit, evidence, baseline_id, action_id, baseline_hash, baseline_present,
                        eligibilities, "FOLLOWUP_LIMIT_REACHED", f"limit {FOLLOWUP_LIMIT} reached")
    iteration = len(existing_revisions) + 1
    if iteration > EVIDENCE_ITERATION_LIMIT:
        return _abstain(run_id, emit, evidence, baseline_id, action_id, baseline_hash, baseline_present,
                        eligibilities, "EVIDENCE_ITERATION_LIMIT_REACHED",
                        f"limit {EVIDENCE_ITERATION_LIMIT} revisions reached")
    return DeepPlan(candidate=evidence, baseline_evidence_id=baseline_id,
                    baseline_evidence_hash=baseline_hash, baseline_already_present=baseline_present,
                    eligibilities=eligibilities, selected_action_id=action_id, abstain_reason=None,
                    abstain_detail=None, iteration_number=iteration,
                    execution_id=stable_id(run_id, f"followup:{candidate['candidate_id']}:{action_id}:{iteration}"),
                    evidence_state_id=stable_id(run_id, f"evidence:{candidate['candidate_id']}:{iteration}"))


def _abstain(run_id: str, emit: Callable[..., Any], evidence: CandidateEvidence, baseline_id: str,
             action_id: str, baseline_hash: str, baseline_present: bool,
             eligibilities: tuple[ActionEligibility, ...], reason: str, detail: str) -> DeepPlan:
    emit(
        run_id, "FOLLOWUP_ABSTAINED", f"deep:{evidence.candidate_id}:abstained:{reason}",
        f"No follow-up executed for candidate {evidence.candidate_id}: {reason}.",
        stage="FOLLOWUP", level="warning", candidate_id=evidence.candidate_id,
        data={"candidate_id": evidence.candidate_id, "action_id": action_id,
              "reason_code": reason, "detail": detail, "input_evidence_state_id": baseline_id},
    )
    return DeepPlan(candidate=evidence, baseline_evidence_id=baseline_id,
                    baseline_evidence_hash=baseline_hash, baseline_already_present=baseline_present,
                    eligibilities=eligibilities, selected_action_id=None, abstain_reason=reason,
                    abstain_detail=detail, iteration_number=None, execution_id=None,
                    evidence_state_id=None)


def _execute_action(*, run_id: str, candidate: CandidateEvidence, record: StateRecord | EvidenceRecord,
                    input_kind: str, action_id: str, previous_evidence_id: str,
                    previous_evidence_hash: str, iteration: int, execution_id: str,
                    evidence_state_id: str, repository: Repository, emit: Callable[..., Any],
                    publish_json: PublishJson,
                    read_artifact: Callable[[str], bytes | None],
                    transport: AcquisitionTransport | None = None) -> FollowUpResult:
    """Run one registered deterministic action and persist an immutable revision.

    The action's declared input kind decides what it reads: an accepted
    StatisticalState, or an existing immutable evidence revision. Every revision
    copies its project-level evidence from the accepted state, links its parent and
    cites the producing action.
    """
    definition = ACTION_REGISTRY[action_id]
    if input_kind == "STATISTICAL_STATE":
        if not isinstance(record, StateRecord):
            raise DeepError("INVALID_ACTION_INPUT", "state input required")
        input_evidence_hash = record.state_hash
        input_evidence_state_id = previous_evidence_id
        action_input: StatisticalState | EvidenceState = record.state
    else:
        if not isinstance(record, EvidenceRecord):
            raise DeepError("INVALID_ACTION_INPUT", "revision input required")
        input_evidence_hash = record.evidence_hash
        input_evidence_state_id = record.evidence_state_id
        action_input = record.revision
    emit(
        run_id, "FOLLOWUP_STARTED", f"deep:{execution_id}:started",
        f"Deterministic follow-up {action_id} started for candidate {candidate.candidate_id}.",
        stage="FOLLOWUP", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"execution_id": execution_id, "candidate_id": candidate.candidate_id,
              "action_id": action_id, "action_version": definition.version,
              "input_ref_kind": input_kind, "input_evidence_state_id": input_evidence_state_id,
              "input_evidence_hash": input_evidence_hash},
    )
    observations: tuple[MeasuredObservation, ...]
    if action_id == "OCCURRENCE_DETAIL_EVIDENCE_V1":
        if not isinstance(record, StateRecord):
            observations = (unavailable_observation(
                gene_id=candidate.entity.gene_id, population_hash=(
                    record.evidence_hash if isinstance(record, EvidenceRecord)
                    else candidate.state_artifact_sha256),
                reason="DETAIL_REQUIRES_ACCEPTED_STATISTICAL_STATE"),)
        elif transport is None:
            observations = (unavailable_observation(
                gene_id=record.state.entity.gene_id,
                population_hash=record.state.projects[0].population.frame.membership_hash,
                reason="DETAIL_TRANSPORT_UNAVAILABLE"),)
        else:
            observations = (measure_occurrence_detail(
                transport, project_id=record.state.research.project_id,
                gene_id=record.state.entity.gene_id, release=record.state.entity.release,
                population_hash=record.state.projects[0].population.frame.membership_hash),)
    else:
        observations = ()
    try:
        outcome = execute(action_id, action_input, read_artifact=read_artifact,
                          observations=observations)
    except ActionError as exc:
        emit(
            run_id, "FOLLOWUP_FAILED", f"deep:{execution_id}:failed",
            f"Deterministic follow-up {action_id} failed: {exc.code}.",
            stage="FOLLOWUP", level="error", candidate_id=candidate.candidate_id,
            iteration=iteration,
            data={"execution_id": execution_id, "candidate_id": candidate.candidate_id,
                  "action_id": action_id, "error_code": exc.code, "detail": exc.detail,
                  "input_evidence_hash": input_evidence_hash},
            registrations=[repository.followup_execution_registration(
                execution_id=execution_id, run_id=run_id, candidate_id=candidate.candidate_id,
                action_id=action_id, action_version=definition.version,
                input_evidence_hash=input_evidence_hash, output_evidence_state_id=None,
                slot=iteration, status="FAILED",
                summary_json=canonical_json({"error_code": exc.code, "detail": exc.detail}).decode(),
                created_at=utc_now(),
            )],
        )
        return FollowUpResult(
            status="FAILED", action_id=action_id, evidence_state_id=None, evidence_hash=None,
            iteration=iteration, checks_total=0, checks_verified=0, checks_contradicted=0,
            checks_not_observed=0, error_code=exc.code, revision=None,
        )

    if candidate.record is None:
        raise DeepError("EVIDENCE_ACCEPTANCE_FAILED", "accepted source missing")
    revision = _followup_evidence(outcome, candidate, candidate.record, run_id=run_id, iteration=iteration,
                                  previous_evidence_id=previous_evidence_id,
                                  previous_evidence_hash=previous_evidence_hash)
    evidence_hash = evidence_identity(revision)
    outcome_label = "COMPLETED_WITH_CONTRADICTIONS" if outcome.contradictions else "COMPLETED"
    artifact = publish_json(run_id, f"runs/{run_id}/evidence/{evidence_state_id}.json",
                            write_evidence(revision), "evidence-state")
    emit(
        run_id, "EVIDENCE_STATE_CREATED", f"evidence:{evidence_state_id}:created",
        f"Immutable evidence revision E{iteration} recorded for candidate {candidate.candidate_id}.",
        stage="EVIDENCE_BUILD", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"evidence_state_id": evidence_state_id, "evidence_hash": evidence_hash,
              "iteration": iteration, "previous_evidence_state_id": previous_evidence_id,
              "candidate_id": candidate.candidate_id, "state_id": candidate.state_id,
              "action_id": action_id, "outcome": outcome_label,
              "checks_verified": outcome.verified, "checks_contradicted": outcome.contradictions,
              "checks_not_observed": outcome.not_observed},
        artifact_refs=[artifact.ref()],
        registrations=[
            repository.artifact_registration(artifact, run_id),
            repository.evidence_state_registration(
                evidence_state_id=evidence_state_id, run_id=run_id,
                candidate_id=candidate.candidate_id,
                previous_evidence_state_id=previous_evidence_id,
                iteration=iteration, evidence_hash=evidence_hash,
                artifact_id=artifact.artifact_id,
                summary_json=canonical_json({
                    "entity": {"gene_id": candidate.entity.gene_id,
                               "gene_symbol": candidate.entity.symbol},
                    "iteration": iteration, "action_id": action_id,
                    "outcome": outcome_label, "checks_verified": outcome.verified,
                    "checks_contradicted": outcome.contradictions,
                    "checks_not_observed": outcome.not_observed,
                }).decode(),
                created_at=utc_now(),
            ),
            repository.candidate_status_registration(
                candidate_id=candidate.candidate_id, status="DEEP_ANALYZED",
                current_stage="EVIDENCE_BUILD", updated_at=utc_now(),
                latest_evidence_state_id=evidence_state_id,
            ),
        ],
    )
    emit(
        run_id, "FOLLOWUP_COMPLETED", f"deep:{execution_id}:completed",
        f"Deterministic follow-up {action_id} completed with {outcome.contradictions} contradicted check(s).",
        stage="FOLLOWUP", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"execution_id": execution_id, "candidate_id": candidate.candidate_id,
              "action_id": action_id, "action_version": definition.version,
              "input_evidence_hash": input_evidence_hash,
              "output_evidence_state_id": evidence_state_id, "outcome": outcome_label,
              "checks_total": len(outcome.checks), "checks_verified": outcome.verified,
              "checks_contradicted": outcome.contradictions,
              "checks_not_observed": outcome.not_observed},
        registrations=[repository.followup_execution_registration(
            execution_id=execution_id, run_id=run_id, candidate_id=candidate.candidate_id,
            action_id=action_id, action_version=definition.version,
            input_evidence_hash=input_evidence_hash,
            output_evidence_state_id=evidence_state_id,
            slot=iteration, status="COMPLETED",
            summary_json=canonical_json({
                "outcome": outcome_label, "checks_total": len(outcome.checks),
                "checks_verified": outcome.verified, "checks_contradicted": outcome.contradictions,
                "checks_not_observed": outcome.not_observed,
            }).decode(),
            created_at=utc_now(),
        )],
    )
    return FollowUpResult(
        status=outcome_label, action_id=action_id, evidence_state_id=evidence_state_id,
        evidence_hash=evidence_hash, iteration=iteration, checks_total=len(outcome.checks),
        checks_verified=outcome.verified, checks_contradicted=outcome.contradictions,
        checks_not_observed=outcome.not_observed, error_code=None,
        revision=EvidenceRecord(evidence_state_id, evidence_hash, revision),
    )


def execute_followup(*, run_id: str, plan: DeepPlan, repository: Repository, emit: Callable[..., Any],
                     publish_json: PublishJson,
                           read_artifact: Callable[[str], bytes | None],
                           transport: AcquisitionTransport | None = None) -> FollowUpResult:
    """Run the selected deterministic action over the candidate's accepted evidence."""
    if plan.selected_action_id is None or plan.iteration_number is None or plan.execution_id is None \
            or plan.evidence_state_id is None:
        raise DeepError("FOLLOWUP_NOT_PLANNED", "execute_followup requires a selected action plan")
    if plan.candidate.record is None:
        raise DeepError("EVIDENCE_ACCEPTANCE_FAILED", "accepted source missing")
    return _execute_action(
        run_id=run_id, candidate=plan.candidate, record=plan.candidate.record,
        input_kind="STATISTICAL_STATE", action_id=plan.selected_action_id,
        previous_evidence_id=plan.baseline_evidence_id,
        previous_evidence_hash=plan.baseline_evidence_hash,
        iteration=plan.iteration_number,
        execution_id=plan.execution_id, evidence_state_id=plan.evidence_state_id,
        repository=repository, emit=emit, publish_json=publish_json, read_artifact=read_artifact,
        transport=transport,
    )


@dataclass(frozen=True)
class DispatchResult:
    dispatched: bool
    reason_code: str
    action_id: str | None
    result: FollowUpResult | None

    def summary(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched, "reason_code": self.reason_code, "action_id": self.action_id,
            "evidence_state_id": self.result.evidence_state_id if self.result else None,
            "result_status": self.result.status if self.result else None,
            "iteration": self.result.iteration if self.result else None,
        }


def dispatch_recorded_move(*, run_id: str, candidate: CandidateEvidence, result: FollowUpResult,
                           decision: dict[str, Any], repository: Repository, emit: Callable[..., Any],
                           publish_json: PublishJson,
                           read_artifact: Callable[[str], bytes | None], authorized: bool,
                           authorized_by: str = "OPERATOR_AUTHORIZATION") -> DispatchResult:
    """Dispatch one recorded FOLLOW_UP, only under an explicit authorization.

    The authorization is declared by the caller and recorded in every dispatch
    decision (`OPERATOR_AUTHORIZATION` for a researcher selection,
    `AUTONOMOUS_DISPATCH_AUTHORIZATION` for the autonomous candidate queue that
    Python policy drives). Ambiguity is never resolved by ordering. At most one
    dispatch happens per step, it obeys the existing follow-up and revision caps
    (every attempt consumes follow-up budget, not only successful ones), and the
    caller judges the new revision exactly once afterwards. Judging here would
    double every Jev call and duplicate the recorded decision, so this function
    decides and executes only. Every refusal reason is recorded rather than
    silently dropped.
    """

    def refuse(reason_code: str, detail: str) -> DispatchResult:
        emit(
            run_id, "NEXT_MOVE_DISPATCHED", f"dispatch:{result.evidence_state_id}:{reason_code}",
            f"Recorded next move was not dispatched: {reason_code}.",
            stage="FOLLOWUP", level="warning" if reason_code != "MOVE_NOT_FOLLOW_UP" else "info",
            candidate_id=candidate.candidate_id, iteration=result.iteration,
            data={"evidence_state_id": result.evidence_state_id, "move": decision.get("move"),
                  "reason_code": reason_code, "detail": detail, "dispatched": False,
                  "decision_reason_code": decision.get("reason_code"),
                  "authorized": authorized, "authorized_by": authorized_by},
        )
        return DispatchResult(dispatched=False, reason_code=reason_code, action_id=None, result=None)

    if decision.get("move") != "FOLLOW_UP":
        return refuse("MOVE_NOT_FOLLOW_UP",
                      f"the recorded move is {decision.get('move')}, so nothing is dispatched")
    if not authorized:
        return refuse("DISPATCH_NOT_AUTHORIZED",
                      "dispatching a recorded move requires an explicit declared authorization")
    if result.revision is None or result.evidence_state_id is None or result.iteration is None:
        return refuse("INPUT_REVISION_MISSING", "no immutable revision is available to continue from")
    # No hidden lexicographic selection: 0 eligible -> refusal, 1 -> dispatch it,
    # more than one -> fail closed. A deterministic optimizer or ranking agent must
    # never choose a scientific follow-up.
    distinct = decision.get("dimensions", {}).get("distinct_eligible_action_ids") or []
    action_ids = sorted(set(distinct))
    if not action_ids:
        return refuse("NO_DISTINCT_ELIGIBLE_ACTION",
                      "no registered action other than the producing one is eligible for this revision")
    if len(action_ids) > 1:
        return refuse("EXPLICIT_ACTION_REQUIRED",
                      f"{len(action_ids)} distinct registered actions are eligible; an explicit "
                      "selection is required, ordering does not choose one")
    action_id = action_ids[0]
    attempts = repository.followup_executions_for(candidate.candidate_id)
    if len(attempts) >= FOLLOWUP_LIMIT:
        return refuse("FOLLOWUP_LIMIT_REACHED",
                      f"{len(attempts)} follow-up attempt(s) reached the limit {FOLLOWUP_LIMIT}; "
                      "a failed attempt consumes budget too")
    iteration = result.iteration + 1
    if iteration > EVIDENCE_ITERATION_LIMIT:
        return refuse("EVIDENCE_ITERATION_LIMIT_REACHED",
                      f"iteration {iteration} exceeds the revision limit {EVIDENCE_ITERATION_LIMIT}")
    execution_id = stable_id(run_id, f"followup:{candidate.candidate_id}:{action_id}:{iteration}")
    evidence_state_id = stable_id(run_id, f"evidence:{candidate.candidate_id}:{iteration}")
    followup = _execute_action(
        run_id=run_id, candidate=candidate, record=result.revision, input_kind="EVIDENCE_STATE",
        action_id=action_id, previous_evidence_id=result.evidence_state_id,
        # FollowUpResult.__post_init__ binds evidence_hash to the present revision's hash.
        previous_evidence_hash=result.revision.evidence_hash, iteration=iteration,
        execution_id=execution_id, evidence_state_id=evidence_state_id, repository=repository,
        emit=emit, publish_json=publish_json, read_artifact=read_artifact,
    )
    if followup.status == "FAILED":
        emit(
            run_id, "NEXT_MOVE_DISPATCHED", f"dispatch:{result.evidence_state_id}:action-failed",
            f"Recorded next move dispatch failed: {followup.error_code}.",
            stage="FOLLOWUP", level="error", candidate_id=candidate.candidate_id, iteration=iteration,
            data={"evidence_state_id": result.evidence_state_id, "move": decision.get("move"),
                  "reason_code": "DISPATCH_ACTION_FAILED", "detail": followup.error_code,
                  "action_id": action_id, "dispatched": False, "authorized": True,
                  "authorized_by": authorized_by},
        )
        return DispatchResult(dispatched=False, reason_code="DISPATCH_ACTION_FAILED", action_id=action_id,
                              result=followup)
    emit(
        run_id, "NEXT_MOVE_DISPATCHED", f"dispatch:{result.evidence_state_id}:{action_id}",
        f"Recorded FOLLOW_UP dispatched as {action_id} under {authorized_by}.",
        stage="FOLLOWUP", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"evidence_state_id": result.evidence_state_id, "move": decision.get("move"),
              "reason_code": "DISPATCHED", "action_id": action_id, "execution_id": execution_id,
              "output_evidence_state_id": evidence_state_id, "output_iteration": iteration,
              "dispatched": True, "authorized": True, "authorized_by": authorized_by,
              "decision_reason_code": decision.get("reason_code"),
              "note": "the new revision is judged once by the caller"},
    )
    return DispatchResult(dispatched=True, reason_code="DISPATCHED", action_id=action_id, result=followup)


def judge_evidence_revision(*, run_id: str, candidate: CandidateEvidence, result: FollowUpResult,
                            jev_service: JevService, emit: Callable[..., Any]) -> dict[str, Any]:
    """One Deep Jev fan-out over the new revision, then the Python next-move policy.

    The eligible set is computed from the revision's own declared input kind, so the
    judgment and the policy see exactly the actions that could run on this revision.
    The judgment is an input to the policy: Jev does not select, authorize or execute
    the move, and no measured field is written from it.
    """
    if result.revision is None or result.evidence_state_id is None or result.evidence_hash is None:
        return {"deep_evaluation_id": None, "deep_error_code": "NO_REVISION_TO_JUDGE",
                "next_move": None}
    revision_eligibilities = eligible_actions(result.revision.revision, "EVIDENCE_STATE")
    eligible_action_ids = [item.action_id for item in revision_eligibilities if item.eligible]
    eligible_action_payloads = [ACTION_REGISTRY[action_id].payload() for action_id in eligible_action_ids]
    emit(
        run_id, "JEV_DEEP_STARTED", f"jev-deep:{result.evidence_state_id}:started",
        f"Deep Jev evidence judgment started for revision {result.iteration}.",
        stage="JEV_DEEP", candidate_id=candidate.candidate_id, iteration=result.iteration,
        data={"evidence_state_id": result.evidence_state_id, "evidence_hash": result.evidence_hash,
              "iteration": result.iteration, "action_id": result.action_id,
              "eligible_action_ids": eligible_action_ids,
              "ineligible": [
                  {"action_id": item.action_id, "reasons": list(item.reasons)}
                  for item in revision_eligibilities if not item.eligible
              ],
              "action_registry_version": ACTION_REGISTRY_VERSION,
              "question_set_version": "deep-v1"},
    )
    evaluation_record = jev_service.evaluate_evidence_record(
        run_id=run_id, evidence=result.revision, eligible_actions=eligible_action_payloads, emit=emit,
        candidate_id=candidate.candidate_id,
    )
    evaluation = evaluation_record.boundary_representation()
    decision = decide_next_move(
        checks=result.revision.revision.summary,
        judgment=DeepJudgment.from_evaluation(evaluation_record, result.action_id),
        eligible_action_ids=eligible_action_ids,
    )
    emit(
        run_id, "NEXT_MOVE_SELECTED", f"next-move:{result.evidence_state_id}:{decision['move']}",
        f"Python next-move policy recorded {decision['move']} for revision {result.iteration}: "
        f"{decision['reason_code']}.",
        stage="JEV_DEEP", candidate_id=candidate.candidate_id, iteration=result.iteration,
        data={"evidence_state_id": result.evidence_state_id, "evidence_hash": result.evidence_hash,
              "evaluation_id": evaluation["evaluation_id"], "policy_version": DEEP_POLICY_VERSION,
              "move": decision["move"], "reason_code": decision["reason_code"],
              "detail": decision["detail"], "dimensions": decision["dimensions"],
              "thresholds": decision["thresholds"], "executed": decision["executed"],
              "execution_note": decision["execution_note"]},
    )
    return {
        "deep_evaluation_id": evaluation["evaluation_id"],
        "deep_error_code": (evaluation["error"] or {}).get("code"),
        "deep_model": evaluation["resolved_model"] or evaluation["requested_model"],
        "deep_usage": evaluation["usage"],
        "deep_judgment_vector": evaluation["answers"],
        "deep_question_set_version": evaluation["question_set_version"],
        "next_move": {
            "policy_version": decision["policy_version"], "move": decision["move"],
            "reason_code": decision["reason_code"], "detail": decision["detail"],
            "dimensions": decision["dimensions"], "executed": decision["executed"],
        },
    }
