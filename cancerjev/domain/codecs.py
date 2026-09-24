"""Direct versioned readers. JSON ends here; no reflection-based decoder.

Legacy records retain their original bytes and scientific identity. They are not
v3 states. Storage must still validate artifact bytes and record bindings (Stage 2).
"""

from dataclasses import asdict

from cancerjev.domain._json import (
    boolean,
    decode,
    integer,
    number,
    obj,
    optional_string,
    seq,
    string,
    string_tuple,
    version,
)
from cancerjev.domain.evidence import (
    ActionRef,
    CheckOutcome,
    CheckSummary,
    EvidenceCheck,
    EvidenceStateV3,
)
from cancerjev.domain.legacy_codecs import LegacyArtifact, read_legacy_evidence, read_legacy_state
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
    CountMeasurement,
    Coverage,
    EntityRef,
    Measurement,
    MethodParameters,
    MethodRef,
    MissingGroup,
    ObservedCount,
    ObservedScalar,
    OperationalSource,
    PopulationFrame,
    PopulationUnit,
    Quality,
    ScalarMeasurement,
    ScientificSource,
    Sufficiency,
    TestedUniverse,
    UnavailableMeasurement,
    UnavailableStatus,
    Unit,
    canonical_bytes,
    digest,
    require,
    sha256,
)
from cancerjev.domain.scientific import (
    CnvOccurrence,
    CnvOccurrenceResult,
    ExpressionSummaryResult,
    ExpressionValue,
    Lane,
    MutationCountResult,
    StatisticalStateV3,
    UnavailableLane,
)


def _entity(value: object) -> EntityRef:
    d = obj(value, "gene_id symbol release")
    return EntityRef(string(d["gene_id"]), optional_string(d["symbol"]), string(d["release"]))


def _frame(value: object) -> PopulationFrame:
    d = obj(value, "cohort_id project_id unit examined_ids eligible_ids selection_rule")
    return PopulationFrame(string(d["cohort_id"]), string(d["project_id"]), PopulationUnit(string(d["unit"])),
                           string_tuple(d["examined_ids"]),
                           None if d["eligible_ids"] is None else string_tuple(d["eligible_ids"]),
                           string(d["selection_rule"]))


def _universe(value: object) -> TestedUniverse:
    d = obj(value, "ordered_ids source release filter_description order offset requested_limit reported_total complete")
    return TestedUniverse(string_tuple(d["ordered_ids"]), string(d["source"]), string(d["release"]),
                          string(d["filter_description"]), string(d["order"]), integer(d["offset"]),
                          integer(d["requested_limit"]), integer(d["reported_total"]), boolean(d["complete"]))


def _source(value: object) -> ScientificSource:
    d = obj(value, "endpoint request_hash response_hash parser_version release acquisition")
    return ScientificSource(string(d["endpoint"]), string(d["request_hash"]), string(d["response_hash"]),
                            string(d["parser_version"]), string(d["release"]), Acquisition(string(d["acquisition"])))


def _sources(value: object) -> tuple[ScientificSource, ...]:
    return tuple(_source(item) for item in seq(value))


def _operational_source(value: object) -> OperationalSource:
    d = obj(value, "source attempt_id artifact_id retrieved_at bytes_read latency_ms http_status cache_hit")
    return OperationalSource(_source(d["source"]), string(d["attempt_id"]), string(d["artifact_id"]),
                             string(d["retrieved_at"]), integer(d["bytes_read"]),
                             None if d["latency_ms"] is None else integer(d["latency_ms"]),
                             None if d["http_status"] is None else integer(d["http_status"]), boolean(d["cache_hit"]))


def _quality(value: object) -> Quality:
    d = obj(value, "acquisition sufficiency compatibility reasons")
    return Quality(Acquisition(string(d["acquisition"])), Sufficiency(string(d["sufficiency"])),
                   Compatibility(string(d["compatibility"])), string_tuple(d["reasons"]))


def _method(value: object) -> MethodRef:
    d = obj(value, "method_id version unit parameters duplicate_rule transform estimator missingness_rule limitations")
    p = obj(d["parameters"], "ddof pseudocount")
    parameters = MethodParameters(None if p["ddof"] is None else integer(p["ddof"]),
                                  None if p["pseudocount"] is None else number(p["pseudocount"]))
    return MethodRef(string(d["method_id"]), string(d["version"]), Unit(string(d["unit"])), parameters,
                     string(d["duplicate_rule"]), string(d["transform"]), string(d["estimator"]),
                     string(d["missingness_rule"]), string_tuple(d["limitations"]))


def read_measurement(value: object) -> Measurement:
    d = obj(value)
    if "status" in d:
        obj(d, "status reason expected_unit population")
        return UnavailableMeasurement(UnavailableStatus(string(d["status"])), string(d["reason"]),
                                      Unit(string(d["expected_unit"])), _frame(d["population"]))
    obj(d, "value unit population method sources")
    unit = Unit(string(d["unit"]))
    if unit in (Unit.CASES, Unit.OBSERVATIONS):
        return ObservedCount(integer(d["value"]), unit, _frame(d["population"]), _method(d["method"]), _sources(d["sources"]))
    return ObservedScalar(number(d["value"]), unit, _frame(d["population"]), _method(d["method"]), _sources(d["sources"]))


def _count(value: object) -> CountMeasurement:
    result = read_measurement(value)
    if isinstance(result, ObservedScalar):
        raise ContractError("count result cannot contain a scalar")
    return result


def _scalar(value: object) -> ScalarMeasurement:
    result = read_measurement(value)
    if isinstance(result, ObservedCount):
        raise ContractError("scalar result cannot contain a count")
    return result


def _missing(value: object) -> MissingGroup:
    d = obj(value, "reason ids")
    return MissingGroup(string(d["reason"]), string_tuple(d["ids"]))


def _coverage(value: object) -> Coverage:
    d = obj(value, "frame returned_ids valid_ids missing assay_available_ids")
    return Coverage(_frame(d["frame"]), string_tuple(d["returned_ids"]), string_tuple(d["valid_ids"]),
                    tuple(_missing(item) for item in seq(d["missing"])),
                    None if d["assay_available_ids"] is None else string_tuple(d["assay_available_ids"]))


def _unavailable_lane(value: object) -> UnavailableLane:
    d = obj(value, "lane enabled status reason")
    return UnavailableLane(Lane(string(d["lane"])), boolean(d["enabled"]),
                           UnavailableStatus(string(d["status"])), string(d["reason"]))


def _mutation(value: object) -> MutationCountResult | UnavailableLane:
    d = obj(value)
    if "status" in d:
        return _unavailable_lane(d)
    obj(d, "affected_cases ssm_coverage_cases frame quality entity")
    return MutationCountResult(_count(d["affected_cases"]), _count(d["ssm_coverage_cases"]),
                               _frame(d["frame"]), _quality(d["quality"]), _entity(d["entity"]))


def _expression_value(value: object) -> ExpressionValue:
    d = obj(value, "case_id uqfpkm")
    return ExpressionValue(string(d["case_id"]), number(d["uqfpkm"]))


def _expression(value: object) -> ExpressionSummaryResult | UnavailableLane:
    d = obj(value)
    if "status" in d:
        return _unavailable_lane(d)
    obj(d, "values coverage median sample_sd minimum maximum quality sources entity")
    return ExpressionSummaryResult(tuple(_expression_value(item) for item in seq(d["values"])),
                                   _coverage(d["coverage"]), _scalar(d["median"]), _scalar(d["sample_sd"]),
                                   _scalar(d["minimum"]), _scalar(d["maximum"]), _quality(d["quality"]), _sources(d["sources"]), _entity(d["entity"]))


def _occurrence(value: object) -> CnvOccurrence:
    d = obj(value, "occurrence_id cnv_id case_id gene_id raw_category source_file_id caller sample_id copy_number")
    return CnvOccurrence(string(d["occurrence_id"]), string(d["cnv_id"]), string(d["case_id"]),
                         string(d["gene_id"]), string(d["raw_category"]), optional_string(d["source_file_id"]),
                         optional_string(d["caller"]), optional_string(d["sample_id"]),
                         None if d["copy_number"] is None else number(d["copy_number"]))


def _cnv(value: object) -> CnvOccurrenceResult | UnavailableLane:
    d = obj(value)
    if "status" in d:
        return _unavailable_lane(d)
    obj(d, "entity frame occurrences sources quality")
    return CnvOccurrenceResult(_entity(d["entity"]), _frame(d["frame"]),
                               tuple(_occurrence(item) for item in seq(d["occurrences"])),
                               _sources(d["sources"]), _quality(d["quality"]))


def _check(value: object) -> EvidenceCheck:
    d = obj(value, "check_id method_id method_version outcome claim input_hashes reason n_effective")
    return EvidenceCheck(string(d["check_id"]), string(d["method_id"]), string(d["method_version"]),
                         CheckOutcome(string(d["outcome"])), string(d["claim"]), string_tuple(d["input_hashes"]),
                         optional_string(d["reason"]), None if d["n_effective"] is None else integer(d["n_effective"]))


def _action(value: object) -> ActionRef | None:
    if value is None:
        return None
    d = obj(value, "action_id version")
    return ActionRef(string(d["action_id"]), string(d["version"]))


def _summary(value: object) -> CheckSummary:
    d = obj(value, "total verified contradicted not_observed")
    return CheckSummary(integer(d["total"]), integer(d["verified"]), integer(d["contradicted"]), integer(d["not_observed"]))


def state_identity(state: StatisticalStateV3) -> str:
    # Explicit boundary serialization. Operational metadata never contributes.
    payload = asdict(state)
    del payload["operational_sources"]
    return digest({"schema_version": 3, "kind": "STATISTICAL_STATE", **payload})


def evidence_identity(state: EvidenceStateV3) -> str:
    return digest({"schema_version": 3, "kind": "EVIDENCE_STATE", **asdict(state)})


def write_state(state: StatisticalStateV3) -> bytes:
    return canonical_bytes({"schema_version": 3, "kind": "STATISTICAL_STATE", **asdict(state), "state_hash": state_identity(state)})


def write_evidence(state: EvidenceStateV3) -> bytes:
    return canonical_bytes({"schema_version": 3, "kind": "EVIDENCE_STATE", **asdict(state),
                            "summary": asdict(state.summary), "evidence_hash": evidence_identity(state)})


def _binding(actual: str, stored: object, expected: str | None) -> None:
    stored_hash = string(stored)
    sha256(stored_hash, "stored scientific hash")
    require(actual == stored_hash, "stored scientific identity mismatch")
    if expected is not None:
        sha256(expected, "expected scientific hash")
        require(actual == expected, "expected scientific identity mismatch")


def read_state(data: bytes, *, expected_hash: str | None = None) -> StatisticalStateV3 | LegacyArtifact:
    try:
        d = decode(data)
        if version(d) != 3:
            return read_legacy_state(data, expected_hash=expected_hash)
        obj(d, "schema_version kind entity frame universe mutation expression cnv quality sources operational_sources state_hash")
        require(d["kind"] == "STATISTICAL_STATE", "wrong artifact kind")
        state = StatisticalStateV3(_entity(d["entity"]), _frame(d["frame"]), _universe(d["universe"]),
                                   _mutation(d["mutation"]), _expression(d["expression"]), _cnv(d["cnv"]),
                                   _quality(d["quality"]), _sources(d["sources"]),
                                   tuple(_operational_source(item) for item in seq(d["operational_sources"])))
        _binding(state_identity(state), d["state_hash"], expected_hash)
        return state
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid statistical state") from exc


def read_evidence(data: bytes, *, expected_hash: str | None = None) -> EvidenceStateV3 | LegacyArtifact:
    try:
        d = decode(data)
        if version(d) != 3:
            return read_legacy_evidence(data, expected_hash=expected_hash)
        obj(d, "schema_version kind entity accepted_state_hash parent_evidence_hash revision_index action checks quality sources summary evidence_hash")
        require(d["kind"] == "EVIDENCE_STATE", "wrong artifact kind")
        state = EvidenceStateV3(_entity(d["entity"]), string(d["accepted_state_hash"]),
                                optional_string(d["parent_evidence_hash"]), integer(d["revision_index"]),
                                _action(d["action"]), tuple(_check(item) for item in seq(d["checks"])),
                                _quality(d["quality"]), _sources(d["sources"]))
        require(_summary(d["summary"]) == state.summary, "check summary does not match checks")
        _binding(evidence_identity(state), d["evidence_hash"], expected_hash)
        return state
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid evidence state") from exc
