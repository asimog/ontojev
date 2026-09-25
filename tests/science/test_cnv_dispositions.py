"""Merged-evidence CNV recurrence dispositions and shard-merge gates."""

from __future__ import annotations

import pytest

from cancerjev.domain.discovery import (
    CNV_DROP_REASON,
    CNV_JEV_REVIEW_CONFLICT_TRIGGER,
    CNV_RETAIN_MIN_AMPLIFICATION_CASES,
    CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES,
    CNV_RETAIN_REASON,
    CnvCategorySummary,
    CnvDisposition,
    CnvGeneEvidence,
    CnvShardEvidence,
)
from cancerjev.domain.measurements import Acquisition, OperationalSource, ScientificSource
from cancerjev.domain.scientific import CnvCategory
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.cnv_discovery import merge_cnv_shard_evidence
from cancerjev.science.descriptors import cnv_lane_disposition

GENE = "ENSG00000141510"


def _source() -> OperationalSource:
    return OperationalSource(
        source=ScientificSource(
            endpoint="/cnv_occurrences", request_hash="a" * 64, response_hash="b" * 64,
            parser_version="gdc-parser-v1", release="Data Release TEST",
            acquisition=Acquisition.COMPLETE),
        attempt_id="attempt-1", artifact_id="artifact-1",
        retrieved_at="2026-09-26T00:00:00Z", bytes_read=1024, latency_ms=1, http_status=200,
        cache_hit=False,
    )


def _gene(gene_id: str, categories: dict[str, tuple[CnvCategory, tuple[str, ...]]], *,
          callers: tuple[str, ...] = ("ASCAT3",), conflicts: tuple[str, ...] = (),
          records: int = 1) -> CnvGeneEvidence:
    return CnvGeneEvidence(
        gene_id,
        tuple(CnvCategorySummary(raw, category, tuple(sorted(case_ids)))
              for raw, (category, case_ids) in sorted(categories.items())),
        tuple(sorted(callers)), tuple(sorted(conflicts)), (), records,
    )


def _shard(index: int, case_ids: tuple[str, ...], genes: tuple[CnvGeneEvidence, ...],
           records: int = 1) -> CnvShardEvidence:
    return CnvShardEvidence(index, tuple(sorted(case_ids)), "TCGA-LUAD", "Data Release TEST",
                            genes, records, (_source(),), ())


def test_recurrence_thresholds_are_declared_case_counts():
    below = _gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                           tuple(f"case-{i}" for i in range(
                                               CNV_RETAIN_MIN_AMPLIFICATION_CASES - 1))),
                        "Gain": (CnvCategory.GAIN, tuple(f"case-g{i}" for i in range(50)))})
    assert cnv_lane_disposition(below) == (CnvDisposition.DROP, CNV_DROP_REASON, None)

    amplified = _gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                               tuple(f"case-{i}" for i in range(
                                                   CNV_RETAIN_MIN_AMPLIFICATION_CASES)))})
    assert cnv_lane_disposition(amplified) == (CnvDisposition.RETAIN, CNV_RETAIN_REASON, None)

    deleted = _gene(GENE, {"Homozygous Deletion": (CnvCategory.HOMOZYGOUS_DELETION,
                                                   tuple(f"case-{i}" for i in range(
                                                       CNV_RETAIN_MIN_HOMOZYGOUS_DELETION_CASES)))})
    assert cnv_lane_disposition(deleted)[0] is CnvDisposition.RETAIN

    deep_gain = _gene(GENE, {"Gain": (CnvCategory.GAIN,
                                      tuple(f"case-{i}" for i in range(200)))})
    assert cnv_lane_disposition(deep_gain)[0] is CnvDisposition.DROP


def test_conflict_on_a_recurrent_gene_goes_to_jev_review():
    conflicted = _gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                tuple(f"case-{i}" for i in range(6)))},
                       conflicts=("case-0",))

    disposition, reason, trigger = cnv_lane_disposition(conflicted)
    assert disposition is CnvDisposition.JEV_REVIEW
    assert reason == CNV_JEV_REVIEW_CONFLICT_TRIGGER and trigger == CNV_JEV_REVIEW_CONFLICT_TRIGGER


def test_thresholds_apply_only_after_merging_every_shard():
    first = _shard(0, ("case-0", "case-1", "case-2"),
                   (_gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                   ("case-0", "case-1", "case-2"))},
                          conflicts=("case-0",)),))
    second = _shard(1, ("case-3", "case-4", "case-5"),
                    (_gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                    ("case-3", "case-4", "case-5"))}),))

    assert cnv_lane_disposition(first.genes[0])[0] is CnvDisposition.DROP
    merged = merge_cnv_shard_evidence((first, second), expected_shards=2)
    assert len(merged) == 1
    assert cnv_lane_disposition(merged[0])[0] is CnvDisposition.JEV_REVIEW
    assert tuple(summary.case_ids for summary in merged[0].categories) == (
        ("case-0", "case-1", "case-2", "case-3", "case-4", "case-5"),)
    assert merged[0].conflicting_case_ids == ("case-0",)


def test_merge_refuses_missing_or_overlapping_shards_and_categories():
    first = _shard(0, ("case-0",), (_gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                                   ("case-0",))}),))
    third = _shard(2, ("case-9",), (_gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                                   ("case-9",))}),))
    with pytest.raises(LiveRunError) as failure:
        merge_cnv_shard_evidence((first, third), expected_shards=3)
    assert failure.value.code == "CNV_SHARDS_NOT_TERMINAL"

    overlap = _shard(1, ("case-0",), (_gene(GENE, {"Amplification": (CnvCategory.AMPLIFICATION,
                                                                     ("case-0",))}),))
    with pytest.raises(LiveRunError) as failure:
        merge_cnv_shard_evidence((first, overlap), expected_shards=2)
    assert failure.value.code == "CNV_SHARD_CASE_OVERLAP"

    remapped = _shard(1, ("case-7",), (_gene(GENE, {"Amplification": (CnvCategory.GAIN,
                                                                      ("case-7",))}),))
    with pytest.raises(LiveRunError) as failure:
        merge_cnv_shard_evidence((first, remapped), expected_shards=2)
    assert failure.value.code == "CNV_CATEGORY_MAPPING_CONFLICT"
