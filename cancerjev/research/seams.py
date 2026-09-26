"""Narrow callbacks at the existing orchestration boundaries; no service container."""

import time
from collections.abc import Callable
from typing import Any, Protocol
from uuid import uuid4

from cancerjev.storage.artifacts import PublishedArtifact

PublishJson = Callable[[str, str, object, str], PublishedArtifact]
# This is explicitly an untrusted generator response, validated by hypotheses.
HypothesisGenerator = Callable[[dict[str, Any]], object]


class StageRunner(Protocol):
    def __call__[T](self, stage: str, function: Callable[[], T], /) -> T: ...


def run_stage[T](emit: Callable[..., Any], run_id: str, stage: str,
                 function: Callable[[], T]) -> T:
    """Emit one STAGE_STARTED/STAGE_COMPLETED pair around a bounded phase."""
    started = time.monotonic()
    emit(run_id, "STAGE_STARTED", f"stage:{stage}:started:{uuid4()}",
         f"Stage {stage} started.", stage=stage)
    try:
        result = function()
    except Exception as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        emit(
            run_id, "STAGE_COMPLETED", f"stage:{stage}:completed:{uuid4()}",
            f"Stage {stage} ended with error: {type(exc).__name__}.", stage=stage, level="error",
            data={"outcome": "FAILED", "elapsed_ms": elapsed, "error": str(exc)},
        )
        raise
    elapsed = int((time.monotonic() - started) * 1000)
    emit(
        run_id, "STAGE_COMPLETED", f"stage:{stage}:completed:{uuid4()}",
        f"Stage {stage} completed.", stage=stage,
        data={"outcome": "COMPLETED", "elapsed_ms": elapsed},
    )
    return result
