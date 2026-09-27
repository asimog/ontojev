"""Preregistered calibration registry: bindings, status semantics and record strictness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cancerjev.research.calibration import (
    CALIBRATION_DESIGN_VERSION,
    THRESHOLDS,
    THRESHOLDS_BY_ID,
    CalibrationError,
    calibration_status,
    load_calibration_record,
    uncalibrated_threshold_ids,
)


def test_registry_binds_every_declared_threshold_to_its_owning_policy_version():
    assert CALIBRATION_DESIGN_VERSION == "calibration-design-v1"
    values = {declaration.threshold_id: declaration.declared_value
              for declaration in THRESHOLDS}

    assert values["mutation.max_survivors"] == 10
    assert values["mutation.review_occurrence_ratio"] == 4
    assert values["mutation.review_hotspot_min_records"] == 20
    assert values["mutation.review_hotspot_top_position_share"] == 0.25
    assert values["expression.minimum_tail_n"] == 20
    assert values["expression.iqr_multiplier"] == 1.5
    assert values["expression.review_asymmetry_ratio"] == 5.0
    assert values["expression.null_excess_sd"] == 3.0
    assert values["cnv.retain_min_amplification_cases"] == 5
    assert values["cnv.retain_min_homozygous_deletion_cases"] == 5
    assert (values["wide.admission_min_warrants"], values["wide.admission_min_uncertainty"],
            values["wide.admission_min_quality"], values["wide.admission_max_confound"]) == \
        (0.60, 0.50, 0.40, 0.50)
    assert (values["deep.revision_reliable_min"], values["deep.evidence_sufficient_min"],
            values["deep.next_step_warranted_min"],
            values["deep.stopping_more_honest_min"]) == (0.5, 0.5, 0.6, 0.5)
    assert (values["hypothesis.testable_min"],
            values["hypothesis.exceeds_recorded_evidence_max"]) == (0.60, 0.50)
    assert len(values) == len(THRESHOLDS), "threshold ids must be unique"


def test_every_declaration_declares_metric_grid_and_corpus():
    for declaration in THRESHOLDS:
        assert declaration.policy_version
        assert declaration.metric and declaration.corpus_requirement
        assert len(declaration.sensitivity_grid) >= 3


def test_no_threshold_is_calibrated_at_head():
    status = calibration_status()
    assert set(status.values()) == {"UNCALIBRATED"}
    assert uncalibrated_threshold_ids() == tuple(sorted(THRESHOLDS_BY_ID))


def _record(threshold_id: str = "wide.admission_min_warrants", *,
            policy_version: str = "wide-policy-v2") -> dict:
    return {
        "schema_version": 1, "kind": "CALIBRATION_RECORD", "threshold_id": threshold_id,
        "policy_version": policy_version, "declared_at": "2026-09-27T00:00:00Z",
        "corpus_hash": "a" * 64, "held_out": True,
        "metric": "precision_at_3_difference_vs_A", "replicates": 200,
        "values": {"0.5": 0.10, "0.6": 0.04, "0.7": -0.02},
    }


def _write(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / f"{document['threshold_id']}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_a_current_policy_record_calibrates_and_a_stale_one_never_does(tmp_path):
    current = load_calibration_record(_write(tmp_path, _record()))
    stale = load_calibration_record(
        _write(tmp_path, _record(policy_version="wide-policy-v1")))

    assert calibration_status((current,))["wide.admission_min_warrants"] == "CALIBRATED"
    assert calibration_status((stale,))["wide.admission_min_warrants"] == "STALE_POLICY_VERSION"
    assert "wide.admission_min_warrants" in uncalibrated_threshold_ids((stale,))
    assert "wide.admission_min_warrants" not in uncalibrated_threshold_ids((current,))
    assert len(uncalibrated_threshold_ids((current,))) == len(THRESHOLDS) - 1


def test_malformed_or_unknown_records_are_refused(tmp_path):
    extra = {**_record(), "extra": 1}
    with pytest.raises(CalibrationError, match="RECORD_MALFORMED"):
        load_calibration_record(_write(tmp_path, extra))
    unknown = {**_record(), "threshold_id": "not.a.threshold"}
    with pytest.raises(CalibrationError, match="UNKNOWN_THRESHOLD"):
        load_calibration_record(_write(tmp_path, unknown))
    few_replicates = {**_record(), "replicates": 10}
    with pytest.raises(CalibrationError, match="RECORD_MALFORMED"):
        load_calibration_record(_write(tmp_path, few_replicates))
    bad_value = {**_record(), "values": {"0.6": None}}
    with pytest.raises(CalibrationError, match="RECORD_MALFORMED"):
        load_calibration_record(_write(tmp_path, bad_value))
    short_hash = {**_record(), "corpus_hash": "abc"}
    with pytest.raises(CalibrationError, match="RECORD_MALFORMED"):
        load_calibration_record(_write(tmp_path, short_hash))
