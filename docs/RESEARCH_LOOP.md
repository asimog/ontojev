# Run and investigation lifecycles

Current behavior after the Stage 3 hard cutover (2026-09-25). Research owns orchestration and
policy; `Repository._reduce` maintains committed projections. API/UI never execute research.
Proposed discovery changes are separate in the [roadmap](DISCOVERY_ROADMAP.md).

## IMPLEMENTED: live sweep

1. `run --live` acquires inventory/release identity and selects exactly `LUAD_RESEARCH_V1`,
   TCGA-LUAD. It does not pool TCGA-LUSC.
2. Mutation-indexed top-gene discovery (at most 20), gene case counts, SSM coverage and gene
   identities provide the current selection-biased candidate pool.
3. Cases are acquired in sorted pages of at most 250, with at most 10 pages and a production
   cohort ceiling of 1,000. Inconsistent pagination or duplicates fail closed. Open file
   metadata provides limited provenance context, not an exhaustive sample census.
4. Expression availability and UQFPKM values are acquired in case batches of at most 250 and
   production gene chunks of at most 10. Identifier-joined values are merged before local
   `log2(x+1)` summaries. Multi-batch provider summaries are not pooled:
   `BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE` is retained.
5. Per-gene typed `StatisticalState` records are serialized once at the artifact boundary. With
   `--jev`, the state projection and the wide question set produce validated typed answers and
   separate baseline/Jev rankings. Python admission promotes at most three candidates; zero is
   valid.
6. Only explicitly selected candidates enter deep investigation. Selection can use an existing
   promotion (`slot:N`) or explicitly promote a successfully Wide-evaluated state under the same
   three-slot cap (`operator-selection-v1`); it is not a Jev admission. Repeated
   `--deep-candidate` selections are supported. Wide admission itself dispatches nothing.

## IMPLEMENTED: candidate arc

```text
accepted StatisticalState -> baseline EvidenceState E0
   -> CHECK_EVIDENCE_INTEGRITY_V1 -> E1
    -> deep judgment (evidence projection + deep question set) -> deep policy recorded move
        COMPLETE / ABSTAIN -> stop arc with the policy's actual reason code
            (a terminal move is never routed through the follow-up dispatcher)
        FOLLOW_UP + authorization + eligible distinct action + budget
          -> 0 eligible -> NO_DISTINCT_ELIGIBLE_ACTION
          -> 1 eligible -> dispatched
          -> >1 eligible -> fail closed EXPLICIT_ACTION_REQUIRED
          -> CHECK_REVISION_FAITHFULNESS_V1 -> E2 -> deep judgment/policy
        GENERATE_HYPOTHESES + authorization + budget
          -> deterministic or injected generator -> bounded hypotheses
          -> hypothesis question set critique (hypothesis projection)
   -> STAGE 8 FINALIZATION:
        FinalCandidateResult derived from the recorded run state
        -> no-jev-baseline-v1 deterministic comparison (read-only replay)
        -> authoritative JSON dossier + derived Markdown
        -> FINAL_CANDIDATE_RESULT_RECORDED + DOSSIER_READY
        -> CANDIDATE_COMPLETE -> next candidate
   -> candidate queue exhausted -> RUN_COMPLETED
```

The current actions inspect retained integrity, not new biological measurements. They acquire
nothing and call no model. A failed action produces no new revision; attempted actions consume
budget. Per candidate, follow-up attempts are at most three, the revision index is at most two
(E0/E1/E2), and hypotheses are at most three. See [budgets](GDC_BUDGETS.md).

`--deep-followup` authorizes further dispatch; it does not compel dispatch. `--deep-hypotheses`
requires deep selection and follow-up authorization and records an operator request without
rewriting the recorded move. The default generator is deterministic. The CLI can inject
`OpenRouterHypothesisGenerator` when configured with an environment credential and model; this
is an implemented optional paid-model path. Generated text is labelled and never evidence.
Python validates output and decides subsequent steps. Jev does not authorize execution or choose
arbitrary action IDs.

Every investigated candidate whose evidence was accepted finalizes in Stage 8
(`research/finalize.py`): one deterministic `FINAL_CANDIDATE_RESULT` artifact, the authoritative
dossier (including the final result and the `jev_vs_no_jev_comparison` section), and
then `CANDIDATE_COMPLETE` with the dossier attached. No human review participates; the candidate
loop continues automatically to the next selection, and the run completes only after the queue is
exhausted (`RUN_COMPLETED` with `candidate_queue_exhausted`). If an authoritative revision or
required artifact is unavailable or corrupt, publication is refused as `DOSSIER_UNAVAILABLE` and
the candidate does NOT become complete (status `FAILED`); earlier revisions never substitute.
A dossier is not proof of adequate scientific evidence.

Stage 8 also records the Jev-vs-no-Jev comparison (`no-jev-baseline-v1`): the observed Jev-assisted
path versus a declared deterministic replay over the same evidence. The replay is read-only — it
never mutates EvidenceState, executes actions or generates hypotheses, and no model is called.
Comparisons that cannot honestly be computed are `NOT_COMPARABLE`, never invented. The comparison
shows decision deltas only; superiority claims require a separate empirical evaluation design. The
human-labelled prospective harness (`research/prospective.py`) is an OPTIONAL evaluation/calibration
capability outside the numbered runtime stages: the runtime never invokes it and candidate
completion never depends on it.

## Fixture demonstration

`run --fixture demo` uses the same `LiveOrchestrator`, `JevService` and persistence with
`FixtureTransport` + `FixtureJevAdapter`, run mode `FIXTURE` and a synthetic notice in the
dossier. Fixture and live records are never mixed. There is no independent fixture engine.

## Runs, interruption and usage

Run transitions are PENDING → RUNNING → COMPLETED/FAILED/STOPPED; PENDING can also stop.
Terminal runs do not restart. Candidate failure can leave a partial run; budget-limited
completion is not scientific success. Events and registrations commit together; the canonical
stream is described in [RunEvents](RUN_EVENTS.md).

A single process lock owns research. On recovery, unfinished prior runs are interrupted and
retained; a new run does not replay uncertain provider requests. Continuous worker mode repeats
bounded runs at the operational interval. Current sweeps have no cross-run discovery cursor;
do not describe an advancing broad-universe scan as implemented.

GDC attempt/byte usage comes from the transport ledger. Jev/LLM counters record logical provider
invocations, and TypeSafe SDK retries are explicitly disabled, so one logical evaluation
corresponds to at most one HTTP attempt. A total paid-model spend gate is still absent
(PLANNED); unknown cost is not zero.

## IMPLEMENTED: systematic pre-Wide discovery

The provider-ranked top-mutation selection above is not the only candidate source. Systematic
discovery is implemented as separately invoked bounded commands (`discover`,
`discover-expression`, `discover-cnv`) over a fixed release-bound indexed universe: indexed
mutation counts, case-labelled expression summaries with Tukey tails, and survivor-only CNV
occurrences, each reduced deterministically and persisted as one immutable typed result; the
cutover composes one canonical `StatisticalState` per survivor with exact cross-stage binding.
No Jev, provider rank, LLM, census status or hidden biological knowledge enters any reduction.
Contracts and evidence gates are owned by [the roadmap](DISCOVERY_ROADMAP.md); the multi-modal
Stage 9 loop (Arm Jev, candidate union, integrated states) is PROVISIONAL and not implemented.

## PLANNED: campaign progression (Stage 9, provisional)

Today one bounded run completes and stops; continuous worker mode repeats bounded runs at the
operational interval. The provisional Stage 9 target adds a named, versioned and deterministic
campaign-selection policy that either selects the next eligible bounded campaign or places the
autonomous program into an explicit idle state — never a hidden model, lexicographic fallback
or implicit ordering, and never one infinite run.