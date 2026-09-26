from enum import StrEnum

from cancerjev.domain.states import RunStatus


class ExecutionOwnership(StrEnum):
    """Who owns the run's writable scientific scope.

    VALIDATION_RUN is the explicit operator route that executes the identical
    canonical science pipeline for a profile below autonomous readiness. It can
    never be selected by the Program, never changes readiness, and exists to
    produce the reviewed live evidence an explicit promotion requires.
    """

    SYSTEM_AUTONOMOUS = "SYSTEM_AUTONOMOUS"
    RESEARCHER_RUN = "RESEARCHER_RUN"
    VALIDATION_RUN = "VALIDATION_RUN"

RUN_TRANSITIONS = {
    RunStatus.PENDING: {RunStatus.RUNNING, RunStatus.STOPPED, RunStatus.FAILED},
    RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.STOPPED: set(),
    RunStatus.FAILED: set(),
}


def validate_run_transition(current: str, target: str) -> None:
    try:
        current_status = RunStatus(current)
        target_status = RunStatus(target)
    except ValueError as exc:
        raise ValueError("unknown run status") from exc
    if target_status not in RUN_TRANSITIONS[current_status]:
        raise ValueError(f"illegal run transition: {current_status} -> {target_status}")

