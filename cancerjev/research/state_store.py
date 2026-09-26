"""Canonical StatisticalState persistence shared by every execution path.

The legacy bounded sweep and the systematic campaign executor register states
through the same codec, artifact path, registration records and event shape:
there is exactly one persisted StatisticalState representation. A StateRecord
is returned for in-flight use; nothing here modifies a registered state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from cancerjev.domain.codecs import state_identity, write_state
from cancerjev.domain.envelopes import StateRecord
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.measurements import Acquisition, MetricRecord, ObservedCount
from cancerjev.domain.scientific import StatisticalState
from cancerjev.research.seams import PublishJson
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.readers import read_state_record
from cancerjev.storage.repositories import Repository


def metric_summary(record: MetricRecord) -> dict[str, Any]:
    """Presentation projection of one typed metric; not a scientific model."""
    return {"value": record.value, "unit": record.unit,
            "availability": record.availability.value, "reason_code": record.reason_code}


def state_summary(state: StatisticalState, artifact: PublishedArtifact, mode: str) -> dict[str, Any]:
    """Operational/presentation summary stored beside a registered state."""
    projects = len(state.projects)
    observed_mutation = sum(1 for project in state.projects
                            if isinstance(project.mutation.affected_cases, ObservedCount))
    observed_expression = state.cross_project.projects_with_expression_observation

    def availability(count: int) -> str:
        return "OBSERVED" if count == projects else ("PARTIAL" if count else "INSUFFICIENT")

    return {
        "entity": {"gene_id": state.entity.gene_id, "gene_symbol": state.entity.symbol},
        "mode": mode,
        "mutation_availability": availability(observed_mutation),
        "expression_availability": availability(observed_expression),
        "projects_with_mutation_observation": state.cross_project.projects_with_mutation_observation,
        "projects_with_expression_observation": observed_expression,
        "affected_case_total": metric_summary(state.cross_project.affected_case_total),
        "top_project_share": metric_summary(state.cross_project.top_project_share),
        "coverage_imbalance": state.cross_project.coverage_imbalance,
        "completeness": "COMPLETE" if state.quality.acquisition is Acquisition.COMPLETE else "PARTIAL",
        "artifact_id": artifact.artifact_id,
        "artifact_sha256": artifact.sha256,
    }


def persist_state(*, run_id: str, state: StatisticalState, repository: Repository,
                  artifacts: ArtifactStore, publish_json: PublishJson,
                  emit: Callable[..., Any], run_mode: str,
                  stage: str | None = "STATE_GENERATION") -> StateRecord:
    """Register one StatisticalState exactly once: artifact + state row + event."""
    state_id = str(uuid4())
    state_hash = state_identity(state)
    artifact = publish_json(run_id, f"runs/{run_id}/statistical_states/{state_id}.json",
                            write_state(state), "statistical-state")
    summary = state_summary(state, artifact, run_mode)
    registrations = [
        repository.artifact_registration(artifact, run_id),
        repository.state_registration(
            state_id=state_id, run_id=run_id, state_hash=state_hash,
            artifact_id=artifact.artifact_id, disposition="GENERATED",
            summary_json=canonical_json(summary).decode(), created_at=utc_now(),
        ),
    ]
    emit(
        run_id, "STATISTICAL_STATE_CREATED", f"state:{state_id}",
        (f"Real StatisticalState for {state.entity.symbol} generated from open GDC evidence."
         if run_mode == "LIVE"
         else f"Synthetic StatisticalState for {state.entity.symbol} generated from labelled fixtures."),
        stage=stage,
        data={"state_id": state_id, "state_hash": state_hash, "gene_id": state.entity.gene_id,
              "gene_symbol": state.entity.symbol, "mode": run_mode},
        artifact_refs=[artifact.ref()], registrations=registrations,
    )
    return StateRecord(state_id, state_hash, state)


def load_run_states(repository: Repository, artifacts: ArtifactStore,
                    run_id: str) -> list[StateRecord]:
    """Rehydrate every persisted state of one run in deterministic state_id order."""
    rows = sorted(repository.list_table("statistical_states", run_id),
                  key=lambda row: str(row["state_id"]))
    return [read_state_record(repository, artifacts, str(row["state_id"])).record for row in rows]
