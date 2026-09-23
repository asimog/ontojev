"""Registered deterministic follow-up actions over immutable statistical evidence.

An action is a bounded, reproducible computation over evidence that already exists.
It never acquires data, never calls a model, never computes a new biological
quantity and never rewrites the evidence it reads. Eligibility is a deterministic
prerequisite check: what cannot be verified from retained evidence is NOT_OBSERVED,
never a silent pass.

Result ids, persistence and selection policy are owned by ``research``; this module
owns the action contract, eligibility and the deterministic computation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.events import canonical_json

CHECK_VERIFIED = "VERIFIED"
CHECK_CONTRADICTED = "CONTRADICTED"
CHECK_NOT_OBSERVED = "NOT_OBSERVED"

OUTCOME_COMPLETED = "COMPLETED"

REQUIRED_SECTIONS = ("populations", "mutation", "expression", "quality", "tested_context", "provenance")


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
            "limitations": list(self.limitations), "changes_evidence": self.changes_evidence,
        }


ACTION_REGISTRY_VERSION = "1"

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
    checks: tuple[dict[str, Any], ...]
    inputs: tuple[dict[str, Any], ...]
    contradictions: int
    unavailable_reason: str | None
    definition: ActionDefinition

    @property
    def verified(self) -> int:
        return sum(1 for check in self.checks if check["outcome"] == CHECK_VERIFIED)

    @property
    def not_observed(self) -> int:
        return sum(1 for check in self.checks if check["outcome"] == CHECK_NOT_OBSERVED)


def _is_observed_metric(metric: Any) -> bool:
    return isinstance(metric, dict) and metric.get("availability") == "OBSERVED"


def _metric_value(metric: Any) -> float | int | None:
    if not _is_observed_metric(metric):
        return None
    value = metric.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _check(check_id: str, claim: str, outcome: str, *, observed: dict[str, Any],
           expected: dict[str, Any] | None = None, notes: tuple[str, ...] = (),
           limitations: tuple[str, ...] = (), n_effective: int | None = None) -> dict[str, Any]:
    return {
        "check_id": check_id, "claim": claim, "outcome": outcome, "observed": observed,
        "expected": expected or {}, "n_effective": n_effective, "notes": list(notes),
        "limitations": list(limitations),
    }


def _first_population(state: dict[str, Any]) -> dict[str, Any]:
    populations = state.get("populations")
    if isinstance(populations, list) and populations and isinstance(populations[0], dict):
        return populations[0]
    return {}


def _project_results(state: dict[str, Any], lane: str) -> list[dict[str, Any]]:
    section = state.get(lane)
    if not isinstance(section, dict):
        return []
    results = section.get("project_results")
    return [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []


def eligibility(state: dict[str, Any], definition: ActionDefinition) -> ActionEligibility:
    """Deterministic prerequisites for an action on one immutable evidence snapshot."""
    reasons: list[str] = []
    prerequisites: dict[str, Any] = {
        "schema_version": state.get("schema_version"),
        "mode": state.get("mode"),
        "gene_id": (state.get("entity") or {}).get("gene_id") if isinstance(state.get("entity"), dict) else None,
    }
    if state.get("schema_version") != 2 or state.get("mode") != "LIVE":
        reasons.append("SNAPSHOT_NOT_LIVE_SCIENTIFIC_EVIDENCE")
    missing = [section for section in REQUIRED_SECTIONS if not isinstance(state.get(section), (dict, list))]
    if missing:
        reasons.append("EVIDENCE_SECTION_MISSING:" + ",".join(missing))
    population = _first_population(state)
    examined_n = population.get("examined_n")
    prerequisites["examined_n"] = examined_n
    if not isinstance(examined_n, int) or examined_n <= 0:
        reasons.append("EXAMINED_POPULATION_EMPTY")
    provenance = state.get("provenance") if isinstance(state.get("provenance"), dict) else {}
    sources = provenance.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    prerequisites["source_count"] = source_count
    if source_count == 0:
        reasons.append("PROVENANCE_SOURCES_MISSING")
    prerequisites["mutation_projects"] = len(_project_results(state, "mutation"))
    prerequisites["expression_projects"] = len(_project_results(state, "expression"))
    if not _project_results(state, "mutation"):
        reasons.append("MUTATION_LANE_MISSING")
    if not _project_results(state, "expression"):
        reasons.append("EXPRESSION_LANE_MISSING")
    tested_context = state.get("tested_context") if isinstance(state.get("tested_context"), dict) else {}
    prerequisites["examined_genes_n"] = (tested_context.get("coverage") or {}).get("examined_genes_n") \
        if isinstance(tested_context.get("coverage"), dict) else None
    return ActionEligibility(action_id=definition.action_id, eligible=not reasons,
                             reasons=tuple(reasons), prerequisites=prerequisites)


def eligible_actions(state: dict[str, Any],
                     registry: dict[str, ActionDefinition] | None = None) -> tuple[ActionEligibility, ...]:
    definitions = registry or ACTION_REGISTRY
    return tuple(
        eligibility(state, definitions[action_id]) for action_id in sorted(definitions)
    )


def _check_frame_agreement(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    population = _first_population(state)
    eligible_n = population.get("eligible_n")
    examined_n = population.get("examined_n")
    mutation = _project_results(state, "mutation")
    expression = _project_results(state, "expression")
    observed = {
        "eligible_n": eligible_n, "examined_n": examined_n,
        "mutation_examined_cases": sorted(
            value for value in (_metric_value(item.get("examined_cases")) for item in mutation) if value is not None
        ),
        "expression_examined_cases": sorted(
            value for value in (_metric_value(item.get("coverage", {}).get("examined_cases"))
                                for item in expression) if value is not None
        ),
    }
    values = [examined_n, *observed["mutation_examined_cases"], *observed["expression_examined_cases"]]
    if not isinstance(examined_n, int) or not observed["mutation_examined_cases"] \
            or not observed["expression_examined_cases"]:
        return _check(
            "COHORT_FRAME_AGREEMENT",
            "Every lane examined the same recorded cohort case frame.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=None,
            notes=("a lane does not record an examined-case count",),
        ), []
    outcome = CHECK_VERIFIED if set(values) == {examined_n} else CHECK_CONTRADICTED
    return _check(
        "COHORT_FRAME_AGREEMENT",
        "Every lane examined the same recorded cohort case frame.",
        outcome, observed=observed, expected={"examined_n": examined_n}, n_effective=examined_n,
        notes=() if outcome == CHECK_VERIFIED else ("lanes disagree on the examined case frame",),
    ), []


def _check_expression_coverage(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results = _project_results(state, "expression")
    observed: dict[str, Any] = {"projects": []}
    contradictions: list[str] = []
    unverifiable: list[str] = []
    for item in results:
        coverage = item.get("coverage") if isinstance(item.get("coverage"), dict) else {}
        local = item.get("local") if isinstance(item.get("local"), dict) else {}
        project_id = item.get("project_id")
        examined = _metric_value(coverage.get("examined_cases"))
        with_expression = _metric_value(coverage.get("cases_with_expression"))
        missing = _metric_value(coverage.get("missing_measurements"))
        returned = _metric_value(coverage.get("returned_case_columns"))
        valid = _metric_value(coverage.get("valid_measurements"))
        n_missing = _metric_value(local.get("n_missing"))
        n_missing_columns = _metric_value(local.get("n_missing_case_columns"))
        n_returned = _metric_value(local.get("n_returned"))
        n_finite = _metric_value(local.get("n_finite"))
        missing_ids = local.get("missing_case_ids")
        missing_ids_n = len(missing_ids) if isinstance(missing_ids, list) else None
        observed["projects"].append({
            "project_id": project_id, "examined_cases": examined, "cases_with_expression": with_expression,
            "missing_measurements": missing, "returned_case_columns": returned,
            "valid_measurements": valid, "n_missing": n_missing,
            "n_missing_case_columns": n_missing_columns, "missing_case_ids_n": missing_ids_n,
            "n_returned": n_returned, "n_finite": n_finite,
        })
        required = (examined, with_expression, missing, n_missing, n_missing_columns, missing_ids_n)
        if any(value is None for value in required):
            unverifiable.append(f"{project_id}: coverage fields not observed")
            continue
        if with_expression + missing != examined:
            contradictions.append(f"{project_id}: cases_with_expression + missing != examined")
        if not (missing == n_missing == n_missing_columns == missing_ids_n):
            contradictions.append(f"{project_id}: recorded missingness counts disagree")
        if n_returned is not None and n_returned + missing != examined:
            contradictions.append(f"{project_id}: returned case columns + missing != examined")
        if returned is not None and n_returned is not None and returned != n_returned:
            contradictions.append(f"{project_id}: returned_case_columns != n_returned")
        if valid is not None and n_finite is not None and valid > n_finite:
            contradictions.append(f"{project_id}: valid_measurements exceeds finite values")
    if contradictions:
        outcome = CHECK_CONTRADICTED
    elif unverifiable or not results:
        outcome = CHECK_NOT_OBSERVED
    else:
        outcome = CHECK_VERIFIED
    notes = tuple(contradictions[:3] + unverifiable[:3])
    return _check(
        "EXPRESSION_COVERAGE_ARITHMETIC",
        "Recorded expression coverage and missingness agree per project and against the examined frame.",
        outcome, observed=observed, expected={"cases_with_expression + missing": "examined_cases"},
        n_effective=len(results), notes=notes,
    ), []


def _check_mutation_scope(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results = _project_results(state, "mutation")
    scope = state.get("scope") if isinstance(state.get("scope"), dict) else {}
    scope_projects = scope.get("projects") if isinstance(scope.get("projects"), list) else None
    observed: dict[str, Any] = {"projects": [], "scope_projects": scope_projects}
    contradictions: list[str] = []
    unverifiable: list[str] = []
    for item in results:
        project_id = item.get("project_id")
        affected = _metric_value(item.get("affected_case_count"))
        with_ssm = _metric_value(item.get("project_case_with_ssm"))
        examined = _metric_value(item.get("examined_cases"))
        observed["projects"].append({
            "project_id": project_id, "affected_case_count": affected,
            "project_case_with_ssm": with_ssm, "examined_cases": examined,
        })
        if scope_projects is not None and project_id not in scope_projects:
            contradictions.append(f"{project_id}: mutation result outside the recorded scope")
        if affected is None:
            unverifiable.append(f"{project_id}: affected case count not observed")
            continue
        if examined is not None and affected > examined:
            contradictions.append(f"{project_id}: affected count exceeds the examined frame")
        if with_ssm is None:
            unverifiable.append(f"{project_id}: project SSM coverage not observed")
            continue
        if affected > with_ssm:
            contradictions.append(f"{project_id}: affected count exceeds project SSM-positive cases")
    if contradictions:
        outcome = CHECK_CONTRADICTED
    elif unverifiable or not results:
        outcome = CHECK_NOT_OBSERVED
    else:
        outcome = CHECK_VERIFIED
    return _check(
        "MUTATION_COUNT_SCOPE",
        "The recorded per-gene affected count is scoped to the examined project and stays within its SSM coverage.",
        outcome, observed=observed,
        expected={"affected_case_count <= project_case_with_ssm": True, "project in scope": True},
        n_effective=len(results), notes=tuple(contradictions[:3] + unverifiable[:3]),
        limitations=(
            "Provider counts cannot distinguish mutation absence from unassayed cases.",
            "No recurrence fraction is computed; the count has no matched denominator.",
        ),
    ), []


def _read_bytes(read_artifact: Callable[[str], bytes | None], artifact_id: Any) -> bytes | None:
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    try:
        return read_artifact(artifact_id)
    except (OSError, ValueError, KeyError):
        return None


def _check_tested_universe(state: dict[str, Any],
                           read_artifact: Callable[[str], bytes | None]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tested_context = state.get("tested_context") if isinstance(state.get("tested_context"), dict) else {}
    gene_id = (state.get("entity") or {}).get("gene_id") if isinstance(state.get("entity"), dict) else None
    ref = tested_context.get("examined_genes_ref")
    recorded_hash = tested_context.get("examined_genes_hash")
    coverage = tested_context.get("coverage") if isinstance(tested_context.get("coverage"), dict) else {}
    examined_genes_n = coverage.get("examined_genes_n")
    content = _read_bytes(read_artifact, ref)
    observed: dict[str, Any] = {
        "recorded_hash": recorded_hash, "recomputed_hash": None,
        "selected_gene_ids_n": None, "gene_in_selected_ids": None, "examined_genes_n": examined_genes_n,
    }
    inputs = [{"kind": "SELECTION_ARTIFACT", "ref": ref, "sha256": recorded_hash,
               "verified": False}] if ref else []
    if content is None:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=("retained selection artifact is unavailable",),
        ), inputs
    recomputed = hashlib.sha256(content).hexdigest()
    observed["recomputed_hash"] = recomputed
    input_entry = {"kind": "SELECTION_ARTIFACT", "ref": ref, "sha256": recomputed, "verified": recomputed == recorded_hash}
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
    if selected_ids is None or gene_id is None:
        return _check(
            "TESTED_UNIVERSE_REPRODUCIBLE",
            "The recorded examined gene universe is reproducible from its retained selection artifact.",
            CHECK_NOT_OBSERVED, observed=observed, n_effective=0,
            notes=("selection artifact does not record the selected gene ids",),
        ), [input_entry]
    contradictions = []
    if gene_id not in selected_ids:
        contradictions.append("candidate gene is absent from the retained selected gene ids")
    if isinstance(examined_genes_n, int) and examined_genes_n != len(selected_ids):
        contradictions.append("examined_genes_n disagrees with the retained selected gene ids")
    outcome = CHECK_CONTRADICTED if contradictions else CHECK_VERIFIED
    return _check(
        "TESTED_UNIVERSE_REPRODUCIBLE",
        "The recorded examined gene universe is reproducible from its retained selection artifact.",
        outcome, observed=observed, expected={"examined_genes_n": len(selected_ids)},
        n_effective=len(selected_ids), notes=tuple(contradictions),
    ), [input_entry]


def _check_response_integrity(state: dict[str, Any],
                              read_artifact: Callable[[str], bytes | None]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provenance = state.get("provenance") if isinstance(state.get("provenance"), dict) else {}
    sources = provenance.get("sources") if isinstance(provenance.get("sources"), list) else []
    verified = 0
    mismatched: list[str] = []
    unavailable: list[str] = []
    attempts_unlinked: list[str] = []
    inputs: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        ref = source.get("response_artifact_id")
        recorded = source.get("response_sha256")
        endpoint = source.get("endpoint")
        if not source.get("request_id"):
            attempts_unlinked.append(str(source.get("json_pointer_or_table_locator") or endpoint))
        content = _read_bytes(read_artifact, ref)
        if content is None:
            unavailable.append(str(ref))
            inputs.append({"kind": "RESPONSE_ARTIFACT", "ref": ref, "sha256": recorded, "verified": False})
            continue
        recomputed = hashlib.sha256(content).hexdigest()
        matched = recomputed == recorded
        verified += int(matched)
        if not matched:
            mismatched.append(f"{endpoint}: retained bytes do not hash to the recorded response hash")
        inputs.append({"kind": "RESPONSE_ARTIFACT", "ref": ref, "sha256": recomputed, "verified": matched})
    observed = {
        "sources": len(sources), "verified": verified, "mismatched": len(mismatched),
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
        outcome, observed=observed, expected={"verified": len(sources)}, n_effective=len(sources),
        notes=tuple(notes),
    ), inputs


def canonical_payload(content: bytes) -> Any:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def execute(action_id: str, state: dict[str, Any], *,
            read_artifact: Callable[[str], bytes | None]) -> ActionOutcome:
    """Run one registered deterministic action over an immutable evidence snapshot."""
    definition = ACTION_REGISTRY.get(action_id)
    if definition is None:
        raise ActionError("UNKNOWN_ACTION", f"{action_id} is not a registered action")
    decision = eligibility(state, definition)
    if not decision.eligible:
        raise ActionError("ACTION_INELIGIBLE", ";".join(decision.reasons))
    frame, _ = _check_frame_agreement(state)
    coverage, _ = _check_expression_coverage(state)
    scope, _ = _check_mutation_scope(state)
    universe, universe_inputs = _check_tested_universe(state, read_artifact)
    integrity, response_inputs = _check_response_integrity(state, read_artifact)
    checks = (frame, coverage, scope, universe, integrity)
    inputs = ([{"kind": "STATISTICAL_STATE_ARTIFACT", "ref": state.get("state_id"),
                "sha256": state.get("state_hash"), "verified": True}] + universe_inputs + response_inputs)
    return ActionOutcome(
        action_id=definition.action_id, status=OUTCOME_COMPLETED, checks=checks, inputs=tuple(inputs),
        contradictions=sum(1 for check in checks if check["outcome"] == CHECK_CONTRADICTED),
        unavailable_reason=None, definition=definition,
    )
