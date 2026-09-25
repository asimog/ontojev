"""Bounded hypothesis generation and its Jev evaluation (Phase 6).

Generated text is never evidence: every statement is stored with an explicit label
that names its generator, it never writes a measured field, and its Jev judgment is
an input to Python policy only. Generation is deterministic by default. An LLM is
used only through a generator injected by the caller — this repository performs no
model request, holds no provider credential and defines no provider contract — and
its absence is a typed, recorded outcome. Python owns the bound, the persistence and
every side effect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from cancerjev.domain.envelopes import EvidenceRecord, HypothesisRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.evidence import CheckOutcome, EvidenceState
from cancerjev.domain.hypotheses import (
    DRAFT_FIELDS,
    HypothesisDraft,
    read_hypothesis_draft,
)
from cancerjev.domain.measurements import ContractError, MetricRecord
from cancerjev.research.deep import stable_id
from cancerjev.science.actions import ACTION_REGISTRY

MAX_HYPOTHESES = 3
MAX_TEXT_CHARS = 2_000
MAX_LIST_ITEMS = 10
TEMPLATE_GENERATOR = "deterministic-template-v1"
INJECTED_GENERATOR = "injected-generator-v1"
LIVE_HYPOTHESIS_LABEL = "GENERATED HYPOTHESIS — NOT EVIDENCE"
LLM_HYPOTHESIS_LABEL = "LLM-GENERATED HYPOTHESIS — NOT EVIDENCE"


class HypothesisUnavailable(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class GeneratedHypotheses:
    generator: str
    label: str
    drafts: tuple[HypothesisDraft, ...]
    provider_attempted: bool
    usage: dict[str, int | None]
    error_code: str | None
    error_detail: str | None


def _metric_value(record: MetricRecord | None) -> Any:
    return record.value if record is not None else None


def _metric_availability(record: MetricRecord | None) -> str | None:
    return record.availability.value if record is not None else None


def _recorded_facts(evidence: EvidenceState) -> dict[str, Any]:
    """Numbers quoted in generated text, read only from the recorded revision."""
    project = evidence.project_evidence[0] if evidence.project_evidence else None
    return {
        "symbol": evidence.entity.symbol,
        "project_id": project.project_id if project is not None else None,
        "affected": _metric_value(project.affected_case_count) if project is not None else None,
        "affected_availability": _metric_availability(project.affected_case_count)
        if project is not None else None,
        "examined": _metric_value(project.examined_cases) if project is not None else None,
        "examined_availability": _metric_availability(project.examined_cases)
        if project is not None else None,
        "expression_cases": _metric_value(project.cases_with_expression) if project is not None else None,
        "expression_missing": _metric_value(project.missing_measurements) if project is not None else None,
        "iteration": evidence.revision_index,
        "contradicted_checks": [check.check_id for check in evidence.checks
                                if check.outcome == CheckOutcome.CONTRADICTED],
        "not_observed_checks": [check.check_id for check in evidence.checks
                                if check.outcome == CheckOutcome.NOT_OBSERVED],
    }


def _draft(generator: str, label: str, *, statement: str, mechanism: str, predictions: list[str],
           contradicted_if: list[str], distinguishing_tests: list[str], required_evidence: list[str],
           assumptions: list[str], generator_model: str | None = None) -> HypothesisDraft:
    return HypothesisDraft(
        label=label, generator=generator, generator_model=generator_model, statement=statement,
        proposed_mechanism=mechanism, predictions=tuple(predictions),
        contradicted_if=tuple(contradicted_if), distinguishing_tests=tuple(distinguishing_tests),
        required_evidence=tuple(required_evidence), unsupported_assumptions=tuple(assumptions),
    )


def generate_template_hypotheses(evidence: EvidenceState, *,
                                 eligible_action_ids: list[str]) -> tuple[HypothesisDraft, ...]:
    """Two competing statements built only from numbers the revision already records.

    A metric the revision does not observe is never quoted as a number: the statement
    says so explicitly instead, because a missing observation is not a zero.
    """
    facts = _recorded_facts(evidence)
    symbol = facts["symbol"] or "the candidate gene"
    tests = sorted(eligible_action_ids)
    affected, examined = facts["affected"], facts["examined"]
    counts_observed = (facts["affected_availability"] == "OBSERVED"
                       and facts["examined_availability"] == "OBSERVED"
                       and affected is not None and examined is not None)
    count_phrase = (
        f"{affected} of {examined} examined cases in {facts['project_id']} carry the mutation bucket"
        if counts_observed else
        "the affected-case count for this examined frame is not observed in this revision"
    )
    expression_cases, expression_missing = facts["expression_cases"], facts["expression_missing"]
    expression_observed = (expression_cases is not None and expression_missing is not None)
    expression_phrase = (
        f"{expression_missing} of {examined} examined cases have no returned expression value "
        f"({expression_cases} observed)"
        if expression_observed and counts_observed else
        "the recorded expression coverage for this examined frame is not observed in this revision"
    )
    common_assumptions = [
        "The statement is a generated explanation, not a measured result.",
        "No biological mechanism is asserted as established.",
    ]
    if not (counts_observed and expression_observed):
        common_assumptions.append(
            "At least one quoted metric is not observed in this revision; the statement is phrased "
            "without a number for it."
        )
    return (
        _draft(
            TEMPLATE_GENERATOR, LIVE_HYPOTHESIS_LABEL,
            statement=(
                f"The recorded mutation signal for {symbol} is an artefact of the examined cohort frame "
                f"rather than a gene-level effect: {count_phrase}."
            ),
            mechanism="Frame composition rather than gene-level biology produces the recorded count.",
            predictions=[
                "Restating the affected-case count over a different bounded examined frame changes it materially.",
                "The recorded expression coverage, not the mutation count, explains any apparent cross-modal gap.",
            ],
            contradicted_if=[
                "A bounded deterministic restatement of the examined frame leaves the affected-case count unchanged.",
            ],
            distinguishing_tests=tests,
            required_evidence=[
                "a per-case mutation membership response for the examined frame (not currently retained)",
            ],
            assumptions=common_assumptions,
        ),
        _draft(
            TEMPLATE_GENERATOR, LIVE_HYPOTHESIS_LABEL,
            statement=(
                f"The {symbol} mutation signal cannot be read as expression-supported evidence because "
                f"{expression_phrase}."
            ),
            mechanism="Unreturned expression columns leave the mutation-only reading unconstrained.",
            predictions=[
                "Any cross-modal reading changes when the unreturned examined cases are accounted for.",
                "The recorded expression summary rests only on the cases that returned values.",
            ],
            contradicted_if=[
                "A retained-evidence recomputation shows the unreturned cases cannot change the cross-modal reading.",
            ],
            distinguishing_tests=tests,
            required_evidence=[
                "expression values for the unreturned examined cases (not currently retained)",
            ],
            assumptions=common_assumptions,
        ),
    )


def generation_request(evidence: EvidenceState, *, eligible_action_ids: list[str]) -> dict[str, Any]:
    """The bounded, recorded-facts-only request handed to an injected generator.

    This repository never performs the model request itself: the caller supplies a
    generator, and this payload is the complete input it may see. It contains only
    numbers the revision already records and the eligible registered action ids.
    """
    return {
        "task": (
            "State at most two competing, falsifiable hypotheses about the supplied recorded evidence. "
            "Use only the supplied facts; invent no numbers. Each hypothesis must be refutable by a bounded "
            "computation over evidence that is already retained or allowlisted. Never assert mechanism, "
            "causality, clinical meaning or wider generalization as established."
        ),
        "recorded_facts": _recorded_facts(evidence),
        "recorded_missing_evidence": [item.needed_evidence for item in evidence.missing_evidence],
        "eligible_registered_actions": sorted(eligible_action_ids),
        "response_schema": {
            "hypotheses": [
                {
                    "statement": "string",
                    "proposed_mechanism": "string (explicitly hypothetical)",
                    "predictions": ["string"],
                    "contradicted_if": ["string"],
                    "distinguishing_tests": ["registered action id or empty"],
                    "required_evidence": ["string"],
                    "unsupported_assumptions": ["string"],
                }
            ]
        },
    }


def validate_generated_drafts(entries: Any, *, eligible_action_ids: list[str],
                              generator: str = INJECTED_GENERATOR,
                              generator_model: str | None = None,
                              label: str = LLM_HYPOTHESIS_LABEL,
                              ) -> tuple[tuple[HypothesisDraft, ...], None]:
    """Validate injected generator output strictly; any deviation is a typed failure.

    Untrusted text is bounded here so it can never reach an evidence record: every
    text field has a length cap, every list field must be a list of strings within a
    cap, and a distinguishing test must name an eligible registered action.
    """
    if not isinstance(entries, list) or not entries:
        raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED", "no hypotheses in the response")
    if len(entries) > MAX_HYPOTHESES:
        raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED",
                                    f"{len(entries)} hypotheses exceed the bound {MAX_HYPOTHESES}")
    drafts: list[HypothesisDraft] = []
    for entry in entries:
        try:
            drafts.append(read_hypothesis_draft(
                entry, allowed_action_ids=frozenset(eligible_action_ids) & frozenset(ACTION_REGISTRY),
                label=label, generator=generator, generator_model=generator_model,
            ))
        except ContractError as exc:
            raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED", str(exc)) from exc
    return tuple(drafts), None


def generate_with_injected_generator(evidence: EvidenceState, *, eligible_action_ids: list[str],
                                     generator: Callable[..., Any],
                                     ) -> tuple[tuple[HypothesisDraft, ...], dict[str, int | None]]:
    """Use a caller-supplied generator and validate its output strictly.

    The generator receives only :func:`generation_request` and may return either the
    entry list or ``(entries, usage)``. Its output is untrusted text: schema, bounds,
    distinguishing tests, label and provider identity are enforced here, and any
    deviation raises a typed :class:`HypothesisUnavailable` rather than producing a
    partly trusted hypothesis.
    """
    request = generation_request(evidence, eligible_action_ids=eligible_action_ids)
    try:
        produced = generator(request)
    except HypothesisUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - every generator failure is a typed outcome
        code = getattr(exc, "code", None) or "GENERATOR_ERROR"
        raise HypothesisUnavailable(str(code), f"{type(exc).__name__}: {exc}") from exc
    usage: dict[str, int | None] = {"input_tokens": None, "output_tokens": None}
    entries = produced
    if isinstance(produced, tuple) and len(produced) == 2:
        entries, raw_usage = produced
        if isinstance(raw_usage, dict):
            usage = {"input_tokens": raw_usage.get("input_tokens"),
                     "output_tokens": raw_usage.get("output_tokens")}
    generator_name = str(getattr(generator, "name", INJECTED_GENERATOR))
    generator_model = getattr(generator, "model", None)
    drafts, _ = validate_generated_drafts(
        entries, eligible_action_ids=eligible_action_ids, generator=generator_name,
        generator_model=str(generator_model) if generator_model else None,
    )
    return drafts, usage


def generate_hypotheses(*, evidence: EvidenceState, eligible_action_ids: list[str],
                        llm_generator: Callable[..., Any] | None = None) -> GeneratedHypotheses:
    """Deterministic template generation by default; an injected generator otherwise."""
    if llm_generator is not None:
        generator_name = str(getattr(llm_generator, "name", INJECTED_GENERATOR))
        try:
            drafts, usage = generate_with_injected_generator(
                evidence, eligible_action_ids=eligible_action_ids, generator=llm_generator)
            return GeneratedHypotheses(generator=generator_name, label=LLM_HYPOTHESIS_LABEL,
                                       drafts=drafts, provider_attempted=True, usage=usage,
                                       error_code=None, error_detail=None)
        except HypothesisUnavailable as exc:
            return GeneratedHypotheses(generator=generator_name, label=LLM_HYPOTHESIS_LABEL, drafts=(),
                                       provider_attempted=True,
                                       usage={"input_tokens": None, "output_tokens": None},
                                       error_code=exc.code, error_detail=exc.detail)
    drafts = generate_template_hypotheses(evidence, eligible_action_ids=eligible_action_ids)
    return GeneratedHypotheses(generator=TEMPLATE_GENERATOR, label=LIVE_HYPOTHESIS_LABEL, drafts=drafts,
                               provider_attempted=False,
                               usage={"input_tokens": None, "output_tokens": None},
                               error_code=None, error_detail=None)


def candidate_hypothesis_ids(hypotheses: list[dict[str, Any]]) -> tuple[str, ...]:
    """Recorded hypothesis ids, used to keep each dossier's reviews to its own statements."""
    return tuple(
        str(item["hypothesis_id"]) for item in hypotheses if item.get("hypothesis_id")
    )


def hypothesis_record_payload(record: HypothesisRecord, *, evidence_state_id: str) -> dict[str, Any]:
    """Persistence-boundary payload for one generated hypothesis."""
    draft = record.draft
    return {
        **asdict(draft),
        "proposed_action_ids": list(draft.distinguishing_tests),
        "factual_observation_refs": [],
        "hypothesis_id": record.hypothesis_id,
        "candidate_id": record.candidate_id,
        "evidence_state_id": evidence_state_id,
        "created_at": utc_now(),
    }


def _eligible_action_payloads(eligible_action_ids: list[str]) -> list[dict[str, Any]]:
    return [ACTION_REGISTRY[action_id].payload() for action_id in sorted(eligible_action_ids)
            if action_id in ACTION_REGISTRY]


def run_hypothesis_stage(*, run_id: str, candidate: dict[str, Any], revision: EvidenceRecord,
                         eligible_action_ids: list[str], repository: Any,
                         jev_service: Any, emit: Callable[..., Any],
                         publish_json: Callable[[str, str, Any, str], Any],
                         llm_generator: Callable[..., Any] | None = None,
                         requested_reason: str | None = None) -> dict[str, Any]:
    """Generate bounded hypotheses, persist them, and have Jev judge each one.

    ``requested_reason`` records an explicit operator request when the stage runs without the
    policy having asked for hypotheses; the recorded next move is never rewritten.
    """
    evidence = revision.revision
    evidence_state_id = revision.evidence_state_id
    existing = repository.page_child("hypotheses", run_id, 100, None,
                                     {"candidate_id": candidate["candidate_id"]})["items"]
    remaining = MAX_HYPOTHESES - len(existing)
    if remaining <= 0:
        emit(
            run_id, "HYPOTHESES_GENERATED", f"hypotheses:{candidate['candidate_id']}:bound",
            f"Hypothesis generation skipped: the candidate already holds {len(existing)} record(s).",
            stage="HYPOTHESIS_GENERATION", level="warning", candidate_id=candidate["candidate_id"],
            data={"outcome": "NO_NEW_HYPOTHESES", "candidate_id": candidate["candidate_id"], "count": 0,
                  "generator": None, "provider_attempted": False, "cache": False,
                  "usage": {"input_tokens": None, "output_tokens": None},
                  "detail": f"the per-candidate bound is {MAX_HYPOTHESES}",
                  "evidence_state_id": evidence_state_id},
        )
        return {"status": "NO_NEW_HYPOTHESES", "hypothesis_ids": [], "evaluations": []}
    generated = generate_hypotheses(evidence=evidence, eligible_action_ids=eligible_action_ids,
                                    llm_generator=llm_generator)
    if not generated.drafts:
        emit(
            run_id, "HYPOTHESES_GENERATED", f"hypotheses:{candidate['candidate_id']}:unavailable",
            f"Hypothesis generation was unavailable: {generated.error_code}.",
            stage="HYPOTHESIS_GENERATION", level="warning", candidate_id=candidate["candidate_id"],
            data={"outcome": "UNAVAILABLE", "candidate_id": candidate["candidate_id"],
                  "generator": generated.generator, "count": 0,
                  "provider_attempted": generated.provider_attempted, "usage": generated.usage,
                  "error_code": generated.error_code, "detail": generated.error_detail,
                  "evidence_state_id": evidence_state_id},
        )
        return {"status": "UNAVAILABLE", "error_code": generated.error_code, "hypothesis_ids": [],
                "evaluations": [], "generator": generated.generator, "label": generated.label}
    hypothesis_ids: list[str] = []
    records: list[HypothesisRecord] = []
    registrations: list[tuple[str, tuple[Any, ...]]] = []
    refs: list[dict[str, Any]] = []
    drafts = generated.drafts[:remaining]
    for index, draft in enumerate(drafts):
        hypothesis_id = stable_id(run_id, f"hypothesis:{candidate['candidate_id']}:{index}")
        record = HypothesisRecord(hypothesis_id, candidate["candidate_id"], draft)
        payload = hypothesis_record_payload(record, evidence_state_id=evidence_state_id)
        artifact = publish_json(run_id, f"runs/{run_id}/hypotheses/{hypothesis_id}.json",
                                payload, "hypothesis")
        hypothesis_ids.append(hypothesis_id)
        records.append(record)
        refs.append(artifact.ref())
        registrations.append(repository.artifact_registration(artifact, run_id))
        registrations.append(repository.hypothesis_registration(
            hypothesis_id=hypothesis_id, run_id=run_id, candidate_id=candidate["candidate_id"],
            evidence_state_id=evidence_state_id, artifact_id=artifact.artifact_id,
            hypothesis_json=canonical_json(payload).decode(), created_at=utc_now(),
        ))
    registrations.append(repository.candidate_status_registration(
        candidate_id=candidate["candidate_id"], status="HYPOTHESIZED",
        current_stage="HYPOTHESIS_GENERATION", updated_at=utc_now(),
    ))
    emit(
        run_id, "HYPOTHESES_GENERATED", f"hypotheses:{candidate['candidate_id']}:generated",
        f"Generated {len(hypothesis_ids)} labelled hypothesis statement(s) without asserting evidence.",
        stage="HYPOTHESIS_GENERATION", candidate_id=candidate["candidate_id"],
        data={"outcome": "GENERATED", "candidate_id": candidate["candidate_id"], "count": len(hypothesis_ids),
              "hypothesis_ids": hypothesis_ids, "generator": generated.generator,
              "label": generated.label, "provider_attempted": generated.provider_attempted,
              "usage": generated.usage, "cache": False,
              "evidence_state_id": evidence_state_id,
              "requested_reason": requested_reason},
        artifact_refs=refs, registrations=registrations,
    )
    evaluations: list[dict[str, Any]] = []
    action_payloads = _eligible_action_payloads(eligible_action_ids)
    for record in records:
        evaluation = jev_service.evaluate_hypothesis_record(
            run_id=run_id, hypothesis=record, evidence=revision,
            eligible_actions=action_payloads, emit=emit,
        )
        vector = evaluation.boundary_representation()
        evaluations.append({
            "hypothesis_id": record.hypothesis_id, "evaluation_id": evaluation.evaluation_id,
            "error_code": (vector["error"] or {}).get("code"),
            "answers": vector["answers"],
        })
    return {"status": "GENERATED", "generator": generated.generator,
            "hypothesis_ids": hypothesis_ids, "evaluations": evaluations,
            "requested_reason": requested_reason}


__all__ = [
    "DRAFT_FIELDS",
    "GeneratedHypotheses",
    "HypothesisUnavailable",
    "candidate_hypothesis_ids",
    "generate_hypotheses",
    "generate_template_hypotheses",
    "generate_with_injected_generator",
    "generation_request",
    "run_hypothesis_stage",
    "validate_generated_drafts",
]
