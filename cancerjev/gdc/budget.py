"""Declared operational policy, separate from scientific cohort/gene scope.

Production requests/pages grow geometrically on demand and are audited. Bytes
never auto-expand: 512 MiB per acquisition shard and 768 MiB per command/run.
Explicit fixed BudgetCaps remain available for replay/contract tests.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cancerjev.gdc.endpoints import GDCRequest
    from cancerjev.gdc.transport import BudgetCaps

from cancerjev.domain.events import canonical_json

BUDGET_POLICY_VERSION = "gdc-adaptive-v1"
SHARD_DOWNLOAD_BYTES = 512 * 1024 * 1024
RUN_DOWNLOAD_BYTES = 768 * 1024 * 1024
INITIAL_REQUESTS = 150
INITIAL_PAGES = 48
REQUEST_DEFECT_CEILING = 10_000
PAGE_DEFECT_CEILING = 10_000


def production_caps(*, per_response_bytes: int, timeout_seconds: float) -> BudgetCaps:
    from cancerjev.gdc.transport import BudgetCaps

    return BudgetCaps(max_requests=INITIAL_REQUESTS, max_bytes=RUN_DOWNLOAD_BYTES,
                      max_pages_per_query=INITIAL_PAGES, max_shard_bytes=SHARD_DOWNLOAD_BYTES,
                      per_response_bytes=per_response_bytes, timeout_seconds=timeout_seconds,
                      adaptive=True)


def policy_payload() -> dict[str, Any]:
    return {"version": BUDGET_POLICY_VERSION, "initial_requests": INITIAL_REQUESTS,
            "initial_pages": INITIAL_PAGES, "max_requests": REQUEST_DEFECT_CEILING,
            "max_pages_per_query": PAGE_DEFECT_CEILING, "max_shard_bytes": SHARD_DOWNLOAD_BYTES,
            "max_run_bytes": RUN_DOWNLOAD_BYTES, "growth": "double_on_demand",
            "on_exhaustion": "INCOMPLETE_OR_UNAVAILABLE", "file_downloads": False}


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
