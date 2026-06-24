from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .market_data import build_market_snapshot, build_technicals
from .models import (
    AgentRunRequest,
    AlertQueueRecord,
    AuditEvent,
    AuditEventCreate,
    BacktestPrepareRequest,
    BacktestRunRequest,
    PacketOutcomeUpdate,
    PortfolioContextUpdate,
    ConfidenceDeriveRequest,
    DecisionPacket,
    DecisionState,
    DecisionUpdate,
    MarketSnapshot,
    OutcomeUpdate,
    RiskEvaluateRequest,
    RetrievalHit,
    RetrievalRequest,
    RetrievalResponse,
    SentimentData,
    TechnicalIndicators,
    ThesisRequest,
    TradeReview,
    ToolBoundary,
)
from .day6 import evaluate_risk, prepare_backtest_plan, run_controlled_backtest
from .day7 import build_portfolio_context, derive_confidence
from .coordinator import run_specialists
from .providers import provider_status, resolve_provider
from .review_engine import detects_prompt_injection, generate_review
from .sentiment import build_sentiment
from .store import store
from .tool_boundaries import list_tool_boundaries

app = FastAPI(title="Ambrosia Trade Review API", version="0.1.0")

default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
configured_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", r"https://.*\.onrender\.com")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[*default_origins, *configured_origins],
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _verify_webhook_signature(request: Request, raw_body: bytes) -> bool:
    secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET", "").strip()
    if not secret:
        return True

    signature = (
        request.headers.get("x-ambrosia-signature")
        or request.headers.get("x-tradingview-signature")
        or ""
    ).strip()
    if not signature:
        return False

    if signature.startswith("sha256="):
        signature = signature[len("sha256=") :]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _review_to_packet(review: TradeReview) -> DecisionPacket:
    return DecisionPacket(
        id=f"pkt-{uuid4().hex[:10]}",
        schemaVersion="packet.v1",
        workflowVersion="quant-agent.v1",
        title=f"Alert packet: {review.ticker}",
        thesis=review.thesis,
        ticker=review.ticker,
        assetClass=review.assetClass,
        timeHorizon=review.timeHorizon,
        intendedExpression=review.intendedExpression,
        status=review.status,
        decisionState=review.decisionState,
        confidence=review.confidence,
        trialCountImpact=review.trialCountImpact,
        followUpDate=review.followUpDate,
        createdAt=review.createdAt,
        claims=review.claims,
        strongestCritique=review.strongestCritique,
        disconfirmingTest=review.disconfirmingTest,
        historicalAnalogue=review.historicalAnalogue,
        validation=review.validation,
        tradeability=review.tradeability,
        sources=review.sources,
        audit=[
            *review.audit,
            AuditEvent(
                id=f"packet-audit-{len(review.audit) + 1}",
                timestamp=_clock(),
                eventType="alert.packet_shell_created",
                detail="TradingView alert converted into packet shell",
            ),
        ],
    )


def _score_text_match(query: str, text: str) -> float:
    query_terms = {term for term in query.lower().split() if term}
    if not query_terms:
        return 0.0
    text_terms = set(text.lower().split())
    overlap = len(query_terms.intersection(text_terms))
    return min(1.0, overlap / len(query_terms))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ambrosia-api"}


@app.get("/reviews", response_model=list[TradeReview])
def list_reviews() -> list[TradeReview]:
    return store.list_reviews()


@app.post("/reviews", response_model=TradeReview)
def create_review(request: ThesisRequest) -> TradeReview:
    review = generate_review(request, store.next_trial_count)
    return store.save_review(review)


@app.get("/reviews/{review_id}", response_model=TradeReview)
def get_review(review_id: str) -> TradeReview:
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.patch("/reviews/{review_id}/decision", response_model=TradeReview)
def record_decision(review_id: str, update: DecisionUpdate) -> TradeReview:
    review = store.record_decision(review_id, update.decision_state)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.post("/reviews/{review_id}/outcome", response_model=TradeReview)
def record_outcome(review_id: str, update: OutcomeUpdate) -> TradeReview:
    review = store.record_outcome(review_id, update)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.post("/packets", response_model=DecisionPacket)
def create_packet(packet: DecisionPacket) -> DecisionPacket:
    return store.save_packet(packet)


@app.get("/packets", response_model=list[DecisionPacket])
def list_packets(
    search: str | None = Query(default=None),
    ticker: str | None = Query(default=None),
    decision_state: DecisionState | None = Query(default=None),
) -> list[DecisionPacket]:
    return store.list_packets(search=search, ticker=ticker, decision_state=decision_state)


@app.get("/packets/{packet_id}", response_model=DecisionPacket)
def get_packet(packet_id: str) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return packet


@app.post("/packets/{packet_id}/audit", response_model=DecisionPacket)
def record_packet_audit(packet_id: str, event: AuditEventCreate) -> DecisionPacket:
    packet = store.add_packet_audit_event(packet_id, event)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return packet


@app.get("/packets/{packet_id}/audit", response_model=list[AuditEvent])
def get_packet_audit(packet_id: str) -> list[AuditEvent]:
    audit_events = store.get_packet_audit(packet_id)
    if audit_events is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return audit_events


@app.get("/market/{ticker}/snapshot", response_model=MarketSnapshot)
def get_market_snapshot(ticker: str) -> MarketSnapshot:
    return build_market_snapshot(ticker)


@app.get("/market/{ticker}/technicals", response_model=TechnicalIndicators)
def get_market_technicals(ticker: str) -> TechnicalIndicators:
    return build_technicals(ticker)


@app.get("/sentiment/{ticker}", response_model=SentimentData)
def get_sentiment(ticker: str) -> SentimentData:
    return build_sentiment(ticker)


@app.post("/packets/{packet_id}/metrics/refresh", response_model=DecisionPacket)
def refresh_packet_metrics(packet_id: str) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    snapshot = build_market_snapshot(packet.ticker)
    technicals = build_technicals(packet.ticker)
    sentiment = build_sentiment(packet.ticker)

    updated_packet = packet.model_copy(
        update={
            "marketSnapshot": snapshot,
            "technicals": technicals,
            "sentiment": sentiment,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="metrics.refreshed",
                    detail=f"Market, technicals, and sentiment refreshed for {packet.ticker}",
                ),
            ],
        }
    )
    store.save_packet(updated_packet)
    store.record_metric_snapshot(packet_id, "market_snapshot", snapshot.model_dump(mode="json"))
    store.record_metric_snapshot(packet_id, "technicals", technicals.model_dump(mode="json"))
    store.record_metric_snapshot(packet_id, "sentiment", sentiment.model_dump(mode="json"))
    return updated_packet


@app.get("/alerts/queue", response_model=list[AlertQueueRecord])
def list_alert_queue() -> list[AlertQueueRecord]:
    return store.list_alerts()


@app.get("/providers/status")
def get_provider_status() -> dict[str, bool]:
    return provider_status()


@app.get("/tools/boundaries", response_model=list[ToolBoundary])
def get_tool_boundaries() -> list[ToolBoundary]:
    return list_tool_boundaries()


@app.post("/packets/{packet_id}/agents/run", response_model=DecisionPacket)
def run_packet_agents(packet_id: str, body: AgentRunRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    selected_provider = resolve_provider(body.providerMode)
    specialist_outputs = run_specialists(packet, selected_provider)

    updated_packet = packet.model_copy(
        update={
            "agentOutputs": specialist_outputs,
            "providerInfo": {
                "name": selected_provider.name,
                "type": selected_provider.provider_type,
                "fallbackChain": selected_provider.fallback_chain,
                "fallbackUsed": selected_provider.fallback_used,
                "reason": selected_provider.reason,
            },
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="agents.completed",
                    detail=f"Coordinator ran specialist outputs via {selected_provider.name}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/backtest/prepare", response_model=DecisionPacket)
def prepare_packet_backtest(packet_id: str, body: BacktestPrepareRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    backtest_plan = prepare_backtest_plan(packet, body)
    updated_packet = packet.model_copy(
        update={
            "backtestPlan": backtest_plan,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="backtest.prepared",
                    detail=f"Backtest plan prepared with status {backtest_plan.status}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/backtest/run", response_model=DecisionPacket)
def run_packet_backtest(packet_id: str, body: BacktestRunRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    result = run_controlled_backtest(packet, force_run=body.forceRun)
    plan = packet.backtestPlan.model_copy() if packet.backtestPlan else None
    if plan is not None:
        plan.status = "completed" if result.validityScore != "refused" else "ineligible"

    updated_packet = packet.model_copy(
        update={
            "backtestPlan": plan,
            "backtestResult": result,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="backtest.completed" if result.validityScore != "refused" else "backtest.refused",
                    detail=f"Controlled backtest run finished with validity {result.validityScore}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/risk/evaluate", response_model=DecisionPacket)
def evaluate_packet_risk(packet_id: str, body: RiskEvaluateRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    risk = evaluate_risk(packet, body)
    updated_packet = packet.model_copy(
        update={
            "riskMonitor": risk,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="risk.evaluated",
                    detail=f"Risk monitor status updated to {risk.status}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/outcome", response_model=DecisionPacket)
def record_packet_outcome(packet_id: str, body: PacketOutcomeUpdate) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    store.record_packet_outcome(
        packet_id,
        body.outcome,
        body.outcome_date,
        {"pnl": body.pnl, "notes": body.notes},
    )

    updated_packet = packet.model_copy(
        update={
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="outcome.recorded",
                    detail=f"Outcome recorded: {body.outcome_date} {body.outcome}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/portfolio/update", response_model=DecisionPacket)
def update_packet_portfolio_context(packet_id: str, body: PortfolioContextUpdate) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    portfolio = build_portfolio_context(body)
    updated_packet = packet.model_copy(
        update={
            "portfolioContext": portfolio,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="portfolio.updated",
                    detail="Portfolio context updated for advisory risk sizing",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/retrieve", response_model=RetrievalResponse)
def retrieve_packet_context(packet_id: str, body: RetrievalRequest) -> RetrievalResponse:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    hits: list[RetrievalHit] = []
    query = body.query.strip()

    for source in packet.sources:
        source_text = f"{source.title} {source.sourceType}"
        score = _score_text_match(query, source_text)
        if score > 0:
            hits.append(
                RetrievalHit(
                    kind="packet_source",
                    id=source.id,
                    title=source.title,
                    snippet=f"{source.sourceType} ({source.timestamp})",
                    score=score,
                )
            )

    for review in store.list_reviews():
        if review.id == packet.id:
            continue
        review_text = f"{review.title} {review.thesis} {review.ticker}"
        score = _score_text_match(query, review_text)
        if score > 0:
            hits.append(
                RetrievalHit(
                    kind="prior_review",
                    id=review.id,
                    title=review.title,
                    snippet=review.thesis[:160],
                    score=score,
                )
            )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    top_hits = hits[: body.topK]

    store.record_retrieval_event(
        packet_id,
        query,
        len(top_hits),
        {"k": body.topK, "hitKinds": [hit.kind for hit in top_hits]},
    )

    updated_packet = packet.model_copy(
        update={
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="retrieval.hybrid",
                    detail=f"Hybrid retrieval executed for query '{query}' with {len(top_hits)} hits",
                ),
            ]
        }
    )
    store.save_packet(updated_packet)

    return RetrievalResponse(packetId=packet_id, query=query, results=top_hits)


@app.post("/packets/{packet_id}/confidence/derive", response_model=DecisionPacket)
def derive_packet_confidence(packet_id: str, body: ConfidenceDeriveRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    confidence = derive_confidence(packet, body)
    updated_packet = packet.model_copy(
        update={
            "confidenceBreakdown": confidence,
            "confidence": confidence.overallConfidence,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="confidence.derived",
                    detail=f"Confidence recomputed with risk-adjusted score {confidence.riskAdjustedScore}",
                ),
            ],
        }
    )
    return store.save_packet(updated_packet)


@app.post("/webhooks/tradingview", response_model=TradeReview)
async def tradingview_webhook(request: Request) -> TradeReview:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object")

    signature_verified = _verify_webhook_signature(request, raw_body)
    if not signature_verified:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    thesis = str(
        payload.get("thesis")
        or payload.get("message")
        or payload.get("condition")
        or "TradingView alert requires review"
    )
    symbol = str(payload.get("symbol") or payload.get("ticker") or "TradingView alert")
    injection_detected = detects_prompt_injection(thesis)

    store.enqueue_alert(
        source="tradingview",
        symbol=symbol,
        message=thesis,
        payload=payload,
        signature_verified=signature_verified,
        prompt_injection_detected=injection_detected,
    )

    thesis_request = ThesisRequest(
        thesis=thesis,
        ticker=symbol,
        asset_class=str(payload.get("asset_class") or "Market alert"),
        time_horizon=str(payload.get("time_horizon") or payload.get("timeframe") or "Unspecified"),
        intended_expression=str(
            payload.get("intended_expression")
            or payload.get("related_instruments")
            or "Expression requires review"
        ),
        source_pointer="TradingView webhook payload",
    )
    review = generate_review(thesis_request, store.next_trial_count)
    return store.save_review(review)


@app.post("/webhooks/tradingview/packet", response_model=DecisionPacket)
async def tradingview_webhook_packet(request: Request) -> DecisionPacket:
    review = await tradingview_webhook(request)
    packet = _review_to_packet(review)
    return store.save_packet(packet)


@app.get("/metrics")
def metrics() -> dict[str, int]:
    reviews = store.list_reviews()
    return {
        "reviews_created": len(reviews),
        "decisions_recorded": sum(1 for review in reviews if review.decisionState is not None),
        "rejected_or_deferred": sum(
            1 for review in reviews if review.decisionState in {"reject", "needs_more_data"}
        ),
    }
