"""Question-scoped expression reaches canonical state and semantic projection."""

from dataclasses import replace

import pytest

from cancerjev.domain.codecs import read_state, state_identity, write_state
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.measurements import Acquisition, UnavailableMeasurement
from cancerjev.gdc.endpoints import cohort_project_request, genes_request
from cancerjev.gdc.parsers import parse_genes, parse_projects
from cancerjev.jev.projection import build_projection
from cancerjev.research.acquisition import acquire_project_frame, response_meta
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.methods import ScienceError, compute_statistical_state
from cancerjev.storage.artifacts import ArtifactStore
from tests.integration.replay import GENES, ReplayTransport


@pytest.mark.parametrize("missing_columns", [0, 1])
def test_expression_question_keeps_mutation_unacquired_and_projects_real_expression(tmp_path, missing_columns):
    release = "Data Release TEST - 2026-01-01"
    transport = ReplayTransport(ArtifactStore(tmp_path), "expression-question",
                                project_case_counts={"TCGA-LUAD": 25},
                                drop_value_columns=missing_columns)
    spec = replace(LUAD_RESEARCH_V1, acquisition=replace(
        LUAD_RESEARCH_V1.acquisition, case_batch_size=20))
    response = transport.request(cohort_project_request("TCGA-LUAD"))
    project = parse_projects(response.body, response_meta(response, release))[0]
    response = transport.request(genes_request(list(GENES)))
    gene = parse_genes(response.body, response_meta(response, release))[0]
    frame, sources, warnings = acquire_project_frame(
        transport, project, spec.acquisition, release, list(GENES), {})
    scope = {
        "gdc_release": release, "spec_id": spec.spec_id, "research_spec": spec.as_dict(),
        "domain": spec.cohort.domain, "cohort": spec.cohort.cohort_id,
        "project_id": project.project_id, "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": "question-selected panel", "scope_hash": "question-scope",
    }
    state = compute_statistical_state(
        gene=gene, frames=[frame], coverage=None, sources=sources, warnings=warnings,
        scope_meta=scope, discovery_meta={"selected_gene_ids": tuple(GENES)},
        question_gene_ids=tuple(GENES))
    mutation = state.projects[0].mutation
    assert isinstance(mutation.affected_cases, UnavailableMeasurement)
    assert isinstance(mutation.ssm_coverage_cases, UnavailableMeasurement)
    assert mutation.quality.acquisition is Acquisition.NOT_ACQUIRED
    assert state.cross_project.affected_case_total.value is None
    assert state.universe.source == "QUESTION_SELECTED_GENE_PANEL"
    assert state.universe.ordered_ids == tuple(GENES)
    assert state.research.modalities == ("expression_summary",)
    assert state.tested_context.discovered_in_project_count == 0
    assert read_state(write_state(state), expected_hash=state_identity(state)) == state
    projection = build_projection(StateRecord("question-state", state_identity(state), state))
    assert projection["cohort"]["affected_cases"] is None
    assert projection["cohort"]["mutation_observed"] is False
    assert projection["cohort"]["expression_observed"] is True
    assert projection["cohort"]["expression_n_finite"] == 25 - 2 * missing_columns
    assert projection["cohort"]["expression_n_missing"] == 2 * missing_columns
    assert "not an unbiased or genome-wide" in projection["scope"]["selection_bias"]
    assert "ssm_occurrences" not in {request.endpoint.name for request in transport.requests}
    with pytest.raises(ScienceError, match="INVALID_QUESTION_EXPRESSION_SCOPE"):
        compute_statistical_state(
            gene=gene, frames=[frame], coverage=None, sources=sources, warnings=warnings,
            scope_meta=scope, discovery_meta={"selected_gene_ids": tuple(GENES)},
            question_gene_ids=(GENES[1],))
