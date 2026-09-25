# Changelog

Records durable repository milestones and boundaries. Entries are descriptive records; the
factual state of the repository lives in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)
and the machine-checked [docs/REPOSITORY_FACTS.md](docs/REPOSITORY_FACTS.md).

## 2026-09-25 — Stage 8 baseline and Stage 9 boundary

- Stage 8 candidate finalization is complete: deterministic `FinalCandidateResult`,
  authoritative dossier with derived Markdown, read-only `no-jev-baseline-v1` comparison, and
  automatic multi-candidate loop completion (`RUN_COMPLETED` on queue exhaustion) with no human
  review. Stages 0-8 are IMPLEMENTED; Stages 4-7 live acceptance is VERIFIED (2026-09-25).
- **Recovery point established:** annotated tag `stage8-pre-stage9-cutover-9fb9192` at commit
  `9fb91922eb32f13d738e5c0fa81d5659e26cf5a6` records the verified Stage 8 baseline. OntoJev
  uses hard fail-closed schema cutovers with no migrations; before any future incompatible
  Stage 9 schema cutover, recover by checking out that tag into a fresh data directory and
  retaining historical databases and artifacts. The tag is local only; do not push or release
  without explicit authorization.
- **Stage 9 boundary:** Stage 9 is the provisional reorientation toward the autonomous
  multi-modal target-discovery loop (PROVISIONAL TARGET ARCHITECTURE, SUBJECT TO THE
  SOURCE-GROUNDED STAGE 9 DESIGN REVIEWS). No Stage 9 contract is frozen in this baseline;
  scientific runtime behavior is unchanged by this documentation baseline.
- Governance note: this repository has no LICENSE file. Whether and under which license the
  repository is published remains an unresolved repository-governance decision; no license was
  invented as part of this baseline.
