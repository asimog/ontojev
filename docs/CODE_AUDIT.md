# OntoJev current code audit

Audited 2026-09-29 against HEAD `da1120449c5ade6c578571047b66c442206fc30c` and the working tree. This replaces the September 26–27 report as the current audit; the original exhaustive ledger remains in Git history. This pass focuses on laboratory convergence, continuation, failure handling, deployment and tests. It is not a fresh line-by-line review of every repository file.

## Verdict

The laboratory now calls existing Campaign functions through seven capabilities. Replay reaches canonical StatisticalState, Wide admission, Candidate investigation, EvidenceState, Stage 8 and a dossier. The old CNV-only description is obsolete.

The full autonomous architecture remains unfinished. Whole-lane and whole-investigation attempts do not guarantee progress within ten-minute runs. Offer selection and failure recovery also have concrete defects. Offline success establishes neither realistic cohort throughput nor scientific calibration. The [implementation plan](IMPLEMENTATION_PLAN.md) orders the remaining work.

## Baseline and scope

Pre-existing uncommitted changes were inspected and preserved: `cancerjev/research/lab_worker.py` repairs recovery-lock ordering, child admission and post-publication failure reporting; `cancerjev/science/methods.py` adds an expression-only constructor for an explicit 1–4-gene panel with unavailable mutation measurements. New local tests are `tests/integration/test_lab_supervisor.py` and `tests/science/test_expression_state.py`. These changes were uncommitted at the audit baseline; see the implementation follow-up below. The expression constructor is not a registered lab capability.

Directly inspected: lab domain, acquisition, capability adapters, stage execution, runtime, portfolio projections, supervisor, Wide evaluation, CLI dispatch, director configuration, Docker/deployment entrypoint, bridge integration tests and local code diffs. Canonical readers, investigation/finalization and Observatory integration were inspected during the preceding bridge implementation; this pass does not claim a fresh audit of every scientific method or UI component. Docs were checked for drift, not treated as proof. `.upstream` was excluded. No deployed volume or external provider was inspected.

## Implementation follow-up (2026-09-29)

After the audit baseline, the existing supervisor and expression-only changes were reviewed for integration, and A01 was repaired across all three offer producers. Only ACTIVE questions enter the bounded offer window; deferred/capability-gap questions require explicit reactivation. The regression failed on the original code and passes after repair. Follow-up verification: 915 offline tests passed (4 deselected), Ruff, strict mypy (112 modules), repository facts and documentation links passed. A02 now has explicit v2 deferred/completed outcomes and retry regression coverage; historical v1 partial admissions still require migration. A03 now has verified publication-ready checkpoint recovery, including preservation of already-admitted Candidates before generic interruption handling; earlier within-stage writes remain unreconciled. A04–A07 remain open; supervisor startup exclusion does not close scientific publication reconciliation.

Publication-recovery follow-up: 922 offline tests passed (4 deselected), including fault injection before the portfolio write, after its file write, after commit, and corrupt-output refusal. Ruff, strict mypy (112 modules), repository facts and documentation links pass. No live provider or deployment validation was performed.

## Findings at the audit baseline

P1 blocks dependable autonomy; P2 describes integration/control limitations. No newly demonstrated P0 scientific corruption is asserted. Findings below are static control-flow findings; dedicated failure reproductions are acceptance work in M1.

| ID | Priority | Evidence and trigger | Consequence / repair |
|---|---|---|---|
| A01 (fixed in follow-up) | P1 | `research/lab_stages.py:99` takes the first two questions before skipping ANSWERED/EXHAUSTED. Two terminal questions rank above an active third with eligible evidence. | Active stage work disappears. Filter before limiting; define consistent DEFERRED/CAPABILITY_GAP handling across offers. |
| A02 (v2 retry handling implemented) | P1 | `research/wide.py:207` retains failed evaluations as deferred; `lab_stages.py:252` still publishes a Wide receipt; `lab_stages.py:140` suppresses further Wide offers for that composition once a receipt exists. | Transient Jev failure can strand states permanently for those inputs. Persist incomplete outcomes and retry only unfinished work without duplicating Candidates. |
| A03 (final publication gap fixed; earlier gaps open) | P1 | `lab_stages.py:290–315` changes Candidate/evidence/dossier state before publishing the receipt; `lab_runtime.py:187` saves the portfolio later. Recovery terminalizes runs and cleans raw workspaces without reconciling unattached scientific outputs. | A crash can leave published science outside the portfolio. Wide admission can be repeated; terminal Candidates can become ineligible before receipt attachment. Add durable operation identity, reconciliation and idempotent publication. Each crash consequence still needs fault-injection proof. |
| A04 | P1 | `lab_capabilities.py` invokes complete mutation/expression executors and explicitly declares no within-lane checkpoint; `lab_stages.py:290` invokes the complete Candidate arc and rejects a nonfinal outcome. | Work larger than one allowance cannot reliably make incremental progress. Add resumable units with unchanged scientific membership. |
| A05 | P2 | `laboratory.py:232` projects stage IDs and generic limitations; lane summaries contain counts. Candidate evidence gaps, Wide dimensions and dossier conclusions are absent from that summary. Projection size is capped. | The director lacks decision-grade scientific context; growing ID/offer lists can exhaust its input limit. Add bounded attributable summaries with visible omissions. |
| A06 | P2 | `cli/main.py:705` still exposes autonomous legacy Program observation/dispatch. Lab `research-portfolio` and legacy `program-state` are separate operational records. | Default worker convergence is not yet a single durable Program/Campaign lifecycle. Resolve legacy dispatch and bind question/Campaign/run identity. `program` is not read-only diagnostics. |
| A07 | P1 operational | `deploy/serve.py:start_worker` starts a child then becomes the API without monitoring/restarting that child. `lab_worker.py:108` performs cleanup/finalization after the child timeout without a separate parent deadline. | API health can stay green after worker death. Child runtime is bounded; total finalization within 600 seconds is not guaranteed on slow storage. Add liveness/restart handling and test the total deadline contract. |

Source paths in the table are under `cancerjev/` except `deploy/`. Line numbers describe the inspected working tree and may move.

A03 includes cleanup semantics: `lab_acquisition.py:56` records evictions and deletes failed-run raw workspaces; `lab_runtime.py` cleans on errors and in its publication `finally` block. Cleanup does not independently verify a complete derived-evidence/provenance commit. Successful publication, resumable partial work and discarded failed attempts need distinct durable outcomes. Failure cleanup itself is intentional.

## Implemented boundaries to preserve

- Canonical mutation/expression reducers, CNV scan/merge and StatisticalState composition are reused.
- Stage receipts bind artifact hashes, spec and release; execution requires terminal source runs. Cross-run Candidate reads require a binding to the original accepted Wide state/receipt.
- Wide rebinds selected states operationally while preserving scientific hashes. Director interpretations and Jev control shadows are not measurements.
- Raw eviction records and restart cleanup exist, but are not an atomic scientific-operation commit protocol.
- `worker --live` and `lab` use `run_lab`; Docker installs a pinned Codex CLI. Git and Codex binaries alone do not implement an engineering worktree/activation loop.

## Tests and verification

`tests/integration/test_lab_capabilities.py` exercises mutation/expression ordering, corrupt-artifact rejection, cross-run composition/Wide, investigation to a readable dossier, scientific hash preservation and missing Candidate-binding rejection. It recreates storage/service objects between operations within one test process. Replay GDC and stub Jev do not prove process-crash safety, provider quality or realistic cohort throughput.

The test-audit skill was applied to assess evidence. No source or tests were changed by this audit. Current working-tree checks passed: Ruff; strict mypy (112 source files); generated repository facts; full default offline pytest (907 passed, 4 deselected; exit 0, selection independently checked). The suite includes the pre-existing local supervisor/expression tests. No frontend build, Docker rebuild or live provider/deployment check was rerun for these documentation-only edits.

Historical bridge evidence: 901 tests passed on its clean code commit, a separate 11-process replay reached a dossier, and Docker/loopback director checks passed. Those are earlier results, not live validation or reruns in this audit. The working tree includes six additional tests for existing local changes.

## Remaining scientific and capability work

Capability-gap engineering, verified activation and question resumption are absent. Mixed historical CNV partitions have no conversion path. Candidate interruption tests must prove that final dossiers retain the complete cross-run history. The expression-only local constructor needs separate scientific review and capability wiring.

External/functional replication, new evidence adapters, calibration and consequential Jev evaluation are separate workstreams. The old audit's live-evidence/calibration objectives are not closed by this refresh. See `CALIBRATION_DESIGN.md`, `FUNCTIONAL_SOURCES.md`, `PATHWAY_SOURCES.md` and `JEV_DECISIONS.md`; revalidate historical results before making new claims. No new inference method, file-download adapter or validated cancer-target claim follows from the bridge.
