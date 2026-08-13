"""Stable, non-secret RFC 9457-style API problem responses."""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

ERROR_CODES = {
    "API_UNREACHABLE", "REQUEST_TIMEOUT", "RESPONSE_CONTRACT_INVALID",
    "API_VERSION_MISMATCH", "AUTHENTICATION_REQUIRED", "AUTHORIZATION_DENIED",
    "CSRF_REJECTED", "NOT_FOUND", "VALIDATION_FAILED", "PERSISTENCE_UNAVAILABLE",
    "REPORT_EXPORT_DISABLED", "ARTIFACT_STORAGE_UNAVAILABLE", "KMS_ACCESS_DENIED",
    "IDEMPOTENCY_KEY_REUSED", "REPORT_GENERATION_IN_PROGRESS",
    "PROPOSAL_CONTENT_RETAINED_DATA_DELETED",
    "CORRECTION_REVERIFICATION_REQUIRED", "CORRECTION_REVERIFICATION_FAILED",
    "MARKET_DATA_UNAVAILABLE", "MODEL_POLICY_UNCONFIGURED", "WORKER_OFFLINE",
    "DIGEST_MISMATCH", "PREFLIGHT_INCOMPLETE", "PROPOSAL_AWAITING_REVIEW",
    "PROPOSAL_STALE", "RATE_LIMITED", "PAYLOAD_TOO_LARGE", "INTERNAL_ERROR",
}

_ALIASES = {
    "proposal_stale": "PROPOSAL_STALE",
    "ollama_operation_incomplete": "PROPOSAL_AWAITING_REVIEW",
    "worker_offline": "WORKER_OFFLINE",
    "no_enrolled_worker": "WORKER_OFFLINE",
    "model_policy_ambiguous": "MODEL_POLICY_UNCONFIGURED",
    "digest_mismatch": "DIGEST_MISMATCH",
    "preflight_incomplete": "PREFLIGHT_INCOMPLETE",
}
_STATUS_DEFAULTS = {400: "VALIDATION_FAILED", 401: "AUTHENTICATION_REQUIRED",
                    403: "AUTHORIZATION_DENIED", 404: "NOT_FOUND",
                    409: "VALIDATION_FAILED", 413: "PAYLOAD_TOO_LARGE",
                    422: "VALIDATION_FAILED", 429: "RATE_LIMITED"}


def normalize_error_code(status: int, detail: Any, path: str = "") -> str:
    candidate = detail.get("code") if isinstance(detail, dict) else None
    if candidate:
        candidate = str(candidate)
        normalized = _ALIASES.get(candidate, re.sub(r"[^A-Z0-9]+", "_", candidate.upper()))
        if normalized in ERROR_CODES:
            return normalized
    text = str(detail).lower()
    if "csrf" in text:
        return "CSRF_REJECTED"
    if "report export" in text and ("disabled" in text or "unavailable" in text):
        return "REPORT_EXPORT_DISABLED"
    if "kms" in text:
        return "KMS_ACCESS_DENIED"
    if "artifact" in text or "s3" in text:
        return "ARTIFACT_STORAGE_UNAVAILABLE"
    if "database" in text or "persistence" in text or "durable audit" in text:
        return "PERSISTENCE_UNAVAILABLE"
    if path.startswith(("/market/", "/sentiment/", "/scanner/")) and status == 503:
        return "MARKET_DATA_UNAVAILABLE"
    if status >= 500:
        return "INTERNAL_ERROR"
    return _STATUS_DEFAULTS.get(status, "VALIDATION_FAILED")


def problem_document(*, status: int, detail: Any, request_id: str, path: str,
                     trace_id: str | None = None, retryable: bool | None = None,
                     code: str | None = None, dependency: str | None = None) -> dict[str, Any]:
    resolved = code or normalize_error_code(status, detail, path)
    document: dict[str, Any] = {
        "type": f"https://ambrosia.invalid/problems/{resolved.lower().replace('_', '-')}",
        "title": resolved.replace("_", " ").title(), "status": status,
        # Retain FastAPI's established extension for backwards-compatible clients.
        "detail": detail, "instance": path, "code": resolved,
        "requestId": request_id, "traceId": trace_id,
        "retryable": status in {429, 502, 503, 504} if retryable is None else retryable,
    }
    if dependency:
        document["dependency"] = dependency
    if isinstance(detail, dict):
        for key in ("operationId", "packetId", "expectedVersion", "actualVersion"):
            if key in detail:
                document[key] = detail[key]
    return document


def problem_response(request: Request, status: int, detail: Any, *,
                     headers: dict[str, str] | None = None, code: str | None = None,
                     retryable: bool | None = None,
                     dependency: str | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get(
        "x-request-id", "unknown"
    )
    return JSONResponse(
        status_code=status,
        content=problem_document(status=status, detail=detail, request_id=request_id,
                                 path=request.url.path,
                                 trace_id=request.headers.get("traceparent"),
                                 retryable=retryable, code=code, dependency=dependency),
        headers=headers, media_type="application/problem+json",
    )
