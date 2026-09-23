"""Baseline-versus-Jev evaluation harness tests. Offline and provider-free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cancerjev.research.evaluation import (
    LIMITATIONS,
    EvaluationError,
    evaluate_run,
    load_labels,
    report_path,
    write_report,
)
from cancerjev.research.ranking import BASELINE_POLICY_VERSION, JEV_POLICY_VERSION


def _labels_file(tmp_path: Path, **overrides) -> Path:
    payload = {
        "protocol_version": "test-labels-v1",
        "declared_at": "2026-09-23T00:00:00Z",
        "source": "test fixture, declared before comparison",
        "rationale": "Declared positives exist so the comparison is not post-hoc in this test.",
        "positive_gene_symbols": ["GENEONE"],
        "limitations": ["test labels only"],
        **overrides,
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _ranking(policy_version: str, symbols: list[str]) -> dict:
    return {
        "policy_version": policy_version,
        "entries": [{"gene_symbol": symbol, "rank": rank} for rank, symbol in enumerate(symbols, start=1)],
        "top_state_ids": [f"state-{symbol}" for symbol in symbols[:3]],
    }


class _Repository:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads

    def ranking_artifacts(self, run_id: str) -> list[dict]:
        return [{"relative_path": f"runs/{run_id}/rankings/{index}.json", "sha256": "a" * 64}
                for index, _ in enumerate(self._payloads)]


class _Artifacts:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads

    def read(self, relative_path: str, sha256: str | None = None) -> bytes:
        index = int(Path(relative_path).stem)
        return json.dumps(self._payloads[index]).encode()


def test_labels_require_the_declared_protocol_and_rationale(tmp_path):
    labels = load_labels(_labels_file(tmp_path))
    assert labels["symbols"] == ("GENEONE",)
    assert labels["hash"]
    with pytest.raises(EvaluationError):
        load_labels(_labels_file(tmp_path, positive_gene_symbols=[]))
    with pytest.raises(EvaluationError):
        load_labels(_labels_file(tmp_path, rationale="short"))
    with pytest.raises(EvaluationError):
        load_labels(_labels_file(tmp_path, declared_at=None))
    with pytest.raises(EvaluationError):
        load_labels(tmp_path / "missing.json")


def test_report_compares_recorded_tops_without_claiming_superiority(tmp_path):
    payloads = [
        _ranking(BASELINE_POLICY_VERSION, ["GENETWO", "GENETHREE", "GENEFOUR", "GENEONE"]),
        _ranking(JEV_POLICY_VERSION, ["GENEONE", "GENETWO", "GENETHREE", "GENEFOUR"]),
    ]
    report = evaluate_run(run_id="run-1", repository=_Repository(payloads), artifacts=_Artifacts(payloads),
                          labels=load_labels(_labels_file(tmp_path)), k=3)
    data = report.as_dict()
    assert data["baseline_top_k"] == ["GENETWO", "GENETHREE", "GENEFOUR"]
    assert data["jev_top_k"] == ["GENEONE", "GENETWO", "GENETHREE"]
    assert data["overlap"] == ["GENETWO", "GENETHREE"], "overlap keeps baseline order"
    assert data["baseline_hits"] == [] and data["jev_hits"] == ["GENEONE"]
    assert data["jev_ranks"]["GENEONE"] == 1 and data["baseline_ranks"]["GENEONE"] == 4
    assert data["ranking_changed"] is True
    assert "No superiority claim" in data["claim"]
    assert data["baseline_policy_version"] == BASELINE_POLICY_VERSION
    assert set(LIMITATIONS) <= set(data["limitations"])
    assert "test labels only" in data["limitations"]


def test_k_is_bounded_and_missing_rankings_fail_closed(tmp_path):
    labels = load_labels(_labels_file(tmp_path))
    payloads = [_ranking(BASELINE_POLICY_VERSION, ["GENEONE"]), _ranking(JEV_POLICY_VERSION, ["GENEONE"])]
    with pytest.raises(EvaluationError):
        evaluate_run(run_id="run-1", repository=_Repository(payloads), artifacts=_Artifacts(payloads),
                     labels=labels, k=9)
    only_baseline = [_ranking(BASELINE_POLICY_VERSION, ["GENEONE"])]
    with pytest.raises(EvaluationError):
        evaluate_run(run_id="run-1", repository=_Repository(only_baseline),
                     artifacts=_Artifacts(only_baseline), labels=labels, k=3)


def test_report_is_written_under_the_data_directory(tmp_path):
    labels = load_labels(_labels_file(tmp_path))
    payloads = [_ranking(BASELINE_POLICY_VERSION, ["GENEONE"]), _ranking(JEV_POLICY_VERSION, ["GENEONE"])]
    report = evaluate_run(run_id="run-1", repository=_Repository(payloads), artifacts=_Artifacts(payloads),
                          labels=labels, k=1)
    target = write_report(report_path(tmp_path, report), report)
    assert target.exists()
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["label_source_hash"] == report.label_source_hash
    assert written["k"] == 1
