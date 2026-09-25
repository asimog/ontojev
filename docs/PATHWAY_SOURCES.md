# Pathway source decision record

Status: **DECIDED 2026-09-25** for membership-only descriptive evidence. No enrichment
or significance claim is implemented or implied by this decision.

## Candidates evaluated

| Source | Licence | Versioning | Ensembl gene-id mapping | TCGA/GDAN precedent | Decision |
|---|---|---|---|---|---|
| Reactome | CC-BY 4.0 (attribution) | versioned releases, stable `R-HSA-*` identifiers | native `Ensembl2Reactome` mapping files keyed by Ensembl gene ID | pathway-level TCGA analyses commonly use Reactome | **ADOPT (membership only)** |
| MSigDB | academic licence terms, redistribution restricted | versioned releases | gene-symbol based; symbol→Ensembl mapping required | widely used for enrichment | DEFER: licence review plus an explicit, hashed symbol-mapping artefact needed before adoption |
| Gene Ontology | CC-BY 4.0 | continuous releases, large | GO-to-Ensembl mapping needed | common background resource | DEFER: mapping and size review exceeds this cycle's bounded snapshot budget |

## Adopted source and snapshot

- Source: Reactome, `https://reactome.org/download/current/Ensembl2Reactome.txt`
  (top-level pathways, all species), retrieved **2026-09-25**.
- Filter: rows whose species column equals `Homo sapiens` only; no other transformation.
- Snapshot: 381,765 rows, 53,124,015 bytes, SHA-256
  `c35b05d6f303a29bcea8dab80bf7de926791ecb83f1b8037574358ed99f74403`.
- Retention: `data/pathways/reactome-ensembl-top-level-homo-sapiens-2026-09-25.txt`
  (untracked data directory; the hash above is the version of record).
- Identifier fidelity check: the adopted snapshot's TP53 (`ENSG00000141510`) rows
  (48 memberships, retained as a committed fixture) are compared against the live
  Reactome Content Service `mapping/ENSEMBL/ENSG00000141510/pathways?species=9606`
  response captured the same day; the contract test requires an exact identifier-set
  match.
- Granularity: top-level pathways only, so counts are not inflated by sub-pathway
  inclusion (the `All_Levels` file is deliberately not used).

## Constraints carried into code

- Membership is external deterministic data: source, version, licence reference,
  mapping method and snapshot hash are recorded on every membership artifact; there
  is no runtime membership mutation and no network call at analysis time.
- No membership is never a negative result: an unmapped gene carries an explicit
  `NO_PATHWAY_MEMBERSHIP_OBSERVED` limitation, never a claim of absence.
- Enrichment background, if ever implemented, must be the actual tested/mapped
  universe under a separately declared null/FDR contract; it is **DEFERRED**.
- Cross-modal pathway analysis additionally requires a declared compatible assay
  intersection and sample mapping; it is **DEFERRED**.
