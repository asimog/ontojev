# OntoJev development skills

Configured through project instructions on 2026-09-25, starting from clean `main` at
`0ed13f547323bd7ff42247fb038258d858eda5c2`. This setup improves development guidance only.
GDC remains the sole scientific runtime source; skills do not expand source or method admission.

## Existing environment and configuration

| Resource | Verified availability | Decision |
|---|---|---|
| OpenAI NGS Analysis 1.0.3 | Installed plugin; all seven core and five on-demand skills below available in this session and readable locally | Reuse selected guidance; no installation |
| OpenAI Life Science Research 1.0.3 | Installed plugin, including research router and database skills | Explicit-request, reference-only; no external scientific retrieval |
| Official TypeSafe skill | Available in both user `.agents/skills/typesafe-ai` and `.codex/skills/typesafe-ai`; SKILL.md files have identical SHA-256 | Reuse; do not add, delete or alter either copy |

The OpenAI plugins reside in the existing Codex `plugins/cache/openai-curated-remote/` cache;
the selected versions are 1.0.3. No plugin cache, global configuration or permissions were changed.
Other installed scientific database/literature plugins are not selected providers or default workflows.
The same no-retrieval rule applies regardless of which plugin exposes a database skill.

The supported plugin and skill mechanisms were reviewed during planning:
[official plugin guidance](https://developers.openai.com/plugins/build/plugins) and
[local skill controls](https://learn.chatgpt.com/docs/build-skills). This task deliberately uses
[AGENTS.md](../AGENTS.md), not global skill disabling, plugin removal or a custom loader.
Availability is distinct from invocation: a skill being listed does not authorize its scripts,
installs or network calls. Project instructions are not an OS/network sandbox and do not hide
globally installed skills from Codex. No technical enforcement beyond existing runtime guards is claimed.
No external skill content is vendored; this document is an OntoJev-specific usage map.

## Core guidance and roadmap map

Core means preferred when relevant, not a requirement to load every skill on every task.
Use the installed namespaced NGS skills (`ngs-analysis:<name>`) when explicitly selecting them.

| Skill | Development stage / useful guidance | Boundary |
|---|---|---|
| `ngs-runtime-env` | Registered scientific actions: eligibility, preflight, reproducibility, software readiness separate from reference/evidence readiness | Use design principles; no pipeline preflight scripts, installs or reference downloads are required by OntoJev |
| `ngs-dna-somatic-variants` | Mutation/broad-universe and CNV survivor review: tumor/normal context, caller/QC, contamination, depth and allele-fraction limitations | No BAM/CRAM variant calling; do not infer unavailable QC or callable negatives |
| `ngs-dna-variant-calling` | Mutation contracts: identifiers, reference/coordinate compatibility, filtering semantics and provenance | GDC contracts govern; no routing into germline/UMI workflows |
| `ngs-bulk-rnaseq` | Expression lane: distinguish raw counts, normalized expression and transformed values | Case-labelled GDC UQFPKM is not a FASTQ/raw-count workflow |
| `ngs-bulk-rnaseq-counts-qc` | Expression lane and empirical tails: matrix/sample identity, missingness, units and assay provenance | Missing is not zero; case IDs do not prove matched tumor aliquots; no quantification pipeline |
| `ngs-bulk-rnaseq-differential-expression` | Guard against invalid contrasts, replication, confounding and inappropriate input scales | Design reference only; empirical within-gene tails are descriptive, not DE; cross-lane inferential associations remain ineligible |
| `ngs-fastq-qc` | General QC: preserve inputs, distinguish assay artifacts from biology and retain limitations | No FASTQ acquisition, trimming or processing |
| `typesafe-ai` | All Jev projections, questions/primitives, Wide/Deep judgments, hypothesis critique, semantic features, reranking, confidence routing and calibration | Mandatory relevant guidance plus current live docs; exact questions stay in code/statistics; no automatic paid calls |

Roadmap stages 1–3 (scientific types, versioned readers and lane composition) remain normal Python
engineering. Use NGS references only when scientific semantics matter; do not replace typed
constructors, direct parsers, deterministic tests or explicit dependency seams with workflow tooling.
Stages 4–6 use mutation/expression/CNV guidance above; stages 7–8 use action preflight and TypeSafe
evaluation guidance. See [roadmap](DISCOVERY_ROADMAP.md), [contracts](DOMAIN_MODELS.md),
[GDC strategy](GDC_STRATEGY.md), [budgets](GDC_BUDGETS.md), [invariants](SCIENTIFIC_INVARIANTS.md)
and [testing](TESTING.md). Existing acceptance gates and ceilings are unchanged.

## On-demand and excluded workflows

Keep these available, but load only for a later explicitly approved GDC capability:
`ngs-scrna-seq`, `scrna-seq-qc`, `ngs-epigenomics-peaks`, `ngs-atacseq-peaks-qc` and
`ngs-chip-cutrun-peaks-qc`. Their installation does not admit scRNA or epigenomics now.

Do not use these as normal OntoJev development workflows: `ngs-bcl-to-fastq`,
`ngs-dna-germline-variants`, `ngs-dna-umi-panel-variants`, `ngs-amplicon-microbiome` and
`ngs-shotgun-metagenomics`. They remain installed globally; this task does not disable them elsewhere.
The general NGS router is not an additional default requirement; choose relevant guidance directly.

Life Science Research, including `research-router-skill`, is explicit-request/reference-only.
Use conceptual guidance for terminology, assay context, research-question decomposition,
hypothesis structure and caveats. Do not follow its external entity-resolution, evidence-gathering
or database-routing steps for OntoJev. No PubMed/PMC/bioRxiv, cBioPortal, Reactome, STRING, UniProt,
Open Targets, GTEx or other non-GDC scientific source is admitted. Runtime hypothesis inputs remain
GDC-derived EvidenceState; developer background knowledge must not become fabricated measured facts.

## Verification and handoff

- Rechecked starting HEAD/main and clean worktree before edits; selected NGS skill files and plugin
  manifests are readable, and the two TypeSafe skill files remain byte-identical.
- Only AGENTS.md and this document changed; runtime APIs/scientific types, dependency manifests,
  tests, CI and frontend are unchanged. Global Codex configuration hash is unchanged.
- Local Markdown links and `git diff --check` pass. The AGENTS addition is 19 lines including its
  heading and blank lines; the detailed catalog stays here.
- Manual rule review: mutation review does not launch calling; expression tails do not become DE;
  hypothesis review does not retrieve external evidence; Jev work requires its skill/live docs and
  cannot replace deterministic measurement. This is an instruction review, not a behavioral model eval.
- No plugins added or globally enabled/disabled; no NGS executables/dependencies installed; no
  scientific API or paid-model calls; no pipeline scripts run; no commit or push.
- No fresh scientific test-suite run is claimed for this documentation-only change.

Next separately authorized task: implement roadmap Stage 1 scientific contracts and versioned
readers, preserving existing behavior and historical artifact identities. Do not begin discovery
lanes or relax scientific admission gates as part of that task.
