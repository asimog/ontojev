from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cancerjev.gdc.parsers import (
    ParserError,
    ResponseMeta,
    parse_cases,
    parse_expression_availability,
    parse_expression_values,
    parse_files_provenance,
    parse_gene_case_counts,
    parse_gene_selection,
    parse_genes,
    parse_mutated_cases_count,
    parse_projects,
    parse_status,
    parse_top_mutated_genes,
    response_warnings,
)

FIXTURES = Path(__file__).parent / "fixtures" / "gdc"


def load(name: str) -> tuple[bytes, ResponseMeta]:
    body = (FIXTURES / f"{name}.body").read_bytes()
    meta = json.loads((FIXTURES / f"{name}.meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(body).hexdigest() == meta["body_sha256"], f"fixture {name} bytes changed"
    return body, ResponseMeta(
        endpoint=meta["endpoint"], method=meta["method"], request_hash="fixture",
        response_sha256=meta["body_sha256"], artifact_id=None, retrieved_at=meta["retrieved_at"],
        source_release="Data Release 46.0 - August 10, 2026", completeness="COMPLETE",
    )


def meta_for(endpoint: str, completeness: str = "COMPLETE") -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="GET", request_hash="synthetic", response_sha256="x",
                        artifact_id=None, retrieved_at="2026-09-22T00:00:00Z", source_release=None,
                        completeness=completeness)


def test_real_status_capture():
    status = parse_status(*load("status"))
    assert status.data_release == "Data Release 46.0 - August 10, 2026"
    assert status.tag == "8.5.0"
    assert status.status == "OK"
    assert status.commit and len(status.commit) == 40


def test_real_projects_capture():
    projects = parse_projects(*load("projects_small"))
    assert len(projects) == 3
    by_id = {project.project_id: project for project in projects}
    assert set(by_id) == {"TCGA-LUAD", "ALCHEMIST-ALCH", "MATCH-S1"}
    luad = by_id["TCGA-LUAD"]
    assert luad.case_count == 585
    assert luad.program_name == "TCGA"
    assert luad.disease_type
    assert "Transcriptome Profiling" in luad.data_categories
    assert by_id["MATCH-S1"].case_count == 41


def test_real_cases_capture_surfaces_field_warnings():
    body, meta = load("cases_small")
    page = parse_cases(body, meta)
    assert len(page.cases) == 2
    assert all(case.project_id == "TCGA-BRCA" for case in page.cases)
    assert any("demographic.gender" in warning for warning in page.warnings)
    assert response_warnings(body, meta)


def test_real_case_frame_capture_is_complete_and_ordered():
    page = parse_cases(*load("cases_250_sorted"))
    assert page.complete is True
    assert len(page.cases) == 51
    assert all(case.project_id == "TCGA-CHOL" for case in page.cases)
    ids = [case.case_id for case in page.cases]
    assert ids == sorted(ids)
    assert page.offset == 0
    assert page.size == 250


def test_case_parser_preserves_explicit_zero_count():
    body, meta = load("cases_small")
    document = json.loads(body)
    document["data"]["pagination"]["count"] = 0
    page = parse_cases(json.dumps(document).encode(), meta)
    assert page.count == 0


def test_case_parser_rejects_malformed_pagination_types():
    body, meta = load("cases_small")
    document = json.loads(body)
    document["data"]["pagination"]["from"] = "0"
    with pytest.raises(ParserError) as exc:
        parse_cases(json.dumps(document).encode(), meta)
    assert exc.value.code == "INVALID_PAGINATION"


def test_real_genes_capture():
    records = parse_genes(*load("genes_tp53"))
    assert len(records) == 1
    gene = records[0]
    assert gene.gene_id == "ENSG00000141510"
    assert gene.symbol == "TP53"
    assert gene.biotype == "protein_coding"
    assert gene.is_cancer_gene_census is True


def test_real_discovery_capture_keeps_ranking_metadata_separate():
    hits = parse_top_mutated_genes(*load("top_mutated_genes_brca"))
    assert len(hits) == 5
    assert [hit.rank for hit in hits] == [1, 2, 3, 4, 5]
    assert all(hit.score is not None for hit in hits)
    assert hits[0].gene_id.startswith("ENSG")


def test_real_gene_case_counts_capture():
    counts = parse_gene_case_counts(*load("top_cases_counts_by_genes_tp53"))
    assert counts.complete is True
    assert counts.projects["TCGA-BRCA"]["ENSG00000141510"] == 720
    assert counts.projects["CPTAC-3"]["ENSG00000141510"] == 788


def test_real_multi_gene_counts_capture():
    counts = parse_gene_case_counts(*load("top_cases_counts_multi_gene"))
    cptac = counts.projects["CPTAC-3"]
    assert cptac["ENSG00000141510"] == 788
    assert cptac["ENSG00000154358"] == 661
    assert cptac["ENSG00000121879"] == 571


def test_real_project_coverage_capture_including_observed_zero():
    coverage = parse_mutated_cases_count(*load("mutated_cases_count_all"))
    assert coverage.complete is True
    assert coverage.case_with_ssm["TCGA-BRCA"] == 1098
    assert coverage.case_with_ssm["NCICCR-DLBCL"] == 0


def test_real_expression_availability_capture():
    body, meta = load("expression_availability")
    availability = parse_expression_availability(
        body, meta, expected_cases=["2779fa01-ac93-4e80-a997-3385f72172c3",
                                    "57a1604c-60b7-4b30-a75e-f70939532c5c"],
        expected_genes=["ENSG00000141510"],
    )
    assert availability.cases == {
        "2779fa01-ac93-4e80-a997-3385f72172c3": True,
        "57a1604c-60b7-4b30-a75e-f70939532c5c": True,
    }
    assert availability.genes["ENSG00000141510"] is True
    assert availability.missing_cases == [] and availability.missing_genes == []


def test_expression_availability_rejects_unrequested_identifiers():
    body = json.dumps({
        "cases": {
            "details": [{"case_id": "wrong-case", "has_gene_expression_values": True}],
            "with_gene_expression_count": 1,
            "without_gene_expression_count": 0,
        },
        "genes": {
            "details": [{"gene_id": "ENSG1", "has_gene_expression_values": True}],
            "with_gene_expression_count": 1,
            "without_gene_expression_count": 0,
        },
    }).encode()
    with pytest.raises(ParserError) as exc:
        parse_expression_availability(
            body, meta_for("/gene_expression/availability"),
            expected_cases=["case-a"], expected_genes=["ENSG1"],
        )
    assert exc.value.code == "UNEXPECTED_IDENTIFIER"


def test_real_gene_selection_capture():
    selection = parse_gene_selection(*load("expression_gene_selection"),
                                     expected_genes=["ENSG00000141510"])
    gene = selection.genes["ENSG00000141510"]
    assert gene.symbol == "TP53"
    assert abs((gene.median or 0) - 3.757) < 0.01
    assert abs((gene.stddev or 0) - 0.29998) < 0.001
    assert selection.missing_genes == []


def test_gene_selection_rejects_unrequested_genes():
    body = json.dumps({"gene_selection": [
        {"gene_id": "ENSG2", "symbol": "B", "log2_uqfpkm_median": 1.0,
         "log2_uqfpkm_stddev": 0.5},
    ]}).encode()
    with pytest.raises(ParserError) as exc:
        parse_gene_selection(
            body, meta_for("/gene_expression/gene_selection"), expected_genes=["ENSG1"],
        )
    assert exc.value.code == "UNEXPECTED_IDENTIFIER"


def test_real_expression_values_capture_uses_labels_not_order():
    body, meta = load("expression_values")
    values = parse_expression_values(
        body, meta,
        expected_cases=["57a1604c-60b7-4b30-a75e-f70939532c5c", "2779fa01-ac93-4e80-a997-3385f72172c3"],
        expected_genes=["ENSG00000141510"],
    )
    row = values.values["ENSG00000141510"]
    assert abs(row["2779fa01-ac93-4e80-a997-3385f72172c3"] - 15.6455) < 0.001
    assert abs(row["57a1604c-60b7-4b30-a75e-f70939532c5c"] - 9.9823) < 0.001
    assert values.nonfinite_values == 0


def test_real_median_centered_values_capture():
    body, meta = load("expression_values_median_centered")
    values = parse_expression_values(
        body, meta,
        expected_cases=["2779fa01-ac93-4e80-a997-3385f72172c3", "57a1604c-60b7-4b30-a75e-f70939532c5c"],
        expected_genes=["ENSG00000141510"],
    )
    row = values.values["ENSG00000141510"]
    assert abs(row["2779fa01-ac93-4e80-a997-3385f72172c3"] - 0.29998) < 0.001
    assert abs(row["57a1604c-60b7-4b30-a75e-f70939532c5c"] + 0.29998) < 0.001


def test_real_files_provenance_capture():
    provenance = parse_files_provenance(*load("files_expression_workflows"))
    assert provenance.workflows == ["STAR - Counts"]
    assert provenance.strategies == ["RNA-Seq"]
    assert provenance.non_open_records == 0


def test_truncated_or_incomplete_responses_are_rejected():
    body, _ = load("status")
    with pytest.raises(ParserError) as exc:
        parse_status(body, meta_for("/status", completeness="TRUNCATED"))
    assert exc.value.code == "INCOMPLETE_RESPONSE"


def test_malformed_json_is_rejected():
    with pytest.raises(ParserError) as exc:
        parse_status(b"{not json", meta_for("/status"))
    assert exc.value.code == "MALFORMED_JSON"


def test_missing_required_field_is_rejected():
    body = json.dumps({"data": {"hits": [{"symbol": "TP53"}]}}).encode()
    with pytest.raises(ParserError) as exc:
        parse_genes(body, meta_for("/genes"))
    assert exc.value.code == "MISSING_FIELD"


def test_duplicate_ids_are_rejected():
    body = json.dumps({"data": {"hits": [
        {"gene_id": "ENSG1", "symbol": "A"}, {"gene_id": "ENSG1", "symbol": "A"},
    ]}}).encode()
    with pytest.raises(ParserError) as exc:
        parse_genes(body, meta_for("/genes"))
    assert exc.value.code == "DUPLICATE_ID"


def test_nonfinite_provider_numbers_are_rejected():
    body = json.dumps({"gene_selection": [
        {"gene_id": "ENSG1", "symbol": "A", "log2_uqfpkm_median": float("nan"), "log2_uqfpkm_stddev": 1.0},
    ]}).encode()
    with pytest.raises(ParserError) as exc:
        parse_gene_selection(body, meta_for("/gene_expression/gene_selection"), expected_genes=["ENSG1"])
    assert exc.value.code == "NONFINITE_VALUE"


def test_tsv_unexpected_identifiers_are_rejected():
    body = b"gene_id\tcase-a\tcase-b\nENSG1\t1.0\t2.0\n"
    with pytest.raises(ParserError) as exc:
        parse_expression_values(body, meta_for("/gene_expression/values"),
                                expected_cases=["case-a"], expected_genes=["ENSG1"])
    assert exc.value.code == "UNEXPECTED_IDENTIFIER"


def test_tsv_missing_cells_become_none_not_zero():
    body = b"gene_id\tcase-a\tcase-b\nENSG1\t1.0\t\n"
    values = parse_expression_values(body, meta_for("/gene_expression/values"),
                                     expected_cases=["case-a", "case-b"], expected_genes=["ENSG1"])
    row = values.values["ENSG1"]
    assert row["case-a"] == 1.0
    assert row["case-b"] is None
    assert values.missing_case_ids == []


def test_tsv_nonfinite_cell_counts_and_nulls():
    body = b"gene_id\tcase-a\nENSG1\tNaN\n"
    values = parse_expression_values(body, meta_for("/gene_expression/values"),
                                     expected_cases=["case-a"], expected_genes=["ENSG1"])
    assert values.values["ENSG1"]["case-a"] is None
    assert values.nonfinite_values == 1


def test_aggregation_partial_flags_are_preserved():
    body = json.dumps({
        "timed_out": True, "sum_other_doc_count": 4, "doc_count_error_upper_bound": 2,
        "aggregations": {"projects": {"buckets": [
            {"key": "P1", "genes": {"my_genes": {"gene_id": {"buckets": [
                {"key": "ENSG1", "doc_count": 3},
            ]}}}},
        ]}},
    }).encode()
    counts = parse_gene_case_counts(body, meta_for("/analysis/top_cases_counts_by_genes"))
    assert counts.complete is False
    assert "timed_out" in counts.partial_reasons
    assert counts.projects["P1"]["ENSG1"] == 3


def test_unfiltered_coverage_is_required_for_scientific_use():
    coverage = parse_mutated_cases_count(*load("mutated_cases_count_all"))
    assert coverage.complete is True
    assert len(coverage.case_with_ssm) > 50


def test_nested_terms_truncation_is_not_treated_as_complete():
    counts_body = json.dumps({
        "aggregations": {"projects": {
            "sum_other_doc_count": 1,
            "buckets": [
                {"key": "P1", "genes": {"my_genes": {"gene_id": {
                    "sum_other_doc_count": 0,
                    "buckets": [{"key": "ENSG1", "doc_count": 3}],
                }}}},
            ],
        }},
    }).encode()
    counts = parse_gene_case_counts(counts_body, meta_for("/analysis/top_cases_counts_by_genes"))
    assert counts.complete is False
    assert any("sum_other_doc_count" in reason for reason in counts.partial_reasons)
    assert counts.projects["P1"]["ENSG1"] == 3

    gene_body = json.dumps({
        "aggregations": {"projects": {"buckets": [
            {"key": "P1", "genes": {"my_genes": {"gene_id": {
                "sum_other_doc_count": 2,
                "buckets": [{"key": "ENSG1", "doc_count": 3}],
            }}}},
        ]}},
    }).encode()
    gene_counts = parse_gene_case_counts(gene_body, meta_for("/analysis/top_cases_counts_by_genes"))
    assert gene_counts.complete is False
    assert any("genes:sum_other_doc_count" in reason for reason in gene_counts.partial_reasons)

    coverage_body = json.dumps({
        "aggregations": {"projects": {"buckets": [
            {"key": "P1", "case_summary": {"case_with_ssm": {
                "doc_count_error_upper_bound": 1, "doc_count": 7,
            }}},
        ]}},
    }).encode()
    coverage = parse_mutated_cases_count(coverage_body, meta_for("/analysis/mutated_cases_count_by_project"))
    assert coverage.complete is False
    assert any("case_with_ssm:doc_count_error_upper_bound" in reason for reason in coverage.partial_reasons)
    assert coverage.case_with_ssm["P1"] == 7


def test_tsv_utf8_bom_header_is_accepted():
    body = "\ufeffgene_id\tcase-a\nENSG1\t1.0\n".encode("utf-8")
    values = parse_expression_values(body, meta_for("/gene_expression/values"),
                                     expected_cases=["case-a"], expected_genes=["ENSG1"])
    assert values.values["ENSG1"]["case-a"] == 1.0


def test_files_record_without_explicit_open_access_is_not_open():
    body = json.dumps({"data": {"hits": [
        {"file_id": "f1", "analysis": {"workflow_type": "STAR - Counts"}},
        {"file_id": "f2", "access": "open", "analysis": {"workflow_type": "STAR - Counts"}},
    ]}, "warnings": {}}).encode()
    provenance = parse_files_provenance(body, meta_for("/files"))
    assert provenance.files_seen == 2
    assert provenance.non_open_records == 1
    assert provenance.workflows == ["STAR - Counts"]
