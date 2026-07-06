"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, LoaderCircle, RefreshCw } from "lucide-react";
import { Panel, SectionTitle, Badge } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, numberOrFallback, textOrFallback } from "@/lib/index84-control-plane";
import { seedIndex97Signals } from "@/lib/api";

export default function SignalsPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading signals...");
  const [signals, setSignals] = useState<Array<Record<string, unknown>>>([]);
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [scorecard, setScorecard] = useState<Record<string, unknown> | null>(null);
  const [seeding, setSeeding] = useState(false);

  async function load() {
    setStatus("loading");
    const [response, metricsResponse, scorecardResponse] = await Promise.all([
      fetchControlPlane("/signals"),
      fetchControlPlane("/signals/program-metrics"),
      fetchControlPlane("/signals/quality-scorecard/weekly")
    ]);
    if (!response.ok) {
      const current = mapStatus(response.status, response.data);
      setStatus(current);
      setMessage(response.message || "Signals endpoint is unavailable.");
      setMetrics(metricsResponse.ok && isRecord(metricsResponse.data) ? metricsResponse.data : null);
      setScorecard(scorecardResponse.ok && isRecord(scorecardResponse.data) ? scorecardResponse.data : null);
      return;
    }

    const items = Array.isArray(response.data) ? (response.data as Array<Record<string, unknown>>) : [];
    setSignals(items);
    setMetrics(metricsResponse.ok && isRecord(metricsResponse.data) ? metricsResponse.data : null);
    setScorecard(scorecardResponse.ok && isRecord(scorecardResponse.data) ? scorecardResponse.data : null);
    setStatus(items.length === 0 ? "empty" : "success");
    setMessage(items.length === 0 ? "No signals available yet." : "Signals loaded.");
  }

  async function seedSignals() {
    setSeeding(true);
    setStatus("loading");
    try {
      const response = await seedIndex97Signals();
      setMessage(`Seeded ${numberOrFallback(response.signalsSeeded, "0")} lifecycle signals.`);
      await load();
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to seed Index97 signal inventory.");
    } finally {
      setSeeding(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Signals" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <SectionTitle eyebrow="Index84 Surface" title="Signals" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/75">
              Review signal inventory, lifecycle status, and promotion posture from a dedicated control-plane view.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button
              type="button"
              onClick={() => void seedSignals()}
              disabled={seeding}
              className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-3 py-1 text-xs font-semibold text-fog disabled:opacity-60"
            >
              {seeding ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
              Seed lifecycle data
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </div>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)]">
        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Program" title="Lifecycle coverage" />
            <Badge tone="neutral">{numberOrFallback(metrics?.totalSignals, "0")} signals</Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-4">
            <Metric label="Validated" value={numberOrFallback(metrics?.validatedSignals, "0")} detail={`${numberOrFallback(metrics?.validatedSignalsPct, "0")}%`} />
            <Metric label="Active" value={numberOrFallback(metrics?.promotedSignals, "0")} detail="candidates" />
            <Metric label="Linked" value={numberOrFallback(metrics?.linkedSignals, "0")} detail={`${numberOrFallback(metrics?.linkedSignalsPct, "0")}%`} />
            <Metric label="Outcomes" value={numberOrFallback(metrics?.recordedOutcomes, "0")} detail="closed" />
          </div>
        </Panel>

        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Weekly" title="Quality gates" />
            <Badge tone={allGatesPass(scorecard) ? "good" : "warn"}>{allGatesPass(scorecard) ? "pass" : "review"}</Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-ink/70">
            {qualityGateEntries(scorecard).map(([name, gate]) => (
              <div key={name} className="rounded-md border border-line bg-fog/70 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="capitalize">{name.replace(/([A-Z])/g, " $1")}</span>
                  <Badge tone={gateTone(gate.status)}>{textOrFallback(gate.status, "n/a")}</Badge>
                </div>
                <p className="mt-1 font-mono text-[11px] text-ink/55">
                  {numberOrFallback(gate.passed, "0")}/{numberOrFallback(gate.total, "0")}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Inventory" title="Signal list" />
          <Badge tone="neutral">{signals.length} total</Badge>
        </div>

        <ul className="mt-4 space-y-2">
          {signals.map((signal) => {
            const signalId = textOrFallback(signal.signalId);
            const statusValue = textOrFallback(signal.status, "hypothesis");
            return (
              <li key={signalId} className="rounded-md border border-line bg-fog/70 p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-sm font-semibold text-ink">{signalId}</p>
                    <p className="text-xs text-ink/65">{textOrFallback(signal.name)}</p>
                  </div>
                  <Badge tone={statusValue === "active_candidate" ? "good" : statusValue === "retired" ? "bad" : "info"}>{statusValue}</Badge>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-4">
                  <span>v{numberOrFallback(signal.activeVersion, "1")}</span>
                  <span>benchmark {textOrFallback(signal.benchmark)}</span>
                  <span>linked reviews {numberOrFallback(signal.linkedReviewCount, "0")}</span>
                  <span>latest {textOrFallback(signal.latestDecisionState, "pending")}</span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-ink/55 md:grid-cols-4">
                  <span>outcome {textOrFallback(signal.latestOutcomeQuality, "open")}</span>
                  <span>overrides {numberOrFallback(signal.overrideCount, "0")}</span>
                  <span>updated {formatDate(textOrFallback(signal.updatedAt, ""))}</span>
                  <span>cost {textOrFallback(signal.costModel)}</span>
                </div>
                <div className="mt-3">
                  <Link
                    href="/alpha"
                    className="focus-ring inline-flex rounded-md border border-line bg-paper px-2 py-1 text-xs font-semibold text-teal"
                  >
                    Open Alpha Lab
                  </Link>
                </div>
              </li>
            );
          })}
          {signals.length === 0 ? (
            <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-3 text-sm text-ink/60">No signals available.</li>
          ) : null}
        </ul>
      </Panel>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/50">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
      <p className="mt-1 text-[11px] text-ink/55">{detail}</p>
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function gateTone(status: unknown): "good" | "warn" | "bad" | "neutral" {
  if (status === "pass") return "good";
  if (status === "fail") return "bad";
  return "neutral";
}

function qualityGateEntries(scorecard: Record<string, unknown> | null) {
  const rawGates = scorecard?.gates;
  const gates = isRecord(rawGates) ? rawGates : {};
  return Object.entries(gates).map(([name, value]) => {
    const gate = isRecord(value) ? value : {};
    return [name, gate] as const;
  });
}

function allGatesPass(scorecard: Record<string, unknown> | null): boolean {
  const entries = qualityGateEntries(scorecard);
  return entries.length > 0 && entries.every(([, gate]) => gate.status === "pass");
}

function formatDate(value: string): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
