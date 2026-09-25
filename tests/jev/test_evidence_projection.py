"""Deep evidence projection contract: typed revision fields, fail-closed identity."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from cancerjev.domain.envelopes import EvidenceRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import (
    ActionRef,
    BaselineObservation,
    CheckOutcome,
    EvidenceCheck,
    EvidenceProvenance,
    EvidenceState,
    InputArtifactRef,
    MissingEvidence,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.hypotheses import HypothesisDraft
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    EntityRef,
    MetricAvailability,
    MetricRecord,
    Quality,
    ScientificSource,
    Sufficiency,
)
from cancerjev.jev.projection import (
    EVIDENCE_INCLUDED_FIELDS,
    EVIDENCE_PROJECTION_VERSION,
    HYPOTHESIS_PROJECTION_VERSION,
    ProjectionError,
    build_evidence_projection,
    build_hypothesis_projection,
    projection_hash,
)
from cancerjev.jev.questions import DEEP_QUESTIONS, applicability_map, validate_definitions
from cancerjev.science.actions import ACTION_REGISTRY

RELEASE = "Data Release 46.0"
ENTITY = EntityRef("ENSG00000141510", "TP53", RELEASE)
ACTION = ActionRef("CHECK_EVIDENCE_INTEGRITY_V1", "1")
ACTION_PAYLOAD = [ACTION_REGISTRY["CHECK_EVIDENCE_INTEGRITY_V1"].payload()]
CHECK_IDS = (
    "COHORT_FRAME_AGREEMENT",
    "EXPRESSION_COVERAGE_ARITHMETIC",
    "MUTATION_COUNT_SCOPE",
    "TESTED_UNIVERSE_REPRODUCIBLE",
    "RESPONSE_ARTIFACT_INTEGRITY",
)


def _check(check_id: str, outcome: str = "VERIFIED") -> EvidenceCheck:
    not_observed = outcome == "NOT_OBSERVED"
    return EvidenceCheck(
        check_id=check_id,
        method_id="EVIDENCE_INTEGRITY_V1",
        method_version="1",
        outcome=CheckOutcome(outcome),
        claim=f"{check_id} claim",
        input_hashes=("a" * 64,),
        reason=None if outcome == "VERIFIED" else f"{check_id} reason",
        n_effective=None if not_observed else 1,
        observed=canonical_json({"value": 1}),
        expected=canonical_json({}),
        notes=(),
        limitations=(),
        missing_count=1 if not_observed else 0,
        missing_reason="RECORDED_EVIDENCE_DOES_NOT_PERMIT_VERIFICATION" if not_observed else None,
    )


def _quality() -> Quality:
    return Quality(Acquisition.COMPLETE, Sufficiency.SUFFICIENT, Compatibility.VERIFIED, ())


def _source(endpoint: str = "/cases") -> ScientificSource:
    return ScientificSource(endpoint, "a" * 64, "b" * 64, "gdc-parser-v1", RELEASE,
                            Acquisition.COMPLETE)


def _provenance(*, input_ref: str = "artifact-2") -> EvidenceProvenance:
    return EvidenceProvenance(
        gdc_release=RELEASE, sources=(_source(),), methods=(),
        environment_hash="c" * 64, action_registry_version="2",
        selection_artifact_sha256="d" * 64,
        input_artifacts=(InputArtifactRef("RESPONSE_ARTIFACT", input_ref, "e" * 64, True),),
    )


def _project_evidence() -> tuple[ProjectEvidenceRow, ...]:
    return (ProjectEvidenceRow(
        project_id="TCGA-LUAD",
        affected_case_count=MetricRecord.observed_value(393, "cases"),
        examined_cases=MetricRecord.observed_value(585, "cases"),
        project_case_with_ssm=MetricRecord.observed_value(573, "cases"),
        cases_with_expression=MetricRecord.observed_value(518, "cases"),
        missing_measurements=MetricRecord.observed_value(67, "cases"),
    ),)


def _missing_evidence() -> tuple[MissingEvidence, ...]:
    return (MissingEvidence("new_gdc_measurement", MetricAvailability.NOT_ACQUIRED,
                            "no acquisition is authorized"),)


def _revision(*, evidence_state_id: str = "evidence-1", evidence_hash: str = "f" * 64,
              checks: tuple[EvidenceCheck, ...] | None = None, source_state_id: str = "state-1",
              state_artifact_id: str = "artifact-1", input_ref: str = "artifact-2",
              action: ActionRef | None = ACTION) -> EvidenceRecord:
    checks = tuple(_check(check_id) for check_id in CHECK_IDS) if checks is None else checks
    revision = EvidenceState(
        entity=ENTITY, accepted_state_hash="a" * 64,
        source_state=SourceStateBinding(source_state_id, "a" * 64, state_artifact_id, "b" * 64),
        parent_evidence_hash="9" * 64, revision_index=1, action=action,
        puzzle=ResearchPuzzle("DETERMINISTIC_ACTION_REGISTRY", "revision question",
                              "revision interpretation",
                              (action.action_id,) if action is not None else ()),
        checks=checks, baseline_observations=(), project_evidence=_project_evidence(),
        missing_evidence=_missing_evidence(), quality=_quality(), warnings=(),
        provenance=_provenance(input_ref=input_ref),
    )
    return EvidenceRecord(evidence_state_id, evidence_hash, revision)


def _baseline_record() -> EvidenceRecord:
    observation = BaselineObservation(
        method_id="MUTATION_AFFECTED_CASE_COUNT_V1", method_version="1",
        observed=canonical_json({"value": 10, "unit": "cases"}), availability="OBSERVED",
        n_effective=60, missingness_count=0, missingness_reason=None,
        notes=("project TCGA-LUAD",), limitations=(),
    )
    revision = EvidenceState(
        entity=ENTITY, accepted_state_hash="a" * 64,
        source_state=SourceStateBinding("state-1", "a" * 64, "artifact-1", "b" * 64),
        parent_evidence_hash=None, revision_index=0, action=None,
        puzzle=ResearchPuzzle("STATISTICAL_STATE_BASELINE", "baseline question",
                              "baseline interpretation", ()),
        checks=(), baseline_observations=(observation,), project_evidence=_project_evidence(),
        missing_evidence=_missing_evidence(), quality=_quality(), warnings=(),
        provenance=_provenance(),
    )
    return EvidenceRecord("evidence-0", "f" * 64, revision)


def test_projection_is_deterministic_and_operational_id_free():
    first = build_evidence_projection(_revision(), ACTION_PAYLOAD)
    second = build_evidence_projection(_revision(), ACTION_PAYLOAD)
    altered = _revision(evidence_state_id="evidence-other", source_state_id="state-other",
                        state_artifact_id="artifact-other", input_ref="artifact-other")
    renamed = build_evidence_projection(altered, ACTION_PAYLOAD)
    assert first == second
    assert projection_hash(first) == projection_hash(renamed)
    assert first["projection_version"] == EVIDENCE_PROJECTION_VERSION
    assert first["revision"]["iteration"] == 1
    assert first["revision"]["source_state_hash"] == "a" * 64
    assert first["revision"]["evidence_hash"] == "f" * 64
    assert first["revision"]["evidence_present"] is True
    assert first["revision"]["integrity_observed"] is True
    assert "state_id" not in first["revision"]
    assert "evidence_state_id" not in json.dumps(first)
    assert "artifact-2" not in json.dumps(first)


def test_projection_tracks_scientific_changes():
    baseline = build_evidence_projection(_revision(), ACTION_PAYLOAD)
    changed_checks = list(_check(check_id) for check_id in CHECK_IDS)
    changed_checks[0] = _check("COHORT_FRAME_AGREEMENT", "CONTRADICTED")
    changed = _revision(checks=tuple(changed_checks))
    assert projection_hash(build_evidence_projection(changed, ACTION_PAYLOAD)) != \
        projection_hash(baseline)
    rehashed = _revision(evidence_hash="0" * 64)
    assert projection_hash(build_evidence_projection(rehashed, ACTION_PAYLOAD)) != \
        projection_hash(baseline)


def test_projection_signals_drive_deep_applicability():
    projection = build_evidence_projection(_revision(), ACTION_PAYLOAD)
    assert projection["revision"]["evidence_present"] is True
    assert projection["revision"]["integrity_observed"] is True
    rules = applicability_map(projection, DEEP_QUESTIONS)
    assert set(rules) == {definition.question_id for definition in DEEP_QUESTIONS}
    assert all(rule["applicable"] for rule in rules.values())

    degraded = list(_check(check_id) for check_id in CHECK_IDS)
    degraded[3] = _check("TESTED_UNIVERSE_REPRODUCIBLE", "NOT_OBSERVED")
    degraded[4] = _check("RESPONSE_ARTIFACT_INTEGRITY", "NOT_OBSERVED")
    projection = build_evidence_projection(_revision(checks=tuple(degraded)), ACTION_PAYLOAD)
    rules = applicability_map(projection, DEEP_QUESTIONS)
    assert rules["revision_reliable"]["applicable"] is False
    assert rules["evidence_sufficient_for_next_step"]["applicable"] is True

    contradicted = list(degraded)
    contradicted[4] = _check("RESPONSE_ARTIFACT_INTEGRITY", "CONTRADICTED")
    projection = build_evidence_projection(_revision(checks=tuple(contradicted)), ACTION_PAYLOAD)
    assert applicability_map(projection, DEEP_QUESTIONS)["revision_reliable"]["applicable"] is True


def test_baseline_observations_project_with_null_outcome():
    projection = build_evidence_projection(_baseline_record(), ACTION_PAYLOAD)
    assert projection["action"] is None
    observation = projection["observations"][0]
    assert observation["check_id"] == "MUTATION_AFFECTED_CASE_COUNT_V1"
    assert observation["outcome"] is None
    assert observation["availability"] == "OBSERVED"
    assert projection["revision"]["evidence_present"] is True
    assert projection["quality"]["checks_total"] == 0


def test_action_block_and_eligible_actions_are_declared():
    projection = build_evidence_projection(_revision(), ACTION_PAYLOAD)
    action = projection["action"]
    assert action["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert action["method_id"] == "EVIDENCE_INTEGRITY_V1"
    assert action["method_version"]
    assert action["unit"]
    assert action["required_evidence"]
    eligible = projection["eligible_actions"]
    assert eligible[0]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    assert eligible[0]["question"]
    assert projection["limitations"], "the revision limitations must stay visible"


def test_projection_byte_cap_fails_closed(monkeypatch):
    monkeypatch.setattr("cancerjev.jev.projection.PROJECTION_BYTE_CAP", 10)
    with pytest.raises(ProjectionError) as exc:
        build_evidence_projection(_revision(), ACTION_PAYLOAD)
    assert exc.value.code == "PROJECTION_TOO_LARGE"


def test_included_fields_declare_the_deep_contract():
    assert "revision.evidence_present" in EVIDENCE_INCLUDED_FIELDS
    assert "observations[].outcome" in EVIDENCE_INCLUDED_FIELDS
    assert "eligible_actions[]" in EVIDENCE_INCLUDED_FIELDS


def test_deep_question_set_is_valid_and_carries_full_semantics():
    validate_definitions(DEEP_QUESTIONS)
    assert len(DEEP_QUESTIONS) == 5
    for definition in DEEP_QUESTIONS:
        assert len(definition.instructions) > 80
        assert definition.criteria
        assert definition.applicability_rule in {"revision_evidence_present", "integrity_observed"}


def test_hypothesis_projection_carries_text_verbatim_and_excludes_run_ids():
    draft = HypothesisDraft(
        label="GENERATED HYPOTHESIS — NOT EVIDENCE", generator="deterministic-template-v1",
        generator_model=None, statement="A bounded statement.",
        proposed_mechanism="A proposed mechanism.", predictions=("prediction",),
        contradicted_if=("contradiction",), distinguishing_tests=(),
        required_evidence=("required",), unsupported_assumptions=("assumption",),
    )
    first = build_hypothesis_projection(draft, _revision(), eligible_actions=ACTION_PAYLOAD)
    assert first["projection_version"] == HYPOTHESIS_PROJECTION_VERSION
    assert first["hypothesis"]["statement"] == "A bounded statement."
    assert first["hypothesis"]["label"] == draft.label
    assert first["hypothesis"]["generator"] == "deterministic-template-v1"
    assert first["hypothesis"]["distinguishing_tests"] == []
    assert "hypothesis_id" not in json.dumps(first)
    assert first["eligible_actions"][0]["action_id"] == "CHECK_EVIDENCE_INTEGRITY_V1"
    changed = replace(draft, statement="A different statement.")
    assert projection_hash(build_hypothesis_projection(changed, _revision(),
                                                       eligible_actions=ACTION_PAYLOAD)) != \
        projection_hash(first)
