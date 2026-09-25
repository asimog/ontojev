"""Canonical modality union: nominations, CNV findings, review marking and gates."""

from __future__ import annotations

import pytest

from cancerjev.domain.codecs import read_state, write_state
from cancerjev.domain.discovery import (
    CNV_DROP_REASON,
    CNV_JEV_REVIEW_CONFLICT_TRIGGER,
    CNV_RETAIN_REASON,
    CNV_SCAN_LIMITATIONS,
    CNV_SCAN_SELECTION_RULE,
    CnvCategorySummary,
    CnvDisposition,
    CnvGeneEvidence,
    CnvProjectCall,
    CnvProjectScanResult,
    cnv_scan_summary_method,
)
from cancerjev.domain.measurements import Acquisition, OperationalSource, ScientificSource
from cancerjev.domain.scientific import (
    CnvProjectFinding,
    Lane,
    UnavailableLane,
    UnavailableStatus,
    cnv_category,
)
from cancerjev.gdc.parsers import PARSER_VERSION
from cancerjev.research.cutover import (
    PENDING_REVIEW_WARNING,
    UNION_SELECTION_RULE_ID,
    CutoverError,
    compose_discovery_states,
)
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.research.expression_discovery import run_expression_discovery
from cancerjev.research.specs import LUAD_RESEARCH_V1
from tests.integration.replay import GENES, ReplayTransport

G1, G2 = GENES[0], GENES[1]


def _emit_box(repository, run_id: str) -> tuple[list[dict], object]:
    events: list[dict] = []

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        events.append(repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                              message=message, **kwargs))
    return events, emit


def _lanes(runtime, spec=LUAD_RESEARCH_V1):
    _, repository, artifacts = runtime
    run_id = repository.create_run("modality-union", mode="LIVE", fixture_id=None,
                                   fixture_version=None, scope={"purpose": "UNION"})
    _, emit = _emit_box(repository, run_id)
    transport = ReplayTransport(artifacts, run_id, repository=repository)
    mutation = run_mutation_discovery(run_id, transport, repository, artifacts, emit, spec)
    expression = run_expression_discovery(run_id, transport, repository, artifacts, emit, spec)
    return mutation, expression


def _cnv_result(mutation, calls: tuple[CnvProjectCall, ...], *,
                release: str | None = None) -> CnvProjectScanResult:
    source = OperationalSource(
        source=ScientificSource(
            endpoint="/cnv_occurrences/shard-evidence", request_hash="a" * 64,
            response_hash="b" * 64, parser_version=PARSER_VERSION,
            release=release or mutation.release, acquisition=Acquisition.COMPLETE),
        attempt_id="shard-0", artifact_id="shard-0", retrieved_at="2026-09-26T00:00:00Z",
        bytes_read=0, latency_ms=None, http_status=None, cache_hit=True)
    return CnvProjectScanResult(
        LUAD_RESEARCH_V1.spec_id, mutation.cohort_id, mutation.project_id,
        release or mutation.release, CNV_SCAN_SELECTION_RULE, 25, 4,
        cnv_scan_summary_method(), calls, (source,), (), CNV_SCAN_LIMITATIONS)


def _call(gene_id: str, category: str, cases: tuple[str, ...], *,
          disposition: CnvDisposition, reason: str, trigger: str | None = None,
          conflicts: tuple[str, ...] = ()) -> CnvProjectCall:
    evidence = CnvGeneEvidence(
        gene_id, (CnvCategorySummary(category, cnv_category(category), tuple(sorted(cases))),),
        ("ASCAT3",), tuple(sorted(conflicts)), (), len(cases))
    return CnvProjectCall(evidence, disposition, reason, trigger)


def test_union_includes_every_nominated_modality_with_typed_provenance(runtime):
    mutation, expression = _lanes(runtime)
    cases = expression.population.examined_ids[:5]
    cnv = _cnv_result(mutation, (
        _call(G1, "Amplification", cases, disposition=CnvDisposition.JEV_REVIEW,
              reason=CNV_JEV_REVIEW_CONFLICT_TRIGGER, trigger=CNV_JEV_REVIEW_CONFLICT_TRIGGER,
              conflicts=(cases[0],)),
        _call(G2, "Gain", (cases[0],), disposition=CnvDisposition.DROP, reason=CNV_DROP_REASON),
    ))

    states = compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)

    assert {state.entity.gene_id for state in states} == {G1, G2}
    by_gene = {state.entity.gene_id: state for state in states}
    first = by_gene[G1]
    assert first.research.gene_selection_rule == UNION_SELECTION_RULE_ID
    assert first.nominations == (("cnv", "JEV_REVIEW"), ("expression", "RETAIN"),
                                 ("mutation", "RETAINED"))
    assert PENDING_REVIEW_WARNING in first.warnings
    lane = first.projects[0].cnv
    assert isinstance(lane, CnvProjectFinding)
    assert lane.disposition == "JEV_REVIEW" and lane.review_trigger == CNV_JEV_REVIEW_CONFLICT_TRIGGER
    assert lane.conflicting_case_ids == (cases[0],)

    second = by_gene[G2]
    second_lane = second.projects[0].cnv
    assert isinstance(second_lane, CnvProjectFinding)
    assert second_lane.disposition == "DROP" and second_lane.review_trigger is None
    assert PENDING_REVIEW_WARNING not in second.warnings
    assert ("cnv", "DROP") not in second.nominations


def test_union_states_round_trip_with_nominations_and_findings(runtime):
    mutation, expression = _lanes(runtime)
    cases = expression.population.examined_ids[:5]
    cnv = _cnv_result(mutation, (
        _call(G1, "Amplification", cases, disposition=CnvDisposition.RETAIN,
              reason=CNV_RETAIN_REASON),
    ))
    state = compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)[0]

    restored = read_state(write_state(state))

    assert restored.nominations == state.nominations
    assert isinstance(restored.projects[0].cnv, CnvProjectFinding)
    assert restored.projects[0].cnv == state.projects[0].cnv
    assert restored.quality == state.quality


def test_union_refuses_a_nomination_outside_the_tested_universe(runtime):
    mutation, expression = _lanes(runtime)
    outsider = "ENSG00000000099"
    cnv = _cnv_result(mutation, (
        _call(outsider, "Amplification", expression.population.examined_ids[:5],
              disposition=CnvDisposition.RETAIN, reason=CNV_RETAIN_REASON),
    ))

    with pytest.raises(CutoverError) as failure:
        compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)

    assert failure.value.code in {"UNION_OUTSIDE_UNIVERSE", "UNION_EVIDENCE_MISSING"}


def test_union_refuses_mixed_releases(runtime):
    mutation, expression = _lanes(runtime)
    cnv = _cnv_result(mutation, (
        _call(G1, "Amplification", expression.population.examined_ids[:5],
              disposition=CnvDisposition.RETAIN, reason=CNV_RETAIN_REASON),
    ), release="Data Release OTHER - 2026-02-02")

    with pytest.raises(CutoverError) as failure:
        compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)

    assert failure.value.code == "SCOPE_MISMATCH"


def test_union_marks_genes_without_positive_cnv_as_not_observed(runtime):
    mutation, expression = _lanes(runtime)
    # Rebuild the same lanes with no CNV calls at all: every union member must carry
    # an explicit NOT_OBSERVED lane rather than an implied neutral state.
    cnv = _cnv_result(mutation, ())
    states = compose_discovery_states(mutation, expression, cnv, LUAD_RESEARCH_V1)

    for state in states:
        lane = state.projects[0].cnv
        assert isinstance(lane, UnavailableLane)
        assert lane.lane is Lane.CNV and lane.status is UnavailableStatus.NOT_OBSERVED
        assert all(modality != "cnv" for modality, _ in state.nominations)
