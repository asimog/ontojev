"""Guard: the default offline test suite stays hermetic.

A clean checkout must be able to run the collected suite without any ignored
developer runtime artifact under ``data/runs``. Only explicitly opt-in live
modules may read local runtime data.
"""

from __future__ import annotations

from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]
NON_COLLECTED_MODULES = {"capture_reconciliation.py", "test_test_hermeticity.py"}
EXEMPT_DIRECTORIES = {"live"}
RUNTIME_DATA_PATTERNS = ('"data" / "runs"', "'data' / 'runs'", "data/runs", "data\\runs")


def test_no_collected_test_reads_ignored_runtime_data():
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        relative = path.relative_to(TESTS_ROOT)
        if path.name in NON_COLLECTED_MODULES or EXEMPT_DIRECTORIES & set(relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in RUNTIME_DATA_PATTERNS):
            offenders.append(str(relative))
    assert offenders == [], (
        "collected tests must not read ignored developer runtime data under data/runs: "
        f"{offenders}"
    )
