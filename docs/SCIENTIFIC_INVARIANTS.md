# Scientific invariants and method registry

Deterministic code is authoritative for N, membership, units, counts, source values, effects, uncertainty intervals, p/q, tested universes and missingness. Jev and LLM outputs live in different record types with no path to write these fields. Provider-returned deterministic summaries retain their source attribution; local calculations retain method provenance. A Jev probability does not confer statistical significance or establish causality.

**Claim boundary — candidate-target investigation, not therapeutic validation.** OntoJev's first
research decision is: among candidate genes in a defined cohort, which have sufficiently coherent
and adequate public GDC evidence to justify spending bounded follow-up budget on deeper
candidate-target investigation? Public GDC evidence alone does not establish dependency,
druggability, therapeutic efficacy, safety, clinical benefit, biomarker qualification or drug
success. Documentation, UI copy and dossiers must not imply those claims.

Missing, not examined, not acquired, inaccessible, insufficient, incompatible and failed remain distinct from observed negative. Partial retrieval is not a complete denominator. Public mutation absence is not an assertion of biological wild type; missing CNV is not diploid; no expression column is not zero.

Use case as the biological analysis unit only where the method defines it. Enforce unique biological keys and explicit sample/workflow resolution. Duplicates cannot silently multiply N. Compare within compatible `(program,project,sample_type,workflow,pipeline,unit,method)` groups; cross-project comparisons require a documented comparability rule. The same gene across projects is insufficient.

Reject NaN/Infinity in output and compute eligibility after finite-value filtering. Constant or undersized inputs are untestable, not p=1 findings. Preserve all exclusions, including untested hypotheses. An interval with an unbounded endpoint uses a typed reason/representation rather than JSON Infinity.

Every method definition must declare:

```text
method_id, version, input/output schema, required fields and units,
eligibility predicate, analysis unit, population semantics, duplicate rule,
minimum sample requirements, sampling rule, estimator, effect definition,
interval method, null hypothesis if any, test assumptions,
correction family and adjustment, missingness handling,
failure/unsupported states, limitations, provenance requirements
```

Phase 2 registered methods (implemented, `cancerjev/science/methods.py`). Each is descriptive; none computes a p-value, q-value, effect size, or biological direction.

| Method | Purpose | Estimator | Registered? |
|---|---|---|---|
| `MUTATION_AFFECTED_CASE_COUNT_V1` | Gene-specific per-project count of cases with an SSM | Provider aggregation bucket count | yes |
| `PROJECT_SSM_COVERAGE_V1` | Per-project mutation-data availability context | `case_with_ssm` count and project case count retained separately | yes |
| `EXPRESSION_LOG2_SUMMARY_V1` | Exact-case-set expression location/dispersion | median (n≥1), sample SD (n≥2), min/max of `log2(UQFPKM+1)` | yes |
| `EXPRESSION_PROVIDER_SUMMARY_V1` | Retain provider expression summary verbatim | provider `log2_uqfpkm_median` / `log2_uqfpkm_stddev`, estimator convention unverified | yes |
| `PROJECT_DOMINANCE_V1` | Descriptive concentration of affected cases | `max(affected)/sum(affected)` over observed projects | yes |
| `MUTATION_RECURRENCE_V1` | Fraction with matched denominator | **not registered** | no — no matched denominator exists in open data |
| `STRATIFY_BY_PROJECT_V1` | Leave-one-project-out recomputation | Phase 4 | no (documented) |

`MUTATION_AFFECTED_CASE_COUNT_V1` — unit `cases`; analysis unit is the case; population is all project cases in the provider’s mutation-indexed universe; duplicate rule is the provider’s unique-case bucket count (locally re-derivable only from occurrence rows, which Phase 2 does not acquire — declared limitation); eligibility is a present aggregation bucket for the project; an absent bucket is `NOT_OBSERVED`, never zero; no sampling (complete provider aggregation over the queried gene set); provenance is the retained response artifact hash, request hash, parser version and `/status` release identity.

`PROJECT_SSM_COVERAGE_V1` — retains `case_with_ssm` and the project’s total case count as separate quantities and never divides them into a callability claim; `case_with_ssm = 0` is a real observed zero for that project’s SSM pipeline availability; a project absent from the response is `NOT_OBSERVED`.

`EXPRESSION_LOG2_SUMMARY_V1` — input is the `/gene_expression/values` TSV with `tsv_units=uqfpkm`; transformation is `log2(x+1)`; median requires ≥1 finite value; sample SD (n−1 denominator) requires ≥2 finite values and is `INSUFFICIENT` otherwise; min/max reported; missing columns are counted, never imputed; non-finite values are excluded before eligibility; no test, interval, null hypothesis or correction family is defined because the method is descriptive; same input bytes and parameters produce the same output hash.

`EXPRESSION_PROVIDER_SUMMARY_V1` — retains provider values unchanged with `source = GENE_SELECTION` and `estimator_note = INFERRED_POPULATION_SD_UNVERIFIED` (live two-case capture: reported 0.29998 matches a population denominator, not sample). The provider summary is corroborating context only and never drives eligibility, thresholds or policy.

`PROJECT_DOMINANCE_V1` — eligibility: ≥2 observed projects and positive total; output is a share in `[0,1]`; `NOT_APPLICABLE` otherwise; descriptive only, with the explicit warning that dominance can be produced by coverage imbalance and does not imply a biological mechanism.

Minimum n above is a computational eligibility condition, not a claim of biological adequacy. Later inferential methods need prospectively specified sample/power limitations. A mutation/expression comparison may use a justified Welch test and Welch-compatible interval; do not copy the old normal `1.96*SE` interval merely because the p-value uses Welch. Continuous CNV/Pearson requires an actual comparable continuous CNV quantity and paired samples; categorical API CNV requires a different declared method.

Survival remains targeted exploratory work. Define time origin, censoring, sample eligibility, duplicate diagnoses/follow-ups, group assignment, missingness and negative-time handling before registering a local estimator. Never average batched survival curves/p-values or present GDC overallStats as a confirmed covariate-adjusted hazard estimate.

For inferential families, freeze the complete tested universe and correction rule before examining selected results. 
BH adjustment applies to the recorded family of testable hypotheses, not just significant/promoted hits. Keep selection bias explicit: adaptive 
exploration is not confirmatory validation. New follow-ups get new family records and do not rewrite prior q-values. No genome-wide FDR claim from a 
top-k candidate list.

## Deterministic follow-up actions (Phase 4 first slice)

A registered action is a bounded, reproducible computation over evidence that already exists. It
acquires no data, calls no model, computes no new biological quantity and never rewrites the
evidence it reads. Its contract (`ACTION_REGISTRY`) declares the question, the falsifiable
interpretation, the method id/version, the analysis unit, required evidence and limitations.

- Eligibility is deterministic and fail-closed: what cannot be verified from retained evidence is
  `NOT_OBSERVED`, never a silent pass, and an ineligible action refuses to execute.
- Every observation records an explicit outcome (`VERIFIED` / `CONTRADICTED` / `NOT_OBSERVED`),
  the evidence it used and its missingness. A check outcome is provenance/consistency evidence, not
  a measurement: `inference_status` is `NOT_APPLICABLE` and no effect estimate, interval or p-value
  is fabricated.
- `CHECK_EVIDENCE_INTEGRITY_V1` verifies the candidate's recorded evidence against its retained
  selection and response artifacts: lane examined-frame agreement, expression coverage arithmetic,
  mutation count scope, tested-universe reproducibility from retained bytes, and response-artifact
  integrity including the acquisition-attempt link.
- Revisions are immutable: each follow-up writes a new EvidenceState whose parent is the previous
  revision (`source_statistical_state` names the accepted StatisticalState). Evidence identity
  excludes operational ids, artifact ids, timestamps and attempt links.
- Python owns selection, budget (`followup_count ≤ 3`, `iteration ≤ 2`), idempotency
  (one execution per candidate/action/input-evidence hash), stopping and abstention. A failure is a
  typed outcome: it promotes nothing, advances nothing and preserves the prior revision.

## Deep Jev judgment and the next-move policy (Phase 4 next stage)

One Deep Jev fan-out judges the current immutable revision together with the eligible registered
action set, using its own versioned question set (`deep-v1`). The boundary is explicit:

- The supplied projection carries only recorded revision content and registry facts; no measured
  field is written from a judgment, and a judgment is never evidence.
- Applicability is decided by code from the revision's recorded checks, so a question that cannot be
  grounded is marked inapplicable and the evaluation records that.
- Provider or validation failure is a persisted `JEV_EVALUATION_FAILED`; the revision stands and the
  run continues. There is no fabricated default answer.
- The Python next-move policy (`deep-policy-v2`) maps the recorded checks and the judgment to exactly
  one typed move (`COMPLETE`, `FOLLOW_UP`, `ABSTAIN`) with named thresholds. A contradicted
  integrity check abstains before any judgment dimension is consulted; a missing or failed judgment
  abstains as `DEEP_JUDGMENT_UNAVAILABLE`.
- The recorded move is never dispatched by the policy: `executed` is always false, and a warranted
  step with no distinct eligible action is reported as `NO_FURTHER_REGISTERED_ACTION` rather than
  dropped. Jev does not select, authorize or execute a computation, and no loop is driven by a
  judgment.
## Generated hypotheses and live dossiers (Phase 5-6)

- Generated text is never evidence. Every statement carries a label naming its generator, is stored in
  its own record, is bounded (`MAX_HYPOTHESES = 3` per candidate) and never writes a measured field.
- This repository performs no model request, holds no provider credential and defines no provider
  contract. Generation is deterministic by default; an LLM is used only through a generator injected
  by the caller, whose output is validated strictly (schema, non-empty statement, distinguishing tests
  restricted to eligible registered actions) and whose absence or deviation is a typed, recorded
  `UNAVAILABLE` outcome.
- `hypothesis-v2` reviews each statement over the new `jev-hypothesis-projection-v1` projection. The
  review is an input to Python policy; it executes nothing and authorizes nothing.
- A live dossier is presentation over what the run already recorded: every section states its
  availability and reason, the live notice names what the dossier does and does not support, and no
  measurement is computed while building it.
- The baseline-versus-Jev harness compares recorded rankings against an operator-supplied,
  pre-registered label file. It is descriptive: with one cohort, a selection-biased examined gene set
  and k <= 3 it never claims that a changed ranking improved the decision.

- Deep thresholds are provisional and must not be tuned to force a move; a `COMPLETE` decision is a
  statement about remaining deterministic work, not a biological conclusion. The `deep-policy-v2`
  values are `revision_reliable_min = 0.5`, `evidence_sufficient_min = 0.5`,
  `next_step_warranted_min = 0.6` and `stopping_more_honest_min = 0.5`
  (`cancerjev/research/nextmove.py` is the source of truth).

## Dispatch of a recorded move (Phase 4 dispatch stage)

- An action declares its input kind, and eligibility is computed against that kind, so a revision
  action can never be run on a state (or the reverse) by accident. `CHECK_REVISION_FAITHFULNESS_V1`
  re-derives no measurement: it verifies restatement, provenance, source-artifact identity and the
  revision chain, and reports anything it cannot verify as `NOT_OBSERVED`.
- The policy's recorded move is never dispatched by the policy; dispatch is a separate Python step
  that requires explicit operator authorization, runs at most once per run, and obeys
  `followup_count ≤ 3` and `iteration ≤ 2`. Every attempt consumes follow-up budget, not only
  successful ones, so a failed action cannot buy extra iterations.
- A dispatched revision is a new immutable revision whose parent is the current one; it cites its
  producing action, which is excluded from its own eligible set, so the follow-on decision is
  `NO_FURTHER_REGISTERED_ACTION` rather than a silent repetition.
- Every refusal to dispatch is recorded with a typed reason. Autonomous iteration, hypothesis
  generation and multi-candidate work remain unimplemented and out of scope here.


Scientific identity includes exact input hashes, population and sample mapping, units, method/version/parameters, tested universe, environment and results. Exclude scheduler, Jev, UI and clock state. Evidence revisions are new immutable records linked to their parent; semantic judgments never overwrite measurements.

Dossier numeric facts are rendered from observation references. Generated prose is labeled interpretation/hypothesis; authoritative measured tables are deterministic. Simple numeric-string screening cannot prove that arbitrary prose contains no fabricated fact. The safe first design uses templates for factual prose and confines model output to clearly labeled hypotheses, predictions and experiments. Scientific factual claims require resolvable observation refs.

Later Jev benchmark: fixed challenge states for obvious/null/weak distributed/direction reversal/project exception/convergence/contradiction/small-N/missingness traps. Compare deterministic ranking, generic LLM judge, and Jev on the same candidate universe and resource envelope; predeclare labels, hold out evaluation states, include failed/abstained cases. Report ranking quality, retrieval, false positives/negatives, repeatability, calibration only where valid labels exist, latency and measured cost. Cookbook results in unrelated domains do not prove cancer-discovery value. A Jev admission is a policy input, never scientific truth: zero admissions and an explicit `ABSTAIN` are valid outcomes, the admission set is not a quota, and a changed ranking is not evidence that Jev improved a research decision (see `docs/PHASE_3_PLAN.md`).
