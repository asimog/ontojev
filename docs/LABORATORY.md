# Autonomous laboratory

`python -m cancerjev lab --root .lab --max-runs 3` executes bounded OntoCodex-directed blocks. `worker --live` repeatedly calls the same supervisor using `CANCERJEV_DATA_DIR`. The lab CLI defaults to `.lab` independently of the worker/API default `./data`; use one explicit root for a shared Observatory.

## Current behavior

The director sees a compact persisted portfolio and preflighted offers, returns a typed decision, and Python validates scope, evidence and budget before execution. Questions currently support TCGA-LUAD and TCGA-LUSC. One block performs one decision and, where selected, one scientific capability. Only ACTIVE questions enter the two-question offer window; answered, exhausted, deferred and capability-gap questions cannot hide active work. A PRIORITIZE decision explicitly reactivates a question before acquisition.

Seven capabilities are registered: mutation discovery, expression discovery, CNV case-shard acquisition, complete CNV merge, canonical StatisticalState composition, Wide Jev/admission, and Candidate investigation through Stage 8/dossier. See [Architecture](ARCHITECTURE.md) for code owners and the [code audit](CODE_AUDIT.md) for verification evidence. Hypothesis generation inside the existing Candidate arc is conditional on its configured provider; it is not an independent director-commissioned capability.

Portfolio revisions retain questions, evidence references and attributed interpretations. They are operational agenda records, not alternative measured scientific states. Jev research-control relevance/Choice experiments are optional shadows; they do not supply biological evidence. The scientific Wide/Deep path uses the existing Jev contracts.

## Runtime and providers

Use the Codex CLI version pinned in the Dockerfile for reproduction. Set server-side `OPENROUTER_API_KEY` and `TYPESAFE_API_KEY`. `CANCERJEV_LLM_MODEL` configures the model; `ONTOCODEX_MODEL` overrides the director model. `ONTOCODEX_EXECUTABLE` and `ONTOCODEX_BASE_URL` configure the harness. No OpenAI key is required by this path. `ONTOCODEX_JEV_EXPERIMENT` defaults to `off`; `relevance` and `choice` enable control shadows.

The director runs in a fresh CLI process with isolated home, restricted configuration and a typed output schema. Python validates returned decisions and persists harness/model/configuration identity and input projection. This restriction is not a verified claim that every CLI auxiliary tool is absent; acceptance should inspect the actual tool surface of the pinned CLI.

Normal runs allow at most 600 seconds; `--seconds` can reduce the allowance for declared tests. The parent terminates overdue research children, reserving finalization time. Cleanup and parent finalization are not independently deadline-bounded. Three consecutive no-progress blocks can put the portfolio in `NO_PROGRESS`; `STOPPED` and `NO_PROGRESS` halt further dispatch. No general resume/reset CLI is documented here because one is not implemented.

## Evidence and continuation

Derived artifacts and reacquisition provenance are retained; raw GDC bodies under `shards/<run>/` are disposable. Normal success verifies derived outputs before portfolio publication and cleanup. Failure paths also delete raw workspaces and restart retries cleanup. Publication/recovery still has crash windows; raw deletion alone is not proof that a scientifically complete operation was committed.

CNV coverage counts disjoint positive-query coverage, not a callable denominator or evidence of neutral CNV. Its merge requires every shard of one fixed partition. Mutation/expression currently attempt a whole canonical lane per run; Candidate investigation attempts the complete arc. Oversized work therefore needs the resumable units in M2. Mixed historical CNV partitions have no automatic conversion.

## Observatory and limits

The read-only `/lab` page shows questions, interpretations and run blocks. `/api/lab` and `/api/runs/{id}/lab` expose persisted decisions, acquisitions, scientific-stage receipts and portfolio state. They do not yet provide the complete question-to-Campaign-to-dossier navigation and scientific comparison planned in M5.

Current defects include Wide receipt suppression of failed-evaluation retries and unreconciled publication gaps. `CAPABILITY_GAP` records missing functionality but does not launch engineering. The [audit](CODE_AUDIT.md) is the current findings record; the [implementation plan](IMPLEMENTATION_PLAN.md) is the sole active roadmap.
