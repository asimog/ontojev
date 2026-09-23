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
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.research.deep import stable_id

MAX_HYPOTHESES = 3
TEMPLATE_GENERATOR = "deterministic-template-v1"
LLM_GENERATOR = "injected-generator-v1"
LIVE_HYPOTHESIS_LABEL = "GENERATED HYPOTHESIS — NOT EVIDENCE"
LLM_HYPOTHESIS_LABEL = "LLM-GENERATED HYPOTHESIS — NOT EVIDENCE"

REQUIRED_DRAFT_KEYS = (
    "statement", "proposed_mechanism", "predictions", "contradicted_if",
    "distinguishing_tests", "required_evidence", "unsupported_assumptions",
)


class HypothesisUnavailable(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class GeneratedHypotheses:
    generator: str
    label: str
    drafts: tuple[dict[str, Any], ...]
    provider_attempted: bool
    usage: dict[str, int | None]
    error_code: str | None
    error_detail: str | None


def _recorded_facts(revision: dict[str, Any]) -> dict[str, Any]:
    """Numbers quoted in generated text, read only from the recorded revision."""
    project = (revision.get("project_level_evidence") or [{}])[0]
    mutation = project.get("affected_case_count") or {}
    examined = project.get("examined_cases") or {}
    expression = project.get("cases_with_expression") or {}
    missing = project.get("missing_measurements") or {}
    contradictions = [
        observation.get("check_id") for observation in revision.get("deterministic_observations", [])
        if observation.get("outcome") == "CONTRADICTED"
    ]
    not_observed = [
        observation.get("check_id") for observation in revision.get("deterministic_observations", [])
        if observation.get("outcome") == "NOT_OBSERVED"
    ]
    return {
        "symbol": (revision.get("entity") or {}).get("gene_symbol"),
        "project_id": project.get("project_id"),
        "affected": mutation.get("value"), "affected_availability": mutation.get("availability"),
        "examined": examined.get("value"), "examined_availability": examined.get("availability"),
        "expression_cases": expression.get("value"),
        "expression_missing": missing.get("value"),
        "iteration": revision.get("iteration_number"),
        "contradicted_checks": contradictions,
        "not_observed_checks": not_observed,
    }


def _draft(generator: str, label: str, *, statement: str, mechanism: str, predictions: list[str],
           contradicted_if: list[str], distinguishing_tests: list[str], required_evidence: list[str],
           assumptions: list[str]) -> dict[str, Any]:
    return {
        "label": label, "generator": generator, "statement": statement,
        "proposed_mechanism": mechanism, "predictions": predictions,
        "contradicted_if": contradicted_if, "distinguishing_tests": distinguishing_tests,
        "required_evidence": required_evidence, "unsupported_assumptions": assumptions,
        "proposed_action_ids": list(distinguishing_tests), "factual_observation_refs": [],
    }


def generate_template_hypotheses(revision: dict[str, Any], *, candidate: dict[str, Any],
                                 eligible_action_ids: list[str]) -> tuple[dict[str, Any], ...]:
    """Two competing statements built only from numbers the revision already records."""
    facts = _recorded_facts(revision)
    symbol = facts["symbol"] or "the candidate gene"
    tests = sorted(eligible_action_ids)
    common_assumptions = [
        "The statement is a generated explanation, not a measured result.",
        "No biological mechanism is asserted as established.",
    ]
    return (
        _draft(
            TEMPLATE_GENERATOR, LIVE_HYPOTHESIS_LABEL,
            statement=(
                f"The recorded mutation signal for {symbol} is an artefact of the examined cohort frame "
                f"rather than a gene-level effect: {facts['affected']} of {facts['examined']} examined cases "
                f"in {facts['project_id']} carry the mutation bucket."
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
                f"{facts['expression_missing']} of {facts['examined']} examined cases have no returned "
                f"expression value ({facts['expression_cases']} observed)."
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


def generation_request(revision: dict[str, Any], *, eligible_action_ids: list[str]) -> dict[str, Any]:
    """The bounded, recorded-facts-only request handed to an injected generator.

    This repository never performs the model request itself: the caller supplies a
    generator, and this payload is the complete input it may see. It contains only
    numbers the revision already records and the eligible registered action ids.
    """
    facts = _recorded_facts(revision)
    return {
        "task": (
            "State at most two competing, falsifiable hypotheses about the supplied recorded evidence. "
            "Use only the supplied facts; invent no numbers. Each hypothesis must be refutable by a bounded "
            "computation over evidence that is already retained or allowlisted. Never assert mechanism, "
            "causality, clinical meaning or wider generalization as established."
        ),
        "recorded_facts": facts,
        "recorded_missing_evidence": [
            item.get("needed_evidence") for item in revision.get("missing_evidence", [])
        ],
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
                              generator: str = LLM_GENERATOR) -> tuple[tuple[dict[str, Any], ...], None]:
    """Validate injected generator output strictly; any deviation is a typed failure."""
    if not isinstance(entries, list) or not entries:
        raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED", "no hypotheses in the response")
    drafts: list[dict[str, Any]] = []
    for entry in entries[:MAX_HYPOTHESES]:
        if not isinstance(entry, dict) or not all(key in entry for key in REQUIRED_DRAFT_KEYS):
            raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED", "a hypothesis misses required fields")
        if not str(entry["statement"]).strip():
            raise HypothesisUnavailable("GENERATOR_RESPONSE_MALFORMED", "an empty statement")
        tests = [test for test in entry["distinguishing_tests"] if test in eligible_action_ids]
        drafts.append(_draft(
            generator, LLM_HYPOTHESIS_LABEL,
            statement=str(entry["statement"]),
            mechanism=str(entry["proposed_mechanism"]),
            predictions=[str(item) for item in entry["predictions"]],
            contradicted_if=[str(item) for item in entry["contradicted_if"]],
            distinguishing_tests=tests,
            required_evidence=[str(item) for item in entry["required_evidence"]],
            assumptions=[str(item) for item in entry["unsupported_assumptions"]],
        ))
    return tuple(drafts), None


def generate_with_injected_generator(revision: dict[str, Any], *, eligible_action_ids: list[str],
                                     generator: Callable[..., Any],
                                     ) -> tuple[tuple[dict[str, Any], ...], dict[str, int | None]]:
    """Use a caller-supplied generator and validate its output strictly.

    The generator receives only :func:`generation_request` and may return either the
    entry list or ``(entries, usage)``. Its output is untrusted text: schema,
    distinguishing tests and label are enforced here, and any deviation raises a
    typed :class:`HypothesisUnavailable` rather than producing a partly trusted
    hypothesis.
    """
    request = generation_request(revision, eligible_action_ids=eligible_action_ids)
    try:
        produced = generator(request)
    except HypothesisUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - every generator failure is a typed outcome
        raise HypothesisUnavailable("GENERATOR_ERROR", f"{type(exc).__name__}: {exc}") from exc
    usage = {"input_tokens": None, "output_tokens": None}
    entries = produced
    if isinstance(produced, tuple) and len(produced) == 2:
        entries, raw_usage = produced
        if isinstance(raw_usage, dict):
            usage = {"input_tokens": raw_usage.get("input_tokens"),
                     "output_tokens": raw_usage.get("output_tokens")}
    drafts, _ = validate_generated_drafts(entries, eligible_action_ids=eligible_action_ids)
    return drafts, usage


def generate_hypotheses(*, revision: dict[str, Any], candidate: dict[str, Any],
                        eligible_action_ids: list[str],
                        llm_generator: Callable[..., Any] | None = None) -> GeneratedHypotheses:
    """Deterministic template generation by default; an injected generator otherwise."""
    if llm_generator is not None:
        try:
            drafts, usage = generate_with_injected_generator(
                revision, eligible_action_ids=eligible_action_ids, generator=llm_generator)
            return GeneratedHypotheses(generator=LLM_GENERATOR, label=LLM_HYPOTHESIS_LABEL,
                                       drafts=drafts, provider_attempted=True, usage=usage,
                                       error_code=None, error_detail=None)
        except HypothesisUnavailable as exc:
            return GeneratedHypotheses(generator=LLM_GENERATOR, label=LLM_HYPOTHESIS_LABEL, drafts=(),
                                       provider_attempted=True,
                                       usage={"input_tokens": None, "output_tokens": None},
                                       error_code=exc.code, error_detail=exc.detail)
    drafts = generate_template_hypotheses(revision, candidate=candidate,
                                          eligible_action_ids=eligible_action_ids)
    return GeneratedHypotheses(generator=TEMPLATE_GENERATOR, label=LIVE_HYPOTHESIS_LABEL, drafts=drafts,
                               provider_attempted=False,
                               usage={"input_tokens": None, "output_tokens": None},
                               error_code=None, error_detail=None)


def run_hypothesis_stage(*, run_id: str, candidate: dict[str, Any], revision: dict[str, Any],
                         evidence_hash: str, eligible_action_ids: list[str], repository: Any,
                         jev_service: Any, emit: Callable[..., Any],
                         publish_json: Callable[[str, str, Any, str], Any],
                         llm_generator: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Generate bounded hypotheses, persist them, and have Jev judge each one."""
    existing = repository.page_child("hypotheses", run_id, 100, None,
                                     {"candidate_id": candidate["candidate_id"]})["items"]
    remaining = MAX_HYPOTHESES - len(existing)
    if remaining <= 0:
        return {"status": "NO_NEW_HYPOTHESES", "hypothesis_ids": [], "evaluations": []}
    generated = generate_hypotheses(revision=revision, candidate=candidate,
                                    eligible_action_ids=eligible_action_ids,
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
                  "evidence_state_id": revision.get("evidence_state_id")},
        )
        return {"status": "UNAVAILABLE", "error_code": generated.error_code, "hypothesis_ids": [],
                "evaluations": []}
    hypothesis_ids: list[str] = []
    registrations: list[tuple[str, tuple[Any, ...]]] = []
    refs: list[dict[str, Any]] = []
    drafts = generated.drafts[:remaining]
    for index, draft in enumerate(drafts):
        hypothesis_id = stable_id(run_id, f"hypothesis:{candidate['candidate_id']}:{index}")
        record = {
            **draft, "hypothesis_id": hypothesis_id,
            "candidate_id": candidate["candidate_id"],
            "evidence_state_id": revision.get("evidence_state_id"),
            "created_at": utc_now(),
        }
        artifact = publish_json(run_id, f"runs/{run_id}/hypotheses/{hypothesis_id}.json",
                                record, "hypothesis")
        hypothesis_ids.append(hypothesis_id)
        refs.append(artifact.ref())
        registrations.append(repository.artifact_registration(artifact, run_id))
        registrations.append(repository.hypothesis_registration(
            hypothesis_id=hypothesis_id, run_id=run_id, candidate_id=candidate["candidate_id"],
            evidence_state_id=revision.get("evidence_state_id"), artifact_id=artifact.artifact_id,
            hypothesis_json=canonical_json(record).decode(), created_at=utc_now(),
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
              "usage": generated.usage, "cache": False, "evidence_state_id": revision.get("evidence_state_id")},
        artifact_refs=refs, registrations=registrations,
    )
    evaluations: list[dict[str, Any]] = []
    for hypothesis_id in hypothesis_ids:
        stored = repository.get_hypothesis(hypothesis_id)
        if stored is None:
            continue
        evaluation = jev_service.evaluate_hypothesis(
            run_id=run_id, hypothesis=stored["hypothesis"], evidence=revision,
            eligible_actions=[{"action_id": action_id} for action_id in eligible_action_ids],
            evidence_hash=evidence_hash, emit=emit,
        )
        evaluations.append({
            "hypothesis_id": hypothesis_id, "evaluation_id": evaluation["evaluation_id"],
            "error_code": (evaluation["error"] or {}).get("code"),
            "answers": evaluation["answers"],
        })
    return {"status": "GENERATED", "generator": generated.generator,
            "hypothesis_ids": hypothesis_ids, "evaluations": evaluations}
