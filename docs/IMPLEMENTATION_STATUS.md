# Phase 0 implementation status and architecture review

**DONE:** Phase 0 document review and design output. **CURRENT:** awaiting explicit user design approval. **NEXT:** Phase 1 fake vertical slice only, if approved. No production/application code, scaffold, database, frontend or runtime has been created.

## Phase report

**What changed / why:** Created README, repository-wide AGENTS, and 17 design documents to make the greenfield architecture reviewable before implementation. The design fixes ownership boundaries, lifecycle semantics, one canonical event stream, bounded API-first science and actual TypeSafe primitives.

**Files created:** README.md; AGENTS.md; docs/ARCHITECTURE.md, DOMAIN_MODELS.md, RUN_EVENTS.md, SCIENTIFIC_INVARIANTS.md, GDC_STRATEGY.md, GDC_BUDGETS.md, JEV_DESIGN.md, JEV_QUESTIONS.md, RESEARCH_LOOP.md, PERSISTENCE.md, API_CONTRACT.md, UI_SPEC.md, DEPLOYMENT_PORTABILITY.md, TESTING.md, PHASE_1_PLAN.md, SOURCE_REVIEW.md, IMPLEMENTATION_STATUS.md.

**Architectural decisions:** one sequential research process; SQLite+local artifacts; OS process lock; interrupted-run preservation instead of generic resume; event/projection transaction; FastAPI reads; App Router polling; fake-only Phase 1; no forbidden infrastructure. Every major choice has a simpler-design comparison in ARCHITECTURE.

**Scientific decisions:** API-first with no file acquisition; preserve unknown/missing/partial; matched populations and units; no fabricated p/q/CI; immutable evidence revisions; Jev vectors retain probabilities; registered actions only; six lifetime hypotheses, three lifetime follow-ups, two follow-up rounds. Use a simple descriptive first scientific slice rather than implementing the entire methods list.

**Checks run:** local reference extraction and identity hashing, selected current GitHub source inspection, documentation link/structure checks and requirement/cap consistency review. Application, browser, scientific and provider tests: **NOT RUN — no implementation exists.** Reference repository tests were not run. See the verification record below for completed documentation checks.

**External calls:** read-only GitHub repository/API/raw-source requests and official Next.js documentation. A PDF text-extraction dependency was installed into a temporary tooling directory, outside the workspace; original attachments remain unchanged. No provider credentials were used. No GDC research requests, TypeSafe calls, or generative-provider calls were made.

**GDC usage:**0 requests,0 response bytes. **Jev usage:**0 calls. **LLM research-provider usage:**0 calls. This describes the proposed application's provider use during review, not the assistant's operation.

## Architecture test

PASS means the design supplies a concrete mechanism, **not** that unimplemented code has passed a test. RISK identifies an unresolved semantic/provider/implementation boundary. No architectural FAIL remains after removing bulk acquisition and extra infrastructure.

| # | Question | Result | Evidence / gate |
|---:|---|---|---|
|1|Can one engineer understand the full fake run in under an hour?|RISK|Small explicit loop and phase-specific tree make this plausible; time-boxed walkthrough with another engineer remains unperformed.|
|2|Exactly one RunEvent source of truth?|PASS|SQLite events; transactional reducer; CLI renders committed events.|
|3|UI derives status from structured state rather than console text?|PASS|Read API projections and typed event payloads.|
|4|Deterministic science separated from Jev?|PASS|Immutable science records; adapter owns semantic outputs only.|
|5|Jev separated from LLM generation?|PASS|Different owned contracts and persisted record types.|
|6|Can TypeSafe be replaced without rewriting scientific code?|PASS|JevService and normalized answer union; no SDK import in science.|
|7|Can LLM provider be replaced without rewriting science?|PASS|HypothesisGenerator boundary; registry owns execution.|
|8|Can an LLM-generated number enter scientific evidence? Required NO.|PASS|Measured fields/observations created only by deterministic methods; generated content stored separately; factual dossier templates resolve refs.|
|9|Can a hypothesis execute arbitrary code? Required NO.|PASS|Allowlisted registry plus strict parameter/eligibility validation; no generated SQL/shell/URLs.|
|10|Can a GDC response exceed 5MiB without interruption? Required NO.|RISK|Proposed header rejection, capped reads and cancellation enforce body-consumption cap; physical OS/TLS read-ahead is not an absolute wire-byte guarantee. Transport proof required before Phase 2.|
|11|Can a run exceed 64MiB GDC download budget? Required NO.|RISK|Shared pessimistic reservations prevent application body-consumption overshoot even at concurrency 4. Literal NIC-byte interpretation has the same unresolved physical limitation.|
|12|Can more than 150 GDC requests occur/run? Required NO.|PASS|Sole transport, per-attempt reservation, no hidden retry/redirect; uncertain dispatches never refunded.|
|13|Can a request send >250 case IDs? Required NO.|PASS|Final request validation across all groups/aliases; typed builders only.|
|14|Can a request send >100 gene IDs? Required NO.|PASS|Aggregate final-request validation, including nested filters.|
|15|Can >20 candidates enter deep investigation? Required NO.|PASS|Permanent transactional admission slots, failures included.|
|16|Is all-GDC coverage bounded repeated traversal? Required YES.|PASS|Fair project/lane/case cursor, explicit incomplete coverage; no claim of exhaustive molecular coverage.|
|17|Can it run locally without cloud services? Required YES.|PASS|Fake mode uses Python/SQLite/files/API/Next/polling only.|
|18|Is there a simpler architecture?|PASS|Selected plain orchestration, SQL and polling; removed queues, generic resumability, redundant log surface and premature cloud adapters.|

Additional budget gates: <=12 scientific projects, <=4 concurrent GDC requests, <=10 pages/logical query, <=100 hits/project/lane, <=1,000 wide states, <=3 follow-ups, <=2 follow-up rounds, <=6 hypotheses and 65,536-byte event payloads all have explicit admission/check points in GDC_BUDGETS. Runtime verification remains future work.

**Overall architecture confidence:8/10.** The offline fake slice is well specified and does not depend on unresolved provider capabilities. Confidence is lower for a full real scientific loop because exact assay/sample semantics, scoped aggregation behavior, Jev service limits/calibration and transport-level byte accounting require verification.

## Known limitations / risks

- “Actual downloaded bytes” must distinguish application response-body consumption from bytes arriving in OS/TLS/network buffers; no false absolute wire-byte claim is made.
- `/analysis/top_cases_counts_by_genes` and `/analysis/mutated_cases_count_by_project` scoped filtering/aggregation completeness are UNVERIFIED; optional lanes stay disabled until confirmed.
- Expression sample/workflow resolution, CNV continuous values/callability and some combined occurrence filter manifests are UNVERIFIED. No assumed sample-matched cross-modal method.
- GDC survival output does not confirm an adjusted hazard model, exact inferential implementation or response pagination. Keep unsupported outputs absent.
- Jev context/question/rate limits, SDK retry behavior, model availability, current cost and cancer calibration are UNVERIFIED. No generic AI score or calibration claim substitutes for evidence.
- SQL+filesystem publication is ordered, not one atomic transaction. Orphans are acceptable; visible dangling references are errors.
- Top-k discovery and adaptive follow-up are exploratory and selection-biased. “All GDC” is fair bounded traversal of available supported API opportunities, not an exhaustive analysis guarantee.

**Deferred:** every real integration (Phases2–10), production science, benchmark, optional stop endpoint, global log page, deployment/backup automation, all forbidden infrastructure and product features. Phase 1 acceptance is not “first meaningful scientific system” completion; the 24 final master-spec criteria require the later real loop and empirical benchmark.

**Stop boundary:** The user explicitly requested stopping after Phase 0 and withholding Phase 1 until approval. This report is the reviewable design; no implementation follows automatically.

## Documentation verification record

Completed: 19 Markdown files present; no non-Markdown files/application code in the workspace; no broken local Markdown links; all fenced blocks balanced; all 13 user-listed budget constants plus the specification's wide-hit and event-payload caps present. Requirement coverage maps all master-spec sections 0–80 to design files. Current reference commit identities were checked through GitHub. These are documentation checks, not runtime acceptance tests.

## THE SIMPLEST VERSION THAT COULD ACTUALLY WORK

**One sequential Python research process, SQLite, local JSON/TSV artifacts, one bounded GDC client, one TypeSafe adapter, one LLM adapter, and a dictionary of registered scientific functions.** No queue, generic workflow engine, distributed workers or cloud storage. This describes the minimum eventual **real** demonstration; Phase 1 remains fake and implementation still requires approval.

Use one automatically selected project, one reproducibly selected collection of at most 250 cases, a small protein-coding gene shortlist, and one promoted candidate. Expression variability alone can demonstrate the entire loop:

1. **Real bounded search → StatisticalState:** query case metadata, expression availability and `/gene_expression/gene_selection`. Store returned variability summaries, exact examined population, missingness, request identities and response hashes. Reject unusable states without a significance threshold. All GDC traffic passes through the existing hard-budget checks; acquire no files.
2. **Jev reranking:** send each compact state with the same batched Noul/Choice/Score questions. Preserve the full vectors and promote one valid candidate using explicit policy. Mark unavailable cross-project/modality questions inapplicable.
3. **Deterministic deep analysis:** request bounded `/gene_expression/values` TSV for that gene and case collection; calculate log2(UQFPKM+1), sample SD, median and missingness locally. Create an immutable EvidenceState. These are descriptive measurements, not invented p-values or claims about sample-matched assays.
4. **Jev fan-out → LLM hypotheses:** independently judge coherence, fragility and follow-up value against that evidence. Ask one LLM for two competing explanations, such as broadly distributed variability versus dependence on a few extreme observations. Mechanistic explanations remain explicitly speculative.
5. **Jev hypothesis evaluation:** evaluate each explanation separately against the same evidence, retaining support, contradiction, uncertainty and testability judgments.
6. **Deterministic follow-up:** one registered `LEAVE_ONE_CASE_OUT_VARIABILITY_V1` action recalculates SD after excluding each observed case in turn. Record sensitivity relative to baseline and exclusions as new evidence; do not overwrite baseline or treat sensitivity as proof of mechanism. This narrower demonstration needs only this additional action, not the full proposed registry.
7. **Dossier:** render authoritative JSON and derived Markdown containing observations, Jev vectors, competing hypotheses, follow-up results, limitations and a falsifiable experimental direction. Finish even when the result weakens the initial lead; defer if evidence cannot support a dossier.

**Why anything else exists:** SQLite, immutable artifacts, provenance, tests and a process lock make the demonstration inspectable and reproducible. RunEvents provide its single durable execution record. FastAPI, Next.js and polling are not necessary for the scientific computation; they satisfy your explicit requirement to watch it live. Module boundaries isolate evidence from model outputs without adding services. Continuous scheduling, the discovery cursor and cache serve repeated exploration, not this first real demonstration; defer them beyond its needs. CNV, mutation, survival, cross-project methods, elaborate ranking and deployment tooling are unnecessary here. The later benchmark exists solely to test whether Jev adds value; completing this loop alone does not establish that.
