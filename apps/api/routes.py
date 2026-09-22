from __future__ import annotations

import json
import sqlite3
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

router = APIRouter()


def services(request: Request) -> tuple[Repository, ArtifactStore]:
    return request.app.state.repository, request.app.state.artifacts


def envelope(items: list[dict]) -> dict:
    return {"items": items, "next_cursor": None, "has_more": False}


@router.get("/health")
def health(request: Request):
    repository, _ = services(request)
    try:
        with repository.database.read() as connection:
            connection.execute("SELECT version FROM schema_info").fetchone()
        return {"status": "ok", "schema_version": 1}
    except sqlite3.Error as exc:
        raise HTTPException(503, detail="CancerJEV storage is unavailable") from exc


@router.get("/api/system")
def system(request: Request):
    repository, _ = services(request)
    with repository.database.read() as connection:
        worker = connection.execute("SELECT * FROM worker_status WHERE singleton=1").fetchone()
        active = connection.execute("SELECT run_id FROM research_runs WHERE status IN ('PENDING','RUNNING') ORDER BY created_at DESC LIMIT 1").fetchone()
    return {"schema_version": 1, "phase": 1, "mode": "FAKE_ONLY", "providers": {"gdc": False, "jev": False, "llm": False}, "worker": dict(worker) if worker else None, "active_run_id": active["run_id"] if active else None}


@router.get("/api/runs")
def runs(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, status: str | None = None, cursor: str | None = None):
    repository, _ = services(request)
    try:
        return repository.page_runs(limit, cursor, status)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/api/runs/{run_id}")
def run_detail(run_id: UUID, request: Request):
    repository, _ = services(request)
    item = repository.get_run(str(run_id))
    if not item:
        raise HTTPException(404, detail="run not found")
    item["candidates"] = repository.list_table("candidates", str(run_id))
    return item


@router.get("/api/runs/{run_id}/events")
def events(run_id: UUID, request: Request, after_sequence: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 200):
    repository, _ = services(request)
    try:
        return repository.events(str(run_id), after_sequence, limit)
    except KeyError as exc:
        raise HTTPException(404, detail="run not found") from exc


def child_list(table: str, run_id: UUID, request: Request, limit: int):
    repository, _ = services(request)
    if not repository.get_run(str(run_id)):
        raise HTTPException(404, detail="run not found")
    return envelope(repository.list_table(table, str(run_id), limit))


@router.get("/api/runs/{run_id}/candidates")
def candidates(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return child_list("candidates", run_id, request, limit)


@router.get("/api/runs/{run_id}/states")
def states(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return child_list("statistical_states", run_id, request, limit)


@router.get("/api/runs/{run_id}/evaluations")
def evaluations(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return child_list("jev_evaluations", run_id, request, limit)


@router.get("/api/runs/{run_id}/hypotheses")
def run_hypotheses(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return child_list("hypotheses", run_id, request, limit)


@router.get("/api/runs/{run_id}/dossiers")
def run_dossiers(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return child_list("dossiers", run_id, request, limit)


@router.get("/api/dossiers")
def dossiers(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, cursor: str | None = None):
    repository, _ = services(request)
    try:
        return repository.page_dossiers(limit, cursor)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/api/dossiers/{dossier_id}")
def dossier(dossier_id: UUID, request: Request, format: Literal["json", "markdown"] = "json"):
    repository, artifacts = services(request)
    with repository.database.read() as connection:
        row = connection.execute("SELECT * FROM dossiers WHERE dossier_id=?", (str(dossier_id),)).fetchone()
    if not row:
        raise HTTPException(404, detail="dossier not found")
    artifact_id = row["json_artifact_id"] if format == "json" else row["markdown_artifact_id"]
    metadata = repository.artifact(artifact_id)
    assert metadata
    try:
        content = artifacts.read(metadata["relative_path"], metadata["sha256"])
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="dossier artifact unavailable or corrupt") from exc
    if format == "markdown":
        return Response(content, media_type="text/markdown")
    return JSONResponse(json.loads(content))


@router.get("/api/artifacts/{artifact_id}")
def artifact(artifact_id: UUID, request: Request):
    repository, artifacts = services(request)
    metadata = repository.artifact(str(artifact_id))
    if not metadata:
        raise HTTPException(404, detail="artifact not found")
    if not (metadata["media_type"].startswith("application/json") or metadata["media_type"].startswith("text/markdown")):
        raise HTTPException(404, detail="artifact is not browser-readable")
    try:
        content = artifacts.read(metadata["relative_path"], metadata["sha256"])
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="artifact unavailable or corrupt") from exc
    return Response(content, media_type=metadata["media_type"], headers={"ETag": f'"{metadata["sha256"]}"'})
