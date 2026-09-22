# Versioned question architecture

Implementation plan for the pending redesign: `docs/PHASE_3_PLAN.md`. This document describes the
current (stale) `wide-v2` set and the planned shape; it does not implement the replacement.

Question sets: `wide-v2` (**technically IMPLEMENTED in Phase 3, semantically STALE pending redesign**), `deep-v2` and `hypothesis-v2` (**PLANNED**, Phase 4+/Phase 6, not implemented). `wide-v1` was the Phase 0 draft for synthetic fixtures; `wide-v2` replaced it because the real state contains mutation counts, expression summaries and coverage context, but no signed effects, no registered follow-up, and no defined cross-modal proposition. `wide-v2` was itself designed around a cross-project evidence model; for the single TCGA-LUAD cohort several of its questions are inapplicable or ungrounded, so the set must be redesigned before Phase 3 is treated as scientifically meaningful. No replacement is implemented here.

Each definition carries an ID, primitive, version, full instruction text, criteria, applicability rule and a hash over the canonical definition bytes. Question IDs are not sent to the model; changing wording changes the definition hash. Questions refer only to supplied observations and their stated limitations, and never ask Jev to invent facts, compute quantities, or establish causality.

Shared Noul criteria template: true means the explicitly stated proposition is supported by the supplied observations and their quality context; false means it is not supported. Missing data does not establish a biological negative; if the prerequisite evidence is absent, deterministic applicability marks the answer unusable for routing.

## `wide-v2`: six questions in one request per StatisticalState (Phase 3, semantically stale)

`wide-v2` remains wired into the code and persists valid evaluations, but under a single-cohort
LUAD state `mutation_project_exception` and `expression_project_exception` (require ≥3 project
observations), `likely_fragile` (needs `top_project_share`, `NOT_APPLICABLE` with one project)
and `coverage_explains_apparent_difference` (needs a cross-project coverage imbalance) become
inapplicable or ungrounded, and the `pattern_type` roster is cross-project. The definitions below
are retained for audit; they are not the target semantics.

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

## `wide-v3`: planned single-cohort redesign (PLANNED, not implemented)

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

Proposed instruction text and the `dominant_limitation` roster are fixed in `docs/PHASE_3_PLAN.md`
§4.2; the roster is `COVERAGE`, `MISSINGNESS`, `MUTATION_ABSENCE`, `EXPRESSION_SPARSITY`,
`PARTIAL_AGGREGATION`, `NONE`, `OTHER`.

Planned `wide-policy-v2` (PLANNED): a deterministic eligibility gate
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

Deterministic baseline (`baseline-wide-v1`, no model input): eligible states ordered by projects with mutation observations descending, then affected-case total descending, then `top_project_share` ascending, then `state_hash` ascending; top-K (≤3) admitted.

Jev policy (`wide-policy-v1`): `warrants_deeper_investigation` descending, then `likely_fragile` ascending, then `pattern_type` class priority (`WIDESPREAD_RECURRENCE` > `PROJECT_SPECIFIC_EXCEPTION` > `WEAK_DISTRIBUTED_SIGNAL` > `NO_COHERENT_PATTERN` > `DATA_QUALITY_CONCERN` > `INSUFFICIENT_EVIDENCE`), then `state_hash` ascending; top-K (≤3) admitted. Raw Noul probabilities, the full Choice distribution and every applicability flag are persisted, so the policy can be recomputed without rerunning Jev. Both rankings are persisted for the baseline-vs-Jev comparison; Jev never replaces the baseline. This ordering depends on stale cross-project dimensions and is superseded by the planned `wide-policy-v2` (see `wide-v3` above and `docs/PHASE_3_PLAN.md` §4.4–4.5); the baseline-vs-Jev evaluation remains the required test of incremental value.

Thresholds and gates are recorded in policy code, never hidden in prompts. Provisional starting gates: Noul ≥0.8 yes / ≤0.2 no, middle band uncertain; Choice confidence ≥0.7. These are unvalidated operational parameters, not provider guarantees. A Jev probability never confers statistical significance, causality, or clinical meaning. Under the planned `wide-policy-v2`, a state that fails the admission thresholds is not admitted, and an empty admission set is a valid `ABSTAIN` outcome rather than a failure.
