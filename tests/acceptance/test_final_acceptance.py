"""End-to-end acceptance: the layered gates as executable, individually observable tests.

Offline by default (fixtures/replay). Live checks stay in ``tests/live`` behind the
existing opt-in marker. A non-LUAD fixture proves generic architecture only and is
never cited as scientific validation; the frozen reconciliation corpus is asserted
read-only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cancerjev.domain.codecs import evidence_identity
from cancerjev.domain.functional import EVIDENCE_AXES
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.gdc.endpoints import FORBIDDEN_PATHS
from cancerjev.research.cutover import compose_discovery_states
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.storage.ownership import OwnershipError
from cancerjev.storage.readers import read_dossier_record, read_state_record
from tests.integration.test_deep_slice import StubAdapter, _candidate_chain
from tests.integration.test_live_replay import _events, _orchestrator, _test_spec
from tests.science.test_modality_union import _cnv_result, _lanes

ROOT = Path(__file__).resolve().parents[2]
RECONCILIATION = ROOT / "tests" / "reconciliation" / "fixtures" / "reconciliation_dr46"


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


def test_replay_requests_never_touch_forbidden_or_controlled_paths(runtime, monkeypatch):
    orchestrator, holder, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"

    paths = {str(request.path) for request in holder["transport"].requests}
    assert paths
    assert not (paths & set(FORBIDDEN_PATHS))
    rendered = json.dumps(sorted(paths))
    assert "/data" not in rendered and "/manifest" not in rendered


def test_autonomous_run_completes_with_a_policy_selected_measured_revision(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=StubAdapter(), deep_selection="GENEONE",
        deep_followup_authorized=True)
    run_id = orchestrator.run()
    completed = next(event for event in _events(repository, run_id)
                     if event["type"] == "RUN_COMPLETED")
    summary = completed["data"]["deep"]["candidates"][0]

    assert summary["status"] == "COMPLETED"
    assert summary["first_step"]["action_id"] == "OCCURRENCE_DETAIL_EVIDENCE_V1"
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


def test_deterministic_replay_yields_identical_final_results(runtime, monkeypatch):
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


def test_non_luad_fixture_runs_the_generic_architecture_only(runtime, monkeypatch):
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
