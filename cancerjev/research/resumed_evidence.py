"""Declared evidence resume for the canonical Campaign continuation.

The canonical spine normally acquires every lane inside one process. Under the
operator's bounded-process rules the CNV lane is executed as small declared shard
processes plus a terminal merge, so the union/admission spine is resumed in a
separate VALIDATION run that consumes the already-published lane results. Any
subset of lanes may be resumed; lanes without a declared source run are acquired
by the identical lane functions in-process. Only published artifacts of terminal
runs are consumed; spec, cohort, project and release identities must agree across
the bound lanes, each lane's recorded method identity must be the currently
declared one (a stale policy version is refused, never silently composed), and
nothing is re-inferred or deleted. A resumed spine records the exact artifact
identities it consumed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cancerjev.domain.codecs import (
    read_cnv_project_scan,
    read_discovery,
    read_expression_discovery,
)
from cancerjev.domain.discovery import (
    EXPRESSION_TAIL_METHOD_ID,
    EXPRESSION_TAIL_VERSION,
    REDUCER_METHOD_ID,
    REDUCER_VERSION,
    CnvProjectScanResult,
    ExpressionDiscoveryResult,
    MutationDiscoveryResult,
)
from cancerjev.domain.measurements import ContractError, MetricAvailability
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.specs import ResearchSpec
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.repositories import Repository

MUTATION_RESULT_PATH = "runs/{run_id}/discovery/result.json"
EXPRESSION_RESULT_PATH = "runs/{run_id}/expression-discovery/result.json"
CNV_RESULT_PATH = "runs/{run_id}/cnv-discovery/project-scan-result.json"
TERMINAL_SOURCE_STATES = ("COMPLETED", "FAILED", "STOPPED")


@dataclass(frozen=True)
class ResumedLaneEvidence:
    """One lane's published result plus the immutable artifact identity consumed."""

    lane: str
    run_id: str
    artifact_id: str
    artifact_sha256: str
    relative_path: str

    def payload(self) -> dict[str, str]:
        return {"lane": self.lane, "run_id": self.run_id, "artifact_id": self.artifact_id,
                "artifact_sha256": self.artifact_sha256, "relative_path": self.relative_path}


@dataclass(frozen=True)
class ResumedEvidence:
    """Published lane results the continuation spine consumes; lanes stay optional."""

    mutation: MutationDiscoveryResult | None
    expression: ExpressionDiscoveryResult | None
    cnv: CnvProjectScanResult | None
    lanes: tuple[ResumedLaneEvidence, ...]

    def payload(self) -> dict[str, object]:
        return {"resumed_lanes": [lane.lane for lane in self.lanes],
                "release": self._release(),
                "cnv_case_shard_size": self.cnv.case_shard_size if self.cnv else None,
                "cnv_shard_count": self.cnv.shard_count if self.cnv else None,
                "lanes": [lane.payload() for lane in self.lanes]}

    def _release(self) -> str | None:
        for lane in (self.mutation, self.expression, self.cnv):
            if lane is not None:
                return lane.release
        return None


def _require_current_methods(lane: str, result: Any) -> None:
    """Refuse a resumed artifact recorded under a retired method/policy version."""
    if lane == "mutation":
        reducer = result.reducer
        if (reducer.method_id, reducer.version) != (REDUCER_METHOD_ID, REDUCER_VERSION):
            raise LiveRunError(
                "EVIDENCE_RESUME_STALE_METHOD",
                f"mutation reducer is {reducer.method_id} v{reducer.version}, not the declared "
                f"{REDUCER_METHOD_ID} v{REDUCER_VERSION}",
            )
    elif lane == "expression":
        observed = {(entry.tail.method.method_id, entry.tail.method.version)
                    for entry in result.entries
                    if entry.tail.availability is MetricAvailability.OBSERVED}
        stale = sorted(pair for pair in observed
                       if pair != (EXPRESSION_TAIL_METHOD_ID, EXPRESSION_TAIL_VERSION))
        if stale:
            raise LiveRunError(
                "EVIDENCE_RESUME_STALE_METHOD",
                f"expression tail method(s) {stale} are not the declared "
                f"{EXPRESSION_TAIL_METHOD_ID} v{EXPRESSION_TAIL_VERSION}",
            )


def _read_lane(*, repository: Repository, artifacts: ArtifactStore, lane: str,
               run_id: str, path: str,
               reader: Callable[[bytes], Any]) -> tuple[Any, ResumedLaneEvidence]:
    run = repository.get_run(run_id)
    if run is None:
        raise LiveRunError(
            "EVIDENCE_RESUME_SOURCE_MISSING",
            f"{lane} source run {run_id} does not exist in this workspace",
        )
    if str(run["status"]) not in TERMINAL_SOURCE_STATES:
        raise LiveRunError(
            "EVIDENCE_RESUME_SOURCE_ACTIVE",
            f"{lane} source run {run_id} is {run['status']}; only terminal runs may be consumed",
        )
    row = repository.artifact_at_path(path)
    if row is None:
        raise LiveRunError(
            "EVIDENCE_RESUME_SOURCE_MISSING",
            f"{lane} evidence artifact is missing ({path})",
        )
    sha = str(row.get("sha256") or "")
    relative = str(row.get("relative_path") or "")
    artifact_id = str(row.get("artifact_id") or "")
    if len(sha) != 64 or not relative:
        raise LiveRunError("EVIDENCE_RESUME_ARTIFACT_INVALID", f"{lane} artifact row is invalid")
    try:
        result = reader(artifacts.read(relative, sha))
    except (OSError, ContractError) as exc:
        raise LiveRunError(
            "EVIDENCE_RESUME_ARTIFACT_INVALID",
            f"{lane} artifact could not be read: {exc}",
        ) from exc
    _require_current_methods(lane, result)
    return result, ResumedLaneEvidence(lane, run_id, artifact_id, sha, relative)


def load_resumed_evidence(*, repository: Repository, artifacts: ArtifactStore,
                          spec: ResearchSpec, mutation_run: str | None = None,
                          expression_run: str | None = None,
                          cnv_run: str | None = None) -> ResumedEvidence:
    """Load and cross-check the declared lane results for the research spec.

    At least one source run is required; lanes without a source run are acquired
    by the campaign spine itself.
    """
    if not any((mutation_run, expression_run, cnv_run)):
        raise LiveRunError(
            "EVIDENCE_RESUME_SOURCE_MISSING",
            "at least one resume source run is required",
        )
    mutation = expression = cnv = None
    lanes: list[ResumedLaneEvidence] = []
    if mutation_run:
        mutation, lane = _read_lane(
            repository=repository, artifacts=artifacts, lane="mutation", run_id=mutation_run,
            path=MUTATION_RESULT_PATH.format(run_id=mutation_run), reader=read_discovery)
        lanes.append(lane)
    if expression_run:
        expression, lane = _read_lane(
            repository=repository, artifacts=artifacts, lane="expression",
            run_id=expression_run,
            path=EXPRESSION_RESULT_PATH.format(run_id=expression_run),
            reader=read_expression_discovery)
        lanes.append(lane)
    if cnv_run:
        cnv, lane = _read_lane(
            repository=repository, artifacts=artifacts, lane="cnv", run_id=cnv_run,
            path=CNV_RESULT_PATH.format(run_id=cnv_run), reader=read_cnv_project_scan)
        attempts = sorted(source.attempt_id for source in cnv.sources)
        required = [f"cnv-shard-{index}" for index in range(cnv.shard_count)]
        if attempts != required:
            raise LiveRunError(
                "EVIDENCE_RESUME_CNV_INCOMPLETE",
                "merged CNV evidence does not cover every declared shard exactly once",
            )
        lanes.append(lane)
    expected_scope = (spec.spec_id, spec.cohort.cohort_id, spec.cohort.project_id)
    for lane_name, result in (("mutation", mutation), ("expression", expression), ("cnv", cnv)):
        if result is None:
            continue
        if (result.spec_id, result.cohort_id, result.project_id) != expected_scope:
            raise LiveRunError(
                "EVIDENCE_RESUME_SCOPE_MISMATCH",
                f"{lane_name} evidence does not bind the declared research scope",
            )
    releases = {result.release for result in (mutation, expression, cnv) if result is not None}
    if len(releases) != 1:
        raise LiveRunError(
            "EVIDENCE_RESUME_RELEASE_MISMATCH",
            f"resumed lane releases differ: {sorted(releases)}",
        )
    return ResumedEvidence(mutation, expression, cnv, tuple(lanes))
