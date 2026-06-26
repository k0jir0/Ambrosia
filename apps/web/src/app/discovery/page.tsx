"use client";

import React, { useState, useEffect } from "react";
import { Badge, Panel, SectionTitle, cn } from "@/components/ui";

interface Signal {
  id: string;
  ticker: string;
  signal_type: string;
  conviction: number;
  description: string;
  data_sources: string[];
}

export default function DiscoveryPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  // Fetch signals from backend discovery API
  const runDiscoveryScan = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        "https://ambrosia-api.onrender.com/discovery/scan",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            universe: "all",
            signal_type: "all",
            min_conviction: 0.7,
            lookback_days: 20,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Discovery scan failed: ${response.statusText}`);
      }

      const data = await response.json();
      setSignals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  // Convert signal to thesis
  const createThesisFromSignal = async (signal: Signal) => {
    try {
      const response = await fetch(
        `https://ambrosia-api.onrender.com/discovery/signal/${signal.id}/create-thesis`,
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
      alert(`✅ Thesis created: ${data.review_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  // Export signal as report
  const exportSignalReport = async (signal: Signal) => {
    try {
      const response = await fetch(
        `https://ambrosia-api.onrender.com/discovery/reports/${signal.id}/export`,
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
    // Auto-run discovery scan on page load
    runDiscoveryScan();
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
              disabled
              className="px-4 py-2 border border-line text-muted rounded font-semibold hover:bg-fog disabled:opacity-50"
            >
              Advanced Filters
            </button>
          </div>
        </Panel>

        {/* Error Alert */}
        {error && (
          <Panel className="mt-6 border border-coral/30 bg-coral/10">
            <p className="text-coral font-semibold">Error</p>
            <p className="text-sm text-coral">{error}</p>
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
                    onClick={() => createThesisFromSignal(signal)}
                    className="flex-1 px-3 py-2 bg-teal text-white rounded text-sm font-semibold hover:bg-teal/90"
                  >
                    Create Thesis
                  </button>
                  <button
                    onClick={() => exportSignalReport(signal)}
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
