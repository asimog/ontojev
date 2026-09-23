"""JevService: the application boundary around one provider adapter.

Owns projection registration, cache identity, provider invocation, fail-closed
validation, persistence and events. Science modules never import provider types.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from cancerjev.config import Settings
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.jev.contracts import JevContractError, validate_answers
from cancerjev.jev.projection import (
    INCLUDED_FIELDS,
    PROJECTION_VERSION,
    build_projection,
    projection_hash,
)
from cancerjev.jev.questions import (
    WIDE_QUESTION_SET_VERSION,
    WIDE_QUESTIONS,
    applicability_map,
    question_set_hash,
)
from cancerjev.jev.typesafe_adapter import ADAPTER_VERSION, JevProviderError, TypeSafeAdapter
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

# A cacheable model identity must be pinned/versioned, for example ``jev-1.13.0``
# or a date-suffixed snapshot name. A mutable alias can resolve to a different
# model later, so it is never treated as an already resolved identity.
_PINNED_MODEL_PATTERN = re.compile(r"-\d+(?:\.\d+)*$")


def is_pinned_model_identity(model: str) -> bool:
    return bool(_PINNED_MODEL_PATTERN.search((model or "").strip()))


@dataclass
class JevService:
    settings: Settings
    repository: Repository
    artifacts: ArtifactStore
    adapter_factory: Callable[[], TypeSafeAdapter] | None = None
    _question_artifact: dict[str, Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ helpers

    def _publish_json(self, run_id: str, relative_path: str, payload: Any, purpose: str) -> Any:
        return self.artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    def _ensure_question_artifact(self, run_id: str) -> Any:
        if run_id in self._question_artifact:
            return self._question_artifact[run_id]
        payload = {
            "question_set_version": WIDE_QUESTION_SET_VERSION,
            "question_set_hash": question_set_hash(),
            "questions": [
                {
                    "question_id": definition.question_id,
                    "primitive": definition.primitive,
                    "version": definition.version,
                    "instructions": definition.instructions,
                    "criteria": definition.criteria,
                    "applicability_rule": definition.applicability_rule,
                }
                for definition in WIDE_QUESTIONS
            ],
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/jev/questions.json", payload, "jev-question-set")
        self.repository.register_artifact(artifact, run_id)
        self._question_artifact[run_id] = artifact
        return artifact

    def _projection_id(self, state_id: str) -> str:
        return str(uuid4())

    def _register_projection(self, *, run_id: str, state: dict[str, Any], projection: dict[str, Any],
                             emit: Callable[..., Any]) -> tuple[str, str, Any]:
        existing = self.repository.find_projection(state["state_id"], PROJECTION_VERSION)
        if existing is not None:
            metadata = self.repository.artifact(existing["artifact_id"])
            return existing["projection_id"], existing["projection_hash"], metadata
        projection_id = self._projection_id(state["state_id"])
        p_hash = projection_hash(projection)
        artifact = self._publish_json(
            run_id, f"runs/{run_id}/jev/projections/{projection_id}.json", projection, "jev-projection",
        )
        registration = self.repository.projection_registration(
            projection_id=projection_id, run_id=run_id, state_id=state["state_id"],
            projection_version=PROJECTION_VERSION, source_state_hash=state["state_hash"],
            projection_hash=p_hash, artifact_id=artifact.artifact_id,
            fields_json=canonical_json(list(INCLUDED_FIELDS)).decode(), created_at=utc_now(),
        )
        emit(
            run_id, "JEV_PROJECTION_CREATED", f"projection:{projection_id}",
            f"Jev projection created for {state['entity']['gene_symbol']}.",
            stage="JEV_WIDE",
            data={"projection_id": projection_id, "state_id": state["state_id"],
                  "projection_version": PROJECTION_VERSION, "source_state_hash": state["state_hash"],
                  "projection_hash": p_hash, "included_fields": list(INCLUDED_FIELDS)},
            artifact_refs=[artifact.ref()],
            registrations=[self.repository.artifact_registration(artifact, run_id), registration],
        )
        return projection_id, p_hash, artifact

    # ----------------------------------------------------------------- evaluate

    def evaluate(self, *, run_id: str, state: dict[str, Any], emit: Callable[..., Any]) -> dict[str, Any]:
        projection = build_projection(state)
        projection_id, p_hash, _ = self._register_projection(run_id=run_id, state=state, projection=projection,
                                                             emit=emit)
        applicability = applicability_map(projection)
        question_artifact = self._ensure_question_artifact(run_id)
        requested_model = self.settings.jev_model
        cache_key: str | None = None
        if is_pinned_model_identity(requested_model):
            cache_key = hashlib.sha256(canonical_json({
                "projection_hash": p_hash,
                "question_set_hash": question_set_hash(),
                "resolved_model": requested_model,
                "adapter_version": ADAPTER_VERSION,
            })).hexdigest()
            cached_id = self.repository.jev_cache_get(cache_key)
            if cached_id is not None:
                source = self.repository.get_evaluation(cached_id)
                if source is not None:
                    evaluation = self._cached_evaluation(state, source, projection_id, p_hash,
                                                         question_artifact, applicability)
                    return self._persist_evaluation(run_id, state, evaluation, emit, cache_key=cache_key,
                                                    provider_attempted=False)
        adapter = (
            self.adapter_factory() if self.adapter_factory is not None
            else TypeSafeAdapter(model=requested_model, timeout=self.settings.jev_timeout_seconds)
        )
        try:
            answer_set = adapter.evaluate(projection, WIDE_QUESTIONS)
            validated = validate_answers(WIDE_QUESTIONS, answer_set.answers)
        except (JevProviderError, JevContractError) as exc:
            return self._record_failure(run_id, state, projection_id, p_hash, question_artifact, applicability,
                                        exc, emit, provider_attempted=True)
        if cache_key is not None and answer_set.resolved_model != requested_model:
            cache_key = None
        evaluation = {
            "evaluation_id": str(uuid4()),
            "mode": "LIVE",
            "purpose": "WIDE",
            "input_ref_kind": "STATISTICAL_STATE",
            "input_ref_id": state["state_id"],
            "source_state_hash": state["state_hash"],
            "projection_id": projection_id,
            "projection_version": PROJECTION_VERSION,
            "projection_hash": p_hash,
            "question_set_version": WIDE_QUESTION_SET_VERSION,
            "question_hash": question_set_hash(),
            "question_definitions_ref": question_artifact.artifact_id,
            "requested_model": answer_set.requested_model,
            "resolved_model": answer_set.resolved_model,
            "adapter_version": ADAPTER_VERSION,
            "answers": validated,
            "applicability": applicability,
            "raw_answers_hash": hashlib.sha256(canonical_json(answer_set.answers)).hexdigest(),
            "request_id": answer_set.request_id,
            "usage": answer_set.usage,
            "latency_ms": answer_set.latency_ms,
            "cache_source_evaluation_id": None,
            "error": None,
            "routing_policy_version": None,
        }
        return self._persist_evaluation(run_id, state, evaluation, emit, cache_key=cache_key,
                                        provider_attempted=True)

    def _cached_evaluation(self, state: dict[str, Any], source: dict[str, Any], projection_id: str,
                           p_hash: str, question_artifact: Any,
                           applicability: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Reuse a stored judgment. Only reachable for a pinned model identity.

        Cache identity requires a pinned/versioned model name, so the requested
        name is the resolved identity the origin evaluation was recorded under;
        no mutable alias is ever treated as an already resolved model.
        """
        return {
            "evaluation_id": str(uuid4()),
            "mode": "LIVE",
            "purpose": "WIDE",
            "input_ref_kind": "STATISTICAL_STATE",
            "input_ref_id": state["state_id"],
            "source_state_hash": state["state_hash"],
            "projection_id": projection_id,
            "projection_version": PROJECTION_VERSION,
            "projection_hash": p_hash,
            "question_set_version": WIDE_QUESTION_SET_VERSION,
            "question_hash": question_set_hash(),
            "question_definitions_ref": question_artifact.artifact_id,
            "requested_model": source["model"],
            "resolved_model": source["model"],
            "adapter_version": ADAPTER_VERSION,
            "answers": source["vector"]["answers"],
            "applicability": applicability,
            "raw_answers_hash": source["vector"].get("raw_answers_hash"),
            "request_id": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "latency_ms": 0,
            "cache_source_evaluation_id": source["evaluation_id"],
            "error": None,
            "routing_policy_version": None,
        }

    def _persist_evaluation(self, run_id: str, state: dict[str, Any], evaluation: dict[str, Any],
                            emit: Callable[..., Any], *, cache_key: str | None,
                            provider_attempted: bool) -> dict[str, Any]:
        evaluation_id = evaluation["evaluation_id"]
        artifact = self._publish_json(run_id, f"runs/{run_id}/jev/{evaluation_id}.json", evaluation,
                                      "jev-evaluation")
        registration = self.repository.jev_evaluation_registration(
            evaluation_id=evaluation_id, run_id=run_id, candidate_id=None,
            input_ref_kind="STATISTICAL_STATE", input_ref_id=state["state_id"], purpose="WIDE",
            artifact_id=artifact.artifact_id, vector_json=canonical_json(evaluation).decode(),
            model=evaluation["resolved_model"], created_at=utc_now(),
        )
        registrations = [self.repository.artifact_registration(artifact, run_id), registration]
        if cache_key is not None and not evaluation["cache_source_evaluation_id"]:
            registrations.append(
                self.repository.jev_cache_registration(cache_key, evaluation_id, utc_now()),
            )
        emit(
            run_id, "JEV_WIDE_STATE_EVALUATED", f"jev-wide:{evaluation_id}",
            f"Jev wide judgment recorded for {state['entity']['gene_symbol']}.",
            stage="JEV_WIDE",
            data={
                "evaluation_id": evaluation_id, "state_id": state["state_id"],
                "projection_id": evaluation["projection_id"], "projection_hash": evaluation["projection_hash"],
                "cache": bool(evaluation["cache_source_evaluation_id"]),
                "cache_source_evaluation_id": evaluation["cache_source_evaluation_id"],
                "provider_attempted": provider_attempted,
                "model": evaluation["resolved_model"], "usage": evaluation["usage"],
                "applicability": evaluation["applicability"],
                "judgment_vector": evaluation["answers"],
                "question_set_version": WIDE_QUESTION_SET_VERSION,
            },
            artifact_refs=[artifact.ref()], registrations=registrations,
        )
        evaluation["artifact_id"] = artifact.artifact_id
        return evaluation

    def _record_failure(self, run_id: str, state: dict[str, Any], projection_id: str, p_hash: str,
                        question_artifact: Any, applicability: dict[str, dict[str, Any]], exc: Exception,
                        emit: Callable[..., Any], *, provider_attempted: bool) -> dict[str, Any]:
        code = getattr(exc, "code", type(exc).__name__)
        evaluation = {
            "evaluation_id": str(uuid4()),
            "mode": "LIVE",
            "purpose": "WIDE",
            "input_ref_kind": "STATISTICAL_STATE",
            "input_ref_id": state["state_id"],
            "source_state_hash": state["state_hash"],
            "projection_id": projection_id,
            "projection_version": PROJECTION_VERSION,
            "projection_hash": p_hash,
            "question_set_version": WIDE_QUESTION_SET_VERSION,
            "question_hash": question_set_hash(),
            "question_definitions_ref": question_artifact.artifact_id,
            "requested_model": self.settings.jev_model,
            "resolved_model": None,
            "adapter_version": ADAPTER_VERSION,
            "answers": {},
            "applicability": applicability,
            "raw_answers_hash": None,
            "request_id": None,
            "usage": {"input_tokens": None, "output_tokens": None},
            "latency_ms": None,
            "cache_source_evaluation_id": None,
            "error": {"code": str(code), "detail": str(exc)},
            "routing_policy_version": None,
        }
        evaluation_id = evaluation["evaluation_id"]
        artifact = self._publish_json(run_id, f"runs/{run_id}/jev/{evaluation_id}.json", evaluation,
                                      "jev-evaluation")
        registration = self.repository.jev_evaluation_registration(
            evaluation_id=evaluation_id, run_id=run_id, candidate_id=None,
            input_ref_kind="STATISTICAL_STATE", input_ref_id=state["state_id"], purpose="WIDE",
            artifact_id=artifact.artifact_id, vector_json=canonical_json(evaluation).decode(),
            model=evaluation["requested_model"], created_at=utc_now(),
        )
        emit(
            run_id, "JEV_EVALUATION_FAILED", f"jev-wide:{evaluation_id}:failed",
            f"Jev wide evaluation failed closed for {state['entity']['gene_symbol']}: {code}.",
            stage="JEV_WIDE", level="error",
            data={"evaluation_id": evaluation_id, "state_id": state["state_id"], "error_code": str(code),
                  "detail": str(exc), "provider_attempted": provider_attempted, "cache": False},
            artifact_refs=[artifact.ref()],
            registrations=[self.repository.artifact_registration(artifact, run_id), registration],
        )
        evaluation["artifact_id"] = artifact.artifact_id
        return evaluation
