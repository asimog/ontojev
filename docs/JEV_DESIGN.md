# Jev capability design and evidence review

Reviewed 2026-09-24 at `42b05d40e6edafec0b8613e7dd154a60a46e4fee`.
No paid Jev or generative call was made. The installed TypeSafe skill was read and compared with
the [official skill](https://github.com/typesafe-ai/skills): identical after newline normalization.
The skill led this review toward live documentation, atomic semantic judgments, deterministic
composition and calibration rather than generic prompt-and-parse or cookbook threshold adoption.

## Sources and uncertainty semantics

Reviewed [index](https://docs.typesafe.ai/llms.txt), [System One](https://docs.typesafe.ai/concepts/system-one),
[state](https://docs.typesafe.ai/concepts/state), [use cases](https://docs.typesafe.ai/concepts/use-case-map),
[Noul](https://docs.typesafe.ai/primitives/noul), [Choice](https://docs.typesafe.ai/primitives/choice),
[Score](https://docs.typesafe.ai/primitives/score), [structured questions](https://docs.typesafe.ai/primitives/advanced),
[confidence](https://docs.typesafe.ai/confidence), [API](https://docs.typesafe.ai/api),
[Python SDK](https://docs.typesafe.ai/sdk/python), [SDK usage/retries](https://docs.typesafe.ai/sdk/python/usage),
[models](https://docs.typesafe.ai/models) and [jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13).
The separate building-guide and autoformat pages were inaccessible through the web reader; the
installed/official skill and accessible pages supplied the relevant guidance. No unsupported
autoformat capability is admitted.

Noul is probability of yes, not intensity or a separate confidence score. Choice distributions compare
closed alternatives; include NONE/OTHER or an explicit no-match when appropriate. Score uses ordered
rubric levels and their expected position, not biological magnitude. Confidence summarizes distribution
concentration, not truth, calibration in LUAD, permission, significance or clinical safety.
Independent questions sharing state may be batched; they cannot read each other's answers.
IDs are program keys, not question meaning. Calculations and exact lookups remain Python-owned.

## Current implementation

wide-v3 (6 Noul+1 Choice), deep-v1 (4 Noul+1 Choice), hypothesis-v2 (2 Noul+1 Choice) are IMPLEMENTED.
Projection versions are jev-state-projection-v2, jev-evidence-projection-v1 and
jev-hypothesis-projection-v1. Existing versions and provisional thresholds remain unchanged.
See [questions](JEV_QUESTIONS.md). The current Deep policy has four moves including
GENERATE_HYPOTHESES; policy never dispatches its own decision.

Stage 2 validates cached-answer hydration against recorded artifacts, original question definitions,
rosters, distributions, projection/applicability and model identity. Invalid cache yields
UNUSABLE_CACHE abstention with no replacement call. Stage 3 keeps those typed answer variants in
EvaluationRecord through Wide/Deep policy and cache reuse; current Wide projection consumes a typed
state summary. Historical adapters and v2 evidence/hypothesis presentation remain. Pinned
requested/resolved Jev identity gates cache reuse. No question/projection/policy semantics change.
Operational IDs are excluded from projections where required. A historical ranking change or
successful provider call does not establish incremental research value.

## Cookbook capability map

Each row records an illustrative problem/state, decomposition, primitive and deterministic surround.
All examples are external demonstrations, not OntoJev/LUAD results.

| Pattern / source | Problem, state and decomposition | Primitive / batching / deterministic surround | OntoJev decision and added complexity |
|---|---|---|---|
| [Feature discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) | Labelled wine notes -> proposed semantic questions -> numeric features -> supervised prediction/error feedback | Score/Noul features; batch questions per note; code owns grouped evaluation and classical learner | LATER: labelled review corpus first; semantic features outside StatisticalState; do not install CatBoost or an autoresearch agent now |
| [Reranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe) | Legal query and candidate passage after cheap retrieval | Comparable per-pair Noul; independent pairs; code sorts and preserves retrieval ceiling | EXPERIMENTAL: survivor relevance only, never recover omitted genes or measure biology; adds calls and held-out ranking evaluation |
| [Parallel questions](https://docs.typesafe.ai/cookbooks/parallel_questions) | One regulatory document, independent rubric dimensions | Noul/Choice/Score fan-out; state sent once | KEEP current Wide/Deep batching; never infer its published cost/speed ratio applies to LUAD |
| [Speculative fan-out](https://docs.typesafe.ai/patterns/fan-out) | Route plus branch-specific judgments on same available state | Independent questions with explicit premises; code consumes applicable branch | KEEP applicability; NEW action-value questions only over eligible held-data actions; no speculative evidence acquisition |
| [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring) | Reusable semantic dimensions under changing preferences | Persist raw scores, code combines weights | LATER optional ablation; keep current lexicographic policy; hard scientific gates never compensated by weighted score |
| [Confidence routing](https://docs.typesafe.ai/patterns/confidence-routing) | Ambiguous classification with review/stop alternatives | Choice/Score concentration or Noul ambiguity; code gates action | KEEP abstention; calibrate domain-specific false-admission/review tradeoff; no copied thresholds |
| [Hierarchy](https://docs.typesafe.ai/cookbooks/hierarchical_classification) | Document into large taxonomy using node Choices and beam alternatives | Code owns tree/search budget, path score and pruning; frontier questions batched | LATER ontology/literature annotation only; needless for two current actions; path scores are not calibrated leaf probabilities |
| [Evidence verification](https://docs.typesafe.ai/cookbooks/citation_check) | Claim, literal quote and source context | Code checks quote existence; Choice evaluates semantic support | EXPERIMENTAL generated-claim critique; exact numeric/hash checks stay deterministic; adds reviewed claim labels |
| [Passage classification](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) | Retrieved text with relevance, evidence, conflict and instruction hazards | Independent Nouls per pair; code separates evidence/conflict/exclusion | LATER if literature is separately admitted; no RAG/vector database now |
| [Semantic selection](https://docs.typesafe.ai/cookbooks/semantic_find) | Query against source lines/passages | Per-candidate judgments; code retains source span and selection/no-match | LATER ambiguous scientific text only; not required for GDC UUID lookup |
| [Entity alignment](https://docs.typesafe.ai/cookbooks/entity_alignment) | Candidate pairs of catalogue records, field agreements | Ordered Score plus companion Nouls; code handles merge/review | REJECT for exact GDC IDs/sample matching; LATER curated literature mentions, never automatic evidence merge |
| [Action selection](https://docs.typesafe.ai/cookbooks/function_calling) | Natural-language request -> fixed function/argument options | Choices/Nouls and speculative arguments; deterministic dispatcher | Adapt only semantic value of already eligible actions; REJECT model authorization, arbitrary query or reflective dispatcher framework |
| [Extraction cascade](https://docs.typesafe.ai/cookbooks/sde_cascade) | Cheap generated extraction -> field verification -> reasoning escalation | Per-field Nouls batched; code validates schema and chooses escalation | LATER for unstructured sources; REJECT replacing strict GDC parsing; adds generator costs and false-accept risk |
| [Noul consistency](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook) | Repeated insurance rubric on one claim | Repeated whole battery; code measures variability and ambiguity band | Evaluation-only: repeats near policy thresholds; no production majority-vote truth or cache-busting UID in scientific state |
| [Choice consistency](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook) | Borderline moderation labels across repeats | Full distributions and coverage/abstention comparison | Evaluation-only: report flips, not just average; confidence not independent evidence |
| [Guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails) | Message hazards plus severity | Noul hazards/Score severity; code applies noncompensating gates | EXPERIMENTAL overclaim/clinical-language review of generated text; never sole safety boundary |
| Escalation (confidence/cascade sources above) | Uncertain semantic judgment or verification failure | Code routes to human or separately authorized reasoning model | Human review first; bounded, recorded, no automatic paid escalation in this plan |

### Calibration and failure modes for every pattern

| Pattern | Uncertainty interpretation | Evaluation required / principal failure |
|---|---|---|
| Feature discovery | Semantic signals, not labels or observed facts | Grouped train/dev/held-out; feedback leakage and overfitting |
| Reranking | Pair relevance under same rubric | precision@k plus shortlist recall; selection bias/omitted positives |
| Parallel questions | Answers independent of siblings, not guaranteed identical across network repeats | Batched/unbatched equivalence and token limits; oversized state |
| Speculation | Ignore unused-branch uncertainty | Applicability/branch-premise tests; hypothetical answer treated as observed |
| Composite | Weighted utility, not probability unless separately modelled/calibrated | Weight/feature ablations; compensating away a serious violation |
| Confidence routing | Distribution concentration, not correctness | Reliability and risk-coverage curves; confident mistakes |
| Hierarchy | Local option competition, path heuristic | Leaf labels and node errors; early pruning and missing taxonomy options |
| Verification | Semantic support from supplied source | Blind support/contradiction/unsupported labels; topical similarity mistaken for support |
| Passage classification | Separate relevance/conflict/hazard propositions | Recall and false drops; unsafe or misleading text passed downstream |
| Semantic selection | Candidate-relative support plus no match | Candidate coverage and selected-span correctness; omitted candidate |
| Alignment | Similarity/identity judgment only | High-cost false-merge labels; aliases/conflated identities |
| Action selection | Semantic utility among deterministic eligible options | Review whether action reduces named uncertainty; eligibility confused with authorization |
| Cascade | Probability a proposed extraction is wrong | Field-level false acceptance and escalation rate; verifier and generator correlated errors |
| Noul/Choice consistency | Within-input variability, not external accuracy | Repeat variance/label flips with coverage; stable wrong answers |
| Guardrails | Hazard/rubric signals | Adversarial and clinical-overclaim false negatives; model guard bypass |
| Escalation | Unknown remains unknown pending review | Review workload, adjudication agreement and unresolved outcomes; forced conclusions |

Illustrative results retain their scope: feature discovery uses wine labels and jev-1.12; reranking
uses 40 CLERC queries/30-candidate lists and jev-1.12; parallel questions uses 13 questions over one
GDPR article and repeated jev-1.12 calls. None demonstrates cancer-discovery benefit.
Consistency notebooks include borderline flips even for TypeSafe. Do not copy their thresholds or
claim model determinism. Historical OntoJev measurements and scenario costs are in
[budgets](GDC_BUDGETS.md); prospective acceptance is in [testing](TESTING.md).

## Adoption boundaries

RETAIN current versions while typed contracts are introduced. PROPOSE separate experimental
discovery-semantic-v1 and deep-action-value-v1 artifacts, never a silent wide-v3/deep-v1 replacement.
New judgments must name a semantic uncertainty ordinary code cannot settle exactly. Exact eligibility,
missingness, sample compatibility, count arithmetic and evidence integrity are not model questions.
Clinical novelty, causal mechanism, druggability and survival benefit are REJECTED measured outputs.

Cache semantic features by scientific projection, full question definition and resolved pinned model,
not timestamp/run ID. Keep human labels and known cancer biology outside production selection and
blind calibration reviewers to method/ranking where feasible. Any automatic expansion waits for
incremental-value and resource-accounting gates.
