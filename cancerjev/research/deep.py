"""Phase 4 first slice: deterministic deep evidence revision for one candidate.

Sequence for one explicitly selected candidate: accept the candidate's immutable
StatisticalState evidence E0, compute the eligible registered deterministic
actions in Python, execute exactly one selected action, and persist the result as
a new immutable EvidenceState revision E1 whose parent is E0.

Python owns selection, budgets, side effects, stopping and abstention. The action
itself is deterministic science and never acquires data or calls a model. A
follow-up never rewrites E0 and never promotes or advances a candidate on its own.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.research.nextmove import DEEP_POLICY_VERSION, next_move
from cancerjev.science.actions import (
    ACTION_REGISTRY,
    ACTION_REGISTRY_VERSION,
    CHECK_CONTRADICTED,
    CHECK_NOT_OBSERVED,
    ActionEligibility,
    ActionError,
    ActionOutcome,
    eligible_actions,
    execute,
)
from cancerjev.science.methods import METHODS

FOLLOWUP_LIMIT = 3
EVIDENCE_ITERATION_LIMIT = 2
LIVE_RESEARCH_NOTICE = (
    "REAL OPEN-ACCESS GDC EVIDENCE — DETERMINISTIC RESEARCH ONLY, NOT CLINICAL OR DIAGNOSTIC USE"
)


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
    entity: dict[str, Any]
    promotion_slot: int
    state_id: str
    state: dict[str, Any]
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

    @property
    def eligible_action_ids(self) -> list[str]:
        return [item.action_id for item in self.eligibilities if item.eligible]


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
    revision: dict[str, Any] | None

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status, "action_id": self.action_id,
            "evidence_state_id": self.evidence_state_id, "evidence_hash": self.evidence_hash,
            "iteration": self.iteration, "checks_total": self.checks_total,
            "checks_verified": self.checks_verified, "checks_contradicted": self.checks_contradicted,
            "checks_not_observed": self.checks_not_observed, "error_code": self.error_code,
        }


def _project_sources(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "endpoint": source["endpoint"],
            "normalized_request_hash": source["normalized_request_hash"],
            "response_artifact_id": source["response_artifact_id"],
            "response_sha256": source["response_sha256"],
            "parser_version": source["parser_version"],
            "completeness": source["completeness"],
            "source_release": source["source_release"],
            "json_pointer_or_table_locator": source["json_pointer_or_table_locator"],
        }
        for source in state["provenance"]["sources"]
    ]


def _provenance(state: dict[str, Any], *, action_method: dict[str, Any] | None = None) -> dict[str, Any]:
    methods = list(state["provenance"]["methods"])
    if action_method is not None:
        methods.append({"method_id": action_method["method_id"], "version": action_method["method_version"],
                        "parameters_hash": action_method["parameters_hash"]})
    return {
        "gdc_release": state["provenance"]["gdc_release"],
        "sources": _project_sources(state),
        "methods": methods,
        "environment_hash": state["provenance"]["environment_hash"],
        "action_registry_version": ACTION_REGISTRY_VERSION,
        "selection_artifact_sha256": state["tested_context"]["examined_genes_hash"],
        "input_artifacts": [],
    }


def _metric_block(metric: Any) -> dict[str, Any]:
    if not isinstance(metric, dict):
        return {"value": None, "unit": None, "availability": "NOT_OBSERVED", "reason_code": "FIELD_ABSENT"}
    return {
        "value": metric.get("value"), "unit": metric.get("unit"),
        "availability": metric.get("availability", "NOT_OBSERVED"),
        "reason_code": metric.get("reason_code"),
    }


def _project_level_evidence(state: dict[str, Any]) -> list[dict[str, Any]]:
    mutation = {item.get("project_id"): item for item in state["mutation"]["project_results"]}
    expression = {item.get("project_id"): item for item in state["expression"]["project_results"]}
    rows: list[dict[str, Any]] = []
    for project_id in sorted(set(mutation) | set(expression)):
        mutation_item = mutation.get(project_id, {})
        expression_item = expression.get(project_id, {})
        coverage = expression_item.get("coverage", {}) if isinstance(expression_item.get("coverage"), dict) else {}
        rows.append({
            "project_id": project_id,
            "affected_case_count": _metric_block(mutation_item.get("affected_case_count")),
            "examined_cases": _metric_block(mutation_item.get("examined_cases")),
            "project_case_with_ssm": _metric_block(mutation_item.get("project_case_with_ssm")),
            "cases_with_expression": _metric_block(coverage.get("cases_with_expression")),
            "missing_measurements": _metric_block(coverage.get("missing_measurements")),
        })
    return rows


def _baseline_observations(state: dict[str, Any], *, run_id: str, candidate_id: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []

    def add(method_id: str, *, availability: str, value: Any, unit: str, n_effective: Any,
            missingness: dict[str, Any], notes: tuple[str, ...] = ()) -> None:
        definition = METHODS[method_id]
        observations.append({
            "result_id": stable_id(run_id, f"baseline-result:{candidate_id}:{method_id}"),
            "method_id": definition.method_id,
            "method_version": definition.version,
            "observed": {"value": value, "unit": unit},
            "availability": availability,
            "n_effective": n_effective,
            "missingness": missingness,
            "inference_status": "NOT_APPLICABLE",
            "notes": list(notes),
            "limitations": list(definition.limitations),
        })

    for item in state["mutation"]["project_results"]:
        metric = item.get("affected_case_count", {})
        add(
            "MUTATION_AFFECTED_CASE_COUNT_V1",
            availability=metric.get("availability", "NOT_OBSERVED"),
            value=metric.get("value"), unit=metric.get("unit", "cases"),
            n_effective=item.get("examined_cases", {}).get("value"),
            missingness={"count": 0, "reason": None},
            notes=(f"project {item.get('project_id')}",),
        )
    coverage = state["mutation"].get("coverage", {})
    if isinstance(coverage, dict) and isinstance(coverage.get("case_with_ssm"), dict):
        add(
            "PROJECT_SSM_COVERAGE_V1",
            availability=coverage["case_with_ssm"].get("availability", "NOT_OBSERVED"),
            value=coverage["case_with_ssm"].get("value"), unit="cases",
            n_effective=state["populations"][0].get("examined_n"),
            missingness={"count": 0, "reason": None},
        )
    for item in state["expression"]["project_results"]:
        local = item.get("local", {}) if isinstance(item.get("local"), dict) else {}
        median = local.get("median", {})
        n_missing = local.get("n_missing", {}).get("value")
        add(
            "EXPRESSION_LOG2_SUMMARY_V1",
            availability=median.get("availability", "NOT_OBSERVED"),
            value=median.get("value"), unit=median.get("unit", "log2(UQFPKM+1)"),
            n_effective=local.get("n_finite", {}).get("value") if isinstance(local.get("n_finite"), dict) else None,
            missingness={"count": n_missing, "reason": "EXAMINED_CASES_WITHOUT_RETURNED_VALUE" if n_missing else None},
            notes=(f"project {item.get('project_id')}",),
        )
    return observations


def _baseline_evidence(state: dict[str, Any], candidate: CandidateEvidence, *, run_id: str,
                       eligible_ids: list[str]) -> dict[str, Any]:
    evidence_state_id = stable_id(run_id, f"evidence:{candidate.candidate_id}:0")
    population = state["populations"][0]
    return {
        "schema_version": 2,
        "mode": "LIVE",
        "evidence_state_id": evidence_state_id,
        "run_id": run_id,
        "candidate_id": candidate.candidate_id,
        "created_at": utc_now(),
        "previous_evidence_state_id": None,
        "iteration_number": 0,
        "entity": state["entity"],
        "source_statistical_state": {
            "state_id": candidate.state_id,
            "state_identity_hash": state["state_hash"],
            "state_artifact_id": candidate.state_artifact_id,
            "state_artifact_sha256": candidate.state_artifact_sha256,
        },
        "research_puzzle": {
            "origin": "STATISTICAL_STATE_BASELINE",
            "question": (
                f"What does the recorded evidence for {state['entity']['gene_symbol']} support, and what "
                "follow-up computation is eligible on it?"
            ),
            "interpretation": (
                "The baseline revision is the accepted current evidence of the candidate, not a Jev judgment "
                "and not a new measurement."
            ),
            "proposed_action_ids": eligible_ids,
        },
        "research_only_notice": LIVE_RESEARCH_NOTICE,
        "action": None,
        "deterministic_observations": _baseline_observations(state, run_id=run_id,
                                                             candidate_id=candidate.candidate_id),
        "project_level_evidence": _project_level_evidence(state),
        "cross_project_patterns": {
            "status": "NOT_APPLICABLE",
            "limitations": ["A single cohort is examined; no cross-project comparison is made."],
        },
        "missing_evidence": [
            {
                "needed_evidence": "population_exclusions",
                "availability": "OBSERVED" if population.get("excluded_counts_by_reason") else "NOT_OBSERVED",
                "reason": None if population.get("excluded_counts_by_reason")
                else "the recorded population does not list excluded cases",
            },
        ],
        "quality_and_fragility": {
            "checks_total": 0, "checks_verified": 0, "checks_contradicted": 0, "checks_not_observed": 0,
            "warnings": list(state["quality"].get("missingness", [])),
        },
        "provenance": _provenance(state),
    }


def _observation(check: dict[str, Any], definition: Any, *, run_id: str, candidate_id: str) -> dict[str, Any]:
    outcome = check["outcome"]
    observed = outcome != CHECK_NOT_OBSERVED
    return {
        "result_id": stable_id(run_id, f"result:{candidate_id}:{definition.action_id}:{check['check_id']}"),
        "method_id": definition.method_id,
        "method_version": definition.method_version,
        "check_id": check["check_id"],
        "claim": check["claim"],
        "outcome": outcome,
        "n_effective": check["n_effective"],
        "availability": "OBSERVED" if observed else "NOT_OBSERVED",
        "observed": check["observed"],
        "expected": check["expected"],
        "notes": check["notes"],
        "missingness": {
            "count": 0 if observed else 1,
            "reason": None if observed else "RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION",
        },
        "inference_status": "NOT_APPLICABLE",
        "limitations": check["limitations"] or list(definition.limitations),
    }


def _followup_evidence(outcome: ActionOutcome, candidate: CandidateEvidence, state: dict[str, Any], *,
                       run_id: str, iteration: int, previous_evidence_id: str) -> dict[str, Any]:
    definition = outcome.definition
    checks = [check for check in outcome.checks]
    missing_evidence = [
        {
            "needed_evidence": check["check_id"],
            "availability": "NOT_OBSERVED",
            "reason": "recorded evidence does not permit verification",
        }
        for check in checks if check["outcome"] == CHECK_NOT_OBSERVED
    ]
    missing_evidence.append({
        "needed_evidence": "new_gdc_measurement",
        "availability": "NOT_ACQUIRED",
        "reason": "this deterministic action acquires no new GDC evidence",
    })
    input_artifacts = [
        {"kind": entry["kind"], "ref": entry["ref"], "sha256": entry["sha256"], "verified": entry["verified"]}
        for entry in outcome.inputs
    ]
    provenance = _provenance(state, action_method=definition.ref())
    provenance["input_artifacts"] = input_artifacts
    return {
        "schema_version": 2,
        "mode": "LIVE",
        "evidence_state_id": stable_id(run_id, f"evidence:{candidate.candidate_id}:{iteration}"),
        "run_id": run_id,
        "candidate_id": candidate.candidate_id,
        "created_at": utc_now(),
        "previous_evidence_state_id": previous_evidence_id,
        "iteration_number": iteration,
        "entity": state["entity"],
        "source_statistical_state": {
            "state_id": candidate.state_id,
            "state_identity_hash": state["state_hash"],
            "state_artifact_id": candidate.state_artifact_id,
            "state_artifact_sha256": candidate.state_artifact_sha256,
        },
        "research_puzzle": {
            "origin": "DETERMINISTIC_ACTION_REGISTRY",
            "question": definition.question,
            "interpretation": definition.interpretation,
            "proposed_action_ids": [definition.action_id],
        },
        "research_only_notice": LIVE_RESEARCH_NOTICE,
        "action": {
            **definition.ref(),
            "title": definition.title,
            "unit": definition.unit,
            "required_evidence": list(definition.required_evidence),
            "limitations": list(definition.limitations),
        },
        "deterministic_observations": [
            _observation(check, definition, run_id=run_id, candidate_id=candidate.candidate_id)
            for check in checks
        ],
        "project_level_evidence": _project_level_evidence(state),
        "cross_project_patterns": {
            "status": "NOT_APPLICABLE",
            "limitations": ["A single cohort is examined; no cross-project comparison is made."],
        },
        "missing_evidence": missing_evidence,
        "quality_and_fragility": {
            "checks_total": len(checks),
            "checks_verified": outcome.verified,
            "checks_contradicted": outcome.contradictions,
            "checks_not_observed": outcome.not_observed,
            "warnings": [
                f"CONTRADICTED check {check['check_id']}" for check in checks
                if check["outcome"] == CHECK_CONTRADICTED
            ],
        },
        "provenance": provenance,
    }


def load_candidate_evidence(repository: Any, artifacts: Any, candidate: dict[str, Any]) -> CandidateEvidence:
    """Accept the candidate's immutable StatisticalState evidence, or fail closed."""
    state_id = candidate["source_state_id"]
    row = repository.get_state(state_id)
    if row is None:
        raise DeepError("EVIDENCE_STATE_MISSING", f"candidate {candidate['candidate_id']} names an unknown state")
    metadata = repository.artifact(row["artifact_id"])
    if metadata is None:
        raise DeepError("EVIDENCE_ARTIFACT_MISSING", f"state {state_id} has no artifact metadata")
    try:
        content = artifacts.read(metadata["relative_path"])
    except (OSError, ValueError) as exc:
        raise DeepError("EVIDENCE_ARTIFACT_UNAVAILABLE", f"state {state_id}: {exc}") from exc
    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise DeepError("EVIDENCE_ARTIFACT_CORRUPT", f"state {state_id} artifact bytes do not match its hash")
    state = json.loads(content)
    recomputed = content_hash(statistical_state_identity_payload(state))
    if recomputed != row["state_hash"] or state.get("state_hash") != row["state_hash"]:
        raise DeepError(
            "EVIDENCE_STATE_HASH_MISMATCH",
            f"state {state_id}: recorded {row['state_hash']}, recomputed {recomputed}",
        )
    return CandidateEvidence(
        candidate_id=candidate["candidate_id"], entity=candidate["entity"],
        promotion_slot=candidate["promotion_slot"], state_id=state_id, state=state,
        state_artifact_id=row["artifact_id"], state_artifact_sha256=metadata["sha256"],
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


def plan_deep_slice(*, run_id: str, candidate: dict[str, Any], repository: Any, artifacts: Any,
                    emit: Callable[..., Any], publish_json: Callable[[str, str, Any, str], Any],
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
            candidate_id=candidate["candidate_id"], entity=candidate["entity"],
            promotion_slot=candidate["promotion_slot"], state_id=candidate["source_state_id"], state={},
            state_artifact_id="", state_artifact_sha256=""), baseline_evidence_id=baseline_id,
            baseline_evidence_hash="", baseline_already_present=False, eligibilities=(),
            selected_action_id=None, abstain_reason="EVIDENCE_ACCEPTANCE_FAILED",
            abstain_detail=exc.detail, iteration_number=None, execution_id=None, evidence_state_id=None)

    state = evidence.state
    eligibilities = eligible_actions(state, "STATISTICAL_STATE")
    eligible_ids = [item.action_id for item in eligibilities if item.eligible]

    baseline_id = stable_id(run_id, f"evidence:{candidate['candidate_id']}:0")
    existing_revisions = repository.evidence_revisions(candidate["candidate_id"])
    baseline_present = any(row["evidence_state_id"] == baseline_id for row in existing_revisions)
    baseline_evidence = _baseline_evidence(state, evidence, run_id=run_id, eligible_ids=eligible_ids)
    baseline_hash = content_hash(evidence_state_identity_payload(baseline_evidence))
    if not baseline_present:
        artifact = publish_json(run_id, f"runs/{run_id}/evidence/{baseline_id}.json",
                                baseline_evidence, "evidence-state")
        emit(
            run_id, "EVIDENCE_STATE_CREATED", f"evidence:{baseline_id}:created",
            f"Accepted baseline evidence E0 for {evidence.entity['gene_symbol']} (iteration 0).",
            stage="DEEP_ANALYSIS", candidate_id=candidate["candidate_id"], iteration=0,
            data={"evidence_state_id": baseline_id, "evidence_hash": baseline_hash,
                  "iteration": 0, "previous_evidence_state_id": None, "candidate_id": candidate["candidate_id"],
                  "state_id": evidence.state_id, "origin": "STATISTICAL_STATE_BASELINE"},
            artifact_refs=[artifact.ref()],
            registrations=[
                repository.artifact_registration(artifact, run_id),
                repository.evidence_state_registration(
                    evidence_state_id=baseline_id, run_id=run_id, candidate_id=candidate["candidate_id"],
                    previous_evidence_state_id=None, iteration=0, evidence_hash=baseline_hash,
                    artifact_id=artifact.artifact_id,
                    summary_json=canonical_json({
                        "entity": evidence.entity, "iteration": 0, "origin": "STATISTICAL_STATE_BASELINE",
                        "state_id": evidence.state_id,
                    }).decode(),
                    created_at=utc_now(),
                ),
                repository.candidate_status_registration(
                    candidate_id=candidate["candidate_id"], status="DEEP_ANALYSIS",
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
              "input_evidence_hash": state["state_hash"], "eligible_action_ids": eligible_ids,
              "ineligible": [
                  {"action_id": item.action_id, "reasons": list(item.reasons)}
                  for item in eligibilities if not item.eligible
              ],
              "selection_policy": "EXPLICIT_SELECTION_ONLY",
              "registry_version": ACTION_REGISTRY_VERSION},
    )

    action_id, abstain_reason, abstain_detail = _resolve_requested_action(eligibilities, requested_action_id)
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
    input_evidence_hash = state["state_hash"]
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


def _execute_action(*, run_id: str, candidate: CandidateEvidence, record: dict[str, Any], input_kind: str,
                    action_id: str, previous_evidence_id: str, iteration: int, execution_id: str,
                    evidence_state_id: str, repository: Any, emit: Callable[..., Any],
                    publish_json: Callable[[str, str, Any, str], Any],
                    read_artifact: Callable[[str], bytes | None]) -> FollowUpResult:
    """Run one registered deterministic action and persist an immutable revision.

    The action's declared input kind decides what it reads: an accepted
    StatisticalState, or an existing immutable evidence revision. Every revision
    copies its project-level evidence from the accepted state, links its parent and
    cites the producing action.
    """
    definition = ACTION_REGISTRY[action_id]
    if input_kind == "STATISTICAL_STATE":
        input_evidence_hash = record["state_hash"]
        input_evidence_state_id = previous_evidence_id
    else:
        input_evidence_hash = content_hash(evidence_state_identity_payload(record))
        input_evidence_state_id = record["evidence_state_id"]
    emit(
        run_id, "FOLLOWUP_STARTED", f"deep:{execution_id}:started",
        f"Deterministic follow-up {action_id} started for candidate {candidate.candidate_id}.",
        stage="FOLLOWUP", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"execution_id": execution_id, "candidate_id": candidate.candidate_id,
              "action_id": action_id, "action_version": definition.version,
              "input_ref_kind": input_kind, "input_evidence_state_id": input_evidence_state_id,
              "input_evidence_hash": input_evidence_hash},
    )
    try:
        outcome = execute(action_id, record, read_artifact=read_artifact)
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

    revision = _followup_evidence(outcome, candidate, candidate.state, run_id=run_id, iteration=iteration,
                                  previous_evidence_id=previous_evidence_id)
    evidence_hash = content_hash(evidence_state_identity_payload(revision))
    outcome_label = "COMPLETED_WITH_CONTRADICTIONS" if outcome.contradictions else "COMPLETED"
    artifact = publish_json(run_id, f"runs/{run_id}/evidence/{evidence_state_id}.json",
                            revision, "evidence-state")
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
                    "entity": candidate.entity, "iteration": iteration, "action_id": action_id,
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
        checks_not_observed=outcome.not_observed, error_code=None, revision=revision,
    )


def execute_followup(*, run_id: str, plan: DeepPlan, repository: Any, emit: Callable[..., Any],
                     publish_json: Callable[[str, str, Any, str], Any],
                     read_artifact: Callable[[str], bytes | None]) -> FollowUpResult:
    """Run the selected deterministic action over the candidate's accepted evidence."""
    if plan.selected_action_id is None or plan.iteration_number is None or plan.execution_id is None \
            or plan.evidence_state_id is None:
        raise DeepError("FOLLOWUP_NOT_PLANNED", "execute_followup requires a selected action plan")
    return _execute_action(
        run_id=run_id, candidate=plan.candidate, record=plan.candidate.state,
        input_kind="STATISTICAL_STATE", action_id=plan.selected_action_id,
        previous_evidence_id=plan.baseline_evidence_id, iteration=plan.iteration_number,
        execution_id=plan.execution_id, evidence_state_id=plan.evidence_state_id,
        repository=repository, emit=emit, publish_json=publish_json, read_artifact=read_artifact,
    )


@dataclass(frozen=True)
class DispatchResult:
    dispatched: bool
    reason_code: str
    action_id: str | None
    result: FollowUpResult | None
    judgement: dict[str, Any] | None

    def summary(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched, "reason_code": self.reason_code, "action_id": self.action_id,
            "evidence_state_id": self.result.evidence_state_id if self.result else None,
            "iteration": self.result.iteration if self.result else None,
            "next_move": (self.judgement or {}).get("next_move"),
        }


def dispatch_recorded_move(*, run_id: str, candidate: CandidateEvidence, result: FollowUpResult,
                           decision: dict[str, Any], repository: Any, emit: Callable[..., Any],
                           publish_json: Callable[[str, str, Any, str], Any],
                           read_artifact: Callable[[str], bytes | None], authorized: bool,
                           jev_service: Any = None) -> DispatchResult:
    """Dispatch one recorded FOLLOW_UP, only when an operator authorized it.

    At most one dispatch happens per run, it obeys the existing follow-up and
    revision caps, and a dispatched revision is judged again by the same deep
    fan-out. Every refusal reason is recorded rather than silently dropped.
    """

    def refuse(reason_code: str, detail: str) -> DispatchResult:
        emit(
            run_id, "NEXT_MOVE_DISPATCHED", f"dispatch:{result.evidence_state_id}:{reason_code}",
            f"Recorded next move was not dispatched: {reason_code}.",
            stage="FOLLOWUP", level="warning" if reason_code != "MOVE_NOT_FOLLOW_UP" else "info",
            candidate_id=candidate.candidate_id, iteration=result.iteration,
            data={"evidence_state_id": result.evidence_state_id, "move": decision.get("move"),
                  "reason_code": reason_code, "detail": detail, "dispatched": False,
                  "authorized": authorized},
        )
        return DispatchResult(dispatched=False, reason_code=reason_code, action_id=None,
                              result=None, judgement=None)

    if decision.get("move") != "FOLLOW_UP":
        return refuse("MOVE_NOT_FOLLOW_UP",
                      f"the recorded move is {decision.get('move')}, so nothing is dispatched")
    if not authorized:
        return refuse("DISPATCH_NOT_AUTHORIZED",
                      "dispatching a recorded move requires explicit operator authorization")
    if result.revision is None or result.evidence_state_id is None or result.iteration is None:
        return refuse("INPUT_REVISION_MISSING", "no immutable revision is available to continue from")
    action_ids = sorted(decision.get("dimensions", {}).get("distinct_eligible_action_ids") or [])
    if not action_ids:
        return refuse("NO_DISTINCT_ELIGIBLE_ACTION",
                      "no registered action other than the producing one is eligible for this revision")
    action_id = action_ids[0]
    completed = [row for row in repository.followup_executions_for(candidate.candidate_id)
                 if row["status"] == "COMPLETED"]
    if len(completed) >= FOLLOWUP_LIMIT:
        return refuse("FOLLOWUP_LIMIT_REACHED", f"the candidate reached the follow-up limit {FOLLOWUP_LIMIT}")
    iteration = result.iteration + 1
    if iteration > EVIDENCE_ITERATION_LIMIT:
        return refuse("EVIDENCE_ITERATION_LIMIT_REACHED",
                      f"iteration {iteration} exceeds the revision limit {EVIDENCE_ITERATION_LIMIT}")
    execution_id = stable_id(run_id, f"followup:{candidate.candidate_id}:{action_id}:{iteration}")
    evidence_state_id = stable_id(run_id, f"evidence:{candidate.candidate_id}:{iteration}")
    followup = _execute_action(
        run_id=run_id, candidate=candidate, record=result.revision, input_kind="EVIDENCE_STATE",
        action_id=action_id, previous_evidence_id=result.evidence_state_id, iteration=iteration,
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
                  "action_id": action_id, "dispatched": False, "authorized": True},
        )
        return DispatchResult(dispatched=False, reason_code="DISPATCH_ACTION_FAILED", action_id=action_id,
                              result=followup, judgement=None)
    judgement = None
    if jev_service is not None:
        judgement = judge_evidence_revision(run_id=run_id, candidate=candidate, result=followup,
                                            jev_service=jev_service, emit=emit)
    emit(
        run_id, "NEXT_MOVE_DISPATCHED", f"dispatch:{result.evidence_state_id}:{action_id}",
        f"Recorded FOLLOW_UP dispatched as {action_id} on the operator's authorization.",
        stage="FOLLOWUP", candidate_id=candidate.candidate_id, iteration=iteration,
        data={"evidence_state_id": result.evidence_state_id, "move": decision.get("move"),
              "reason_code": "DISPATCHED", "action_id": action_id, "execution_id": execution_id,
              "output_evidence_state_id": evidence_state_id, "output_iteration": iteration,
              "dispatched": True, "authorized": True,
              "new_move": (judgement or {}).get("next_move", {}).get("move")},
    )
    return DispatchResult(dispatched=True, reason_code="DISPATCHED", action_id=action_id,
                          result=followup, judgement=judgement)


def judge_evidence_revision(*, run_id: str, candidate: CandidateEvidence, result: FollowUpResult,
                            jev_service: Any, emit: Callable[..., Any]) -> dict[str, Any]:
    """One Deep Jev fan-out over the new revision, then the Python next-move policy.

    The eligible set is computed from the revision's own declared input kind, so the
    judgment and the policy see exactly the actions that could run on this revision.
    The judgment is an input to the policy: Jev does not select, authorize or execute
    the move, and no measured field is written from it.
    """
    if result.revision is None or result.evidence_state_id is None or result.evidence_hash is None:
        return {"deep_evaluation_id": None, "deep_error_code": "NO_REVISION_TO_JUDGE",
                "next_move": None}
    revision_eligibilities = eligible_actions(result.revision, "EVIDENCE_STATE")
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
    evaluation = jev_service.evaluate_evidence(
        run_id=run_id, evidence=result.revision, eligible_actions=eligible_action_payloads,
        evidence_hash=result.evidence_hash, emit=emit,
    )
    judgment = {
        "answers": evaluation["answers"], "error": evaluation["error"],
        "action_id": result.action_id,
    }
    decision = next_move(
        checks=result.revision["quality_and_fragility"], judgment=judgment,
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
