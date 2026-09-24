# Run and investigation lifecycles

Current behavior at `42b05d40e6edafec0b8613e7dd154a60a46e4fee`; proposed discovery changes are
separate in the [roadmap](DISCOVERY_ROADMAP.md). Research owns orchestration and policy;
`Repository._reduce` maintains committed projections. API/UI never execute research.

## Implemented live sweep

1. `run --live` acquires inventory/release identity and selects exactly `LUAD_RESEARCH_V1`,
   TCGA-LUAD. It does not pool TCGA-LUSC.
2. Mutation-indexed top-gene discovery (at most 20), gene case counts, SSM coverage and gene
   identities provide the current selection-biased candidate pool.
3. Cases are acquired in sorted pages of at most 250, with at most 10 pages and a production
   cohort ceiling of 1,000. Inconsistent pagination/duplicates fail closed. Open file metadata
   provides limited provenance context, not an exhaustive sample census.
4. Expression availability and UQFPKM values are acquired in case batches at most 250 and
   production gene chunks at most 10. Identifier-joined values are merged before local
   `log2(x+1)` summaries. Multi-batch provider summaries are not pooled:
   `BATCHED_PROVIDER_SUMMARY_NOT_COHORT_WIDE` is retained.
5. Per-gene schema-2 StatisticalStates are serialized dictionaries with scientific identity.
   With `--jev`, `jev-state-projection-v2` and `wide-v3` produce evaluations and separate
   baseline/Jev rankings. Python admission promotes at most three candidates; zero is valid.
6. Only explicitly selected candidates enter deep investigation. Selection can use an existing
   promotion or explicitly promote a successfully Wide-evaluated state under the same three-slot
   cap (`operator-selection-v1`); it is not a Jev admission. Repeated `--deep-candidate` selections
   are supported. Wide admission itself dispatches nothing.

## Implemented candidate arc

```text
accepted StatisticalState → baseline EvidenceState E0
   → CHECK_EVIDENCE_INTEGRITY_V1 → E1
   → deep-v1 judgment → deep-policy-v2 recorded move
       COMPLETE / ABSTAIN → stop arc
       FOLLOW_UP + authorization + eligible distinct action + budget
         → CHECK_REVISION_FAITHFULNESS_V1 → E2 → deep judgment/policy
       GENERATE_HYPOTHESES + authorization + budget
         → deterministic or injected generator → bounded hypotheses → hypothesis-v2
   → dossier over the current revision and recorded history
```

The current actions inspect retained integrity, not new biological measurements. They acquire
nothing and call no model. A failed action produces no new revision; attempted actions consume
budget. Per candidate, follow-up attempts are at most three, revision index is at most two
(E0/E1/E2), and hypotheses are at most three. See [budgets](GDC_BUDGETS.md).

`--deep-followup` authorizes further dispatch; it does not compel dispatch. `--deep-hypotheses`
requires deep selection and follow-up authorization. The default generator is deterministic.
The CLI can inject `OpenRouterHypothesisGenerator` when configured with an environment credential
and model; this is an implemented optional paid-model path, not a future adapter.
Generated text is labelled and never evidence. Python validates output and decides subsequent
steps. Jev does not authorize execution or choose arbitrary action IDs.

A completed arc with a current revision produces JSON and derived Markdown and can become
`DOSSIER_READY`. Early selection/eligibility/action failure paths may return without a dossier.
Dossier creation currently has an artifact-availability defect; see
[review Q3](PYTHON_CORE_REVIEW.md). A dossier is not proof of adequate scientific evidence.

## Runs, interruption and usage

Run transitions are PENDING → RUNNING → COMPLETED/FAILED/STOPPED; PENDING can also stop.
Terminal runs do not restart. Candidate failure can leave a partial run; budget-limited completion
is not scientific success. Events and registrations commit together; the canonical stream is
described in [RunEvents](RUN_EVENTS.md).

A single process lock owns research. On recovery, unfinished prior runs are interrupted and
retained; a new run does not replay uncertain provider requests. Continuous worker mode repeats
bounded runs at the operational interval. Current sweeps have no cross-run discovery cursor;
do not describe an advancing broad-universe scan as implemented.

GDC attempt/byte usage comes from transport accounting. Jev/LLM counters record logical provider
invocations; TypeSafe SDK retries are not separately represented. Unknown cost is not zero.
The fixture slice remains offline, labelled synthetic and isolated from live evidence.

## Planned discovery transition

Replace the top-mutation-only selection bottleneck with an explicit bounded measurable universe,
cheap deterministic reduction and richer survivor acquisition. Add only admitted typed lanes and
versioned policy. Reuse this bounded candidate arc; do not introduce a workflow engine.
Acquisition-capable or measurement-producing actions require a new explicit contract and budget
reservation, not an exception hidden inside the existing integrity action registry.
