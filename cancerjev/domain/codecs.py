"""Schema-4 boundary codecs for the canonical scientific objects.

JSON exists here only at the persistence boundary. Readers are explicit: no
reflection-based decoder, no schema-1/2/3 compatibility and no legacy scientific
model. An older, newer or wrongly typed schema version fails closed.
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
)
from cancerjev.domain.discovery import (
    CnvCategorySummary,
    CnvDiscoveryEntry,
    CnvDiscoveryResult,
    CnvDiscoverySpec,
    CnvDisposition,
    CnvGeneEvidence,
    CnvProjectCall,
    CnvProjectScanResult,
    CnvShardEvidence,
    DiscoveryComparator,
    DiscoveryDisposition,
    DiscoverySpec,
    ExpressionDiscoveryEntry,
    ExpressionDiscoveryResult,
    ExpressionDiscoverySpec,
    ExpressionDisposition,
    ExpressionTailDescriptor,
    MutationDescriptiveEvidence,
    MutationDiscoveryEntry,
    MutationDiscoveryResult,
)
from cancerjev.domain.evidence import (
    ActionRef,
    BaselineObservation,
    CheckOutcome,
    EvidenceCheck,
    EvidenceProvenance,
    EvidenceState,
    InputArtifactRef,
    MeasuredObservation,
    MissingEvidence,
    ProjectEvidenceRow,
    ResearchPuzzle,
    SourceStateBinding,
)
from cancerjev.domain.measurements import (
    Acquisition,
    Compatibility,
    ContractError,
    CountMeasurement,
    Coverage,
    EntityRef,
    Measurement,
    MethodIdentityRef,
    MethodParameters,
    MethodRef,
    MetricAvailability,
    MetricRecord,
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
    AcquisitionScope,
    CnvCategory,
    CnvOccurrence,
    CnvOccurrenceResult,
    CnvProjectFinding,
    CrossProjectSummary,
    ExpressionSummaryResult,
    ExpressionValue,
    GeneAnnotation,
    Lane,
    MutationCountResult,
    PopulationRecord,
    ProjectState,
    ProviderDiscoveryMetadata,
    ProviderExpressionSummary,
    ResearchState,
    StatisticalState,
    TestedContext,
    UnavailableLane,
)

STATE_SCHEMA_VERSION = 5
EVIDENCE_SCHEMA_VERSION = 4
DISCOVERY_SCHEMA_VERSION = 1
EXPRESSION_DISCOVERY_SCHEMA_VERSION = 1
CNV_DISCOVERY_SCHEMA_VERSION = 1
CNV_SHARD_EVIDENCE_SCHEMA_VERSION = 2
CNV_PROJECT_SCAN_SCHEMA_VERSION = 1


# --------------------------------------------------------------- shared readers


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


def _discovery_spec(value: object) -> DiscoverySpec:
    d = obj(value, "universe_method biotype order offset universe_limit occurrence_scan_page_size")
    return DiscoverySpec(string(d["universe_method"]), string(d["biotype"]), string(d["order"]),
                         integer(d["offset"]), integer(d["universe_limit"]),
                         integer(d["occurrence_scan_page_size"]))


def _disposition(value: object) -> DiscoveryDisposition:
    return DiscoveryDisposition(string(value))


def _comparator(value: object) -> DiscoveryComparator | None:
    if value is None:
        return None
    d = obj(value, "rule provider_gene_ids survivor_overlap")
    return DiscoveryComparator(string(d["rule"]), string_tuple(d["provider_gene_ids"]),
                               string_tuple(d["survivor_overlap"]))


def _entry(value: object) -> MutationDiscoveryEntry:
    d = obj(value)
    required = {"entity", "outcome", "disposition", "reason", "rank"}
    allowed = required | {"descriptive"}
    require(set(d) <= allowed, "entry carries unexpected fields")
    require(set(d) >= required, "entry is missing required fields")
    descriptive = d.get("descriptive")
    return MutationDiscoveryEntry(
        _entity(d["entity"]), _mutation(d["outcome"]), _disposition(d["disposition"]),
        string(d["reason"]), None if d["rank"] is None else integer(d["rank"]),
        None if descriptive is None else _descriptive(descriptive))


def _string_string_pair(value: object) -> tuple[str, str]:
    parts = seq(value)
    require(len(parts) == 2, "expected a two-item pair")
    return string(parts[0]), string(parts[1])


def _string_int_pairs(value: object) -> tuple[tuple[str, int], ...]:
    pairs: list[tuple[str, int]] = []
    for item in seq(value):
        parts = seq(item)
        require(len(parts) == 2, "expected a two-item pair")
        pairs.append((string(parts[0]), integer(parts[1])))
    return tuple(pairs)


def _int_int_pairs(value: object) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for item in seq(value):
        parts = seq(item)
        require(len(parts) == 2, "expected a two-item pair")
        pairs.append((integer(parts[0]), integer(parts[1])))
    return tuple(pairs)


def _descriptive(value: object) -> MutationDescriptiveEvidence:
    d = obj(value, "consequence_composition canonical_transcript_n protein_position_top "
                   "hotspot_descriptor review_trigger method limitations")
    return MutationDescriptiveEvidence(
        _string_int_pairs(d["consequence_composition"]),
        integer(d["canonical_transcript_n"]),
        _int_int_pairs(d["protein_position_top"]),
        optional_string(d["hotspot_descriptor"]),
        optional_string(d["review_trigger"]),
        _method_identity(d["method"]),
        string_tuple(d["limitations"]),
    )


_SOURCE_REQUIRED_FIELDS = ("endpoint", "request_hash", "response_hash", "parser_version", "release",
                           "acquisition")
_SOURCE_OPTIONAL_FIELDS = ("workflow_family", "caller_family", "strategy", "annotation_context")


def _source(value: object) -> ScientificSource:
    d = obj(value)
    allowed = set(_SOURCE_REQUIRED_FIELDS) | set(_SOURCE_OPTIONAL_FIELDS)
    require(set(d) <= allowed, "source carries unexpected fields")
    require(set(d) >= set(_SOURCE_REQUIRED_FIELDS), "source is missing required fields")
    return ScientificSource(
        string(d["endpoint"]), string(d["request_hash"]), string(d["response_hash"]),
        string(d["parser_version"]), string(d["release"]), Acquisition(string(d["acquisition"])),
        optional_string(d.get("workflow_family")), optional_string(d.get("caller_family")),
        optional_string(d.get("strategy")), optional_string(d.get("annotation_context")),
    )


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


def _method_identity(value: object) -> MethodIdentityRef:
    d = obj(value, "method_id version parameters_hash")
    return MethodIdentityRef(string(d["method_id"]), string(d["version"]), string(d["parameters_hash"]))


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


def _mutation(value: object) -> MutationCountResult:
    d = obj(value, "affected_cases ssm_coverage_cases coverage_complete frame quality entity")
    return MutationCountResult(_count(d["affected_cases"]), _count(d["ssm_coverage_cases"]),
                               boolean(d["coverage_complete"]), _frame(d["frame"]),
                               _quality(d["quality"]), _entity(d["entity"]))


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
                                   _scalar(d["minimum"]), _scalar(d["maximum"]), _quality(d["quality"]),
                                   _sources(d["sources"]), _entity(d["entity"]))


def _occurrence(value: object) -> CnvOccurrence:
    d = obj(value, "occurrence_id cnv_id case_id gene_id raw_category source_file_id caller sample_id copy_number")
    return CnvOccurrence(string(d["occurrence_id"]), string(d["cnv_id"]), string(d["case_id"]),
                         string(d["gene_id"]), string(d["raw_category"]), optional_string(d["source_file_id"]),
                         optional_string(d["caller"]), optional_string(d["sample_id"]),
                         None if d["copy_number"] is None else number(d["copy_number"]))


def _cnv(value: object) -> CnvOccurrenceResult | CnvProjectFinding | UnavailableLane:
    d = obj(value)
    if "status" in d:
        return _unavailable_lane(d)
    if "disposition" in d:
        obj(d, "disposition reason review_trigger raw_categories callers "
               "conflicting_case_ids records")
        categories: list[tuple[str, tuple[str, ...]]] = []
        for item in seq(d["raw_categories"]):
            parts = seq(item)
            require(len(parts) == 2, "expected a two-item CNV category pair")
            categories.append((string(parts[0]), string_tuple(parts[1])))
        return CnvProjectFinding(
            string(d["disposition"]), string(d["reason"]), optional_string(d["review_trigger"]),
            tuple(categories), string_tuple(d["callers"]),
            string_tuple(d["conflicting_case_ids"]), integer(d["records"]),
        )
    obj(d, "entity frame occurrences sources quality")
    return CnvOccurrenceResult(_entity(d["entity"]), _frame(d["frame"]),
                               tuple(_occurrence(item) for item in seq(d["occurrences"])),
                               _sources(d["sources"]), _quality(d["quality"]))


# ------------------------------------------------------------- state components


def _metric_record(value: object) -> MetricRecord:
    d = obj(value, "value unit availability reason_code")
    raw = d["value"]
    if raw is None:
        parsed: int | float | None = None
    elif type(raw) is int:
        parsed = raw
    else:
        parsed = number(raw)
    return MetricRecord(parsed, optional_string(d["unit"]), MetricAvailability(string(d["availability"])),
                        optional_string(d["reason_code"]))


def _metric_tuple(value: object) -> tuple[MetricRecord, ...]:
    return tuple(_metric_record(item) for item in seq(value))


def _annotation(value: object) -> GeneAnnotation:
    d = obj(value, "biotype cancer_census genome_build genome_build_note")
    return GeneAnnotation(optional_string(d["biotype"]),
                          None if d["cancer_census"] is None else boolean(d["cancer_census"]),
                          optional_string(d["genome_build"]), string(d["genome_build_note"]))


def _acquisition_scope(value: object) -> AcquisitionScope:
    d = obj(value, "case_page_size case_batch_size max_cohort_cases discovery_gene_limit "
                   "count_gene_limit candidate_gene_limit expression_file_sample_size")
    return AcquisitionScope(integer(d["case_page_size"]), integer(d["case_batch_size"]),
                            integer(d["max_cohort_cases"]), integer(d["discovery_gene_limit"]),
                            integer(d["count_gene_limit"]), integer(d["candidate_gene_limit"]),
                            integer(d["expression_file_sample_size"]))


def _count_pairs(value: object, name: str) -> tuple[tuple[str, int], ...]:
    result: list[tuple[str, int]] = []
    for item in seq(value):
        pair = seq(item)
        require(len(pair) == 2, f"{name} entries must be pairs")
        result.append((string(pair[0]), integer(pair[1])))
    return tuple(result)


def _sample_type_counts(value: object) -> tuple[tuple[str, tuple[tuple[str, int], ...]], ...]:
    result: list[tuple[str, tuple[tuple[str, int], ...]]] = []
    for item in seq(value):
        pair = seq(item)
        require(len(pair) == 2, "sample type counts must be project/count pairs")
        result.append((string(pair[0]), _count_pairs(pair[1], "sample type counts")))
    return tuple(result)


def _research_state(value: object) -> ResearchState:
    d = obj(value, "spec_id domain cohort project_id cohort_selection_rule gene_selection_rule "
                   "examined_case_frame acquisition modalities programs projects workflows sample_types "
                   "sample_type_counts comparability_statuses within_cohort_status within_cohort_reason "
                   "cross_project_status cross_project_reason")
    return ResearchState(
        string(d["spec_id"]), string(d["domain"]), string(d["cohort"]), string(d["project_id"]),
        string(d["cohort_selection_rule"]), string(d["gene_selection_rule"]), string(d["examined_case_frame"]),
        _acquisition_scope(d["acquisition"]), string_tuple(d["modalities"]), string_tuple(d["programs"]),
        string_tuple(d["projects"]), string_tuple(d["workflows"]), string_tuple(d["sample_types"]),
        _sample_type_counts(d["sample_type_counts"]), string_tuple(d["comparability_statuses"]),
        string(d["within_cohort_status"]), string(d["within_cohort_reason"]),
        string(d["cross_project_status"]), string(d["cross_project_reason"]),
    )


def _population_record(value: object) -> PopulationRecord:
    d = obj(value, "population_id frame program provider_reported_cases frame_hash workflows sample_types "
                   "selection_method selection_version harmonization_context excluded_counts")
    return PopulationRecord(
        string(d["population_id"]), _frame(d["frame"]), optional_string(d["program"]),
        None if d["provider_reported_cases"] is None else integer(d["provider_reported_cases"]),
        string(d["frame_hash"]), string_tuple(d["workflows"]),
        _count_pairs(d["sample_types"], "population sample types"),
        string(d["selection_method"]), string(d["selection_version"]), string(d["harmonization_context"]),
        _count_pairs(d["excluded_counts"], "excluded counts"),
    )


def _provider_discovery(value: object) -> ProviderDiscoveryMetadata:
    d = obj(value, "rank score lane_id note")
    return ProviderDiscoveryMetadata(integer(d["rank"]),
                                     None if d["score"] is None else number(d["score"]),
                                     string(d["lane_id"]), string(d["note"]))


def _provider_expression(value: object) -> ProviderExpressionSummary:
    d = obj(value, "median stddev source estimator_note unavailable_reason")
    return ProviderExpressionSummary(
        None if d["median"] is None else number(d["median"]),
        None if d["stddev"] is None else number(d["stddev"]),
        string(d["source"]), string(d["estimator_note"]), optional_string(d["unavailable_reason"]),
    )


def _project_state(value: object) -> ProjectState:
    d = obj(value, "population mutation expression provider_expression discovery cnv")
    return ProjectState(
        _population_record(d["population"]), _mutation(d["mutation"]), _expression(d["expression"]),
        None if d["provider_expression"] is None else _provider_expression(d["provider_expression"]),
        None if d["discovery"] is None else _provider_discovery(d["discovery"]),
        _cnv(d["cnv"]),
    )


def _tested_context(value: object) -> TestedContext:
    d = obj(value, "examined_genes_hash examined_genes_n rank_in_lane selection_rule selection_bias "
                   "discovered_in_project_count selection_artifact_id")
    return TestedContext(string(d["examined_genes_hash"]), integer(d["examined_genes_n"]),
                         integer(d["rank_in_lane"]), string(d["selection_rule"]), string(d["selection_bias"]),
                         integer(d["discovered_in_project_count"]), optional_string(d["selection_artifact_id"]))


def _cross_project(value: object) -> CrossProjectSummary:
    d = obj(value, "projects_with_mutation_observation projects_with_expression_observation "
                   "affected_case_total top_project_share expression_median_min expression_median_max "
                   "coverage_imbalance dominance_definition coverage_imbalance_definition direction "
                   "comparability_status notes")
    return CrossProjectSummary(
        integer(d["projects_with_mutation_observation"]), integer(d["projects_with_expression_observation"]),
        _metric_record(d["affected_case_total"]), _metric_record(d["top_project_share"]),
        _metric_record(d["expression_median_min"]), _metric_record(d["expression_median_max"]),
        boolean(d["coverage_imbalance"]), string(d["dominance_definition"]),
        string(d["coverage_imbalance_definition"]), string(d["direction"]),
        string(d["comparability_status"]), string_tuple(d["notes"]),
    )


# ------------------------------------------------------------ evidence readers


def _check(value: object) -> EvidenceCheck:
    d = obj(value, "check_id method_id method_version outcome claim input_hashes reason n_effective "
                   "observed expected notes limitations missing_count missing_reason")
    return EvidenceCheck(
        string(d["check_id"]), string(d["method_id"]), string(d["method_version"]),
        CheckOutcome(string(d["outcome"])), string(d["claim"]), string_tuple(d["input_hashes"]),
        optional_string(d["reason"]), None if d["n_effective"] is None else integer(d["n_effective"]),
        canonical_bytes(d["observed"]), canonical_bytes(d["expected"]), string_tuple(d["notes"]),
        string_tuple(d["limitations"]), integer(d["missing_count"]), optional_string(d["missing_reason"]),
    )


def _baseline_observation(value: object) -> BaselineObservation:
    d = obj(value, "method_id method_version observed availability n_effective "
                   "missingness_count missingness_reason notes limitations")
    return BaselineObservation(
        string(d["method_id"]), string(d["method_version"]), canonical_bytes(d["observed"]),
        string(d["availability"]), None if d["n_effective"] is None else integer(d["n_effective"]),
        None if d["missingness_count"] is None else integer(d["missingness_count"]),
        optional_string(d["missingness_reason"]),
        string_tuple(d["notes"]), string_tuple(d["limitations"]),
    )


def _measured_observation(value: object) -> MeasuredObservation:
    d = obj(value, "method_id method_version evidence_kind observed availability n_effective "
                   "population_hash reason notes limitations")
    return MeasuredObservation(
        string(d["method_id"]), string(d["method_version"]), string(d["evidence_kind"]),
        canonical_bytes(d["observed"]), string(d["availability"]),
        None if d["n_effective"] is None else integer(d["n_effective"]),
        string(d["population_hash"]), optional_string(d["reason"]),
        string_tuple(d["notes"]), string_tuple(d["limitations"]),
    )


def _action(value: object) -> ActionRef | None:
    if value is None:
        return None
    d = obj(value, "action_id version")
    return ActionRef(string(d["action_id"]), string(d["version"]))


def _source_state_binding(value: object) -> SourceStateBinding:
    d = obj(value, "state_id state_identity_hash state_artifact_id state_artifact_sha256")
    return SourceStateBinding(string(d["state_id"]), string(d["state_identity_hash"]),
                              string(d["state_artifact_id"]), string(d["state_artifact_sha256"]))


def _research_puzzle(value: object) -> ResearchPuzzle:
    d = obj(value, "origin question interpretation proposed_action_ids")
    return ResearchPuzzle(string(d["origin"]), string(d["question"]), string(d["interpretation"]),
                          string_tuple(d["proposed_action_ids"]))


def _project_evidence_row(value: object) -> ProjectEvidenceRow:
    d = obj(value, "project_id affected_case_count examined_cases project_case_with_ssm "
                   "cases_with_expression missing_measurements")
    return ProjectEvidenceRow(string(d["project_id"]), _metric_record(d["affected_case_count"]),
                              _metric_record(d["examined_cases"]), _metric_record(d["project_case_with_ssm"]),
                              _metric_record(d["cases_with_expression"]),
                              _metric_record(d["missing_measurements"]))


def _missing_evidence(value: object) -> MissingEvidence:
    d = obj(value, "needed_evidence availability reason")
    return MissingEvidence(string(d["needed_evidence"]), MetricAvailability(string(d["availability"])),
                           optional_string(d["reason"]))


def _input_artifact(value: object) -> InputArtifactRef:
    d = obj(value, "kind ref sha256 verified")
    return InputArtifactRef(string(d["kind"]), optional_string(d["ref"]),
                            optional_string(d["sha256"]), boolean(d["verified"]))


def _evidence_provenance(value: object) -> EvidenceProvenance:
    d = obj(value, "gdc_release sources methods environment_hash action_registry_version "
                   "selection_artifact_sha256 input_artifacts")
    return EvidenceProvenance(
        string(d["gdc_release"]), _sources(d["sources"]),
        tuple(_method_identity(item) for item in seq(d["methods"])), string(d["environment_hash"]),
        string(d["action_registry_version"]), string(d["selection_artifact_sha256"]),
        tuple(_input_artifact(item) for item in seq(d["input_artifacts"])),
    )


# -------------------------------------------------------------------- identity


def _jsonable(value: object) -> object:
    """Convert retained boundary bytes into their decoded JSON form for identity/serialization."""
    if isinstance(value, bytes):
        return decode(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _strip_unset_source_fields(value: object) -> object:
    """Drop unset provenance fields so an unannotated source keeps its historical identity."""
    if isinstance(value, dict):
        if {"endpoint", "request_hash", "response_hash"} <= set(value):
            for key in _SOURCE_OPTIONAL_FIELDS:
                if value.get(key) is None:
                    value.pop(key, None)
        return {key: _strip_unset_source_fields(item) for key, item in list(value.items())}
    if isinstance(value, (list, tuple)):
        return [_strip_unset_source_fields(item) for item in value]
    return value


def _state_identity_payload(state: StatisticalState) -> dict[str, object]:
    payload = _strip_unset_source_fields(_jsonable(asdict(state)))
    assert isinstance(payload, dict)
    # Operational attempt/cache/artifact links and provider ranking metadata are
    # not scientific truth and never contribute to identity.
    payload.pop("operational_sources")
    if payload.get("nominations") == []:
        payload.pop("nominations", None)
    if payload.get("evidence_level") == "MEASURED":
        payload.pop("evidence_level", None)
    tested_context = payload["tested_context"]
    if isinstance(tested_context, dict):
        tested_context.pop("selection_artifact_id", None)
    projects = payload["projects"]
    if isinstance(projects, list):
        for project in projects:
            if isinstance(project, dict):
                project["discovery"] = None
    return payload


def _evidence_identity_payload(state: EvidenceState) -> dict[str, object]:
    payload = _strip_unset_source_fields(_jsonable(asdict(state)))
    assert isinstance(payload, dict)
    # The revision's scientific identity is its content: the accepted state's
    # identity hash, parent identity, revision index, checks and copied evidence.
    # Source state ids and input artifact ids are operational and never enter it.
    source = payload["source_state"]
    if isinstance(source, dict):
        source.pop("state_artifact_id", None)
        source.pop("state_artifact_sha256", None)
        source.pop("state_id", None)
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        for artifact in provenance.get("input_artifacts", []):
            if isinstance(artifact, dict):
                artifact["ref"] = None
    if payload.get("measured_observations") == []:
        payload.pop("measured_observations", None)
    return payload


def state_identity(state: StatisticalState) -> str:
    return digest({"schema_version": STATE_SCHEMA_VERSION, "kind": "STATISTICAL_STATE",
                   **_state_identity_payload(state)})


def evidence_identity(state: EvidenceState) -> str:
    return digest({"schema_version": EVIDENCE_SCHEMA_VERSION, "kind": "EVIDENCE_STATE",
                   **_evidence_identity_payload(state)})


# ---------------------------------------------------------------- serialization


def write_state(state: StatisticalState) -> bytes:
    payload = _jsonable(asdict(state))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": STATE_SCHEMA_VERSION, "kind": "STATISTICAL_STATE",
                            **payload, "state_hash": state_identity(state)})


def write_evidence(state: EvidenceState) -> bytes:
    payload = _jsonable(asdict(state))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": EVIDENCE_SCHEMA_VERSION, "kind": "EVIDENCE_STATE",
                            **payload, "evidence_hash": evidence_identity(state)})


def _binding(actual: str, stored: object, expected: str | None) -> None:
    stored_hash = string(stored)
    sha256(stored_hash, "stored scientific hash")
    require(actual == stored_hash, "stored scientific identity mismatch")
    if expected is not None:
        sha256(expected, "expected scientific hash")
        require(actual == expected, "expected scientific identity mismatch")


def _unsupported(record: dict[str, object], version: int, kind: str) -> None:
    if record.get("schema_version") != version:
        raise ContractError("unsupported scientific schema version", "UNSUPPORTED_SCHEMA_VERSION")
    if record.get("kind") != kind:
        raise ContractError("wrong artifact kind", "UNSUPPORTED_SCHEMA_VERSION")


def read_state(data: bytes, *, expected_hash: str | None = None) -> StatisticalState:
    try:
        d = decode(data)
        _unsupported(d, STATE_SCHEMA_VERSION, "STATISTICAL_STATE")
        required = set(
            "schema_version kind entity annotation research universe tested_context projects "
            "cross_project quality warnings missingness methods environment_hash sources "
            "operational_sources state_hash".split())
        allowed = required | {"nominations", "evidence_level"}
        require(set(d) <= allowed, "state carries unexpected fields")
        require(set(d) >= required, "state is missing required fields")
        state = StatisticalState(
            _entity(d["entity"]), _annotation(d["annotation"]), _research_state(d["research"]),
            _universe(d["universe"]), _tested_context(d["tested_context"]),
            tuple(_project_state(item) for item in seq(d["projects"])), _cross_project(d["cross_project"]),
            _quality(d["quality"]), string_tuple(d["warnings"]), string_tuple(d["missingness"]),
            tuple(_method_identity(item) for item in seq(d["methods"])), string(d["environment_hash"]),
            _sources(d["sources"]),
            tuple(_operational_source(item) for item in seq(d["operational_sources"])),
            tuple(_string_string_pair(item) for item in seq(d.get("nominations", []))),
            "MEASURED" if "evidence_level" not in d else string(d["evidence_level"]),
        )
        _binding(state_identity(state), d["state_hash"], expected_hash)
        return state
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid statistical state") from exc


def read_evidence(data: bytes, *, expected_hash: str | None = None) -> EvidenceState:
    try:
        d = decode(data)
        _unsupported(d, EVIDENCE_SCHEMA_VERSION, "EVIDENCE_STATE")
        required = set(
            "schema_version kind entity accepted_state_hash source_state parent_evidence_hash "
            "revision_index action puzzle checks baseline_observations project_evidence "
            "missing_evidence quality warnings provenance evidence_hash".split())
        allowed = required | {"measured_observations"}
        require(set(d) <= allowed, "evidence state carries unexpected fields")
        require(set(d) >= required, "evidence state is missing required fields")
        state = EvidenceState(
            _entity(d["entity"]), string(d["accepted_state_hash"]), _source_state_binding(d["source_state"]),
            optional_string(d["parent_evidence_hash"]), integer(d["revision_index"]), _action(d["action"]),
            None if d["puzzle"] is None else _research_puzzle(d["puzzle"]),
            tuple(_check(item) for item in seq(d["checks"])),
            tuple(_baseline_observation(item) for item in seq(d["baseline_observations"])),
            tuple(_project_evidence_row(item) for item in seq(d["project_evidence"])),
            tuple(_missing_evidence(item) for item in seq(d["missing_evidence"])),
            _quality(d["quality"]), string_tuple(d["warnings"]), _evidence_provenance(d["provenance"]),
            tuple(_measured_observation(item) for item in seq(d.get("measured_observations", []))),
        )
        _binding(evidence_identity(state), d["evidence_hash"], expected_hash)
        return state
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid evidence state") from exc


# -------------------------------------------------------------- discovery codec


def discovery_identity(result: MutationDiscoveryResult) -> str:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    # Operational attempt/cache/artifact links never contribute to identity.
    payload.pop("sources")
    for entry in payload.get("entries", []):
        if isinstance(entry, dict) and entry.get("descriptive") is None:
            entry.pop("descriptive", None)
    return digest({"schema_version": DISCOVERY_SCHEMA_VERSION, "kind": "MUTATION_DISCOVERY_RESULT",
                   **payload})


def write_discovery(result: MutationDiscoveryResult) -> bytes:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": DISCOVERY_SCHEMA_VERSION,
                            "kind": "MUTATION_DISCOVERY_RESULT", **payload,
                            "discovery_hash": discovery_identity(result)})


def read_discovery(data: bytes, *, expected_hash: str | None = None) -> MutationDiscoveryResult:
    try:
        d = decode(data)
        _unsupported(d, DISCOVERY_SCHEMA_VERSION, "MUTATION_DISCOVERY_RESULT")
        obj(d, "schema_version kind spec_id cohort_id project_id release discovery universe reducer "
               "entries survivor_ids sources warnings limitations comparator discovery_hash")
        result = MutationDiscoveryResult(
            string(d["spec_id"]), string(d["cohort_id"]), string(d["project_id"]), string(d["release"]),
            _discovery_spec(d["discovery"]), _universe(d["universe"]), _method_identity(d["reducer"]),
            tuple(_entry(item) for item in seq(d["entries"])), string_tuple(d["survivor_ids"]),
            tuple(_operational_source(item) for item in seq(d["sources"])),
            string_tuple(d["warnings"]), string_tuple(d["limitations"]), _comparator(d["comparator"]),
        )
        _binding(discovery_identity(result), d["discovery_hash"], expected_hash)
        return result
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid mutation discovery result") from exc


# --------------------------------------------------- expression discovery codec


def _expression_discovery_spec(value: object) -> ExpressionDiscoverySpec:
    d = obj(value, "selection_rule gene_batch_size minimum_tail_n quantile_rule iqr_multiplier "
                   "input_unit transform")
    return ExpressionDiscoverySpec(
        string(d["selection_rule"]), integer(d["gene_batch_size"]),
        integer(d["minimum_tail_n"]), string(d["quantile_rule"]),
        number(d["iqr_multiplier"]), string(d["input_unit"]), string(d["transform"]),
    )


def _tail_descriptor(value: object) -> ExpressionTailDescriptor:
    d = obj(value, "availability reason q1 q3 lower_fence upper_fence lower_case_ids "
                   "upper_case_ids valid_n method")

    def optional_number(raw: object) -> float | None:
        return None if raw is None else number(raw)

    return ExpressionTailDescriptor(
        MetricAvailability(string(d["availability"])), optional_string(d["reason"]),
        optional_number(d["q1"]), optional_number(d["q3"]),
        optional_number(d["lower_fence"]), optional_number(d["upper_fence"]),
        string_tuple(d["lower_case_ids"]), string_tuple(d["upper_case_ids"]),
        integer(d["valid_n"]), _method_identity(d["method"]),
    )


def _expression_entry(value: object) -> ExpressionDiscoveryEntry:
    d = obj(value)
    required = {"entity", "outcome", "tail"}
    allowed = required | {"disposition", "disposition_reason", "review_trigger"}
    require(set(d) <= allowed, "expression entry carries unexpected fields")
    require(set(d) >= required, "expression entry is missing required fields")
    disposition = d.get("disposition")
    return ExpressionDiscoveryEntry(
        _entity(d["entity"]), _expression(d["outcome"]), _tail_descriptor(d["tail"]),
        None if disposition is None else ExpressionDisposition(string(disposition)),
        optional_string(d.get("disposition_reason")),
        optional_string(d.get("review_trigger")),
    )


def expression_discovery_identity(result: ExpressionDiscoveryResult) -> str:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    payload.pop("sources")
    if payload.get("workflow_file_counts") == []:
        payload.pop("workflow_file_counts", None)
    if payload.get("workflow_coverage_complete") is True:
        payload.pop("workflow_coverage_complete", None)
    if payload.get("retained_ids") == []:
        payload.pop("retained_ids", None)
    if payload.get("jev_review_ids") == []:
        payload.pop("jev_review_ids", None)
    for entry in payload.get("entries", []):
        if isinstance(entry, dict) and entry.get("disposition") is None:
            for key in ("disposition", "disposition_reason", "review_trigger"):
                entry.pop(key, None)
    return digest({"schema_version": EXPRESSION_DISCOVERY_SCHEMA_VERSION,
                   "kind": "EXPRESSION_DISCOVERY_RESULT", **payload})


def write_expression_discovery(result: ExpressionDiscoveryResult) -> bytes:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": EXPRESSION_DISCOVERY_SCHEMA_VERSION,
                            "kind": "EXPRESSION_DISCOVERY_RESULT", **payload,
                            "expression_discovery_hash": expression_discovery_identity(result)})


def read_expression_discovery(
    data: bytes, *, expected_hash: str | None = None,
) -> ExpressionDiscoveryResult:
    try:
        d = decode(data)
        _unsupported(d, EXPRESSION_DISCOVERY_SCHEMA_VERSION, "EXPRESSION_DISCOVERY_RESULT")
        required = set(
            "schema_version kind spec_id cohort_id project_id release expression_discovery "
            "universe population entries workflows strategies sources warnings limitations "
            "request_plan_max expression_discovery_hash".split())
        allowed = required | {"workflow_file_counts", "workflow_coverage_complete",
                              "retained_ids", "jev_review_ids"}
        require(set(d) <= allowed, "expression discovery carries unexpected fields")
        require(set(d) >= required, "expression discovery is missing required fields")
        result = ExpressionDiscoveryResult(
            string(d["spec_id"]), string(d["cohort_id"]), string(d["project_id"]),
            string(d["release"]), _expression_discovery_spec(d["expression_discovery"]),
            _universe(d["universe"]), _frame(d["population"]),
            tuple(_expression_entry(item) for item in seq(d["entries"])),
            string_tuple(d["workflows"]), string_tuple(d["strategies"]),
            tuple(_operational_source(item) for item in seq(d["sources"])),
            string_tuple(d["warnings"]), string_tuple(d["limitations"]),
            integer(d["request_plan_max"]),
            _string_int_pairs(d.get("workflow_file_counts", [])),
            True if "workflow_coverage_complete" not in d else boolean(d["workflow_coverage_complete"]),
            string_tuple(d["retained_ids"]) if "retained_ids" in d else (),
            string_tuple(d["jev_review_ids"]) if "jev_review_ids" in d else (),
        )
        _binding(expression_discovery_identity(result), d["expression_discovery_hash"], expected_hash)
        return result
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid expression discovery result") from exc


# ---------------------------------------------------------- CNV discovery codec


def _cnv_discovery_spec(value: object) -> CnvDiscoverySpec:
    d = obj(value, "selection_rule page_size max_pages_per_gene max_genes category_field")
    return CnvDiscoverySpec(
        string(d["selection_rule"]), integer(d["page_size"]),
        integer(d["max_pages_per_gene"]), integer(d["max_genes"]),
        string(d["category_field"]),
    )


def _cnv_category_summary(value: object) -> CnvCategorySummary:
    d = obj(value, "raw_category category case_ids")
    return CnvCategorySummary(
        string(d["raw_category"]), CnvCategory(string(d["category"])),
        string_tuple(d["case_ids"]),
    )


def _cnv_discovery_entry(value: object) -> CnvDiscoveryEntry:
    d = obj(value, "entity outcome categories conflicting_case_ids callers "
                   "missing_sample_occurrence_ids")
    outcome = _cnv(d["outcome"])
    if not isinstance(outcome, (CnvOccurrenceResult, UnavailableLane)):
        raise ContractError("legacy CNV discovery entry carries an occurrence outcome")
    return CnvDiscoveryEntry(
        _entity(d["entity"]), outcome,
        tuple(_cnv_category_summary(item) for item in seq(d["categories"])),
        string_tuple(d["conflicting_case_ids"]), string_tuple(d["callers"]),
        string_tuple(d["missing_sample_occurrence_ids"]),
    )


def cnv_discovery_identity(result: CnvDiscoveryResult) -> str:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    payload.pop("sources")
    return digest({"schema_version": CNV_DISCOVERY_SCHEMA_VERSION,
                   "kind": "CNV_DISCOVERY_RESULT", **payload})


def write_cnv_discovery(result: CnvDiscoveryResult) -> bytes:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": CNV_DISCOVERY_SCHEMA_VERSION,
                            "kind": "CNV_DISCOVERY_RESULT", **payload,
                            "cnv_discovery_hash": cnv_discovery_identity(result)})


def read_cnv_discovery(data: bytes, *, expected_hash: str | None = None) -> CnvDiscoveryResult:
    try:
        d = decode(data)
        _unsupported(d, CNV_DISCOVERY_SCHEMA_VERSION, "CNV_DISCOVERY_RESULT")
        obj(d, "schema_version kind spec_id cohort_id project_id release mutation_discovery_hash "
               "survivor_ids cnv_discovery population summary_method entries sources warnings "
               "limitations request_plan_max cnv_discovery_hash")
        result = CnvDiscoveryResult(
            string(d["spec_id"]), string(d["cohort_id"]), string(d["project_id"]),
            string(d["release"]), string(d["mutation_discovery_hash"]),
            string_tuple(d["survivor_ids"]), _cnv_discovery_spec(d["cnv_discovery"]),
            _frame(d["population"]), _method_identity(d["summary_method"]),
            tuple(_cnv_discovery_entry(item) for item in seq(d["entries"])),
            tuple(_operational_source(item) for item in seq(d["sources"])),
            string_tuple(d["warnings"]), string_tuple(d["limitations"]),
            integer(d["request_plan_max"]),
        )
        _binding(cnv_discovery_identity(result), d["cnv_discovery_hash"], expected_hash)
        return result
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid CNV discovery result") from exc


def _cnv_gene_evidence(value: object) -> CnvGeneEvidence:
    d = obj(value, "gene_id categories callers conflicting_case_ids "
                   "missing_sample_occurrence_ids records")
    return CnvGeneEvidence(
        string(d["gene_id"]),
        tuple(_cnv_category_summary(item) for item in seq(d["categories"])),
        string_tuple(d["callers"]), string_tuple(d["conflicting_case_ids"]),
        string_tuple(d["missing_sample_occurrence_ids"]), integer(d["records"]),
    )


def cnv_shard_identity(evidence: CnvShardEvidence) -> str:
    payload = _jsonable(asdict(evidence))
    assert isinstance(payload, dict)
    payload.pop("sources")
    return digest({"schema_version": CNV_SHARD_EVIDENCE_SCHEMA_VERSION,
                   "kind": "CNV_SHARD_EVIDENCE", **payload})


def write_cnv_shard_evidence(evidence: CnvShardEvidence) -> bytes:
    payload = _jsonable(asdict(evidence))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": CNV_SHARD_EVIDENCE_SCHEMA_VERSION,
                            "kind": "CNV_SHARD_EVIDENCE", **payload,
                            "shard_hash": cnv_shard_identity(evidence)})


def read_cnv_shard_evidence(data: bytes, *, expected_hash: str | None = None) -> CnvShardEvidence:
    try:
        d = decode(data)
        _unsupported(d, CNV_SHARD_EVIDENCE_SCHEMA_VERSION, "CNV_SHARD_EVIDENCE")
        obj(d, "schema_version kind shard_index case_ids project_id release genes records "
               "sources warnings shard_hash cohort_case_ids case_shard_size spec_hash")
        evidence = CnvShardEvidence(
            integer(d["shard_index"]), string_tuple(d["case_ids"]), string(d["project_id"]),
            string(d["release"]), tuple(_cnv_gene_evidence(item) for item in seq(d["genes"])),
            integer(d["records"]),
            tuple(_operational_source(item) for item in seq(d["sources"])),
            string_tuple(d["warnings"]),
            string_tuple(d["cohort_case_ids"]), integer(d["case_shard_size"]),
            string(d["spec_hash"]),
        )
        _binding(cnv_shard_identity(evidence), d["shard_hash"], expected_hash)
        return evidence
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid CNV shard evidence") from exc


def _cnv_project_call(value: object) -> CnvProjectCall:
    d = obj(value, "evidence disposition reason review_trigger")
    return CnvProjectCall(
        _cnv_gene_evidence(d["evidence"]), CnvDisposition(string(d["disposition"])),
        string(d["reason"]), optional_string(d["review_trigger"]),
    )


def cnv_project_scan_identity(result: CnvProjectScanResult) -> str:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    payload.pop("sources")
    return digest({"schema_version": CNV_PROJECT_SCAN_SCHEMA_VERSION,
                   "kind": "CNV_PROJECT_SCAN_RESULT", **payload})


def write_cnv_project_scan(result: CnvProjectScanResult) -> bytes:
    payload = _jsonable(asdict(result))
    assert isinstance(payload, dict)
    return canonical_bytes({"schema_version": CNV_PROJECT_SCAN_SCHEMA_VERSION,
                            "kind": "CNV_PROJECT_SCAN_RESULT", **payload,
                            "scan_hash": cnv_project_scan_identity(result)})


def read_cnv_project_scan(data: bytes, *,
                          expected_hash: str | None = None) -> CnvProjectScanResult:
    try:
        d = decode(data)
        _unsupported(d, CNV_PROJECT_SCAN_SCHEMA_VERSION, "CNV_PROJECT_SCAN_RESULT")
        obj(d, "schema_version kind spec_id cohort_id project_id release selection_rule "
               "case_shard_size shard_count summary_method calls sources warnings limitations "
               "scan_hash")
        result = CnvProjectScanResult(
            string(d["spec_id"]), string(d["cohort_id"]), string(d["project_id"]),
            string(d["release"]), string(d["selection_rule"]), integer(d["case_shard_size"]),
            integer(d["shard_count"]), _method_identity(d["summary_method"]),
            tuple(_cnv_project_call(item) for item in seq(d["calls"])),
            tuple(_operational_source(item) for item in seq(d["sources"])),
            string_tuple(d["warnings"]), string_tuple(d["limitations"]),
        )
        _binding(cnv_project_scan_identity(result), d["scan_hash"], expected_hash)
        return result
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid CNV project scan result") from exc
