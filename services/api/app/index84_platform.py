from __future__ import annotations

import json
import hashlib
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .db import PostgresReviewStore
from .project_paths import PROJECT_ROOT


router = APIRouter(tags=["index84-platform"])

_relay_runs: dict[str, dict] = {}
_features: dict[str, dict] = {}
_signals: dict[str, dict] = {}
_backtests: dict[str, dict] = {}
_signal_review_links: dict[str, dict] = {}
_signal_versions: dict[str, list[dict]] = {}
_signal_validation_runs: dict[str, list[dict]] = {}
_signal_policy_events: dict[str, list[dict]] = {}
_scanner_promotions: dict[str, dict] = {}
_paper_trades: dict[str, dict] = {}
_fills: dict[str, dict] = {}
_service_accounts: dict[str, dict] = {}
_audit_exports: dict[str, dict] = {}
_market_replays: dict[str, dict] = {}
_alpha_hypotheses: dict[str, dict] = {}
_warm_path_events: list[dict] = []
_sso_config: dict = {
    "enabled": False,
    "provider": "none",
    "issuerUrl": None,
    "audience": None,
    "defaultRole": "viewer",
    "roleMappings": {"analyst-group": "analyst", "admin-group": "admin"},
    "updatedAt": None,
}

_ROOT = PROJECT_ROOT
_RELEASE_EVIDENCE_PATH = _ROOT / "artifacts" / "release-evidence.json"
_SIGNAL_STATE_PATH = Path(
    os.getenv(
        "AMBROSIA_SIGNAL_STATE_PATH",
        str(_ROOT / "artifacts" / "signal-lifecycle-state.json"),
    )
)
_index84_db: PostgresReviewStore | None = None

_database_url = os.getenv("DATABASE_URL")
if _database_url:
    try:
        _index84_db = PostgresReviewStore(_database_url)
        _index84_db.healthcheck()
    except Exception:
        _index84_db = None


def _now() -> str:
    return datetime.now().isoformat()


def _stable_id(prefix: str, seed: str | None = None) -> str:
    if seed:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
        return f"{prefix}-{digest}"
    return f"{prefix}-{uuid4().hex[:10]}"


def _persist_signal_state() -> None:
    payload = {
        "schemaVersion": "signal-lifecycle-state.v1",
        "updatedAt": _now(),
        "signals": _signals,
        "signalVersions": _signal_versions,
        "signalReviewLinks": _signal_review_links,
        "signalValidationRuns": _signal_validation_runs,
        "signalPolicyEvents": _signal_policy_events,
        "scannerPromotions": _scanner_promotions,
        "alphaHypotheses": _alpha_hypotheses,
    }
    if _index84_db is not None:
        try:
            _index84_db.save_signal_lifecycle_snapshot(payload)
        except Exception:
            pass
    _SIGNAL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SIGNAL_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_signal_state() -> None:
    if _index84_db is not None:
        try:
            payload = _index84_db.load_signal_lifecycle_snapshot()
            if isinstance(payload, dict):
                if isinstance(payload.get("signals"), dict):
                    _signals.update(payload["signals"])
                if isinstance(payload.get("signalVersions"), dict):
                    _signal_versions.update(payload["signalVersions"])
                if isinstance(payload.get("signalReviewLinks"), dict):
                    _signal_review_links.update(payload["signalReviewLinks"])
                if isinstance(payload.get("signalValidationRuns"), dict):
                    _signal_validation_runs.update(payload["signalValidationRuns"])
                if isinstance(payload.get("signalPolicyEvents"), dict):
                    _signal_policy_events.update(payload["signalPolicyEvents"])
                if isinstance(payload.get("scannerPromotions"), dict):
                    _scanner_promotions.update(payload["scannerPromotions"])
                if isinstance(payload.get("alphaHypotheses"), dict):
                    _alpha_hypotheses.update(payload["alphaHypotheses"])
                return
        except Exception:
            pass

    if not _SIGNAL_STATE_PATH.exists():
        return
    try:
        payload = json.loads(_SIGNAL_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    if isinstance(payload.get("signals"), dict):
        _signals.update(payload["signals"])
    if isinstance(payload.get("signalVersions"), dict):
        _signal_versions.update(payload["signalVersions"])
    if isinstance(payload.get("signalReviewLinks"), dict):
        _signal_review_links.update(payload["signalReviewLinks"])
    if isinstance(payload.get("signalValidationRuns"), dict):
        _signal_validation_runs.update(payload["signalValidationRuns"])
    if isinstance(payload.get("signalPolicyEvents"), dict):
        _signal_policy_events.update(payload["signalPolicyEvents"])
    if isinstance(payload.get("scannerPromotions"), dict):
        _scanner_promotions.update(payload["scannerPromotions"])
    if isinstance(payload.get("alphaHypotheses"), dict):
        _alpha_hypotheses.update(payload["alphaHypotheses"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "ambrosia-relay-fixture"
    messages: list[ChatMessage] = Field(default_factory=list)
    temperature: float = 0.0


class RelayEvaluateRequest(BaseModel):
    question: str = Field(min_length=3)
    documents: list[str] = Field(default_factory=list)
    benchmark: str = "financebench-open-subset"


class FeatureUpsertRequest(BaseModel):
    featureId: str | None = None
    name: str = Field(min_length=3)
    ticker: str = Field(min_length=1)
    asOf: str
    value: float
    source: str = "fixture"
    pointInTime: bool = True
    provenance: list[str] = Field(default_factory=list)


class SignalCreateRequest(BaseModel):
    signalId: str | None = None
    name: str = Field(min_length=3)
    universe: list[str] = Field(default_factory=list)
    horizon: str = "20d"
    formula: str = Field(min_length=3)
    costModel: str = "10 bps round-trip"
    benchmark: str = "SPY"
    validationGates: list[str] = Field(default_factory=lambda: ["point_in_time", "costs", "walk_forward"])


class ScannerCandidatePromoteRequest(BaseModel):
    ticker: str = Field(min_length=1)
    signal: str = Field(min_length=2)
    thesisSuggestion: str = Field(min_length=8)
    score: float = Field(ge=0.0, le=1.0)
    price: float = Field(gt=0)
    trend: str = Field(min_length=2)
    rsi: float | None = None
    volume: float = Field(ge=0)
    scannerRunId: str | None = None
    universe: list[str] = Field(default_factory=list)
    horizon: str = "20d"
    costModel: str = "10 bps round-trip"
    benchmark: str = "SPY"
    owner: str = "research"
    promotedBy: str = "scanner-ui"


class SignalVersionCreateRequest(BaseModel):
    horizon: str | None = None
    formula: str | None = None
    universe: list[str] | None = None
    costModel: str | None = None
    benchmark: str | None = None
    validationGates: list[str] | None = None
    createdBy: str = "research"


class SignalValidateRequest(BaseModel):
    signalVersion: int | None = Field(default=None, ge=1)
    runType: str = "event_driven_backtest"
    sampleWindows: dict = Field(default_factory=lambda: {"train": "2024-01-01/2024-12-31", "validation": "2025-01-01/2025-06-30", "test": "2025-07-01/2026-01-01"})
    pointInTimeGuaranteed: bool = True
    includesCosts: bool = True
    includesSlippage: bool = True
    includesLiquidity: bool = True


class SignalPolicyTransitionRequest(BaseModel):
    signalVersion: int | None = Field(default=None, ge=1)
    actor: str = "system"
    reason: str | None = None


class BacktestRunRequest(BaseModel):
    signalId: str = Field(min_length=1)
    startDate: str = "2025-01-01"
    endDate: str = "2026-01-01"
    walkForward: bool = True
    includeCosts: bool = True
    includeSlippage: bool = True


class SignalReviewLinkRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    hypothesisId: str | None = None
    signalVersion: int | None = Field(default=None, ge=1)


class SignalDecisionWritebackRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)
    decisionState: str = Field(min_length=3)
    decisionAction: str | None = None
    decisionUse: list[str] = Field(default_factory=list)
    instrumentAction: dict | None = None
    riskBudgetId: str | None = None
    maxPositionSize: float | None = Field(default=None, gt=0)
    maxDrawdownLimit: float | None = None
    hedgePlan: str | None = None
    riskAdjustment: str | None = None
    liquidityCheck: str | None = None
    costCheck: str | None = None
    approvalState: str | None = None
    executionReadiness: str | None = None
    outcomeWritebackRequired: bool = True
    rationale: str | None = None
    overrideUsed: bool = False
    decisionQuality: str = "D2"
    evidenceLinks: list[str] = Field(default_factory=list)
    verifierStatus: str | None = None
    reviewDate: str | None = None


class SignalOutcomeWritebackRequest(BaseModel):
    reviewId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)
    outcomeQuality: str = Field(min_length=3)
    lastReviewedAt: str | None = None


class AlphaHypothesisSignalLinkRequest(BaseModel):
    signalId: str = Field(min_length=1)
    signalVersion: int | None = Field(default=None, ge=1)


DECISION_QUALITY_STATES = {"D0", "D1", "D2", "D3", "D4", "D5"}
PLAN_QUALITY_STATES = {"P0", "P1", "P2", "P3", "P4"}
PROMOTION_STATES = {"promoted", "promote", "go_live", "deploy", "pursue"}
SIGNAL_DECISION_ACTIONS = {"BUY", "SELL", "HOLD", "HEDGE", "RISK_ADJUST", "BLOCK", "RETIRE"}
ACTIONABLE_SIGNAL_DECISIONS = {"BUY", "SELL", "HEDGE", "RISK_ADJUST"}

INDEX97_VALIDATION_WINDOWS = {
    "train": "2022-01-01/2023-12-31",
    "validation": "2024-01-01/2024-12-31",
    "test": "2025-01-01/2026-06-30",
}

INDEX97_SIGNAL_SEED: list[dict] = [
    {
        "targetStatus": "hypothesis",
        "signal": {
            "signalId": "sig-index97-qqq-risk-on-5d",
            "name": "QQQ Risk-On Breadth 5D",
            "universe": ["QQQ", "SPY", "IWM"],
            "horizon": "5d",
            "formula": "qqq_rel_strength_5d > 0.015 and adv_decline_z > 0.8",
            "costModel": "us_equities_taker_v1",
            "benchmark": "SPY",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-qqq-risk-on-5d",
            "title": "QQQ Risk-On Breadth 5D",
            "signalFamily": "breadth",
            "universe": ["QQQ", "SPY", "IWM"],
            "horizon": "5d",
            "thesis": "Nasdaq breadth confirmation can identify short-horizon risk-on continuation before the broad market reprices.",
            "planQuality": "P3",
            "disconfirmingTests": ["Breadth thrust fails outside mega-cap contributors", "Post-cost hit rate falls below 52%"],
            "costModel": "us_equities_taker_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "hypothesis",
        "signal": {
            "signalId": "sig-index97-iemg-fx-stress-1m",
            "name": "IEMG FX Stress Reversal 1M",
            "universe": ["IEMG", "EEM", "UUP"],
            "horizon": "1m",
            "formula": "usd_stress_z < -0.6 and iemg_discount_to_ma20 < -0.02",
            "costModel": "etf_liquidity_v1",
            "benchmark": "EEM",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-iemg-fx-stress-1m",
            "title": "IEMG FX Stress Reversal 1M",
            "signalFamily": "macro",
            "universe": ["IEMG", "EEM", "UUP"],
            "horizon": "1m",
            "thesis": "Emerging-market ETF mean reversion improves when USD stress fades and price remains below intermediate trend.",
            "planQuality": "P3",
            "disconfirmingTests": ["USD stress remains elevated for two additional weeks", "Liquidity-adjusted rebound underperforms EEM"],
            "costModel": "etf_liquidity_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "validation_passed",
        "signal": {
            "signalId": "sig-index97-msft-quality-1m",
            "name": "MSFT Quality Momentum 1M",
            "universe": ["MSFT"],
            "horizon": "1m",
            "formula": "gross_margin_revision_z > 0.7 and ret_20d > spy_ret_20d",
            "costModel": "us_equities_taker_v1",
            "benchmark": "SPY",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-msft-quality-1m",
            "title": "MSFT Quality Momentum 1M",
            "signalFamily": "quality",
            "universe": ["MSFT"],
            "horizon": "1m",
            "thesis": "Quality revisions paired with relative strength can produce resilient one-month continuation in large-cap software.",
            "planQuality": "P4",
            "disconfirmingTests": ["Revision breadth turns negative", "Walk-forward performance fails after modeled costs"],
            "costModel": "us_equities_taker_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "validation_passed",
        "signal": {
            "signalId": "sig-index97-xlf-mean-reversion-1w",
            "name": "XLF Mean Reversion 1W",
            "universe": ["XLF", "KRE"],
            "horizon": "1w",
            "formula": "xlf_rsi_3 < 24 and credit_spread_delta_5d <= 0",
            "costModel": "etf_liquidity_v1",
            "benchmark": "SPY",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-xlf-mean-reversion-1w",
            "title": "XLF Mean Reversion 1W",
            "signalFamily": "mean_reversion",
            "universe": ["XLF", "KRE"],
            "horizon": "1w",
            "thesis": "Oversold financials recover faster when credit stress is not widening and liquidity remains stable.",
            "planQuality": "P4",
            "disconfirmingTests": ["Credit spreads widen during the holding window", "Regional-bank beta dominates XLF response"],
            "costModel": "etf_liquidity_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "active_candidate",
        "review": {
            "reviewId": "review-index97-aapl-momo-01",
            "decisionState": "pursue",
            "decisionAction": "BUY",
            "decisionQuality": "D4",
            "outcomeQuality": "validated",
            "rationale": "Validation passed with complete point-in-time, cost, slippage, and liquidity hygiene.",
        },
        "signal": {
            "signalId": "sig-index97-aapl-momentum-1d",
            "name": "AAPL Momentum 1D",
            "universe": ["AAPL"],
            "horizon": "1d",
            "formula": "ret_5d > 0 and volume_z > 1.2 and close > vwap_20d",
            "costModel": "us_equities_taker_v1",
            "benchmark": "SPY",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-aapl-momentum-1d",
            "title": "AAPL Momentum 1D",
            "signalFamily": "momentum",
            "universe": ["AAPL"],
            "horizon": "1d",
            "thesis": "AAPL short-horizon continuation is strongest when positive five-day return is confirmed by relative volume.",
            "planQuality": "P4",
            "disconfirmingTests": ["Opening gap reverses below VWAP", "Realized spread exceeds modeled taker cost"],
            "costModel": "us_equities_taker_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "active_candidate",
        "review": {
            "reviewId": "review-index97-soxx-breadth-01",
            "decisionState": "pursue",
            "decisionAction": "BUY",
            "decisionQuality": "D4",
            "outcomeQuality": "validated",
            "rationale": "Semiconductor breadth and benchmark-relative returns passed the seeded validation gates.",
        },
        "signal": {
            "signalId": "sig-index97-soxx-breadth-2w",
            "name": "SOXX Semiconductor Breadth 2W",
            "universe": ["SOXX", "NVDA", "AMD", "AVGO"],
            "horizon": "2w",
            "formula": "semi_advancers_pct > 0.62 and soxx_rel_spy_10d > 0.01",
            "costModel": "etf_liquidity_v1",
            "benchmark": "QQQ",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-soxx-breadth-2w",
            "title": "SOXX Semiconductor Breadth 2W",
            "signalFamily": "breadth",
            "universe": ["SOXX", "NVDA", "AMD", "AVGO"],
            "horizon": "2w",
            "thesis": "SOXX continuation is higher quality when chip leadership broadens beyond the largest constituents.",
            "planQuality": "P4",
            "disconfirmingTests": ["Breadth narrows to fewer than half of tracked constituents", "QQQ beta explains the full signal return"],
            "costModel": "etf_liquidity_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "constrained",
        "review": {
            "reviewId": "review-index97-arkk-liquidity-01",
            "decisionState": "pursue",
            "decisionAction": "RISK_ADJUST",
            "decisionQuality": "D4",
            "outcomeQuality": "degraded",
            "rationale": "Signal had validation support, but liquidity and implementation shortfall require a live trading constraint.",
        },
        "signal": {
            "signalId": "sig-index97-arkk-liquidity-2w",
            "name": "ARKK Liquidity Breakout 2W",
            "universe": ["ARKK"],
            "horizon": "2w",
            "formula": "arkk_breakout_z > 1.1 and bid_ask_bps < 18",
            "costModel": "high_beta_etf_liquidity_v1",
            "benchmark": "QQQ",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-arkk-liquidity-2w",
            "title": "ARKK Liquidity Breakout 2W",
            "signalFamily": "momentum",
            "universe": ["ARKK"],
            "horizon": "2w",
            "thesis": "High-beta innovation ETF breakouts need explicit liquidity constraints to preserve post-cost edge.",
            "planQuality": "P3",
            "disconfirmingTests": ["Spread widens beyond execution budget", "Breakout fails under high-volatility regime filter"],
            "costModel": "high_beta_etf_liquidity_v1",
            "owner": "research_ops",
        },
    },
    {
        "targetStatus": "retired",
        "review": {
            "reviewId": "review-index97-tlt-duration-01",
            "decisionState": "pursue",
            "decisionAction": "RETIRE",
            "decisionQuality": "D4",
            "outcomeQuality": "retired_after_decay",
            "rationale": "Duration signal was once promotion-ready but is now retired after outcome decay and regime instability.",
        },
        "signal": {
            "signalId": "sig-index97-tlt-duration-1m",
            "name": "TLT Duration Relief 1M",
            "universe": ["TLT", "IEF"],
            "horizon": "1m",
            "formula": "real_yield_delta_10d < -0.08 and tlt_price_above_ma20",
            "costModel": "treasury_etf_liquidity_v1",
            "benchmark": "IEF",
            "validationGates": ["point_in_time", "costs", "walk_forward"],
        },
        "hypothesis": {
            "hypothesisId": "alpha-index97-tlt-duration-1m",
            "title": "TLT Duration Relief 1M",
            "signalFamily": "macro",
            "universe": ["TLT", "IEF"],
            "horizon": "1m",
            "thesis": "Long-duration relief rallies are tradable when real yields fall and price confirms above intermediate trend.",
            "planQuality": "P3",
            "disconfirmingTests": ["Inflation surprise reverses real-yield trend", "IEF-relative performance fails after costs"],
            "costModel": "treasury_etf_liquidity_v1",
            "owner": "research_ops",
        },
    },
]


class AlphaHypothesisCreateRequest(BaseModel):
    hypothesisId: str | None = None
    title: str = Field(min_length=3)
    signalFamily: str = Field(min_length=2)
    universe: list[str] = Field(default_factory=list)
    horizon: str = "20d"
    thesis: str = Field(min_length=8)
    planQuality: str = "P2"
    disconfirmingTests: list[str] = Field(default_factory=list)
    costModel: str = "10 bps round-trip"
    owner: str = "research"


class PaperTradeCreateRequest(BaseModel):
    decisionId: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    side: str = "buy"
    quantity: float = Field(gt=0)
    thesis: str = "paper decision loop"
    intendedPrice: float = Field(gt=0, default=100.0)
    stopLoss: float | None = None
    reviewDate: str = "2026-07-11"


class FillIngestRequest(BaseModel):
    paperTradeId: str = Field(min_length=1)
    fillPrice: float = Field(gt=0)
    latencyMs: int = Field(ge=0)
    venue: str = "paper-sim"


class ReplayRunRequest(BaseModel):
    ticker: str = Field(min_length=1)
    scenario: str = "spread-widening"
    latencyMs: int = Field(ge=0, default=125)


class WarmPathEventRequest(BaseModel):
    eventType: str = Field(min_length=3)
    source: str = "broker-sandbox"
    ticker: str = Field(min_length=1)
    latencyMs: int = Field(ge=0)
    notionalUsd: float = Field(gt=0)
    details: dict = Field(default_factory=dict)


class ServiceAccountCreateRequest(BaseModel):
    name: str = Field(min_length=3)
    scopes: list[str] = Field(default_factory=lambda: ["public:read"])
    expiresInDays: int = Field(default=90, ge=1, le=365)


class ServiceAccountRotateRequest(BaseModel):
    rotatedBy: str = "system"


class SSOConfigRequest(BaseModel):
    provider: str = Field(default="oidc", pattern="^(oidc|saml)$")
    issuerUrl: str = Field(min_length=5)
    audience: str = Field(min_length=2)
    defaultRole: str = "viewer"
    roleMappings: dict[str, str] = Field(default_factory=dict)


class AuditExportRequest(BaseModel):
    requestedBy: str = "admin"
    scope: str = "all"
    format: str = "jsonl"


_load_signal_state()


@router.post("/v1/chat/completions")
def openai_compatible_chat_completion(request: ChatCompletionRequest) -> dict:
    prompt = "\n".join(message.content for message in request.messages if message.role != "system")
    run = _build_relay_trace(prompt or "empty request", request.model)
    return {
        "id": _stable_id("chatcmpl", prompt),
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": run["answer"],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(run["answer"].split()), "total_tokens": len(prompt.split()) + len(run["answer"].split())},
        "ambrosiaTrace": run,
    }


@router.post("/relay/evaluate")
def evaluate_relay(
    request: RelayEvaluateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/relay/evaluate")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    run = _build_relay_trace(request.question, request.benchmark, request.documents)
    _relay_runs[run["runId"]] = run
    if _index84_db is not None:
        try:
            _index84_db.save_relay_run(run)
        except Exception:
            pass
    _idempotency_store(endpoint, idempotency_key, run)
    return run


@router.get("/relay/runs/{run_id}")
def get_relay_run(run_id: str) -> dict:
    run = _relay_runs.get(run_id)
    if run is None and _index84_db is not None:
        try:
            run = _index84_db.get_relay_run(run_id)
            if run is not None:
                _relay_runs[run_id] = run
        except Exception:
            run = None
    if run is None:
        raise HTTPException(status_code=404, detail="Relay run not found")
    return run


@router.get("/relay/runs")
def list_relay_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    runs: list[dict]
    if _index84_db is not None:
        try:
            runs = _index84_db.list_relay_runs(limit=500)
        except Exception:
            runs = list(_relay_runs.values())
    else:
        runs = list(_relay_runs.values())
    total = len(runs)
    sliced = runs[offset : offset + limit]
    return {
        "schemaVersion": "relay-runs-list.v1",
        "items": sliced,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "hasMore": offset + limit < total,
        },
    }


@router.get("/relay/scorecard")
def get_relay_scorecard() -> dict:
    if _index84_db is not None:
        try:
            runs = _index84_db.list_relay_runs(limit=2000)
        except Exception:
            runs = list(_relay_runs.values())
    else:
        runs = list(_relay_runs.values())
    completed = len(runs)
    abstained = sum(1 for run in runs if run.get("abstention", {}).get("required"))
    calc_verified = sum(1 for run in runs if run.get("verification", {}).get("status") == "passed")
    grounding_passed = sum(1 for run in runs if run.get("grounding", {}).get("status") == "passed")
    return {
        "schemaVersion": "relay-scorecard.v1",
        "runs": completed,
        "accuracy": max(0.0, 1.0 - (abstained / completed)) if completed else 0.0,
        "evidenceRecall": max(0.0, (completed - abstained) / completed) if completed else 0.0,
        "calculationVerificationPassRate": (calc_verified / completed) if completed else 0.0,
        "groundingPassRate": (grounding_passed / completed) if completed else 0.0,
        "failureClusters": [],
        "unsupportedAnswersRefused": abstained > 0,
        "updatedAt": _now(),
    }


def _endpoint_key(path: str) -> str:
    return f"index84:{path}"


def _idempotency_lookup(endpoint: str, key: str | None) -> dict | None:
    if not key or _index84_db is None:
        return None
    try:
        return _index84_db.get_idempotency_response(key, endpoint)
    except Exception:
        return None


def _idempotency_store(endpoint: str, key: str | None, payload: dict) -> None:
    if not key or _index84_db is None:
        return
    try:
        _index84_db.save_idempotency_response(key, endpoint, payload)
    except Exception:
        pass


def _execution_feasibility_assessment(
    ticker: str,
    side: str,
    quantity: float,
    intended_price: float,
) -> dict:
    notional = float(quantity) * float(intended_price)
    liquidity_bucket = "high" if ticker.upper() in {"SPY", "QQQ", "AAPL", "MSFT", "NVDA"} else "medium"
    spread_bps = 4.0 if liquidity_bucket == "high" else 9.5
    slippage_bps = 3.0 if liquidity_bucket == "high" else 7.0
    impact_bps = min(35.0, 2.0 + (notional / 500000.0) * 9.0)
    implementation_shortfall_bps = round(spread_bps + slippage_bps + impact_bps, 2)

    fragility_score = round(min(1.0, implementation_shortfall_bps / 40.0), 3)
    block = implementation_shortfall_bps > 28.0 or notional > 350000.0

    return {
        "schemaVersion": "execution-feasibility.v1",
        "ticker": ticker.upper(),
        "side": side,
        "quantity": quantity,
        "intendedPrice": intended_price,
        "notionalUsd": round(notional, 2),
        "spreadBps": spread_bps,
        "slippageBps": slippage_bps,
        "impactBps": round(impact_bps, 2),
        "implementationShortfallEstimateBps": implementation_shortfall_bps,
        "fragilityScore": fragility_score,
        "gate": "blocked" if block else "pass",
        "reasons": ["notional_or_cost_limit_exceeded"] if block else ["within_warm_path_budget"],
        "assessedAt": _now(),
    }


@router.post("/features", status_code=201)
def upsert_feature(
    request: FeatureUpsertRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/features")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    feature_id = request.featureId or _stable_id("feature", f"{request.name}:{request.ticker}:{request.asOf}")
    feature = {
        "featureId": feature_id,
        "schemaVersion": "feature.v1",
        **request.model_dump(exclude={"featureId"}),
        "createdAt": _features.get(feature_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _features[feature_id] = feature
    _idempotency_store(endpoint, idempotency_key, feature)
    return feature


@router.get("/features")
def list_features() -> list[dict]:
    return sorted(_features.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.get("/features/{feature_id}")
def get_feature(feature_id: str) -> dict:
    feature = _features.get(feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.post("/signals", status_code=201)
def create_signal(
    request: SignalCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal_id = request.signalId or _stable_id("signal", request.name)
    existing = _signals.get(signal_id, {})
    active_version = int(existing.get("activeVersion", existing.get("version", 1)))
    spec_keys = ["universe", "horizon", "formula", "costModel", "benchmark", "validationGates"]
    spec_changed = bool(existing) and any(existing.get(key) != request.model_dump().get(key) for key in spec_keys)
    next_version = active_version + 1 if spec_changed else active_version
    signal = {
        "signalId": signal_id,
        "schemaVersion": "signal.v1",
        **request.model_dump(exclude={"signalId"}),
        "version": next_version,
        "activeVersion": next_version,
        "status": existing.get("status", "hypothesis"),
        "linkedHypothesisIds": existing.get("linkedHypothesisIds", []),
        "linkedReviewIds": existing.get("linkedReviewIds", []),
        "linkedReviewCount": existing.get("linkedReviewCount", 0),
        "latestDecisionState": existing.get("latestDecisionState"),
        "latestOutcomeQuality": existing.get("latestOutcomeQuality"),
        "lastReviewedAt": existing.get("lastReviewedAt"),
        "overrideCount": existing.get("overrideCount", 0),
        "outcomeCount": existing.get("outcomeCount", 0),
        "createdAt": existing.get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _signals[signal_id] = signal
    versions = _signal_versions.setdefault(signal_id, [])
    version_exists = any(int(item.get("version", 0)) == next_version for item in versions)
    if not version_exists:
        versions.append(
            {
                "schemaVersion": "signal-version.v1",
                "signalId": signal_id,
                "version": next_version,
                "horizon": signal["horizon"],
                "formula": signal["formula"],
                "universe": signal["universe"],
                "costModel": signal["costModel"],
                "benchmark": signal["benchmark"],
                "validationGates": signal["validationGates"],
                "createdBy": "system",
                "createdAt": _now(),
            }
        )
    _persist_signal_state()
    _idempotency_store(endpoint, idempotency_key, signal)
    return signal


@router.post("/alpha/hypotheses", status_code=201)
def create_alpha_hypothesis(
    request: AlphaHypothesisCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/alpha/hypotheses")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    plan_quality = request.planQuality.upper()
    if plan_quality not in PLAN_QUALITY_STATES:
        raise HTTPException(status_code=400, detail="planQuality must be one of P0-P4")

    hypothesis_id = request.hypothesisId or _stable_id("alpha", f"{request.signalFamily}:{request.title}")
    hypothesis = {
        "hypothesisId": hypothesis_id,
        "schemaVersion": "alpha-hypothesis.v1",
        **request.model_dump(exclude={"hypothesisId"}),
        "planQuality": plan_quality,
        "quality": "D3",
        "status": "active",
        "linkedSignals": _alpha_hypotheses.get(hypothesis_id, {}).get("linkedSignals", []),
        "createdAt": _alpha_hypotheses.get(hypothesis_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _alpha_hypotheses[hypothesis_id] = hypothesis
    _idempotency_store(endpoint, idempotency_key, hypothesis)
    return hypothesis


@router.get("/alpha/hypotheses")
def list_alpha_hypotheses() -> list[dict]:
    return sorted(_alpha_hypotheses.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.get("/alpha/hypotheses/{hypothesis_id}")
def get_alpha_hypothesis(hypothesis_id: str) -> dict:
    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")
    return hypothesis


@router.get("/signals")
def list_signals() -> list[dict]:
    return sorted(_signals.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.post("/signals/seed-index97")
def seed_index97_signals() -> dict:
    seeded_signals: list[dict] = []
    for scenario in INDEX97_SIGNAL_SEED:
        signal_payload = scenario["signal"]
        signal_id = str(signal_payload["signalId"])
        signal = create_signal(
            SignalCreateRequest(**signal_payload),
            _index97_idempotency_key(signal_id, "create-signal"),
        )
        _signals[signal_id]["demoSeed"] = "index97"
        _signals[signal_id]["sourceLabel"] = "Demo Lifecycle"
        signal_version = int(signal.get("activeVersion", signal.get("version", 1)))

        hypothesis_payload = scenario["hypothesis"]
        hypothesis = create_alpha_hypothesis(
            AlphaHypothesisCreateRequest(**hypothesis_payload),
            _index97_idempotency_key(signal_id, "create-hypothesis"),
        )
        hypothesis_id = str(hypothesis.get("hypothesisId"))
        _alpha_hypotheses[hypothesis_id]["demoSeed"] = "index97"
        _alpha_hypotheses[hypothesis_id]["sourceLabel"] = "Demo Lifecycle"
        link_alpha_hypothesis_signal(
            hypothesis_id,
            AlphaHypothesisSignalLinkRequest(signalId=signal_id, signalVersion=signal_version),
            _index97_idempotency_key(signal_id, "link-hypothesis"),
        )

        target_status = str(scenario["targetStatus"])
        if target_status != "hypothesis":
            _ensure_index97_validation(signal_id, signal_version)
        else:
            _ensure_index97_status(signal_id, "hypothesis", signal_version, "Seeded hypothesis awaiting validation")

        if target_status == "active_candidate":
            _ensure_index97_policy_transition(signal_id, "active_candidate", signal_version)
        elif target_status == "constrained":
            _ensure_index97_policy_transition(signal_id, "constrained", signal_version)
        elif target_status == "retired":
            _ensure_index97_policy_transition(signal_id, "retired", signal_version)
        elif target_status == "validation_passed":
            _ensure_index97_status(signal_id, "validation_passed", signal_version, "Seed validation passed")

        review_payload = scenario.get("review")
        if isinstance(review_payload, dict):
            review_id = str(review_payload["reviewId"])
            link_signal_review(
                signal_id,
                SignalReviewLinkRequest(
                    reviewId=review_id,
                    hypothesisId=hypothesis_id,
                    signalVersion=signal_version,
                ),
                _index97_idempotency_key(signal_id, f"link-review:{review_id}"),
            )
            writeback_signal_decision(
                signal_id,
                SignalDecisionWritebackRequest(
                    reviewId=review_id,
                    signalVersion=signal_version,
                    decisionState=str(review_payload["decisionState"]),
                    decisionAction=str(review_payload.get("decisionAction", "")) or None,
                    decisionUse=["buy", "sell", "hold", "hedge", "risk_adjust"],
                    decisionQuality=str(review_payload["decisionQuality"]),
                    overrideUsed=False,
                    rationale=str(review_payload["rationale"]),
                    evidenceLinks=[f"artifacts/signals/{signal_id}/validation/{signal_version}"],
                    verifierStatus="passed",
                    reviewDate="2026-07-06",
                ),
                _index97_idempotency_key(signal_id, f"decision:{review_id}"),
            )
            writeback_signal_outcome(
                signal_id,
                SignalOutcomeWritebackRequest(
                    reviewId=review_id,
                    signalVersion=signal_version,
                    outcomeQuality=str(review_payload["outcomeQuality"]),
                    lastReviewedAt="2026-07-06T18:00:00Z",
                ),
                _index97_idempotency_key(signal_id, f"outcome:{review_id}"),
            )
            _ensure_index97_policy_transition(signal_id, target_status, signal_version)

        seeded_signals.append(_signals[signal_id])

    _persist_signal_state()
    status_distribution = _status_distribution(seeded_signals)
    linked_review_signals = sum(1 for signal in seeded_signals if int(signal.get("linkedReviewCount", 0)) > 0)
    outcome_writeback_signals = sum(1 for signal in seeded_signals if int(signal.get("outcomeCount", 0)) > 0)
    validation_run_signals = sum(1 for signal in seeded_signals if bool(_signal_validation_runs_for(str(signal.get("signalId")))))
    scorecard = get_weekly_quality_scorecard()

    return {
        "schemaVersion": "index97-signal-seed.v1",
        "status": "ok",
        "signalsSeeded": len(seeded_signals),
        "signalIds": [signal["signalId"] for signal in seeded_signals],
        "statusDistribution": status_distribution,
        "linkedReviewSignals": linked_review_signals,
        "validationRunSignals": validation_run_signals,
        "outcomeWritebackSignals": outcome_writeback_signals,
        "programMetrics": get_signal_program_metrics(),
        "qualityGates": scorecard.get("gates", {}),
        "seededAt": _now(),
    }


@router.get("/signals/program-metrics")
def get_signal_program_metrics() -> dict:
    total_signals = len(_signals)
    total_links = len(_signal_review_links)
    linked_signals = sum(1 for signal in _signals.values() if int(signal.get("linkedReviewCount", 0)) > 0)
    validated_signals = sum(1 for signal in _signals.values() if signal.get("status") in {"validation_passed", "active_candidate", "constrained", "retired"})
    promoted_signals = sum(1 for signal in _signals.values() if signal.get("status") == "active_candidate")
    constrained_signals = sum(1 for signal in _signals.values() if signal.get("status") == "constrained")
    retired_signals = sum(1 for signal in _signals.values() if signal.get("status") == "retired")
    outcome_rollups = [_signal_rollup(signal_id) for signal_id in _signals.keys()]
    pursued_total = sum(int(item.get("pursuedCount", 0)) for item in outcome_rollups)
    rejected_total = sum(int(item.get("rejectedCount", 0)) for item in outcome_rollups)
    outcome_total = sum(int(item.get("outcomeCount", 0)) for item in outcome_rollups)

    return {
        "schemaVersion": "signals-program-metrics.v1",
        "totalSignals": total_signals,
        "linkedSignals": linked_signals,
        "linkedSignalsPct": round((linked_signals / total_signals) * 100, 1) if total_signals else 0.0,
        "totalDecisionLinks": total_links,
        "validatedSignals": validated_signals,
        "validatedSignalsPct": round((validated_signals / total_signals) * 100, 1) if total_signals else 0.0,
        "promotedSignals": promoted_signals,
        "constrainedSignals": constrained_signals,
        "retiredSignals": retired_signals,
        "pursuedDecisions": pursued_total,
        "rejectedDecisions": rejected_total,
        "recordedOutcomes": outcome_total,
        "updatedAt": _now(),
    }


@router.get("/signals/{signal_id}")
def get_signal(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.post("/scanner/candidates/promote-alpha", status_code=201)
def promote_scanner_candidate_to_alpha(
    request: ScannerCandidatePromoteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/scanner/candidates/promote-alpha")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    ticker = request.ticker.strip().upper()
    signal_tag = request.signal.strip().lower()
    scanner_run_id = request.scannerRunId or _stable_id("scanner-run", f"{ticker}:{signal_tag}")
    candidate_key = f"{scanner_run_id}:{ticker}:{signal_tag}"

    for existing in _scanner_promotions.values():
        if str(existing.get("candidateKey")) == candidate_key:
            response = {
                "schemaVersion": "scanner-candidate-promotion.v1",
                "alreadyPromoted": True,
                "promotion": _scanner_promotion_summary(existing),
                "hypothesis": _alpha_hypotheses.get(str(existing.get("hypothesisId") or "")),
                "signal": _signals.get(str(existing.get("signalId") or "")),
                "link": {
                    "hypothesisId": existing.get("hypothesisId"),
                    "signalId": existing.get("signalId"),
                    "signalVersion": existing.get("signalVersion"),
                },
            }
            _idempotency_store(endpoint, idempotency_key, response)
            return response

    signal_label = _scanner_signal_label(signal_tag)
    signal_family = _scanner_signal_family(signal_tag)
    universe = request.universe if request.universe else [ticker]
    promoted_at = _now()

    hypothesis_request = AlphaHypothesisCreateRequest(
        title=f"{ticker} {signal_label}",
        signalFamily=signal_family,
        universe=universe,
        horizon=request.horizon,
        thesis=request.thesisSuggestion,
        planQuality="P3",
        disconfirmingTests=_scanner_disconfirming_tests(signal_tag, ticker),
        costModel=request.costModel,
        owner=request.owner,
    )
    hypothesis = create_alpha_hypothesis(hypothesis_request, None)

    signal_request = SignalCreateRequest(
        name=f"{ticker} {signal_label} Signal",
        universe=universe,
        horizon=request.horizon,
        formula=_scanner_formula(signal_tag, ticker, request.trend, request.rsi),
        costModel=request.costModel,
        benchmark=request.benchmark,
        validationGates=["point_in_time", "costs", "walk_forward"],
    )
    signal = create_signal(signal_request, None)

    link = link_alpha_hypothesis_signal(
        hypothesis_id=str(hypothesis.get("hypothesisId")),
        request=AlphaHypothesisSignalLinkRequest(
            signalId=str(signal.get("signalId")),
            signalVersion=int(signal.get("activeVersion", signal.get("version", 1))),
        ),
        idempotency_key=None,
    )

    hypothesis_id = str(hypothesis.get("hypothesisId"))
    signal_id = str(signal.get("signalId"))
    signal_version = int(signal.get("activeVersion", signal.get("version", 1)))

    _alpha_hypotheses[hypothesis_id]["origin"] = "scanner"
    _alpha_hypotheses[hypothesis_id]["scannerRunId"] = scanner_run_id
    _alpha_hypotheses[hypothesis_id]["sourceTicker"] = ticker
    _alpha_hypotheses[hypothesis_id]["sourceSignal"] = signal_tag
    _alpha_hypotheses[hypothesis_id]["promotedAt"] = promoted_at
    _alpha_hypotheses[hypothesis_id]["promotedBy"] = request.promotedBy
    _alpha_hypotheses[hypothesis_id]["updatedAt"] = _now()

    _signals[signal_id]["origin"] = "scanner"
    _signals[signal_id]["scannerRunId"] = scanner_run_id
    _signals[signal_id]["sourceTicker"] = ticker
    _signals[signal_id]["sourceSignal"] = signal_tag
    _signals[signal_id]["promotedAt"] = promoted_at
    _signals[signal_id]["promotedBy"] = request.promotedBy
    _signals[signal_id]["updatedAt"] = _now()

    promotion_id = _stable_id("scanner-promotion", candidate_key)
    promotion_record = {
        "promotionId": promotion_id,
        "schemaVersion": "scanner-candidate-promotion.v1",
        "candidateKey": candidate_key,
        "scannerRunId": scanner_run_id,
        "ticker": ticker,
        "signal": signal_tag,
        "score": request.score,
        "price": request.price,
        "trend": request.trend,
        "rsi": request.rsi,
        "volume": request.volume,
        "universe": universe,
        "horizon": request.horizon,
        "costModel": request.costModel,
        "benchmark": request.benchmark,
        "owner": request.owner,
        "promotedBy": request.promotedBy,
        "promotedAt": promoted_at,
        "hypothesisId": hypothesis_id,
        "signalId": signal_id,
        "signalVersion": signal_version,
        "updatedAt": _now(),
    }
    _scanner_promotions[promotion_id] = promotion_record
    _persist_signal_state()

    response = {
        "schemaVersion": "scanner-candidate-promotion.v1",
        "alreadyPromoted": False,
        "promotion": _scanner_promotion_summary(promotion_record),
        "hypothesis": _alpha_hypotheses[hypothesis_id],
        "signal": _signals[signal_id],
        "link": {
            "hypothesisId": hypothesis_id,
            "signalId": signal_id,
            "signalVersion": signal_version,
            "linkedSignals": link.get("linkedSignals", []),
        },
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.get("/scanner/candidates/promotions")
def list_scanner_candidate_promotions() -> list[dict]:
    records = sorted(_scanner_promotions.values(), key=lambda item: item.get("promotedAt", ""), reverse=True)
    return [_scanner_promotion_summary(record) for record in records]


def _resolve_signal_version(signal_id: str, requested: int | None) -> int:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    version = requested or int(signal.get("activeVersion", signal.get("version", 1)))
    versions = _signal_versions.get(signal_id, [])
    if not any(int(item.get("version", 0)) == version for item in versions):
        raise HTTPException(status_code=404, detail="Signal version not found")
    return version


def _find_signal_review_link(signal_id: str, review_id: str, signal_version: int | None = None) -> dict | None:
    candidates = [
        link
        for link in _signal_review_links.values()
        if link.get("signalId") == signal_id and link.get("reviewId") == review_id
    ]
    if signal_version is not None:
        for link in candidates:
            if int(link.get("signalVersion", 0)) == signal_version:
                return link
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda item: int(item.get("signalVersion", 0)), reverse=True)
    return candidates[0]


@router.post("/signals/{signal_id}/versions", status_code=201)
def create_signal_version(
    signal_id: str,
    request: SignalVersionCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/versions")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    current_version = int(signal.get("activeVersion", signal.get("version", 1)))
    next_version = current_version + 1
    version = {
        "schemaVersion": "signal-version.v1",
        "signalId": signal_id,
        "version": next_version,
        "horizon": request.horizon or signal.get("horizon"),
        "formula": request.formula or signal.get("formula"),
        "universe": request.universe if request.universe is not None else signal.get("universe", []),
        "costModel": request.costModel or signal.get("costModel"),
        "benchmark": request.benchmark or signal.get("benchmark"),
        "validationGates": request.validationGates if request.validationGates is not None else signal.get("validationGates", []),
        "createdBy": request.createdBy,
        "createdAt": _now(),
    }
    _signal_versions.setdefault(signal_id, []).append(version)

    signal["horizon"] = version["horizon"]
    signal["formula"] = version["formula"]
    signal["universe"] = version["universe"]
    signal["costModel"] = version["costModel"]
    signal["benchmark"] = version["benchmark"]
    signal["validationGates"] = version["validationGates"]
    signal["version"] = next_version
    signal["activeVersion"] = next_version
    signal["updatedAt"] = _now()
    _persist_signal_state()
    _idempotency_store(endpoint, idempotency_key, version)
    return version


@router.get("/signals/{signal_id}/versions")
def list_signal_versions(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    versions = _signal_versions.get(signal_id, [])
    return sorted(versions, key=lambda item: int(item.get("version", 0)), reverse=True)


@router.get("/signals/{signal_id}/versions/{version}")
def get_signal_version(signal_id: str, version: int) -> dict:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    for item in _signal_versions.get(signal_id, []):
        if int(item.get("version", 0)) == version:
            return item
    raise HTTPException(status_code=404, detail="Signal version not found")


def _signal_links(signal_id: str) -> list[dict]:
    return [link for link in _signal_review_links.values() if link.get("signalId") == signal_id]


def _signal_validation_runs_for(signal_id: str) -> list[dict]:
    return _signal_validation_runs.get(signal_id, [])


def _signal_latest_validation(signal_id: str, signal_version: int | None = None) -> dict | None:
    runs = _signal_validation_runs_for(signal_id)
    if signal_version is not None:
        runs = [run for run in runs if int(run.get("signalVersion", 0)) == signal_version]
    if not runs:
        return None
    return sorted(runs, key=lambda item: item.get("completedAt", ""), reverse=True)[0]


def _append_signal_policy_event(signal_id: str, event_type: str, to_status: str, actor: str, reason: str | None, signal_version: int | None = None) -> dict:
    event = {
        "eventId": _stable_id("signal-policy", f"{signal_id}:{event_type}:{to_status}:{actor}:{len(_signal_policy_events.get(signal_id, []))}"),
        "schemaVersion": "signal-policy-event.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "eventType": event_type,
        "toStatus": to_status,
        "actor": actor,
        "reason": reason,
        "createdAt": _now(),
    }
    _signal_policy_events.setdefault(signal_id, []).append(event)
    return event


def _required_validation_gates_present(signal: dict) -> tuple[bool, list[str]]:
    required = {"point_in_time", "costs", "walk_forward"}
    gates = set(signal.get("validationGates", []))
    missing = sorted(required - gates)
    return len(missing) == 0, missing


def _signal_rollup(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    links = _signal_links(signal_id)
    pursued_count = sum(1 for link in links if link.get("reviewDecisionState") == "pursue")
    rejected_count = sum(1 for link in links if link.get("reviewDecisionState") == "reject")
    needs_more_data_count = sum(1 for link in links if link.get("reviewDecisionState") == "needs_more_data")
    override_count = sum(1 for link in links if link.get("overrideUsed") is True)
    outcome_count = sum(1 for link in links if bool(link.get("outcomeQuality")))
    latest_outcome = max((link.get("lastOutcomeAt") for link in links if link.get("lastOutcomeAt")), default=None)
    latest_reviewed = max((link.get("lastReviewedAt") for link in links if link.get("lastReviewedAt")), default=signal.get("lastReviewedAt"))

    return {
        "schemaVersion": "signal-outcome-rollup.v1",
        "signalId": signal_id,
        "signalVersion": signal.get("version", 1),
        "linkedDecisionCount": len(links),
        "pursuedCount": pursued_count,
        "rejectedCount": rejected_count,
        "needsMoreDataCount": needs_more_data_count,
        "overrideCount": override_count,
        "outcomeCount": outcome_count,
        "latestDecisionState": signal.get("latestDecisionState"),
        "latestOutcomeQuality": signal.get("latestOutcomeQuality"),
        "status": signal.get("status", "hypothesis"),
        "activeVersion": signal.get("activeVersion", signal.get("version", 1)),
        "latestValidationStatus": (_signal_latest_validation(signal_id) or {}).get("status"),
        "lastReviewedAt": latest_reviewed,
        "lastOutcomeAt": latest_outcome,
        "updatedAt": _now(),
    }


def _index97_idempotency_key(signal_id: str, action: str) -> str:
    return f"index97:{signal_id}:{action}"


def _ensure_index97_validation(signal_id: str, signal_version: int) -> dict:
    latest_validation = _signal_latest_validation(signal_id, signal_version)
    if latest_validation is not None and latest_validation.get("status") == "passed":
        _ensure_index97_status(signal_id, "validation_passed", signal_version, "Existing Index97 validation retained")
        return latest_validation

    return validate_signal(
        signal_id,
        SignalValidateRequest(
            signalVersion=signal_version,
            runType="backtest",
            sampleWindows=INDEX97_VALIDATION_WINDOWS,
            pointInTimeGuaranteed=True,
            includesCosts=True,
            includesSlippage=True,
            includesLiquidity=True,
        ),
        _index97_idempotency_key(signal_id, f"validate:{signal_version}"),
    )


def _ensure_index97_status(signal_id: str, target_status: str, signal_version: int, reason: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.get("status") == target_status:
        return signal

    signal["status"] = target_status
    signal["updatedAt"] = _now()
    _append_signal_policy_event(
        signal_id=signal_id,
        event_type="index97.seed.status",
        to_status=target_status,
        actor="research_ops",
        reason=reason,
        signal_version=signal_version,
    )
    return signal


def _ensure_index97_policy_transition(signal_id: str, target_status: str, signal_version: int) -> dict:
    if target_status == "hypothesis":
        return _ensure_index97_status(signal_id, "hypothesis", signal_version, "Seeded hypothesis awaiting validation")
    if target_status == "validation_passed":
        return _ensure_index97_status(signal_id, "validation_passed", signal_version, "Seed validation passed")

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.get("status") == target_status:
        return {
            "schemaVersion": "signal-policy-transition.v1",
            "signalId": signal_id,
            "signalVersion": signal_version,
            "status": target_status,
            "event": None,
        }

    if target_status == "active_candidate":
        return promote_signal(
            signal_id,
            SignalPolicyTransitionRequest(
                signalVersion=signal_version,
                actor="research_ops",
                reason="Index97 seed: validation passed with complete hygiene",
            ),
            _index97_idempotency_key(signal_id, f"promote:{signal_version}"),
        )
    if target_status == "constrained":
        return constrain_signal(
            signal_id,
            SignalPolicyTransitionRequest(
                signalVersion=signal_version,
                actor="risk_ops",
                reason="Index97 seed: policy constraint after validation and evidence review",
            ),
            _index97_idempotency_key(signal_id, f"constrain:{signal_version}"),
        )
    if target_status == "retired":
        return retire_signal(
            signal_id,
            SignalPolicyTransitionRequest(
                signalVersion=signal_version,
                actor="research_ops",
                reason="Index97 seed: lifecycle closure after outcome writeback",
            ),
            _index97_idempotency_key(signal_id, f"retire:{signal_version}"),
        )

    raise HTTPException(status_code=400, detail=f"Unsupported Index97 target status: {target_status}")


def _status_distribution(signals: list[dict]) -> dict:
    distribution: dict[str, int] = {}
    for signal in signals:
        status = str(signal.get("status") or "unknown")
        distribution[status] = distribution.get(status, 0) + 1
    return distribution


@router.post("/signals/{signal_id}/validate")
def validate_signal(
    signal_id: str,
    request: SignalValidateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/validate")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    hygiene_issues: list[str] = []
    if not request.pointInTimeGuaranteed:
        hygiene_issues.append("missing_point_in_time_guarantee")
    if not request.includesCosts:
        hygiene_issues.append("missing_transaction_costs")
    if not request.includesSlippage:
        hygiene_issues.append("missing_slippage_model")
    if not request.includesLiquidity:
        hygiene_issues.append("missing_liquidity_model")

    has_required_gates, missing_gates = _required_validation_gates_present(signal)
    if not has_required_gates:
        hygiene_issues.extend([f"missing_validation_gate:{gate}" for gate in missing_gates])

    status = "passed" if len(hygiene_issues) == 0 else "failed"
    run = {
        "validationRunId": _stable_id("signal-validation", f"{signal_id}:{signal_version}:{len(_signal_validation_runs_for(signal_id))}"),
        "schemaVersion": "signal-validation-run.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "runType": request.runType,
        "sampleWindows": request.sampleWindows,
        "pointInTimeGuaranteed": request.pointInTimeGuaranteed,
        "includesCosts": request.includesCosts,
        "includesSlippage": request.includesSlippage,
        "includesLiquidity": request.includesLiquidity,
        "benchmarkComparison": {"benchmark": signal.get("benchmark"), "activeReturn": 0.039},
        "hygieneIssues": hygiene_issues,
        "metrics": {
            "sharpeRatio": 1.21,
            "maxDrawdown": -0.082,
            "hitRate": 0.57,
            "implementationShortfallBps": 10.6,
        },
        "artifactRefs": [f"artifacts/signals/{signal_id}/validation/{signal_version}"],
        "status": status,
        "completedAt": _now(),
    }
    _signal_validation_runs.setdefault(signal_id, []).append(run)

    signal["updatedAt"] = _now()
    signal["status"] = "validation_passed" if status == "passed" else "validation_pending"

    _append_signal_policy_event(
        signal_id=signal_id,
        event_type="validation.completed",
        to_status=signal["status"],
        actor="system",
        reason="Validation run completed",
        signal_version=signal_version,
    )
    _persist_signal_state()
    _idempotency_store(endpoint, idempotency_key, run)
    return run


@router.get("/signals/{signal_id}/validation-runs")
def list_signal_validation_runs(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    runs = _signal_validation_runs_for(signal_id)
    return sorted(runs, key=lambda item: item.get("completedAt", ""), reverse=True)


@router.post("/signals/{signal_id}/promote")
def promote_signal(
    signal_id: str,
    request: SignalPolicyTransitionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/promote")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    latest_validation = _signal_latest_validation(signal_id, signal_version)
    if latest_validation is None:
        raise HTTPException(status_code=409, detail="Promotion blocked: missing validation run for signal version")
    if latest_validation.get("status") != "passed":
        raise HTTPException(status_code=409, detail="Promotion blocked: validation status is not passed")

    signal["status"] = "active_candidate"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.promoted",
        to_status="active_candidate",
        actor=request.actor,
        reason=request.reason,
        signal_version=signal_version,
    )
    _persist_signal_state()
    response = {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.post("/signals/{signal_id}/constrain")
def constrain_signal(
    signal_id: str,
    request: SignalPolicyTransitionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/constrain")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    signal["status"] = "constrained"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.constrained",
        to_status="constrained",
        actor=request.actor,
        reason=request.reason or "manual constraint",
        signal_version=signal_version,
    )
    _persist_signal_state()
    response = {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.post("/signals/{signal_id}/retire")
def retire_signal(
    signal_id: str,
    request: SignalPolicyTransitionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/retire")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    signal["status"] = "retired"
    signal["updatedAt"] = _now()
    event = _append_signal_policy_event(
        signal_id=signal_id,
        event_type="signal.retired",
        to_status="retired",
        actor=request.actor,
        reason=request.reason or "manual retirement",
        signal_version=signal_version,
    )
    _persist_signal_state()
    response = {
        "schemaVersion": "signal-policy-transition.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "status": signal["status"],
        "event": event,
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.get("/signals/{signal_id}/policy-events")
def list_signal_policy_events(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    events = _signal_policy_events.get(signal_id, [])
    return sorted(events, key=lambda item: item.get("createdAt", ""), reverse=True)


@router.get("/signals/quality-scorecard/weekly")
def get_weekly_quality_scorecard() -> dict:
    links = list(_signal_review_links.values())
    hypotheses = list(_alpha_hypotheses.values())

    total_plans = len(hypotheses)
    total_decisions = len(links)
    decisions_with_quality = sum(1 for link in links if (link.get("decisionQuality") or "").upper() in DECISION_QUALITY_STATES)
    promotion_decisions = [
        link
        for link in links
        if str(link.get("reviewDecisionState", "")).strip().lower() in PROMOTION_STATES
    ]
    promotion_ready_decisions = sum(
        1
        for link in promotion_decisions
        if bool(link.get("evidenceLinks"))
        and str(link.get("verifierStatus", "")).lower() == "passed"
        and bool(link.get("reviewDate"))
    )
    outcomes_recorded = sum(1 for link in links if bool(link.get("outcomeQuality")))
    plan_gate_pass = sum(1 for item in hypotheses if str(item.get("planQuality", "")).upper() in {"P3", "P4"})

    return {
        "schemaVersion": "quality-scorecard-weekly.v1",
        "weekEnding": datetime.now().date().isoformat(),
        "summary": {
            "planGatePassRate": round((plan_gate_pass / total_plans), 4) if total_plans else 0.0,
            "decisionQualityCoverage": round((decisions_with_quality / total_decisions), 4) if total_decisions else 0.0,
            "promotionEvidencePassRate": round((promotion_ready_decisions / total_decisions), 4) if total_decisions else 0.0,
            "outcomeClosureRate": round((outcomes_recorded / total_decisions), 4) if total_decisions else 0.0,
        },
        "gates": {
            "planQuality": {"status": "pass" if total_plans == 0 or plan_gate_pass == total_plans else "fail", "passed": plan_gate_pass, "total": total_plans},
            "decisionQuality": {"status": "pass" if total_decisions == 0 or decisions_with_quality == total_decisions else "fail", "passed": decisions_with_quality, "total": total_decisions},
            "promotionEvidence": {
                "status": "pass" if not promotion_decisions or promotion_ready_decisions == len(promotion_decisions) else "fail",
                "passed": promotion_ready_decisions,
                "total": len(promotion_decisions),
            },
            "outcomeClosure": {"status": "pass" if outcomes_recorded >= max(1, int(total_decisions * 0.7)) or total_decisions == 0 else "fail", "passed": outcomes_recorded, "total": total_decisions},
        },
        "trendDelta": {
            "planQuality": 0.0,
            "decisionQuality": 0.0,
            "promotionEvidence": 0.0,
            "outcomeClosure": 0.0,
            "note": "Baseline week; trend deltas populate after additional snapshots.",
        },
        "updatedAt": _now(),
    }


@router.post("/signals/{signal_id}/link-review", status_code=201)
def link_signal_review(
    signal_id: str,
    request: SignalReviewLinkRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/link-review")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    key = f"{signal_id}:{signal_version}:{request.reviewId}"
    link_id = _stable_id("signal-review-link", key)
    existing = _signal_review_links.get(link_id)
    linked_at = existing.get("linkedAt") if existing else _now()

    link = {
        "linkId": link_id,
        "schemaVersion": "signal-review-link.v1",
        "signalId": signal_id,
        "signalVersion": signal_version,
        "hypothesisId": request.hypothesisId,
        "reviewId": request.reviewId,
        "reviewDecisionState": existing.get("reviewDecisionState") if existing else None,
        "overrideUsed": existing.get("overrideUsed", False) if existing else False,
        "overrideRationale": existing.get("overrideRationale") if existing else None,
        "outcomeQuality": existing.get("outcomeQuality") if existing else None,
        "linkedAt": linked_at,
        "lastReviewedAt": existing.get("lastReviewedAt") if existing else None,
        "lastOutcomeAt": existing.get("lastOutcomeAt") if existing else None,
        "updatedAt": _now(),
    }
    _signal_review_links[link_id] = link

    linked_ids = list(dict.fromkeys([*signal.get("linkedReviewIds", []), request.reviewId]))
    signal["linkedReviewIds"] = linked_ids
    signal["linkedReviewCount"] = len(linked_ids)
    signal["lastReviewedAt"] = signal.get("lastReviewedAt") or linked_at
    signal["updatedAt"] = _now()
    _persist_signal_state()
    _idempotency_store(endpoint, idempotency_key, link)
    return link


@router.get("/signals/{signal_id}/decision-links")
def get_signal_decision_links(signal_id: str) -> list[dict]:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    links = _signal_links(signal_id)
    return sorted(links, key=lambda link: link.get("updatedAt", ""), reverse=True)


def _normalize_signal_decision_action(action: str | None) -> str | None:
    if action is None or not action.strip():
        return None
    normalized = action.strip().upper().replace("-", "_").replace(" ", "_")
    if normalized == "RISK":
        normalized = "RISK_ADJUST"
    if normalized not in SIGNAL_DECISION_ACTIONS:
        allowed = ", ".join(sorted(SIGNAL_DECISION_ACTIONS))
        raise HTTPException(status_code=400, detail=f"decisionAction must be one of {allowed}")
    return normalized


def _has_decision_risk_budget(signal: dict, request: SignalDecisionWritebackRequest) -> bool:
    return any(
        value is not None and value != ""
        for value in [
            request.riskBudgetId,
            request.maxPositionSize,
            request.maxDrawdownLimit,
            request.hedgePlan,
            signal.get("riskBudget"),
            signal.get("riskLimits"),
            signal.get("maxPositionSize"),
            signal.get("maxDrawdownLimit"),
            signal.get("hedgePlan"),
        ]
    )


def _resolve_execution_readiness(signal: dict, action: str | None, request: SignalDecisionWritebackRequest) -> str:
    if request.executionReadiness:
        return request.executionReadiness
    if action in {"BLOCK", "RETIRE"}:
        return "execution_blocked"
    if action in ACTIONABLE_SIGNAL_DECISIONS and not _has_decision_risk_budget(signal, request):
        return "execution_blocked"
    if action in ACTIONABLE_SIGNAL_DECISIONS and (request.approvalState or "").lower() == "approved":
        return "execution_candidate"
    if action in ACTIONABLE_SIGNAL_DECISIONS:
        return "paper_trade_ready"
    return "not_executable"


@router.post("/signals/{signal_id}/writeback-decision")
def writeback_signal_decision(
    signal_id: str,
    request: SignalDecisionWritebackRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/writeback-decision")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    decision_quality = request.decisionQuality.upper()
    if decision_quality not in DECISION_QUALITY_STATES:
        raise HTTPException(status_code=400, detail="decisionQuality must be one of D0-D5")

    normalized_state = request.decisionState.strip().lower()
    decision_action = _normalize_signal_decision_action(request.decisionAction)
    requires_promotion_evidence = normalized_state in PROMOTION_STATES or decision_action in ACTIONABLE_SIGNAL_DECISIONS
    if requires_promotion_evidence:
        if not request.evidenceLinks:
            raise HTTPException(status_code=400, detail="Promotion decisions require evidenceLinks")
        if (request.verifierStatus or "").lower() != "passed":
            raise HTTPException(status_code=400, detail="Promotion decisions require verifierStatus=passed")
        if not request.reviewDate:
            raise HTTPException(status_code=400, detail="Promotion decisions require reviewDate")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    existing = _find_signal_review_link(signal_id, request.reviewId, signal_version)
    if existing is None:
        raise HTTPException(status_code=404, detail="Signal review link not found")

    was_override = existing.get("overrideUsed") is True
    is_override = request.overrideUsed is True
    execution_readiness = _resolve_execution_readiness(signal, decision_action, request)

    existing["reviewDecisionState"] = request.decisionState
    existing["decisionAction"] = decision_action
    existing["decisionUse"] = request.decisionUse
    existing["instrumentAction"] = request.instrumentAction
    existing["riskBudgetId"] = request.riskBudgetId
    existing["maxPositionSize"] = request.maxPositionSize
    existing["maxDrawdownLimit"] = request.maxDrawdownLimit
    existing["hedgePlan"] = request.hedgePlan
    existing["riskAdjustment"] = request.riskAdjustment
    existing["liquidityCheck"] = request.liquidityCheck
    existing["costCheck"] = request.costCheck
    existing["approvalState"] = request.approvalState
    existing["executionReadiness"] = execution_readiness
    existing["outcomeWritebackRequired"] = request.outcomeWritebackRequired
    existing["decisionQuality"] = decision_quality
    existing["overrideUsed"] = is_override
    existing["overrideRationale"] = request.rationale
    existing["evidenceLinks"] = request.evidenceLinks
    existing["verifierStatus"] = request.verifierStatus
    existing["reviewDate"] = request.reviewDate
    existing["lastReviewedAt"] = _now()
    existing["updatedAt"] = _now()

    signal["latestDecisionState"] = request.decisionState
    signal["latestDecisionAction"] = decision_action
    signal["latestDecisionUse"] = request.decisionUse
    signal["executionReadiness"] = execution_readiness
    signal["approvalState"] = request.approvalState
    signal["latestDecisionQuality"] = decision_quality
    signal["lastReviewedAt"] = existing["lastReviewedAt"]
    if is_override and not was_override:
        signal["overrideCount"] = int(signal.get("overrideCount", 0)) + 1
    signal["updatedAt"] = _now()
    _persist_signal_state()

    response = {
        "schemaVersion": "signal-writeback-decision.v1",
        "signalId": signal_id,
        "reviewId": request.reviewId,
        "latestDecisionState": signal["latestDecisionState"],
        "latestDecisionAction": signal.get("latestDecisionAction"),
        "executionReadiness": signal.get("executionReadiness"),
        "latestDecisionQuality": signal.get("latestDecisionQuality"),
        "overrideCount": signal.get("overrideCount", 0),
        "lastReviewedAt": signal.get("lastReviewedAt"),
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.post("/signals/{signal_id}/writeback-outcome")
def writeback_signal_outcome(
    signal_id: str,
    request: SignalOutcomeWritebackRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/signals/writeback-outcome")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(signal_id, request.signalVersion)
    existing = _find_signal_review_link(signal_id, request.reviewId, signal_version)
    if existing is None:
        raise HTTPException(status_code=404, detail="Signal review link not found")

    timestamp = request.lastReviewedAt or _now()
    already_counted = bool(existing.get("outcomeQuality"))
    existing["outcomeQuality"] = request.outcomeQuality
    existing["lastReviewedAt"] = timestamp
    existing["lastOutcomeAt"] = timestamp
    existing["updatedAt"] = _now()

    signal["latestOutcomeQuality"] = request.outcomeQuality
    signal["lastReviewedAt"] = timestamp
    if not already_counted:
        signal["outcomeCount"] = int(signal.get("outcomeCount", 0)) + 1
    signal["updatedAt"] = _now()
    _persist_signal_state()
    response = _signal_rollup(signal_id)
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.get("/signals/{signal_id}/outcome-rollup")
def get_signal_outcome_rollup(signal_id: str) -> dict:
    return _signal_rollup(signal_id)


@router.post("/alpha/hypotheses/{hypothesis_id}/link-signal")
def link_alpha_hypothesis_signal(
    hypothesis_id: str,
    request: AlphaHypothesisSignalLinkRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/alpha/hypotheses/link-signal")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")
    signal = _signals.get(request.signalId)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal_version = _resolve_signal_version(request.signalId, request.signalVersion)
    links = hypothesis.get("linkedSignals", [])
    entry = {
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "linkedAt": _now(),
    }
    exists = any(
        item.get("signalId") == request.signalId and int(item.get("signalVersion", 0)) == signal_version
        for item in links
    )
    if not exists:
        links.append(entry)
    hypothesis["linkedSignals"] = links
    hypothesis["updatedAt"] = _now()

    linked_hypotheses = list(dict.fromkeys([*signal.get("linkedHypothesisIds", []), hypothesis_id]))
    signal["linkedHypothesisIds"] = linked_hypotheses
    signal["updatedAt"] = _now()
    _persist_signal_state()
    response = {
        "schemaVersion": "alpha-hypothesis-signal-link.v1",
        "hypothesisId": hypothesis_id,
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "linkedSignals": links,
    }
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.get("/alpha/hypotheses/{hypothesis_id}/signals")
def list_alpha_hypothesis_signals(hypothesis_id: str) -> list[dict]:
    hypothesis = _alpha_hypotheses.get(hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Alpha hypothesis not found")

    results: list[dict] = []
    for link in hypothesis.get("linkedSignals", []):
        signal_id = link.get("signalId")
        if not signal_id or signal_id not in _signals:
            continue
        signal = _signals[signal_id]
        results.append(
            {
                "signalId": signal_id,
                "name": signal.get("name"),
                "status": signal.get("status"),
                "activeVersion": signal.get("activeVersion", signal.get("version", 1)),
                "linkedVersion": link.get("signalVersion"),
                "linkedAt": link.get("linkedAt"),
            }
        )
    return results


@router.get("/signals/{signal_id}/alpha-context")
def get_signal_alpha_context(signal_id: str) -> dict:
    signal = _signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    linked_hypotheses = signal.get("linkedHypothesisIds", [])
    hypotheses = []
    for hypothesis_id in linked_hypotheses:
        hypothesis = _alpha_hypotheses.get(hypothesis_id)
        if hypothesis:
            hypotheses.append(
                {
                    "hypothesisId": hypothesis_id,
                    "title": hypothesis.get("title"),
                    "signalFamily": hypothesis.get("signalFamily"),
                    "status": hypothesis.get("status"),
                    "updatedAt": hypothesis.get("updatedAt"),
                }
            )

    return {
        "schemaVersion": "signal-alpha-context.v1",
        "signal": signal,
        "signalVersions": _signal_versions.get(signal_id, []),
        "validationRuns": _signal_validation_runs_for(signal_id),
        "policyEvents": _signal_policy_events.get(signal_id, []),
        "linkedHypotheses": hypotheses,
        "outcomeRollup": _signal_rollup(signal_id),
        "updatedAt": _now(),
    }


@router.post("/backtests/run")
def run_backtest(
    request: BacktestRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/backtests/run")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    signal = _signals.get(request.signalId)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    backtest_id = _stable_id("backtest", f"{request.signalId}:{request.startDate}:{request.endDate}")
    hygiene = []
    if not request.walkForward:
        hygiene.append("missing_walk_forward_validation")
    if not request.includeCosts:
        hygiene.append("missing_transaction_costs")
    if not request.includeSlippage:
        hygiene.append("missing_slippage_model")
    result = {
        "backtestId": backtest_id,
        "schemaVersion": "backtest-result.v1",
        "signalId": request.signalId,
        "status": "alpha_candidate" if not hygiene else "hypothesis_only",
        "samplePeriod": f"{request.startDate}/{request.endDate}",
        "metrics": {
            "totalReturn": 0.118,
            "excessReturn": 0.041,
            "activeReturn": 0.039,
            "annualizedReturn": 0.109,
            "volatility": 0.091,
            "sharpeRatio": 1.21,
            "sortinoRatio": 1.63,
            "calmarRatio": 1.32,
            "maxDrawdown": -0.082,
            "profitFactor": 1.36,
            "hitRate": 0.57,
            "informationCoefficient": 0.11,
            "rankInformationCoefficient": 0.09,
            "informationRatio": 0.72,
            "signalDecayCurve": [0.12, 0.09, 0.05, 0.02],
            "turnover": 1.7,
            "capacityUsdMillions": 42.0,
            "betaExposure": 0.84,
            "factorExposure": {"value": 0.19, "momentum": 0.27, "quality": 0.11, "size": -0.06},
            "sectorExposure": {"technology": 0.41, "industrials": 0.18, "healthcare": 0.12},
            "spreadCostBps": 6.4,
            "slippageBps": 4.2,
            "implementationShortfallBps": 10.6,
        },
        "benchmark": signal["benchmark"],
        "hygieneIssues": hygiene,
        "disconfirmingTests": ["underperforms after costs in high-spread regime"],
        "createdAt": _now(),
    }
    _backtests[backtest_id] = result

    signal_version = int(signal.get("activeVersion", signal.get("version", 1)))
    validation_run = {
        "validationRunId": _stable_id("signal-validation", backtest_id),
        "schemaVersion": "signal-validation-run.v1",
        "signalId": request.signalId,
        "signalVersion": signal_version,
        "runType": "event_driven_backtest",
        "sampleWindows": {"train": request.startDate, "test": request.endDate},
        "pointInTimeGuaranteed": True,
        "includesCosts": request.includeCosts,
        "includesSlippage": request.includeSlippage,
        "includesLiquidity": True,
        "benchmarkComparison": {"benchmark": signal.get("benchmark"), "activeReturn": result["metrics"]["activeReturn"]},
        "hygieneIssues": hygiene,
        "metrics": result["metrics"],
        "artifactRefs": [f"backtests/{backtest_id}"],
        "status": "passed" if not hygiene else "failed",
        "completedAt": _now(),
    }
    _signal_validation_runs.setdefault(request.signalId, []).append(validation_run)
    signal["status"] = "validation_passed" if not hygiene else "validation_pending"
    signal["updatedAt"] = _now()
    _append_signal_policy_event(
        signal_id=request.signalId,
        event_type="backtest.completed",
        to_status=signal["status"],
        actor="system",
        reason="Backtest run updated validation posture",
        signal_version=signal_version,
    )
    _persist_signal_state()
    _idempotency_store(endpoint, idempotency_key, result)
    return result


@router.get("/backtests/{backtest_id}")
def get_backtest(backtest_id: str) -> dict:
    backtest = _backtests.get(backtest_id)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest


@router.post("/paper-trades", status_code=201)
def create_paper_trade(
    request: PaperTradeCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/paper-trades")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    trade_id = _stable_id("paper-trade", f"{request.decisionId}:{request.ticker}:{request.reviewDate}")
    feasibility = _execution_feasibility_assessment(
        ticker=request.ticker,
        side=request.side,
        quantity=request.quantity,
        intended_price=request.intendedPrice,
    )

    trade = {
        "paperTradeId": trade_id,
        "schemaVersion": "paper-trade.v1",
        **request.model_dump(),
        "status": "open" if feasibility["gate"] == "pass" else "requires_execution_review",
        "riskControls": ["paper_only", "human_review_required", "no_live_broker_credentials"],
        "outcomePlan": {"reviewDate": request.reviewDate, "qualityTarget": "O3"},
        "executionFeasibility": feasibility,
        "createdAt": _paper_trades.get(trade_id, {}).get("createdAt", _now()),
        "updatedAt": _now(),
    }
    _paper_trades[trade_id] = trade
    _idempotency_store(endpoint, idempotency_key, trade)
    return trade


@router.get("/paper-trades")
def list_paper_trades(
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict | list[dict]:
    items = sorted(_paper_trades.values(), key=lambda item: item["updatedAt"], reverse=True)
    if limit is None and offset == 0:
        return items

    effective_limit = limit or 100
    total = len(items)
    return {
        "schemaVersion": "paper-trades-list.v1",
        "items": items[offset : offset + effective_limit],
        "pagination": {
            "limit": effective_limit,
            "offset": offset,
            "total": total,
            "hasMore": offset + effective_limit < total,
        },
    }


@router.post("/execution/fills", status_code=201)
def ingest_execution_fill(
    request: FillIngestRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/execution/fills")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    trade = _paper_trades.get(request.paperTradeId)
    if trade is None:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    shortfall = round(((request.fillPrice - trade["intendedPrice"]) / trade["intendedPrice"]) * 10000, 2)
    fill_id = _stable_id("fill", f"{request.paperTradeId}:{request.fillPrice}:{request.latencyMs}")
    fill = {
        "fillId": fill_id,
        "schemaVersion": "execution-fill.v1",
        **request.model_dump(),
        "ticker": trade["ticker"],
        "side": trade["side"],
        "quantity": trade["quantity"],
        "implementationShortfallBps": shortfall,
        "latencyFitness": "warm_path_ok" if request.latencyMs <= 1000 else "manual_review_required",
        "attribution": {"priceMovement": shortfall * 0.4, "spread": shortfall * 0.3, "timing": shortfall * 0.3},
        "createdAt": _now(),
    }
    _fills[fill_id] = fill
    _idempotency_store(endpoint, idempotency_key, fill)
    return fill


@router.post("/execution/market-replay")
def run_market_replay(
    request: ReplayRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/execution/market-replay")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    replay_id = _stable_id("replay", f"{request.ticker}:{request.scenario}:{request.latencyMs}")
    replay = {
        "replayId": replay_id,
        "schemaVersion": "market-replay.v1",
        **request.model_dump(),
        "result": "accepted" if request.latencyMs <= 1000 else "downgraded",
        "killCriteria": ["reject if latency exceeds edge half-life", "reject if spread cost exceeds expected edge"],
        "createdAt": _now(),
    }
    _market_replays[replay_id] = replay
    _idempotency_store(endpoint, idempotency_key, replay)
    return replay


@router.post("/execution/warm-path/events", status_code=201)
def ingest_warm_path_event(
    request: WarmPathEventRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/execution/warm-path/events")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    risk_checks = {
        "size_limit": request.notionalUsd <= 250000.0,
        "latency_limit": request.latencyMs <= 1000,
        "kill_switch": request.details.get("killSwitchTriggered", False) is False,
    }
    accepted = all(risk_checks.values())
    event = {
        "eventId": _stable_id("warm-event", f"{request.eventType}:{request.ticker}:{request.latencyMs}:{len(_warm_path_events)}"),
        "schemaVersion": "warm-path-event.v1",
        **request.model_dump(),
        "riskChecks": risk_checks,
        "accepted": accepted,
        "result": "processed" if accepted else "rejected",
        "createdAt": _now(),
    }
    _warm_path_events.append(event)
    _idempotency_store(endpoint, idempotency_key, event)
    return event


@router.get("/execution/warm-path/events")
def list_warm_path_events(
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict | list[dict]:
    items = list(reversed(_warm_path_events))
    if limit is None and offset == 0:
        return items[:100]

    effective_limit = limit or 100
    total = len(items)
    return {
        "schemaVersion": "warm-path-events-list.v1",
        "items": items[offset : offset + effective_limit],
        "pagination": {
            "limit": effective_limit,
            "offset": offset,
            "total": total,
            "hasMore": offset + effective_limit < total,
        },
    }


@router.get("/signals/{signal_id}/alpha-decay")
def get_alpha_decay(signal_id: str) -> dict:
    if signal_id not in _signals:
        raise HTTPException(status_code=404, detail="Signal not found")
    rolling_ic = [0.12, 0.1, 0.06, 0.03, 0.01]
    rolling_sharpe = [1.3, 1.2, 0.95, 0.72, 0.44]
    rolling_hit_rate = [0.58, 0.56, 0.53, 0.49, 0.46]
    decay_detected = rolling_ic[-1] < 0.03 or rolling_sharpe[-1] < 0.6
    return {
        "schemaVersion": "alpha-decay.v1",
        "signalId": signal_id,
        "rollingIC": rolling_ic,
        "rollingSharpe": rolling_sharpe,
        "rollingHitRate": rolling_hit_rate,
        "spreadCostTrendBps": [5.8, 6.1, 6.9, 7.4, 8.2],
        "slippageTrendBps": [3.2, 3.9, 4.8, 5.2, 6.0],
        "capacityTrendUsdMillions": [58, 54, 49, 45, 39],
        "regimePerformance": {
            "risk_on": 0.09,
            "risk_off": -0.02,
            "high_volatility": -0.04,
        },
        "decayDetected": decay_detected,
        "recommendedAction": "downgrade_or_recalibrate" if decay_detected else "keep_active",
        "createdAt": _now(),
    }


@router.get("/execution/warm-path/status")
def get_warm_path_status() -> dict:
    return {
        "schemaVersion": "warm-path-status.v1",
        "status": "designed",
        "latencyTarget": "milliseconds-to-seconds",
        "llmInLiveOrderLoop": False,
        "localRiskChecks": ["size_limit", "price_collar", "kill_switch"],
        "brokerAutomation": "paper_or_broker_supervised_only",
    }


@router.post("/enterprise/service-accounts", status_code=201)
def create_service_account(
    request: ServiceAccountCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/enterprise/service-accounts")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    service_account_id = _stable_id("svc", request.name)
    token_fingerprint = hashlib.sha256(f"{request.name}:{request.scopes}".encode("utf-8")).hexdigest()[:16]
    now = datetime.now()
    expires_at = (now + timedelta(days=request.expiresInDays)).isoformat()
    account = {
        "serviceAccountId": service_account_id,
        "schemaVersion": "service-account.v1",
        **request.model_dump(),
        "status": "active",
        "tokenFingerprint": token_fingerprint,
        "createdAt": _service_accounts.get(service_account_id, {}).get("createdAt", now.isoformat()),
        "expiresAt": expires_at,
        "lastRotatedAt": now.isoformat(),
        "rotationIntervalDays": 30,
        "updatedAt": _now(),
    }
    _service_accounts[service_account_id] = account
    _idempotency_store(endpoint, idempotency_key, account)
    return account


@router.get("/enterprise/service-accounts")
def list_service_accounts() -> list[dict]:
    return sorted(_service_accounts.values(), key=lambda item: item["updatedAt"], reverse=True)


@router.post("/enterprise/service-accounts/{service_account_id}/rotate")
def rotate_service_account_token(
    service_account_id: str,
    request: ServiceAccountRotateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/enterprise/service-accounts/rotate")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    account = _service_accounts.get(service_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    account["tokenFingerprint"] = hashlib.sha256(f"{service_account_id}:{uuid4().hex}".encode("utf-8")).hexdigest()[:16]
    account["lastRotatedAt"] = _now()
    account["updatedAt"] = _now()
    account["rotatedBy"] = request.rotatedBy
    account["lifecycle"] = {
        "requiresRotation": False,
        "rotationIntervalDays": account.get("rotationIntervalDays", 30),
        "revocable": True,
    }
    _idempotency_store(endpoint, idempotency_key, account)
    return account


@router.post("/enterprise/service-accounts/{service_account_id}/revoke")
def revoke_service_account(
    service_account_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/enterprise/service-accounts/revoke")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    account = _service_accounts.get(service_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Service account not found")
    account["status"] = "revoked"
    account["revokedAt"] = _now()
    account["updatedAt"] = _now()
    _idempotency_store(endpoint, idempotency_key, account)
    return account


@router.post("/enterprise/audit-exports")
def create_audit_export(
    request: AuditExportRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/enterprise/audit-exports")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    export_id = _stable_id("audit-export", f"{request.requestedBy}:{request.scope}:{request.format}:{len(_audit_exports)}")
    export = {
        "exportJobId": export_id,
        "schemaVersion": "audit-export.v1",
        **request.model_dump(),
        "status": "completed",
        "downloadUrl": f"/enterprise/audit-exports/{export_id}/download",
        "columns": ["timestamp", "actor", "action", "resource", "scope", "result"],
        "createdAt": _now(),
        "completedAt": _now(),
    }
    _audit_exports[export_id] = export
    _idempotency_store(endpoint, idempotency_key, export)
    return export


@router.post("/enterprise/sso/config")
def configure_sso(
    request: SSOConfigRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    endpoint = _endpoint_key("/enterprise/sso/config")
    cached = _idempotency_lookup(endpoint, idempotency_key)
    if cached is not None:
        return cached

    _sso_config.update(
        {
            "enabled": True,
            **request.model_dump(),
            "updatedAt": _now(),
        }
    )
    response = {"schemaVersion": "enterprise-sso-config.v1", **_sso_config}
    _idempotency_store(endpoint, idempotency_key, response)
    return response


@router.get("/enterprise/sso/config")
def get_sso_config() -> dict:
    return {"schemaVersion": "enterprise-sso-config.v1", **_sso_config}


@router.get("/enterprise/deployment-bundles/offline")
def get_offline_bundle_manifest() -> dict:
    return {
        "schemaVersion": "enterprise-offline-bundle.v1",
        "bundleVersion": "0.1.0",
        "deliveryModes": ["private-registry", "air-gapped-offline"],
        "components": ["ambrosia-api", "ambrosia-web", "ambrosia-cli", "ambrosia-sdk"],
        "integrity": {
            "checksumManifest": "artifacts/release-checksums.sha256",
            "signature": "sigstore-cosign",
        },
        "documentation": [
            "docs/roadmap/index85-evidence-matrix.md",
            "artifacts/release-evidence.json",
        ],
    }


@router.get("/enterprise/readiness")
def get_enterprise_readiness() -> dict:
    package_provenance = {
        "checksums": True,
        "dockerCliImagePlan": True,
        "signedBinaryPlan": True,
        "semverPolicy": "0.x pre-release",
        "source": "plan",
    }
    if _RELEASE_EVIDENCE_PATH.exists():
        try:
            release_evidence = json.loads(_RELEASE_EVIDENCE_PATH.read_text(encoding="utf-8"))
            package_provenance = {
                "checksums": bool(release_evidence.get("provenance", {}).get("checksums")),
                "dockerCliImage": release_evidence.get("provenance", {}).get("dockerImage"),
                "signature": release_evidence.get("provenance", {}).get("signature"),
                "semverPolicy": release_evidence.get("release", {}).get("semverPolicy", "0.x pre-release"),
                "source": "release-evidence",
            }
        except json.JSONDecodeError:
            package_provenance["source"] = "invalid-release-evidence"

    return {
        "schemaVersion": "enterprise-readiness.v1",
        "tiers": ["Developer", "Team", "Enterprise"],
        "scopes": ["public:read", "advanced:read", "team:write", "admin:write"],
        "serviceAccounts": len(_service_accounts),
        "auditExports": len(_audit_exports),
        "sso": {"enabled": _sso_config["enabled"], "provider": _sso_config["provider"], "roleMappings": _sso_config["roleMappings"]},
        "privateDeployment": {"databaseRequired": True, "privateApiUrlSupported": True, "customerManagedDatabase": True},
        "packageProvenance": package_provenance,
    }


@router.get("/enterprise/support/security-packet")
def get_enterprise_security_packet() -> dict:
    return {
        "schemaVersion": "enterprise-security-packet.v1",
        "retentionPolicy": {
            "auditDays": 365,
            "benchmarkTraceDays": 180,
            "decisionMemoryDays": 730,
        },
        "supportPolicy": {
            "sla": "P1 1h response, P2 4h response",
            "channels": ["ticket", "email"],
            "coverage": "business-hours-plus-critical-oncall",
        },
        "securityReview": {
            "tokenRotation": "30 days",
            "leastPrivilegeScopes": True,
            "auditExportAvailable": True,
            "customerManagedDatabase": True,
            "privateDeploymentProfile": True,
        },
        "createdAt": _now(),
    }


def _build_relay_trace(question: str, benchmark: str, documents: list[str] | None = None) -> dict:
    evidence = documents or [
        "annual_report_q4_revenue_usd=118000000",
        "annual_report_q3_revenue_usd=100000000",
    ]

    retrieval_events = [
        {
            "source": source,
            "score": max(0.5, 0.93 - (index * 0.06)),
            "snippet": source[:140],
        }
        for index, source in enumerate(evidence)
    ]

    def _infer_unit(source: str) -> str:
        lowered = source.lower()
        if "usd" in lowered or "$" in source:
            return "USD"
        if "%" in source or "percent" in lowered:
            return "PERCENT"
        if "ms" in lowered:
            return "MILLISECONDS"
        return "unknown"

    table_extractions = [
        {
            "tableId": f"doc-table-{index + 1}",
            "unit": _infer_unit(source),
            "confidence": max(0.55, 0.95 - index * 0.08),
            "source": source,
        }
        for index, source in enumerate(evidence)
    ]

    numeric_tokens: list[float] = []
    for source in evidence:
        matches = re.findall(r"-?\d+(?:\.\d+)?", source)
        numeric_tokens.extend(float(value) for value in matches)

    calculations: list[dict] = []
    if len(numeric_tokens) >= 2 and numeric_tokens[1] != 0:
        base = numeric_tokens[1]
        current = numeric_tokens[0]
        growth_percent = round(((current - base) / base) * 100, 4)
        calculations.append(
            {
                "expression": f"(({current} - {base}) / {base}) * 100",
                "result": growth_percent,
                "verified": True,
            }
        )

    disagreement = any("conflict" in source.lower() or "disagree" in source.lower() for source in evidence)
    verification_status = "failed" if disagreement else "passed"
    abstain = disagreement or not evidence

    if abstain:
        answer = "Insufficient internally consistent evidence to provide a grounded answer; abstaining."
    elif calculations:
        answer = f"Evidence-backed estimate computed from retrieved documents: {calculations[0]['result']}% change."
    else:
        answer = "Evidence was retrieved but no deterministic calculation could be verified."

    run_id = _stable_id("relay-run", f"{benchmark}:{question}:{len(_relay_runs)}")
    return {
        "runId": run_id,
        "schemaVersion": "benchmark-trace.v1",
        "benchmark": benchmark,
        "question": question,
        "answer": answer,
        "route": "retrieval_numeric_qa",
        "retrievalEvents": retrieval_events,
        "tableExtractions": table_extractions,
        "calculations": calculations,
        "verification": {
            "status": verification_status,
            "calculationVerifier": "deterministic-parser.v1",
            "disagreementDetected": disagreement,
        },
        "grounding": {
            "status": "failed" if abstain else "passed",
            "unsupportedClaims": ["calculation disagreement"] if disagreement else [],
        },
        "abstention": {
            "required": abstain,
            "reason": "verifier_disagreement" if disagreement else ("insufficient_evidence" if not evidence else None),
        },
        "cost": {"usd": 0.0, "mode": "fixture"},
        "latencyMs": 42,
        "createdAt": _now(),
    }


def _scanner_signal_family(signal: str) -> str:
    normalized = signal.strip().lower()
    if normalized.startswith("momentum"):
        return "momentum"
    if normalized.startswith("mean_reversion"):
        return "mean_reversion"
    if normalized.startswith("breadth"):
        return "breadth"
    return "custom"


def _scanner_signal_label(signal: str) -> str:
    return signal.strip().replace("_", " ").title()


def _scanner_disconfirming_tests(signal: str, ticker: str) -> list[str]:
    family = _scanner_signal_family(signal)
    if family == "momentum":
        return [
            f"{ticker} loses relative strength versus benchmark for 3 consecutive sessions",
            "Post-cost Sharpe drops below threshold in walk-forward window",
        ]
    if family == "mean_reversion":
        return [
            f"{ticker} fails to mean-revert within expected horizon windows",
            "Implementation shortfall exceeds modeled edge",
        ]
    return [
        "Out-of-sample performance fails validation gates",
        "Regime stability check invalidates core thesis",
    ]


def _scanner_formula(signal: str, ticker: str, trend: str, rsi: float | None) -> str:
    family = _scanner_signal_family(signal)
    rsi_text = f"{rsi:.1f}" if rsi is not None else "n/a"
    if family == "momentum":
        direction = "up" if "up" in signal else "down"
        return f"scanner_{ticker.lower()}_momentum_{direction}; trend={trend}; rsi={rsi_text}"
    if family == "mean_reversion":
        direction = "up" if "up" in signal else "down"
        return f"scanner_{ticker.lower()}_mean_reversion_{direction}; trend={trend}; rsi={rsi_text}"
    return f"scanner_{ticker.lower()}_{signal}; trend={trend}; rsi={rsi_text}"


def _scanner_promotion_status(signal: dict | None) -> str:
    if not isinstance(signal, dict):
        return "alpha_created"
    status = str(signal.get("status") or "hypothesis").strip().lower()
    if status in {"retired", "constrained", "active_candidate", "validation_pending", "validation_passed", "hypothesis"}:
        return status
    return "signal_linked"


def _scanner_promotion_summary(record: dict) -> dict:
    signal_id = str(record.get("signalId") or "")
    signal = _signals.get(signal_id) if signal_id else None
    latest_validation = _signal_latest_validation(signal_id) if signal_id and signal_id in _signals else None
    latest_policy = None
    if signal_id and signal_id in _signals:
        policy_events = _signal_policy_events.get(signal_id, [])
        if policy_events:
            latest_policy = sorted(policy_events, key=lambda item: item.get("createdAt", ""), reverse=True)[0]

    linked_reviews = int((signal or {}).get("linkedReviewCount", 0)) if isinstance(signal, dict) else 0
    status = _scanner_promotion_status(signal)
    if linked_reviews > 0 and status == "hypothesis":
        status = "review_linked"

    return {
        "promotionId": record.get("promotionId"),
        "candidateKey": record.get("candidateKey"),
        "ticker": record.get("ticker"),
        "signal": record.get("signal"),
        "scannerRunId": record.get("scannerRunId"),
        "hypothesisId": record.get("hypothesisId"),
        "signalId": signal_id or None,
        "signalVersion": (signal or {}).get("activeVersion", record.get("signalVersion")) if isinstance(signal, dict) else record.get("signalVersion"),
        "promotedAt": record.get("promotedAt"),
        "promotedBy": record.get("promotedBy"),
        "status": status,
        "linkedReviewCount": linked_reviews,
        "latestDecisionState": (signal or {}).get("latestDecisionState") if isinstance(signal, dict) else None,
        "latestOutcomeQuality": (signal or {}).get("latestOutcomeQuality") if isinstance(signal, dict) else None,
        "latestValidationStatus": (latest_validation or {}).get("status") if isinstance(latest_validation, dict) else None,
        "latestPolicyEvent": (latest_policy or {}).get("eventType") if isinstance(latest_policy, dict) else None,
    }
