"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { Activity, AlertTriangle, BarChart3, BookOpen, CheckCircle2, ClipboardCheck, Database, FileSearch, History, ShieldCheck, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ApiUnavailableError, createReview, getMarketSnapshot, getMarketTechnicals, listReviews, recordDecision } from "@/lib/api";
import { sampleReviews } from "@/lib/sample-data";
import { generateLocalReview, thesisCandidates } from "@/lib/review-generator";
import type { Claim, DashboardMetrics, DecisionState, ReviewStatus, SourcePointer, ThesisInput, TradeReview } from "@/lib/types";
import { Badge, Panel, SectionTitle, cn } from "./ui";
import { CommonActionsBar } from "./common-actions";

type NavView = "workbench" | "memory" | "calibration" | "sources";

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
  const [activeId, setActiveId] = useState(sampleReviews[0]?.id ?? "");
  const [activeView, setActiveView] = useState<NavView>("workbench");
  const [generationMode, setGenerationMode] = useState<"api" | "fallback" | "idle">("idle");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [seedRequestToken, setSeedRequestToken] = useState(0);
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

  async function refreshMarketMetrics() {
    if (!activeReview?.ticker) {
      appendAuditEvent("metrics.refresh.skipped", "No ticker available for metrics refresh.");
      return;
    }

    try {
      const [snapshot, technicals] = await Promise.all([
        getMarketSnapshot(activeReview.ticker),
        getMarketTechnicals(activeReview.ticker)
      ]);

      appendAuditEvent(
        "metrics.refresh",
        `Metrics refreshed for ${activeReview.ticker}: source=${snapshot.dataSource} (${snapshot.dataSourceConfidence}), trend=${technicals.trend}.`
      );
    } catch {
      appendAuditEvent(
        "metrics.refresh.fallback",
        `Metrics refresh API unavailable for ${activeReview.ticker}; local workflow remains active.`
      );
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
              <CommonActionsBar
                onNewPacket={() => {
                  setActiveView("workbench");
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                onGenerateThesis={() => setSeedRequestToken((current) => current + 1)}
                onIngestAlert={() => appendAuditEvent("event_intake.manual", "Manual alert intake opened from common actions.")}
                onRefreshMetrics={() => {
                  void refreshMarketMetrics();
                }}
                onViewTechnicals={() => appendAuditEvent("view.technicals", "Technical section inspected from common actions.")}
                onViewSentiment={() => appendAuditEvent("view.sentiment", "Sentiment section inspected from common actions.")}
                onCompareMarkets={() => appendAuditEvent("view.inter_market", "Inter-market comparison requested from common actions.")}
                onPrepareBacktest={() => appendAuditEvent("backtest.prepare", "Backtest preparation requested from common actions.")}
                onRunBacktest={() => appendAuditEvent("backtest.run_requested", "Backtest run requested; eligibility checks pending.")}
                onRecordDecision={() => updateDecision(activeReview.decisionState ?? "watch")}
                onSetFollowUp={() => appendAuditEvent("follow_up.set", `Follow-up reminder set for ${activeReview.followUpDate}.`)}
                onViewRisks={() => appendAuditEvent("view.risk", "Risk monitor viewed from common actions.")}
                onExportReport={exportActiveReview}
              />
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
          <div className="mt-3 grid gap-3">
            {review.claims.map((claim) => <ClaimCard key={claim.id} claim={claim} />)}
          </div>
        </div>

        <div>
          <h3 className="font-semibold">Tradeability checklist</h3>
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
