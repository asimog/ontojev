"""Documentation-facts contract: the checked facts table must match current code.

Failure mode protected: a doc edit (or a code version bump without re-rendering)
leaves authoritative documentation stating schema/projection/question-set/policy
versions that no longer match the owning code constants, and a production module
added without extending ``[tool.mypy] files`` silently escapes strict typing.
Both checks fail on drift so stale facts or type-coverage holes cannot be
reintroduced silently.
"""

from __future__ import annotations

import pytest
import repository_facts


def test_repository_facts_block_matches_code() -> None:
    problems = repository_facts.check_document()
    assert problems == [], "stale repository facts:\n" + "\n".join(problems)


def test_repository_facts_block_is_deterministic() -> None:
    document = repository_facts.FACTS_DOCUMENT.read_text(encoding="utf-8")
    rendered = repository_facts.render_facts().rstrip("\n")
    assert repository_facts._block(document) == rendered


def test_repository_facts_reject_drift() -> None:
    drifted = repository_facts.collect_facts()
    drifted["sqlite_schema_version"] = drifted["sqlite_schema_version"] + 1
    problems = repository_facts.check_document(drifted)
    assert any("sqlite_schema_version" in problem for problem in problems)


@pytest.mark.local_process
def test_strict_mypy_covers_every_tracked_production_module() -> None:
    problems = repository_facts.check_mypy_coverage()
    assert problems == [], "strict-mypy coverage holes:\n" + "\n".join(problems)


@pytest.mark.local_process
def test_mypy_coverage_check_rejects_a_new_unlisted_module() -> None:
    modules = repository_facts.tracked_production_modules()
    listed = repository_facts.configured_mypy_modules()
    problems = repository_facts.check_mypy_coverage(
        modules=modules + ("cancerjev/research/new_escaped_module.py",), listed=listed)
    assert any("new_escaped_module.py" in problem for problem in problems)


def test_mypy_coverage_check_rejects_stale_entries_and_undocumented_exclusions() -> None:
    problems = repository_facts.check_mypy_coverage(
        modules=("cancerjev/config.py",),
        listed=("cancerjev/config.py", "cancerjev/deleted_module.py"),
        excluded=("cancerjev/excluded_module.py",))
    assert any("deleted_module.py" in problem for problem in problems)
    assert any("excluded_module.py" in problem for problem in problems), \
        "a stale or undocumented exclusion must be reported"


def test_mypy_coverage_check_honors_a_documented_exclusion(monkeypatch) -> None:
    excluded = "cancerjev/excluded_module.py"
    monkeypatch.setattr(repository_facts, "MYPY_EXCLUDED_MODULES", (excluded,))
    monkeypatch.setattr(repository_facts, "MYPY_EXCLUSION_REASONS", {excluded: "test-only"})
    problems = repository_facts.check_mypy_coverage(modules=(excluded,), listed=())
    assert problems == []
