# TypeSafe / Jev capability decision record

Version: **typesafe-decisions-v1** (2026-09-25). Reference of record for live
capabilities: the official TypeSafe documentation refreshed into
`.upstream/typesafe/` (snapshot dated 2026-09-25); the authoring cookbook is
`https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery`. The snapshot
must be refreshed with a new SHA before any posture change below is reversed.

## Posture per capability

| Capability | Decision | Why deterministic code cannot answer / conditions |
|---|---|---|
| Noul / Choice / Score primitives | KEEP | Existing owned validation and fail-closed typed failures; each question uses the smallest primitive that answers it. |
| Wide question set (`wide-v3`) | KEEP | Validated live on 2026-09-25 against the pinned model over one real replayed state (usage recorded, no cache reuse). |
| Deep question set (`deep-v1`) and hypothesis critique | KEEP | Bounded revision-scoped judgments only; facts and maturity stay Python-derived. |
| Multiple questions per target | KEEP | Existing `system_one` question map. |
| Multiple-target batching / speculative fan-out | DEFER | Requires re-validated SDK behavior, identity association, applicability and partial-failure semantics before use. |
| Semantic reranking | KEEP existing Python-owned ranking; DEFER new schemes | Semantic outputs remain policy inputs; they cannot alter evidence facts. |
| Confidence routing | DEFER | Needs held-out calibration and declared Python thresholds; confidence is not genomic significance. |
| Semantic feature discovery | DEFER to an offline study | The cookbook is a labelled supervised experiment, not runtime scientific validation. |
| Uncertainty / action-value judgment | KEEP bounded existing roles | Extend only where a registered action and validated evidence make the question meaningful. |
| Cascades | DEFER | Revisit only for measured cost/quality benefit with fixed stop/failure semantics. |
| Model-controlled actions, measurements or maturity | REJECT | Violates deterministic scientific and control ownership. |
| **Arm Jev** | **DEFER** | No named consumer needs a preserve-or-drop triage: deterministic dispositions already decide admission (Python), and `JEV_REVIEW` entries are carried as typed pending-semantic-review through the P10 union without being admitted or silently dropped. Re-evaluate when an autonomous-program consumer requires triage of review entries; adoption would add `arm-v1` (one Noul question plus at most one Choice dominant-pattern answer) with per-lane bounded projections, fail-closed to "unpreserved and recorded", and no effect on facts, maturity or admission. |

## Consequences in code

- No `arm-v1` question set exists; the Arm decision is a typed constant
  (`cancerjev/jev/posture.py`) rendered into Repository Facts, and this record is
  checked against it by `tests/jev/test_arm_posture.py`.
- `JEV_REVIEW` preservation semantics live in the P10 union (`PENDING_SEMANTIC_REVIEW`
  warning plus typed `nominations`), never in Jev.
- Admission enforcement: while Arm Jev is deferred, the Wide ranking policy excludes
  `JEV_REVIEW`-nominated (and `PENDING_SEMANTIC_REVIEW`-warned) states
  unconditionally, so even maximally favorable answers can never promote them
  (`tests/jev/test_ranking.py`).
- Live revalidation evidence: `tests/live/test_live_jev.py` (marker `live_jev`)
  evaluates exactly one typed state with the pinned model; the emit callback must be
  the real event-writing callback so projection/question registrations persist.
