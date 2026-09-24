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
    "followups_completed": 0, "followups_failed": 0, "evidence_revisions": 0,
    "dossiers_created": 0, "candidates_failed": 0, "candidates_deferred": 0,
    "jev_evaluations": 0,
}
ZERO_USAGE = {
    "gdc_requests": 0, "gdc_bytes": 0, "gdc_cache_hits": 0, "jev_calls": 0, "llm_calls": 0,
    "jev_input_tokens": None, "jev_output_tokens": None, "jev_cost": None,
    "llm_input_tokens": None, "llm_output_tokens": None, "llm_cost": None,
}

CHILD_TABLES = {
    "candidates": "candidate_id",
    "statistical_states": "state_id",
    "jev_evaluations": "evaluation_id",
    "jev_projections": "projection_id",
    "hypotheses": "hypothesis_id",
    "followup_executions": "execution_id",
    "evidence_states": "evidence_state_id",
    "dossiers": "dossier_id",
}
CHILD_FILTERS = {
    "candidates": frozenset(),
    "statistical_states": frozenset({"disposition"}),
    "jev_evaluations": frozenset({"candidate_id", "purpose"}),
    "jev_projections": frozenset(),
    "hypotheses": frozenset({"candidate_id"}),
    "followup_executions": frozenset({"status", "candidate_id"}),
    "evidence_states": frozenset({"candidate_id"}),
    "dossiers": frozenset(),
}


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def create_run(self, worker_id: str, *, mode: str = "FAKE", fixture_id: str | None = "demo",
                   fixture_version: str | None = "1", scope: dict[str, Any] | None = None) -> str:
        run_id = str(uuid4())
        default_scope = (
            {"selected_project_ids": ["SYNTHETIC-DEMO-A", "SYNTHETIC-DEMO-B"]}
            if mode == "FAKE" else {"selected_project_ids": []}
        )
        effective_scope = dict(scope) if scope is not None else default_scope
        effective_scope.setdefault("selected_project_ids", [])
        with self.database.connect(write=True) as connection:
            connection.execute(
                "INSERT INTO research_runs(run_id,mode,fixture_id,fixture_version,status,created_at,worker_id,counters_json,usage_json,scope_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, mode, fixture_id, fixture_version, "PENDING", utc_now(), worker_id,
                 _json(EMPTY_COUNTERS), _json(ZERO_USAGE), _json(effective_scope)),
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
                "UPDATE research_runs SET status=?,current_stage=?,last_sequence=?,started_at=?,ended_at=?,outcome_reason=?,coverage=?,counters_json=?,stages_json=?,usage_json=?,scope_json=? WHERE run_id=?",
                (projection["status"], projection["current_stage"], event.sequence,
                 projection["started_at"], projection["ended_at"], projection["outcome_reason"],
                 projection["coverage"], projection["counters_json"], projection["stages_json"],
                 projection["usage_json"], projection["scope_json"], run_id),
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
            "STATISTICAL_STATE_CREATED": "states_generated",
            "JEV_WIDE_STATE_EVALUATED": "states_evaluated",
            "CANDIDATE_PROMOTED": "candidates_promoted", "HYPOTHESES_GENERATED": "hypotheses_created",
            "FOLLOWUP_STARTED": "followups_started", "DOSSIER_CREATED": "dossiers_created",
            "FOLLOWUP_COMPLETED": "followups_completed", "FOLLOWUP_FAILED": "followups_failed",
            "EVIDENCE_STATE_CREATED": "evidence_revisions",
            "CANDIDATE_DEFERRED": "candidates_deferred", "CANDIDATE_FAILED": "candidates_failed",
            "JEV_DEEP_COMPLETED": "jev_evaluations", "HYPOTHESIS_EVALUATED": "jev_evaluations",
            "JEV_EVALUATION_FAILED": "jev_evaluations",
            "JEV_DEEP_EVIDENCE_JUDGED": "jev_evaluations",
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
        usage = json.loads(run["usage_json"])
        if event["type"] == "GDC_REQUEST_COMPLETED":
            usage["gdc_requests"] += 1
            usage["gdc_bytes"] += int(event["data"].get("bytes_read", 0))
        elif event["type"] == "GDC_CACHE_HIT":
            usage["gdc_cache_hits"] += 1
        elif event["type"] in {"JEV_WIDE_STATE_EVALUATED", "JEV_DEEP_COMPLETED",
                               "JEV_DEEP_EVIDENCE_JUDGED", "JEV_EVALUATION_FAILED",
                               "HYPOTHESIS_EVALUATED"}:
            data = event["data"]
            if data.get("provider_attempted") is True and not data.get("cache"):
                usage["jev_calls"] += 1
                provider_usage = data.get("usage") or {}
                for token_key in ("input_tokens", "output_tokens"):
                    value = provider_usage.get(token_key)
                    if value is not None:
                        target = f"jev_{token_key}"
                        usage[target] = (usage[target] or 0) + int(value)
        if event["type"] == "HYPOTHESES_GENERATED" and event["data"].get("provider_attempted") is True:
            usage["llm_calls"] += 1
            llm_usage = event["data"].get("usage") or {}
            for token_key in ("input_tokens", "output_tokens"):
                value = llm_usage.get(token_key)
                if value is not None:
                    target = f"llm_{token_key}"
                    usage[target] = (usage[target] or 0) + int(value)
        run["usage_json"] = _json(usage)
        if event["type"] == "PROJECT_SCOPE_SELECTED":
            scope = json.loads(run["scope_json"])
            scope["selected_project_ids"] = event["data"].get("selected_project_ids", [])
            if event["data"].get("scope_hash"):
                scope["scope_hash"] = event["data"]["scope_hash"]
            if event["data"].get("gdc_release"):
                scope["gdc_release"] = event["data"]["gdc_release"]
            run["scope_json"] = _json(scope)
        return run

    def artifact_registration(self, artifact: PublishedArtifact, run_id: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO artifacts(artifact_id,run_id,relative_path,sha256,size_bytes,media_type,purpose,schema_version) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(artifact_id) DO NOTHING",
            (artifact.artifact_id, run_id, artifact.relative_path, artifact.sha256, artifact.size_bytes, artifact.media_type, artifact.purpose, artifact.schema_version),
        )

    def register_artifact(self, artifact: PublishedArtifact, run_id: str) -> None:
        """Register an operational artifact outside the event transaction.

        Used by the GDC transport so a published response is referenceable by
        the attempt ledger and cache even if the emitting callback is a no-op.
        """
        statement, parameters = self.artifact_registration(artifact, run_id)
        with self.database.connect(write=True) as connection:
            connection.execute(statement, parameters)

    # ------------------------------------------------------- GDC operational ledger

    def gdc_attempt_start(self, *, request_id: str, run_id: str, logical_query_id: str, attempt_no: int,
                          method: str, endpoint: str, request_hash: str, reserved_bytes: int,
                          started_at: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute(
                "INSERT INTO gdc_attempts(request_id,run_id,logical_query_id,attempt_no,method,endpoint,request_hash,status,reserved_bytes,bytes_read,started_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (request_id, run_id, logical_query_id, attempt_no, method, endpoint, request_hash,
                 "RESERVED", reserved_bytes, 0, started_at),
            )

    def gdc_attempt_finish(self, *, request_id: str, status: str, bytes_read: int, http_status: int | None,
                           response_artifact_id: str | None, response_hash: str | None,
                           completeness: str | None, error: str | None, finished_at: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute(
                "UPDATE gdc_attempts SET status=?,bytes_read=?,http_status=?,response_artifact_id=?,response_hash=?,completeness=?,error=?,finished_at=? WHERE request_id=?",
                (status, bytes_read, http_status, response_artifact_id, response_hash,
                 completeness, error, finished_at, request_id),
            )

    def gdc_cache_get(self, request_hash: str, contract_version: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT * FROM gdc_cache WHERE cache_key=?", (gdc_cache_key(request_hash, contract_version),),
            ).fetchone()
            return dict(row) if row else None

    def gdc_cache_put(self, *, request_hash: str, method: str, endpoint: str, response_artifact_id: str,
                      response_hash: str, size_bytes: int, completeness: str, contract_version: str,
                      created_at: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute(
                "INSERT INTO gdc_cache(cache_key,request_hash,method,endpoint,response_artifact_id,response_hash,size_bytes,completeness,contract_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cache_key) DO NOTHING",
                (gdc_cache_key(request_hash, contract_version), request_hash, method, endpoint,
                 response_artifact_id, response_hash, size_bytes, completeness, contract_version,
                 created_at),
            )

    def gdc_attempts(self, run_id: str) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT * FROM gdc_attempts WHERE run_id=? ORDER BY started_at ASC,request_id ASC",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def ranking_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE run_id=? AND purpose='wide-ranking' ORDER BY artifact_id",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def gdc_run_totals(self, run_id: str) -> dict[str, int]:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS attempts, COALESCE(SUM(bytes_read),0) AS bytes, "
                "COALESCE(SUM(CASE WHEN status='CACHE_HIT' THEN 1 ELSE 0 END),0) AS cache_hits "
                "FROM gdc_attempts WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return {"attempts": row["attempts"], "bytes": row["bytes"], "cache_hits": row["cache_hits"]}

    # ------------------------------------------------------- Jev projections and cache

    def projection_registration(self, *, projection_id: str, run_id: str, state_id: str,
                                projection_version: str, source_state_hash: str, projection_hash: str,
                                artifact_id: str, fields_json: str, created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO jev_projections(projection_id,run_id,state_id,projection_version,source_state_hash,projection_hash,artifact_id,fields_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (projection_id, run_id, state_id, projection_version, source_state_hash,
             projection_hash, artifact_id, fields_json, created_at),
        )

    def find_projection(self, state_id: str, projection_version: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT * FROM jev_projections WHERE state_id=? AND projection_version=?",
                (state_id, projection_version),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------- deterministic deep slice

    def evidence_revisions(self, candidate_id: str) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_states WHERE candidate_id=? ORDER BY iteration ASC,created_at ASC",
                (candidate_id,),
            ).fetchall()
        return [_decode_row(row) for row in rows]

    def get_evidence_state(self, evidence_state_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT * FROM evidence_states WHERE evidence_state_id=?", (evidence_state_id,),
            ).fetchone()
        return _decode_row(row) if row else None

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id=?", (hypothesis_id,),
            ).fetchone()
        return _decode_row(row) if row else None

    def get_dossier(self, dossier_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute(
                "SELECT * FROM dossiers WHERE dossier_id=?", (dossier_id,),
            ).fetchone()
        return _decode_row(row) if row else None

    def followup_executions_for(self, candidate_id: str) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT * FROM followup_executions WHERE candidate_id=? ORDER BY created_at ASC,execution_id ASC",
                (candidate_id,),
            ).fetchall()
        return [_decode_row(row) for row in rows]

    def state_registration(self, *, state_id: str, run_id: str, state_hash: str, artifact_id: str,
                           disposition: str, summary_json: str,
                           created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO statistical_states(state_id,run_id,state_hash,artifact_id,disposition,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (state_id, run_id, state_hash, artifact_id, disposition, summary_json, created_at),
        )

    def candidate_registration(self, *, candidate_id: str, run_id: str, promotion_slot: int, status: str,
                               current_stage: str | None, source_state_id: str, entity_json: str,
                               summary_json: str, created_at: str,
                               updated_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO candidates(candidate_id,run_id,promotion_slot,status,current_stage,source_state_id,entity_json,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (candidate_id, run_id, promotion_slot, status, current_stage, source_state_id,
             entity_json, summary_json, created_at, updated_at),
        )

    def candidate_status_registration(self, *, candidate_id: str, status: str, current_stage: str | None,
                                      updated_at: str, latest_evidence_state_id: str | None = None,
                                      dossier_id: str | None = None) -> tuple[str, tuple[Any, ...]]:
        assignments = ["status=?", "current_stage=?", "updated_at=?"]
        values: list[Any] = [status, current_stage, updated_at]
        if latest_evidence_state_id is not None:
            assignments.append("latest_evidence_state_id=?")
            values.append(latest_evidence_state_id)
        if dossier_id is not None:
            assignments.append("dossier_id=?")
            values.append(dossier_id)
        values.append(candidate_id)
        return (
            f"UPDATE candidates SET {', '.join(assignments)} WHERE candidate_id=?",
            tuple(values),
        )

    def candidate_deferred_registration(self, *, candidate_id: str, reason: str,
                                        updated_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "UPDATE candidates SET status='DEFERRED',current_stage=NULL,updated_at=?,summary_json=json_set(summary_json,'$.terminal_reason',?) WHERE candidate_id=?",
            (updated_at, reason, candidate_id),
        )

    def evidence_state_registration(self, *, evidence_state_id: str, run_id: str, candidate_id: str,
                                    previous_evidence_state_id: str | None, iteration: int,
                                    evidence_hash: str, artifact_id: str, summary_json: str,
                                    created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO evidence_states(evidence_state_id,run_id,candidate_id,previous_evidence_state_id,iteration,evidence_hash,artifact_id,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (evidence_state_id, run_id, candidate_id, previous_evidence_state_id, iteration,
             evidence_hash, artifact_id, summary_json, created_at),
        )

    def hypothesis_registration(self, *, hypothesis_id: str, run_id: str, candidate_id: str,
                                evidence_state_id: str, artifact_id: str, hypothesis_json: str,
                                created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO hypotheses(hypothesis_id,run_id,candidate_id,evidence_state_id,artifact_id,hypothesis_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (hypothesis_id, run_id, candidate_id, evidence_state_id, artifact_id, hypothesis_json,
             created_at),
        )

    def followup_execution_registration(self, *, execution_id: str, run_id: str, candidate_id: str,
                                        action_id: str, action_version: str, input_evidence_hash: str,
                                        output_evidence_state_id: str | None, slot: int, status: str,
                                        summary_json: str,
                                        created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO followup_executions(execution_id,run_id,candidate_id,action_id,action_version,input_evidence_hash,output_evidence_state_id,slot,status,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (execution_id, run_id, candidate_id, action_id, action_version, input_evidence_hash,
             output_evidence_state_id, slot, status, summary_json, created_at),
        )

    def dossier_registration(self, *, dossier_id: str, run_id: str, candidate_id: str,
                             json_artifact_id: str, markdown_artifact_id: str, summary_json: str,
                             created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO dossiers(dossier_id,run_id,candidate_id,json_artifact_id,markdown_artifact_id,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (dossier_id, run_id, candidate_id, json_artifact_id, markdown_artifact_id, summary_json,
             created_at),
        )

    def jev_evaluation_registration(self, *, evaluation_id: str, run_id: str, candidate_id: str | None,
                                    input_ref_kind: str, input_ref_id: str, purpose: str,
                                    artifact_id: str, vector_json: str, model: str,
                                    created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO jev_evaluations(evaluation_id,run_id,candidate_id,input_ref_kind,input_ref_id,purpose,artifact_id,vector_json,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (evaluation_id, run_id, candidate_id, input_ref_kind, input_ref_id, purpose, artifact_id,
             vector_json, model, created_at),
        )

    def jev_cache_registration(self, cache_key: str, evaluation_id: str,
                               created_at: str) -> tuple[str, tuple[Any, ...]]:
        return (
            "INSERT INTO jev_cache(cache_key,evaluation_id,created_at) VALUES(?,?,?) ON CONFLICT(cache_key) DO NOTHING",
            (cache_key, evaluation_id, created_at),
        )

    def jev_cache_get(self, cache_key: str) -> str | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT evaluation_id FROM jev_cache WHERE cache_key=?", (cache_key,)).fetchone()
        return row["evaluation_id"] if row else None

    def jev_cache_put(self, cache_key: str, evaluation_id: str, created_at: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute(
                "INSERT INTO jev_cache(cache_key,evaluation_id,created_at) VALUES(?,?,?) ON CONFLICT(cache_key) DO NOTHING",
                (cache_key, evaluation_id, created_at),
            )

    def get_evaluation(self, evaluation_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM jev_evaluations WHERE evaluation_id=?", (evaluation_id,)).fetchone()
        return _decode_row(row) if row else None

    def get_state(self, state_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM statistical_states WHERE state_id=?", (state_id,)).fetchone()
            return _decode_row(row) if row else None

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            return _decode_row(row) if row else None

    def page_projections(self, run_id: str, limit: int, cursor: str | None) -> dict[str, Any]:
        return self.page_child("jev_projections", run_id, limit, cursor, {})

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
                    registrations=[self.candidate_deferred_registration(
                        candidate_id=candidate_id, reason="INTERRUPTED", updated_at=utc_now(),
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
        allowed = {"candidates", "statistical_states", "jev_evaluations", "hypotheses", "followup_executions",
                   "evidence_states", "dossiers"}
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

    def artifact_at_path(self, relative_path: str) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE relative_path=?", (relative_path,)).fetchone()
            return dict(row) if row else None

    def heartbeat(self, owner_id: str) -> None:
        with self.database.connect(write=True) as connection:
            connection.execute("INSERT INTO worker_status(singleton,owner_id,heartbeat_at,version) VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET owner_id=excluded.owner_id,heartbeat_at=excluded.heartbeat_at,version=excluded.version", (owner_id, utc_now(), "0.1.0"))


def gdc_cache_key(request_hash: str, contract_version: str) -> str:
    """Cache identity is the canonical request hash qualified by the transport contract.

    An entry written under an older contract version stays immutable and readable but
    can never block storing the current contract's entry for the same request.
    """
    return f"{contract_version}:{request_hash}"


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
