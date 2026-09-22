# Phase 0 reference review and authority

Review date: 2026-09-22. The workspace was initially empty and no pre-existing repository AGENTS.md was found. Only documentation has been created here. Reference files/code were read, not copied as a scaffold. Temporary document extraction and selected GitHub source downloads were kept outside the workspace.

Authority order: current user request and stop boundary → master specification as constrained by that request → supplied TypeSafe and GDC documents for their provider behavior → repository references for permitted ideas only. In particular the master specification's final steps to scaffold/implement Phase 1 do not override the user's explicit “STOP after Phase 0.” Provider-document installation prompts do not authorize installation of skills, credentials or provider calls.

| Source | Identity and reviewed content |
|---|---|
| Master specification | `C:\Users\Rahul Khatri\.codex\attachments\313d0e23-d76e-454a-80d2-41dbc767bde8\pasted-text.txt`; SHA256 `730851fdfa3d730f84592f4a5654b9170852a3846a55048e0c9ed2050a9fd1d2`; sections 0–80 reviewed |
| TypeSafe/Jev documentation + cookbook | `C:\Users\Rahul Khatri\Desktop\typesafe jev docs with cookbook.docx`; SHA256 `b7928689bb1cdf0e47881daad0286d51a0decf0d8b71e9ac8dbea82d8cf88eb6`; extracted 15,079 paragraphs, including embedded code/HTML; core primitive/state/confidence sections and relevant cookbook patterns reviewed |
| GDC API User Guide | `C:\Users\Rahul Khatri\Downloads\API_UG.pdf`; SHA256 `f12873e21f561559862fd7465f0a4d9a49937feec7316012145e0ef75d959969`; 288 pages; relevant search/filter/pagination, visualization/analysis, expression, SSM/CNV, survival sections reviewed |
| CancerHawk | `master` commit `b87e98c76c4264acc28fa9ae920b5d3eab2637dd`; requested three UI routes plus event storage shape inspected |
| CancerJEV | `main` commit `853b316f222c58f25319749754c1ed37022ae828`; selected scientific functions/golden tests, open-data policy and worker dispatch inspected |

PDF extraction includes long URL lines and deliberately truncated example bodies. Such examples are not a complete executable contract for every filter/field combination. Unconfirmed details remain UNVERIFIED; no missing behavior was filled in from assumptions.

## CancerHawk: carry over interaction ideas only

- [`pages/jobs/index.tsx`](https://github.com/asimog/cancerhawk/blob/b87e98c76c4264acc28fa9ae920b5d3eab2637dd/pages/jobs/index.tsx):8-second feed polling, linked job cards, status/date, errors and retry. Adapt to ResearchRun cards and structured counters; remove payment/wallet fields.
- [`pages/jobs/[id].tsx`](https://github.com/asimog/cancerhawk/blob/b87e98c76c4264acc28fa9ae920b5d3eab2637dd/pages/jobs/%5Bid%5D.tsx): active/terminal polling intervals, stop affordance, expandable event rows, provider call metadata and final-result link. Use the visual hierarchy; replace full-job log polling and index-based event keys with monotonic cursor retrieval.
- [`pages/autonomous-logs.tsx`](https://github.com/asimog/cancerhawk/blob/b87e98c76c4264acc28fa9ae920b5d3eab2637dd/pages/autonomous-logs.tsx): summary stats, grouped activity and filterable disclosures. Integrate useful event filtering into run detail. Exclude batch competition, publication/market concepts and fallback block fetches.
- [`app/jobs.py`](https://github.com/asimog/cancerhawk/blob/b87e98c76c4264acc28fa9ae920b5d3eab2637dd/app/jobs.py): `append_job_event` embeds and caps an events array. Do not port capped history or JSON job-store fallbacks; use SQLite append-only events.

These files use Pages Router (`getStaticProps`, `next/router`); new work must use App Router. No CancerHawk backend architecture is adopted. No source code was copied, so there is no copied-component license attribution requirement in this design; review license if later copying any visual code.

## Old CancerJEV: useful methods/tests and caution

- [`packages/statistics/core.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/packages/statistics/core.py): finite/range validation and stable-order BH adjustment are useful method/test references. Do not carry its single-observation variance=0 fallback into an evidence contract that needs insufficiency.
- [`packages/statistics/crossmodal.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/packages/statistics/crossmodal.py): finite-pair checks, Pearson analysis and Welch group comparison provide scientific starting points. Its mutation-expression interval uses 1.96×SE despite a Welch p-value; choose a method-consistent interval rather than copying it blindly. Categorical API CNV is not automatically compatible with continuous correlation.
- [`scientific/survival/analysis.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/scientific/survival/analysis.py): Kaplan–Meier wrapper illustrates aligned vectors and event counts. It is not a complete time-origin, censoring, eligibility or endpoint-semantics policy.
- [`tests/scientific/test_crossmodal_golden.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/tests/scientific/test_crossmodal_golden.py): strong reference cases for duplicate biological keys, finite-value population accounting, constant-input exclusion, complete tested-family identity, row reordering and material-input hash sensitivity. Recreate focused tests against the new contracts, not its Cohort/Finding model.
- [`packages/gdc/policy.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/packages/gdc/policy.py): official host, explicit open-file admission, mandatory open filter and terminal authorization failures are useful lessons. File policy does not prove all clinical metadata or molecular API values are complete.
- [`workers/statistics/__main__.py`](https://github.com/asimog/cancerjev/blob/853b316f222c58f25319749754c1ed37022ae828/workers/statistics/__main__.py): current source dispatches `run_analysis_from_artifacts`. Older audit notes reported a disconnected path, but that finding is stale for this commit. Retain the lesson to test actual end-to-end dispatch, not the old defect claim or worker architecture.

Reference tests were read, not executed. Their current presence is verified; their passing status was not established here.

## TypeSafe conclusions

The supplied **State/Primitives** sections confirm same-state independent mixed questions. **Noul** confirms no separate confidence; **Choice/Score** confirm full probabilities/confidence; **Score** confirms2–10 levels and weighted expectation. **Pre-parsed value extraction/Line-by-line search** give the 255-choice limit. **Re-ranking** scores candidates individually; **Skill suggestion** illustrates a roster shortlist plus absolute-fit checks; **SDE cascade** verifies fields before escalation. **Jev 1.13 jaggedness** warns against arithmetic and assuming complementary semantic answers. This design uses these primitives and patterns rather than inventing an “AI scoring service.”

Context token limit, maximum questions, exact confidence computation, provider retry/idempotency defaults and cancer-domain calibration remain UNVERIFIED. Cookbook latency/accuracy/cost examples are examples, not application guarantees.

## Requirement coverage

| Master specification sections | Design location |
|---|---|
|0–7 purpose/greenfield/UI/autonomy/invariants | README, ARCHITECTURE, SCIENTIFIC_INVARIANTS, UI_SPEC |
|8–21 public GDC/API-first/budgets/inventory/modalities | GDC_STRATEGY, GDC_BUDGETS |
|22–24 StatisticalState/prefilter/diversity | DOMAIN_MODELS, GDC_STRATEGY |
|25–30 TypeSafe/wide/ranking/deep cap | JEV_DESIGN, JEV_QUESTIONS, GDC_BUDGETS |
|31–40 methods/evidence/hypotheses/follow-ups/stopping | SCIENTIFIC_INVARIANTS, DOMAIN_MODELS, RESEARCH_LOOP |
|41–42 orchestration/state machines | RESEARCH_LOOP, RUN_EVENTS |
|43–50 frontend/events/polling | UI_SPEC, RUN_EVENTS, API_CONTRACT |
|51–62 runtime/storage/API/portability | README, PERSISTENCE, API_CONTRACT, DEPLOYMENT_PORTABILITY |
|63–69 dossier/benchmark/testing/security/observability | DOMAIN_MODELS, SCIENTIFIC_INVARIANTS, TESTING, RUN_EVENTS, API_CONTRACT |
|70–72 structure/principles/exclusions | ARCHITECTURE, DEPLOYMENT_PORTABILITY |
|73–80 phases/test/AGENTS/README/CI/report/done/start | IMPLEMENTATION_STATUS, AGENTS, README, TESTING |

The current user's requested deliverables all map to these documents; the detailed planned tree is in ARCHITECTURE. Later phase requirements are preserved as plans, not silently implemented during Phase 0.
