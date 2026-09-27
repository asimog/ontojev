# Calibration and evaluation design (preregistered, Gate 6)

Status at HEAD: **records exist for the mutation family only**. `python -m cancerjev calibrate` computes the declared mutation metrics on the frozen DR46 reconciliation panel (17-gene complete occurrence captures) with a deterministic gene bootstrap (seed `20260927`, 200 replicates) and writes strict records to `data/calibration/`; the four mutation thresholds report `CALIBRATED` at the current policy version, the other 17 thresholds stay `UNCALIBRATED` until their declared corpus/metric is computed (the Wide admission family additionally requires blinded held-out labels). `EvidenceLevel.STATISTICALLY_SUPPORTED` stays blocked until records exist for a selected claim family. Status semantics are machine-checked:

- `UNCALIBRATED` — no record for this threshold exists.
- `CALIBRATED` — a schema-valid record for the threshold's **current** policy
  version exists (`load_calibration_record`, `calibration_status`).
- `STALE_POLICY_VERSION` — only an older policy version is recorded; never counts.

A calibration record is one JSON object:

```json
{
  "schema_version": 1,
  "kind": "CALIBRATION_RECORD",
  "threshold_id": "wide.admission_min_warrants",
  "policy_version": "wide-policy-v2",
  "declared_at": "2026-09-27T00:00:00Z",
  "corpus_hash": "<sha256 of the frozen corpus>",
  "held_out": true,
  "metric": "precision_at_3_difference_vs_A",
  "replicates": 200,
  "values": {"0.5": 0.10, "0.6": 0.04, "0.7": -0.02}
}
```

Records are operator artifacts (`data/calibration/`); they are never written by
the runtime, and the registry refuses unknown thresholds, extra fields, fewer than
100 replicates and non-finite grid values.

## 1. Preregistered sensitivity design per threshold

Every design freezes the corpus (hash recorded), the metric, the sensitivity grid
and the decision rule before the first evaluation. Grid values are the *only*
values that may be reported as evaluated; any other value is exploratory and must
be labelled as such. With no held-out labels recorded yet, label-dependent
thresholds can only be evaluated against frozen replay corpora and must not be
presented as calibrated.

| threshold | metric | corpus (frozen, hash recorded) | sensitivity grid |
|---|---|---|---|
| `mutation.max_survivors` | survivor-set stability and downstream union membership | reconciliation corpus DR46 LUAD + complete occurrence scan | 5 / 10 / 20 / 50 |
| `mutation.review_occurrence_ratio` | review volume and overlap with retained survivors | same | 2 / 4 / 6 / 8 |
| `mutation.review_hotspot_min_records` | review volume and hotspot stability | position-level occurrences | 10 / 20 / 40 |
| `mutation.review_hotspot_top_position_share` | review volume and hotspot stability | position-level occurrences | 0.1 / 0.25 / 0.5 |
| `expression.minimum_tail_n` | tail eligibility and nomination count | expression corpus DR46 LUAD | 10 / 20 / 40 |
| `expression.iqr_multiplier` | fence-exceedance rate and nomination count | same | 1.0 / 1.5 / 2.0 / 3.0 |
| `expression.review_asymmetry_ratio` | review volume and veto recall cost | same | 2 / 5 / 10 |
| `expression.null_excess_sd` | nominations vs within-null drops | same | 2 / 3 / 4 |
| `cnv.retain_min_amplification_cases` | recurrent-set stability | complete CNV case-shard scan | 3 / 5 / 8 |
| `cnv.retain_min_homozygous_deletion_cases` | recurrent-set stability | same | 3 / 5 / 8 |
| `wide.admission_min_warrants` | admission precision and recall against blinded labels | preregistered blinded label set (required; none recorded) | 0.5 / 0.6 / 0.7 |
| `wide.admission_min_uncertainty` | same | same | 0.4 / 0.5 / 0.6 |
| `wide.admission_min_quality` | same | same | 0.3 / 0.4 / 0.5 |
| `wide.admission_max_confound` | same | same | 0.3 / 0.5 / 0.7 |
| `pre_wide.stratum_shares` | stratum representation under the hard ceiling | frozen DR46 union | 0.2 / 0.3 / 0.4 |
| `deep.revision_reliable_min` | continuation precision and stop correctness | frozen deep-slice replay | 0.4 / 0.5 / 0.6 |
| `deep.evidence_sufficient_min` | same | same | 0.4 / 0.5 / 0.6 |
| `deep.next_step_warranted_min` | same | same | 0.5 / 0.6 / 0.7 |
| `deep.stopping_more_honest_min` | same | same | 0.4 / 0.5 / 0.6 |
| `hypothesis.testable_min` | keep/abstain agreement with frozen critique | hypothesis critique replay | 0.5 / 0.6 / 0.7 |
| `hypothesis.exceeds_recorded_evidence_max` | same | same | 0.4 / 0.5 / 0.6 |

Calibration records must state the metric actually computed; a threshold whose
metric cannot be computed on the frozen corpus stays `UNCALIBRATED` and is reported
as such.

## 2. JEV_REVIEW volume and the veto decision (P1-10)

Measured on the Phase 7 DR46 corpus (expression lane; mutation lane; CNV merge not
reached in that run):

- Expression: 19,843 measured genes, 14,998 `RETAIN` under the pre-Phase-8 policy,
  **1,942 `JEV_REVIEW`** (all two-sided asymmetry triggers, ratio min 5.0, median
  8.0; no one-sided or mutation-ratio triggers).
- The review set is 9.8% of measured genes and 11.5% of non-dropped nominations
  under the old policy; under the Phase 8 policy (4,969 `RETAIN`) the review set is
  28.1% of all nominations, because the asymmetry check runs first.
- Mutation: 10 survivors, 0 `JEV_REVIEW`; one gene (TP53, `ENSG00000141510`) is
  both a mutation survivor and an expression asymmetry review state.
- The veto (`ranking.py:175-180`) excludes every `PENDING_SEMANTIC_REVIEW` state
  unconditionally: with Arm Jev deferred there is no promotion path, so all 1,942
  flagged genes are unpromotable.

**Decision:** the recall cost is material and now measured, but no Arm-Jev triage
is implemented in this phase. A narrow semantic-only triage (modality-ambiguity
adjudication, no statistics, no evidence creation) may only be proposed after the
preregistered Jev evaluation below has held-out labels and shows a decision change
that is defensible. Until then the veto stays fail-closed.

## 3. Preregistered Jev-vs-no-Jev evaluation

Design (frozen once labels exist; `research/prospective.py` is the harness):

- **Policies are frozen per protocol**: `wide-policy-v2`, `deep-policy-v2`,
  `hypothesis-policy-v2`, `pre-wide-policy-v2` and the model identifier used by the
  Jev arms. A policy change requires a new protocol and a new `declared_at`.
- **Arms**: A = deterministic baseline without Jev judgments (measurement-only
  decisions); B = the current pipeline with Wide/Deep Jev at the frozen policies.
  Optional C = Jev with a declared prompt/model variant. Arm predictions carry
  disposition, score, unsupported-assertion and wrong-population flags, attempts,
  tokens, latency, human minutes and spend.
- **Labels**: blinded, independently reviewed (`reviewer_count >= 2`,
  `adjudicated: true`), grouped so no gene or group crosses TRAIN/DEVELOPMENT/
  HOLDOUT. Where no held-out labels exist, the evaluation runs on the frozen
  replay corpus and is reported as a design rehearsal, never as incremental-value
  evidence.
- **Metrics** (paired grouped bootstrap, declared seed and replicate count):
  `coverage`, `abstention_rate`, `stop_rate`, `investigate_precision`,
  `precision_at_3` (declared K = 3), `nDCG@3`, `unsupported_assertion_rate`,
  `wrong_population_rate`, and per-arm resources.
- **Failure and abstention analysis is mandatory**: an arm is never dropped from an
  interval for abstaining; every arm is measured on the identical paired resample
  set; a `None` metric in a report is a bug, not a result.
- **Decision rule**: no automatic claim. The report always returns
  `HUMAN_REVIEW_REQUIRED`; a positive or negative incremental-value statement
  requires the interval, the label hash and the frozen policy set in one record.

The harness is testable today with declared fixtures (see
`tests/unit/test_prospective.py::test_jev_vs_no_jev_design_is_evaluable_under_the_preregistered_contract`).
A synthetic design rehearsal is recorded in `docs/JEV_REVIEW_REHEARSAL.md`
(report in `data/calibration/jev-review-rehearsal.report.json`): it exercises the
frozen protocols end-to-end, returns `HUMAN_REVIEW_REQUIRED` with a [0.0, 0.0]
rehearsal interval, and is never incremental-value evidence.
