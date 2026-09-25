"""Live research dossier: deterministic JSON plus derived Markdown.

A dossier is presentation, never evidence: it assembles what the run already
recorded for one candidate — the accepted state, every immutable evidence
revision, the deterministic follow-up executions, the Jev judgments, the recorded
next moves, the generated hypotheses, the Stage 8 final candidate result and its
no-Jev comparison — with an explicit availability for every declared section and
a notice that names what the dossier does and does not support. No measurement is
computed here and no model is called.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cancerjev.domain.dossier import DOSSIER_SCHEMA_VERSION, DOSSIER_SECTIONS
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.dossier.renderer import render_markdown
from cancerjev.research.deep import stable_id
from cancerjev.science.actions import ACTION_REGISTRY
from cancerjev.storage.readers import (
    ScientificReadError,
    StoredEvidence,
    StoredHypothesis,
    StoredState,
    read_candidate_state,
    read_evaluation_record,
    read_hypothesis_record,
    read_revision_chain,
)

LIVE_NOTICE = (
    "REAL OPEN-ACCESS GDC EVIDENCE — DETERMINISTIC RESEARCH WITH GENERATED HYPOTHESES — "
    "NOT CLINICAL OR DIAGNOSTIC USE"
)
LLM_NOTICE = (
    "REAL OPEN-ACCESS GDC EVIDENCE — INCLUDES LLM-GENERATED TEXT THAT IS NOT EVIDENCE — "
    "NOT CLINICAL OR DIAGNOSTIC USE"
)
SYNTHETIC_NOTICE = (
    "SYNTHETIC DEMONSTRATION — NO REAL GDC DATA WAS ANALYZED — NO REAL JEV CALL WAS MADE — "
    "NO REAL LLM CALL WAS MADE"
)
RESEARCH_ONLY_SECTION = "research_only_notice"
LLM_GENERATOR_NAME = "openrouter-chat-v1"


def _section(availability: str, *, narrative: str | None = None, reason: str | None = None) -> dict[str, Any]:
    return {"availability": availability, "reason": reason, "narrative": narrative}


def _uses_llm(hypotheses: list[StoredHypothesis]) -> bool:
    return any(hypothesis.draft.generator == LLM_GENERATOR_NAME for hypothesis in hypotheses)


def _comparison_narrative(comparison: dict[str, Any] | None) -> str | None:
    if comparison is None:
        return None
    wide = comparison.get("wide") or {}
    investigation = comparison.get("investigation") or {}
    if wide.get("comparison") is not None:
        wide_part = (
            f"Wide stage: actual admission recorded under {wide.get('jev_policy_version')}; "
            f"baseline {wide.get('baseline_policy_version')} admission "
            f"{wide.get('baseline_admitted')} rank {wide.get('baseline_rank')}; "
            f"comparison {wide.get('comparison')}.")
    else:
        wide_part = f"Wide stage: NOT_COMPARABLE ({wide.get('reason')})."
    if investigation.get("baseline_next_move") is not None:
        investigation_part = (
            f"Investigation: actual final move {investigation.get('actual_final_move')}; "
            f"baseline next move {investigation.get('baseline_next_move')} "
            f"({investigation.get('baseline_reason_code')}); comparison "
            f"{investigation.get('comparison')}.")
    else:
        investigation_part = (
            f"Investigation: {investigation.get('reason') or investigation.get('comparison')}.")
    return " ".join([
        "Observed Jev-assisted path versus deterministic no-Jev replay "
        f"({comparison.get('baseline_policy_version')}); overall comparison "
        f"{comparison.get('overall')}.",
        wide_part, investigation_part, str(comparison.get("note")),
        str(comparison.get("claim")),
    ])


def build_live_dossier(*, run_id: str, candidate: dict[str, Any], state: StoredState | None,
                       revisions: list[StoredEvidence], executions: list[dict[str, Any]],
                       decisions: list[dict[str, Any]], hypotheses: list[StoredHypothesis],
                       hypothesis_evaluations: list[dict[str, Any]],
                       wide_evaluation: dict[str, Any] | None,
                       deep_evaluation: dict[str, Any] | None = None,
                       final_result: dict[str, Any] | None = None,
                       comparison: dict[str, Any] | None = None,
                       mode: str = "LIVE") -> dict[str, Any]:
    """Assemble every declared dossier section from what the run already recorded."""
    if mode == "LIVE":
        notice = LLM_NOTICE if _uses_llm(hypotheses) else LIVE_NOTICE
    else:
        notice = SYNTHETIC_NOTICE
    entity = candidate.get("entity") or {}
    symbol = entity.get("gene_symbol") or candidate.get("candidate_id")
    candidate_summary = candidate.get("summary") or {}
    last_evidence = revisions[-1].evidence if revisions else None
    check_outcomes: list[str] = []
    for revision in revisions:
        summary = revision.evidence.summary
        action_id = revision.evidence.action.action_id if revision.evidence.action else None
        check_outcomes.append(
            f"E{revision.iteration}: {action_id} — {summary.verified} verified, "
            f"{summary.contradicted} contradicted, {summary.not_observed} not observed"
        )
    contradicted = [revision for revision in revisions
                    if revision.evidence.summary.contradicted]
    missing = [
        {"needed_evidence": item.needed_evidence, "availability": item.availability.value}
        for revision in revisions
        for item in revision.evidence.missing_evidence
    ]
    final_decision = decisions[-1] if decisions else {}
    provenance = last_evidence.provenance if last_evidence is not None else None
    methods = provenance.methods if provenance is not None else ()
    # Admission provenance comes from the persisted candidate record, never from the mere
    # presence or absence of a Wide evaluation.
    admission_policy = (candidate.get("summary") or {}).get(
        "policy_version") or "operator-selection-v1"
    if admission_policy == "wide-policy-v2":
        admission_narrative = (
            "Candidate was admitted by wide-policy-v2 (recorded promotion reason: "
            f"{candidate_summary.get('promotion_reason')}).")
    else:
        admission_narrative = (
            "Candidate was explicitly selected for investigation after Wide evaluation "
            f"(recorded policy {admission_policy}; reason "
            f"{candidate_summary.get('promotion_reason')}).")
    sections = {key: _section("NOT_ACQUIRED", reason="not required for this single-cohort deterministic arc")
                for key in DOSSIER_SECTIONS}
    sections["research_puzzle"] = _section(
        "OBSERVED",
        narrative=last_evidence.puzzle.question if last_evidence is not None
        and last_evidence.puzzle is not None else None,
    )
    sections["candidate_entity"] = _section(
        "OBSERVED", narrative=f"Candidate {candidate.get('candidate_id')} examines {symbol}.")
    sections["investigation_rationale"] = _section(
        "OBSERVED",
        narrative=(
            f"{admission_narrative} Wide admission never dispatches a follow-up. "
            f"Recorded next moves: {', '.join(item.get('move', 'n/a') for item in decisions) or 'none'}."
        ),
    )
    sections["initial_broad_evidence"] = _section(
        "OBSERVED" if state is not None else "NOT_ACQUIRED",
        narrative=(
            f"Accepted StatisticalState {state.state_hash[:12]} with "
            f"{len(state.state.sources)} retained response source(s)."
            if state is not None else None
        ),
        reason=None if state is not None else "the accepted state artifact was not read",
    )
    sections["jev_wide_judgments"] = _section(
        "OBSERVED" if wide_evaluation is not None else "NOT_ACQUIRED",
        narrative=(
            f"Wide judgment under {(wide_evaluation or {}).get('question_set_version')} with model "
            f"{(wide_evaluation or {}).get('resolved_model')}; {admission_narrative}"
            if wide_evaluation is not None else None
        ),
        reason=None if wide_evaluation is not None else "no wide evaluation was recorded for this state",
    )
    sections["deterministic_deep_evidence"] = _section(
        "OBSERVED" if revisions else "NOT_ACQUIRED",
        narrative="; ".join(check_outcomes) or None,
        reason=None if revisions else "no evidence revision was recorded",
    )
    sections["project_evidence"] = _section(
        "OBSERVED" if last_evidence is not None else "NOT_ACQUIRED",
        narrative=(
            ", ".join(
                f"{row.project_id}: {row.affected_case_count.value} affected of "
                f"{row.examined_cases.value} examined"
                for row in (last_evidence.project_evidence if last_evidence is not None else ())
            ) or None
        ),
        reason=None if last_evidence is not None else "no project-level evidence was recorded",
    )
    cohort_label = state.state.research.cohort if state is not None else None
    sections["cross_project_evidence"] = _section(
        "NOT_ACQUIRED",
        reason=(f"a single cohort is examined; {cohort_label} is never pooled with another cohort"
                if cohort_label else
                "a single cohort is examined; no cross-cohort pooling is performed"))
    sections["cross_modal_evidence"] = _section(
        "NOT_ACQUIRED", reason="case-to-sample resolution for expression values is UNVERIFIED")
    sections["contradictory_evidence"] = _section(
        "OBSERVED" if revisions else "NOT_ACQUIRED",
        narrative=(
            "; ".join(f"E{revision.iteration} contradicted "
                      f"{revision.evidence.summary.contradicted} check(s)"
                      for revision in contradicted) or "no contradicted check was recorded"
        ),
        reason=None if revisions else "no evidence revision was recorded",
    )
    sections["missing_unavailable_evidence"] = _section(
        "OBSERVED" if revisions else "NOT_ACQUIRED",
        narrative=", ".join(sorted({item["needed_evidence"] for item in missing
                                     if item.get("needed_evidence")})) or None,
        reason=None if revisions else "no evidence revision was recorded",
    )
    sections["jev_deep_judgments"] = _section(
        "OBSERVED" if decisions else "NOT_ACQUIRED",
        narrative=(
            "; ".join(
                f"E{item.get('iteration')}: {item.get('move')} / {item.get('reason_code')}"
                for item in decisions
            ) or None
        ),
        reason=None if decisions else "no deep judgment was recorded",
    )
    sections["competing_hypotheses"] = _section(
        "OBSERVED" if hypotheses else "NOT_ACQUIRED",
        narrative="; ".join(hypothesis.draft.statement for hypothesis in hypotheses) or None,
        reason=None if hypotheses else "hypothesis generation was not authorized or not reached",
    )
    sections["hypothesis_jev_reviews"] = _section(
        "OBSERVED" if hypothesis_evaluations else "NOT_ACQUIRED",
        narrative=(
            "; ".join(
                f"{str(item.get('hypothesis_id'))[:8]}"
                f" ({item.get('generator')}, {item.get('question_set_version')}): "
                f"testable={item.get('answers', {}).get('hypothesis_testable', {}).get('probability_yes')}, "
                f"exceeds_evidence="
                f"{item.get('answers', {}).get('hypothesis_exceeds_recorded_evidence', {}).get('probability_yes')}"
                for item in hypothesis_evaluations
            ) or None
        ),
        reason=None if hypothesis_evaluations else "no hypothesis judgment was recorded",
    )
    sections["deterministic_followups_performed"] = _section(
        "OBSERVED" if executions else "NOT_ACQUIRED",
        narrative="; ".join(
            f"{row['action_id']} v{row['action_version']} -> {row['status']}" for row in executions
        ) or None,
        reason=None if executions else "no follow-up was executed",
    )
    sections["followup_results"] = _section(
        "OBSERVED" if executions else "NOT_ACQUIRED",
        narrative=(
            "; ".join(
                f"{row['action_id']}: input {str(row.get('input_evidence_hash'))[:12]}, output "
                f"{str(row.get('output_evidence_state_id'))[:12]}"
                for row in executions
            ) or None
        ),
        reason=None if executions else "no follow-up was executed",
    )
    sections["final_candidate_result"] = _section(
        "OBSERVED" if final_result is not None else "NOT_ACQUIRED",
        narrative=(
            f"Final result {str((final_result or {}).get('final_result_id'))[:12]}: status "
            f"{(final_result or {}).get('investigation_status')}, final move "
            f"{(final_result or {}).get('final_move')}, stop reason "
            f"{(final_result or {}).get('stop_reason')}, dossier "
            f"{(final_result or {}).get('dossier_reference')}."
            if final_result is not None else None
        ),
        reason=None if final_result is not None
        else "the Stage 8 final candidate result was not supplied",
    )
    sections["jev_vs_no_jev_comparison"] = _section(
        "OBSERVED" if comparison is not None else "NOT_ACQUIRED",
        narrative=_comparison_narrative(comparison),
        reason=None if comparison is not None
        else "the no-Jev comparison was not attached to this dossier",
    )
    sections["remaining_uncertainty"] = _section(
        "OBSERVED" if final_result is not None else "NOT_ACQUIRED",
        narrative=(
            f"Final recorded move {final_decision.get('move')} ({final_decision.get('reason_code')}); "
            f"dominant limitation {final_decision.get('dimensions', {}).get('dominant_limitation')}."
            if final_result is None and final_decision else
            "; ".join(
                f"remaining uncertainty includes {item}" for item in
                ((final_result or {}).get("remaining_uncertainty", {}).get("state_missingness")
                 or [])[:4]) or None
            if final_result is not None else None
        ),
        reason=None if final_result is not None else "no Stage 8 final result was recorded",
    )
    sections["predictions_by_hypothesis"] = _section(
        "OBSERVED" if hypotheses else "NOT_ACQUIRED",
        narrative=(
            "; ".join(f"{hypothesis.hypothesis_id}: {', '.join(hypothesis.draft.predictions)}"
                      for hypothesis in hypotheses) or None
        ),
        reason=None if hypotheses else "no generated hypothesis exists",
    )
    sections["falsification_criteria"] = _section(
        "OBSERVED" if hypotheses else "NOT_ACQUIRED",
        narrative=(
            "; ".join(f"{hypothesis.hypothesis_id}: {', '.join(hypothesis.draft.contradicted_if)}"
                      for hypothesis in hypotheses) or None
        ),
        reason=None if hypotheses else "no generated hypothesis exists",
    )
    sections["gdc_provenance"] = _section(
        "OBSERVED" if provenance is not None else "NOT_ACQUIRED",
        narrative=(
            f"release {provenance.gdc_release} with {len(provenance.sources)} retained "
            "response source(s); every source names its acquisition attempt in the stored revision"
            if provenance is not None else None
        ),
        reason=None if provenance is not None else "no provenance was recorded",
    )
    sections["method_versions"] = _section(
        "OBSERVED" if methods else "NOT_ACQUIRED",
        narrative=", ".join(f"{item.method_id} v{item.version}" for item in methods) or None,
        reason=None if methods else "no method reference was recorded",
    )
    sections["jev_model_question_versions"] = _section(
        "OBSERVED" if decisions else "NOT_ACQUIRED",
        narrative=(
            f"deep question set {deep_evaluation.get('question_set_version')} with model "
            f"{deep_evaluation.get('resolved_model') or deep_evaluation.get('requested_model')}; policy "
            f"{final_decision.get('policy_version')}"
            if final_decision is not None and deep_evaluation is not None else
            (f"policy {final_decision.get('policy_version')} recorded without a deep judgment"
             if final_decision is not None else None)
        ),
        reason=None if decisions else "no deep judgment was recorded",
    )
    uses_llm = _uses_llm(hypotheses)
    sections["llm_provider_model_metadata"] = _section(
        "OBSERVED" if uses_llm else "NOT_ACQUIRED",
        narrative=(
            "hypotheses were generated by the configured LLM provider; the generator name is recorded on each"
            if uses_llm else None
        ),
        reason=None if uses_llm
        else "no LLM was configured for this run; hypothesis text is deterministic template output",
    )
    sections[RESEARCH_ONLY_SECTION] = _section("OBSERVED", narrative=notice)
    dossier_id = stable_id(run_id, f"dossier:{candidate['candidate_id']}")
    return {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "dossier_id": dossier_id,
        "run_id": run_id,
        "candidate_id": candidate["candidate_id"],
        "mode": mode,
        "warning": notice,
        "entity": entity,
        "evidence_state_ids": [revision.evidence_state_id for revision in revisions],
        "hypothesis_ids": [hypothesis.hypothesis_id for hypothesis in hypotheses],
        "next_moves": [{"move": item.get("move"), "reason_code": item.get("reason_code")}
                       for item in decisions],
        "final_result": final_result,
        "comparison": comparison,
        "sections": sections,
        "created_at": utc_now(),
        "limitations": [
            "Deterministic checks are integrity and consistency evidence, not biological evidence.",
            "A single cohort is examined and the examined gene set is selection-biased.",
            "Jev judgments are inputs to Python policy; they select, authorize and execute nothing.",
            "The no-Jev comparison is a declared deterministic replay, not an observed human "
            "trajectory, and cannot support a superiority claim.",
        ],
    }


def run_dossier_stage(*, run_id: str, candidate: dict[str, Any], repository: Any, artifacts: Any,
                      decisions: list[dict[str, Any]],
                      publish_json: Callable[[str, str, Any, str], Any],
                      emit: Callable[..., Any], mode: str = "LIVE",
                      final_result: dict[str, Any] | None = None,
                      comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist the authoritative JSON dossier, its derived Markdown, and its record."""
    try:
        return _publish_dossier_stage(
            run_id=run_id, candidate=candidate, repository=repository, artifacts=artifacts,
            decisions=decisions, publish_json=publish_json, emit=emit, mode=mode,
            final_result=final_result, comparison=comparison,
        )
    except ScientificReadError as exc:
        summary = {"status": "UNAVAILABLE", "candidate_id": candidate["candidate_id"],
                   "error_code": exc.code, "detail": exc.detail}
        emit(run_id, "DOSSIER_UNAVAILABLE", f"dossier:{candidate['candidate_id']}:unavailable",
             "Dossier publication refused: authoritative evidence is unavailable or corrupt.",
             stage="DOSSIER", candidate_id=candidate["candidate_id"], level="error", data=summary)
        return summary


def _publish_dossier_stage(*, run_id: str, candidate: dict[str, Any], repository: Any, artifacts: Any,
                           decisions: list[dict[str, Any]],
                           publish_json: Callable[[str, str, Any, str], Any],
                           emit: Callable[..., Any], mode: str = "LIVE",
                           final_result: dict[str, Any] | None = None,
                           comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    # Reload authoritative storage, not a stale caller copy or an earlier valid revision.
    stored_state = read_candidate_state(repository, artifacts, candidate["candidate_id"])
    chain = read_revision_chain(repository, artifacts, candidate["candidate_id"])
    if not chain:
        raise ScientificReadError("EVIDENCE_STATE_MISSING", "dossier requires accepted evidence")
    executions = repository.followup_executions_for(candidate["candidate_id"])
    hypothesis_rows = repository.page_child("hypotheses", run_id, 100, None,
                                            {"candidate_id": candidate["candidate_id"]})["items"]
    hypotheses = [read_hypothesis_record(
        repository, artifacts, row["hypothesis_id"], candidate_id=candidate["candidate_id"],
        allowed_action_ids=frozenset(ACTION_REGISTRY),
    ) for row in hypothesis_rows]
    hypothesis_ids = {row["hypothesis_id"] for row in hypothesis_rows}
    hypothesis_evaluations = [
        read_evaluation_record(repository, artifacts, row["evaluation_id"]).artifact.boundary_representation()
        for row in repository.page_child(
            "jev_evaluations", run_id, 100, None,
            {"purpose": "HYPOTHESIS", "candidate_id": candidate["candidate_id"]},
        )["items"]
        if row["input_ref_id"] in hypothesis_ids
    ]
    deep_evaluations = [
        read_evaluation_record(repository, artifacts, row["evaluation_id"]).artifact.boundary_representation()
        for row in repository.page_child(
            "jev_evaluations", run_id, 100, None,
            {"purpose": "DEEP", "candidate_id": candidate["candidate_id"]},
        )["items"]
    ]
    wide_evaluations = [
        read_evaluation_record(repository, artifacts, row["evaluation_id"]).artifact.boundary_representation()
        for row in repository.page_child("jev_evaluations", run_id, 100, None,
                                         {"purpose": "WIDE"})["items"]
        if row["input_ref_id"] == candidate.get("source_state_id")
    ]
    dossier = build_live_dossier(
        run_id=run_id, candidate=candidate, state=stored_state, revisions=list(chain),
        executions=executions, decisions=decisions, hypotheses=hypotheses,
        hypothesis_evaluations=hypothesis_evaluations,
        wide_evaluation=wide_evaluations[0] if wide_evaluations else None,
        deep_evaluation=deep_evaluations[-1] if deep_evaluations else None,
        final_result=final_result, comparison=comparison,
        mode=mode,
    )
    json_artifact = publish_json(run_id, f"runs/{run_id}/dossier/{dossier['dossier_id']}.json",
                                 dossier, "authoritative-dossier")
    markdown = render_markdown(dossier, warning=dossier["warning"]).encode()
    md_artifact = artifacts.publish(f"runs/{run_id}/dossier/{dossier['dossier_id']}.md", markdown,
                                    "text/markdown; charset=utf-8", "derived-dossier-markdown")
    summary = {
        "dossier_id": dossier["dossier_id"], "run_id": run_id,
        "candidate_id": candidate["candidate_id"], "mode": mode, "entity": dossier["entity"],
        "puzzle": dossier["sections"]["research_puzzle"]["narrative"], "warning": dossier["warning"],
        "evidence_state_ids": dossier["evidence_state_ids"], "hypothesis_ids": dossier["hypothesis_ids"],
        "next_moves": dossier["next_moves"],
        "json_artifact_id": json_artifact.artifact_id, "markdown_artifact_id": md_artifact.artifact_id,
    }
    emit(
        run_id, "DOSSIER_CREATED", f"dossier:{dossier['dossier_id']}:created",
        f"Created the authoritative JSON and derived Markdown dossier for candidate "
        f"{candidate['candidate_id']}.",
        stage="DOSSIER", candidate_id=candidate["candidate_id"],
        data=summary, artifact_refs=[json_artifact.ref(), md_artifact.ref()],
        registrations=[
            repository.artifact_registration(json_artifact, run_id),
            repository.artifact_registration(md_artifact, run_id),
            repository.dossier_registration(
                dossier_id=dossier["dossier_id"], run_id=run_id,
                candidate_id=candidate["candidate_id"], json_artifact_id=json_artifact.artifact_id,
                markdown_artifact_id=md_artifact.artifact_id,
                summary_json=canonical_json(summary).decode(), created_at=dossier["created_at"],
            ),
            repository.candidate_status_registration(
                candidate_id=candidate["candidate_id"], status="DOSSIER_READY", current_stage=None,
                updated_at=utc_now(), dossier_id=dossier["dossier_id"],
            ),
        ],
    )
    return summary
