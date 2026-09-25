# OntoJev development skills

Development-guidance map for the current architecture (2026-09-25). This document improves
development guidance only. GDC remains the sole scientific runtime source; skills do not expand
source or method admission and are not runtime dependencies or acquisition authority.

## Existing environment and configuration

| Resource | Verified availability | Decision |
|---|---|---|
| OpenAI NGS Analysis | Installed plugin; core and on-demand skills readable locally | Reuse selected guidance; no installation |
| OpenAI Life Science Research | Installed plugin, including research router and database skills | Explicit-request, reference-only; no external scientific retrieval |
| Official TypeSafe skill | Available in the user skill directories; copies read as identical | Reuse; do not add, delete or alter the installed copies |

Other installed scientific database/literature plugins are not selected providers or default
workflows. The same no-retrieval rule applies regardless of which plugin exposes a database
skill. Availability is distinct from invocation: a skill being listed does not authorize its
scripts, installs or network calls. Project instructions are not an OS/network sandbox and do not
hide globally installed skills; no technical enforcement beyond existing runtime guards is
claimed. No external skill content is vendored; this document is an OntoJev-specific usage map.

## Core guidance and roadmap map

Core means preferred when relevant, not a requirement to load every skill on every task. Use the
installed namespaced NGS skills when explicitly selecting them.

| Skill | Useful guidance | Boundary |
|---|---|---|
| `ngs-runtime-env` | Registered scientific actions: eligibility, preflight, reproducibility, software readiness separate from reference/evidence readiness | Use design principles; no pipeline preflight scripts, installs or reference downloads are required by OntoJev |
| `ngs-dna-somatic-variants` | Mutation/broad-universe and CNV survivor review: tumor/normal context, caller/QC, contamination, depth and allele-fraction limitations | No BAM/CRAM variant calling; do not infer unavailable QC or callable negatives |
| `ngs-dna-variant-calling` | Mutation contracts: identifiers, reference/coordinate compatibility, filtering semantics and provenance | GDC contracts govern; no routing into germline/UMI workflows |
| `ngs-bulk-rnaseq` | Expression lane: distinguish raw counts, normalized expression and transformed values | Case-labelled GDC UQFPKM is not a FASTQ/raw-count workflow |
| `ngs-bulk-rnaseq-counts-qc` | Expression lane and empirical tails: matrix/sample identity, missingness, units and assay provenance | Missing is not zero; case IDs do not prove matched tumor aliquots; no quantification pipeline |
| `ngs-bulk-rnaseq-differential-expression` | Guard against invalid contrasts, replication, confounding and inappropriate input scales | Design reference only; empirical within-gene tails are descriptive, not DE; cross-lane inferential associations remain ineligible |
| `ngs-fastq-qc` | General QC: preserve inputs, distinguish assay artifacts from biology, retain limitations | No FASTQ acquisition, trimming or processing |
| `typesafe-ai` | Jev projections, questions/primitives, Wide/Deep judgments, hypothesis critique, semantic features, reranking, confidence routing and calibration | Mandatory relevant guidance plus current live docs; exact questions stay in code/statistics; no automatic paid calls |

Roadmap Stages 0–3 (scientific contracts, verified consumption, typed lane composition) are
IMPLEMENTED and offline-verified. Stage 4 (indexed systematic discovery) is the next separately
authorized task; Stages 5–8 use mutation/expression/CNV and TypeSafe evaluation guidance. See
[roadmap](DISCOVERY_ROADMAP.md), [contracts](DOMAIN_MODELS.md), [GDC strategy](GDC_STRATEGY.md),
[budgets](GDC_BUDGETS.md), [invariants](SCIENTIFIC_INVARIANTS.md) and [testing](TESTING.md).
Existing acceptance gates and ceilings are unchanged, and skill guidance does not authorize
discovery lanes, new endpoints or paid calls.

## On-demand and excluded workflows

Keep these available, but load only for a later explicitly approved GDC capability:
`ngs-scrna-seq`, `scrna-seq-qc`, `ngs-epigenomics-peaks`, `ngs-atacseq-peaks-qc` and
`ngs-chip-cutrun-peaks-qc`. Their installation does not admit scRNA or epigenomics now.

Do not use these as normal OntoJev development workflows: `ngs-bcl-to-fastq`,
`ngs-dna-germline-variants`, `ngs-dna-umi-panel-variants`, `ngs-amplicon-microbiome` and
`ngs-shotgun-metagenomics`. They remain installed globally; this document does not disable them
elsewhere. The general NGS router is not an additional default requirement; choose relevant
guidance directly.

Life Science Research, including its research router, is explicit-request/reference-only. Use
conceptual guidance for terminology, assay context, research-question decomposition, hypothesis
structure and caveats. Do not follow its external entity-resolution, evidence-gathering or
database-routing steps for OntoJev. No PubMed/PMC/bioRxiv, cBioPortal, Reactome, STRING, UniProt,
Open Targets, GTEx or other non-GDC scientific source is admitted. Runtime hypothesis inputs
remain GDC-derived EvidenceState; developer background knowledge must not become fabricated
measured facts.

## Boundary reminders

- Mutation review does not launch variant calling; expression tails do not become differential
  expression; hypothesis review does not retrieve external evidence.
- Jev work requires its skill/live docs and cannot replace deterministic measurement. If
  deterministic code or classical statistics can answer exactly, do not use Jev.
- Registered actions do not acquire data, call models or compute new biological quantities; a
  measurement-producing or acquisition-capable action needs its own explicit contract, budget
  reservation and acceptance gate.
- Generated hypothesis text is never evidence and never writes a measured field.