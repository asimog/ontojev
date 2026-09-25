from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from cancerjev.cli.console import render_event, render_json_event
from cancerjev.config import Settings, load_local_env
from cancerjev.domain.discovery import OCCURRENCE_SCAN_MAX_BYTES, OCCURRENCE_SCAN_MAX_PAGES
from cancerjev.domain.measurements import ContractError
from cancerjev.gdc.capture import CaptureSink, run_contract_probe
from cancerjev.gdc.parsers import ParserError
from cancerjev.gdc.transport import BudgetCaps, GDCTransport, RunBudget, TransportError
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
    discover = commands.add_parser(
        "discover",
        help="bounded Stage 4 systematic mutation discovery over the fixed indexed gene universe",
    )
    discover.add_argument("--live", action="store_true",
                          help="real bounded open-access GDC systematic discovery")
    discover_expression = commands.add_parser(
        "discover-expression",
        help="bounded Stage 5 expression discovery over the fixed indexed gene universe",
    )
    discover_expression.add_argument(
        "--live", action="store_true",
        help="real bounded open-access GDC independent expression discovery",
    )
    discover_cnv = commands.add_parser(
        "discover-cnv",
        help="bounded Stage 6 CNV occurrence discovery for one Stage 4 survivor result",
    )
    discover_cnv.add_argument("--live", action="store_true",
                              help="real bounded open-access GDC CNV discovery")
    discover_cnv.add_argument(
        "--stage4-run", required=True,
        help="completed Stage 4 run whose immutable survivor result is the only CNV gene input",
    )
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


def _probe(settings: Settings, repository: Repository, artifacts: ArtifactStore, capture_dir: str | None) -> None:
    caps = BudgetCaps(
        max_requests=30, max_bytes=8 * 1024 * 1024,
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    run_id = repository.create_run("probe", mode="LIVE", fixture_id=None, fixture_version=None,
                                   scope={"purpose": "CONTRACT_PROBE"})

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        event = repository.append_event(run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)
        render_event(event)

    emit("RUN_STARTED", "run:started", "Contract probe run started.", data={"mode": "LIVE", "purpose": "CONTRACT_PROBE"})
    transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit, cache_enabled=False)
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
    print(f"[PROBE] captures written to {directory} ({summary['captures']} requests, {summary['bytes']} bytes)", flush=True)


def _discover(settings: Settings, repository: Repository, artifacts: ArtifactStore) -> None:
    from cancerjev.research.discovery import run_mutation_discovery
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    # The systematic-discovery worker declares the mutation occurrence-scan budget
    # explicitly: a complete project scan is the scientific quantity source, and its
    # declared ceiling lives in domain.discovery (not env-adjustable in this change).
    caps = BudgetCaps(
        max_requests=settings.gdc_max_requests,
        max_bytes=OCCURRENCE_SCAN_MAX_BYTES,
        per_response_bytes=settings.gdc_per_response_bytes,
        max_pages_per_query=OCCURRENCE_SCAN_MAX_PAGES,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    run_id = repository.create_run(
        "discovery-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "SYSTEMATIC_DISCOVERY", "spec_id": spec.spec_id,
               "domain": spec.cohort.domain, "cohort": spec.cohort.cohort_id,
               "project_id": spec.cohort.project_id, "discovery": asdict(spec.discovery),
               "selection_rule": spec.discovery_selection_rule()},
    )

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                        message=message, **kwargs)
        render_event(event)

    emit("RUN_STARTED", "run:started", "Bounded systematic discovery run started.",
         data={"mode": "LIVE", "purpose": "SYSTEMATIC_DISCOVERY", "research_spec": spec.as_dict()})
    budget = RunBudget(caps=caps)
    transport = GDCTransport(repository, artifacts, budget, run_id, emit,
                             cache_enabled=settings.gdc_cache_enabled)
    try:
        result = run_mutation_discovery(run_id, transport, repository, artifacts, emit, spec)
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        emit("RUN_FAILED", "run:failed", f"Systematic discovery failed: {code}.",
             level="error", data={"status": "FAILED", "reason_code": str(code), "detail": str(exc)})
        return
    totals = repository.gdc_run_totals(run_id)
    emit("RUN_COMPLETED", "run:completed",
         f"Systematic discovery completed with {len(result.survivor_ids)} survivor(s).",
         data={"status": "COMPLETED", "reason_code": "DISCOVERY_COMPLETE",
               "coverage": "COMPLETE_FOR_SCOPE", "survivor_ids": list(result.survivor_ids),
               "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
               "gdc_cache_hits": totals["cache_hits"]})


def _discover_expression(
    settings: Settings, repository: Repository, artifacts: ArtifactStore,
) -> None:
    from cancerjev.research.expression_discovery import run_expression_discovery
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    spec = LUAD_RESEARCH_V1
    caps = BudgetCaps(
        max_requests=settings.gdc_max_requests,
        max_bytes=settings.gdc_max_bytes,
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    run_id = repository.create_run(
        "expression-discovery-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "EXPRESSION_DISCOVERY", "spec_id": spec.spec_id,
               "domain": spec.cohort.domain, "cohort": spec.cohort.cohort_id,
               "project_id": spec.cohort.project_id,
               "expression_discovery": asdict(spec.expression_discovery),
               "selection_rule": spec.discovery_selection_rule()},
    )

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                        message=message, **kwargs)
        render_event(event)

    emit("RUN_STARTED", "run:started", "Bounded expression discovery run started.",
         data={"mode": "LIVE", "purpose": "EXPRESSION_DISCOVERY",
               "research_spec": spec.as_dict()})
    transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                             cache_enabled=settings.gdc_cache_enabled)
    try:
        result = run_expression_discovery(
            run_id, transport, repository, artifacts, emit, spec)
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        emit("RUN_FAILED", "run:failed", f"Expression discovery failed: {code}.",
             level="error", data={"status": "FAILED", "reason_code": str(code),
                                  "detail": str(exc)})
        return
    totals = repository.gdc_run_totals(run_id)
    emit("RUN_COMPLETED", "run:completed",
         f"Expression discovery completed for {len(result.entries)} gene(s).",
         data={"status": "COMPLETED", "reason_code": "EXPRESSION_DISCOVERY_COMPLETE",
               "coverage": "COMPLETE_FOR_SCOPE", "genes": len(result.entries),
               "gdc_attempts": totals["attempts"], "gdc_bytes": totals["bytes"],
               "gdc_cache_hits": totals["cache_hits"]})


def _discover_cnv(
    settings: Settings, repository: Repository, artifacts: ArtifactStore, stage4_run_id: str,
) -> None:
    from cancerjev.domain.codecs import discovery_identity, read_discovery
    from cancerjev.research.cnv_discovery import run_cnv_discovery
    from cancerjev.research.specs import LUAD_RESEARCH_V1

    source_run = repository.get_run(stage4_run_id)
    if source_run is None or source_run["status"] != "COMPLETED":
        raise SystemExit("--stage4-run must identify a completed Stage 4 run")
    events = repository.events(stage4_run_id, 0, 500)["items"]
    completed = [event for event in events if event["type"] == "DISCOVERY_COMPLETED"]
    if len(completed) != 1:
        raise SystemExit("--stage4-run must contain exactly one DISCOVERY_COMPLETED event")
    artifact_id = completed[0]["data"].get("artifact_id")
    if not isinstance(artifact_id, str):
        raise SystemExit("Stage 4 completion event has no result artifact")
    metadata = repository.artifact(artifact_id)
    if metadata is None:
        raise SystemExit("Stage 4 result artifact registration is missing")
    raw = artifacts.read(metadata["relative_path"], metadata["sha256"])
    mutation_result = read_discovery(raw)
    mutation_hash = discovery_identity(mutation_result)
    spec = LUAD_RESEARCH_V1
    caps = BudgetCaps(
        max_requests=settings.gdc_max_requests, max_bytes=settings.gdc_max_bytes,
        per_response_bytes=settings.gdc_per_response_bytes,
        timeout_seconds=settings.gdc_timeout_seconds,
    )
    run_id = repository.create_run(
        "cnv-discovery-worker", mode="LIVE", fixture_id=None, fixture_version=None,
        scope={"purpose": "CNV_DISCOVERY", "spec_id": spec.spec_id,
               "cohort": spec.cohort.cohort_id, "project_id": spec.cohort.project_id,
               "stage4_run_id": stage4_run_id, "mutation_discovery_hash": mutation_hash,
               "cnv_discovery": asdict(spec.cnv_discovery)},
    )

    def emit(event_type: str, key: str, message: str, **kwargs) -> None:
        event = repository.append_event(run_id, event_type=event_type, idempotency_key=key,
                                        message=message, **kwargs)
        render_event(event)

    emit("RUN_STARTED", "run:started", "Bounded CNV discovery run started.",
         data={"mode": "LIVE", "purpose": "CNV_DISCOVERY",
               "stage4_run_id": stage4_run_id, "mutation_discovery_hash": mutation_hash,
               "research_spec": spec.as_dict()})
    transport = GDCTransport(repository, artifacts, RunBudget(caps=caps), run_id, emit,
                             cache_enabled=settings.gdc_cache_enabled)
    try:
        result = run_cnv_discovery(
            run_id, transport, repository, artifacts, emit, spec, mutation_result)
    except (TransportError, ParserError, LiveRunError, ContractError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        emit("RUN_FAILED", "run:failed", f"CNV discovery failed: {code}.", level="error",
             data={"status": "FAILED", "reason_code": str(code), "detail": str(exc)})
        return
    totals = repository.gdc_run_totals(run_id)
    emit("RUN_COMPLETED", "run:completed",
         f"CNV discovery completed for {len(result.entries)} survivor(s).",
         data={"status": "COMPLETED", "reason_code": "CNV_DISCOVERY_COMPLETE",
               "coverage": "COMPLETE_OR_EXPLICITLY_UNAVAILABLE_PER_SURVIVOR",
               "genes": len(result.entries), "gdc_attempts": totals["attempts"],
               "gdc_bytes": totals["bytes"], "gdc_cache_hits": totals["cache_hits"]})


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
                _discover_cnv(settings, repository, artifacts, args.stage4_run)
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
                                                llm_generator=llm_generator)
            else:
                orchestrator = DemoOrchestrator(settings, repository, artifacts, render_event)
            if args.command == "run":
                orchestrator.run()
                return
            while True:
                orchestrator.run()
                print(f"[WORKER] sleeping {settings.run_interval_minutes} minute(s)", flush=True)
                time.sleep(settings.run_interval_minutes * 60)
    except OwnershipError as exc:
        raise SystemExit(str(exc)) from exc
    except KeyboardInterrupt:
        print("[WORKER] stopped", flush=True)
