"""One bounded release observation per interval; comparison is a separate decision.

Polling is operational only: it reads the pinned provider status once, records the
release identity with its source, and tells the caller whether the release or its
commit changed. It never mutates prior campaigns and never triggers acquisition.
"""

from __future__ import annotations

from dataclasses import dataclass

from cancerjev.domain.measurements import ScientificSource, sha256, text
from cancerjev.gdc.endpoints import status_request
from cancerjev.gdc.parsers import parse_status
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    response_meta,
    response_operational_source,
)

RELEASE_MONITOR_VERSION = "release-monitor-v1"


@dataclass(frozen=True)
class ReleaseObservation:
    """One pinned release as observed at one point in time."""

    release: str
    release_commit: str | None
    source: ScientificSource

    def __post_init__(self) -> None:
        text(self.release, "release observation")
        if self.release_commit is not None:
            text(self.release_commit, "release observation commit")
        if not isinstance(self.source, ScientificSource):
            raise TypeError("release observation requires typed provenance")


def observe_release(transport: AcquisitionTransport) -> ReleaseObservation:
    """Exactly one bounded status request; provenance is recorded with the release."""
    response = transport.request(status_request())
    status = parse_status(response.body, response_meta(response, None))
    release = status.data_release or "UNVERIFIED_RELEASE"
    source = response_operational_source(response, release=release).source
    return ReleaseObservation(release=release, release_commit=status.commit, source=source)


def release_changed(previous: ReleaseObservation, current: ReleaseObservation) -> bool:
    """A release or its pinned commit changed; biology is never inferred here."""
    return (previous.release != current.release
            or previous.release_commit != current.release_commit)


def observation_hash(observation: ReleaseObservation) -> str:
    from cancerjev.domain.measurements import digest

    sha256(observation.source.response_hash, "release observation response hash")
    return digest({"version": RELEASE_MONITOR_VERSION, "release": observation.release,
                   "release_commit": observation.release_commit,
                   "response_hash": observation.source.response_hash})
