# Functional / external source decision record

Status: **DECIDED 2026-09-26 — all candidate sources DEFERRED**. No download, adapter or
evidence axis is adopted this cycle; only the recorded classification and separation of
axes are kept. Adoption requires a declared functional question, verified current terms,
a bounded mapping snapshot and the standard acquisition preflight.

## Axes (never collapsed)

`GENOMIC_DISCOVERY` · `STATISTICAL_SUPPORT` · `REPLICATION` · `FUNCTIONAL_DEPENDENCY` ·
`KNOWN_CANCER_CONTEXT` · `TARGETABILITY` · `CLINICAL_EVIDENCE`

Pan-cancer dependency is never cohort-specific support; dependency is not therapeutic
efficacy; known-gene status is not proof of a target in this cohort.

## Candidates evaluated

| Source | Access | Licence state | Mapping fidelity | Roles | Decision |
|---|---|---|---|---|---|
| DepMap CRISPR dependency (depmap.org) (`DEPMAP_CRISPR`) | portal bulk files require registration | current terms must be re-verified at adoption time; not verified this cycle | gene-symbol based; Ensembl mapping artefact would be required | `FUNCTIONAL_DEPENDENCY` (follow-up only) | **DEFER** |
| Sanger Cancer Gene Census (cancer.sanger.ac.uk/census) (`SANGER_CGC`) | download | academic licence terms | gene-symbol based | `KNOWN_CANCER_CONTEXT` | **DEFER** (note: the GDC-derived `is_cancer_gene_census` flag is **not** Sanger CGC licensing and is used only as GDC project metadata with role `KNOWN_CANCER_CONTEXT`) |
| Targetability resources (ChEMBL / Open Targets / DrugBank) (`TARGETABILITY_RESOURCES`) | API or download, mixed terms | mixed, must be verified | mixed identifiers | `TARGETABILITY` | **DEFER** |
| Independent compatible cohort (external replication) (`INDEPENDENT_COHORT_REPLICATION`) | GDC or another open repository | open-access only; a second validated campaign is required first | cohort-dependent | `REPLICATION` | **DEFER** (needs a separately validated independent campaign; the P16 machinery only sequences campaigns) |

## Consequences in code

- `domain/functional.py` holds the typed posture (`functional-sources-v1`): every candidate
  decision is `DEFER`, the axis vocabulary is declared, and a test verifies this record
  matches the constants.
- No functional adapter, action or evidence field is implemented; nothing can produce
  `FUNCTIONALLY_SUPPORTED` (the maturity derivation records the missing contract), and Jev
  cannot manufacture functional evidence.
- Re-evaluation trigger: a declared functional or external-replication question, plus a
  verified licence/access record and a bounded, hashed mapping snapshot evaluated under
  the same acquisition gates as every other source.
