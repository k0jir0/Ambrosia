from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import AlphaHypothesisCreate, PaperTradeCreate, SignalCreate, SignalDecisionWriteback, SignalOutcomeWriteback, SignalReviewLink

JsonObject = dict[str, Any]
PayloadObject = JsonObject | AlphaHypothesisCreate | PaperTradeCreate | SignalCreate | SignalDecisionWriteback | SignalOutcomeWriteback | SignalReviewLink
Transport = Callable[[str, str, JsonObject | None, dict[str, str], float], JsonObject]


class AmbrosiaApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class AmbrosiaClient:
    base_url: str | None = None
    token: str | None = None
    timeout: float = 65.0
    transport: Transport | None = None

    def __post_init__(self) -> None:
        configured_base_url = self.base_url or os.getenv("AMBROSIA_API_URL") or "http://localhost:8000"
        object.__setattr__(self, "base_url", configured_base_url.rstrip("/"))
        object.__setattr__(self, "token", self.token or os.getenv("AMBROSIA_TOKEN"))

    def health(self) -> JsonObject:
        return self._get("/health")

    def health_detailed(self) -> JsonObject:
        return self._get("/health/detailed")

    def list_reviews(self) -> list[JsonObject]:
        return self._get("/reviews")

    def create_review(self, thesis: str, **fields: Any) -> JsonObject:
        return self._post("/reviews", {"thesis": thesis, **fields})

    def get_review(self, review_id: str) -> JsonObject:
        return self._get(f"/reviews/{_path(review_id)}")

    def list_packets(self) -> list[JsonObject]:
        return self._get("/packets")

    def create_packet(self, packet: JsonObject) -> JsonObject:
        return self._post("/packets", packet)

    def get_packet(self, packet_id: str) -> JsonObject:
        return self._get(f"/packets/{_path(packet_id)}")

    def market_snapshot(self, ticker: str) -> JsonObject:
        return self._get(f"/market/{_path(_normalize_ticker(ticker))}/snapshot")

    def scanner_run(self, universe: list[str] | None = None, max_candidates: int = 10) -> JsonObject:
        return self._post("/scanner/run", {"universe": universe, "maxCandidates": max_candidates})

    def list_jobs(self) -> list[JsonObject]:
        return self._get("/jobs")

    def get_job(self, job_id: str) -> JsonObject:
        return self._get(f"/jobs/{_path(job_id)}")

    def wait_job(self, job_id: str) -> JsonObject:
        return self.get_job(job_id)

    def list_plans(self) -> list[JsonObject]:
        return self._get("/roadmap/plans")

    def get_plan(self, plan_id: str) -> JsonObject:
        return self._get(f"/roadmap/plans/{_path(plan_id)}")

    def relay_evaluate(self, question: str, documents: list[str] | None = None) -> JsonObject:
        return self._post("/relay/evaluate", {"question": question, "documents": documents or []})

    def relay_scorecard(self) -> JsonObject:
        return self._get("/relay/scorecard")

    def list_relay_runs(self, limit: int | None = None, offset: int = 0) -> JsonObject:
        path = f"/relay/runs?offset={offset}"
        if limit is not None:
            path += f"&limit={limit}"
        return self._get(path)

    def get_relay_run(self, run_id: str) -> JsonObject:
        return self._get(f"/relay/runs/{_path(run_id)}")

    def create_signal(self, payload: JsonObject | SignalCreate) -> JsonObject:
        return self._post("/signals", _as_payload(payload))

    def list_signals(self) -> list[JsonObject]:
        return self._get("/signals")

    def get_signal(self, signal_id: str) -> JsonObject:
        return self._get(f"/signals/{_path(signal_id)}")

    def link_signal_review(self, signal_id: str, payload: JsonObject | SignalReviewLink) -> JsonObject:
        return self._post(f"/signals/{_path(signal_id)}/link-review", _as_payload(payload))

    def writeback_signal_decision(self, signal_id: str, payload: JsonObject | SignalDecisionWriteback) -> JsonObject:
        return self._post(f"/signals/{_path(signal_id)}/writeback-decision", _as_payload(payload))

    def writeback_signal_outcome(self, signal_id: str, payload: JsonObject | SignalOutcomeWriteback) -> JsonObject:
        return self._post(f"/signals/{_path(signal_id)}/writeback-outcome", _as_payload(payload))

    def signal_quality_scorecard_weekly(self) -> JsonObject:
        return self._get("/signals/quality-scorecard/weekly")

    def create_alpha_hypothesis(self, payload: JsonObject | AlphaHypothesisCreate) -> JsonObject:
        return self._post("/alpha/hypotheses", _as_payload(payload))

    def list_alpha_hypotheses(self) -> list[JsonObject]:
        return self._get("/alpha/hypotheses")

    def get_alpha_hypothesis(self, hypothesis_id: str) -> JsonObject:
        return self._get(f"/alpha/hypotheses/{_path(hypothesis_id)}")

    def run_backtest(self, signal_id: str, **fields: Any) -> JsonObject:
        return self._post("/backtests/run", {"signalId": signal_id, **fields})

    def get_alpha_decay(self, signal_id: str) -> JsonObject:
        return self._get(f"/signals/{_path(signal_id)}/alpha-decay")

    def create_paper_trade(self, payload: JsonObject | PaperTradeCreate) -> JsonObject:
        return self._post("/paper-trades", _as_payload(payload))

    def list_paper_trades(self, limit: int | None = None, offset: int = 0) -> Any:
        if limit is None and offset == 0:
            return self._get("/paper-trades")
        return self._get(f"/paper-trades?limit={limit or 100}&offset={offset}")

    def create_service_account(self, name: str, scopes: list[str] | None = None) -> JsonObject:
        return self._post("/enterprise/service-accounts", {"name": name, "scopes": scopes or ["public:read"]})

    def rotate_service_account(self, service_account_id: str, rotated_by: str = "system") -> JsonObject:
        return self._post(f"/enterprise/service-accounts/{_path(service_account_id)}/rotate", {"rotatedBy": rotated_by})

    def revoke_service_account(self, service_account_id: str) -> JsonObject:
        return self._post(f"/enterprise/service-accounts/{_path(service_account_id)}/revoke", {})

    def create_audit_export(self, requested_by: str = "admin", scope: str = "all") -> JsonObject:
        return self._post("/enterprise/audit-exports", {"requestedBy": requested_by, "scope": scope})

    def configure_sso(
        self,
        provider: str,
        issuer_url: str,
        audience: str,
        default_role: str = "viewer",
        role_mappings: dict[str, str] | None = None,
    ) -> JsonObject:
        return self._post(
            "/enterprise/sso/config",
            {
                "provider": provider,
                "issuerUrl": issuer_url,
                "audience": audience,
                "defaultRole": default_role,
                "roleMappings": role_mappings or {},
            },
        )

    def get_sso_config(self) -> JsonObject:
        return self._get("/enterprise/sso/config")

    def get_offline_bundle_manifest(self) -> JsonObject:
        return self._get("/enterprise/deployment-bundles/offline")

    def get_enterprise_security_packet(self) -> JsonObject:
        return self._get("/enterprise/support/security-packet")

    def ingest_warm_path_event(self, payload: JsonObject) -> JsonObject:
        return self._post("/execution/warm-path/events", payload)

    def list_warm_path_events(self) -> list[JsonObject]:
        return self._get("/execution/warm-path/events")

    def list_service_accounts(self) -> list[JsonObject]:
        return self._get("/enterprise/service-accounts")

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: JsonObject) -> Any:
        return self._request("POST", path, body)

    def _request(self, method: str, path: str, body: JsonObject | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if self.transport is not None:
            return self.transport(method, path, body, headers, self.timeout)

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - caller controls API URL.
                content_type = response.headers.get("content-type", "")
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            payload = _decode_error_payload(exc)
            message = _error_message(payload) or f"Ambrosia API request failed with HTTP {exc.code}"
            raise AmbrosiaApiError(message, status_code=exc.code, payload=payload) from exc
        except URLError as exc:
            raise AmbrosiaApiError(f"Ambrosia API unavailable: {exc.reason}") from exc

        if "application/json" not in content_type:
            raise AmbrosiaApiError("Ambrosia API returned a non-JSON response")
        return json.loads(raw) if raw else None


def _decode_error_payload(exc: HTTPError) -> Any:
    try:
        raw = exc.read().decode("utf-8")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("message"), str):
            return payload["message"]
        if isinstance(payload.get("detail"), str):
            return payload["detail"]
    return None


def _as_payload(payload: PayloadObject) -> JsonObject:
    if isinstance(payload, dict):
        return payload
    return payload.to_payload()


def _normalize_ticker(ticker: str) -> str:
    return " ".join(ticker.replace("/", " ").split())


def _path(value: str) -> str:
    return quote(value, safe="")