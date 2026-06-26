"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, Beaker, CheckCircle2, Circle, Clock3, RefreshCw, ShieldCheck, SlidersHorizontal } from "lucide-react";
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
  runPacketAgents
} from "@/lib/api";
import { sampleReviews } from "@/lib/sample-data";
import type {
  Claim,
  DecisionPacket,
  DecisionState,
  MarketSnapshot,
  ReviewStatus,
  SentimentData,
  SourcePointer,
  TechnicalIndicators,
  TradeReview
} from "@/lib/types";
import { Badge, Panel, cn } from "./ui";

type ActionResult = "ok" | "fallback" | "skipped";

type LiveMarketData = {
  snapshot: MarketSnapshot | null;
  technicals: TechnicalIndicators | null;
  sentiment: SentimentData | null;
  ticker: string;
  fetchedAt: string;
};

type WorkflowStage = {
  status: ReviewStatus;
  label: string;
  summary: string;
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

const statusOrder: ReviewStatus[] = ["intake", "retrieval", "adversarial_review", "validation", "tradeability", "synthesis", "decision_recorded"];

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
        // The review route remains usable with bundled sample reviews when the API is unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setLiveMarketData(null);
    setActivePacketData(null);
    setActionFeedback(null);
  }, [activeId]);

  useEffect(() => {
    if (!initialReviewId) return;
    if (reviews.some((review) => review.id === initialReviewId)) {
      setActiveId(initialReviewId);
    }
  }, [initialReviewId, reviews]);

  const recentReviews = useMemo(() => reviews.slice(0, 4), [reviews]);

  function updateReview(reviewId: string, updater: (review: TradeReview) => TradeReview) {
    setReviews((current) => current.map((review) => (review.id === reviewId ? updater(review) : review)));
  }

  function updateConfidence(value: number) {
    updateReview(activeReview.id, (review) => ({
      ...review,
      confidence: value
    }));
  }

  function updateDecision(decisionState: DecisionState) {
    updateReview(activeReview.id, (review) => ({
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
    }));
    void recordDecision(activeReview.id, decisionState).catch(() => {
      // Sample and fallback reviews may not exist in the API store; keep local decision memory intact.
    });
  }

  function appendAuditEvent(eventType: string, detail: string) {
    if (!activeReview) return;
    updateReview(activeReview.id, (review) => ({
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
    }));
  }

  async function runAction(label: string, action: () => Promise<ActionResult>) {
    setActiveAction(label);
    setActionFeedback({ tone: "neutral", message: `${label} running...` });
    const result = await action();
    if (result === "ok") {
      setActionFeedback({ tone: "good", message: `${label} completed. The workflow trace was updated.` });
    } else if (result === "fallback") {
      setActionFeedback({ tone: "warn", message: `${label} could not reach every API path, so the review stayed in fallback-safe mode.` });
    } else {
      setActionFeedback({ tone: "warn", message: `${label} skipped because required packet context was missing.` });
    }
    setActiveAction(null);
  }

  function syncReviewFromPacket(reviewId: string, packet: DecisionPacket) {
    setActivePacketData(packet);
    updateReview(reviewId, (review) => ({
      ...review,
      confidence: packet.confidence,
      status: packet.status,
      decisionState: packet.decisionState,
      followUpDate: packet.followUpDate,
      audit: packet.audit
    }));
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
      providerInfo: null
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
        fetchedAt: new Date().toISOString()
      });
      appendAuditEvent("metrics.refresh", `Packet metrics refreshed for ${activeReview.ticker} via ${packetId}.`);
      return "ok";
    } catch {
      appendAuditEvent("metrics.refresh.fallback", `Metrics refresh API unavailable for ${activeReview.ticker}; local workflow remains active.`);
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
        riskConstraints: ["Max loss 8%", "Liquidity floor enforced"]
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("backtest.prepare", `Backtest plan prepared for ${activeReview.ticker} with status ${packet.backtestPlan?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("backtest.prepare.fallback", "Backtest preparation endpoint unavailable; packet flow remains in local mode.");
      return "fallback";
    }
  }

  async function evaluateRisk(): Promise<ActionResult> {
    if (!activeReview) {
      appendAuditEvent("risk.evaluate.skipped", "Risk evaluation skipped because no active review is selected.");
      return "skipped";
    }
    try {
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await evaluatePacketRisk(packetId, {
        activePositionSize: 250000,
        maxDrawdownThreshold: 0.12
      });
      syncReviewFromPacket(reviewId, packet);
      appendAuditEvent("risk.evaluate", `Risk evaluated for ${activeReview.ticker}: status ${packet.riskMonitor?.status ?? "unknown"}.`);
      return "ok";
    } catch {
      appendAuditEvent("risk.evaluate.fallback", "Risk evaluation endpoint unavailable; local advisory workflow remains active.");
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

  async function deriveConfidenceFromMarket(): Promise<ActionResult> {
    if (!activeReview?.ticker) {
      appendAuditEvent("confidence.derive.skipped", "No ticker available for technicals inspection.");
      return "skipped";
    }

    try {
      const [sentimentResult, technicalsResult, snapshotResult] = await Promise.allSettled([
        getSentiment(activeReview.ticker),
        getMarketTechnicals(activeReview.ticker),
        getMarketSnapshot(activeReview.ticker)
      ]);
      const sentiment = sentimentResult.status === "fulfilled" ? sentimentResult.value : null;
      const technicals = technicalsResult.status === "fulfilled" ? technicalsResult.value : null;
      const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : null;
      const { reviewId, packetId } = await ensurePacketForReview(activeReview);
      const packet = await derivePacketConfidence(packetId, {
        technicalScore: technicals?.rsi !== null && technicals?.rsi !== undefined ? Math.round(technicals.rsi) : 66,
        sentimentScore: sentiment ? Math.round(sentiment.overallScore) : 50,
        blockers: sentiment?.sentiment === "bearish" ? ["Sentiment regime still bearish"] : []
      });
      syncReviewFromPacket(reviewId, packet);
      setLiveMarketData({ snapshot, technicals, sentiment, ticker: activeReview.ticker, fetchedAt: new Date().toISOString() });
      appendAuditEvent("confidence.derive", `Technicals reviewed and confidence derived for ${activeReview.ticker}: ${packet.confidence}%.`);
      return "ok";
    } catch {
      appendAuditEvent("confidence.derive.fallback", "Technicals inspection endpoint unavailable; keeping deterministic local view.");
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
        outcome: activeReview.decisionState ?? "watch",
        outcome_date: new Date().toISOString().slice(0, 10),
        pnl: 0,
        notes: "Outcome placeholder captured from focused review workbench."
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
    <main className="min-h-screen pb-36 text-ink">
      <div className="mx-auto max-w-[1500px] space-y-4">
        <TopBar review={activeReview} />
        {actionFeedback ? <FeedbackBanner feedback={actionFeedback} /> : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_minmax(360px,1.35fr)_minmax(280px,0.85fr)]">
          <ContextPanel review={activeReview} recentReviews={recentReviews} onSelectReview={setActiveId} />
          <AnalysisFeed
            review={activeReview}
            packet={activePacketData}
            activeAction={activeAction}
            onRunAgents={() => runAction("Run analysis", runAgentSwarm)}
            onPrepareBacktest={() => runAction("Prepare backtest", prepareBacktest)}
            onDeriveConfidence={() => runAction("Derive confidence", deriveConfidenceFromMarket)}
          />
          <MarketAndRiskPanel
            review={activeReview}
            packet={activePacketData}
            marketData={liveMarketData}
            activeAction={activeAction}
            onRefresh={() => runAction("Refresh metrics", refreshMarketMetrics)}
            onEvaluateRisk={() => runAction("Evaluate risk", evaluateRisk)}
            onRecordOutcome={() => runAction("Record outcome", recordOutcomeForDecision)}
          />
        </div>

        <DecisionStrip review={activeReview} activeAction={activeAction} onConfidenceChange={updateConfidence} onDecision={updateDecision} />
      </div>
    </main>
  );
}

function TopBar({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Pre-trade adversarial review</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal text-ink">{review.title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-5 text-slate-400">
            Focused decision workspace for one packet: original thesis, agent analysis, market context, and the human decision.
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
      </div>
    </Panel>
  );
}

function FeedbackBanner({ feedback }: { feedback: { tone: "neutral" | "good" | "warn"; message: string } }) {
  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-sm",
        feedback.tone === "good"
          ? "border-teal/30 bg-teal/10 text-teal"
          : feedback.tone === "warn"
            ? "border-amber/30 bg-amber/10 text-amber"
            : "border-line bg-paper text-slate-300"
      )}
    >
      {feedback.message}
    </div>
  );
}

function ContextPanel({ review, recentReviews, onSelectReview }: { review: TradeReview; recentReviews: TradeReview[]; onSelectReview: (reviewId: string) => void }) {
  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <PanelHeader eyebrow="Left Context" title="Thesis and sources" />
        <div className="mt-4 space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <ContextMetric label="Ticker" value={review.ticker} />
            <ContextMetric label="Asset" value={review.assetClass} />
            <ContextMetric label="Horizon" value={review.timeHorizon} />
            <ContextMetric label="Expression" value={review.intendedExpression} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Original thesis</p>
            <p className="mt-2 leading-6 text-slate-200">{review.thesis}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Claim map</p>
            <ul className="mt-2 space-y-2">
              {review.claims.map((claim) => (
                <ClaimRow key={claim.id} claim={claim} />
              ))}
            </ul>
          </div>
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Source Context" title="Evidence pointers" />
        <ul className="mt-3 space-y-2">
          {review.sources.map((source) => (
            <SourceRow key={source.id} source={source} />
          ))}
        </ul>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Review Queue" title="Resume another packet" />
        <div className="mt-3 space-y-2">
          {recentReviews.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => onSelectReview(item.id)}
              className={cn(
                "focus-ring w-full rounded-md border p-3 text-left text-sm transition",
                item.id === review.id ? "border-teal/70 bg-teal/10" : "border-line bg-fog/60 hover:border-teal/40"
              )}
            >
              <span className="block font-semibold">{item.title}</span>
              <span className="mt-1 block text-xs text-slate-400">
                {item.ticker} / {item.timeHorizon}
              </span>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function AnalysisFeed({
  review,
  packet,
  activeAction,
  onRunAgents,
  onPrepareBacktest,
  onDeriveConfidence
}: {
  review: TradeReview;
  packet: DecisionPacket | null;
  activeAction: string | null;
  onRunAgents: () => void;
  onPrepareBacktest: () => void;
  onDeriveConfidence: () => void;
}) {
  const stages = buildWorkflowStages(review, packet);

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PanelHeader eyebrow="Center Analysis" title="Live workflow feed" />
          <div className="flex flex-wrap gap-2">
            <ActionButton label="Run analysis" icon={<Activity className="h-4 w-4" />} activeAction={activeAction} onClick={onRunAgents} />
            <ActionButton label="Prepare backtest" icon={<Beaker className="h-4 w-4" />} activeAction={activeAction} onClick={onPrepareBacktest} />
            <ActionButton label="Derive confidence" icon={<SlidersHorizontal className="h-4 w-4" />} activeAction={activeAction} onClick={onDeriveConfidence} />
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {stages.map((stage) => (
            <WorkflowStageCard key={stage.status} stage={stage} currentStatus={review.status} review={review} packet={packet} />
          ))}
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Decision Evidence" title="Critique and disconfirming test" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <EvidenceBlock label="Strongest critique" text={review.strongestCritique} tone="warn" />
          <EvidenceBlock label="Disconfirming test" text={review.disconfirmingTest} tone="info" />
        </div>
        <details className="mt-3 rounded-md border border-line bg-fog/60 p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-slate-200">Historical analogue</summary>
          <div className="mt-3 space-y-2 text-slate-300">
            <p className="font-semibold">{review.historicalAnalogue.title}</p>
            <p>{review.historicalAnalogue.similarity}</p>
            <p>{review.historicalAnalogue.differences}</p>
            <p>{review.historicalAnalogue.resolution}</p>
          </div>
        </details>
      </Panel>
    </div>
  );
}

function MarketAndRiskPanel({
  review,
  packet,
  marketData,
  activeAction,
  onRefresh,
  onEvaluateRisk,
  onRecordOutcome
}: {
  review: TradeReview;
  packet: DecisionPacket | null;
  marketData: LiveMarketData | null;
  activeAction: string | null;
  onRefresh: () => void;
  onEvaluateRisk: () => void;
  onRecordOutcome: () => void;
}) {
  const snapshot = marketData?.snapshot ?? packet?.marketSnapshot ?? null;
  const technicals = marketData?.technicals ?? packet?.technicals ?? null;
  const sentiment = marketData?.sentiment ?? packet?.sentiment ?? null;

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex items-start justify-between gap-3">
          <PanelHeader eyebrow="Right Context" title={`${review.ticker} market dock`} />
          <ActionButton label="Refresh" icon={<RefreshCw className="h-4 w-4" />} activeAction={activeAction} onClick={onRefresh} compact />
        </div>
        <div className="mt-4 space-y-2 text-sm">
          <MetricRow label="Price" value={snapshot ? `$${snapshot.price.toFixed(2)}` : "Not loaded"} />
          <MetricRow label="24h change" value={snapshot ? `${snapshot.priceChange24h >= 0 ? "+" : ""}${snapshot.priceChange24h.toFixed(2)}%` : "Not loaded"} tone={snapshot && snapshot.priceChange24h < 0 ? "warn" : "good"} />
          <MetricRow label="Volume" value={snapshot ? compactNumber(snapshot.volume24h) : "Not loaded"} />
          <MetricRow label="RSI" value={technicals?.rsi !== null && technicals?.rsi !== undefined ? technicals.rsi.toFixed(1) : "Not loaded"} />
          <MetricRow label="MA200" value={technicals?.movingAverage200 !== null && technicals?.movingAverage200 !== undefined ? `$${technicals.movingAverage200.toFixed(2)}` : "Not loaded"} />
          <MetricRow label="Sentiment" value={sentiment ? `${sentiment.sentiment} (${Math.round(sentiment.overallScore)}%)` : "Not loaded"} />
        </div>
        <div className="mt-4 rounded-md border border-line bg-fog/60 p-3 text-xs text-slate-400">
          Source: {snapshot?.dataSource ?? "pending"} / Mode: {snapshot?.dataSourceConfidence ?? technicals?.dataMode ?? sentiment?.dataMode ?? "not loaded"}
        </div>
        <Link href={`/markets/${review.ticker}`} className="focus-ring mt-3 inline-flex items-center gap-1 text-sm font-semibold text-teal">
          Open deep charting <ArrowRight className="h-4 w-4" />
        </Link>
      </Panel>

      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PanelHeader eyebrow="Risk Gate" title="Tradeability and controls" />
          <ActionButton label="Evaluate" icon={<ShieldCheck className="h-4 w-4" />} activeAction={activeAction} onClick={onEvaluateRisk} compact />
        </div>
        <div className="mt-4 space-y-3">
          {review.tradeability.map((item) => (
            <div key={`${item.topic}-${item.question}`} className="rounded-md border border-line bg-fog/60 p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{item.topic}</p>
                <Badge tone={item.severity === "high" ? "warn" : "neutral"}>{item.severity}</Badge>
              </div>
              <p className="mt-2 text-slate-300">{item.question}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-md border border-line bg-fog/60 p-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk monitor</p>
          <p className="mt-2 text-slate-300">{packet?.riskMonitor ? `${packet.riskMonitor.status} / concentration ${packet.riskMonitor.concentrationRisk}` : "Not evaluated yet"}</p>
        </div>
      </Panel>

      <Panel className="p-5">
        <PanelHeader eyebrow="Outcome Loop" title="After decision" />
        <p className="mt-3 text-sm text-slate-400">
          Once a human decision is recorded, capture the outcome so Ambrosia can update history and calibration.
        </p>
        <button
          type="button"
          onClick={onRecordOutcome}
          disabled={Boolean(activeAction) || !review.decisionState}
          className="focus-ring mt-4 w-full rounded-md border border-line bg-paper px-3 py-2 text-sm font-semibold text-slate-200 hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Record outcome
        </button>
      </Panel>
    </div>
  );
}

function DecisionStrip({
  review,
  activeAction,
  onConfidenceChange,
  onDecision
}: {
  review: TradeReview;
  activeAction: string | null;
  onConfidenceChange: (value: number) => void;
  onDecision: (decisionState: DecisionState) => void;
}) {
  return (
    <Panel className="sticky bottom-3 z-30 border-2 border-teal/40 bg-paper/95 p-4 shadow-panel backdrop-blur">
      <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(360px,1.2fr)_minmax(220px,0.8fr)] lg:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal">Sticky decision strip</p>
          <p className="mt-1 text-sm text-slate-400">Human authority remains explicit. Ambrosia supports the decision; it does not make it.</p>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Confidence</span>
            <span className="font-semibold text-teal">{review.confidence}%</span>
          </div>
          <input
            aria-label="Confidence"
            type="range"
            min={0}
            max={100}
            value={review.confidence}
            onChange={(event) => onConfidenceChange(Number(event.target.value))}
            className="w-full accent-teal"
          />
          <p className="text-xs text-slate-500">
            Trial impact: +{review.trialCountImpact} / Follow-up: {review.followUpDate}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(Object.entries(decisionLabels) as Array<[DecisionState, string]>).map(([state, label]) => (
            <button
              type="button"
              key={state}
              onClick={() => onDecision(state)}
              disabled={Boolean(activeAction)}
              className={cn(
                "focus-ring rounded-md px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
                review.decisionState === state ? "bg-teal text-fog" : "border border-line bg-fog/70 text-slate-200 hover:border-teal/50"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function WorkflowStageCard({ stage, currentStatus, review, packet }: { stage: WorkflowStage; currentStatus: ReviewStatus; review: TradeReview; packet: DecisionPacket | null }) {
  const currentIndex = statusOrder.indexOf(currentStatus);
  const stageIndex = statusOrder.indexOf(stage.status);
  const done = stageIndex < currentIndex || currentStatus === "decision_recorded";
  const active = stage.status === currentStatus && currentStatus !== "decision_recorded";
  const waiting = stageIndex > currentIndex;
  const Icon = done ? CheckCircle2 : active ? Clock3 : Circle;

  return (
    <details className={cn("rounded-md border p-3 text-sm", done ? "border-teal/30 bg-teal/5" : active ? "border-amber/40 bg-amber/5" : "border-line bg-fog/60")} open={active}>
      <summary className="flex cursor-pointer list-none items-start gap-3">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", done ? "text-teal" : active ? "text-amber" : "text-slate-500")} />
        <span className="flex-1">
          <span className="block font-semibold">{stage.label}</span>
          <span className={cn("mt-1 block text-xs", waiting ? "text-slate-500" : "text-slate-300")}>{stage.summary}</span>
        </span>
      </summary>
      <div className="mt-3 border-t border-line pt-3 text-xs leading-5 text-slate-300">
        {stage.status === "validation" ? (
          <div className="space-y-2">
            <p>{review.validation.hypothesis}</p>
            <p className="text-slate-500">Null: {review.validation.nullHypothesis}</p>
            {review.validation.refusalReason ? <p className="text-amber">Refusal: {review.validation.refusalReason}</p> : null}
          </div>
        ) : stage.status === "tradeability" ? (
          <ul className="space-y-1">
            {review.tradeability.map((item) => (
              <li key={item.question}>{item.topic}: {item.question}</li>
            ))}
          </ul>
        ) : stage.status === "synthesis" && packet?.agentOutputs ? (
          <ul className="space-y-1">
            {Object.values(packet.agentOutputs).flatMap((agent) => (agent ? [agent] : [])).map((agent) => (
              <li key={`${agent.role}-${agent.timestamp}`}>{agent.role}: {agent.summary}</li>
            ))}
          </ul>
        ) : (
          <p>{stage.summary}</p>
        )}
      </div>
    </details>
  );
}

function buildWorkflowStages(review: TradeReview, packet: DecisionPacket | null): WorkflowStage[] {
  return [
    { status: "intake", label: statusLabels.intake, summary: `${review.ticker} thesis normalized into a review packet.` },
    { status: "retrieval", label: statusLabels.retrieval, summary: `${review.sources.length} source pointer${review.sources.length === 1 ? "" : "s"} available for review context.` },
    { status: "adversarial_review", label: statusLabels.adversarial_review, summary: review.strongestCritique },
    { status: "validation", label: statusLabels.validation, summary: review.validation.status === "refused" ? "Validation refused until the evidence contract is tighter." : "Validation protocol is specified." },
    { status: "tradeability", label: statusLabels.tradeability, summary: `${review.tradeability.length} tradeability question${review.tradeability.length === 1 ? "" : "s"} must be answered before action.` },
    { status: "synthesis", label: statusLabels.synthesis, summary: packet?.providerInfo ? `Coordinator output available from ${packet.providerInfo.name}.` : `Current confidence is ${review.confidence}%.` },
    { status: "decision_recorded", label: statusLabels.decision_recorded, summary: review.decisionState ? `Human decision: ${decisionLabels[review.decisionState]}.` : "Awaiting human decision." }
  ];
}

function ActionButton({ label, icon, activeAction, onClick, compact = false }: { label: string; icon: React.ReactNode; activeAction: string | null; onClick: () => void; compact?: boolean }) {
  const running = activeAction === label;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={Boolean(activeAction)}
      className={cn(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-md border border-line bg-fog/70 font-semibold text-slate-200 transition hover:border-teal/50 disabled:cursor-not-allowed disabled:opacity-50",
        compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-xs"
      )}
    >
      {icon}
      {running ? "Running..." : label}
    </button>
  );
}

function PanelHeader({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-teal">{eyebrow}</p>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
    </div>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/60 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function ClaimRow({ claim }: { claim: Claim }) {
  return (
    <li className="rounded-md border border-line bg-fog/60 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-slate-200">{claim.text}</p>
        <Badge tone={claim.kind === "contradiction" ? "warn" : claim.kind === "sourced" ? "good" : "neutral"}>{claim.kind}</Badge>
      </div>
      <p className="mt-2 text-xs text-slate-500">Confidence: {claim.confidence}%{claim.evidence ? ` / ${claim.evidence}` : ""}</p>
    </li>
  );
}

function SourceRow({ source }: { source: SourcePointer }) {
  return (
    <li className="rounded-md border border-line bg-fog/60 p-3 text-sm">
      <p className="font-semibold text-slate-200">{source.title}</p>
      <p className="mt-1 text-xs text-slate-500">
        {source.sourceType} / {source.timestamp} / relevance {Math.round(source.relevance * 100)}%
      </p>
    </li>
  );
}

function EvidenceBlock({ label, text, tone }: { label: string; text: string; tone: "warn" | "info" }) {
  return (
    <div className={cn("rounded-md border p-3 text-sm", tone === "warn" ? "border-amber/30 bg-amber/5" : "border-violet/30 bg-violet/5")}>
      <p className={cn("text-xs font-semibold uppercase tracking-wide", tone === "warn" ? "text-amber" : "text-violet")}>{label}</p>
      <p className="mt-2 leading-5 text-slate-200">{text}</p>
    </div>
  );
}

function MetricRow({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "good" | "warn" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-fog/60 px-3 py-2">
      <span className="text-slate-400">{label}</span>
      <span className={cn("font-semibold", tone === "good" ? "text-teal" : tone === "warn" ? "text-amber" : "text-slate-200")}>{value}</span>
    </div>
  );
}

function compactNumber(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function mergeReviews(apiReviews: TradeReview[], localReviews: TradeReview[]): TradeReview[] {
  const apiMap = new Map(apiReviews.map((review) => [review.id, review]));
  const merged = [...apiReviews];
  for (const local of localReviews) {
    if (!apiMap.has(local.id)) {
      merged.push(local);
    }
  }
  return merged;
}
