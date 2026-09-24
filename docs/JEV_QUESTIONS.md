# Versioned Jev questions

Current definitions live in cancerjev/jev/questions.py at baseline
`42b05d40e6edafec0b8613e7dd154a60a46e4fee`. No question text, criteria, applicability or policy
threshold changed in this documentation pass. [Jev design](JEV_DESIGN.md) owns the capability review.

## IMPLEMENTED sets

| Set / projection | Questions | Applicability |
|---|---|---|
| wide-v3 / jev-state-projection-v2 | evidence_quality_adequate; mutation_evidence_coherent; expression_evidence_coherent; signal_explained_by_coverage; unresolved_uncertainty_material; warrants_deeper_investigation (Noul); dominant_limitation (Choice) | mutation/expression-specific questions require that lane observed; others any_observation |
| deep-v1 / jev-evidence-projection-v1 | revision_reliable; evidence_sufficient_for_next_step; next_step_warranted; stopping_more_honest (Noul); dominant_limitation (Choice) | integrity_observed for reliability; revision_evidence_present otherwise |
| hypothesis-v2 / jev-hypothesis-projection-v1 | hypothesis_testable; hypothesis_exceeds_recorded_evidence (Noul); hypothesis_dominant_unsupported_assumption (Choice) | hypothesis_present |

Wide Choice roster: COVERAGE, MISSINGNESS, MUTATION_ABSENCE, EXPRESSION_SPARSITY,
PARTIAL_AGGREGATION, NONE, OTHER. Deep: EVIDENCE_GAPS, SCOPE_LIMITS, INTEGRITY_CONCERNS,
NO_FURTHER_ACTION, NONE, OTHER. Hypothesis: MECHANISM, CAUSALITY, CLINICAL, POPULATION, NONE, OTHER.
Each Noul judges support for its supplied proposition; absent prerequisites are inapplicable, not
biologically negative. Code owns applicability. Raw answers and excluded dimensions remain auditable.

wide-policy-v2 first requires complete acquisition, observed mutation and expression OBSERVED/PARTIAL.
Then warrants>=0.60, uncertainty>=0.50, quality>=0.40 and applicable coverage confound<=0.50.
It admits at most 3; zero is ABSTAIN. baseline-wide-v2 remains comparison-only. Deep thresholds:
reliable>=0.5, sufficient>=0.5, warranted>=0.6, stopping>=0.5, with branch order in nextmove.py.
Four moves: COMPLETE/FOLLOW_UP/GENERATE_HYPOTHESES/ABSTAIN. All thresholds remain provisional,
not calibrated. Jev never authorizes or executes the selected move.

wide-v2 is historical, documented in [Phase 3 history](PHASE_3_PLAN.md) and retained evaluations.
Earlier draft prose that called a six-question hypothetical battery “hypothesis-v2” was not the
implemented contract. Only the three current definitions above have that name. Earlier deep-v2
drafts are unimplemented and do not supersede deep-v1.

## PLANNED: separately versioned experimental specifications

No new judgment changes scientific eligibility or measured status. All rows inspect supplied state,
cannot see sibling answers, and run only after deterministic prerequisite checks. Proposed versions
below are design identifiers, not registered runtime sets. Calibration is mandatory before policy use.

| Version / question | State and why code cannot answer exactly | Primitive and criteria | Independence/no-match/policy/calibration |
|---|---|---|---|
| discovery-semantic-v1 / uncertainty_material | Typed observed descriptors, explicitly named uncertainty and bounded research intent; contextual relevance is semantic | Noul: true uncertainty could change interpretation of the bounded observation; false merely restates an already settled fact | Independent; missing named uncertainty makes inapplicable; experimental ranking dimension; blind materiality labels |
| discovery-semantic-v1 / interpretation_overclaims | Proposed narrative plus measured facts/limitations; implication can exceed literal arithmetic | Noul: true narrative asserts unsupported mechanism, causality, population or clinical conclusion; false stays descriptive or explicitly hypothetical | Independent; no narrative -> not applicable; review/veto signal, never evidence; reviewed overclaim labels |
| discovery-semantic-v1 / investigation_relevance | One survivor profile plus intent; semantic fit is not a count or effect | Score with 4 ordered levels: unrelated; relevant but no identifiable unresolved question; concrete unresolved question with bounded test; concrete consequential uncertainty with discriminating eligible test | Lowest level supplies no useful match; expected level is not success probability; reranking ablation only; blinded ordinal usefulness ratings |
| deep-action-value-v1 / reduces_uncertainty.<action_id> | Current evidence, named uncertainty, one already eligible action's exact contract; relevance of its possible outcomes is contextual | Noul: true at least one allowed outcome discriminates named interpretations; false repeats known information or cannot bear on them | Ask eligible actions together on shared state; none eligible -> no action questions and deterministic stop; code handles authorization/cost; human action-value labels |
| hypothesis-review-v3-design / source_support | One hypothesis claim and exact retained source context; semantic entailment is not literal matching | Choice: SUPPORTED, CONTRADICTED, UNSUPPORTED, UNRESOLVED; code checks numeric/source existence first | No source -> ineligible, not model guess; review-only and no promotion; blinded entailment labels and false-support rate |
| hypothesis-review-v3-design / clinical_overclaim | Generated text plus research-only boundary; implied clinical promise needs semantic interpretation | Noul: true implies diagnosis/prognosis/treatment benefit unsupported here; false does not | Independent; threshold calibrated for false negatives; flags human review; cannot certify safety |

The Score rubric is about research relevance, not cancer importance. Noul values mean probability of
the stated proposition, not its magnitude. Choice confidence is concentration among supplied options,
not proof the source is true. A low value or no match never becomes a biological negative.

No proposed cross-modal “coherence” or “conflict” question is admitted until code supplies a precisely
defined, matched scientific proposition. Presence of mutation plus an expression median is insufficient.
No model questions for exact missingness, hash integrity, available action existence, sample identity,
callable denominators, p-values or effect sizes. A real new evidence revision justifies a new request;
policy-weight changes over unchanged answers do not.
