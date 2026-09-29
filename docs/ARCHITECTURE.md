# OntoJev architecture

Current implementation, inspected 2026-09-29 at `da1120449c5ade6c578571047b66c442206fc30c` plus the local changes identified in the [audit](CODE_AUDIT.md). This document describes current ownership; unfinished architecture is in the [active plan](IMPLEMENTATION_PLAN.md). Scientific requirements remain in [SCIENTIFIC_INVARIANTS.md](SCIENTIFIC_INVARIANTS.md).

## Authority

Humans bound the domain and access/resource constraints. OntoCodex proposes questions, priorities, eligible operations and attributed interpretations. Python owns measurements, eligibility, budget checks, persistence and execution. Jev returns bounded typed judgments, never measurements. Control shadows are experimental and cannot enter biological evidence.

## Runtime and scientific spine

```text
lab / worker --live
  → run_lab: exclusive writer, child supervision, recovery
  → run_block: persisted context → Codex decision → Python validation
  → ScientificLabCapabilities / CampaignLabStages
      mutation discovery ─┐
      expression discovery ├→ composition → StatisticalState
      CNV shards → merge ─┘                  ↓
                                  Wide Jev → Candidate
                                              ↓
                                EvidenceState / Deep / follow-ups
                                              ↓
                                       Stage 8 / dossier
  → verified receipt / portfolio revision / raw cleanup
  → next bounded run
```

| Responsibility | Current owner |
|---|---|
| Typed questions, decisions, offers, portfolio and stage receipts | `domain/laboratory.py` |
| Portfolio validation and compact model projection | `research/laboratory.py` |
| Codex CLI/OpenRouter director | `llm/ontocodex.py` |
| One decision/action block and process supervisor | `research/lab_runtime.py`, `lab_worker.py` |
| Ephemeral GDC responses, preflight and CNV acquisition | `research/lab_acquisition.py` |
| Mutation/expression adapters and stage offers | `research/lab_capabilities.py`, `lab_stages.py` |
| Canonical discovery and composition | `research/discovery.py`, `expression_discovery.py`, `cnv_discovery.py`, `cutover.py` |
| Scientific judgment/investigation/finalization | `research/wide.py`, `deep.py`, `investigation.py`, `finalize.py`, `dossier.py` |
| Canonical storage, hash verification and cross-run readers | `storage/`, especially `repositories.py` and `readers.py` |
| Read-only Observatory | `apps/api`, `apps/web` |

Python paths are under `cancerjev/`. The full Campaign executor remains `research/systematic.py`; the lab reuses its constituent owners rather than launching it wholesale for every run. Method details and identities belong in code and [generated facts](REPOSITORY_FACTS.md).

## Durable identities

A Campaign's scientific scope is cohort + pinned release + versioned method/spec. The lab currently carries these through offers, lane artifacts and stage receipts. It does not yet bind its agenda into one durable lifecycle with legacy Program records: `research-portfolio` and `program-state` remain distinct operational artifacts. The explicit legacy `program` command can still dispatch work. M3 resolves that authority/lifecycle gap.

LabState holds questions, interpretations and evidence references. Canonical StatisticalState holds computed science; Candidate records bind admitted states; EvidenceState revisions retain investigation evidence. Interpretations remain attributed judgments and cannot overwrite measurements. Researcher and validation ownership remain isolated from autonomous scientific consumption.

Stage receipts reference immutable input/output hashes. Execution checks terminal source runs. Wide creates local operational state bindings while preserving scientific hashes; cross-run Candidate investigation requires a binding to the original Wide receipt/state. A registered publication-ready checkpoint binds verified durable artifacts to the next portfolio revision. Recovery adopts it before generic interruption handling, preserving admitted Candidates without repeating science. This closes the final portfolio-publication gap, but does not make earlier within-stage writes atomic; that reconciliation remains M1.

## Budgets, storage and cleanup

The lab uses existing SQLite/event/artifact storage and one writer lock. Research children have a supervised deadline, normally 600 seconds with a finalization reserve. Estimates gate operations; they do not prove completion time. Parent cleanup/finalization can exceed the reserve on slow storage and requires operational hardening.

GDC responses use `shards/<run>/`; derived artifacts, source requests/hashes and scientific provenance are durable. Raw eviction is recorded and failed/interrupted workspaces are cleaned. Successful publication and failure cleanup currently span separate writes. Preserve explicit incomplete outcomes and implement recovery before claiming transactional continuation.

CNV uses fixed case partitions once chosen. Mutation/expression are whole-lane bounded attempts. Candidate investigation is still a whole-arc attempt. Finer checkpoints are M2; budget exhaustion must never shrink a population labelled complete.

## Remaining architecture

The [audit](CODE_AUDIT.md) records the repaired question-window starvation and versioned Wide retry handling, outstanding publication crash windows, sparse director summaries and deployment liveness gaps. The [plan](IMPLEMENTATION_PLAN.md) adds bounded continuation, one Campaign lifecycle, isolated capability engineering and live/evaluation gates. No generic workflow engine, second scientific-state model or microservice split is required.

Existing descriptive methods and typed maturity do not imply calibrated inference, replication or therapeutic validation. New sources/methods must meet the data and scientific contracts before becoming capabilities.
