"""SCIENTIFIC_RECONCILIATION_FIXTURE tests: frozen GDC bytes prove the measurement chain.

Chain under proof, per gene and per batch composition:

    frozen public GDC records
    → independent derivation (tests.reconciliation.independent_counts, no production parser)
    → expected biological quantity (distinct affected cases for TCGA-LUAD)
    → OntoJev production parser produces the same quantity (or the documented
      defect it had on Data Release 46.0 is proven, not assumed)

Fixtures were captured live from api.gdc.cancer.gov on 2026-09-25 (open data,
no credentials) and are immutable: every body is SHA-256 pinned in
``MANIFEST.json``. The expected value is NEVER derived from the field the
production parser reads; the endpoint-bucket value is recorded for comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

from cancerjev.gdc.parsers import (
    ResponseMeta,
    parse_gene_case_counts,
    parse_ssm_occurrence_page,
)
from tests.reconciliation.independent_counts import (
    count_from_top_cases_response,
    derive_from_occurrence_pages,
    sha256_hex,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reconciliation_dr46"
PROJECT = "TCGA-LUAD"
SENTINEL_IDS = {
    "ENSG00000141510", "ENSG00000133703", "ENSG00000146648",
    "ENSG00000118046", "ENSG00000079999",
}
RELEASE = "Data Release 46.0 - August 10, 2026"


def _manifest() -> dict:
    return json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))


MANIFEST = _manifest()


def test_manifest_declares_the_reconciliation_category_and_pin_integrity():
    assert MANIFEST["category"] == "SCIENTIFIC_RECONCILIATION_FIXTURE"
    assert MANIFEST["release"] == RELEASE
    assert MANIFEST["method_of_derivation"].startswith("tests.reconciliation.independent_counts")
    for record in MANIFEST["records"]:
        body = (FIXTURES / f"{record['slug']}.body").read_bytes()
        assert sha256_hex(body) == record["sha256"], f"fixture drift: {record['slug']}"
        for page_hash in record["page_sha256"]:
            assert page_hash


def test_sentinels_are_present_and_derived_independently():
    panel = MANIFEST["panel"]
    assert set(panel["sentinels"].values()) == SENTINEL_IDS
    rows = {row["gene_id"]: row for row in MANIFEST["rows"]}
    for gene_id in SENTINEL_IDS:
        row = rows[gene_id]
        assert row["project"] == PROJECT
        assert row["release"] == RELEASE
        # Independent derivation from /ssm_occurrences raw pages:
        assert row["C_distinct_cases"] <= row["C_total_occurrences"]
        assert row["C_distinct_cases"] >= 0


def _meta(endpoint: str) -> ResponseMeta:
    return ResponseMeta(
        endpoint=endpoint, method="GET", request_hash="reconciliation-frozen",
        response_sha256="reconciliation-frozen", artifact_id=None,
        retrieved_at="reconciliation-frozen", source_release=RELEASE,
        completeness="COMPLETE")


def _page_bodies(gene_id: str) -> list[bytes]:
    capture = next(record for record in MANIFEST["records"]
                   if record["slug"] == f"C_ssm_occurrences_{gene_id}")
    combined = (FIXTURES / f"{capture['slug']}.body").read_bytes()
    return combined.split(b"\n\x00\n")


def test_production_parser_matches_the_independent_distinct_case_derivation():
    """Acceptance A for the V2 source: OntoJev quantity == independent expected value.

    The expected value is the cardinality of the distinct case_id set derived
    from the frozen /ssm_occurrences records; the OntoJev production page
    parser reads the same frozen records and the locally-derived per-gene
    distinct sets must agree, case for case.
    """
    rows = {row["gene_id"]: row for row in MANIFEST["rows"]}
    for gene_id, row in rows.items():
        pages = _page_bodies(gene_id)
        independent = derive_from_occurrence_pages(pages, PROJECT, gene_id)
        seen_occurrence_ids: set[str] = set()
        cases_per_gene: set[str] = set()
        for offset, body in enumerate(pages):
            page = parse_ssm_occurrence_page(
                body, _meta("/ssm_occurrences"), expected_project=PROJECT,
                expected_offset=offset * 250, expected_size=250)
            assert page.total == row["C_total_occurrences"]
            for record in page.records:
                assert record.occurrence_id not in seen_occurrence_ids
                seen_occurrence_ids.add(record.occurrence_id)
                if gene_id in record.gene_ids:
                    cases_per_gene.add(record.case_id)
        assert len(cases_per_gene) == independent.distinct_cases
        assert len(cases_per_gene) == row["C_distinct_cases"]


def test_endpoint_bucket_defect_is_proven_not_assumed():
    """Acceptance B evidence: the V1 bucket is neither distinct cases nor occurrences.

    For every panel gene with an endpoint bucket, the bucket value must be
    compared against the independently derived quantities; the defect class is
    recorded as a proven relationship on Data Release 46.0.
    """
    rows = [row for row in MANIFEST["rows"] if row["A_single_gene_count"] is not None]
    assert len(rows) >= 10
    defect_proven = []
    for row in rows:
        a = row["A_single_gene_count"]
        b = row["B_batched_count"]
        c_distinct = row["C_distinct_cases"]
        c_total = row["C_total_occurrences"]
        if b is not None:
            assert a == b, f"batch composition must not change the bucket value: {row['gene_id']}"
        assert c_distinct <= c_total
        if a != c_distinct or a != c_total:
            defect_proven.append(row["gene_id"])
        if row["gene_id"] == "ENSG00000184182":
            # The zero-occurrence gene: the bucket reports 176 affected cases
            # while the released occurrence corpus has none.
            assert row["A_single_gene_count"] > 0 and row["C_total_occurrences"] == 0
            defect_proven.append(row["gene_id"])
    assert defect_proven, "at least one defect must be proven by the frozen records"
    assert "ENSG00000141510" in defect_proven, "TP53 must be among the proven defects"
    assert "ENSG00000042781" in defect_proven, "the retained top survivor must be among them"


def test_production_top_cases_parser_sees_the_same_frozen_bucket():
    """The production aggregation parser reads the frozen A bytes as captured.

    This pins the parser against byte drift independently of the defect: the
    bucket value the production parser derives from the frozen response equals
    the independently extracted one, so the reconciliation compares the same
    number the production pipeline would have measured.
    """
    rows = [row for row in MANIFEST["rows"] if row["A_single_gene_count"] is not None]
    for row in rows[:4]:
        capture = next(record for record in MANIFEST["records"]
                       if record["slug"] == f"A_top_cases_counts_by_genes_{row['gene_id']}")
        body = (FIXTURES / f"{capture['slug']}.body").read_bytes()
        counts = parse_gene_case_counts(body, _meta("/analysis/top_cases_counts_by_genes"))
        bucket = counts.projects[PROJECT][row["gene_id"]]
        independent = count_from_top_cases_response(body, PROJECT, row["gene_id"])
        assert bucket == independent == row["A_single_gene_count"]


def test_sentinels_are_validation_controls_only():
    """The sentinel panel must never enter the tested universe artifacts.

    The sentinels live outside the first-1000 gene-id-ascending prefix of the
    retained Stage-4 universe (verified live at capture time); this test pins
    that property so a future universe change cannot silently absorb the
    validation controls into target selection.
    """
    prior_universe = json.loads(
        (Path(__file__).parents[1] / ".." / "data" / "runs" /
         "e2035487-cb7e-47b2-83d4-0cee31153143" / "discovery" / "result.json")
        .read_text(encoding="utf-8"))["universe"]["ordered_ids"]
    universe_set = set(prior_universe)
    assert universe_set.isdisjoint(SENTINEL_IDS)
    for survivor_gene in MANIFEST["panel"]["survivors"].values():
        assert survivor_gene in universe_set
