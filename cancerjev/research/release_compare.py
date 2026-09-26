"""Release-comparison classifier over persisted campaign snapshots.

Classification is operational and decision-level only: source or method changes
are reported as such and candidate rows become NOT_COMPARABLE, because biology is
never inferred from a source or method change. No acquisition happens here.
"""

from __future__ import annotations

from cancerjev.domain.program import (
    ComparisonClass,
    ComparisonRow,
    ReleaseSnapshot,
    SnapshotCandidate,
)
from cancerjev.domain.scientific import EVIDENCE_LEVEL_ORDER

RELEASE_COMPARISON_POLICY_VERSION = "release-comparison-v1"


def _rank_order(rank: int | None) -> int:
    return rank if rank is not None else 1_000_000


def _level_rank(level: str) -> int:
    known = [member.value for member in EVIDENCE_LEVEL_ORDER]
    return known.index(level) if level in known else -1


def compare_release_snapshots(before: ReleaseSnapshot, after: ReleaseSnapshot,
                              ) -> tuple[ComparisonRow, ...]:
    """Deterministic diff in the declared vocabulary; incompatible rows fail closed."""
    if before.campaign_id != after.campaign_id:
        raise ValueError("release snapshots must describe the same campaign")
    rows: list[ComparisonRow] = []
    methods_changed = before.methods_hash != after.methods_hash
    if methods_changed:
        rows.append(ComparisonRow(
            None, ComparisonClass.METHOD_CHANGED,
            f"method profile changed ({before.methods_hash[:12]} -> {after.methods_hash[:12]})"))
    if before.release_commit != after.release_commit:
        rows.append(ComparisonRow(
            None, ComparisonClass.SOURCE_CHANGED,
            f"pinned source commit changed ({before.release_commit} -> {after.release_commit})"))
    before_by = {item.gene_id: item for item in before.candidates}
    after_by = {item.gene_id: item for item in after.candidates}
    for gene_id in sorted(set(before_by) | set(after_by)):
        older = before_by.get(gene_id)
        newer = after_by.get(gene_id)
        if older is None:
            rows.append(ComparisonRow(gene_id, ComparisonClass.NEW_CANDIDATE,
                                      f"candidate absent in {before.release}"))
            continue
        if newer is None:
            rows.append(ComparisonRow(gene_id, ComparisonClass.LOST_CANDIDATE,
                                      f"candidate absent in {after.release}"))
            continue
        if methods_changed:
            rows.append(ComparisonRow(
                gene_id, ComparisonClass.NOT_COMPARABLE,
                "method profile changed, so the candidate delta is not assigned to biology"))
            continue
        row = _compare_candidate(older, newer)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _compare_candidate(older: SnapshotCandidate, newer: SnapshotCandidate,
                       ) -> ComparisonRow | None:
    if older.modalities != newer.modalities:
        return ComparisonRow(
            newer.gene_id, ComparisonClass.MODALITY_CHANGED,
            f"modalities {list(older.modalities)} -> {list(newer.modalities)}")
    if _rank_order(older.rank) != _rank_order(newer.rank):
        return ComparisonRow(
            newer.gene_id, ComparisonClass.RANK_CHANGED,
            f"rank {older.rank} -> {newer.rank}")
    older_level = _level_rank(older.evidence_level)
    newer_level = _level_rank(newer.evidence_level)
    if older_level != newer_level:
        classification = (ComparisonClass.EVIDENCE_STRENGTHENED if newer_level > older_level
                          else ComparisonClass.EVIDENCE_WEAKENED)
        return ComparisonRow(
            newer.gene_id, classification,
            f"evidence level {older.evidence_level} -> {newer.evidence_level}")
    return None
