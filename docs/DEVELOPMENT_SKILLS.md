# OntoJev development skills

Development-guidance map for the current architecture (2026-09-25, starting HEAD `97272ae`). This
document improves development guidance only. GDC remains the sole scientific runtime source; skills
do not expand source or method admission and are not runtime dependencies or acquisition authority.

## Verified environment and installation

Skill-level enablement was used. The `ngs-analysis` plugin itself is not installed, so no plugin
scripts, hooks, MCP servers or app connectors are active; only the selected `SKILL.md` guidance is
on disk. Nothing is vendored into this repository.

| Resource | Verified state | Decision |
|---|---|---|
| NGS Analysis core skills | Seven skills installed from `openai/plugins` (plugin v1.0.3, MIT) for Codex (`~/.codex/skills/`) and Kilo (`~/.config/kilo/skills/`); listed by `codex debug prompt-input` | Reuse selected guidance; no plugin-level install |
| NGS Analysis on-demand skills | Not installed; one-command enable below | Enable only for a later explicitly approved GDC capability |
| NGS Analysis router and non-OntoJev workflows | Not installed | Do not install (see excluded list) |
| Life Science Research | Plugin not installed; skills readable upstream as an explicit-request reference | Reference-only; never a default workflow; no external scientific retrieval |
| Official TypeSafe skill | Installed at `~/.agents/skills/typesafe-ai` (Codex-visible) and `~/.config/kilo/skills/typesafe-ai` (Kilo-visible), from `typesafe-ai/skills` | Mandatory for Jev work; do not alter the installed copies |

Installed-skill provenance: `openai/plugins` `main` at `1dc195897af4161d039b80d8471ec0a10c9bbc89`
(2026-09-11), plugin version 1.0.3, MIT. The upstream text describes pipelines and tools that
OntoJev does not run; it is guidance, not admission.

### Reproducing or updating the install

The official Codex `skill-installer` script fetches individual skills with a sparse git checkout:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo openai/plugins --method git `
  --dest "$env:USERPROFILE\.config\kilo\skills" `  # omit --dest for Codex ($CODEX_HOME/skills)
  --path plugins/ngs-analysis/skills/ngs-runtime-env `
         plugins/ngs-analysis/skills/ngs-dna-somatic-variants `
         plugins/ngs-analysis/skills/ngs-dna-variant-calling `
         plugins/ngs-analysis/skills/ngs-bulk-rnaseq `
         plugins/ngs-analysis/skills/ngs-bulk-rnaseq-counts-qc `
         plugins/ngs-analysis/skills/ngs-bulk-rnaseq-differential-expression `
         plugins/ngs-analysis/skills/ngs-fastq-qc
```

The installer aborts when a destination skill directory already exists; update by removing that
directory and re-running, or by pinning a reviewed upstream ref. No automatic update, plugin
install, package install or pipeline run is performed by this repository. There is no
project-local skill copy: project instructions are not an OS/network sandbox and do not hide
globally installed skills; no technical enforcement beyond existing runtime guards is claimed.

## Core guidance and roadmap map

Core means preferred when relevant, not a requirement to load every skill on every task.

| Skill | Useful guidance | Boundary |
|---|---|---|
| `ngs-runtime-env` | Stage 7 registered scientific actions: eligibility/preflight, software-versus-evidence readiness separation, fail-closed execution, reproducibility, provenance | Use design principles; OntoJev runs no pipeline preflight script, install or reference download |
| `ngs-dna-somatic-variants` | Stage 4 bounded broad-universe mutation work and Stage 6 CNV survivor review: tumor context, caller/QC, contamination, depth and allele-fraction limitations | No BAM/CRAM variant calling; do not infer unavailable QC, callable negatives or neutral CNV |
| `ngs-dna-variant-calling` | Stage 4 mutation contract design: identifiers, reference/coordinate compatibility, filtering semantics, provenance | GDC contracts govern; no routing into germline or UMI workflows |
| `ngs-bulk-rnaseq` | Stage 5 expression arm: distinguish raw counts, normalized expression and transformed values | Case-labelled GDC UQFPKM is not a FASTQ/raw-count workflow |
| `ngs-bulk-rnaseq-counts-qc` | Stage 5 expression lane and empirical-tail descriptor: matrix/sample identity, missingness, units, coverage, assay provenance | Missing is not zero; case IDs do not prove matched tumor aliquots; no quantification pipeline |
| `ngs-bulk-rnaseq-differential-expression` | Guard against invalid contrasts, replication, confounding and input scales, and against misclassifying the within-gene empirical tail as differential expression | Design reference only; empirical tails are descriptive, not DE; cross-lane inferential associations remain ineligible (Stage 9) |
| `ngs-fastq-qc` | General QC/provenance design reference: preserve inputs, separate assay artifacts from biology, retain limitations | No FASTQ acquisition, trimming or processing |
| `typesafe-ai` | Jev projections, questions/primitives, Wide/Deep judgments, hypothesis critique, semantic features, reranking, confidence routing and calibration | Mandatory relevant guidance plus current live docs; exact questions stay in code/statistics; no automatic paid calls |

Roadmap Stages 0–8 (through the bounded broad universe, independent expression arm,
survivor-only CNV lane, cutover with held-data descriptor actions and the offline prospective
protocol validator) are IMPLEMENTED and offline-verified. Stage 9
(conditional inferential extensions) is deferred. See [roadmap](DISCOVERY_ROADMAP.md),
[contracts](DOMAIN_MODELS.md), [GDC strategy](GDC_STRATEGY.md), [budgets](GDC_BUDGETS.md),
[invariants](SCIENTIFIC_INVARIANTS.md) and [testing](TESTING.md). Skill guidance does not
authorize discovery lanes, new endpoints or paid calls.

## On-demand and excluded skills

Not installed; enable only for a later explicitly approved GDC capability (add the path to the
install command above): `ngs-scrna-seq`, `scrna-seq-qc`, `ngs-epigenomics-peaks`,
`ngs-atacseq-peaks-qc` and `ngs-chip-cutrun-peaks-qc`. Enabling one does not admit scRNA or
epigenomics now.

Do not install or use: `ngs-bcl-to-fastq`, `ngs-dna-germline-variants`,
`ngs-dna-umi-panel-variants`, `ngs-amplicon-microbiome` and `ngs-shotgun-metagenomics`. The
`ngs-analysis-router` is not an additional default requirement; choose relevant guidance directly.

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

## Verification record (2026-09-25)

- Starting HEAD `97272ae`; working tree clean apart from this document.
- Kilo: seven core skills present under `~/.config/kilo/skills/<name>/SKILL.md` with valid
  `name`/`description` frontmatter (Kilo's `{skill,skills}/<name>/SKILL.md` discovery pattern);
  `typesafe-ai` unchanged.
- Codex: `codex debug prompt-input` lists the seven core skills plus `typesafe-ai`.
- No plugin-level install: neither `ngs-analysis` nor `life-science-research` is in the Codex
  plugin cache; no plugin script, MCP server or app connector was activated.
- No production dependency, Python package, endpoint, model call, `cancerjev/` change or
  `apps/web/` change; `pyproject.toml` is untouched and the offline suite (652 tests) passed with
  no failures (a pytest temp-directory cleanup warning on Windows is environmental).
