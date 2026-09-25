"""Machine-checked leakage guard: labels and known-cancer context stay out of runtime discovery.

Known-cancer context is judgment context only. Evaluation labels, external
knowledge with a non-follow-up role and the cancer-census annotation must not be
reachable from feature construction, disposition triggers or admission.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CENSUS_ALLOWED = {
    "cancerjev/domain/scientific.py",
    "cancerjev/domain/codecs.py",
    "cancerjev/domain/maturity.py",
    "cancerjev/jev/projection.py",
}
EVALUATION_MODULES = {
    "cancerjev/research/prospective.py",
    "cancerjev/research/evaluation.py",
}
EVALUATION_IMPORTERS_ALLOWED = {"cancerjev/cli/main.py"}
CENSUS_FREE_SCIENTIFIC = (
    "cancerjev/research/ranking.py",
    "cancerjev/research/discovery.py",
    "cancerjev/research/cutover.py",
    "cancerjev/science/mutation.py",
    "cancerjev/science/descriptors.py",
)


def _modules() -> list[Path]:
    return sorted((ROOT / "cancerjev").rglob("*.py"))


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(_text(path))
    return {node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None}


def test_known_cancer_context_is_confined_to_its_declared_role():
    offenders = [_relative(path) for path in _modules()
                 if "cancer_census" in _text(path) and _relative(path) not in CENSUS_ALLOWED]

    assert offenders == []


def test_discovery_runtime_never_imports_evaluation_labels():
    offenders: list[str] = []
    for path in _modules():
        if _relative(path) in EVALUATION_MODULES | EVALUATION_IMPORTERS_ALLOWED:
            continue
        for module in _imported_modules(path):
            if module in {"cancerjev.research.prospective", "cancerjev.research.evaluation"}:
                offenders.append(f"{_relative(path)} imports {module}")

    assert offenders == []


def test_disposition_and_admission_code_never_reads_the_census_field():
    offenders = [relative for relative in CENSUS_FREE_SCIENTIFIC
                 if (ROOT / relative).exists() and "cancer_census" in _text(ROOT / relative)]

    assert offenders == []
