"""Stage 7 cutover replay: Stages 4-6 artifacts compose exactly into canonical states.

The chain runs the real discovery functions over provider-shaped replay
transports, then composes one ``StatisticalState`` per Stage 4 survivor through
the deterministic cutover. Assertions protect the binding contracts (release,
universe, frame, survivors, entities), the fail-closed refusals, and the
registered descriptor actions over the composed states.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from cancerjev.domain.codecs import read_state, state_identity, write_state
from cancerjev.domain.scientific import CnvOccurrenceResult
from cancerjev.research.cnv_discovery import run_cnv_discovery
from cancerjev.research.cutover import CutoverError, compose_discovery_states
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.research.expression_discovery import run_expression_discovery
from cancerjev.science.actions import eligible_actions, execute
from tests.integration.replay import ReplayTransport
from tests.integration.test_cnv_discovery_replay import CnvReplayTransport
from tests.integration.test_discovery_replay import (
    CASE_COUNT,
    PROJECT,
    SPEC,
    DiscoveryReplayTransport,
)


class _ExpressionDelegatingTransport(DiscoveryReplayTransport):
    """Stage 4 replay transport that also serves the Stage 5 expression endpoints."""

    def __init__(self, artifacts, run_id, repository) -> None:
        super().__init__(artifacts, run_id, repository)
        self._expression = ReplayTransport(
            artifacts, run_id, repository=repository,
            project_case_counts={PROJECT: CASE_COUNT},
        )

    def request(self, request):
        if request.endpoint.name in {
            "files", "gene_expression_availability", "gene_expression_gene_selection",
            "gene_expression_values",
        }:
            return self._expression.request(request)
        return super().request(request)


def _emit(repository, run_id):
    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        return repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                       message=message, **kwargs)
    return emit


def _stage_chain(runtime):
    _, repository, artifacts = runtime
    mutation_run = repository.create_run("cutover-stage4", mode="LIVE", fixture_id=None,
                                         fixture_version=None,
                                         scope={"purpose": "CUTOVER_REPLAY"})
    mutation = run_mutation_discovery(
        mutation_run, DiscoveryReplayTransport(artifacts, mutation_run, repository),
        repository, artifacts, _emit(repository, mutation_run), SPEC)

    expression_run = repository.create_run("cutover-stage5", mode="LIVE", fixture_id=None,
                                           fixture_version=None,
                                           scope={"purpose": "EXPRESSION_DISCOVERY"})
    expression = run_expression_discovery(
        expression_run, _ExpressionDelegatingTransport(artifacts, expression_run, repository),
        repository, artifacts, _emit(repository, expression_run), SPEC)

    cnv_run = repository.create_run("cutover-stage6", mode="LIVE", fixture_id=None,
                                    fixture_version=None, scope={"purpose": "CNV_DISCOVERY"})
    cnv = run_cnv_discovery(
        cnv_run, CnvReplayTransport(artifacts, cnv_run, repository),
        repository, artifacts, _emit(repository, cnv_run), SPEC, mutation)
    return mutation, expression, cnv


def test_cutover_composes_one_state_per_survivor_with_bound_lanes(runtime):
    mutation, expression, cnv = _stage_chain(runtime)
    states = compose_discovery_states(mutation, expression, cnv, SPEC)

    assert [state.entity.gene_id for state in states] == list(mutation.survivor_ids)
    ranks = {state.entity.gene_id: state.tested_context.rank_in_lane for state in states}
    assert ranks == {survivor_id: index + 1
                     for index, survivor_id in enumerate(mutation.survivor_ids)}
    for state in states:
        project = state.projects[0]
        assert isinstance(project.cnv, CnvOccurrenceResult)
        assert project.cnv.entity == state.entity
        assert state.quality.acquisition.value == "COMPLETE"
        assert state.universe == mutation.universe
        assert state.research.modalities == (
            "mutation_counts", "expression_summary", "cnv_occurrences")
        assert state.tested_context.selection_rule == "MUTATION_AFFECTED_CASE_COUNT_DESC_V1"
        assert "mutation-first reduction" in state.tested_context.selection_bias
        assert state.sources
        assert set(project.cnv.sources) <= set(state.sources)

    first = states[0]
    payload = write_state(first)
    assert read_state(payload, expected_hash=state_identity(first)) == first
    assert b'"schema_version": 5' in payload or b'"schema_version":5' in payload


def test_composed_states_admit_the_descriptor_actions(runtime):
    mutation, expression, cnv = _stage_chain(runtime)
    states = compose_discovery_states(mutation, expression, cnv, SPEC)
    by_id = {item.action_id: item for item in eligible_actions(states[0], "STATISTICAL_STATE")}
    assert by_id["CHECK_EVIDENCE_INTEGRITY_V1"].eligible is True
    assert by_id["SUMMARIZE_EXPRESSION_TAIL_V1"].eligible is True
    assert by_id["SUMMARIZE_CNV_CATEGORIES_V1"].eligible is True
    assert by_id["SUMMARIZE_EXPRESSION_TAIL_V1"].prerequisites["tail_availability"] == "OBSERVED"

    tail = execute("SUMMARIZE_EXPRESSION_TAIL_V1", states[0], read_artifact=lambda _: None)
    assert tail.checks[0].outcome == "VERIFIED"
    cnv_summary = execute("SUMMARIZE_CNV_CATEGORIES_V1", states[0], read_artifact=lambda _: None)
    assert cnv_summary.checks[0].outcome == "VERIFIED"
    observed = json.loads(cnv_summary.checks[0].observed_json)
    assert observed["conflicting_case_ids"] == [f"{PROJECT}-case-0000"]
    assert [item["raw_category"] for item in observed["categories"]] == [
        "Amplification", "Gain", "Loss"]


def test_cutover_refuses_cross_stage_binding_drift(runtime):
    mutation, expression, cnv = _stage_chain(runtime)
    with pytest.raises(CutoverError, match="SPEC_MISMATCH"):
        compose_discovery_states(
            mutation, dataclasses.replace(expression, spec_id="OTHER_SPEC"), cnv, SPEC)
    with pytest.raises(CutoverError, match="MUTATION_BINDING_MISMATCH"):
        compose_discovery_states(
            mutation, expression, dataclasses.replace(cnv, mutation_discovery_hash="f" * 64), SPEC)
    trimmed = dataclasses.replace(
        cnv, survivor_ids=cnv.survivor_ids[:-1], entries=cnv.entries[:-1])
    with pytest.raises(CutoverError, match="SURVIVOR_MISMATCH"):
        compose_discovery_states(mutation, expression, trimmed, SPEC)
    with pytest.raises(CutoverError, match="SCOPE_MISMATCH"):
        compose_discovery_states(
            mutation, dataclasses.replace(expression, release="Data Release 99.0 - never"), cnv,
            SPEC)