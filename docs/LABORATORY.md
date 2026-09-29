# Autonomous laboratory

## Current implementation

`python -m cancerjev lab` runs a bounded OntoCodex-directed block and persists a
Program research portfolio. `--max-runs` sets an operational allowance; the human
does not select genes, cases, experiments or priorities. Each block uses the
existing research-run table, events, immutable artifact store, GDC transport,
strict parsers and canonical CNV shard executor.

```powershell
.venv\Scripts\python.exe -m cancerjev lab --max-runs 3
```

The default state directory is `.lab/`, separate from historical `data/`.
Mount that directory on durable storage for deployment. Raw inputs live under
`shards/<run UUID>/` and are deleted after verified evidence and portfolio
publication. Failed-run inputs are also cleaned; failures remain visible and
cleanup is retried on restart. There is one research writer.

The normal hard run ceiling is ten minutes. The parent process terminates an
overdue worker and its descendants, reserving time for cleanup and finalization.
The worker refuses operations whose estimates exceed remaining time. A smaller
`--seconds` ceiling is available for declared tests. Resource constants belong
to `domain/laboratory.py` and `research/lab_acquisition.py`. The current shard
allowance was raised from 16 to 32 MiB after live preflight estimated 17 MB for
one case; larger alternatives remained refused. A budget never changes a
partial population into a complete one.

## Providers

Install the upstream Codex CLI, for example `npm install -g @openai/codex`.
Set `OPENROUTER_API_KEY` and `TYPESAFE_API_KEY` server-side, or in `.env.local`.
The director uses the existing configured LLM model unless `ONTOCODEX_MODEL`
overrides it. `ONTOCODEX_EXECUTABLE` and `ONTOCODEX_BASE_URL` support deployment
configuration. No OpenAI API key is required.

Each invocation uses a fresh Codex process, isolated home, disabled tools and
plugins, compact persisted state, and a JSON output schema. Python independently
validates every returned decision. Model and harness identity, configuration
hash, input projection, decision, and consequential priorities are persisted.
Provider failures leave recoverable operational state; repeated failures stop.

The integration follows [Codex noninteractive execution](https://developers.openai.com/codex/noninteractive)
and [OpenRouter's Codex configuration](https://openrouter.ai/blog/tutorials/codex-cli-openrouter/).
The output schema is also included in the prompt because live provider responses
did not consistently obey the schema parameter alone.

Jev's existing adapter and service support versioned acquisition-relevance Noul
and comparative Choice experiments. These run in opt-in shadow mode, retain
`RESEARCH_CONTROL` provenance, and cannot enter biological evidence. See
[Jev decision boundaries](JEV_DECISIONS.md) for the evaluation contract.

## Observatory

Point the API at the same state directory:

```powershell
$env:CANCERJEV_DATA_DIR = 'C:\dev\ontojev\.lab'
.venv\Scripts\python.exe -m uvicorn apps.api.main:create_app --factory
```

The existing frontend's `/lab` page shows the portfolio and run cards. Opening a
run exposes its persisted decision, Jev control judgment, acquisition provenance,
portfolio revision and event stream. `/api/lab` and `/api/runs/{id}/lab` are
read-only projections; the frontend cannot direct science.

## Scientific scope and remaining work

The bounded lab executor currently supports descriptive positive CNV occurrence
shards in the configured lung-cancer projects. It offers alternative case-window
sizes, avoids previously acquired cases within the same release, and never calls
missing CNV data neutral. API response sizes are estimates from metadata and one
row, not file-size measurements. Every complete shard remains a shard, not a
complete-cohort result. Director interpretations are separately labelled judgments
and cite registered deterministic evidence; they do not overwrite StatisticalState.

Every block persists typed cumulative query coverage, grouped by project, release,
method specification and cohort manifest. It reads retained derived shards,
rejects overlapping cases, and labels incomplete coverage PARTIAL. Coverage is
not a callable CNV denominator. Interpretations cannot cite another cohort.
Their uncertainty and next action update the question while the original evidence
remains immutable. Reprioritizing or rewording alone does not reset the three-block
no-progress stop; fresh acquisitions and evidence-linked interpretations do.

The existing mutation/expression, Wide/Deep Jev, Candidate, Stage 8 and dossier
paths remain in the repository. They are **not yet integrated into bounded lab
runs**. Adaptive throughput estimation, scientific Jev and StatisticalState
synthesis within this loop, literature/hypothesis commissioning, capability
engineering worktrees, cumulative full-cohort analysis and the final laboratory
dossier remain implementation work. `CAPABILITY_GAP` preserves unsupported
questions; it does not pretend those capabilities exist.

This is an implemented foundation, not the completed laboratory transformation.
