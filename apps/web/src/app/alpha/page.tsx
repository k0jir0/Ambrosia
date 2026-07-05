"use client";

import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";

export default function AlphaPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading alpha surfaces...");
  const [hypotheses, setHypotheses] = useState<Array<Record<string, unknown>>>([]);
  const [signals, setSignals] = useState<Array<Record<string, unknown>>>([]);

  async function load() {
    setStatus("loading");
    const [alpha, signal] = await Promise.all([fetchControlPlane("/alpha/hypotheses"), fetchControlPlane("/signals")]);

    if (!alpha.ok || !signal.ok) {
      const current = mapStatus(Math.max(alpha.status, signal.status), null);
      setStatus(current);
      setMessage(alpha.message || signal.message || "Alpha endpoints are unavailable.");
      return;
    }

    const alphaItems = Array.isArray(alpha.data) ? (alpha.data as Array<Record<string, unknown>>) : [];
    const signalItems = Array.isArray(signal.data) ? (signal.data as Array<Record<string, unknown>>) : [];
    setHypotheses(alphaItems);
    setSignals(signalItems);
    setStatus(alphaItems.length === 0 && signalItems.length === 0 ? "empty" : "success");
    setMessage("Alpha data loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Alpha Lab" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Alpha Lab" />
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
          Track alpha hypotheses and signal lifecycle so research posture remains measurable and review-linked.
        </p>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Hypotheses" title="Recent alpha objects" />
        <ul className="mt-3 space-y-2 text-sm">
          {hypotheses.slice(0, 5).map((item) => (
            <li key={textOrFallback(item.hypothesisId)} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              <span className="font-semibold text-ink">{textOrFallback(item.title)}</span>
              <span className="ml-2 text-ink/70">{textOrFallback(item.signalFamily)}</span>
            </li>
          ))}
          {hypotheses.length === 0 ? <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-2 text-ink/60">No hypotheses available.</li> : null}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Signals" title="Signal inventory" />
        <ul className="mt-3 space-y-2 text-sm">
          {signals.slice(0, 5).map((item) => (
            <li key={textOrFallback(item.signalId)} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              <span className="font-semibold text-ink">{textOrFallback(item.name)}</span>
              <span className="ml-2 text-ink/70">{textOrFallback(item.formula)}</span>
            </li>
          ))}
          {signals.length === 0 ? <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-2 text-ink/60">No signals available.</li> : null}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="How to use" title="Alpha module intent" />
        <ul className="mt-3 space-y-2 text-sm text-ink/80">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Create hypotheses as structured objects, not narrative notes.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Link each signal to validation gates and cost assumptions.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Track decay to downgrade or recalibrate before confidence drifts.</li>
        </ul>
      </Panel>
    </div>
  );
}
