"""Real SQLite/artifact boundary corruption, not mocked scientific outcomes."""

import json

import pytest

from cancerjev.domain.events import canonical_json
from cancerjev.research.dossier import run_dossier_stage
from cancerjev.storage.readers import (
    ScientificReadError,
    read_candidate_state,
    read_revision_chain,
)
from tests.integration.test_deep_slice import _completed_slice


def _candidate(runtime, monkeypatch):
    run_id, _, repository = _completed_slice(runtime, monkeypatch, deep_selection="GENEONE")
    candidate = repository.list_table("candidates", run_id)[0]
    return run_id, repository, candidate


def test_valid_candidate_and_revision_chain_are_typed(runtime, monkeypatch):
    _, repository, candidate = _candidate(runtime, monkeypatch)
    state = read_candidate_state(repository, runtime[2], candidate["candidate_id"])
    chain = read_revision_chain(repository, runtime[2], candidate["candidate_id"])
    assert state.state.scientific_hash == state.scientific_hash
    assert [revision.iteration for revision in chain] == [0, 1]
    assert chain[1].evidence.check_summary.total == 5


@pytest.mark.parametrize("corruption", ["missing", "truncated", "same_size", "wrong_size", "escape"])
def test_state_artifact_corruption_refused(runtime, monkeypatch, corruption):
    _, repository, candidate = _candidate(runtime, monkeypatch)
    row = repository.get_state(candidate["source_state_id"])
    metadata = repository.artifact(row["artifact_id"])
    path = runtime[2].data_dir / metadata["relative_path"]
    if corruption == "missing":
        path.unlink()
    elif corruption == "truncated":
        path.write_bytes(b"{")
    elif corruption == "same_size":
        path.write_bytes(b" " * metadata["size_bytes"])
    else:
        column, value = ("size_bytes", 1) if corruption == "wrong_size" else ("relative_path", "../escape")
        with repository.database.connect(write=True) as connection:
            # Deliberately damaged database, beyond the normal immutable writer boundary.
            connection.execute("DROP TRIGGER artifacts_no_update")
            connection.execute(f"UPDATE artifacts SET {column}=? WHERE artifact_id=?", (value, metadata["artifact_id"]))
    with pytest.raises(ScientificReadError):
        read_candidate_state(repository, runtime[2], candidate["candidate_id"])


@pytest.mark.parametrize("target", ["candidate_entity", "state_identity", "parent", "latest", "summary"])
def test_record_binding_corruption_refused(runtime, monkeypatch, target):
    _, repository, candidate = _candidate(runtime, monkeypatch)
    revisions = repository.evidence_revisions(candidate["candidate_id"])
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER statistical_states_no_update")
        connection.execute("DROP TRIGGER evidence_states_no_update")
        if target == "candidate_entity":
            connection.execute("UPDATE candidates SET entity_json=? WHERE candidate_id=?",
                               (json.dumps({"gene_id": "ENSG00000000000"}), candidate["candidate_id"]))
        elif target == "state_identity":
            connection.execute("UPDATE statistical_states SET state_hash=? WHERE state_id=?",
                               ("0" * 64, candidate["source_state_id"]))
        elif target == "parent":
            connection.execute("UPDATE evidence_states SET previous_evidence_state_id=NULL WHERE evidence_state_id=?",
                               (revisions[1]["evidence_state_id"],))
        elif target == "latest":
            connection.execute("UPDATE candidates SET latest_evidence_state_id=? WHERE candidate_id=?",
                               (revisions[0]["evidence_state_id"], candidate["candidate_id"]))
        else:
            connection.execute("UPDATE evidence_states SET summary_json='{}' WHERE evidence_state_id=?",
                               (revisions[1]["evidence_state_id"],))
    with pytest.raises(ScientificReadError):
        read_revision_chain(repository, runtime[2], candidate["candidate_id"])


def test_latest_corrupt_refuses_dossier_despite_valid_earlier_revision(runtime, monkeypatch):
    run_id, repository, candidate = _candidate(runtime, monkeypatch)
    revisions = repository.evidence_revisions(candidate["candidate_id"])
    latest = repository.artifact(revisions[-1]["artifact_id"])
    (runtime[2].data_dir / latest["relative_path"]).write_bytes(b"{}")
    # Simulate the point before publication; immutable previously published dossier is retained.
    with repository.database.connect(write=True) as connection:
        connection.execute("UPDATE candidates SET status='DEEP_ANALYZED' WHERE candidate_id=?",
                           (candidate["candidate_id"],))
    before = len(repository.list_table("dossiers", run_id))

    def emit(rid, event_type, key, message, **kwargs):
        repository.append_event(rid, event_type=event_type, idempotency_key=key, message=message, **kwargs)

    def publish(*args):
        pytest.fail("corrupt latest evidence must not publish a dossier")

    result = run_dossier_stage(run_id=run_id, candidate=candidate, repository=repository,
                               artifacts=runtime[2], state=None, decisions=[], publish_json=publish, emit=emit)
    assert result["status"] == "UNAVAILABLE"
    assert repository.get_candidate(candidate["candidate_id"])["status"] == "DEEP_ANALYZED"
    assert len(repository.list_table("dossiers", run_id)) == before
    assert repository.events(run_id, 0, 1000)["items"][-1]["type"] == "DOSSIER_UNAVAILABLE"


@pytest.mark.parametrize("schema", [99, "2", True])
def test_unknown_schema_refused_even_with_valid_byte_hash(runtime, monkeypatch, schema):
    _, repository, candidate = _candidate(runtime, monkeypatch)
    state = read_candidate_state(repository, runtime[2], candidate["candidate_id"])
    payload = state.artifact.boundary_representation()
    payload["schema_version"] = schema
    replacement = runtime[2].publish("corrupt-state.json", canonical_json(payload), "application/json", "statistical-state")
    repository.register_artifact(replacement, state.run_id)
    with repository.database.connect(write=True) as connection:
        connection.execute("DROP TRIGGER statistical_states_no_update")
        connection.execute("UPDATE statistical_states SET artifact_id=? WHERE state_id=?",
                           (replacement.artifact_id, state.state_id))
    with pytest.raises(ScientificReadError):
        read_candidate_state(repository, runtime[2], candidate["candidate_id"])
