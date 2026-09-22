from __future__ import annotations

import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routes import router
from cancerjev.config import Settings
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository


def create_app() -> FastAPI:
    settings = Settings.from_env()
    database = Database(settings.database_path)
    database.bootstrap()
    app = FastAPI(title="CancerJEV Phase 1 Read API", version="1.0.0")
    app.state.settings = settings
    app.state.repository = Repository(database)
    app.state.artifacts = ArtifactStore(settings.data_dir)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Artifact-Id", "X-Artifact-SHA256"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/health" or request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail), "request_id": request.headers.get("x-request-id", "local")}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = f"invalid request: {location}: {first.get('msg', 'invalid value')}" if location else "invalid request"
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": message, "request_id": request.headers.get("x-request-id", "local")}})

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error):
        return JSONResponse(status_code=503, content={"error": {"code": "STORAGE_UNAVAILABLE", "message": "CancerJEV storage is unavailable", "request_id": request.headers.get("x-request-id", "local")}})

    app.include_router(router)
    return app


app = create_app()
