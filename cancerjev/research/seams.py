"""Narrow callbacks at the existing orchestration boundaries; no service container."""

from collections.abc import Callable
from typing import Any, Protocol

from cancerjev.storage.artifacts import PublishedArtifact

PublishJson = Callable[[str, str, object, str], PublishedArtifact]
# This is explicitly an untrusted generator response, validated by hypotheses.
HypothesisGenerator = Callable[[dict[str, Any]], object]


class StageRunner(Protocol):
    def __call__[T](self, stage: str, function: Callable[[], T], /) -> T: ...
