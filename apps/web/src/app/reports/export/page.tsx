"use client";

import React, { Suspense, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Badge, Panel, SectionTitle, cn } from "@/components/ui";
import { getApiBaseUrl } from "@/lib/api";

export default function ReportExportPage() {
  return (
    <Suspense fallback={<ReportExportShell reviewId="atr-003" />}>
      <ReportExportClient />
    </Suspense>
  );
}

function ReportExportClient() {
  const params = useParams();
  const searchParams = useSearchParams();
  const routeReviewId = typeof params?.id === "string" ? params.id : "";
  const reviewId = routeReviewId || searchParams.get("id") || "atr-003";

  const [exportFormat, setExportFormat] = useState<"pdf" | "html" | "email">(
    "pdf"
  );
  const [includeCharts, setIncludeCharts] = useState(true);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Export report via API
  const handleExport = async () => {
    if (!reviewId) {
      setError("Review ID not found");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      if (exportFormat === "email") {
        if (!recipientEmail) {
          throw new Error("Please enter a recipient email");
        }

        const response = await fetch(
          `${apiBaseUrl}/discovery/reports/${reviewId}/email?recipient=${encodeURIComponent(
            recipientEmail
          )}`,
          {
            method: "POST",
          }
        );

        if (!response.ok) {
          throw new Error(`Email send failed: ${response.statusText}`);
        }

        setSuccess(true);
        setRecipientEmail("");
      } else {
        const response = await fetch(
          `${apiBaseUrl}/discovery/reports/${reviewId}/export?format=${encodeURIComponent(
            exportFormat
          )}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              format: exportFormat,
              include_charts: includeCharts,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Export failed: ${response.statusText}`);
        }

        const data = await response.json();

        // Open download or new tab
        if (exportFormat === "pdf" || exportFormat === "html") {
          window.open(data.url, "_blank");
          setSuccess(true);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return <ReportExportShell reviewId={reviewId} exportFormat={exportFormat} setExportFormat={setExportFormat} includeCharts={includeCharts} setIncludeCharts={setIncludeCharts} recipientEmail={recipientEmail} setRecipientEmail={setRecipientEmail} loading={loading} error={error} success={success} handleExport={handleExport} />;
}

function ReportExportShell({
  reviewId,
  exportFormat = "pdf",
  setExportFormat,
  includeCharts = true,
  setIncludeCharts,
  recipientEmail = "",
  setRecipientEmail,
  loading = false,
  error,
  success = false,
  handleExport,
}: {
  reviewId: string;
  exportFormat?: "pdf" | "html" | "email";
  setExportFormat?: (format: "pdf" | "html" | "email") => void;
  includeCharts?: boolean;
  setIncludeCharts?: (includeCharts: boolean) => void;
  recipientEmail?: string;
  setRecipientEmail?: (email: string) => void;
  loading?: boolean;
  error?: string | null;
  success?: boolean;
  handleExport?: () => void;
}) {
  return (
    <div className="min-h-screen bg-fog p-8">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <Panel>
          <SectionTitle eyebrow="Reports" title="Export Review" />
          <p className="text-sm text-muted mt-2">
            Generate and export review analysis in multiple formats
          </p>
        </Panel>

        {/* Export Card */}
        <Panel className="mt-6 border border-line">
          <SectionTitle title="Report Format" />
          <p className="text-sm text-muted mt-1 mb-6">
            Choose how to export this review
          </p>

          <div className="space-y-6">
            {/* Format Selection */}
            <div className="space-y-3">
              <label className="text-sm font-semibold text-ink block">
                Export Format
              </label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* PDF Option */}
                <div
                  onClick={() => setExportFormat?.("pdf")}
                  className={cn(
                    "p-4 rounded border-2 cursor-pointer transition-all",
                    exportFormat === "pdf"
                      ? "border-teal bg-teal/5"
                      : "border-line hover:border-teal/50"
                  )}
                >
                  <h3 className="font-semibold text-ink mb-1">PDF</h3>
                  <p className="text-xs text-muted">
                    Professional document format
                  </p>
                </div>

                {/* HTML Option */}
                <div
                  onClick={() => setExportFormat?.("html")}
                  className={cn(
                    "p-4 rounded border-2 cursor-pointer transition-all",
                    exportFormat === "html"
                      ? "border-teal bg-teal/5"
                      : "border-line hover:border-teal/50"
                  )}
                >
                  <h3 className="font-semibold text-ink mb-1">HTML</h3>
                  <p className="text-xs text-muted">Interactive web format</p>
                </div>

                {/* Email Option */}
                <div
                  onClick={() => setExportFormat?.("email")}
                  className={cn(
                    "p-4 rounded border-2 cursor-pointer transition-all",
                    exportFormat === "email"
                      ? "border-teal bg-teal/5"
                      : "border-line hover:border-teal/50"
                  )}
                >
                  <h3 className="font-semibold text-ink mb-1">Email</h3>
                  <p className="text-xs text-muted">Send to recipient</p>
                </div>
              </div>
            </div>

            {/* Charts Option */}
            {exportFormat !== "email" && (
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="charts"
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts?.(e.target.checked)}
                  className="w-4 h-4 cursor-pointer"
                />
                <label htmlFor="charts" className="text-sm cursor-pointer">
                  Include performance charts and visualizations
                </label>
              </div>
            )}

            {/* Email Input */}
            {exportFormat === "email" && (
              <div>
                <label className="text-sm font-semibold text-ink block mb-2">
                  Recipient Email
                </label>
                <input
                  type="email"
                  placeholder="recipient@example.com"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail?.(e.target.value)}
                  className="w-full px-4 py-2 border border-line rounded font-mono text-sm"
                />
              </div>
            )}

            {/* Error Alert */}
            {error && (
              <Panel className="border border-coral/30 bg-coral/10">
                <p className="text-coral font-semibold">Error</p>
                <p className="text-sm text-coral mt-1">{error}</p>
              </Panel>
            )}

            {/* Success Alert */}
            {success && (
              <Panel className="border border-teal/30 bg-teal/5">
                <p className="text-teal font-semibold">Export successful</p>
                <p className="text-sm text-teal mt-1">
                  Check your browser or email.
                </p>
              </Panel>
            )}

            {/* Export Button */}
            <button
              onClick={handleExport}
              disabled={loading || (exportFormat === "email" && !recipientEmail)}
              className="w-full px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90 disabled:opacity-50"
            >
              {loading
                ? "Processing..."
                : `Export as ${exportFormat.toUpperCase()}`}
            </button>
          </div>
        </Panel>

        {/* Preview Card */}
        <Panel className="mt-6 border border-line">
          <SectionTitle title="Report Preview" />
          <p className="text-xs text-muted font-mono mt-1 mb-4">
            Review ID: {reviewId}
          </p>

          <div className="space-y-4">
            <div className="bg-line/20 rounded p-4">
              <h3 className="font-semibold text-ink mb-3">Report Contents</h3>
              <ul className="space-y-2 text-sm text-muted">
                <ReportContentItem label="Thesis Summary" />
                <ReportContentItem label="Risk Assessment" />
                <ReportContentItem label="Market Analysis" />
                <ReportContentItem label="Confidence Score" />
                {includeCharts && (
                  <>
                    <ReportContentItem label="Performance Charts" />
                    <ReportContentItem label="Data Visualizations" />
                  </>
                )}
              </ul>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted uppercase font-semibold mb-2">
                  Format
                </p>
                <Badge>{exportFormat.toUpperCase()}</Badge>
              </div>
              <div>
                <p className="text-xs text-muted uppercase font-semibold mb-2">
                  Quality
                </p>
                <Badge tone="good">Production</Badge>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ReportContentItem({ label }: { label: string }) {
  return (
    <li className="flex items-center gap-2">
      <CheckCircle2 className="h-4 w-4 text-teal" />
      {label}
    </li>
  );
}
