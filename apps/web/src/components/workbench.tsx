"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { Activity, AlertTriangle, BarChart3, BookOpen, CheckCircle2, ClipboardCheck, Database, FileSearch, History, ShieldCheck, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ApiUnavailableError,
  createPacket,
  createReview,
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
  retrievePacketContext,
  runPacketAgents,
  runPacketBacktest,
  updatePacketPortfolio,
} from "@/lib/api";
import { sampleReviews } from "@/lib/sample-data";
import { generateLocalReview, thesisCandidates } from "@/lib/review-generator";
import type { Claim, DashboardMetrics, DecisionPacket, DecisionState, MarketSnapshot, ReviewStatus, SentimentData, SourcePointer, TechnicalIndicators, ThesisInput, TradeReview } from "@/lib/types";
import { Badge, Panel, SectionTitle, cn } from "./ui";
import { CommonActionsBar } from "./common-actions";

type NavView = "workbench" | "memory" | "calibration" | "sources";
type ActionResult = "ok" | "fallback" | "skipped";

type LiveMarketData = {
  snapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  ticker: string;
  fetchedAt: string;
};

const thesisSchema = z.object({
  thesis: z.string().min(16, "Enter a decision-relevant thesis."),
  ticker: z.string().min(1, "Add a ticker, basket, or instrument."),
  assetClass: z.string().min(1, "Add an asset class."),
  timeHorizon: z.string().min(1, "Add a time horizon."),
  intendedExpression: z.string().min(1, "Add the intended expression."),
  sourcePointer: z.string().optional().default("")
});

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

export function Workbench() {
  const [reviews, setReviews] = useState<TradeReview[]>(sampleReviews);
  const [packetIdsByReviewId, setPacketIdsByReviewId] = useState<Record<string, string>>({});
  const [activeId, setActiveId] = useState(sampleReviews[0]?.id ?? "");
  const [activeView, setActiveView] = useState<NavView>("workbench");
  const [generationMode, setGenerationMode] = useState<"api" | "fallback" | "idle">("idle");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [seedRequestToken, setSeedRequestToken] = useState(0);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ tone: "neutral" | "good" | "warn"; message: string } | null>(null);
  const [liveMarketData, setLiveMarketData] = useState<LiveMarketData | null>(null);
  const [activePacketData, setActivePacketData] = useState<DecisionPacket | null>(null);
  const activeReview = reviews.find((review) => review.id === activeId) ?? reviews[0];
  const metrics = useMemo(() => computeDashboardMetrics(reviews), [reviews]);
  const decisionChartData = useMemo(() => buildDecisionChartData(reviews), [reviews]);

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

  async function addReview(input: ThesisInput) {
    setGenerationError(null);
    try {
      const review = await createReview(input);
      setReviews((current) => [review, ...current]);
      setActiveId(review.id);
      setActiveView("workbench");
      setGenerationMode("api");
    } catch (error) {
      const review = generateLocalReview(input, metrics.activeTrialCount);
      review.audit = [
        ...review.audit,
        {
          id: `audit-fallback-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          eventType: "api.fallback",
          detail: "FastAPI review endpoint unavailable; deterministic local generator used."
        }
      ];
      setReviews((current) => [review, ...current]);
      setActiveId(review.id);
      setActiveView("workbench");
      setGenerationMode("fallback");
      setGenerationError(error instanceof ApiUnavailableError ? null : "API review generation failed, so Ambrosia generated this review locally.");
    }
  }

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
    setSeedRequestToken((current) => current + 1);
    appendAuditEvent("packet.new", "New packet draft opened and seeded with the next thesis candidate.");
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    return "ok";
  }

  async function ingestManualAlert(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("event_intake.manual.skipped", "Manual alert intake skipped because no active review is selected.");
      return "skipped";
    }

    appendAuditEvent("event_intake.manual", `Manual alert intake opened from common actions for ${activeReview.ticker}.`);
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

  async function inspectSentiment(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("view.sentiment.skipped", "No ticker available for sentiment inspection.");
      return "skipped";
    }

    try {
      const sentiment = await getSentiment(activeReview.ticker);
      setLiveMarketData((prev) => ({
        snapshot: prev?.ticker === activeReview.ticker ? (prev.snapshot ?? null) : null,
        technicals: prev?.ticker === activeReview.ticker ? (prev.technicals ?? null) : null,
        sentiment,
        ticker: activeReview.ticker,
        fetchedAt: new Date().toISOString(),
      }));
      appendAuditEvent(
        "view.sentiment",
        `Sentiment inspected for ${activeReview.ticker}: ${sentiment.sentiment} (${sentiment.overallScore}) from ${sentiment.sources.join(", ")}.`
      );
      return "ok";
    } catch {
      appendAuditEvent(
        "view.sentiment.fallback",
        `Sentiment endpoint unavailable for ${activeReview.ticker}; deterministic review flow remains active.`
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

  async function runBacktest(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("backtest.run.skipped", "Backtest run skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await runPacketBacktest(packetId, { forceRun: false });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("backtest.run", `Backtest run completed for ${activeReview.ticker} with validity ${packet.backtestResult?.validityScore ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("backtest.run.fallback", "Backtest run endpoint unavailable; no external backtest executed.");
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

  async function compareMarkets(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("view.inter_market.skipped", "Inter-market comparison skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const retrieval = await retrievePacketContext(packetId, `${activeReview.ticker} ${activeReview.thesis}`, 4);
      const packet = await runPacketAgents(packetId, "deterministic");
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent(
        "view.inter_market",
        `Hybrid retrieval returned ${retrieval.results.length} hits; specialist coordinator completed for ${activeReview.ticker}.`
      );
      return "ok";
    } catch {
      appendAuditEvent("view.inter_market.fallback", "Coordinator endpoint unavailable; inter-market comparison stayed local.");
      return "fallback";
    }
  }

  async function setFollowUpWithPortfolioUpdate(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("follow_up.set.skipped", "Follow-up update skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await updatePacketPortfolio(packetId, {
        grossExposure: 0.82,
        netExposure: 0.19,
        longExposure: 0.51,
        shortExposure: 0.32,
        concentrationBySector: { Technology: 0.34, Health: 0.16 },
        concentrationByFactor: { Momentum: 0.22, Quality: 0.18 },
        relatedPositions: [activeReview.ticker],
        factorOverlap: ["Growth", "Beta"],
        riskBudgetRemaining: 0.31,
        sizingConstraints: ["Advisory mode only", "No live broker execution"],
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("follow_up.set", `Follow-up and portfolio context updated for ${activeReview.ticker}.`);
      return "ok";
    } catch {
      appendAuditEvent("follow_up.set.fallback", `Follow-up reminder set for ${activeReview.followUpDate} (local mode).`);
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

  function exportActiveReview() {
    if (!activeReview) return;
    const payload = JSON.stringify(activeReview, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${activeReview.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    appendAuditEvent("report.export", `Exported structured review artifact for ${activeReview.id}.`);
  }

  return (
    <main className="min-h-screen px-5 py-5 text-ink">
      <div className="mx-auto grid max-w-[1540px] grid-cols-[260px_minmax(0,1fr)_360px] gap-4 max-xl:grid-cols-[220px_minmax(0,1fr)] max-lg:grid-cols-1">
        <LeftRail reviews={reviews} activeId={activeReview.id} activeView={activeView} onSelect={(reviewId) => { setActiveId(reviewId); setActiveView("workbench"); }} onViewChange={setActiveView} />
        <div className="space-y-4">
          <TopBar review={activeReview} />
          {activeView === "workbench" ? (
            <>
              {actionFeedback ? (
                <div className={cn("rounded-lg border px-3 py-2 text-sm", actionFeedback.tone === "good" ? "border-teal/30 bg-teal/10 text-teal" : actionFeedback.tone === "warn" ? "border-amber/30 bg-amber/10 text-amber" : "border-line bg-paper text-slate-300")}>
                  {actionFeedback.message}
                </div>
              ) : null}
              <CommonActionsBar
                onNewPacket={() => {
                  void runAction("New Packet", startNewPacketDraft);
                }}
                onGenerateThesis={() => setSeedRequestToken((current) => current + 1)}
                onIngestAlert={() => {
                  void runAction("Ingest Alert", ingestManualAlert);
                }}
                onRefreshMetrics={() => {
                  void runAction("Refresh Metrics", refreshMarketMetrics);
                }}
                onViewTechnicals={() => {
                  void runAction("View Technicals", viewTechnicalsAndDeriveConfidence);
                }}
                onViewSentiment={() => {
                  void runAction("View Sentiment", inspectSentiment);
                }}
                onCompareMarkets={() => {
                  void runAction("Compare Markets", compareMarkets);
                }}
                onPrepareBacktest={() => {
                  void runAction("Prepare Backtest", prepareBacktest);
                }}
                onRunBacktest={() => {
                  void runAction("Run Backtest", runBacktest);
                }}
                onRecordDecision={() => {
                  updateDecision(activeReview.decisionState ?? "watch");
                  void runAction("Record Decision", recordOutcomeForDecision);
                }}
                onSetFollowUp={() => {
                  void runAction("Set Follow-Up", setFollowUpWithPortfolioUpdate);
                }}
                onViewRisks={() => {
                  void runAction("View Risks", viewRisks);
                }}
                onExportReport={exportActiveReview}
                disabled={Boolean(activeAction)}
              />
              <MarketIntelligencePanel data={liveMarketData} ticker={activeReview.ticker} />
              <PacketExecutionPanel packet={activePacketData} />
              <ThesisIntake onSubmit={addReview} generationMode={generationMode} generationError={generationError} seedRequestToken={seedRequestToken} />
              <StatusTimeline status={activeReview.status} />
              <ReviewArtifact review={activeReview} />
            </>
          ) : null}
          {activeView === "memory" ? <DecisionMemoryPanel reviews={reviews} onSelectReview={(reviewId) => { setActiveId(reviewId); setActiveView("workbench"); }} /> : null}
          {activeView === "calibration" ? <CalibrationPanel metrics={metrics} chartData={decisionChartData} reviews={reviews} /> : null}
          {activeView === "sources" ? <SourceLibraryPanel sources={collectSources(reviews)} onSelectReview={(reviewId) => { setActiveId(reviewId); setActiveView("workbench"); }} /> : null}
        </div>
        <aside className="space-y-4 max-xl:col-span-2 max-lg:col-span-1">
          <EvidencePanel review={activeReview} />
          <DecisionStrip review={activeReview} onDecision={updateDecision} />
          <DashboardPanel metrics={metrics} chartData={decisionChartData} />
          <AuditPanel review={activeReview} />
        </aside>
      </div>
    </main>
  );
}

function LeftRail({ reviews, activeId, activeView, onSelect, onViewChange }: { reviews: TradeReview[]; activeId: string; activeView: NavView; onSelect: (id: string) => void; onViewChange: (view: NavView) => void }) {
  const navItems: Array<[React.ElementType, string, NavView]> = [
    [ClipboardCheck, "Review workbench", "workbench"],
    [History, "Decision memory", "memory"],
    [BarChart3, "Calibration", "calibration"],
    [Database, "Source library", "sources"]
  ];

  return (
    <Panel className="h-[calc(100vh-2.5rem)] overflow-hidden p-3 max-lg:h-auto">
      <div className="flex items-center gap-2 px-2 py-2">
        <div className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-lg border border-line bg-paper p-1">
          <Image src="/logo.png" alt="Ambrosia" width={44} height={44} className="h-full w-full object-contain" priority />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold">Ambrosia</p>
          <p className="text-xs text-slate-500">Trade Review</p>
        </div>
      </div>
      <nav className="mt-4 grid gap-1 text-sm">
        {navItems.map(([Icon, label, view]) => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            className={cn(
              "focus-ring flex items-center gap-2 rounded-md px-2 py-2 text-left text-slate-200 hover:bg-line",
              activeView === view ? "bg-teal/10 font-semibold text-teal" : ""
            )}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>
      <div className="mt-5 border-t border-line pt-4">
        <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Recent reviews</p>
        <div className="mt-2 space-y-2 overflow-auto pr-1 max-lg:max-h-72 lg:max-h-[calc(100vh-20rem)]">
          {reviews.map((review) => (
            <button
              key={review.id}
              onClick={() => onSelect(review.id)}
              className={cn(
                "focus-ring w-full rounded-lg border p-3 text-left transition",
                review.id === activeId ? "border-teal bg-teal/10" : "border-line bg-paper hover:border-teal/40"
              )}
            >
              <p className="line-clamp-2 text-sm font-medium">{review.title}</p>
              <p className="mt-1 text-xs text-slate-500">{review.assetClass} · {review.timeHorizon}</p>
            </button>
          ))}
        </div>
      </div>
    </Panel>
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
      <div className="flex flex-wrap gap-2">
        <Badge tone="info">{review.schemaVersion}</Badge>
        <Badge tone="neutral">{review.workflowVersion}</Badge>
        <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ? decisionLabels[review.decisionState] : "Decision pending"}</Badge>
      </div>
    </Panel>
  );
}

function ThesisIntake({ onSubmit, generationMode, generationError, seedRequestToken }: { onSubmit: (input: ThesisInput) => Promise<void>; generationMode: "api" | "fallback" | "idle"; generationError: string | null; seedRequestToken: number }) {
  const [seedIndex, setSeedIndex] = useState(0);
  const form = useForm<ThesisInput>({
    resolver: zodResolver(thesisSchema),
    defaultValues: {
      thesis: "",
      ticker: "",
      assetClass: "",
      timeHorizon: "",
      intendedExpression: "",
      sourcePointer: ""
    }
  });

  function generateThesisCandidate() {
    const candidate = thesisCandidates[seedIndex % thesisCandidates.length];
    form.setValue("thesis", candidate.thesis, { shouldDirty: true, shouldValidate: true });
    form.setValue("ticker", candidate.ticker, { shouldDirty: true, shouldValidate: true });
    form.setValue("assetClass", candidate.assetClass, { shouldDirty: true, shouldValidate: true });
    form.setValue("timeHorizon", candidate.timeHorizon, { shouldDirty: true, shouldValidate: true });
    form.setValue("intendedExpression", candidate.intendedExpression, { shouldDirty: true, shouldValidate: true });
    form.setValue("sourcePointer", candidate.sourcePointer, { shouldDirty: true, shouldValidate: true });
    form.clearErrors();
    setSeedIndex((current) => current + 1);
  }

  useEffect(() => {
    if (seedRequestToken > 0) {
      generateThesisCandidate();
    }
    // Only react to explicit seed requests from the parent common actions bar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedRequestToken]);

  return (
    <Panel className="p-4">
      <div className="flex items-center justify-between gap-3">
        <SectionTitle eyebrow="New review" title="Run a thesis through Ambrosia" />
        <Badge tone={generationMode === "api" ? "good" : generationMode === "fallback" ? "warn" : "neutral"}>{generationMode === "api" ? "API-backed" : generationMode === "fallback" ? "Local fallback" : "Manual thesis intake first"}</Badge>
      </div>
      <p className="mt-2 text-sm leading-5 text-slate-400">
        Enter a market idea here and Ambrosia turns it into a structured review with critique, validation checks, sources, and a decision record.
      </p>
      <form
        className="mt-4 grid gap-3"
        onSubmit={form.handleSubmit(async (value) => {
          await onSubmit(value);
          form.reset();
        })}
      >
        {generationError ? <p className="rounded-md border border-amber/30 bg-amber/10 p-3 text-xs text-amber">{generationError}</p> : null}
        <textarea
          className="focus-ring min-h-24 resize-y rounded-lg border border-line bg-paper p-3 text-sm"
          placeholder="Example: BTC miners may be mispriced relative to spot Bitcoin after a breakout..."
          {...form.register("thesis")}
        />
        {form.formState.errors.thesis?.message ? <FieldError message={form.formState.errors.thesis.message} /> : null}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Input label="Ticker / basket" placeholder="BTC miners" error={form.formState.errors.ticker?.message} {...form.register("ticker")} />
          <Input label="Asset class" placeholder="Equities" error={form.formState.errors.assetClass?.message} {...form.register("assetClass")} />
          <Input label="Time horizon" placeholder="1-4 weeks" error={form.formState.errors.timeHorizon?.message} {...form.register("timeHorizon")} />
          <Input label="Expression" placeholder="Long basket" error={form.formState.errors.intendedExpression?.message} {...form.register("intendedExpression")} />
          <Input label="Source pointer" placeholder="Optional URL/note" {...form.register("sourcePointer")} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-xs text-slate-500">The static MVP generator preserves artifact shape, refusal behavior, and audit events before model credentials are connected. Generated thesis candidates are review inputs, not recommendations.</p>
          <div className="flex flex-wrap gap-2">
            <button
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink hover:border-teal"
              type="button"
              onClick={generateThesisCandidate}
            >
              <Sparkles size={16} />
              Generate thesis
            </button>
            <button className="focus-ring rounded-md bg-teal px-4 py-2 text-sm font-semibold text-fog hover:bg-teal/80 disabled:cursor-not-allowed disabled:opacity-60" type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Generating..." : "Generate review"}
            </button>
          </div>
        </div>
      </form>
    </Panel>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const { label, error, ...inputProps } = props;
  return (
    <label className="grid min-w-0 gap-1 text-xs font-medium text-slate-300">
      <span className="truncate">{label}</span>
      <input className="focus-ring min-w-0 rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink" {...inputProps} />
      {error ? <FieldError message={error} /> : null}
    </label>
  );
}

function FieldError({ message }: { message: string }) {
  return <span className="text-xs font-medium text-coral">{message}</span>;
}

function StatusTimeline({ status }: { status: ReviewStatus }) {
  const steps = Object.keys(statusLabels) as ReviewStatus[];
  const activeIndex = steps.indexOf(status);
  return (
    <Panel className="p-4">
      <p className="mb-3 text-sm leading-5 text-slate-400">
        This timeline shows where the idea is in the review process, from intake through validation and final decision capture.
      </p>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-7">
        {steps.map((step, index) => {
          const complete = index <= activeIndex;
          return (
            <div key={step} className="flex items-center gap-2 rounded-md border border-line bg-paper px-2 py-2">
              {complete ? <CheckCircle2 className="text-teal" size={16} /> : <Activity className="text-slate-500" size={16} />}
              <span className={cn("text-xs font-medium", complete ? "text-ink" : "text-slate-500")}>{statusLabels[step]}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ReviewArtifact({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-5">
      <div className="grid gap-5">
        <div className="grid gap-3 border-b border-line pb-4">
          <SectionTitle eyebrow="Structured thesis" title={review.thesis} />
          <p className="text-sm leading-5 text-slate-400">
            This module turns the original idea into a decision packet: what is being considered, what could break it, and what must be checked first.
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge>{review.ticker}</Badge>
            <Badge>{review.assetClass}</Badge>
            <Badge>{review.timeHorizon}</Badge>
            <Badge tone="info">Trial +{review.trialCountImpact}</Badge>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <ArtifactBlock icon={<AlertTriangle size={18} />} title="Strongest critique" body={review.strongestCritique} tone="bad" />
          <ArtifactBlock icon={<FileSearch size={18} />} title="Disconfirming test" body={review.disconfirmingTest} tone="warn" />
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-lg border border-line bg-paper p-4">
            <div className="flex items-center gap-2">
              <BookOpen className="text-violet" size={18} />
              <h3 className="font-semibold">Historical analogue</h3>
            </div>
            <p className="mt-3 font-medium">{review.historicalAnalogue.title}</p>
            <dl className="mt-3 grid gap-2 text-sm text-slate-300">
              <div><dt className="font-semibold text-ink">Similarity</dt><dd>{review.historicalAnalogue.similarity}</dd></div>
              <div><dt className="font-semibold text-ink">Differences</dt><dd>{review.historicalAnalogue.differences}</dd></div>
              <div><dt className="font-semibold text-ink">Resolution</dt><dd>{review.historicalAnalogue.resolution}</dd></div>
            </dl>
          </div>
          <div className="rounded-lg border border-line bg-paper p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="text-teal" size={18} />
                <h3 className="font-semibold">Validation specification</h3>
              </div>
              <Badge tone={review.validation.status === "refused" ? "bad" : "good"}>{review.validation.status}</Badge>
            </div>
            <p className="mt-3 text-sm text-slate-200">{review.validation.protocol}</p>
            {review.validation.refusalReason ? <p className="mt-3 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-coral">{review.validation.refusalReason}</p> : null}
            <ul className="mt-3 grid gap-2 text-sm text-slate-300">
              {review.validation.dataRequirements.map((item) => <li key={item}>- {item}</li>)}
            </ul>
          </div>
        </div>

        <div>
          <h3 className="font-semibold">Claims and assumptions</h3>
          <p className="mt-2 text-sm leading-5 text-slate-400">
            These are the building blocks of the thesis, separated into evidence, assumptions, unknowns, and contradictions.
          </p>
          <div className="mt-3 grid gap-3">
            {review.claims.map((claim) => <ClaimCard key={claim.id} claim={claim} />)}
          </div>
        </div>

        <div>
          <h3 className="font-semibold">Tradeability checklist</h3>
          <p className="mt-2 text-sm leading-5 text-slate-400">
            This checklist asks whether the idea can actually be traded responsibly, including liquidity, costs, expression, and missing data.
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {review.tradeability.map((question) => (
              <div key={`${question.topic}-${question.question}`} className="rounded-lg border border-line bg-paper p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">{question.topic}</p>
                  <Badge tone={question.severity === "high" ? "bad" : question.severity === "medium" ? "warn" : "neutral"}>{question.severity}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-300">{question.question}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function ArtifactBlock({ icon, title, body, tone }: { icon: React.ReactNode; title: string; body: string; tone: "bad" | "warn" }) {
  return (
    <div className={cn("rounded-lg border p-4", tone === "bad" ? "border-coral/30 bg-coral/10" : "border-amber/30 bg-amber/10")}>
      <div className="flex items-center gap-2 font-semibold">{icon}{title}</div>
      <p className="mt-3 text-sm leading-6 text-slate-200">{body}</p>
    </div>
  );
}

function ClaimCard({ claim }: { claim: Claim }) {
  const tone = claim.kind === "sourced" ? "good" : claim.kind === "contradiction" ? "bad" : claim.kind === "unknown" ? "warn" : "neutral";
  return (
    <div className="rounded-lg border border-line bg-paper p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone={tone}>{claim.kind}</Badge>
        <span className="text-xs text-slate-500">Confidence {claim.confidence}%</span>
      </div>
      <p className="mt-2 text-sm text-slate-200">{claim.text}</p>
      {claim.evidence ? <p className="mt-2 text-xs text-slate-500">Evidence: {claim.evidence}</p> : null}
    </div>
  );
}

function EvidencePanel({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-4">
      <SectionTitle eyebrow="Evidence" title="Source pointers" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module lists the notes, prior reviews, or source references used to ground the current thesis.
      </p>
      <div className="mt-3 space-y-3">
        {review.sources.map((source) => (
          <div key={source.id} className="rounded-lg border border-line bg-paper p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{source.title}</p>
                <p className="mt-1 text-xs text-slate-500">{source.sourceType} · {source.timestamp}</p>
              </div>
              <Badge tone={source.permission === "user_owned" ? "good" : "warn"}>{source.permission}</Badge>
            </div>
            <div className="mt-3 h-2 rounded-full bg-line">
              <div className="h-2 rounded-full bg-teal" style={{ width: `${Math.round(source.relevance * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function DecisionStrip({ review, onDecision }: { review: TradeReview; onDecision: (decision: DecisionState) => void }) {
  return (
    <Panel className="p-4">
      <SectionTitle eyebrow="Human authority" title="Decision state" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module records the human choice: pursue, watch, reject, or ask for more data. Ambrosia supports the decision; it does not make it for you.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {(Object.keys(decisionLabels) as DecisionState[]).map((decision) => (
          <button
            key={decision}
            onClick={() => onDecision(decision)}
            className={cn(
              "focus-ring rounded-md border px-3 py-2 text-sm font-semibold",
              review.decisionState === decision ? "border-pine bg-teal text-fog" : "border-line bg-paper text-ink hover:border-teal"
            )}
          >
            {decisionLabels[decision]}
          </button>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center text-sm">
        <Metric label="Confidence" value={`${review.confidence}%`} />
        <Metric label="Trial" value={`+${review.trialCountImpact}`} />
        <Metric label="Follow-up" value={review.followUpDate.slice(5)} />
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-paper p-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  );
}

function DashboardPanel({ metrics, chartData }: { metrics: DashboardMetrics; chartData: Array<{ bucket: string; count: number }> }) {
  return (
    <Panel className="p-4">
      <SectionTitle eyebrow="Decision memory" title="Calibration snapshot" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module summarizes how many ideas have been reviewed, how often they were deferred or rejected, and the average confidence level.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Reviews" value={metrics.reviewsCreated} />
        <Metric label="Reject/defer" value={metrics.rejectedOrDeferred} />
        <Metric label="Follow-ups" value={metrics.followUpsRecorded} />
        <Metric label="Avg confidence" value={`${metrics.averageConfidence}%`} />
      </div>
      <div className="mt-4 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#138c7e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

function DecisionMemoryPanel({ reviews, onSelectReview }: { reviews: TradeReview[]; onSelectReview: (reviewId: string) => void }) {
  return (
    <Panel className="p-5">
      <SectionTitle eyebrow="Decision memory" title="Captured review decisions" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module keeps a record of prior reviews so past decisions can be revisited instead of disappearing after the meeting.
      </p>
      <div className="mt-4 overflow-hidden rounded-lg border border-line bg-paper">
        <div className="grid grid-cols-[1.4fr_0.7fr_0.7fr_0.5fr] border-b border-line bg-fog px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 max-md:hidden">
          <span>Review</span>
          <span>Decision</span>
          <span>Follow-up</span>
          <span>Trial</span>
        </div>
        {reviews.map((review) => (
          <button key={review.id} onClick={() => onSelectReview(review.id)} className="focus-ring grid w-full grid-cols-[1.4fr_0.7fr_0.7fr_0.5fr] gap-3 border-b border-line px-3 py-3 text-left text-sm last:border-b-0 hover:bg-teal/5 max-md:grid-cols-1">
            <span>
              <span className="block font-medium text-ink">{review.title}</span>
              <span className="text-xs text-slate-500">{review.assetClass} · {review.timeHorizon}</span>
            </span>
            <span>{review.decisionState ? <Badge tone={review.decisionState === "reject" || review.decisionState === "needs_more_data" ? "warn" : "good"}>{decisionLabels[review.decisionState]}</Badge> : <Badge tone="neutral">Pending</Badge>}</span>
            <span className="text-slate-300">{review.followUpDate}</span>
            <span className="font-semibold text-violet">+{review.trialCountImpact}</span>
          </button>
        ))}
      </div>
    </Panel>
  );
}

function CalibrationPanel({ metrics, chartData, reviews }: { metrics: DashboardMetrics; chartData: Array<{ bucket: string; count: number }>; reviews: TradeReview[] }) {
  return (
    <Panel className="p-5">
      <SectionTitle eyebrow="Calibration" title="Decision discipline dashboard" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module helps compare decisions over time, showing whether the workflow is becoming more disciplined or simply producing more activity.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Reviews" value={metrics.reviewsCreated} />
        <Metric label="Reject/defer" value={metrics.rejectedOrDeferred} />
        <Metric label="Follow-ups" value={metrics.followUpsRecorded} />
        <Metric label="Avg confidence" value={`${metrics.averageConfidence}%`} />
        <Metric label="Trial count" value={metrics.activeTrialCount} />
      </div>
      <div className="mt-5 h-64 rounded-lg border border-line bg-paper p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#138c7e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {reviews.slice(0, 4).map((review) => (
          <div key={review.id} className="rounded-lg border border-line bg-paper p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold">{review.title}</p>
              <Badge tone="info">{review.confidence}%</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">Outcome memory: {review.decisionState ? decisionLabels[review.decisionState] : "pending decision"}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SourceLibraryPanel({ sources, onSelectReview }: { sources: Array<SourcePointer & { reviewId: string; reviewTitle: string }>; onSelectReview: (reviewId: string) => void }) {
  return (
    <Panel className="p-5">
      <SectionTitle eyebrow="Source library" title="User-owned evidence and source pointers" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module gathers the evidence library behind the reviews, including user-owned notes and pointer-only references.
      </p>
      <div className="mt-4 grid gap-3">
        {sources.map((source) => (
          <button key={`${source.reviewId}-${source.id}`} onClick={() => onSelectReview(source.reviewId)} className="focus-ring rounded-lg border border-line bg-paper p-4 text-left hover:border-teal/50">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{source.title}</p>
                <p className="mt-1 text-xs text-slate-500">{source.sourceType} · {source.timestamp} · from {source.reviewTitle}</p>
              </div>
              <Badge tone={source.permission === "user_owned" ? "good" : "warn"}>{source.permission}</Badge>
            </div>
            <div className="mt-3 h-2 rounded-full bg-line">
              <div className="h-2 rounded-full bg-teal" style={{ width: `${Math.round(source.relevance * 100)}%` }} />
            </div>
          </button>
        ))}
      </div>
    </Panel>
  );
}

function AuditPanel({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-4">
      <SectionTitle eyebrow="Audit" title="Workflow trace" />
      <p className="mt-2 text-sm leading-5 text-slate-400">
        This module shows what Ambrosia did, when it did it, and why, so the workflow can be checked after the fact.
      </p>
      <div className="mt-3 space-y-2">
        {review.audit.map((event) => (
          <div key={event.id} className="rounded-md border border-line bg-paper p-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{event.eventType}</span>
              <span className="text-xs text-slate-500">{event.timestamp}</span>
            </div>
            <p className="mt-1 text-xs text-slate-300">{event.detail}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function computeDashboardMetrics(reviews: TradeReview[]): DashboardMetrics {
  const rejectedOrDeferred = reviews.filter((review) => review.decisionState === "reject" || review.decisionState === "needs_more_data").length;
  const confidenceTotal = reviews.reduce((total, review) => total + review.confidence, 0);
  return {
    reviewsCreated: reviews.length,
    rejectedOrDeferred,
    followUpsRecorded: reviews.filter((review) => review.audit.some((event) => event.eventType === "outcome.recorded")).length,
    averageConfidence: reviews.length ? Math.round(confidenceTotal / reviews.length) : 0,
    activeTrialCount: reviews.reduce((total, review) => total + review.trialCountImpact, 0)
  };
}

function buildDecisionChartData(reviews: TradeReview[]) {
  const counts: Record<string, number> = {
    Reject: 0,
    "Needs data": 0,
    Watch: 0,
    Pursue: 0,
    Pending: 0
  };
  for (const review of reviews) {
    if (review.decisionState === "reject") counts.Reject += 1;
    else if (review.decisionState === "needs_more_data") counts["Needs data"] += 1;
    else if (review.decisionState === "watch") counts.Watch += 1;
    else if (review.decisionState === "pursue") counts.Pursue += 1;
    else counts.Pending += 1;
  }
  return Object.entries(counts).map(([bucket, count]) => ({ bucket, count }));
}

function collectSources(reviews: TradeReview[]): Array<SourcePointer & { reviewId: string; reviewTitle: string }> {
  return reviews.flatMap((review) => review.sources.map((source) => ({ ...source, reviewId: review.id, reviewTitle: review.title })));
}

function mergeReviews(primary: TradeReview[], secondary: TradeReview[]): TradeReview[] {
  const seen = new Set<string>();
  const merged: TradeReview[] = [];
  for (const review of [...primary, ...secondary]) {
    if (!seen.has(review.id)) {
      seen.add(review.id);
      merged.push(review);
    }
  }
  return merged;
}

function fmtVol(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

function rsiTone(rsi: number | null): "up" | "down" | undefined {
  if (rsi === null) return undefined;
  if (rsi > 70) return "down";
  if (rsi < 30) return "up";
  return undefined;
}

function MIMetric({ label, value, tone, small }: { label: string; value: string; tone?: "up" | "down"; small?: boolean }) {
  return (
    <div className="rounded-md border border-line bg-paper p-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={cn("mt-1 truncate font-semibold", small ? "text-xs" : "text-sm", tone === "up" ? "text-teal" : tone === "down" ? "text-coral" : "text-ink")}>
        {value}
      </p>
    </div>
  );
}

function MarketIntelligencePanel({ data, ticker }: { data: LiveMarketData | null; ticker: string }) {
  if (!data) {
    return (
      <Panel className="p-5">
        <SectionTitle eyebrow="Market intelligence" title="Price · technicals · sentiment" />
        <p className="mt-3 text-sm leading-6 text-slate-300">
          Ambrosia connects to market data adapters to fetch price, volume, technical indicators, and news sentiment for the instrument under review. Every metric shows its data source, timestamp, and mode — live, fallback, or demo. No metric is invented or hidden.
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Click <span className="font-semibold text-teal">Refresh Metrics</span> to load a full snapshot for <span className="font-semibold text-ink">{ticker || "this instrument"}</span>, or use <span className="font-semibold text-teal">View Technicals</span> or <span className="font-semibold text-teal">View Sentiment</span> for individual modules.
        </p>
      </Panel>
    );
  }

  const confidence = data.snapshot?.dataSourceConfidence ?? (data.technicals?.dataQuality === "verified" ? "live" : "fallback");
  const confTone: "good" | "warn" | "neutral" = confidence === "live" ? "good" : confidence === "fallback" ? "warn" : "neutral";
  const fetchedTime = new Date(data.fetchedAt).toLocaleTimeString();

  return (
    <Panel className="space-y-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionTitle eyebrow="Market intelligence" title={data.ticker} />
        <div className="flex items-center gap-2">
          <Badge tone={confTone}>{confidence}</Badge>
          <span className="text-xs text-slate-500">fetched {fetchedTime}</span>
        </div>
      </div>

      {data.snapshot && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Market snapshot</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            Price and volume from market data adapter. Source: <span className="text-slate-300">{data.snapshot.dataSource}</span>. Ambrosia labels stale or proxy data explicitly.
          </p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            <MIMetric label="Price" value={`$${data.snapshot.price.toFixed(2)}`} />
            <MIMetric label="24h change" value={`${data.snapshot.priceChange24h >= 0 ? "+" : ""}${data.snapshot.priceChange24h.toFixed(2)}%`} tone={data.snapshot.priceChange24h >= 0 ? "up" : "down"} />
            <MIMetric label="Volume" value={fmtVol(data.snapshot.volume24h)} />
            <MIMetric label="Data source" value={data.snapshot.dataSource.replace("Deterministic fallback", "Fallback")} small />
          </div>
        </section>
      )}

      {data.technicals && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Technical indicators</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            Computed from price history — not model opinion. RSI measures momentum relative to recent price range. Moving averages indicate trend regime. Realized volatility is annualized from daily log returns.
          </p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
            <MIMetric label="RSI (14)" value={data.technicals.rsi !== null ? data.technicals.rsi.toFixed(1) : "—"} tone={rsiTone(data.technicals.rsi)} />
            <MIMetric label="Trend" value={data.technicals.trend} />
            <MIMetric label="Volatility (ann.)" value={data.technicals.volatilityRealized !== null ? `${(data.technicals.volatilityRealized * 100).toFixed(1)}%` : "—"} />
            <MIMetric label="MA 30d" value={data.technicals.movingAverage30 !== null ? `$${data.technicals.movingAverage30.toFixed(2)}` : "—"} />
            <MIMetric label="MA 50d" value={data.technicals.movingAverage50 !== null ? `$${data.technicals.movingAverage50.toFixed(2)}` : "—"} />
            <MIMetric label="MA 200d" value={data.technicals.movingAverage200 !== null ? `$${data.technicals.movingAverage200.toFixed(2)}` : "—"} />
            <MIMetric label="MACD line" value={data.technicals.macdLine !== null ? data.technicals.macdLine.toFixed(4) : "—"} />
            <MIMetric label="MACD signal" value={data.technicals.macdSignal !== null ? data.technicals.macdSignal.toFixed(4) : "—"} />
            <MIMetric label="Histogram" value={data.technicals.macdHistogram !== null ? `${data.technicals.macdHistogram >= 0 ? "+" : ""}${data.technicals.macdHistogram.toFixed(4)}` : "—"} tone={data.technicals.macdHistogram !== null ? (data.technicals.macdHistogram >= 0 ? "up" : "down") : undefined} />
          </div>
          <p className="mt-2 text-xs text-slate-500">Quality: <span className="text-slate-300">{data.technicals.dataQuality}</span> · Updated {new Date(data.technicals.updateTime).toLocaleTimeString()}</p>
        </section>
      )}

      {data.sentiment && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Sentiment</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            News sentiment scored 0–100 (50 = neutral) from keyword analysis of recent headlines. Social score is null when venue data is unavailable — never estimated. Source confidence mode is shown on every value.
          </p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            <MIMetric label="Overall" value={data.sentiment.overallScore.toFixed(1)} tone={data.sentiment.sentiment === "bullish" ? "up" : data.sentiment.sentiment === "bearish" ? "down" : undefined} />
            <MIMetric label="Signal" value={data.sentiment.sentiment} />
            <MIMetric label="Trend" value={data.sentiment.trendDirection} />
            <MIMetric label="News score" value={data.sentiment.newsScore !== null ? data.sentiment.newsScore.toFixed(1) : "—"} />
          </div>
          <p className="mt-2 text-xs text-slate-500">Sources: <span className="text-slate-300">{data.sentiment.sources.join(", ")}</span> · Mode: <span className="text-slate-300">{data.sentiment.sourceConfidence}</span></p>
        </section>
      )}
    </Panel>
  );
}

function PacketExecutionPanel({ packet }: { packet: DecisionPacket | null }) {
  if (!packet) {
    return (
      <Panel className="p-5">
        <SectionTitle eyebrow="Execution state" title="Specialists · confidence · risk" />
        <p className="mt-3 text-sm leading-6 text-slate-300">
          Packet actions can produce structured specialist outputs, confidence derivation, backtest gates, risk state, and portfolio context. This panel shows those results only when the packet workflow has actually computed them.
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Ambrosia should surface computed state plainly. If a module has not run yet, the absence is real and visible rather than silently filled with invented content.
        </p>
      </Panel>
    );
  }

  const providerTone: "good" | "warn" | "neutral" = packet.providerInfo?.fallbackUsed ? "warn" : packet.providerInfo ? "good" : "neutral";
  const confidence = packet.confidenceBreakdown;
  const specialistOutputs = packet.agentOutputs
    ? Object.values(packet.agentOutputs).filter((output): output is NonNullable<typeof output> => output !== null)
    : [];

  return (
    <Panel className="space-y-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionTitle eyebrow="Execution state" title="Packet-derived modules" />
        {packet.providerInfo ? <Badge tone={providerTone}>{packet.providerInfo.fallbackUsed ? "fallback used" : "provider active"}</Badge> : <Badge tone="neutral">no provider metadata</Badge>}
      </div>

      {packet.providerInfo ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Provider provenance</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            Model and coordinator runs should be labeled by runtime mode, not implied. This packet records which provider path was used and whether fallback execution was required.
          </p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <MIMetric label="Provider" value={packet.providerInfo.name ?? "—"} />
            <MIMetric label="Type" value={packet.providerInfo.type ?? "—"} />
            <MIMetric label="Fallback" value={packet.providerInfo.fallbackUsed ? "yes" : "no"} />
            <MIMetric label="Reason" value={packet.providerInfo.reason ?? "direct path"} small />
          </div>
        </section>
      ) : null}

      {confidence ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Confidence breakdown</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            Confidence should decompose into evidence, technical, sentiment, validation, tradeability, and risk-adjusted components. This is operational state, not a single opaque model score.
          </p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <MIMetric label="Evidence" value={`${confidence.evidenceScore}%`} />
            <MIMetric label="Technical" value={`${confidence.technicalScore}%`} />
            <MIMetric label="Sentiment" value={`${confidence.sentimentScore}%`} />
            <MIMetric label="Inter-market" value={`${confidence.interMarketScore}%`} />
            <MIMetric label="Validation" value={`${confidence.validationScore}%`} />
            <MIMetric label="Tradeability" value={`${confidence.tradeabilityScore}%`} />
            <MIMetric label="Risk-adjusted" value={`${confidence.riskAdjustedScore}%`} />
            <MIMetric label="Overall" value={`${confidence.overallConfidence}%`} />
          </div>
          {confidence.blockers.length > 0 ? <p className="mt-2 text-xs text-amber">Blockers: {confidence.blockers.join(", ")}</p> : null}
        </section>
      ) : null}

      {packet.backtestPlan || packet.backtestResult ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Backtest state</p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <MIMetric label="Plan status" value={packet.backtestPlan?.status ?? "—"} />
            <MIMetric label="Validity" value={packet.backtestResult?.validityScore ?? "—"} />
            <MIMetric label="Sharpe" value={packet.backtestResult?.sharpeRatio !== null && packet.backtestResult?.sharpeRatio !== undefined ? packet.backtestResult.sharpeRatio.toFixed(2) : "—"} />
            <MIMetric label="Max drawdown" value={packet.backtestResult?.maxDrawdown !== null && packet.backtestResult?.maxDrawdown !== undefined ? `${(packet.backtestResult.maxDrawdown * 100).toFixed(1)}%` : "—"} />
          </div>
          {packet.backtestResult?.hygienIssues?.length ? <p className="mt-2 text-xs text-slate-500">Hygiene issues: {packet.backtestResult.hygienIssues.join(", ")}</p> : null}
        </section>
      ) : null}

      {packet.riskMonitor ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Risk monitor</p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <MIMetric label="Status" value={packet.riskMonitor.status} tone={packet.riskMonitor.status === "safe" ? "up" : packet.riskMonitor.status === "alert" ? "down" : undefined} />
            <MIMetric label="Position size" value={packet.riskMonitor.activePositionSize.toFixed(0)} />
            <MIMetric label="Concentration" value={packet.riskMonitor.concentrationRisk} />
            <MIMetric label="Max DD threshold" value={`${(packet.riskMonitor.maxDrawdownThreshold * 100).toFixed(1)}%`} />
          </div>
          {packet.riskMonitor.followUpTriggers.length > 0 ? <p className="mt-2 text-xs text-slate-500">Triggers: {packet.riskMonitor.followUpTriggers.join(", ")}</p> : null}
        </section>
      ) : null}

      {packet.portfolioContext ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Portfolio context</p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <MIMetric label="Gross" value={`${(packet.portfolioContext.grossExposure * 100).toFixed(0)}%`} />
            <MIMetric label="Net" value={`${(packet.portfolioContext.netExposure * 100).toFixed(0)}%`} />
            <MIMetric label="Long" value={`${(packet.portfolioContext.longExposure * 100).toFixed(0)}%`} />
            <MIMetric label="Short" value={`${(packet.portfolioContext.shortExposure * 100).toFixed(0)}%`} />
            <MIMetric label="Risk budget left" value={`${(packet.portfolioContext.riskBudgetRemaining * 100).toFixed(0)}%`} />
          </div>
          <p className="mt-2 text-xs text-slate-500">Constraints: {packet.portfolioContext.sizingConstraints.join(", ")}</p>
        </section>
      ) : null}

      {specialistOutputs.length > 0 ? (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Specialist outputs</p>
          <p className="mb-3 text-xs leading-5 text-slate-500">
            These are the structured role outputs generated by the coordinator path. The provider used and any fallback are shown on each role output so the user can distinguish deterministic scaffolding from live model execution.
          </p>
          <div className="grid gap-3 lg:grid-cols-2">
            {specialistOutputs.map((output) => (
              <div key={`${output.role}-${output.timestamp}`} className="rounded-lg border border-line bg-paper p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">{output.role}</p>
                  <div className="flex items-center gap-2">
                    <Badge tone={output.fallbackUsed ? "warn" : "good"}>{output.fallbackUsed ? "deterministic" : "provider"}</Badge>
                    <span className="text-xs text-slate-500">{output.provider}</span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-slate-300">{output.summary}</p>
                {output.keyPoints.length > 0 ? (
                  <ul className="mt-2 grid gap-1 text-xs text-slate-500">
                    {output.keyPoints.map((point) => <li key={point}>- {point}</li>)}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </Panel>
  );
}
