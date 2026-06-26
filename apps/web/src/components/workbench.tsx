"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import {
  createPacket,
  derivePacketConfidence,
  evaluatePacketRisk,
  getMarketSnapshot,
  getMarketTechnicals,
  getPacket,
  getSentiment,
  listReviews,
  preparePacketBacktest,
  recordDecision,
  recordPacketOutcome,
  refreshPacketMetrics,
  runPacketAgents,
} from "@/lib/api";
import { sampleReviews } from "@/lib/sample-data";
import type { DecisionPacket, DecisionState, MarketSnapshot, ReviewStatus, SentimentData, TechnicalIndicators, TradeReview } from "@/lib/types";
import { Badge, Panel, cn } from "./ui";

type NavView = "workbench" | "memory" | "calibration" | "sources";
type ActionResult = "ok" | "fallback" | "skipped";

type LiveMarketData = {
  snapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  ticker: string;
  fetchedAt: string;
};

const statusLabels: Record<ReviewStatus, string> = {
  intake: "Intake",
  retrieval: "Retrieval",
  adversarial_review: "Adversarial critique",
  validation: "Validation gate",
  tradeability: "Tradeability",
  synthesis: "Synthesis",
  decision_recorded: "Decision recorded"
};

const decisionLabels: Record<DecisionState, string> = {
  pursue: "Pursue",
  watch: "Watch",
  reject: "Reject",
  needs_more_data: "Needs more data"
};

export function Workbench({ initialReviewId }: { initialReviewId?: string } = {}) {
  const [reviews, setReviews] = useState<TradeReview[]>(sampleReviews);
  const [packetIdsByReviewId, setPacketIdsByReviewId] = useState<Record<string, string>>({});
  const [activeId, setActiveId] = useState(initialReviewId && sampleReviews.some((review) => review.id === initialReviewId) ? initialReviewId : sampleReviews[0]?.id ?? "");
  const [activeView, setActiveView] = useState<NavView>("workbench");
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ tone: "neutral" | "good" | "warn"; message: string } | null>(null);
  const [liveMarketData, setLiveMarketData] = useState<LiveMarketData | null>(null);
  const [activePacketData, setActivePacketData] = useState<DecisionPacket | null>(null);
  const activeReview = reviews.find((review) => review.id === activeId) ?? reviews[0];

  useEffect(() => {
    let cancelled = false;
    listReviews()
      .then((apiReviews) => {
        if (!cancelled && apiReviews.length > 0) {
          setReviews((current) => mergeReviews(apiReviews, current));
          setActiveId((currentActiveId) => currentActiveId || apiReviews[0].id);
        }
      })
      .catch(() => {
        // The workbench remains fully usable with sample reviews and local generation.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setLiveMarketData(null);
    setActivePacketData(null);
  }, [activeId]);

  useEffect(() => {
    if (!initialReviewId) return;
    if (reviews.some((review) => review.id === initialReviewId)) {
      setActiveId(initialReviewId);
    }
  }, [initialReviewId, reviews]);

  function updateDecision(decisionState: DecisionState) {
    setReviews((current) =>
      current.map((review) =>
        review.id === activeReview.id
          ? {
              ...review,
              decisionState,
              status: "decision_recorded",
              audit: [
                ...review.audit,
                {
                  id: `audit-${Date.now()}`,
                  timestamp: new Date().toLocaleTimeString(),
                  eventType: "decision.recorded",
                  detail: `Human decision captured: ${decisionLabels[decisionState]}`
                }
              ]
            }
          : review
      )
    );
    void recordDecision(activeReview.id, decisionState).catch(() => {
      // Sample and fallback reviews may not exist in the API store; keep the local decision memory intact.
    });
  }

  function appendAuditEvent(eventType: string, detail: string) {
    if (!activeReview) return;
    setReviews((current) =>
      current.map((review) =>
        review.id === activeReview.id
          ? {
              ...review,
              audit: [
                ...review.audit,
                {
                  id: `audit-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                  timestamp: new Date().toLocaleTimeString(),
                  eventType,
                  detail
                }
              ]
            }
          : review
      )
    );
  }

  async function runAction(label: string, action: () => Promise<ActionResult>) {
    setActiveAction(label);
    setActionFeedback({ tone: "neutral", message: `${label} running...` });
    const result = await action();
    if (result === "ok") {
      setActionFeedback({ tone: "good", message: `${label} completed. Review workflow trace for details.` });
    } else if (result === "fallback") {
      setActionFeedback({ tone: "warn", message: `${label} ran in fallback mode because API endpoints were unavailable.` });
    } else {
      setActionFeedback({ tone: "warn", message: `${label} skipped. Required packet context was missing.` });
    }
    setActiveAction(null);
  }

  async function startNewPacketDraft(): Promise<ActionResult> {
    setActiveView("workbench");
    appendAuditEvent("packet.new", "New packet draft opened and seeded with the next thesis candidate.");
    return "ok";
  }

  async function openExistingReview(): Promise<ActionResult> {
    setActiveView("memory");
    appendAuditEvent("review.open_existing", "Opened existing review list from core actions.");
    return "ok";
  }

  function syncReviewFromPacket(reviewId: string, packet: DecisionPacket) {
    setActivePacketData(packet);
    setReviews((current) =>
      current.map((review) =>
        review.id === reviewId
          ? {
              ...review,
              confidence: packet.confidence,
              status: packet.status,
              decisionState: packet.decisionState,
              followUpDate: packet.followUpDate,
              audit: packet.audit,
            }
          : review
      )
    );
  }

  function buildPacketShell(review: TradeReview): DecisionPacket {
    return {
      id: `pkt-${review.id}`,
      schemaVersion: "packet.v1",
      workflowVersion: "quant-agent.v1",
      title: review.title,
      thesis: review.thesis,
      ticker: review.ticker,
      assetClass: review.assetClass,
      timeHorizon: review.timeHorizon,
      intendedExpression: review.intendedExpression,
      status: review.status,
      decisionState: review.decisionState,
      confidence: review.confidence,
      trialCountImpact: review.trialCountImpact,
      followUpDate: review.followUpDate,
      createdAt: review.createdAt,
      claims: review.claims,
      strongestCritique: review.strongestCritique,
      disconfirmingTest: review.disconfirmingTest,
      historicalAnalogue: review.historicalAnalogue,
      validation: review.validation,
      tradeability: review.tradeability,
      sources: review.sources,
      audit: review.audit,
      marketSnapshot: null,
      technicals: null,
      sentiment: null,
      interMarket: null,
      fundamentals: null,
      backtestPlan: null,
      backtestResult: null,
      riskMonitor: null,
      portfolioContext: null,
      confidenceBreakdown: null,
      agentOutputs: null,
      coordinatorVersion: "coordinator.v1",
      providerInfo: null,
    };
  }

  async function ensurePacketForReview(review: TradeReview): Promise<{ reviewId: string; packetId: string; packet: DecisionPacket }> {
    const cachedPacketId = packetIdsByReviewId[review.id];
    if (cachedPacketId) {
      const existing = await getPacket(cachedPacketId);
      return { reviewId: review.id, packetId: cachedPacketId, packet: existing };
    }

    const packetId = `pkt-${review.id}`;
    try {
      const existing = await getPacket(packetId);
      setPacketIdsByReviewId((current) => ({ ...current, [review.id]: packetId }));
      return { reviewId: review.id, packetId, packet: existing };
    } catch {
      const created = await createPacket(buildPacketShell(review));
      setPacketIdsByReviewId((current) => ({ ...current, [review.id]: created.id }));
      return { reviewId: review.id, packetId: created.id, packet: created };
    }
  }

  async function refreshMarketMetrics(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("metrics.refresh.skipped", "No ticker available for metrics refresh.");
      return "skipped";
    }

    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await refreshPacketMetrics(packetId);
      syncReviewFromPacket(reviewId, packet);
      setLiveMarketData({
        snapshot: packet.marketSnapshot ?? null,
        technicals: packet.technicals ?? null,
        sentiment: packet.sentiment ?? null,
        ticker: activeReview.ticker,
        fetchedAt: new Date().toISOString(),
      });
      appendAuditEvent(
        "metrics.refresh",
        `Packet metrics refreshed for ${activeReview.ticker} via ${packetId}.`
      );
      return "ok";
    } catch {
      appendAuditEvent(
        "metrics.refresh.fallback",
        `Metrics refresh API unavailable for ${activeReview.ticker}; local workflow remains active.`
      );
      return "fallback";
    }
  }

  async function prepareBacktest(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("backtest.prepare.skipped", "Backtest preparation skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await preparePacketBacktest(packetId, {
        lookbackPeriod: 252,
        holdingPeriodDays: 10,
        riskConstraints: ["Max loss 8%", "Liquidity floor enforced"],
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("backtest.prepare", `Backtest plan prepared for ${activeReview.ticker} with status ${packet.backtestPlan?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("backtest.prepare.fallback", "Backtest preparation endpoint unavailable; packet flow remains in local mode.");
      return "fallback";
    }
  }

  async function viewRisks(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("view.risk.skipped", "Risk evaluation skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await evaluatePacketRisk(packetId, {
        activePositionSize: 250000,
        maxDrawdownThreshold: 0.12,
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("view.risk", `Risk evaluated for ${activeReview.ticker}: status ${packet.riskMonitor?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("view.risk.fallback", "Risk evaluation endpoint unavailable; local advisory workflow remains active.");
      return "fallback";
    }
  }

  async function runAgentSwarm(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("agents.run.skipped", "Agent swarm run skipped because no active review is selected.");
      return "skipped";
    }

    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await runPacketAgents(packetId, "hybrid");
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("agents.run", `Agent swarm completed for ${activeReview.ticker} using ${packet.providerInfo?.name ?? "unknown provider"}.`);
      return "ok";
    } catch {
      appendAuditEvent("agents.run.fallback", "Agent swarm endpoint unavailable; keeping local workflow state.");
      return "fallback";
    }
  }

  async function viewTechnicalsAndDeriveConfidence(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("view.technicals.skipped", "No ticker available for technicals inspection.");
      return "skipped";
    }

    try {
      const [sentimentResult, technicalsResult, snapshotResult] = await Promise.allSettled([
        getSentiment(activeReview.ticker),
        getMarketTechnicals(activeReview.ticker),
        getMarketSnapshot(activeReview.ticker),
      ]);
      const sentiment = sentimentResult.status === "fulfilled" ? sentimentResult.value : null;
      const technicals = technicalsResult.status === "fulfilled" ? technicalsResult.value : null;
      const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : null;
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await derivePacketConfidence(packetId, {
        technicalScore: technicals?.rsi !== null && technicals?.rsi !== undefined ? Math.round(technicals.rsi) : 66,
        sentimentScore: sentiment ? Math.round(sentiment.overallScore) : 50,
        blockers: sentiment?.sentiment === "bearish" ? ["Sentiment regime still bearish"] : [],
      });
      syncReviewFromPacket(reviewId, packet);
      setLiveMarketData({ snapshot, technicals, sentiment, ticker: activeReview.ticker, fetchedAt: new Date().toISOString() });
      appendAuditEvent("view.technicals", `Technicals reviewed and confidence derived for ${activeReview.ticker}: ${packet.confidence}%.`);
      return "ok";
    } catch {
      appendAuditEvent("view.technicals.fallback", "Technicals inspection endpoint unavailable; keeping deterministic local view.");
      return "fallback";
    }
  }

  async function recordOutcomeForDecision(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("outcome.recorded.skipped", "Outcome attribution skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await recordPacketOutcome(packetId, {
        outcome: "decision_recorded",
        outcome_date: new Date().toISOString().slice(0, 10),
        pnl: 0,
        notes: "Outcome placeholder captured from common action.",
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("outcome.recorded", `Outcome attribution recorded for ${activeReview.ticker}.`);
      return "ok";
    } catch {
      appendAuditEvent("outcome.recorded.fallback", "Outcome attribution endpoint unavailable; local decision memory retained.");
      return "fallback";
    }
  }

  return (
    <main className="min-h-screen px-5 py-5 text-ink">
      <div className="mx-auto max-w-[1540px] space-y-4">
        {/* Top bar with review context */}
        <TopBar review={activeReview} />
        
        {/* Action feedback */}
        {actionFeedback ? (
          <div className={cn("rounded-lg border px-3 py-2 text-sm", actionFeedback.tone === "good" ? "border-teal/30 bg-teal/10 text-teal" : actionFeedback.tone === "warn" ? "border-amber/30 bg-amber/10 text-amber" : "border-line bg-paper text-slate-300")}>
            {actionFeedback.message}
          </div>
        ) : null}

        {/* Main content area - 3 column layout for review workbench */}
        {activeView === "workbench" ? (
          <div className="grid gap-4 xl:grid-cols-3">
            {/* Left column: Thesis & Source Context */}
            <div className="space-y-4">
              <Panel className="p-5">
                <h2 className="text-sm font-semibold mb-3">Thesis</h2>
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Ticker</p>
                    <Badge tone="info">{activeReview.ticker}</Badge>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Title</p>
                    <p className="font-medium">{activeReview.title}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Thesis</p>
                    <p className="text-slate-200">{activeReview.thesis}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Time Horizon</p>
                    <p>{activeReview.timeHorizon}</p>
                  </div>
                </div>
              </Panel>
              
              {/* Compact market summary */}
              {liveMarketData?.snapshot ? (
                <Panel className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-xs font-semibold uppercase text-slate-400">Market Snapshot</h3>
                    <button
                      onClick={() => {
                        void runAction("Refresh Metrics", refreshMarketMetrics);
                      }}
                      disabled={Boolean(activeAction)}
                      className="text-xs text-teal hover:text-teal/70 disabled:opacity-50"
                    >
                      ↻
                    </button>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Price</span>
                      <span className="font-medium">${liveMarketData.snapshot.price?.toFixed(2) || "N/A"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Change</span>
                      <span className={liveMarketData.snapshot.priceChange24h >= 0 ? "text-teal" : "text-amber"}>
                        {liveMarketData.snapshot.priceChange24h >= 0 ? "+" : ""}{liveMarketData.snapshot.priceChange24h?.toFixed(2) || "N/A"}%
                      </span>
                    </div>
                  </div>
                  <Link href={`/markets/${activeReview.ticker}`} className="focus-ring mt-3 inline-flex items-center gap-1 text-xs font-medium text-teal">
                    Deep Analysis <ArrowRight className="h-3 w-3" />
                  </Link>
                </Panel>
              ) : null}
            </div>

            {/* Center column: Analysis & Evidence */}
            <div className="space-y-4">
              <Panel className="p-5">
                <h2 className="text-sm font-semibold mb-3">Analysis</h2>
                <div className="space-y-4 text-sm">
                  {activeReview.claims.length > 0 ? (
                    <div>
                      <p className="text-xs text-slate-400 mb-2">Key Claims</p>
                      <ul className="space-y-2">
                        {activeReview.claims.map((claim) => (
                          <li key={claim.id} className="p-2 rounded border border-line bg-paper/50 text-xs">
                            {claim.text}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  
                  {activeReview.strongestCritique ? (
                    <div className="rounded border border-amber/20 bg-amber/5 p-3">
                      <p className="text-xs text-amber mb-1 font-semibold">Strongest Critique</p>
                      <p className="text-xs text-slate-300">{activeReview.strongestCritique}</p>
                    </div>
                  ) : null}
                  
                  {activeReview.validation ? (
                    <div className="rounded border border-teal/20 bg-teal/5 p-3">
                      <p className="text-xs text-teal mb-1 font-semibold">Validation Gate</p>
                      <p className="text-xs text-slate-300">{activeReview.validation.hypothesis}</p>
                    </div>
                  ) : null}
                </div>
              </Panel>
              
              {/* Status timeline */}
              <Panel className="p-4">
                <h3 className="text-xs font-semibold mb-3 uppercase text-slate-400">Workflow Status</h3>
                <div className="space-y-2">
                  {Object.entries(statusLabels).map(([status, label]) => (
                    <div key={status} className={cn("text-xs px-2 py-1 rounded", activeReview.status === status ? "bg-teal/20 text-teal font-semibold" : "text-slate-400")}>
                      {label}
                    </div>
                  ))}
                </div>
              </Panel>
            </div>

            {/* Right column: Decision Controls & Risk */}
            <div className="space-y-4">
              {/* Sticky decision strip */}
              <Panel className="sticky bottom-0 p-4 border-2 border-teal/30 bg-teal/5 shadow-lg">
                <h2 className="text-sm font-semibold mb-3">Decision</h2>
                <div className="space-y-2">
                  {(Object.entries(decisionLabels) as Array<[DecisionState, string]>).map(([state, label]) => (
                    <button
                      key={state}
                      onClick={() => updateDecision(state)}
                      className={cn(
                        "focus-ring w-full rounded px-3 py-2 text-sm font-medium transition",
                        activeReview.decisionState === state
                          ? "bg-teal text-fog"
                          : "border border-line bg-paper hover:border-teal/40 text-slate-200"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <p className="mt-3 text-xs text-slate-400">Current: {activeReview.decisionState ? decisionLabels[activeReview.decisionState] : "Undecided"}</p>
              </Panel>

              {/* Confidence */}
              <Panel className="p-4">
                <h3 className="text-xs font-semibold mb-2 uppercase text-slate-400">Confidence</h3>
                <p className="text-2xl font-bold text-teal">{activeReview.confidence}%</p>
              </Panel>

              {/* Risk monitor */}
              {activePacketData?.riskMonitor ? (
                <Panel className="p-4">
                  <h3 className="text-xs font-semibold mb-2 uppercase text-slate-400">Risk Status</h3>
                  <p className="text-sm text-slate-200">{activePacketData.riskMonitor.status}</p>
                </Panel>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Memory view - coming in Phase D */}
        {/* Calibration view - coming in Phase D */}
        {/* Sources view - coming in Phase D */}
      </div>
    </main>
  );
}

function TopBar({ review }: { review: TradeReview }) {
  return (
    <Panel className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-teal">Pre-trade adversarial review</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-normal text-ink">{review.title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-5 text-slate-400">
          This is the active idea under review, with its current decision state and workflow version shown before any trade action is taken.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href={`/markets/${encodeURIComponent(review.ticker.toUpperCase())}`}
          className="focus-ring inline-flex items-center rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-teal hover:border-teal/60"
        >
          Open {review.ticker.toUpperCase()} intelligence
        </Link>
        <Badge tone="info">{review.schemaVersion}</Badge>
        <Badge tone="neutral">{review.workflowVersion}</Badge>
        <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ? decisionLabels[review.decisionState] : "Decision pending"}</Badge>
      </div>
    </Panel>
  );
}

function mergeReviews(apiReviews: TradeReview[], localReviews: TradeReview[]): TradeReview[] {
  const apiMap = new Map(apiReviews.map((r) => [r.id, r]));
  const merged = [...apiReviews];
  for (const local of localReviews) {
    if (!apiMap.has(local.id)) {
      merged.push(local);
    }
  }
  return merged;
}
