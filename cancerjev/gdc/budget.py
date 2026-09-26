"""Declared operational policy, separate from scientific cohort/gene scope.

Production requests/pages grow geometrically on demand and are audited. Bytes
never auto-expand: 512 MiB per acquisition shard and 768 MiB per command/run.
Explicit fixed BudgetCaps remain available for replay/contract tests.

A canonical Campaign executes mutation, expression, CNV shards and candidate
follow-ups inside ONE declared Campaign budget: the byte/request ceilings below
are Campaign-global, while the 512 MiB per-acquisition-shard allowance still
applies to every shard. The Campaign ceilings are sized from the measured live
cost of the declared LUAD cohort (one 25-case CNV shard = 817 requests / 107 MB,
complete mutation scan = ~206 MB, expression plan <= 1,400 requests), so a
declared full Campaign fits while an exhausted budget still reports
INCOMPLETE_OR_UNAVAILABLE instead of a smaller complete population.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cancerjev.gdc.endpoints import GDCRequest
    from cancerjev.gdc.transport import BudgetCaps

from cancerjev.domain.events import canonical_json

BUDGET_POLICY_VERSION = "gdc-adaptive-v1"
CAMPAIGN_BUDGET_POLICY_VERSION = "gdc-campaign-v1"
SHARD_DOWNLOAD_BYTES = 512 * 1024 * 1024
RUN_DOWNLOAD_BYTES = 768 * 1024 * 1024
INITIAL_REQUESTS = 150
INITIAL_PAGES = 48
REQUEST_DEFECT_CEILING = 10_000
PAGE_DEFECT_CEILING = 10_000
# Declared Campaign-global ceilings (all lanes and candidate follow-ups share one
# budget object). Non-adaptive so the declared ceiling is exact and auditable.
CAMPAIGN_REQUESTS = 25_000
CAMPAIGN_PAGES_PER_QUERY = 10_000
CAMPAIGN_DOWNLOAD_BYTES = 4 * 1024 * 1024 * 1024


def production_caps(*, per_response_bytes: int, timeout_seconds: float) -> BudgetCaps:
    from cancerjev.gdc.transport import BudgetCaps

    return BudgetCaps(max_requests=INITIAL_REQUESTS, max_bytes=RUN_DOWNLOAD_BYTES,
                      max_pages_per_query=INITIAL_PAGES, max_shard_bytes=SHARD_DOWNLOAD_BYTES,
                      per_response_bytes=per_response_bytes, timeout_seconds=timeout_seconds,
                      adaptive=True)


def campaign_caps(*, per_response_bytes: int, timeout_seconds: float) -> BudgetCaps:
    """One declared Campaign-global budget shared by every lane and follow-up."""
    from cancerjev.gdc.transport import BudgetCaps

    return BudgetCaps(max_requests=CAMPAIGN_REQUESTS, max_bytes=CAMPAIGN_DOWNLOAD_BYTES,
                      max_pages_per_query=CAMPAIGN_PAGES_PER_QUERY,
                      max_shard_bytes=SHARD_DOWNLOAD_BYTES,
                      per_response_bytes=per_response_bytes, timeout_seconds=timeout_seconds,
                      adaptive=False)


def policy_payload() -> dict[str, Any]:
    return {"version": BUDGET_POLICY_VERSION, "initial_requests": INITIAL_REQUESTS,
            "initial_pages": INITIAL_PAGES, "max_requests": REQUEST_DEFECT_CEILING,
            "max_pages_per_query": PAGE_DEFECT_CEILING, "max_shard_bytes": SHARD_DOWNLOAD_BYTES,
            "max_run_bytes": RUN_DOWNLOAD_BYTES, "growth": "double_on_demand",
            "on_exhaustion": "INCOMPLETE_OR_UNAVAILABLE", "file_downloads": False,
            "campaign_version": CAMPAIGN_BUDGET_POLICY_VERSION,
            "campaign_requests": CAMPAIGN_REQUESTS,
            "campaign_pages_per_query": CAMPAIGN_PAGES_PER_QUERY,
            "campaign_bytes": CAMPAIGN_DOWNLOAD_BYTES}


def shard_key(request: GDCRequest) -> str:
    """All pages/retries of a query share a bucket; expression groups by gene batch.

    Case batches for the same expression gene batch share the same allowance,
    as do availability and values. Query parameters that change scientific
    membership (e.g. CNV case shard) remain in the identity.
    """
    import hashlib

    if request.path.startswith("/gene_expression/") and request.body is not None:
        scope = {"expression_genes": request.body.get("gene_ids", [])}
    else:
        scope = {"query": request.logical_query_id,
                 "params": [(key, value) for key, value in request.params
                            if key not in {"from", "size"}], "body": request.body}
    return hashlib.sha256(canonical_json(scope)).hexdigest()
