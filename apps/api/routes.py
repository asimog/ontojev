from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from cancerjev.gdc.budget import INITIAL_REQUESTS, RUN_DOWNLOAD_BYTES, policy_payload
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import SCHEMA_VERSION
from cancerjev.storage.readers import (
    read_artifact,
    read_dossier_record,
    read_evidence_record,
    read_state_record,
)
from cancerjev.storage.repositories import Repository

from . import serializers

router = APIRouter()
API_VERSION = "3.0.0"


def services(request: Request) -> tuple[Repository, ArtifactStore]:
    return request.app.state.repository, request.app.state.artifacts


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    repository, _ = services(request)
    with repository.database.read() as connection:
        connection.execute("SELECT version FROM schema_info").fetchone()
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@router.get("/api/system")
def system(request: Request) -> dict[str, Any]:
    repository, _ = services(request)
    settings = request.app.state.settings
    with repository.database.read() as connection:
        worker = connection.execute("SELECT * FROM worker_status WHERE singleton=1").fetchone()
        active = connection.execute("SELECT run_id FROM research_runs WHERE status IN ('PENDING','RUNNING') ORDER BY created_at DESC LIMIT 1").fetchone()
        artifacts = connection.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()
        cache_entries = connection.execute("SELECT COUNT(*) AS count FROM gdc_cache").fetchone()["count"]
        jev_cache_entries = connection.execute("SELECT COUNT(*) AS count FROM jev_cache").fetchone()["count"]
        cache_bytes = connection.execute("SELECT COALESCE(SUM(size_bytes),0) AS total FROM gdc_cache").fetchone()["total"]
    heartbeat_at = worker["heartbeat_at"] if worker else None
    fresh = None
    if active and heartbeat_at:
        fresh = (datetime.now(UTC) - datetime.fromisoformat(heartbeat_at.replace("Z", "+00:00"))).total_seconds() <= 60
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": 3,
        "mode": "LIVE_AND_FIXTURE",
        "providers": {
            "gdc": True,
            "jev": bool(os.getenv("TYPESAFE_API_KEY")),
            "llm": bool(os.getenv("OPENROUTER_API_KEY")),
        },
        "worker": {"owner_id": worker["owner_id"], "heartbeat_at": heartbeat_at, "version": worker["version"], "fresh": fresh} if worker else None,
        "active_run_id": active["run_id"] if active else None,
        "data": {
            "directory": settings.data_dir.name,
            "database_bytes": settings.database_path.stat().st_size if settings.database_path.exists() else 0,
            "artifact_files": artifacts["count"],
        },
        "versions": {"api": API_VERSION, "schema": SCHEMA_VERSION, "worker": worker["version"] if worker else None},
        "budget_policy": policy_payload(),
        "budget_defaults": {
            "gdc_requests": INITIAL_REQUESTS,
            "gdc_bytes": RUN_DOWNLOAD_BYTES,
            "per_response_bytes": settings.gdc_per_response_bytes,
            "max_case_ids": 250,
            "max_gene_ids": 100,
            "reason": "Initial request allowance grows under budget_policy; run and shard byte ceilings are fixed.",
        },
        "cursor": {"present": False, "reason": "Phase 2 bounded sweeps are self-contained and use no cross-run discovery cursor."},
        "cache": {
            "entries": cache_entries, "bytes": cache_bytes,
            "jev_entries": jev_cache_entries,
            "reason": None,
        },
    }


@router.get("/api/runs")
def runs(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, status: str | None = None, cursor: str | None = None) -> dict[str, Any]:
    repository, _ = services(request)
    try:
        return repository.page_runs(limit, cursor, status)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/api/runs/{run_id}")
def run_detail(run_id: UUID, request: Request) -> dict[str, Any]:
    repository, _ = services(request)
    item = repository.get_run(str(run_id))
    if not item:
        raise HTTPException(404, detail="run not found")
    item["candidates"] = repository.list_table("candidates", str(run_id))
    return item


@router.get("/api/runs/{run_id}/events")
def events(run_id: UUID, request: Request, after_sequence: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 200) -> dict[str, Any]:
    repository, _ = services(request)
    try:
        return repository.events(str(run_id), after_sequence, limit)
    except KeyError as exc:
        raise HTTPException(404, detail="run not found") from exc


def child_list(table: str, run_id: UUID, request: Request, limit: int, cursor: str | None, filters: dict[str, str | None]) -> dict[str, Any]:
    repository, _ = services(request)
    if not repository.get_run(str(run_id)):
        raise HTTPException(404, detail="run not found")
    try:
        return repository.page_child(table, str(run_id), limit, cursor, filters)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/api/runs/{run_id}/candidates")
def candidates(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None) -> dict[str, Any]:
    return child_list("candidates", run_id, request, limit, cursor, {})


@router.get("/api/runs/{run_id}/states")
def states(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None, disposition: str | None = None) -> dict[str, Any]:
    return child_list("statistical_states", run_id, request, limit, cursor, {"disposition": disposition})


@router.get("/api/states/{state_id}")
def state_detail(state_id: UUID, request: Request) -> Response:
    repository, artifacts = services(request)
    row = repository.get_state(str(state_id))
    if not row:
        raise HTTPException(404, detail="state not found")
    metadata = repository.artifact(row["artifact_id"])
    if not metadata:
        raise HTTPException(503, detail="state artifact metadata missing")
    try:
        stored = read_state_record(repository, artifacts, str(state_id))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="state artifact unavailable or corrupt") from exc
    payload = serializers.state_detail(stored.record)
    headers = {"ETag": f'"{serializers.response_etag(payload)}"',
               "X-Artifact-Id": metadata["artifact_id"], "X-Artifact-SHA256": metadata["sha256"]}
    return JSONResponse(payload, headers=headers)


@router.get("/api/runs/{run_id}/projections")
def projections(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None) -> dict[str, Any]:
    return child_list("jev_projections", run_id, request, limit, cursor, {})


@router.get("/api/runs/{run_id}/rankings")
def rankings(run_id: UUID, request: Request) -> dict[str, object]:
    repository, artifacts = services(request)
    if not repository.get_run(str(run_id)):
        raise HTTPException(404, detail="run not found")
    result: dict[str, object] = {"baseline": None, "jev": None}
    for row in repository.ranking_artifacts(str(run_id)):
        key = "baseline" if row["relative_path"].endswith("baseline_ranking.json") else "jev"
        try:
            result[key] = json.loads(artifacts.read(row["relative_path"], row["sha256"]))
        except (OSError, ValueError) as exc:
            raise HTTPException(503, detail=f"{key} ranking artifact unavailable or corrupt") from exc
    return result


@router.get("/api/runs/{run_id}/evaluations")
def evaluations(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None, candidate_id: str | None = None, purpose: str | None = None) -> dict[str, Any]:
    return child_list("jev_evaluations", run_id, request, limit, cursor, {"candidate_id": candidate_id, "purpose": purpose})


@router.get("/api/runs/{run_id}/hypotheses")
def run_hypotheses(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
    return child_list("hypotheses", run_id, request, limit, cursor, {"candidate_id": candidate_id})


@router.get("/api/runs/{run_id}/dossiers")
def run_dossiers(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None) -> dict[str, Any]:
    return child_list("dossiers", run_id, request, limit, cursor, {})


@router.get("/api/runs/{run_id}/evidence")
def evidence_revisions(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
    return child_list("evidence_states", run_id, request, limit, cursor, {"candidate_id": candidate_id})


@router.get("/api/evidence/{evidence_state_id}")
def evidence_detail(evidence_state_id: UUID, request: Request) -> Response:
    repository, artifacts = services(request)
    row = repository.get_evidence_state(str(evidence_state_id))
    if not row:
        raise HTTPException(404, detail="evidence revision not found")
    metadata = repository.artifact(row["artifact_id"])
    if not metadata:
        raise HTTPException(503, detail="evidence artifact metadata missing")
    try:
        stored = read_evidence_record(repository, artifacts, str(evidence_state_id))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="evidence artifact unavailable or corrupt") from exc
    payload = serializers.evidence_detail(stored.record)
    headers = {"ETag": f'"{serializers.response_etag(payload)}"',
               "X-Artifact-Id": metadata["artifact_id"], "X-Artifact-SHA256": metadata["sha256"]}
    return JSONResponse(payload, headers=headers)


@router.get("/api/runs/{run_id}/followups")
def followup_executions(run_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100, cursor: str | None = None, candidate_id: str | None = None, status: str | None = None) -> dict[str, Any]:
    return child_list("followup_executions", run_id, request, limit, cursor,
                      {"candidate_id": candidate_id, "status": status})


@router.get("/api/dossiers")
def dossiers(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, cursor: str | None = None) -> dict[str, Any]:
    repository, _ = services(request)
    try:
        return repository.page_dossiers(limit, cursor)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/api/dossiers/{dossier_id}")
def dossier(dossier_id: UUID, request: Request, format: Literal["json", "markdown"] = "json") -> Response:
    repository, artifacts = services(request)
    row = repository.get_dossier(str(dossier_id))
    if not row:
        raise HTTPException(404, detail="dossier not found")
    artifact_id = row["json_artifact_id"] if format == "json" else row["markdown_artifact_id"]
    metadata = repository.artifact(artifact_id)
    if not metadata:
        raise HTTPException(503, detail="dossier artifact metadata missing")
    try:
        authoritative = read_dossier_record(repository, artifacts, str(dossier_id))
        content = (authoritative.content if format == "json" else
                   read_artifact(repository, artifacts, artifact_id, run_id=row["run_id"]).content)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, detail="dossier artifact unavailable or corrupt") from exc
    headers = {"ETag": f'"{metadata["sha256"]}"', "X-Artifact-Id": metadata["artifact_id"], "X-Artifact-SHA256": metadata["sha256"]}
    if format == "markdown":
        return Response(content, media_type="text/markdown", headers=headers)
    return JSONResponse(json.loads(content), headers=headers)


@router.get("/api/artifacts/{artifact_id}")
def artifact(artifact_id: UUID, request: Request) -> Response:
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
