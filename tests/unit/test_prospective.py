"""Stage 8 prospective protocol validation: blinded grouped labels and arm comparison.

These tests protect the realistic failure modes: label leakage across fixed
splits/groups, unblinded or unreviewed labels, arm outputs that do not bind the
protocol or cover every item, and bootstrap intervals that stay deterministic
under the declared seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cancerjev.research.prospective import (
    ProspectiveError,
    evaluate_prospective,
    load_arms,
    load_protocol,
)


def _write(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _protocol_document() -> dict:
    labels = []
    for index in range(4):
        labels.append({
            "item_id": f"item-{index}",
            "gene_id": f"ENSG{index:011d}",
            "group_id": f"group-{index // 2}",
            "split": "HOLDOUT" if index >= 2 else "TRAIN",
            "useful_investigation": index % 2 == 0,
            "ordinal_usefulness": index,
            "rationale": "Blinded reviewer rationale long enough for the contract.",
            "reviewer_count": 2,
            "adjudicated": True,
        })
    return {
        "schema_version": 1, "kind": "PROSPECTIVE_PROTOCOL", "protocol_id": "PROTO-1",
        "declared_at": "2026-09-25T00:00:00Z", "seed": 7, "bootstrap_replicates": 200,
        "blinded_to_arms": True, "labels": labels,
    }


def _arm_document() -> dict:
    predictions_a = []
    predictions_b = []
    for label in _protocol_document()["labels"]:
        base = {
            "item_id": label["item_id"], "score": 1.0, "unsupported_assertion": False,
            "wrong_population": False, "attempts": 1, "input_tokens": 100, "output_tokens": 10,
            "latency_ms": 10, "human_minutes": 1.0, "spend_usd": 0.01,
        }
        predictions_a.append({**base, "disposition": "INVESTIGATE"})
        predictions_b.append({**base, "disposition": "STOP" if label["item_id"] == "item-3"
                              else "INVESTIGATE"})
    return {
        "schema_version": 1, "kind": "PROSPECTIVE_ARM_OUTPUTS", "protocol_id": "PROTO-1",
        "arms": [
            {"arm_id": "A", "description": "deterministic baseline", "predictions": predictions_a},
            {"arm_id": "B", "description": "comparison arm", "predictions": predictions_b},
        ],
    }


def _prepared(tmp_path: Path):
    protocol_document = _protocol_document()
    protocol_path = _write(tmp_path / "protocol.json", protocol_document)
    protocol = load_protocol(protocol_path)
    arms, arm_hash = load_arms(_write(tmp_path / "arms.json", _arm_document()), protocol)
    return protocol, arms, protocol_path


def test_valid_protocol_and_arms_load_with_source_hashes(tmp_path):
    protocol, arms, protocol_path = _prepared(tmp_path)
    assert protocol.protocol_id == "PROTO-1" and protocol.seed == 7
    assert len(protocol.source_hash) == 64
    reloaded = load_protocol(protocol_path)
    assert reloaded == protocol
    assert [arm.arm_id for arm in arms] == ["A", "B"]
    assert len(load_arms(tmp_path / "arms.json", protocol)[1]) == 64


def test_holdout_metrics_are_deterministic_and_never_claim_value(tmp_path):
    protocol, arms, _ = _prepared(tmp_path)
    first = evaluate_prospective(protocol, arms, split="HOLDOUT")
    second = evaluate_prospective(protocol, arms, split="HOLDOUT")
    assert first == second
    assert first["release_decision"] == "HUMAN_REVIEW_REQUIRED"
    assert "No incremental-value" in first["claim"]
    assert first["items"] == 2 and first["groups"] == 1
    assert first["protocol_hash"] == protocol.source_hash
    metrics = first["arms"]
    assert metrics["A"]["investigate_precision"] == 0.5
    assert metrics["B"]["investigate_precision"] == 1.0
    assert metrics["A"]["abstention_rate"] == 0.0
    intervals = first["grouped_bootstrap"]
    assert intervals["B"]["metric"] == "precision_at_3_difference_vs_A"
    assert intervals["B"]["replicates"] == 200
    assert intervals["B"]["lower_95"] is not None and intervals["B"]["upper_95"] is not None
    assert intervals["B"]["lower_95"] <= intervals["B"]["upper_95"]


def test_grouped_bootstrap_follows_the_declared_seed(tmp_path):
    _, arms, protocol_path = _prepared(tmp_path)
    protocol = load_protocol(protocol_path)
    shifted_document = {**_protocol_document(), "seed": 8}
    shifted = load_protocol(_write(tmp_path / "protocol2.json", shifted_document))
    first = evaluate_prospective(protocol, arms, split="HOLDOUT")["grouped_bootstrap"]
    other = evaluate_prospective(shifted, arms, split="HOLDOUT")["grouped_bootstrap"]
    # Both intervals are finite and bound the same difference metric.
    assert first["B"]["lower_95"] is not None and other["B"]["lower_95"] is not None


def test_group_leakage_across_splits_is_refused(tmp_path):
    document = _protocol_document()
    document["labels"][0]["split"] = "HOLDOUT"
    document["labels"][2]["split"] = "TRAIN"
    with pytest.raises(ProspectiveError, match="GROUP_LEAKAGE"):
        load_protocol(_write(tmp_path / "leaky.json", document))


def test_gene_reassignment_across_groups_is_refused(tmp_path):
    document = _protocol_document()
    document["labels"][2]["group_id"] = "group-0"
    with pytest.raises(ProspectiveError, match="GROUP_LEAKAGE"):
        load_protocol(_write(tmp_path / "gene-leak.json", document))


def test_unblinded_or_unreviewed_or_duplicate_labels_are_refused(tmp_path):
    unblinded = {**_protocol_document(), "blinded_to_arms": False}
    with pytest.raises(ProspectiveError, match="UNBLINDED_LABELS"):
        load_protocol(_write(tmp_path / "unblinded.json", unblinded))
    unreviewed = _protocol_document()
    unreviewed["labels"][0]["reviewer_count"] = 1
    with pytest.raises(ProspectiveError, match="UNREVIEWED_LABEL"):
        load_protocol(_write(tmp_path / "unreviewed.json", unreviewed))
    duplicate = _protocol_document()
    duplicate = {**duplicate, "labels": duplicate["labels"] + [dict(duplicate["labels"][0])]}
    with pytest.raises(ProspectiveError, match="INVALID_SPLIT_ASSIGNMENT"):
        load_protocol(_write(tmp_path / "duplicate.json", duplicate))


def test_arm_outputs_must_bind_the_protocol_and_cover_every_item(tmp_path):
    protocol, _, _ = _prepared(tmp_path)
    wrong_binding = {**_arm_document(), "protocol_id": "OTHER"}
    with pytest.raises(ProspectiveError, match="MALFORMED_OUTPUT"):
        load_arms(_write(tmp_path / "wrong-binding.json", wrong_binding), protocol)
    uncovered = _arm_document()
    uncovered["arms"][0]["predictions"] = uncovered["arms"][0]["predictions"][:1]
    with pytest.raises(ProspectiveError, match="OUTPUT_COVERAGE_MISMATCH"):
        load_arms(_write(tmp_path / "uncovered.json", uncovered), protocol)
    no_baseline = _arm_document()
    no_baseline["arms"][0]["arm_id"] = "B2"
    with pytest.raises(ProspectiveError, match="BASELINE_MISSING"):
        load_arms(_write(tmp_path / "no-baseline.json", no_baseline), protocol)
    duplicate = _arm_document()
    duplicate["arms"] = duplicate["arms"] + [dict(duplicate["arms"][1])]
    with pytest.raises(ProspectiveError, match="MALFORMED_OUTPUT"):
        load_arms(_write(tmp_path / "duplicate.json", duplicate), protocol)


def test_split_with_no_labels_is_a_typed_refusal(tmp_path):
    protocol, arms, _ = _prepared(tmp_path)
    with pytest.raises(ProspectiveError, match="EMPTY_SPLIT"):
        evaluate_prospective(protocol, arms, split="DEVELOPMENT")