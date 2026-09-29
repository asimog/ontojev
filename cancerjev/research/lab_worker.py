"""Process supervisor: hard run deadline, restart recovery and first-class lab CLI."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from cancerjev.config import Settings
from cancerjev.domain.laboratory import FINALIZATION_SECONDS, RUN_SECONDS
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.jev.service import JevService
from cancerjev.llm.ontocodex import CodexDirector
from cancerjev.research.lab_acquisition import cleanup_shard
from cancerjev.research.lab_capabilities import ScientificLabCapabilities
from cancerjev.research.lab_runtime import RunClock, run_block
from cancerjev.research.laboratory import load_lab, next_revision, save_lab
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.ownership import ResearchOwnership
from cancerjev.storage.repositories import Repository


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def supervise(command: list[str], *, timeout: float) -> int:
    """No scientific writes in the parent until the worker process has exited."""
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               start_new_session=os.name != "nt",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(process)
        return 124
    except BaseException:
        terminate_tree(process)
        raise


def recover_workspaces(repository: Repository, artifacts: ArtifactStore) -> None:
    root = artifacts.data_dir / "shards"
    if not root.exists():
        return
    for path in root.iterdir():
        try:
            run_id = str(UUID(path.name))
        except ValueError:
            raise ValueError("unrecognized directory in lab shard workspace") from None
        run = repository.get_run(run_id)
        if run is None or run.get("purpose") != "LAB":
            raise ValueError("shard workspace has no owning laboratory run")
        cleanup = cleanup_shard(repository, artifacts, run_id)
        repository.append_event(run_id, event_type="LAB_RAW_CLEANUP",
                                idempotency_key=f"lab:recovery-cleanup:{time.time_ns()}",
                                message="Interrupted raw workspace cleanup retried.",
                                data={"category": "raw_data", **cleanup})
        if cleanup["status"] != "CLEAN":
            raise OSError("raw shard cleanup remains incomplete")


def run_lab(settings: Settings, *, max_runs: int = 1, seconds: float = RUN_SECONDS) -> list[str]:
    if not 1 <= max_runs <= 100:
        raise ValueError("max_runs must be 1..100")
    RunClock(seconds=seconds)
    database = Database(settings.database_path)
    database.bootstrap()
    repository, artifacts = Repository(database), ArtifactStore(settings.data_dir)
    completed: list[str] = []
    with ResearchOwnership(settings.lock_path):
        # Recovery and worker startup share a lock. A late child must observe
        # its recovered terminal run before it can initialize any provider.
        with ResearchOwnership(settings.data_dir / "lab-worker.lock"):
            repository.recover_interrupted()
            recover_workspaces(repository, artifacts)
        for _ in range(max_runs):
            state = load_lab(repository, artifacts)
            if state.operational_state in {"STOPPED", "NO_PROGRESS"}:
                break
            run_id = repository.create_run("ontocodex", mode="LIVE", fixture_id=None,
                fixture_version=None, scope={"purpose": "LAB", "budget_seconds": seconds,
                    "objective": state.domain, "selected_project_ids": sorted({q.project_id for q in state.questions})})
            repository.append_event(run_id, event_type="RUN_STARTED", idempotency_key="run:start",
                                    message="Bounded autonomous laboratory block started.")
            started = time.monotonic()
            code = supervise([sys.executable, "-m", "cancerjev.research.lab_worker",
                              "--child", run_id, "--root", str(settings.data_dir),
                              "--seconds", str(seconds)], timeout=seconds - FINALIZATION_SECONDS)
            cleanup = cleanup_shard(repository, artifacts, run_id)
            repository.append_event(run_id, event_type="LAB_RAW_CLEANUP",
                idempotency_key="lab:supervisor-cleanup", message="Supervisor verified raw workspace cleanup.",
                data={"category": "raw_data", **cleanup})
            current = load_lab(repository, artifacts)
            reason: str = current.operational_state
            if code != 0:
                # The worker can fail after committing science. Keep that
                # immutable revision, but report the process failure honestly.
                reason = "CONTINUE_NEXT_RUN" if code == 124 else "OPERATION_FAILED"
            if current.last_run_id != run_id:
                reason = "CONTINUE_NEXT_RUN" if code == 124 else "OPERATION_FAILED"
                current = current.model_copy(update={"operational_state": reason,
                    "consecutive_no_progress": current.consecutive_no_progress + 1})
                if current.consecutive_no_progress >= 3:
                    current = current.model_copy(update={"operational_state": "NO_PROGRESS"})
                save_lab(repository, artifacts, run_id, next_revision(repository, current, run_id))
            if cleanup["status"] != "CLEAN":
                reason = "CLEANUP_FAILED"
            success = code == 0 and reason in {"READY", "STOPPED", "CAPABILITY_GAP"}
            repository.append_event(run_id, event_type="RUN_COMPLETED" if success else "RUN_STOPPED",
                idempotency_key="run:terminal", message="Research Run finalized.",
                data={"reason_code": reason, "coverage": "PARTIAL",
                      "elapsed_seconds": time.monotonic() - started, "exit_code": code})
            completed.append(run_id)
            print(f"{run_id} {reason}", flush=True)
            if not success:
                break
    return completed


def child_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    run_id = str(UUID(args.child))
    root = Path(args.root).resolve()
    with ResearchOwnership(root / "lab-worker.lock"):
        settings = replace(Settings.from_env(), data_dir=root)
        repository = Repository(Database(settings.database_path))
        run = repository.get_run(run_id)
        if (run is None or run.get("purpose") != "LAB" or run["status"] != "RUNNING"
                or run["execution_ownership"] != ExecutionOwnership.SYSTEM_AUTONOMOUS.value):
            raise ValueError("worker requires an active autonomous laboratory run")
        artifacts = ArtifactStore(settings.data_dir)
        clock = RunClock(seconds=args.seconds)
        director = CodexDirector.from_settings(settings)
        acquisition = ScientificLabCapabilities.live(repository, artifacts, run_id, clock)
        experiment = os.getenv("ONTOCODEX_JEV_EXPERIMENT", "off")
        if experiment not in {"off", "relevance", "choice"}:
            raise ValueError("ONTOCODEX_JEV_EXPERIMENT must be off, relevance or choice")
        run_block(repository, artifacts, run_id, director, acquisition, clock,
                  JevService(settings, repository, artifacts) if experiment != "off" else None,
                  comparative_jev=experiment == "choice")


if __name__ == "__main__":
    child_main()
