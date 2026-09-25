"""Typed scientific identity: stable across operational context, sensitive to content.

Identity is relational here, never a hardcoded historical hash: two constructions
from the same scientific content must agree, an operational or provider-ranking
change must not move identity, and a measured or scope change must move it.
"""

from dataclasses import replace

import pytest

from cancerjev.domain.codecs import (
    evidence_identity,
    read_evidence,
    read_state,
    state_identity,
    write_evidence,
    write_state,
)
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import (
    ActionRef,
    BaselineObservation,
    CheckOutcome,
    EvidenceCheck,
    EvidenceProvenance,
    EvidenceState,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    Acquisition,
    ContractError,
    MetricRecord,
    OperationalSource,
    ScientificSource,
    digest,
)
from cancerjev.domain.scientific import ProviderDiscoveryMetadata
from cancerjev.gdc.parsers import (
    CaseRecord,
    DiscoveryHit,
    ExpressionAvailability,
    ExpressionValues,
    GeneCaseCounts,
    GeneRecord,
    ProjectCoverage,
    ProjectRecord,
    ProviderGene,
    ProviderSelection,
)
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.methods import ProjectFrame, compute_statistical_state

GENE = GeneRecord(gene_id="ENSG00000141510", symbol="TP53", name="tumor protein p53",
                  biotype="protein_coding", is_cancer_gene_census=True)
GENE_ID = GENE.gene_id
RELEASE = "Data Release 46.0"
SOURCE_SET = (
    OperationalSource(
        ScientificSource("/analysis/top_cases_counts_by_genes", "b" * 64, "a" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-1", "artifact-1", "2026-09-25T00:00:00Z", 100, 5, 200, False),
    OperationalSource(
        ScientificSource("/analysis/mutated_cases_count_by_project", "b" * 64, "d" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-2", "artifact-2", "2026-09-25T00:00:00Z", 100, 5, 200, False),
    OperationalSource(
        ScientificSource("/gene_expression/values", "b" * 64, "e" * 64, "gdc-parser-v1",
                         RELEASE, Acquisition.COMPLETE),
        "attempt-3", "artifact-3", "2026-09-25T00:00:00Z", 100, 5, 200, False),
)


def scope_meta():
    spec = LUAD_RESEARCH_V1
    return {
        "gdc_release": RELEASE,
        "cohort": spec.cohort.cohort_id,
        "project_id": spec.cohort.project_id,
        "spec_id": spec.spec_id,
        "domain": spec.cohort.domain,
        "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": spec.gene_selection_rule(),
        "examined_case_frame": "ALL_CASES_PAGINATED",
        "research_spec": {"acquisition": {
            "case_page_size": spec.acquisition.case_page_size,
            "case_batch_size": spec.acquisition.case_batch_size,
            "max_cohort_cases": spec.acquisition.max_cohort_cases,
            "discovery_gene_limit": spec.acquisition.discovery_gene_limit,
            "count_gene_limit": spec.acquisition.count_gene_limit,
            "candidate_gene_limit": spec.acquisition.candidate_gene_limit,
            "expression_file_sample_size": spec.acquisition.expression_file_sample_size,
        }},
    }


def discovery_meta():
    return {
        "selected_gene_ids": (GENE_ID,),
        "examined_genes_hash": digest([GENE_ID]),
        "examined_genes_n": 3,
        "rank_in_lane": 1,
        "observed_in_project_count": 1,
        "ranking_rule": "provider top-mutated ranking for the single examined cohort",
        "examined_genes_ref": "selection-artifact-1",
    }


def frame(project_id="TCGA-LUAD", *, cases=6):
    case_records = [CaseRecord(case_id=f"{project_id}-case-{index:02d}", submitter_id=f"S-{index}",
                               project_id=project_id, sample_types=["Primary Tumor"])
                    for index in range(cases)]
    coverage = ExpressionAvailability(
        cases={case.case_id: True for case in case_records}, genes={GENE_ID: True},
        with_count=cases, without_count=0, missing_cases=[], missing_genes=[], warnings=[])
    values = ExpressionValues(
        values={GENE_ID: {case.case_id: float(index + 1) for index, case in enumerate(case_records)}},
        missing_case_ids=[], missing_gene_ids=[], nonfinite_values=0, warnings=[])
    provider = ProviderSelection(
        genes={GENE_ID: ProviderGene(gene_id=GENE_ID, symbol="TP53", median=2.5, stddev=0.3)},
        missing_genes=[], warnings=[])
    hits = {GENE_ID: DiscoveryHit(gene_id=GENE_ID, symbol="TP53", rank=1, score=99.0)}
    return ProjectFrame(
        project_id=project_id,
        project_record=ProjectRecord(project_id=project_id, name=project_id, program_name="TCGA",
                                     primary_site=["Lung"], disease_type=["Adenocarcinoma"],
                                     case_count=cases, file_count=cases * 5,
                                     data_categories=["Transcriptome Profiling"]),
        cases=case_records, frame_hash="f" * 64, expression_coverage=coverage,
        provider_selection=provider, expression_values=values, workflows=["STAR - Counts"],
        strategies=["RNA-Seq"], discovery_hits=hits)


def build_state(*, frames=None, counts=None, coverage=None, sources=SOURCE_SET):
    frames = frames or [frame()]
    counts = counts if counts is not None else {f.project_id: {GENE_ID: 2} for f in frames}
    coverage = coverage if coverage is not None else {f.project_id: len(f.cases) for f in frames}
    return compute_statistical_state(
        gene=GENE, frames=frames,
        counts=GeneCaseCounts(projects=counts, hits_total=10, complete=True, partial_reasons=[],
                              warnings=[]),
        coverage=ProjectCoverage(case_with_ssm=coverage, complete=True, partial_reasons=[],
                                 warnings=[]),
        sources=sources, warnings=[], scope_meta=scope_meta(),
        discovery_meta=discovery_meta())


def project_row(affected=2, examined=6):
    return ProjectEvidenceRow(
        "TCGA-LUAD", MetricRecord.observed_value(affected, "cases"),
        MetricRecord.observed_value(examined, "cases"), MetricRecord.observed_value(examined, "cases"),
        MetricRecord.observed_value(examined, "cases"), MetricRecord.observed_value(0, "cases"))


def baseline_evidence(state):
    accepted = state_identity(state)
    return EvidenceState(
        entity=state.entity, accepted_state_hash=accepted,
        source_state=SourceStateBinding("state-1", accepted, "artifact-1", "c" * 64),
        parent_evidence_hash=None, revision_index=0, action=None,
        puzzle=ResearchPuzzle("STATISTICAL_STATE_BASELINE", "What is supported?",
                              "The baseline is accepted evidence, not a judgment.",
                              ("CHECK_EVIDENCE_INTEGRITY_V1",)),
        checks=(),
        baseline_observations=(BaselineObservation(
            "MUTATION_AFFECTED_CASE_COUNT_V1", "1",
            canonical_json({"value": 2, "unit": "cases"}), "OBSERVED", 6, 0, None),),
        project_evidence=(project_row(),), missing_evidence=(),
        quality=state.quality, warnings=state.missingness,
        provenance=EvidenceProvenance(state.entity.release, state.sources, state.methods,
                                      state.environment_hash, "2",
                                      state.tested_context.examined_genes_hash, ()))


def action_revision(base, state, outcome=CheckOutcome.VERIFIED):
    check = EvidenceCheck(
        "CHECK_EVIDENCE_INTEGRITY_V1", "EVIDENCE_INTEGRITY_V1", "1", outcome,
        "recorded counts are internally consistent", (base.accepted_state_hash,),
        None if outcome == CheckOutcome.VERIFIED else "recorded evidence contradicts the claim",
        len(state.projects), canonical_json({"affected": 2}), canonical_json({"affected": 2}),
        missing_count=1 if outcome == CheckOutcome.NOT_OBSERVED else 0,
        missing_reason=("RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION"
                        if outcome == CheckOutcome.NOT_OBSERVED else None))
    return replace(base, parent_evidence_hash=evidence_identity(base), revision_index=1,
                   action=ActionRef("CHECK_EVIDENCE_INTEGRITY_V1", "1"),
                   puzzle=ResearchPuzzle("DETERMINISTIC_ACTION_REGISTRY", "Is the revision faithful?",
                                         "Checks are not measurements.",
                                         ("CHECK_EVIDENCE_INTEGRITY_V1",)),
                   checks=(check,), baseline_observations=())


# ------------------------------------------------------------ state identity


def test_state_identity_excludes_operational_links_ranking_and_selection_binding():
    base = build_state()
    replayed = build_state(sources=(
        replace(SOURCE_SET[0], attempt_id="retry-9", artifact_id="artifact-9",
                retrieved_at="2027-01-01T00:00:00Z", bytes_read=9, latency_ms=1, http_status=None,
                cache_hit=True),
        *SOURCE_SET[1:]))
    assert state_identity(replayed) == state_identity(base)
    assert write_state(replayed) != write_state(base)
    assert read_state(write_state(replayed), expected_hash=state_identity(base)) == replayed

    ranked = replace(base, projects=(replace(
        base.projects[0],
        discovery=ProviderDiscoveryMetadata(rank=9, score=123.0, lane_id="MUTATION_DISCOVERY_V1",
                                            note="selection metadata only")),))
    assert state_identity(ranked) == state_identity(base)
    unranked = replace(base, projects=(replace(base.projects[0], discovery=None),))
    assert state_identity(unranked) == state_identity(base)

    rebound = replace(base, tested_context=replace(base.tested_context,
                                                   selection_artifact_id="other-selection-artifact"))
    assert state_identity(rebound) == state_identity(base)

    with pytest.raises(ContractError):
        replace(base, operational_sources=(
            replace(SOURCE_SET[0], source=replace(SOURCE_SET[0].source, response_hash="9" * 64)),
            *SOURCE_SET[1:]))


def test_state_identity_tracks_measured_content_and_scope():
    base = build_state()
    baseline = state_identity(base)
    measured = replace(base, projects=(replace(
        base.projects[0],
        mutation=replace(base.projects[0].mutation,
                         affected_cases=replace(base.projects[0].mutation.affected_cases, value=3))),))
    assert state_identity(measured) != baseline
    assert state_identity(build_state(frames=[frame(cases=7)])) != baseline
    assert state_identity(replace(
        base, methods=(replace(base.methods[0], version="2"), *base.methods[1:]))) != baseline
    assert state_identity(replace(base, missingness=("a case column was not returned",))) != baseline
    assert state_identity(replace(
        base, universe=replace(base.universe, filter_description="different tested scope"))) != baseline
    other = replace(base.entity, symbol="OTHER")
    renamed = replace(base, entity=other, projects=(replace(
        base.projects[0],
        mutation=replace(base.projects[0].mutation, entity=other),
        expression=replace(base.projects[0].expression, entity=other)),))
    assert state_identity(renamed) != baseline


# --------------------------------------------------------- evidence identity


def test_evidence_identity_excludes_only_the_source_artifact_binding():
    state = build_state()
    base = baseline_evidence(state)
    moved = replace(base, source_state=replace(base.source_state, state_artifact_id="other-artifact",
                                               state_artifact_sha256="d" * 64))
    assert evidence_identity(moved) == evidence_identity(base)
    assert write_evidence(moved) != write_evidence(base)
    assert read_evidence(write_evidence(moved), expected_hash=evidence_identity(base)) == moved


def test_evidence_identity_tracks_revision_content():
    state = build_state()
    base = baseline_evidence(state)
    verified = action_revision(base, state, CheckOutcome.VERIFIED)
    contradicted = action_revision(base, state, CheckOutcome.CONTRADICTED)
    assert evidence_identity(verified) != evidence_identity(base)
    assert evidence_identity(contradicted) != evidence_identity(verified)
    metrics_changed = replace(verified, project_evidence=(
        replace(verified.project_evidence[0],
                affected_case_count=MetricRecord.observed_value(5, "cases")),))
    assert evidence_identity(metrics_changed) != evidence_identity(verified)
    observation_changed = replace(base, baseline_observations=(
        replace(base.baseline_observations[0],
                observed=canonical_json({"value": 4, "unit": "cases"})),))
    assert evidence_identity(observation_changed) != evidence_identity(base)
