# Jev review — declared evaluation rehearsal (synthetic labels, no value claim)

Status: **design rehearsal only.** The labels in this rehearsal are synthetic
(`REHEARSAL synthetic label; not human-reviewed evidence`) and exist solely to
exercise the preregistered harness end-to-end. This document never claims
incremental value, superiority or readiness; the Arm-Jev veto stays fail-closed
and no triage is implemented.

## Frozen inputs

| Field | Value |
|---|---|
| Protocol id | `JEV-REVIEW-REHEARSAL-2026-09-27` |
| Declared at | 2026-09-27T00:00:00Z |
| Blinded to arms | true |
| Seed / replicates | 20260927 / 200 |
| Split | `HOLDOUT` (2 items, 1 group) |
| Policies (declared) | `wide-policy-v2`, `deep-policy-v2`, `hypothesis-policy-v2`, `pre-wide-policy-v2` |
| Arm A | deterministic baseline without Jev judgments (measurement-only decisions) |
| Arm B | pipeline with Wide/Deep Jev at the frozen policies |

Artifacts (operator directory, regenerate with `research/prospective.py`):
`data/calibration/jev-review-rehearsal.protocol.json`,
`data/calibration/jev-review-rehearsal.arms.json`,
`data/calibration/jev-review-rehearsal.report.json`.

Protocol hash `a10e72e5…`, arm-output hash `04dbe9f0…` — both bound in the report.

## Rehearsal report (as generated)

| Metric | Arm A | Arm B |
|---|---|---|
| `investigate_precision` | 0.5 | 0.5 |
| `precision_at_3` (K = 3) | 1/3 | 1/3 |
| `stop_rate` | 0.0 | 0.0 |
| `abstention_rate` | 0.0 | 0.0 |
| `coverage` | 1.0 | 1.0 |

Grouped paired bootstrap (B − A, `precision_at_3_difference_vs_A`): 95% interval
**[0.0, 0.0]** over 200 replicates. `release_decision = HUMAN_REVIEW_REQUIRED`
with the standard claim: *"No incremental-value, scientific-readiness or
superiority claim is made automatically."*

## Decision (unchanged)

The rehearsal verifies the harness contract (frozen policies, blinded label
gating, paired replicates, mandatory failure/abstention analysis, no automatic
claim). It does **not** measure the value of Jev judgments: the labels are
synthetic and the split carries no signal. Arm-Jev triage therefore remains
unimplemented and the `PENDING_SEMANTIC_REVIEW` veto stays fail-closed. Re-opening
that decision requires the preregistered evaluation recorded with real blinded
held-out labels (`reviewer_count >= 2`, `adjudicated: true`) and a decision change
that is defensible on those labels — never a silent threshold change.
