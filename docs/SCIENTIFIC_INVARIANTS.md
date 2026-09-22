# Scientific invariants and method registry

Deterministic code is authoritative for N, membership, units, counts, source values, effects, uncertainty intervals, p/q, tested universes and missingness. Jev and LLM outputs live in different record types with no path to write these fields. Provider-returned deterministic summaries retain their source attribution; local calculations retain method provenance. A Jev probability does not confer statistical significance or establish causality.

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

Initial proposed methods, introduced only after Phase 1:

| Method | Minimal scientific contract |
|---|---|
| MUTATION_RECURRENCE_V1 | Unique observed affected cases; fraction only with a matched known denominator, N>0. Descriptive first; no invented null, p, or q. Unknown assay callability prevents wild-type interpretation. |
| EXPRESSION_VARIABILITY_V1 | Valid nonnegative UQFPKM; local log2(x+1); sample SD requires >=2 finite values and is descriptive. Retain source SD separately when estimator convention is unknown. Rank only within explicit examined universe. |
| STRATIFY_BY_PROJECT_V1 | Recompute per-project contributions, dominant-project share and leave-one-project-out recurrence from held observations; requires >=2 comparable projects. New result/state can support or weaken a dominance hypothesis. Descriptive, no fake p-value. |

Minimum n above is a computational eligibility condition, not a claim of biological adequacy. Later inferential methods need prospectively specified sample/power limitations. A mutation/expression comparison may use a justified Welch test and Welch-compatible interval; do not copy the old normal `1.96*SE` interval merely because the p-value uses Welch. Continuous CNV/Pearson requires an actual comparable continuous CNV quantity and paired samples; categorical API CNV requires a different declared method.

Survival remains targeted exploratory work. Define time origin, censoring, sample eligibility, duplicate diagnoses/follow-ups, group assignment, missingness and negative-time handling before registering a local estimator. Never average batched survival curves/p-values or present GDC overallStats as a confirmed covariate-adjusted hazard estimate.

For inferential families, freeze the complete tested universe and correction rule before examining selected results. BH adjustment applies to the recorded family of testable hypotheses, not just significant/promoted hits. Keep selection bias explicit: adaptive exploration is not confirmatory validation. New follow-ups get new family records and do not rewrite prior q-values. No genome-wide FDR claim from a top-k candidate list.

Scientific identity includes exact input hashes, population and sample mapping, units, method/version/parameters, tested universe, environment and results. Exclude scheduler, Jev, UI and clock state. Evidence revisions are new immutable records linked to their parent; semantic judgments never overwrite measurements.

Dossier numeric facts are rendered from observation references. Generated prose is labeled interpretation/hypothesis; authoritative measured tables are deterministic. Simple numeric-string screening cannot prove that arbitrary prose contains no fabricated fact. The safe first design uses templates for factual prose and confines model output to clearly labeled hypotheses, predictions and experiments. Scientific factual claims require resolvable observation refs.

Later Jev benchmark: fixed challenge states for obvious/null/weak distributed/direction reversal/project exception/convergence/contradiction/small-N/missingness traps. Compare deterministic ranking, generic LLM judge, and Jev on the same candidate universe and resource envelope; predeclare labels, hold out evaluation states, include failed/abstained cases. Report ranking quality, retrieval, false positives/negatives, repeatability, calibration only where valid labels exist, latency and measured cost. Cookbook results in unrelated domains do not prove cancer-discovery value.
