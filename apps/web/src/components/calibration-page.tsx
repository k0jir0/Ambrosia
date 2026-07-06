"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getApiBaseUrl } from "@/lib/api";
import { Badge, Panel, SectionTitle } from "./ui";

type FeedbackOutcome = "won" | "lost" | "whipsaw" | "invalidated" | "no_setup" | "partial";

type FeedbackRecord = {
  id: string;
  packet_id: string;
  decision_state: string;
  confidence: number;
  ticker: string;
  asset_class: string;
  time_horizon: string;
  outcome_date: string;
  outcome: FeedbackOutcome;
  pnl: number | null;
  notes: string;
  recorded_at: string;
  recorded_by?: string;
};

type CalibrationSummary = {
  total_decisions: number;
  overall_accuracy: number;
  total_alerts: number;
  over_confident_count: number;
  under_confident_count: number;
  well_calibrated_count: number;
};

type CalibrationAlert = {
  id: string;
  ticker: string;
  asset_class: string;
  time_horizon: string;
  confidence_band: string;
  alert_type: "over-confident" | "under-confident";
  target_accuracy: number;
  actual_accuracy: number;
  calibration_error: number;
  decision_count: number;
  severity: "info" | "warning" | "critical";
  generated_at: string;
};

type MetricsBoard = {
  review_validity?: MetricObject;
  packet_integrity?: MetricObject;
  data_quality?: MetricObject;
  agent_consensus?: MetricObject;
  backtest_validity?: MetricObject;
  risk_estimate?: MetricObject;
  confidence_calibration?: MetricObject;
  overall_status?: string;
  computed_at?: string;
};

type MetricObject = Record<string, number | string | boolean | Record<string, unknown> | null | undefined>;

type BandRow = {
  band: string;
  target: number;
  accuracy: number;
  decisions: number;
  wins: number;
  partials: number;
  losses: number;
  gap: number;
  avgReturn: number | null;
  status: "calibrated" | "conservative" | "over-confident";
};

type TrendRow = {
  week: string;
  accuracy: number;
  calibrationScore: number;
  decisions: number;
};

type CohortRow = {
  name: string;
  detail: string;
  decisions: number;
  accuracy: number;
  avgConfidence: number;
  calibrationGap: number;
  avgReturn: number | null;
};

type HealthMetric = {
  label: string;
  value: string;
  target: string;
  status: "good" | "warn" | "bad" | "neutral";
};

type CalibrationDashboardData = {
  source: "live" | "fixture";
  sourceLabel: string;
  message: string;
  asOf: string;
  totalDecisions: number;
  overallAccuracy: number;
  calibrationQuality: number;
  averageReturn: number | null;
  records: FeedbackRecord[];
  bands: BandRow[];
  trend: TrendRow[];
  cohorts: CohortRow[];
  alerts: CalibrationAlert[];
  health: HealthMetric[];
};

const EMPTY_SUMMARY: CalibrationSummary = {
  total_decisions: 0,
  overall_accuracy: 0,
  total_alerts: 0,
  over_confident_count: 0,
  under_confident_count: 0,
  well_calibrated_count: 0
};

const STABLE_CALIBRATION_AS_OF = "2026-07-03T16:20:00";

const SEEDED_RECORDS: FeedbackRecord[] = [
  {
    id: "model-eval-001",
    packet_id: "PKT-20260628-SPY-001",
    decision_state: "watch",
    confidence: 64,
    ticker: "SPY",
    asset_class: "ETF",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-07-03",
    outcome: "won",
    pnl: 1.1,
    notes: "Breadth confirmation arrived after the first pullback.",
    recorded_at: "2026-07-03T16:10:00"
  },
  {
    id: "model-eval-002",
    packet_id: "PKT-20260627-QQQ-001",
    decision_state: "pursue",
    confidence: 76,
    ticker: "QQQ",
    asset_class: "ETF",
    time_horizon: "1-3 weeks",
    outcome_date: "2026-07-02",
    outcome: "partial",
    pnl: 0.6,
    notes: "Direction right, but follow-through faded at resistance.",
    recorded_at: "2026-07-02T15:40:00"
  },
  {
    id: "model-eval-003",
    packet_id: "PKT-20260626-NVDA-001",
    decision_state: "watch",
    confidence: 69,
    ticker: "NVDA",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    outcome_date: "2026-07-01",
    outcome: "lost",
    pnl: -1.4,
    notes: "Momentum signal failed after semis reversed.",
    recorded_at: "2026-07-01T16:05:00"
  },
  {
    id: "model-eval-004",
    packet_id: "PKT-20260624-AAPL-001",
    decision_state: "watch",
    confidence: 58,
    ticker: "AAPL",
    asset_class: "Stock",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-30",
    outcome: "won",
    pnl: 1.9,
    notes: "Base breakout confirmed with volume expansion.",
    recorded_at: "2026-06-30T16:00:00"
  },
  {
    id: "model-eval-005",
    packet_id: "PKT-20260621-TSLA-001",
    decision_state: "reject",
    confidence: 52,
    ticker: "TSLA",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    outcome_date: "2026-06-27",
    outcome: "won",
    pnl: 0.8,
    notes: "Avoided a false breakout after volatility expanded.",
    recorded_at: "2026-06-27T15:35:00"
  },
  {
    id: "model-eval-006",
    packet_id: "PKT-20260620-META-001",
    decision_state: "pursue",
    confidence: 83,
    ticker: "META",
    asset_class: "Stock",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-26",
    outcome: "won",
    pnl: 2.4,
    notes: "Ad-growth thesis held and relative strength improved.",
    recorded_at: "2026-06-26T15:55:00"
  },
  {
    id: "model-eval-007",
    packet_id: "PKT-20260618-IWM-001",
    decision_state: "watch",
    confidence: 61,
    ticker: "IWM",
    asset_class: "ETF",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-25",
    outcome: "lost",
    pnl: -0.9,
    notes: "Small-cap breadth failed to confirm.",
    recorded_at: "2026-06-25T16:15:00"
  },
  {
    id: "model-eval-008",
    packet_id: "PKT-20260614-TLT-001",
    decision_state: "watch",
    confidence: 57,
    ticker: "TLT",
    asset_class: "Rates",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-21",
    outcome: "partial",
    pnl: 0.3,
    notes: "Duration bid appeared briefly, then reversed.",
    recorded_at: "2026-06-21T15:45:00"
  },
  {
    id: "model-eval-009",
    packet_id: "PKT-20260612-MSFT-001",
    decision_state: "pursue",
    confidence: 88,
    ticker: "MSFT",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    outcome_date: "2026-06-19",
    outcome: "won",
    pnl: 1.7,
    notes: "High-quality trend continued after risk checks passed.",
    recorded_at: "2026-06-19T16:05:00"
  },
  {
    id: "model-eval-010",
    packet_id: "PKT-20260608-AMD-001",
    decision_state: "watch",
    confidence: 73,
    ticker: "AMD",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    outcome_date: "2026-06-17",
    outcome: "whipsaw",
    pnl: -1.1,
    notes: "Initial breakout failed after a gap reversal.",
    recorded_at: "2026-06-17T16:20:00"
  },
  {
    id: "model-eval-011",
    packet_id: "PKT-20260605-XLF-001",
    decision_state: "pursue",
    confidence: 81,
    ticker: "XLF",
    asset_class: "ETF",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-14",
    outcome: "won",
    pnl: 1.3,
    notes: "Yield curve impulse supported financials.",
    recorded_at: "2026-06-14T15:50:00"
  },
  {
    id: "model-eval-012",
    packet_id: "PKT-20260603-XBI-001",
    decision_state: "watch",
    confidence: 66,
    ticker: "XBI",
    asset_class: "ETF",
    time_horizon: "2-6 weeks",
    outcome_date: "2026-06-12",
    outcome: "lost",
    pnl: -1.8,
    notes: "Risk appetite narrowed; setup invalidated.",
    recorded_at: "2026-06-12T15:30:00"
  }
];

const SEEDED_ALERTS: CalibrationAlert[] = [
  {
    id: "fixture-alert-001",
    ticker: "NVDA",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    confidence_band: "60-70%",
    alert_type: "over-confident",
    target_accuracy: 0.65,
    actual_accuracy: 0.5,
    calibration_error: 0.15,
    decision_count: 4,
    severity: "warning",
    generated_at: "2026-07-03T16:20:00"
  },
  {
    id: "fixture-alert-002",
    ticker: "MSFT",
    asset_class: "Stock",
    time_horizon: "1-3 weeks",
    confidence_band: "80-90%",
    alert_type: "under-confident",
    target_accuracy: 0.85,
    actual_accuracy: 1.0,
    calibration_error: 0.15,
    decision_count: 3,
    severity: "info",
    generated_at: "2026-07-03T16:20:00"
  }
];

export function CalibrationPage() {
  const [data, setData] = useState<CalibrationDashboardData>(() =>
    buildDashboardData({
      records: SEEDED_RECORDS,
      alerts: SEEDED_ALERTS,
      summary: EMPTY_SUMMARY,
      metrics: null,
      source: "fixture",
      message: "Seeded model-evaluation fixture shown until staging records settled outcomes."
    })
  );
  const [loading, setLoading] = useState(false);

  async function loadCalibrationData() {
    const apiBaseUrl = getApiBaseUrl();
    if (!apiBaseUrl) {
      setData(
        buildDashboardData({
          records: SEEDED_RECORDS,
          alerts: SEEDED_ALERTS,
          summary: EMPTY_SUMMARY,
          metrics: null,
          source: "fixture",
          message: "API base URL is unavailable; showing seeded model-evaluation fixture."
        })
      );
      return;
    }

    setLoading(true);
    try {
      const [summary, records, warningAlerts, criticalAlerts, metrics] = await Promise.all([
        fetchJson<CalibrationSummary>(`${apiBaseUrl}/feedback/calibration/summary`),
        fetchJson<FeedbackRecord[]>(`${apiBaseUrl}/feedback/records?limit=500`),
        fetchJson<CalibrationAlert[]>(`${apiBaseUrl}/feedback/calibration/alerts?severity=warning`),
        fetchJson<CalibrationAlert[]>(`${apiBaseUrl}/feedback/calibration/alerts?severity=critical`),
        fetchJson<MetricsBoard>(`${apiBaseUrl}/metrics`)
      ]);

      const liveRecords = Array.isArray(records) ? records : [];
      const liveSummary = summary ?? EMPTY_SUMMARY;
      const liveAlerts = [...(warningAlerts ?? []), ...(criticalAlerts ?? [])];

      if (liveRecords.length === 0 && liveSummary.total_decisions === 0) {
        setData(
          buildDashboardData({
            records: SEEDED_RECORDS,
            alerts: SEEDED_ALERTS,
            summary: liveSummary,
            metrics,
            source: "fixture",
            message: "Staging feedback store is empty; seeded model-evaluation fixture is shown."
          })
        );
        return;
      }

      setData(
        buildDashboardData({
          records: liveRecords,
          alerts: liveAlerts,
          summary: liveSummary,
          metrics,
          source: "live",
          message: "Live feedback records from the Ambrosia calibration API."
        })
      );
    } catch {
      setData(
        buildDashboardData({
          records: SEEDED_RECORDS,
          alerts: SEEDED_ALERTS,
          summary: EMPTY_SUMMARY,
          metrics: null,
          source: "fixture",
          message: "Calibration API unavailable; showing seeded model-evaluation fixture."
        })
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCalibrationData();
  }, []);

  const recentRecords = useMemo(
    () =>
      [...data.records]
        .sort((a, b) => getTime(b.outcome_date || b.recorded_at) - getTime(a.outcome_date || a.recorded_at))
        .slice(0, 8),
    [data.records]
  );

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <SectionTitle eyebrow="Calibration" title="Model outcome calibration" />
            <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">{data.message}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.source === "live" ? "good" : "warn"}>{data.sourceLabel}</Badge>
            <button
              type="button"
              onClick={() => void loadCalibrationData()}
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-ink/80"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </Panel>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard title="Decisions Scored" value={String(data.totalDecisions)} target="min 30" tone={data.totalDecisions >= 30 ? "good" : "warn"} />
        <MetricCard title="Outcome Accuracy" value={`${data.overallAccuracy}%`} target="68%" tone={data.overallAccuracy >= 68 ? "good" : "warn"} />
        <MetricCard title="Calibration Quality" value={`${data.calibrationQuality}%`} target="75%" tone={data.calibrationQuality >= 75 ? "good" : "warn"} />
        <MetricCard title="Avg Realized Return" value={formatReturn(data.averageReturn)} target="+0.6%" tone={(data.averageReturn ?? 0) >= 0.6 ? "good" : "warn"} />
      </section>

      <Panel className="p-5">
        <SectionTitle eyebrow="Confidence Bands" title="Actual accuracy vs stated confidence" />
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.bands}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
              <XAxis dataKey="band" stroke="#9db2bf" />
              <YAxis stroke="#9db2bf" domain={[0, 100]} />
              <Tooltip formatter={(value) => `${value}%`} />
              <Bar dataKey="accuracy" name="Actual accuracy" fill="#38c7b6" radius={[6, 6, 0, 0]} />
              <Line type="monotone" dataKey="target" name="Target confidence" stroke="#f2b84b" strokeWidth={2} dot={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 grid gap-2 text-xs md:grid-cols-2 xl:grid-cols-3">
          {data.bands.map((band) => (
            <div key={band.band} className="rounded-md border border-line bg-fog/70 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-semibold">{band.band}%</span>
                <Badge tone={band.status === "calibrated" ? "good" : band.status === "conservative" ? "info" : "warn"}>{band.status}</Badge>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-ink/70">
                <span>N {band.decisions}</span>
                <span>Accuracy {band.accuracy}%</span>
                <span>Target {band.target}%</span>
                <span>Gap {formatSignedPercent(band.gap)}</span>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-5">
          <SectionTitle eyebrow="Trend" title="Calibration quality over time" />
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                <XAxis dataKey="week" stroke="#9db2bf" />
                <YAxis stroke="#9db2bf" domain={[40, 100]} />
                <Tooltip formatter={(value, name) => (name === "decisions" ? value : `${value}%`)} />
                <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke="#38c7b6" strokeWidth={2} />
                <Line type="monotone" dataKey="calibrationScore" name="Calibration quality" stroke="#9f8cff" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel className="p-5">
          <SectionTitle eyebrow="Cohorts" title="Performance by decision cohort" />
          <div className="mt-4 space-y-3">
            {data.cohorts.map((cohort) => (
              <div key={`${cohort.name}-${cohort.detail}`} className="rounded-md border border-line bg-fog/70 p-3 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-ink">{cohort.name}</p>
                    <p className="text-xs text-ink/60">{cohort.detail}</p>
                  </div>
                  <Badge tone={cohort.calibrationGap <= 5 ? "good" : cohort.calibrationGap <= 10 ? "warn" : "bad"}>
                    gap {cohort.calibrationGap}%
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-4">
                  <span>N {cohort.decisions}</span>
                  <span>Accuracy {cohort.accuracy}%</span>
                  <span>Avg conf {cohort.avgConfidence}%</span>
                  <span>{formatReturn(cohort.avgReturn)}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-5">
          <SectionTitle eyebrow="Health" title="Operational calibration metrics" />
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.health.map((metric) => (
              <div key={metric.label} className="rounded-md border border-line bg-fog/70 p-3 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-ink/65">{metric.label}</p>
                    <p className="mt-1 font-semibold text-ink">{metric.value}</p>
                  </div>
                  <Badge tone={metric.status}>{metric.target}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-5">
          <SectionTitle eyebrow="Alerts" title="Calibration watchlist" />
          <div className="mt-4 space-y-2">
            {data.alerts.length === 0 ? (
              <div className="rounded-md border border-line bg-fog/70 p-3 text-sm text-ink/70">No active calibration alerts.</div>
            ) : (
              data.alerts.slice(0, 6).map((alert) => (
                <div key={alert.id} className="rounded-md border border-line bg-fog/70 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink">
                      {alert.ticker} {alert.confidence_band}
                    </span>
                    <Badge tone={alert.severity === "critical" ? "bad" : alert.severity === "warning" ? "warn" : "info"}>{alert.alert_type}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-ink/70">
                    Actual {toPercent(alert.actual_accuracy)} vs target {toPercent(alert.target_accuracy)} across {alert.decision_count} decisions.
                  </p>
                </div>
              ))
            )}
          </div>
        </Panel>
      </section>

      <Panel className="p-5">
        <SectionTitle eyebrow="Recent Outcomes" title="Feedback records used in this view" />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[780px] border-separate border-spacing-0 text-sm">
            <thead>
              <tr className="text-left text-ink/65">
                <th className="border-b border-line px-3 py-2">Outcome Date</th>
                <th className="border-b border-line px-3 py-2">Ticker</th>
                <th className="border-b border-line px-3 py-2">Decision</th>
                <th className="border-b border-line px-3 py-2">Confidence</th>
                <th className="border-b border-line px-3 py-2">Outcome</th>
                <th className="border-b border-line px-3 py-2">Return</th>
                <th className="border-b border-line px-3 py-2">Horizon</th>
              </tr>
            </thead>
            <tbody>
              {recentRecords.map((record) => (
                <tr key={record.id} className="hover:bg-white/5">
                  <td className="border-b border-line/70 px-3 py-3">{formatDate(record.outcome_date)}</td>
                  <td className="border-b border-line/70 px-3 py-3">
                    <Badge tone="info">{record.ticker}</Badge>
                  </td>
                  <td className="border-b border-line/70 px-3 py-3 uppercase">{record.decision_state}</td>
                  <td className="border-b border-line/70 px-3 py-3">{record.confidence}%</td>
                  <td className="border-b border-line/70 px-3 py-3">
                    <Badge tone={record.outcome === "won" ? "good" : record.outcome === "partial" ? "warn" : "bad"}>{record.outcome}</Badge>
                  </td>
                  <td className="border-b border-line/70 px-3 py-3">{formatReturn(record.pnl)}</td>
                  <td className="border-b border-line/70 px-3 py-3">{record.time_horizon}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

async function fetchJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url, { method: "GET" });
  if (!response.ok) return null;
  return (await response.json()) as T;
}

function buildDashboardData({
  records,
  alerts,
  summary,
  metrics,
  source,
  message
}: {
  records: FeedbackRecord[];
  alerts: CalibrationAlert[];
  summary: CalibrationSummary;
  metrics: MetricsBoard | null;
  source: "live" | "fixture";
  message: string;
}): CalibrationDashboardData {
  const bands = buildBands(records);
  const totalDecisions = records.length || summary.total_decisions;
  const overallAccuracy = records.length ? round(mean(records.map(outcomeScore)) * 100) : round(summary.overall_accuracy * 100);
  const calibrationQuality = buildCalibrationQuality(bands, metrics);
  const pnlValues = records.map((record) => record.pnl).filter((value): value is number => typeof value === "number");
  const averageReturn = pnlValues.length ? round(mean(pnlValues), 1) : null;

  return {
    source,
    sourceLabel: source === "live" ? "Live API data" : "Seeded fixture",
    message,
    asOf: source === "fixture" ? STABLE_CALIBRATION_AS_OF : new Date().toISOString(),
    totalDecisions,
    overallAccuracy,
    calibrationQuality,
    averageReturn,
    records,
    bands,
    trend: buildTrend(records),
    cohorts: buildCohorts(records),
    alerts: alerts.length ? alerts : buildAlertsFromBands(bands, source === "fixture" ? STABLE_CALIBRATION_AS_OF : undefined),
    health: buildHealthMetrics(metrics, bands, totalDecisions)
  };
}

function buildBands(records: FeedbackRecord[]): BandRow[] {
  const grouped = new Map<string, FeedbackRecord[]>();

  records.forEach((record) => {
    const band = confidenceBand(record.confidence);
    grouped.set(band, [...(grouped.get(band) ?? []), record]);
  });

  const rows = Array.from(grouped.entries())
    .map(([band, bandRecords]) => {
      const [low, high] = band.split("-").map(Number);
      const target = high === 100 ? 95 : low + 5;
      const accuracy = round(mean(bandRecords.map(outcomeScore)) * 100);
      const wins = bandRecords.filter((record) => record.outcome === "won").length;
      const partials = bandRecords.filter((record) => record.outcome === "partial").length;
      const losses = bandRecords.length - wins - partials;
      const gap = round(accuracy - target);
      const returns = bandRecords.map((record) => record.pnl).filter((value): value is number => typeof value === "number");

      return {
        band,
        target,
        accuracy,
        decisions: bandRecords.length,
        wins,
        partials,
        losses,
        gap,
        avgReturn: returns.length ? round(mean(returns), 1) : null,
        status: Math.abs(gap) <= 5 ? "calibrated" : gap > 5 ? "conservative" : "over-confident"
      } satisfies BandRow;
    })
    .sort((a, b) => Number(a.band.split("-")[0]) - Number(b.band.split("-")[0]));

  return rows.length ? rows : [{ band: "60-70", target: 65, accuracy: 0, decisions: 0, wins: 0, partials: 0, losses: 0, gap: -65, avgReturn: null, status: "over-confident" }];
}

function buildTrend(records: FeedbackRecord[]): TrendRow[] {
  const sorted = [...records].sort((a, b) => getTime(a.outcome_date || a.recorded_at) - getTime(b.outcome_date || b.recorded_at));
  const groups = new Map<string, FeedbackRecord[]>();

  sorted.forEach((record) => {
    const date = new Date(record.outcome_date || record.recorded_at);
    const key = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    groups.set(key, [...(groups.get(key) ?? []), record]);
  });

  return Array.from(groups.entries()).map(([week, group]) => {
    const accuracy = round(mean(group.map(outcomeScore)) * 100);
    const calibrationError = mean(group.map((record) => Math.abs(outcomeScore(record) * 100 - record.confidence)));
    return {
      week,
      accuracy,
      calibrationScore: round(Math.max(0, 100 - calibrationError)),
      decisions: group.length
    };
  });
}

function buildCohorts(records: FeedbackRecord[]): CohortRow[] {
  const groups = new Map<string, FeedbackRecord[]>();

  records.forEach((record) => {
    const key = `${record.asset_class}|${record.time_horizon}`;
    groups.set(key, [...(groups.get(key) ?? []), record]);
  });

  return Array.from(groups.entries())
    .map(([key, group]) => {
      const [assetClass, horizon] = key.split("|");
      const accuracy = round(mean(group.map(outcomeScore)) * 100);
      const avgConfidence = round(mean(group.map((record) => record.confidence)));
      const returns = group.map((record) => record.pnl).filter((value): value is number => typeof value === "number");
      const tickers = Array.from(new Set(group.map((record) => record.ticker))).slice(0, 4).join(", ");

      return {
        name: `${assetClass} - ${horizon}`,
        detail: tickers,
        decisions: group.length,
        accuracy,
        avgConfidence,
        calibrationGap: Math.abs(round(accuracy - avgConfidence)),
        avgReturn: returns.length ? round(mean(returns), 1) : null
      };
    })
    .sort((a, b) => b.decisions - a.decisions)
    .slice(0, 5);
}

function buildAlertsFromBands(bands: BandRow[], generatedAt = new Date().toISOString()): CalibrationAlert[] {
  return bands
    .filter((band) => band.decisions >= 3 && Math.abs(band.gap) >= 10)
    .map((band, index) => ({
      id: `derived-alert-${band.band}-${index}`,
      ticker: "Portfolio",
      asset_class: "Mixed",
      time_horizon: "Mixed",
      confidence_band: `${band.band}%`,
      alert_type: band.gap < 0 ? "over-confident" : "under-confident",
      target_accuracy: band.target / 100,
      actual_accuracy: band.accuracy / 100,
      calibration_error: Math.abs(band.gap) / 100,
      decision_count: band.decisions,
      severity: Math.abs(band.gap) >= 15 ? "critical" : "warning",
      generated_at: generatedAt
    }));
}

function buildHealthMetrics(metrics: MetricsBoard | null, bands: BandRow[], totalDecisions: number): HealthMetric[] {
  if (!metrics) {
    return [
      { label: "Feedback sample", value: `${totalDecisions} decisions`, target: "target 30", status: totalDecisions >= 30 ? "good" : "warn" },
      { label: "Confidence bands", value: `${bands.length} populated`, target: "target 4", status: bands.length >= 4 ? "good" : "warn" },
      { label: "Calibration quality", value: `${buildCalibrationQuality(bands, null)}%`, target: "target 75%", status: buildCalibrationQuality(bands, null) >= 75 ? "good" : "warn" },
      { label: "Outcome coverage", value: "seeded", target: "fixture", status: "neutral" }
    ];
  }

  return [
    metricFromBoard("Review validity", metrics.review_validity, "conversion_rate", "target"),
    metricFromBoard("Packet integrity", metrics.packet_integrity, "integrity_score", "target"),
    metricFromBoard("Data quality", metrics.data_quality, "quality_score", "target"),
    metricFromBoard("Agent consensus", metrics.agent_consensus, "avg_consensus_score", "target"),
    metricFromBoard("Risk estimate", metrics.risk_estimate, "estimate_accuracy", "target"),
    metricFromBoard("Confidence calibration", metrics.confidence_calibration, "calibration_score", "target")
  ];
}

function metricFromBoard(label: string, metric: MetricObject | undefined, valueKey: string, targetKey: string): HealthMetric {
  const value = toNumber(metric?.[valueKey]);
  const target = toNumber(metric?.[targetKey]);
  const status = String(metric?.status ?? "");

  return {
    label,
    value: value === null ? "n/a" : `${round(value * 100)}%`,
    target: target === null ? "target n/a" : `target ${round(target * 100)}%`,
    status: status === "critical" ? "bad" : status === "warning" ? "warn" : status === "ok" ? "good" : "neutral"
  };
}

function buildCalibrationQuality(bands: BandRow[], metrics: MetricsBoard | null): number {
  const metricScore = toNumber(metrics?.confidence_calibration?.calibration_score);
  if (metricScore !== null && metricScore > 0) return round(metricScore * 100);

  const weightedDecisions = bands.reduce((sum, band) => sum + band.decisions, 0);
  if (weightedDecisions === 0) return 0;

  const weightedError = bands.reduce((sum, band) => sum + Math.abs(band.gap) * band.decisions, 0) / weightedDecisions;
  return round(Math.max(0, 100 - weightedError));
}

function confidenceBand(confidence: number): string {
  const low = Math.min(90, Math.max(0, Math.floor(confidence / 10) * 10));
  return `${low}-${low + 10}`;
}

function outcomeScore(record: FeedbackRecord): number {
  if (record.outcome === "won") return 1;
  if (record.outcome === "partial") return 0.5;
  return 0;
}

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function round(value: number, digits = 0): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function toNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toPercent(value: number): string {
  return `${round(value * 100)}%`;
}

function formatSignedPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value}%`;
}

function formatReturn(value: number | null): string {
  if (value === null) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "n/a";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function getTime(value: string): number {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function MetricCard({
  title,
  value,
  target,
  tone
}: {
  title: string;
  value: string;
  target: string;
  tone: "good" | "warn";
}) {
  return (
    <Panel className="p-5">
      <SectionTitle eyebrow="Scorecard" title={title} />
      <p className={`mt-3 text-2xl font-semibold ${tone === "good" ? "text-teal" : "text-amber"}`}>{value}</p>
      <p className="mt-1 text-sm text-ink/70">Target: {target}</p>
    </Panel>
  );
}
