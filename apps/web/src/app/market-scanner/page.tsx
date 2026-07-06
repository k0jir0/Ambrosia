"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, Clock3, LoaderCircle, Play, RefreshCw, Send, SlidersHorizontal } from "lucide-react";
import { listJobs, listScannerCandidatePromotions, promoteScannerCandidateToAlpha, runScanner, runScannerAsync, validateSignal } from "@/lib/api";
import type { JobRecord, ScannerCandidate, ScannerCandidatePromotion, ScannerResult, ScannerRunRequest, ScannerSignal } from "@/lib/types";
import { Badge, Panel, SectionTitle, cn } from "@/components/ui";
import { RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";

type WatchlistKey = "core" | "etfs" | "tech" | "custom";

const WATCHLISTS: Record<Exclude<WatchlistKey, "custom">, { label: string; universe: string[] }> = {
  core: { label: "Core liquid watchlist", universe: ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "JPM", "XOM", "SPY", "QQQ"] },
  etfs: { label: "Index and sector ETFs", universe: ["SPY", "QQQ", "IWM", "RSP", "SOXX", "XLF", "XLE", "XLV", "TLT", "USO"] },
  tech: { label: "Large-cap technology", universe: ["AAPL", "MSFT", "NVDA", "AVGO", "AMD", "META", "GOOGL", "AMZN", "TSLA", "ORCL"] }
};

const DEFAULT_RESULT: ScannerResult = {
  candidates: [],
  scannedAt: "",
  universe: [],
  totalScanned: 0,
  dataMode: "demo"
};

export default function MarketScannerPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState("Loading market scanner...");
  const [watchlist, setWatchlist] = useState<WatchlistKey>("core");
  const [customUniverse, setCustomUniverse] = useState("SPY, QQQ, NVDA, MSFT");
  const [signalFilter, setSignalFilter] = useState<ScannerRunRequest["signalFilter"]>("all");
  const [maxCandidates, setMaxCandidates] = useState(8);
  const [minVolume, setMinVolume] = useState(1_000_000);
  const [result, setResult] = useState<ScannerResult>(DEFAULT_RESULT);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [promotions, setPromotions] = useState<ScannerCandidatePromotion[]>([]);
  const [activeAction, setActiveAction] = useState<"scan" | "queue" | "jobs" | null>(null);
  const [candidateBusyKey, setCandidateBusyKey] = useState<string | null>(null);

  const promotionByCandidate = useMemo(() => {
    const byCandidate = new Map<string, ScannerCandidatePromotion>();
    for (const promotion of promotions) {
      const key = scannerPromotionKey(promotion.ticker, promotion.signal);
      const current = byCandidate.get(key);
      if (!current) {
        byCandidate.set(key, promotion);
        continue;
      }
      const currentTs = Date.parse(current.promotedAt || "");
      const nextTs = Date.parse(promotion.promotedAt || "");
      if (Number.isFinite(nextTs) && (!Number.isFinite(currentTs) || nextTs >= currentTs)) {
        byCandidate.set(key, promotion);
      }
    }
    return byCandidate;
  }, [promotions]);

  const selectedUniverse = useMemo(() => {
    if (watchlist !== "custom") return WATCHLISTS[watchlist].universe;
    return customUniverse
      .split(/[\s,]+/)
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean)
      .slice(0, 50);
  }, [customUniverse, watchlist]);

  const requestBody = useMemo<ScannerRunRequest>(
    () => ({
      universe: selectedUniverse,
      signalFilter,
      maxCandidates,
      minVolume
    }),
    [maxCandidates, minVolume, selectedUniverse, signalFilter]
  );

  const scannerJobs = useMemo(() => jobs.filter((job) => job.jobType === "scanner.run"), [jobs]);
  const latestJob = scannerJobs[0] ?? null;

  async function refreshJobs() {
    setActiveAction("jobs");
    try {
      const records = await listJobs();
      setJobs(records);
    } catch {
      setJobs([]);
    } finally {
      setActiveAction(null);
    }
  }

  async function refreshPromotions() {
    try {
      const records = await listScannerCandidatePromotions();
      setPromotions(records);
    } catch {
      setPromotions([]);
    }
  }

  async function runScan() {
    setActiveAction("scan");
    setStatus("loading");
    setMessage("Running scanner...");
    try {
      const nextResult = await runScanner(requestBody);
      setResult(nextResult);
      setStatus(nextResult.candidates.length === 0 ? "empty" : "success");
      setMessage(nextResult.candidates.length === 0 ? "No candidates matched the current scanner filters." : "Market scanner loaded.");
      await refreshPromotions();
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Market scanner endpoint is unavailable.");
    } finally {
      setActiveAction(null);
    }
  }

  async function queueScan() {
    setActiveAction("queue");
    try {
      const job = await runScannerAsync(requestBody);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setMessage(`Queued scanner job ${job.id}.`);
      setStatus(result.candidates.length === 0 ? "empty" : "success");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to queue scanner job.");
    } finally {
      setActiveAction(null);
    }
  }

  async function promoteCandidate(candidate: ScannerCandidate) {
    const busyKey = scannerPromotionKey(candidate.ticker, candidate.signal);
    setCandidateBusyKey(busyKey);
    try {
      const scannerRunId = result.scannedAt || candidate.scannedAt;
      await promoteScannerCandidateToAlpha({
        ticker: candidate.ticker,
        signal: candidate.signal,
        thesisSuggestion: candidate.thesisSuggestion,
        score: candidate.score,
        price: candidate.price,
        trend: candidate.trend,
        rsi: candidate.rsi,
        volume: candidate.volume24h,
        scannerRunId,
        universe: selectedUniverse,
        horizon: "2-6 weeks",
        costModel: "10 bps round-trip",
        benchmark: "SPY",
        owner: "research",
        promotedBy: "scanner-ui",
      });
      await refreshPromotions();
      setStatus("success");
      setMessage(`${candidate.ticker} promoted into Alpha Lab.`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Failed to promote scanner candidate.");
    } finally {
      setCandidateBusyKey(null);
    }
  }

  async function queueValidation(candidate: ScannerCandidate, promotion: ScannerCandidatePromotion | null) {
    if (!promotion?.signalId) {
      setStatus("error");
      setMessage(`Promote ${candidate.ticker} first to queue validation.`);
      return;
    }
    const busyKey = `${scannerPromotionKey(candidate.ticker, candidate.signal)}:validate`;
    setCandidateBusyKey(busyKey);
    try {
      await validateSignal(promotion.signalId, { signalVersion: promotion.signalVersion });
      await refreshPromotions();
      setStatus("success");
      setMessage(`Validation queued for ${promotion.signalId}.`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Failed to run validation for candidate signal.");
    } finally {
      setCandidateBusyKey(null);
    }
  }

  useEffect(() => {
    async function loadInitial() {
      setActiveAction("scan");
      try {
        const nextResult = await runScanner({
          universe: WATCHLISTS.core.universe,
          signalFilter: "all",
          maxCandidates: 8,
          minVolume: 1_000_000
        });
        setResult(nextResult);
        setStatus(nextResult.candidates.length === 0 ? "empty" : "success");
        setMessage(nextResult.candidates.length === 0 ? "No candidates matched the current scanner filters." : "Market scanner loaded.");
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "Market scanner endpoint is unavailable.");
      } finally {
        setActiveAction(null);
      }

      try {
        const records = await listJobs();
        setJobs(records);
      } catch {
        setJobs([]);
      }

      await refreshPromotions();
    }

    void loadInitial();
  }, []);

  const showNotice = status !== "success" && status !== "loading";

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <SectionTitle eyebrow="Market Intelligence" title="Market Scanner" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/75">
              Scan liquid watchlists for momentum and mean-reversion candidates, then promote the strongest setups into review.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button type="button" onClick={() => void runScan()} className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-ink/80">
              {activeAction === "scan" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </button>
          </div>
        </div>
      </Panel>

      {showNotice ? <RouteNotice status={status} message={message} retry={() => void runScan()} /> : null}

      <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Panel className="p-5">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-teal" />
            <SectionTitle eyebrow="Scanner" title="Launch criteria" />
          </div>

          <div className="mt-4 space-y-4 text-sm">
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink/60">Watchlist</span>
              <select value={watchlist} onChange={(event) => setWatchlist(event.target.value as WatchlistKey)} className="focus-ring mt-1 w-full rounded-md border border-line bg-fog/70 px-3 py-2">
                <option value="core">Core liquid watchlist</option>
                <option value="etfs">Index and sector ETFs</option>
                <option value="tech">Large-cap technology</option>
                <option value="custom">Custom tickers</option>
              </select>
            </label>

            {watchlist === "custom" ? (
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-ink/60">Custom universe</span>
                <textarea value={customUniverse} onChange={(event) => setCustomUniverse(event.target.value)} rows={3} className="focus-ring mt-1 w-full rounded-md border border-line bg-fog/70 px-3 py-2" />
              </label>
            ) : (
              <div className="rounded-md border border-line bg-fog/70 p-3 text-xs leading-5 text-ink/70">
                {WATCHLISTS[watchlist].universe.join(", ")}
              </div>
            )}

            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink/60">Signal filter</span>
              <select value={signalFilter} onChange={(event) => setSignalFilter(event.target.value as ScannerRunRequest["signalFilter"])} className="focus-ring mt-1 w-full rounded-md border border-line bg-fog/70 px-3 py-2">
                <option value="all">All signals</option>
                <option value="momentum">Momentum</option>
                <option value="mean_reversion">Mean reversion</option>
                <option value="breadth">Breadth candidates</option>
              </select>
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-ink/60">Max results</span>
                <input type="number" min={1} max={50} value={maxCandidates} onChange={(event) => setMaxCandidates(Number(event.target.value))} className="focus-ring mt-1 w-full rounded-md border border-line bg-fog/70 px-3 py-2" />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wide text-ink/60">Min volume</span>
                <input type="number" min={0} step={100000} value={minVolume} onChange={(event) => setMinVolume(Number(event.target.value))} className="focus-ring mt-1 w-full rounded-md border border-line bg-fog/70 px-3 py-2" />
              </label>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <button type="button" onClick={() => void runScan()} className="focus-ring inline-flex items-center justify-center gap-2 rounded-md bg-teal px-3 py-2 font-semibold text-fog">
                {activeAction === "scan" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run scan
              </button>
              <button type="button" onClick={() => void queueScan()} className="focus-ring inline-flex items-center justify-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 font-semibold text-ink/80">
                {activeAction === "queue" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Queue job
              </button>
            </div>
          </div>
        </Panel>

        <div className="space-y-4">
          <section className="grid gap-3 md:grid-cols-4">
            <Metric label="Candidates" value={String(result.candidates.length)} />
            <Metric label="Tickers scanned" value={String(result.totalScanned)} />
            <Metric label="Data mode" value={result.dataMode} />
            <Metric label="Scanner jobs" value={String(scannerJobs.length)} />
          </section>

          <Panel className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SectionTitle eyebrow="Ranked Output" title="Candidate list" />
              <span className="text-xs text-ink/55">{result.scannedAt ? `Updated ${formatTime(result.scannedAt)}` : "No scan yet"}</span>
            </div>
            <div className="mt-4 space-y-2">
              {result.candidates.map((candidate) => (
                <CandidateRow
                  key={`${candidate.ticker}-${candidate.signal}`}
                  candidate={candidate}
                  promotion={promotionByCandidate.get(scannerPromotionKey(candidate.ticker, candidate.signal)) ?? null}
                  busyKey={candidateBusyKey}
                  onPromote={promoteCandidate}
                  onQueueValidation={queueValidation}
                />
              ))}
              {result.candidates.length === 0 ? (
                <div className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-6 text-center text-sm text-ink/60">
                  No candidates matched the current scanner filters.
                </div>
              ) : null}
            </div>
          </Panel>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Panel className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SectionTitle eyebrow="Jobs" title="Scanner queue" />
            <button type="button" onClick={() => void refreshJobs()} className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-ink/80">
              {activeAction === "jobs" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh jobs
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {scannerJobs.slice(0, 6).map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
            {scannerJobs.length === 0 ? (
              <div className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-4 text-sm text-ink/60">
                No scanner jobs are currently visible.
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel className="p-5">
          <SectionTitle eyebrow="Job Details" title="Latest scanner job" />
          {latestJob ? (
            <div className="mt-4 space-y-3 text-sm">
              <Detail label="ID" value={latestJob.id} />
              <Detail label="State" value={latestJob.state} />
              <Detail label="Input" value={latestJob.inputSummary} />
              <Detail label="Queued" value={formatTime(latestJob.queuedAt)} />
              <Detail label="Completed" value={latestJob.completedAt ? formatTime(latestJob.completedAt) : "pending"} />
              {latestJob.error ? <Detail label="Error" value={latestJob.error} tone="bad" /> : null}
            </div>
          ) : (
            <p className="mt-4 rounded-md border border-dashed border-line bg-fog/50 px-3 py-4 text-sm text-ink/60">
              Queue a scanner job to track async progress.
            </p>
          )}
        </Panel>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/55">{label}</p>
      <p className="mt-2 truncate text-xl font-semibold text-ink">{value}</p>
    </Panel>
  );
}

function CandidateRow({
  candidate,
  promotion,
  busyKey,
  onPromote,
  onQueueValidation,
}: {
  candidate: ScannerCandidate;
  promotion: ScannerCandidatePromotion | null;
  busyKey: string | null;
  onPromote: (candidate: ScannerCandidate) => Promise<void>;
  onQueueValidation: (candidate: ScannerCandidate, promotion: ScannerCandidatePromotion | null) => Promise<void>;
}) {
  const promoteBusy = busyKey === scannerPromotionKey(candidate.ticker, candidate.signal);
  const validateBusy = busyKey === `${scannerPromotionKey(candidate.ticker, candidate.signal)}:validate`;

  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <div className="grid gap-3 lg:grid-cols-[84px_150px_minmax(0,1fr)_120px_120px] lg:items-center">
        <div>
          <p className="font-mono text-sm font-semibold text-ink">{candidate.ticker}</p>
          <p className="text-xs text-ink/60">${candidate.price.toFixed(2)}</p>
        </div>
        <Badge tone={signalTone(candidate.signal)}>{candidate.signal.replace(/_/g, " ")}</Badge>
        <p className="text-sm leading-6 text-ink/75">{candidate.thesisSuggestion}</p>
        <div className="grid grid-cols-2 gap-2 text-xs text-ink/65">
          <span>RSI {candidate.rsi ?? "n/a"}</span>
          <span>{candidate.trend}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-ink">{Math.round(candidate.score * 100)}%</span>
          <Badge tone={promotion ? promotionTone(promotion.status) : "neutral"}>{promotion ? promotionLabel(promotion.status) : "Not promoted"}</Badge>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/55">
        <Activity className="h-3.5 w-3.5" />
        <span>{formatCompact(candidate.volume24h)} volume</span>
        <span>{candidate.dataSource}</span>
        <Badge tone={candidate.dataMode === "live" ? "good" : candidate.dataMode === "fallback" ? "warn" : "neutral"}>{candidate.dataMode}</Badge>
        {promotion?.latestDecisionState ? <span>decision {promotion.latestDecisionState}</span> : null}
        {typeof promotion?.linkedReviewCount === "number" ? <span>reviews {promotion.linkedReviewCount}</span> : null}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void onPromote(candidate)}
          disabled={promoteBusy}
          className="focus-ring inline-flex items-center gap-1 rounded-md bg-teal px-2 py-1 text-xs font-semibold text-fog disabled:opacity-60"
        >
          {promoteBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : null}
          Promote to Alpha
        </button>
        <Link href={buildReviewHref(candidate, promotion)} className="focus-ring rounded-md border border-line bg-paper px-2 py-1 text-xs font-semibold text-ink/85">
          Create Review
        </Link>
        <button
          type="button"
          onClick={() => void onQueueValidation(candidate, promotion)}
          disabled={validateBusy || !promotion?.signalId}
          className="focus-ring inline-flex items-center gap-1 rounded-md border border-line bg-paper px-2 py-1 text-xs font-semibold text-ink/85 disabled:opacity-50"
        >
          {validateBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : null}
          Queue validation
        </button>
        <Link href={`/markets/${encodeURIComponent(candidate.ticker)}`} className="focus-ring rounded-md border border-line bg-paper px-2 py-1 text-xs font-semibold text-ink/85">
          Open ticker intelligence
        </Link>
      </div>
    </div>
  );
}

function JobRow({ job }: { job: JobRecord }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-sm font-semibold text-ink">{job.id}</p>
          <p className="text-xs text-ink/60">{job.inputSummary}</p>
        </div>
        <Badge tone={job.state === "completed" ? "good" : job.state === "failed" ? "bad" : job.state === "running" ? "info" : "warn"}>{job.state}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/55">
        <Clock3 className="h-3.5 w-3.5" />
        <span>Queued {formatTime(job.queuedAt)}</span>
        {job.completedAt ? <span>Completed {formatTime(job.completedAt)}</span> : null}
      </div>
    </div>
  );
}

function Detail({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "bad" }) {
  return (
    <div className={cn("rounded-md border border-line bg-fog/70 px-3 py-2", tone === "bad" ? "border-coral/30" : "")}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/55">{label}</p>
      <p className={cn("mt-1 break-words font-semibold", tone === "bad" ? "text-coral" : "text-ink")}>{value}</p>
    </div>
  );
}

function signalTone(signal: ScannerSignal): "good" | "warn" | "bad" | "neutral" | "info" {
  if (signal === "momentum_up" || signal === "mean_reversion_up") return "good";
  if (signal === "momentum_down") return "warn";
  if (signal === "mean_reversion_down") return "bad";
  return "neutral";
}

function buildReviewHref(candidate: ScannerCandidate, promotion: ScannerCandidatePromotion | null) {
  const source = promotion?.signalId ? "alpha" : "scanner";
  const params = new URLSearchParams({
    source,
    ticker: candidate.ticker,
    assetClass: "Equities",
    timeHorizon: "2-6 weeks",
    expression: "Long via equity",
    thesis: candidate.thesisSuggestion,
    sourcePointer: `scanner:${candidate.ticker}:${candidate.signal}:${candidate.scannedAt}`
  });

  if (promotion?.signalId) {
    params.set("alphaType", "signal");
    params.set("signalId", promotion.signalId);
    params.set("alphaSignalVersion", String(promotion.signalVersion ?? 1));
    params.set("hypothesisId", promotion.hypothesisId ?? "");
    params.set("alphaTitle", `${candidate.ticker} ${candidate.signal.replace(/_/g, " ")}`);
    params.set("alphaSignalFamily", candidate.signal.startsWith("momentum") ? "momentum" : candidate.signal.startsWith("mean_reversion") ? "mean_reversion" : "custom");
    params.set("alphaFormula", `scanner:${candidate.signal}`);
  }

  return `/review/new?${params.toString()}`;
}

function scannerPromotionKey(ticker: string, signal: string): string {
  return `${ticker.trim().toUpperCase()}::${signal.trim().toLowerCase()}`;
}

function promotionLabel(status: ScannerCandidatePromotion["status"]): string {
  switch (status) {
    case "alpha_created":
      return "Alpha created";
    case "signal_linked":
      return "Signal linked";
    case "review_linked":
      return "Review linked";
    case "validation_pending":
      return "Validation pending";
    case "validation_passed":
      return "Validation passed";
    case "active_candidate":
      return "Active candidate";
    case "constrained":
      return "Constrained";
    case "retired":
      return "Retired";
    default:
      return "Hypothesis";
  }
}

function promotionTone(status: ScannerCandidatePromotion["status"]): "good" | "warn" | "bad" | "neutral" | "info" {
  if (status === "validation_passed" || status === "active_candidate") return "good";
  if (status === "validation_pending" || status === "review_linked") return "info";
  if (status === "constrained") return "warn";
  if (status === "retired") return "bad";
  return "neutral";
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatCompact(value: number) {
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}
