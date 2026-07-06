"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel, SectionTitle, Badge } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, numberOrFallback, textOrFallback } from "@/lib/index84-control-plane";

export default function SignalsPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading signals...");
  const [signals, setSignals] = useState<Array<Record<string, unknown>>>([]);

  async function load() {
    setStatus("loading");
    const response = await fetchControlPlane("/signals");
    if (!response.ok) {
      const current = mapStatus(response.status, response.data);
      setStatus(current);
      setMessage(response.message || "Signals endpoint is unavailable.");
      return;
    }

    const items = Array.isArray(response.data) ? (response.data as Array<Record<string, unknown>>) : [];
    setSignals(items);
    setStatus(items.length === 0 ? "empty" : "success");
    setMessage(items.length === 0 ? "No signals available yet." : "Signals loaded.");
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
              onClick={() => void load()}
              className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
            >
              Refresh
            </button>
          </div>
        </div>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

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
