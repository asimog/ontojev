"""Canonical systematic Campaign execution path.

One campaign run performs: profile/spec/capability validation → mutation
discovery → expression discovery → required CNV shard completion → terminal CNV
merge → deterministic modality union → canonical StatisticalState persistence →
the typed pre-Wide boundary → the existing Wide semantic/admission layer.

The transitional provider-ranked sweep remains available only as the explicitly
labelled legacy researcher/comparator path and cannot produce canonical Campaign
results. No operator flags exist here: autonomy is declared by the run's
ownership, and deep investigation is driven by the autonomous candidate queue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cancerjev.config import Settings
from cancerjev.domain.capability import CohortCapability, Modality
from cancerjev.domain.discovery import CNV_CASE_SHARD_SIZE
from cancerjev.domain.measurements import Acquisition
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.gdc.budget import production_caps
from cancerjev.gdc.transport import GDCTransport, RunBudget
from cancerjev.jev.service import JevService
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.campaign import (
    CampaignProfile,
    require_autonomous_activation,
    require_capability,
)
from cancerjev.research.cnv_discovery import (
    plan_cnv_case_shards,
    run_cnv_shard_merge,
    run_cnv_shard_scan,
)
from cancerjev.research.cutover import UNION_SELECTION_RULE_ID, compose_discovery_states
from cancerjev.research.discovery import run_mutation_discovery
from cancerjev.research.expression_discovery import run_expression_discovery
from cancerjev.research.seams import PublishJson, run_stage
from cancerjev.research.specs import ResearchSpec
from cancerjev.research.state_store import persist_state
from cancerjev.research.wide import (
    PreWideSelection,
    record_pre_wide_selection,
    run_wide_evaluation,
    select_pre_wide_states,
)
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

TransportFactory = Callable[
    [Repository, ArtifactStore, RunBudget, str, Callable[..., Any]], Any]
REQUIRED_MODALITIES: tuple[Modality, ...] = (
    Modality.CNV,
    Modality.EXPRESSION_RNASEQ,
    Modality.MUTATION_WXS,
)


@dataclass(frozen=True)
class SystematicCampaignResult:
    """Outcome of one canonical Campaign run; the run itself owns persistence."""

    run_id: str
    profile_id: str
    spec_id: str
    mutation_survivors: tuple[str, ...]
    expression_genes: int
    cnv_shards: int
    cnv_calls: int
    state_ids: tuple[str, ...]
    union_selection_rule: str
    coverage: str
    pre_wide: PreWideSelection
    wide: dict[str, Any] | None

    def summary(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id, "spec_id": self.spec_id,
            "execution": "SYSTEMATIC_MODALITY_UNION",
            "selection_rule": self.union_selection_rule,
            "mutation_survivors": list(self.mutation_survivors),
            "expression_genes": self.expression_genes,
            "cnv_shards": self.cnv_shards, "cnv_calls": self.cnv_calls,
            "states": len(self.state_ids), "state_ids": list(self.state_ids),
            "coverage": self.coverage,
            "pre_wide": self.pre_wide.payload(),
            "wide": {
                "evaluations": len(self.wide["baseline"]["entries"]) if self.wide else 0,
                "promoted": len(self.wide["promoted"]) if self.wide else 0,
                "admission_decision": (self.wide["jev"]["admission"]["decision"]
                                       if self.wide else None),
            } if self.wide is not None else None,
        }


def validate_campaign_binding(profile: CampaignProfile, spec: ResearchSpec,
                              capability: CohortCapability) -> None:
    """The canonical executor refuses anything but the full systematic modality set."""
    if profile.spec_id != spec.spec_id:
        raise LiveRunError("CAMPAIGN_SPEC_MISMATCH",
                           f"{profile.profile_id} binds {profile.spec_id}, not {spec.spec_id}")
    require_autonomous_activation(profile)
    require_capability(profile, capability)
    if profile.enabled_modalities != REQUIRED_MODALITIES:
        raise LiveRunError(
            "CAMPAIGN_MODALITY_SET_UNSUPPORTED",
            f"{profile.profile_id} enables "
            f"{[modality.value for modality in profile.enabled_modalities]}; the canonical "
            "systematic path requires mutation, expression and CNV",
        )


def run_systematic_campaign(*, run_id: str, profile: CampaignProfile, spec: ResearchSpec,
                            capability: CohortCapability, settings: Settings,
                            repository: Repository, artifacts: ArtifactStore,
                            emit: Callable[..., Any], publish_json: PublishJson,
                            jev_service: JevService,
                            transport_factory: TransportFactory | None = None,
                            max_states: int | None = None) -> SystematicCampaignResult:
    """Execute the canonical Campaign spine on one SYSTEM_AUTONOMOUS run."""
    repository.require_run_ownership(run_id, ExecutionOwnership.SYSTEM_AUTONOMOUS)
    validate_campaign_binding(profile, spec, capability)
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )

    def lane_transport() -> Any:
        budget = RunBudget(caps=caps)
        if transport_factory is not None:
            return transport_factory(repository, artifacts, budget, run_id, emit)
        return GDCTransport(repository, artifacts, budget, run_id, emit,
                            cache_enabled=settings.gdc_cache_enabled)

    def lane_emit(event_type: str, key: str, message: str, **kwargs: Any) -> None:
        """Lane functions own one run id, so their emit is already bound."""
        emit(run_id, event_type, key, message, **kwargs)

    mutation = run_stage(
        emit, run_id, "STATE_GENERATION",
        lambda: run_mutation_discovery(run_id, lane_transport(), repository, artifacts,
                                       lane_emit, spec),
    )
    expression = run_stage(
        emit, run_id, "STATE_GENERATION",
        lambda: run_expression_discovery(run_id, lane_transport(), repository, artifacts,
                                         lane_emit, spec),
    )
    cnv_transport = lane_transport()
    shards = run_stage(
        emit, run_id, "STATE_GENERATION",
        lambda: plan_cnv_case_shards(cnv_transport, spec, case_shard_size=CNV_CASE_SHARD_SIZE),
    )
    for shard_index in range(len(shards)):

        def scan_shard(index: int = shard_index) -> Any:
            return run_cnv_shard_scan(
                run_id, cnv_transport, repository, artifacts, lane_emit, spec,
                shard_index=index, case_shard_size=CNV_CASE_SHARD_SIZE)

        run_stage(emit, run_id, "STATE_GENERATION", scan_shard)
    cnv = run_stage(
        emit, run_id, "STATE_GENERATION",
        lambda: run_cnv_shard_merge(
            run_id, repository, artifacts, lane_emit, spec, expected_shards=len(shards),
            case_shard_size=CNV_CASE_SHARD_SIZE),
    )
    states = run_stage(
        emit, run_id, "STATE_GENERATION",
        lambda: compose_discovery_states(mutation, expression, cnv, spec),
    )
    records = [persist_state(
        run_id=run_id, state=state, repository=repository, artifacts=artifacts,
        publish_json=publish_json, emit=emit, run_mode="LIVE",
    ) for state in states]
    coverage = "COMPLETE_FOR_SCOPE"
    if any(record.state.quality.acquisition is not Acquisition.COMPLETE for record in records):
        coverage = "PARTIAL"
    selection = select_pre_wide_states(records, ceiling=max_states)
    record_pre_wide_selection(run_id=run_id, selection=selection, repository=repository,
                              publish_json=publish_json, emit=emit)
    wide_result = run_stage(
        emit, run_id, "JEV_WIDE",
        lambda: run_wide_evaluation(
            run_id=run_id, states=list(selection.states), coverage=coverage,
            repository=repository, jev_service=jev_service, emit=emit,
            publish_json=publish_json, max_states=None),
    )
    return SystematicCampaignResult(
        run_id=run_id, profile_id=profile.profile_id, spec_id=spec.spec_id,
        mutation_survivors=tuple(mutation.survivor_ids),
        expression_genes=len(expression.entries), cnv_shards=len(shards),
        cnv_calls=len(cnv.calls),
        state_ids=tuple(record.state_id for record in records),
        union_selection_rule=UNION_SELECTION_RULE_ID, coverage=coverage,
        pre_wide=selection, wide=wide_result,
    )
