"""Stage 5 independent expression arm over the fixed systematic gene universe."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import write_expression_discovery
from cancerjev.domain.discovery import (
    EXPRESSION_LIMITATIONS,
    EXPRESSION_REQUEST_AVERAGE_BYTES,
    EXPRESSION_RUN_MAX_BYTES,
    EXPRESSION_RUN_MAX_REQUESTS,
    ExpressionDiscoveryEntry,
    ExpressionDiscoveryResult,
    ExpressionDisposition,
    ExpressionRunPlan,
)
from cancerjev.domain.measurements import (
    ContractError,
    EntityRef,
    MetricAvailability,
    PopulationFrame,
    PopulationUnit,
)
from cancerjev.domain.scientific import ExpressionSummaryResult
from cancerjev.domain.shards import ShardKind, ShardLedger, ShardRecord, ShardStatus
from cancerjev.gdc.endpoints import cohort_project_request, status_request
from cancerjev.gdc.parsers import GeneRecord, parse_projects, parse_status
from cancerjev.research.acquisition import (
    LiveRunError,
    acquire_batched_expression,
    acquire_cohort,
    response_meta,
    response_operational_source,
)
from cancerjev.research.discovery import UNIVERSE_PAGE_SIZE, acquire_gene_universe
from cancerjev.research.shards import ledger_summary, publish_shard_ledger
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.descriptors import expression_lane_disposition, expression_tail_descriptor
from cancerjev.science.expression import expression_observation
from cancerjev.science.methods import ProjectFrame, expression_result
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository


def _expression_run_plan(spec: ResearchSpec, *, gene_count: int, case_count: int) -> ExpressionRunPlan:
    """Declared pre-run volume plan over the enumerated universe and cohort."""
    acquisition = spec.acquisition
    expression = spec.expression_discovery
    cohort_pages = math.ceil(acquisition.max_cohort_cases / acquisition.case_page_size)
    universe_pages = math.ceil(gene_count / UNIVERSE_PAGE_SIZE)
    case_batches = math.ceil(case_count / acquisition.case_batch_size)
    gene_batches = math.ceil(gene_count / expression.gene_batch_size)
    # status + project inventory + cohort + universe + workflow facets
    # + availability/values matrices over every gene and case batch
    request_count = 2 + cohort_pages + universe_pages + 1 + 2 * case_batches * gene_batches
    return ExpressionRunPlan(
        gene_count=gene_count, case_count=case_count, gene_batches=gene_batches,
        case_batches=case_batches, request_count=request_count,
        projected_bytes=request_count * EXPRESSION_REQUEST_AVERAGE_BYTES,
        max_requests=EXPRESSION_RUN_MAX_REQUESTS, max_bytes=EXPRESSION_RUN_MAX_BYTES,
    )


def run_expression_discovery(
    run_id: str,
    transport: Any,
    repository: Repository,
    artifacts: ArtifactStore,
    emit: Callable[..., Any],
    research_spec: ResearchSpec,
) -> ExpressionDiscoveryResult:
    """Execute and persist Stage 5; this path performs no mutation or model work."""
    cohort_spec = research_spec.cohort
    emit("EXPRESSION_DISCOVERY_STARTED", f"expression-discovery:started:{uuid4()}",
         "Independent expression discovery started.",
         data={"spec_id": research_spec.spec_id,
               "expression_discovery": asdict(research_spec.expression_discovery)})
    status_response = transport.request(status_request())
    status = parse_status(status_response.body, response_meta(status_response, None))
    release = status.data_release
    project_response = transport.request(cohort_project_request(cohort_spec.project_id))
    projects = parse_projects(project_response.body, response_meta(project_response, release))
    selected = [project for project in projects if project.project_id == cohort_spec.project_id]
    if not selected:
        raise LiveRunError("COHORT_PROJECT_NOT_FOUND",
                           f"cohort project {cohort_spec.project_id} not present in the open inventory")
    project = selected[0]
    sources = [response_operational_source(status_response, release=release),
               response_operational_source(project_response, release=release)]
    warnings = list(status.warnings)
    cohort = acquire_cohort(transport, project, research_spec.acquisition, release)
    sources.extend(cohort.sources)
    warnings.extend(cohort.warnings)
    population = PopulationFrame(
        cohort_spec.cohort_id, cohort_spec.project_id, PopulationUnit.CASE,
        tuple(case.case_id for case in cohort.cases), None, "ALL_CASES_PAGINATED",
    )
    universe = acquire_gene_universe(transport, research_spec.discovery, release)
    sources.extend(universe.sources)
    warnings.extend(universe.warnings)
    emit("EXPRESSION_UNIVERSE_ACQUIRED", f"expression-discovery:universe:{uuid4()}",
         "Expression universe enumerated.",
         data={"returned": len(universe.universe.ordered_ids),
               "membership_hash": universe.universe.membership_hash,
               "release": universe.universe.release})
    try:
        run_plan = _expression_run_plan(
            research_spec, gene_count=len(universe.universe.ordered_ids),
            case_count=len(cohort.cases))
    except ContractError as exc:
        raise LiveRunError("EXPRESSION_RUN_PLAN_EXCEEDS_BUDGET", str(exc)) from exc
    plan_artifact = artifacts.publish(
        f"runs/{run_id}/expression-discovery/run-plan.json",
        json.dumps({"kind": "EXPRESSION_RUN_PLAN", **run_plan.payload()},
                   sort_keys=True, separators=(",", ":")).encode("utf-8"),
        "application/json", "expression-run-plan",
    )
    repository.register_artifact(plan_artifact, run_id)
    emit("EXPRESSION_RUN_PLANNED", f"expression-discovery:plan:{uuid4()}",
         "Expression run volume plan admitted against the declared budgets.",
         data={"run_plan": run_plan.payload()},
         artifact_refs=[plan_artifact.ref()])
    acquired = acquire_batched_expression(
        transport, project, research_spec.acquisition, release, cohort,
        list(universe.universe.ordered_ids), research_spec.expression_discovery.gene_batch_size,
    )
    sources.extend(acquired.sources)
    warnings.extend(acquired.warnings)
    expression_ledger = ShardLedger(
        kind=ShardKind.EXPRESSION_GENE_BATCHES, required=len(acquired.batches),
        records=tuple(ShardRecord(
            index=batch.batch_index, status=ShardStatus.COMPLETED,
            item_count=len(batch.gene_ids),
            request_hash=batch.sources[-1].source.request_hash if batch.sources else None,
            response_hash=batch.sources[-1].source.response_hash if batch.sources else None,
            artifact_id=batch.sources[-1].artifact_id if batch.sources else None,
            detail=None,
        ) for batch in acquired.batches),
    ) if acquired.batches else ShardLedger(
        kind=ShardKind.EXPRESSION_GENE_BATCHES, required=1,
        records=(ShardRecord(index=0, status=ShardStatus.FAILED, item_count=None,
                             request_hash=None, response_hash=None, artifact_id=None,
                             detail="no expression gene batch was acquired"),),
    )
    ledger_artifact = publish_shard_ledger(
        artifacts, repository, run_id, expression_ledger,
        relative_path=f"runs/{run_id}/expression-discovery/shards.json")
    if not expression_ledger.terminal:
        raise LiveRunError(
            "SHARD_LEDGER_NOT_TERMINAL",
            "the expression shard ledger is not terminal; no reduction may finalize",
        )
    emit("EXPRESSION_SHARDS_COMPLETED", f"expression-discovery:shards:{uuid4()}",
         "Expression gene batches completed for every required shard.",
         data={"shard_ledger": ledger_summary(expression_ledger), "release": release},
         artifact_refs=[ledger_artifact.ref()])
    entries_by_id: dict[str, ExpressionDiscoveryEntry] = {}
    for batch in acquired.batches:
        frame = ProjectFrame(
            project.project_id, project, list(cohort.cases), cohort.frame_hash,
            batch.availability, None, batch.values, list(acquired.workflows),
            list(acquired.strategies), {}, "PROVIDER_SUMMARY_NOT_REQUESTED_IN_STAGE_5",
        )
        for gene_id in batch.gene_ids:
            gene: GeneRecord = universe.genes[gene_id]
            observation = expression_observation(
                project_id=project.project_id, gene_id=gene_id,
                case_ids=population.examined_ids, coverage=batch.availability,
                values=batch.values, provider=None,
                provider_unavailable_reason="PROVIDER_SUMMARY_NOT_REQUESTED_IN_STAGE_5",
            )
            outcome = expression_result(
                frame, population, gene, observation, universe.universe.release, batch.sources)
            entity = EntityRef(gene_id, gene.symbol, universe.universe.release)
            tail = expression_tail_descriptor(outcome, research_spec.expression_discovery)
            disposition, reason, trigger = expression_lane_disposition(outcome, tail)
            entries_by_id[gene_id] = ExpressionDiscoveryEntry(
                entity, outcome, tail, disposition, reason, trigger)
    entries = tuple(entries_by_id[gene_id] for gene_id in universe.universe.ordered_ids)
    retained_ids = tuple(sorted(entry.entity.gene_id for entry in entries
                                if entry.disposition is ExpressionDisposition.RETAIN))
    review_ids = tuple(sorted(entry.entity.gene_id for entry in entries
                              if entry.disposition is ExpressionDisposition.JEV_REVIEW))
    result = ExpressionDiscoveryResult(
        research_spec.spec_id, cohort_spec.cohort_id, cohort_spec.project_id,
        universe.universe.release, research_spec.expression_discovery, universe.universe,
        population, entries, acquired.workflows, acquired.strategies, tuple(sources),
        tuple(warnings), EXPRESSION_LIMITATIONS, run_plan.request_count,
        workflow_file_counts=acquired.workflow_file_counts,
        workflow_coverage_complete=acquired.workflow_coverage_complete,
        retained_ids=retained_ids, jev_review_ids=review_ids,
    )
    artifact = artifacts.publish(
        f"runs/{run_id}/expression-discovery/result.json", write_expression_discovery(result),
        "application/json", "expression-discovery-result",
    )
    repository.register_artifact(artifact, run_id)
    observed = sum(isinstance(entry.outcome, ExpressionSummaryResult) for entry in entries)
    tails = sum(entry.tail.availability is MetricAvailability.OBSERVED for entry in entries)
    emit("EXPRESSION_DISCOVERY_COMPLETED", f"expression-discovery:completed:{uuid4()}",
         f"Independent expression discovery completed for {len(entries)} gene(s).",
         data={"entries": len(entries), "observed": observed, "tail_eligible": tails,
               "retained": len(retained_ids), "jev_review": len(review_ids),
               "universe_membership_hash": universe.universe.membership_hash,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result
