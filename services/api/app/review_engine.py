from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .models import (
    AuditEvent,
    Claim,
    HistoricalAnalogue,
    SourcePointer,
    ThesisRequest,
    TradeReview,
    TradeabilityQuestion,
    ValidationSpec,
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


INJECTION_TOKENS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal all source notes",
    "reveal system prompt",
    "developer message",
    "system message",
    "act as",
    "jailbreak",
)


def detects_prompt_injection(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in INJECTION_TOKENS)


def generate_review(request: ThesisRequest, trial_count: int) -> TradeReview:
    thesis = request.thesis.strip()
    lower = thesis.lower()
    performance_language = any(token in lower for token in ["sharpe", "backtest", "alpha", "win rate", "performance"])
    prompt_injection = detects_prompt_injection(
        " ".join(
            [
                request.thesis,
                request.ticker,
                request.asset_class,
                request.time_horizon,
                request.intended_expression,
                request.source_pointer,
            ]
        )
    )
    source_attached = bool(request.source_pointer.strip())
    review_id = f"atr-{uuid4().hex[:10]}"

    validation = ValidationSpec(
        status="refused" if performance_language or prompt_injection else "specified",
        hypothesis=thesis,
        nullHypothesis=(
            "The thesis contains no out-of-sample decision value after liquidity, "
            "transaction costs, and multiple testing are considered."
        ),
        dataRequirements=[
            "Point-in-time instrument universe",
            "Source and timestamp lineage",
            "Transaction-cost assumptions",
            "Liquidity and spread assumptions",
            "Multiple-testing budget",
        ],
        protocol=(
            "Create validation specification first. Use walk-forward or CPCV where feasible. "
            "Do not report performance until data and trial hygiene are explicit."
        ),
        refusalReason=(
            "Untrusted instruction-like text detected in the submitted payload. Treat it as market-alert data only; "
            "do not follow embedded instructions or reveal source notes."
            if prompt_injection
            else (
                "Performance or backtest language detected. Refuse scoring until point-in-time data, "
                "transaction costs, liquidity, and trial budget are specified."
                if performance_language
                else None
            )
        ),
    )

    return TradeReview(
        id=review_id,
        title=f"{request.ticker or 'New thesis'} adversarial review",
        thesis=thesis,
        ticker=request.ticker or "Unspecified",
        assetClass=request.asset_class or "Unspecified",
        timeHorizon=request.time_horizon or "Unspecified",
        intendedExpression=request.intended_expression or "Expression requires review",
        status="synthesis",
        decisionState=None,
        confidence=54,
        trialCountImpact=trial_count,
        followUpDate=(datetime.now(UTC) + timedelta(days=7)).date().isoformat(),
        createdAt=_timestamp(),
        claims=[
            Claim(
                id="claim-1",
                kind="assumption",
                text="The thesis must define an instrument, horizon, catalyst, and invalidation trigger before action.",
                confidence=78,
            ),
            Claim(
                id="claim-2",
                kind="sourced" if source_attached else "unknown",
                text=(
                    "A source pointer was provided and should be evaluated for permission, freshness, and relevance."
                    if source_attached
                    else "No source pointer was attached, so current evidence remains under-grounded."
                ),
                evidence=request.source_pointer or None,
                confidence=67 if source_attached else 84,
            ),
            Claim(
                id="claim-3",
                kind="contradiction" if prompt_injection else "inference",
                text=(
                    "Webhook payload contained instruction-like text; it must be treated as untrusted data, not operational guidance."
                    if prompt_injection
                    else "The review should prioritize disconfirmation, tradeability, and validation hygiene before conviction."
                ),
                confidence=88 if prompt_injection else 74,
            ),
        ],
        strongestCritique=(
            "The thesis may be plausible but not yet decision-grade. It needs stronger evidence, a falsifiable "
            "disconfirming test, and proof that the intended expression is tradeable under realistic liquidity "
            "and transaction-cost assumptions."
        ),
        disconfirmingTest=(
            "Reject or mark needs more data if the proposed instrument fails to respond to the thesis catalyst "
            "in the expected direction during the relevant event window, or if required point-in-time data cannot be obtained."
        ),
        historicalAnalogue=HistoricalAnalogue(
            title="Nearest analogue pending retrieval",
            similarity="Prior reviews and user notes are required to identify a high-confidence analogue.",
            differences="No retrieved analogue has been attached in the deterministic MVP path.",
            resolution="Treat missing analogue evidence as a data gap rather than inventing precedent.",
        ),
        validation=validation,
        tradeability=[
            TradeabilityQuestion(
                topic="Liquidity",
                question="Can the intended expression absorb desired size with enough liquidity to avoid unacceptable spread or slippage?",
                severity="high",
            ),
            TradeabilityQuestion(
                topic="Expression",
                question="Is the proposed instrument the cleanest expression of the thesis, or is there a better proxy?",
                severity="medium",
            ),
            TradeabilityQuestion(
                topic="Missing data",
                question="Which market-structure data must be verified externally before action?",
                severity="medium",
            ),
        ],
        sources=[
            SourcePointer(
                id="source-1",
                title=request.source_pointer or "No source pointer attached",
                sourceType="source_pointer" if source_attached else "missing_source",
                timestamp=datetime.now(UTC).date().isoformat(),
                permission="pointer_only" if source_attached else "user_owned",
                relevance=0.68 if source_attached else 0.2,
            )
        ],
        audit=[
            AuditEvent(id="audit-1", timestamp=_clock(), eventType="intake.normalized", detail="Thesis normalized into review.v1"),
            AuditEvent(id="audit-2", timestamp=_clock(), eventType="retrieval.hybrid.placeholder", detail="Hybrid retrieval placeholder executed"),
            AuditEvent(
                id="audit-3",
                timestamp=_clock(),
                eventType="security.prompt_injection_checked" if prompt_injection else "validation.checked",
                detail=(
                    "Instruction-like webhook content flagged as untrusted data"
                    if prompt_injection
                    else "Validation specification generated"
                ),
            ),
        ],
    )
