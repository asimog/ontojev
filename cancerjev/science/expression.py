"""Local expression summaries; normalized values are not raw counts or DE evidence."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from dataclasses import dataclass

from cancerjev.gdc.parsers import (
    ExpressionAvailability,
    ExpressionValues,
    ProviderGene,
    ProviderSelection,
)
from cancerjev.science.errors import ScienceError


@dataclass(frozen=True)
class Log2Summary:
    median: float | None
    sample_sd: float | None
    minimum: float | None
    maximum: float | None
    n_finite: int
    n_missing: int
    n_returned: int
    availability: str


def expression_log2_summary(row: Mapping[str, float | None], *, missing_case_columns: int = 0) -> Log2Summary:
    """Summarize one gene row over the examined case set.

    ``row`` holds only the case columns the provider returned. ``missing_case_columns``
    counts examined cases whose column was not returned at all; those remain visible in
    ``n_missing`` so a fully valid returned subset can never report zero missingness.
    """
    finite: list[float] = []
    missing_cells = 0
    for value in row.values():
        if value is None:
            missing_cells += 1
            continue
        if value < 0:
            raise ScienceError("NEGATIVE_EXPRESSION", f"UQFPKM must be nonnegative, saw {value!r}")
        finite.append(math.log2(value + 1.0))
    missing = missing_cells + max(0, missing_case_columns)
    if not finite:
        return Log2Summary(None, None, None, None, 0, missing, len(row), "INSUFFICIENT")
    median = statistics.median(finite)
    sample_sd = statistics.stdev(finite) if len(finite) >= 2 else None
    if len(finite) < 2:
        availability = "INSUFFICIENT"
    elif missing:
        availability = "PARTIAL"
    else:
        availability = "OBSERVED"
    return Log2Summary(median, sample_sd, min(finite), max(finite), len(finite), missing,
                       len(row), availability)


@dataclass(frozen=True)
class ExpressionObservation:
    project_id: str
    gene_id: str
    cases_with_expression: int | None
    local: Log2Summary | None
    local_availability: str
    availability: str
    returned_case_columns: int | None
    valid_measurements: int | None
    missing_measurements: int | None
    missing_case_ids: tuple[str, ...]
    provider: ProviderGene | None
    provider_unavailable_reason: str | None
    missingness: tuple[str, ...]


def expression_observation(*, project_id: str, gene_id: str, case_ids: tuple[str, ...],
                           coverage: ExpressionAvailability | None, values: ExpressionValues | None,
                           provider: ProviderSelection | None,
                           provider_unavailable_reason: str | None = None) -> ExpressionObservation:
    missingness: list[str] = []
    cases_with_expression = None
    if coverage is not None:
        cases_with_expression = sum(1 for case_id in case_ids if coverage.cases.get(case_id) is True)
        for case_id in case_ids:
            if coverage.cases.get(case_id) is None:
                missingness.append(f"{project_id}: case {case_id} absent from expression availability")
    summary = None
    local_availability = "NOT_ACQUIRED"
    returned = valid = missing = None
    missing_case_ids: tuple[str, ...] = ()
    if values is not None:
        missing_case_ids = tuple(values.missing_case_ids)
        row = values.values.get(gene_id)
        if row is None:
            local_availability = "NOT_OBSERVED"
            returned = valid = 0
            missing = len(case_ids)
            missingness.append(f"{project_id}: gene {gene_id} absent from expression values")
        else:
            summary = expression_log2_summary(row, missing_case_columns=len(missing_case_ids))
            local_availability = summary.availability
            returned, valid, missing = summary.n_returned, summary.n_finite, summary.n_missing
            if missing:
                missingness.append(
                    f"{project_id}: {missing} of {len(case_ids)} examined cases have no "
                    f"expression value ({len(missing_case_ids)} case column(s) not returned by the provider)"
                )
    provider_gene = None if provider is None else provider.genes.get(gene_id)
    if provider is not None and provider_gene is None:
        missingness.append(
            f"{project_id}: gene {gene_id} absent from provider gene selection "
            "(below provider median threshold or not returned)"
        )
    availability = local_availability
    if local_availability in {"NOT_ACQUIRED", "NOT_OBSERVED"} and provider_gene is not None:
        availability = "PARTIAL"
    return ExpressionObservation(project_id, gene_id, cases_with_expression, summary,
                                 local_availability, availability, returned, valid, missing,
                                 missing_case_ids, provider_gene,
                                 provider_unavailable_reason if provider_gene is None else None,
                                 tuple(missingness))
