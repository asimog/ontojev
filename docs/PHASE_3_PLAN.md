# Phase 3 implementation plan — TCGA-LUAD Wide Jev semantic/admission redesign

Status: **PLAN (not implemented).** Step 2 of the sequence in `docs/IMPLEMENTATION_STATUS.md`.
Step 1 (targeted pre-Phase-3 readiness audit) is complete (`docs/SOURCE_REVIEW.md`).

Authority: `docs/SOURCE_REVIEW.md` (GDC docs + TypeSafe docs), `docs/JEV_DESIGN.md`,
`docs/JEV_QUESTIONS.md`, `docs/ARCHITECTURE.md`, `docs/SCIENTIFIC_INVARIANTS.md`, and the
implemented code referenced by file and line.

This plan fully specifies the redesign so it can be implemented as one bounded task. It changes no
code. It does not implement Deep Jev, Phase 4, or any LLM path.

---

## 1. Goal

Replace the semantically stale cross-project `wide-v2` question set with a single-cohort
TCGA-LUAD Wide design that:

- asks atomic questions over a deterministic single-cohort projection;
- separates **evidence quality**, **evidence pattern**, and **value of deeper investigation**;
- never asks Jev for a deterministic fact;
- preserves the deterministic baseline and every raw Jev dimension;
- uses an **explicit Python admission rule** that permits **zero admissions** and supports
  `ABSTAIN`;
- treats the promotion limit as a **maximum, not a quota**;
- makes no claim that Jev improves a research decision (step 3 evaluates that).

The decision the redesigned set must answer:

> Which TCGA-LUAD candidate states, if any, contain sufficiently coherent and decision-relevant
> evidence to justify spending bounded future follow-up budget on deeper investigation?

## 2. Non-goals

- No Deep Jev, no Phase 4 `EvidenceState` runtime, no follow-up execution, no autonomous loop.
- No LLM/hypothesis work, no OpenRouter call, no new GDC modalities, no LUSC production spec.
- No change to the measurement boundary: Jev never writes a measured field.
- No new framework/service/planner objects; no schema migration (new versions are new records).

---

## 3. Current-state analysis (what exists, what is stale)

The Phase 3 path is real and tested:

| Concern | Location | Current value |
|---|---|---|
| Projection | `cancerjev/jev/projection.py:16-17` | `jev-state-projection-v1`, 64 KiB cap |
| Projection shape | `cancerjev/jev/projection.py:89-157` | `project_observations[]` + `cross_project{}` |
| Question set | `cancerjev/jev/questions.py:17` | `wide-v2`, six questions |
| Applicability | `cancerjev/jev/questions.py:171-189` | code-owned rules |
| Service/cache | `cancerjev/jev/service.py:110-168` | projection + question hash + model + adapter |
| Contracts | `cancerjev/jev/contracts.py` | primitive-based, fail-closed |
| Adapter | `cancerjev/jev/typesafe_adapter.py` | one provider boundary, typed errors |
| Policy | `cancerjev/research/ranking.py:13-15` | `baseline-wide-v1`, `wide-policy-v1`, `PROMOTION_LIMIT = 3` |
| Orchestration | `cancerjev/research/wide.py`, `cancerjev/research/live.py:321-329` | `JEV_WIDE` stage |
| State | `cancerjev/science/methods.py:353-736` | schema v2 |
| Exposure | `apps/api/routes.py:151-168`; `apps/web/components/WideJudgment.tsx`, `WideRanking.tsx`, `RunDetail.tsx:154-173` | rankings + judgments |

### Why `wide-v2` is stale for one cohort

The production spec is exactly one project (`LUAD_RESEARCH_V1` → `TCGA-LUAD`), so
`state["project_observations"]` has length 1 and `cross_project` is degenerate:

| wide-v2 question | Applicability rule | Behavior with one cohort |
|---|---|---|
| `warrants_deeper_investigation` | `any_observation` | Applicable; instruction says "across several cancer projects" |
| `mutation_project_exception` | `three_mutation_observations` | Always inapplicable (1 project) |
| `expression_project_exception` | `three_expression_observations` | Always inapplicable |
| `coverage_explains_apparent_difference` | `coverage_imbalance` | Cross-project imbalance cannot occur |
| `likely_fragile` | `two_observations` | Inapplicable (needs ≥2 projects) |
| `pattern_type` | `any_observation` | Roster describes cross-project patterns |

`wide-policy-v1` then sorts on `warrants_deeper_investigation`, `likely_fragile` (always null) and
cross-project `pattern_type`, so ranking degenerates to one usable dimension plus a null tiebreaker,
and it always admits top-3 with **no threshold and no abstain** (`ranking.py:106-124`).

---

## 4. Target design

### 4.1 Projection v2 (single cohort)

New `PROJECTION_VERSION = "jev-state-projection-v2"`. Replace `project_observations[]` and
`cross_project{}` with one `cohort` block. **Every value is copied from the existing deterministic
state; no new measurement is computed.** Ratios not already present in the state are omitted rather
than derived in the projection.

```jsonc
{
  "projection_version": "jev-state-projection-v2",
  "entity": { "gene_id": "...", "symbol": "...", "biotype": "...", "cancer_census": false },
  "scope": {
    "cohort": "TCGA-LUAD",
    "domain": "lung cancer",
    "projects": ["TCGA-LUAD"],
    "modalities": ["mutation_counts", "expression_summary"],
    "expression_unit": "log2(UQFPKM+1)",
    "workflow": "STAR - Counts",            // null when unknown
    "examined_case_frame": "ALL_CASES_PAGINATED",
    "selection_bias": "Genes are discovered from the provider top-mutated ranking ..."
  },
  "cohort": {
    "project_id": "TCGA-LUAD",
    "examined_cases": 510,                  // populations[0].examined_n
    "affected_cases": 12,                   // mutation.project_results[0].affected_case_count (or null)
    "mutation_observed": true,              // affected_case_count.availability == "OBSERVED"
    "mutation_coverage_complete": true,     // mutation.coverage.coverage_complete
    "ssm_coverage_cases": 498,              // mutation.project_results[0].project_case_with_ssm
    "expression_observed": true,            // local median availability == "OBSERVED"
    "expression_median": 3.14,              // local.median (log2(UQFPKM+1))
    "expression_sample_sd": 1.02,           // local.sample_sd
    "expression_n_finite": 505,             // local.n_finite
    "expression_n_missing": 5,              // local.n_missing
    "expression_provider_median": 3.10,     // provider.median (corroborating context only)
    "expression_provider_stddev": 1.00,     // provider.stddev
    "coverage_imbalance": false,            // cross_project.coverage_imbalance (existing flag)
    "completeness": "COMPLETE",             // quality.completeness
    "scientific_sufficiency": "SUFFICIENT"  // quality.scientific_sufficiency
  },
  "missingness": ["..."],
  "limitations": ["..."],
  "eligible_followups": []
}
```

`INCLUDED_FIELDS` is rewritten to this shape; `projection_hash` covers canonical bytes; the 64 KiB
cap and `PROJECTION_TOO_LARGE` behavior are unchanged. `eligible_followups` stays empty until Phase 4.

### 4.2 Question set v3 (atomic, single cohort)

New `WIDE_QUESTION_SET_VERSION = "wide-v3"`. Six Nouls + one closed Choice. Exact instruction text
below is the proposed definition; it is finalized in implementation and hashed.

Shared criteria: reuse `NOUL_TRUE_CRITERION` / `NOUL_FALSE_CRITERION` (true = stated proposition is
supported by the supplied observations and their quality context; false = not supported). Missing
data never establishes a biological negative.

| # | question_id | Primitive | Dimension | Applicability rule |
|---|---|---|---|---|
| 1 | `evidence_quality_adequate` | Noul | quality | `any_observation` |
| 2 | `mutation_evidence_coherent` | Noul | pattern | `mutation_observed` |
| 3 | `expression_evidence_coherent` | Noul | pattern | `expression_observed` |
| 4 | `signal_explained_by_coverage` | Noul | confound | `any_observation` |
| 5 | `unresolved_uncertainty_material` | Noul | value | `any_observation` |
| 6 | `warrants_deeper_investigation` | Noul | value/admission | `any_observation` |
| 7 | `dominant_limitation` | Choice | naming | `any_observation` |

Proposed instructions (verbatim definitions):

1. **`evidence_quality_adequate`** — "You are reviewing a compact deterministic profile of one
   gene in one TCGA-LUAD cohort. It states the examined-case count, the number of cases with a
   somatic mutation in this gene, the number of cases with an observed SSM (mutation-data
   coverage), the number of cases with gene expression values, and the local log2(UQFPKM+1)
   expression summary, with missingness and acquisition completeness stated explicitly. Decide
   whether this evidence is adequate to make a bounded investigation decision for this candidate.
   Adequacy means the measurements cover enough of the examined cohort and the stated missingness
   is small enough that deeper investigation would rest on observed evidence rather than on absent
   data. Biological novelty is not required."
2. **`mutation_evidence_coherent`** — "Using the supplied mutation evidence
   (`cohort.affected_cases`, `cohort.ssm_coverage_cases`, `cohort.examined_cases`) and the stated
   partial-aggregation and missingness context, decide whether the mutation counts support a
   coherent interpretation for this cohort, rather than being an artifact of absent gene buckets,
   partial aggregation or incomplete mutation-data coverage. An observed zero is a valid
   observation; an absent bucket is not."
3. **`expression_evidence_coherent`** — "Using the supplied local expression summary
   (`cohort.expression_median`, `cohort.expression_sample_sd`, `cohort.expression_n_finite`,
   `cohort.expression_n_missing`) and the stated missing-expression context, decide whether the
   expression evidence is coherent and interpretable for this cohort, rather than being dominated
   by missing values or too few finite measurements to characterize the gene."
4. **`signal_explained_by_coverage`** — "The profile states examined cases, mutation-data coverage
   and expression coverage for this cohort. Decide whether the apparent candidate signal
   (mutation count and/or expression level) is plausibly explained by unequal or incomplete
   coverage or by missing data, rather than by a candidate-relevant pattern in the observed
   cases."
5. **`unresolved_uncertainty_material`** — "Given the stated evidence and its named limitations,
   decide whether a material, specific uncertainty about this candidate remains unresolved — one
   that a bounded registered follow-up over held or small public data could reduce. Do not count
   uncertainty that is merely 'more data would be nice'; the uncertainty must be specific and
   addressable."
6. **`warrants_deeper_investigation`** — "Decide whether spending bounded follow-up budget on a
   deeper investigation of this candidate is justified now. Consider the stated evidence quality,
   the coherence of the mutation and expression evidence, whether coverage or missingness
   plausibly explains the apparent signal, and whether a material uncertainty remains. A follow-up
   is a small registered computation over held data or a small bounded public-data query, not a
   clinical action; biological novelty is not required."
7. **`dominant_limitation`** — "Which single limitation most dominates the interpretation of this
   candidate's evidence? Choose the one best-fitting option, or NONE when no listed limitation
   dominates."

`dominant_limitation` roster (closed; every option the single-cohort state can express):

```text
COVERAGE: incomplete or unequal mutation/expression coverage limits interpretation.
MISSINGNESS: missing measurements or absent columns dominate the evidence.
MUTATION_ABSENCE: no mutation observation exists for this cohort (bucket absent, not a callable negative).
EXPRESSION_SPARSITY: too few finite expression values to characterize the gene.
PARTIAL_AGGREGATION: a provider aggregation was incomplete.
NONE: no listed limitation dominates.
OTHER: a limitation outside the listed options dominates.
```

Design notes:

- Questions 1–3 are the three separated dimensions; 4 is the confound; 5–6 are the value of
  investigation; 7 names the uncertainty a follow-up would target.
- `dominant_limitation` is a Choice because the alternatives are genuinely mutually exclusive and
  closed. It is **not** used to rank and computes nothing deterministic.
- No Score is introduced. No deterministic fact (counts, shares, flags) is asked of the model.
- Excluded from v3 and why: `mutation_project_exception` / `expression_project_exception` /
  `likely_fragile` / cross-project `pattern_type` (single-cohort degeneracy); `direction_reversal`
  (no signed effect); `multimodal_convergence` (no defined cross-modal proposition); any Score
  follow-up-value rubric (no registered action until Phase 4).

### 4.3 Deterministic applicability (code-owned)

New rules are added to `applicability()` (`questions.py:171-189`) and to the import-time
`validate_definitions` allow list:

- `mutation_observed`: `projection.cohort.mutation_observed is True`.
- `expression_observed`: `projection.cohort.expression_observed is True`.
- `any_observation`: mutation observed or expression observed.

A question whose prerequisite is absent is retained but marked inapplicable and excluded from
routing, exactly as today. The model never decides applicability.

### 4.4 Baseline ranking v2

New `BASELINE_POLICY_VERSION = "baseline-wide-v2"`, deterministic and single-cohort:
`affected_cases` desc, then `mutation_observed` desc, then `coverage_imbalance` asc, then
`state_hash` asc. Top-K (≤3) is retained for display/comparison only; the baseline is **not** the
admission authority.

### 4.5 Admission and Jev ranking v2

New `JEV_POLICY_VERSION = "wide-policy-v2"`. `PROMOTION_LIMIT = 3` remains a **maximum**.

Deterministic eligibility gate (no Jev; applied before any dimension is read):

```text
cohort.completeness == "COMPLETE"
cohort.mutation_observed is True
expression availability in {"OBSERVED", "PARTIAL"}
```

Admission (raw Noul dimensions, only when applicable):

```text
qualify if:
  warrants_deeper_investigation    >= ADMISSION_MIN_WARRANTS
  unresolved_uncertainty_material  >= ADMISSION_MIN_UNCERTAINTY
  evidence_quality_adequate        >= ADMISSION_MIN_QUALITY
  and (signal_explained_by_coverage is not applicable or <= ADMISSION_MAX_CONFOUND)

rank qualifiers by:
  warrants_deeper_investigation desc,
  unresolved_uncertainty_material desc,
  evidence_quality_adequate desc,
  signal_explained_by_coverage asc,
  affected_cases desc,
  state_hash asc

admit at most PROMOTION_LIMIT; if none qualify -> admission_decision = "ABSTAIN" (zero promotions)
```

Provisional constants (named in `ranking.py`, recorded in the ranking artifact, calibrated in
step 3 — never hidden in prompts):

```text
ADMISSION_MIN_WARRANTS     = 0.60
ADMISSION_MIN_UNCERTAINTY  = 0.50
ADMISSION_MIN_QUALITY      = 0.40
ADMISSION_MAX_CONFOUND     = 0.50
PROMOTION_LIMIT            = 3   # maximum, not a quota
```

The Jev ranking artifact gains an `admission` block: `decision` (`ADMIT`/`ABSTAIN`), the four
thresholds, `promotion_limit`, and per-state `qualified`/`excluded_reason`. `admitted_state_ids`
may be empty. Raw Noul probabilities, the full Choice distribution, every applicability flag and
`cache_source_evaluation_id` remain persisted so policy can be recomputed without rerunning Jev.

### 4.6 Contracts, adapter, service

- `contracts.py` stays generic; a 7-option Choice and Nouls need no new primitive support.
- `typesafe_adapter.py` unchanged; import-time validation already enforces Choice ≤255 and the
  documented limits.
- `service.py` is unchanged in logic. Because the question-set hash and projection version change,
  cache keys separate v2 from v3 automatically. v2 evaluations remain valid immutable records.

### 4.7 Versioning, cache, immutability

- New projection version and question-set version; existing artifacts/rows are never rewritten.
- `_register_projection` already keys on `(state_id, projection_version)`, so v1 and v2 projections
  coexist (`service.py:76-84`).
- No DB schema change (`jev_evaluations.vector_json` is version-agnostic); no migration.

### 4.8 Events, artifacts, API, UI

- `JEV_WIDE_STARTED` reports `question_set: "wide-v3"`.
- `WIDE_RANKING_COMPLETED` gains `admission_decision` and `thresholds`; `JEV_WIDE_COMPLETED` gains
  `admission_decision` and may report `promoted: 0`.
- Ranking artifacts (`baseline_ranking.json`, `jev_ranking.json`) include the `admission` block.
- `/api/runs/{id}/rankings` needs no route change (it returns artifacts verbatim).
- UI: update `WideJudgment.tsx` label map, `WideRanking.tsx` dimension labels, and
  `RunDetail.tsx:154-173` summary for the v3 IDs; display `admission_decision` and show `ABSTAIN`
  and zero promotions explicitly rather than as an error.

---

## 5. Implementation steps (ordered, file-by-file)

1. `cancerjev/jev/projection.py` — rewrite `build_projection`, `INCLUDED_FIELDS`,
   `_limitations`; bump `PROJECTION_VERSION` to `jev-state-projection-v2`. Keep the byte cap.
2. `cancerjev/jev/questions.py` — replace `WIDE_QUESTIONS`, `PATTERN_ROSTER`; bump
   `WIDE_QUESTION_SET_VERSION` to `wide-v3`; add `mutation_observed`/`expression_observed`
   applicability rules and update the validation allow list.
3. `cancerjev/research/ranking.py` — new `baseline-wide-v2`; new `wide-policy-v2` with the
   eligibility gate, admission rule, threshold constants and `admission` block; keep raw dimensions.
4. `cancerjev/research/wide.py` — emit `question_set: wide-v3`, surface `admission_decision`,
   tolerate zero promotions.
5. `apps/web/components/WideJudgment.tsx`, `apps/web/components/WideRanking.tsx`,
   `apps/web/components/RunDetail.tsx` — v3 labels, admission/`ABSTAIN` display.
6. Tests (§6).
7. Docs (§7).

No production code is changed by this planning task.

---

## 6. Tests

All offline and provider-free by default:

- **Projection v2**: deterministic bytes for a fixed state; no `cross_project` key; hash stable;
  byte-cap fail-closed; each included field copied from the state (no recomputation); a state with
  no expression yields `expression_observed = false` and null summaries.
- **Questions v3**: validates at import; question-set hash changes from v2; the applicability table
  in §4.2/§4.3 matches observed/absent mutation and expression; inapplicable answers retained but
  excluded from policy.
- **Contracts**: `dominant_limitation` outside the roster rejected; Noul range checks; a missing
  answer fails closed; Choice/Score probability keys enforced.
- **Ranking/admission v2**: deterministic for identical evaluations; the eligibility gate excludes
  non-`COMPLETE`/unobserved states; a threshold miss yields `admission_decision = "ABSTAIN"` with
  zero admissions; promotion count never exceeds `PROMOTION_LIMIT`; raw dimensions and the
  `admission` block persisted; baseline and Jev rankings cover the same states.
- **Cache**: v2 and v3 evaluations never collide; a v3 cache hit yields zero provider usage.
- **Orchestration (replay)**: a `--jev` run with a stub adapter produces v3 evaluations, rankings
  and either promotions or an explicit `ABSTAIN`.
- **Adversarial**: a failed/malformed evaluation defers its state rather than scoring it.
- **Live**: existing `live_jev` opt-in unchanged; no live call in this task.

---

## 7. Docs to update

| Document | Change |
|---|---|
| `docs/PHASE_3_PLAN.md` | This plan (the redesign specification). |
| `docs/JEV_QUESTIONS.md` | Add the planned `wide-v3` specification; keep `wide-v2` as stale history; describe planned `wide-policy-v2`. |
| `docs/JEV_DESIGN.md` | Mark projection v2 and policy v2 as PLANNED; state the admission rule is explicit and may admit zero. |
| `docs/IMPLEMENTATION_STATUS.md` | Record the plan and the redesign's planned versions; keep step 2 as NEXT. |
| `docs/GDC_BUDGETS.md` | Planned judgment count becomes seven questions per state. |
| `docs/TESTING.md` | Add the planned Phase 3 redesign gates. |
| `docs/ARCHITECTURE.md` | Note the planned single-cohort Wide redesign and admission policy. |
| `docs/SCIENTIFIC_INVARIANTS.md` | Add that zero admissions / `ABSTAIN` is a valid, non-failure outcome and that Jev admission confers no significance. |

---

## 8. Acceptance criteria

1. `wide-v3` is the current set; `wide-v2` is retained only as history.
2. Projection v2 is single-cohort with no misleading cross-project fields.
3. Questions separate quality, pattern and value; none asks for a deterministic fact.
4. Applicability is computed in code; inapplicable answers never drive policy.
5. The admission rule is explicit in `ranking.py`, permits zero admissions, and supports `ABSTAIN`.
6. The promotion limit is enforced as a maximum.
7. Baseline and Jev rankings are both persisted for the same states.
8. No claim of improved scientific decision quality; step 3 remains required.
9. `python -m ruff check cancerjev apps tests` and `python -m pytest` pass.
10. No Deep/Phase 4/LLM code is added.

---

## 9. Risks and guardrails

- **Selection bias is unchanged** — states still come from the provider top-mutated ranking; the
  projection keeps `selection_bias` and the state keeps its limitation text.
- **Single-cohort degeneracy is expected** — the redesign removes cross-project questions rather
  than manufacturing cross-project signal.
- **Thresholds are provisional** — `ADMISSION_*` constants are not calibrated; step 3 calibrates
  them against the deterministic baseline. Do not present them as validated.
- **Jev is not truth** — a high Noul is not significance, causality or clinical evidence.
- **No measurement leakage** — the projection copies measured values; no projection-side
  arithmetic becomes a scientific field.

## 10. Open questions to resolve before coding

1. Keep `dominant_limitation` in v3? (Recommendation: yes — closed, cheap, names the uncertainty.)
2. Include any projection-side ratio (e.g. affected share, missing share)? (Recommendation: no —
   omit ratios not already present in the state.)
3. Should baseline v2 order on `affected_cases` at all? (Recommendation: keep as a deterministic
   ordering/display field with the existing no-matched-denominator limitation, never a rate.)

## 11. Out of scope (do not implement here)

Deep Jev fan-out, registered follow-up execution, `EvidenceState` revisions, autonomous candidate
iteration, LLM hypothesis generation, LUSC, CNV/survival/scRNA, literature/DepMap/GTEx, new
endpoints, agent/planner/graph/queue frameworks.
