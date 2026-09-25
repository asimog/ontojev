"""Hypothesis stage integration: bounded generation, labelled text, one review each.

Template generation is the default and is deterministic. An injected generator is
untrusted input: malformed output is a typed UNAVAILABLE outcome, nothing is persisted
partially, and generated text never writes a measured field. Each stored hypothesis is
judged exactly once under ``hypothesis-v2``.
"""

from __future__ import annotations

import json

import pytest

from cancerjev.domain.hypotheses import DRAFT_FIELDS
from cancerjev.research.hypotheses import (
    LIVE_HYPOTHESIS_LABEL,
    LLM_HYPOTHESIS_LABEL,
    TEMPLATE_GENERATOR,
)
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.storage.readers import read_hypothesis_record
from tests.integration.test_live_replay import (
    _api_client,
    _events,
    _orchestrator,
)
from tests.jev.stub_adapter import StubAdapter

HYPOTHESIS_ANSWERS = {
    "hypothesis_testable", "hypothesis_exceeds_recorded_evidence",
    "hypothesis_dominant_unsupported_assumption",
}


def _hypothesis_adapter(*, stopping: float = 0.2, warranted: float = 0.2,
                        sufficient: float = 0.8, reliable: float = 0.9) -> StubAdapter:
    return StubAdapter(
        override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}},
        deep_override={
            "stopping_more_honest": {"kind": "noul", "probability_yes": stopping},
            "next_step_warranted": {"kind": "noul", "probability_yes": warranted},
            "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": sufficient},
            "revision_reliable": {"kind": "noul", "probability_yes": reliable},
        },
    )


def _run(runtime, monkeypatch, *, jev_adapter=None, authorized=True, hypotheses_requested=False,
         llm_generator=None, **replay_options):
    adapter = jev_adapter if jev_adapter is not None else _hypothesis_adapter()
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=adapter, deep_selection="GENEONE",
        deep_followup_authorized=authorized, deep_hypotheses_requested=hypotheses_requested,
        llm_generator=llm_generator, **replay_options)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    deep = next(event for event in _events(repository, run_id)
                if event["type"] == "RUN_COMPLETED")["data"]["deep"]
    assert deep["candidate_count"] == 1
    return run_id, deep["candidates"][0], repository


def _hypothesis_rows(repository, run_id, candidate_id=None):
    return repository.page_child("hypotheses", run_id, 100, None,
                                 {"candidate_id": candidate_id})["items"]


def _evaluations(repository, run_id, purpose):
    return repository.page_child("jev_evaluations", run_id, 100, None,
                                 {"purpose": purpose})["items"]


def _dossier(runtime, repository, run_id, candidate_id):
    row = next(item for item in repository.list_table("dossiers", run_id)
               if item["candidate_id"] == candidate_id)
    return json.loads(runtime[2].read(repository.artifact(row["json_artifact_id"])["relative_path"]))


def _generator(entries, *, name=None, usage=None):
    payload = entries if usage is None else (entries, usage)

    def generate(request):
        generate.requests.append(request)
        return payload

    generate.requests = []
    if name is not None:
        generate.name = name
    return generate


def _valid_entry(statement: str = "A competing explanation for the recorded signal.") -> dict:
    return {
        "statement": statement,
        "proposed_mechanism": "hypothetical mechanism",
        "predictions": ["a bounded restatement changes the reading"],
        "contradicted_if": ["the restatement leaves the reading unchanged"],
        "distinguishing_tests": ["CHECK_REVISION_FAITHFULNESS_V1"],
        "required_evidence": ["a retained per-case membership response"],
        "unsupported_assumptions": ["not a measured result"],
    }


# ------------------------------------------------------------------ template default


def test_deep_policy_asks_for_hypotheses_without_dispatching_them(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch)
    assert summary["status"] == "HYPOTHESIZED"
    assert summary["final_move"] == "GENERATE_HYPOTHESES"
    manifest = summary["decisions"][0]
    assert manifest["move"] == "GENERATE_HYPOTHESES"
    assert manifest["reason_code"] == "HYPOTHESES_JUSTIFIED"
    assert manifest["executed"] is False
    assert summary["hypothesis"]["status"] == "GENERATED"
    assert summary["hypothesis"]["requested_reason"] is None
    dispatch = [event for event in _events(repository, run_id)
                if event["type"] == "NEXT_MOVE_DISPATCHED"]
    assert dispatch and dispatch[-1]["data"]["reason_code"] == "MOVE_NOT_FOLLOW_UP"
    assert dispatch[-1]["data"]["dispatched"] is False
    assert len(_hypothesis_rows(repository, run_id)) == 2
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 0


def test_template_generation_is_labelled_bounded_and_judged_once(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch)
    rows = _hypothesis_rows(repository, run_id)
    assert len(rows) == 2
    assert summary["hypothesis"]["generator"] == TEMPLATE_GENERATOR
    assert summary["hypothesis"]["hypothesis_ids"] == [row["hypothesis_id"] for row in rows]

    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"]
    assert len(generated) == 1
    assert generated[0]["data"]["outcome"] == "GENERATED"
    assert generated[0]["data"]["count"] == 2
    assert generated[0]["data"]["label"] == LIVE_HYPOTHESIS_LABEL
    assert generated[0]["data"]["generator"] == TEMPLATE_GENERATOR
    assert generated[0]["data"]["provider_attempted"] is False
    assert generated[0]["data"]["requested_reason"] is None

    for row in rows:
        draft = row["hypothesis"]
        assert draft["label"] == LIVE_HYPOTHESIS_LABEL
        assert draft["generator"] == TEMPLATE_GENERATOR
        assert draft["candidate_id"] == row["candidate_id"]
        assert draft["statement"]
        assert draft["predictions"] and draft["contradicted_if"]
        assert set(draft["proposed_action_ids"]) <= set(ACTION_REGISTRY)
        assert any("not a measured result" in item for item in draft["unsupported_assumptions"])
        for field in DRAFT_FIELDS:
            assert field in draft

    types = [event["type"] for event in _events(repository, run_id)]
    assert types.count("HYPOTHESIS_EVALUATED") == 2
    assert types.index("HYPOTHESES_GENERATED") < types.index("HYPOTHESIS_EVALUATED")
    assert types.index("HYPOTHESIS_EVALUATED") < types.index("DOSSIER_CREATED")
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 0


def test_operator_requested_hypotheses_record_their_reason(runtime, monkeypatch):
    adapter = _hypothesis_adapter(stopping=0.8)
    run_id, summary, repository = _run(runtime, monkeypatch, jev_adapter=adapter,
                                       hypotheses_requested=True)
    assert summary["final_move"] == "COMPLETE"
    assert summary["status"] == "HYPOTHESIZED"
    assert summary["hypothesis"]["requested_reason"] == "OPERATOR_REQUESTED_HYPOTHESES"
    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["requested_reason"] == "OPERATOR_REQUESTED_HYPOTHESES"
    assert generated["data"]["outcome"] == "GENERATED"


def test_unauthorized_arc_generates_nothing(runtime, monkeypatch):
    run_id, summary, _ = _run(runtime, monkeypatch, authorized=False)
    repository = runtime[1]
    assert summary["final_move"] == "GENERATE_HYPOTHESES"
    assert summary["hypothesis"] is None
    assert _hypothesis_rows(repository, run_id) == []
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 0
    dossiers = repository.list_table("dossiers", run_id)
    assert len(dossiers) == 1


# ------------------------------------------------------------------- injected generator


def test_injected_generator_text_is_labelled_bounded_and_reviewed(runtime, monkeypatch):
    entries = [_valid_entry("An injected statement about the recorded mutation signal.")]
    generator = _generator(entries, name="test-generator", usage={"input_tokens": 321, "output_tokens": 45})
    run_id, summary, repository = _run(runtime, monkeypatch, llm_generator=generator)
    assert summary["status"] == "HYPOTHESIZED"
    assert summary["hypothesis"]["generator"] == "test-generator"
    assert summary["hypothesis"]["status"] == "GENERATED"
    assert generator.requests
    request = generator.requests[0]
    assert set(request["recorded_facts"]) >= {"symbol", "affected", "examined", "iteration"}
    assert request["eligible_registered_actions"] == ["CHECK_REVISION_FAITHFULNESS_V1"]
    assert "invent no numbers" in request["task"]

    rows = _hypothesis_rows(repository, run_id)
    assert len(rows) == 1
    draft = rows[0]["hypothesis"]
    assert draft["label"] == LLM_HYPOTHESIS_LABEL
    assert draft["generator"] == "test-generator"
    assert draft["generator_model"] is None
    assert draft["statement"] == entries[0]["statement"]

    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["provider_attempted"] is True
    assert generated["data"]["usage"] == {"input_tokens": 321, "output_tokens": 45}
    run_usage = repository.get_run(run_id)["provider_usage"]
    assert run_usage["llm_calls"] == 1
    assert run_usage["llm_input_tokens"] == 321
    assert run_usage["llm_output_tokens"] == 45

    dossier = _dossier(runtime, repository, run_id, rows[0]["candidate_id"])
    assert dossier["sections"]["llm_provider_model_metadata"]["availability"] == "NOT_ACQUIRED", (
        "only the known provider adapter is reported as LLM-generated text")
    assert "no LLM was configured" in dossier["sections"]["llm_provider_model_metadata"]["reason"]
    assert dossier["hypothesis_ids"] == [rows[0]["hypothesis_id"]]


def test_injected_text_never_writes_a_measured_field(runtime, monkeypatch):
    state_artifacts = {}
    entries = [_valid_entry("Generated claim: the mutation bucket is a frame artefact.")]
    generator = _generator(entries)
    run_id, summary, repository = _run(runtime, monkeypatch, llm_generator=generator)
    candidate = repository.get_candidate(summary["candidate_id"])
    for table in ("statistical_states", "evidence_states"):
        for row in repository.list_table(table, run_id):
            state_artifacts[row["artifact_id"]] = row["artifact_sha256"] if "artifact_sha256" in row else None
    for row in repository.list_table("statistical_states", run_id):
        body = runtime[2].read(repository.artifact(row["artifact_id"])["relative_path"]).decode()
        assert entries[0]["statement"] not in body
    for row in repository.list_table("evidence_states", run_id):
        body = runtime[2].read(repository.artifact(row["artifact_id"])["relative_path"]).decode()
        assert entries[0]["statement"] not in body
    for row in _hypothesis_rows(repository, run_id):
        assert "not a measured result" in " ".join(row["hypothesis"]["unsupported_assumptions"])
    assert candidate["status"] == "DOSSIER_READY", "the dossier is published after the text is stored"


@pytest.mark.parametrize("bad_payload", [
    [],
    [_valid_entry()] * 4,
    [{"statement": "too thin"}],
    [dict(_valid_entry(), statement="x" * 5000)],
    [dict(_valid_entry(), predictions="not-a-list")],
    [dict(_valid_entry(), distinguishing_tests=["NOT_A_REGISTERED_ACTION"])],
    [_valid_entry(), {"statement": "the second statement is malformed"}],
])
def test_malformed_generator_output_is_a_typed_unavailable_outcome(runtime, monkeypatch, bad_payload):
    generator = _generator(bad_payload)
    run_id, summary, repository = _run(runtime, monkeypatch, llm_generator=generator)
    assert summary["status"] == "ABSTAINED"
    assert summary["hypothesis"]["status"] == "UNAVAILABLE"
    assert summary["hypothesis"]["error_code"] == "GENERATOR_RESPONSE_MALFORMED"
    assert _hypothesis_rows(repository, run_id) == []
    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["outcome"] == "UNAVAILABLE"
    assert generated["data"]["error_code"] == "GENERATOR_RESPONSE_MALFORMED"
    assert generated["data"]["provider_attempted"] is True
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 1
    assert len(repository.list_table("dossiers", run_id)) == 1


def test_generator_failure_is_a_typed_outcome(runtime, monkeypatch):
    def failing(request):
        raise TimeoutError("synthetic provider timeout")

    run_id, summary, repository = _run(runtime, monkeypatch, llm_generator=failing)
    assert summary["status"] == "ABSTAINED"
    assert summary["hypothesis"]["status"] == "UNAVAILABLE"
    assert summary["hypothesis"]["error_code"] == "GENERATOR_ERROR"
    assert _hypothesis_rows(repository, run_id) == []
    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["outcome"] == "UNAVAILABLE"
    assert generated["data"]["error_code"] == "GENERATOR_ERROR"
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 1


def test_per_candidate_bound_limits_recorded_statements(runtime, monkeypatch):
    generator = _generator([_valid_entry()])
    monkeypatch.setattr("cancerjev.research.hypotheses.MAX_HYPOTHESES", 1)
    run_id, summary, repository = _run(runtime, monkeypatch, llm_generator=generator)
    assert summary["status"] == "HYPOTHESIZED"
    assert len(_hypothesis_rows(repository, run_id)) == 1
    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["count"] == 1


def test_the_per_candidate_bound_is_respected_when_already_exhausted(runtime, monkeypatch):
    monkeypatch.setattr("cancerjev.research.hypotheses.MAX_HYPOTHESES", 0)
    run_id, summary, repository = _run(runtime, monkeypatch)
    assert summary["status"] == "ABSTAINED"
    assert summary["hypothesis"]["status"] == "NO_NEW_HYPOTHESES"
    assert _hypothesis_rows(repository, run_id) == []
    generated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESES_GENERATED"][-1]
    assert generated["data"]["outcome"] == "NO_NEW_HYPOTHESES"
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 0
    dossier = _dossier(runtime, repository, run_id, summary["candidate_id"])
    assert dossier["sections"]["competing_hypotheses"]["availability"] == "NOT_ACQUIRED"


# ------------------------------------------------------------------------ reviews


def test_each_statement_is_judged_once_and_bound_to_its_evidence(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch)
    rows = _hypothesis_rows(repository, run_id)
    candidate = repository.get_candidate(summary["candidate_id"])
    evidence_state_id = candidate["latest_evidence_state_id"]
    evaluations = _evaluations(repository, run_id, "HYPOTHESIS")
    assert len(evaluations) == 2
    assert {row["input_ref_id"] for row in evaluations} == {row["hypothesis_id"] for row in rows}
    for evaluation in evaluations:
        vector = evaluation["vector"]
        assert vector["input_ref_kind"] == "HYPOTHESIS"
        assert vector["question_set_version"] == "hypothesis-v2"
        assert vector["error"] is None
        assert set(vector["answers"]) == HYPOTHESIS_ANSWERS
        assert all(entry["applicable"] for entry in vector["applicability"].values())
        assert vector["generator"] == TEMPLATE_GENERATOR
        assert vector["source_evidence_hash"]
        assert vector["resolved_model"] == "jev-1.13.0"
    evaluated = [event for event in _events(repository, run_id)
                 if event["type"] == "HYPOTHESIS_EVALUATED"]
    assert len(evaluated) == 2
    assert {event["data"]["hypothesis_id"] for event in evaluated} == {row["hypothesis_id"] for row in rows}
    assert all(event["data"]["input_ref_kind"] == "HYPOTHESIS" for event in evaluated)
    assert all(event["data"]["evidence_state_id"] == evidence_state_id for event in evaluated)
    assert all(event["data"]["generator"] == TEMPLATE_GENERATOR for event in evaluated)

    for row in rows:
        stored = read_hypothesis_record(repository, runtime[2], row["hypothesis_id"],
                                        candidate_id=candidate["candidate_id"],
                                        allowed_action_ids=frozenset(ACTION_REGISTRY))
        assert stored.draft.statement == row["hypothesis"]["statement"]
        assert stored.evidence_state_id == evidence_state_id


def test_identical_generated_text_reuses_its_review(runtime, monkeypatch):
    entries = [_valid_entry("An identical injected statement for cache reuse."),
               _valid_entry("An identical injected statement for cache reuse.")]
    generator = _generator(entries, name="test-generator")
    adapter = _hypothesis_adapter()
    run_id, _, repository = _run(runtime, monkeypatch, jev_adapter=adapter,
                                 llm_generator=generator)
    reviews = _evaluations(repository, run_id, "HYPOTHESIS")
    assert len(reviews) == 2
    cached = [row for row in reviews if row["vector"]["cache_source_evaluation_id"]]
    supplied = [row for row in reviews if not row["vector"]["cache_source_evaluation_id"]]
    assert len(cached) == 1, "identical generated text reuses its recorded review"
    assert len(supplied) == 1
    assert cached[0]["vector"]["cache_source_evaluation_id"] == supplied[0]["evaluation_id"]
    assert cached[0]["vector"]["projection_hash"] == supplied[0]["vector"]["projection_hash"]
    assert adapter.calls == 4, "2 wide + 1 deep + 1 reviewed hypothesis"


def test_dossiers_keep_their_reviews_to_their_own_candidate(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_hypothesis_adapter(),
        deep_selections=("GENEONE", "GENETWO"), deep_followup_authorized=True)
    run_id = orchestrator.run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    candidates = repository.list_table("candidates", run_id)
    assert {row["entity"]["gene_symbol"] for row in candidates} == {"GENEONE", "GENETWO"}
    dossiers = repository.list_table("dossiers", run_id)
    assert len(dossiers) == 2
    seen: set[str] = set()
    for candidate in candidates:
        own = _hypothesis_rows(repository, run_id, candidate["candidate_id"])
        assert len(own) == 2
        other_ids = {row["hypothesis_id"]
                     for other in candidates if other["candidate_id"] != candidate["candidate_id"]
                     for row in _hypothesis_rows(repository, run_id, other["candidate_id"])}
        dossier = _dossier(runtime, repository, run_id, candidate["candidate_id"])
        assert dossier["hypothesis_ids"] == [row["hypothesis_id"] for row in own]
        assert set(dossier["hypothesis_ids"]).isdisjoint(other_ids)
        narrative = dossier["sections"]["hypothesis_jev_reviews"]["narrative"]
        assert all(hypothesis_id[:8] in narrative for hypothesis_id in dossier["hypothesis_ids"])
        assert "hypothesis-v2" in narrative
        assert dossier["sections"]["competing_hypotheses"]["availability"] == "OBSERVED"
        assert dossier["sections"]["llm_provider_model_metadata"]["availability"] == "NOT_ACQUIRED"
        seen.update(dossier["hypothesis_ids"])
    assert len(seen) == 4


def test_dossier_names_the_deep_judgment_question_set_and_model(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch)
    dossier = _dossier(runtime, repository, run_id, summary["candidate_id"])
    versions = dossier["sections"]["jev_model_question_versions"]["narrative"]
    assert "deep-v1" in versions
    assert "jev-1.13.0" in versions
    assert dossier["sections"]["jev_deep_judgments"]["availability"] == "OBSERVED"


def test_duplicate_selections_are_investigated_once(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_hypothesis_adapter(),
        deep_selections=("GENEONE", "GENEONE"), deep_followup_authorized=True)
    run_id = orchestrator.run()
    deep = next(event for event in _events(repository, run_id)
                if event["type"] == "RUN_COMPLETED")["data"]["deep"]
    assert deep["selections"] == ["GENEONE"]
    assert deep["candidate_count"] == 1
    duplicates = [event for event in _events(repository, run_id)
                  if event["type"] == "DEEP_SELECTION_UNAVAILABLE"]
    assert duplicates and duplicates[-1]["data"]["reason_code"] == "DUPLICATE_SELECTION"
    assert len(repository.list_table("candidates", run_id)) == 1
    assert len(repository.list_table("dossiers", run_id)) == 1
    assert len(_hypothesis_rows(repository, run_id)) == 2


def test_template_phrasing_never_quotes_an_unobserved_metric(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch,
                                       empty_expression_projects={"TCGA-LUAD"})
    assert summary["status"] == "HYPOTHESIZED"
    rows = _hypothesis_rows(repository, run_id)
    assert len(rows) == 2
    for row in rows:
        draft = row["hypothesis"]
        assert "None" not in draft["statement"]
        assert any("not observed in this revision" in item for item in draft["unsupported_assumptions"])
    expression_statement = rows[1]["hypothesis"]["statement"]
    assert "not observed in this revision" in expression_statement
    assert "0 of 100" not in expression_statement, "an unobserved metric is never quoted as a number"
    assert "0 observed" not in expression_statement
    assert repository.get_run(run_id)["provider_usage"]["llm_calls"] == 0


# ---------------------------------------------------------------------------- API


def test_hypothesis_stage_is_visible_through_the_api(runtime, monkeypatch):
    run_id, summary, repository = _run(runtime, monkeypatch)
    client = _api_client(runtime, monkeypatch)
    rows = _hypothesis_rows(repository, run_id)
    listed = client.get(f"/api/runs/{run_id}/hypotheses").json()["items"]
    assert {item["hypothesis_id"] for item in listed} == {row["hypothesis_id"] for row in rows}
    assert all(item["hypothesis"]["label"] == LIVE_HYPOTHESIS_LABEL for item in listed)

    evaluations = client.get(f"/api/runs/{run_id}/evaluations",
                             params={"purpose": "HYPOTHESIS"}).json()["items"]
    assert len(evaluations) == 2
    assert all(row["vector"]["question_set_version"] == "hypothesis-v2" for row in evaluations)
    assert all(row["vector"]["generator"] == TEMPLATE_GENERATOR for row in evaluations)

    dossier_row = repository.list_table("dossiers", run_id)[0]
    dossier = client.get(f"/api/dossiers/{dossier_row['dossier_id']}").json()
    assert dossier["hypothesis_ids"] == [row["hypothesis_id"] for row in rows]
    assert dossier["sections"]["competing_hypotheses"]["availability"] == "OBSERVED"
    assert dossier["sections"]["research_only_notice"]["narrative"] == dossier["warning"]