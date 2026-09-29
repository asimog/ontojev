from __future__ import annotations

import json
from typing import Any

from cancerjev.domain.dossier import DOSSIER_SECTIONS

WARNING = "SYNTHETIC DEMONSTRATION — NO REAL GDC DATA WAS ANALYZED — NO REAL JEV CALL WAS MADE — NO REAL LLM CALL WAS MADE"


def render_markdown(dossier: dict[str, Any], warning: str = WARNING) -> str:
    lines = [f"# {warning}", "", f"Dossier `{dossier['dossier_id']}`", ""]
    for key in DOSSIER_SECTIONS:
        section = dossier["sections"][key]
        lines.extend([f"## {key.replace('_', ' ').title()}", "", section.get("narrative") or f"Availability: {section['availability']}. Reason: {section.get('reason', 'n/a')}", ""])
        for evaluation in section.get("evaluations", []):
            contract = evaluation.get("contract") or {}
            lines.extend([
                f"### Jev evaluation {evaluation.get('evaluation_id')}", "",
                f"Role: {evaluation.get('role')}. Contract: {contract.get('contract_id', 'not recorded')}. "
                f"Question set: {evaluation.get('question_set_version')}. "
                f"Evaluation status: {contract.get('evaluation_status', 'not recorded')}.", "",
                f"Projection: `{evaluation.get('projection_id')}` / `{evaluation.get('projection_hash')}`.", "",
                evaluation.get("relationship", ""), "",
            ])
            for question in contract.get("questions", []):
                lines.extend([f"**{question['id']}**: {question['instructions']}", ""])
            lines.extend(["```json", json.dumps({
                "answers": evaluation.get("answers"), "error": evaluation.get("error"),
                "uncertainty": evaluation.get("uncertainty"),
            }, indent=2, ensure_ascii=False), "```", ""])
    return "\n".join(lines)

