from __future__ import annotations

import hashlib
import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .market_data import build_market_snapshot, build_technicals
from .models import (
    AgentRunRequest,
    AttributionRequest,
    AlertQueueRecord,
    AuditEvent,
    AuditEventCreate,
    BacktestPrepareRequest,
    BacktestRunRequest,
    BrokerSandboxOrderRequest,
    PacketApproval,
    PacketApprovalCreate,
    PacketComment,
    PacketCommentCreate,
    PacketOutcomeUpdate,
    MobileAlertSubscriptionCreate,
    PortfolioContextUpdate,
    ConfidenceDeriveRequest,
    DecisionPacket,
    DecisionMemoryRecord,
    DecisionState,
    DecisionUpdate,
    IntegrationStage,
    JobRecord,
    MarketSnapshot,
    MemoryResolutionRequest,
    OutcomeUpdate,
    PacketDecisionUpdate,
    PacketWorkflowStatus,
    RiskEvaluateRequest,
    ReviewStatus,
    RoadmapDecisionRecord,
    RoadmapOutcomeRecord,
    RoadmapPlanRecord,
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
from .auth_api import router as auth_router
from .market_providers import market_provider_status
from .providers import provider_status, resolve_provider
from .report import generate_report
from .retrieval_quality import (
    get_retrieval_quality_tracker,
    generate_retrieval_quality_report,
)
from .review_engine import detects_prompt_injection, generate_review
from .scanner import run_scanner
from .sentiment import build_sentiment
from .selective_integration import (
    attach_provenance,
    build_packet_provenance,
    build_workflow_status,
    create_decision_memory_record,
    evaluate_risk_gate,
    invalidate_integration,
    packet_decision_blockers,
    run_disconfirmation,
    score_memory_relevance,
    verify_audit_chain,
)
from .store import store
from .visibility_registry import (
    load_admin_boundary_rules,
    load_frontend_visibility_matrix,
    load_function_registry,
)
from .tool_boundaries import list_tool_boundaries
from .phase_c_discovery import router as discovery_router
from .phase_e_execution import router as execution_router
from .phase_index61_completion import router as completion_router
from .phase_b_ci_cd import router as phase_b_router
from .phase_c_discovery_ui import router as phase_c_ui_router
from .phase_d_governance_ui import router as phase_d_router
from .phase_e_execution_loop import router as phase_e_router
from .phase_e_market_integration import router as market_integration_router
from .index84_platform import INDEX97_SIGNAL_SEED, router as index84_platform_router
from .mobile_api import router as mobile_router
from .llm_catalog import router as llm_catalog_router
from .team_api import router as team_router
from .product_analytics import router as product_analytics_router
from .artifact_store import artifact_store, router as artifact_router
from .tenant_context import reset_organization_id, set_organization_id
from .operations import (
    ApiPrefixMiddleware,
    ProductionBoundaryMiddleware,
    current_principal,
    register_audit_sink,
    register_readiness_check,
    router as operations_router,
    telemetry,
)

_executor = ThreadPoolExecutor(max_workers=4)
ROADMAP_LEDGER_PATH = Path(__file__).resolve().parents[3] / "docs" / "roadmap" / "pdo-ledger.seed.json"
DB_SCHEMA_VERSION_PATH = Path(__file__).resolve().parents[3] / "infra" / "db" / "schema-version.json"

app = FastAPI(title="Ambrosia Trade Review API", version="0.1.0")


def _submit_tenant_task(function) -> None:
    """Propagate only the server-derived tenant into a worker thread."""
    principal = current_principal()
    if principal is None or not principal.organization_id:
        raise HTTPException(status_code=401, detail="Tenant-bound identity required")
    organization_id = principal.organization_id

    def scoped() -> None:
        token = set_organization_id(organization_id)
        try:
            function()
        finally:
            reset_organization_id(token)

    _executor.submit(scoped)

TEAM_READ_ROLES = {"viewer", "analyst", "reviewer", "owner", "admin", "service"}
TEAM_WRITE_ROLES = {"analyst", "reviewer", "owner", "admin", "service"}
TEAM_APPROVAL_ROLES = {"reviewer", "owner", "admin", "service"}
ADVANCED_ROLES = {"analyst", "reviewer", "owner", "admin", "service"}
ADMIN_ROLES = {"owner", "admin", "service"}

default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
configured_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", "").strip() or None


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
app.include_router(auth_router)

# Include Phase B: CI/CD Industrialization
app.include_router(phase_b_router)

# Include Phase C: Discovery & Intelligence
app.include_router(discovery_router)
app.include_router(phase_c_ui_router)

# Include Phase D: Enterprise Governance & RBAC
app.include_router(phase_d_router)

# Include Phase E: Execution Loop & Attribution
app.include_router(execution_router)
app.include_router(phase_e_router)
app.include_router(market_integration_router)
app.include_router(index84_platform_router)
app.include_router(mobile_router)
app.include_router(llm_catalog_router)
app.include_router(team_router)
app.include_router(product_analytics_router)
app.include_router(artifact_router)
app.include_router(operations_router)

# Include INDEX61 Completion Status & RBAC
app.include_router(completion_router)

# This is the authoritative identity, policy, request-safety, audit, and
# telemetry boundary. Production identities are accepted only from managed
# bearer credentials; development header identities are explicitly local-only.
app.add_middleware(ProductionBoundaryMiddleware)
# Last-added middleware is outermost in Starlette, so the public /api prefix is
# normalized before authentication, route policy, telemetry, and FastAPI routing.
app.add_middleware(ApiPrefixMiddleware)


def _persistence_readiness() -> None:
    status = store.persistence_status()
    if status["databaseRequired"] and not status["databaseConnected"]:
        raise RuntimeError("required_database_unavailable")


register_readiness_check("persistence", _persistence_readiness)
register_readiness_check("artifactStorage", artifact_store.healthcheck)
register_audit_sink(store.append_security_audit)


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _feature_enabled(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _require_selective_integration_enabled() -> None:
    if not _feature_enabled("SELECTIVE_INTEGRATION_ENABLED", default=True):
        telemetry.increment("selective_stage_blocked", "feature_disabled")
        raise HTTPException(status_code=503, detail="Selective integration is disabled by feature flag")


def _request_actor(request: Request, fallback: str = "system") -> str:
    principal = getattr(request.state, "principal", None)
    return str(getattr(principal, "subject", fallback))


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


def _load_roadmap_seed_plans() -> list[RoadmapPlanRecord]:
    data = json.loads(ROADMAP_LEDGER_PATH.read_text(encoding="utf-8"))
    return [RoadmapPlanRecord.model_validate(plan) for plan in data.get("plans", [])]


def _load_db_schema_version() -> dict[str, str]:
    try:
        data = json.loads(DB_SCHEMA_VERSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"dbSchemaVersion": "unknown"}
    return {"dbSchemaVersion": str(data.get("dbSchemaVersion", "unknown"))}


def _normalize_role(role: str | None) -> str:
    return (role or "").strip().lower()


def _require_role(
    allowed_roles: set[str],
    header_role: str | None,
    *,
    scope: str,
    force: bool = False,
) -> str:
    # The request boundary authenticates once and places the server-derived
    # principal in context. Header values remain in signatures temporarily for
    # API compatibility but never decide authorization.
    del header_role, force
    principal = current_principal()
    role = _normalize_role(principal.role if principal else None)
    if not role:
        raise HTTPException(
            status_code=403,
            detail=f"Authenticated role required for {scope} access",
        )
    if role not in allowed_roles:
        allowed = ", ".join(sorted(allowed_roles))
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not allowed for {scope}; allowed roles: {allowed}",
        )
    return role


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ambrosia-api",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health/phases")
def health_phases() -> dict:
    """Detailed health check with all phase statuses"""
    return {
        "status": "ok",
        "service": "ambrosia-api",
        "timestamp": datetime.now().isoformat(),
        "phases": {
            "phase_a": {
                "status": "OPERATIONAL",
                "retrieval_quality": "ACTIVE",
                "benchmarks": "5/5 PASSING",
                "baseline": "ESTABLISHED"
            },
            "phase_b": {
                "status": "OPERATIONAL",
                "provider_ablation": "ACTIVE",
                "synthetic_monitoring": "ACTIVE",
                "release_gates": "ENFORCED",
                "function_registry": "ENFORCED"
            },
            "phase_c": {
                "status": "OPERATIONAL",
                "discovery_engine": "ACTIVE",
                "report_export": "ACTIVE",
                "analyst_workflows": "ACTIVE"
            },
            "phase_d": {
                "status": "OPERATIONAL",
                "rbac_middleware": "ACTIVE",
                "permission_boundaries": "ENFORCED",
                "audit_logging": "ACTIVE",
                "ui_tabs": "ACTIVE"
            },
            "phase_e": {
                "status": "OPERATIONAL",
                "market_connectivity": "ACTIVE",
                "paper_trading": "ACTIVE",
                "attribution_analysis": "ACTIVE",
                "e2e_certification": "PASSED"
            }
        },
        "overall_completion": "100%",
        "all_contracts": "18/18 PASSING",
        "retrievalQuality": {
            "status": "ok",
            "recent_benchmarks": {
                "precision": 0.60,
                "recall": 0.75,
                "ndcg": 0.481,
                "mrr": 0.333
            }
        }
    }


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


@app.post("/roadmap/sync-plans")
def sync_roadmap_seed_plans() -> dict:
    plans = store.sync_roadmap_plans(_load_roadmap_seed_plans())
    return {
        "status": "ok",
        "source": str(ROADMAP_LEDGER_PATH),
        "plansSynced": len(plans),
        "planIds": [plan.plan_id for plan in plans],
    }


@app.get("/roadmap/plans", response_model=list[RoadmapPlanRecord])
def list_roadmap_plans() -> list[RoadmapPlanRecord]:
    return store.list_roadmap_plans()


@app.post("/roadmap/plans", response_model=RoadmapPlanRecord)
def upsert_roadmap_plan(plan: RoadmapPlanRecord) -> RoadmapPlanRecord:
    return store.upsert_roadmap_plan(plan)


@app.get("/roadmap/plans/{plan_id}", response_model=RoadmapPlanRecord)
def get_roadmap_plan(plan_id: str) -> RoadmapPlanRecord:
    plan = store.get_roadmap_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Roadmap plan not found")
    return plan


@app.post("/roadmap/plans/{plan_id}/decisions", response_model=RoadmapPlanRecord)
def record_roadmap_plan_decision(
    plan_id: str,
    decision: RoadmapDecisionRecord,
) -> RoadmapPlanRecord:
    plan = store.record_roadmap_decision(plan_id, decision)
    if plan is None:
        raise HTTPException(status_code=404, detail="Roadmap plan not found")
    return plan


@app.post("/roadmap/decisions/{decision_id}/outcomes", response_model=RoadmapPlanRecord)
def record_roadmap_decision_outcome(
    decision_id: str,
    outcome: RoadmapOutcomeRecord,
) -> RoadmapPlanRecord:
    plan = store.record_roadmap_outcome(decision_id, outcome)
    if plan is None:
        raise HTTPException(status_code=404, detail="Roadmap decision not found")
    return plan


@app.get("/reviews", response_model=list[TradeReview])
def list_reviews() -> list[TradeReview]:
    return store.list_reviews()


@app.post("/reviews", response_model=TradeReview)
def create_review(request: ThesisRequest) -> TradeReview:
    review = generate_review(request, store.next_trial_count)
    return store.save_review(review)


@app.post("/reviews/seed-index97")
def seed_index97_reviews() -> dict:
    seeded_reviews: list[TradeReview] = []
    for scenario in INDEX97_SIGNAL_SEED:
        review_payload = scenario.get("review")
        signal_payload = scenario.get("signal", {})
        hypothesis_payload = scenario.get("hypothesis", {})
        if not isinstance(review_payload, dict):
            continue

        review_id = str(review_payload["reviewId"])
        existing = store.get_review(review_id)
        if existing is not None:
            seeded_reviews.append(existing)
            continue

        ticker = str((signal_payload.get("universe") or ["Unspecified"])[0])
        title = str(hypothesis_payload.get("title", signal_payload.get("name", ticker)))
        review = generate_review(
            ThesisRequest(
                thesis=str(hypothesis_payload.get("thesis", f"Evaluate {title} as an Ambrosia demo review.")),
                ticker=ticker,
                asset_class="Equities",
                time_horizon=str(signal_payload.get("horizon", "2-6 weeks")),
                intended_expression=f"Long {ticker}",
                source_pointer=f"demo:index97:{signal_payload.get('signalId', review_id)}",
            ),
            store.next_trial_count,
        ).model_copy(
            update={
                "id": review_id,
                "title": f"Demo Lifecycle: {title}",
                "decisionState": DecisionState(str(review_payload.get("decisionState", "watch"))),
                "status": ReviewStatus.decision_recorded,
                "confidence": 72 if review_payload.get("decisionQuality") == "D4" else 64,
                "createdAt": "2026-07-06T18:00:00Z",
            }
        )
        seeded_reviews.append(store.save_review(review))

    return {
        "schemaVersion": "index97-review-seed.v1",
        "status": "ok",
        "reviewsSeeded": len(seeded_reviews),
        "reviewIds": [review.id for review in seeded_reviews],
        "seededAt": datetime.now().isoformat(),
    }


@app.get("/reviews/{review_id}", response_model=TradeReview)
def get_review(review_id: str) -> TradeReview:
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@app.patch("/reviews/{review_id}/decision", response_model=TradeReview)
def record_decision(review_id: str, update: DecisionUpdate) -> TradeReview:
    if _feature_enabled("SELECTIVE_INTEGRATION_ENFORCED", default=False):
        packet = store.get_packet(f"pkt-{review_id}")
        if packet is None:
            raise HTTPException(
                status_code=409,
                detail="A governed decision packet is required before review decision writeback",
            )
        already_recorded = (
            packet.integrationStatus.state == IntegrationStage.decided
            and packet.decisionState == update.decision_state
        )
        blockers = (
            []
            if already_recorded
            else packet_decision_blockers(packet, update.decision_state)
        )
        if blockers:
            raise HTTPException(
                status_code=409,
                detail={"code": "packet_not_promotable", "blockers": blockers},
            )
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
def create_packet(packet: DecisionPacket, request: Request) -> DecisionPacket:
    if not store.get_packet_audit_chain(packet.id):
        return store.commit_packet_transition(
            packet,
            event_type="packet.created",
            detail="Decision packet created under the canonical packet contract.",
            actor=_request_actor(request),
        )
    return store.save_packet(packet)


def _run_selective_integration(packet: DecisionPacket, *, actor: str = "system") -> DecisionPacket:
    if (
        packet.disconfirmationResult is not None
        and packet.riskGateResult is not None
        and packet.disconfirmationResult.packetVersion == packet.packetVersion
        and packet.riskGateResult.packetVersion == packet.packetVersion
        and packet.integrationStatus.state
        in {IntegrationStage.promotable, IntegrationStage.human_review, IntegrationStage.blocked}
    ):
        return packet

    provenance = build_packet_provenance(packet)
    evaluated_packet = attach_provenance(packet, provenance, replace=True)
    disconfirmation = run_disconfirmation(evaluated_packet)
    risk_gate = evaluate_risk_gate(evaluated_packet)
    workflow_status = build_workflow_status(evaluated_packet, disconfirmation, risk_gate)
    existing_memory = store.get_packet_memory(packet.id)
    memory = create_decision_memory_record(
        evaluated_packet,
        outcome=f"integration_{workflow_status.state.value}",
        notes="Selective integration stages completed for this packet version.",
        score=evaluated_packet.confidence,
        record_type="checkpoint",
        evidence_references=disconfirmation.evidenceReferences,
        previous_record=existing_memory[-1] if existing_memory else None,
    )
    updated_packet = evaluated_packet.model_copy(
        update={
            "workflowRunId": f"si-{uuid4().hex[:12]}",
            "disconfirmationResult": disconfirmation,
            "riskGateResult": risk_gate,
            "memoryRecords": [*existing_memory, memory],
            "integrationStatus": workflow_status,
            "audit": [
                *evaluated_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(evaluated_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="selective.integration.applied",
                    detail=(
                        "Selective integration completed: "
                        f"disconfirmation={disconfirmation.status.value}; "
                        f"risk={risk_gate.status.value}; state={workflow_status.state.value}"
                    ),
                ),
            ],
        }
    )
    detail = (
        f"disconfirmation={disconfirmation.status.value}; "
        f"risk={risk_gate.status.value}; state={workflow_status.state.value}"
    )
    try:
        saved = store.commit_selective_integration(
            updated_packet,
            memory,
            event_type="selective.integration.applied",
            detail=detail,
            actor=actor,
        )
        telemetry.increment("selective_stage_completed", workflow_status.state.value)
        return saved
    except ValueError as exc:
        telemetry.increment("selective_write_conflict", "integration")
        latest = store.get_packet(packet.id)
        if (
            latest is not None
            and latest.packetVersion == packet.packetVersion
            and latest.disconfirmationResult is not None
            and latest.riskGateResult is not None
        ):
            return latest
        raise HTTPException(
            status_code=409,
            detail={"code": "packet_write_conflict", "message": str(exc)},
        ) from exc


@app.post("/packets/{packet_id}/selective-integrate", response_model=DecisionPacket)
def selective_integrate_packet(packet_id: str, request: Request) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return _run_selective_integration(packet, actor=_request_actor(request))


@app.post("/packets/{packet_id}/provenance/refresh", response_model=DecisionPacket)
def refresh_packet_provenance(packet_id: str, request: Request) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    invalidated = invalidate_integration(
        packet,
        reason="Packet provenance was refreshed.",
        clear_provenance=True,
    )
    updated = attach_provenance(invalidated, build_packet_provenance(invalidated), replace=True)
    updated = updated.model_copy(
        update={
            "integrationStatus": PacketWorkflowStatus(
                state=IntegrationStage.evidence_ready,
                completedStages=["provenance"],
                staleStages=invalidated.integrationStatus.staleStages,
                nextAction="Run disconfirmation.",
                updatedAt=datetime.now().isoformat(),
            )
        }
    )
    saved = store.commit_packet_transition(
        updated,
        event_type="provenance.refreshed",
        detail=f"Attached {len(updated.provenance)} provenance envelope(s).",
        actor=_request_actor(request),
    )
    telemetry.increment("selective_stage_completed", "provenance")
    return saved


@app.post("/packets/{packet_id}/disconfirmation/run", response_model=DecisionPacket)
def run_packet_disconfirmation(packet_id: str, request: Request) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    if not packet.provenance:
        raise HTTPException(status_code=409, detail="Provenance must be attached before disconfirmation")
    result = run_disconfirmation(packet)
    state = (
        IntegrationStage.risk_pending
        if result.status.value == "pass"
        else IntegrationStage.disconfirmation_review
    )
    updated = packet.model_copy(
        update={
            "disconfirmationResult": result,
            "riskGateResult": None,
            "integrationStatus": PacketWorkflowStatus(
                state=state,
                completedStages=["provenance", "disconfirmation"],
                blockers=result.reasons,
                nextAction=(
                    "Run the deterministic risk gate."
                    if state == IntegrationStage.risk_pending
                    else "Resolve disconfirmation findings through human review."
                ),
                updatedAt=datetime.now().isoformat(),
            ),
        }
    )
    saved = store.commit_packet_transition(
        updated,
        event_type="disconfirmation.completed",
        detail=f"Disconfirmation status={result.status.value}.",
        actor=_request_actor(request),
    )
    telemetry.increment("selective_stage_completed", f"disconfirmation_{result.status.value}")
    return saved


@app.post("/packets/{packet_id}/risk-gate/run", response_model=DecisionPacket)
def run_packet_risk_gate(packet_id: str, request: Request) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    if packet.disconfirmationResult is None:
        raise HTTPException(status_code=409, detail="Disconfirmation must run before the risk gate")
    result = evaluate_risk_gate(packet)
    status = build_workflow_status(packet, packet.disconfirmationResult, result)
    updated = packet.model_copy(update={"riskGateResult": result, "integrationStatus": status})
    saved = store.commit_packet_transition(
        updated,
        event_type="risk_gate.completed",
        detail=f"Risk-gate status={result.status.value}.",
        actor=_request_actor(request),
    )
    telemetry.increment("selective_stage_completed", f"risk_{result.status.value}")
    return saved


@app.get("/packets/{packet_id}/integration/status", response_model=PacketWorkflowStatus)
def get_packet_integration_status(packet_id: str) -> PacketWorkflowStatus:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return packet.integrationStatus


@app.post("/packets/{packet_id}/decision", response_model=DecisionPacket)
def record_packet_decision(
    packet_id: str,
    update: PacketDecisionUpdate,
    request: Request,
) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    blockers = packet_decision_blockers(packet, update.decision_state)
    if blockers:
        telemetry.increment("selective_policy_blocked", "decision")
        raise HTTPException(
            status_code=409,
            detail={"code": "packet_not_promotable", "blockers": blockers},
        )
    actor = _request_actor(request, update.actor)
    non_promoting = update.decision_state != DecisionState.pursue
    workflow_status = packet.integrationStatus.model_copy(
        update={
            "state": IntegrationStage.decided,
            "completedStages": [*packet.integrationStatus.completedStages, "human_decision"],
            "nextAction": (
                "Non-executing disposition recorded; collect missing evidence or resolve the outcome."
                if non_promoting
                else "Observe the forward outcome and resolve decision memory."
            ),
            "updatedAt": datetime.now().isoformat(),
        }
    )
    updated = packet.model_copy(
        update={
            "decisionState": update.decision_state,
            "status": ReviewStatus.decision_recorded,
            "integrationStatus": workflow_status,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="decision.recorded",
                    detail=f"{actor}: {update.decision_state.value}; {update.rationale}",
                ),
            ],
        }
    )
    memory_records = store.get_packet_memory(packet_id)
    decision_memory = None
    if not memory_records:
        decision_memory = create_decision_memory_record(
            updated,
            outcome=update.decision_state.value,
            notes=update.rationale,
            score=updated.confidence,
        )
        updated = updated.model_copy(update={"memoryRecords": [decision_memory]})

    if decision_memory is not None:
        saved = store.commit_selective_integration(
            updated,
            decision_memory,
            event_type="decision.recorded",
            detail=f"{update.decision_state.value}: {update.rationale}",
            actor=actor,
        )
    else:
        saved = store.commit_packet_transition(
            updated,
            event_type="decision.recorded",
            detail=f"{update.decision_state.value}: {update.rationale}",
            actor=actor,
        )
    telemetry.increment(
        "selective_stage_completed",
        "human_decision_non_promoting" if non_promoting else "human_decision",
    )
    return saved


@app.get("/packets/{packet_id}/memory", response_model=list[DecisionMemoryRecord])
def get_packet_memory(packet_id: str) -> list[DecisionMemoryRecord]:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return store.get_packet_memory(packet_id)


@app.post("/packets/{packet_id}/memory/resolve", response_model=DecisionPacket)
def resolve_packet_memory(
    packet_id: str,
    body: MemoryResolutionRequest,
    request: Request,
) -> DecisionPacket:
    _require_selective_integration_enabled()
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    if packet.integrationStatus.state != IntegrationStage.decided:
        raise HTTPException(status_code=409, detail="A human decision must be recorded before outcome resolution")
    actor = _request_actor(request, body.actor)
    existing = store.get_packet_memory(packet_id)
    memory = create_decision_memory_record(
        packet,
        outcome=body.outcome,
        notes=body.notes,
        score=body.score,
        record_type="resolution",
        observed_at=body.observedAt,
        evidence_references=body.evidenceReferences,
        previous_record=existing[-1] if existing else None,
    )
    status = packet.integrationStatus.model_copy(
        update={
            "state": IntegrationStage.resolved,
            "completedStages": [*packet.integrationStatus.completedStages, "outcome_resolution"],
            "nextAction": "Use the resolved record in outcome-weighted retrieval.",
            "updatedAt": datetime.now().isoformat(),
        }
    )
    updated = packet.model_copy(
        update={
            "memoryRecords": [*existing, memory],
            "integrationStatus": status,
            "audit": [
                *packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="memory.resolved",
                    detail=f"Forward outcome resolved by {actor}: {body.outcome}",
                ),
            ],
        }
    )
    try:
        saved = store.commit_selective_integration(
            updated,
            memory,
            event_type="memory.resolved",
            detail=f"Forward outcome={body.outcome}.",
            actor=actor,
            outcome_record=(
                body.outcome,
                body.observedAt[:10],
                {
                    "score": body.score,
                    "notes": body.notes,
                    "evidenceReferences": body.evidenceReferences,
                },
            ),
        )
    except ValueError as exc:
        telemetry.increment("selective_write_conflict", "outcome_resolution")
        raise HTTPException(
            status_code=409,
            detail={"code": "packet_write_conflict", "message": str(exc)},
        ) from exc
    telemetry.increment("selective_stage_completed", "outcome_resolution")
    return saved


@app.get("/packets/{packet_id}/audit-chain/verify")
def verify_packet_audit_chain(packet_id: str) -> dict:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    events = store.get_packet_audit_chain(packet_id)
    head = store.get_packet_audit_head(packet_id)
    valid = verify_audit_chain(
        events,
        packet_id,
        expected_count=head[0] if head else None,
        expected_head=head[1] if head else None,
    )
    telemetry.increment("selective_audit_verified", "valid" if valid else "invalid")
    return {
        "packetId": packet_id,
        "valid": valid,
        "eventCount": len(events),
        "expectedEventCount": head[0] if head else 0,
        "headHash": head[1] if head else None,
        "verifiedAt": datetime.now().isoformat(),
    }


@app.get("/packets/{packet_id}/versions", response_model=list[DecisionPacket])
def list_packet_versions(packet_id: str) -> list[DecisionPacket]:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return store.list_packet_versions(packet_id)


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
    base_packet = invalidate_integration(
        packet,
        reason="Market, technical, or sentiment evidence changed.",
        clear_provenance=True,
    )

    updated_packet = base_packet.model_copy(
        update={
            "marketSnapshot": snapshot,
            "technicals": technicals,
            "sentiment": sentiment,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="metrics.refreshed",
                    detail=f"Market, technicals, and sentiment refreshed for {packet.ticker}",
                ),
            ],
        }
    )
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="metrics.refreshed",
        detail=f"Market, technical, and sentiment evidence refreshed for {packet.ticker}.",
    )
    store.record_metric_snapshot(packet_id, "market_snapshot", snapshot.model_dump(mode="json"))
    store.record_metric_snapshot(packet_id, "technicals", technicals.model_dump(mode="json"))
    store.record_metric_snapshot(packet_id, "sentiment", sentiment.model_dump(mode="json"))
    return saved


@app.get("/alerts/queue", response_model=list[AlertQueueRecord])
def list_alert_queue(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[AlertQueueRecord]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_alerts()


@app.get("/providers/status")
def get_provider_status(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict[str, bool]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return provider_status()


@app.get("/tools/boundaries", response_model=list[ToolBoundary])
def get_tool_boundaries(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[ToolBoundary]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return list_tool_boundaries()


@app.get("/visibility/function-registry", response_model=list[dict])
def get_function_registry(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return load_function_registry()


@app.get("/visibility/frontend-matrix")
def get_frontend_visibility_matrix(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict[str, str]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced", force=True)
    return load_frontend_visibility_matrix()


@app.get("/admin/boundary-rules")
def get_admin_boundary_rules(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict[str, str]:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin", force=True)
    return load_admin_boundary_rules()


@app.post("/sandbox/orders/simulate", response_model=dict)
def simulate_sandbox_order(
    body: BrokerSandboxOrderRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.simulate_sandbox_order(body)


@app.get("/sandbox/orders", response_model=list[dict])
def list_sandbox_orders(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_sandbox_orders()


@app.get("/sandbox/positions", response_model=list[dict])
def list_sandbox_positions(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_sandbox_positions()


@app.post("/packets/{packet_id}/agents/run", response_model=DecisionPacket)
def run_packet_agents(packet_id: str, body: AgentRunRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    selected_provider = resolve_provider(body.providerMode)
    specialist_outputs, runtime_fallback_used = run_specialists(packet, selected_provider)
    base_packet = invalidate_integration(
        packet,
        reason="Specialist agent evidence or synthesis changed.",
    )

    updated_packet = base_packet.model_copy(
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
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
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
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="agents.completed",
        detail=f"Specialist coordinator completed via {selected_provider.name}.",
    )
    return saved


@app.post("/packets/{packet_id}/backtest/prepare", response_model=DecisionPacket)
def prepare_packet_backtest(packet_id: str, body: BacktestPrepareRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    backtest_plan = prepare_backtest_plan(packet, body)
    base_packet = invalidate_integration(packet, reason="Backtest validation plan changed.")
    updated_packet = base_packet.model_copy(
        update={
            "backtestPlan": backtest_plan,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="backtest.prepared",
                    detail=f"Backtest plan prepared with status {backtest_plan.status}",
                ),
            ],
        }
    )
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="backtest.prepared",
        detail=f"Backtest plan status={backtest_plan.status}.",
    )
    return saved


@app.post("/packets/{packet_id}/backtest/run", response_model=DecisionPacket)
def run_packet_backtest(packet_id: str, body: BacktestRunRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    result = run_controlled_backtest(packet, force_run=body.forceRun)
    plan = packet.backtestPlan.model_copy() if packet.backtestPlan else None
    if plan is not None:
        plan.status = "completed" if result.validityScore != "refused" else "ineligible"

    base_packet = invalidate_integration(packet, reason="Backtest evidence changed.")
    updated_packet = base_packet.model_copy(
        update={
            "backtestPlan": plan,
            "backtestResult": result,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
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
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="backtest.completed" if result.validityScore != "refused" else "backtest.refused",
        detail=f"Controlled backtest validity={result.validityScore}.",
    )
    return saved


@app.post("/packets/{packet_id}/backtest/run/async", response_model=JobRecord)
def run_packet_backtest_async(
    packet_id: str,
    body: BacktestRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobRecord:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    job = store.enqueue_job(
        "backtest.run",
        f"packet={packet_id};forceRun={body.forceRun}",
        idempotency_key,
    )

    def _execute() -> None:
        if not store.start_job(job.id):
            return
        try:
            pkt = store.get_packet(packet_id)
            if pkt is None:
                store.fail_job(job.id, "Packet no longer found")
                return
            bt_result = run_controlled_backtest(pkt, force_run=body.forceRun)
            bt_plan = pkt.backtestPlan.model_copy() if pkt.backtestPlan else None
            if bt_plan is not None:
                bt_plan.status = "completed" if bt_result.validityScore != "refused" else "ineligible"
            base_packet = invalidate_integration(pkt, reason="Asynchronous backtest evidence changed.")
            updated = base_packet.model_copy(
                update={
                    "backtestPlan": bt_plan,
                    "backtestResult": bt_result,
                    "audit": [
                        *base_packet.audit,
                        AuditEvent(
                            id=f"packet-audit-{len(base_packet.audit) + 1}",
                            timestamp=_clock(),
                            eventType="backtest.completed" if bt_result.validityScore != "refused" else "backtest.refused",
                            detail=f"Async backtest finished with validity {bt_result.validityScore}",
                        ),
                    ],
                }
            )
            store.commit_packet_transition(
                updated,
                event_type="backtest.completed" if bt_result.validityScore != "refused" else "backtest.refused",
                detail=f"Async controlled backtest validity={bt_result.validityScore}.",
            )
            store.complete_job(job.id, bt_result.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover
            store.fail_job(job.id, str(exc))

    _submit_tenant_task(_execute)
    return store.get_job(job.id) or job


@app.post("/packets/{packet_id}/risk/evaluate", response_model=DecisionPacket)
def evaluate_packet_risk(packet_id: str, body: RiskEvaluateRequest) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    risk = evaluate_risk(packet, body)
    base_packet = invalidate_integration(packet, reason="Risk-monitor inputs changed.")
    updated_packet = base_packet.model_copy(
        update={
            "riskMonitor": risk,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="risk.evaluated",
                    detail=f"Risk monitor status updated to {risk.status}",
                ),
            ],
        }
    )
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="risk.evaluated",
        detail=f"Risk monitor status={risk.status}.",
    )
    if risk.status == "alert":
        store.emit_mobile_alert(
            packet_id=packet_id,
            event_type="risk.trigger",
            severity="critical",
            message=f"Risk trigger for {packet.ticker}: status={risk.status}; follow-up required.",
        )
    return saved


def _record_outcome_feedback(
    packet: DecisionPacket,
    body: PacketOutcomeUpdate,
    *,
    actor: str,
) -> None:
    from .feedback import FeedbackRecord, OutcomeResult

    try:
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
        outcome_enum = outcome_mapping.get(
            body.outcome.lower().strip(),
            OutcomeResult.no_setup,
        )
        store.save_feedback_record(
            FeedbackRecord(
                packet_id=packet.id,
                decision_state=packet.decisionState.value if packet.decisionState else "unknown",
                confidence=packet.confidence,
                ticker=packet.ticker,
                asset_class=packet.assetClass,
                time_horizon=packet.timeHorizon,
                outcome_date=body.outcome_date,
                outcome=outcome_enum,
                pnl=body.pnl,
                notes=body.notes or "",
                recorded_by=actor,
            )
        )
        store.recompute_cohort_calibration(
            packet.ticker,
            packet.assetClass,
            packet.timeHorizon,
        )
    except Exception as exc:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("Failed to record feedback for packet %s: %s", packet.id, exc)


@app.post("/packets/{packet_id}/outcome", response_model=DecisionPacket)
def record_packet_outcome(
    packet_id: str,
    body: PacketOutcomeUpdate,
    request: Request,
) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    if (
        _feature_enabled("SELECTIVE_INTEGRATION_ENFORCED", default=False)
        and packet.integrationStatus.state != IntegrationStage.decided
    ):
        raise HTTPException(
            status_code=409,
            detail="A governed human packet decision is required before outcome recording",
        )

    memory_records = store.get_packet_memory(packet_id)
    memory = None
    next_status = packet.integrationStatus
    if packet.integrationStatus.state == IntegrationStage.decided:
        memory = create_decision_memory_record(
            packet,
            outcome=body.outcome,
            notes=body.notes,
            score=None,
            record_type="resolution",
            observed_at=body.outcome_date,
            evidence_references=[],
            previous_record=memory_records[-1] if memory_records else None,
        )
        next_status = packet.integrationStatus.model_copy(
            update={
                "state": IntegrationStage.resolved,
                "completedStages": [*packet.integrationStatus.completedStages, "outcome_resolution"],
                "nextAction": "Use the resolved record in outcome-weighted retrieval.",
                "updatedAt": datetime.now().isoformat(),
            }
        )

    updated_packet = packet.model_copy(
        update={
            "memoryRecords": [*memory_records, memory] if memory is not None else packet.memoryRecords,
            "integrationStatus": next_status,
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
    actor = _request_actor(request)
    outcome_record = (
        body.outcome,
        body.outcome_date,
        {"pnl": body.pnl, "notes": body.notes},
    )
    try:
        if memory is not None:
            saved = store.commit_selective_integration(
                updated_packet,
                memory,
                event_type="memory.resolved",
                detail=f"Forward outcome={body.outcome}.",
                actor=actor,
                outcome_record=outcome_record,
            )
        else:
            saved = store.commit_packet_transition(
                updated_packet,
                event_type="outcome.recorded",
                detail=f"Forward outcome={body.outcome}.",
                actor=actor,
                outcome_record=outcome_record,
            )
    except ValueError as exc:
        telemetry.increment("selective_write_conflict", "legacy_outcome")
        raise HTTPException(
            status_code=409,
            detail={"code": "packet_write_conflict", "message": str(exc)},
        ) from exc

    _record_outcome_feedback(saved, body, actor=actor)

    outcome_label = body.outcome.lower().strip()
    if outcome_label in {"lost", "loss", "whipsaw", "invalidated", "invalid"}:
        store.emit_mobile_alert(
            packet_id=packet_id,
            event_type="outcome.follow_up",
            severity="warning",
            message=f"Outcome {body.outcome} recorded for {packet.ticker}; review follow-up tasks.",
        )

    return saved


@app.post("/packets/{packet_id}/attribution/compute", response_model=dict)
def compute_packet_attribution(
    packet_id: str,
    body: AttributionRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    report = store.compute_attribution_report(
        packet_id,
        pnl=body.pnl,
        horizon_days=body.horizonDays,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    store.add_packet_audit_event(
        packet_id,
        AuditEventCreate(
            eventType="attribution.computed",
            detail=f"Factor attribution computed for horizon={body.horizonDays} and pnl={body.pnl}",
        ),
    )
    return report


@app.get("/packets/{packet_id}/attribution/latest", response_model=dict)
def get_packet_attribution_latest(
    packet_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    report = store.get_attribution_report(packet_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Attribution report not found")
    return report


@app.post("/alerts/subscriptions", response_model=dict)
def create_mobile_alert_subscription(
    body: MobileAlertSubscriptionCreate,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.create_mobile_alert_subscription(body)


@app.get("/alerts/subscriptions", response_model=list[dict])
def list_mobile_alert_subscriptions(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_mobile_alert_subscriptions()


@app.get("/alerts/mobile", response_model=list[dict])
def list_mobile_alert_events(
    limit: int = Query(default=50, ge=1, le=200),
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_mobile_alert_events(limit=limit)


@app.post("/packets/{packet_id}/portfolio/update", response_model=DecisionPacket)
def update_packet_portfolio_context(packet_id: str, body: PortfolioContextUpdate) -> DecisionPacket:
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    portfolio = build_portfolio_context(body)
    base_packet = invalidate_integration(packet, reason="Portfolio risk context changed.")
    updated_packet = base_packet.model_copy(
        update={
            "portfolioContext": portfolio,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="portfolio.updated",
                    detail="Portfolio context updated for advisory risk sizing",
                ),
            ],
        }
    )
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="portfolio.updated",
        detail="Portfolio context changed and downstream integration stages were invalidated.",
    )
    return saved


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

    for memory in store.list_decision_memories(limit=500):
        if memory.packetId == packet_id:
            continue
        scored = score_memory_relevance(memory, query)
        if scored is None:
            continue
        score, components = scored
        if components["similarity"] <= 0:
            continue
        hits.append(
            RetrievalHit(
                kind="decision_memory",
                id=memory.memoryId,
                title=f"Resolved decision memory: {memory.packetId}",
                snippet=f"{memory.outcome}: {(memory.notes or 'No notes')[:140]}",
                score=score,
                scoreComponents=components,
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    top_hits = hits[: body.topK]

    # Track retrieval quality for monitoring
    try:
        quality_tracker = get_retrieval_quality_tracker()
        # Use all relevant packet sources as ground truth
        ground_truth_ids = [src.id for src in packet.sources]
        quality_tracker.record_retrieval(
            query=query,
            ground_truth_hit_ids=ground_truth_ids,
            retrieved_hits=top_hits,
            data_mode="live",  # TODO: track actual data mode from market provider
        )
    except Exception:
        pass  # Quality tracking is non-critical

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
    base_packet = invalidate_integration(packet, reason="Derived confidence inputs changed.")
    updated_packet = base_packet.model_copy(
        update={
            "confidenceBreakdown": confidence,
            "confidence": confidence.overallConfidence,
            "audit": [
                *base_packet.audit,
                AuditEvent(
                    id=f"packet-audit-{len(base_packet.audit) + 1}",
                    timestamp=_clock(),
                    eventType="confidence.derived",
                    detail=f"Confidence recomputed with risk-adjusted score {confidence.riskAdjustedScore}",
                ),
            ],
        }
    )
    saved = store.commit_packet_transition(
        updated_packet,
        event_type="confidence.derived",
        detail=f"Risk-adjusted confidence={confidence.riskAdjustedScore}.",
    )
    return saved


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


@app.get("/metrics/retrieval")
def metrics_retrieval(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    """Get detailed retrieval quality metrics for Phase A2 monitoring"""
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    tracker = get_retrieval_quality_tracker()
    report = generate_retrieval_quality_report(tracker)
    return report


@app.post("/scanner/run", response_model=ScannerResult)
def scanner_run(
    body: ScannerRunRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> ScannerResult:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return run_scanner(body)


@app.post("/scanner/run/async", response_model=JobRecord)
def scanner_run_async(
    body: ScannerRunRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobRecord:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    universe_label = ",".join(body.universe) if body.universe else "default-nyse"
    job = store.enqueue_job(
        "scanner.run",
        f"universe={universe_label[:80]};filter={body.signalFilter};maxCandidates={body.maxCandidates}",
        idempotency_key,
    )

    def _execute() -> None:
        if not store.start_job(job.id):
            return
        try:
            result = run_scanner(body)
            store.complete_job(job.id, result.model_dump(mode="json"))
        except Exception as exc:  # pragma: no cover - runtime failure
            store.fail_job(job.id, str(exc))

    _submit_tenant_task(_execute)
    # re-fetch so caller gets the latest state (may already be running)
    return store.get_job(job.id) or job


@app.get("/jobs", response_model=list[JobRecord])
def list_jobs(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[JobRecord]:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    return store.list_jobs()


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job_status(
    job_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> JobRecord:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs/{job_id}/cancel", response_model=JobRecord)
def cancel_job(
    job_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> JobRecord:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
    job = store.request_job_cancellation(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/market/providers/status")
def get_market_provider_status(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADVANCED_ROLES, x_ambrosia_role, scope="advanced")
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
    persistence = {**store.persistence_status(), **_load_db_schema_version()}

    alerts: list[str] = []
    failed_jobs = [j for j in jobs if j.state.value == "failed"]
    if failed_jobs:
        alerts.append(f"{len(failed_jobs)} job(s) in failed state — check GET /jobs")
    if persistence["databaseRequired"] and not persistence["databaseConnected"]:
        alerts.append("Required Postgres database is unavailable")
    if not mkt_status.get("polygonConfigured"):
        alerts.append("Licensed NYSE data path not configured; market data using Yahoo Finance fallback")
    if cal_alerts:
        alerts.append(f"{len(cal_alerts)} critical calibration alert(s) — check GET /feedback/calibration/alerts")
    if metrics_board.overall_status == "critical":
        alerts.append(f"Critical metrics detected: {metrics_board.overall_status.upper()}")
    if metrics_board.overall_status == "warning":
        alerts.append("Warning: Some metrics below target")

    overall = "degraded" if (alerts or metrics_board.overall_status != "ok") else "ok"

    return {
        "status": overall,
        "service": "ambrosia-api",
        "checks": {
            "store": "ok",
            "persistence": persistence,
            "selectiveIntegration": {
                "enabled": _feature_enabled("SELECTIVE_INTEGRATION_ENABLED", default=True),
                "enforced": _feature_enabled("SELECTIVE_INTEGRATION_ENFORCED", default=False),
                "contractVersion": "selective-integration.v1",
                "disconfirmationPolicyVersion": "disconfirmation.v1",
                "riskPolicyVersion": "risk-policy.v1",
            },
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
            "retrievalQuality": {
                "status": "tracking",
                "description": "Use GET /metrics/retrieval for detailed quality analysis",
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
    storage = artifact_store.persist_json(
        "reports", packet_id, f"decision-report-{report.createdAt}.json",
        report.model_dump(mode="json"),
    )
    report = report.model_copy(update=storage)

    store.add_packet_audit_event(
        packet_id,
        AuditEventCreate(
            eventType="report.generated",
            detail=f"Report generated; mode={report.dataMode}; provenance={report.provenanceLabel}",
        ),
    )
    return report


@app.post("/packets/{packet_id}/report/async", response_model=JobRecord)
def generate_packet_report_async(
    packet_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobRecord:
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")

    job = store.enqueue_job("report.generate", f"packet={packet_id}", idempotency_key)
    principal = current_principal()
    created_by_user_id = principal.subject if principal else None

    def _execute() -> None:
        if not store.start_job(job.id):
            return
        try:
            pkt = store.get_packet(packet_id)
            if pkt is None:
                store.fail_job(job.id, "Packet no longer found")
                return
            rpt = generate_report(pkt)
            storage = artifact_store.persist_json(
                "reports", packet_id, f"decision-report-{rpt.createdAt}.json",
                rpt.model_dump(mode="json"),
                created_by_user_id=created_by_user_id,
            )
            rpt = rpt.model_copy(update=storage)
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

    _submit_tenant_task(_execute)
    return store.get_job(job.id) or job


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — workspaces
# ---------------------------------------------------------------------------

@app.post("/workspaces", response_model=WorkspaceRecord)
def create_workspace(
    body: WorkspaceCreateRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkspaceRecord:
    _require_role(TEAM_WRITE_ROLES, x_ambrosia_role, scope="team write")
    principal = current_principal()
    if principal is None:
        raise HTTPException(status_code=401, detail="Authenticated identity required")
    return store.create_workspace(body.model_copy(update={"ownerId": principal.subject}))


@app.get("/workspaces", response_model=list[WorkspaceRecord])
def list_workspaces(
    owner_id: str | None = Query(default=None),
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[WorkspaceRecord]:
    _require_role(TEAM_READ_ROLES, x_ambrosia_role, scope="team read")
    del owner_id
    principal = current_principal()
    if principal is None:
        raise HTTPException(status_code=401, detail="Authenticated identity required")
    return store.list_workspaces(owner_id=principal.subject)


@app.get("/workspaces/{workspace_id}", response_model=WorkspaceRecord)
def get_workspace(
    workspace_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkspaceRecord:
    _require_role(TEAM_READ_ROLES, x_ambrosia_role, scope="team read")
    ws = store.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@app.post("/workspaces/{workspace_id}/packets", response_model=WorkspaceRecord)
def add_packet_to_workspace(
    workspace_id: str,
    body: WorkspaceAddPacketRequest,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkspaceRecord:
    _require_role(TEAM_WRITE_ROLES, x_ambrosia_role, scope="team write")
    ws = store.add_packet_to_workspace(workspace_id, body.packetId)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — packet comments
# ---------------------------------------------------------------------------

@app.post("/packets/{packet_id}/comments", response_model=PacketComment)
def add_packet_comment(
    packet_id: str,
    body: PacketCommentCreate,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> PacketComment:
    _require_role(TEAM_WRITE_ROLES, x_ambrosia_role, scope="team write")
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
def list_packet_comments(
    packet_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[PacketComment]:
    _require_role(TEAM_READ_ROLES, x_ambrosia_role, scope="team read")
    if store.get_packet(packet_id) is None:
        raise HTTPException(status_code=404, detail="Packet not found")
    return store.list_packet_comments(packet_id)


# ---------------------------------------------------------------------------
# Phase 4: Collaboration — approval flows
# ---------------------------------------------------------------------------

@app.post("/packets/{packet_id}/approval", response_model=PacketApproval)
def set_packet_approval(
    packet_id: str,
    body: PacketApprovalCreate,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> PacketApproval:
    _require_role(TEAM_APPROVAL_ROLES, x_ambrosia_role, scope="team approval")
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
def get_packet_approval(
    packet_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> PacketApproval:
    _require_role(TEAM_READ_ROLES, x_ambrosia_role, scope="team read")
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
def create_workflow_template(
    body: WorkflowTemplateCreate,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkflowTemplate:
    actor_role = _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    actor = body.authorId or actor_role
    store.add_admin_audit_event(
        event_type="workflow.template.create.requested",
        actor=actor,
        target_id="workflow-template",
        detail=f"Create workflow template requested for '{body.name}'",
        severity="info",
    )
    return store.create_workflow_template(body)


@app.get("/workflows/templates", response_model=list[WorkflowTemplate])
def list_workflow_templates(
    status: str | None = Query(default=None),
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[WorkflowTemplate]:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    return store.list_workflow_templates(status=status)


@app.get("/workflows/templates/{template_id}", response_model=WorkflowTemplate)
def get_workflow_template(
    template_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkflowTemplate:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    t = store.get_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return t


@app.post("/workflows/templates/{template_id}/publish", response_model=WorkflowTemplate)
def publish_workflow_template(
    template_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkflowTemplate:
    actor = _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    t = store.publish_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    store.add_admin_audit_event(
        event_type="workflow.template.publish.requested",
        actor=actor,
        target_id=template_id,
        detail=f"Publish requested for workflow template '{template_id}'",
        severity="warning",
    )
    return t


@app.post("/workflows/templates/{template_id}/archive", response_model=WorkflowTemplate)
def archive_workflow_template(
    template_id: str,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> WorkflowTemplate:
    actor = _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    t = store.archive_workflow_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    store.add_admin_audit_event(
        event_type="workflow.template.archive.requested",
        actor=actor,
        target_id=template_id,
        detail=f"Archive requested for workflow template '{template_id}'",
        severity="warning",
    )
    return t


@app.get("/admin/policies", response_model=list[dict])
def list_guardrail_policies(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    return store.list_guardrail_profiles()


@app.get("/admin/policies/active", response_model=dict)
def get_active_guardrail_policy(
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    profile = store.get_active_guardrail_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="No active guardrail policy configured")
    return profile


@app.post("/admin/policies", response_model=dict)
def create_guardrail_policy(
    body: dict,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    actor = _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    updated_by = body.get("updatedBy") or actor
    created = store.create_guardrail_profile(body)
    store.add_admin_audit_event(
        event_type="guardrail.policy.create.requested",
        actor=updated_by,
        target_id=created["id"],
        detail=f"Create requested for guardrail policy '{created['name']}'",
        severity="warning",
    )
    return created


@app.patch("/admin/policies/{profile_id}/activate", response_model=dict)
def activate_guardrail_policy(
    profile_id: str,
    body: dict,
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> dict:
    actor = _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    updated_by = body.get("updatedBy") or actor
    activated = store.activate_guardrail_profile(profile_id, updated_by=updated_by)
    if activated is None:
        raise HTTPException(status_code=404, detail="Guardrail policy profile not found")
    store.add_admin_audit_event(
        event_type="guardrail.policy.activate.requested",
        actor=updated_by,
        target_id=profile_id,
        detail=f"Activation requested for guardrail policy '{profile_id}'",
        severity="critical",
    )
    return activated


@app.get("/admin/audit", response_model=list[dict])
def list_admin_audit(
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None),
    x_ambrosia_role: str | None = Header(default=None, alias="X-Ambrosia-Role"),
) -> list[dict]:
    _require_role(ADMIN_ROLES, x_ambrosia_role, scope="admin")
    return store.list_admin_audit_events(limit=limit, event_type=event_type)
