"""Real captured expression workflow-coverage facets drive the provider annotation.

The body under ``fixtures/gdc/expression_coverage`` was captured anonymously from
the GDC API on 2026-09-26 for TCGA-LUAD (open files, Gene Expression
Quantification, one aggregate request). Workflow coverage and the single-family
source annotation must reproduce from those pinned bytes alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cancerjev.gdc.parsers import ResponseMeta, parse_file_facets
from cancerjev.research.acquisition import _expression_annotation, _expression_workflow_coverage

FIXTURES = Path(__file__).parent / "fixtures" / "gdc" / "expression_coverage"


def _load(name: str) -> tuple[bytes, ResponseMeta]:
    body = (FIXTURES / f"{name}.body").read_bytes()
    meta = json.loads((FIXTURES / f"{name}.meta.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(body).hexdigest() == meta["body_sha256"], f"fixture {name} changed"
    return body, ResponseMeta(
        endpoint=meta["endpoint"], method=meta["method"], request_hash="fixture",
        response_sha256=meta["body_sha256"], artifact_id=None, retrieved_at=meta["retrieved_at"],
        source_release="fixture", completeness="COMPLETE",
    )


def test_real_expression_coverage_capture_is_complete_and_single_family():
    facets = parse_file_facets(*_load("luad_expression_workflow_facets"))

    assert facets.total_open_files == 601
    assert facets.facet("access") == {"open": 601}
    workflows, counts, strategies, complete, warnings = _expression_workflow_coverage(
        "TCGA-LUAD", facets)
    assert workflows == ("STAR - Counts",)
    assert counts == (("STAR - Counts", 601),)
    assert strategies == ("RNA-Seq",)
    assert complete is True
    assert warnings == ()

    annotation, notes = _expression_annotation("TCGA-LUAD", workflows, strategies, complete)
    assert annotation == {"workflow_family": "STAR_COUNTS", "strategy": "RNA-Seq",
                          "annotation_context": "GENCODE_V36"}
    assert notes == []
