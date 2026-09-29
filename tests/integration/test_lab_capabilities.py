"""Director-selected canonical science persists across independent lab processes."""

import json

import pytest

from cancerjev.domain.codecs import read_discovery, read_expression_discovery
from cancerjev.jev.service import JevService
from cancerjev.research.lab_acquisition import CNV_LAB_METHOD, ShardArtifactStore
from cancerjev.research.lab_capabilities import EXPRESSION, MUTATION, ScientificLabCapabilities
from cancerjev.research.lab_runtime import RunClock, run_block
from cancerjev.research.lab_stages import COMPOSE, INVESTIGATE, MERGE, WIDE, read_stage
from cancerjev.research.laboratory import load_lab
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.readers import (
    ScientificReadError,
    read_candidate_state,
    read_dossier_record,
    read_revision_chain,
    read_state_record,
)
from cancerjev.storage.repositories import Repository
from tests.integration.replay import GENES, ReplayTransport
from tests.integration.test_laboratory import ReplayDirector, block, decision
from tests.jev.stub_adapter import StubAdapter


class SelectCapability(ReplayDirector):
    def __init__(self, method):
        self.method = method
        self.projection = None

    def decide(self, projection, *, timeout):
        self.projection = projection
        offer = next(o for o in projection["offers"] if o["method"] == self.method
                     and (self.method != CNV_LAB_METHOD or len(o["cases"]) == 25))
        return decision("EXECUTE", question_id="q1", offer_id=offer["offer_id"])


def execute(runtime, method):
    settings, _, _ = runtime
    # Reopen stores and reconstruct every adapter; continuation uses no in-memory science.
    repository = Repository(Database(settings.database_path))
    artifacts = ArtifactStore(settings.data_dir)
    run_id = repository.create_run("lab-test", scope={"purpose": "LAB"})
    repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="start", message="Replay.")
    clock = RunClock()
    transport = ReplayTransport(ShardArtifactStore(settings.data_dir, run_id), run_id,
                                repository=repository)
    capabilities = ScientificLabCapabilities(repository, artifacts, run_id, transport, clock,
        JevService(settings, repository, artifacts, adapter_factory=lambda: StubAdapter()))
    director = SelectCapability(method)
    state = run_block(repository, artifacts, run_id, director, capabilities, clock)
    repository.append_event(run_id, event_type="RUN_COMPLETED", idempotency_key="complete", message="Replay complete.")
    return run_id, state, director.projection


@pytest.mark.parametrize("methods", [(MUTATION, EXPRESSION), (EXPRESSION, MUTATION)])
def test_director_selects_canonical_lanes_across_restart(runtime, methods):
    _, repository, artifacts = runtime
    block(runtime, ReplayDirector(decision()))
    previous = []
    for method in methods:
        run_id, state, projection = execute(runtime, method.method)
        assert state.operational_state == "READY"
        assert projection["evidence_ids"] == previous
        assert len(projection["evidence_summaries"]) == len(previous)
        row = repository.artifact(state.evidence_ids[-1])
        raw = artifacts.read(row["relative_path"], row["sha256"])
        result = read_discovery(raw) if method == MUTATION else read_expression_discovery(raw)
        assert {entry.entity.gene_id for entry in result.entries} == set(GENES)
        assert result.project_id == "TCGA-LUAD"
        assert result.universe.complete
        assert row["purpose"] == method.result_purpose
        assert row["relative_path"] == f"runs/{run_id}/{method.result_path}"
        assert not (artifacts.data_dir / "shards" / run_id).exists()
        provenance = repository.artifact_at_path(f"runs/{run_id}/lab/scientific-acquisition.json")
        document = json.loads(artifacts.read(provenance["relative_path"], provenance["sha256"]))
        assert document["evidence_sha256"] == row["sha256"]
        endpoints = {request["endpoint"] for request in document["requests"]}
        assert ("/ssm_occurrences" if method == MUTATION else "/gene_expression/values") in endpoints
        previous = list(state.evidence_ids)
    assert load_lab(repository, artifacts).evidence_ids == tuple(previous)
    # Both modalities can now be cited by a director; its interpretation remains control state.
    _, interpreted = block(runtime, ReplayDirector(decision(
        "INTERPRET", question_id="q1", interpretation={
            "question_id": "q1", "evidence_ids": previous,
            "conclusion": "Two canonical evidence axes are available for composition.",
            "uncertainty": ["A complete CNV lane has not been acquired."],
        })))
    assert interpreted.interpretations[-1].evidence_ids == tuple(previous)


def test_corrupt_cross_run_evidence_is_rejected_before_director(runtime):
    _, repository, artifacts = runtime
    block(runtime, ReplayDirector(decision()))
    _, state, _ = execute(runtime, MUTATION.method)
    row = repository.artifact(state.evidence_ids[-1])
    (artifacts.data_dir / row["relative_path"]).write_bytes(b"{}")
    with pytest.raises(OSError, match="artifact size mismatch"):
        execute(runtime, EXPRESSION.method)
    assert load_lab(repository, artifacts).revision == state.revision


def test_cross_run_multimodal_composition_wide_and_candidate_admission(runtime):
    _, repository, artifacts = runtime
    block(runtime, ReplayDirector(decision()))
    # A deliberate expression-first trajectory, with a restart at every operation.
    for method in (EXPRESSION.method, MUTATION.method, *(CNV_LAB_METHOD,) * 4, MERGE, COMPOSE):
        _, state, projection = execute(runtime, method)
        if method == COMPOSE:
            composition = read_stage(repository, artifacts, state.evidence_ids[-1])
            before = {identity: read_state_record(repository, artifacts, identity)
                      for identity in composition.state_ids}
            assert {item.state.entity.gene_id for item in before.values()} == set(GENES)
            assert any(dict(item.state.nominations).get("cnv") == "RETAIN" for item in before.values())
    run_id, state, projection = execute(runtime, WIDE)
    wide = read_stage(repository, artifacts, state.evidence_ids[-1])
    assert wide.candidate_ids
    assert {read_state_record(repository, artifacts, identity).state_hash for identity in wide.state_ids} == {
        item.state_hash for item in before.values()}
    for candidate_id in wide.candidate_ids:
        accepted = read_candidate_state(repository, artifacts, candidate_id)
        assert accepted.run_id == run_id
        assert accepted.state_hash in {item.state_hash for item in before.values()}
    for identity, original in before.items():
        assert read_state_record(repository, artifacts, identity) == original
    # Wide returns scientific judgment to the director without converting it into measurements.
    _, interpreted = block(runtime, ReplayDirector(decision("INTERPRET", question_id="q1", interpretation={
        "question_id": "q1", "evidence_ids": [state.evidence_ids[-1]],
        "conclusion": "Investigate the admitted canonical Candidates.",
        "uncertainty": ["Wide is semantic judgment, not biological validation."],
    })))
    assert interpreted.interpretations[-1].evidence_ids == (state.evidence_ids[-1],)
    deep_run, state, _ = execute(runtime, INVESTIGATE)
    investigation = read_stage(repository, artifacts, state.evidence_ids[-1])
    candidate_id = investigation.candidate_ids[0]
    assert repository.get_candidate(candidate_id)["status"] == "CANDIDATE_COMPLETE"
    chain = read_revision_chain(repository, artifacts, candidate_id)
    assert len(chain) >= 2
    assert chain[0].record.revision.accepted_state_hash in {item.state_hash for item in before.values()}
    dossiers = repository.list_table("dossiers", deep_run)
    assert len(dossiers) == 1
    read_dossier_record(repository, artifacts, dossiers[0]["dossier_id"])
    # The same director loop continues after a completed dossier, with no CLI scientific flags.
    next_question = decision().question.model_copy(update={"question_id": "q2", "project_id": "TCGA-LUSC"})
    _, next_state = block(runtime, ReplayDirector(decision(question=next_question)))
    assert {question.question_id for question in next_state.questions} == {"q1", "q2"}
    binding = repository.artifact_at_path(f"runs/{deep_run}/lab/candidate-binding.json")
    (artifacts.data_dir / binding["relative_path"]).unlink()
    with pytest.raises(ScientificReadError, match="EVIDENCE_ARTIFACT_UNAVAILABLE"):
        read_revision_chain(repository, artifacts, candidate_id)
