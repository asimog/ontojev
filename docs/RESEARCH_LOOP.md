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
5. Per-gene typed `StatisticalState` records (schema 4) are serialized once at the artifact
   boundary. With `--jev`, `jev-state-projection-v4` and `wide-v3` produce validated typed
   answers and separate baseline/Jev rankings. Python admission (`wide-policy-v2`) promotes at
   most three candidates; zero is valid.
6. Only explicitly selected candidates enter deep investigation. Selection can use an existing
   promotion (`slot:N`) or explicitly promote a successfully Wide-evaluated state under the same
   three-slot cap (`operator-selection-v1`); it is not a Jev admission. Repeated
   `--deep-candidate` selections are supported. Wide admission itself dispatches nothing.

## IMPLEMENTED: candidate arc

```text
accepted StatisticalState -> baseline EvidenceState E0
   -> CHECK_EVIDENCE_INTEGRITY_V1 -> E1
   -> deep-v1 judgment (jev-evidence-projection-v2) -> deep-policy-v2 recorded move
        COMPLETE / ABSTAIN -> stop arc
        FOLLOW_UP + authorization + eligible distinct action + budget
          -> CHECK_REVISION_FAITHFULNESS_V1 -> E2 -> deep judgment/policy
        GENERATE_HYPOTHESES + authorization + budget
          -> deterministic or injected generator -> bounded hypotheses
          -> hypothesis-v2 critique (jev-hypothesis-projection-v2)
   -> dossier (schema 2) over the current revision and recorded history
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

A completed arc with a current revision produces authoritative JSON and derived Markdown and can
become `DOSSIER_READY`. If an authoritative revision or required artifact is unavailable or
corrupt, publication is refused as `DOSSIER_UNAVAILABLE`; earlier revisions never substitute.
Early selection/eligibility/action failure paths may end without a dossier. A dossier is not
proof of adequate scientific evidence.

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

## PLANNED: Stage 4 discovery transition

Replace the top-mutation-only selection bottleneck with an explicit bounded measurable universe,
cheap deterministic reduction and richer survivor acquisition. Add only admitted typed lanes and
versioned policy. Reuse this bounded candidate arc; do not introduce a workflow engine.
Acquisition-capable or measurement-producing actions require a new explicit contract and budget
reservation, not an exception hidden inside the existing integrity action registry. Indexed
systematic discovery is the next separately authorized task; proposed contracts in the roadmap
are not current runtime.