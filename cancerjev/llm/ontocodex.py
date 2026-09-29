"""Replaceable scientific director using the upstream Codex executable."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cancerjev.config import Settings
from cancerjev.domain.laboratory import (
    MAX_PROJECTION_BYTES,
    DirectorIdentity,
    ResearchDecision,
)

DIRECTOR_INSTRUCTIONS = """You are OntoCodex, the scientific director of OntoJev.
Research lung cancer using permitted open-access GDC/GDAN evidence. Choose one
bounded next decision from the supplied structured state. Python executes it.
Start by forming a useful ResearchQuestion when the portfolio is empty. Select
only offered acquisitions; prefer the smallest sufficient experiment. If no
registered capability can answer the next question, report CAPABILITY_GAP.
Prioritize information value, uncertainty, conflicting evidence and replication.
Never fabricate measurements or citations. Missing is not negative. Control
priorities and model judgments are not biological evidence. Interpretations
must cite supplied evidence identities and explicitly retain uncertainty.
Do not call tools, inspect files, or execute commands. Return only the requested
ResearchDecision JSON. All unused optional fields must be null.
Action-specific fields (every other optional field MUST be null):
CREATE_QUESTION: question only (question_id MUST be null; put its id inside question).
PRIORITIZE: question_id and priority.
ACQUIRE: question_id and offer_id.
INTERPRET or ANSWER: question_id and interpretation.
DEFER, EXHAUST or CAPABILITY_GAP: question_id only.
STOP: no optional fields.
New questions must have status ACTIVE. Do not declare a capability gap before
creating the question; capability gaps must refer to an existing question.
If a deferred or capability-gap question now has a feasible offer, PRIORITIZE
it to reactivate it. ACQUIRE is permitted only for ACTIVE questions.
"""


class DirectorError(RuntimeError):
    """Recoverable operational failure, with a safe code rather than provider logs."""


class Director(Protocol):
    @property
    def identity(self) -> DirectorIdentity: ...

    def decide(self, projection: dict[str, Any], *, timeout: float) -> ResearchDecision: ...


def codex_executable() -> str:
    configured = os.getenv("ONTOCODEX_EXECUTABLE")
    if configured:
        executable = shutil.which(configured)
        if executable:
            return executable
        raise DirectorError("CODEX_EXECUTABLE_UNAVAILABLE")
    if os.name == "nt":
        # npm's .cmd wrapper requires a shell. Resolve its packaged native binary
        # instead, preserving argv boundaries and avoiding visible shell windows.
        wrapper = shutil.which("codex.cmd")
        if wrapper:
            root = Path(wrapper).parent / "node_modules" / "@openai" / "codex"
            matches = list(root.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
            if len(matches) == 1:
                return str(matches[0])
    executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if executable:
        return executable
    raise DirectorError("CODEX_EXECUTABLE_UNAVAILABLE")


@dataclass(frozen=True)
class CodexDirector:
    executable: str
    model: str
    base_url: str
    harness_version: str

    @classmethod
    def from_settings(cls, settings: Settings) -> CodexDirector:
        executable = codex_executable()
        try:
            version = subprocess.run([executable, "--version"], capture_output=True,
                                     text=True, check=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise DirectorError("CODEX_VERSION_UNAVAILABLE") from exc
        return cls(executable, os.getenv("ONTOCODEX_MODEL", settings.llm_model),
                   os.getenv("ONTOCODEX_BASE_URL", "https://openrouter.ai/api/v1"), version)

    @property
    def identity(self) -> DirectorIdentity:
        config = {"model": self.model, "base_url": self.base_url,
                  "instructions": DIRECTOR_INSTRUCTIONS,
                  "schema": ResearchDecision.model_json_schema(), "tools": False}
        return DirectorIdentity(harness_version=self.harness_version, provider="openrouter",
                                model=self.model, base_url=self.base_url,
                                configuration_hash=hashlib.sha256(
                                    json.dumps(config, sort_keys=True).encode()).hexdigest())

    def decide(self, projection: dict[str, Any], *, timeout: float) -> ResearchDecision:
        content = json.dumps(projection, sort_keys=True, allow_nan=False)
        if len(content.encode()) > MAX_PROJECTION_BYTES:
            raise DirectorError("DIRECTOR_PROJECTION_TOO_LARGE")
        if timeout <= 0:
            raise DirectorError("DIRECTOR_DEADLINE_EXHAUSTED")
        if not os.getenv("OPENROUTER_API_KEY"):
            raise DirectorError("OPENROUTER_CREDENTIAL_UNAVAILABLE")
        with tempfile.TemporaryDirectory(prefix="ontocodex-") as temporary:
            workspace = Path(temporary)
            home = workspace / "home"
            home.mkdir()
            schema = workspace / "decision.schema.json"
            output = workspace / "decision.json"
            schema.write_text(json.dumps(ResearchDecision.model_json_schema()), encoding="utf-8")
            # Dedicated home: no user MCP servers, hooks, plugins, conversations,
            # credentials or repository instructions enter the director context.
            config: dict[str, object] = {
                "model_provider": "ontocodex", "approval_policy": "never",
                "model_providers.ontocodex.name": "OpenRouter",
                "model_providers.ontocodex.base_url": self.base_url,
                "model_providers.ontocodex.env_key": "OPENROUTER_API_KEY",
                "model_providers.ontocodex.wire_api": "responses",
                "model_providers.ontocodex.requires_openai_auth": False,
                "model_providers.ontocodex.request_max_retries": 0,
                "model_providers.ontocodex.stream_max_retries": 0,
                "features.shell_tool": False, "features.unified_exec": False,
                "features.multi_agent": False, "features.apply_patch_freeform": False,
                "features.js_repl": False, "features.apps": False,
                "features.hooks": False, "features.plugins": False,
                "features.remote_plugin": False, "web_search": "disabled",
                "project_doc_max_bytes": 0,
            }
            command = [self.executable, "exec", "--ephemeral", "--ignore-user-config",
                       "--ignore-rules", "--skip-git-repo-check", "--sandbox", "read-only",
                       "--model", self.model, "--cd", str(workspace),
                       "--output-schema", str(schema), "--output-last-message", str(output)]
            for key, value in config.items():
                command.extend(["-c", f"{key}={json.dumps(value)}"])
            command.append("-")
            environment = {key: value for key, value in os.environ.items()
                           if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
                                              "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                                              "OPENROUTER_API_KEY", "SSL_CERT_FILE", "SSL_CERT_DIR"}}
            environment["CODEX_HOME"] = str(home)
            try:
                process = subprocess.run(
                    command, input=DIRECTOR_INSTRUCTIONS + "\nOUTPUT JSON SCHEMA:\n"
                    + schema.read_text(encoding="utf-8") + "\nSTATE:\n" + content,
                    text=True, encoding="utf-8", stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, cwd=workspace, env=environment,
                    timeout=timeout, check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if process.returncode != 0 or not output.is_file():
                    raise DirectorError("DIRECTOR_OUTPUT_MISSING")
                if output.stat().st_size > MAX_PROJECTION_BYTES:
                    raise DirectorError("DIRECTOR_OUTPUT_TOO_LARGE")
                return ResearchDecision.model_validate_json(output.read_bytes())
            except subprocess.TimeoutExpired as exc:
                raise DirectorError("DIRECTOR_TIMEOUT") from exc
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                raise DirectorError("DIRECTOR_INVALID_OR_UNAVAILABLE") from exc
