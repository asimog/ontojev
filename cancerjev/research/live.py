"""Live Phase 2/3 orchestrator: bounded open-access GDC sweep to real states.

Sequence: INVENTORY → GDC_FAST_SEARCH (mutation lane) → STATE_GENERATION
(mutation + expression + coverage) → optional JEV_WIDE (Phase 3) → terminal run
event. Every request goes through the sole transport; every measured number
comes from deterministic methods; Jev never runs during a Phase 2 sweep.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from cancerjev.config import Settings
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.gdc.endpoints import (
    cases_request,
    cohort_project_request,
    expression_availability_request,
    expression_gene_selection_request,
    expression_values_request,
    files_expression_request,
    gene_case_counts_request,
    genes_request,
    mutated_cases_count_request,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    ParserError,
    ProjectCoverage,
    ProjectRecord,
    ProviderSelection,
    ResponseMeta,
    parse_cases,
    parse_expression_availability,
    parse_expression_values,
    parse_files_provenance,
    parse_gene_case_counts,
    parse_gene_selection,
    parse_genes,
    parse_mutated_cases_count,
    parse_projects,
    parse_status,
    parse_top_mutated_genes,
    response_warnings,
)
from cancerjev.gdc.transport import BudgetCaps, GDCResponse, GDCTransport, RunBudget, TransportError
from cancerjev.research.wide import run_wide_evaluation
from cancerjev.science.methods import ProjectFrame, ScienceError, build_statistical_state
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

DOMAIN = "lung cancer"
COHORT_PROJECT_ID = "TCGA-LUAD"
COHORT_SELECTION_RULE = (
    "single explicit cohort: domain=lung cancer, cohort=TCGA-LUAD; the cohort is selected by exact "
    "project_id from the open GDC project inventory; no case-count window, no cross-project pooling, "
    "and no configurable multi-cancer framework"
)
GENE_SELECTION_RULE = (
    "genes discovered from the provider top-mutated ranking for TCGA-LUAD (size 20); selection takes the "
    "top 10 genes by provider rank, skipping duplicates; _score is provider selection metadata and is "
    "never a mutation count or effect size"
)
DISCOVERY_GENES_PER_PROJECT = 20
COUNT_GENE_LIMIT = 100
CANDIDATE_GENE_LIMIT = 10
WIDE_SCAN_RULE = (
    "states_valid = states generated; states_selected = states admitted by the active ranking policy"
)


class LiveRunError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Inventory:
    release: str | None
    release_commit: str | None
    projects: list[ProjectRecord]
    selected: list[ProjectRecord]
    inventory_artifact: Any
    sources: list[dict[str, Any]]
    warnings: list[str]
    scope_hash: str


@dataclass
class Selection:
    discovery_by_project: dict[str, dict[str, Any]]
    count_genes: list[str]
    selected_gene_ids: list[str]
    genes: dict[str, Any]
    counts: GeneCaseCounts
    coverage: ProjectCoverage
    sources: list[dict[str, Any]]
    warnings: list[str]
    artifact: Any
    examined_genes_hash: str


@dataclass
class LiveOrchestrator:
    settings: Settings
    repository: Repository
    artifacts: ArtifactStore
    render: Callable[..., Any] = field(default=lambda *args, **kwargs: None)
    jev_service: Any = None
    worker_id: str = "live-worker"
    transport_factory: Callable[..., Any] | None = None

    # ------------------------------------------------------------- event helpers

    def _event(self, run_id: str, event_type: str, key: str, message: str, *, stage: str | None = None,
               data: dict[str, Any] | None = None, level: str = "info", candidate_id: str | None = None,
               artifact_refs: list[dict[str, Any]] | None = None,
               registrations: list[tuple[str, tuple[Any, ...]]] | None = None) -> dict[str, Any]:
        event = self.repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, stage=stage,
            data=data or {}, level=level, candidate_id=candidate_id, artifact_refs=artifact_refs,
            registrations=registrations,
        )
        self.render(event)
        return event

    def _stage(self, run_id: str, stage: str, function: Callable[[], Any]) -> Any:
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

    def _publish_json(self, run_id: str, relative_path: str, payload: Any, purpose: str) -> Any:
        content = canonical_json(payload) if not isinstance(payload, bytes) else payload
        return self.artifacts.publish(relative_path, content, "application/json", purpose)

    def _meta(self, response: GDCResponse, release: str | None) -> ResponseMeta:
        return ResponseMeta(
            endpoint=response.endpoint, method=response.method, request_hash=response.request_hash,
            response_sha256=response.body_sha256, artifact_id=response.artifact.artifact_id,
            retrieved_at=response.retrieved_at, source_release=release, completeness=response.completeness,
        )

    def _source(self, response: GDCResponse, *, locator: str, release: str | None) -> dict[str, Any]:
        return {
            "request_id": None,
            "response_artifact_id": response.artifact.artifact_id,
            "response_sha256": response.body_sha256,
            "endpoint": response.endpoint,
            "normalized_request_hash": response.request_hash,
            "retrieved_at": response.retrieved_at,
            "source_release": release,
            "release_status": "KNOWN" if release else "UNVERIFIED",
            "parser_version": PARSER_VERSION,
            "json_pointer_or_table_locator": locator,
            "completeness": response.completeness,
        }

    # --------------------------------------------------------------------- run

    def run(self) -> str:
        caps = BudgetCaps(
            max_requests=self.settings.gdc_max_requests,
            max_bytes=self.settings.gdc_max_bytes,
            per_response_bytes=self.settings.gdc_per_response_bytes,
            timeout_seconds=self.settings.gdc_timeout_seconds,
        )
        budget = RunBudget(caps=caps)
        run_id = self.repository.create_run(
            self.worker_id, mode="LIVE", fixture_id=None, fixture_version=None,
            scope={"purpose": "LIVE_SWEEP", "domain": DOMAIN, "cohort": COHORT_PROJECT_ID,
                   "selection_rule": COHORT_SELECTION_RULE},
        )

        def emit(event_type: str, key: str, message: str, **kwargs: Any) -> Any:
            return self._event(run_id, event_type, key, message, **kwargs)

        transport = (
            self.transport_factory(self.repository, self.artifacts, budget, run_id, emit)
            if self.transport_factory is not None
            else GDCTransport(self.repository, self.artifacts, budget, run_id, emit,
                              cache_enabled=self.settings.gdc_cache_enabled)
        )
        self._event(run_id, "RUN_STARTED", "run:started", "Live bounded GDC sweep started.", stage=None,
                    data={"mode": "LIVE", "caps": {
                        "max_requests": caps.max_requests, "max_bytes": caps.max_bytes,
                        "per_response_bytes": caps.per_response_bytes,
                        "max_case_ids": caps.max_case_ids, "max_gene_ids": caps.max_gene_ids,
                    }})
        try:
            inventory = self._stage(run_id, "INVENTORY", lambda: self._inventory(run_id, transport))
            selection = self._stage(run_id, "GDC_FAST_SEARCH", lambda: self._fast_search(run_id, transport, inventory))
            states = self._stage(
                run_id, "STATE_GENERATION",
                lambda: self._generate_states(run_id, transport, inventory, selection),
            )
            coverage = "COMPLETE_FOR_SCOPE"
            if any(state["quality"]["completeness"] != "COMPLETE" for state in states):
                coverage = "PARTIAL"
            if self.jev_service is not None:
                self._stage(
                    run_id, "JEV_WIDE",
                    lambda: run_wide_evaluation(
                        run_id=run_id, states=states, coverage=coverage,
                        repository=self.repository, jev_service=self.jev_service,
                        emit=self._event, publish_json=self._publish_json,
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
        self._event(
            run_id, "RUN_COMPLETED", "run:completed",
            f"Live bounded sweep completed with {len(states)} statistical states.",
            data={
                "status": "COMPLETED", "reason_code": "BOUNDED_SWEEP_COMPLETE", "coverage": coverage,
                "states": len(states), "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
                "gdc_cache_hits": totals["cache_hits"],
            },
        )
        return run_id

    # ----------------------------------------------------------------- inventory

    def _inventory(self, run_id: str, transport: GDCTransport) -> Inventory:
        self._event(run_id, "INVENTORY_STARTED", "inventory:started", "Reading bounded GDC inventory.",
                    stage="INVENTORY")
        status_response = transport.request(status_request())
        status = parse_status(status_response.body, self._meta(status_response, None))
        release = status.data_release
        project_response = transport.request(cohort_project_request(COHORT_PROJECT_ID))
        projects = parse_projects(project_response.body, self._meta(project_response, release))
        selected = [project for project in projects if project.project_id == COHORT_PROJECT_ID]
        if not selected:
            raise LiveRunError(
                "COHORT_PROJECT_NOT_FOUND",
                f"cohort project {COHORT_PROJECT_ID} not present in the open GDC project inventory",
            )
        scope_hash = hashlib.sha256(canonical_json({
            "rule": COHORT_SELECTION_RULE, "domain": DOMAIN, "cohort": COHORT_PROJECT_ID,
            "project_id": selected[0].project_id, "case_count": selected[0].case_count,
        })).hexdigest()
        inventory_payload = {
            "release": release, "release_commit": status.commit, "release_tag": status.tag,
            "domain": DOMAIN, "cohort": COHORT_PROJECT_ID, "projects_total": len(projects),
            "selected": [
                {"project_id": project.project_id, "case_count": project.case_count,
                 "program": project.program_name, "primary_site": project.primary_site,
                 "disease_type": project.disease_type, "data_categories": project.data_categories}
                for project in selected
            ],
            "selection_rule": COHORT_SELECTION_RULE, "scope_hash": scope_hash,
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/inventory/projects.json", inventory_payload, "gdc-inventory")
        sources = [
            self._source(status_response, locator="/status", release=release),
            self._source(project_response, locator="/projects", release=release),
        ]
        warnings = status.warnings + response_warnings(project_response.body, self._meta(project_response, release))
        self._event(
            run_id, "PROJECT_SCOPE_SELECTED", "inventory:scope",
            f"Selected cohort {COHORT_PROJECT_ID} ({DOMAIN}); {len(projects)} project record(s) examined.",
            stage="INVENTORY",
            data={"domain": DOMAIN, "cohort": COHORT_PROJECT_ID,
                  "selected_project_ids": [project.project_id for project in selected],
                  "scope_hash": scope_hash, "gdc_release": release,
                  "projects_examined": len(projects), "inventory_artifact_id": artifact.artifact_id},
            artifact_refs=[artifact.ref()],
        )
        self._event(
            run_id, "INVENTORY_COMPLETED", "inventory:completed",
            f"Inventory completed; cohort {COHORT_PROJECT_ID} selected.",
            stage="INVENTORY", data={"projects": len(selected), "projects_total": len(projects)},
            artifact_refs=[artifact.ref()],
        )
        return Inventory(release=release, release_commit=status.commit, projects=projects,
                         selected=selected, inventory_artifact=artifact, sources=sources,
                         warnings=warnings, scope_hash=scope_hash)

    # --------------------------------------------------------------- fast search

    def _fast_search(self, run_id: str, transport: GDCTransport, inventory: Inventory) -> Selection:
        self._event(run_id, "WIDE_SCAN_STARTED", "wide:started",
                    "Mutation discovery and count lane started.", stage="GDC_FAST_SEARCH")
        sources = list(inventory.sources)
        warnings = list(inventory.warnings)
        discovery_by_project: dict[str, dict[str, Any]] = {}
        ranked_genes: list[str] = []
        for project in inventory.selected:
            response = transport.request(top_mutated_genes_request(project.project_id, DISCOVERY_GENES_PER_PROJECT))
            hits = parse_top_mutated_genes(response.body, self._meta(response, inventory.release))
            discovery_by_project[project.project_id] = {hit.gene_id: hit for hit in hits}
            ranked_genes = [hit.gene_id for hit in sorted(hits, key=lambda hit: hit.rank)]
            sources.append(self._source(response, locator=f"/analysis/top_mutated_genes_by_project[{project.project_id}]",
                                        release=inventory.release))
        count_genes = ranked_genes[:COUNT_GENE_LIMIT]
        if not count_genes:
            raise LiveRunError("NO_DISCOVERED_GENES", f"provider discovery returned no genes for {COHORT_PROJECT_ID}")
        counts_response = transport.request(gene_case_counts_request(count_genes))
        counts = parse_gene_case_counts(counts_response.body, self._meta(counts_response, inventory.release))
        sources.append(self._source(counts_response, locator="/analysis/top_cases_counts_by_genes",
                                    release=inventory.release))
        warnings += counts.warnings
        coverage_response = transport.request(mutated_cases_count_request())
        coverage = parse_mutated_cases_count(coverage_response.body, self._meta(coverage_response, inventory.release))
        sources.append(self._source(coverage_response, locator="/analysis/mutated_cases_count_by_project",
                                    release=inventory.release))
        warnings += coverage.warnings
        scope_ids = [project.project_id for project in inventory.selected]
        totals = {
            gene_id: sum(counts.projects.get(project_id, {}).get(gene_id, 0) for project_id in scope_ids)
            for gene_id in count_genes
        }
        selected_gene_ids = ranked_genes[:CANDIDATE_GENE_LIMIT]
        if not selected_gene_ids:
            raise LiveRunError("NO_DISCOVERED_GENES", "gene selection produced an empty set")
        genes_response = transport.request(genes_request(selected_gene_ids))
        gene_records = parse_genes(genes_response.body, self._meta(genes_response, inventory.release))
        sources.append(self._source(genes_response, locator="/genes", release=inventory.release))
        if len(gene_records) != len(selected_gene_ids):
            raise LiveRunError("GENE_IDENTITY_INCOMPLETE",
                               f"requested {len(selected_gene_ids)} genes, received {len(gene_records)}")
        genes = {record.gene_id: record for record in gene_records}
        selection_payload = {
            "selection_rule": GENE_SELECTION_RULE,
            "domain": DOMAIN,
            "cohort": COHORT_PROJECT_ID,
            "provider_ranked_genes": ranked_genes,
            "counted_genes": count_genes,
            "affected_totals_in_scope": totals,
            "selected_gene_ids": selected_gene_ids,
            "provider_ranking_note": (
                "Discovery uses the provider top-mutated ranking; _score is provider-internal selection "
                "metadata and is never treated as a mutation count or effect size."
            ),
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/selection/examined_genes.json",
                                     selection_payload, "gdc-gene-selection")
        examined_genes_hash = hashlib.sha256(canonical_json(selection_payload)).hexdigest()
        return Selection(
            discovery_by_project=discovery_by_project, count_genes=count_genes,
            selected_gene_ids=selected_gene_ids, genes=genes, counts=counts, coverage=coverage,
            sources=sources, warnings=warnings, artifact=artifact, examined_genes_hash=examined_genes_hash,
        )

    # ---------------------------------------------------------- state generation

    def _acquire_project_frame(self, run_id: str, transport: GDCTransport, inventory: Inventory,
                               selection: Selection, project: ProjectRecord,
                               ) -> tuple[ProjectFrame, list[dict[str, Any]], list[str]]:
        """Acquire one cohort case frame plus its expression lanes.

        Returns the frame together with the sources and warnings it produced so the
        caller keeps a single provenance list. The frame carries the parser's
        ``missing_case_ids`` untouched; deterministic science decides how missing
        examined cases are counted.
        """
        sources: list[dict[str, Any]] = []
        warnings: list[str] = []
        gene_ids = selection.selected_gene_ids
        cases_response = transport.request(cases_request(project.project_id, 250))
        page = parse_cases(cases_response.body, self._meta(cases_response, inventory.release))
        if not page.complete:
            raise LiveRunError(
                "CASE_FRAME_INCOMPLETE",
                f"{project.project_id}: frame returned {page.count} of {page.total} cases in one page",
            )
        case_ids = [case.case_id for case in page.cases]
        frame_hash = hashlib.sha256(canonical_json(sorted(case_ids))).hexdigest()
        sources.append(self._source(cases_response, locator=f"/cases[{project.project_id}]",
                                    release=inventory.release))
        warnings += page.warnings
        files_response = transport.request(files_expression_request(project.project_id, 5))
        provenance = parse_files_provenance(files_response.body, self._meta(files_response, inventory.release))
        sources.append(self._source(files_response, locator=f"/files[{project.project_id}]",
                                    release=inventory.release))
        warnings += provenance.warnings
        if provenance.non_open_records:
            raise LiveRunError("CONTROLLED_RECORD_RETURNED",
                               f"{project.project_id}: {provenance.non_open_records} non-open file records")
        availability: ExpressionAvailability | None = None
        provider: ProviderSelection | None = None
        values: ExpressionValues | None = None
        if case_ids:
            availability_response = transport.request(expression_availability_request(case_ids, gene_ids))
            availability = parse_expression_availability(
                availability_response.body, self._meta(availability_response, inventory.release),
                expected_cases=case_ids, expected_genes=gene_ids,
            )
            sources.append(self._source(availability_response,
                                        locator=f"/gene_expression/availability[{project.project_id}]",
                                        release=inventory.release))
            warnings += availability.warnings
            cases_with_values = [
                case.case_id for case in page.cases
                if availability.cases.get(case.case_id) is True
            ]
            if cases_with_values:
                selection_response = transport.request(expression_gene_selection_request(case_ids, gene_ids))
                provider = parse_gene_selection(
                    selection_response.body, self._meta(selection_response, inventory.release),
                    expected_genes=gene_ids,
                )
                sources.append(self._source(selection_response,
                                            locator=f"/gene_expression/gene_selection[{project.project_id}]",
                                            release=inventory.release))
                warnings += provider.warnings
                values_response = transport.request(expression_values_request(case_ids, gene_ids))
                values = parse_expression_values(
                    values_response.body, self._meta(values_response, inventory.release),
                    expected_cases=case_ids, expected_genes=gene_ids,
                )
                sources.append(self._source(values_response,
                                            locator=f"/gene_expression/values[{project.project_id}]",
                                            release=inventory.release))
            else:
                warnings.append(
                    f"{project.project_id}: no examined case has gene expression values; "
                    "provider selection and local values lanes skipped (expression NOT_OBSERVED)"
                )
        frame = ProjectFrame(
            project_id=project.project_id, project_record=project, cases=page.cases,
            frame_hash=frame_hash, expression_coverage=availability, provider_selection=provider,
            expression_values=values, workflows=provenance.workflows, strategies=provenance.strategies,
            discovery_hits=selection.discovery_by_project.get(project.project_id, {}),
        )
        return frame, sources, warnings

    def _generate_states(self, run_id: str, transport: GDCTransport, inventory: Inventory,
                         selection: Selection) -> list[dict[str, Any]]:
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
        states: list[dict[str, Any]] = []
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
                "ranking_rule": GENE_SELECTION_RULE,
            }
            state = build_statistical_state(
                run_id=run_id, state_id=state_id, created_at=utc_now(), gene=gene, frames=frames,
                counts=selection.counts, coverage=selection.coverage, sources=sources, warnings=warnings,
                scope_meta={"gdc_release": inventory.release, "examined_case_frame": "ALL_CASES_SINGLE_PAGE",
                            "scope_hash": inventory.scope_hash, "domain": DOMAIN,
                            "cohort": COHORT_PROJECT_ID},
                discovery_meta=discovery_meta,
            )
            artifact = self._publish_json(
                run_id, f"runs/{run_id}/statistical_states/{state_id}.json", state, "statistical-state",
            )
            summary = {
                "entity": {"gene_id": gene.gene_id, "gene_symbol": gene.symbol},
                "mode": "LIVE",
                "mutation_availability": state["mutation"]["availability"],
                "expression_availability": state["expression"]["availability"],
                "projects_with_mutation_observation": state["cross_project"]["projects_with_mutation_observation"],
                "projects_with_expression_observation": state["cross_project"]["projects_with_expression_observation"],
                "affected_case_total": state["cross_project"]["affected_case_total"],
                "top_project_share": state["cross_project"]["top_project_share"],
                "coverage_imbalance": state["cross_project"]["coverage_imbalance"],
                "completeness": state["quality"]["completeness"],
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
            }
            registrations = [
                self.repository.artifact_registration(artifact, run_id),
                (
                    "INSERT INTO statistical_states(state_id,run_id,state_hash,artifact_id,disposition,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
                    (state_id, run_id, state["state_hash"], artifact.artifact_id, "GENERATED",
                     canonical_json(summary).decode(), utc_now()),
                ),
            ]
            self._event(
                run_id, "STATISTICAL_STATE_CREATED", f"state:{state_id}",
                f"Real StatisticalState for {gene.symbol} generated from open GDC evidence.",
                stage="STATE_GENERATION",
                data={"state_id": state_id, "state_hash": state["state_hash"], "gene_id": gene.gene_id,
                      "gene_symbol": gene.symbol, "mode": "LIVE"},
                artifact_refs=[artifact.ref()], registrations=registrations,
            )
            states.append(state)
        self._event(
            run_id, "WIDE_SCAN_COMPLETED", "wide:completed",
            f"Wide evidence scan completed with {len(states)} states.",
            stage="STATE_GENERATION",
            data={"valid_count": len(states), "selected_count": 0, "selection_rule": WIDE_SCAN_RULE},
        )
        return states
