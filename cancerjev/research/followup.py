"""One bounded measured follow-up: per-gene canonical occurrence detail.

Acquisition stays in the research layer; the action is deterministic and
network-free. Over-cap, transport or parser failure yields a typed unavailable
observation with its reason, never a truncated claim.
"""

from __future__ import annotations

from typing import Any

from cancerjev.domain.discovery import (
    MUTATION_CANONICAL_COMPOSITION_METHOD_ID,
    MUTATION_CANONICAL_COMPOSITION_VERSION,
    MUTATION_COMPOSITION_LIMITATIONS,
)
from cancerjev.domain.events import canonical_json
from cancerjev.domain.evidence import MeasuredObservation
from cancerjev.gdc.endpoints import ssm_occurrence_gene_page_request
from cancerjev.gdc.parsers import ParserError, parse_ssm_occurrence_page
from cancerjev.gdc.transport import TransportError
from cancerjev.research.acquisition import AcquisitionTransport, response_meta

OCCURRENCE_DETAIL_PAGE_SIZE = 250
OCCURRENCE_DETAIL_MAX_PAGES = 40
OCCURRENCE_DETAIL_EVIDENCE_KIND = "MUTATION_CANONICAL_COMPOSITION"


def _observation(*, population_hash: str, observed: dict[str, Any], availability: str,
                 n_effective: int | None, reason: str | None) -> MeasuredObservation:
    return MeasuredObservation(
        method_id=MUTATION_CANONICAL_COMPOSITION_METHOD_ID,
        method_version=MUTATION_CANONICAL_COMPOSITION_VERSION,
        evidence_kind=OCCURRENCE_DETAIL_EVIDENCE_KIND,
        observed=canonical_json(observed),
        availability=availability,
        n_effective=n_effective,
        population_hash=population_hash,
        reason=reason,
        limitations=MUTATION_COMPOSITION_LIMITATIONS,
    )


def unavailable_observation(*, gene_id: str, population_hash: str,
                            reason: str) -> MeasuredObservation:
    """Typed unavailable detail observation; never a truncated or fabricated claim."""
    return _observation(
        population_hash=population_hash,
        observed={"gene_id": gene_id, "reason": reason},
        availability="NOT_OBSERVED", n_effective=None, reason=reason)


def measure_occurrence_detail(
    transport: AcquisitionTransport,
    *,
    project_id: str,
    gene_id: str,
    release: str | None,
    population_hash: str,
    page_size: int = OCCURRENCE_DETAIL_PAGE_SIZE,
    max_pages: int = OCCURRENCE_DETAIL_MAX_PAGES,
) -> MeasuredObservation:
    """Read the complete bounded gene detail pages and compose canonical counts."""
    composition: dict[str, int] = {}
    transcripts: set[str] = set()
    records = 0
    pages_read = 0
    total: int | None = None
    offset = 0
    previous_id: str | None = None
    while True:
        if pages_read >= max_pages:
            return unavailable_observation(gene_id=gene_id, population_hash=population_hash,
                                           reason="OCCURRENCE_DETAIL_PAGE_CAP_REACHED")
        try:
            response = transport.request(
                ssm_occurrence_gene_page_request(project_id, gene_id, offset=offset, size=page_size))
            page = parse_ssm_occurrence_page(
                response.body, response_meta(response, release), expected_project=project_id,
                expected_offset=offset, expected_size=page_size)
        except (ParserError, TransportError) as exc:
            return _observation(
                population_hash=population_hash,
                observed={"gene_id": gene_id, "error_code": exc.code},
                availability="NOT_OBSERVED", n_effective=None, reason=str(exc.code))
        pages_read += 1
        if pages_read > max_pages:
            return _observation(
                population_hash=population_hash,
                observed={"gene_id": gene_id, "pages_read": pages_read,
                          "page_cap": max_pages},
                availability="NOT_OBSERVED", n_effective=None,
                reason="OCCURRENCE_DETAIL_PAGE_CAP_REACHED")
        if total is None:
            total = page.total
        elif page.total != total:
            return _observation(
                population_hash=population_hash,
                observed={"gene_id": gene_id, "total": total, "changed_to": page.total},
                availability="NOT_OBSERVED", n_effective=None,
                reason="OCCURRENCE_DETAIL_TOTAL_CHANGED")
        for record in page.records:
            if previous_id is not None and record.occurrence_id <= previous_id:
                return unavailable_observation(gene_id=gene_id, population_hash=population_hash,
                                               reason="OCCURRENCE_DETAIL_ORDER_VIOLATION")
            if gene_id not in record.gene_ids:
                return unavailable_observation(gene_id=gene_id, population_hash=population_hash,
                                               reason="OCCURRENCE_DETAIL_UNEXPECTED_GENE")
            previous_id = record.occurrence_id
            records += 1
            rows = tuple(row for row in record.canonical_rows if row.gene_id == gene_id)
            terms = {row.consequence for row in rows if row.consequence}
            for term in sorted(terms):
                composition[term] = composition.get(term, 0) + 1
            for row in rows:
                if row.transcript_id is not None:
                    transcripts.add(row.transcript_id)
        offset += page.count
        if offset >= page.total or page.count == 0:
            break
    observed = {
        "gene_id": gene_id,
        "consequence_composition": [list(item) for item in sorted(composition.items())],
        "canonical_transcript_n": len(transcripts),
        "occurrence_records": records,
        "pages_read": pages_read,
        "total_occurrences": total or 0,
    }
    return _observation(
        population_hash=population_hash, observed=observed, availability="OBSERVED",
        n_effective=records, reason=None)
