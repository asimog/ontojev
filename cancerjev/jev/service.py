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
    EVIDENCE_INCLUDED_FIELDS,
    EVIDENCE_PROJECTION_VERSION,
    HYPOTHESIS_INCLUDED_FIELDS,
    HYPOTHESIS_PROJECTION_VERSION,
    INCLUDED_FIELDS,
    PROJECTION_VERSION,
    ProjectionError,
    build_evidence_projection,
    build_hypothesis_projection,
    build_projection,
    projection_hash,
)
from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    DEEP_QUESTIONS,
    HYPOTHESIS_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTIONS,
    WIDE_QUESTION_SET_VERSION,
    WIDE_QUESTIONS,
    QuestionDefinition,
    applicability_map,
    deep_question_set_hash,
    hypothesis_question_set_hash,
    wide_question_set_hash,
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


@dataclass(frozen=True)
class EvaluationContext:
    """What a Jev evaluation is about, independent of how it is judged."""

    purpose: str
    input_ref_kind: str
    input_ref_id: str
    subject: str
    stage: str
    projection_version: str
    projection_id: str
    projection_hash: str
    question_set_version: str
    question_set_hash: str
    question_definitions_ref: str
    event_type: str
    event_key_prefix: str
    registered: bool = True

    def payload(self) -> dict[str, Any]:
        return {
            "purpose": self.purpose,
            "input_ref_kind": self.input_ref_kind,
            "input_ref_id": self.input_ref_id,
            "stage": self.stage,
            "projection_id": self.projection_id,
            "projection_version": self.projection_version,
            "projection_hash": self.projection_hash,
            "question_set_version": self.question_set_version,
            "question_hash": self.question_set_hash,
            "question_definitions_ref": self.question_definitions_ref,
        }


@dataclass(frozen=True)
class JudgementSpec:
    """What one judgment is about and how it is recorded."""

    purpose: str
    input_ref_kind: str
    input_ref_id: str
    label: str
    stage: str
    questions: tuple[QuestionDefinition, ...]
    question_set_version: str
    set_hash: str
    projection_version: str
    event_type: str
    event_prefix: str
    common: dict[str, Any]


@dataclass
class JevService:
    settings: Settings
    repository: Repository
    artifacts: ArtifactStore
    adapter_factory: Callable[[], TypeSafeAdapter] | None = None
    _question_artifacts: dict[tuple[str, str], Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ helpers

    def _publish_json(self, run_id: str, relative_path: str, payload: Any, purpose: str) -> Any:
        return self.artifacts.publish(relative_path, canonical_json(payload), "application/json", purpose)

    def _ensure_question_artifact(self, run_id: str, *, version: str,
                                  definitions: tuple[QuestionDefinition, ...],
                                  set_hash: str) -> Any:
        key = (run_id, version)
        if key in self._question_artifacts:
            return self._question_artifacts[key]
        payload = {
            "question_set_version": version,
            "question_set_hash": set_hash,
            "questions": [
                {
                    "question_id": definition.question_id,
                    "primitive": definition.primitive,
                    "version": definition.version,
                    "instructions": definition.instructions,
                    "criteria": definition.criteria,
                    "applicability_rule": definition.applicability_rule,
                }
                for definition in definitions
            ],
        }
        artifact = self._publish_json(run_id, f"runs/{run_id}/jev/questions-{version}.json", payload,
                                      "jev-question-set")
        self.repository.register_artifact(artifact, run_id)
        self._question_artifacts[key] = artifact
        return artifact

    def _cache_key(self, *, projection_hash_value: str, question_set_hash_value: str,
                   requested_model: str) -> str | None:
        if not is_pinned_model_identity(requested_model):
            return None
        return hashlib.sha256(canonical_json({
            "projection_hash": projection_hash_value,
            "question_set_hash": question_set_hash_value,
            "resolved_model": requested_model,
            "adapter_version": ADAPTER_VERSION,
        })).hexdigest()

    def _projection_id(self) -> str:
        return str(uuid4())

    def _register_projection(self, *, run_id: str, state: dict[str, Any], projection: dict[str, Any],
                             emit: Callable[..., Any]) -> tuple[str, str, Any]:
        existing = self.repository.find_projection(state["state_id"], PROJECTION_VERSION)
        if existing is not None:
            metadata = self.repository.artifact(existing["artifact_id"])
            return existing["projection_id"], existing["projection_hash"], metadata
        projection_id = self._projection_id()
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

    def _invoke(self, adapter: TypeSafeAdapter, projection: dict[str, Any],
                questions: tuple[QuestionDefinition, ...]) -> tuple[Any, dict[str, dict[str, Any]]]:
        """One provider call plus fail-closed validation of its answers."""
        answer_set = adapter.evaluate(projection, questions)
        return answer_set, validate_answers(questions, answer_set.answers)

    def evaluate(self, *, run_id: str, state: dict[str, Any], emit: Callable[..., Any]) -> dict[str, Any]:
        projection = build_projection(state)
        projection_id, p_hash, _ = self._register_projection(run_id=run_id, state=state, projection=projection,
                                                             emit=emit)
        applicability = applicability_map(projection)
        question_artifact = self._ensure_question_artifact(
            run_id, version=WIDE_QUESTION_SET_VERSION, definitions=WIDE_QUESTIONS,
            set_hash=wide_question_set_hash(),
        )
        requested_model = self.settings.jev_model
        cache_key = self._cache_key(projection_hash_value=p_hash,
                                    question_set_hash_value=wide_question_set_hash(),
                                    requested_model=requested_model)
        if cache_key is not None:
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
            answer_set, validated = self._invoke(adapter, projection, WIDE_QUESTIONS)
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
            "question_hash": wide_question_set_hash(),
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

    def _projection_failure(self, *, run_id: str, subject_record: dict[str, Any], spec: JudgementSpec,
                            exc: Exception, emit: Callable[..., Any]) -> dict[str, Any]:
        """Persist a typed failure when an input cannot be projected at all.

        A projection that exceeds the byte cap or carries an unsupported schema is
        a fail-closed outcome, never a run abort: the revision or generated text it
        came from stands and the failure is recorded.
        """
        code = getattr(exc, "code", type(exc).__name__)
        evaluation = {
            "evaluation_id": str(uuid4()), "mode": "LIVE", "purpose": spec.purpose,
            "input_ref_kind": spec.input_ref_kind, "input_ref_id": spec.input_ref_id,
            "projection_id": None, "projection_version": spec.projection_version,
            "projection_hash": None, "question_set_version": spec.question_set_version,
            "question_hash": spec.set_hash, "question_definitions_ref": None,
            "adapter_version": ADAPTER_VERSION, "applicability": {},
            "routing_policy_version": None, **spec.common,
            "requested_model": self.settings.jev_model, "resolved_model": None,
            "answers": {}, "raw_answers_hash": None, "request_id": None,
            "usage": {"input_tokens": None, "output_tokens": None}, "latency_ms": None,
            "cache_source_evaluation_id": None,
            "error": {"code": str(code), "detail": str(exc)},
        }
        return self._persist_evaluation(run_id, subject_record, evaluation, emit, cache_key=None,
                                        provider_attempted=False, purpose=spec.purpose, stage=spec.stage,
                                        subject=spec.label, event_type=None, event_prefix=spec.event_prefix)

    def evaluate_evidence(self, *, run_id: str, evidence: dict[str, Any],
                          eligible_actions: list[dict[str, Any]], evidence_hash: str,
                          emit: Callable[..., Any]) -> dict[str, Any]:
        """Judge one immutable EvidenceState revision with the deep question set.

        The projection carries the revision's recorded checks, its copied
        project-level evidence, its missing evidence and the eligible registered
        action set. The judgment is an input to Python policy: it neither selects
        nor executes an action, and no measured field is written from it.
        """
        deep_spec = JudgementSpec(
            purpose="DEEP", input_ref_kind="EVIDENCE_STATE", input_ref_id=evidence["evidence_state_id"],
            label=(evidence.get("entity") or {}).get("gene_symbol") or evidence["evidence_state_id"],
            stage="JEV_DEEP", questions=DEEP_QUESTIONS,
            question_set_version=DEEP_QUESTION_SET_VERSION, set_hash=deep_question_set_hash(),
            projection_version=EVIDENCE_PROJECTION_VERSION, event_prefix="jev-deep",
            event_type="JEV_DEEP_EVIDENCE_JUDGED",
            common={
                "source_state_hash": (evidence.get("source_statistical_state") or {}).get("state_identity_hash"),
                "source_evidence_hash": evidence_hash,
                "evidence_state_id": evidence["evidence_state_id"],
                "candidate_id": evidence.get("candidate_id"),
                "action_id": (evidence.get("action") or {}).get("action_id"),
            },
        )
        try:
            projection = build_evidence_projection(evidence, eligible_actions, evidence_hash=evidence_hash)
        except ProjectionError as exc:
            return self._projection_failure(run_id=run_id, subject_record=evidence, spec=deep_spec,
                                           exc=exc, emit=emit)
        projection_id = self._projection_id()
        p_hash = projection_hash(projection)
        projection_artifact = self._publish_json(
            run_id, f"runs/{run_id}/jev/projections/{projection_id}.json", projection,
            "jev-evidence-projection",
        )
        input_ref_id = evidence["evidence_state_id"]
        emit(
            run_id, "JEV_PROJECTION_CREATED", f"projection:{projection_id}",
            f"Jev evidence projection created for revision {input_ref_id}.",
            stage="JEV_DEEP",
            data={"projection_id": projection_id, "input_ref_kind": "EVIDENCE_STATE",
                  "input_ref_id": input_ref_id, "projection_version": EVIDENCE_PROJECTION_VERSION,
                  "source_evidence_hash": evidence_hash, "projection_hash": p_hash,
                  "included_fields": list(EVIDENCE_INCLUDED_FIELDS)},
            artifact_refs=[projection_artifact.ref()],
            registrations=[self.repository.artifact_registration(projection_artifact, run_id)],
        )
        question_artifact = self._ensure_question_artifact(
            run_id, version=DEEP_QUESTION_SET_VERSION, definitions=DEEP_QUESTIONS,
            set_hash=deep_question_set_hash(),
        )
        return self._judge(run_id=run_id, subject_record=evidence, projection=projection,
                           projection_id=projection_id, p_hash=p_hash,
                           question_artifact=question_artifact, spec=deep_spec, emit=emit)

    def evaluate_hypothesis(self, *, run_id: str, hypothesis: dict[str, Any], evidence: dict[str, Any],
                            eligible_actions: list[dict[str, Any]], evidence_hash: str,
                            emit: Callable[..., Any]) -> dict[str, Any]:
        """Judge one generated hypothesis against the revision it came from.

        The generated text is carried into the projection verbatim and labelled with
        its generator; the judgment is an input to Python policy, never evidence, and
        never a measured field.
        """
        input_ref_id = hypothesis["hypothesis_id"]
        spec = JudgementSpec(
            purpose="HYPOTHESIS", input_ref_kind="HYPOTHESIS", input_ref_id=input_ref_id,
            label=hypothesis.get("label") or input_ref_id, stage="HYPOTHESIS_VERIFICATION",
            questions=HYPOTHESIS_QUESTIONS,
            question_set_version=HYPOTHESIS_QUESTION_SET_VERSION,
            set_hash=hypothesis_question_set_hash(),
            projection_version=HYPOTHESIS_PROJECTION_VERSION, event_prefix="jev-hypothesis",
            event_type="HYPOTHESIS_EVALUATED",
            common={
                "source_state_hash": (evidence.get("source_statistical_state") or {}).get("state_identity_hash"),
                "source_evidence_hash": evidence_hash,
                "evidence_state_id": evidence.get("evidence_state_id"),
                "hypothesis_id": input_ref_id,
                "candidate_id": evidence.get("candidate_id"),
                "generator": hypothesis.get("generator"),
            },
        )
        try:
            projection = build_hypothesis_projection(hypothesis, evidence,
                                                     eligible_actions=eligible_actions,
                                                     evidence_hash=evidence_hash)
        except ProjectionError as exc:
            return self._projection_failure(run_id=run_id, subject_record=hypothesis, spec=spec,
                                           exc=exc, emit=emit)
        projection_id = self._projection_id()
        p_hash = projection_hash(projection)
        projection_artifact = self._publish_json(
            run_id, f"runs/{run_id}/jev/projections/{projection_id}.json", projection,
            "jev-hypothesis-projection",
        )
        emit(
            run_id, "JEV_PROJECTION_CREATED", f"projection:{projection_id}",
            f"Jev hypothesis projection created for hypothesis {input_ref_id}.",
            stage="HYPOTHESIS_VERIFICATION",
            data={"projection_id": projection_id, "input_ref_kind": "HYPOTHESIS",
                  "input_ref_id": input_ref_id, "projection_version": HYPOTHESIS_PROJECTION_VERSION,
                  "source_evidence_hash": evidence_hash, "projection_hash": p_hash,
                  "included_fields": list(HYPOTHESIS_INCLUDED_FIELDS)},
            artifact_refs=[projection_artifact.ref()],
            registrations=[self.repository.artifact_registration(projection_artifact, run_id)],
        )
        question_artifact = self._ensure_question_artifact(
            run_id, version=HYPOTHESIS_QUESTION_SET_VERSION, definitions=HYPOTHESIS_QUESTIONS,
            set_hash=hypothesis_question_set_hash(),
        )
        return self._judge(run_id=run_id, subject_record=hypothesis, projection=projection,
                           projection_id=projection_id, p_hash=p_hash,
                           question_artifact=question_artifact, spec=spec, emit=emit)

    def _judge(self, *, run_id: str, subject_record: dict[str, Any], projection: dict[str, Any],
               projection_id: str, p_hash: str, question_artifact: Any, spec: JudgementSpec,
               emit: Callable[..., Any]) -> dict[str, Any]:
        """Shared judgment path: cache, fail-closed provider call, persistence."""
        applicability = applicability_map(projection, spec.questions)
        requested_model = self.settings.jev_model
        common = {
            "evaluation_id": str(uuid4()),
            "mode": "LIVE",
            "purpose": spec.purpose,
            "input_ref_kind": spec.input_ref_kind,
            "input_ref_id": spec.input_ref_id,
            "projection_id": projection_id,
            "projection_version": spec.projection_version,
            "projection_hash": p_hash,
            "question_set_version": spec.question_set_version,
            "question_hash": spec.set_hash,
            "question_definitions_ref": question_artifact.artifact_id,
            "adapter_version": ADAPTER_VERSION,
            "applicability": applicability,
            "routing_policy_version": None,
            **spec.common,
        }
        persist = dict(purpose=spec.purpose, stage=spec.stage, subject=spec.label,
                       event_type=spec.event_type, event_prefix=spec.event_prefix)
        cache_key = self._cache_key(projection_hash_value=p_hash, question_set_hash_value=spec.set_hash,
                                    requested_model=requested_model)
        if cache_key is not None:
            cached_id = self.repository.jev_cache_get(cache_key)
            if cached_id is not None:
                source = self.repository.get_evaluation(cached_id)
                if source is not None:
                    evaluation = {
                        **common,
                        "requested_model": source["model"], "resolved_model": source["model"],
                        "answers": source["vector"]["answers"],
                        "raw_answers_hash": source["vector"].get("raw_answers_hash"),
                        "request_id": None, "usage": {"input_tokens": 0, "output_tokens": 0},
                        "latency_ms": 0, "cache_source_evaluation_id": source["evaluation_id"],
                        "error": None,
                    }
                    return self._persist_evaluation(run_id, subject_record, evaluation, emit,
                                                    cache_key=cache_key, provider_attempted=False,
                                                    **persist)
        adapter = (
            self.adapter_factory() if self.adapter_factory is not None
            else TypeSafeAdapter(model=requested_model, timeout=self.settings.jev_timeout_seconds)
        )
        try:
            answer_set, validated = self._invoke(adapter, projection, spec.questions)
        except (JevProviderError, JevContractError) as exc:
            code = getattr(exc, "code", type(exc).__name__)
            evaluation = {
                **common,
                "requested_model": requested_model, "resolved_model": None,
                "answers": {}, "raw_answers_hash": None, "request_id": None,
                "usage": {"input_tokens": None, "output_tokens": None}, "latency_ms": None,
                "cache_source_evaluation_id": None,
                "error": {"code": str(code), "detail": str(exc)},
            }
            return self._persist_evaluation(run_id, subject_record, evaluation, emit, cache_key=None,
                                            provider_attempted=True, **persist)
        if cache_key is not None and answer_set.resolved_model != requested_model:
            cache_key = None
        evaluation = {
            **common,
            "requested_model": answer_set.requested_model, "resolved_model": answer_set.resolved_model,
            "answers": validated,
            "raw_answers_hash": hashlib.sha256(canonical_json(answer_set.answers)).hexdigest(),
            "request_id": answer_set.request_id, "usage": answer_set.usage,
            "latency_ms": answer_set.latency_ms, "cache_source_evaluation_id": None, "error": None,
        }
        return self._persist_evaluation(run_id, subject_record, evaluation, emit, cache_key=cache_key,
                                        provider_attempted=True, **persist)

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
            "question_hash": wide_question_set_hash(),
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

    def _persist_evaluation(self, run_id: str, subject_record: dict[str, Any], evaluation: dict[str, Any],
                            emit: Callable[..., Any], *, cache_key: str | None, provider_attempted: bool,
                            purpose: str = "WIDE", stage: str = "JEV_WIDE",
                            subject: str | None = None, event_type: str | None = None,
                            event_prefix: str | None = None) -> dict[str, Any]:
        """Persist one evaluation (success or fail-closed failure) with its event.

        ``subject_record`` is the evaluated StatisticalState or EvidenceState
        revision; only its identifiers are read here, so one path serves both the
        wide state fan-out and the deep evidence fan-out.
        """
        evaluation_id = evaluation["evaluation_id"]
        artifact = self._publish_json(run_id, f"runs/{run_id}/jev/{evaluation_id}.json", evaluation,
                                      "jev-evaluation")
        input_ref_kind = evaluation["input_ref_kind"]
        input_ref_id = evaluation["input_ref_id"]
        error = evaluation.get("error")
        registration = self.repository.jev_evaluation_registration(
            evaluation_id=evaluation_id, run_id=run_id,
            candidate_id=evaluation.get("candidate_id") if purpose == "DEEP"
            else subject_record.get("candidate_id"),
            input_ref_kind=input_ref_kind, input_ref_id=input_ref_id, purpose=purpose,
            artifact_id=artifact.artifact_id, vector_json=canonical_json(evaluation).decode(),
            model=evaluation["resolved_model"] or evaluation["requested_model"], created_at=utc_now(),
        )
        registrations = [self.repository.artifact_registration(artifact, run_id), registration]
        if cache_key is not None and not evaluation["cache_source_evaluation_id"]:
            registrations.append(
                self.repository.jev_cache_registration(cache_key, evaluation_id, utc_now()),
            )
        label = subject or (subject_record.get("entity") or {}).get("gene_symbol") or input_ref_id
        prefix = event_prefix or ("jev-wide" if purpose == "WIDE" else "jev-deep")
        data = {
            "evaluation_id": evaluation_id,
            "purpose": purpose,
            "input_ref_kind": input_ref_kind,
            "input_ref_id": input_ref_id,
            "state_id": input_ref_id if input_ref_kind == "STATISTICAL_STATE" else None,
            "evidence_state_id": input_ref_id if input_ref_kind == "EVIDENCE_STATE" else None,
            "projection_id": evaluation["projection_id"],
            "projection_hash": evaluation["projection_hash"],
            "cache": bool(evaluation["cache_source_evaluation_id"]),
            "cache_source_evaluation_id": evaluation["cache_source_evaluation_id"],
            "provider_attempted": provider_attempted,
            "model": evaluation["resolved_model"] or evaluation["requested_model"],
            "usage": evaluation["usage"],
            "applicability": evaluation["applicability"],
            "judgment_vector": evaluation["answers"],
            "question_set_version": evaluation["question_set_version"],
        }
        if input_ref_kind == "HYPOTHESIS":
            data["hypothesis_id"] = input_ref_id
        if evaluation.get("evidence_state_id") is not None:
            data["input_evidence_state_id"] = evaluation["evidence_state_id"]
            data["evidence_state_id"] = evaluation["evidence_state_id"]
        if evaluation.get("generator") is not None:
            data["generator"] = evaluation["generator"]
        if error is not None:
            event_type = "JEV_EVALUATION_FAILED"
            key = f"{prefix}:{evaluation_id}:failed"
            message = f"Jev {purpose.lower()} evaluation failed closed for {label}: {error['code']}."
            data["error_code"] = error["code"]
            data["detail"] = error["detail"]
            if evaluation.get("action_id") is not None:
                data["action_id"] = evaluation["action_id"]
        else:
            event_type = event_type or (
                "JEV_WIDE_STATE_EVALUATED" if purpose == "WIDE" else "JEV_DEEP_EVIDENCE_JUDGED"
            )
            key = f"{prefix}:{evaluation_id}"
            message = f"Jev {purpose.lower()} judgment recorded for {label}."
        emit(
            run_id, event_type, key, message, stage=stage, level="error" if error is not None else "info",
            data=data, artifact_refs=[artifact.ref()], registrations=registrations,
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
            "question_hash": wide_question_set_hash(),
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
        return self._persist_evaluation(run_id, state, evaluation, emit, cache_key=None,
                                        provider_attempted=provider_attempted, purpose="WIDE",
                                        stage="JEV_WIDE")
