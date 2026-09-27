# Functional / external source decision record

Status: **DECIDED 2026-09-26 — decision record version `1`; all candidate sources
DEFERRED**. No download, adapter or evidence axis is adopted this cycle; only the
recorded classification and separation of axes are kept. Adoption requires a
declared functional question, verified current terms, a bounded mapping snapshot
and the standard acquisition preflight.

## Axes (never collapsed)

`GENOMIC_DISCOVERY` · `STATISTICAL_SUPPORT` · `REPLICATION` · `FUNCTIONAL_DEPENDENCY` ·
`KNOWN_CANCER_CONTEXT` · `TARGETABILITY` · `CLINICAL_EVIDENCE`

Pan-cancer dependency is never cohort-specific support; dependency is not therapeutic
efficacy; known-gene status is not proof of a target in this cohort.

## Candidates evaluated

| Source | Access | Licence state | Mapping fidelity | Roles | Decision |
|---|---|---|---|---|---|
| DepMap CRISPR dependency (depmap.org) (`DEPMAP_CRISPR`) | portal bulk files require registration | **verified 2026-09-27:** Broad-generated data CC BY 4.0; the portal terms additionally state commercial use is not permitted without a separate licence (forum.depmap.org, depmap.org) — a licence barrier for unrestricted use | gene-symbol based; Ensembl mapping artefact would be required | `FUNCTIONAL_DEPENDENCY` (follow-up only) | **DEFER** |
| Sanger Cancer Gene Census (cancer.sanger.ac.uk/census) (`SANGER_CGC`) | download after registration | **verified 2026-09-27:** COSMIC/CGC non-commercial registered-user terms; commercial use via QIAGEN (cancer.sanger.ac.uk/cosmic/download, COSMIC non-commercial licence) — registered, non-commercial, not unrestricted open access | gene-symbol based | `KNOWN_CANCER_CONTEXT` | **DEFER** (note: the GDC-derived `is_cancer_gene_census` flag is **not** Sanger CGC licensing and is used only as GDC project metadata with role `KNOWN_CANCER_CONTEXT`) |
| Targetability resources (ChEMBL / Open Targets / DrugBank) (`TARGETABILITY_RESOURCES`) | API or download, mixed terms | **verified 2026-09-27:** Open Targets Platform data CC0 1.0 with per-source terms for embedded datasets (platform-docs.opentargets.org/licence); ChEMBL CC BY-SA 3.0 Unported, attribution with URL + release (ChEMBL_37, 2026-05-01, ebi.ac.uk/chembl); UniProt CC BY 4.0; DrugBank CC BY-NC 4.0 (non-commercial) | mixed identifiers | `TARGETABILITY` | **DEFER** (adoptable candidates restricted to CC0/CC BY/CC BY-SA terms; DrugBank excluded as non-commercial) |
| Independent compatible cohort (external replication) (`INDEPENDENT_COHORT_REPLICATION`) | GDC or another open repository | open-access only; a second validated campaign is required first | cohort-dependent | `REPLICATION` | **DEFER** (needs a separately validated independent campaign; the P16 machinery only sequences campaigns) |

## Licence verification record (2026-09-27)

Evidence gathered from the sources' own licensing pages; recorded so an adoption
decision starts from verified terms instead of "must be re-verified":

| Source | Licence/terms | Evidence URL |
|---|---|---|
| Open Targets Platform (data) | CC0 1.0; per-source terms apply to embedded datasets (ChEMBL CC BY-SA 3.0, HPA CC BY-SA 3.0, CGC commercial-for-OT) | `https://platform-docs.opentargets.org/licence` |
| ChEMBL (current release ChEMBL_37) | CC BY-SA 3.0 Unported; cite resource URL and release version | `https://www.ebi.ac.uk/chembl/g`, `https://chembl.github.io/chembl-licensing` |
| UniProt | CC BY 4.0 | `https://platform-docs.opentargets.org/licence` (source table) |
| DepMap | CC BY 4.0 for Broad-generated data; portal terms exclude commercial use without a separate licence | `https://forum.depmap.org/t/license-for-data-found-in-the-depmap-portal/130`, `https://depmap.org/` |
| Sanger CGC / COSMIC | registered non-commercial licence terms; commercial via QIAGEN | `https://cancer.sanger.ac.uk/cosmic/download`, `https://cancer.sanger.ac.uk/cosmic/terms` |
| DrugBank | CC BY-NC 4.0 (non-commercial) | `https://go.drugbank.com/legal/terms_of_use` (via PubChem source listing) |

None of this changes any `DEFER`: adoption still requires a declared functional
question, a bounded hashed mapping snapshot and a consumer; the verification only
removes the "terms unknown" state for the named candidates.

## Consequences in code

- `domain/functional.py` holds the typed posture (decision record version `1`, matching `FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION`): every candidate
  decision is `DEFER`, the axis vocabulary is declared, and a test verifies this record
  matches the constants.
- No functional adapter, action or evidence field is implemented; nothing can produce
  `FUNCTIONALLY_SUPPORTED` (the maturity derivation records the missing contract), and Jev
  cannot manufacture functional evidence.
- Re-evaluation trigger: a declared functional or external-replication question, plus a
  verified licence/access record and a bounded, hashed mapping snapshot evaluated under
  the same acquisition gates as every other source.
