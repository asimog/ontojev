"""Validated scientific reads; SQL decoding alone is not scientific acceptance.

Readers return canonical typed scientific objects bound to verified operational
ids, hashes and artifacts. Only genuinely presentation-bound artifacts (hypothesis
drafts, evaluation vectors, dossiers) are exposed as validated JSON.
"""

from __future__ import annotations

from dataclasses import dataclass

from cancerjev.domain._json import decode, obj, optional_string, string, version
from cancerjev.domain.codecs import read_evidence, read_state
from cancerjev.domain.envelopes import EvidenceRecord, StateRecord
from cancerjev.domain.evidence import EvidenceState
from cancerjev.domain.hypotheses import DRAFT_FIELDS, HypothesisDraft, read_hypothesis_draft
from cancerjev.domain.measurements import ContractError
from cancerjev.domain.scientific import StatisticalState
from cancerjev.jev.contracts import JevContractError, ValidatedAnswers, read_answers
from cancerjev.jev.projection import projection_hash
from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    DEEP_QUESTIONS,
    HYPOTHESIS_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTIONS,
    WIDE_QUESTION_SET_VERSION,
    WIDE_QUESTIONS,
    applicability_map,
    question_set_hash,
)
from cancerjev.storage.artifacts import ArtifactStore, artifact_id_for
from cancerjev.storage.repositories import Repository


class ScientificReadError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class VerifiedArtifact:
    artifact_id: str
    sha256: str
    content: bytes

    def boundary_representation(self) -> dict[str, object]:
        return obj(decode(self.content))


@dataclass(frozen=True)
class StoredState:
    state_id: str
    run_id: str
    state_hash: str
    artifact: VerifiedArtifact
    record: StateRecord

    def __post_init__(self) -> None:
        if (self.record.state_id, self.record.state_hash) != (self.state_id, self.state_hash):
            raise ScientificReadError("RECORD_BINDING_MISMATCH", "state record binding")

    @property
    def state(self) -> StatisticalState:
        return self.record.state


@dataclass(frozen=True)
class StoredEvidence:
    evidence_state_id: str
    candidate_id: str
    iteration: int
    parent_id: str | None
    artifact: VerifiedArtifact
    record: EvidenceRecord

    def __post_init__(self) -> None:
        if (self.record.evidence_state_id, self.record.revision.revision_index) != (
                self.evidence_state_id, self.iteration):
            raise ScientificReadError("RECORD_BINDING_MISMATCH", "evidence record binding")

    @property
    def evidence(self) -> EvidenceState:
        return self.record.revision


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ScientificReadError("RECORD_BINDING_MISMATCH", label)


def read_artifact(repository: Repository, artifacts: ArtifactStore, artifact_id: str,
                  *, run_id: str | None = None) -> VerifiedArtifact:
    metadata = repository.artifact(artifact_id)
    if metadata is None:
        raise ScientificReadError("EVIDENCE_ARTIFACT_MISSING", artifact_id)
    try:
        path = string(metadata["relative_path"])
        digest = string(metadata["sha256"])
        require_equal(metadata["artifact_id"], artifact_id, "artifact id")
        require_equal(artifact_id_for(path, digest), artifact_id, "artifact path/content identity")
        if run_id is not None:
            require_equal(metadata["run_id"], run_id, "artifact run")
        content = artifacts.read(path, digest, expected_size=metadata["size_bytes"])
    except FileNotFoundError as exc:
        raise ScientificReadError("EVIDENCE_ARTIFACT_UNAVAILABLE", artifact_id) from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ScientificReadError):
            raise
        raise ScientificReadError("EVIDENCE_ARTIFACT_CORRUPT", artifact_id) from exc
    return VerifiedArtifact(artifact_id, digest, content)


def read_state_record(repository: Repository, artifacts: ArtifactStore, state_id: str) -> StoredState:
    row = repository.get_state(state_id)
    if row is None:
        raise ScientificReadError("EVIDENCE_STATE_MISSING", state_id)
    artifact = read_artifact(repository, artifacts, row["artifact_id"], run_id=row["run_id"])
    try:
        state = read_state(artifact.content, expected_hash=row["state_hash"])
        require_equal(state.entity.gene_id, row["summary"]["entity"]["gene_id"], "state entity")
    except ContractError as exc:
        code = "EVIDENCE_STATE_HASH_MISMATCH" if "hash" in str(exc).lower() else exc.code
        raise ScientificReadError(code, str(exc)) from exc
    except (KeyError, TypeError) as exc:
        raise ScientificReadError("RECORD_BINDING_MISMATCH", state_id) from exc
    return StoredState(state_id, row["run_id"], row["state_hash"], artifact,
                       StateRecord(state_id, row["state_hash"], state))


def read_candidate_state(repository: Repository, artifacts: ArtifactStore,
                         candidate_id: str) -> StoredState:
    candidate = repository.get_candidate(candidate_id)
    if candidate is None:
        raise ScientificReadError("CANDIDATE_MISSING", candidate_id)
    state = read_state_record(repository, artifacts, candidate["source_state_id"])
    require_equal(state.run_id, candidate["run_id"], "candidate run")
    require_equal(state.state.entity.gene_id, candidate["entity"]["gene_id"], "candidate gene")
    return state


def read_evidence_record(repository: Repository, artifacts: ArtifactStore,
                         evidence_state_id: str, *, _ancestors: frozenset[str] = frozenset()) -> StoredEvidence:
    if evidence_state_id in _ancestors or len(_ancestors) > 2:
        raise ScientificReadError("RECORD_BINDING_MISMATCH", "cyclic or overlong revision ancestry")
    row = repository.get_evidence_state(evidence_state_id)
    if row is None:
        raise ScientificReadError("EVIDENCE_STATE_MISSING", evidence_state_id)
    artifact = read_artifact(repository, artifacts, row["artifact_id"], run_id=row["run_id"])
    try:
        evidence = read_evidence(artifact.content, expected_hash=row["evidence_hash"])
        state = read_candidate_state(repository, artifacts, row["candidate_id"])
        require_equal(state.run_id, row["run_id"], "revision run")
        require_equal(evidence.accepted_state_hash, state.state_hash, "accepted state")
        require_equal(evidence.revision_index, row["iteration"], "revision iteration")
        require_equal(evidence.entity.gene_id, state.state.entity.gene_id, "revision entity")
        parent_id = row["previous_evidence_state_id"]
        if row["iteration"] == 0:
            require_equal(parent_id, None, "baseline parent")
        else:
            if parent_id is None:
                raise ScientificReadError("RECORD_BINDING_MISMATCH", "revision requires a parent")
            parent = read_evidence_record(repository, artifacts, parent_id,
                                          _ancestors=_ancestors | {evidence_state_id})
            require_equal(parent.candidate_id, row["candidate_id"], "parent candidate")
            require_equal(parent.iteration + 1, row["iteration"], "parent iteration")
            require_equal(evidence.parent_evidence_hash, parent.record.evidence_hash, "parent identity")
    except ContractError as exc:
        raise ScientificReadError(exc.code, str(exc)) from exc
    except (KeyError, TypeError) as exc:
        raise ScientificReadError("RECORD_BINDING_MISMATCH", evidence_state_id) from exc
    return StoredEvidence(evidence_state_id, row["candidate_id"], row["iteration"],
                          row["previous_evidence_state_id"], artifact,
                          EvidenceRecord(evidence_state_id, row["evidence_hash"], evidence))


def read_revision_chain(repository: Repository, artifacts: ArtifactStore,
                        candidate_id: str) -> tuple[StoredEvidence, ...]:
    candidate = repository.get_candidate(candidate_id)
    if candidate is None:
        raise ScientificReadError("CANDIDATE_MISSING", candidate_id)
    rows = repository.evidence_revisions(candidate_id)
    revisions = tuple(read_evidence_record(repository, artifacts, row["evidence_state_id"])
                      for row in rows)
    parent: StoredEvidence | None = None
    for index, revision in enumerate(revisions):
        require_equal(revision.iteration, index, "contiguous revision chain")
        require_equal(revision.parent_id, parent.evidence_state_id if parent else None, "parent chain")
        parent = revision
    require_equal(candidate["latest_evidence_state_id"],
                  parent.evidence_state_id if parent else None, "authoritative latest revision")
    return revisions


@dataclass(frozen=True)
class StoredHypothesis:
    hypothesis_id: str
    evidence_state_id: str
    draft: HypothesisDraft
    artifact: VerifiedArtifact


def read_hypothesis_record(repository: Repository, artifacts: ArtifactStore, hypothesis_id: str,
                           *, candidate_id: str, allowed_action_ids: frozenset[str]) -> StoredHypothesis:
    row = repository.get_hypothesis(hypothesis_id)
    if row is None:
        raise ScientificReadError("HYPOTHESIS_MISSING", hypothesis_id)
    artifact = read_artifact(repository, artifacts, row["artifact_id"], run_id=row["run_id"])
    try:
        payload = artifact.boundary_representation()
        require_equal(payload, row["hypothesis"], "hypothesis artifact/record")
        for key in ("hypothesis_id", "candidate_id", "evidence_state_id"):
            require_equal(payload[key], row[key], f"hypothesis {key}")
        require_equal(row["candidate_id"], candidate_id, "hypothesis candidate")
        revision = read_evidence_record(repository, artifacts, row["evidence_state_id"])
        require_equal(revision.candidate_id, candidate_id, "hypothesis revision candidate")
        draft = read_hypothesis_draft(
            {key: payload[key] for key in DRAFT_FIELDS},
            allowed_action_ids=allowed_action_ids,
            label=string(payload["label"]), generator=string(payload["generator"]),
            generator_model=optional_string(payload.get("generator_model")),
        )
        require_equal(payload["proposed_action_ids"], list(draft.distinguishing_tests),
                      "hypothesis proposed actions")
        if payload.get("factual_observation_refs") != []:
            raise ScientificReadError("INVALID_HYPOTHESIS", "generated text cannot add measured facts")
    except (ContractError, KeyError, TypeError) as exc:
        raise ScientificReadError("INVALID_HYPOTHESIS", str(exc)) from exc
    return StoredHypothesis(hypothesis_id, row["evidence_state_id"], draft, artifact)


@dataclass(frozen=True)
class StoredEvaluation:
    evaluation_id: str
    purpose: str
    input_ref_id: str
    answers: ValidatedAnswers | None
    error_code: str | None
    artifact: VerifiedArtifact


def read_evaluation_record(repository: Repository, artifacts: ArtifactStore,
                           evaluation_id: str) -> StoredEvaluation:
    row = repository.get_evaluation(evaluation_id)
    if row is None:
        raise ScientificReadError("EVALUATION_MISSING", evaluation_id)
    artifact = read_artifact(repository, artifacts, row["artifact_id"], run_id=row["run_id"])
    try:
        payload = artifact.boundary_representation()
        require_equal(payload, row["vector"], "evaluation artifact/vector")
        for key in ("evaluation_id", "purpose", "input_ref_kind", "input_ref_id"):
            require_equal(payload[key], row[key], f"evaluation {key}")
        definitions_by_version = {
            WIDE_QUESTION_SET_VERSION: ("WIDE", "STATISTICAL_STATE", WIDE_QUESTIONS),
            DEEP_QUESTION_SET_VERSION: ("DEEP", "EVIDENCE_STATE", DEEP_QUESTIONS),
            HYPOTHESIS_QUESTION_SET_VERSION: ("HYPOTHESIS", "HYPOTHESIS", HYPOTHESIS_QUESTIONS),
        }
        question_version = string(payload["question_set_version"])
        if question_version not in definitions_by_version:
            raise ScientificReadError("UNSUPPORTED_QUESTION_VERSION", question_version)
        purpose, input_kind, definitions = definitions_by_version[question_version]
        require_equal(payload["purpose"], purpose, "question purpose")
        require_equal(payload["input_ref_kind"], input_kind, "question input kind")
        require_equal(payload["question_hash"], question_set_hash(definitions, question_version),
                      "question hash")
        if input_kind == "STATISTICAL_STATE":
            input_state = repository.get_state(row["input_ref_id"])
            if input_state is None:
                raise ScientificReadError("EVIDENCE_STATE_MISSING", row["input_ref_id"])
            require_equal(payload["source_state_hash"], input_state["state_hash"], "judged state identity")
        else:
            revision_id = string(payload["evidence_state_id"])
            revision_row = repository.get_evidence_state(revision_id)
            if revision_row is None:
                raise ScientificReadError("EVIDENCE_STATE_MISSING", revision_id)
            require_equal(payload["source_evidence_hash"], revision_row["evidence_hash"],
                          "judged evidence identity")
            require_equal(row["candidate_id"], revision_row["candidate_id"], "judged candidate")
            if input_kind == "EVIDENCE_STATE":
                require_equal(row["input_ref_id"], revision_id, "judged revision id")
            else:
                hypothesis_row = repository.get_hypothesis(row["input_ref_id"])
                if hypothesis_row is None:
                    raise ScientificReadError("HYPOTHESIS_MISSING", row["input_ref_id"])
                require_equal(hypothesis_row["evidence_state_id"], revision_id,
                              "hypothesis review revision")
                require_equal(hypothesis_row["candidate_id"], row["candidate_id"],
                              "hypothesis review candidate")
        error = payload["error"]
        if error is not None:
            error_code = string(obj(error)["code"])
            require_equal(payload["answers"], {}, "failed evaluation cannot carry answers")
            answers = None
        else:
            error_code = None
            answers = read_answers(definitions, payload["answers"])
            require_equal(answers.boundary_representation(), payload["answers"], "answer fields")
            require_equal(payload["resolved_model"], row["model"], "model binding")
            question_artifact = read_artifact(repository, artifacts,
                                              string(payload["question_definitions_ref"]),
                                              run_id=row["run_id"])
            require_equal(question_artifact.boundary_representation(), {
                "question_set_version": question_version,
                "question_set_hash": payload["question_hash"],
                "questions": [{"question_id": q.question_id, "primitive": q.primitive,
                               "version": q.version, "instructions": q.instructions,
                               "criteria": q.criteria, "applicability_rule": q.applicability_rule}
                              for q in definitions],
            }, "original question definitions")
            path = f"runs/{row['run_id']}/jev/projections/{payload['projection_id']}.json"
            metadata = repository.artifact_at_path(path)
            # Wide cache reuse may reference an earlier run's projection row.
            if metadata is None and purpose == "WIDE":
                projection_row = repository.find_projection(row["input_ref_id"],
                                                            string(payload["projection_version"]))
                if projection_row is not None:
                    metadata = repository.artifact(projection_row["artifact_id"])
            if metadata is None:
                raise ScientificReadError("PROJECTION_MISSING", path)
            projection = read_artifact(repository, artifacts, metadata["artifact_id"])
            projected = projection.boundary_representation()
            require_equal(projection_hash(projected), payload["projection_hash"], "projection identity")
            require_equal(projected["projection_version"], payload["projection_version"],
                          "projection version")
            require_equal(applicability_map(projected, definitions), payload["applicability"],
                          "applicability")
    except (ContractError, JevContractError, KeyError, TypeError) as exc:
        raise ScientificReadError("INVALID_EVALUATION", str(exc)) from exc
    return StoredEvaluation(evaluation_id, row["purpose"], row["input_ref_id"], answers, error_code, artifact)


def read_dossier_record(repository: Repository, artifacts: ArtifactStore,
                        dossier_id: str) -> VerifiedArtifact:
    row = repository.get_dossier(dossier_id)
    if row is None:
        raise ScientificReadError("DOSSIER_MISSING", dossier_id)
    artifact = read_artifact(repository, artifacts, row["json_artifact_id"], run_id=row["run_id"])
    try:
        payload = artifact.boundary_representation()
        schema = version(payload)
        if schema != 2:
            raise ScientificReadError("UNSUPPORTED_SCHEMA_VERSION", "dossier version")
        for key in ("dossier_id", "candidate_id", "run_id"):
            require_equal(payload[key], row[key], f"dossier {key}")
        if schema == 2:
            chain = read_revision_chain(repository, artifacts, row["candidate_id"])
            require_equal(payload["evidence_state_ids"], [r.evidence_state_id for r in chain],
                          "dossier authoritative revision chain")
    except (ContractError, KeyError, TypeError) as exc:
        raise ScientificReadError("INVALID_DOSSIER", str(exc)) from exc
    return artifact
