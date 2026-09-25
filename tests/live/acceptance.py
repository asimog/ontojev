"""Opt-in integration-test helpers, never a production policy or dispatcher.

The independent text-generation check reads accepted evidence and publishes a
separate test report. It does not append events or hypotheses to the source run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from cancerjev.config import Settings
from cancerjev.domain.events import canonical_json
from cancerjev.domain.hypotheses import DRAFT_FIELDS, read_hypothesis_draft
from cancerjev.jev.contracts import read_answers
from cancerjev.jev.projection import build_hypothesis_projection, projection_hash
from cancerjev.jev.questions import (
    HYPOTHESIS_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTIONS,
    question_set_hash,
)
from cancerjev.jev.typesafe_adapter import JevProviderError, TypeSafeAdapter
from cancerjev.llm.openrouter import OpenRouterGenerator
from cancerjev.research.hypotheses import (
    LLM_HYPOTHESIS_LABEL,
    MAX_HYPOTHESES,
    generation_request,
)
from cancerjev.science.actions import ACTION_REGISTRY, eligible_actions
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.readers import read_candidate_state, read_revision_chain
from cancerjev.storage.repositories import Repository


@dataclass
class CallBudget:
    jev_attempts: int = 0
    llm_attempts: int = 0

    def reserve_jev(self) -> None:
        if self.jev_attempts >= 15:
            raise JevProviderError("ACCEPTANCE_BUDGET_EXHAUSTED", "15 Jev attempts reached")
        self.jev_attempts += 1

    def reserve_llm(self) -> None:
        if self.llm_attempts >= 1:
            raise ValueError("one acceptance LLM attempt already reserved")
        self.llm_attempts += 1


class BudgetedAdapter(TypeSafeAdapter):
    def __init__(self, settings: Settings, budget: CallBudget):
        super().__init__(model=settings.jev_model, timeout=settings.jev_timeout_seconds)
        self.budget = budget

    def evaluate(self, state, definitions):
        self.budget.reserve_jev()
        return super().evaluate(state, definitions)


def check_generated_text(
    settings: Settings, repository: Repository, artifacts: ArtifactStore,
    candidate_id: str, budget: CallBudget, *, generator=None, adapter=None,
) -> dict[str, Any]:
    """One real generator attempt and up to three critiques; failures are recorded.

    Injection exists for offline verification of this test harness. All scientific
    input is loaded through verified storage readers before any provider call.
    """
    report: dict[str, Any] = {
        "kind": "INDEPENDENT_PROVIDER_INTEGRATION_TEST",
        "notice": "NOT A PRODUCTION NEXT MOVE; GENERATED TEXT IS NOT EVIDENCE",
        "status": "FAILED", "candidate_id": candidate_id,
        "requested_jev_model": settings.jev_model,
        "requested_llm_model": settings.llm_model,
        "llm_model_resolution": "UNVERIFIED",
        "reviews": [],
    }
    report_id = str(uuid4())
    try:
        state = read_candidate_state(repository, artifacts, candidate_id)
        run = repository.get_run(state.run_id)
        if run is None or run["mode"] != "LIVE":
            raise ValueError("live acceptance requires retained live GDC evidence")
        revisions = read_revision_chain(repository, artifacts, candidate_id)
        if not revisions or revisions[-1].iteration < 1:
            raise ValueError("an accepted action revision is required")
        stored = revisions[-1]
        revision = stored.artifact.boundary_representation()
        evidence_hash = repository.get_evidence_state(stored.evidence_state_id)["evidence_hash"]
        report.update({
            "source_run_id": state.run_id, "source_state_hash": state.scientific_hash,
            "source_state_artifact_sha256": state.artifact.sha256,
            "evidence_state_id": stored.evidence_state_id,
            "evidence_artifact_sha256": stored.artifact.sha256,
            "evidence_hash": evidence_hash,
        })
        actions = [item.action_id for item in eligible_actions(stored.evidence, "EVIDENCE_STATE")
                   if item.eligible]
        request = generation_request(revision, eligible_action_ids=actions)
        report["generation_request"] = request
        llm = generator if generator is not None else OpenRouterGenerator(
            model=settings.llm_model, timeout=settings.llm_timeout_seconds,
        )
        judge = adapter if adapter is not None else BudgetedAdapter(settings, budget)
        budget.reserve_llm()
        entries, usage = llm(request)
        report["llm_usage"] = usage
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_HYPOTHESES:
            raise ValueError("generator response exceeds the hypothesis contract")
        drafts = tuple(read_hypothesis_draft(entry, allowed_action_ids=frozenset(actions))
                       for entry in entries)
        for draft in drafts:
            hypothesis = {**asdict(draft), "label": LLM_HYPOTHESIS_LABEL,
                          "generator": getattr(llm, "name", "injected-test-generator"),
                          "generator_model": settings.llm_model}
            projection = build_hypothesis_projection(
                hypothesis, revision,
                eligible_actions=[ACTION_REGISTRY[action].payload() for action in actions],
                evidence_hash=evidence_hash,
            )
            result = judge.evaluate(projection, HYPOTHESIS_QUESTIONS)
            answers = read_answers(HYPOTHESIS_QUESTIONS, result.answers)
            report["reviews"].append({
                "hypothesis": {key: hypothesis[key] for key in DRAFT_FIELDS},
                "projection": projection, "projection_hash": projection_hash(projection),
                "question_set_version": HYPOTHESIS_QUESTION_SET_VERSION,
                "question_hash": question_set_hash(HYPOTHESIS_QUESTIONS, HYPOTHESIS_QUESTION_SET_VERSION),
                "requested_model": result.requested_model, "resolved_model": result.resolved_model,
                "answers": answers.boundary_representation(), "usage": result.usage,
                "latency_ms": result.latency_ms, "request_id": result.request_id,
            })
            if result.resolved_model != settings.jev_model:
                raise ValueError("Jev resolved model differs from the requested pinned identity")
        report["status"] = "PASSED"
    except Exception as exc:  # test report must survive provider/validation failures
        # Do not persist provider exception bodies: they can echo request secrets.
        report["error_code"] = getattr(exc, "code", type(exc).__name__)
    finally:
        report["attempts"] = asdict(budget)
        published = artifacts.publish(
            f"acceptance/{report_id}.json", canonical_json(report), "application/json",
            "independent-provider-integration-test",
        )
        report["report_path"] = published.relative_path
    return report
