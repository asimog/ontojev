"""Scientific reads: validated readers bind typed records to verified artifacts.

Readers must return typed objects whose ids, hashes and record fields agree with the
immutable artifact bytes; anything else is refused with a typed ``ScientificReadError``.
No reader ever returns a partially verified record.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from cancerjev.config import Settings
from cancerjev.domain.codecs import canonical_bytes, state_identity
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.storage.artifacts import ArtifactStore, artifact_id_for
from cancerjev.storage.database import Database
from cancerjev.storage.readers import (
    ScientificReadError,
    read_candidate_state,
    read_dossier_record,
    read_evaluation_record,
    read_hypothesis_record,
    read_revision_chain,
)
from cancerjev.storage.repositories import Repository
from tests.integration.test_hypothesis_stage import _hypothesis_adapter
from tests.integration.test_live_replay import _api_client, _orchestrator


@pytest.fixture(scope="module")
def _canned_run(tmp_path_factory):
    """Build the canonical hypothesis arc once; each test reads a private copy."""
    data_dir = tmp_path_factory.mktemp("reads-canned")
    settings = Settings(data_dir, 0, 60, "http://localhost:3000")
    database = Database(settings.database_path)
    database.bootstrap()
    repository = Repository(database)
    orchestrator, _, _ = _orchestrator(
        (settings, repository, ArtifactStore(data_dir)), jev_adapter=_hypothesis_adapter(),
        deep_selection="GENEONE", deep_followup_authorized=True,
        deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1")
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    with database.connect(write=True) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return data_dir, run_id, candidate["candidate_id"]


@pytest.fixture
def runtime(tmp_path, _canned_run):
    data_dir = tmp_path / "data"
    shutil.copytree(_canned_run[0], data_dir)
    settings = Settings(data_dir, 0, 60, "http://localhost:3000")
    return settings, Repository(Database(settings.database_path)), ArtifactStore(data_dir)


def _fixture_run(runtime, monkeypatch, **kwargs):
    repository = runtime[1]
    run_id = repository.list_runs()[0]["run_id"]
    candidate = next(row for row in repository.list_table("candidates", run_id)
                     if row["entity"]["gene_symbol"] == "GENEONE")
    return run_id, repository, candidate


def _chain(runtime, repository, candidate):
    return read_revision_chain(repository, runtime[2], candidate["candidate_id"])


def _corrupt_artifact_file(runtime, repository, candidate, mode: str) -> None:
    state_row = repository.get_state(candidate["source_state_id"])
    metadata = repository.artifact(state_row["artifact_id"])
    path = runtime[0].data_dir / metadata["relative_path"]
    if mode == "truncated":
        path.write_bytes(b"{")
    elif mode == "same_size":
        size = metadata["size_bytes"]
        path.write_bytes(b" " * size)
    elif mode == "wrong_size":
        path.write_bytes(b" " * (metadata["size_bytes"] + 3))
    elif mode == "escape":
        with repository.database.connect(write=True) as connection:
            connection.execute("DROP TRIGGER artifacts_no_update")
            connection.execute("UPDATE artifacts SET relative_path='../escape' WHERE artifact_id=?",
                               (metadata["artifact_id"],))
    elif mode == "missing":
        path.unlink()
    else:  # pragma: no cover - programming error
        raise AssertionError(mode)


def _tamper_record(repository, candidate, target: str) -> None:
    with repository.database.connect(write=True) as connection:
        if target == "candidate_entity":
            connection.execute("UPDATE candidates SET entity_json=? WHERE candidate_id=?",
                               (json.dumps({"gene_id": "ENSG00000000000", "gene_symbol": "OTHER"}),
                                candidate["candidate_id"]))
        elif target == "state_identity":
            connection.execute("DROP TRIGGER statistical_states_no_update")
            connection.execute("UPDATE statistical_states SET state_hash=? WHERE state_id=?",
                               ("0" * 64, candidate["source_state_id"]))
        elif target == "state_summary":
            connection.execute("DROP TRIGGER statistical_states_no_update")
            connection.execute("UPDATE statistical_states SET summary_json='{}' WHERE state_id=?",
                               (candidate["source_state_id"],))
        elif target == "parent":
            connection.execute("DROP TRIGGER evidence_states_no_update")
            connection.execute(
                "UPDATE evidence_states SET previous_evidence_state_id=NULL WHERE candidate_id=? "
                "AND iteration=1", (candidate["candidate_id"],))
        elif target == "latest":
            revisions = repository.evidence_revisions(candidate["candidate_id"])
            connection.execute("UPDATE candidates SET latest_evidence_state_id=? WHERE candidate_id=?",
                               (revisions[0]["evidence_state_id"], candidate["candidate_id"]))
        else:  # pragma: no cover - programming error
            raise AssertionError(target)


def test_typed_reads_are_bound_to_verified_ids_and_hashes(runtime, monkeypatch):
    run_id, repository, candidate = _fixture_run(runtime, monkeypatch)
    chain = _chain(runtime, repository, candidate)
    assert [stored.iteration for stored in chain] == [0, 1]
    assert chain[0].parent_id is None
    assert chain[1].parent_id == chain[0].evidence_state_id
    assert candidate["latest_evidence_state_id"] == chain[1].evidence_state_id
    for stored in chain:
        assert hashlib.sha256(stored.artifact.content).hexdigest() == stored.artifact.sha256
        assert stored.record.evidence_state_id == stored.evidence_state_id
        assert stored.record.revision.revision_index == stored.iteration

    state = read_candidate_state(repository, runtime[2], candidate["candidate_id"])
    assert state.state_hash == repository.get_state(candidate["source_state_id"])["state_hash"]
    assert state_identity(state.state) == state.state_hash
    assert hashlib.sha256(state.artifact.content).hexdigest() == state.artifact.sha256

    wide = read_evaluation_record(repository, runtime[2],
                                  repository.page_child(
                                      "jev_evaluations", run_id, 20, None,
                                      {"purpose": "WIDE"})["items"][0]["evaluation_id"])
    assert wide.purpose == "WIDE"
    assert wide.error_code is None
    assert wide.answers is not None
    assert wide.input_ref_id == candidate["source_state_id"]

    hypothesis_evaluation = read_evaluation_record(
        repository, runtime[2],
        repository.page_child("jev_evaluations", run_id, 20, None,
                              {"purpose": "HYPOTHESIS"})["items"][0]["evaluation_id"])
    assert hypothesis_evaluation.purpose == "HYPOTHESIS"
    assert hypothesis_evaluation.error_code is None
    assert hypothesis_evaluation.answers is not None

    hypothesis_row = repository.page_child("hypotheses", run_id, 20, None, {})["items"][0]
    stored_hypothesis = read_hypothesis_record(
        repository, runtime[2], hypothesis_row["hypothesis_id"],
        candidate_id=candidate["candidate_id"], allowed_action_ids=frozenset(ACTION_REGISTRY))
    assert stored_hypothesis.draft.statement == hypothesis_row["hypothesis"]["statement"]
    assert stored_hypothesis.evidence_state_id == chain[1].evidence_state_id

    dossier_row = repository.list_table("dossiers", run_id)[0]
    dossier = read_dossier_record(repository, runtime[2], dossier_row["dossier_id"])
    payload = json.loads(dossier.content)
    assert payload["schema_version"] == 2
    assert payload["evidence_state_ids"] == [stored.evidence_state_id for stored in chain]
    assert payload["hypothesis_ids"] == [row["hypothesis_id"] for row in
                                         repository.page_child("hypotheses", run_id, 20, None, {})["items"]]


@pytest.mark.parametrize(("mode", "code"), [
    ("truncated", "EVIDENCE_ARTIFACT_CORRUPT"),
    ("same_size", "EVIDENCE_ARTIFACT_CORRUPT"),
    ("wrong_size", "EVIDENCE_ARTIFACT_CORRUPT"),
    ("escape", "RECORD_BINDING_MISMATCH"),
    ("missing", "EVIDENCE_ARTIFACT_UNAVAILABLE"),
])
def test_corrupt_artifacts_are_refused(runtime, monkeypatch, mode, code):
    _, repository, candidate = _fixture_run(runtime, monkeypatch)
    _corrupt_artifact_file(runtime, repository, candidate, mode)
    with pytest.raises(ScientificReadError) as failure:
        read_candidate_state(repository, runtime[2], candidate["candidate_id"])
    assert failure.value.code == code
    with pytest.raises(ScientificReadError):
        read_revision_chain(repository, runtime[2], candidate["candidate_id"])


@pytest.mark.parametrize(("target", "code"), [
    ("candidate_entity", "RECORD_BINDING_MISMATCH"),
    ("state_identity", "INVALID_SCIENTIFIC_CONTRACT"),
    ("state_summary", "RECORD_BINDING_MISMATCH"),
    ("parent", "RECORD_BINDING_MISMATCH"),
    ("latest", "RECORD_BINDING_MISMATCH"),
])
def test_record_binding_corruption_is_refused(runtime, monkeypatch, target, code):
    _, repository, candidate = _fixture_run(runtime, monkeypatch)
    _tamper_record(repository, candidate, target)
    with pytest.raises(ScientificReadError) as failure:
        read_revision_chain(repository, runtime[2], candidate["candidate_id"])
    assert failure.value.code == code


@pytest.mark.parametrize("bad_version", [99, "2", True])
def test_unknown_schema_is_refused_even_with_a_consistent_artifact_row(
        runtime, monkeypatch, bad_version):
    run_id, repository, candidate = _fixture_run(runtime, monkeypatch)
    state_row = repository.get_state(candidate["source_state_id"])
    original = repository.artifact(state_row["artifact_id"])
    payload = canonical_bytes({"schema_version": bad_version, "kind": "STATISTICAL_STATE"})
    path = f"runs/{run_id}/states/unknown-schema.json"
    runtime[2].publish(path, payload, "application/json", "corrupt-state")
    digest = hashlib.sha256(payload).hexdigest()
    replacement_id = artifact_id_for(path, digest)
    with repository.database.connect(write=True) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TRIGGER artifacts_no_update")
        connection.execute("DROP TRIGGER statistical_states_no_update")
        connection.execute(
            "UPDATE artifacts SET artifact_id=?, relative_path=?, sha256=?, size_bytes=? "
            "WHERE artifact_id=?",
            (replacement_id, path, digest, len(payload), original["artifact_id"]))
        connection.execute("UPDATE statistical_states SET artifact_id=? WHERE state_id=?",
                           (replacement_id, candidate["source_state_id"]))
    with pytest.raises(ScientificReadError) as failure:
        read_candidate_state(repository, runtime[2], candidate["candidate_id"])
    assert failure.value.code == "UNSUPPORTED_SCHEMA_VERSION"

    client = _api_client(runtime, monkeypatch)
    response = client.get(f"/api/states/{candidate['source_state_id']}")
    assert response.status_code == 503


def test_evaluation_binding_refuses_a_tampered_vector(runtime, monkeypatch):
    run_id, repository, _ = _fixture_run(runtime, monkeypatch)
    evaluation = repository.page_child("jev_evaluations", run_id, 20, None,
                                       {"purpose": "WIDE"})["items"][0]
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER jev_evaluations_no_update")
        connection.execute("UPDATE jev_evaluations SET vector_json='{}' WHERE evaluation_id=?",
                           (evaluation["evaluation_id"],))
    with pytest.raises(ScientificReadError) as failure:
        read_evaluation_record(repository, runtime[2], evaluation["evaluation_id"])
    assert failure.value.code == "RECORD_BINDING_MISMATCH", (
        "the artifact no longer agrees with its recorded vector")


def test_hypothesis_binding_refuses_a_tampered_record(runtime, monkeypatch):
    run_id, repository, candidate = _fixture_run(runtime, monkeypatch)
    hypothesis_row = repository.page_child("hypotheses", run_id, 20, None, {})["items"][0]
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER hypotheses_no_update")
        connection.execute("UPDATE hypotheses SET hypothesis_json='{}' WHERE hypothesis_id=?",
                           (hypothesis_row["hypothesis_id"],))
    with pytest.raises(ScientificReadError) as failure:
        read_hypothesis_record(
            repository, runtime[2], hypothesis_row["hypothesis_id"],
            candidate_id=candidate["candidate_id"],
            allowed_action_ids=frozenset(ACTION_REGISTRY))
    assert failure.value.code == "RECORD_BINDING_MISMATCH", (
        "the artifact no longer agrees with its recorded hypothesis")


def test_dossier_refuses_a_corrupt_authoritative_revision(runtime, monkeypatch):
    from cancerjev.research.dossier import run_dossier_stage

    run_id, repository, candidate = _fixture_run(runtime, monkeypatch)
    chain = _chain(runtime, repository, candidate)
    latest_metadata = repository.artifact(repository.get_evidence_state(
        chain[1].evidence_state_id)["artifact_id"])
    (runtime[0].data_dir / latest_metadata["relative_path"]).write_bytes(
        b" " * latest_metadata["size_bytes"])
    with repository.database.connect(write=True) as connection:
        connection.execute("UPDATE candidates SET status='DEEP_ANALYZED' WHERE candidate_id=?",
                           (candidate["candidate_id"],))
    dossiers_before = len(repository.list_table("dossiers", run_id))

    def never_publish(*args):
        raise AssertionError("a refused dossier never publishes")

    result = run_dossier_stage(run_id=run_id, candidate=repository.get_candidate(
        candidate["candidate_id"]), repository=repository, artifacts=runtime[2],
        decisions=[], publish_json=never_publish,
        emit=lambda rid, event_type, key, message, **kwargs: repository.append_event(
            rid, event_type=event_type, idempotency_key=key, message=message, **kwargs))
    assert result["status"] == "UNAVAILABLE"
    assert result["error_code"] in {"EVIDENCE_ARTIFACT_CORRUPT", "RECORD_BINDING_MISMATCH"}
    assert repository.get_candidate(candidate["candidate_id"])["status"] == "DEEP_ANALYZED"
    assert len(repository.list_table("dossiers", run_id)) == dossiers_before
    assert repository.events(run_id, 0, 900)["items"][-1]["type"] == "DOSSIER_UNAVAILABLE"


def test_deep_evaluations_are_bound_to_the_candidate_they_judged(runtime, monkeypatch):
    run_id, repository, _ = _fixture_run(runtime, monkeypatch)
    deep = repository.page_child("jev_evaluations", run_id, 20, None,
                                 {"purpose": "DEEP"})["items"]
    assert len(deep) == 1
    stored = read_evaluation_record(repository, runtime[2], deep[0]["evaluation_id"])
    assert stored.purpose == "DEEP"
    assert stored.error_code is None
    assert stored.answers is not None