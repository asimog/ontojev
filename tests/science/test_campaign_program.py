"""Campaign selection, bounded program step and release-change classification."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cancerjev.domain.capability import ScientificReadiness
from cancerjev.domain.program import (
    CampaignStatus,
    ComparisonClass,
    ProgramState,
    ReleaseSnapshot,
    SnapshotCandidate,
)
from cancerjev.research.campaign import (
    LUAD_CAMPAIGN_V1,
    CampaignActivationError,
    require_autonomous_activation,
)
from cancerjev.research.campaign_selection import (
    IDLE_REASON,
    SELECTED_REASON,
    eligible_campaigns,
    select_next_campaign,
)
from cancerjev.research.program import run_program_once
from cancerjev.research.release_compare import compare_release_snapshots

VALIDATED = replace(LUAD_CAMPAIGN_V1, readiness=ScientificReadiness.VALIDATED_FOR_AUTONOMOUS_USE)
TP53 = "ENSG00000141510"
EGFR = "ENSG00000146648"


def test_experimental_campaigns_never_run_autonomously():
    assert LUAD_CAMPAIGN_V1.readiness is ScientificReadiness.EXPERIMENTAL

    profile, reason = select_next_campaign((LUAD_CAMPAIGN_V1,))
    assert profile is None and reason == IDLE_REASON
    with pytest.raises(CampaignActivationError):
        require_autonomous_activation(LUAD_CAMPAIGN_V1)


def test_selection_order_is_priority_then_campaign_id_never_registry_order():
    low = replace(VALIDATED, profile_id="CAMPAIGN_C", priority=1)
    high_a = replace(VALIDATED, profile_id="CAMPAIGN_A", priority=5)
    high_b = replace(VALIDATED, profile_id="CAMPAIGN_B", priority=5)

    assert [item.profile_id for item in eligible_campaigns((low, high_b, high_a))] == [
        "CAMPAIGN_A", "CAMPAIGN_B", "CAMPAIGN_C"]
    selected, reason = select_next_campaign((low, high_b, high_a))
    assert selected is high_a and reason == SELECTED_REASON


def test_program_once_runs_one_campaign_then_idles_or_blocks():
    calls: list[str] = []

    def succeed(profile) -> bool:
        calls.append(profile.profile_id)
        return True

    outcome = run_program_once(profiles=(VALIDATED,), run_campaign=succeed)
    assert calls == [VALIDATED.profile_id]
    assert outcome.state is ProgramState.CAMPAIGN_COMPLETE
    assert outcome.reason_code == "CAMPAIGN_COMPLETED"
    assert outcome.campaign_statuses == ((VALIDATED.profile_id, CampaignStatus.CAMPAIGN_COMPLETE),)

    completed = (replace(VALIDATED, status=CampaignStatus.CAMPAIGN_COMPLETE),)
    idle = run_program_once(profiles=completed, run_campaign=lambda profile: True)
    assert idle.state is ProgramState.PROGRAM_IDLE and idle.selected_profile_id is None

    blocked = run_program_once(profiles=(VALIDATED,), run_campaign=lambda profile: False)
    assert blocked.state is ProgramState.BLOCKED_NOT_READY
    assert blocked.campaign_statuses == ((VALIDATED.profile_id, CampaignStatus.BLOCKED),)


def _snapshot(**overrides) -> ReleaseSnapshot:
    arguments = {
        "campaign_id": LUAD_CAMPAIGN_V1.profile_id,
        "release": "Data Release 46.0",
        "release_commit": "a" * 40,
        "methods_hash": "b" * 64,
        "candidates": (SnapshotCandidate(TP53, 1, ("expression", "mutation"),
                                         "DESCRIPTIVE_CANDIDATE"),),
    }
    arguments.update(overrides)
    return ReleaseSnapshot(**arguments)


def test_release_comparison_uses_the_declared_vocabulary():
    before = _snapshot()
    after = _snapshot(
        release="Data Release 47.0", release_commit="c" * 40,
        candidates=(
            SnapshotCandidate(TP53, 2, ("expression", "mutation"), "DESCRIPTIVE_CANDIDATE"),
            SnapshotCandidate(EGFR, 1, ("cnv",), "DESCRIPTIVE_CANDIDATE"),
        ))

    rows = compare_release_snapshots(before, after)

    classes = {(row.gene_id, row.classification) for row in rows}
    assert (None, ComparisonClass.SOURCE_CHANGED) in classes
    assert (EGFR, ComparisonClass.NEW_CANDIDATE) in classes
    assert (TP53, ComparisonClass.RANK_CHANGED) in classes


def test_release_comparison_separates_evidence_level_and_method_changes():
    strengthened = _snapshot(candidates=(
        SnapshotCandidate(TP53, 1, ("expression", "mutation"), "STATISTICALLY_SUPPORTED"),))
    rows = compare_release_snapshots(_snapshot(), strengthened)
    assert [(row.gene_id, row.classification) for row in rows] == [
        (TP53, ComparisonClass.EVIDENCE_STRENGTHENED)]

    lost = _snapshot(release="Data Release 47.0", candidates=())
    assert compare_release_snapshots(_snapshot(), lost)[-1].classification is (
        ComparisonClass.LOST_CANDIDATE)

    method_changed = _snapshot(methods_hash="d" * 64)
    rows = compare_release_snapshots(_snapshot(), method_changed)
    assert [(row.gene_id, row.classification) for row in rows] == [
        (None, ComparisonClass.METHOD_CHANGED),
        (TP53, ComparisonClass.NOT_COMPARABLE)]


def test_release_snapshot_inputs_are_immutable_and_reject_other_campaigns():
    before = _snapshot()
    compare_release_snapshots(before, _snapshot(release="Data Release 47.0"))
    assert before.release == "Data Release 46.0"

    with pytest.raises(ValueError):
        compare_release_snapshots(before, _snapshot(campaign_id="OTHER"))
