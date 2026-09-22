from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4, uuid5

from cancerjev.config import Settings
from cancerjev.domain.dossier import DOSSIER_SECTIONS
from cancerjev.domain.events import canonical_json, utc_now
from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.dossier.renderer import WARNING, render_markdown
from cancerjev.research.fixtures import (
    evidence,
    hypotheses,
    judgment_vector,
    statistical_states,
)
from cancerjev.research.policy import PROMOTED_STATE_INDEXES, PROMOTION_POLICY_VERSION
from cancerjev.storage.artifacts import ArtifactStore, PublishedArtifact
from cancerjev.storage.repositories import Repository, _json


@dataclass
class DemoOrchestrator:
    settings: Settings
    repository: Repository
    artifacts: ArtifactStore
    emit: Callable[[dict[str, Any]], None]
    worker_id: str = field(default_factory=lambda: str(uuid4()))

    def run(self, *, stop_requested: Callable[[], bool] = lambda: False) -> str:
        worker_id = self.worker_id
        self.repository.heartbeat(worker_id)
        run_id = self.repository.create_run(worker_id)
        def make_id(name: str) -> str:
            return str(uuid5(UUID(run_id), name))
        try:
            self._event(run_id, "RUN_CREATED", "run:created", "Created FAKE SYNTHETIC fixture run.", data={"status": "PENDING", "fixture_id": "demo", "config_ref": "inline-phase1-fixture"})
            self._event(run_id, "RUN_STARTED", "run:started", "Started offline fixture research run.", data={"status": "RUNNING"})
            states: list[dict[str, Any]] = []
            self._stage(run_id, "INVENTORY", lambda: self._event(run_id, "INVENTORY_COMPLETED", "inventory:complete", "Synthetic inventory ready: 2 simulated projects.", stage="INVENTORY", data={"projects": 2, "selected_project_ids": ["SYNTHETIC-DEMO-A", "SYNTHETIC-DEMO-B"], "completeness": "COMPLETE_FOR_FIXTURE"}))
            self._stage(run_id, "GDC_FAST_SEARCH", lambda: self._event(run_id, "WIDE_SCAN_STARTED", "fast-search:synthetic", "FAKE search generated locally; GDC requests remain zero.", stage="GDC_FAST_SEARCH", data={"external_requests": 0, "fixture": True}))
            def generate_states():
                for index, state in enumerate(statistical_states(run_id, make_id)):
                    state_hash = content_hash(statistical_state_identity_payload(state))
                    state["state_hash"] = state_hash
                    artifact = self._publish_json(run_id, f"statistical_states/{state['state_id']}.json", state, "statistical-state")
                    disposition = "PROMOTED" if index in PROMOTED_STATE_INDEXES else "NOT_SELECTED"
                    registrations = [self.repository.artifact_registration(artifact, run_id), (
                        "INSERT INTO statistical_states(state_id,run_id,state_hash,artifact_id,disposition,summary_json,created_at) VALUES(?,?,?,?,?,?,?)",
                        (state["state_id"], run_id, state_hash, artifact.artifact_id, disposition, _json({"entity": state["entity"], "pattern": state["pattern"], "availability": "OBSERVED", "fixture": True}), utc_now()),
                    )]
                    self._event(run_id, "STATISTICAL_STATE_CREATED", f"state:{index}", f"Created synthetic StatisticalState for {state['entity']['gene_symbol']}.", stage="STATE_GENERATION", data={"state_id": state["state_id"], "shape": state["pattern"]["shape"], "fixture": True}, artifact_refs=[artifact.ref()], registrations=registrations)
                    states.append(state)
                self._event(run_id, "WIDE_SCAN_COMPLETED", "states:summary", "Generated 12 synthetic StatisticalStates.", stage="STATE_GENERATION", data={"valid_count": 12, "selected_count": 2})
            self._stage(run_id, "STATE_GENERATION", generate_states)
            candidates: list[dict[str, Any]] = []
            def wide():
                for index, state in enumerate(states):
                    chosen = "PROMOTE" if index in PROMOTED_STATE_INDEXES else "DEFER"
                    vector = judgment_vector("wide_pattern_route", chosen, 0.88 if index == 0 else 0.74 if index == 3 else 0.3, 4 if index == 0 else 3 if index == 3 else 1)
                    evaluation_id = make_id(f"wide-eval:{index}")
                    evaluation = {"evaluation_id": evaluation_id, "purpose": "WIDE", "input_ref_kind": "STATISTICAL_STATE", "input_ref_id": state["state_id"], "mode": "FAKE", "model": "fixture-jev-wide-v1", "questions": vector}
                    artifact = self._publish_json(run_id, f"jev/{evaluation_id}.json", evaluation, "jev-evaluation")
                    regs = [self.repository.artifact_registration(artifact, run_id), ("INSERT INTO jev_evaluations(evaluation_id,run_id,candidate_id,input_ref_kind,input_ref_id,purpose,artifact_id,vector_json,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (evaluation_id, run_id, None, "STATISTICAL_STATE", state["state_id"], "WIDE", artifact.artifact_id, _json(vector), "fixture-jev-wide-v1", utc_now()))]
                    self._event(run_id, "JEV_WIDE_STATE_EVALUATED", f"wide:{index}", f"Fixture Jev-shaped wide judgment for {state['entity']['gene_symbol']}.", stage="JEV_WIDE", data={"evaluation_id": evaluation_id, "state_id": state["state_id"], "judgment_vector": vector, "external_calls": 0}, artifact_refs=[artifact.ref()], registrations=regs)
                    if index in PROMOTED_STATE_INDEXES:
                        slot = len(candidates) + 1
                        candidate_id = make_id(f"candidate:{index}")
                        now = utc_now()
                        candidate = {"candidate_id": candidate_id, "run_id": run_id, "promotion_slot": slot, "source_state_id": state["state_id"], "entity": state["entity"], "status": "WIDE_EVALUATED"}
                        regs = [("INSERT INTO candidates(candidate_id,run_id,promotion_slot,status,current_stage,source_state_id,entity_json,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (candidate_id, run_id, slot, "WIDE_EVALUATED", "JEV_WIDE", state["state_id"], _json(state["entity"]), _json({"promotion_reason": state["pattern"]["description"], "wide_evaluation_id": evaluation_id}), now, now))]
                        self._event(run_id, "CANDIDATE_PROMOTED", f"candidate:{slot}:promoted", f"Promoted synthetic candidate {state['entity']['gene_symbol']} into slot {slot}.", stage="JEV_WIDE", candidate_id=candidate_id, data={"candidate_id": candidate_id, "source_state_id": state["state_id"], "evaluation_id": evaluation_id, "promotion_slot": slot, "policy_version": PROMOTION_POLICY_VERSION, "reason": state["pattern"]["description"]}, registrations=regs)
                        candidate["state"] = state
                        candidates.append(candidate)
            self._stage(run_id, "JEV_WIDE", wide)
            if stop_requested():
                return self._stop(run_id)
            primary, deferred = candidates
            baseline: dict[str, Any] = {}
            def deep():
                nonlocal baseline
                baseline = evidence(run_id, primary["candidate_id"], primary["state"], make_id)
                self._record_evidence(run_id, primary, baseline, "baseline", "Created immutable baseline fixture evidence.")
                regs = [("UPDATE candidates SET status='DEFERRED',current_stage=NULL,updated_at=?,summary_json=json_set(summary_json,'$.terminal_reason','FRAGILE_SYNTHETIC_PATTERN') WHERE candidate_id=?", (utc_now(), deferred["candidate_id"]))]
                self._event(run_id, "CANDIDATE_DEFERRED", "candidate:2:deferred", "Deferred second synthetic candidate after fragility branch.", stage="DEEP_ANALYSIS", candidate_id=deferred["candidate_id"], data={"terminal_state": "DEFERRED", "reason": "FRAGILE_SYNTHETIC_PATTERN"}, registrations=regs)
            self._stage(run_id, "DEEP_ANALYSIS", deep, candidate_id=primary["candidate_id"])
            self._stage(run_id, "EVIDENCE_BUILD", lambda: self._event(run_id, "EVIDENCE_BUILD_COMPLETED", "evidence:baseline:built", "Baseline deterministic fixture evidence available.", stage="EVIDENCE_BUILD", candidate_id=primary["candidate_id"], data={"evidence_state_id": baseline["evidence_state_id"], "availability": "OBSERVED"}), candidate_id=primary["candidate_id"])
            deep_vector = judgment_vector("deep_route", "FOLLOW_UP", 0.82, 3)
            def deep_jev():
                evaluation_id = make_id("deep-eval:baseline")
                answers = {"questions": [{"question": "Is the pattern coherent?", "primitive": "Noul", "answer": deep_vector["noul"], "applicability": "APPLICABLE"}, {"question": "Which route best resolves fragility?", "primitive": "Choice", "answer": deep_vector["choice"], "applicability": "APPLICABLE"}, {"question": "How useful is follow-up?", "primitive": "Score", "answer": deep_vector["score"], "applicability": "APPLICABLE"}]}
                self._record_evaluation(run_id, primary["candidate_id"], evaluation_id, "EVIDENCE_STATE", baseline["evidence_state_id"], "DEEP", answers, "deep:baseline")
            self._stage(run_id, "JEV_DEEP", deep_jev, candidate_id=primary["candidate_id"])
            fixture_hypotheses = hypotheses(primary["candidate_id"], baseline["evidence_state_id"], make_id)
            def make_hypotheses():
                regs = []
                refs = []
                for item in fixture_hypotheses:
                    artifact = self._publish_json(run_id, f"hypotheses/{item['hypothesis_id']}.json", item, "fixture-hypothesis")
                    regs += [self.repository.artifact_registration(artifact, run_id), ("INSERT INTO hypotheses(hypothesis_id,run_id,candidate_id,evidence_state_id,artifact_id,hypothesis_json,created_at) VALUES(?,?,?,?,?,?,?)", (item["hypothesis_id"], run_id, primary["candidate_id"], baseline["evidence_state_id"], artifact.artifact_id, _json(item), utc_now()))]
                    refs.append(artifact.ref())
                regs.append(("UPDATE candidates SET status='HYPOTHESIZED',current_stage='HYPOTHESIS_GENERATION',updated_at=? WHERE candidate_id=?", (utc_now(), primary["candidate_id"])))
                self._event(run_id, "HYPOTHESES_GENERATED", "hypotheses:generated", "Generated 2 competing GENERATED FIXTURE HYPOTHESES without an LLM.", stage="HYPOTHESIS_GENERATION", candidate_id=primary["candidate_id"], data={"count": 2, "hypothesis_ids": [h["hypothesis_id"] for h in fixture_hypotheses], "external_calls": 0}, artifact_refs=refs, registrations=regs)
            self._stage(run_id, "HYPOTHESIS_GENERATION", make_hypotheses, candidate_id=primary["candidate_id"])
            def verify():
                for index, hypothesis in enumerate(fixture_hypotheses):
                    vector = {"support": round(0.72 - index * 0.17, 2), "contradiction": round(0.21 + index * 0.18, 2), "exceeds_evidence": 0.61, "discriminability": 0.86, "registered_test_exists": True, "unavailable_dependency": False, **judgment_vector("hypothesis_testability", "TESTABLE", 0.78, 3)}
                    evaluation_id = make_id(f"hypothesis-eval:{index}")
                    item = {"evaluation_id": evaluation_id, "candidate_id": primary["candidate_id"], "hypothesis_id": hypothesis["hypothesis_id"], "purpose": "HYPOTHESIS", "input_ref_kind": "HYPOTHESIS", "input_ref_id": hypothesis["hypothesis_id"], "mode": "FAKE", "model": "fixture-jev-hypothesis-v1", "answer_vector": vector, "external_calls": 0}
                    artifact = self._publish_json(run_id, f"jev/{evaluation_id}.json", item, "jev-evaluation")
                    regs = [self.repository.artifact_registration(artifact, run_id), ("INSERT INTO jev_evaluations(evaluation_id,run_id,candidate_id,input_ref_kind,input_ref_id,purpose,artifact_id,vector_json,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (evaluation_id, run_id, primary["candidate_id"], "HYPOTHESIS", hypothesis["hypothesis_id"], "HYPOTHESIS", artifact.artifact_id, _json(vector), "fixture-jev-hypothesis-v1", utc_now()))]
                    self._event(run_id, "HYPOTHESIS_EVALUATED", f"hypothesis:{index}:evaluated", f"Independently evaluated fixture hypothesis {index + 1}.", stage="HYPOTHESIS_VERIFICATION", candidate_id=primary["candidate_id"], data={"evaluation_id": evaluation_id, "hypothesis_id": hypothesis["hypothesis_id"], "judgment_vector": vector, "external_calls": 0}, artifact_refs=[artifact.ref()], registrations=regs)
            self._stage(run_id, "HYPOTHESIS_VERIFICATION", verify, candidate_id=primary["candidate_id"])
            followup_evidence: dict[str, Any] = {}
            def followup():
                nonlocal followup_evidence
                execution_id = make_id("followup:1")
                action_id = "DROP_INFLUENTIAL_FIXTURE_POINTS_V1"
                self._event(run_id, "FOLLOWUP_STARTED", "followup:started", "Started registered deterministic fixture follow-up.", stage="FOLLOWUP", candidate_id=primary["candidate_id"], iteration=1, data={"action_id": action_id, "version": "1", "execution_id": execution_id, "slot": 1, "input_hash": baseline["evidence_hash"]})
                followup_evidence = evidence(run_id, primary["candidate_id"], primary["state"], make_id, followup=True, previous=baseline["evidence_state_id"])
                self._record_evidence(run_id, primary, followup_evidence, "followup", "Follow-up created a NEW immutable EvidenceState.", iteration=1)
                regs = [("INSERT INTO followup_executions(execution_id,run_id,candidate_id,action_id,action_version,input_evidence_hash,output_evidence_state_id,slot,status,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (execution_id, run_id, primary["candidate_id"], action_id, "1", baseline["evidence_hash"], followup_evidence["evidence_state_id"], 1, "COMPLETED", _json({"before": 0.88, "after": 0.61, "fixture": True}), utc_now()))]
                self._event(run_id, "FOLLOWUP_COMPLETED", "followup:completed", "Fixture follow-up changed the descriptive value from 0.88 to 0.61; baseline remains unchanged.", stage="FOLLOWUP", candidate_id=primary["candidate_id"], iteration=1, data={"action_id": action_id, "execution_id": execution_id, "input_evidence_state_id": baseline["evidence_state_id"], "output_evidence_state_id": followup_evidence["evidence_state_id"], "outcome": "WEAKENED", "before": 0.88, "after": 0.61}, registrations=regs)
            self._stage(run_id, "FOLLOWUP", followup, candidate_id=primary["candidate_id"])
            self._stage(run_id, "EVIDENCE_BUILD", lambda: self._event(run_id, "EVIDENCE_BUILD_COMPLETED", "evidence:followup:built", "New post-follow-up evidence revision available.", stage="EVIDENCE_BUILD", candidate_id=primary["candidate_id"], iteration=1, data={"evidence_state_id": followup_evidence["evidence_state_id"], "previous_evidence_state_id": baseline["evidence_state_id"]}), candidate_id=primary["candidate_id"], iteration=1)
            self._stage(run_id, "JEV_DEEP", lambda: self._record_evaluation(run_id, primary["candidate_id"], make_id("deep-eval:followup"), "EVIDENCE_STATE", followup_evidence["evidence_state_id"], "DEEP", {"questions": [{"question": "Did fixture follow-up weaken the lead?", "primitive": "Choice", "answer": judgment_vector("followup_outcome", "WEAKENED", 0.84, 2)["choice"], "applicability": "APPLICABLE"}]}, "deep:followup"), candidate_id=primary["candidate_id"], iteration=1)
            self._stage(run_id, "DOSSIER", lambda: self._make_dossier(run_id, primary, baseline, followup_evidence, fixture_hypotheses, make_id), candidate_id=primary["candidate_id"])
            self._event(run_id, "RUN_COMPLETED", "run:completed", "FAKE SYNTHETIC fixture run completed with one dossier and one deferred candidate.", data={"status": "COMPLETED", "coverage": "COMPLETE_FOR_SCOPE", "external_provider_calls": {"gdc": 0, "jev": 0, "llm": 0}})
            return run_id
        except KeyboardInterrupt:
            self._stop(run_id)
            raise
        except Exception as exc:
            self._event(run_id, "RUN_FAILED", "run:failed", "Fixture run failed.", data={"status": "FAILED", "reason_code": type(exc).__name__}, level="error")
            raise

    def _stage(self, run_id: str, stage: str, action, *, candidate_id: str | None = None, iteration: int | None = None):
        start = time.monotonic()
        key = f"stage:{stage}:{candidate_id or 'run'}:{iteration or 0}"
        self._event(run_id, "STAGE_STARTED", f"{key}:started", f"{stage} started.", stage=stage, candidate_id=candidate_id, iteration=iteration, data={"stage": stage, "outcome": "STARTED"})
        self._delay()
        action()
        self._event(run_id, "STAGE_COMPLETED", f"{key}:completed", f"{stage} completed.", stage=stage, candidate_id=candidate_id, iteration=iteration, data={"stage": stage, "outcome": "COMPLETED", "elapsed_ms": int((time.monotonic() - start) * 1000)})

    def _record_evidence(self, run_id, candidate, item, suffix, message, iteration=0):
        item["evidence_hash"] = content_hash(evidence_state_identity_payload(item))
        artifact = self._publish_json(run_id, f"evidence/{item['evidence_state_id']}.json", item, "evidence-state")
        regs = [self.repository.artifact_registration(artifact, run_id), ("INSERT INTO evidence_states(evidence_state_id,run_id,candidate_id,previous_evidence_state_id,iteration,evidence_hash,artifact_id,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (item["evidence_state_id"], run_id, candidate["candidate_id"], item.get("previous_evidence_state_id"), iteration, item["evidence_hash"], artifact.artifact_id, _json({"entity": item["entity"], "observation": item["deterministic_observations"][0], "fixture": True}), utc_now())), ("UPDATE candidates SET status='DEEP_ANALYZED',current_stage='EVIDENCE_BUILD',latest_evidence_state_id=?,updated_at=? WHERE candidate_id=?", (item["evidence_state_id"], utc_now(), candidate["candidate_id"]))]
        self._event(run_id, "EVIDENCE_STATE_CREATED", f"evidence:{suffix}:created", message, stage="EVIDENCE_BUILD", candidate_id=candidate["candidate_id"], iteration=iteration, data={"evidence_state_id": item["evidence_state_id"], "previous_evidence_state_id": item.get("previous_evidence_state_id"), "availability": "OBSERVED", "n": item["deterministic_observations"][0]["n_effective"], "effect_like_value": item["deterministic_observations"][0]["effect"]["value"], "synthetic": True}, artifact_refs=[artifact.ref()], registrations=regs)

    def _record_evaluation(self, run_id, candidate_id, evaluation_id, input_ref_kind, input_ref_id, purpose, vector, key):
        item = {"evaluation_id": evaluation_id, "candidate_id": candidate_id, "input_ref_kind": input_ref_kind, "input_ref_id": input_ref_id, "purpose": purpose, "mode": "FAKE", "model": "fixture-jev-deep-v1", "answer_vector": vector, "external_calls": 0}
        artifact = self._publish_json(run_id, f"jev/{evaluation_id}.json", item, "jev-evaluation")
        regs = [self.repository.artifact_registration(artifact, run_id), ("INSERT INTO jev_evaluations(evaluation_id,run_id,candidate_id,input_ref_kind,input_ref_id,purpose,artifact_id,vector_json,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (evaluation_id, run_id, candidate_id, input_ref_kind, input_ref_id, purpose, artifact.artifact_id, _json(vector), "fixture-jev-deep-v1", utc_now()))]
        self._event(run_id, "JEV_DEEP_COMPLETED", key, "Fixture Jev-shaped deep judgment vector recorded; no Jev call made.", stage="JEV_DEEP", candidate_id=candidate_id, data={"evaluation_id": evaluation_id, "input_ref_kind": input_ref_kind, "input_ref_id": input_ref_id, "judgment_vector": vector, "external_calls": 0}, artifact_refs=[artifact.ref()], registrations=regs)

    def _make_dossier(self, run_id, candidate, baseline, after, fixture_hypotheses, make_id):
        dossier_id = make_id("dossier:primary")
        available = {
            "research_puzzle", "candidate_entity", "investigation_rationale", "initial_broad_evidence",
            "jev_wide_judgments", "deterministic_deep_evidence", "project_evidence",
            "contradictory_evidence", "missing_unavailable_evidence", "jev_deep_judgments",
            "competing_hypotheses", "hypothesis_jev_reviews", "deterministic_followups_performed",
            "followup_results", "remaining_uncertainty", "predictions_by_hypothesis",
            "falsification_criteria", "method_versions", "jev_model_question_versions", "research_only_notice",
        }
        sections = {}
        for key in DOSSIER_SECTIONS:
            sections[key] = {"availability": "OBSERVED" if key in available else "NOT_ACQUIRED", "reason": None if key in available else "Unavailable in the Phase 1 synthetic fixture.", "narrative": (WARNING if key == "research_only_notice" else f"Synthetic fixture section: {key.replace('_', ' ')}.") if key in available else None}
        dossier = {"schema_version": 1, "dossier_id": dossier_id, "run_id": run_id, "candidate_id": candidate["candidate_id"], "mode": "FAKE", "warning": WARNING, "evidence_state_ids": [baseline["evidence_state_id"], after["evidence_state_id"]], "hypothesis_ids": [h["hypothesis_id"] for h in fixture_hypotheses], "sections": sections, "created_at": utc_now()}
        json_artifact = self.artifacts.publish(f"runs/{run_id}/dossier/{dossier_id}.json", canonical_json(dossier), "application/json", "authoritative-dossier")
        markdown = render_markdown(dossier).encode()
        md_artifact = self.artifacts.publish(f"runs/{run_id}/dossier/{dossier_id}.md", markdown, "text/markdown; charset=utf-8", "derived-dossier-markdown")
        summary = {"dossier_id": dossier_id, "run_id": run_id, "candidate_id": candidate["candidate_id"], "mode": "FAKE", "entity": candidate["entity"], "puzzle": sections["research_puzzle"]["narrative"], "warning": WARNING, "json_artifact_id": json_artifact.artifact_id, "markdown_artifact_id": md_artifact.artifact_id}
        regs = [self.repository.artifact_registration(json_artifact, run_id), self.repository.artifact_registration(md_artifact, run_id), ("INSERT INTO dossiers(dossier_id,run_id,candidate_id,json_artifact_id,markdown_artifact_id,summary_json,created_at) VALUES(?,?,?,?,?,?,?)", (dossier_id, run_id, candidate["candidate_id"], json_artifact.artifact_id, md_artifact.artifact_id, _json(summary), dossier["created_at"])), ("UPDATE candidates SET status='DOSSIER_READY',current_stage=NULL,dossier_id=?,updated_at=? WHERE candidate_id=?", (dossier_id, utc_now(), candidate["candidate_id"]))]
        self._event(run_id, "DOSSIER_CREATED", "dossier:created", "Created authoritative JSON and deterministic Markdown synthetic dossier.", stage="DOSSIER", candidate_id=candidate["candidate_id"], data=summary, artifact_refs=[json_artifact.ref(), md_artifact.ref()], registrations=regs)

    def _publish_json(self, run_id: str, suffix: str, value: dict[str, Any], purpose: str) -> PublishedArtifact:
        return self.artifacts.publish(f"runs/{run_id}/{suffix}", canonical_json(value), "application/json", purpose)

    def _event(self, run_id: str, event_type: str, key: str, message: str, **kwargs):
        event = self.repository.append_event(run_id, event_type=event_type, idempotency_key=key, message=message, **kwargs)
        self.emit(event)
        self.repository.heartbeat(self.worker_id)
        return event

    def _delay(self):
        if self.settings.fixture_stage_delay_ms:
            time.sleep(self.settings.fixture_stage_delay_ms / 1000)

    def _stop(self, run_id: str) -> str:
        self._event(run_id, "RUN_STOPPED", "run:stopped", "Fixture run stopped at a safe boundary.", data={"status": "STOPPED", "reason_code": "INTERRUPTED", "coverage": "PARTIAL"}, level="warning")
        return run_id


REGISTERED_FIXTURE_ACTIONS = {"DROP_INFLUENTIAL_FIXTURE_POINTS_V1": "deterministic fixture implementation"}
