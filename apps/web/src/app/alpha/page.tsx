"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";
import { getApiBaseUrl } from "@/lib/api";

export default function AlphaPage() {
  const apiBaseUrl = getApiBaseUrl();
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading alpha surfaces...");
  const [hypotheses, setHypotheses] = useState<Array<Record<string, unknown>>>([]);
  const [signals, setSignals] = useState<Array<Record<string, unknown>>>([]);
  const [decay, setDecay] = useState<Record<string, unknown> | null>(null);
  const [openDataPanels, setOpenDataPanels] = useState<Record<string, boolean>>({});
  const [openDataPayloads, setOpenDataPayloads] = useState<Record<string, Record<string, unknown>>>({});
  const [openDataLoading, setOpenDataLoading] = useState<Record<string, boolean>>({});
  const [openDataErrors, setOpenDataErrors] = useState<Record<string, string>>({});

  function panelKey(kind: "hypothesis" | "signal", id: string): string {
    return `${kind}:${id}`;
  }

  async function toggleOpenData(kind: "hypothesis" | "signal", id: string, path: string) {
    const key = panelKey(kind, id);
    const currentlyOpen = openDataPanels[key] === true;

    if (currentlyOpen) {
      setOpenDataPanels((previous) => ({ ...previous, [key]: false }));
      return;
    }

    setOpenDataPanels((previous) => ({ ...previous, [key]: true }));

    if (!apiBaseUrl || openDataPayloads[key] || openDataLoading[key]) {
      return;
    }

    setOpenDataLoading((previous) => ({ ...previous, [key]: true }));
    setOpenDataErrors((previous) => ({ ...previous, [key]: "" }));

    try {
      const response = await fetch(`${apiBaseUrl}${path}`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const payload = (await response.json()) as Record<string, unknown>;
      setOpenDataPayloads((previous) => ({ ...previous, [key]: payload }));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unable to load object details.";
      setOpenDataErrors((previous) => ({ ...previous, [key]: detail }));
    } finally {
      setOpenDataLoading((previous) => ({ ...previous, [key]: false }));
    }
  }

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

    let decayData: Record<string, unknown> | null = null;
    const firstSignalId = textOrFallback(signalItems[0]?.signalId, "");
    if (firstSignalId) {
      const decayResult = await fetchControlPlane(`/signals/${firstSignalId}/alpha-decay`);
      if (decayResult.ok && decayResult.data && typeof decayResult.data === "object") {
        decayData = decayResult.data as Record<string, unknown>;
      }
    }

    setHypotheses(alphaItems);
    setSignals(signalItems);
    setDecay(decayData);
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
        <SectionTitle eyebrow="Program View" title="Alpha credibility snapshot" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Hypotheses tracked" value={String(hypotheses.length)} />
          <Metric label="Signals tracked" value={String(signals.length)} />
          <Metric label="Primary quality tier" value={textOrFallback(hypotheses[0]?.quality, "research")} />
          <Metric label="Decay action" value={textOrFallback(decay?.recommendedAction, "pending diagnostics")} />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Hypotheses" title="Recent alpha objects" />
        <ul className="mt-3 space-y-2 text-sm">
          {hypotheses.slice(0, 5).map((item) => (
            <li key={textOrFallback(item.hypothesisId)} className="rounded-md border border-line bg-fog/70 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-semibold text-ink">{textOrFallback(item.title)}</span>
                  <span className="ml-2 text-ink/70">{textOrFallback(item.signalFamily)}</span>
                </div>
                {apiBaseUrl ? (
                  <div className="flex items-center gap-2">
                    <Link
                      href={buildReviewPrefillHref("hypothesis", item)}
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-ink/80"
                    >
                      Create review
                    </Link>
                    <button
                      type="button"
                      onClick={() =>
                        void toggleOpenData(
                          "hypothesis",
                          textOrFallback(item.hypothesisId, ""),
                          `/alpha/hypotheses/${encodeURIComponent(textOrFallback(item.hypothesisId, ""))}`
                        )
                      }
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-teal"
                    >
                      Open data
                    </button>
                    <a
                      href={`${apiBaseUrl}/alpha/hypotheses/${encodeURIComponent(textOrFallback(item.hypothesisId, ""))}`}
                      target="_blank"
                      rel="noreferrer"
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-ink/80"
                    >
                      New tab
                    </a>
                  </div>
                ) : null}
              </div>
              {openDataPanels[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))] ? (
                <div className="mt-3 rounded-md border border-line bg-paper/70 p-3">
                  {openDataLoading[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))] ? (
                    <p className="text-xs text-ink/70">Loading object data...</p>
                  ) : null}
                  {openDataErrors[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))] ? (
                    <p className="text-xs text-coral">{openDataErrors[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))]}</p>
                  ) : null}
                  {openDataPayloads[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))] ? (
                    <DataDropdown payload={openDataPayloads[panelKey("hypothesis", textOrFallback(item.hypothesisId, ""))]} />
                  ) : null}
                </div>
              ) : null}
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
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-semibold text-ink">{textOrFallback(item.name)}</span>
                  <span className="ml-2 text-ink/70">{textOrFallback(item.formula)}</span>
                </div>
                {apiBaseUrl ? (
                  <div className="flex items-center gap-2">
                    <Link
                      href={buildReviewPrefillHref("signal", item)}
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-ink/80"
                    >
                      Create review
                    </Link>
                    <button
                      type="button"
                      onClick={() =>
                        void toggleOpenData("signal", textOrFallback(item.signalId, ""), `/signals/${encodeURIComponent(textOrFallback(item.signalId, ""))}`)
                      }
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-teal"
                    >
                      Open data
                    </button>
                    <a
                      href={`${apiBaseUrl}/signals/${encodeURIComponent(textOrFallback(item.signalId, ""))}`}
                      target="_blank"
                      rel="noreferrer"
                      className="focus-ring rounded-md border border-line bg-paper/80 px-2 py-1 text-xs font-semibold text-ink/80"
                    >
                      New tab
                    </a>
                  </div>
                ) : null}
              </div>
              {openDataPanels[panelKey("signal", textOrFallback(item.signalId, ""))] ? (
                <div className="mt-3 rounded-md border border-line bg-paper/70 p-3">
                  {openDataLoading[panelKey("signal", textOrFallback(item.signalId, ""))] ? (
                    <p className="text-xs text-ink/70">Loading object data...</p>
                  ) : null}
                  {openDataErrors[panelKey("signal", textOrFallback(item.signalId, ""))] ? (
                    <p className="text-xs text-coral">{openDataErrors[panelKey("signal", textOrFallback(item.signalId, ""))]}</p>
                  ) : null}
                  {openDataPayloads[panelKey("signal", textOrFallback(item.signalId, ""))] ? (
                    <DataDropdown payload={openDataPayloads[panelKey("signal", textOrFallback(item.signalId, ""))]} />
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
          {signals.length === 0 ? <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-2 text-ink/60">No signals available.</li> : null}
        </ul>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Factor + Cost" title="Alpha model assumptions" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Benchmark" value={textOrFallback(signals[0]?.benchmark)} />
          <Metric label="Cost model" value={textOrFallback(signals[0]?.costModel)} />
          <Metric
            label="Validation gates"
            value={Array.isArray(signals[0]?.validationGates) ? String((signals[0]?.validationGates as unknown[]).length) : "n/a"}
          />
          <Metric label="Residual alpha decomposition" value="planned" />
        </div>
        <p className="mt-3 text-xs text-ink/60">
          Quant-theory note: this module now exposes benchmark and cost assumptions directly; full factor-adjusted residual alpha decomposition is the next implementation milestone.
        </p>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Validation" title="Evidence quality and multiple-testing controls" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Disconfirming tests" value={Array.isArray(hypotheses[0]?.disconfirmingTests) ? String((hypotheses[0]?.disconfirmingTests as unknown[]).length) : "0"} />
          <Metric label="Research status" value={textOrFallback(hypotheses[0]?.status, "research")} />
          <Metric label="Trial complexity proxy" value={String(Math.max(hypotheses.length + signals.length, 1))} />
          <Metric label="False-discovery warning" value={hypotheses.length + signals.length > 8 ? "elevated" : "controlled"} />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Decay" title="Rolling diagnostics" />
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Decay detected" value={decay?.decayDetected === true ? "yes" : decay?.decayDetected === false ? "no" : "n/a"} />
          <Metric label="Latest rolling IC" value={tailValue(decay?.rollingIC)} />
          <Metric label="Latest rolling Sharpe" value={tailValue(decay?.rollingSharpe)} />
          <Metric label="Latest rolling hit-rate" value={tailValue(decay?.rollingHitRate)} />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3 text-sm">
          <RegimeMetric label="Risk-on" value={textOrFallback((decay?.regimePerformance as Record<string, unknown> | undefined)?.risk_on, "n/a")} />
          <RegimeMetric label="Risk-off" value={textOrFallback((decay?.regimePerformance as Record<string, unknown> | undefined)?.risk_off, "n/a")} />
          <RegimeMetric label="High-volatility" value={textOrFallback((decay?.regimePerformance as Record<string, unknown> | undefined)?.high_volatility, "n/a")} />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Attribution" title="Alpha-goal readiness checklist" />
        <ul className="mt-3 space-y-2 text-sm text-ink/80">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Separate factor exposure from residual alpha before promotion.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Track post-cost outcome quality in paper trades and warm-path records.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Retire or recalibrate signals when decay and capacity metrics deteriorate.</li>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3 text-sm">
      <p className="text-ink/70">{label}</p>
      <p className="mt-1 font-semibold text-ink">{value}</p>
    </div>
  );
}

function RegimeMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/60 px-3 py-2">
      <p className="text-ink/60">{label}</p>
      <p className="font-semibold text-ink">{value}</p>
    </div>
  );
}

function tailValue(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return "n/a";
  const tail = value[value.length - 1];
  return typeof tail === "number" ? String(tail) : "n/a";
}

function DataDropdown({ payload }: { payload: Record<string, unknown> }) {
  const visibleEntries = Object.entries(payload).slice(0, 8);

  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-2">
        {visibleEntries.map(([key, value]) => (
          <div key={key} className="rounded-md border border-line bg-fog/60 px-2 py-1.5">
            <p className="text-[11px] uppercase tracking-wide text-ink/60">{key}</p>
            <p className="mt-1 break-words text-xs font-semibold text-ink">{formatDropdownValue(value)}</p>
          </div>
        ))}
      </div>
      <details className="rounded-md border border-line bg-fog/60 p-2">
        <summary className="cursor-pointer text-xs font-semibold text-ink/80">Raw JSON</summary>
        <pre className="mt-2 overflow-x-auto text-[11px] text-ink/80">{JSON.stringify(payload, null, 2)}</pre>
      </details>
    </div>
  );
}

function formatDropdownValue(value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === "object") return `${Object.keys(value as Record<string, unknown>).length} fields`;
  return "n/a";
}

function buildReviewPrefillHref(kind: "hypothesis" | "signal", item: Record<string, unknown>): string {
  const id = kind === "hypothesis" ? textOrFallback(item.hypothesisId, "") : textOrFallback(item.signalId, "");
  const title = kind === "hypothesis" ? textOrFallback(item.title, "") : textOrFallback(item.name, "");
  const ticker = inferTicker(item);
  const thesis =
    kind === "hypothesis"
      ? `Evaluate alpha hypothesis "${title || id || "untitled"}" with adversarial review and disconfirming tests.`
      : `Evaluate signal "${title || id || "untitled"}" for robustness, tradeability, and promotion readiness.`;

  const params = new URLSearchParams({
    source: "alpha",
    alphaType: kind,
    alphaTitle: title,
    ticker,
    assetClass: "Equities",
    timeHorizon: textOrFallback(item.horizon, "2-6 weeks"),
    expression: "Long via equity",
    thesis,
    sourcePointer: `alpha:${kind}:${id}`
  });

  if (kind === "hypothesis") {
    params.set("hypothesisId", id);
    params.set("alphaSignalFamily", textOrFallback(item.signalFamily, ""));
  } else {
    params.set("signalId", id);
    params.set("alphaFormula", textOrFallback(item.formula, ""));
  }

  return `/review/new?${params.toString()}`;
}

function inferTicker(item: Record<string, unknown>): string {
  const explicitTicker = textOrFallback(item.ticker, "").toUpperCase();
  if (explicitTicker) return explicitTicker;

  const universe = item.universe;
  if (Array.isArray(universe) && universe.length > 0) {
    const first = textOrFallback(universe[0], "").toUpperCase();
    if (first) return first;
  }

  return "AAPL";
}
