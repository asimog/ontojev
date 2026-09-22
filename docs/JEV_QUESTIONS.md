# Versioned question architecture

Question sets: `wide-v2` (**IMPLEMENTED** in Phase 3), `deep-v2` and `hypothesis-v2` (**PROPOSED**, Phase 4+/Phase 6, not implemented). `wide-v1` was the Phase 0 draft for synthetic fixtures; `wide-v2` replaces it because the real state contains mutation counts, expression summaries and coverage context, but no signed effects, no registered follow-up, and no defined cross-modal proposition.

Each definition carries an ID, primitive, version, full instruction text, criteria, applicability rule and a hash over the canonical definition bytes. Question IDs are not sent to the model; changing wording changes the definition hash. Questions refer only to supplied observations and their stated limitations, and never ask Jev to invent facts, compute quantities, or establish causality.

Shared Noul criteria template: true means the explicitly stated proposition is supported by the supplied observations and their quality context; false means it is not supported. Missing data does not establish a biological negative; if the prerequisite evidence is absent, deterministic applicability marks the answer unusable for routing.

## `wide-v2`: six questions in one request per StatisticalState (Phase 3)

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

## `deep-v2`: reduced deep battery (Phase 4 draft, not implemented)

All Noul questions independently inspect the same immutable EvidenceState.

| ID | Primitive | Proposition |
|---|---|---|
| `coherent_evidence` | Noul | The supplied deterministic observations support one coherent description of the research puzzle. |
| `project_contradiction` | Noul | A comparable project’s observed result materially contradicts the dominant relationship. |
| `likely_fragile` | Noul | The supplied sample-size, dominance and sensitivity context makes the pattern fragile. |
| `bounded_test_value` | Noul | A listed eligible registered deterministic action could materially clarify the puzzle. |
| `evidence_pattern` | Choice | Use the `wide-v2` pattern roster against deep evidence. |
| `next_test_value` | Score | Five-level follow-up-value rubric (0 no eligible test … 4 unusually compelling clarification). |

## `hypothesis-v2`: hypothesis review (Phase 6 draft, not implemented)

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

## Wide policy and baseline comparison

Deterministic baseline (`baseline-wide-v1`, no model input): eligible states ordered by projects with mutation observations descending, then affected-case total descending, then `top_project_share` ascending, then `state_hash` ascending; top-K (≤3) admitted.

Jev policy (`wide-policy-v1`): `warrants_deeper_investigation` descending, then `likely_fragile` ascending, then `pattern_type` class priority (`WIDESPREAD_RECURRENCE` > `PROJECT_SPECIFIC_EXCEPTION` > `WEAK_DISTRIBUTED_SIGNAL` > `NO_COHERENT_PATTERN` > `DATA_QUALITY_CONCERN` > `INSUFFICIENT_EVIDENCE`), then `state_hash` ascending; top-K (≤3) admitted. Raw Noul probabilities, the full Choice distribution and every applicability flag are persisted, so the policy can be recomputed without rerunning Jev. Both rankings are persisted for the Phase 3 baseline-vs-Jev comparison; Jev never replaces the baseline.

Thresholds and gates are recorded in policy code, never hidden in prompts. Provisional starting gates: Noul ≥0.8 yes / ≤0.2 no, middle band uncertain; Choice confidence ≥0.7. These are unvalidated operational parameters, not provider guarantees. A Jev probability never confers statistical significance, causality, or clinical meaning.
