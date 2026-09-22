# Run and investigation lifecycles

One authoritative transition module owns these rules. API and UI display structured state; they never infer it from messages. Phase 1 exercises this contract with fixtures; later phases replace one boundary at a time.

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> RUNNING: owner starts
    PENDING --> STOPPED: interrupted before start
    RUNNING --> COMPLETED: bounded sweep finished
    RUNNING --> FAILED: run cannot safely continue
    RUNNING --> STOPPED: stop or process interruption
    COMPLETED --> [*]
    FAILED --> [*]
    STOPPED --> [*]
```

Terminal runs never return to RUNNING. New attempts create new runs with explicit predecessor links where useful. Candidate failure need not fail the run: finish other candidates, record counts and PARTIAL coverage. Budget-limited normal runs may be COMPLETED with deferred candidates. COMPLETED is not a scientific success classification.

Stages: INVENTORY → GDC_FAST_SEARCH → STATE_GENERATION → JEV_WIDE, then candidate DEEP_ANALYSIS → EVIDENCE_BUILD → JEV_DEEP → HYPOTHESIS_GENERATION → HYPOTHESIS_VERIFICATION → FOLLOWUP → EVIDENCE_BUILD/JEV_DEEP/review → DOSSIER or candidate termination. Store stage occurrences with candidate/iteration IDs; a single pipeline display cannot imply all candidates advance together.

Candidate transitions:

```text
NEW -> WIDE_EVALUATED -> DEEP_ANALYZED -> HYPOTHESIZED
HYPOTHESIZED -> FOLLOWUP -> DEEP_ANALYZED -> HYPOTHESIZED
HYPOTHESIZED -> DOSSIER_READY
NEW|WIDE_EVALUATED|DEEP_ANALYZED|HYPOTHESIZED|FOLLOWUP
    -> TERMINATED | DEFERRED | FAILED
```

Re-entering HYPOTHESIZED after follow-up may mean re-reviewing existing hypotheses, not generating six new ones. Retain immutable state/evaluation histories; `latest_evidence_state_id` is only a pointer.

Baseline deep evidence is iteration 0. At most two subsequent follow-up rounds create iteration 1 and 2. Within these rounds at most three total follow-up executions are admitted. A round can execute multiple independent eligible actions, each using a slot, and publish one combined new EvidenceState only after their outcomes are recorded. Failed actions consume slots; a round containing admitted work consumes the iteration even if no useful evidence emerges. No repeated unchanged-state loop.

Hypotheses have a lifetime cap of six per candidate. Preserve initial hypotheses; if a later generation is useful, ask only for remaining capacity. A revision/new replacement counts as a new hypothesis. Re-reviewing an unchanged hypothesis against new evidence consumes a Jev call, not a new hypothesis slot.

Routing order: hard validity/access checks → resource and capability checks → semantic evaluation → deterministic eligible-action selection → execute or terminal disposition. Registered action selection records action/version, evidence hash, parameters, expected costs and reason. Model-proposed action IDs and parameters must match the registry; unknown names or incompatible inputs produce `UNSUPPORTED_FOLLOWUP`. Code recomputes eligibility immediately before execution.

TERMINATED reasons include invalid candidate, no useful pattern, no information gain, redundant hypotheses and supported no-further-test decision. DEFERRED reasons include DEFERRED_BUDGET, UNAVAILABLE_ACCESS, UNVERIFIED_CAPABILITY, UNSUPPORTED_FOLLOWUP, UNSUPPORTED_IN_V1 and INSUFFICIENT_EVIDENCE. FAILED is execution/contract failure, not weak biology. On interrupted run, unfinished candidates become DEFERRED/INTERRUPTED, with their previous evidence preserved.

Dossier readiness requires an explicit research puzzle, adequate deterministic observations, missingness/contradictions represented, competing hypotheses, and a falsifiable wet-lab direction. It does not require a proven mechanism or significant p-value. Dossier creation and DOSSIER_READY commit together; one candidate has at most one dossier. No-result runs are valid outcomes.

Continuous mode takes the process lock, reconciles prior unfinished runs, creates a run immediately, completes it, persists cursor advancement and terminal event in one transaction, waits the configured interval (default 60 minutes), and repeats. Advance traversal based on attempted scope with explicit incomplete dispositions so a failing project cannot starve the roster. Mid-run process loss is recorded before the next cursor decision. No cloud scheduler or queue.

Phase 1 demo must include a promoted candidate, baseline fake evidence, independent fake Jev judgments, competing fixture hypotheses, one registered fixture follow-up producing different evidence, and a fake dossier. Separate small fixtures cover defer, failure, stop and no-dossier branches. Every artifact is labeled synthetic; fake provider usage is never presented as real network usage.
