from __future__ import annotations

from typing import Any

from cancerjev.domain.dossier import DOSSIER_SECTIONS

WARNING = "SYNTHETIC DEMONSTRATION — NO REAL GDC DATA WAS ANALYZED — NO REAL JEV CALL WAS MADE — NO REAL LLM CALL WAS MADE"


def render_markdown(dossier: dict[str, Any], warning: str = WARNING) -> str:
    lines = [f"# {warning}", "", f"Dossier `{dossier['dossier_id']}`", ""]
    for key in DOSSIER_SECTIONS:
        section = dossier["sections"][key]
        lines.extend([f"## {key.replace('_', ' ').title()}", "", section.get("narrative") or f"Availability: {section['availability']}. Reason: {section.get('reason', 'n/a')}", ""])
    return "\n".join(lines)

