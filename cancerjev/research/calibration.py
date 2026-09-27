"""Preregistered calibration design for every declared scientific threshold.

Design only: NO calibration record exists at HEAD, so every threshold below is a
declared policy parameter, not a validated scientific cutoff. The registry binds
each threshold to the code constant that owns it and to the owning policy version,
so a value change is visible here. A threshold counts as ``CALIBRATED`` only when a
schema-valid calibration record for its current policy version is recorded; a
record for an older policy version is ``STALE_POLICY_VERSION`` and never counts.
``STATISTICALLY_SUPPORTED`` stays blocked until records exist (Phase 9).

The evaluated designs, metrics, sensitivity grids and corpus requirements live in
docs/CALIBRATION_DESIGN.md; this module machine-binds the declarations.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cancerjev.domain._json import decode
from cancerjev.domain.discovery import (
    CNV_DISPOSITION_POLICY_VERSION,
    CNV_RETAIN_MIN_AMPLIFICATION_CASES,
    CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES,
    EXPRESSION_DISPOSITION_POLICY_VERSION,
    EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO,
    EXPRESSION_TAIL_NULL_EXCESS_SD,
    EXPRESSION_TAIL_VERSION,
    JEV_REVIEW_HOTSPOT_MIN_RECORDS,
    JEV_REVIEW_HOTSPOT_TOP_POSITION_SHARE,
    JEV_REVIEW_MAX_OCCURRENCE_PER_CASE_RATIO,
    MAX_DISCOVERY_SURVIVORS,
    MIN_EXPRESSION_TAIL_N,
)
from cancerjev.domain.measurements import text
from cancerjev.research.hypothesis_policy import (
    HYPOTHESIS_POLICY_VERSION,
)
from cancerjev.research.hypothesis_policy import (
    THRESHOLDS as HYPOTHESIS_THRESHOLDS,
)
from cancerjev.research.nextmove import DEEP_POLICY_VERSION
from cancerjev.research.nextmove import THRESHOLDS as DEEP_THRESHOLDS
from cancerjev.research.ranking import (
    ADMISSION_MAX_CONFOUND,
    ADMISSION_MIN_QUALITY,
    ADMISSION_MIN_UNCERTAINTY,
    ADMISSION_MIN_WARRANTS,
    JEV_POLICY_VERSION,
    PRE_WIDE_POLICY_VERSION,
    PRE_WIDE_STRATUM_SHARES,
)

CALIBRATION_DESIGN_VERSION = "calibration-design-v1"
CALIBRATION_RECORD_SCHEMA_VERSION = 1
CALIBRATION_STATUS_VALUES = ("UNCALIBRATED", "CALIBRATED", "STALE_POLICY_VERSION")
MUTATION_REDUCER_VERSION = "mutation-count-v2"


class CalibrationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ThresholdDeclaration:
    threshold_id: str
    policy_version: str
    declared_value: float | int
    metric: str
    sensitivity_grid: tuple[float, ...]
    corpus_requirement: str


@dataclass(frozen=True)
class CalibrationRecord:
    threshold_id: str
    policy_version: str
    declared_at: str
    corpus_hash: str
    held_out: bool
    metric: str
    replicates: int
    values: tuple[tuple[str, float], ...]
    source_hash: str


THRESHOLDS: tuple[ThresholdDeclaration, ...] = (
    ThresholdDeclaration(
        "mutation.max_survivors", MUTATION_REDUCER_VERSION, MAX_DISCOVERY_SURVIVORS,
        "mutation-lane survivor cutoff", (5.0, 10.0, 20.0, 50.0),
        "frozen reconciliation corpus (DR46 LUAD) with the complete occurrence scan"),
    ThresholdDeclaration(
        "mutation.review_occurrence_ratio", MUTATION_REDUCER_VERSION,
        JEV_REVIEW_MAX_OCCURRENCE_PER_CASE_RATIO,
        "occurrence-per-case review trigger", (2.0, 4.0, 6.0, 8.0),
        "frozen reconciliation corpus (DR46 LUAD) with the complete occurrence scan"),
    ThresholdDeclaration(
        "mutation.review_hotspot_min_records", MUTATION_REDUCER_VERSION,
        JEV_REVIEW_HOTSPOT_MIN_RECORDS,
        "hotspot-concentration review trigger", (10.0, 20.0, 40.0),
        "frozen reconciliation corpus (DR46 LUAD) with position-level occurrences"),
    ThresholdDeclaration(
        "mutation.review_hotspot_top_position_share", MUTATION_REDUCER_VERSION,
        JEV_REVIEW_HOTSPOT_TOP_POSITION_SHARE,
        "hotspot-concentration review trigger", (0.1, 0.25, 0.5),
        "frozen reconciliation corpus (DR46 LUAD) with position-level occurrences"),
    ThresholdDeclaration(
        "expression.minimum_tail_n", EXPRESSION_DISPOSITION_POLICY_VERSION,
        MIN_EXPRESSION_TAIL_N,
        "expression tail eligibility", (10.0, 20.0, 40.0),
        "frozen expression corpus (DR46 LUAD case-labelled UQFPKM)"),
    ThresholdDeclaration(
        "expression.iqr_multiplier", EXPRESSION_TAIL_VERSION, 1.5,
        "expression Tukey fence definition", (1.0, 1.5, 2.0, 3.0),
        "frozen expression corpus (DR46 LUAD case-labelled UQFPKM)"),
    ThresholdDeclaration(
        "expression.review_asymmetry_ratio", EXPRESSION_DISPOSITION_POLICY_VERSION,
        EXPRESSION_JEV_REVIEW_ASYMMETRY_RATIO,
        "expression asymmetry review trigger", (2.0, 5.0, 10.0),
        "frozen expression corpus (DR46 LUAD case-labelled UQFPKM)"),
    ThresholdDeclaration(
        "expression.null_excess_sd", EXPRESSION_TAIL_VERSION, EXPRESSION_TAIL_NULL_EXCESS_SD,
        "expression nomination screen over the pooled empirical null",
        (2.0, 3.0, 4.0), "frozen expression corpus (DR46 LUAD case-labelled UQFPKM)"),
    ThresholdDeclaration(
        "cnv.retain_min_amplification_cases", CNV_DISPOSITION_POLICY_VERSION,
        CNV_RETAIN_MIN_AMPLIFICATION_CASES, "CNV amplification recurrence cutoff",
        (3.0, 5.0, 8.0), "frozen CNV project scan (DR46 LUAD complete case shards)"),
    ThresholdDeclaration(
        "cnv.retain_min_homozygous_deletion_cases", CNV_DISPOSITION_POLICY_VERSION,
        CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES,
        "CNV homozygous-deletion recurrence cutoff", (3.0, 5.0, 8.0),
        "frozen CNV project scan (DR46 LUAD complete case shards)"),
    ThresholdDeclaration(
        "wide.admission_min_warrants", JEV_POLICY_VERSION, ADMISSION_MIN_WARRANTS,
        "Wide admission: minimum warrants probability", (0.5, 0.6, 0.7),
        "preregistered blinded label set (docs/CALIBRATION_DESIGN.md)"),
    ThresholdDeclaration(
        "wide.admission_min_uncertainty", JEV_POLICY_VERSION, ADMISSION_MIN_UNCERTAINTY,
        "Wide admission: minimum uncertainty probability", (0.4, 0.5, 0.6),
        "preregistered blinded label set (docs/CALIBRATION_DESIGN.md)"),
    ThresholdDeclaration(
        "wide.admission_min_quality", JEV_POLICY_VERSION, ADMISSION_MIN_QUALITY,
        "Wide admission: minimum evidence-quality probability", (0.3, 0.4, 0.5),
        "preregistered blinded label set (docs/CALIBRATION_DESIGN.md)"),
    ThresholdDeclaration(
        "wide.admission_max_confound", JEV_POLICY_VERSION, ADMISSION_MAX_CONFOUND,
        "Wide admission: maximum confounding probability", (0.3, 0.5, 0.7),
        "preregistered blinded label set (docs/CALIBRATION_DESIGN.md)"),
    ThresholdDeclaration(
        "pre_wide.stratum_shares", PRE_WIDE_POLICY_VERSION,
        PRE_WIDE_STRATUM_SHARES["mutation"],
        "pre-Wide per-stratum quota under the hard ceiling", (0.2, 0.3, 0.4),
        "frozen DR46 union with the Phase 2 quota policy"),
    ThresholdDeclaration(
        "deep.revision_reliable_min", DEEP_POLICY_VERSION,
        DEEP_THRESHOLDS["revision_reliable_min"],
        "Deep continuation: minimum reliability probability", (0.4, 0.5, 0.6),
        "frozen deep-slice replay corpus (Stage 8 comparison)"),
    ThresholdDeclaration(
        "deep.evidence_sufficient_min", DEEP_POLICY_VERSION,
        DEEP_THRESHOLDS["evidence_sufficient_min"],
        "Deep continuation: minimum evidence-sufficiency probability", (0.4, 0.5, 0.6),
        "frozen deep-slice replay corpus (Stage 8 comparison)"),
    ThresholdDeclaration(
        "deep.next_step_warranted_min", DEEP_POLICY_VERSION,
        DEEP_THRESHOLDS["next_step_warranted_min"],
        "Deep continuation: minimum warrant probability", (0.5, 0.6, 0.7),
        "frozen deep-slice replay corpus (Stage 8 comparison)"),
    ThresholdDeclaration(
        "deep.stopping_more_honest_min", DEEP_POLICY_VERSION,
        DEEP_THRESHOLDS["stopping_more_honest_min"],
        "Deep stopping: minimum stop probability", (0.4, 0.5, 0.6),
        "frozen deep-slice replay corpus (Stage 8 comparison)"),
    ThresholdDeclaration(
        "hypothesis.testable_min", HYPOTHESIS_POLICY_VERSION,
        HYPOTHESIS_THRESHOLDS["testable_min"],
        "hypothesis keep/abstain: minimum testability probability", (0.5, 0.6, 0.7),
        "frozen hypothesis critique corpus (Phase 3 replay)"),
    ThresholdDeclaration(
        "hypothesis.exceeds_recorded_evidence_max", HYPOTHESIS_POLICY_VERSION,
        HYPOTHESIS_THRESHOLDS["exceeds_recorded_evidence_max"],
        "hypothesis keep/abstain: maximum exceedance probability", (0.4, 0.5, 0.6),
        "frozen hypothesis critique corpus (Phase 3 replay)"),
)


def _read(path: Path) -> tuple[dict[str, Any], str]:
    try:
        content = path.read_bytes()
        payload = decode(content)
    except Exception as exc:
        raise CalibrationError("RECORD_UNREADABLE", f"{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CalibrationError("RECORD_MALFORMED", f"{path} must contain one JSON object")
    return payload, hashlib.sha256(content).hexdigest()


def load_calibration_record(path: Path) -> CalibrationRecord:
    """Strict reader for one recorded calibration artifact."""
    payload, source_hash = _read(path)
    expected = {"schema_version", "kind", "threshold_id", "policy_version", "declared_at",
                "corpus_hash", "held_out", "metric", "replicates", "values"}
    if set(payload) != expected or payload.get("schema_version") != CALIBRATION_RECORD_SCHEMA_VERSION \
            or payload.get("kind") != "CALIBRATION_RECORD":
        raise CalibrationError("RECORD_MALFORMED", "unknown, missing or extra record fields")
    threshold_id = payload["threshold_id"]
    policy_version = payload["policy_version"]
    declared_at = payload["declared_at"]
    metric = payload["metric"]
    corpus_hash = payload["corpus_hash"]
    if not isinstance(threshold_id, str) or threshold_id not in THRESHOLD_IDS:
        raise CalibrationError("UNKNOWN_THRESHOLD", str(threshold_id))
    text(policy_version, "policy_version")
    text(declared_at, "declared_at")
    text(metric, "metric")
    if not isinstance(corpus_hash, str) or len(corpus_hash) != 64:
        raise CalibrationError("RECORD_MALFORMED", "corpus_hash must be a sha256")
    if type(payload["held_out"]) is not bool:
        raise CalibrationError("RECORD_MALFORMED", "held_out must be boolean")
    replicates = payload["replicates"]
    if type(replicates) is not int or replicates < 100:
        raise CalibrationError("RECORD_MALFORMED", "replicates must be an integer >= 100")
    raw_values = payload["values"]
    if not isinstance(raw_values, dict) or not raw_values:
        raise CalibrationError("RECORD_MALFORMED", "values must be a non-empty object")
    values: list[tuple[str, float]] = []
    for key, value in sorted(raw_values.items()):
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            raise CalibrationError("RECORD_MALFORMED", f"value for {key} must be a finite number")
        values.append((str(key), float(value)))
    return CalibrationRecord(threshold_id, policy_version, declared_at, corpus_hash,
                             payload["held_out"], metric, replicates, tuple(values), source_hash)


THRESHOLD_IDS = frozenset(declaration.threshold_id for declaration in THRESHOLDS)
THRESHOLDS_BY_ID = {declaration.threshold_id: declaration for declaration in THRESHOLDS}


def calibration_status(
        records: tuple[CalibrationRecord, ...] = ()) -> dict[str, str]:
    """Per-threshold status; only a record for the current policy version counts."""
    status = {declaration.threshold_id: "UNCALIBRATED" for declaration in THRESHOLDS}
    for record in records:
        declaration = THRESHOLDS_BY_ID[record.threshold_id]
        if record.policy_version == declaration.policy_version:
            status[record.threshold_id] = "CALIBRATED"
        elif status[record.threshold_id] != "CALIBRATED":
            status[record.threshold_id] = "STALE_POLICY_VERSION"
    return status


def uncalibrated_threshold_ids(
        records: tuple[CalibrationRecord, ...] = ()) -> tuple[str, ...]:
    status = calibration_status(records)
    return tuple(sorted(threshold_id for threshold_id, value in status.items()
                        if value != "CALIBRATED"))
