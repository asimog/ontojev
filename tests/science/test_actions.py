"""Registered deterministic action contract tests. Offline and provider-free.

Integrity checks run over a real typed ``StatisticalState`` produced by the
production pipeline from provider-shaped replay data; revision checks run over an
E1 ``EvidenceState`` produced by the production deep machinery. Missing or
unavailable retained artifacts are NOT_OBSERVED, never a silent pass.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace

import pytest

from cancerjev.domain.codecs import evidence_identity, read_state, state_identity, write_state
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import ActionRef, EvidenceState
from cancerjev.domain.measurements import (
    Acquisition,
    ContractError,
    MetricRecord,
    ScientificSource,
)
from cancerjev.domain.scientific import StatisticalState
from cancerjev.gdc.parsers import (
    GeneCaseCounts,
    ResponseMeta,
    parse_gene_case_counts,
    parse_genes,
    parse_projects,
    parse_top_mutated_genes,
)
from cancerjev.research.acquisition import acquire_mutation_counts, acquire_project_frame
from cancerjev.research.deep import CandidateEvidence, _baseline_evidence, _followup_evidence
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.science.actions import (
    ACTION_REGISTRY,
    ACTION_REGISTRY_VERSION,
    CHECK_CONTRADICTED,
    CHECK_NOT_OBSERVED,
    CHECK_VERIFIED,
    OUTCOME_COMPLETED,
    ActionError,
    _check_frame_agreement,
    eligibility,
    eligible_actions,
    execute,
)
from cancerjev.science.methods import compute_statistical_state
from tests.integration.replay import (
    GENES,
    PROJECTS,
    ReplayTransport,
    counts_body,
    discovery_body,
    genes_body,
    projects_body,
)

ACTION_ID = "CHECK_EVIDENCE_INTEGRITY_V1"
REVISION_ACTION_ID = "CHECK_REVISION_FAITHFULNESS_V1"
RELEASE = "Data Release TEST - 2026-01-01"
GENE = GENES[0]
OTHER_GENE = GENES[1]


def _meta(endpoint: str, body: bytes) -> ResponseMeta:
    return ResponseMeta(endpoint=endpoint, method="GET", request_hash="r" * 64,
                        response_sha256=hashlib.sha256(body).hexdigest(), artifact_id=None,
                        retrieved_at="2026-09-25T00:00:00Z", source_release=RELEASE,
                        completeness="COMPLETE")


def _gene(gene_id: str = GENE):
    body = genes_body()
    return {record.gene_id: record for record in parse_genes(body, _meta("/genes", body))}[gene_id]


def _scope_meta() -> dict:
    spec = LUAD_RESEARCH_V1
    return {
        "gdc_release": RELEASE, "examined_case_frame": "ALL_CASES_PAGINATED",
        "scope_hash": "scope-hash", "spec_id": spec.spec_id,
        "research_spec": spec.as_dict(), "domain": spec.cohort.domain,
        "cohort": spec.cohort.cohort_id, "project_id": spec.cohort.project_id,
        "cohort_selection_rule": spec.cohort_selection_rule(),
        "gene_selection_rule": spec.gene_selection_rule(),
    }


def _selection_payload(selected: tuple[str, ...] = tuple(GENES)) -> dict:
    return {"selected_gene_ids": list(selected), "provider_ranked_genes": list(selected)}


def _discovery_meta(selection_artifact_id: str, *, examined_genes_n: int = 2) -> dict:
    return {
        "method_id": "MUTATION_DISCOVERY_V1", "examined_genes_ref": selection_artifact_id,
        "examined_genes_hash": hashlib.sha256(canonical_json(_selection_payload())).hexdigest(),
        "examined_genes_n": examined_genes_n, "rank_in_lane": 1, "observed_in_project_count": 1,
        "ranking_rule": LUAD_RESEARCH_V1.gene_selection_rule(), "selected_gene_ids": tuple(GENES),
    }


def _counts(*, drop_gene: str | None = None) -> GeneCaseCounts:
    document = json.loads(counts_body())
    for bucket in document["aggregations"]["projects"]["buckets"]:
        entries = bucket["genes"]["my_genes"]["gene_id"]["buckets"]
        if drop_gene is not None:
            entries[:] = [entry for entry in entries if entry["key"] != drop_gene]
        bucket["doc_count"] = sum(entry["doc_count"] for entry in entries)
    document["hits"]["total"]["value"] = sum(
        bucket["doc_count"] for bucket in document["aggregations"]["projects"]["buckets"])
    body = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    return parse_gene_case_counts(body, _meta("/analysis/top_cases_counts_by_genes", body))


def _tamper(record, **attributes):
    """Simulate a corrupted persisted record without touching production types."""
    clone = copy.deepcopy(record)
    for name, value in attributes.items():
        object.__setattr__(clone, name, value)
    return clone


def _checks(outcome) -> dict:
    return {check.check_id: check.outcome for check in outcome.checks}


@dataclass(frozen=True)
class _Evidence:
    state: StatisticalState
    state_artifact_id: str
    state_artifact_sha256: str
    selection_artifact_id: str
    blobs: dict[str, bytes]
    record: StateRecord
    baseline: EvidenceState
    revision: EvidenceState
    outcome: object


def _build(runtime, *, drop_columns: int = 0, empty_expression: bool = False,
           drop_gene: str | None = None, examined_genes_n: int = 2,
           blank_cell: bool = False) -> _Evidence:
    _, repository, artifacts = runtime
    run_id = repository.create_run("actions-test-worker", mode="LIVE", scope={
        "spec_id": LUAD_RESEARCH_V1.spec_id, "selected_project_ids": ["TCGA-LUAD"]})
    transport = ReplayTransport(
        artifacts, run_id, repository=repository, drop_value_columns=drop_columns,
        empty_expression_projects={"TCGA-LUAD"} if empty_expression else set())
    body = projects_body(PROJECTS, "TCGA-LUAD")
    project = parse_projects(body, _meta("/projects", body))[0]
    discovery_bytes = discovery_body("TCGA-LUAD")
    hits = parse_top_mutated_genes(
        discovery_bytes, _meta("/analysis/top_mutated_genes_by_project", discovery_bytes))
    frame, frame_sources, frame_warnings = acquire_project_frame(
        transport, project, LUAD_RESEARCH_V1.acquisition, RELEASE, list(GENES),
        {hit.gene_id: hit for hit in hits})
    if blank_cell:
        values = frame.expression_values
        row = dict(values.values[GENE])
        blank_case = sorted(row)[3]
        row[blank_case] = None
        frame = replace(frame, expression_values=replace(
            values, values={**values.values, GENE: row}))
    mutation = acquire_mutation_counts(transport, list(GENES), RELEASE)
    counts = mutation.counts if drop_gene is None else _counts(drop_gene=drop_gene)

    selection_bytes = canonical_json(_selection_payload())
    selection_artifact = artifacts.publish(f"runs/{run_id}/selection/examined_genes.json",
                                           selection_bytes, "application/json", "gdc-gene-selection")
    repository.register_artifact(selection_artifact, run_id)
    state = compute_statistical_state(
        gene=_gene(), frames=[frame], counts=counts, coverage=mutation.coverage,
        sources=frame_sources + mutation.sources,
        warnings=list(frame_warnings) + list(mutation.warnings),
        scope_meta=_scope_meta(),
        discovery_meta=_discovery_meta(selection_artifact.artifact_id,
                                       examined_genes_n=examined_genes_n))
    state_bytes = write_state(state)
    state_artifact = artifacts.publish(
        f"runs/{run_id}/statistical_states/{state.entity.gene_id}.json", state_bytes,
        "application/json", "statistical-state")
    repository.register_artifact(state_artifact, run_id)

    blobs = {artifact.artifact_id: artifacts.read(artifact.relative_path)
             for artifact in transport.published}
    blobs[selection_artifact.artifact_id] = selection_bytes
    blobs[state_artifact.artifact_id] = state_bytes

    record = StateRecord("state-live", state_identity(state), state)
    candidate = CandidateEvidence(
        candidate_id="candidate-1", entity=state.entity, promotion_slot=1,
        state_id="state-live", record=record, state_artifact_id=state_artifact.artifact_id,
        state_artifact_sha256=state_artifact.sha256)
    outcome = execute(ACTION_ID, state, read_artifact=blobs.get)
    baseline = _baseline_evidence(record, candidate, run_id=run_id, eligible_ids=[ACTION_ID])
    revision = _followup_evidence(outcome, candidate, record, run_id=run_id, iteration=1,
                                  previous_evidence_id="evidence-0",
                                  previous_evidence_hash=evidence_identity(baseline))
    return _Evidence(state, state_artifact.artifact_id, state_artifact.sha256,
                     selection_artifact.artifact_id, blobs, record, baseline, revision, outcome)


# ------------------------------------------------------------------ contracts


def test_registered_actions_have_explicit_contracts():
    assert ACTION_REGISTRY_VERSION == "2"
    integrity = ACTION_REGISTRY[ACTION_ID]
    assert integrity.version == "1" and integrity.input_kind == "STATISTICAL_STATE"
    assert integrity.method_id == "EVIDENCE_INTEGRITY_V1"
    assert integrity.question and integrity.interpretation
    assert integrity.required_evidence and integrity.limitations
    assert integrity.ref()["action_id"] == ACTION_ID

    revision = ACTION_REGISTRY[REVISION_ACTION_ID]
    assert revision.version == "1" and revision.input_kind == "EVIDENCE_STATE"
    assert revision.method_id == "REVISION_FAITHFULNESS_V1"
    assert revision.question and revision.interpretation and revision.limitations
    assert revision.ref()["action_id"] == REVISION_ACTION_ID


def test_wrong_input_kind_is_refused_not_silently_skipped(runtime):
    evidence = _build(runtime)
    with pytest.raises(ActionError) as exc:
        eligible_actions(evidence.state, "EVIDENCE_STATE")
    assert exc.value.code == "WRONG_INPUT_KIND"
    with pytest.raises(ActionError) as exc:
        eligible_actions(evidence.revision, "STATISTICAL_STATE")
    assert exc.value.code == "WRONG_INPUT_KIND"


def test_fixture_or_partial_snapshot_is_ineligible():
    with pytest.raises(ActionError) as exc:
        eligible_actions({"schema_version": 1, "mode": "FAKE"}, "STATISTICAL_STATE")
    assert exc.value.code == "WRONG_INPUT_KIND"


def test_unknown_input_kind_is_refused(runtime):
    evidence = _build(runtime)
    definition = replace(ACTION_REGISTRY[ACTION_ID], input_kind="SOMETHING_ELSE")
    with pytest.raises(ActionError) as exc:
        eligibility(evidence.state, definition)
    assert exc.value.code == "UNKNOWN_INPUT_KIND"


def test_unknown_action_is_refused(runtime):
    evidence = _build(runtime)
    with pytest.raises(ActionError) as exc:
        execute("NOT_AN_ACTION", evidence.state, read_artifact=evidence.blobs.get)
    assert exc.value.code == "UNKNOWN_ACTION"


def test_missing_provenance_sources_block_eligibility(runtime):
    evidence = _build(runtime)
    stripped = _tamper(evidence.state, sources=(), operational_sources=())
    decision = eligible_actions(stripped, "STATISTICAL_STATE")[0]
    assert decision.eligible is False
    assert "PROVENANCE_SOURCES_MISSING" in decision.reasons


def test_ineligible_action_refuses_to_execute(runtime):
    evidence = _build(runtime)
    stripped = _tamper(evidence.state, sources=(), operational_sources=())
    with pytest.raises(ActionError) as exc:
        execute(ACTION_ID, stripped, read_artifact=evidence.blobs.get)
    assert exc.value.code == "ACTION_INELIGIBLE"


def test_eligible_state_passes_every_integrity_check(runtime):
    evidence = _build(runtime)
    decision = eligible_actions(evidence.state, "STATISTICAL_STATE")[0]
    assert decision.eligible is True and decision.reasons == ()
    outcome = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    assert outcome.status == OUTCOME_COMPLETED
    assert _checks(outcome) == {
        "COHORT_FRAME_AGREEMENT": CHECK_VERIFIED,
        "EXPRESSION_COVERAGE_ARITHMETIC": CHECK_VERIFIED,
        "MUTATION_COUNT_SCOPE": CHECK_VERIFIED,
        "TESTED_UNIVERSE_REPRODUCIBLE": CHECK_VERIFIED,
        "RESPONSE_ARTIFACT_INTEGRITY": CHECK_VERIFIED,
    }
    assert outcome.verified == 5 and outcome.contradictions == 0 and outcome.not_observed == 0
    assert any(item.kind == "SELECTION_ARTIFACT" and item.verified is True for item in outcome.inputs)
    assert any(item.kind == "RESPONSE_ARTIFACT" and item.verified is True for item in outcome.inputs)


# ------------------------------------------------------------------ integrity outcomes


def _affected_count_exceeds_scope(state):
    return _tamper(state, projects=tuple(
        _tamper(project, mutation=_tamper(project.mutation,
                                         affected_cases=_tamper(project.mutation.affected_cases,
                                                                value=999)))
        for project in state.projects))


def _expression_coverage_arithmetic_breaks(state):
    return _tamper(state, projects=tuple(
        _tamper(project, expression=_tamper(
            project.expression,
            coverage=_tamper(project.expression.coverage,
                             valid_ids=tuple(project.expression.coverage.valid_ids[:5]))))
        for project in state.projects))


def _lane_examined_frame_disagrees(state):
    return _tamper(state, projects=tuple(
        _tamper(project, mutation=_tamper(
            project.mutation,
            frame=_tamper(project.mutation.frame,
                          examined_ids=tuple(project.mutation.frame.examined_ids[:-1]))))
        for project in state.projects))


@pytest.mark.parametrize(("mutate", "expected_check"), [
    (_affected_count_exceeds_scope, "MUTATION_COUNT_SCOPE"),
    (_expression_coverage_arithmetic_breaks, "EXPRESSION_COVERAGE_ARITHMETIC"),
    (_lane_examined_frame_disagrees, "COHORT_FRAME_AGREEMENT"),
])
def test_inconsistent_recorded_evidence_is_contradicted(runtime, mutate, expected_check):
    evidence = _build(runtime)
    corrupt = mutate(evidence.state)
    assert isinstance(corrupt, StatisticalState)
    outcome = execute(ACTION_ID, corrupt, read_artifact=evidence.blobs.get)
    assert _checks(outcome)[expected_check] == CHECK_CONTRADICTED
    assert outcome.contradictions >= 1


def test_frame_agreement_is_not_observed_when_a_lane_records_no_examined_cases(runtime):
    evidence = _build(runtime)
    empty = _tamper(evidence.state, projects=tuple(
        _tamper(project,
                mutation=_tamper(project.mutation,
                                 frame=_tamper(project.mutation.frame, examined_ids=())),
                population=_tamper(project.population,
                                   frame=_tamper(project.population.frame, examined_ids=())))
        for project in evidence.state.projects))
    check = _check_frame_agreement(empty)
    assert check.outcome == CHECK_NOT_OBSERVED


def test_expression_coverage_is_not_observed_when_the_lane_is_unavailable(runtime):
    evidence = _build(runtime, empty_expression=True)
    outcome = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    outcomes = _checks(outcome)
    assert outcomes["EXPRESSION_COVERAGE_ARITHMETIC"] == CHECK_NOT_OBSERVED
    assert outcomes["COHORT_FRAME_AGREEMENT"] == CHECK_VERIFIED
    assert outcomes["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_VERIFIED


def test_mutation_scope_is_not_observed_when_the_gene_bucket_is_absent(runtime):
    evidence = _build(runtime, drop_gene=GENE)
    outcome = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    entries = json.loads([check for check in outcome.checks
                          if check.check_id == "MUTATION_COUNT_SCOPE"][0].observed_json)
    assert entries["projects"][0]["affected_case_count"] is None
    assert _checks(outcome)["MUTATION_COUNT_SCOPE"] == CHECK_NOT_OBSERVED
    assert outcome.contradictions == 0


def test_blank_expression_value_is_not_reported_as_self_contradiction(runtime):
    evidence = _build(runtime, blank_cell=True)
    expression = evidence.state.projects[0].expression
    assert [group.reason for group in expression.coverage.missing] == ["VALUE_MISSING_OR_NONFINITE"]
    outcome = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["EXPRESSION_COVERAGE_ARITHMETIC"] != CHECK_CONTRADICTED


def test_tampered_selection_artifact_is_contradicted(runtime):
    evidence = _build(runtime)
    blobs = dict(evidence.blobs)
    blobs[evidence.selection_artifact_id] = canonical_json({"selected_gene_ids": [OTHER_GENE]})
    outcome = execute(ACTION_ID, evidence.state, read_artifact=blobs.get)
    assert _checks(outcome)["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_CONTRADICTED


def test_selection_gene_count_mismatch_is_contradicted(runtime):
    evidence = _build(runtime, examined_genes_n=3)
    outcome = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_CONTRADICTED
    assert evidence.state.tested_context.examined_genes_n == 3


def test_absent_retained_bytes_are_not_observed_never_a_silent_pass(runtime):
    evidence = _build(runtime)
    outcome = execute(ACTION_ID, evidence.state, read_artifact=lambda _: None)
    outcomes = _checks(outcome)
    assert outcomes["TESTED_UNIVERSE_REPRODUCIBLE"] == CHECK_NOT_OBSERVED
    assert outcomes["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_NOT_OBSERVED
    assert outcomes["COHORT_FRAME_AGREEMENT"] == CHECK_VERIFIED
    assert outcome.not_observed == 2


def test_tampered_response_bytes_are_contradicted(runtime):
    evidence = _build(runtime)
    response_ref = next(iter(ref for ref in evidence.blobs
                             if ref != evidence.selection_artifact_id
                             and ref != evidence.state_artifact_id))
    blobs = dict(evidence.blobs)
    blobs[response_ref] = b"tampered-response"
    outcome = execute(ACTION_ID, evidence.state, read_artifact=blobs.get)
    assert _checks(outcome)["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_CONTRADICTED


def test_unlinked_source_attempts_are_not_observed(runtime):
    evidence = _build(runtime)
    unlinked = _tamper(evidence.state, operational_sources=tuple(
        _tamper(link, attempt_id="") if index == 0 else link
        for index, link in enumerate(evidence.state.operational_sources)))
    outcome = execute(ACTION_ID, unlinked, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["RESPONSE_ARTIFACT_INTEGRITY"] == CHECK_NOT_OBSERVED
    assert outcome.contradictions == 0


def test_execution_is_deterministic_and_leaves_the_evidence_untouched(runtime):
    evidence = _build(runtime)
    before = copy.deepcopy(evidence.state)
    first = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    second = execute(ACTION_ID, evidence.state, read_artifact=evidence.blobs.get)
    assert [check.check_id for check in first.checks] == [check.check_id for check in second.checks]
    assert first.checks == second.checks
    assert json.dumps([check.boundary_representation() for check in first.checks], sort_keys=True) == \
        json.dumps([check.boundary_representation() for check in second.checks], sort_keys=True)
    assert evidence.state == before, "a deterministic action must never rewrite the evidence it reads"


# ------------------------------------------------------------------ revision outcomes


def test_revision_action_is_eligible_only_for_a_revision(runtime):
    evidence = _build(runtime)
    revision_decisions = eligible_actions(evidence.revision, "EVIDENCE_STATE")
    assert [item.action_id for item in revision_decisions] == [REVISION_ACTION_ID]
    assert revision_decisions[0].eligible is True and revision_decisions[0].reasons == ()
    assert [item.action_id for item in eligible_actions(evidence.state, "STATISTICAL_STATE")] == [ACTION_ID]
    with pytest.raises(ActionError) as exc:
        eligible_actions(evidence.state, "EVIDENCE_STATE")
    assert exc.value.code == "WRONG_INPUT_KIND"


def test_baseline_revision_is_ineligible_for_the_revision_action(runtime):
    evidence = _build(runtime)
    decision = eligible_actions(evidence.baseline, "EVIDENCE_STATE")[0]
    assert decision.eligible is False
    assert "REVISION_ITERATION_INVALID" in decision.reasons
    assert "REVISION_PARENT_MISSING" in decision.reasons
    with pytest.raises(ActionError) as exc:
        execute(REVISION_ACTION_ID, evidence.baseline, read_artifact=evidence.blobs.get)
    assert exc.value.code == "ACTION_INELIGIBLE"


def test_action_revision_without_parent_is_not_representable(runtime):
    evidence = _build(runtime)
    with pytest.raises(ContractError):
        replace(evidence.revision, parent_evidence_hash=None)


def test_faithful_revision_verifies_provenance_identity_and_chain(runtime):
    evidence = _build(runtime)
    outcome = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=evidence.blobs.get)
    outcomes = _checks(outcome)
    assert outcomes["SOURCE_PROVENANCE_UNCHANGED"] == CHECK_VERIFIED
    assert outcomes["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == CHECK_VERIFIED
    assert outcomes["REVISION_CHAIN_LINKED"] == CHECK_VERIFIED
    assert outcome.contradictions == 0
    assert any(item.kind == "SOURCE_STATE_ARTIFACT" and item.verified is True
               for item in outcome.inputs)


def test_faithful_revision_restates_source_evidence(runtime):
    evidence = _build(runtime)
    outcome = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["SOURCE_EVIDENCE_RESTATED"] == CHECK_VERIFIED


def test_restated_metric_mismatch_is_contradicted(runtime):
    evidence = _build(runtime)
    row = evidence.revision.project_evidence[0]
    revision = replace(evidence.revision, project_evidence=(
        replace(row, affected_case_count=MetricRecord.observed_value(999, "cases")),))
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["SOURCE_EVIDENCE_RESTATED"] == CHECK_CONTRADICTED


def test_provenance_substitution_is_contradicted(runtime):
    evidence = _build(runtime)
    injected = ScientificSource("/cases", "a" * 64, "b" * 64, "gdc-parser-v1",
                                evidence.state.entity.release, Acquisition.COMPLETE)
    revision = replace(evidence.revision, provenance=replace(
        evidence.revision.provenance,
        sources=evidence.revision.provenance.sources + (injected,)))
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["SOURCE_PROVENANCE_UNCHANGED"] == CHECK_CONTRADICTED


def test_tampered_source_artifact_is_contradicted(runtime):
    evidence = _build(runtime)
    other = replace(evidence.state, warnings=evidence.state.warnings + ("altered",))
    blobs = dict(evidence.blobs)
    blobs[evidence.state_artifact_id] = write_state(other)
    outcome = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=blobs.get)
    assert _checks(outcome)["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == CHECK_CONTRADICTED


def test_unregistered_producing_action_is_contradicted(runtime):
    evidence = _build(runtime)
    revision = replace(evidence.revision, action=ActionRef("NOT_A_REGISTERED_ACTION", "1"))
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["REVISION_CHAIN_LINKED"] == CHECK_CONTRADICTED


def test_retired_producing_action_version_is_not_observed_not_contradicted(runtime):
    evidence = _build(runtime)
    revision = replace(evidence.revision, action=ActionRef(ACTION_ID, "99"))
    outcome = execute(REVISION_ACTION_ID, revision, read_artifact=evidence.blobs.get)
    assert _checks(outcome)["REVISION_CHAIN_LINKED"] == CHECK_NOT_OBSERVED
    assert outcome.contradictions == 0, "a retired action version is unverifiable, not a contradiction"


def test_unavailable_source_artifact_is_not_observed(runtime):
    evidence = _build(runtime)
    outcome = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=lambda _: None)
    outcomes = _checks(outcome)
    assert outcomes["SOURCE_EVIDENCE_RESTATED"] == CHECK_NOT_OBSERVED
    assert outcomes["SOURCE_PROVENANCE_UNCHANGED"] == CHECK_NOT_OBSERVED
    assert outcomes["SOURCE_STATE_IDENTITY_REPRODUCIBLE"] == CHECK_NOT_OBSERVED
    assert outcome.not_observed >= 3 and outcome.contradictions == 0


def test_revision_action_is_deterministic_and_leaves_the_revision_untouched(runtime):
    evidence = _build(runtime)
    before = copy.deepcopy(evidence.revision)
    first = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=evidence.blobs.get)
    second = execute(REVISION_ACTION_ID, evidence.revision, read_artifact=evidence.blobs.get)
    assert first.checks == second.checks
    assert json.dumps([check.boundary_representation() for check in first.checks], sort_keys=True) == \
        json.dumps([check.boundary_representation() for check in second.checks], sort_keys=True)
    assert evidence.revision == before


def test_revision_binding_matches_the_accepted_state(runtime):
    evidence = _build(runtime)
    assert evidence.revision.accepted_state_hash == state_identity(evidence.state)
    assert evidence.revision.source_state.state_identity_hash == state_identity(evidence.state)
    assert evidence.revision.source_state.state_artifact_id == evidence.state_artifact_id
    assert evidence.revision.source_state.state_artifact_sha256 == evidence.state_artifact_sha256
    assert read_state(evidence.blobs[evidence.state_artifact_id],
                      expected_hash=state_identity(evidence.state)) == evidence.state
