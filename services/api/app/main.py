from __future__ import annotations

import hashlib
import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor
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
    PacketApproval,
    PacketApprovalCreate,
    PacketComment,
    PacketCommentCreate,
    PacketOutcomeUpdate,
    PortfolioContextUpdate,
    ConfidenceDeriveRequest,
    DecisionPacket,
    DecisionState,
    DecisionUpdate,
    JobRecord,
    MarketSnapshot,
    OutcomeUpdate,
    RiskEvaluateRequest,
    ReportArtifact,
    RetrievalHit,
    RetrievalRequest,
    RetrievalResponse,
    ScannerRunRequest,
    ScannerResult,
    SentimentData,
    TechnicalIndicators,
    ThesisRequest,
    TradeReview,
    ToolBoundary,
    WorkspaceAddPacketRequest,
    WorkspaceCreateRequest,
    WorkspaceRecord,
    WorkflowTemplate,
    WorkflowTemplateCreate,
)
from .day6 import evaluate_risk, prepare_backtest_plan, run_controlled_backtest
from .day7 import build_portfolio_context, derive_confidence
from .coordinator import run_specialists
from .feedback_api import feedback_router
from .market_providers import market_provider_status
from .providers import provider_status, resolve_provider
from .report import generate_report
from .review_engine import detects_prompt_injection, generate_review
from .scanner import run_scanner
from .sentiment import build_sentiment
from .store import store
from .tool_boundaries import list_tool_boundaries

_executor = ThreadPoolExecutor(max_workers=4)

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

# Include feedback router for calibration queries and feedback recording
app.include_router(feedback_router)


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


def _originating_review_id_from_packet_id(packet_id: str) -> str | None:
    return packet_id[len("pkt-") :] if packet_id.startswith("pkt-") else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ambrosia-api"}


@app.get("/metrics")
def get_metrics():
    """Get detailed calibration metrics board."""
    metrics_board = store.get_calibration_metrics()
    return metrics_board.model_dump()


@app.get("/scorecard")
def get_operational_scorecard():
    """Get Index39 operational certification scorecard."""
    scorecard = store.get_operational_scorecard()
    return scorecard.model_dump()


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
    specialist_outputs, runtime_fallback_used = run_specialists(packet, selected_provider)

    updated_packet = packet.model_copy(
        update={
            "agentOutputs": specialist_outputs,
            "providerInfo": {
                "name": selected_provider.name,
                "type": selected_provider.provider_type,
                "fallbackChain": selected_provider.fallback_chain,
                "fallbackUsed": runtime_fallback_used,
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
    store.record_workflow_run(
        _originating_review_id_from_packet_id(packet_id),
        f"{packet_id}:agents.run:{selected_provider.name}:{datetime.now().isoformat()}",
        "completed",
        "coordinator.v1",
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
    store.record_workflow_run(
        _originating_review_id_from_packet_id(packet_id),
        f"{packet_id}:backtest.run:{datetime.now().isoformat()}",
        "completed" if result.validityScore != "refused" else "refused",
        "backtest.v1",
        None if result.validityScore != "refused" else "Backtest run refused by validation gates",
    )
    return store.save_packet(updated_packet)


@app.post("/packets/{packet_id}/backtest/run/async", response_model=JobRecord)
def run_packet_backtest_async(packet_id: str, body: BacktestRunRequest) -> JobRecord:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    job = store.enqueue_job(
        "backtest.run",
        f"packet={packet_id};forceRun={body.forceRun}",
    )

    def _execute() -> None:
        store.start_job(job.id)
        try:
            pkt = store.get_packet(packet_id)
            if pkt is None:
                store.fail_job(job.id, "Packet no longer found")
                return
            bt_result = run_controlled_backtest(pkt, force_run=body.forceRun)
            bt_plan = pkt.backtestPlan.model_copy() if pkt.backtestPlan else None
            if bt_plan is not None:
                bt_plan.status = "completed" if bt_result.validityScore != "refused" else "ineligible"
            updated = pkt.model_copy(
                update={
                    "backtestPlan": bt_plan,
                    "backtestResult": bt_result,
                    "audit": [
                        *pkt.audit,
                        AuditEvent(
                            id=f"packet-audit-{len(pkt.audit) + 1}",
                            timestamp=_clock(),
                            eventType="backtest.completed" if bt_result.validityScore != "refused" else "backtest.refused",
                            detail=f"Async backtest finished with validity {bt_result.validityScore}",
                        ),
                    ],
                }
            )
            store.save_packet(updated)
            store.complete_job(job.id, bt_result.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover
            store.fail_job(job.id, str(exc))

    _executor.submit(_execute)
    return store.get_job(job.id) or job


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
    from .feedback import FeedbackRecord, OutcomeResult
    
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    store.record_packet_outcome(
        packet_id,
        body.outcome,
        body.outcome_date,
        {"pnl": body.pnl, "notes": body.notes},
    )

    # Create and save feedback record for calibration tracking
    try:
        # Map outcome string to OutcomeResult enum (try common variations)
        outcome_lower = body.outcome.lower().strip()
        outcome_mapping = {
            "won": OutcomeResult.won,
            "win": OutcomeResult.won,
            "correct": OutcomeResult.won,
            "lost": OutcomeResult.lost,
            "loss": OutcomeResult.lost,
            "wrong": OutcomeResult.lost,
            "whipsaw": OutcomeResult.whipsaw,
            "invalidated": OutcomeResult.invalidated,
            "invalid": OutcomeResult.invalidated,
            "no_setup": OutcomeResult.no_setup,
            "no setup": OutcomeResult.no_setup,
            "partial": OutcomeResult.partial,
            "half": OutcomeResult.partial,
        }
        
        outcome_enum = outcome_mapping.get(outcome_lower, OutcomeResult.no_setup)
        
        feedback = FeedbackRecord(
            packet_id=packet_id,
            decision_state=packet.decisionState.value if packet.decisionState else "unknown",
            confidence=packet.confidence,
            ticker=packet.ticker,
            asset_class=packet.assetClass,
            time_horizon=packet.timeHorizon,
            outcome_date=body.outcome_date,
            outcome=outcome_enum,
            pnl=body.pnl,
            notes=body.notes or "",
            recorded_by="system",  # TODO: Use authenticated user ID when available
        )
        
        store.save_feedback_record(feedback)
        
        # Recompute cohort calibration
        store.recompute_cohort_calibration(
            packet.ticker,
            packet.assetClass,
            packet.timeHorizon,
        )
    except Exception as exc:
        # Log but don't fail the outcome recording
        logger = __import__("logging").getLogger(__name__)
        logger.warning("Failed to record feedback for packet %s: %s", packet_id, exc)

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
    originating_review_id = packet.id[len("pkt-") :] if packet.id.startswith("pkt-") else None

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
        if review.id == packet.id or (originating_review_id is not None and review.id == originating_review_id):
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
    store.record_workflow_run(
        originating_review_id,
        f"{packet_id}:retrieve:{query}:{datetime.now().isoformat()}",
        "completed",
        "retrieval.v1",
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


@app.post("/scanner/run", response_model=ScannerResult)
def scanner_run(body: ScannerRunRequest) -> ScannerResult:
    return run_scanner(body)


@app.post("/scanner/run/async", response_model=JobRecord)
def scanner_run_async(body: ScannerRunRequest) -> JobRecord:
    universe_label = ",".join(body.universe) if body.universe else "default-nyse"
    job = store.enqueue_job(
        "scanner.run",
        f"universe={universe_label[:80]};filter={body.signalFilter};maxCandidates={body.maxCandidates}",
    )

    def _execute() -> None:
        store.start_job(job.id)
        try:
            result = run_scanner(body)
            store.complete_job(job.id, result.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover - runtime failure
            store.fail_job(job.id, str(exc))

    _executor.submit(_execute)
    # re-fetch so caller gets the latest state (may already be running)
    return store.get_job(job.id) or job


@app.get("/jobs", response_model=list[JobRecord])
def list_jobs() -> list[JobRecord]:
    return store.list_jobs()


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job_status(job_id: str) -> JobRecord:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/market/providers/status")
def get_market_provider_status() -> dict:
    return market_provider_status()


@app.get("/health/detailed")
def health_detailed() -> dict:
    reviews = store.list_reviews()
    packets = store.list_packets()
    jobs = store.list_jobs()
    mkt_status = market_provider_status()
    
    # Get calibration health info
    cal_summary = store.get_calibration_summary()
    cal_alerts = store.list_calibration_alerts(severity="critical")
    
    # Get all calibration metrics
    metrics_board = store.get_calibration_metrics()

    alerts: list[str] = []
    failed_jobs = [j for j in jobs if j.state.value == "failed"]
    if failed_jobs:
        alerts.append(f"{len(failed_jobs)} job(s) in failed state — check GET /jobs")
    if not mkt_status.get("polygonConfigured"):
        alerts.append("Licensed NYSE data path not configured; market data using Yahoo Finance fallback")
    if cal_alerts:
        alerts.append(f"{len(cal_alerts)} critical calibration alert(s) — check GET /feedback/calibration/alerts")
    if metrics_board.overall_status == "critical":
        alerts.append(f"Critical metrics detected: {metrics_board.overall_status.upper()}")
    if metrics_board.overall_status == "warning":
        alerts.append(f"Warning: Some metrics below target")

    overall = "degraded" if (alerts or metrics_board.overall_status != "ok") else "ok"

    return {
        "status": overall,
        "service": "ambrosia-api",
        "checks": {
            "store": "ok",
            "marketData": mkt_status,
            "llmProviders": provider_status(),
            "calibrationMetrics": {
                "reviewValidity": {
                    "conversionRate": metrics_board.review_validity.conversion_rate,
                    "target": metrics_board.review_validity.target,
                    "status": metrics_board.review_validity.status,
                },
                "decisionConsistency": {
                    "avgScore": metrics_board.decision_consistency_avg,
                    "target": 1.0,
                    "status": "ok" if metrics_board.decision_consistency_avg >= 0.7 else "warning",
                },
                "packetIntegrity": {
                    "integrityScore": metrics_board.packet_integrity.integrity_score,
                    "target": metrics_board.packet_integrity.target,
                    "status": metrics_board.packet_integrity.status,
                },
                "dataQuality": {
                    "qualityScore": metrics_board.data_quality.quality_score,
                    "target": metrics_board.data_quality.target,
                    "status": metrics_board.data_quality.status,
                },
                "agentConsensus": {
                    "consensusScore": metrics_board.agent_consensus.avg_consensus_score,
                    "target": metrics_board.agent_consensus.target,
                    "status": metrics_board.agent_consensus.status,
                },
                "backtestValidity": {
                    "correlation": metrics_board.backtest_validity.avg_correlation,
                    "target": metrics_board.backtest_validity.target,
                    "status": metrics_board.backtest_validity.status,
                },
                "riskEstimate": {
                    "accuracy": metrics_board.risk_estimate.estimate_accuracy,
                    "target": metrics_board.risk_estimate.target,
                    "status": metrics_board.risk_estimate.status,
                },
                "confidenceCalibration": {
                    "calibrationScore": metrics_board.confidence_calibration.calibration_score,
                    "target": metrics_board.confidence_calibration.target,
                    "status": metrics_board.confidence_calibration.status,
                },
            },
            "feedbackSystem": {
                "totalDecisions": cal_summary.total_decisions,
                "overallAccuracy": round(cal_summary.overall_accuracy, 3),
                "wellCalibratedBands": cal_summary.well_calibrated_count,
                "overConfidentBands": cal_summary.over_confident_count,
                "underConfidentBands": cal_summary.under_confident_count,
                "totalAlerts": cal_summary.total_alerts,
            },
        },
        "slo": {
            "reviewsCreated": len(reviews),
            "packetsCreated": len(packets),
            "jobsQueued": sum(1 for j in jobs if j.state.value == "queued"),
            "jobsRunning": sum(1 for j in jobs if j.state.value == "running"),
            "jobsCompleted": sum(1 for j in jobs if j.state.value == "completed"),
            "jobsFailed": sum(1 for j in jobs if j.state.value == "failed"),
        },
        "metrics": {
            "overallStatus": metrics_board.overall_status,
            "computedAt": metrics_board.computed_at,
        },
        "alerts": alerts,
    }


@app.post("/packets/{packet_id}/report", response_model=ReportArtifact)
def generate_packet_report(packet_id: str) -> ReportArtifact:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    report = generate_report(packet)

    store.add_packet_audit_event(
        packet_id,
        AuditEventCreate(
            eventType="report.generated",
            detail=f"Report generated; mode={report.dataMode}; provenance={report.provenanceLabel}",
        ),
    )
    return report


@app.post("/packets/{packet_id}/report/async", response_model=JobRecord)
def generate_packet_report_async(packet_id: str) -> JobRecord:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    job = store.enqueue_job("report.generate", f"packet={packet_id}")

    def _execute() -> None:
        store.start_job(job.id)
        try:
            pkt = store.get_packet(packet_id)
            if pkt is None:
                store.fail_job(job.id, "Packet no longer found")
                return
            rpt = generate_report(pkt)
            store.add_packet_audit_event(
                packet_id,
                AuditEventCreate(
                    eventType="report.generated",
                    detail=f"Async report generated; mode={rpt.dataMode}",
                ),
            )
            store.complete_job(job.id, rpt.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover
            store.fail_job(job.id, str(exc))

    _executor.submit(_execute)
    return store.get_job(job.id) or job


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — workspaces
# ---------------------------------------------------------------------------

@app.post("/workspaces", response_model=WorkspaceRecord)
def create_workspace(body: WorkspaceCreateRequest) -> WorkspaceRecord:
    return store.create_workspace(body)


@app.get("/workspaces", response_model=list[WorkspaceRecord])
def list_workspaces(owner_id: str | None = Query(default=None)) -> list[WorkspaceRecord]:
    return store.list_workspaces(owner_id=owner_id)


@app.get("/workspaces/{workspace_id}", response_model=WorkspaceRecord)
def get_workspace(workspace_id: str) -> WorkspaceRecord:
    ws = store.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@app.post("/workspaces/{workspace_id}/packets", response_model=WorkspaceRecord)
def add_packet_to_workspace(workspace_id: str, body: WorkspaceAddPacketRequest) -> WorkspaceRecord:
    ws = store.add_packet_to_workspace(workspace_id, body.packetId)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — packet comments
# ---------------------------------------------------------------------------

@app.post("/packets/{packet_id}/comments", response_model=PacketComment)
def add_packet_comment(packet_id: str, body: PacketCommentCreate) -> PacketComment:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    comment = store.add_packet_comment(packet_id, body)
    store.add_packet_audit_event(
        packet_id,
        AuditEventCreate(
            eventType="comment.added",
            detail=f"{body.commentType.value} comment from {body.authorId}",
        ),
    )
    return comment


@app.get("/packets/{packet_id}/comments", response_model=list[PacketComment])
def list_packet_comments(packet_id: str) -> list[PacketComment]:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return store.list_packet_comments(packet_id)


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — approval flows
# ---------------------------------------------------------------------------

@app.post("/packets/{packet_id}/approval", response_model=PacketApproval)
def set_packet_approval(packet_id: str, body: PacketApprovalCreate) -> PacketApproval:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    approval = store.set_packet_approval(packet_id, body)
    store.add_packet_audit_event(
        packet_id,
        AuditEventCreate(
            eventType="approval.recorded",
            detail=f"Approval decision '{approval.decision.value}' by {body.reviewerId}",
        ),
    )
    return approval


@app.get("/packets/{packet_id}/approval", response_model=PacketApproval)
def get_packet_approval(packet_id: str) -> PacketApproval:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    approval = store.get_packet_approval(packet_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="No approval recorded for this packet")
    return approval


# ---------------------------------------------------------------------------
# Phase 5: Workflow templates (enterprise / marketplace layer)
# ---------------------------------------------------------------------------

@app.post("/workflows/templates", response_model=WorkflowTemplate)
def create_workflow_template(body: WorkflowTemplateCreate) -> WorkflowTemplate:
    return store.create_workflow_template(body)


@app.get("/workflows/templates", response_model=list[WorkflowTemplate])
def list_workflow_templates(status: str | None = Query(default=None)) -> list[WorkflowTemplate]:
    return store.list_workflow_templates(status=status)


@app.get("/workflows/templates/{template_id}", response_model=WorkflowTemplate)
def get_workflow_template(template_id: str) -> WorkflowTemplate:
    t = store.get_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return t


@app.post("/workflows/templates/{template_id}/publish", response_model=WorkflowTemplate)
def publish_workflow_template(template_id: str) -> WorkflowTemplate:
    t = store.publish_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return t


@app.post("/workflows/templates/{template_id}/archive", response_model=WorkflowTemplate)
def archive_workflow_template(template_id: str) -> WorkflowTemplate:
    t = store.archive_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return t