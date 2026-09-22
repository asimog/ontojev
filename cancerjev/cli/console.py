from __future__ import annotations

import json
from typing import Any

LABELS = {
    "RUN_CREATED": "RUN", "RUN_STARTED": "RUN", "RUN_COMPLETED": "DONE",
    "RUN_FAILED": "FAILED", "RUN_STOPPED": "STOPPED", "STATISTICAL_STATE_CREATED": "STATE",
    "JEV_WIDE_STATE_EVALUATED": "JEV WIDE", "CANDIDATE_PROMOTED": "CANDIDATE",
    "EVIDENCE_STATE_CREATED": "EVIDENCE", "JEV_DEEP_COMPLETED": "JEV DEEP",
    "HYPOTHESES_GENERATED": "HYPOTHESES", "FOLLOWUP_COMPLETED": "FOLLOWUP",
    "DOSSIER_CREATED": "DOSSIER",
}


def render_event(event: dict[str, Any]) -> None:
    label = LABELS.get(event["type"], event.get("stage") or "EVENT")
    print(f"[{label}] #{event['sequence']} {event['message']}", flush=True)


def render_json_event(event: dict[str, Any]) -> None:
    print(json.dumps(event, indent=2, sort_keys=True), flush=True)

