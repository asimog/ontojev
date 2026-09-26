"""Live orchestrator: bounded open-access GDC sweep to canonical typed states.

Sequence: INVENTORY → GDC_FAST_SEARCH (provider-ranked mutation discovery) →
STATE_GENERATION (typed mutation, expression and coverage lanes) → optional
JEV_WIDE → optional explicit deep-candidate investigation → terminal run event.
Every request goes through the sole transport; every measured number comes from
deterministic methods; Jev never computes a measurement and never runs an action.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from cancerjev.config import Settings
from cancerjev.domain.codecs import state_identity, write_state
from cancerjev.domain.discovery import LIVE_RUN_MAX_BYTES, LIVE_RUN_MAX_REQUESTS
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.measurements import (
    Acquisition,
    MetricRecord,
    ObservedCount,
    OperationalSource,
    digest,
)
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.domain.scientific import StatisticalState
from cancerjev.gdc.endpoints import (
    cohort_project_request,
    genes_request,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.parsers import (
    DiscoveryHit,
    GeneRecord,
    ParserError,
    ProjectCoverage,
    ProjectRecord,
    parse_genes,
    parse_projects,
    parse_status,
    parse_top_mutated_genes,
    response_warnings,
)
from cancerjev.gdc.transport import BudgetCaps, GDCTransport, RunBudget, TransportError
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    LiveRunError,
    acquire_project_coverage,
    acquire_project_frame,
    acquire_project_mutation_occurrence_scan,
    response_meta,
    response_operational_source,
)
from cancerjev.research.acquisition import (
    _merge_expression_availability as _merge_expression_availability,
)
from cancerjev.research.deep import stable_id
from cancerjev.research.discovery import publish_occurrence_scan
from cancerjev.research.investigation import run_candidate_investigation
from cancerjev.research.ranking import PROMOTION_LIMIT
from cancerjev.research.seams import HypothesisGenerator
from cancerjev.research.specs import LUAD_RESEARCH_V1, ResearchSpec
from cancerjev.research.wide import run_wide_evaluation
from cancerjev.science.methods import (
    ProjectFrame,
    ScannedMutationCounts,
    ScienceError,
    compute_statistical_state,
)
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.repositories import Repository

WIDE_SCAN_RULE = (
    "states_valid = states generated; states_selected = states admitted by the active ranking policy"
)


def _metric_summary(record: MetricRecord) -> dict[str, Any]:
    """Presentation projection of one typed metric; not a scientific model."""
    return {"value": record.value, "unit": record.unit,
            "availability": record.availability.value, "reason_code": record.reason_code}


def _state_summary(state: StatisticalState, artifact: PublishedArtifact, mode: str) -> dict[str, Any]:
    """Operational/presentation summary stored beside a registered state."""
    projects = len(state.projects)
    observed_mutation = sum(1 for project in state.projects
                            if isinstance(project.mutation.affected_cases, ObservedCount))
    observed_expression = state.cross_project.projects_with_expression_observation

    def availability(count: int) -> str:
        return "OBSERVED" if count == projects else ("PARTIAL" if count else "INSUFFICIENT")

    return {
        "entity": {"gene_id": state.entity.gene_id, "gene_symbol": state.entity.symbol},
        "mode": mode,
        "mutation_availability": availability(observed_mutation),
        "expression_availability": availability(observed_expression),
        "projects_with_mutation_observation": state.cross_project.projects_with_mutation_observation,
        "projects_with_expression_observation": observed_expression,
        "affected_case_total": _metric_summary(state.cross_project.affected_case_total),
        "top_project_share": _metric_summary(state.cross_project.top_project_share),
        "coverage_imbalance": state.cross_project.coverage_imbalance,
        "completeness": "COMPLETE" if state.quality.acquisition is Acquisition.COMPLETE else "PARTIAL",
        "artifact_id": artifact.artifact_id,
        "artifact_sha256": artifact.sha256,
    }


@dataclass
class Inventory:
    release: str | None
    release_commit: str | None
    projects: list[ProjectRecord]
    selected: list[ProjectRecord]
    inventory_artifact: PublishedArtifact
    sources: tuple[OperationalSource, ...]
    warnings: list[str]
    scope_hash: str


@dataclass
class Selection:
    discovery_by_project: dict[str, dict[str, DiscoveryHit]]
    count_genes: list[str]
    selected_gene_ids: list[str]
    genes: dict[str, GeneRecord]
    scan_counts: dict[str, ScannedMutationCounts]
    coverage: ProjectCoverage
    sources: tuple[OperationalSource, ...]
    warnings: list[str]
    artifact: PublishedArtifact
    examined_genes_hash: str


@dataclass
class LiveOrchestrator:
    settings: Settings
    repository: Repository
    artifacts: ArtifactStore
    render: Callable[..., Any] = field(default=lambda *args, **kwargs: None)
    jev_service: JevService | None = None
    worker_id: str = "live-worker"
    transport_factory: Callable[[Repository, ArtifactStore, RunBudget, str, Callable[..., Any]], AcquisitionTransport] | None = None
    research_spec: ResearchSpec = LUAD_RESEARCH_V1
    deep_selection: str | None = None
    deep_selections: tuple[str, ...] = ()
    deep_action_id: str | None = None
    deep_followup_authorized: bool = False
    deep_hypotheses_requested: bool = False
    llm_generator: HypothesisGenerator | None = None
    run_mode: str = "LIVE"
    fixture_id: str | None = None
    fixture_version: str | None = None
    execution_ownership: ExecutionOwnership = ExecutionOwnership.SYSTEM_AUTONOMOUS

    # ------------------------------------------------------------- event helpers

    def _event(self, run_id: str, event_type: str, key: str, message: str, *, stage: str | None = None,
               data: dict[str, Any] | None = None, level: str = "info", candidate_id: str | None = None,
               iteration: int | None = None,
               artifact_refs: list[dict[str, Any]] | None = None,
               registrations: list[tuple[str, tuple[Any, ...]]] | None = None) -> dict[str, Any]:
        event = self.repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, stage=stage,
            data=data or {}, level=level, candidate_id=candidate_id, iteration=iteration,
            artifact_refs=artifact_refs, registrations=registrations,
        )
        self.render(event)
        return event

    def _stage[T](self, run_id: str, stage: str, function: Callable[[], T]) -> T:
        started = time.monotonic()
        self._event(run_id, "STAGE_STARTED", f"stage:{stage}:started:{uuid4()}", f"Stage {stage} started.", stage=stage)
        try:
            result = function()
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            self._event(
                run_id, "STAGE_COMPLETED", f"stage:{stage}:completed:{uuid4()}",
                f"Stage {stage} ended with error: {type(exc).__name__}.", stage=stage, level="error",
                data={"outcome": "FAILED", "elapsed_ms": elapsed, "error": str(exc)},
            )
            raise
        elapsed = int((time.monotonic() - started) * 1000)
        self._event(
            run_id, "STAGE_COMPLETED", f"stage:{stage}:completed:{uuid4()}",
            f"Stage {stage} completed.", stage=stage,
            data={"outcome": "COMPLETED", "elapsed_ms": elapsed},
        )
        return result

    def _publish_json(self, run_id: str, relative_path: str, payload: object, purpose: str) -> PublishedArtifact:
        content = canonical_json(payload) if not isinstance(payload, bytes) else payload
        return self.artifacts.publish(relative_path, content, "application/json", purpose)

    _meta = staticmethod(response_meta)
    _source = staticmethod(response_operational_source)

    # --------------------------------------------------------------------- run

    def run(self) -> str:
        operator_flags = any((
            self.deep_selection, self.deep_selections, self.deep_action_id,
            self.deep_followup_authorized, self.deep_hypotheses_requested,
        ))
        if operator_flags and self.execution_ownership is not ExecutionOwnership.RESEARCHER_RUN:
            raise LiveRunError(
                "OPERATOR_FLAGS_REQUIRE_RESEARCHER_RUN",
                "operator deep flags are only valid for an explicit researcher run",
            )
        spec_payload = self.research_spec.as_dict()
        cohort = self.research_spec.cohort
        caps = BudgetCaps(
            max_requests=LIVE_RUN_MAX_REQUESTS,
            max_bytes=LIVE_RUN_MAX_BYTES,
            per_response_bytes=self.settings.gdc_per_response_bytes,
            timeout_seconds=self.settings.gdc_timeout_seconds,
        )
        budget = RunBudget(caps=caps)
        run_id = self.repository.create_run(
            self.worker_id, mode=self.run_mode, fixture_id=self.fixture_id,
            fixture_version=self.fixture_version, ownership=self.execution_ownership,
            scope={
                "purpose": "LIVE_SWEEP", "spec_id": self.research_spec.spec_id,
                "domain": cohort.domain, "cohort": cohort.cohort_id,
                "project_id": cohort.project_id, "acquisition": spec_payload["acquisition"],
                "selection_rule": self.research_spec.cohort_selection_rule(),
            },
        )

        def emit(event_type: str, key: str, message: str, **kwargs: Any) -> Any:
            return self._event(run_id, event_type, key, message, **kwargs)

        transport = (
            self.transport_factory(self.repository, self.artifacts, budget, run_id, emit)
            if self.transport_factory is not None
            else GDCTransport(self.repository, self.artifacts, budget, run_id, emit,
                              cache_enabled=self.settings.gdc_cache_enabled)
        )
        self._event(run_id, "RUN_STARTED", "run:started",
                    ("Live bounded GDC sweep started." if self.run_mode == "LIVE"
                     else "Synthetic fixture research run started."), stage=None,
data={"mode": self.run_mode, "research_spec": spec_payload, "caps": {
                        "max_requests": caps.max_requests, "max_bytes": caps.max_bytes,
                        "per_response_bytes": caps.per_response_bytes,
                        "max_case_ids": caps.max_case_ids, "max_gene_ids": caps.max_gene_ids,
                        "timeout_seconds": caps.timeout_seconds,
                        "cache_enabled": self.settings.gdc_cache_enabled,
                        "jev_max_states": self.settings.jev_max_states,
                    },
                    "deep_selection": self.deep_selection,
                    "deep_selections": list(self._deep_selections()),
                    "deep_action_id": self.deep_action_id,
                    "deep_followup_authorized": self.deep_followup_authorized,
                    "deep_hypotheses_requested": self.deep_hypotheses_requested,
                    "llm_generation": {
                        "enabled": self.llm_generator is not None,
                        "generator": str(getattr(self.llm_generator, "name", "deterministic-template-v1"))
                        if self.llm_generator is not None else "deterministic-template-v1",
                        "model": str(getattr(self.llm_generator, "model", None))
                        if self.llm_generator is not None else None,
                        "credential": "environment-only; never recorded",
                    },
                    "deep_selection_rule": (
                        "An operator names one promoted candidate explicitly; wide admission never "
                        "dispatches a follow-up on its own."
                    ) if self.deep_selection else None,
                    "deep_dispatch_rule": (
                        "One recorded FOLLOW_UP may be dispatched for the named candidate on explicit "
                        "operator authorization, inside the existing follow-up and revision caps."
                    ) if self.deep_followup_authorized else None})
        wide_result: dict[str, Any] | None = None
        try:
            inventory = self._stage(run_id, "INVENTORY", lambda: self._inventory(run_id, transport))
            selection = self._stage(run_id, "GDC_FAST_SEARCH", lambda: self._fast_search(run_id, transport, inventory))
            states = self._stage(
                run_id, "STATE_GENERATION",
                lambda: self._generate_states(run_id, transport, inventory, selection),
            )
            coverage = "COMPLETE_FOR_SCOPE"
            if any(state.state.quality.acquisition is not Acquisition.COMPLETE for state in states):
                coverage = "PARTIAL"
            if self.jev_service is not None:
                jev_service = self.jev_service
                wide_result = self._stage(
                    run_id, "JEV_WIDE",
                    lambda: run_wide_evaluation(
                        run_id=run_id, states=states, coverage=coverage,
                        repository=self.repository, jev_service=jev_service,
                        emit=self._event, publish_json=self._publish_json,
                        max_states=self.settings.jev_max_states,
                    ),
                )
        except (TransportError, ParserError, ScienceError, LiveRunError) as exc:
            code = getattr(exc, "code", type(exc).__name__)
            self._event(
                run_id, "RUN_FAILED", "run:failed", f"Live sweep failed: {code}.",
                level="error", data={"status": "FAILED", "reason_code": str(code), "coverage": "PARTIAL",
                                     "detail": str(exc)},
            )
            return run_id
        except Exception as exc:  # noqa: BLE001 - an unexpected defect must not leave a run RUNNING
            self._event(
                run_id, "RUN_FAILED", "run:failed", f"Live sweep failed unexpectedly: {type(exc).__name__}.",
                level="error", data={"status": "FAILED", "reason_code": "UNEXPECTED_ERROR",
                                     "coverage": "PARTIAL", "detail": str(exc)},
            )
            raise
        totals = self.repository.gdc_run_totals(run_id)
        deep_summary = None
        if self._deep_selections() and wide_result is not None:
            deep_summary = self._deep_candidates(run_id, wide_result, transport=transport)
        completion_data = {
            "status": "COMPLETED", "reason_code": "BOUNDED_SWEEP_COMPLETE", "coverage": coverage,
            "states": len(states), "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
            "gdc_cache_hits": totals["cache_hits"],
            "run_scope": "CANDIDATE_QUEUE_EXHAUSTED",
        }
        if deep_summary is not None:
            completion_data["deep"] = deep_summary
            completion_data["candidate_queue_exhausted"] = deep_summary["candidate_queue_exhausted"]
            completion_data["run_scope"] = (
                "CANDIDATE_QUEUE_EXHAUSTED" if deep_summary["candidate_queue_exhausted"]
                else "CANDIDATES_INCOMPLETE")
        self._event(
            run_id, "RUN_COMPLETED", "run:completed",
            (f"Live bounded sweep completed with {len(states)} statistical states."
             if self.run_mode == "LIVE"
             else f"Synthetic fixture run completed with {len(states)} statistical states."),
            data=completion_data,
        )
        return run_id

    # -------------------------------------------------------------- deep slice

    def _deep_selections(self) -> tuple[str, ...]:
        selections: list[str] = []
        for raw in (self.deep_selections or ((self.deep_selection,) if self.deep_selection else ())):
            selection = (raw or "").strip()
            if selection and selection not in selections:
                selections.append(selection)
        return tuple(selections)

    def _resolve_deep_candidate(self, run_id: str, promoted: list[dict[str, Any]],
                                selection: str) -> dict[str, Any] | None:
        rows = {row["candidate_id"]: row for row in self.repository.list_table("candidates", run_id)}
        for promotion in promoted:
            row = rows.get(promotion["candidate_id"])
            if row is None:
                continue
            entity = row["entity"]
            if selection == entity.get("gene_symbol"):
                return {**row, "entity": entity}
            if selection == f"slot:{promotion['slot']}":
                return {**row, "entity": entity}
        return None

    def _deep_state_index(self, run_id: str) -> dict[str, dict[str, Any]]:
        evaluations = {
            row["input_ref_id"]: row for row in self.repository.page_child(
                "jev_evaluations", run_id, 1000, None, {"purpose": "WIDE"},
            )["items"]
        }
        index: dict[str, dict[str, Any]] = {}
        for row in self.repository.list_table("statistical_states", run_id, limit=1000):
            evaluation = evaluations.get(row["state_id"])
            summary = row["summary"] if isinstance(row["summary"], dict) else {}
            index[row["state_id"]] = {
                "state_id": row["state_id"], "state_hash": row["state_hash"],
                "entity": summary.get("entity") or {}, "disposition": row["disposition"],
                "evaluation_id": evaluation["evaluation_id"] if evaluation else None,
                "evaluation_error": (evaluation["vector"].get("error") if evaluation else None),
            }
        return index

    def _operator_selection_target(self, selection: str,
                                   index: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
        if selection.startswith("slot:"):
            return None, "only a policy-promoted candidate can be named by slot"
        if selection.startswith("state:"):
            state_id = selection[len("state:"):]
            if state_id not in index:
                return None, "no statistical state in this run has that id"
            return state_id, None
        symbol = selection[len("gene:"):] if selection.startswith("gene:") else selection
        matches = [state_id for state_id, entry in index.items()
                   if (entry["entity"] or {}).get("gene_symbol") == symbol]
        if not matches:
            return None, "no statistical state in this run has that gene symbol"
        if len(matches) > 1:
            return None, "the gene symbol is ambiguous in this run; use state:<state_id>"
        return matches[0], None

    def _operator_candidate(self, run_id: str, state_id: str, selection: str) -> dict[str, Any] | None:
        """Create one explicitly operator-selected candidate for deep analysis.

        Wide admission never selects it: the operator named it, the recorded rule says
        so, and the promotion cap still applies.
        """
        index = self._deep_state_index(run_id)
        entry = index.get(state_id)
        if entry is None:
            return None
        existing = self.repository.list_table("candidates", run_id)
        slot = len(existing) + 1
        if slot > PROMOTION_LIMIT:
            self._event(
                run_id, "DEEP_SELECTION_UNAVAILABLE", f"deep:selection:cap:{selection}",
                f"Explicit deep selection was refused: the promotion cap of {PROMOTION_LIMIT} is reached.",
                stage="DEEP_ANALYSIS", level="warning",
                data={"selection": selection, "reason_code": "PROMOTION_LIMIT_REACHED",
                      "detail": f"{len(existing)} candidate(s) already exist in this run"},
            )
            return None
        if not entry["evaluation_id"] or entry["evaluation_error"] is not None:
            self._event(
                run_id, "DEEP_SELECTION_UNAVAILABLE", f"deep:selection:not-evaluated:{selection}",
                "Explicit deep selection was refused: the named state has no successful wide evaluation.",
                stage="DEEP_ANALYSIS", level="warning",
                data={"selection": selection, "source_state_id": state_id,
                      "reason_code": "STATE_NOT_EVALUATED",
                      "detail": "operator selection requires a state with a successful wide Jev evaluation"},
            )
            return None
        entity = entry["entity"]
        candidate_id = stable_id(run_id, f"operator-candidate:{state_id}")
        now = utc_now()
        self._event(
            run_id, "CANDIDATE_PROMOTED", f"candidate:{candidate_id}:operator-promoted",
            f"Operator-approved candidate {entity.get('gene_symbol')} created for deep analysis.",
            stage="DEEP_ANALYSIS", candidate_id=candidate_id,
            data={
                "candidate_id": candidate_id, "source_state_id": state_id,
                "evaluation_id": entry["evaluation_id"], "promotion_slot": slot,
                "policy_version": "operator-selection-v1", "reason": "OPERATOR_APPROVED_SELECTION",
                "selection": selection,
                "selection_rule": (
                    "An operator named this candidate explicitly; wide admission did not select it and "
                    "no follow-up is dispatched automatically."
                ),
                "auto_dispatched": False,
            },
            registrations=[self.repository.candidate_registration(
                candidate_id=candidate_id, run_id=run_id, promotion_slot=slot,
                status="WIDE_EVALUATED", current_stage="DEEP_ANALYSIS", source_state_id=state_id,
                entity_json=canonical_json(entity).decode(),
                summary_json=canonical_json({
                    "promotion_reason": f"OPERATOR_APPROVED_SELECTION:{selection}",
                    "wide_evaluation_id": entry["evaluation_id"], "selection": selection,
                    "policy_version": "operator-selection-v1", "auto_dispatched": False,
                }).decode(),
                created_at=now, updated_at=now,
            )],
        )
        return {"candidate_id": candidate_id, "entity": entity, "promotion_slot": slot,
                "source_state_id": state_id}

    def _read_artifact(self, artifact_id: str) -> bytes | None:
        metadata = self.repository.artifact(artifact_id)
        if metadata is None:
            return None
        return self.artifacts.read(metadata["relative_path"])

    def _resolve_selection(self, run_id: str, promoted: list[dict[str, Any]],
                           selection: str) -> dict[str, Any] | None:
        candidate = self._resolve_deep_candidate(run_id, promoted, selection)
        if candidate is not None:
            return candidate
        refusal_emitted = False
        index = self._deep_state_index(run_id)
        state_id, detail = self._operator_selection_target(selection, index)
        if state_id is not None:
            candidate = self._operator_candidate(run_id, state_id, selection)
            refusal_emitted = candidate is None
        elif detail is not None:
            self._event(
                run_id, "DEEP_SELECTION_UNAVAILABLE", f"deep:selection:unavailable:{selection}",
                f"Explicit deep selection {selection!r} matched no candidate: {detail}.",
                stage="DEEP_ANALYSIS", level="warning",
                data={"selection": selection, "promoted_candidates": len(promoted),
                      "reason_code": "DEEP_SELECTION_UNAVAILABLE", "detail": detail},
            )
            refusal_emitted = True
        if candidate is None and not refusal_emitted:
            self._event(
                run_id, "DEEP_SELECTION_UNAVAILABLE", f"deep:selection:unavailable:{selection}",
                f"Explicit deep selection {selection!r} matched no promoted candidate.",
                stage="DEEP_ANALYSIS", level="warning",
                data={"selection": selection, "promoted_candidates": len(promoted),
                      "reason_code": "DEEP_SELECTION_UNAVAILABLE",
                      "detail": "the selection must name a gene symbol, slot:N or state:<state_id> "
                                "of a wide-evaluated state in this run"},
            )
        return candidate

    def _deep_candidates(self, run_id: str, wide_result: dict[str, Any],
                         transport: AcquisitionTransport | None = None) -> dict[str, Any]:
        """Investigate each explicitly selected candidate with the bounded arc."""
        promoted = wide_result.get("promoted", [])
        selections = self._deep_selections()
        seen: set[str] = set()
        for raw in (self.deep_selections or ((self.deep_selection,) if self.deep_selection else ())):
            selection = (raw or "").strip()
            if not selection:
                continue
            if selection in seen:
                self._event(
                    run_id, "DEEP_SELECTION_UNAVAILABLE", f"deep:selection:duplicate:{selection}",
                    f"Duplicate deep selection {selection!r} was ignored; each candidate is investigated once.",
                    stage="DEEP_ANALYSIS", level="warning",
                    data={"selection": selection, "reason_code": "DUPLICATE_SELECTION",
                          "detail": "the selection list is de-duplicated in order"},
                )
            seen.add(selection)
        summaries: list[dict[str, Any]] = []
        for selection in selections:
            candidate = self._resolve_selection(run_id, promoted, selection)
            if candidate is None:
                summaries.append({
                    "selection": selection, "candidate_id": None, "status": "DEEP_SELECTION_UNAVAILABLE",
                    "investigation_status": "DEEP_SELECTION_UNAVAILABLE", "candidate_status": None,
                    "final_move": None, "stop_reason": "DEEP_SELECTION_UNAVAILABLE", "error_code": None,
                    "first_step": {}, "steps": [], "decisions": [], "hypothesis": None,
                    "dossier": None, "final_result": None,
                })
                continue
            investigation = run_candidate_investigation(
                run_id=run_id, candidate=candidate, selection=selection,
                repository=self.repository, artifacts=self.artifacts, emit=self._event,
                publish_json=self._publish_json, read_artifact=self._read_artifact,
                stage=lambda name, function: self._stage(run_id, name, function),
                jev_service=self.jev_service, requested_action_id=self.deep_action_id,
                authorize_iteration=self.deep_followup_authorized,
                hypotheses_requested=self.deep_hypotheses_requested,
                llm_generator=self.llm_generator,
                transport=transport,
                mode=self.run_mode,
            )
            summaries.append(investigation.summary())
        completed = [summary for summary in summaries
                     if summary.get("candidate_status") == "CANDIDATE_COMPLETE"]
        return {"selections": list(selections), "candidate_count": len(summaries),
                "candidates": summaries,
                "completed_count": len(completed),
                "candidate_queue_exhausted": len(completed) == len(summaries) and bool(summaries),
                "candidates_completed": [
                    {"candidate_id": summary["candidate_id"],
                     "final_result_id": (summary.get("final_result") or {}).get("final_result_id"),
                     "dossier_id": (summary.get("dossier") or {}).get("dossier_id"),
                     "candidate_status": summary.get("candidate_status"),
                     "comparison_status": (summary.get("final_result") or {}).get("comparison_status")}
                    for summary in summaries
                ]}

    # ----------------------------------------------------------------- inventory

    def _inventory(self, run_id: str, transport: AcquisitionTransport) -> Inventory:
        cohort = self.research_spec.cohort
        selection_rule = self.research_spec.cohort_selection_rule()
        self._event(run_id, "INVENTORY_STARTED", "inventory:started", "Reading bounded GDC inventory.",
                    stage="INVENTORY")
        status_response = transport.request(status_request())
        status = parse_status(status_response.body, self._meta(status_response, None))
        release = status.data_release
        project_response = transport.request(cohort_project_request(cohort.project_id))
        projects = parse_projects(project_response.body, self._meta(project_response, release))
        selected = [project for project in projects if project.project_id == cohort.project_id]
        if not selected:
            raise LiveRunError(
                "COHORT_PROJECT_NOT_FOUND",
                f"cohort project {cohort.project_id} not present in the open GDC project inventory",
            )
        scope_hash = digest({
            "research_spec": self.research_spec.as_dict(), "selection_rule": selection_rule,
            "project_id": selected[0].project_id, "case_count": selected[0].case_count,
        })
        inventory_payload = {
            "release": release, "release_commit": status.commit, "release_tag": status.tag,
            "research_spec": self.research_spec.as_dict(), "domain": cohort.domain,
            "cohort": cohort.cohort_id, "project_id": cohort.project_id,
            "projects_total": len(projects),
            "selected": [
                {"project_id": project.project_id, "case_count": project.case_count,
                 "program": project.program_name, "primary_site": project.primary_site,
                 "disease_type": project.disease_type, "data_categories": project.data_categories}
                for project in selected
            ],
            "selection_rule": selection_rule, "scope_hash": scope_hash,
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/inventory/projects.json", inventory_payload, "gdc-inventory")
        self.repository.register_artifact(artifact, run_id)
        sources = [
            self._source(status_response, release=release),
            self._source(project_response, release=release),
        ]
        warnings = status.warnings + response_warnings(project_response.body, self._meta(project_response, release))
        self._event(
            run_id, "PROJECT_SCOPE_SELECTED", "inventory:scope",
            f"Selected cohort {cohort.cohort_id} ({cohort.domain}); {len(projects)} project record(s) examined.",
            stage="INVENTORY",
            data={"spec_id": self.research_spec.spec_id, "domain": cohort.domain,
                  "cohort": cohort.cohort_id, "project_id": cohort.project_id,
                  "acquisition": self.research_spec.as_dict()["acquisition"],
                  "selected_project_ids": [project.project_id for project in selected],
                  "scope_hash": scope_hash, "gdc_release": release,
                  "projects_examined": len(projects), "inventory_artifact_id": artifact.artifact_id},
            artifact_refs=[artifact.ref()],
        )
        self._event(
            run_id, "INVENTORY_COMPLETED", "inventory:completed",
            f"Inventory completed; cohort {cohort.cohort_id} selected.",
            stage="INVENTORY", data={"projects": len(selected), "projects_total": len(projects)},
            artifact_refs=[artifact.ref()],
        )
        return Inventory(release=release, release_commit=status.commit, projects=projects,
                         selected=selected, inventory_artifact=artifact, sources=tuple(sources),
                         warnings=warnings, scope_hash=scope_hash)

    # --------------------------------------------------------------- fast search

    def _fast_search(self, run_id: str, transport: AcquisitionTransport, inventory: Inventory) -> Selection:
        acquisition = self.research_spec.acquisition
        cohort = self.research_spec.cohort
        gene_selection_rule = self.research_spec.gene_selection_rule()
        self._event(run_id, "WIDE_SCAN_STARTED", "wide:started",
                    "Mutation discovery and count lane started.", stage="GDC_FAST_SEARCH")
        sources = list(inventory.sources)
        warnings = list(inventory.warnings)
        discovery_by_project: dict[str, dict[str, DiscoveryHit]] = {}
        ranked_genes: list[str] = []
        for project in inventory.selected:
            response = transport.request(
                top_mutated_genes_request(project.project_id, acquisition.discovery_gene_limit)
            )
            hits = parse_top_mutated_genes(response.body, self._meta(response, inventory.release))
            discovery_by_project[project.project_id] = {hit.gene_id: hit for hit in hits}
            ranked_genes = [hit.gene_id for hit in sorted(hits, key=lambda hit: hit.rank)]
            sources.append(self._source(response, release=inventory.release))
        count_genes = ranked_genes[:acquisition.count_gene_limit]
        if not count_genes:
            raise LiveRunError("NO_DISCOVERED_GENES", f"provider discovery returned no genes for {cohort.project_id}")
        scan_counts: dict[str, ScannedMutationCounts] = {}
        for project in inventory.selected:
            scan = acquire_project_mutation_occurrence_scan(
                transport, project.project_id,
                self.research_spec.discovery.occurrence_scan_page_size, inventory.release)
            scan_artifact, scan_source = publish_occurrence_scan(
                self.artifacts, self.repository, run_id, scan,
                relative_path=f"runs/{run_id}/selection/occurrence-scan-{project.project_id}.json")
            self._event(
                run_id, "DISCOVERY_OCCURRENCE_SCAN_ACQUIRED", f"scan:{project.project_id}",
                "Complete released-occurrence scan acquired for the examined cohort.",
                stage="GDC_FAST_SEARCH",
                data={"project_id": project.project_id, "pages": scan.page_count,
                      "total_occurrences": scan.total_occurrences,
                      "distinct_cases_total": sum(scan.distinct_cases_per_gene.values()),
                      "release": inventory.release},
                artifact_refs=[scan_artifact.ref()],
            )
            scan_counts[project.project_id] = ScannedMutationCounts(
                project.project_id, scan.distinct_cases_per_gene, scan_source)
            sources.append(scan_source)
            warnings.extend(scan.warnings)
        coverage, coverage_source = acquire_project_coverage(transport, inventory.release)
        sources.append(coverage_source)
        scope_ids = [project.project_id for project in inventory.selected]
        totals = {
            gene_id: sum(scan_counts[project_id].distinct_cases_per_gene.get(gene_id, 0)
                         for project_id in scope_ids)
            for gene_id in count_genes
        }
        selected_gene_ids = ranked_genes[:acquisition.candidate_gene_limit]
        if not selected_gene_ids:
            raise LiveRunError("NO_DISCOVERED_GENES", "gene selection produced an empty set")
        genes_response = transport.request(genes_request(selected_gene_ids))
        gene_records = parse_genes(genes_response.body, self._meta(genes_response, inventory.release))
        sources.append(self._source(genes_response, release=inventory.release))
        if len(gene_records) != len(selected_gene_ids):
            raise LiveRunError("GENE_IDENTITY_INCOMPLETE",
                               f"requested {len(selected_gene_ids)} genes, received {len(gene_records)}")
        genes = {record.gene_id: record for record in gene_records}
        selection_payload = {
            "selection_rule": gene_selection_rule,
            "spec_id": self.research_spec.spec_id,
            "domain": cohort.domain,
            "cohort": cohort.cohort_id,
            "project_id": cohort.project_id,
            "acquisition": self.research_spec.as_dict()["acquisition"],
            "provider_ranked_genes": ranked_genes,
            "counted_genes": count_genes,
            "affected_totals_in_scope": totals,
            "affected_count_method": "MUTATION_AFFECTED_CASE_COUNT_V2",
            "affected_count_note": (
                "Totals are distinct released cases per gene over the complete /ssm_occurrences "
                "scan; a gene absent from a complete scan is an observed zero."
            ),
            "selected_gene_ids": selected_gene_ids,
            "provider_ranking_note": (
                "Discovery uses the provider top-mutated ranking; _score is provider-internal selection "
                "metadata and is never treated as a mutation count or effect size."
            ),
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/selection/examined_genes.json",
                                     selection_payload, "gdc-gene-selection")
        self.repository.register_artifact(artifact, run_id)
        examined_genes_hash = digest(selection_payload)
        return Selection(
            discovery_by_project=discovery_by_project, count_genes=count_genes,
            selected_gene_ids=selected_gene_ids, genes=genes, scan_counts=scan_counts,
            coverage=coverage, sources=tuple(sources), warnings=warnings, artifact=artifact,
            examined_genes_hash=examined_genes_hash,
        )

    # ---------------------------------------------------------- state generation

    def _acquire_project_frame(self, run_id: str, transport: AcquisitionTransport, inventory: Inventory,
                               selection: Selection, project: ProjectRecord,
                               ) -> tuple[ProjectFrame, tuple[OperationalSource, ...], list[str]]:
        return acquire_project_frame(transport, project, self.research_spec.acquisition, inventory.release,
                                     selection.selected_gene_ids,
                                     selection.discovery_by_project.get(project.project_id, {}))

    def _generate_states(self, run_id: str, transport: AcquisitionTransport, inventory: Inventory,
                         selection: Selection) -> list[StateRecord]:
        frames: list[ProjectFrame] = []
        sources = list(selection.sources)
        warnings = list(selection.warnings)
        for project in inventory.selected:
            frame, frame_sources, frame_warnings = self._acquire_project_frame(
                run_id, transport, inventory, selection, project,
            )
            sources.extend(frame_sources)
            warnings.extend(frame_warnings)
            frames.append(frame)
        states: list[StateRecord] = []
        cohort = self.research_spec.cohort
        gene_selection_rule = self.research_spec.gene_selection_rule()
        for rank, gene_id in enumerate(selection.selected_gene_ids, start=1):
            gene = selection.genes[gene_id]
            state_id = str(uuid4())
            discovery_meta = {
                "method_id": "MUTATION_DISCOVERY_V1",
                "examined_genes_ref": selection.artifact.artifact_id,
                "examined_genes_hash": selection.examined_genes_hash,
                "examined_genes_n": len(selection.selected_gene_ids),
                "rank_in_lane": rank,
                "observed_in_project_count": sum(1 for frame in frames if gene_id in frame.discovery_hits),
                "ranking_rule": gene_selection_rule,
                "selected_gene_ids": tuple(selection.selected_gene_ids),
            }
            state = compute_statistical_state(
                gene=gene, frames=frames,
                scan_counts_by_project=selection.scan_counts, coverage=selection.coverage,
                sources=tuple(sources),
                warnings=warnings,
                scope_meta={
                    "gdc_release": inventory.release, "examined_case_frame": "ALL_CASES_PAGINATED",
                    "scope_hash": inventory.scope_hash, "spec_id": self.research_spec.spec_id,
                    "research_spec": self.research_spec.as_dict(), "domain": cohort.domain,
                    "cohort": cohort.cohort_id, "project_id": cohort.project_id,
                    "cohort_selection_rule": self.research_spec.cohort_selection_rule(),
                    "gene_selection_rule": gene_selection_rule,
                },
                discovery_meta=discovery_meta,
            )
            state_hash = state_identity(state)
            artifact = self._publish_json(
                run_id, f"runs/{run_id}/statistical_states/{state_id}.json", write_state(state),
                "statistical-state",
            )
            summary = _state_summary(state, artifact, self.run_mode)
            registrations = [
                self.repository.artifact_registration(artifact, run_id),
                self.repository.state_registration(
                    state_id=state_id, run_id=run_id, state_hash=state_hash,
                    artifact_id=artifact.artifact_id, disposition="GENERATED",
                    summary_json=canonical_json(summary).decode(), created_at=utc_now(),
                ),
            ]
            self._event(
                run_id, "STATISTICAL_STATE_CREATED", f"state:{state_id}",
                (f"Real StatisticalState for {gene.symbol} generated from open GDC evidence."
                 if self.run_mode == "LIVE"
                 else f"Synthetic StatisticalState for {gene.symbol} generated from labelled fixtures."),
                stage="STATE_GENERATION",
                data={"state_id": state_id, "state_hash": state_hash, "gene_id": gene.gene_id,
                      "gene_symbol": gene.symbol, "mode": "LIVE"},
                artifact_refs=[artifact.ref()], registrations=registrations,
            )
            states.append(StateRecord(state_id, state_hash, state))
        self._event(
            run_id, "WIDE_SCAN_COMPLETED", "wide:completed",
            f"Wide evidence scan completed with {len(states)} states.",
            stage="STATE_GENERATION",
            data={"valid_count": len(states), "selected_count": 0, "selection_rule": WIDE_SCAN_RULE},
        )
        return states
