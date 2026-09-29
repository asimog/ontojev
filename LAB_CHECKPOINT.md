# Autonomous laboratory checkpoint

- Baseline HEAD: `c8e03b2a0c2e3ba8c59f13c44ab062806e255c99`.
- Objective: evolve the existing Program/Campaign system into the autonomous lung-cancer laboratory described in the supplied specification.
- Completed implementation: typed OntoCodex protocol, isolated Codex/OpenRouter adapter, immutable portfolio revisions in existing storage, ownership filtering, bounded control block, failure/no-progress handling.
- Current milestone: connect real preflighted ephemeral acquisition and the CLI supervisor.
- Decisions: models cannot write measurements; interpretations cite Python-registered evidence. No historical `data/` was inspected. Provider/model configuration reuses the existing configured model and supports an OntoCodex override. The installed harness is `codex-cli 0.157.1`.
- Verification: 20 focused tests passed; repository ruff and strict mypy passed (106 modules); full offline suite 888 passed, 4 deselected; repository facts current. Real Codex 0.157.1/OpenRouter/configured DeepSeek returned a validated CREATE_QUESTION. Initial malformed live outputs were safely rejected; explicit action rules and schema in the prompt resolved the failures.
- Upstream references fetched: gdc-docs `157cef9dac084ce30720f0ad507cd54017263be7`; gdcdatamodel2 `9c6a046b96c130ea131d2ce2c9160381edd2fcc1`; gdc-workflow-overview `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e`.
- Blockers: none for offline implementation. Real Jev in the new lab loop is not yet verified.
- Next: supervised ten-minute runs; reuse strict CNV shard execution, persist reproducibility information before cleanup, wire Observatory, then expand scientific methods and Jev/dossier integration.
