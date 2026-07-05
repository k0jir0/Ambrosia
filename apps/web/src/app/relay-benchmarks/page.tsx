"use client";

import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";

export default function RelayBenchmarksPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading relay scorecard...");
  const [scorecard, setScorecard] = useState<Record<string, unknown> | null>(null);

  async function load() {
    setStatus("loading");
    const result = await fetchControlPlane("/relay/scorecard");
    if (!result.ok) {
      const current = mapStatus(result.status, result.data);
      setStatus(current);
      setMessage(result.message || "Relay endpoints are unavailable.");
      return;
    }
    setScorecard((result.data as Record<string, unknown>) || null);
    setStatus("success");
    setMessage("Relay scorecard loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Relay + Benchmarks" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Relay + Benchmarks" />
          <RouteStatusBadge status={status} />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink/75">
          OpenAI-compatible relay posture and benchmark evidence status for FinanceBench, FinQA, and TAT-QA operating loops.
        </p>
      </Panel>

      {status === "forbidden" || status === "error" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Scorecard" title="Relay quality metrics" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Runs" value={textOrFallback(scorecard?.runs)} />
          <Metric label="Accuracy" value={textOrFallback(scorecard?.accuracy)} />
          <Metric label="Grounding pass rate" value={textOrFallback(scorecard?.groundingPassRate)} />
          <Metric label="Calc verifier pass rate" value={textOrFallback(scorecard?.calculationVerificationPassRate)} />
        </div>
      </Panel>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3 text-sm">
      <p className="text-ink/70">{label}</p>
      <p className="mt-1 font-semibold text-ink">{value}</p>
    </div>
  );
}
