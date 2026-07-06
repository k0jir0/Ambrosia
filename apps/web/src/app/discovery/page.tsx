"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Badge, Panel, SectionTitle, cn } from "@/components/ui";
import { getApiBaseUrl } from "@/lib/api";

interface Signal {
  id: string;
  ticker: string;
  signal_type: string;
  conviction: number;
  description: string;
  data_sources: string[];
}

type DiscoveryScanConfig = {
  universe: string;
  signal_type: string;
  min_conviction: number;
  lookback_days: number;
};

const INITIAL_SCAN_CONFIG: DiscoveryScanConfig = {
  universe: "all",
  signal_type: "all",
  min_conviction: 0.7,
  lookback_days: 20,
};

async function fetchDiscoverySignals(config: DiscoveryScanConfig): Promise<Signal[]> {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
  const response = await fetch(`${apiBaseUrl}/discovery/scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    throw new Error(`Discovery scan failed: ${response.statusText}`);
  }

  return response.json();
}

export default function DiscoveryPage() {
  const router = useRouter();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [universe, setUniverse] = useState("all");
  const [signalType, setSignalType] = useState("all");
  const [minConviction, setMinConviction] = useState(0.7);
  const [lookbackDays, setLookbackDays] = useState(20);

  // Fetch signals from backend discovery API
  const runDiscoveryScan = async () => {
    setLoading(true);
    setError(null);
    setStatus(null);
    try {
      const data = await fetchDiscoverySignals({
        universe,
        signal_type: signalType,
        min_conviction: minConviction,
        lookback_days: lookbackDays,
      });
      setSignals(data);
      setStatus(`Discovery scan returned ${data.length} candidates.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  // Convert signal to thesis
  const createThesisFromSignal = async (signal: Signal) => {
    try {
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      const response = await fetch(
        `${apiBaseUrl}/discovery/signal/${signal.id}/create-thesis`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Thesis creation failed: ${response.statusText}`);
      }

      const data = await response.json();
      const params = new URLSearchParams({
        source: "scanner",
        ticker: signal.ticker,
        assetClass: "Equities",
        timeHorizon: "2-6 weeks",
        expression: `Long ${signal.ticker}`,
        thesis: typeof data.thesis === "string" ? data.thesis : `Evaluate ${signal.ticker} ${signal.signal_type.replace(/_/g, " ")} signal for review readiness.`,
        sourcePointer: `discovery:signal:${signal.id}`,
      });
      setStatus(`Thesis staged for review intake: ${signal.ticker}`);
      router.push(`/review/new?${params.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  // Export signal as report
  const exportSignalReport = async (signal: Signal) => {
    try {
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      const response = await fetch(
        `${apiBaseUrl}/discovery/reports/${signal.id}/export`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            format: "pdf",
            include_charts: true,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      const data = await response.json();
      window.open(data.url, "_blank");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  useEffect(() => {
    async function loadInitialScan() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchDiscoverySignals(INITIAL_SCAN_CONFIG);
        setSignals(data);
        setStatus(`Discovery scan returned ${data.length} candidates.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    void loadInitialScan();
  }, []);

  return (
    <div className="min-h-screen bg-fog p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <Panel>
          <SectionTitle eyebrow="Phase C" title="Discovery Scanner" />
          <p className="text-sm text-muted mt-2">
            AI-powered market signal discovery and thesis generation
          </p>
        </Panel>

        {/* Controls */}
        <Panel className="mt-6">
          <div className="flex gap-4">
            <button
              onClick={runDiscoveryScan}
              disabled={loading}
              className="px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90 disabled:opacity-50"
            >
              {loading ? "Scanning..." : "Run Discovery Scan"}
            </button>
            <button
              type="button"
              onClick={() => setShowFilters((value) => !value)}
              className="px-4 py-2 border border-line text-ink rounded font-semibold hover:bg-fog"
            >
              {showFilters ? "Hide Filters" : "Advanced Filters"}
            </button>
          </div>
          {showFilters && (
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
              <label className="text-sm font-semibold text-ink">
                Universe
                <select value={universe} onChange={(event) => setUniverse(event.target.value)} className="mt-2 w-full rounded border border-line bg-paper px-3 py-2 text-sm font-normal">
                  <option value="all">All</option>
                  <option value="equities">Equities</option>
                  <option value="etf">ETF</option>
                  <option value="rates">Rates</option>
                </select>
              </label>
              <label className="text-sm font-semibold text-ink">
                Signal Type
                <select value={signalType} onChange={(event) => setSignalType(event.target.value)} className="mt-2 w-full rounded border border-line bg-paper px-3 py-2 text-sm font-normal">
                  <option value="all">All</option>
                  <option value="momentum">Momentum</option>
                  <option value="mean_reversion">Mean reversion</option>
                  <option value="technical">Technical</option>
                </select>
              </label>
              <label className="text-sm font-semibold text-ink">
                Minimum Conviction
                <input type="number" min="0" max="1" step="0.05" value={minConviction} onChange={(event) => setMinConviction(Number(event.target.value))} className="mt-2 w-full rounded border border-line bg-paper px-3 py-2 text-sm font-normal" />
              </label>
              <label className="text-sm font-semibold text-ink">
                Lookback Days
                <input type="number" min="1" max="90" value={lookbackDays} onChange={(event) => setLookbackDays(Number(event.target.value))} className="mt-2 w-full rounded border border-line bg-paper px-3 py-2 text-sm font-normal" />
              </label>
            </div>
          )}
        </Panel>

        {/* Error Alert */}
        {error && (
          <Panel className="mt-6 border border-coral/30 bg-coral/10">
            <p className="text-coral font-semibold">Error</p>
            <p className="text-sm text-coral">{error}</p>
          </Panel>
        )}

        {status && (
          <Panel className="mt-6 border border-teal/30 bg-teal/5">
            <p className="text-teal font-semibold">{status}</p>
          </Panel>
        )}

        {/* Signals Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
          {signals.map((signal) => (
            <div
              key={signal.id}
              onClick={() => setSelectedSignal(signal)}
              className="cursor-pointer"
            >
              <Panel
                className={cn(
                  "border-2 h-full",
                  selectedSignal?.id === signal.id
                    ? "border-teal bg-teal/5"
                    : "border-line hover:border-teal/50"
                )}
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-ink">{signal.ticker}</h3>
                    <p className="text-xs text-muted capitalize">
                      {signal.signal_type.replace(/_/g, " ")}
                    </p>
                  </div>
                  <Badge tone="good">{(signal.conviction * 100).toFixed(0)}%</Badge>
                </div>
                <p className="text-sm text-muted mb-3">{signal.description}</p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {signal.data_sources.map((source) => (
                    <Badge key={source} tone="info">
                      {source}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      createThesisFromSignal(signal);
                    }}
                    className="flex-1 px-3 py-2 bg-teal text-white rounded text-sm font-semibold hover:bg-teal/90"
                  >
                    Create Thesis
                  </button>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      exportSignalReport(signal);
                    }}
                    className="flex-1 px-3 py-2 border border-line text-ink rounded text-sm font-semibold hover:bg-fog"
                  >
                    Export
                  </button>
                </div>
              </Panel>
            </div>
          ))}
        </div>

        {/* Signal Details Panel */}
        {selectedSignal && (
          <Panel className="mt-6">
            <SectionTitle title={`Signal Details: ${selectedSignal.ticker}`} />
            <div className="space-y-4 mt-4">
              <div>
                <h4 className="font-semibold text-ink mb-2">Description</h4>
                <p className="text-sm text-muted">{selectedSignal.description}</p>
              </div>
              <div>
                <h4 className="font-semibold text-ink mb-2">Conviction Score</h4>
                <div className="bg-line rounded h-2">
                  <div
                    className="bg-teal h-2 rounded"
                    style={{ width: `${selectedSignal.conviction * 100}%` }}
                  />
                </div>
                <p className="text-sm text-muted mt-1">
                  {(selectedSignal.conviction * 100).toFixed(1)}% confidence
                </p>
              </div>
              <div>
                <h4 className="font-semibold text-ink mb-2">Data Sources</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedSignal.data_sources.map((source) => (
                    <Badge key={source}>{source}</Badge>
                  ))}
                </div>
              </div>
              <button
                onClick={() => createThesisFromSignal(selectedSignal)}
                className="w-full px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90 mt-4"
              >
                Create Trading Thesis
              </button>
            </div>
          </Panel>
        )}

        {/* Empty State */}
        {!loading && signals.length === 0 && !error && (
          <Panel className="mt-6 text-center">
            <p className="text-muted mb-4">
              No signals found. Try running a discovery scan.
            </p>
            <button
              onClick={runDiscoveryScan}
              className="px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90"
            >
              Start Scan
            </button>
          </Panel>
        )}
      </div>
    </div>
  );
}
