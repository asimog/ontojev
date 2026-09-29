"""Director control state. None of these records is measured biological evidence."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=2000)]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")]
QuestionStatus = Literal["ACTIVE", "DEFERRED", "ANSWERED", "EXHAUSTED", "CAPABILITY_GAP"]
LAB_VERSION: Literal["ontocodex-lab-v1"] = "ontocodex-lab-v1"
RUN_SECONDS = 600.0
FINALIZATION_SECONDS = 20.0
MAX_PROJECTION_BYTES = 64 * 1024


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ResearchQuestion(FrozenModel):
    question_id: Identifier
    question: Text
    rationale: Text
    project_id: Literal["TCGA-LUAD", "TCGA-LUSC"]
    priority: int = Field(ge=0, le=100)
    status: QuestionStatus
    uncertainty: tuple[Text, ...] = Field(max_length=12)
    next_action: Text


class Interpretation(FrozenModel):
    """An evidence-linked director judgment, never a replacement for StatisticalState."""

    source_kind: Literal["ONTOCODEX_JUDGMENT"] = "ONTOCODEX_JUDGMENT"
    question_id: Identifier
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    conclusion: Text
    uncertainty: tuple[Text, ...] = Field(min_length=1, max_length=12)


class ResearchDecision(FrozenModel):
    """Closed execution protocol: no SQL, paths, queries, measurements or code."""

    action: Literal["CREATE_QUESTION", "PRIORITIZE", "DEFER", "ANSWER", "EXHAUST",
                    "CAPABILITY_GAP", "ACQUIRE", "INTERPRET", "STOP"]
    rationale: Text
    question_id: Identifier | None
    question: ResearchQuestion | None
    priority: int | None = Field(ge=0, le=100)
    offer_id: Identifier | None
    interpretation: Interpretation | None
    next_action: Text

    @model_validator(mode="after")
    def action_shape(self) -> Self:
        fields = {name for name in ("question_id", "question", "priority", "offer_id",
                                     "interpretation") if getattr(self, name) is not None}
        expected = {
            "CREATE_QUESTION": {"question"}, "PRIORITIZE": {"question_id", "priority"},
            "DEFER": {"question_id"}, "ANSWER": {"question_id", "interpretation"},
            "EXHAUST": {"question_id"}, "CAPABILITY_GAP": {"question_id"},
            "ACQUIRE": {"question_id", "offer_id"},
            "INTERPRET": {"question_id", "interpretation"}, "STOP": set(),
        }[self.action]
        if fields != expected:
            raise ValueError(f"{self.action} requires exactly {sorted(expected)}")
        if self.interpretation and self.interpretation.question_id != self.question_id:
            raise ValueError("interpretation belongs to a different question")
        return self


class DirectorIdentity(FrozenModel):
    version: str = LAB_VERSION
    harness_version: Text
    provider: Identifier
    model: Text
    base_url: Text
    configuration_hash: Identifier


class AcquisitionOffer(FrozenModel):
    """Python-prepared choice. Budgets are upper bounds, estimates are not observations."""

    offer_id: Identifier
    question_id: Identifier
    project_id: Literal["TCGA-LUAD", "TCGA-LUSC"]
    method: Identifier
    modality: Identifier
    cases: tuple[Identifier, ...] = Field(max_length=100)
    expected_bytes: int = Field(ge=0)
    maximum_bytes: int = Field(gt=0)
    estimated_seconds: float = Field(gt=0)
    estimate_basis: Text = "INITIAL_CONSERVATIVE_ESTIMATE"
    evidence_provided: Text
    limitations: tuple[Text, ...] = Field(min_length=1)


class LabState(FrozenModel):
    version: Literal["ontocodex-lab-v1"] = LAB_VERSION
    domain: Literal["lung cancer; open-access GDC/GDAN evidence"] = "lung cancer; open-access GDC/GDAN evidence"
    revision: int = Field(ge=0, default=0)
    previous_artifact_id: Identifier | None = None
    questions: tuple[ResearchQuestion, ...] = Field(default=(), max_length=40)
    interpretations: tuple[Interpretation, ...] = Field(default=(), max_length=100)
    evidence_ids: tuple[Identifier, ...] = ()
    consecutive_no_progress: int = Field(default=0, ge=0)
    last_run_id: Identifier | None = None
    operational_state: Literal["READY", "PROVIDER_UNAVAILABLE", "CONTINUE_NEXT_RUN",
                               "NO_PROGRESS", "STOPPED", "CAPABILITY_GAP", "OPERATION_FAILED"] = "READY"

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        ids = [q.question_id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate research question identity")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate evidence identity")
        return self


class CnvCoverageSummary(FrozenModel):
    """Query coverage across retained shards, never a callable CNV denominator."""

    source_kind: Literal["DETERMINISTICALLY_DERIVED"] = "DETERMINISTICALLY_DERIVED"
    project_id: Identifier
    release: Text
    spec_hash: Identifier
    cohort_hash: Identifier
    evidence_ids: tuple[Identifier, ...]
    queried_cases: int = Field(ge=0)
    cohort_cases: int = Field(gt=0)
    positive_records: int = Field(ge=0)
    coverage: Literal["PARTIAL", "COMPLETE_POSITIVE_QUERY"]
    limitation: str = "Query coverage is not CNV callability. Absence is not neutral; partial cohorts cannot establish cohort recurrence."

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        if self.queried_cases > self.cohort_cases:
            raise ValueError("queried cases exceed cohort")
        if (self.coverage == "COMPLETE_POSITIVE_QUERY") != (self.queried_cases == self.cohort_cases):
            raise ValueError("coverage does not match queried case count")
        return self
