"""Documentation-facts contract: the checked facts table must match current code.

Failure mode protected: a doc edit (or a code version bump without re-rendering)
leaves authoritative documentation stating schema/projection/question-set/policy
versions that no longer match the owning code constants. This test fails on any
such drift so stale mutable facts cannot be reintroduced silently.
"""

from __future__ import annotations

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
