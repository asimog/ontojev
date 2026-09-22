# Versioned question architecture

Proposed question sets: `wide-v1`, `deep-v1`, `hypothesis-v1`; all are design drafts. Questions refer only to supplied observations and their limitations. They do not ask Jev to invent facts or prove mechanisms. Each definition includes an ID, primitive, exact instructions/criteria, applicability rule and version; changing wording changes the definition hash.

Shared Noul criteria template: true means the explicitly stated proposition is supported by the supplied observations and quality context; false means it is not supported. Lack of data does not establish a biological negative. If the necessary evidence is absent, deterministic applicability marks the answer unusable for that decision. Specialized wording below further fixes the proposition.

## Wide: nine questions in one request per state

| ID | Primitive | Instruction / applicability |
|---|---|---|
| warrants_deeper_investigation | Noul | Does the supplied observed pattern warrant a bounded deterministic investigation of the stated uncertainty? Requires >=1 usable observation; biological novelty is not a criterion. |
| cross_project_coherence | Noul | Do the supplied comparable project summaries support a coherent recurring pattern? At least two comparable projects; cross-project data need not be statistically independent. |
| project_specific_exception | Noul | Does an observed comparable project materially depart from the supplied dominant pattern? Missing projects are not exceptions. |
| direction_reversal | Noul | Do the supplied comparable signed effects exhibit a meaningful reversal? Requires >=2 valid signed effects and their uncertainty; variance/count alone is inapplicable. |
| weak_distributed_signal | Noul | Do the supplied moderate observations collectively form a coherent distributed pattern? Code supplies effect-size descriptors and coverage; Jev does not calculate a combined p-value. |
| multimodal_convergence | Noul | Do the supplied compatible modality observations support the same stated pattern? Require >=2 usable modalities and explicit shared-case/dependence caveats. |
| likely_fragile | Noul | Does the supplied sensitivity/coverage evidence indicate that the apparent pattern depends on one small or unstable subset? Code supplies dominance and missingness features. |
| pattern_type | Choice | Which pattern description best fits the supplied evidence? Use roster below; Insufficient evidence remains available. |
| followup_value | Score | How useful would one eligible bounded deterministic follow-up be for resolving this state's uncertainty? Five-level rubric below. |

Choice criteria:

```text
NO_COHERENT_PATTERN: usable observations show no coherent pattern.
WIDESPREAD_RECURRENCE: comparable observations recur across multiple projects.
PROJECT_SPECIFIC_EXCEPTION: an observed comparable project departs from the majority.
DIRECTION_REVERSAL: comparable signed effects reverse direction.
MULTIMODAL_CONVERGENCE: compatible modality observations agree on a stated pattern.
MULTIMODAL_DISCORDANCE: compatible modality observations conflict.
WEAK_DISTRIBUTED_SIGNAL: individually moderate observations recur coherently.
DATA_QUALITY_CONCERN: measurement/mapping/coverage problems dominate interpretation.
INSUFFICIENT_EVIDENCE: available observations cannot distinguish the patterns.
```

Follow-up-value Score levels, in exact order: 0 no eligible test can meaningfully reduce the stated uncertainty; 1 only weak expected clarification; 2 plausible clarification; 3 strong clarification of an explicit unresolved distinction; 4 unusually compelling clarification central to interpreting the supplied pattern. These are semantic ordinal levels; Score expectation is not an information-gain measurement.

## Deep: sixteen questions in one request per EvidenceState

All Noul questions independently inspect the same evidence, not earlier answers.

| ID | Primitive | Proposition |
|---|---|---|
| coherent_evidence | Noul | Observations support a coherent description of the research puzzle. |
| cross_project_recurrence | Noul | Comparable observations recur across the supplied projects; claimed independence is supported by metadata. |
| project_contradiction | Noul | A comparable project's observed result materially contradicts the dominant relationship. |
| project_dominance | Noul | The supplied pattern depends predominantly on one project. |
| small_n_fragility | Noul | The supplied sample-size/sensitivity context makes the pattern fragile. |
| modality_convergence | Noul | Compatible modality observations converge on the stated pattern. |
| modality_disagreement | Noul | Compatible modality observations materially disagree. |
| missingness_explanation | Noul | Supplied missingness patterns plausibly explain the apparent signal. |
| coverage_explanation | Noul | Supplied coverage imbalance plausibly explains the apparent signal. |
| bounded_test_value | Noul | A listed eligible deterministic action could materially clarify the puzzle. |
| hypothesis_generation_warranted | Noul | Available observations justify formulating competing explanations. |
| defer_candidate | Noul | Critical missing/unavailable evidence prevents useful further V1 investigation. |
| contradiction_warrants_test | Noul | Observed contradiction itself justifies a listed deterministic follow-up. |
| evidence_pattern | Choice | Use the wide pattern roster against deep evidence. |
| coherence | Score | 0 incoherent; 1 mostly unresolved; 2 partly coherent; 3 coherent with explicit caveats; 4 strongly coherent across supplied comparable observations. |
| next_test_value | Score | Use the five-level follow-up-value rubric. |

Code checks data comparability and eligible actions; Jev's positive answer cannot bypass those checks. Contradiction and support can both be high; retain that tension.

## Hypothesis review: nine questions per isolated hypothesis

State consists of one immutable EvidenceState, one generated hypothesis, and deterministically eligible action descriptions. No other hypotheses or their reviews. A re-review on new evidence creates a new evaluation linked to the same hypothesis.

| ID | Primitive | Proposition / criteria |
|---|---|---|
| supported | Noul | Supplied observations materially support this hypothesis over the stated null interpretation. |
| contradicted | Noul | Supplied observations materially contradict a prediction of this hypothesis. |
| exceeds_evidence | Noul | The hypothesis asserts factual conclusions beyond the supplied observations. |
| public_data_discriminability | Noul | Available public GDC evidence could discriminate a prediction from its stated alternative. |
| registered_test_exists | Noul | At least one supplied eligible registered action addresses a prediction. |
| unavailable_dependency | Noul | The hypothesis critically depends on evidence currently unavailable. |
| assessment | Choice | SUPPORT: observations favor predictions; CONTRADICT: observations oppose predictions; UNRESOLVED: neither disposition is justified or evidence conflicts. |
| discriminability | Score | 0 no distinction testable; 1 weak; 2 plausible; 3 strong; 4 clear decisive distinction within listed action scope. |
| next_test_value | Score | Five-level follow-up-value rubric. |

The deterministic registry, not `registered_test_exists`, establishes whether a test exists. The question evaluates its semantic fit. Hypothesis review is critique, not scientific verification/proof. Dossiers label it accordingly.

Thresholds/ranking are recorded in policy, not hidden in prompts. Fake examples must preserve all Noul values, Choice distributions, Score legends/distributions/confidence and uncertainty. No scalar `interesting_score` replaces this vector.
