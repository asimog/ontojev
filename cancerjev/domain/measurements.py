"""Small immutable scientific contracts. No provider, storage or model dependencies."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum


class ContractError(ValueError):
    def __init__(self, detail: str, code: str = "INVALID_SCIENTIFIC_CONTRACT") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ContractError(detail)


def text(value: str, name: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonblank text")


def count(value: int, name: str) -> None:
    require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")


def finite(value: float, name: str) -> None:
    require(type(value) in (int, float), f"{name} must be numeric, not bool/null")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    require(valid, f"{name} must be finite")


def strings(values: tuple[str, ...], name: str, *, unique: bool = True) -> None:
    require(type(values) is tuple, f"{name} must be an immutable tuple")
    for value in values:
        text(value, name)
    require(not unique or len(set(values)) == len(values), f"duplicate {name}")


def sha256(value: str, name: str) -> None:
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), f"{name} must be SHA-256")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class Unit(StrEnum):
    CASES = "CASES"
    OBSERVATIONS = "OBSERVATIONS"
    UQFPKM = "UQFPKM"
    LOG2_UQFPKM_PLUS_ONE = "LOG2_UQFPKM_PLUS_ONE"
    SHARE = "SHARE"


class MetricAvailability(StrEnum):
    """Explicit availability of a descriptive value; absent is never zero."""

    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    NOT_ACQUIRED = "NOT_ACQUIRED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PopulationUnit(StrEnum):
    CASE = "CASE"
    SAMPLE = "SAMPLE"


class UnavailableStatus(StrEnum):
    NOT_ACQUIRED = "NOT_ACQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_OBSERVED = "NOT_OBSERVED"
    INCOMPATIBLE = "INCOMPATIBLE"
    INVALID = "INVALID"
    INSUFFICIENT = "INSUFFICIENT"


class Acquisition(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_ACQUIRED = "NOT_ACQUIRED"


class Sufficiency(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_ASSESSED = "NOT_ASSESSED"


class Compatibility(StrEnum):
    VERIFIED = "VERIFIED"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class EntityRef:
    gene_id: str
    symbol: str | None
    release: str

    def __post_init__(self) -> None:
        text(self.gene_id, "gene_id")
        require(self.gene_id.startswith("ENSG") and len(self.gene_id) == 15
                and self.gene_id[4:].isascii() and self.gene_id[4:].isdigit(), "expected Ensembl gene ID")
        if self.symbol is not None:
            text(self.symbol, "symbol")
        text(self.release, "release")


@dataclass(frozen=True)
class PopulationFrame:
    cohort_id: str
    project_id: str
    unit: PopulationUnit
    examined_ids: tuple[str, ...]
    eligible_ids: tuple[str, ...] | None
    selection_rule: str

    def __post_init__(self) -> None:
        text(self.cohort_id, "cohort_id")
        text(self.project_id, "project_id")
        require(isinstance(self.unit, PopulationUnit), "invalid population unit")
        strings(self.examined_ids, "examined_ids")
        require(tuple(sorted(self.examined_ids)) == self.examined_ids, "examined_ids must be sorted")
        if self.eligible_ids is not None:
            strings(self.eligible_ids, "eligible_ids")
            require(tuple(sorted(self.eligible_ids)) == self.eligible_ids, "eligible_ids must be sorted")
            require(set(self.examined_ids) <= set(self.eligible_ids), "examined outside eligible population")
        text(self.selection_rule, "selection_rule")

    @property
    def membership_hash(self) -> str:
        return digest([self.unit, self.project_id, self.examined_ids])


MAX_UNIVERSE_REQUEST_LIMIT = 100_000


@dataclass(frozen=True)
class TestedUniverse:
    """The actual bounded universe a run examined, in its declared order.

    ``GENE_ID_ASC`` describes an indexed ascending slice; ``PROVIDER_RANK_ASC``
    describes the bounded provider-ranked selection a discovery lane returned.
    The order string is part of the declared tested context, never inferred.
    """

    ordered_ids: tuple[str, ...]
    source: str
    release: str
    filter_description: str
    order: str
    offset: int
    requested_limit: int
    reported_total: int
    complete: bool

    def __post_init__(self) -> None:
        strings(self.ordered_ids, "universe IDs")
        for value in self.ordered_ids:
            EntityRef(value, None, self.release)
        for name in ("source", "release", "filter_description", "order"):
            text(getattr(self, name), name)
        require(self.order in {"GENE_ID_ASC", "PROVIDER_RANK_ASC"}, "unsupported universe ordering")
        if self.order == "GENE_ID_ASC":
            require(tuple(sorted(self.ordered_ids)) == self.ordered_ids, "universe is not ordered")
        count(self.offset, "offset")
        count(self.requested_limit, "requested_limit")
        count(self.reported_total, "reported_total")
        require(1 <= self.requested_limit <= MAX_UNIVERSE_REQUEST_LIMIT,
                f"universe limit must be 1..{MAX_UNIVERSE_REQUEST_LIMIT}")
        require(type(self.complete) is bool, "complete must be bool")
        expected = min(self.requested_limit, max(0, self.reported_total - self.offset))
        require(len(self.ordered_ids) <= expected, "universe exceeds declared slice")
        require(not self.complete or len(self.ordered_ids) == expected, "incomplete declared slice")

    @property
    def membership_hash(self) -> str:
        return digest(self.ordered_ids)


@dataclass(frozen=True)
class MethodParameters:
    """Only parameters used by the admitted count/expression summaries."""

    ddof: int | None = None
    pseudocount: float | None = None

    def __post_init__(self) -> None:
        if self.ddof is not None:
            count(self.ddof, "ddof")
            require(self.ddof == 1, "only sample SD (ddof=1) is admitted")
        if self.pseudocount is not None:
            finite(self.pseudocount, "pseudocount")
            require(self.pseudocount == 1, "only log2(UQFPKM+1) is admitted")
            object.__setattr__(self, "pseudocount", float(self.pseudocount))


@dataclass(frozen=True)
class MethodRef:
    method_id: str
    version: str
    unit: Unit
    parameters: MethodParameters
    duplicate_rule: str
    transform: str
    estimator: str
    missingness_rule: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.method_id, self.version, self.duplicate_rule, self.transform,
                      self.estimator, self.missingness_rule):
            text(value, "method contract")
        require(isinstance(self.unit, Unit), "invalid method unit")
        require(isinstance(self.parameters, MethodParameters), "parameters must have a declared contract")
        strings(self.limitations, "limitations")


@dataclass(frozen=True)
class MethodIdentityRef:
    """Recorded method identity; parameters hash binds the exact admitted parameters."""

    method_id: str
    version: str
    parameters_hash: str

    def __post_init__(self) -> None:
        text(self.method_id, "method_id")
        text(self.version, "method version")
        sha256(self.parameters_hash, "method parameters hash")


@dataclass(frozen=True)
class ScientificSource:
    endpoint: str
    request_hash: str
    response_hash: str
    parser_version: str
    release: str
    acquisition: Acquisition
    workflow_family: str | None = None
    caller_family: str | None = None
    strategy: str | None = None
    annotation_context: str | None = None

    def __post_init__(self) -> None:
        text(self.endpoint, "endpoint")
        require(self.endpoint.startswith("/") and not self.endpoint.startswith("//"), "endpoint must be a path")
        sha256(self.request_hash, "request_hash")
        sha256(self.response_hash, "response_hash")
        text(self.parser_version, "parser_version")
        text(self.release, "release")
        require(isinstance(self.acquisition, Acquisition), "invalid source acquisition")
        for value, name in ((self.workflow_family, "workflow_family"),
                            (self.caller_family, "caller_family"),
                            (self.strategy, "strategy"),
                            (self.annotation_context, "annotation_context")):
            if value is not None:
                text(value, f"source {name}")


@dataclass(frozen=True)
class OperationalSource:
    source: ScientificSource
    attempt_id: str
    artifact_id: str
    retrieved_at: str
    bytes_read: int
    latency_ms: int | None
    http_status: int | None
    cache_hit: bool

    def __post_init__(self) -> None:
        require(isinstance(self.source, ScientificSource), "invalid scientific source link")
        for value in (self.attempt_id, self.artifact_id, self.retrieved_at):
            text(value, "operational source")
        count(self.bytes_read, "bytes_read")
        if self.latency_ms is not None:
            count(self.latency_ms, "latency_ms")
        if self.http_status is not None:
            require(type(self.http_status) is int and 100 <= self.http_status <= 599, "invalid HTTP status")
        require(type(self.cache_hit) is bool, "cache_hit must be bool")


@dataclass(frozen=True)
class Quality:
    acquisition: Acquisition
    sufficiency: Sufficiency
    compatibility: Compatibility
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        require(isinstance(self.acquisition, Acquisition), "invalid acquisition")
        require(isinstance(self.sufficiency, Sufficiency), "invalid sufficiency")
        require(isinstance(self.compatibility, Compatibility), "invalid compatibility")
        strings(self.reasons, "quality reasons")
        if self.acquisition in (Acquisition.FAILED, Acquisition.NOT_ACQUIRED) or self.compatibility == Compatibility.INCOMPATIBLE:
            require(self.sufficiency != Sufficiency.SUFFICIENT, "unacquired/failed/incompatible evidence cannot be sufficient")
        if self.acquisition != Acquisition.COMPLETE or self.sufficiency != Sufficiency.SUFFICIENT \
                or self.compatibility in (Compatibility.INCOMPATIBLE, Compatibility.UNVERIFIED):
            require(bool(self.reasons), "non-affirmative quality requires a reason")


@dataclass(frozen=True)
class MissingGroup:
    reason: str
    ids: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.reason, "missing reason")
        strings(self.ids, "missing IDs")
        require(bool(self.ids), "empty missing group")
        require(self.ids == tuple(sorted(self.ids)), "missing IDs must be sorted")


@dataclass(frozen=True)
class Coverage:
    frame: PopulationFrame
    returned_ids: tuple[str, ...]
    valid_ids: tuple[str, ...]
    missing: tuple[MissingGroup, ...]
    assay_available_ids: tuple[str, ...] | None

    def __post_init__(self) -> None:
        require(isinstance(self.frame, PopulationFrame), "invalid coverage frame")
        strings(self.returned_ids, "returned IDs")
        strings(self.valid_ids, "valid IDs")
        require(self.returned_ids == tuple(sorted(self.returned_ids))
                and self.valid_ids == tuple(sorted(self.valid_ids)), "coverage IDs must be sorted")
        require(type(self.missing) is tuple and all(isinstance(m, MissingGroup) for m in self.missing),
                "missingness must be immutable typed groups")
        strings(tuple(m.reason for m in self.missing), "missing reasons")
        missing_ids = tuple(i for group in self.missing for i in group.ids)
        strings(missing_ids, "missing IDs across reasons")
        examined = set(self.frame.examined_ids)
        require(set(self.valid_ids) <= set(self.returned_ids) <= examined, "invalid returned/valid membership")
        require(not set(self.valid_ids) & set(missing_ids), "valid and missing overlap")
        require(set(self.valid_ids) | set(missing_ids) == examined, "coverage must account for every examined ID")
        if self.assay_available_ids is not None:
            strings(self.assay_available_ids, "assay available IDs")
            require(self.assay_available_ids == tuple(sorted(self.assay_available_ids)), "assay IDs must be sorted")
            require(set(self.assay_available_ids) <= examined, "assay availability outside frame")


def observed_context(unit: Unit, population: PopulationFrame, method: MethodRef,
                     sources: tuple[ScientificSource, ...]) -> None:
    require(isinstance(unit, Unit) and isinstance(population, PopulationFrame)
            and isinstance(method, MethodRef), "invalid measurement context")
    require(method.unit == unit, "method/measurement unit mismatch")
    require(type(sources) is tuple and bool(sources)
            and all(isinstance(s, ScientificSource) for s in sources), "observation needs typed sources")
    require(all(s.acquisition in (Acquisition.COMPLETE, Acquisition.PARTIAL) for s in sources),
            "failed/unacquired source cannot support an observation")


@dataclass(frozen=True)
class ObservedCount:
    value: int
    unit: Unit
    population: PopulationFrame
    method: MethodRef
    sources: tuple[ScientificSource, ...]

    def __post_init__(self) -> None:
        count(self.value, "observed count")
        observed_context(self.unit, self.population, self.method, self.sources)
        require(self.unit in (Unit.CASES, Unit.OBSERVATIONS), "count requires a count unit")
        if self.value == 0:
            require(all(s.acquisition == Acquisition.COMPLETE for s in self.sources),
                    "observed zero requires complete supporting source scope")


@dataclass(frozen=True)
class ObservedScalar:
    value: float
    unit: Unit
    population: PopulationFrame
    method: MethodRef
    sources: tuple[ScientificSource, ...]

    def __post_init__(self) -> None:
        finite(self.value, "observed scalar")
        object.__setattr__(self, "value", float(self.value))
        observed_context(self.unit, self.population, self.method, self.sources)
        require(self.unit in (Unit.UQFPKM, Unit.LOG2_UQFPKM_PLUS_ONE), "unsupported scalar unit")
        require(self.value >= 0, "expression measurement must be nonnegative")


@dataclass(frozen=True)
class UnavailableMeasurement:
    status: UnavailableStatus
    reason: str
    expected_unit: Unit
    population: PopulationFrame

    def __post_init__(self) -> None:
        require(isinstance(self.status, UnavailableStatus), "invalid unavailable status")
        text(self.reason, "unavailable reason")
        require(isinstance(self.expected_unit, Unit), "invalid expected unit")
        require(isinstance(self.population, PopulationFrame), "invalid unavailable population")


@dataclass(frozen=True)
class MetricRecord:
    """A descriptive value with explicit availability; a missing value is never zero.

    This is the typed form of the retained per-field availability records (unit,
    availability, reason). It is a presentation/evidence restatement, not a
    substitute for the lane measurement contracts.
    """

    value: int | float | None
    unit: str | None
    availability: MetricAvailability
    reason_code: str | None = None

    def __post_init__(self) -> None:
        require(isinstance(self.availability, MetricAvailability), "invalid metric availability")
        if self.availability == MetricAvailability.OBSERVED:
            metric_value = self.value
            if metric_value is None:
                raise ContractError("observed metric must be numeric, not bool/null")
            finite(metric_value, "observed metric")
            require(self.unit is not None and bool(self.unit.strip()), "observed metric requires a unit")
            if self.unit in {"cases", "count"}:
                require(type(self.value) is int and self.value >= 0, "count metric must be a nonnegative integer")
        else:
            require(self.value is None, "unavailable metric cannot carry a value")
            if self.reason_code is not None:
                text(self.reason_code, "metric reason code")

    @property
    def observed(self) -> bool:
        return self.availability == MetricAvailability.OBSERVED

    @classmethod
    def observed_value(cls, value: int | float, unit: str) -> MetricRecord:
        return cls(value, unit, MetricAvailability.OBSERVED)

    @classmethod
    def unavailable(cls, unit: str | None, availability: MetricAvailability,
                    reason_code: str | None = None) -> MetricRecord:
        return cls(None, unit, availability, reason_code)


type CountMeasurement = ObservedCount | UnavailableMeasurement
type ScalarMeasurement = ObservedScalar | UnavailableMeasurement
type Measurement = ObservedCount | ObservedScalar | UnavailableMeasurement
