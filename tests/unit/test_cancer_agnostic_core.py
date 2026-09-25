"""Guard: shared scientific/Jev modules carry no cancer-name string literals.

The literal guard protects the architecture rule that the core is
cancer-agnostic: cohort names belong in campaign profiles and fixtures, never
in question text, method identities or state reasons. It is a literal check,
not a substitute for behavioural tests.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CORE_MODULES = (
    "cancerjev/jev/questions.py",
    "cancerjev/jev/typesafe_adapter.py",
    "cancerjev/research/cutover.py",
    "cancerjev/research/dossier.py",
    "cancerjev/domain/discovery.py",
    "cancerjev/science/methods.py",
)
CANCER_TOKENS = ("LUAD", "lung adenocarcinoma", "TCGA-LUAD")


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


@pytest.mark.parametrize("relative", CORE_MODULES)
def test_core_module_strings_carry_no_cancer_name(relative: str) -> None:
    root = Path(__file__).resolve().parents[2]
    offenders = sorted({
        text for text in _string_literals(root / relative)
        if any(token.lower() in text.lower() for token in CANCER_TOKENS)
    })
    assert offenders == [], f"{relative} carries cancer-name literals: {offenders}"
