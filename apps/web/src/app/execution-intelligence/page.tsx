"use client";

import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, numberOrFallback, textOrFallback } from "@/lib/index84-control-plane";

export default function ExecutionIntelligencePage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading warm-path events...");
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);

  async function load() {
    setStatus("loading");
    const warm = await fetchControlPlane("/execution/warm-path/events");
    if (!warm.ok) {
      const current = mapStatus(warm.status, warm.data);
      setStatus(current);
      setMessage(warm.message || "Execution intelligence endpoints are unavailable.");
      return;
    }
    const items = Array.isArray(warm.data) ? (warm.data as Array<Record<string, unknown>>) : [];
    setEvents(items);
    setStatus(items.length === 0 ? "empty" : "success");
    setMessage("Warm-path state loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Execution Intelligence" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Execution Intelligence" />
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button
              type="button"
              onClick={() => void load()}
              className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
            >
              Refresh module data
            </button>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink/75">
          Monitor warm-path events and execution diagnostics under human-supervised risk boundaries.
        </p>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Warm Path" title="Recent events" />
        <ul className="mt-3 space-y-2 text-sm">
          {events.slice(0, 8).map((event) => (
            <li key={textOrFallback(event.eventId)} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              <span className="font-semibold text-ink">{textOrFallback(event.eventType)}</span>
              <span className="ml-2 text-ink/70">{textOrFallback(event.ticker)}</span>
              <span className="ml-2 text-ink/70">latency {numberOrFallback(event.latencyMs)} ms</span>
            </li>
          ))}
          {events.length === 0 ? <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-2 text-ink/60">No warm-path events yet.</li> : null}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Diagnostics" title="Execution checks surfaced" />
        <ul className="mt-3 space-y-2 text-sm text-ink/80">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Latency and notional checks per warm-path event.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Kill-switch and risk-check pass/fail context.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Operator read path for pre-trade and post-fill diagnostics.</li>
        </ul>
      </Panel>
    </div>
  );
}
