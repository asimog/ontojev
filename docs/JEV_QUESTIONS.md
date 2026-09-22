# Versioned question architecture

Active Wide specification and historical question-set record. The current `wide-v3` implementation
is defined in `cancerjev/jev/questions.py`; the implementation and verification record is in
`docs/IMPLEMENTATION_STATUS.md` and the design rationale is in `docs/PHASE_3_PLAN.md`.

Question sets: `wide-v3` (**IMPLEMENTED**, current), `wide-v2` (retained as historical record), `deep-v2` and
`hypothesis-v2` (**PLANNED**, Phase 4+/Phase 6, not implemented). The earlier `wide-v2` set was designed
around cross-project evidence and became semantically stale when production scope narrowed to one
TCGA-LUAD cohort. `wide-v3` replaces those questions with single-cohort evidence judgments and a
deterministic admission policy. This implementation does not establish scientific improvement.

Each definition carries an ID, primitive, version, full instruction text, criteria, applicability rule and a hash over the canonical definition bytes. Question IDs are not sent to the model; changing wording changes the definition hash. Questions refer only to supplied observations and their stated limitations, and never ask Jev to invent facts, compute quantities, or establish causality.

Shared Noul criteria template: true means the explicitly stated proposition is supported by the supplied observations and their quality context; false means it is not supported. Missing data does not establish a biological negative; if the prerequisite evidence is absent, deterministic applicability marks the answer unusable for routing.

## `wide-v2`: historical question set (superseded)

These definitions document the retired cross-project semantics. They remain useful when reading
older immutable evaluations, but current runs use `wide-v3`.

| ID | Primitive | Instruction (verbatim definition) | Applicability (deterministic) |
|---|---|---|---|
| `warrants_deeper_investigation` | Noul | “You are reviewing a compact deterministic profile of one gene across several cancer projects. It contains per-project counts of cases with a somatic mutation in this gene (`project_observations[].affected_cases`), examined-case and mutation-data coverage, and per-project expression summaries in log2(UQFPKM+1), with missingness stated explicitly. Decide whether this profile warrants a bounded deterministic follow-up investigation. A follow-up is a small registered computation over held data or a small bounded public-data query, not a clinical action; biological novelty is not required.” | ≥1 project with an observed mutation count or expression summary |
| `mutation_project_exception` | Noul | “Compare the supplied per-project affected-case counts (`project_observations[].affected_cases`). Does at least one project depart materially from the dominant cross-project pattern of these counts, beyond what the stated coverage and case counts would explain? A project with no mutation observation is not an exception.” | ≥3 projects with mutation observations |
| `expression_project_exception` | Noul | “Compare the supplied per-project expression summaries (`project_observations[].expression_local`). Does at least one project depart materially from the dominant cross-project pattern of expression median or dispersion, beyond what the stated missing-expression counts would explain?” | ≥3 projects with local expression summaries |
| `coverage_explains_apparent_difference` | Noul | “The supplied profile states per-project examined-case counts, mutation-data coverage and expression coverage. Is the apparent cross-project difference plausibly explained by unequal coverage or missingness rather than by a biological difference?” | coverage imbalance flag set by code |
| `likely_fragile` | Noul | “Using the supplied dominance context (`cross_project.top_project_share`) and coverage/missingness, does the apparent cross-project pattern look fragile — dependent on one project or on incomplete coverage?” | ≥2 projects with observations |
| `pattern_type` | Choice | “Which supplied pattern description best fits the observed evidence?” | ≥1 usable observation |

`pattern_type` roster (closed set; no option that the state cannot express):

```text
WIDESPREAD_RECURRENCE: comparable projects show recurring mutation counts without a dominant exception.
PROJECT_SPECIFIC_EXCEPTION: one observed comparable project departs from the majority pattern.
WEAK_DISTRIBUTED_SIGNAL: individually moderate mutation counts recur across projects.
NO_COHERENT_PATTERN: usable observations show no coherent cross-project pattern.
DATA_QUALITY_CONCERN: coverage, missingness or mapping problems dominate interpretation.
INSUFFICIENT_EVIDENCE: available observations cannot distinguish the patterns.
```

Excluded from `wide-v2` and why:

| Excluded question | Reason |
|---|---|
| `multimodal_convergence` / `multimodal_discordance` | The state has no defined cross-modal proposition linking mutation counts to expression summaries; asking would invite invented relationships. |
| `direction_reversal` | No signed, comparable effect measure exists in the state (`cross_project.direction = NOT_EXAMINED`). |
| `followup_value` (Score) | No registered eligible follow-up exists in Phase 3; the rubric would be ungrounded. It returns when Phase 4 registers executable actions. |
| `cross_project_coherence` (wide-v1) | Superseded by the narrower exception/coverage/fragility questions that the real state can actually answer. |

Deterministic applicability, not the model, decides whether an answer is usable. A returned answer whose applicability is false is retained for audit but excluded from routing; it is never read as a biological negative.

## `deep-v2`: reduced deep battery (PLANNED, Phase 4 draft, not implemented)

Python computes the deterministically eligible registered actions first and supplies them to Jev.
All questions independently inspect the same immutable EvidenceState, so they are asked in **one
fan-out request** where the state is shared. Action value is asked per action as an atomic Noul
proposition, not as an abstract `next_test_value` Score.

| ID | Primitive | Proposition |
|---|---|---|
| `material_unresolved_uncertainty` | Noul | The supplied deterministic observations leave a material, named uncertainty about the research puzzle. |
| `action_reduces_uncertainty.<action_id>` | Noul (one per eligible action) | Running the listed eligible registered action would materially reduce the named uncertainty. |
| `hypotheses_would_help` | Noul | Bounded hypothesis generation would materially help resolve the named uncertainty. |
| `evidence_sufficient_to_stop` | Noul | The current evidence is sufficient to stop this investigation. |
| `coherent_evidence` | Noul | The supplied deterministic observations support one coherent description of the research puzzle. |
| `contradictory_evidence` | Noul | Supplied observations materially conflict with one another or with the stated puzzle. |

A `Score` is not used merely because actions must be ranked: Python combines each per-action Noul
probability with deterministic eligibility, action cost and remaining budget. A closed Choice is
appropriate only for genuinely mutually exclusive alternatives. `evidence_pattern` (Choice over a
pattern roster) is deferred until the Wide redesign defines a roster the single-cohort state can
actually express. A second Jev request is justified only when a genuinely new evidence revision
exists.

## `hypothesis-v2`: hypothesis review (PLANNED, Phase 6 draft, not implemented)

State contains one immutable EvidenceState, one generated hypothesis, and deterministically eligible action descriptions. No sibling hypotheses or sibling verdicts.

| ID | Primitive | Proposition / criteria |
|---|---|---|
| `supported` | Noul | Supplied observations materially support this hypothesis over the stated null interpretation. |
| `contradicted` | Noul | Supplied observations materially contradict a prediction of this hypothesis. |
| `exceeds_evidence` | Noul | The hypothesis asserts factual conclusions beyond the supplied observations. |
| `unavailable_dependency` | Noul | The hypothesis critically depends on evidence currently unavailable. |
| `assessment` | Choice | `SUPPORT` / `CONTRADICT` / `UNRESOLVED` (observations favor predictions / oppose predictions / neither disposition is justified or evidence conflicts). |
| `discriminability` | Score | 0 no distinction testable … 4 clear decisive distinction within the listed action scope. |

The deterministic registry — not `registered_test_exists` — establishes whether a test exists. Hypothesis review is critique, not scientific verification.

## `wide-v3`: single-cohort set (IMPLEMENTED)

Full specification: `docs/PHASE_3_PLAN.md`. The next Wide decision is: **which TCGA-LUAD
candidate states, if any, contain sufficiently coherent and decision-relevant evidence to justify
spending bounded future follow-up budget on deeper investigation?**

`wide-v3` uses six atomic Nouls plus one closed Choice over a single-cohort projection
(`jev-state-projection-v2`). It separates evidence quality, evidence pattern, and the value of
deeper investigation, and asks no deterministic fact.

| # | question_id | Primitive | Dimension | Applicability (deterministic) |
|---|---|---|---|---|
| 1 | `evidence_quality_adequate` | Noul | quality | mutation or expression observed |
| 2 | `mutation_evidence_coherent` | Noul | pattern | mutation observed |
| 3 | `expression_evidence_coherent` | Noul | pattern | expression observed |
| 4 | `signal_explained_by_coverage` | Noul | confound | mutation or expression observed |
| 5 | `unresolved_uncertainty_material` | Noul | value | mutation or expression observed |
| 6 | `warrants_deeper_investigation` | Noul | value/admission | mutation or expression observed |
| 7 | `dominant_limitation` | Choice | naming | mutation or expression observed |

The versioned instruction text and criteria are defined in `cancerjev/jev/questions.py` and
specified in `docs/PHASE_3_PLAN.md` §4.2; the Choice roster is `COVERAGE`, `MISSINGNESS`, `MUTATION_ABSENCE`, `EXPRESSION_SPARSITY`,
`PARTIAL_AGGREGATION`, `NONE`, `OTHER`.

Implemented `wide-policy-v2`: a deterministic eligibility gate
(`completeness == COMPLETE`, mutation observed, expression in `OBSERVED`/`PARTIAL`) followed by an
explicit admission rule over raw Nouls with provisional `ADMISSION_*` thresholds and
`PROMOTION_LIMIT = 3` as a maximum; if no state qualifies, `admission_decision = "ABSTAIN"` and
zero candidates are promoted. The rule is specified in `docs/PHASE_3_PLAN.md` §4.5. Raw Noul
probabilities, the full Choice distribution and every applicability flag remain persisted so the
policy can be recomputed without rerunning Jev. The deterministic baseline (`baseline-wide-v2`) is
retained separately; Jev never replaces it. Changed ranking is not evidence of a better research
decision — step 3 (baseline-vs-Jev evaluation) remains required.

The pre-Phase-3 audit's candidate list of semantic judgments that could replace fragile string
logic (workflow/assay comparability, canonical file selection, gene-mention resolution, clinical
label normalization) is in `docs/SOURCE_REVIEW.md`; each remains PLANNED and none may compute a
measurement or write a measured field.

## Wide policy and baseline comparison

Deterministic baseline (`baseline-wide-v2`, no model input): states ordered by affected cases
descending, mutation observation descending, coverage imbalance ascending, then `state_hash`
ascending. The first three state IDs are retained as `top_state_ids` for display/comparison only;
`admitted_state_ids` is empty because the baseline is not the admission authority.

Jev policy (`wide-policy-v2`): first exclude incomplete acquisition, unobserved mutation, or
expression outside `OBSERVED`/`PARTIAL`; then require warrants ≥0.60, material uncertainty ≥0.50,
evidence quality ≥0.40, and (when applicable) coverage confound ≤0.50. Rank qualified states by
warrants, uncertainty, quality, coverage confound, affected cases, and `state_hash`; admit at most
three. A threshold miss can produce a valid `ABSTAIN` with zero promotions. The ranking artifact
retains raw judgments, the full Choice distribution, applicability, per-state qualification and
exclusion reasons, and the thresholds. Thresholds are provisional and not calibrated. Both rankings
are retained; changed ranking is not evidence of a better research decision.

Thresholds and gates are recorded in policy code, never hidden in prompts. These are unvalidated
operational parameters, not provider guarantees. A Jev probability never confers statistical
significance, causality, or clinical meaning. Zero admissions and `ABSTAIN` are valid outcomes, not
failures.
