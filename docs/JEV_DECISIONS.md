# Jev decision boundaries

OntoCodex generates and synthesizes; Jev supplies bounded probabilistic
judgments; Python computes and executes. The compact contract registry is
`cancerjev/jev/decisions.py`. A contract identifies role, question set, projection,
outputs, baseline, uncertainty semantics, failure behavior and evaluation status.

## Current assessment

| Boundary | Assessment | Treatment |
| --- | --- | --- |
| Wide coherence/limitations | Useful bounded judgments, not validated target scores | Preserve scientific contract and deterministic narrowing |
| Wide follow-up warrant | Combines several semantic questions; incremental value unevaluated | Explicit experimental status; preserve historical version pending paired evaluation |
| Deep reliability | Partly duplicates deterministic integrity checks | Python contradictions remain decisive; no Jev override |
| Deep continue/stop | Related propositions may conflict | Preserve probabilities and next-move abstention; experimental status |
| Hypothesis critique | Appropriate bounded testability/overreach judgment | Does not confirm hypotheses; Python decides test availability |
| Acquisition relevance | Plausible but unproven pointwise Noul use | Shadow evaluation, disabled by default |
| Acquisition comparison | Choice over feasible alternatives plus NONE | Shadow evaluation, disabled by default |
| Numerical checks, maturity, eligibility | Deterministic | No new Jev calls |

No registry entry claims established scientific accuracy or superiority. Existing
Wide/Deep behavior remains operational; experimental metadata makes its evidence
status explicit. Historical artifacts are unchanged. No genome-wide Jev ranker
was introduced. Near-tie diagnostics expose weak separation; the existing exact
tie order uses measured affected-case counts then a stable administrative hash,
which is not scientific evidence.

## Controlled experiments

Set `ONTOCODEX_JEV_EXPERIMENT=relevance` or `choice` to record one bounded control
experiment per eligible block. The default is `off`. Python excludes offers that
cannot fit byte/time budgets before asking Jev. Shadow answers are not sent to
OntoCodex, preserving the direct decision as a comparator. No probability
threshold accepts a new contract automatically.

`python -m cancerjev.jev.replay corpus.json` compares recorded answers with
baseline decisions. Each corpus row includes `contract_id`, `questions` (the
QuestionDefinition fields), validated `answers`, and optionally
`baseline_option`, `equivalent_state_id`, `latency_ms`, `cost`, and binary
`labels`. It reports agreement, repeat stability, uncertainty diagnostics and
labelled Brier score. Unlabelled runs report no accuracy/calibration claim.
Equivalent-state groups must be independently declared by the evaluator.

Acceptance requires a named evaluation corpus and comparison supporting the
boundary's intended use. Passing a replay or software test alone does not
promote EXPERIMENTAL to ACCEPTED. Future question changes must retain their
original question/projection identities for historical readers.

The Observatory exposes role, contract, questions, answers and experimental
status with deeper traces expandable. Scientific evaluation records include
contract and uncertainty provenance; dossier limitations distinguish these
judgments from measured evidence and from control history.
