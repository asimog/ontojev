"""End-to-end acceptance: the layered gates as executable, individually observable tests.

Offline by default (fixtures/replay). Live checks stay in ``tests/live`` behind the
existing opt-in marker. Canonical autonomous evidence is asserted only for tests that
drive ``run_systematic_campaign`` end-to-end; tests that drive the legacy
``LiveOrchestrator`` are labelled comparator-path regressions and are never cited as
autonomy evidence. A non-LUAD fixture proves generic architecture only and is never
cited as scientific validation; the frozen reconciliation corpus is asserted
read-only.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cancerjev.domain.codecs import evidence_identity
from cancerjev.domain.functional import EVIDENCE_AXES
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.domain.scientific import (
    CnvProjectFinding,
    MutationCountResult,
    UnavailableLane,
    UnavailableStatus,
)
from cancerjev.gdc.endpoints import FORBIDDEN_PATHS
from cancerjev.research.cutover import UNION_SELECTION_RULE_ID, compose_discovery_states
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.storage.ownership import OwnershipError
from cancerjev.storage.readers import read_dossier_record, read_state_record
from tests.integration.test_deep_slice import StubAdapter, _candidate_chain
from tests.integration.test_live_replay import _events, _orchestrator, _test_spec
from tests.integration.test_systematic_campaign import _execute as _execute_campaign
from tests.science.test_modality_union import _cnv_result, _lanes

ROOT = Path(__file__).resolve().parents[2]
RECONCILIATION = ROOT / "tests" / "reconciliation" / "fixtures" / "reconciliation_dr46"
GENE_ONE, GENE_TWO = "ENSG00000000001", "ENSG00000000002"
EXPRESSION_ONLY_GENE = "ENSG00000000003"
# The canonical replay transport options that exercise all three modalities: a
# widened expression universe with a declared excess over the pooled null in one
# mutation survivor and one expression-only gene.
CANONICAL_TRANSPORT_OPTIONS = {
    "expression_only_gene": EXPRESSION_ONLY_GENE, "expression_extra_genes": 9,
    "heavy_tail_cases": {GENE_ONE: 5, EXPRESSION_ONLY_GENE: 5},
}
EXPECTED_CANONICAL_UNION = {
    GENE_ONE: (("cnv", "RETAIN"), ("expression", "RETAIN"), ("mutation", "RETAINED")),
    GENE_TWO: (("mutation", "RETAINED"),),
    EXPRESSION_ONLY_GENE: (("expression", "RETAIN"),),
}


def _assert_canonical_union(result, repository, artifacts):
    """Exact union membership and nominations read back through the validated readers.

    Ports the ``tests/science/test_modality_union.py`` assertions onto the canonical
    campaign boundary: every nominated modality is present with its exact disposition,
    the expression-only member is retained with an observed zero mutation count and a
    NOT_OBSERVED CNV lane, and a dropped CNV call never appears as a nomination.
    """
    states = {state_id: read_state_record(repository, artifacts, state_id).state
              for state_id in result.state_ids}
    union = {state.entity.gene_id: tuple(state.nominations) for state in states.values()}
    assert union == EXPECTED_CANONICAL_UNION, \
        "the canonical union is exactly the per-modality nominations"
    for state in states.values():
        assert state.research.gene_selection_rule == UNION_SELECTION_RULE_ID
        assert state.tested_context.selection_rule == UNION_SELECTION_RULE_ID

    expression_only = next(state for state in states.values()
                           if state.entity.gene_id == EXPRESSION_ONLY_GENE)
    mutation_lane = expression_only.projects[0].mutation
    assert isinstance(mutation_lane, MutationCountResult)
    assert mutation_lane.affected_cases.value == 0, \
        "the complete scan observes zero occurrences; it never infers absence"
    cnv_lane = expression_only.projects[0].cnv
    assert isinstance(cnv_lane, UnavailableLane)
    assert cnv_lane.status is UnavailableStatus.NOT_OBSERVED

    dropped = next(state for state in states.values() if state.entity.gene_id == GENE_TWO)
    dropped_lane = dropped.projects[0].cnv
    assert isinstance(dropped_lane, CnvProjectFinding)
    assert dropped_lane.disposition == "DROP" and dropped_lane.review_trigger is None
    assert ("cnv", "DROP") not in dropped.nominations

    retained = next(state for state in states.values() if state.entity.gene_id == GENE_ONE)
    retained_lane = retained.projects[0].cnv
    assert isinstance(retained_lane, CnvProjectFinding)
    assert retained_lane.disposition == "RETAIN"
    return states



def test_frozen_reconciliation_corpus_is_read_only_evidence():
    manifest = json.loads((RECONCILIATION / "MANIFEST.json").read_text(encoding="utf-8"))
    body_files = sorted(RECONCILIATION.glob("*.body"))
    assert body_files, "the frozen corpus must exist"
    assert manifest["release"].startswith("Data Release")
    assert manifest["project"] == "TCGA-LUAD"
    assert manifest["panel"] and manifest["rows"] and manifest["records"]
    assert all(body.stat().st_size > 0 for body in body_files)


def test_modality_union_states_carry_levels_nominations_and_axes(runtime):
    from cancerjev.domain.scientific import EVIDENCE_LEVEL_ORDER

    mutation, expression = _lanes(runtime)
    states = compose_discovery_states(mutation, expression, _cnv_result(mutation, ()),
                                      LUAD_RESEARCH_V1)

    assert states
    known_levels = {member.value for member in EVIDENCE_LEVEL_ORDER}
    for state in states:
        assert state.evidence_level in known_levels
        assert state.nominations
    assert expression.workflow_coverage_complete is True
    assert expression.workflow_file_counts
    assert len(EVIDENCE_AXES) == len(set(EVIDENCE_AXES))


def test_canonical_executor_union_membership_and_nominations_are_exact(runtime):
    """Autonomous acceptance evidence comes from the canonical executor alone."""
    _, repository, artifacts = runtime
    _, _, _, result = _execute_campaign(runtime, transport_options=CANONICAL_TRANSPORT_OPTIONS)

    assert result.activation == "AUTONOMOUS"
    assert result.run_id
    states = _assert_canonical_union(result, repository, artifacts)
    assert len(states) == len(EXPECTED_CANONICAL_UNION)
    assert result.mutation_survivors == (GENE_ONE, GENE_TWO), \
        "the expression-only member is never a mutation survivor"
    assert result.cnv_shards == 4 and result.cnv_calls == 2


def test_corrupted_union_probe_fails_the_canonical_union_guarantee(runtime, monkeypatch):
    """Must-fail regression for the R2-02 probe: a union that drops every
    non-mutation nomination and non-mutation state must not pass acceptance."""
    real_compose = compose_discovery_states

    def corrupted(mutation, expression, cnv, spec):
        states = real_compose(mutation, expression, cnv, spec)
        mutation_only = [
            replace(state, nominations=tuple(
                (modality, disposition) for modality, disposition in state.nominations
                if modality == "mutation"))
            for state in states
        ]
        return [state for state in mutation_only if state.nominations]

    monkeypatch.setattr("cancerjev.research.systematic.compose_discovery_states", corrupted)
    _, repository, artifacts = runtime
    _, _, _, result = _execute_campaign(runtime, transport_options=CANONICAL_TRANSPORT_OPTIONS)

    assert len(result.state_ids) >= 2, \
        "the pre-fix in-lane assertion alone cannot tell the corrupted union apart"
    with pytest.raises(AssertionError, match="exactly the per-modality nominations"):
        _assert_canonical_union(result, repository, artifacts)


def test_corrupted_nominations_probe_fails_without_dropping_states(runtime, monkeypatch):
    """A union that keeps every state but drops non-mutation nominations must fail."""
    real_compose = compose_discovery_states

    def corrupted(mutation, expression, cnv, spec):
        return [
            replace(state, nominations=tuple(
                (modality, disposition) for modality, disposition in state.nominations
                if modality == "mutation"))
            for state in real_compose(mutation, expression, cnv, spec)
        ]

    monkeypatch.setattr("cancerjev.research.systematic.compose_discovery_states", corrupted)
    _, repository, artifacts = runtime
    _, _, _, result = _execute_campaign(runtime, transport_options=CANONICAL_TRANSPORT_OPTIONS)

    assert len(result.state_ids) == len(EXPECTED_CANONICAL_UNION), \
        "membership is unchanged; only the nominations were corrupted"
    with pytest.raises(AssertionError, match="exactly the per-modality nominations"):
        _assert_canonical_union(result, repository, artifacts)


def test_comparator_path_requests_never_touch_forbidden_or_controlled_paths(runtime, monkeypatch):
    """Legacy LiveOrchestrator comparator path: request safety, not autonomy evidence."""
    orchestrator, holder, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"

    paths = {str(request.path) for request in holder["transport"].requests}
    assert paths
    assert not (paths & set(FORBIDDEN_PATHS))
    rendered = json.dumps(sorted(paths))
    assert "/data" not in rendered and "/manifest" not in rendered


def test_comparator_path_run_completes_with_a_policy_selected_measured_revision(runtime, monkeypatch):
    """Legacy LiveOrchestrator comparator path: deep-slice revision behaviour only.

    This is a RESEARCHER_RUN with operator selection and a stub Jev; it is
    comparator-path regression coverage and never autonomous acceptance evidence.
    """
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE",
        deep_followup_authorized=True)
    run_id = orchestrator.run()
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    summary = completed["data"]["deep"]["candidates"][0]

    assert summary["status"] == "ABSTAINED"
    assert summary["final_move"] == "ABSTAIN"
    assert summary["stop_reason"] == "DEEP_JUDGMENT_UNAVAILABLE"
    assert summary["first_step"]["action_id"] == "OCCURRENCE_DETAIL_EVIDENCE_V1"
    assert summary["decisions"][0]["dimensions"]["revision_reliable"] is None, \
        "an inapplicable reliability answer cannot authorize continuation"
    candidate = repository.get_candidate(summary["candidate_id"])
    chain = _candidate_chain(runtime, repository, candidate)
    assert [stored.evidence.revision_index for stored in chain] == [0, 1, 2][:len(chain)]
    revision = chain[-1].evidence
    assert revision.measured_observations
    assert revision.action is not None

    dossier = read_dossier_record(repository, runtime[2], candidate["dossier_id"])
    text = dossier.content.decode("utf-8").lower()
    assert "computational target candidate" in text
    assert "not an experimentally or therapeutically validated target" in text


def test_comparator_path_deterministic_replay_yields_identical_final_results(runtime, monkeypatch):
    """Legacy LiveOrchestrator comparator path: deterministic replay only."""
    hashes = []
    for _ in range(2):
        orchestrator, _, repository = _orchestrator(
            runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE",
            deep_followup_authorized=True)
        run_id = orchestrator.run()
        completed = next(event for event in _events(repository, run_id)
                         if event["type"] == "RUN_COMPLETED")
        summary = completed["data"]["deep"]["candidates"][0]
        candidate = repository.get_candidate(summary["candidate_id"])
        chain = _candidate_chain(runtime, repository, candidate)
        hashes.append((evidence_identity(chain[-1].evidence), summary["status"]))
    assert hashes[0] == hashes[1]


def test_ownership_boundary_fails_closed_in_both_directions(runtime):
    _, repository, _ = runtime
    autonomous = repository.create_run("acceptance", mode="LIVE", fixture_id=None,
                                       fixture_version=None, scope={"purpose": "ACCEPTANCE"})
    researcher = repository.create_run("acceptance", mode="LIVE", fixture_id=None,
                                       fixture_version=None, scope={"purpose": "ACCEPTANCE"},
                                       ownership=ExecutionOwnership.RESEARCHER_RUN)
    repository.require_run_ownership(autonomous, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    repository.require_run_ownership(researcher, ExecutionOwnership.RESEARCHER_RUN)
    with pytest.raises(OwnershipError):
        repository.require_run_ownership(autonomous, ExecutionOwnership.RESEARCHER_RUN)
    with pytest.raises(OwnershipError):
        repository.require_run_ownership(researcher, ExecutionOwnership.SYSTEM_AUTONOMOUS)


def test_comparator_path_non_luad_fixture_runs_the_generic_architecture_only(runtime, monkeypatch):
    """Legacy LiveOrchestrator comparator path on a non-LUAD fixture: generic proof only."""
    spec = _test_spec("TCGA-LUSC")
    orchestrator, _, repository = _orchestrator(runtime, monkeypatch, research_spec=spec)
    run_id = orchestrator.run()

    assert repository.get_run(run_id)["status"] == "COMPLETED"
    rows = repository.list_table("statistical_states", run_id)
    assert rows, "the generic path still produces typed states"
    states = [read_state_record(repository, runtime[2], row["state_id"]).state for row in rows]
    assert all(state.research.project_id == "TCGA-LUSC" for state in states)
    # Non-LUAD evidence is generic-architecture proof only; the validated campaign
    # profile remains the only autonomous candidate and stays EXPERIMENTAL.
    from cancerjev.domain.capability import ScientificReadiness
    from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
    assert LUAD_CAMPAIGN_V1.readiness is ScientificReadiness.EXPERIMENTAL
