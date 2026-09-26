# Review corrections and bounded adaptive acquisition

Baseline: `c58e38b80e118ab1cbbabaf3e26fa0d4368eb908`.
Existing user edits: live page-cap wiring and OpenRouter response-byte allowance; preserve both.

The full-codebase review was independently reproduced offline. This supersedes the
fixed-budget assumptions for this repair; it does not activate future scientific methods.

Status after the parallel-agent merge `215d54a`:

- Unit 2 is landed to a substantial degree: CNV shard evidence binds cohort case ids,
  case-shard size, spec hash, release and owner, and merge stays fail-closed on any
  missing or mismatched shard.
- Unit 4 is landed: `cancerjev/jev/context.py` declares `jev-context-bytes-v1`, a
  conservative per-request byte guard separate from run cost accounting; the retired
  operator attempt/input-token knobs are inert.
- Unit 5 is landed: `cancerjev/gdc/budget.py` declares `gdc-adaptive-v1`; CLI runs record
  the policy payload in their scope, and the declared initial/ceiling/byte values are
  indexed in `docs/REPOSITORY_FACTS.md`.
- Units 1, 3 and 6 remain to be verified against `215d54a`; the post-merge test
  reconciliation and documentation sync are tracked in `docs/IMPLEMENTATION_PLAN.md`.

Implementation units:

1. Correct gene-specific detail, cross-page identity checks, and terminal failure handling. (OPEN: verify.)
2. Bind CNV shard acquisition/merge to the full cohort, spec, release and owner; preserve repeatable immutable artifacts. (LANDED as noted above.)
3. Scope GDC caches by fresh release identity and ownership, and Jev caches by ownership/mode. (OPEN: verify.)
4. Separate per-request Jev context bounds from optional run cost quotas and correct accounting. (LANDED as noted above.)
5. Centralize adaptive GDC request/page allowances under a fixed sub-GiB run download ceiling. Record policy and every expansion; never reduce scientific scope to fit a budget. (LANDED as noted above.)
6. Return CLI failure status, add regression tests, update current behavior documentation. (OPEN: verify; documentation sync tracked in `docs/IMPLEMENTATION_PLAN.md`.)

Validation: targeted fixture/loopback regression checks, Ruff, strict project mypy,
and the full default offline pytest suite. No live scientific acquisitions or commits required.

Upstream references inspected, with remote HEAD verified during this session:
`gdc-docs@157cef9dac084ce30720f0ad507cd54017263be7`,
`gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1`,
`gdc-workflow-overview@2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e`.
Existing untracked `.upstream/gdc/` clones and `.upstream/SOURCES.lock.json` are retained.
