"""Stage 8 provider-free prospective protocol validation and arm comparison."""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from cancerjev.domain._json import decode

PROTOCOL_SCHEMA_VERSION = 1
OUTPUT_SCHEMA_VERSION = 1
ALLOWED_SPLITS = frozenset({"TRAIN", "DEVELOPMENT", "HOLDOUT"})
ALLOWED_DISPOSITIONS = frozenset({"INVESTIGATE", "STOP", "ABSTAIN", "EXTERNAL_EVIDENCE_REQUIRED"})


class ProspectiveError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Label:
    item_id: str
    gene_id: str
    group_id: str
    split: str
    useful_investigation: bool
    ordinal_usefulness: int
    rationale: str


@dataclass(frozen=True)
class Protocol:
    protocol_id: str
    declared_at: str
    seed: int
    bootstrap_replicates: int
    labels: tuple[Label, ...]
    source_hash: str


@dataclass(frozen=True)
class Prediction:
    item_id: str
    disposition: str
    score: float
    unsupported_assertion: bool
    wrong_population: bool
    attempts: int
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    human_minutes: float
    spend_usd: float | None


@dataclass(frozen=True)
class Arm:
    arm_id: str
    description: str
    predictions: tuple[Prediction, ...]


def _read(path: Path) -> tuple[dict[str, Any], str]:
    try:
        content = path.read_bytes()
        payload = decode(content)
    except Exception as exc:
        raise ProspectiveError("FILE_UNREADABLE", f"{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProspectiveError("MALFORMED_DOCUMENT", f"{path} must contain one JSON object")
    return payload, hashlib.sha256(content).hexdigest()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProspectiveError("MALFORMED_DOCUMENT", f"{field} must be non-blank text")
    return value.strip()


def load_protocol(path: Path) -> Protocol:
    payload, source_hash = _read(path)
    expected = {"schema_version", "kind", "protocol_id", "declared_at", "seed",
                "bootstrap_replicates", "blinded_to_arms", "labels"}
    if set(payload) != expected or payload.get("schema_version") != PROTOCOL_SCHEMA_VERSION \
            or payload.get("kind") != "PROSPECTIVE_PROTOCOL":
        raise ProspectiveError("MALFORMED_PROTOCOL", "unknown, missing or extra protocol fields")
    if payload["blinded_to_arms"] is not True:
        raise ProspectiveError("UNBLINDED_LABELS", "labels must be recorded blind to arm identity/output")
    seed = payload["seed"]
    replicates = payload["bootstrap_replicates"]
    if type(seed) is not int or type(replicates) is not int or not 100 <= replicates <= 10_000:
        raise ProspectiveError("MALFORMED_PROTOCOL", "invalid seed/bootstrap_replicates")
    raw_labels = payload["labels"]
    if not isinstance(raw_labels, list) or not raw_labels:
        raise ProspectiveError("MALFORMED_PROTOCOL", "labels must be a non-empty list")
    labels: list[Label] = []
    seen_items: set[str] = set()
    group_splits: dict[str, str] = {}
    gene_groups: dict[str, str] = {}
    for raw in raw_labels:
        if not isinstance(raw, dict) or set(raw) != {
            "item_id", "gene_id", "group_id", "split", "useful_investigation",
            "ordinal_usefulness", "rationale", "reviewer_count", "adjudicated",
        }:
            raise ProspectiveError("MALFORMED_PROTOCOL", "invalid label fields")
        item_id = _text(raw["item_id"], "item_id")
        gene_id = _text(raw["gene_id"], "gene_id")
        group_id = _text(raw["group_id"], "group_id")
        split = _text(raw["split"], "split")
        if item_id in seen_items or split not in ALLOWED_SPLITS:
            raise ProspectiveError("INVALID_SPLIT_ASSIGNMENT", f"duplicate item or invalid split: {item_id}")
        if group_id in group_splits and group_splits[group_id] != split:
            raise ProspectiveError("GROUP_LEAKAGE", f"group {group_id} crosses fixed splits")
        if gene_id in gene_groups and gene_groups[gene_id] != group_id:
            raise ProspectiveError("GROUP_LEAKAGE", f"gene {gene_id} crosses groups")
        useful = raw["useful_investigation"]
        ordinal = raw["ordinal_usefulness"]
        if type(useful) is not bool or type(ordinal) is not int or not 0 <= ordinal <= 3:
            raise ProspectiveError("MALFORMED_PROTOCOL", f"invalid labels for {item_id}")
        if type(raw["reviewer_count"]) is not int or raw["reviewer_count"] < 2 \
                or raw["adjudicated"] is not True:
            raise ProspectiveError("UNREVIEWED_LABEL", f"{item_id} lacks blinded independent review")
        rationale = _text(raw["rationale"], "rationale")
        if len(rationale) < 20:
            raise ProspectiveError("UNREVIEWED_LABEL", f"{item_id} rationale is too short")
        seen_items.add(item_id)
        group_splits[group_id] = split
        gene_groups[gene_id] = group_id
        labels.append(Label(item_id, gene_id, group_id, split, useful, ordinal, rationale))
    return Protocol(
        _text(payload["protocol_id"], "protocol_id"),
        _text(payload["declared_at"], "declared_at"), seed, replicates, tuple(labels), source_hash,
    )


def load_arms(path: Path, protocol: Protocol) -> tuple[tuple[Arm, ...], str]:
    payload, source_hash = _read(path)
    if set(payload) != {"schema_version", "kind", "protocol_id", "arms"} \
            or payload.get("schema_version") != OUTPUT_SCHEMA_VERSION \
            or payload.get("kind") != "PROSPECTIVE_ARM_OUTPUTS" \
            or payload.get("protocol_id") != protocol.protocol_id:
        raise ProspectiveError("MALFORMED_OUTPUT", "arm output does not bind the protocol")
    raw_arms = payload["arms"]
    if not isinstance(raw_arms, list) or len(raw_arms) < 2:
        raise ProspectiveError("MALFORMED_OUTPUT", "at least baseline A and one comparison arm are required")
    expected_items = {label.item_id for label in protocol.labels}
    arms: list[Arm] = []
    arm_ids: set[str] = set()
    for raw_arm in raw_arms:
        if not isinstance(raw_arm, dict) or set(raw_arm) != {"arm_id", "description", "predictions"}:
            raise ProspectiveError("MALFORMED_OUTPUT", "invalid arm fields")
        arm_id = _text(raw_arm["arm_id"], "arm_id")
        if arm_id in arm_ids:
            raise ProspectiveError("MALFORMED_OUTPUT", f"duplicate arm {arm_id}")
        arm_ids.add(arm_id)
        predictions: list[Prediction] = []
        if not isinstance(raw_arm["predictions"], list):
            raise ProspectiveError("MALFORMED_OUTPUT", f"predictions in arm {arm_id} must be a list")
        for raw in raw_arm["predictions"]:
            if not isinstance(raw, dict) or set(raw) != {
                "item_id", "disposition", "score", "unsupported_assertion", "wrong_population",
                "attempts", "input_tokens", "output_tokens", "latency_ms", "human_minutes", "spend_usd",
            }:
                raise ProspectiveError("MALFORMED_OUTPUT", f"invalid prediction fields in arm {arm_id}")
            disposition = _text(raw["disposition"], "disposition")
            score = raw["score"]
            if disposition not in ALLOWED_DISPOSITIONS or isinstance(score, bool) \
                    or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
                raise ProspectiveError("MALFORMED_OUTPUT", f"invalid decision in arm {arm_id}")
            for field in ("unsupported_assertion", "wrong_population"):
                if type(raw[field]) is not bool:
                    raise ProspectiveError("MALFORMED_OUTPUT", f"{field} must be boolean")
            for field in ("attempts", "latency_ms"):
                if type(raw[field]) is not int or raw[field] < 0:
                    raise ProspectiveError("MALFORMED_OUTPUT", f"{field} must be nonnegative")
            for field in ("input_tokens", "output_tokens"):
                if raw[field] is not None and (type(raw[field]) is not int or raw[field] < 0):
                    raise ProspectiveError("MALFORMED_OUTPUT", f"{field} must be null or nonnegative")
            if raw["human_minutes"] is None:
                raise ProspectiveError("MALFORMED_OUTPUT", "human_minutes must be measured")
            for field in ("human_minutes", "spend_usd"):
                if raw[field] is not None and (isinstance(raw[field], bool)
                                               or not isinstance(raw[field], (int, float))
                                               or not math.isfinite(float(raw[field]))
                                               or raw[field] < 0):
                    raise ProspectiveError("MALFORMED_OUTPUT", f"{field} must be null or nonnegative")
            predictions.append(Prediction(
                _text(raw["item_id"], "item_id"), disposition, float(score),
                raw["unsupported_assertion"], raw["wrong_population"], raw["attempts"],
                raw["input_tokens"], raw["output_tokens"], raw["latency_ms"],
                float(raw["human_minutes"]),
                None if raw["spend_usd"] is None else float(raw["spend_usd"]),
            ))
        item_ids = [item.item_id for item in predictions]
        if len(item_ids) != len(set(item_ids)) or set(item_ids) != expected_items:
            raise ProspectiveError("OUTPUT_COVERAGE_MISMATCH", f"arm {arm_id} must cover every protocol item once")
        arms.append(Arm(arm_id, _text(raw_arm["description"], "description"), tuple(predictions)))
    if "A" not in arm_ids:
        raise ProspectiveError("BASELINE_MISSING", "arm A is required")
    return tuple(arms), source_hash


def _metrics(labels: tuple[Label, ...], predictions: tuple[Prediction, ...]) -> dict[str, Any]:
    label_by_id = {label.item_id: label for label in labels}
    ordered = sorted(
        (item for item in predictions if item.disposition == "INVESTIGATE"),
        key=lambda item: (-item.score, item.item_id),
    )
    top = ordered[:3]
    covered = [item for item in predictions if item.disposition != "ABSTAIN"]
    investigated = ordered
    gains = [label_by_id[item.item_id].ordinal_usefulness for item in top]
    ideal = sorted((label.ordinal_usefulness for label in labels), reverse=True)[:3]

    def dcg(values: list[int]) -> float:
        return float(sum((2 ** value - 1) / math.log2(index + 2)
                         for index, value in enumerate(values)))

    known_input = all(item.input_tokens is not None for item in predictions)
    known_output = all(item.output_tokens is not None for item in predictions)
    known_spend = all(item.spend_usd is not None for item in predictions)
    return {
        "n": len(labels),
        "coverage": len(covered) / len(labels),
        "abstention_rate": 1.0 - len(covered) / len(labels),
        "investigate_precision": (
            sum(label_by_id[item.item_id].useful_investigation for item in investigated)
            / len(investigated) if investigated else None),
        "precision_at_3": (
            sum(label_by_id[item.item_id].useful_investigation for item in top) / len(top)
            if top else None),
        "ndcg_at_3": dcg(gains) / dcg(ideal) if ideal and dcg(ideal) else None,
        "unsupported_assertion_rate": sum(item.unsupported_assertion for item in covered) / len(covered)
        if covered else None,
        "wrong_population_rate": sum(item.wrong_population for item in covered) / len(covered)
        if covered else None,
        "resources": {
            "attempts": sum(item.attempts for item in predictions),
            "input_tokens": sum(item.input_tokens or 0 for item in predictions) if known_input else None,
            "output_tokens": sum(item.output_tokens or 0 for item in predictions) if known_output else None,
            "latency_ms": sum(item.latency_ms for item in predictions),
            "human_minutes": sum(item.human_minutes for item in predictions),
            "spend_usd": sum(item.spend_usd or 0.0 for item in predictions) if known_spend else None,
        },
    }


def evaluate_prospective(protocol: Protocol, arms: tuple[Arm, ...], *, split: str = "HOLDOUT") -> dict[str, Any]:
    if split not in ALLOWED_SPLITS:
        raise ProspectiveError("INVALID_SPLIT", split)
    labels = tuple(label for label in protocol.labels if label.split == split)
    if not labels:
        raise ProspectiveError("EMPTY_SPLIT", f"no labels assigned to {split}")
    item_ids = {label.item_id for label in labels}
    metrics = {
        arm.arm_id: _metrics(labels, tuple(item for item in arm.predictions if item.item_id in item_ids))
        for arm in arms
    }
    groups = sorted({label.group_id for label in labels})
    rng = random.Random(protocol.seed)
    differences: dict[str, list[float]] = {arm.arm_id: [] for arm in arms if arm.arm_id != "A"}
    by_group = {group: tuple(label for label in labels if label.group_id == group) for group in groups}
    for _ in range(protocol.bootstrap_replicates):
        sampled = [rng.choice(groups) for _ in groups]
        sample_labels: list[Label] = []
        sampled_predictions: dict[str, list[Prediction]] = {arm.arm_id: [] for arm in arms}
        prediction_maps = {
            arm.arm_id: {item.item_id: item for item in arm.predictions} for arm in arms
        }
        for sample_index, group in enumerate(sampled):
            for label in by_group[group]:
                sampled_id = f"{label.item_id}#bootstrap-{sample_index}"
                sample_labels.append(replace(label, item_id=sampled_id))
                for arm_id in sampled_predictions:
                    sampled_predictions[arm_id].append(
                        replace(prediction_maps[arm_id][label.item_id], item_id=sampled_id))
        sample_label_tuple = tuple(sample_labels)
        baseline = _metrics(
            sample_label_tuple, tuple(sampled_predictions["A"]))["precision_at_3"]
        for arm_id in differences:
            comparison = _metrics(
                sample_label_tuple, tuple(sampled_predictions[arm_id]))["precision_at_3"]
            if baseline is not None and comparison is not None:
                differences[arm_id].append(comparison - baseline)
    intervals: dict[str, Any] = {}
    for arm_id, values in differences.items():
        values.sort()
        if values:
            intervals[arm_id] = {
                "metric": "precision_at_3_difference_vs_A",
                "lower_95": values[int(0.025 * (len(values) - 1))],
                "upper_95": values[int(0.975 * (len(values) - 1))],
                "replicates": len(values),
            }
        else:
            intervals[arm_id] = {"metric": "precision_at_3_difference_vs_A",
                                 "lower_95": None, "upper_95": None, "replicates": 0}
    return {
        "schema_version": 1, "kind": "PROSPECTIVE_EVALUATION_REPORT",
        "protocol_id": protocol.protocol_id, "protocol_hash": protocol.source_hash,
        "split": split, "groups": len(groups), "items": len(labels), "arms": metrics,
        "grouped_bootstrap": intervals,
        "release_decision": "HUMAN_REVIEW_REQUIRED",
        "claim": "No incremental-value, scientific-readiness or superiority claim is made automatically.",
    }
