"""Baseline-versus-Jev decision-quality harness (offline, provider-free).

It compares the persisted baseline and Jev rankings of one run against a
pre-registered label file and reports rank-based agreement metrics with explicit
limitations. It acquires nothing, calls no model, computes no new measurement, and
never claims that a changed ranking is an improvement: with k ≤ 3, one cohort and a
selection-biased examined gene set the numbers are descriptive only. The label file
is supplied by the operator and is never produced or inferred by this repository.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cancerjev.research.ranking import BASELINE_POLICY_VERSION, JEV_POLICY_VERSION

MAX_EVALUATION_K = 3
MIN_LABEL_RATIONALE = 20

LIMITATIONS = (
    "Descriptive comparison of recorded rankings against an operator-supplied label set; it is not a "
    "statistical test.",
    "A single cohort is examined, the examined gene set is selection-biased, and k is at most 3.",
    "A changed ranking is not evidence that the research decision improved; that claim needs a "
    "pre-registered protocol and held-out labels.",
    "No measured field is recomputed or written by this harness.",
)


class EvaluationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EvaluationReport:
    run_id: str
    protocol_version: str
    label_source_hash: str
    rationale: str
    k: int
    baseline_top_k: tuple[str, ...]
    jev_top_k: tuple[str, ...]
    overlap: tuple[str, ...]
    baseline_hits: tuple[str, ...]
    jev_hits: tuple[str, ...]
    baseline_ranks: dict[str, int]
    jev_ranks: dict[str, int]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id, "protocol_version": self.protocol_version,
            "label_source_hash": self.label_source_hash, "rationale": self.rationale, "k": self.k,
            "baseline_top_k": list(self.baseline_top_k), "jev_top_k": list(self.jev_top_k),
            "overlap": list(self.overlap), "baseline_hits": list(self.baseline_hits),
            "jev_hits": list(self.jev_hits), "baseline_ranks": self.baseline_ranks,
            "jev_ranks": self.jev_ranks,
            "baseline_hits_at_k": len(self.baseline_hits), "jev_hits_at_k": len(self.jev_hits),
            "baseline_policy_version": BASELINE_POLICY_VERSION,
            "jev_policy_version": JEV_POLICY_VERSION,
            "ranking_changed": list(self.baseline_top_k) != list(self.jev_top_k),
            "limitations": list(self.limitations),
            "claim": (
                "No superiority claim is made: this report compares recorded rankings to labelled "
                "symbols and cannot establish incremental value."
            ),
        }


def load_labels(path: Path) -> dict[str, Any]:
    """Read and validate an operator-supplied, pre-registered label file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvaluationError("LABEL_FILE_UNREADABLE", str(exc)) from exc
    if not isinstance(payload, dict):
        raise EvaluationError("LABEL_FILE_MALFORMED", "the label file must be a JSON object")
    symbols = payload.get("positive_gene_symbols")
    if not isinstance(symbols, list) or not symbols or not all(
            isinstance(symbol, str) and symbol.strip() for symbol in symbols):
        raise EvaluationError("LABEL_FILE_MALFORMED", "positive_gene_symbols must be a non-empty string list")
    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or len(rationale.strip()) < MIN_LABEL_RATIONALE:
        raise EvaluationError("LABEL_FILE_MALFORMED", "a pre-registered rationale is required")
    protocol = payload.get("protocol_version")
    if not isinstance(protocol, str) or not protocol.strip():
        raise EvaluationError("LABEL_FILE_MALFORMED", "protocol_version is required")
    for field in ("declared_at", "source", "limitations"):
        if not payload.get(field):
            raise EvaluationError("LABEL_FILE_MALFORMED", f"{field} is required so the labels are auditable")
    return {
        "protocol_version": protocol, "rationale": rationale,
        "symbols": tuple(dict.fromkeys(symbol.strip() for symbol in symbols)),
        "declared_at": payload["declared_at"], "source": payload["source"],
        "limitations": tuple(str(item) for item in payload["limitations"]),
        "hash": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _rankings(run_id: str, repository: Any, artifacts: Any) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for row in repository.ranking_artifacts(run_id):
        payload = json.loads(artifacts.read(row["relative_path"], row["sha256"]))
        payloads[payload["policy_version"]] = payload
    if BASELINE_POLICY_VERSION not in payloads or JEV_POLICY_VERSION not in payloads:
        raise EvaluationError(
            "RANKINGS_MISSING",
            f"run {run_id} does not record both {BASELINE_POLICY_VERSION} and {JEV_POLICY_VERSION} rankings",
        )
    return payloads


def _top_k(payload: dict[str, Any], k: int) -> tuple[tuple[str, ...], dict[str, int]]:
    ordered = [entry["gene_symbol"] for entry in sorted(payload["entries"], key=lambda item: item["rank"])]
    ranks = {entry["gene_symbol"]: entry["rank"] for entry in payload["entries"]}
    return tuple(ordered[:k]), ranks


def evaluate_run(*, run_id: str, repository: Any, artifacts: Any, labels: dict[str, Any],
                 k: int = MAX_EVALUATION_K) -> EvaluationReport:
    """Compare one run's recorded baseline and Jev tops against pre-registered labels."""
    if not isinstance(k, int) or k < 1 or k > MAX_EVALUATION_K:
        raise EvaluationError("INVALID_K", f"k must be an integer between 1 and {MAX_EVALUATION_K}")
    positives = set(labels["symbols"])
    payloads = _rankings(run_id, repository, artifacts)
    baseline_top, baseline_ranks = _top_k(payloads[BASELINE_POLICY_VERSION], k)
    jev_top, jev_ranks = _top_k(payloads[JEV_POLICY_VERSION], k)
    return EvaluationReport(
        run_id=run_id, protocol_version=labels["protocol_version"], label_source_hash=labels["hash"],
        rationale=labels["rationale"], k=k, baseline_top_k=baseline_top, jev_top_k=jev_top,
        overlap=tuple(symbol for symbol in baseline_top if symbol in set(jev_top)),
        baseline_hits=tuple(symbol for symbol in baseline_top if symbol in positives),
        jev_hits=tuple(symbol for symbol in jev_top if symbol in positives),
        baseline_ranks={symbol: baseline_ranks.get(symbol) for symbol in labels["symbols"]},
        jev_ranks={symbol: jev_ranks.get(symbol) for symbol in labels["symbols"]},
        limitations=LIMITATIONS + labels["limitations"],
    )


def report_path(data_dir: Path, report: EvaluationReport) -> Path:
    directory = data_dir / "evaluations"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{report.run_id}-{report.label_source_hash[:12]}-k{report.k}.json"


def write_report(path: Path, report: EvaluationReport) -> Path:
    path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
