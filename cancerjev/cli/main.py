from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cancerjev.cli.console import render_event, render_json_event
from cancerjev.config import Settings, load_local_env
from cancerjev.domain.discovery import (
    CNV_CASE_SHARD_SIZE,
)
from cancerjev.domain.measurements import ContractError
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.gdc.budget import policy_payload, production_caps
from cancerjev.gdc.capture import CaptureSink, run_contract_probe
from cancerjev.gdc.parsers import ParserError
from cancerjev.gdc.transport import GDCTransport, RunBudget, TransportError
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.live import LiveOrchestrator
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.ownership import OwnershipError, ResearchOwnership
from cancerjev.storage.repositories import Repository


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m cancerjev")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("run", "worker"):
        command = commands.add_parser(name)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--fixture", choices=["demo"])
        mode.add_argument("--live", action="store_true", help="real bounded open-access GDC sweep")
        command.add_argument("--researcher", action="store_true",
                             help="mark the run as RESEARCHER_RUN (required for operator deep flags)")
        command.add_argument("--jev", action="store_true",
                             help="wide Jev evaluation over real states (requires TYPESAFE_API_KEY)")
        command.add_argument("--deep-candidate", action="append", default=None,
                             help="explicitly selected candidate for the deterministic deep investigation "
                                  "(repeatable: gene symbol, gene:<SYMBOL>, state:<STATE_ID> for a "
                                  "wide-evaluated state, or slot:N for a policy-promoted candidate); "
                                  "requires --live --jev")
        command.add_argument("--deep-action", default=None,
                             help="explicitly selected registered action id for the first deterministic "
                                  "step on the accepted evidence E0 (optional); dispatched follow-ups "
                                  "use the policy's distinct eligible revision action instead")
        command.add_argument("--deep-followup", action="store_true",
                             help="authorize bounded iteration for the selected candidate(s): recorded "
                                  "FOLLOW_UP moves are dispatched and re-judged while the follow-up and "
                                  "revision caps allow, and bounded hypothesis generation runs when the "
                                  "policy asks for it; requires --deep-candidate")
        command.add_argument("--deep-hypotheses", action="store_true",
                             help="explicitly request bounded hypothesis generation for the selected "
                                  "candidate(s) even when the recorded next move is not "
                                  "GENERATE_HYPOTHESES (recorded as OPERATOR_REQUESTED_HYPOTHESES); "
                                  "requires --deep-candidate --deep-followup")
    probe = commands.add_parser("probe", help="bounded anonymous GDC contract capture")
    probe.add_argument("--capture-dir", default=None)
    capability = commands.add_parser(
        "capability",
        help="bounded cohort capability probe (status + one project + one open-file facet aggregate)",
    )
    capability.add_argument(
        "--project", default=None,
        help="open GDC project id to probe (default: the declared LUAD campaign project)",
    )
    commands.add_parser(
        "program",
        help="one autonomous program step: select an eligible campaign by the declared policy",
    )
    discover = commands.add_parser(
        "discover",
        help="bounded Stage 4 systematic mutation discovery over the complete protein-coding gene universe",
    )
    discover.add_argument("--live", action="store_true",
                          help="real bounded open-access GDC systematic discovery")
    discover_expression = commands.add_parser(
        "discover-expression",
        help="bounded Stage 5 expression discovery over the complete systematic universe",
    )
    discover_expression.add_argument(
        "--live", action="store_true",
        help="real bounded open-access GDC independent expression discovery",
    )
    discover_cnv = commands.add_parser(
        "discover-cnv",
        help="bounded independent CNV case-shard scan of the project occurrence index",
    )
    discover_cnv.add_argument("--live", action="store_true",
                              help="real bounded open-access GDC CNV discovery")
    discover_cnv.add_argument("--case-shard", type=int, required=True,
                              help="zero-based case shard index of the declared cohort frame")
    discover_cnv.add_argument("--case-shard-size", type=int, default=CNV_CASE_SHARD_SIZE,
                              help="declared operational case-shard size (default 25)")
    cnv_merge = commands.add_parser(
        "cnv-merge",
        help="merge every required CNV shard evidence artifact into one project call set",
    )
    cnv_merge.add_argument("--source-run", action="append", required=True,
                           help="source run ID: repeat in shard-index order, or name one run holding all shards")
    cnv_merge.add_argument("--shards", type=int, required=True,
                           help="number of case shards that must all exist before merging")
    cnv_merge.add_argument("--case-shard-size", type=int, default=CNV_CASE_SHARD_SIZE,
                           help="declared operational case-shard size (default 25)")
    show = commands.add_parser("show")
    show.add_argument("run_id")
    show.add_argument("--events", action="store_true")
    evaluate = commands.add_parser(
        "evaluate",
        help="compare one run's baseline and Jev rankings against pre-registered labels (offline)",
    )
    evaluate.add_argument("--run", dest="run_id", required=True, help="id of a completed run")
    evaluate.add_argument("--labels", required=True,
                          help="operator-supplied label JSON; never produced by cancerjev")
    evaluate.add_argument("--k", type=int, default=3, help="top-k size (1..3)")
    evaluate.add_argument("--out", default=None, help="report path (defaults to <data>/evaluations/...)")
    return root


def _services(settings: Settings) -> tuple[Repository, ArtifactStore]:
    database = Database(settings.database_path)
    database.bootstrap()
    return Repository(database), ArtifactStore(settings.data_dir)


@contextmanager
def _started_run(
    repository: Repository,
    *,
    worker_id: str,
    scope: dict[str, Any],
    started_message: str,
    started_data: dict[str, Any] | None = None,
    mode: str = "LIVE",
    fixture_id: str | None = None,
    fixture_version: str | None = None,
    ownership: ExecutionOwnership = ExecutionOwnership.SYSTEM_AUTONOMOUS,
) -> Iterator[str]:
    """Create one run and guarantee it reaches a terminal state in this invocation.

    Normal failures end the run ``FAILED``; a deliberate operator interrupt ends it
    ``STOPPED``. A process that dies without reaching either state is handled by
    crash recovery (``recover_interrupted``), never by this routine handler.
    """
    run_id = repository.create_run(
        worker_id, mode=mode, fixture_id=fixture_id, fixture_version=fixture_version,
        scope=scope, ownership=ownership)
    repository.append_event(
        run_id, event_type="RUN_STARTED", idempotency_key="run:started",
        message=started_message,
        data={**(started_data or {}), "mode": mode, "purpose": scope.get("purpose")})
    try:
        yield run_id
    except KeyboardInterrupt:
        repository.append_event(
            run_id, event_type="RUN_STOPPED", idempotency_key="run:stopped",
            message="Run stopped by operator interrupt.", level="warning",
            data={"status": "STOPPED", "reason_code": "INTERRUPTED_BY_OPERATOR"})
        raise
    except Exception as exc:
        code = str(getattr(exc, "code", type(exc).__name__))
        repository.append_event(
            run_id, event_type="RUN_FAILED", idempotency_key="run:failed",
            message=f"Run failed: {code}.", level="error",
            data={"status": "FAILED", "reason_code": code, "coverage": "PARTIAL",
                  "detail": str(exc)})
        raise


def _probe(settings: Settings, repository: Repository, artifacts: ArtifactStore, capture_dir: str | None) -> None:
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    with _started_run(
        repository, worker_id="probe",
        scope={"budget_policy": policy_payload(), "purpose": "CONTRACT_PROBE"},
        started_message="Contract probe run started.",
    ) as run_id:

        def emit(event_type: str, key: str, message: str, **kwargs) -> None:
            event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                            message=message, **kwargs)
            render_event(event)

        transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                                 cache_enabled=False)
        directory = (
            Path(capture_dir) if capture_dir
            else settings.data_dir / f"gdc-contract-captures-{time.strftime('%Y-%m-%d')}" / f"probe-{run_id[:8]}"
        )
        sink = CaptureSink(directory)
        summary = run_contract_probe(transport, sink, release=None)
        totals = repository.gdc_run_totals(run_id)
        emit(
            "RUN_COMPLETED", "run:completed",
            f"Contract probe completed with {summary['captures']} captures.",
            data={"status": "COMPLETED", "reason_code": "CONTRACT_PROBE_COMPLETE", "coverage": "COMPLETE_FOR_SCOPE",
                  "captures": summary["captures"], "bytes": totals["bytes"], "gdc_attempts": totals["attempts"]},
        )
        print(f"[PROBE] captures written to {directory} ({summary['captures']} requests, {summary['bytes']} bytes)",
              flush=True)


def _capability(settings: Settings, repository: Repository, artifacts: ArtifactStore,
                *, project_id: str | None) -> None:
    from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
    from cancerjev.research.capability import discover_cohort_capability

    target = project_id or LUAD_CAMPAIGN_V1.project_id
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    with _started_run(
        repository, worker_id="capability",
        scope={"budget_policy": policy_payload(), "purpose": "CAPABILITY_PROBE", "project_id": target},
        started_message=f"Cohort capability probe started for {target}.",
        started_data={"project_id": target},
    ) as run_id:

        def emit(event_type: str, key: str, message: str, **kwargs) -> None:
            event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                            message=message, **kwargs)
            render_event(event)

        transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                                 cache_enabled=False)
        capability = discover_cohort_capability(transport, project_id=target)
        payload = {"kind": "COHORT_CAPABILITY", "capability_hash": capability.capability_hash(),
                   **capability.payload()}
        artifact = artifacts.publish(
            f"runs/{run_id}/capability/{target}.json",
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            "application/json", "cohort-capability",
        )
        repository.register_artifact(artifact, run_id)
        totals = repository.gdc_run_totals(run_id)
        emit("RUN_COMPLETED", "run:completed", f"Cohort capability probe completed for {target}.",
             data={"status": "COMPLETED", "reason_code": "CAPABILITY_PROBE_COMPLETE",
                   "coverage": "COMPLETE_FOR_SCOPE", "project_id": target,
                   "available_modalities": [modality.value
                                            for modality in capability.available_modalities()],
                   "bytes": totals["bytes"], "gdc_attempts": totals["attempts"]})
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        print(f"[CAPABILITY] {target}: available modalities = "
              f"{', '.join(modality.value for modality in capability.available_modalities())}", flush=True)


def _discover(settings: Settings, repository: Repository, artifacts: ArtifactStore) -> None:
    from cancerjev.research.discovery import run_mutation_discovery
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    # The systematic-discovery worker declares the mutation occurrence-scan budget
    # explicitly: a complete project scan is the scientific quantity source, and its
    # declared ceiling lives in domain.discovery (not env-adjustable in this change).
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    try:
        with _started_run(
            repository, worker_id="discovery-worker",
            scope={"budget_policy": policy_payload(), "purpose": "SYSTEMATIC_DISCOVERY",
                   "spec_id": spec.spec_id, "domain": spec.cohort.domain,
                   "cohort": spec.cohort.cohort_id, "project_id": spec.cohort.project_id,
                   "discovery": asdict(spec.discovery),
                   "selection_rule": spec.discovery_selection_rule()},
            started_message="Bounded systematic discovery run started.",
            started_data={"research_spec": spec.as_dict()},
        ) as run_id:

            def emit(event_type: str, key: str, message: str, **kwargs) -> None:
                event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                                message=message, **kwargs)
                render_event(event)

            budget = RunBudget(caps=caps)
            transport = GDCTransport(repository, artifacts, budget, run_id, emit,
                                     cache_enabled=settings.gdc_cache_enabled)
            result = run_mutation_discovery(run_id, transport, repository, artifacts, emit, spec)
            totals = repository.gdc_run_totals(run_id)
            emit("RUN_COMPLETED", "run:completed",
                 f"Systematic discovery completed with {len(result.survivor_ids)} survivor(s).",
                 data={"status": "COMPLETED", "reason_code": "DISCOVERY_COMPLETE",
                       "coverage": "COMPLETE_FOR_SCOPE", "survivor_ids": list(result.survivor_ids),
                       "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
                       "gdc_cache_hits": totals["cache_hits"]})
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        raise SystemExit(1) from exc


def _discover_expression(
    settings: Settings, repository: Repository, artifacts: ArtifactStore,
) -> None:
    from cancerjev.research.expression_discovery import run_expression_discovery
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    try:
        with _started_run(
            repository, worker_id="expression-discovery-worker",
            scope={"budget_policy": policy_payload(), "purpose": "EXPRESSION_DISCOVERY",
                   "spec_id": spec.spec_id, "domain": spec.cohort.domain,
                   "cohort": spec.cohort.cohort_id, "project_id": spec.cohort.project_id,
                   "expression_discovery": asdict(spec.expression_discovery),
                   "selection_rule": spec.discovery_selection_rule()},
            started_message="Bounded expression discovery run started.",
            started_data={"research_spec": spec.as_dict()},
        ) as run_id:

            def emit(event_type: str, key: str, message: str, **kwargs) -> None:
                event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                                message=message, **kwargs)
                render_event(event)

            transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                                     cache_enabled=settings.gdc_cache_enabled)
            result = run_expression_discovery(
                run_id, transport, repository, artifacts, emit, spec)
            totals = repository.gdc_run_totals(run_id)
            emit("RUN_COMPLETED", "run:completed",
                 f"Expression discovery completed for {len(result.entries)} gene(s).",
                 data={"status": "COMPLETED", "reason_code": "EXPRESSION_DISCOVERY_COMPLETE",
                       "coverage": "COMPLETE_FOR_SCOPE", "genes": len(result.entries),
                       "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
                       "gdc_cache_hits": totals["cache_hits"]})
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        raise SystemExit(1) from exc


def _discover_cnv(
    settings: Settings, repository: Repository, artifacts: ArtifactStore, case_shard: int,
    case_shard_size: int,
) -> None:
    from cancerjev.research.cnv_discovery import run_cnv_shard_scan
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    caps = production_caps(
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    try:
        with _started_run(
            repository, worker_id="cnv-shard-scan-worker",
            scope={"budget_policy": policy_payload(), "purpose": "CNV_SHARD_SCAN",
                   "spec_id": spec.spec_id, "cohort": spec.cohort.cohort_id,
                   "project_id": spec.cohort.project_id, "case_shard": case_shard,
                   "case_shard_size": case_shard_size},
            started_message=f"CNV case shard {case_shard} scan started.",
            started_data={"case_shard": case_shard, "case_shard_size": case_shard_size,
                          "research_spec": spec.as_dict()},
        ) as run_id:

            def emit(event_type: str, key: str, message: str, **kwargs) -> None:
                event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                                message=message, **kwargs)
                render_event(event)

            transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                                     cache_enabled=settings.gdc_cache_enabled)
            evidence = run_cnv_shard_scan(
                run_id, transport, repository, artifacts, emit, spec, shard_index=case_shard,
                case_shard_size=case_shard_size)
            totals = repository.gdc_run_totals(run_id)
            emit("RUN_COMPLETED", "run:completed",
                 f"CNV case shard {case_shard} completed over {len(evidence.case_ids)} case(s).",
                 data={"status": "COMPLETED", "reason_code": "CNV_SHARD_SCAN_COMPLETE",
                       "coverage": "COMPLETE_SHARD", "shard_index": case_shard,
                       "cases": len(evidence.case_ids), "genes": len(evidence.genes),
                       "records": evidence.records, "gdc_attempts": totals["attempts"],
                       "gdc_bytes": totals["bytes"], "gdc_cache_hits": totals["cache_hits"]})
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        raise SystemExit(1) from exc


def _cnv_merge(
    settings: Settings, repository: Repository, artifacts: ArtifactStore, shards: int,
    case_shard_size: int, source_run_ids: tuple[str, ...],
) -> None:
    from cancerjev.research.cnv_discovery import run_cnv_shard_merge
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    try:
        with _started_run(
            repository, worker_id="cnv-merge-worker",
            scope={"budget_policy": policy_payload(), "purpose": "CNV_PROJECT_SCAN",
                   "spec_id": spec.spec_id, "cohort": spec.cohort.cohort_id,
                   "project_id": spec.cohort.project_id, "shards": shards,
                   "case_shard_size": case_shard_size},
            started_message=f"Merged CNV project scan started over {shards} shard(s).",
            started_data={"shards": shards},
        ) as run_id:

            def emit(event_type: str, key: str, message: str, **kwargs) -> None:
                event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                                message=message, **kwargs)
                render_event(event)

            result = run_cnv_shard_merge(
                run_id, repository, artifacts, emit, spec, expected_shards=shards,
                case_shard_size=case_shard_size, source_run_ids=source_run_ids)
            emit("RUN_COMPLETED", "run:completed",
                 f"Merged CNV project scan completed for {len(result.calls)} observed gene(s).",
                 data={"status": "COMPLETED", "reason_code": "CNV_PROJECT_SCAN_COMPLETE",
                       "coverage": "COMPLETE_PROJECT", "genes": len(result.calls),
                       "retained": len(result.retained_ids),
                       "jev_review": len(result.jev_review_ids), "shards": shards})
    except (LiveRunError, ContractError) as exc:
        raise SystemExit(1) from exc


def _run_campaign_sweep(settings: Settings, repository: Repository, artifacts: ArtifactStore,
                        profile: Any, spec: Any, transport_factory: Any) -> bool:
    """The existing bounded sweep, dispatched under SYSTEM_AUTONOMOUS ownership only."""
    orchestrator = LiveOrchestrator(
        settings, repository, artifacts, render_event, transport_factory=transport_factory,
        research_spec=spec, worker_id="campaign-worker",
        execution_ownership=ExecutionOwnership.SYSTEM_AUTONOMOUS)
    run_id = orchestrator.run()
    return repository.get_run(run_id)["status"] == "COMPLETED"


def _dispatch_campaign(settings: Settings, repository: Repository, artifacts: ArtifactStore,
                       profile: Any, *, capability: Any = None,
                       transport_factory: Any = None) -> bool:
    """Ownership-gated autonomous dispatch of one validated campaign; no operator flags.

    A profile that is not validated for autonomous use, an unknown spec and a missing
    or incomplete capability record are refused loudly. When no capability is supplied,
    a bounded preflight probe (status, one project, one open-file facet aggregate) runs
    first inside a SYSTEM_AUTONOMOUS run and its result feeds the same gate.
    """
    from cancerjev.research.campaign import CampaignActivationError, require_autonomous_activation
    from cancerjev.research.capability import discover_cohort_capability
    from cancerjev.research.program import dispatch_validated_campaign
    from cancerjev.research.specs import research_spec_by_id

    spec = research_spec_by_id(profile.spec_id)
    if spec is None:
        raise CampaignActivationError("UNKNOWN_RESEARCH_SPEC",
                                      f"{profile.profile_id} declares unknown spec {profile.spec_id}")
    require_autonomous_activation(profile)
    if capability is None:
        caps = production_caps(per_response_bytes=settings.gdc_per_response_bytes,
                               timeout_seconds=settings.gdc_timeout_seconds)
        factory = transport_factory if transport_factory is not None else (
            lambda repo, arts, budget, run_id, emit: GDCTransport(
                repo, arts, budget, run_id, emit, cache_enabled=settings.gdc_cache_enabled))
        with _started_run(
            repository, worker_id="campaign-preflight",
            scope={"budget_policy": policy_payload(), "purpose": "CAMPAIGN_CAPABILITY_PREFLIGHT",
                   "profile_id": profile.profile_id, "project_id": profile.project_id},
            started_message=f"Campaign capability preflight started for {profile.project_id}.",
            started_data={"project_id": profile.project_id},
        ) as preflight_run:

            def preflight_emit(event_type: str, key: str, message: str, **kwargs: Any) -> None:
                render_event(repository.append_event(preflight_run, event_type=event_type,
                                                     idempotency_key=key, message=message, **kwargs))

            transport = factory(repository, artifacts, RunBudget(caps=caps), preflight_run,
                                preflight_emit)
            capability = discover_cohort_capability(transport, project_id=profile.project_id)
            totals = repository.gdc_run_totals(preflight_run)
            preflight_emit("RUN_COMPLETED", "run:completed",
                           f"Campaign capability preflight completed for {profile.project_id}.",
                           data={"status": "COMPLETED",
                                 "reason_code": "CAMPAIGN_CAPABILITY_PREFLIGHT_COMPLETE",
                                 "coverage": "COMPLETE_FOR_SCOPE", "project_id": profile.project_id,
                                 "available_modalities": [modality.value
                                                          for modality in capability.available_modalities()],
                                 "bytes": totals["bytes"], "gdc_attempts": totals["attempts"]})
    return dispatch_validated_campaign(
        profile=profile, capability=capability,
        run_campaign=lambda selected: _run_campaign_sweep(
            settings, repository, artifacts, selected, spec, transport_factory))


def _program(settings: Settings, repository: Repository, artifacts: ArtifactStore) -> None:
    """One autonomous program step; with no validated campaign it records PROGRAM_IDLE."""
    from cancerjev.research.campaign import LUAD_CAMPAIGN_V1, CampaignActivationError
    from cancerjev.research.capability import CapabilityError
    from cancerjev.research.program import run_program_worker

    profiles = (LUAD_CAMPAIGN_V1,)
    with _started_run(
        repository, worker_id="program-worker",
        scope={"budget_policy": policy_payload(), "purpose": "PROGRAM",
               "profiles": [profile.payload() for profile in profiles]},
        started_message="Autonomous program step started.",
    ) as run_id:

        def emit(target_run_id: str, event_type: str, key: str, message: str, **kwargs) -> None:
            event = repository.append_event(target_run_id, event_type=event_type,
                                            idempotency_key=key, message=message, **kwargs)
            render_event(event)

        def run_campaign(profile: Any) -> bool:
            """Ownership-gated dispatch; a blocked campaign is recorded, never overridden."""
            try:
                return _dispatch_campaign(settings, repository, artifacts, profile)
            except (CampaignActivationError, CapabilityError, TransportError, ParserError,
                    LiveRunError, ContractError) as exc:
                code = getattr(exc, "code", type(exc).__name__)
                emit(run_id, "CAMPAIGN_DISPATCH_FAILED",
                     f"program:{run_id}:dispatch-failed:{profile.profile_id}",
                     f"Campaign dispatch failed: {code}.", level="error",
                     data={"profile_id": profile.profile_id, "reason_code": str(code)})
                return False

        def publish_json(target_run_id: str, path: str, payload: bytes, purpose: str) -> Any:
            return artifacts.publish(path, payload, "application/json", purpose)

        outcome, artifact = run_program_worker(
            run_id=run_id, repository=repository, artifacts=artifacts, emit=emit,
            publish_json=publish_json, profiles=profiles, run_campaign=run_campaign)
        emit(run_id, "RUN_COMPLETED", "run:completed", "Program step completed.",
             data={"status": "COMPLETED", "reason_code": outcome.reason_code,
                   "state": outcome.state.value, "selected_profile_id": outcome.selected_profile_id,
                   "artifact_id": artifact.artifact_id},
             artifact_refs=[artifact.ref()])
        print(f"[PROGRAM] state={outcome.state.value} reason={outcome.reason_code} "
              f"selected={outcome.selected_profile_id}", flush=True)


def main(argv: list[str] | None = None) -> None:
    load_local_env()
    args = parser().parse_args(argv)
    live = bool(getattr(args, "live", False))
    jev_requested = bool(getattr(args, "jev", False))
    deep_candidate = getattr(args, "deep_candidate", None)
    deep_action = getattr(args, "deep_action", None)
    deep_followup = bool(getattr(args, "deep_followup", False))
    deep_hypotheses = bool(getattr(args, "deep_hypotheses", False))
    if jev_requested and not live:
        raise SystemExit("--jev requires --live (Jev evaluates real GDC states only).")
    if jev_requested and not os.getenv("TYPESAFE_API_KEY"):
        raise SystemExit("--jev requires the TYPESAFE_API_KEY environment variable (server-side only).")
    if deep_candidate and not (live and jev_requested):
        raise SystemExit("--deep-candidate requires --live --jev (a deep slice needs a wide-evaluated candidate).")
    if deep_followup and not deep_candidate:
        raise SystemExit("--deep-followup requires --deep-candidate (dispatch is authorized per candidate).")
    if deep_hypotheses and not (deep_candidate and deep_followup):
        raise SystemExit("--deep-hypotheses requires --deep-candidate --deep-followup.")
    if deep_action:
        from cancerjev.science.actions import ACTION_REGISTRY

        if not deep_candidate:
            raise SystemExit("--deep-action requires --deep-candidate (an action is selected for one candidate).")
        if deep_action not in ACTION_REGISTRY:
            raise SystemExit(f"Unknown action id: {deep_action}. Registered: {', '.join(sorted(ACTION_REGISTRY))}")
    if (deep_candidate or deep_action or deep_followup or deep_hypotheses) \
            and not getattr(args, "researcher", False):
        raise SystemExit("operator deep flags require --researcher (autonomous runs reject operator overrides).")
    if args.command in {"run", "worker"} and not live and getattr(args, "fixture", None) != "demo":
        raise SystemExit("Choose --fixture demo for the offline demonstration or --live for a real open-access GDC sweep.")
    if args.command in {"discover", "discover-expression", "discover-cnv"} and not live:
        raise SystemExit(f"{args.command} requires --live (systematic discovery is a real bounded open-access GDC task).")
    settings = Settings.from_env()
    repository, artifacts = _services(settings)
    if args.command == "show":
        run = repository.get_run(args.run_id)
        if not run:
            raise SystemExit(f"Unknown run: {args.run_id}")
        print(json.dumps(run, indent=2, sort_keys=True), flush=True)
        if args.events:
            page = repository.events(args.run_id, 0, 500)
            for event in page["items"]:
                render_json_event(event)
        return
    if args.command == "evaluate":
        from pathlib import Path as _Path

        from cancerjev.research.evaluation import (
            EvaluationError,
            evaluate_run,
            load_labels,
            report_path,
            write_report,
        )

        try:
            labels = load_labels(_Path(args.labels))
            report = evaluate_run(run_id=args.run_id, repository=repository, artifacts=artifacts,
                                 labels=labels, k=args.k)
        except EvaluationError as exc:
            raise SystemExit(str(exc)) from exc
        target = _Path(args.out) if args.out else report_path(settings.data_dir, report)
        write_report(target, report)
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True), flush=True)
        print(f"[EVALUATION] report written to {target}", flush=True)
        return
    if args.command == "probe":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _probe(settings, repository, artifacts, args.capture_dir)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "capability":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _capability(settings, repository, artifacts, project_id=args.project)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "program":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _program(settings, repository, artifacts)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "discover":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _discover(settings, repository, artifacts)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "discover-expression":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _discover_expression(settings, repository, artifacts)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "discover-cnv":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _discover_cnv(settings, repository, artifacts, args.case_shard,
                              args.case_shard_size)
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    if args.command == "cnv-merge":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _cnv_merge(settings, repository, artifacts, args.shards, args.case_shard_size,
                           tuple(args.source_run))
        except OwnershipError as exc:
            raise SystemExit(str(exc)) from exc
        return
    try:
        with ResearchOwnership(settings.lock_path):
            recovered = repository.recover_interrupted()
            for run_id in recovered:
                print(f"[RECOVERY] preserved and stopped interrupted run {run_id}", flush=True)
            if live:
                jev_service = None
                if jev_requested:
                    from cancerjev.jev.service import JevService

                    jev_service = JevService(settings, repository, artifacts)
                llm_generator = None
                if deep_candidate and jev_requested and settings.llm_model and os.getenv("OPENROUTER_API_KEY"):
                    from cancerjev.llm.openrouter import OpenRouterGenerator

                    llm_generator = OpenRouterGenerator(model=settings.llm_model,
                                                        timeout=settings.llm_timeout_seconds)
                    print(f"[LLM] hypothesis generation enabled with {settings.llm_model}", flush=True)
                elif deep_candidate:
                    print("[LLM] no provider credential/model configured; generated text stays deterministic",
                          flush=True)
                orchestrator = LiveOrchestrator(settings, repository, artifacts, render_event,
                                                jev_service=jev_service,
                                                deep_selection=(deep_candidate or [None])[0],
                                                deep_selections=tuple(deep_candidate or ()),
                                                deep_action_id=deep_action,
                                                deep_followup_authorized=deep_followup,
                                                deep_hypotheses_requested=deep_hypotheses,
                                                execution_ownership=(
                                                    ExecutionOwnership.RESEARCHER_RUN
                                                    if args.researcher else
                                                    ExecutionOwnership.SYSTEM_AUTONOMOUS),
                                                llm_generator=llm_generator)
            else:
                orchestrator = DemoOrchestrator(settings, repository, artifacts, render_event)
            if args.command == "run":
                completed_run_id = orchestrator.run()
                if repository.get_run(completed_run_id)["status"] != "COMPLETED":
                    raise SystemExit(1)
                return
            while True:
                orchestrator.run()
                print(f"[WORKER] sleeping {settings.run_interval_minutes} minute(s)", flush=True)
                time.sleep(settings.run_interval_minutes * 60)
    except OwnershipError as exc:
        raise SystemExit(str(exc)) from exc
    except KeyboardInterrupt:
        print("[WORKER] stopped", flush=True)
