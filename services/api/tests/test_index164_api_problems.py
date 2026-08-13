from app.api_problems import normalize_error_code, problem_document


def test_domain_failures_are_not_classified_as_api_unreachable() -> None:
    assert normalize_error_code(503, "provider unavailable", "/market/AAPL/snapshot") == (
        "MARKET_DATA_UNAVAILABLE"
    )
    assert normalize_error_code(503, {"code": "worker_offline"}, "/providers/status") == (
        "WORKER_OFFLINE"
    )
    assert normalize_error_code(503, {"code": "no_enrolled_worker"}, "/providers/status") == (
        "NO_ENROLLED_WORKER"
    )
    assert normalize_error_code(409, {"code": "proposal_stale"}, "/operations/1/admission") == (
        "PROPOSAL_STALE"
    )


def test_problem_document_has_stable_correlation_and_retry_contract() -> None:
    value = problem_document(
        status=503,
        detail={"code": "worker_offline", "operationId": "op-1"},
        request_id="request-1",
        trace_id="trace-1",
        path="/providers/status",
    )
    assert value["code"] == "WORKER_OFFLINE"
    assert value["requestId"] == "request-1"
    assert value["traceId"] == "trace-1"
    assert value["operationId"] == "op-1"
    assert value["retryable"] is True
