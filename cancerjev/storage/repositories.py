from __future__ import annotations

import base64
import json
import sqlite3
from typing import Any
from uuid import uuid4

from cancerjev.domain.events import RunEvent, utc_now
from cancerjev.domain.runs import validate_run_transition
from cancerjev.storage.artifacts import PublishedArtifact
from cancerjev.storage.database import Database

EMPTY_COUNTERS = {
    "projects_attempted": 0, "projects_completed": 0, "states_generated": 0,
    "states_valid": 0, "states_selected": 0, "states_evaluated": 0,
    "candidates_promoted": 0, "hypotheses_created": 0, "followups_started": 0,
    "dossiers_created": 0, "candidates_failed": 0, "candidates_deferred": 0,
    "jev_evaluations": 0,
}
ZERO_USAGE = {
    "gdc_requests": 0, "gdc_bytes": 0, "jev_calls": 0, "llm_calls": 0,
    "jev_input_tokens": None, "jev_output_tokens": None, "jev_cost": None,
    "llm_input_tokens": None, "llm_output_tokens": None, "llm_cost": None,
}

CHILD_TABLES = {
    "candidates": "candidate_id",
    "statistical_states": "state_id",
    "jev_evaluations": "evaluation_id",
    "hypotheses": "hypothesis_id",
    "followup_executions": "execution_id",
    "dossiers": "dossier_id",
}
CHILD_FILTERS = {
    "candidates": frozenset(),
    "statistical_states": frozenset({"disposition"}),
    "jev_evaluations": frozenset({"candidate_id", "purpose"}),
    "hypotheses": frozenset({"candidate_id"}),
    "followup_executions": frozenset({"status"}),
    "dossiers": frozenset(),
}


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def create_run(self, worker_id: str) -> str:
        run_id = str(uuid4())
        with self.database.connect(write=True) as connection:
            connection.execute(
                "INSERT INTO research_runs(run_id,mode,fixture_id,fixture_version,status,created_at,worker_id,counters_json,usage_json,scope_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, "FAKE", "demo", "1", "PENDING", utc_now(), worker_id,
                 _json(EMPTY_COUNTERS), _json(ZERO_USAGE), _json({"selected_project_ids": ["SYNTHETIC-DEMO-A", "SYNTHETIC-DEMO-B"]})),
            )
        return run_id

    def append_event(
        self, run_id: str, *, event_type: str, idempotency_key: str, message: str,
        stage: str | None = None, data: dict[str, Any] | None = None,
        candidate_id: str | None = None, iteration: int | None = None,
        level: str = "info", artifact_refs: list[dict[str, Any]] | None = None,
        registrations: list[tuple[str, tuple[Any, ...]]] | None = None,
    ) -> dict[str, Any]:
        connection = self.database.connect(write=True)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT event_json FROM run_events WHERE run_id=? AND idempotency_key=?", (run_id, idempotency_key)
            ).fetchone()
            if existing:
                connection.commit()
                return json.loads(existing["event_json"])
            run = connection.execute("SELECT * FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            event = RunEvent(
                run_id=run_id, sequence=run["last_sequence"] + 1, type=event_type,
                idempotency_key=idempotency_key, message=message, stage=stage,
                data=data or {}, candidate_id=candidate_id, iteration=iteration, level=level,
                artifact_refs=artifact_refs or [],
            )
            event_json = event.checked_json()
            for statement, parameters in registrations or []:
                connection.execute(statement, parameters)
            projection = self._reduce(dict(run), event.model_dump(mode="json"))
            connection.execute(
                "INSERT INTO run_events(event_id,run_id,sequence,idempotency_key,event_json) VALUES(?,?,?,?,?)",
                (str(event.event_id), run_id, event.sequence, idempotency_key, event_json),
            )
            connection.execute(
                "UPDATE research_runs SET status=?,current_stage=?,last_sequence=?,started_at=?,ended_at=?,outcome_reason=?,coverage=?,counters_json=?,stages_json=? WHERE run_id=?",
                (projection["status"], projection["current_stage"], event.sequence,
                 projection["started_at"], projection["ended_at"], projection["outcome_reason"],
                 projection["coverage"], projection["counters_json"], projection["stages_json"], run_id),
            )
            connection.commit()
            return json.loads(event_json)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _reduce(self, run: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        target_by_type = {
            "RUN_STARTED": "RUNNING", "RUN_COMPLETED": "COMPLETED",
            "RUN_FAILED": "FAILED", "RUN_STOPPED": "STOPPED",
        }
        if event["type"] in target_by_type:
            target = target_by_type[event["type"]]
            validate_run_transition(run["status"], target)
            run["status"] = target
            if target == "RUNNING":
                run["started_at"] = event["timestamp"]
            if target in {"COMPLETED", "FAILED", "STOPPED"}:
                run["ended_at"] = event["timestamp"]
                run["current_stage"] = None
                run["outcome_reason"] = event["data"].get("reason_code")
                run["coverage"] = event["data"].get("coverage", run["coverage"])
        if event["type"] == "STAGE_STARTED":
            run["current_stage"] = event["stage"]
        stages = json.loads(run["stages_json"])
        if event["type"] in {"STAGE_STARTED", "STAGE_COMPLETED"}:
            stages.append({"stage": event["stage"], "type": event["type"], "sequence": event["sequence"], "candidate_id": event["candidate_id"], "iteration": event["iteration"]})
        run["stages_json"] = _json(stages)
        counters = json.loads(run["counters_json"])
        increments = {
            "STATISTICAL_STATE_CREATED": "states_generated", "JEV_WIDE_STATE_EVALUATED": "states_evaluated",
            "CANDIDATE_PROMOTED": "candidates_promoted", "HYPOTHESES_GENERATED": "hypotheses_created",
            "FOLLOWUP_STARTED": "followups_started", "DOSSIER_CREATED": "dossiers_created",
            "CANDIDATE_DEFERRED": "candidates_deferred", "CANDIDATE_FAILED": "candidates_failed",
            "JEV_DEEP_COMPLETED": "jev_evaluations", "HYPOTHESIS_EVALUATED": "jev_evaluations",
        }
        key = increments.get(event["type"])
        if key:
            counters[key] += event["data"].get("count", 1)
        if event["type"] == "JEV_WIDE_STATE_EVALUATED":
            counters["jev_evaluations"] += 1
        if event["type"] == "INVENTORY_COMPLETED":
            counters["projects_attempted"] = event["data"].get("projects", 0)
            counters["projects_completed"] = event["data"].get("projects", 0)
        if event["type"] == "WIDE_SCAN_COMPLETED":
            counters["states_valid"] = event["data"].get("valid_count", counters["states_valid"])
            counters["states_selected"] = event["data"].get("selected_count", counters["states_selected"])
        run["counters_json"] = _json(counters)
        return run

    def artifact_registration(self, artifact: PublishedArtifact, run_id: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO artifacts(artifact_id,run_id,relative_path,sha256,size_bytes,media_type,purpose,schema_version) VALUES(?,?,?,?,?,?,?,?)",
            (artifact.artifact_id, run_id, artifact.relative_path, artifact.sha256, artifact.size_bytes, artifact.media_type, artifact.purpose, artifact.schema_version),
        )

    def recover_interrupted(self) -> list[str]:
        with self.database.read() as connection:
            ids = [row["run_id"] for row in connection.execute("SELECT run_id FROM research_runs WHERE status IN ('PENDING','RUNNING')")]
        for run_id in ids:
            with self.database.read() as connection:
                candidates = connection.execute(
                    "SELECT candidate_id FROM candidates WHERE run_id=? AND status NOT IN ('DOSSIER_READY','TERMINATED','DEFERRED','FAILED')",
                    (run_id,),
                ).fetchall()
            for candidate in candidates:
                candidate_id = candidate["candidate_id"]
                self.append_event(
                    run_id,
                    event_type="CANDIDATE_DEFERRED",
                    idempotency_key=f"recovery:candidate:{candidate_id}",
                    message="Interrupted candidate preserved and deferred.",
                    candidate_id=candidate_id,
                    data={"terminal_state": "DEFERRED", "reason": "INTERRUPTED"},
                    level="warning",
                    registrations=[(
                        "UPDATE candidates SET status='DEFERRED',current_stage=NULL,updated_at=?,summary_json=json_set(summary_json,'$.terminal_reason','INTERRUPTED') WHERE candidate_id=?",
                        (utc_now(), candidate_id),
                    )],
                )
            self.append_event(run_id, event_type="RUN_STOPPED", idempotency_key="recovery:interrupted", message="Previous unfinished run preserved and stopped as interrupted.", data={"status": "STOPPED", "reason_code": "INTERRUPTED", "coverage": "PARTIAL"}, level="warning")
        return ids

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
            return _run(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            return [_run(row) for row in connection.execute("SELECT * FROM research_runs ORDER BY created_at DESC,run_id DESC LIMIT ?", (limit,))]

    def page_runs(self, limit: int, cursor: str | None, status: str | None) -> dict[str, Any]:
        values: list[Any] = []
        clauses: list[str] = []
        if status:
            clauses.append("status=?")
            values.append(status)
        if cursor:
            decoded = _decode_cursor(cursor)
            if decoded.get("status") != status:
                raise ValueError("cursor does not match filters")
            clauses.append("(created_at < ? OR (created_at = ? AND run_id < ?))")
            values += [decoded["created_at"], decoded["created_at"], decoded["id"]]
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit + 1)
        with self.database.read() as connection:
            rows = connection.execute(
                f"SELECT * FROM research_runs{where} ORDER BY created_at DESC,run_id DESC LIMIT ?",
                tuple(values),
            ).fetchall()
        has_more = len(rows) > limit
        items = [_run(row) for row in rows[:limit]]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = _encode_cursor({"created_at": last["created_at"], "id": last["run_id"], "status": status})
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    def page_dossiers(self, limit: int, cursor: str | None) -> dict[str, Any]:
        values: list[Any] = []
        where = ""
        if cursor:
            decoded = _decode_cursor(cursor)
            where = " WHERE (created_at < ? OR (created_at = ? AND dossier_id < ?))"
            values += [decoded["created_at"], decoded["created_at"], decoded["id"]]
        values.append(limit + 1)
        with self.database.read() as connection:
            rows = connection.execute(
                f"SELECT * FROM dossiers{where} ORDER BY created_at DESC,dossier_id DESC LIMIT ?",
                tuple(values),
            ).fetchall()
        has_more = len(rows) > limit
        items = [_decode_row(row) for row in rows[:limit]]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = _encode_cursor({"created_at": last["created_at"], "id": last["dossier_id"]})
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    def list_table(self, table: str, run_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        allowed = {"candidates", "statistical_states", "jev_evaluations", "hypotheses", "followup_executions", "dossiers"}
        if table not in allowed:
            raise ValueError("invalid table")
        clause = " WHERE run_id=?" if run_id else ""
        params: tuple[Any, ...] = (run_id, limit) if run_id else (limit,)
        with self.database.read() as connection:
            rows = connection.execute(f"SELECT * FROM {table}{clause} ORDER BY created_at ASC LIMIT ?", params).fetchall()
            return [_decode_row(row) for row in rows]

    def page_child(self, table: str, run_id: str, limit: int, cursor: str | None, filters: dict[str, str | None]) -> dict[str, Any]:
        id_column = CHILD_TABLES.get(table)
        if id_column is None:
            raise ValueError("invalid table")
        applied = {name: value for name, value in filters.items() if value is not None}
        if not set(applied) <= CHILD_FILTERS[table]:
            raise ValueError("invalid filter")
        clauses = ["run_id=?"]
        values: list[Any] = [run_id]
        for column, value in applied.items():
            clauses.append(f"{column}=?")
            values.append(value)
        if cursor:
            decoded = _decode_child_cursor(cursor)
            if decoded["table"] != table or decoded["run_id"] != run_id or decoded["filters"] != applied:
                raise ValueError("cursor does not match filters")
            clauses.append(f"(created_at > ? OR (created_at = ? AND {id_column} > ?))")
            values += [decoded["created_at"], decoded["created_at"], decoded["id"]]
        values.append(limit + 1)
        with self.database.read() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY created_at ASC,{id_column} ASC LIMIT ?",
                tuple(values),
            ).fetchall()
        has_more = len(rows) > limit
        items = [_decode_row(row) for row in rows[:limit]]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = _encode_cursor({"table": table, "run_id": run_id, "filters": applied, "created_at": last["created_at"], "id": last[id_column]})
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    def events(self, run_id: str, after: int, limit: int) -> dict[str, Any]:
        with self.database.read() as connection:
            run = connection.execute("SELECT last_sequence FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                raise KeyError(run_id)
            rows = connection.execute("SELECT event_json FROM run_events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?", (run_id, after, limit + 1)).fetchall()
        items: list[dict[str, Any]] = []
        size = 0
        for row in rows[:limit]:
            encoded = row["event_json"].encode()
            if items and size + len(encoded) > 1024 * 1024:
                break
            items.append(json.loads(row["event_json"]))
            size += len(encoded)
        next_after = items[-1]["sequence"] if items else after
        return {"items": items, "next_after_sequence": next_after, "has_more": next_after < run["last_sequence"], "run_last_sequence": run["last_sequence"]}

    def artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
            return dict(row) if row else None

    def heartbeat(self, owner_id: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute("INSERT INTO worker_status(singleton,owner_id,heartbeat_at,version) VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET owner_id=excluded.owner_id,heartbeat_at=excluded.heartbeat_at,version=excluded.version", (owner_id, utc_now(), "0.1.0"))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key, value in list(result.items()):
        if key.endswith("_json"):
            result[key.removesuffix("_json")] = json.loads(value)
            del result[key]
    return result


def _run(row: sqlite3.Row) -> dict[str, Any]:
    result = _decode_row(row)
    result["counts"] = result.pop("counters")
    result["provider_usage"] = result.pop("usage")
    result["stage_occurrences"] = result.pop("stages")
    result.update(result.pop("scope"))
    return result


def _encode_cursor(value: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(_json(value).encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> dict[str, Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(decoded, dict) or "created_at" not in decoded or "id" not in decoded:
            raise ValueError
        return decoded
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor") from exc


def _decode_child_cursor(value: str) -> dict[str, Any]:
    decoded = _decode_cursor(value)
    if not isinstance(decoded.get("filters"), dict) or "table" not in decoded or "run_id" not in decoded:
        raise ValueError("invalid cursor")
    return decoded
