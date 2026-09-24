"""Validated historical boundary snapshots, never relabelled as v3 science.

Legacy units/statuses and serialized fields retain their original meaning. The
opaque original bytes are for archival replay; typed summaries are not a v3
conversion. These readers do not validate storage paths or database bindings.
"""

from dataclasses import dataclass
from typing import Literal

from cancerjev.domain._json import (
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
from cancerjev.domain.evidence import CheckSummary
from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.domain.measurements import ContractError, EntityRef, count, require, sha256


@dataclass(frozen=True)
class LegacyMetric:
    path: str
    value: float | int | None
    unit: str | None
    availability: str
    reason: str | None


@dataclass(frozen=True)
class LegacyPopulation:
    population_id: str
    project_id: str
    examined_n: int
    eligible_n: int | None
    case_set_hash: str


@dataclass(frozen=True)
class LegacyArtifact:
    schema_version: int
    kind: Literal["STATISTICAL_STATE", "EVIDENCE_STATE"]
    scientific_hash: str
    gene_id: str
    metrics: tuple[LegacyMetric, ...]
    populations: tuple[LegacyPopulation, ...]
    check_summary: CheckSummary | None
    original_bytes: bytes

    def boundary_representation(self) -> dict[str, object]:
        """A fresh presentation/replay copy; not a typed-domain input."""
        return decode(self.original_bytes)


def _nonnegative(value: object) -> int:
    result = integer(value)
    count(result, "historical count")
    return result


def _metric(value: object, path: str) -> LegacyMetric:
    d = obj(value)
    availability = string(d["availability"])
    require(availability in {"OBSERVED", "NOT_OBSERVED", "NOT_ACQUIRED", "NOT_APPLICABLE",
                             "PARTIAL", "UNAVAILABLE", "INSUFFICIENT", "INCOMPATIBLE", "INVALID"},
            f"unknown historical availability at {path}")
    unit = optional_string(d["unit"])
    raw = d["value"]
    parsed: float | int | None = None
    if availability == "OBSERVED":
        require(unit is not None, f"observed metric missing unit at {path}")
        parsed = number(raw)
        if unit in {"cases", "count"}:
            require(parsed >= 0 and parsed.is_integer(), f"invalid historical count at {path}")
            # Preserve integer versus float spelling in original_bytes, not by
            # forcing legacy values through the v3 unit/measurement contracts.
            parsed = raw if type(raw) is int else int(parsed)
    else:
        require(raw is None, f"unavailable metric has a value at {path}")
    return LegacyMetric(path, parsed, unit, availability, optional_string(d.get("reason_code")))


def _metrics(value: object, path: str, keys: str) -> tuple[LegacyMetric, ...]:
    d = obj(value)
    return tuple(_metric(d[key], f"{path}.{key}") for key in keys.split())


def _provenance(value: object, *, evidence: bool = False) -> None:
    d = obj(value)
    string(d["gdc_release"])
    string(d["environment_hash"])
    sources = seq(d["sources"])
    require(bool(sources), "live evidence requires sources")
    for item in sources:
        source = obj(item)
        for key in ("endpoint", "normalized_request_hash", "response_sha256", "parser_version",
                    "completeness", "source_release"):
            string(source[key])
    for item in seq(d["methods"]):
        method = obj(item)
        string(method["method_id"])
        string(method["version"])
    if evidence:
        string(d["action_registry_version"])
        string(d["selection_artifact_sha256"])


def _identity(d: dict[str, object], *, evidence: bool, expected_hash: str | None) -> str:
    projected = evidence_state_identity_payload(d) if evidence else statistical_state_identity_payload(d)
    actual = content_hash(projected)
    key = "evidence_hash" if evidence else "state_hash"
    if key in d:
        require(string(d[key]) == actual, "historical stored scientific identity mismatch")
    if expected_hash is not None:
        sha256(expected_hash, "expected historical hash")
        require(actual == expected_hash, "historical expected scientific identity mismatch")
    return actual


def _fixture(d: dict[str, object]) -> str:
    string(d["fixture_notice"])
    gene_id = string(obj(d["entity"])["gene_id"])
    require(gene_id.startswith("SYNTHETIC-"), "v1 is a synthetic fixture, not live evidence")
    require(not seq(obj(d["provenance"])["sources"]), "fixture cannot contain live sources")
    return gene_id


def read_legacy_state(data: bytes, *, expected_hash: str | None = None) -> LegacyArtifact:
    try:
        d = decode(data)
        schema = version(d)
        require(schema in (1, 2), "legacy state reader requires v1/v2")
        metrics: list[LegacyMetric] = []
        populations: list[LegacyPopulation] = []
        string(d["state_id"])
        string(d["run_id"])
        if schema == 1:
            gene_id = _fixture(d)
            pattern = obj(d["pattern"])
            metrics.append(LegacyMetric("pattern.effect_like_descriptive_value",
                                       number(pattern["effect_like_descriptive_value"]), string(pattern["unit"]),
                                       string(obj(d["quality"])["availability"]), None))
            require(metrics[0].availability == "OBSERVED", "fixture pattern must be observed")
            string_tuple(obj(d["scope"])["projects"])
            obj(d["tested_context"])
        else:
            require(d["mode"] == "LIVE", "v2 requires LIVE mode")
            gene_id = string(obj(d["entity"])["gene_id"])
            EntityRef(gene_id, None, string(obj(d["provenance"])["gdc_release"]))
            projects = string_tuple(obj(d["scope"])["projects"])
            require(bool(projects) and len(set(projects)) == len(projects), "invalid historical project roster")
            for item in seq(d["populations"]):
                p = obj(item)
                examined = _nonnegative(p["examined_n"])
                eligible = None if p["eligible_n"] is None else _nonnegative(p["eligible_n"])
                require(eligible is None or examined <= eligible, "examined exceeds historical eligible population")
                populations.append(LegacyPopulation(string(p["population_id"]), string(p["project"]),
                                                    examined, eligible, string(p["case_set_hash"])))
                for excluded in obj(p["excluded_counts_by_reason"]).values():
                    _nonnegative(excluded)
            require(tuple(p.project_id for p in populations) == tuple(sorted(projects)), "population/project roster mismatch")
            require(len({p.population_id for p in populations}) == len(populations), "duplicate populations")
            by_id = {p.population_id: p for p in populations}
            for lane in ("mutation", "expression"):
                section = obj(d[lane])
                rows = tuple(obj(row) for row in seq(section["project_results"]))
                require(tuple(string(r["project_id"]) for r in rows) == tuple(sorted(projects)), "lane/project roster mismatch")
                for row in rows:
                    population = by_id[string(row["population_id"])]
                    require(population.project_id == row["project_id"], "lane/population binding mismatch")
                    path = f"{lane}.{population.project_id}"
                    if lane == "mutation":
                        parsed = _metrics(row, path, "examined_cases affected_case_count project_case_with_ssm project_case_count")
                        require(parsed[0].value == population.examined_n, "examined metric/population mismatch")
                        for count_metric in parsed[1:]:
                            require(count_metric.value is None or population.eligible_n is None
                                    or count_metric.value <= population.eligible_n,
                                    "count exceeds historical project population")
                        metrics.extend(parsed)
                    else:
                        metrics.extend(_metrics(row["coverage"], path + ".coverage",
                                                "examined_cases assay_available_cases cases_with_expression returned_case_columns valid_measurements missing_measurements"))
                        if row["local"] is not None:
                            local = obj(row["local"])
                            metrics.extend(_metrics(local, path + ".local", "median sample_sd minimum maximum n_finite n_missing n_returned n_missing_case_columns"))
                            string_tuple(local["missing_case_ids"])
                        if row["provider"] is not None:
                            metrics.extend(_metrics(row["provider"], path + ".provider", "median stddev"))
                coverage_keys = "case_with_ssm" if lane == "mutation" else "cases_with_expression examined_cases"
                metrics.extend(_metrics(section["coverage"], lane + ".coverage", coverage_keys))
            metrics.extend(_metrics(d["cross_project"], "cross_project",
                                    "affected_case_total top_project_share expression_median_min expression_median_max"))
            quality = obj(d["quality"])
            require(quality["completeness"] in {"COMPLETE", "PARTIAL"}, "invalid historical completeness")
            obj(d["generation"])
            string(obj(d["tested_context"])["examined_genes_hash"])
            _provenance(d["provenance"])
        return LegacyArtifact(schema, "STATISTICAL_STATE", _identity(d, evidence=False, expected_hash=expected_hash),
                              gene_id, tuple(metrics), tuple(populations), None, data)
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid historical statistical state") from exc


def read_legacy_evidence(data: bytes, *, expected_hash: str | None = None) -> LegacyArtifact:
    try:
        d = decode(data)
        schema = version(d)
        require(schema in (1, 2), "legacy evidence reader requires v1/v2")
        for key in ("evidence_state_id", "run_id", "candidate_id"):
            string(d[key])
        iteration = _nonnegative(d["iteration_number"])
        source = obj(d["source_statistical_state"])
        sha256(string(source["state_identity_hash"]), "source state identity")
        metrics: list[LegacyMetric] = []
        observations = tuple(obj(item) for item in seq(d["deterministic_observations"]))
        summary: CheckSummary | None = None
        if schema == 1:
            gene_id = _fixture(d)
            require(iteration in (0, 1), "unknown fixture revision")
            for index, observation in enumerate(observations):
                effect = obj(observation["effect"])
                metrics.append(_metric({**effect, "availability": observation["availability"]}, f"observations.{index}"))
        else:
            require(d["mode"] == "LIVE" and iteration <= 2, "invalid live revision")
            gene_id = string(obj(d["entity"])["gene_id"])
            EntityRef(gene_id, None, string(obj(d["provenance"])["gdc_release"]))
            _provenance(d["provenance"], evidence=True)
            counts = obj(d["quality_and_fragility"])
            summary = CheckSummary(*(_nonnegative(counts[key]) for key in (
                "checks_total", "checks_verified", "checks_contradicted", "checks_not_observed")))
            if iteration == 0:
                require(d["action"] is None and d["previous_evidence_state_id"] is None, "invalid E0 action/parent")
                require(summary.total == 0, "E0 cannot claim completed checks")
                for index, observation in enumerate(observations):
                    observed = obj(observation["observed"])
                    metrics.append(_metric({**observed, "availability": observation["availability"]}, f"observations.{index}"))
            else:
                string(d["previous_evidence_state_id"])
                action = obj(d["action"])
                string(action["action_id"])
                string(action["method_id"])
                string(action["method_version"])
                outcomes = tuple(string(o["outcome"]) for o in observations)
                require(all(o in {"VERIFIED", "CONTRADICTED", "NOT_OBSERVED"} for o in outcomes), "invalid check outcome")
                require(bool(outcomes), "action revision requires checks")
                require(summary == CheckSummary(len(outcomes), outcomes.count("VERIFIED"),
                                                outcomes.count("CONTRADICTED"), outcomes.count("NOT_OBSERVED")),
                        "historical check summary mismatch")
                ids = tuple(string(o["check_id"]) for o in observations)
                require(len(set(ids)) == len(ids), "duplicate checks")
                for observation in observations:
                    require(observation["availability"] == ("NOT_OBSERVED" if observation["outcome"] == "NOT_OBSERVED" else "OBSERVED"),
                            "check outcome/availability mismatch")
                    obj(observation["observed"])
                    obj(observation["expected"])
        for observation in observations:
            string(observation["method_id"])
            string(observation["method_version"])
            if observation["n_effective"] is not None:
                _nonnegative(observation["n_effective"])
            string_tuple(observation["limitations"])
            obj(observation["missingness"])
        for index, item in enumerate(seq(d["project_level_evidence"])):
            row = obj(item)
            string(row["project_id"])
            if schema == 1:
                _nonnegative(row["n"])
                number(row["effect_like_value"])
                require(row["availability"] == "OBSERVED", "fixture project must be observed")
            else:
                metrics.extend(_metrics(row, f"project_level_evidence.{index}",
                                        "affected_case_count examined_cases project_case_with_ssm cases_with_expression missing_measurements"))
        obj(d["research_puzzle"])
        obj(d["cross_project_patterns"])
        seq(d["missing_evidence"])
        return LegacyArtifact(schema, "EVIDENCE_STATE", _identity(d, evidence=True, expected_hash=expected_hash),
                              gene_id, tuple(metrics), (), summary, data)
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ContractError("invalid historical evidence state") from exc
