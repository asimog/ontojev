from __future__ import annotations

from typing import Any

from cancerjev.domain.hypotheses import HYPOTHESIS_LABEL

FIXTURE_NOTICE = "SYNTHETIC FAKE FIXTURE — NO REAL GDC DATA"

PATTERNS = (
    ("FJEV1", "obvious strong synthetic pattern", 0.88, "coherent"),
    ("FJEV2", "weak distributed synthetic pattern", 0.46, "weak"),
    ("FJEV3", "project-specific synthetic exception", 0.63, "exception"),
    ("FJEV4", "fragile synthetic candidate", 0.74, "fragile"),
    ("FJEV5", "no coherent synthetic pattern", 0.18, "none"),
    ("FJEV6", "moderate distributed synthetic pattern", 0.57, "distributed"),
    ("FJEV7", "missing-heavy synthetic pattern", 0.31, "missing"),
    ("FJEV8", "opposing-project synthetic pattern", 0.52, "opposed"),
    ("FJEV9", "flat synthetic pattern", 0.12, "none"),
    ("FJEV10", "localized synthetic pattern", 0.41, "localized"),
    ("FJEV11", "replicated synthetic pattern", 0.69, "replicated"),
    ("FJEV12", "insufficient synthetic pattern", 0.22, "insufficient"),
)

# Valid option rosters per fixture question, mirroring the Choice contract.
CHOICE_ROSTERS = {
    "wide_pattern_route": ("PROMOTE", "DEFER"),
    "deep_route": ("FOLLOW_UP", "CLOSE"),
    "followup_outcome": ("WEAKENED", "UNCHANGED", "STRENGTHENED"),
    "hypothesis_testability": ("TESTABLE", "NOT_TESTABLE"),
}

# Jev Score contract: 0..4 follow-up-value rubric, numbered from zero.
SCORE_LEVELS = ("0", "1", "2", "3", "4")
SCORE_LEGEND = {
    "0": "no useful eligible test",
    "1": "weak reason",
    "2": "plausible reason",
    "3": "strong reason",
    "4": "unusually compelling reason",
}


def _normalized_distribution(options: tuple[str, ...], weights: list[float]) -> dict[str, float]:
    total = sum(weights)
    if total <= 0:
        raise ValueError("distribution weights must be positive")
    scaled = [weight / total for weight in weights]
    distribution = {option: round(share, 3) for option, share in zip(options[:-1], scaled[:-1], strict=True)}
    distribution[options[-1]] = round(max(0.0, 1 - sum(distribution.values())), 3)
    return distribution


def choice_answer(question_id: str, chosen: str, probability: float, confidence: float) -> dict[str, Any]:
    roster = CHOICE_ROSTERS[question_id]
    if chosen not in roster:
        raise ValueError(f"{chosen} is not in the {question_id} roster")
    if not 0 <= probability <= 1 or not 0 <= confidence <= 1:
        raise ValueError("choice probabilities must be within [0,1]")
    weights = [probability if option == chosen else (1 - probability) / (len(roster) - 1) for option in roster]
    return {"question_id": question_id, "chosen": chosen, "distribution": _normalized_distribution(roster, weights), "confidence": confidence}


def score_answer(selected: int, confidence: float) -> dict[str, Any]:
    if selected not in range(len(SCORE_LEVELS)):
        raise ValueError("score level outside the 0..4 rubric")
    if not 0 <= confidence <= 1:
        raise ValueError("score confidence must be within [0,1]")
    weights = [0.05] * len(SCORE_LEVELS)
    weights[selected] = 0.8
    distribution = _normalized_distribution(SCORE_LEVELS, weights)
    expected = round(sum(int(level) * share for level, share in distribution.items()), 3)
    return {"selected": selected, "expected": expected, "distribution": distribution, "confidence": confidence, "legend": dict(SCORE_LEGEND)}


def statistical_states(run_id: str, make_id) -> list[dict[str, Any]]:
    result = []
    for index, (symbol, description, effect, shape) in enumerate(PATTERNS):
        result.append({
            "schema_version": 1, "state_id": make_id(f"state:{index}"), "run_id": run_id,
            "fixture_notice": FIXTURE_NOTICE,
            "entity": {"gene_id": f"SYNTHETIC-{index + 1:03d}", "gene_symbol": symbol, "genome_build": "SYNTHETIC"},
            "scope": {"projects": ["SYNTHETIC-DEMO-A", "SYNTHETIC-DEMO-B"], "modalities": ["fixture-expression"]},
            "pattern": {"description": description, "shape": shape, "effect_like_descriptive_value": effect, "unit": "synthetic-unit"},
            "quality": {"availability": "OBSERVED", "missingness": round(index * 0.01, 2), "warnings": ["Fixture values are not scientific observations."]},
            "tested_context": {"exploratory": True, "coverage": "COMPLETE_FOR_FIXTURE"},
            "provenance": {"sources": [], "methods": ["SYNTHETIC_FIXTURE_GENERATOR_V1"]},
        })
    return result


def judgment_vector(question_id: str, chosen: str, probability: float, score_level: int) -> dict[str, Any]:
    return {
        "fixture_notice": FIXTURE_NOTICE,
        "noul": {"probability": probability, "semantic_label": "pattern merits attention"},
        "choice": choice_answer(question_id, chosen, probability, 0.79),
        "score": score_answer(score_level, 0.76),
    }


def evidence(run_id: str, candidate_id: str, state: dict[str, Any], make_id, *, followup: bool = False, previous: str | None = None) -> dict[str, Any]:
    iteration = 1 if followup else 0
    n = 20 if followup else 24
    effect = 0.61 if followup else 0.88
    return {
        "schema_version": 1, "evidence_state_id": make_id(f"evidence:{candidate_id}:{iteration}"),
        "run_id": run_id, "candidate_id": candidate_id, "fixture_notice": FIXTURE_NOTICE,
        "previous_evidence_state_id": previous, "iteration_number": iteration,
        "entity": state["entity"], "source_statistical_state": {"state_identity_hash": state["state_hash"]},
        "research_puzzle": {"origin": "DETERMINISTIC_TEMPLATE", "unresolved_questions": ["Is the synthetic pattern robust to influential fixture observations?"]},
        "deterministic_observations": [{
            "result_id": make_id(f"result:{candidate_id}:{iteration}"), "method_id": "FIXTURE_DESCRIPTIVE_V1",
            "method_version": "1", "n_effective": n, "availability": "OBSERVED",
            "effect": {"name": "synthetic contrast", "value": effect, "unit": "synthetic-unit"},
            "p_value": None, "q_value": None, "inference_status": "NOT_APPLICABLE_FIXTURE",
            "missingness": {"count": 4 if followup else 2, "reason": "deliberate fixture variation"},
            "limitations": ["Synthetic fixture only; no real population, assay, or inferential claim."],
        }],
        "project_level_evidence": [
            {"project_id": "SYNTHETIC-DEMO-A", "n": n // 2, "effect_like_value": effect, "availability": "OBSERVED"},
            {"project_id": "SYNTHETIC-DEMO-B", "n": n // 2, "effect_like_value": round(effect - 0.17, 2), "availability": "OBSERVED"},
        ],
        "cross_project_patterns": {"limitations": ["Two fabricated projects cannot establish generality."]},
        "missing_evidence": [{"needed_evidence": "real molecular observations", "availability": "NOT_ACQUIRED", "reason": "Phase 1 forbids providers"}],
        "quality_and_fragility": {"sample_sizes": [n // 2, n // 2], "sensitivity_results": ([{"action": "DROP_INFLUENTIAL_FIXTURE_POINTS", "before": 0.88, "after": 0.61}] if followup else []), "warnings": ["SYNTHETIC"]},
        "provenance": {"sources": [], "environment": "fixture"},
    }


def hypotheses(candidate_id: str, evidence_id: str, make_id) -> list[dict[str, Any]]:
    return [
        {"hypothesis_id": make_id(f"hypothesis:{candidate_id}:a"), "label": HYPOTHESIS_LABEL, "candidate_id": candidate_id, "evidence_state_id": evidence_id, "statement": "The synthetic pattern is broadly distributed across fixture observations.", "proposed_mechanism": "Fixture generator branch A", "predictions": ["Removing a few points preserves most of the pattern."], "contradicted_if": ["The fixture contrast collapses after sensitivity analysis."], "distinguishing_tests": ["DROP_INFLUENTIAL_FIXTURE_POINTS_V1"], "required_evidence": ["fixture sensitivity result"], "unsupported_assumptions": ["No biological mechanism is asserted."], "proposed_action_ids": ["DROP_INFLUENTIAL_FIXTURE_POINTS_V1"], "factual_observation_refs": []},
        {"hypothesis_id": make_id(f"hypothesis:{candidate_id}:b"), "label": HYPOTHESIS_LABEL, "candidate_id": candidate_id, "evidence_state_id": evidence_id, "statement": "The synthetic pattern is dominated by a small number of fixture observations.", "proposed_mechanism": "Fixture generator branch B", "predictions": ["Removing influential points materially weakens the pattern."], "contradicted_if": ["The fixture contrast is stable."], "distinguishing_tests": ["DROP_INFLUENTIAL_FIXTURE_POINTS_V1"], "required_evidence": ["fixture sensitivity result"], "unsupported_assumptions": ["No biological mechanism is asserted."], "proposed_action_ids": ["DROP_INFLUENTIAL_FIXTURE_POINTS_V1"], "factual_observation_refs": []},
    ]

