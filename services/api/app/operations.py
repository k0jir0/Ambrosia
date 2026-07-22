"""Production boundary controls and operational telemetry for Ambrosia.

The module is dependency-light so the same controls run in local tests and the
deployed API. Production fails closed when identity configuration is missing;
development may use explicit header identities for local workflows.
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import binascii
import json
import logging
import os
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

LOGGER = logging.getLogger("ambrosia.operations")
router = APIRouter(tags=["operations"])

ROLE_LEVELS = {
    "viewer": 0,
    "user": 0,
    "analyst": 1,
    "reviewer": 2,
    "team_lead": 2,
    "owner": 3,
    "admin": 3,
    "service": 3,
}
PUBLIC_PATHS = {"/", "/health", "/live", "/ready", "/openapi.json"}
PUBLIC_PREFIXES = ("/docs", "/redoc")
SENSITIVE_PREFIXES = (
    "/admin", "/enterprise", "/governance", "/roadmap", "/execution",
)
AUDIT_PREFIXES = ("/operational/audit", "/packets/")
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def _is_production() -> bool:
    return _environment() in {"production", "staging"}


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    team: str | None
    auth_method: str


def _configured_api_keys() -> dict[str, dict[str, str]]:
    """Load API identities from JSON without ever logging credential values.

    Format: {"secret-token": {"subject": "svc-ci", "role": "service",
    "team": "platform"}}. A managed secret should supply this value.
    """
    raw = os.getenv("AMBROSIA_API_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AMBROSIA_API_KEYS_JSON is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("AMBROSIA_API_KEYS_JSON must be a JSON object")
    identities: dict[str, dict[str, str]] = {}
    for token, identity in parsed.items():
        if not isinstance(token, str) or len(token) < 16 or not isinstance(identity, dict):
            continue
        subject = str(identity.get("subject", "")).strip()
        role = str(identity.get("role", "")).strip().lower()
        if subject and role in ROLE_LEVELS:
            identities[token] = {
                "subject": subject,
                "role": role,
                "team": str(identity.get("team", "")).strip(),
            }
    return identities


def _decode_b64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _authenticate_hs256_jwt(token: str) -> Principal | None:
    secret = os.getenv("AMBROSIA_JWT_HS256_SECRET", "").strip()
    if not secret or len(secret) < 32:
        return None
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        header = json.loads(_decode_b64url(header_segment))
        claims = json.loads(_decode_b64url(payload_segment))
        signature = _decode_b64url(signature_segment)
    except (ValueError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if header.get("alg") != "HS256" or header.get("typ", "JWT") != "JWT":
        return None
    expected = hmac.new(
        secret.encode(), f"{header_segment}.{payload_segment}".encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, signature):
        return None
    now = int(time.time())
    try:
        if int(claims["exp"]) <= now or int(claims.get("nbf", 0)) > now + 30:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    issuer = os.getenv("AMBROSIA_JWT_ISSUER", "").strip()
    audience = os.getenv("AMBROSIA_JWT_AUDIENCE", "").strip()
    if issuer and claims.get("iss") != issuer:
        return None
    token_audience = claims.get("aud")
    if audience and token_audience != audience and not (
        isinstance(token_audience, list) and audience in token_audience
    ):
        return None
    subject = str(claims.get("sub", "")).strip()
    role = str(claims.get("role", "")).strip().lower()
    if not subject or role not in ROLE_LEVELS:
        return None
    return Principal(
        subject=subject,
        role=role,
        team=str(claims.get("team", "")).strip() or None,
        auth_method="jwt-hs256",
    )


def authenticate(request: Request) -> Principal | None:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        candidate = auth[7:].strip()
        for token, identity in _configured_api_keys().items():
            if hmac.compare_digest(candidate, token):
                return Principal(
                    subject=identity["subject"],
                    role=identity["role"],
                    team=identity["team"] or None,
                    auth_method="bearer-api-key",
                )
        jwt_principal = _authenticate_hs256_jwt(candidate)
        if jwt_principal is not None:
            return jwt_principal

    allow_dev = _truthy("ALLOW_INSECURE_DEV_IDENTITY", default=not _is_production())
    if allow_dev and not _is_production():
        role = (
            request.headers.get("x-ambrosia-role")
            or request.headers.get("x-user-role")
            or os.getenv("AMBROSIA_DEV_DEFAULT_ROLE", "admin")
        ).strip().lower()
        if role in ROLE_LEVELS:
            return Principal(
                subject=request.headers.get("x-ambrosia-user", "local-developer"),
                role=role,
                team=request.headers.get("x-ambrosia-team"),
                auth_method="development-header",
            )
    return None


def _required_level(path: str, method: str) -> int:
    if path.startswith("/operational/audit"):
        return 2
    if any(path.startswith(prefix) for prefix in SENSITIVE_PREFIXES):
        return 3 if method in WRITE_METHODS else 2
    if method in WRITE_METHODS:
        return 1
    if any(path.startswith(prefix) for prefix in AUDIT_PREFIXES) and path.endswith("/audit"):
        return 2
    return 0


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            remaining = max(0, limit - len(events))
            if len(events) >= limit:
                return False, 0
            events.append(now)
            return True, max(0, remaining - 1)


class Telemetry:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.counters: Counter[tuple[str, ...]] = Counter()
        self.latency_ms: Counter[str] = Counter()
        self._lock = threading.Lock()

    def record(self, method: str, route: str, status: int, elapsed_ms: float) -> None:
        route = route if len(route) <= 120 else route[:120]
        status_class = f"{status // 100}xx"
        with self._lock:
            self.counters[(method, route, status_class)] += 1
            self.latency_ms[route] += int(elapsed_ms)

    def increment(self, name: str, label: str = "total") -> None:
        with self._lock:
            self.counters[("domain", name, label)] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptimeSeconds": round(time.monotonic() - self.started, 3),
                "requests": [
                    {"method": k[0], "route": k[1], "statusClass": k[2], "count": v}
                    for k, v in self.counters.items()
                    if len(k) == 3 and k[0] != "domain"
                ],
                "domainEvents": [
                    {"name": k[1], "label": k[2], "count": v}
                    for k, v in self.counters.items()
                    if len(k) == 3 and k[0] == "domain"
                ],
            }

    def prometheus(self) -> str:
        lines = [
            "# HELP ambrosia_uptime_seconds API process uptime.",
            "# TYPE ambrosia_uptime_seconds gauge",
            f"ambrosia_uptime_seconds {time.monotonic() - self.started:.3f}",
            "# HELP ambrosia_http_requests_total HTTP requests by method, route, and status class.",
            "# TYPE ambrosia_http_requests_total counter",
        ]
        with self._lock:
            for key, value in sorted(self.counters.items()):
                if len(key) == 3 and key[0] != "domain":
                    method, route, status_class = key
                    safe_route = route.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(
                        f'ambrosia_http_requests_total{{method="{method}",route="{safe_route}",status="{status_class}"}} {value}'
                    )
                elif len(key) == 3:
                    _, name, label = key
                    lines.append(
                        f'ambrosia_domain_events_total{{name="{name}",label="{label}"}} {value}'
                    )
        return "\n".join(lines) + "\n"


@dataclass
class SecurityAuditEvent:
    sequence: int
    timestamp: str
    request_id: str
    actor: str
    role: str
    action: str
    resource: str
    status: int
    previous_hash: str
    event_hash: str


class HashChainAuditLog:
    def __init__(self, max_events: int = 10_000) -> None:
        self._events: deque[SecurityAuditEvent] = deque(maxlen=max_events)
        self._last_hash = "0" * 64
        self._sequence = 0
        self._lock = threading.Lock()

    def append(self, *, request_id: str, principal: Principal | None, action: str,
               resource: str, status: int) -> SecurityAuditEvent:
        with self._lock:
            self._sequence += 1
            payload = {
                "sequence": self._sequence,
                "timestamp": _utc_now(),
                "request_id": request_id,
                "actor": principal.subject if principal else "anonymous",
                "role": principal.role if principal else "none",
                "action": action,
                "resource": resource,
                "status": status,
                "previous_hash": self._last_hash,
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            event_hash = hashlib.sha256(encoded).hexdigest()
            event = SecurityAuditEvent(**payload, event_hash=event_hash)
            self._events.append(event)
            self._last_hash = event_hash
            return event

    def recent(self, limit: int) -> list[dict]:
        with self._lock:
            return [asdict(event) for event in list(self._events)[-limit:]]

    def verify(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for event in self._events:
                payload = asdict(event)
                event_hash = payload.pop("event_hash")
                if payload["previous_hash"] != previous:
                    return False
                encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                if not hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), event_hash):
                    return False
                previous = event_hash
            return True


telemetry = Telemetry()
security_audit = HashChainAuditLog()
rate_limiter = SlidingWindowRateLimiter()
_readiness_checks: list[tuple[str, Callable[[], None]]] = []
_audit_sink: Callable[..., None] | None = None
_audit_sink_error: str | None = None


def register_readiness_check(name: str, check: Callable[[], None]) -> None:
    _readiness_checks.append((name, check))


def register_audit_sink(sink: Callable[..., None]) -> None:
    global _audit_sink
    _audit_sink = sink


def _persist_security_audit(event: SecurityAuditEvent) -> None:
    global _audit_sink_error
    if _audit_sink is None:
        return
    try:
        _audit_sink(
            request_id=event.request_id,
            actor=event.actor,
            role=event.role,
            action=event.action,
            resource=event.resource,
            status=event.status,
        )
        _audit_sink_error = None
    except Exception as exc:  # durable failure becomes a readiness and write gate
        _audit_sink_error = type(exc).__name__
        telemetry.increment("audit_persistence_failure")
        LOGGER.exception("durable security audit append failed")


class ProductionBoundaryMiddleware:
    """Authenticate, authorize, limit, correlate, measure, and secure requests."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path
        method = request.method.upper()
        request_id = request.headers.get("x-request-id", "").strip()
        if not request_id or len(request_id) > 128:
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()

        content_length = request.headers.get("content-length")
        max_bytes = int(os.getenv("MAX_REQUEST_BYTES", "1048576"))
        if content_length and content_length.isdigit() and int(content_length) > max_bytes:
            telemetry.increment("request_rejected", "body_too_large")
            await self._json(send, 413, {"detail": "Request body exceeds configured limit"}, request_id)
            return

        if _is_production() and method in WRITE_METHODS and _audit_sink_error is not None:
            await self._json(send, 503, {"detail": "Durable audit path unavailable"}, request_id)
            return

        is_public = path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)
        principal = None if is_public else authenticate(request)
        if not is_public and principal is None:
            telemetry.increment("authentication_failure")
            security_audit.append(request_id=request_id, principal=None, action=method,
                                  resource=path, status=401)
            await self._json(send, 401, {"detail": "Valid bearer identity required"}, request_id)
            return

        if principal:
            scope["state"]["principal"] = principal
            required = _required_level(path, method)
            if ROLE_LEVELS.get(principal.role, -1) < required:
                telemetry.increment("authorization_failure", principal.role)
                security_audit.append(request_id=request_id, principal=principal, action=method,
                                      resource=path, status=403)
                await self._json(send, 403, {"detail": "Insufficient role for operation"}, request_id)
                return

            # Several legacy FastAPI handlers still accept X-Ambrosia-Role.
            # Replace any client value with the role from the authenticated
            # principal so those handlers cannot trust or be confused by a
            # spoofable header while they are migrated to request.state.
            if principal.auth_method != "development-header":
                scope["headers"] = [
                    (name, value)
                    for name, value in scope.get("headers", [])
                    if name.lower() != b"x-ambrosia-role"
                ]
                scope["headers"].append((b"x-ambrosia-role", principal.role.encode("ascii")))

        identity = principal.subject if principal else (scope.get("client") or ("unknown",))[0]
        rate = int(os.getenv("RATE_LIMIT_PER_MINUTE", "300"))
        enforce_rate_limit = _is_production() or _truthy("ENABLE_RATE_LIMITING")
        if enforce_rate_limit:
            allowed, remaining = rate_limiter.allow(str(identity), rate)
            if not allowed:
                telemetry.increment("request_rejected", "rate_limit")
                await self._json(send, 429, {"detail": "Rate limit exceeded"}, request_id,
                                 extra_headers=[(b"retry-after", b"60")])
                return
        else:
            remaining = rate

        status_code = 500

        async def secure_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"cache-control", b"no-store"),
                    (b"x-ratelimit-remaining", str(remaining).encode()),
                ])
                if _is_production():
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, secure_send)
        finally:
            elapsed_ms = (time.monotonic() - started) * 1000
            telemetry.record(method, path, status_code, elapsed_ms)
            if method in WRITE_METHODS or status_code >= 400:
                event = security_audit.append(
                    request_id=request_id, principal=principal, action=method,
                    resource=path, status=status_code,
                )
                _persist_security_audit(event)
                LOGGER.info(json.dumps({"event": "security_audit", **asdict(event)}))

    @staticmethod
    async def _json(send, status: int, payload: dict, request_id: str,
                    extra_headers: list[tuple[bytes, bytes]] | None = None) -> None:
        body = json.dumps(payload).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"x-request-id", request_id.encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"cache-control", b"no-store"),
        ]
        headers.extend(extra_headers or [])
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


@router.get("/live")
def liveness() -> dict:
    return {"status": "alive", "service": "ambrosia-api", "timestamp": _utc_now()}


@router.get("/ready")
def readiness() -> Response:
    checks: dict[str, dict[str, str]] = {}
    ready = True
    for name, check in _readiness_checks:
        try:
            check()
            checks[name] = {"status": "ok"}
        except Exception as exc:  # readiness deliberately collapses secret details
            ready = False
            checks[name] = {"status": "failed", "reason": type(exc).__name__}
    jwt_ready = len(os.getenv("AMBROSIA_JWT_HS256_SECRET", "").strip()) >= 32
    if _is_production() and not (_configured_api_keys() or jwt_ready):
        ready = False
        checks["identity"] = {"status": "failed", "reason": "identity_not_configured"}
    else:
        checks["identity"] = {"status": "ok"}
    if _audit_sink_error is not None:
        ready = False
        checks["auditPersistence"] = {"status": "failed", "reason": _audit_sink_error}
    else:
        checks["auditPersistence"] = {"status": "ok"}
    status = 200 if ready else 503
    return JSONResponse(
        status_code=status,
        content={"status": "ready" if ready else "not_ready", "checks": checks,
                 "timestamp": _utc_now()},
    )


@router.get("/operational/metrics")
def operational_metrics(request: Request) -> Response:
    accept = request.headers.get("accept", "")
    if "text/plain" in accept or request.query_params.get("format") == "prometheus":
        return PlainTextResponse(telemetry.prometheus(), media_type="text/plain; version=0.0.4")
    return JSONResponse({"timestamp": _utc_now(), **telemetry.snapshot()})


@router.get("/operational/audit")
def operational_audit(limit: int = 100) -> dict:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    return {"chainValid": security_audit.verify(), "events": security_audit.recent(limit)}


def record_domain_event(name: str, label: str = "total") -> None:
    telemetry.increment(name, label)
