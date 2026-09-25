"""Offline Stage 5 replay through real acquisition, parsing, typing and persistence."""

from __future__ import annotations

from cancerjev.domain.codecs import (
    expression_discovery_identity,
    read_expression_discovery,
)
from cancerjev.domain.discovery import DiscoverySpec
from cancerjev.domain.measurements import MetricAvailability
from cancerjev.domain.scientific import ExpressionSummaryResult
from cancerjev.research.expression_discovery import run_expression_discovery
from cancerjev.research.specs import (
    AcquisitionSpec,
    CohortSpec,
    ResearchSpec,
    ScientificLimits,
)
from tests.integration.replay import GENES, ReplayTransport

SPEC = ResearchSpec(
    spec_id="LUAD_EXPRESSION_REPLAY_V1",
    intent="bounded offline independent expression discovery replay",
    cohort=CohortSpec("TCGA-LUAD", "lung cancer", "TCGA-LUAD"),
    discovery=DiscoverySpec(
        universe_method="GENE_ID_ASC_INDEXED_PREFIX_V1", biotype="protein_coding",
        order="GENE_ID_ASC", offset=0, universe_limit=2, mutation_batch_size=2,
    ),
    acquisition=AcquisitionSpec(
        case_page_size=25, case_batch_size=20, max_cohort_cases=25,
        discovery_gene_limit=2, count_gene_limit=2, candidate_gene_limit=2,
        expression_file_sample_size=3,
    ),
    limits=ScientificLimits(),
    allowed_actions=("CHECK_EVIDENCE_INTEGRITY_V1", "CHECK_REVISION_FAITHFULNESS_V1"),
)


def test_expression_discovery_replay_is_complete_hash_bound_and_model_free(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run(
        "expression-replay-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "EXPRESSION_DISCOVERY"},
    )
    events: list[dict] = []

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs))

    transport = ReplayTransport(
        artifacts, run_id, repository=repository,
        project_case_counts={"TCGA-LUAD": 25}, drop_value_columns=1,
    )
    result = run_expression_discovery(
        run_id, transport, repository, artifacts, emit, SPEC)

    assert result.universe.ordered_ids == tuple(GENES)
    assert len(result.population.examined_ids) == 25
    assert result.request_plan_max == 9
    assert len(result.entries) == 2
    for entry in result.entries:
        assert isinstance(entry.outcome, ExpressionSummaryResult)
        assert len(entry.outcome.values) == 23
        assert len(entry.outcome.coverage.missing) == 1
        assert entry.outcome.coverage.missing[0].reason == "CASE_COLUMN_NOT_RETURNED"
        assert len(entry.outcome.coverage.missing[0].ids) == 2
        assert entry.tail.availability is MetricAvailability.OBSERVED
        assert entry.tail.valid_n == 23

    names = [request.endpoint.name for request in transport.requests]
    assert names.count("files") == 1
    assert names.count("gene_expression_availability") == 2
    assert names.count("gene_expression_values") == 2
    assert "top_cases_counts_by_genes" not in names
    assert "top_mutated_genes_by_project" not in names
    assert "gene_expression_gene_selection" not in names

    completed = [event for event in events if event["type"] == "EXPRESSION_DISCOVERY_COMPLETED"]
    assert len(completed) == 1
    metadata = repository.artifact(completed[0]["data"]["artifact_id"])
    raw = artifacts.read(metadata["relative_path"], metadata["sha256"])
    assert read_expression_discovery(
        raw, expected_hash=expression_discovery_identity(result)) == result
    assert not [event for event in repository.events(run_id, 0, 100)["items"]
                if event["type"].startswith("JEV")]


def test_expression_tail_reports_degenerate_reference_instead_of_ranking(runtime):
    settings, repository, artifacts = runtime
    run_id = repository.create_run(
        "expression-degenerate-replay", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "EXPRESSION_DISCOVERY"},
    )

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        repository.append_event(
            run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)

    result = run_expression_discovery(
        run_id,
        ReplayTransport(
            artifacts, run_id, repository=repository,
            project_case_counts={"TCGA-LUAD": 25}, constant_expression_value=4.0,
        ),
        repository, artifacts, emit, SPEC,
    )
    assert {entry.tail.availability for entry in result.entries} == {
        MetricAvailability.UNAVAILABLE}
    assert {entry.tail.reason for entry in result.entries} == {"DEGENERATE_REFERENCE"}
    assert all(not entry.tail.lower_case_ids and not entry.tail.upper_case_ids
               for entry in result.entries)
