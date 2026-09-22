from __future__ import annotations

import argparse
import time

from cancerjev.cli.console import render_event, render_json_event
from cancerjev.config import Settings
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
        command.add_argument("--fixture", choices=["demo"])
    show = commands.add_parser("show")
    show.add_argument("run_id")
    show.add_argument("--events", action="store_true")
    return root


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    settings = Settings.from_env()
    database = Database(settings.database_path)
    database.bootstrap()
    repository = Repository(database)
    if args.command == "show":
        run = repository.get_run(args.run_id)
        if not run:
            raise SystemExit(f"Unknown run: {args.run_id}")
        print(run)
        if args.events:
            page = repository.events(args.run_id, 0, 500)
            for event in page["items"]:
                render_json_event(event)
        return
    if args.fixture != "demo":
        raise SystemExit("Live research is not implemented in Phase 1. Use --fixture demo.")
    try:
        with ResearchOwnership(settings.lock_path):
            recovered = repository.recover_interrupted()
            for run_id in recovered:
                print(f"[RECOVERY] preserved and stopped interrupted run {run_id}", flush=True)
            orchestrator = DemoOrchestrator(settings, repository, ArtifactStore(settings.data_dir), render_event)
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

