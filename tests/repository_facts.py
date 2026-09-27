"""Repository facts renderer/checker for docs/REPOSITORY_FACTS.md.

The facts table is the only place where mutable repository-wide facts (schema
versions, projection/question-set identities, policy versions, registry
versions) may be stated in prose-bearing documentation. Facts are collected
directly from the code that owns them; the checked markdown block must equal
the rendered block or the offline test fails.

``check`` also verifies the strict-mypy coverage invariant: every tracked
production Python module under ``cancerjev/``, ``apps/`` and ``deploy/`` must
be listed in ``[tool.mypy] files`` unless it is named in the explicit,
documented exclusion list. Mypy reports errors only for modules in that list,
so an unlisted module silently escapes strict typing.

Commands (run from the repository root with the project venv active):

    python tests/repository_facts.py check   # exit 1 with stale facts, if any
    python tests/repository_facts.py render  # rewrite the generated block

This module is documentation tooling. It is not part of the scientific runtime
chain, acquires nothing, and never contacts a provider.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from cancerjev import __version__ as PACKAGE_VERSION
from cancerjev.domain.codecs import (
    CNV_DISCOVERY_SCHEMA_VERSION,
    DISCOVERY_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    EXPRESSION_DISCOVERY_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
)
from cancerjev.domain.discovery import (
    CNV_DISPOSITION_POLICY_VERSION,
    EXPRESSION_ALIQUOT_IDENTITY_STATUS,
    EXPRESSION_DISPOSITION_POLICY_VERSION,
    MUTATION_CANONICAL_COMPOSITION_METHOD_ID,
    MUTATION_CANONICAL_COMPOSITION_VERSION,
    REDUCER_METHOD_ID,
    REDUCER_VERSION,
)
from cancerjev.domain.dossier import DOSSIER_SCHEMA_VERSION
from cancerjev.domain.events import SUPPORTED_SCHEMA_VERSION
from cancerjev.domain.functional import (
    FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION,
    FUNCTIONAL_SOURCE_DECISIONS,
    SourceDecision,
)
from cancerjev.domain.maturity import EVIDENCE_MATURITY_POLICY_VERSION
from cancerjev.domain.pathway import (
    REACTOME_MEMBERSHIP_METHOD_ID,
    REACTOME_MEMBERSHIP_VERSION,
)
from cancerjev.domain.runs import ExecutionOwnership
from cancerjev.gdc.budget import (
    BUDGET_POLICY_VERSION,
    INITIAL_PAGES,
    INITIAL_REQUESTS,
    PAGE_DEFECT_CEILING,
    REQUEST_DEFECT_CEILING,
    RUN_DOWNLOAD_BYTES,
    SHARD_DOWNLOAD_BYTES,
)
from cancerjev.gdc.endpoints import GDC_DATA_MODEL_REFERENCE
from cancerjev.jev.context import CONTEXT_GUARD_VERSION
from cancerjev.jev.posture import ARM_JEV_DECISION, TYPESAFE_DECISION_RECORD_VERSION
from cancerjev.jev.projection import (
    EVIDENCE_PROJECTION_VERSION,
    HYPOTHESIS_PROJECTION_VERSION,
    PROJECTION_VERSION,
)
from cancerjev.jev.questions import (
    DEEP_QUESTION_SET_VERSION,
    HYPOTHESIS_QUESTION_SET_VERSION,
    WIDE_QUESTION_SET_VERSION,
)
from cancerjev.research.campaign import LUAD_CAMPAIGN_V1
from cancerjev.research.campaign_selection import CAMPAIGN_SELECTION_POLICY_VERSION
from cancerjev.research.cnv_discovery import CNV_SHARD_RAW_EVICTION_POLICY
from cancerjev.research.deep import DEEP_ACTION_POLICY_VERSION
from cancerjev.research.finalize import FINAL_RESULT_SCHEMA_VERSION, NO_JEV_BASELINE_VERSION
from cancerjev.research.hypothesis_policy import HYPOTHESIS_POLICY_VERSION
from cancerjev.research.nextmove import DEEP_POLICY_VERSION
from cancerjev.research.program import PROGRAM_LOOP_VERSION
from cancerjev.research.ranking import (
    BASELINE_POLICY_VERSION,
    JEV_POLICY_VERSION,
    PRE_WIDE_POLICY_VERSION,
)
from cancerjev.research.release_monitor import RELEASE_MONITOR_VERSION
from cancerjev.research.specs import LUAD_DISCOVERY_V1, RESEARCH_SPEC_SCHEMA_VERSION
from cancerjev.science.actions import (
    ACTION_REGISTRY,
    ACTION_REGISTRY_VERSION,
    EVIDENCE_PRODUCING_ACTION_IDS,
)
from cancerjev.science.methods import (
    MUTATION_INFERENCE_DECISION_ID,
    MUTATION_INFERENCE_DECISION_VERSION,
)
from cancerjev.storage.database import SCHEMA_VERSION as SQLITE_SCHEMA_VERSION

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
FACTS_DOCUMENT = REPOSITORY_ROOT / "docs" / "REPOSITORY_FACTS.md"
PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"
BEGIN_MARKER = "<!-- repository-facts:begin (generated; python tests/repository_facts.py render) -->"
END_MARKER = "<!-- repository-facts:end -->"
# Production roots whose tracked Python modules must stay in the strict-mypy
# list. The literal ``cancerjev/**/*.py`` pathspec misses modules directly under
# ``cancerjev/`` (git ``**`` needs a directory level), so the check enumerates
# every tracked ``.py`` under these roots instead.
PRODUCTION_ROOTS = ("cancerjev", "apps", "deploy")
# Decision (P1-15): no standing exclusions. Every tracked production module,
# including package ``__init__.py`` markers and ``__main__.py``, is strictly
# typed. A future exclusion must be added here with its reason in
# ``MYPY_EXCLUSION_REASONS`` in the same change.
MYPY_EXCLUDED_MODULES: tuple[str, ...] = ()
MYPY_EXCLUSION_REASONS: dict[str, str] = {}


def tracked_production_modules() -> tuple[str, ...]:
    """Every tracked production Python module, enumerated from git."""
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", *PRODUCTION_ROOTS],
        cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=True)
    return tuple(sorted(path for path in completed.stdout.split("\0") if path.endswith(".py")))


def configured_mypy_modules() -> tuple[str, ...]:
    """The ``[tool.mypy] files`` list as configured."""
    with PYPROJECT.open("rb") as stream:
        pyproject = tomllib.load(stream)
    files = pyproject["tool"]["mypy"]["files"]
    if not isinstance(files, list) or not all(isinstance(entry, str) for entry in files):
        raise ValueError("[tool.mypy] files must be a list of paths")
    return tuple(files)


def check_mypy_coverage(*, modules: tuple[str, ...] | None = None,
                        listed: tuple[str, ...] | None = None,
                        excluded: tuple[str, ...] | None = None) -> list[str]:
    """Return strict-mypy coverage problems; empty means every module is covered."""
    production = set(tracked_production_modules() if modules is None else modules)
    configured = set(configured_mypy_modules() if listed is None else listed)
    exclusions = set(MYPY_EXCLUDED_MODULES if excluded is None else excluded)
    problems: list[str] = []
    for module in sorted(production - exclusions - configured):
        problems.append(f"{module}: tracked production module missing from [tool.mypy] files")
    for entry in sorted(configured - production):
        problems.append(f"{entry}: [tool.mypy] files entry is not a tracked production module")
    for exclusion in sorted(exclusions - production):
        problems.append(f"{exclusion}: documented mypy exclusion is not a tracked production module")
    for exclusion in sorted(exclusions):
        if exclusion not in MYPY_EXCLUSION_REASONS:
            problems.append(f"{exclusion}: mypy exclusion has no documented reason")
    return problems


def collect_facts() -> dict[str, object]:
    """Collect mutable repository-wide facts from their owning code constants."""
    return {
        "api_version": _api_version(),
        "action_registry_version": ACTION_REGISTRY_VERSION,
        "registered_action_ids": sorted(ACTION_REGISTRY),
        "evidence_producing_action_ids": sorted(EVIDENCE_PRODUCING_ACTION_IDS),
        "hypothesis_policy": HYPOTHESIS_POLICY_VERSION,
        "deep_next_move_policy": DEEP_POLICY_VERSION,
        "deep_question_set": DEEP_QUESTION_SET_VERSION,
        "dossier_schema_version": DOSSIER_SCHEMA_VERSION,
        "evidence_projection_version": EVIDENCE_PROJECTION_VERSION,
        "evidence_state_schema_version": EVIDENCE_SCHEMA_VERSION,
        "expression_discovery_result_schema_version": EXPRESSION_DISCOVERY_SCHEMA_VERSION,
        "final_candidate_result_schema_version": FINAL_RESULT_SCHEMA_VERSION,
        "gdc_data_model_reference": GDC_DATA_MODEL_REFERENCE,
        "systematic_universe_method": LUAD_DISCOVERY_V1.universe_method,
        "mutation_composition_method": (
            f"{MUTATION_CANONICAL_COMPOSITION_METHOD_ID} v{MUTATION_CANONICAL_COMPOSITION_VERSION}"),
        "mutation_inference_decision": (
            f"{MUTATION_INFERENCE_DECISION_ID} v{MUTATION_INFERENCE_DECISION_VERSION}"),
        "expression_disposition_policy": EXPRESSION_DISPOSITION_POLICY_VERSION,
        "expression_aliquot_identity": EXPRESSION_ALIQUOT_IDENTITY_STATUS,
        "gdc_budget_policy": BUDGET_POLICY_VERSION,
        "gdc_initial_pages_per_query": INITIAL_PAGES,
        "gdc_initial_requests": INITIAL_REQUESTS,
        "gdc_max_pages_per_query": PAGE_DEFECT_CEILING,
        "gdc_max_requests": REQUEST_DEFECT_CEILING,
        "gdc_run_download_bytes": RUN_DOWNLOAD_BYTES,
        "gdc_shard_download_bytes": SHARD_DOWNLOAD_BYTES,
        "jev_context_guard": CONTEXT_GUARD_VERSION,
        "cnv_disposition_policy": CNV_DISPOSITION_POLICY_VERSION,
        "cnv_shard_raw_eviction_policy": CNV_SHARD_RAW_EVICTION_POLICY,
        "evidence_maturity_policy": EVIDENCE_MATURITY_POLICY_VERSION,
        "pathway_membership_method": (
            f"{REACTOME_MEMBERSHIP_METHOD_ID} v{REACTOME_MEMBERSHIP_VERSION}"),
        "arm_jev_decision": ARM_JEV_DECISION.value,
        "typesafe_decision_record": TYPESAFE_DECISION_RECORD_VERSION,
        "execution_ownership_values": ",".join(
            ownership.value for ownership in ExecutionOwnership),
        "deep_action_policy": DEEP_ACTION_POLICY_VERSION,
        "campaign_selection_policy": CAMPAIGN_SELECTION_POLICY_VERSION,
        "program_loop_version": PROGRAM_LOOP_VERSION,
        "release_monitor_version": RELEASE_MONITOR_VERSION,
        "luad_campaign_readiness": LUAD_CAMPAIGN_V1.readiness.value,
        "functional_sources_record": FUNCTIONAL_SOURCE_DECISION_RECORD_VERSION,
        "functional_source_decision": ("DEFER" if all(
            decision is SourceDecision.DEFER for decision in FUNCTIONAL_SOURCE_DECISIONS.values())
            else "REVIEW"),
        "hypothesis_projection_version": HYPOTHESIS_PROJECTION_VERSION,
        "hypothesis_question_set": HYPOTHESIS_QUESTION_SET_VERSION,
        "mutation_discovery_result_schema_version": DISCOVERY_SCHEMA_VERSION,
        "mutation_reduction_method": f"{REDUCER_METHOD_ID} v{REDUCER_VERSION}",
        "no_jev_baseline_version": NO_JEV_BASELINE_VERSION,
        "package_version": PACKAGE_VERSION,
        "pre_wide_selection_policy": PRE_WIDE_POLICY_VERSION,
        "presentation_payload_schema_version": _presentation_schema_version(),
        "research_spec_schema_version": RESEARCH_SPEC_SCHEMA_VERSION,
        "run_event_schema_version": SUPPORTED_SCHEMA_VERSION,
        "sqlite_schema_version": SQLITE_SCHEMA_VERSION,
        "state_projection_version": PROJECTION_VERSION,
        "statistical_state_schema_version": STATE_SCHEMA_VERSION,
        "wide_admission_policy": JEV_POLICY_VERSION,
        "wide_baseline_policy": BASELINE_POLICY_VERSION,
        "wide_question_set": WIDE_QUESTION_SET_VERSION,
        "cnv_discovery_result_schema_version": CNV_DISCOVERY_SCHEMA_VERSION,
    }


def render_facts(facts: dict[str, object] | None = None) -> str:
    payload = json.dumps(collect_facts() if facts is None else facts, indent=2, sort_keys=True)
    return f"{BEGIN_MARKER}\n```json\n{payload}\n```\n{END_MARKER}\n"


def _block(document: str) -> str:
    start = document.find(BEGIN_MARKER)
    end = document.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise LookupError(f"generated facts block markers missing in {FACTS_DOCUMENT}")
    return document[start:end + len(END_MARKER)]


def _payload(block: str) -> dict[str, object]:
    fenced = block.removeprefix(BEGIN_MARKER).removesuffix(END_MARKER).strip()
    if not fenced.startswith("```json") or not fenced.endswith("```"):
        raise ValueError(f"generated facts block in {FACTS_DOCUMENT} is not a json fence")
    decoded = json.loads(fenced.removeprefix("```json").removesuffix("```"))
    if not isinstance(decoded, dict):
        raise ValueError(f"generated facts block in {FACTS_DOCUMENT} must be a json object")
    return decoded


def check_document(facts: dict[str, object] | None = None) -> list[str]:
    """Return human-readable stale-fact problems; empty means the block is current."""
    try:
        actual_facts = _payload(_block(FACTS_DOCUMENT.read_text(encoding="utf-8")))
    except (LookupError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    expected_facts = collect_facts() if facts is None else facts
    problems: list[str] = []
    for key in sorted(set(expected_facts) | set(actual_facts)):
        if key not in actual_facts:
            problems.append(f"{key}: missing from {FACTS_DOCUMENT.name} (expected {expected_facts[key]!r})")
        elif key not in expected_facts:
            problems.append(f"{key}: stale entry {actual_facts[key]!r} no longer exists in code")
        elif actual_facts[key] != expected_facts[key]:
            problems.append(f"{key}: documented {actual_facts[key]!r} != code {expected_facts[key]!r}")
    return problems


def render_document(facts: dict[str, object] | None = None) -> None:
    document = FACTS_DOCUMENT.read_text(encoding="utf-8")
    start = document.find(BEGIN_MARKER)
    end = document.find(END_MARKER)
    if start == -1 or end == -1:
        raise SystemExit(f"generated facts block markers missing in {FACTS_DOCUMENT}")
    rewritten = document[:start] + render_facts(facts) + document[end + len(END_MARKER):].lstrip("\n")
    FACTS_DOCUMENT.write_text(rewritten, encoding="utf-8")


def _api_version() -> str:
    from apps.api.routes import API_VERSION

    return API_VERSION


def _presentation_schema_version() -> int:
    from apps.api.serializers import PRESENTATION_SCHEMA_VERSION

    return PRESENTATION_SCHEMA_VERSION


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "render":
        render_document()
        print(f"rendered {FACTS_DOCUMENT.relative_to(REPOSITORY_ROOT)}")
        return 0
    if command == "check":
        problems = check_document()
        problems.extend(check_mypy_coverage())
        if problems:
            print("REPOSITORY FACTS OR STRICT-MYPY COVERAGE IS STALE:")
            for problem in problems:
                print(f"  - {problem}")
            print("run: python tests/repository_facts.py render "
                  "(facts only; mypy coverage is fixed in pyproject.toml)")
            return 1
        print("repository facts are current")
        return 0
    raise SystemExit(f"unknown command {command!r}; expected 'check' or 'render'")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
