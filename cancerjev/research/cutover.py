"""Stage 7 deterministic cutover from discovery artifacts to canonical states."""

from __future__ import annotations

from cancerjev.domain.codecs import discovery_identity
from cancerjev.domain.discovery import (
    CnvDiscoveryResult,
    ExpressionDiscoveryResult,
    MutationDiscoveryResult,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    MetricAvailability,
    MetricRecord,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    Quality,
    Sufficiency,
)
from cancerjev.domain.scientific import (
    AcquisitionScope,
    CrossProjectSummary,
    ExpressionSummaryResult,
    GeneAnnotation,
    MutationCountResult,
    PopulationRecord,
    ProjectState,
    ResearchState,
    StatisticalState,
    TestedContext,
    UnavailableLane,
)
from cancerjev.research.specs import ResearchSpec
from cancerjev.science.methods import (
    COMPARABILITY_STATUSES,
    CROSS_PROJECT_COMPARABILITY,
    WITHIN_COHORT_COMPARABILITY,
    _environment_hash,
    _state_methods,
)

CUTOVER_SELECTION_BIAS = (
    "States are limited to Stage 4 mutation-count survivors from a fixed indexed gene prefix; "
    "expression and CNV descriptors do not recover genes excluded by that mutation-first reduction."
)


class CutoverError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _scope(spec: ResearchSpec) -> AcquisitionScope:
    value = spec.acquisition
    return AcquisitionScope(
        value.case_page_size, value.case_batch_size, value.max_cohort_cases,
        value.discovery_gene_limit, value.count_gene_limit, value.candidate_gene_limit,
        value.expression_file_sample_size,
    )


def _unique_operational(*groups: tuple[OperationalSource, ...]) -> tuple[OperationalSource, ...]:
    result: list[OperationalSource] = []
    for source in (item for group in groups for item in group):
        if source not in result:
            result.append(source)
    return tuple(result)


def _metric(value: float | int | None, unit: str, reason: str) -> MetricRecord:
    if value is None:
        return MetricRecord.unavailable(unit, MetricAvailability.NOT_APPLICABLE, reason)
    return MetricRecord.observed_value(value, unit)


def compose_discovery_states(
    mutation: MutationDiscoveryResult,
    expression: ExpressionDiscoveryResult,
    cnv: CnvDiscoveryResult,
    spec: ResearchSpec,
) -> tuple[StatisticalState, ...]:
    """Bind Stages 4–6 exactly and create one canonical state per mutation survivor."""
    identity = discovery_identity(mutation)
    if mutation.spec_id != spec.spec_id or expression.spec_id != spec.spec_id or cnv.spec_id != spec.spec_id:
        raise CutoverError("SPEC_MISMATCH", "all discovery artifacts must use the selected ResearchSpec")
    if cnv.mutation_discovery_hash != identity:
        raise CutoverError("MUTATION_BINDING_MISMATCH", "CNV artifact does not bind the Stage 4 result")
    identities = {
        (item.cohort_id, item.project_id, item.release)
        for item in (mutation, expression, cnv)
    }
    if len(identities) != 1:
        raise CutoverError("SCOPE_MISMATCH", "release/cohort/project differs across discovery artifacts")
    if expression.universe != mutation.universe:
        raise CutoverError("UNIVERSE_MISMATCH", "Stage 5 universe differs from Stage 4")
    if cnv.survivor_ids != mutation.survivor_ids:
        raise CutoverError("SURVIVOR_MISMATCH", "Stage 6 entries differ from Stage 4 survivors")
    mutation_by_id = {entry.entity.gene_id: entry for entry in mutation.entries}
    expression_by_id = {entry.entity.gene_id: entry for entry in expression.entries}
    cnv_by_id = {entry.entity.gene_id: entry for entry in cnv.entries}
    frame = cnv.population
    if expression.population != frame:
        raise CutoverError("FRAME_MISMATCH", "Stage 5 and Stage 6 population frames differ")
    sources = _unique_operational(mutation.sources, expression.sources, cnv.sources)
    scientific_sources = tuple(dict.fromkeys(source.source for source in sources))
    population = PopulationRecord(
        population_id=f"{mutation.cohort_id}:CASES", frame=frame, program=None,
        provider_reported_cases=len(frame.examined_ids), frame_hash=frame.membership_hash,
        workflows=expression.workflows, sample_types=(), selection_method=frame.selection_rule,
        selection_version="1", harmonization_context="GDC_RELEASE_BOUND_SINGLE_COHORT",
    )
    research = ResearchState(
        spec_id=spec.spec_id, domain=spec.cohort.domain, cohort=spec.cohort.cohort_id,
        project_id=spec.cohort.project_id, cohort_selection_rule=spec.cohort_selection_rule(),
        gene_selection_rule=mutation.reducer.method_id,
        examined_case_frame=frame.selection_rule, acquisition=_scope(spec),
        modalities=("mutation_counts", "expression_summary", "cnv_occurrences"),
        programs=(), projects=(spec.cohort.project_id,), workflows=expression.workflows,
        sample_types=(), sample_type_counts=(), comparability_statuses=COMPARABILITY_STATUSES,
        within_cohort_status=WITHIN_COHORT_COMPARABILITY["status"],
        within_cohort_reason=WITHIN_COHORT_COMPARABILITY["reason"],
        cross_project_status=CROSS_PROJECT_COMPARABILITY["status"],
        cross_project_reason=CROSS_PROJECT_COMPARABILITY["reason"],
    )
    states: list[StatisticalState] = []
    for rank, gene_id in enumerate(mutation.survivor_ids, start=1):
        mutation_entry = mutation_by_id[gene_id]
        expression_entry = expression_by_id.get(gene_id)
        cnv_entry = cnv_by_id.get(gene_id)
        if expression_entry is None or cnv_entry is None:
            raise CutoverError("SURVIVOR_EVIDENCE_MISSING", f"missing Stage 5/6 entry for {gene_id}")
        mutation_outcome = mutation_entry.outcome
        if not isinstance(mutation_outcome, MutationCountResult) or mutation_outcome.frame != frame:
            raise CutoverError("FRAME_MISMATCH", f"Stage 4 frame differs for {gene_id}")
        if expression_entry.entity != mutation_entry.entity or cnv_entry.entity != mutation_entry.entity:
            raise CutoverError("ENTITY_MISMATCH", f"lane entity differs for {gene_id}")
        expression_outcome = expression_entry.outcome
        cnv_outcome = cnv_entry.outcome
        if isinstance(expression_outcome, ExpressionSummaryResult) and expression_outcome.coverage.frame != frame:
            raise CutoverError("FRAME_MISMATCH", f"expression frame differs for {gene_id}")
        affected = mutation_outcome.affected_cases
        affected_value = affected.value if isinstance(affected, ObservedCount) else None
        median_value = (expression_outcome.median.value
                        if isinstance(expression_outcome, ExpressionSummaryResult)
                        and isinstance(expression_outcome.median, ObservedScalar) else None)
        acquisition_complete = all(
            not isinstance(outcome, UnavailableLane) and outcome.quality.acquisition is Acquisition.COMPLETE
            for outcome in (expression_outcome, cnv_outcome)
        ) and mutation_outcome.quality.acquisition is Acquisition.COMPLETE
        quality = Quality(
            Acquisition.COMPLETE if acquisition_complete else Acquisition.PARTIAL,
            Sufficiency.SUFFICIENT if acquisition_complete else Sufficiency.PARTIAL,
            Compatibility.UNVERIFIED,
            ("Stages 4-6 are exactly release/frame bound; cross-assay sample matching remains unverified.",),
        )
        state = StatisticalState(
            entity=mutation_entry.entity,
            annotation=GeneAnnotation(None, None, None, "not observed in admitted discovery endpoints"),
            research=research, universe=mutation.universe,
            tested_context=TestedContext(
                mutation.universe.membership_hash, len(mutation.universe.ordered_ids), rank,
                mutation.reducer.method_id, CUTOVER_SELECTION_BIAS, 1, None,
            ),
            projects=(ProjectState(
                population, mutation_outcome, expression_outcome, None, None, cnv_outcome),),
            cross_project=CrossProjectSummary(
                1 if affected_value is not None else 0,
                1 if median_value is not None else 0,
                _metric(affected_value, "cases", "NO_MUTATION_OBSERVATION"),
                _metric(None, "share", "SINGLE_PROJECT"),
                _metric(median_value, "log2(UQFPKM+1)", "NO_EXPRESSION_OBSERVATION"),
                _metric(median_value, "log2(UQFPKM+1)", "NO_EXPRESSION_OBSERVATION"),
                False, "not applicable to one project", "not applicable to one project",
                "NOT_EXAMINED", "NOT_APPLICABLE", (),
            ),
            quality=quality,
            warnings=tuple(dict.fromkeys((*mutation.warnings, *expression.warnings, *cnv.warnings))),
            missingness=tuple(
                f"{group.reason}: {len(group.ids)} case(s)"
                for group in (expression_outcome.coverage.missing
                              if isinstance(expression_outcome, ExpressionSummaryResult) else ())
            ),
            methods=_state_methods(), environment_hash=_environment_hash(),
            sources=scientific_sources, operational_sources=sources,
        )
        states.append(state)
    return tuple(states)
