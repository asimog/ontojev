"""Phase 6: bounded hypothesis generation, its Jev review, and the live dossier."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from apps.api.main import create_app
from cancerjev.research.hypotheses import (
    INJECTED_GENERATOR,
    LIVE_HYPOTHESIS_LABEL,
    LLM_HYPOTHESIS_LABEL,
    MAX_HYPOTHESES,
    TEMPLATE_GENERATOR,
    generate_template_hypotheses,
)
from cancerjev.science.actions import ACTION_REGISTRY
from tests.integration.test_live_replay import _orchestrator
from tests.jev.stub_adapter import StubAdapter

HYPOTHESIS_QUESTIONS = {
    "hypothesis_testable", "hypothesis_exceeds_recorded_evidence",
    "hypothesis_dominant_unsupported_assumption",
}


def _hypothesis_adapter(**deep_overrides) -> StubAdapter:
    """Wide admission abstains; the deep judgment asks for competing explanations."""
    deep = {"next_step_warranted": {"kind": "noul", "probability_yes": 0.2},
            "stopping_more_honest": {"kind": "noul", "probability_yes": 0.2},
            "evidence_sufficient_for_next_step": {"kind": "noul", "probability_yes": 0.8}}
    deep.update(deep_overrides)
    return StubAdapter(override={"warrants_deeper_investigation": {"kind": "noul", "probability_yes": 0.05}},
                       deep_override=deep)


def _run(runtime, monkeypatch, *, authorized=True, settings_override=None, llm_generator=None, **kwargs):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch,
        jev_adapter=_hypothesis_adapter(**kwargs.pop("deep_overrides", {})),
        deep_selection="GENEONE", deep_followup_authorized=authorized, **kwargs)
    if settings_override is not None:
        orchestrator.settings = settings_override
    if llm_generator is not None:
        orchestrator.llm_generator = llm_generator
    run_id = orchestrator.run()
    run = repository.get_run(run_id)
    assert run["status"] == "COMPLETED"
    completed = [event for event in repository.events(run_id, 0, 800)["items"]
                 if event["type"] == "RUN_COMPLETED"][-1]
    return run_id, run, repository, completed["data"]["deep"]["candidates"][0]


def _llm_generator(payload: dict):
    def generate(request: dict):
        assert set(request) >= {"recorded_facts", "eligible_registered_actions", "response_schema"}
        assert request["eligible_registered_actions"], "the request supplies only eligible registered actions"
        return payload["hypotheses"], {"input_tokens": 321, "output_tokens": 45}

    return generate


def test_unauthorized_arc_records_no_hypotheses(runtime, monkeypatch):
    run_id, run, repository, summary = _run(runtime, monkeypatch, authorized=False)
    assert summary["final_move"] == "GENERATE_HYPOTHESES"
    assert summary["hypothesis"] is None
    assert repository.list_table("hypotheses", run_id) == []
    assert run["provider_usage"]["llm_calls"] == 0
    dossier = repository.list_table("dossiers", run_id)
    assert len(dossier) == 1, "the dossier still records what was and was not done"
    assert dossier[0]["summary"]["warning"].startswith("REAL OPEN-ACCESS GDC EVIDENCE")


def test_authorized_arc_generates_labelled_hypotheses_and_has_jev_review_them(runtime, monkeypatch):
    run_id, run, repository, summary = _run(runtime, monkeypatch, authorized=True)
    assert summary["final_move"] == "GENERATE_HYPOTHESES"
    assert summary["hypothesis"]["status"] == "GENERATED"
    assert summary["hypothesis"]["generator"] == TEMPLATE_GENERATOR
    assert len(summary["hypothesis"]["hypothesis_ids"]) == 2

    events = repository.events(run_id, 0, 800)["items"]
    generated = [event for event in events if event["type"] == "HYPOTHESES_GENERATED"]
    assert len(generated) == 1
    data = generated[0]["data"]
    assert data["outcome"] == "GENERATED" and data["count"] == 2
    assert data["label"] == LIVE_HYPOTHESIS_LABEL
    assert data["provider_attempted"] is False, "the default generator is deterministic and offline"

    rows = repository.page_child("hypotheses", run_id, 20, None, {})["items"]
    assert len(rows) == 2
    for row in rows:
        hypothesis = row["hypothesis"]
        assert hypothesis["label"] == LIVE_HYPOTHESIS_LABEL
        assert hypothesis["generator"] == TEMPLATE_GENERATOR
        assert hypothesis["statement"] and hypothesis["predictions"] and hypothesis["contradicted_if"]
        assert set(hypothesis["proposed_action_ids"]) <= set(ACTION_REGISTRY)
        assert "not a measured result" in hypothesis["unsupported_assumptions"][0]

    evaluations = repository.page_child("jev_evaluations", run_id, 20, None,
                                        {"purpose": "HYPOTHESIS"})["items"]
    assert len(evaluations) == 2
    for row in evaluations:
        vector = row["vector"]
        assert vector["input_ref_kind"] == "HYPOTHESIS"
        assert vector["question_set_version"] == "hypothesis-v2"
        assert set(vector["answers"]) == HYPOTHESIS_QUESTIONS
        assert all(rule["applicable"] for rule in vector["applicability"].values())
        assert vector["generator"] == TEMPLATE_GENERATOR
        assert vector["error"] is None
    hypotheses_left = repository.page_child("hypotheses", run_id, 20, None, {})["items"]
    assert len(hypotheses_left) <= MAX_HYPOTHESES
    assert run["provider_usage"]["llm_calls"] == 0
    assert run["provider_usage"]["jev_calls"] >= 3, "two hypothesis judgments on top of the deep ones"

    dossier = repository.list_table("dossiers", run_id)[0]
    payload = json.loads(runtime[2].read(repository.artifact(
        dossier["json_artifact_id"])["relative_path"]))
    sections = payload["sections"]
    assert sections["competing_hypotheses"]["availability"] == "OBSERVED"
    assert sections["hypothesis_jev_reviews"]["availability"] == "OBSERVED"
    assert sections["falsification_criteria"]["availability"] == "OBSERVED"
    assert sections["llm_provider_model_metadata"]["availability"] == "NOT_ACQUIRED"
    assert sections["research_only_notice"]["narrative"] == payload["warning"]
    assert payload["hypothesis_ids"] == summary["hypothesis"]["hypothesis_ids"]


def test_configured_llm_generation_is_labelled_bound_and_uses_its_own_usage(runtime, monkeypatch):
    payload = {"hypotheses": [{
        "statement": "The recorded mutation count is dominated by the examined frame composition.",
        "proposed_mechanism": "Hypothetically, frame composition drives the count.",
        "predictions": ["A bounded restatement changes the count."],
        "contradicted_if": ["A bounded restatement leaves the count unchanged."],
        "distinguishing_tests": ["CHECK_REVISION_FAITHFULNESS_V1"],
        "required_evidence": ["per-case mutation membership"],
        "unsupported_assumptions": ["Mechanism is hypothetical only."],
    }]}
    run_id, run, repository, summary = _run(
        runtime, monkeypatch, authorized=True, llm_generator=_llm_generator(payload))
    assert summary["hypothesis"]["status"] == "GENERATED", summary["hypothesis"]
    assert summary["hypothesis"]["generator"] == INJECTED_GENERATOR
    rows = repository.page_child("hypotheses", run_id, 20, None, {})["items"]
    assert len(rows) == 1
    assert rows[0]["hypothesis"]["label"] == LLM_HYPOTHESIS_LABEL
    generated = [event for event in repository.events(run_id, 0, 800)["items"]
                 if event["type"] == "HYPOTHESES_GENERATED"][0]["data"]
    assert generated["provider_attempted"] is True
    assert generated["usage"] == {"input_tokens": 321, "output_tokens": 45}
    assert run["provider_usage"]["llm_calls"] == 1
    assert run["provider_usage"]["llm_input_tokens"] == 321


def test_malformed_llm_response_is_a_typed_unavailability(runtime, monkeypatch):
    def broken_generator(request: dict):
        raise TimeoutError("provider timed out")

    run_id, run, repository, summary = _run(
        runtime, monkeypatch, authorized=True, llm_generator=broken_generator)
    assert summary["hypothesis"]["status"] == "UNAVAILABLE"
    assert summary["hypothesis"]["error_code"] == "GENERATOR_ERROR"
    assert repository.list_table("hypotheses", run_id) == []
    events = [event for event in repository.events(run_id, 0, 800)["items"]
              if event["type"] == "HYPOTHESES_GENERATED"]
    assert events[-1]["data"]["outcome"] == "UNAVAILABLE"
    assert events[-1]["data"]["error_code"] == "GENERATOR_ERROR"
    assert run["provider_usage"]["llm_calls"] == 1, "the failed attempt is still recorded as a call"


def test_malformed_generator_output_is_rejected_without_storing_anything(runtime, monkeypatch):
    def bad_generator(request: dict):
        return [{"statement": "too thin a draft"}], {"input_tokens": 10, "output_tokens": 1}

    run_id, run, repository, summary = _run(
        runtime, monkeypatch, authorized=True, llm_generator=bad_generator)
    assert summary["hypothesis"]["status"] == "UNAVAILABLE"
    assert summary["hypothesis"]["error_code"] == "GENERATOR_RESPONSE_MALFORMED"
    assert repository.list_table("hypotheses", run_id) == []


def test_hypotheses_and_dossier_are_visible_through_the_api(runtime, monkeypatch):
    run_id, _, repository, summary = _run(runtime, monkeypatch, authorized=True)
    client = TestClient(create_app())
    hypotheses = client.get(f"/api/runs/{run_id}/hypotheses")
    assert hypotheses.status_code == 200
    assert len(hypotheses.json()["items"]) == 2
    dossiers = client.get(f"/api/runs/{run_id}/dossiers")
    assert dossiers.status_code == 200
    items = dossiers.json()["items"]
    assert len(items) == 1
    detail = client.get(f"/api/dossiers/{items[0]['dossier_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["mode"] == "LIVE"
    assert payload["warning"].startswith("REAL OPEN-ACCESS GDC EVIDENCE")
    assert payload["hypothesis_ids"] == summary["hypothesis"]["hypothesis_ids"]
    assert payload["sections"]["deterministic_deep_evidence"]["availability"] == "OBSERVED"
    assert "SYNTHETIC" not in detail.text

def _live_hypothesis_events(repository, run_id):
    return [event for event in repository.events(run_id, 0, 800)["items"]
            if event["type"] in {"HYPOTHESIS_EVALUATED", "JEV_DEEP_EVIDENCE_JUDGED"}]


def test_live_hypothesis_review_is_recorded_as_hypothesis_evaluated(runtime, monkeypatch):
    """The live review must appear under its own registered event type, once per statement."""
    run_id, _, repository, summary = _run(runtime, monkeypatch, authorized=True)
    events = _live_hypothesis_events(repository, run_id)
    reviews = [event for event in events if event["type"] == "HYPOTHESIS_EVALUATED"]
    revisions = [event for event in events if event["type"] == "JEV_DEEP_EVIDENCE_JUDGED"]
    assert len(reviews) == len(summary["hypothesis"]["hypothesis_ids"]) == 2
    for event in reviews:
        data = event["data"]
        assert data["input_ref_kind"] == "HYPOTHESIS"
        assert data["hypothesis_id"] in summary["hypothesis"]["hypothesis_ids"]
        assert data["evidence_state_id"], "the judged revision must be named"
        assert data["generator"] == TEMPLATE_GENERATOR
    assert len(revisions) == len(summary["steps"]), "one deep revision judgment per step, never a review"


def test_identical_generated_text_reuses_its_review_across_runs(runtime, monkeypatch):
    """The review projection must not include the run-specific hypothesis id."""
    payload = {"hypotheses": [{
        "statement": "Recorded mutation count may follow the examined frame composition.",
        "proposed_mechanism": "Hypothetically frame composition drives the count.",
        "predictions": ["A bounded restatement changes the count."],
        "contradicted_if": ["A bounded restatement leaves the count unchanged."],
        "distinguishing_tests": ["CHECK_REVISION_FAITHFULNESS_V1"],
        "required_evidence": ["per-case mutation membership"],
        "unsupported_assumptions": ["Mechanism is hypothetical only."],
    }]}
    settings, repository, artifacts = runtime
    from cancerjev.jev.service import JevService
    from cancerjev.research.live import LiveOrchestrator
    from cancerjev.research.specs import LUAD_RESEARCH_V1
    from tests.integration.replay import ReplayTransport

    adapter = _hypothesis_adapter()
    service = JevService(settings, repository, artifacts, adapter_factory=lambda: adapter)
    calls_before = adapter.calls

    def _run_once():
        orchestrator = LiveOrchestrator(
            settings, repository, artifacts, lambda event: None, jev_service=service,
            transport_factory=lambda repo, store, budget, run_id, emit: ReplayTransport(
                store, run_id, repository=repo),
            research_spec=LUAD_RESEARCH_V1, deep_selection="GENEONE",
            deep_followup_authorized=True, llm_generator=_llm_generator(payload),
        )
        run_id = orchestrator.run()
        return run_id, adapter.calls

    first_run, calls_after_first = _run_once()
    second_run, calls_after_second = _run_once()
    assert calls_after_first > calls_before
    assert calls_after_second == calls_after_first, "an identical review must not be recomputed"
    for run_id, expected_cache in ((first_run, False), (second_run, True)):
        rows = repository.page_child("jev_evaluations", run_id, 50, None,
                                     {"purpose": "HYPOTHESIS"})["items"]
        assert len(rows) == 1
        assert bool(rows[0]["vector"]["cache_source_evaluation_id"]) is expected_cache


def test_oversized_or_malformed_generated_output_is_rejected_typed(runtime, monkeypatch):
    def oversized(request):
        return ([{"statement": "x" * 5_000, "proposed_mechanism": "m", "predictions": ["p"],
                  "contradicted_if": ["c"], "distinguishing_tests": [],
                  "required_evidence": ["r"], "unsupported_assumptions": ["a"]}], None)

    run_id, run, repository, summary = _run(runtime, monkeypatch, authorized=True,
                                            llm_generator=oversized)
    assert summary["hypothesis"]["status"] == "UNAVAILABLE"
    assert summary["hypothesis"]["error_code"] == "GENERATOR_RESPONSE_MALFORMED"
    assert repository.list_table("hypotheses", run_id) == []
    assert run["status"] == "COMPLETED", "a rejected generation never aborts the run"

    def stringly(request):
        return ([{"statement": "A statement.", "proposed_mechanism": "m", "predictions": "not a list",
                  "contradicted_if": ["c"], "distinguishing_tests": [],
                  "required_evidence": ["r"], "unsupported_assumptions": ["a"]}], None)

    run_id, run, repository, summary = _run(runtime, monkeypatch, authorized=True,
                                            llm_generator=stringly)
    assert summary["hypothesis"]["error_code"] == "GENERATOR_RESPONSE_MALFORMED"
    assert repository.list_table("hypotheses", run_id) == []


def test_hypothesis_bound_is_recorded_when_already_reached(runtime, monkeypatch):
    monkeypatch.setattr("cancerjev.research.hypotheses.MAX_HYPOTHESES", 0)
    run_id, run, repository, summary = _run(runtime, monkeypatch, authorized=True)
    assert summary["hypothesis"]["status"] == "NO_NEW_HYPOTHESES"
    events = [event for event in repository.events(run_id, 0, 800)["items"]
              if event["type"] == "HYPOTHESES_GENERATED"]
    assert events[-1]["data"]["outcome"] == "NO_NEW_HYPOTHESES"
    assert events[-1]["data"]["count"] == 0
    assert repository.list_table("hypotheses", run_id) == []
    assert run["provider_usage"]["llm_calls"] == 0


def test_template_phrasing_never_quotes_an_unobserved_metric():
    revision = {
        "entity": {"gene_symbol": "GENEONE"}, "iteration_number": 1,
        "project_level_evidence": [{
            "project_id": "TCGA-LUAD",
            "affected_case_count": {"value": None, "availability": "NOT_OBSERVED"},
            "examined_cases": {"value": 585, "availability": "OBSERVED"},
            "projects_case_with_ssm": {"value": None, "availability": "NOT_OBSERVED"},
            "cases_with_expression": {"value": None, "availability": "NOT_OBSERVED"},
            "missing_measurements": {"value": None, "availability": "NOT_OBSERVED"},
        }],
        "deterministic_observations": [], "missing_evidence": [],
    }
    drafts = generate_template_hypotheses(revision, candidate={"entity": {"gene_symbol": "GENEONE"}},
                                          eligible_action_ids=["CHECK_REVISION_FAITHFULNESS_V1"])
    assert len(drafts) == 2
    for draft in drafts:
        assert "None" not in draft["statement"]
        assert "not observed" in draft["statement"]
    assert any("not observed in this revision" in item for item in drafts[0]["unsupported_assumptions"])


def test_duplicate_selection_is_de_duplicated_with_a_typed_notice(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_hypothesis_adapter(),
        deep_selections=("GENEONE", "GENEONE"), deep_followup_authorized=True)
    run_id = orchestrator.run()
    completed = [event for event in repository.events(run_id, 0, 800)["items"]
                 if event["type"] == "RUN_COMPLETED"][-1]["data"]["deep"]
    assert completed["selections"] == ["GENEONE"]
    assert completed["candidate_count"] == 1
    duplicates = [event for event in repository.events(run_id, 0, 800)["items"]
                  if event["type"] == "DEEP_SELECTION_UNAVAILABLE"
                  and event["data"].get("reason_code") == "DUPLICATE_SELECTION"]
    assert len(duplicates) == 1
    assert len(repository.list_table("candidates", run_id)) == 1
    assert len(repository.list_table("dossiers", run_id)) == 1


def test_multi_candidate_dossiers_keep_their_own_reviews_and_model(runtime, monkeypatch):
    orchestrator, _, repository = _orchestrator(
        runtime, monkeypatch, jev_adapter=_hypothesis_adapter(),
deep_selections=("GENEONE", "GENETWO"), deep_followup_authorized=True)
    run_id = orchestrator.run()
    artifacts = runtime[2]
    for row in repository.list_table("dossiers", run_id):
        payload = json.loads(artifacts.read(repository.artifact(row["json_artifact_id"])["relative_path"]))
        own_ids = set(payload["hypothesis_ids"])
        assert own_ids, "each investigated candidate records its own statements"
        reviews = payload["sections"]["hypothesis_jev_reviews"]["narrative"] or ""
        assert reviews.count(";") + 1 == len(own_ids), "no other candidate's review may appear"
        versions = payload["sections"]["jev_model_question_versions"]["narrative"]
        assert versions and "n/a" not in versions
        assert "deep-v1" in versions and "jev-1.13.0" in versions, "real question set and model are reported"
