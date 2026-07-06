"use client";

import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { getApiBaseUrl } from "@/lib/api";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";

export default function RelayBenchmarksPage() {
  const apiBaseUrl = getApiBaseUrl();
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading relay scorecard...");
  const [scorecard, setScorecard] = useState<Record<string, unknown> | null>(null);
  const [runningProbe, setRunningProbe] = useState(false);
  const [benchmarkRuns, setBenchmarkRuns] = useState<Record<string, Record<string, unknown> | null>>({
    "financebench-open-subset": null,
    "finqa-open-subset": null,
    "tatqa-open-subset": null
  });

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

  async function runRelayProbe() {
    if (!apiBaseUrl || runningProbe) return;
    setRunningProbe(true);
    setMessage("Running relay probe for benchmark evidence...");
    try {
      const response = await fetch(`${apiBaseUrl}/relay/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "What is Ambrosia relay benchmark posture?",
          benchmark: "financebench-open-subset",
          documents: ["Relay benchmark control-plane probe initiated from staging UI."]
        })
      });
      if (!response.ok) {
        throw new Error(`Probe failed with status ${response.status}`);
      }
      await load();
      setMessage("Relay probe completed and scorecard refreshed.");
    } catch {
      setMessage("Relay probe failed. Refresh and check relay API status.");
    } finally {
      setRunningProbe(false);
    }
  }

  async function runBenchmarkProbe(benchmark: "financebench-open-subset" | "finqa-open-subset" | "tatqa-open-subset") {
    if (!apiBaseUrl || runningProbe) return;
    setRunningProbe(true);
    setMessage(`Running ${benchmark} relay probe...`);
    try {
      const response = await fetch(`${apiBaseUrl}/relay/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: `What is Ambrosia ${benchmark} relay benchmark posture?`,
          benchmark,
          documents: [
            "Relay benchmark probe from control-plane UI.",
            "Use retrieval, numeric verification, and grounding checks."
          ]
        })
      });
      if (!response.ok) {
        throw new Error(`Probe failed with status ${response.status}`);
      }
      const run = (await response.json()) as Record<string, unknown>;
      setBenchmarkRuns((previous) => ({ ...previous, [benchmark]: run }));
      await load();
      setMessage(`${benchmark} relay probe completed and scorecard refreshed.`);
    } catch {
      setMessage(`${benchmark} relay probe failed. Refresh and check relay API status.`);
    } finally {
      setRunningProbe(false);
    }
  }

  async function runAllBenchmarkProbes() {
    if (!apiBaseUrl || runningProbe) return;
    await runBenchmarkProbe("financebench-open-subset");
    await runBenchmarkProbe("finqa-open-subset");
    await runBenchmarkProbe("tatqa-open-subset");
  }

  if (status === "loading") return <RouteLoading title="Relay + Benchmarks" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Relay + Benchmarks" />
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button
              type="button"
              onClick={() => void runRelayProbe()}
              disabled={!apiBaseUrl || runningProbe}
              className="focus-ring rounded-md border border-line bg-paper/80 px-3 py-1 text-xs font-semibold text-teal disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runningProbe ? "Running relay probe..." : "Run relay probe"}
            </button>
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
          OpenAI-compatible relay posture and benchmark evidence status for FinanceBench, FinQA, and TAT-QA operating loops.
        </p>
        <p className="mt-2 text-xs text-ink/60">Model relay path from index86 Phase 7: OpenAI-compatible endpoint + evaluate/runs/scorecard + benchmark artifacts + routing map.</p>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Scorecard" title="Relay quality metrics" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Runs" value={formatNumber(scorecard?.runs)} />
          <Metric label="Accuracy" value={formatRate(scorecard?.accuracy)} />
          <Metric label="Grounding pass rate" value={formatRate(scorecard?.groundingPassRate)} />
          <Metric label="Calc verifier pass rate" value={formatRate(scorecard?.calculationVerificationPassRate)} />
          <Metric label="Evidence recall" value={formatRate(scorecard?.evidenceRecall)} />
          <Metric label="Unsupported answers refused" value={formatBoolean(scorecard?.unsupportedAnswersRefused)} />
          <Metric label="Failure clusters" value={formatFailureClusters(scorecard?.failureClusters)} />
          <Metric label="Schema version" value={textOrFallback(scorecard?.schemaVersion)} />
        </div>
        <p className="mt-3 text-xs text-ink/60">Last updated: {textOrFallback(scorecard?.updatedAt)}</p>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Benchmark Loops" title="Coverage posture" />
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void runAllBenchmarkProbes()}
            disabled={!apiBaseUrl || runningProbe}
            className="focus-ring rounded-md border border-line bg-paper/80 px-3 py-1 text-xs font-semibold text-teal disabled:cursor-not-allowed disabled:opacity-50"
          >
            {runningProbe ? "Running probes..." : "Run all benchmark probes"}
          </button>
          <button
            type="button"
            onClick={() => void runBenchmarkProbe("financebench-open-subset")}
            disabled={!apiBaseUrl || runningProbe}
            className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            FinanceBench probe
          </button>
          <button
            type="button"
            onClick={() => void runBenchmarkProbe("finqa-open-subset")}
            disabled={!apiBaseUrl || runningProbe}
            className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            FinQA probe
          </button>
          <button
            type="button"
            onClick={() => void runBenchmarkProbe("tatqa-open-subset")}
            disabled={!apiBaseUrl || runningProbe}
            className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            TAT-QA probe
          </button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <BenchmarkRunCard label="FinanceBench" benchmark="financebench-open-subset" run={benchmarkRuns["financebench-open-subset"]} scorecard={scorecard} />
          <BenchmarkRunCard label="FinQA" benchmark="finqa-open-subset" run={benchmarkRuns["finqa-open-subset"]} scorecard={scorecard} />
          <BenchmarkRunCard label="TAT-QA" benchmark="tatqa-open-subset" run={benchmarkRuns["tatqa-open-subset"]} scorecard={scorecard} />
        </div>
        <p className="mt-3 text-xs text-ink/60">
          These loop states summarize relay benchmark readiness from the shared scorecard. Use Run relay probe to generate fresh evidence when the panel looks stale.
        </p>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Relay Path" title="Endpoint posture and controls" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="OpenAI-compatible" value="POST /v1/chat/completions" />
          <Metric label="Relay evaluate" value="POST /relay/evaluate" />
          <Metric label="Relay run lookup" value="GET /relay/runs/{run_id}" />
          <Metric label="Relay scorecard" value="GET /relay/scorecard" />
        </div>
        <p className="mt-3 text-xs text-ink/60">Operational intent: evidence-backed answer generation with retrieval events, calculation verification, grounding checks, abstention policy, and latency/cost metadata.</p>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Index86 Evidence" title="Representative implementation and artifacts" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <EvidenceList
            title="Representative code surfaces"
            items={[
              "services/api/app/index84_platform.py",
              "packages/evals/run_financebench_relay.py",
              "packages/evals/run_finqa_relay.py",
              "packages/evals/run_tatqa_relay.py",
              "scripts/generate-open-finllm-routing-map.py"
            ]}
          />
          <EvidenceList
            title="Repository artifacts"
            items={[
              "artifacts/financebench-relay-trace.json",
              "artifacts/finqa-relay-trace.json",
              "artifacts/tatqa-relay-trace.json",
              "artifacts/open-finllm-routing-map.json",
              "artifacts/provider-ablation.json"
            ]}
          />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Interpretation" title="What these metrics mean" />
        <ul className="mt-3 space-y-2 text-sm text-ink/80">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Accuracy tracks benchmark answer quality across relay runs.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Grounding pass rate confirms claims are tied to supportable evidence.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Calculation verifier pass rate tracks numeric consistency and replayability.</li>
        </ul>
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

function formatNumber(value: unknown): string {
  return typeof value === "number" ? String(value) : "n/a";
}

function formatRate(value: unknown): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

function formatBoolean(value: unknown): string {
  return typeof value === "boolean" ? (value ? "yes" : "no") : "n/a";
}

function formatFailureClusters(value: unknown): string {
  return Array.isArray(value) ? String(value.length) : "n/a";
}

function readinessValue(scorecard: Record<string, unknown> | null): string {
  const runs = scorecard?.runs;
  if (typeof runs === "number" && runs > 0) return "evidence-ready";
  return "pending evidence";
}

function BenchmarkRunCard({
  label,
  benchmark,
  run,
  scorecard
}: {
  label: string;
  benchmark: string;
  run: Record<string, unknown> | null;
  scorecard: Record<string, unknown> | null;
}) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3 text-sm">
      <p className="font-semibold text-ink">{label}</p>
      <p className="mt-1 text-xs text-ink/60">{readinessValue(scorecard)}</p>
      <div className="mt-2 space-y-1 text-xs text-ink/75">
        <p>Benchmark id: {benchmark}</p>
        <p>Run id: {textOrFallback(run?.runId)}</p>
        <p>Route: {textOrFallback(run?.route)}</p>
        <p>Verification: {textOrFallback((run?.verification as Record<string, unknown> | undefined)?.status)}</p>
        <p>Grounding: {textOrFallback((run?.grounding as Record<string, unknown> | undefined)?.status)}</p>
        <p>Retrieval events: {formatNumber(Array.isArray(run?.retrievalEvents) ? run?.retrievalEvents.length : null)}</p>
        <p>Calculations verified: {formatBoolean((Array.isArray(run?.calculations) ? (run?.calculations[0] as Record<string, unknown> | undefined)?.verified : null) ?? null)}</p>
        <p>Latency: {typeof run?.latencyMs === "number" ? `${run.latencyMs} ms` : "n/a"}</p>
        <p>Cost mode: {textOrFallback((run?.cost as Record<string, unknown> | undefined)?.mode)}</p>
      </div>
    </div>
  );
}

function EvidenceList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3 text-sm">
      <p className="font-semibold text-ink">{title}</p>
      <ul className="mt-2 space-y-1 text-xs text-ink/75">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
