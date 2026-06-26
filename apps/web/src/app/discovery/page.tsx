"use client";

import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";

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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">
            Discovery Scanner
          </h1>
          <p className="text-slate-600">
            AI-powered market signal discovery and thesis generation
          </p>
        </div>

        {/* Controls */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Scanner Controls</CardTitle>
            <CardDescription>
              Run discovery scan to identify trading signals
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-4">
            <Button
              onClick={runDiscoveryScan}
              disabled={loading}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {loading ? "Scanning..." : "Run Discovery Scan"}
            </Button>
            <Button variant="outline" disabled>
              Advanced Filters
            </Button>
          </CardContent>
        </Card>

        {/* Error Alert */}
        {error && (
          <Alert className="mb-8 border-red-200 bg-red-50">
            <AlertDescription className="text-red-800">
              Error: {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Signals Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {signals.map((signal) => (
            <Card
              key={signal.id}
              className={`cursor-pointer transition-all ${
                selectedSignal?.id === signal.id
                  ? "ring-2 ring-teal-500"
                  : "hover:shadow-lg"
              }`}
              onClick={() => setSelectedSignal(signal)}
            >
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-2xl font-bold">
                      {signal.ticker}
                    </CardTitle>
                    <CardDescription className="capitalize">
                      {signal.signal_type.replace(/_/g, " ")}
                    </CardDescription>
                  </div>
                  <Badge className="bg-teal-100 text-teal-800">
                    {(signal.conviction * 100).toFixed(0)}%
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-600 mb-4">
                  {signal.description}
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {signal.data_sources.map((source) => (
                    <Badge key={source} variant="outline" className="text-xs">
                      {source}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => createThesisFromSignal(signal)}
                    className="flex-1 bg-amber-600 hover:bg-amber-700 text-white"
                  >
                    Create Thesis
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => exportSignalReport(signal)}
                    className="flex-1"
                  >
                    Export
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Signal Details Panel */}
        {selectedSignal && (
          <Card>
            <CardHeader>
              <CardTitle>Signal Details: {selectedSignal.ticker}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h4 className="font-semibold text-slate-900 mb-2">
                    Description
                  </h4>
                  <p className="text-slate-600">{selectedSignal.description}</p>
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 mb-2">
                    Conviction Score
                  </h4>
                  <div className="bg-slate-100 rounded h-2">
                    <div
                      className="bg-teal-600 h-2 rounded"
                      style={{ width: `${selectedSignal.conviction * 100}%` }}
                    />
                  </div>
                  <p className="text-sm text-slate-600 mt-1">
                    {(selectedSignal.conviction * 100).toFixed(1)}% confidence
                  </p>
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 mb-2">
                    Data Sources
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedSignal.data_sources.map((source) => (
                      <Badge key={source}>{source}</Badge>
                    ))}
                  </div>
                </div>
                <Button
                  onClick={() => createThesisFromSignal(selectedSignal)}
                  className="w-full bg-teal-600 hover:bg-teal-700"
                >
                  Create Trading Thesis
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Empty State */}
        {!loading && signals.length === 0 && !error && (
          <Card className="text-center py-12">
            <CardContent>
              <p className="text-slate-600 mb-4">
                No signals found. Try running a discovery scan.
              </p>
              <Button
                onClick={runDiscoveryScan}
                className="bg-teal-600 hover:bg-teal-700"
              >
                Start Scan
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
