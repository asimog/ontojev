from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from cancerjev.cli.console import render_event, render_json_event
from cancerjev.config import Settings
from cancerjev.gdc.capture import CaptureSink, run_contract_probe
from cancerjev.gdc.transport import BudgetCaps, GDCTransport, RunBudget
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
                             help="Phase 3 wide Jev evaluation over real states (requires TYPESAFE_API_KEY)")
        command.add_argument("--deep-candidate", default=None,
                             help="explicitly selected candidate for the deterministic deep slice: gene symbol, "
                                  "gene:<SYMBOL>, state:<STATE_ID> (wide-evaluated states) or slot:N "
                                  "(policy-promoted candidates); requires --live --jev")
        command.add_argument("--deep-action", default=None,
                             help="explicitly selected registered action id for the deep slice (optional)")
    probe = commands.add_parser("probe", help="bounded anonymous GDC contract capture")
    probe.add_argument("--capture-dir", default=None)
    show = commands.add_parser("show")
    show.add_argument("run_id")
    show.add_argument("--events", action="store_true")
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


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    live = bool(getattr(args, "live", False))
    jev_requested = bool(getattr(args, "jev", False))
    deep_candidate = getattr(args, "deep_candidate", None)
    deep_action = getattr(args, "deep_action", None)
    if jev_requested and not live:
        raise SystemExit("--jev requires --live (Jev evaluates real GDC states only).")
    if jev_requested and not os.getenv("TYPESAFE_API_KEY"):
        raise SystemExit("--jev requires the TYPESAFE_API_KEY environment variable (server-side only).")
    if deep_candidate and not (live and jev_requested):
        raise SystemExit("--deep-candidate requires --live --jev (a deep slice needs a wide-evaluated candidate).")
    if deep_action:
        from cancerjev.science.actions import ACTION_REGISTRY

        if not deep_candidate:
            raise SystemExit("--deep-action requires --deep-candidate (an action is selected for one candidate).")
        if deep_action not in ACTION_REGISTRY:
            raise SystemExit(f"Unknown action id: {deep_action}. Registered: {', '.join(sorted(ACTION_REGISTRY))}")
    if args.command in {"run", "worker"} and not live and getattr(args, "fixture", None) != "demo":
        raise SystemExit("Choose --fixture demo for the offline demonstration or --live for a real open-access GDC sweep.")
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
    if args.command == "probe":
        try:
            with ResearchOwnership(settings.lock_path):
                repository.recover_interrupted()
                _probe(settings, repository, artifacts, args.capture_dir)
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
                orchestrator = LiveOrchestrator(settings, repository, artifacts, render_event,
                                                jev_service=jev_service,
                                                deep_selection=deep_candidate,
                                                deep_action_id=deep_action)
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
