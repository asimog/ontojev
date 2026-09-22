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


def judgment_vector(label: str, probability: float, score: int) -> dict[str, Any]:
    return {
        "fixture_notice": FIXTURE_NOTICE,
        "noul": {"probability": probability, "semantic_label": "pattern merits attention"},
        "choice": {"chosen": label, "distribution": {"PROMOTE": probability, "DEFER": round(1 - probability, 3)}, "confidence": 0.79},
        "score": {"selected": score, "expected": float(score), "distribution": {str(score - 1): 0.15, str(score): 0.7, str(score + 1): 0.15}, "confidence": 0.76, "rubric": "1=weak fixture lead, 5=strong fixture lead"},
    }


def evidence(run_id: str, candidate_id: str, state: dict[str, Any], make_id, *, followup: bool = False, previous: str | None = None) -> dict[str, Any]:
    iteration = 1 if followup else 0
    n = 20 if followup else 24
    effect = 0.61 if followup else 0.88
    return {
        "schema_version": 1, "evidence_state_id": make_id(f"evidence:{candidate_id}:{iteration}"),
        "run_id": run_id, "candidate_id": candidate_id, "fixture_notice": FIXTURE_NOTICE,
        "previous_evidence_state_id": previous, "iteration_number": iteration,
        "entity": state["entity"], "source_statistical_state": {"state_id": state["state_id"]},
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

