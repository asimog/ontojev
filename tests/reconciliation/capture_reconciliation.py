"""Live capture for SCIENTIFIC_RECONCILIATION_FIXTURE (manual, not collected by pytest).

Fetches, for one fixed validation panel on TCGA-LUAD:

* A — ``/analysis/top_cases_counts_by_genes`` with one gene per request;
* B — production-form batched requests (sentinel batch plus the frozen
  contiguous 100-gene production batches that contain the panel genes);
* C — ``/ssm_occurrences`` records for the same project/gene filter.

Every response is frozen verbatim with its SHA-256 and request parameters, and
the independent expected values are derived from the raw bytes by
``tests.reconciliation.independent_counts`` (never by the production parser).
The panel and the production batch composition come from the already-frozen
``MANIFEST.json`` (repository-owned evidence), so re-capture never reads an
untracked developer runtime artifact. No file is mutated unless this module is
explicitly invoked.

Run: ``.venv/Scripts/python -m tests.reconciliation.capture_reconciliation``
Requires network access to api.gdc.cancer.gov (open data only, no credentials).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from tests.reconciliation.independent_counts import (
    count_from_top_cases_response,
    derive_from_occurrence_pages,
    sha256_hex,
)

BASE_URL = "https://api.gdc.cancer.gov"
PROJECT_ID = "TCGA-LUAD"
USER_AGENT = "CancerJEV-reconciliation-capture/0.1 (scientific reconciliation; anonymous)"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "reconciliation_dr46"

SENTINELS = ("TP53", "KRAS", "EGFR", "STK11", "KEAP1")
SURVIVOR_SYMBOLS = ("USH2A", "ASPM", "INSRR")
LOW_SYMBOLS = ("TSPAN6", "TNMD", "LAS1L")
ZERO_PROBE_LIMIT = 8
OCCURRENCE_PAGE_SIZE = 250


class CaptureError(RuntimeError):
    pass


def _get(path: str, params: dict[str, str] | None = None, *, attempts: int = 4) -> dict:
    query = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 200:
                    raise CaptureError(f"{url}: HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - capture tool retries any transport failure
            last_error = exc
            if attempt + 1 < attempts and _retryable(exc):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise CaptureError(f"{url}: {exc}") from exc
    raise CaptureError(f"{url}: {last_error}")


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 500, 502, 503, 504)
    return not isinstance(exc, CaptureError)


def _get_raw(path: str, params: dict[str, str]) -> tuple[bytes, str]:
    """Frozen capture of one response, verbatim bytes."""
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}?{query}"
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                if response.status != 200:
                    raise CaptureError(f"{url}: HTTP {response.status}")
                release = response.headers.get("x-gdc-data_release", "")
                return response.read(), release
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 < 4 and _retryable(exc):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise CaptureError(f"{url}: {exc}") from exc
    raise CaptureError(f"{url}: {last_error}")


def capture_a(gene_id: str) -> dict:
    body, release = _get_raw("/analysis/top_cases_counts_by_genes", {"gene_ids": gene_id})
    return {
        "slug": f"A_top_cases_counts_by_genes_{gene_id}",
        "path": "/analysis/top_cases_counts_by_genes",
        "params": {"gene_ids": gene_id},
        "body": body,
        "release": release,
    }


def capture_b(gene_ids: list[str], label: str) -> dict:
    ordered = sorted(gene_ids)
    body, release = _get_raw("/analysis/top_cases_counts_by_genes", {"gene_ids": ",".join(ordered)})
    return {
        "slug": f"B_top_cases_counts_by_genes_{label}",
        "path": "/analysis/top_cases_counts_by_genes",
        "params": {"gene_ids": ",".join(ordered)},
        "body": body,
        "release": release,
        "batch_label": label,
    }


def capture_c(gene_id: str) -> dict:
    filters = {"op": "and", "content": [
        {"op": "in", "content": {"field": "case.project.project_id", "value": [PROJECT_ID]}},
        {"op": "in", "content": {
            "field": "ssm.consequence.transcript.gene.gene_id", "value": [gene_id]}},
    ]}
    pages: list[bytes] = []
    offset = 0
    total = None
    while True:
        body, release = _get_raw("/ssm_occurrences", {
            "filters": json.dumps(filters, separators=(",", ":")),
            "size": str(OCCURRENCE_PAGE_SIZE),
            "from": str(offset),
            "sort": "ssm_occurrence_id:asc",
            "fields": "ssm_occurrence_id,case.case_id,case.project.project_id,ssm.consequence.transcript.gene.gene_id",
        })
        pages.append(body)
        document = json.loads(body.decode("utf-8"))
        pagination = document["data"]["pagination"]
        if total is None:
            total = int(pagination["total"])
        count = int(pagination["count"])
        offset += count
        if offset >= total:
            break
        if count == 0:
            raise CaptureError(f"ssm_occurrences stalled at offset {offset} for {gene_id}")
    return {
        "slug": f"C_ssm_occurrences_{gene_id}",
        "path": "/ssm_occurrences",
        "params": {
            "filters": json.dumps(filters, separators=(",", ":")),
            "size": str(OCCURRENCE_PAGE_SIZE),
            "sort": "ssm_occurrence_id:asc",
            "fields": "ssm_occurrence_id,case.case_id,case.project.project_id,ssm.consequence.transcript.gene.gene_id",
        },
        "pages": pages,
        "release": release,
    }


def _resolve_symbols() -> dict[str, str]:
    symbols = sorted(set(SENTINELS + SURVIVOR_SYMBOLS + LOW_SYMBOLS))
    document = _get("/genes", {
        "filters": json.dumps({"op": "in", "content": {"field": "symbol", "value": symbols}}),
        "fields": "gene_id,symbol",
        "size": str(len(symbols)),
    })
    resolved = {hit["symbol"]: hit["gene_id"] for hit in document["data"]["hits"]}
    missing = [symbol for symbol in symbols if symbol not in resolved]
    if missing:
        raise CaptureError(f"genes not resolved: {missing}")
    return resolved


def _frozen_panel() -> tuple[list[str], dict[int, list[str]], dict[str, int], str, list[str]]:
    """Read the validation panel and production batches from the frozen MANIFEST."""
    manifest = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    panel = sorted(
        record["params"]["gene_ids"]
        for record in manifest["records"]
        if record["slug"].startswith("A_top_cases_counts_by_genes_"))
    batch_ids_by_index: dict[int, list[str]] = {}
    for record in manifest["records"]:
        label = record.get("batch_label")
        if label and str(label).startswith("production_"):
            index = int(str(label).removeprefix("production_"))
            batch_ids_by_index[index] = record["params"]["gene_ids"].split(",")
    batch_of = {gene_id: index for index, ids in batch_ids_by_index.items() for gene_id in ids}
    random_ids = [str(gene_id) for gene_id in manifest["panel"]["random_from_prior_universe"]]
    return panel, batch_ids_by_index, batch_of, str(manifest["prior_stage4_release"]), random_ids


def _find_zero_gene(resolved: dict[str, str], extra_candidates: list[str]) -> str | None:
    for gene_id in extra_candidates:
        filters = {"op": "and", "content": [
            {"op": "in", "content": {"field": "case.project.project_id", "value": [PROJECT_ID]}},
            {"op": "in", "content": {
                "field": "ssm.consequence.transcript.gene.gene_id", "value": [gene_id]}},
        ]}
        document = _get("/ssm_occurrences", {
            "filters": json.dumps(filters, separators=(",", ":")),
            "size": "0",
            "fields": "ssm_occurrence_id",
        })
        if int(document["data"]["pagination"]["total"]) == 0:
            return gene_id
    return None


def main() -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    captured: dict[str, dict] = {}
    records: list[dict] = []

    panel, batch_ids_by_index, batch_of, prior_release, random_ids = _frozen_panel()
    production_batches = sorted(batch_ids_by_index)

    status = _get("/status")
    release = status["data_release"]
    print(f"provider release: {release}")

    resolved = _resolve_symbols()
    by_id = {gene_id: symbol for symbol, gene_id in resolved.items()}

    # Zero/absent-bucket candidate: genes beyond the tested prefix range.
    beyond = _get("/genes", {
        "filters": json.dumps({
            "op": "in", "content": {"field": "biotype", "value": ["protein_coding"]}}),
        "size": str(ZERO_PROBE_LIMIT),
        "from": "15000",
        "sort": "gene_id:asc",
        "fields": "gene_id,symbol",
    })
    zero_candidates = [hit["gene_id"] for hit in beyond["data"]["hits"]]
    zero_gene = _find_zero_gene(resolved, zero_candidates)
    zero_symbol = by_id.get(zero_gene, zero_gene) if zero_gene else None
    print(f"zero-bucket gene: {zero_gene} ({zero_symbol})")

    for gene_id in panel:
        a_capture = capture_a(gene_id)
        c_capture = capture_c(gene_id)
        captured[a_capture["slug"]] = a_capture
        captured[c_capture["slug"]] = c_capture
        print(f"captured A+C for {by_id.get(gene_id, gene_id)} ({gene_id})")

    sentinel_batch = capture_b([resolved[s] for s in SENTINELS], "sentinels")
    captured[sentinel_batch["slug"]] = sentinel_batch
    for batch_index in production_batches:
        batch_capture = capture_b(batch_ids_by_index[batch_index], f"production_{batch_index:03d}")
        captured[batch_capture["slug"]] = batch_capture
        print(f"captured B production batch {batch_index}")

    # Freeze every capture verbatim and derive expected values independently.
    for slug, capture in sorted(captured.items()):
        destination = FIXTURE_ROOT / f"{slug}.body"
        if "pages" in capture:
            combined = b"\n\x00\n".join(capture["pages"])
            destination.write_bytes(combined)
            page_hashes = [sha256_hex(page) for page in capture["pages"]]
        else:
            destination.write_bytes(capture["body"])
            page_hashes = [sha256_hex(capture["body"])]
        record = {
            "slug": slug,
            "endpoint": capture["path"],
            "params": capture["params"],
            "release": capture.get("release", release),
            "sha256": sha256_hex(destination.read_bytes()),
            "page_sha256": page_hashes,
            "bytes": len(destination.read_bytes()),
            "batch_label": capture.get("batch_label"),
        }
        records.append(record)

    # Independent derivation and reconciliation matrix.
    report_rows: list[dict] = []
    for gene_id in panel:
        symbol = by_id.get(gene_id, gene_id)
        a = captured[f"A_top_cases_counts_by_genes_{gene_id}"]["body"]
        c_pages = captured[f"C_ssm_occurrences_{gene_id}"]["pages"]
        derived = derive_from_occurrence_pages(c_pages, PROJECT_ID, gene_id)
        a_count = count_from_top_cases_response(a, PROJECT_ID, gene_id)
        b_count: int | None = None
        batch_index = batch_of.get(gene_id)
        for label in ("sentinels",) + tuple(
            f"production_{index:03d}" for index in production_batches
            if batch_index is not None and index == batch_index
        ):
            slug = f"B_top_cases_counts_by_genes_{label}"
            if slug in captured:
                value = count_from_top_cases_response(captured[slug]["body"], PROJECT_ID, gene_id)
                if value is not None:
                    b_count = value
                    break
        report_rows.append({
            "gene_id": gene_id,
            "symbol": symbol,
            "project": PROJECT_ID,
            "A_single_gene_count": a_count,
            "B_batched_count": b_count,
            "C_distinct_cases": derived.distinct_cases,
            "C_total_occurrences": derived.total_occurrences,
            "A_equals_B": (a_count == b_count) if (a_count is not None and b_count is not None) else None,
            "A_equals_C_distinct": (a_count == derived.distinct_cases) if a_count is not None else None,
            "B_equals_C_distinct": (b_count == derived.distinct_cases) if b_count is not None else None,
            "distinct_le_total": derived.distinct_cases <= derived.total_occurrences,
            "release": release,
        })
        print(f"{symbol}: A={a_count} B={b_count} C_distinct={derived.distinct_cases} "
              f"C_total={derived.total_occurrences}")

    manifest = {
        "category": "SCIENTIFIC_RECONCILIATION_FIXTURE",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release": release,
        "prior_stage4_release": prior_release,
        "project": PROJECT_ID,
        "method_of_derivation": "tests.reconciliation.independent_counts (no production parser)",
        "panel": {
            "sentinels": {symbol: resolved[symbol] for symbol in SENTINELS},
            "survivors": {symbol: resolved[symbol] for symbol in SURVIVOR_SYMBOLS},
            "low_counts": {symbol: resolved[symbol] for symbol in LOW_SYMBOLS},
            "random_from_prior_universe": random_ids,
            "zero_bucket": {"gene_id": zero_gene, "symbol": zero_symbol},
        },
        "production_batches": production_batches,
        "records": records,
        "rows": report_rows,
    }
    (FIXTURE_ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"frozen {len(records)} captures in {FIXTURE_ROOT}")


if __name__ == "__main__":
    main()
