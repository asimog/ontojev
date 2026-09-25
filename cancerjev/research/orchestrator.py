"""Offline demonstration run over the shared current architecture.

The demo is not a separate engine: it runs the same bounded live orchestrator,
strict parsers, deterministic methods, typed states and revisions, registered
actions, Jev projections and dossier path, with only the provider transport and
the Jev adapter substituted by clearly labelled synthetic fixtures. No socket is
opened and no credential is read.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from cancerjev.config import Settings
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.jev.service import JevService
from cancerjev.jev.typesafe_adapter import TypeSafeAdapter
from cancerjev.research.fixtures import (
    FIXTURE_ID,
    FIXTURE_VERSION,
    FixtureJevAdapter,
    FixtureTransport,
)
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.specs import LUAD_RESEARCH_V1
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

DEMO_DEEP_SELECTION = "slot:1"


class DemoOrchestrator:
    """Run one deterministic synthetic demonstration through the shared engine."""

    def __init__(self, settings: Settings, repository: Repository, artifacts: ArtifactStore,
                 render: Callable[..., Any] | None = None) -> None:
        self.settings = settings
        self.repository = repository
        self.artifacts = artifacts
        self.render = render or (lambda *args, **kwargs: None)

    def run(self) -> str:
        adapter = FixtureJevAdapter(model=self.settings.jev_model)
        # JevService uses only the adapter's evaluate contract, which FixtureJevAdapter
        # implements with the same signature; the provider adapter type is nominal.
        jev_service = JevService(self.settings, self.repository, self.artifacts,
                                 adapter_factory=lambda: cast(TypeSafeAdapter, adapter))
        orchestrator = LiveOrchestrator(
            settings=self.settings, repository=self.repository, artifacts=self.artifacts,
            render=self.render, jev_service=jev_service, worker_id="demo-worker",
            transport_factory=(
                lambda repository, artifacts, budget, run_id, emit:
                FixtureTransport(artifacts, run_id, repository=repository)
            ),
            research_spec=LUAD_RESEARCH_V1,
            deep_selection=DEMO_DEEP_SELECTION,
            deep_action_id="CHECK_EVIDENCE_INTEGRITY_V1",
            deep_followup_authorized=True,
            deep_hypotheses_requested=True,
            run_mode="FIXTURE",
            fixture_id=FIXTURE_ID,
            fixture_version=FIXTURE_VERSION,
            execution_ownership=ExecutionOwnership.RESEARCHER_RUN,
        )
        return orchestrator.run()
