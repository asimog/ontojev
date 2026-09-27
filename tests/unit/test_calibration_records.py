"""Calibration record generation from a frozen corpus slice."""

from __future__ import annotations

import json
from pathlib import Path

from cancerjev.research.calibration import calibration_status, load_calibration_record
from cancerjev.research.calibration_records import (
    BOOTSTRAP_REPLICATES,
    corpus_hash,
    load_occurrence_panel,
    write_mutation_records,
)


def _write_gene(path: Path, gene_id: str, hits: list[dict]) -> None:
    payload = {"data": {"hits": hits}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _hit(case_id: str, gene_id: str, *, canonical: bool = True,
         protein_start: int | None = 10) -> dict:
    transcript: dict = {
        "gene": {"gene_id": gene_id},
        "is_canonical": canonical,
        "consequence_type": "missense_variant",
    }
    if protein_start is not None:
        transcript["protein_start"] = protein_start
    return {"case": {"case_id": case_id}, "ssm": {"consequence": [{"transcript": transcript}]}}


def _corpus(tmp_path: Path, genes: dict[str, list[dict]]) -> Path:
    directory = tmp_path / "corpus"
    directory.mkdir()
    for gene_id, hits in genes.items():
        _write_gene(directory / f"C_ssm_occurrences_{gene_id}.body", gene_id, hits)
    return directory


def test_corpus_hash_and_panel_derive_distinct_cases_and_positions(tmp_path):
    directory = _corpus(tmp_path, {
        "ENSG00000000001": [_hit("case-1", "ENSG00000000001", protein_start=10),
                            _hit("case-1", "ENSG00000000001", protein_start=20),
                            _hit("case-2", "ENSG00000000001", protein_start=10)],
        "ENSG00000000002": [_hit("case-3", "ENSG00000000002", protein_start=5)],
    })

    genes = load_occurrence_panel(directory)

    assert [gene.gene_id for gene in genes] == ["ENSG00000000001", "ENSG00000000002"]
    assert genes[0].distinct_cases == 2
    assert genes[0].occurrence_docs == 3
    assert genes[0].positions == ((10, 2), (20, 1))
    assert len(corpus_hash(directory)) == 64


def test_mutation_family_records_load_strictly_and_report_calibrated(tmp_path):
    directory = _corpus(tmp_path, {
        "ENSG00000000001": [_hit("case-1", "ENSG00000000001"),
                            _hit("case-1", "ENSG00000000001"),
                            _hit("case-2", "ENSG00000000001")],
        "ENSG00000000002": [_hit("case-3", "ENSG00000000002")],
    })
    out = tmp_path / "calibration"

    written = write_mutation_records(corpus=directory, out=out)
    records = tuple(load_calibration_record(path) for path in written)
    status = calibration_status(records)

    assert len(written) == 4
    assert all(record.replicates == BOOTSTRAP_REPLICATES for record in records)
    assert all(record.held_out is False for record in records)
    assert all(len(record.source_hash) == 64 for record in records)
    assert {record.threshold_id for record in records} == {
        "mutation.max_survivors", "mutation.review_occurrence_ratio",
        "mutation.review_hotspot_min_records",
        "mutation.review_hotspot_top_position_share",
    }
    assert status["mutation.max_survivors"] == "CALIBRATED"
    assert status["expression.null_excess_sd"] == "UNCALIBRATED"
    assert status["wide.admission_min_warrants"] == "UNCALIBRATED", \
        "label-dependent thresholds are never marked calibrated without held-out labels"


def test_corpus_refuses_a_record_that_does_not_annotate_the_captured_gene(tmp_path):
    directory = _corpus(tmp_path, {
        "ENSG00000000001": [_hit("case-1", "ENSG00000000002")],
    })

    import pytest

    from cancerjev.research.calibration_records import CalibrationRecordError

    with pytest.raises(CalibrationRecordError) as excinfo:
        load_occurrence_panel(directory)

    assert excinfo.value.code == "CORPUS_MALFORMED"
