from __future__ import annotations

import dataclasses
import hashlib
import json
import time
import urllib.parse

import pytest

from cancerjev.gdc.endpoints import (
    EndpointError,
    EndpointSpec,
    GDCRequest,
    cases_request,
    expression_availability_request,
    files_expression_request,
    gene_case_counts_request,
    genes_request,
    projects_request,
    resolve_endpoint,
    status_request,
    top_mutated_genes_request,
)
from cancerjev.gdc.transport import (
    TRANSPORT_CONTRACT_VERSION,
    BudgetCaps,
    TransportError,
    TransportErrorCode,
)

STATUS_BODY = json.dumps({
    "commit": "8f7c2a51ab0084b216ad1b62a3fae8b945439c53",
    "data_release": "Data Release 46.0 - August 10, 2026",
    "status": "OK",
    "tag": "8.5.0",
}).encode()


def _error_code(exc_info) -> str:
    return str(exc_info.value.code)


def test_query_parameters_are_sorted_and_encoded(transport_builder, loopback):
    loopback.json("/projects", json.dumps({"data": {"hits": []}}).encode())
    transport = transport_builder()
    request = projects_request(size=2)
    transport.request(request)
    recorded = loopback.requests[0]
    assert recorded.path.startswith("/projects?")
    query = recorded.path.split("?", 1)[1]
    assert query.startswith("fields=")
    assert "&size=2" in query
    assert "%20" not in query and " " not in query
    decoded = dict(urllib.parse.parse_qsl(query))
    assert decoded == dict(request.params), "the wire query must decode to the recorded params"


def test_request_completes_records_ledger_and_cache(transport_builder, loopback, runtime):
    _, repository, _ = runtime
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder()
    response = transport.request(status_request())
    assert response.body == STATUS_BODY
    assert response.from_cache is False
    assert response.completeness == "COMPLETE"
    assert len(response.body_sha256) == 64
    totals = repository.gdc_run_totals(transport.run_id)
    assert totals == {"attempts": 1, "bytes": len(STATUS_BODY), "cache_hits": 0}

    again = transport.request(status_request())
    assert again.from_cache is True
    assert again.body == STATUS_BODY
    assert len(loopback.requests) == 1, "cache hit must not touch the network"
    totals = repository.gdc_run_totals(transport.run_id)
    assert totals["attempts"] == 2 and totals["cache_hits"] == 1
    assert totals["bytes"] == len(STATUS_BODY)


def test_no_authentication_headers_are_ever_sent(transport_builder, loopback):
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder()
    transport.request(status_request())
    recorded = loopback.requests[0]
    assert "authorization" not in recorded.headers
    assert "x-auth-token" not in recorded.headers
    assert recorded.headers["accept-encoding"] == "identity"


def test_default_caps_match_documented_hard_budgets():
    caps = BudgetCaps()
    assert caps.max_requests == 150
    assert caps.max_bytes == 256 * 1024 * 1024
    assert caps.per_response_bytes == 5 * 1024 * 1024
    assert caps.max_pages_per_query == 48
    assert caps.max_case_ids == 250
    assert caps.max_gene_ids == 100


def test_declared_content_length_over_cap_is_rejected(transport_builder, loopback):
    def responder(request):
        return 200, {"Content-Type": "application/json", "Content-Length": "999999"}, b"{}"

    loopback.raw("/status", responder)
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=1_000_000, per_response_bytes=100))
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.RESPONSE_TOO_LARGE


def test_body_over_cap_is_truncated_and_charged_once(transport_builder, loopback):
    for size in (101, 900):
        body = b"z" * size
        loopback.raw("/status", lambda request, body=body: (
            200, {"Content-Type": "application/json", "Transfer-Encoding": "chunked"}, body))
        transport = transport_builder(
            caps=BudgetCaps(max_requests=5, max_bytes=1_000_000, per_response_bytes=100))
        with pytest.raises(TransportError) as exc:
            transport.request(status_request())
        assert _error_code(exc) == TransportErrorCode.RESPONSE_TRUNCATED
        if size == 101:
            assert transport.budget.bytes_read == 101, (
                "the read allowance and sentinel must be charged exactly once")


def test_error_body_is_bounded_by_response_and_run_allowance(transport_builder, loopback):
    loopback.raw("/status", lambda request: (400, {"Content-Type": "application/json"}, b"E" * 1000))
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=32, per_response_bytes=10),
                                  cache_enabled=False)
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.PROVIDER_ERROR
    assert transport.budget.bytes_read == 10, "error bodies must respect the configured allowance"
    assert transport.budget.bytes_read <= transport.budget.caps.max_bytes


def test_cache_hit_respects_current_response_cap(transport_builder, loopback):
    loopback.json("/status", STATUS_BODY)
    first = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=1_000_000))
    first.request(status_request())
    assert len(loopback.requests) == 1

    second = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=1_000_000, per_response_bytes=1))
    with pytest.raises(TransportError) as exc:
        second.request(status_request())
    assert _error_code(exc) in {TransportErrorCode.RESPONSE_TOO_LARGE, TransportErrorCode.RESPONSE_TRUNCATED}
    assert len(loopback.requests) == 2, "a cached body larger than the current cap must not be replayed"


def test_redirect_is_refused_not_followed(transport_builder, loopback):
    loopback.raw("/status", lambda request: (302, {"Location": "https://evil.example/steal"}, b""))
    transport = transport_builder()
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.REDIRECT_REFUSED
    assert len(loopback.requests) == 1


def test_401_and_403_fail_closed_without_retry_or_credentials(transport_builder, loopback, runtime):
    _, repository, _ = runtime
    loopback.raw("/status", lambda request: (401, {"Content-Type": "application/json"}, b"{}"))
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=100_000, max_retries=2))
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.UNAVAILABLE_ACCESS
    assert len(loopback.requests) == 1, "no retry may occur after an access failure"
    assert "authorization" not in loopback.requests[0].headers

    loopback.raw("/status", lambda request: (403, {"Content-Type": "application/json"}, b"{}"))
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.UNAVAILABLE_ACCESS


def test_retryable_status_is_bounded(transport_builder, loopback):
    state = {"count": 0}

    def responder(request):
        state["count"] += 1
        if state["count"] == 1:
            return 429, {"Content-Type": "application/json", "Retry-After": "0"}, b"{}"
        return 200, {"Content-Type": "application/json"}, STATUS_BODY

    loopback.raw("/status", responder)
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=100_000, max_retries=2))
    response = transport.request(status_request())
    assert response.http_status == 200
    assert len(loopback.requests) == 2

    loopback.raw("/status", lambda request: (503, {"Content-Type": "application/json"}, b"{}"))
    exhausting = transport_builder(
        caps=BudgetCaps(max_requests=10, max_bytes=100_000, max_retries=1), cache_enabled=False)
    with pytest.raises(TransportError) as exc:
        exhausting.request(status_request())
    assert _error_code(exc) == TransportErrorCode.PROVIDER_ERROR
    assert len(loopback.requests) == 4, "retries are bounded by max_retries"


def test_compressed_response_is_rejected(transport_builder, loopback):
    loopback.raw("/status", lambda request: (200, {"Content-Type": "application/json",
                                                   "Content-Encoding": "gzip"}, b"\x1f\x8b\x08\x00"))
    transport = transport_builder()
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.INVALID_CONTENT_ENCODING


def test_timeout_is_typed(transport_builder, loopback):
    def responder(request):
        time.sleep(0.5)
        return 200, {"Content-Type": "application/json"}, STATUS_BODY

    loopback.raw("/status", responder)
    transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=100_000, max_retries=0,
                                                  timeout_seconds=0.1))
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.TIMEOUT


class _RefusingConnection:
    def request(self, *args, **kwargs):
        raise ConnectionRefusedError("synthetic connection refused")

    def close(self) -> None:
        return None


def test_connection_error_is_typed(transport_builder):
    transport = transport_builder(
        caps=BudgetCaps(max_requests=5, max_bytes=100_000, max_retries=0),
        connection_factory=_RefusingConnection)
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.CONNECTION_ERROR


def test_request_budget_is_enforced(transport_builder, loopback):
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder(caps=BudgetCaps(max_requests=1, max_bytes=100_000), cache_enabled=False)
    transport.request(status_request())
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.REQUEST_BUDGET_EXHAUSTED


def test_page_budget_is_enforced(transport_builder):
    transport = transport_builder(caps=BudgetCaps(max_requests=50, max_bytes=100_000, max_pages_per_query=10))
    paged = dataclasses.replace(status_request(), page=11, logical_query_id="paged")
    with pytest.raises(TransportError) as exc:
        transport.request(paged)
    assert _error_code(exc) == TransportErrorCode.PAGE_BUDGET_EXHAUSTED


def test_run_byte_budget_is_enforced(transport_builder, loopback):
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder(caps=BudgetCaps(max_requests=50, max_bytes=len(STATUS_BODY)), cache_enabled=False)
    transport.request(status_request())
    with pytest.raises(TransportError) as exc:
        transport.request(status_request())
    assert _error_code(exc) == TransportErrorCode.BYTE_BUDGET_EXHAUSTED


def test_forbidden_and_unknown_endpoints_are_rejected():
    with pytest.raises(EndpointError):
        resolve_endpoint("GET", "/data")
    with pytest.raises(EndpointError):
        resolve_endpoint("GET", "/ssms")
    with pytest.raises(EndpointError):
        resolve_endpoint("GET", "/../data")
    forged = EndpointSpec("forged", "GET", "/data")
    assert resolve_endpoint("GET", "/status").method == "GET"
    request = GDCRequest(endpoint=forged)
    assert request.path == "/data"


def test_forged_endpoint_spec_is_rejected_by_transport(transport_builder):
    transport = transport_builder()
    forged = EndpointSpec("forged", "GET", "/data")
    with pytest.raises(TransportError) as exc:
        transport.request(GDCRequest(endpoint=forged))
    assert _error_code(exc) == TransportErrorCode.UNSUPPORTED_ENDPOINT


def test_identity_and_size_caps_are_enforced():
    with pytest.raises(EndpointError):
        cases_request("TCGA-BRCA", size=251)
    with pytest.raises(EndpointError):
        genes_request([f"ENSG{i:011d}" for i in range(101)])
    with pytest.raises(EndpointError):
        expression_availability_request(["a", "a"], ["ENSG1"])
    with pytest.raises(EndpointError):
        gene_case_counts_request([])
    with pytest.raises(EndpointError):
        expression_availability_request(["case"], [])
    with pytest.raises(EndpointError):
        genes_request(["x" * 129])
    with pytest.raises(EndpointError):
        cases_request("TCGA-BRCA", offset=-1)
    with pytest.raises(EndpointError):
        cases_request("TCGA-BRCA", size=True)
    with pytest.raises(EndpointError):
        cases_request("TCGA-BRCA", offset=1.5)
    with pytest.raises(EndpointError):
        files_expression_request("TCGA-BRCA", size=6)
    with pytest.raises(EndpointError):
        files_expression_request("TCGA-BRCA", size=False)
    with pytest.raises(EndpointError):
        projects_request(size=True)
    with pytest.raises(EndpointError):
        projects_request(size=1.5)
    with pytest.raises(EndpointError):
        top_mutated_genes_request("TCGA-BRCA", size=True)
    with pytest.raises(EndpointError):
        top_mutated_genes_request("TCGA-BRCA", size=0)
    request = cases_request("TCGA-BRCA", size=100, offset=200)
    assert dict(request.params)["from"] == "200"
    assert request.page == 3


def test_cases_page_advance_can_exceed_offset_derived_page():
    request = cases_request("TCGA-BRCA", size=250, offset=0, page=11)
    assert dict(request.params)["from"] == "0"
    assert request.page == 11, "short pages must still consume one page advance each"


def test_host_allowlist_rejects_non_gdc_host(runtime):
    _, repository, artifacts = runtime
    from cancerjev.gdc.transport import GDCTransport, RunBudget

    with pytest.raises(TransportError) as exc:
        GDCTransport(repository, artifacts, RunBudget(), repository.create_run("x"),
                     lambda *args, **kwargs: None, host="evil.example")
    assert _error_code(exc) == TransportErrorCode.UNSUPPORTED_ENDPOINT


def test_usage_counters_update_from_transport_events(runtime, loopback, transport_builder):
    _, repository, _ = runtime
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder(emit=lambda *args, **kwargs: None)

    def emit(event_type, key, message, **kwargs):
        return repository.append_event(transport.run_id, event_type=event_type,
                                       idempotency_key=key, message=message, **kwargs)

    transport.emit = emit
    response = transport.request(status_request())
    run = repository.get_run(transport.run_id)
    assert run["provider_usage"]["gdc_requests"] == 1
    assert run["provider_usage"]["gdc_bytes"] == len(STATUS_BODY)
    assert run["provider_usage"]["gdc_cache_hits"] == 0
    attempts = repository.gdc_attempts(transport.run_id)
    assert [attempt["status"] for attempt in attempts] == ["COMPLETED"]
    assert response.request_id == attempts[0]["request_id"], "the response must name its own attempt"
    assert response.attempt_no == attempts[0]["attempt_no"] == 1
    assert attempts[0]["request_hash"] == response.request_hash
    assert attempts[0]["response_hash"] == response.body_sha256


def test_received_body_storage_failure_leaves_no_reserved_attempt(runtime, loopback, transport_builder, monkeypatch):
    _, repository, _ = runtime
    loopback.json("/status", STATUS_BODY)
    transport = transport_builder()
    events: list[dict] = []

    def emit(event_type, key, message, **kwargs):
        event = repository.append_event(transport.run_id, event_type=event_type,
                                        idempotency_key=key, message=message, **kwargs)
        events.append(event)
        return event

    transport.emit = emit

    def failing_register(artifact, run_id):
        raise OSError("artifact registry unavailable")

    monkeypatch.setattr(repository, "register_artifact", failing_register)
    with pytest.raises(OSError, match="artifact registry unavailable"):
        transport.request(status_request())

    attempts = repository.gdc_attempts(transport.run_id)
    assert [attempt["status"] for attempt in attempts] == ["FAILED"]
    assert attempts[0]["finished_at"] is not None
    assert "RESPONSE_STORAGE_FAILED" in attempts[0]["error"]
    assert attempts[0]["response_hash"] == hashlib.sha256(STATUS_BODY).hexdigest()
    assert [event["type"] for event in events] == ["GDC_REQUEST_STARTED", "GDC_REQUEST_FAILED"]


def test_stale_contract_version_cache_row_cannot_block_a_new_entry(runtime, loopback, transport_builder):
    _, repository, artifacts = runtime
    loopback.json("/status", STATUS_BODY)
    request = status_request()
    request_hash = request.request_hash()
    run_id = repository.create_run("stale-cache")
    stale_artifact = artifacts.publish("gdc/stale.body", STATUS_BODY, "application/json", "gdc-response")
    repository.register_artifact(stale_artifact, run_id)
    repository.gdc_cache_put(
        request_hash=request_hash, method="GET", endpoint="/status",
        response_artifact_id=stale_artifact.artifact_id, response_hash=stale_artifact.sha256,
        size_bytes=len(STATUS_BODY), completeness="COMPLETE", contract_version="gdc-transport-v0",
        created_at="2026-01-01T00:00:00Z",
    )

    fresh_transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=1_000_000))
    fresh = fresh_transport.request(request)
    assert fresh.from_cache is False, "an older contract version must not be replayed as current evidence"
    assert len(loopback.requests) == 1

    cached_transport = transport_builder(caps=BudgetCaps(max_requests=5, max_bytes=1_000_000))
    cached = cached_transport.request(request)
    assert cached.from_cache is True
    assert len(loopback.requests) == 1, "the current contract version entry must be storable"
    assert repository.gdc_cache_get(request_hash, TRANSPORT_CONTRACT_VERSION)["completeness"] == "COMPLETE"
    assert repository.gdc_cache_get(request_hash, "gdc-transport-v0")["created_at"] == "2026-01-01T00:00:00Z"
