# Review corrections and bounded adaptive acquisition

Baseline: `c58e38b80e118ab1cbbabaf3e26fa0d4368eb908`.
Existing user edits: live page-cap wiring and OpenRouter response-byte allowance; preserve both.

The full-codebase review was independently reproduced offline. This supersedes the
fixed-budget assumptions for this repair; it does not activate future scientific methods.

Implementation units:

1. Correct gene-specific detail, cross-page identity checks, and terminal failure handling.
2. Bind CNV shard acquisition/merge to the full cohort, spec, release and owner; preserve repeatable immutable artifacts.
3. Scope GDC caches by fresh release identity and ownership, and Jev caches by ownership/mode.
4. Separate per-request Jev context bounds from optional run cost quotas and correct accounting.
5. Centralize adaptive GDC request/page allowances under a fixed sub-GiB run download ceiling. Record policy and every expansion; never reduce scientific scope to fit a budget.
6. Return CLI failure status, add regression tests, update current behavior documentation.

Validation: targeted fixture/loopback regression checks, Ruff, strict project mypy,
and the full default offline pytest suite. No live scientific acquisitions or commits required.

Upstream references inspected, with remote HEAD verified during this session:
`gdc-docs@157cef9dac084ce30720f0ad507cd54017263be7`,
`gdcdatamodel2@9c6a046b96c130ea131d2ce2c9160381edd2fcc1`,
`gdc-workflow-overview@2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e`.
Existing untracked `.upstream/gdc/` clones and `.upstream/SOURCES.lock.json` are retained.
