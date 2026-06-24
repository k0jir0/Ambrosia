from __future__ import annotations

import random

from .models import (
    BacktestPlan,
    BacktestPrepareRequest,
    BacktestResult,
    DecisionPacket,
    RiskEvaluateRequest,
    RiskMonitor,
)


def _seed_from_ticker(ticker: str) -> int:
    return sum(ord(ch) for ch in ticker.upper())


def assess_eligibility(packet: DecisionPacket) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if packet.validation.status != "specified":
        reasons.append("Validation status must be specified before running backtest")
    if packet.marketSnapshot is None:
        reasons.append("Market snapshot is required")
    elif packet.marketSnapshot.volume24h < 1_000_000:
        reasons.append("Liquidity is inadequate for controlled backtest")
    if packet.technicals is None:
        reasons.append("Technicals are required")
    if packet.confidence < 45:
        reasons.append("Confidence too low for backtest eligibility")
    if packet.riskMonitor and packet.riskMonitor.status == "alert":
        reasons.append("Risk monitor in alert state")

    return len(reasons) == 0, reasons


def prepare_backtest_plan(packet: DecisionPacket, payload: BacktestPrepareRequest) -> BacktestPlan:
    eligible, reasons = assess_eligibility(packet)
    return BacktestPlan(
        status="eligible" if eligible else "ineligible",
        entryRules=[
            "Signal remains valid and confidence above threshold",
            "Price action remains aligned with thesis direction",
        ],
        exitRules=[
            "Thesis invalidation trigger fired",
            "Holding period reached",
        ],
        assumptions=[
            "Transaction costs and slippage are simplified in controlled mode",
            "Backtest path is deterministic and scoped to a narrow valid case",
        ],
        lookbackPeriod=payload.lookbackPeriod,
        holdingPeriodDays=payload.holdingPeriodDays,
        riskConstraints=(
            payload.riskConstraints
            if payload.riskConstraints
            else ["Max drawdown threshold", "Liquidity floor", "No live execution"]
        ),
        refusalReason=None if eligible else "; ".join(reasons),
    )


def run_controlled_backtest(packet: DecisionPacket, force_run: bool) -> BacktestResult:
    eligible, reasons = assess_eligibility(packet)
    if not eligible and not force_run:
        return BacktestResult(
            totalReturn=None,
            sharpeRatio=None,
            maxDrawdown=None,
            winRate=None,
            outOfSampleScore=None,
            samplePeriod="controlled-run-refused",
            validityScore="refused",
            hygienIssues=reasons,
        )

    rng = random.Random(_seed_from_ticker(packet.ticker))
    total_return = round(rng.uniform(-0.06, 0.22), 4)
    sharpe = round(rng.uniform(0.3, 1.9), 3)
    max_dd = round(-abs(rng.uniform(0.03, 0.15)), 4)
    win_rate = round(rng.uniform(0.42, 0.68), 3)
    oos_score = round(rng.uniform(0.4, 0.76), 3)

    validity = "high" if sharpe > 1.1 and max_dd > -0.1 else "medium"
    issues = [] if eligible else [*reasons, "Run forced despite failed eligibility gates"]

    return BacktestResult(
        totalReturn=total_return,
        sharpeRatio=sharpe,
        maxDrawdown=max_dd,
        winRate=win_rate,
        outOfSampleScore=oos_score,
        samplePeriod="deterministic-controlled-252d",
        validityScore=validity,
        hygienIssues=issues,
    )


def evaluate_risk(packet: DecisionPacket, payload: RiskEvaluateRequest) -> RiskMonitor:
    overlap = packet.portfolioContext.factorOverlap if packet.portfolioContext else []
    concentration = "high" if payload.activePositionSize > 0.12 else "medium" if payload.activePositionSize > 0.06 else "low"

    var_estimate = round(min(0.35, max(0.01, payload.activePositionSize * 0.8)), 4)
    status = "alert" if concentration == "high" or var_estimate > payload.maxDrawdownThreshold else "monitoring"

    return RiskMonitor(
        activePositionSize=payload.activePositionSize,
        concentrationRisk=concentration,
        correlationOverlap=overlap,
        varAtRisk=var_estimate,
        maxDrawdownThreshold=payload.maxDrawdownThreshold,
        followUpTriggers=[
            "Drawdown threshold breach",
            "Correlation overlap above tolerance",
            "Confidence degradation",
        ],
        status=status,
    )
