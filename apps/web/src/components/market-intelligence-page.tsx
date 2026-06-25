"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRightLeft, BarChart2, RefreshCw } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  ApiUnavailableError,
  getMarketSnapshot,
  getMarketTechnicals,
  getSentiment,
} from "@/lib/api";
import {
  buildCorrelationMatrix,
  buildEfficientFrontier,
  buildEquityCurve,
  buildOhlcSeries,
  buildRiskReturn,
  buildYieldCurve,
  summarizeTicker,
  withMovingAverages
} from "@/lib/market-intelligence";
import type { MarketSnapshot, SentimentData, TechnicalIndicators } from "@/lib/types";
import { Badge, Panel, SectionTitle, cn } from "./ui";

type Tab = "primary" | "analytics" | "macro" | "performance";
type PriceStyle = "candlestick" | "ohlc" | "line";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "primary", label: "Primary" },
  { id: "analytics", label: "Analytics" },
  { id: "macro", label: "Macro" },
  { id: "performance", label: "Performance" }
];

export function MarketIntelligencePage({ ticker, compare = [] }: { ticker: string; compare?: string[] }) {
  const [activeTab, setActiveTab] = useState<Tab>("primary");
  const [priceStyle, setPriceStyle] = useState<PriceStyle>("candlestick");
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [technicals, setTechnicals] = useState<TechnicalIndicators | null>(null);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [liveMode, setLiveMode] = useState<"live" | "fallback">("fallback");

  const baseSeries = useMemo(() => buildOhlcSeries(ticker, 72), [ticker]);
  const series = useMemo(() => withMovingAverages(baseSeries), [baseSeries]);
  const yieldCurve = useMemo(() => buildYieldCurve(ticker), [ticker]);
  const performance = useMemo(() => buildEquityCurve(baseSeries), [baseSeries]);
  const heatmap = useMemo(() => buildCorrelationMatrix(ticker), [ticker]);
  const riskReturn = useMemo(() => buildRiskReturn(ticker), [ticker]);
  const frontier = useMemo(() => buildEfficientFrontier(ticker), [ticker]);
  const summary = useMemo(() => summarizeTicker(ticker, series), [ticker, series]);
  const compareSymbols = useMemo(
    () => Array.from(new Set(compare.map((item) => item.trim().toUpperCase()).filter((item) => item && item !== ticker.toUpperCase()))).slice(0, 3),
    [compare, ticker]
  );
  const compareSeries = useMemo(() => compareSymbols.map((symbol) => ({ symbol, points: withMovingAverages(buildOhlcSeries(symbol, 72)) })), [compareSymbols]);
  const mergedLineSeries = useMemo(
    () =>
      series.map((point, index) => {
        const peers = compareSeries.reduce<Record<string, number>>((acc, peer) => {
          acc[`${peer.symbol}_close`] = peer.points[index]?.close ?? point.close;
          return acc;
        }, {});
        return { ...point, ...peers };
      }),
    [series, compareSeries]
  );

  const latest = series[series.length - 1];
  const prev = series[series.length - 2] ?? latest;
  const delta = (((latest.close - prev.close) / prev.close) * 100).toFixed(2);

  useEffect(() => {
    let cancelled = false;

    async function loadLive() {
      try {
        const [nextSnapshot, nextTechnicals, nextSentiment] = await Promise.all([
          getMarketSnapshot(ticker),
          getMarketTechnicals(ticker),
          getSentiment(ticker),
        ]);

        if (cancelled) return;
        setSnapshot(nextSnapshot);
        setTechnicals(nextTechnicals);
        setSentiment(nextSentiment);
        setLiveMode("live");
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiUnavailableError) {
          setLiveMode("fallback");
          return;
        }
        setLiveMode("fallback");
      }
    }

    void loadLive();

    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const displayPrice = snapshot?.price ?? latest.close;
  const displayDelta = snapshot ? (snapshot.priceChange24h * 100).toFixed(2) : delta;
  const providerBadge = snapshot ? `${snapshot.dataSource} ${snapshot.timestamp}` : "Simulated feed";

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Badge tone="info">{ticker.toUpperCase()}</Badge>
              <Badge tone={liveMode === "live" ? "good" : "warn"}>{liveMode === "live" ? "Live" : "Fallback"}</Badge>
              <Badge tone="neutral">{providerBadge}</Badge>
              {compare.length > 0 ? <Badge tone="warn">Compare: {compare.join(" · ")}</Badge> : null}
            </div>
            <h1 className="text-2xl font-semibold">{summary.headline}</h1>
            <p className="mt-2 max-w-4xl text-sm text-ink/75">{summary.line}</p>
          </div>
          <div className="rounded-md border border-line bg-fog/70 px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-wide text-ink/60">Last Price</p>
            <p className="text-2xl font-semibold">${displayPrice.toFixed(2)}</p>
            <p className={cn("text-sm", Number(displayDelta) >= 0 ? "text-teal" : "text-coral")}>{Number(displayDelta) >= 0 ? "+" : ""}{displayDelta}%</p>
          </div>
        </div>
      </Panel>

      <Panel className="p-3">
        <div className="flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "focus-ring rounded-md border px-3 py-1.5 text-sm",
                activeTab === tab.id ? "border-teal bg-teal/10 text-teal" : "border-line text-ink/70"
              )}
            >
              {tab.label}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2 text-xs text-ink/60">
            <RefreshCw className="h-3.5 w-3.5" />
            {liveMode === "live" ? "Live quote and sentiment connected" : "Using deterministic fallback market data"}
          </div>
        </div>
      </Panel>

      {activeTab === "primary" ? (
        <div className="grid gap-4 xl:grid-cols-3">
          <Panel className="p-4 xl:col-span-2">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <SectionTitle eyebrow="Price" title="Line, Candlestick, and OHLC" />
              <div className="flex gap-2 text-xs">
                {(["candlestick", "ohlc", "line"] as PriceStyle[]).map((style) => (
                  <button
                    key={style}
                    type="button"
                    className={cn("focus-ring rounded-md border px-2 py-1", priceStyle === style ? "border-teal text-teal" : "border-line text-ink/70")}
                    onClick={() => setPriceStyle(style)}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                {priceStyle === "line" ? (
                  <LineChart data={mergedLineSeries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                    <XAxis dataKey="label" hide />
                    <YAxis domain={["dataMin - 2", "dataMax + 2"]} />
                    <Tooltip />
                    <Line dataKey="close" stroke="#38c7b6" dot={false} strokeWidth={2} />
                    <Line dataKey="sma20" stroke="#a9a4ff" dot={false} strokeWidth={1.6} />
                    <Line dataKey="sma50" stroke="#f2b84b" dot={false} strokeWidth={1.3} />
                    {compareSeries.map((peer, idx) => (
                      <Line
                        key={peer.symbol}
                        dataKey={`${peer.symbol}_close`}
                        stroke={["#60a5fa", "#f97316", "#e879f9"][idx % 3]}
                        dot={false}
                        strokeWidth={1.4}
                        name={`${peer.symbol} close`}
                      />
                    ))}
                  </LineChart>
                ) : (
                  <ComposedChart data={series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                    <XAxis dataKey="label" hide />
                    <YAxis domain={["dataMin - 2", "dataMax + 2"]} />
                    <Tooltip />
                    <Legend />
                    <Line dataKey="high" stroke="#38c7b6" dot={false} strokeWidth={1.2} name={priceStyle === "candlestick" ? "wick high" : "high"} />
                    <Line dataKey="low" stroke="#ff7366" dot={false} strokeWidth={1.2} name={priceStyle === "candlestick" ? "wick low" : "low"} />
                    <Bar dataKey="close" fill="#38c7b6" name={priceStyle === "candlestick" ? "body close" : "close"} />
                    <Line dataKey="open" stroke="#a9a4ff" dot={false} strokeWidth={1.2} name="open" />
                  </ComposedChart>
                )}
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel className="p-4">
            <SectionTitle eyebrow="Intelligence" title="Technical and risk snapshot" />
            <div className="mt-3 space-y-2 text-sm">
              <Stat label="MA20" value={technicals?.movingAverage30 ? technicals.movingAverage30.toFixed(2) : latest.sma20.toFixed(2)} />
              <Stat label="MA50" value={technicals?.movingAverage50 ? technicals.movingAverage50.toFixed(2) : latest.sma50.toFixed(2)} />
              <Stat label="RSI" value={technicals?.rsi ? technicals.rsi.toFixed(1) : "N/A"} />
              <Stat label="Volume" value={snapshot?.volume24h ? Math.round(snapshot.volume24h).toLocaleString() : latest.volume.toLocaleString()} />
              <Stat label="Regime" value={technicals?.trend ? technicals.trend : latest.close > latest.sma50 ? "Trend above MA50" : "Below MA50"} />
              <Stat label="Sentiment" value={sentiment ? `${sentiment.sentiment} (${sentiment.overallScore.toFixed(2)})` : "N/A"} />
              <Stat label="Ticker Coherence" value="Active ticker synchronized" />
            </div>
          </Panel>

          <Panel className="p-4 xl:col-span-3">
            <SectionTitle eyebrow="Volume" title="Participation and momentum confirmation" />
            <div className="mt-3 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={series.slice(-36)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                  <XAxis dataKey="label" hide />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="volume" fill="#3b82f6" />
                  <Line dataKey="sma20" stroke="#f2b84b" dot={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      ) : null}

      {activeTab === "analytics" ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel className="p-4">
            <SectionTitle eyebrow="Correlation Heatmap" title="Ticker concentration and co-movement" />
            <Heatmap symbols={heatmap.symbols} values={heatmap.points} primary={ticker.toUpperCase()} />
          </Panel>

          <Panel className="p-4">
            <SectionTitle eyebrow="Risk-Return Scatter" title="Relative efficiency view" />
            <div className="mt-3 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                  <XAxis dataKey="risk" name="Risk" unit="%" type="number" />
                  <YAxis dataKey="ret" name="Return" unit="%" type="number" />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter data={riskReturn} fill="#38c7b6" />
                  <ReferenceLine x={18} stroke="#f2b84b" strokeDasharray="4 2" />
                  <ReferenceLine y={10} stroke="#a9a4ff" strokeDasharray="4 2" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel className="p-4 xl:col-span-2">
            <SectionTitle eyebrow="Efficient Frontier" title="Portfolio construction reference" />
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={frontier.curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                  <XAxis dataKey="risk" type="number" domain={["dataMin", "dataMax"]} />
                  <YAxis dataKey="ret" type="number" domain={["dataMin", "dataMax"]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="ret" stroke="#38c7b6" dot={false} strokeWidth={2} />
                  <ReferenceLine x={frontier.current.risk} stroke="#f2b84b" strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-ink/70">
              <span className="inline-flex items-center gap-1"><Activity className="h-3.5 w-3.5 text-teal" /> Max Sharpe: {frontier.maxSharpe.ret}% @ {frontier.maxSharpe.risk}% risk</span>
              <span className="inline-flex items-center gap-1"><ArrowRightLeft className="h-3.5 w-3.5 text-amber" /> Min Variance: {frontier.minVar.ret}% @ {frontier.minVar.risk}% risk</span>
            </div>
          </Panel>
        </div>
      ) : null}

      {activeTab === "macro" ? (
        <Panel className="p-4">
          <SectionTitle eyebrow="Yield Curve" title="Cross-asset macro regime" />
          <div className="mt-3 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={yieldCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                <XAxis dataKey="tenor" />
                <YAxis unit="%" />
                <Tooltip />
                <Line dataKey="today" stroke="#38c7b6" strokeWidth={2} dot />
                <Line dataKey="previous" stroke="#a9a4ff" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-3 text-sm text-ink/70">10Y-2Y slope: {(yieldCurve[3].today - yieldCurve[1].today).toFixed(2)}%. Lower slope generally pressures growth valuation multiples.</p>
        </Panel>
      ) : null}

      {activeTab === "performance" ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel className="p-4">
            <SectionTitle eyebrow="Equity Curve" title="Cumulative decision performance" />
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={performance.equity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                  <XAxis dataKey="label" hide />
                  <YAxis />
                  <Tooltip />
                  <Line dataKey="equity" stroke="#38c7b6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel className="p-4">
            <SectionTitle eyebrow="Drawdown" title="Peak-to-trough risk" />
            <div className="mt-3 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={performance.drawdown}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                  <XAxis dataKey="label" hide />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="drawdown" fill="#ff7366" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      ) : null}

      <Panel className="p-4 text-sm text-ink/70">
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-teal" />
          All core intelligence graphs are ticker-bound. Thesis ticker is pinned as primary in comparison mode.
        </div>
      </Panel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-line bg-fog/70 px-3 py-2">
      <span className="text-ink/70">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function Heatmap({ symbols, values, primary }: { symbols: string[]; values: Array<{ row: string; col: string; value: number }>; primary: string }) {
  const byKey = new Map(values.map((item) => [`${item.row}:${item.col}`, item.value]));

  return (
    <div className="mt-3 overflow-x-auto">
      <div className="grid min-w-[560px]" style={{ gridTemplateColumns: `140px repeat(${symbols.length}, minmax(80px, 1fr))` }}>
        <div />
        {symbols.map((symbol) => (
          <div key={`col-${symbol}`} className={cn("px-2 py-2 text-center text-xs font-semibold", symbol === primary ? "text-teal" : "text-ink/70")}>{symbol}</div>
        ))}

        {symbols.map((row) => (
          <div key={`row-${row}`} className="contents">
            <div key={`row-title-${row}`} className={cn("px-2 py-2 text-xs font-semibold", row === primary ? "text-teal" : "text-ink/70")}>{row}</div>
            {symbols.map((col) => {
              const value = byKey.get(`${row}:${col}`) ?? 0;
              return (
                <div
                  key={`${row}-${col}`}
                  className="m-0.5 rounded p-2 text-center text-xs"
                  style={{ backgroundColor: colorForCorrelation(value), color: Math.abs(value) > 0.65 ? "#101820" : "#edf7f4" }}
                  title={`${row}/${col}: ${value}`}
                >
                  {value.toFixed(2)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function colorForCorrelation(value: number) {
  const normalized = Math.max(-1, Math.min(1, value));
  if (normalized > 0.75) return "#38c7b6";
  if (normalized > 0.45) return "#7fd8cc";
  if (normalized > 0.1) return "#355362";
  if (normalized > -0.2) return "#2b3f4c";
  if (normalized > -0.5) return "#8c5560";
  return "#ff7366";
}
