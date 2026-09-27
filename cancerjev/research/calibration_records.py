"""Operator-side generation of preregistered calibration records.

Records are operator artifacts (``data/calibration/``); the runtime never writes
them. This module computes the metrics declared in ``docs/CALIBRATION_DESIGN.md``
from a frozen corpus slice and emits strict ``CALIBRATION_RECORD`` objects that
``research/calibration.py`` validates. Only thresholds whose declared metric is
computable on the given corpus are produced; label-dependent thresholds (Wide
admission) are refused here until blinded held-out labels exist.

The mutation family is computed from the frozen DR46 reconciliation panel: the
per-gene ``/ssm_occurrences`` captures under
``tests/reconciliation/fixtures/reconciliation_dr46``. Distinct cases follow the
production rule (every record's case counts once per annotated gene); positions
follow the canonical-transcript rows (``transcript.is_canonical is True`` and
``transcript.protein_start``). Statistics are gene-level bootstraps with a fixed
seed, so a record is reproducible from its corpus hash alone.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.research.calibration import (
    CALIBRATION_RECORD_SCHEMA_VERSION,
    THRESHOLDS_BY_ID,
)

BOOTSTRAP_SEED = 20260927
BOOTSTRAP_REPLICATES = 200
CORPUS_HASH_KIND = "calibration-corpus-v1"


class CalibrationRecordError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class GeneStats:
    gene_id: str
    distinct_cases: int
    occurrence_docs: int
    positions: tuple[tuple[int, int], ...]


def corpus_hash(directory: Path) -> str:
    """Deterministic sha256 over the frozen corpus files (name + bytes, sorted)."""
    digest = hashlib.sha256(CORPUS_HASH_KIND.encode())
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    if not files:
        raise CalibrationRecordError("CORPUS_EMPTY", f"{directory} contains no files")
    for path in files:
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _gene_id_from_path(path: Path) -> str:
    name = path.name
    for prefix in ("C_ssm_occurrences_", "A_top_cases_counts_by_genes_"):
        if name.startswith(prefix):
            return name[len(prefix):].split(".")[0]
    raise CalibrationRecordError("CORPUS_UNSUPPORTED", f"unexpected corpus file {name}")


def _parse_documents(text: str) -> list[dict[str, Any]]:
    """Parse one or more concatenated/newline-separated JSON responses per capture."""
    documents: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index] in " \r\n\t\x00":
            index += 1
        if index >= length:
            break
        document, index = decoder.raw_decode(text, index)
        if not isinstance(document, dict):
            raise CalibrationRecordError("CORPUS_MALFORMED", "capture is not a JSON object")
        documents.append(document)
    return documents


def load_occurrence_panel(directory: Path) -> tuple[GeneStats, ...]:
    """Read the per-gene occurrence captures of the frozen reconciliation panel."""
    genes: list[GeneStats] = []
    for path in sorted(directory.glob("C_ssm_occurrences_*.body")):
        documents = _parse_documents(path.read_text(encoding="utf-8"))
        cases: set[str] = set()
        positions: Counter[int] = Counter()
        docs = 0
        expected_gene = _gene_id_from_path(path)
        for document in documents:
            hits = ((document.get("data") or {}).get("hits")) or []
            for hit in hits:
                if not isinstance(hit, dict):
                    raise CalibrationRecordError("CORPUS_MALFORMED", "hit is not an object")
                case_id = ((hit.get("case") or {}).get("case_id"))
                if not isinstance(case_id, str) or not case_id:
                    raise CalibrationRecordError("CORPUS_MALFORMED", "record has no case id")
                cases.add(case_id)
                gene_ids: set[str] = set()
                for consequence in (hit.get("ssm") or {}).get("consequence") or []:
                    transcript = consequence.get("transcript") or {}
                    gene_id = (transcript.get("gene") or {}).get("gene_id")
                    if isinstance(gene_id, str) and gene_id:
                        gene_ids.add(gene_id)
                    if transcript.get("is_canonical") is not True:
                        continue
                    protein_start = transcript.get("protein_start")
                    if isinstance(protein_start, int) and not isinstance(protein_start, bool):
                        positions[protein_start] += 1
                if expected_gene not in gene_ids:
                    raise CalibrationRecordError("CORPUS_MALFORMED",
                                                 f"record does not annotate {expected_gene}")
                docs += 1
        genes.append(GeneStats(expected_gene, len(cases), docs,
                               tuple(sorted(positions.items()))))
    if not genes:
        raise CalibrationRecordError("CORPUS_EMPTY", "no C_ssm_occurrences captures found")
    return tuple(genes)


def _top_positions_share(gene: GeneStats) -> tuple[int, float]:
    total = sum(count for _, count in gene.positions)
    if total == 0:
        return 0, 0.0
    top = max(count for _, count in gene.positions)
    return total, top / total


def _survivor_sets(genes: tuple[GeneStats, ...], survivors: int) -> tuple[str, ...]:
    ranked = sorted(genes, key=lambda gene: (-gene.distinct_cases, gene.gene_id))
    return tuple(gene.gene_id for gene in ranked[:survivors])


def _jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    first, second = set(left), set(right)
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def _bootstrap_mean(genes: tuple[GeneStats, ...], statistic: Any) -> float:
    rng = random.Random(BOOTSTRAP_SEED)
    total = 0.0
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = tuple(genes[rng.randrange(len(genes))] for _ in range(len(genes)))
        total += statistic(sample)
    value = total / BOOTSTRAP_REPLICATES
    if not math.isfinite(value):
        raise CalibrationRecordError("METRIC_NOT_FINITE", "bootstrap mean is not finite")
    return value


def _ratio_triggered(gene: GeneStats, ratio: float) -> bool:
    return gene.distinct_cases > 0 and gene.occurrence_docs > ratio * gene.distinct_cases


def _hotspot_triggered(gene: GeneStats, *, min_records: float, share: float) -> bool:
    total, top_share = _top_positions_share(gene)
    return total >= min_records and top_share >= share


def mutation_family_values(genes: tuple[GeneStats, ...]) -> dict[str, dict[str, float]]:
    """Declared metrics for the four mutation thresholds on the frozen panel."""
    observed_survivors = _survivor_sets(genes, 10)

    def stability(survivors: float) -> Any:
        def statistic(sample: tuple[GeneStats, ...]) -> float:
            return _jaccard(_survivor_sets(sample, int(survivors)), observed_survivors)
        return statistic

    def review_fraction(ratio: float) -> Any:
        def statistic(sample: tuple[GeneStats, ...]) -> float:
            return sum(1 for gene in sample if _ratio_triggered(gene, ratio)) / len(sample)
        return statistic

    def hotspot_fraction(min_records: float, share: float) -> Any:
        def statistic(sample: tuple[GeneStats, ...]) -> float:
            return sum(1 for gene in sample
                       if _hotspot_triggered(gene, min_records=min_records, share=share)) \
                / len(sample)
        return statistic

    declaration = THRESHOLDS_BY_ID["mutation.max_survivors"]
    values: dict[str, dict[str, float]] = {}
    values["mutation.max_survivors"] = {
        str(int(grid)): _bootstrap_mean(genes, stability(grid))
        for grid in declaration.sensitivity_grid
    }
    values["mutation.review_occurrence_ratio"] = {
        str(int(grid)): _bootstrap_mean(genes, review_fraction(grid))
        for grid in THRESHOLDS_BY_ID["mutation.review_occurrence_ratio"].sensitivity_grid
    }
    values["mutation.review_hotspot_min_records"] = {
        str(int(grid)): _bootstrap_mean(
            genes, hotspot_fraction(grid, THRESHOLDS_BY_ID[
                "mutation.review_hotspot_top_position_share"].declared_value))
        for grid in THRESHOLDS_BY_ID["mutation.review_hotspot_min_records"].sensitivity_grid
    }
    values["mutation.review_hotspot_top_position_share"] = {
        str(grid): _bootstrap_mean(
            genes, hotspot_fraction(THRESHOLDS_BY_ID[
                "mutation.review_hotspot_min_records"].declared_value, grid))
        for grid in THRESHOLDS_BY_ID[
            "mutation.review_hotspot_top_position_share"].sensitivity_grid
    }
    return values


MUTATION_METRICS = {
    "mutation.max_survivors": "gene-bootstrap mean Jaccard of the top-k survivor set against "
                              "the observed top-10 on the frozen DR46 reconciliation panel",
    "mutation.review_occurrence_ratio": "gene-bootstrap mean fraction of panel genes that the "
                                       "declared occurrence-per-case review trigger would flag",
    "mutation.review_hotspot_min_records": "gene-bootstrap mean fraction of panel genes that the "
                                          "declared hotspot review trigger would flag at the "
                                          "declared top-position share",
    "mutation.review_hotspot_top_position_share": "gene-bootstrap mean fraction of panel genes "
                                                 "that the declared hotspot review trigger would "
                                                 "flag at the declared minimum records",
}


def write_mutation_records(*, corpus: Path, out: Path) -> tuple[Path, ...]:
    """Emit one strict calibration record per mutation-family threshold."""
    genes = load_occurrence_panel(corpus)
    values = mutation_family_values(genes)
    digest = corpus_hash(corpus)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for threshold_id, grid_values in sorted(values.items()):
        declaration = THRESHOLDS_BY_ID[threshold_id]
        payload = {
            "schema_version": CALIBRATION_RECORD_SCHEMA_VERSION,
            "kind": "CALIBRATION_RECORD",
            "threshold_id": threshold_id,
            "policy_version": declaration.policy_version,
            "declared_at": utc_now(),
            "corpus_hash": digest,
            "held_out": False,
            "metric": MUTATION_METRICS[threshold_id],
            "replicates": BOOTSTRAP_REPLICATES,
            "values": grid_values,
        }
        path = out / f"{threshold_id}.json"
        path.write_bytes(canonical_json(payload))
        written.append(path)
    return tuple(written)
