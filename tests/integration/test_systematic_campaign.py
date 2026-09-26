"""Canonical systematic Campaign execution over provider-shaped replay bytes.

The real executor runs the real mutation, expression and CNV lanes, the terminal
CNV merge, the deterministic modality union, canonical state persistence and the
Wide handoff. Assertions protect the canonical spine: every lane executes, the
union is reached, states use the one canonical representation, the legacy
GDC_FAST_SEARCH path is not the autonomous science path, the pre-Wide boundary
never truncates, and replay stays deterministic.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.events import canonical_json
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.jev.service import JevService
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.cutover import UNION_SELECTION_RULE_ID
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.research.systematic import run_systematic_campaign
from cancerjev.storage.ownership import OwnershipError
from cancerjev.storage.readers import read_state_record
from tests.helpers import canned_capability
from tests.integration.replay import ReplayTransport
from tests.jev.stub_adapter import StubAdapter

VALIDATED_TEST_PROFILE = replace(
    LUAD_CAMPAIGN_V1, profile_id="LUAD_CAMPAIGN_SYSTEMATIC_TEST",
    readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE,
    readiness_reason="offline test profile; production LUAD readiness is unchanged",
)


def _execute(runtime, *, max_states=None, ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS):
    settings, repository, artifacts = runtime
    run_id = repository.create_run(
        "campaign-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "SYSTEMATIC_CAMPAIGN"}, ownership=ownership)
    transport = ReplayTransport(artifacts, run_id, repository=repository)
    events: list[dict] = []

    def emit(target_run_id, event_type, key, message, **kwargs):
        events.append(repository.append_event(target_run_id, event_type=event_type,
                                              idempotency_key=key, message=message, **kwargs))

    def publish_json(target_run_id, path, payload, purpose):
        content = payload if isinstance(payload, bytes) else canonical_json(payload)
        return artifacts.publish(path, content, "application/json", purpose)

    result = run_systematic_campaign(
        run_id=run_id, profile=VALIDATED_TEST_PROFILE, spec=LUAD_RESEARCH_V1,
        capability=canned_capability(), settings=settings, repository=repository,
        artifacts=artifacts, emit=emit, publish_json=publish_json,
        jev_service=JevService(settings, repository, artifacts,
                               adapter_factory=lambda: StubAdapter()),
        transport_factory=lambda repo, arts, budget, rid, emitter: transport,
        max_states=max_states)
    return run_id, transport, events, result


def test_canonical_campaign_runs_every_modality_and_the_union(runtime):
    _, repository, _ = runtime
    run_id, transport, events, result = _execute(runtime)
    types = [event["type"] for event in events]

    assert result.mutation_survivors, "the mutation lane produced survivors"
    assert result.cnv_shards == 4, "100 cases partition into four 25-case shards"
    assert result.state_ids, "the modality union produced states"
    assert result.union_selection_rule == UNION_SELECTION_RULE_ID
    assert result.wide is not None, "the canonical path reaches Wide evaluation"
    assert len(result.state_ids) >= 2, "both mutation survivors are union states"

    for expected in ("DISCOVERY_STARTED", "DISCOVERY_COMPLETED",
                     "EXPRESSION_DISCOVERY_STARTED", "EXPRESSION_DISCOVERY_COMPLETED",
                     "CNV_SHARD_SCAN_COMPLETED", "CNV_PROJECT_SCAN_COMPLETED",
                     "STATISTICAL_STATE_CREATED", "JEV_WIDE_STARTED", "JEV_WIDE_COMPLETED"):
        assert expected in types, f"missing canonical event {expected}"
    assert types.count("CNV_SHARD_SCAN_COMPLETED") == result.cnv_shards

    requested = [request.endpoint.name for request in transport.requests]
    assert "ssm_occurrences" in requested
    assert "gene_expression_values" in requested
    assert "cnv_occurrences" in requested
    assert repository.get_run(run_id)["status"] == "PENDING", "the CLI owns the run terminal state"


def test_union_states_use_the_canonical_persistence(runtime):
    _, repository, artifacts = runtime
    run_id, _, _, result = _execute(runtime)

    rows = repository.list_table("statistical_states", run_id)
    assert [row["state_id"] for row in rows] == list(result.state_ids)
    by_hash: dict[str, str] = {}
    for row in rows:
        stored = read_state_record(repository, artifacts, row["state_id"])
        by_hash[stored.state_hash] = stored.state_id
        assert stored.record.state_hash == row["state_hash"]
        state = stored.state
        assert state.research.gene_selection_rule == UNION_SELECTION_RULE_ID
        assert state.tested_context.selection_rule == UNION_SELECTION_RULE_ID
        assert state.research.modalities == (
            "mutation_counts", "expression_summary", "cnv_occurrences")
        assert state.nominations, "every union state carries its modality nominations"
        assert {modality for modality, _ in state.nominations} <= {
            "mutation", "expression", "cnv"}
    assert len(by_hash) == len(rows), "every union state is distinct and re-readable"


def test_gdc_fast_search_is_not_the_autonomous_science_path(runtime):
    _, repository, _ = runtime
    run_id, transport, events, _ = _execute(runtime)
    assert "GDC_FAST_SEARCH" not in {event["stage"] for event in events if event["stage"]}
    assert "WIDE_SCAN_COMPLETED" not in [event["type"] for event in events]
    endpoints = {request.endpoint.name for request in transport.requests}
    assert "top_cases_counts_by_genes" not in endpoints, \
        "the retired count-bucket endpoint is never a canonical source"
    assert repository.get_run(run_id)["purpose"] == "SYSTEMATIC_CAMPAIGN"


def test_pre_wide_boundary_cuts_by_measured_evidence_and_never_truncates(runtime):
    _, repository, _ = runtime
    run_id, _, events, result = _execute(runtime)
    assert len(result.state_ids) >= 2
    assert result.pre_wide.reason_code == "WITHIN_CEILING"

    cut_run, _, cut_events, cut_result = _execute(runtime, max_states=1)
    assert cut_result.pre_wide.considered >= 2
    assert len(cut_result.pre_wide.states) == 1
    assert cut_result.pre_wide.reason_code == "CUT_AT_MEASURED_ORDERING"
    excluded = {entry["state_id"] for entry in cut_result.pre_wide.excluded}
    assert excluded, "the cut records the excluded states explicitly"
    assert all(entry["reason"] == "BELOW_PRE_WIDE_CUTOFF"
               for entry in cut_result.pre_wide.excluded)
    assert cut_result.pre_wide.states[0].state_id not in excluded

    persisted = repository.list_table("statistical_states", cut_run)
    assert len(persisted) == cut_result.pre_wide.considered, \
        "the complete union stays persisted even when Wide is bounded"
    recorded = [event for event in cut_events
                if event["type"] == "PRE_WIDE_SELECTION_RECORDED"]
    assert len(recorded) == 1
    data = recorded[0]["data"]
    assert data["policy_version"] == "pre-wide-policy-v1"
    assert data["considered"] == cut_result.pre_wide.considered
    assert data["selected"] == 1 and data["excluded"] == len(excluded)
    evaluations = repository.list_table("jev_evaluations", cut_run)
    selected_state_id = cut_result.pre_wide.states[0].state_id
    assert [row for row in evaluations if row["input_ref_id"] == selected_state_id]
    assert not [row for row in evaluations if row["input_ref_id"] in excluded], \
        "only the selected population reaches Wide Jev"
    assert "JEV_WIDE_STARTED" in [event["type"] for event in events]


def test_replay_determinism_is_stable(runtime):
    _, repository, artifacts = runtime
    first = _execute(runtime)
    second = _execute(runtime)

    def projection(run_id, state_ids):
        rows = []
        for state_id in state_ids:
            state = read_state_record(repository, artifacts, state_id).state
            cnv_disposition = None
            for project in state.projects:
                cnv_disposition = getattr(project.cnv, "disposition", None)
            rows.append((
                state.entity.gene_id,
                tuple(state.nominations or ()),
                state.universe.membership_hash,
                state.tested_context.rank_in_lane,
                state.research.gene_selection_rule,
                state.quality.acquisition.value,
                state.cross_project.affected_case_total.value,
                cnv_disposition,
            ))
        return rows

    assert first[3].mutation_survivors == second[3].mutation_survivors
    assert first[3].union_selection_rule == second[3].union_selection_rule
    assert projection(first[0], first[3].state_ids) == projection(second[0], second[3].state_ids)
    assert first[3].pre_wide.payload() == second[3].pre_wide.payload()
    first_genes = [record["entity"]["gene_id"]
                   for record in repository.list_table("candidates", first[0])]
    second_genes = [record["entity"]["gene_id"]
                    for record in repository.list_table("candidates", second[0])]
    assert first_genes == second_genes


def test_researcher_ownership_is_refused(runtime):
    with pytest.raises(OwnershipError):
        _execute(runtime, ownership=ExecutionOwnership.RESEARCHER_RUN)
