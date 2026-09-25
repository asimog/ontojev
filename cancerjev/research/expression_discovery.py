"""Stage 5 independent expression arm over the fixed systematic gene universe."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import write_expression_discovery
from cancerjev.domain.discovery import (
    EXPRESSION_LIMITATIONS,
    EXPRESSION_TAIL_METHOD_ID,
    EXPRESSION_TAIL_VERSION,
    ExpressionDiscoveryEntry,
    ExpressionDiscoveryResult,
    ExpressionTailDescriptor,
)
from cancerjev.domain.measurements import (
    EntityRef,
    MethodIdentityRef,
    MetricAvailability,
    PopulationFrame,
    PopulationUnit,
    digest,
)
from cancerjev.domain.scientific import ExpressionSummaryResult, UnavailableLane
from cancerjev.gdc.endpoints import cohort_project_request, status_request
from cancerjev.gdc.parsers import GeneRecord, parse_projects, parse_status
from cancerjev.research.acquisition import (
    LiveRunError,
    acquire_batched_expression,
    acquire_cohort,
    response_meta,
    response_operational_source,
)
from cancerjev.research.discovery import acquire_gene_universe
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.expression import expression_observation
from cancerjev.science.methods import ProjectFrame, expression_result
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository


def _linear_quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def expression_tail_descriptor(
    outcome: ExpressionSummaryResult | UnavailableLane,
    spec: Any,
) -> ExpressionTailDescriptor:
    parameters = {
        "minimum_n": spec.minimum_tail_n,
        "quantile_rule": spec.quantile_rule,
        "iqr_multiplier": spec.iqr_multiplier,
        "input_unit": spec.input_unit,
        "transform": spec.transform,
    }
    method = MethodIdentityRef(
        EXPRESSION_TAIL_METHOD_ID, EXPRESSION_TAIL_VERSION, digest(parameters))
    if isinstance(outcome, UnavailableLane):
        return ExpressionTailDescriptor(
            MetricAvailability.NOT_OBSERVED, outcome.reason, None, None, None, None,
            (), (), 0, method,
        )
    transformed = sorted(
        (math.log2(value.uqfpkm + 1.0), value.case_id) for value in outcome.values)
    if len(transformed) < spec.minimum_tail_n:
        return ExpressionTailDescriptor(
            MetricAvailability.INSUFFICIENT, "INSUFFICIENT_FINITE_VALUES", None, None, None, None,
            (), (), len(transformed), method,
        )
    ordered_values = [value for value, _ in transformed]
    q1 = _linear_quantile(ordered_values, 0.25)
    q3 = _linear_quantile(ordered_values, 0.75)
    iqr = q3 - q1
    if iqr == 0:
        return ExpressionTailDescriptor(
            MetricAvailability.UNAVAILABLE, "DEGENERATE_REFERENCE", None, None, None, None,
            (), (), len(transformed), method,
        )
    lower_fence = q1 - spec.iqr_multiplier * iqr
    upper_fence = q3 + spec.iqr_multiplier * iqr
    lower_ids = tuple(sorted(case_id for value, case_id in transformed if value < lower_fence))
    upper_ids = tuple(sorted(case_id for value, case_id in transformed if value > upper_fence))
    return ExpressionTailDescriptor(
        MetricAvailability.OBSERVED, None, q1, q3, lower_fence, upper_fence,
        lower_ids, upper_ids, len(transformed), method,
    )


def _request_plan_max(spec: ResearchSpec) -> int:
    acquisition = spec.acquisition
    discovery = spec.discovery
    expression = spec.expression_discovery
    cohort_pages = math.ceil(acquisition.max_cohort_cases / acquisition.case_page_size)
    universe_pages = math.ceil(discovery.universe_limit / 100)
    case_batches = math.ceil(acquisition.max_cohort_cases / acquisition.case_batch_size)
    gene_batches = math.ceil(discovery.universe_limit / expression.gene_batch_size)
    # status + project inventory + cohort + universe + file provenance + availability/values matrices
    return 2 + cohort_pages + universe_pages + 1 + 2 * case_batches * gene_batches


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
    plan_max = _request_plan_max(research_spec)
    if plan_max > 150:
        raise LiveRunError("EXPRESSION_REQUEST_PLAN_EXCEEDS_CAP",
                           f"worst-case plan needs {plan_max} requests")
    emit("EXPRESSION_DISCOVERY_STARTED", f"expression-discovery:started:{uuid4()}",
         "Independent expression discovery started.",
         data={"spec_id": research_spec.spec_id,
               "expression_discovery": asdict(research_spec.expression_discovery),
               "request_plan_max": plan_max})
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
    acquired = acquire_batched_expression(
        transport, project, research_spec.acquisition, release, cohort,
        list(universe.universe.ordered_ids), research_spec.expression_discovery.gene_batch_size,
    )
    sources.extend(acquired.sources)
    warnings.extend(acquired.warnings)
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
            entries_by_id[gene_id] = ExpressionDiscoveryEntry(
                entity, outcome,
                expression_tail_descriptor(outcome, research_spec.expression_discovery),
            )
    entries = tuple(entries_by_id[gene_id] for gene_id in universe.universe.ordered_ids)
    result = ExpressionDiscoveryResult(
        research_spec.spec_id, cohort_spec.cohort_id, cohort_spec.project_id,
        universe.universe.release, research_spec.expression_discovery, universe.universe,
        population, entries, acquired.workflows, acquired.strategies, tuple(sources),
        tuple(warnings), EXPRESSION_LIMITATIONS, plan_max,
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
               "universe_membership_hash": universe.universe.membership_hash,
               "artifact_id": artifact.artifact_id, "artifact_sha256": artifact.sha256},
         artifact_refs=[artifact.ref()],
         registrations=[repository.artifact_registration(artifact, run_id)])
    return result
