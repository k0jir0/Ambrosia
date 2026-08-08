"use client";

import { useEffect, useState } from "react";
import { Activity, Bell, Boxes, Gauge, RefreshCw, ShieldCheck, Waypoints } from "lucide-react";

import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { Panel, SectionTitle } from "@/components/ui";
import { fetchControlPlane, mapStatus } from "@/lib/index84-control-plane";

type OperationsSection = {
  id: string;
  title: string;
  path: string;
  icon: typeof Activity;
  data: unknown;
  status: RouteStatus;
  message: string;
};

const SECTION_DEFINITIONS = [
  { id: "health", title: "Service health", path: "/health/detailed", icon: Activity },
  { id: "providers", title: "Provider posture", path: "/providers/status", icon: Waypoints },
  { id: "jobs", title: "Background jobs", path: "/jobs", icon: Boxes },
  { id: "alerts", title: "Active alerts", path: "/alerts/queue", icon: Bell },
  { id: "metrics", title: "Runtime metrics", path: "/metrics", icon: Gauge },
  { id: "boundaries", title: "Tool boundaries", path: "/tools/boundaries", icon: ShieldCheck },
] as const;

export default function OperationsPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState("Loading operational state...");
  const [sections, setSections] = useState<OperationsSection[]>([]);

  async function load() {
    setStatus("loading");
    setMessage("Loading operational state...");
    const results = await Promise.all(
      SECTION_DEFINITIONS.map(async (definition) => {
        const result = await fetchControlPlane(definition.path);
        return {
          ...definition,
          data: result.data,
          status: result.ok ? mapStatus(result.status, result.data) : mapStatus(result.status, null),
          message: result.message || (result.ok ? "Current state loaded." : "Endpoint unavailable."),
        } satisfies OperationsSection;
      }),
    );
    setSections(results);
    const failures = results.filter((section) => section.status === "error" || section.status === "forbidden");
    setStatus(failures.length === results.length ? "error" : failures.length > 0 ? "degraded" : "success");
    setMessage(failures.length > 0 ? `${failures.length} operational sections are unavailable.` : "Operational state loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading" && sections.length === 0) return <RouteLoading title="Operations" />;

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Operator surface" title="Operations" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">
              Read-only service health, provider, job, alert, metric, and boundary evidence from the authenticated control plane.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button
              type="button"
              onClick={() => void load()}
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-xs font-semibold"
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
          </div>
        </div>
      </Panel>

      {status !== "success" && status !== "loading" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <Panel key={section.id} className="min-w-0 p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Icon className="h-5 w-5 text-teal" />
                  <h2 className="font-semibold text-ink">{section.title}</h2>
                </div>
                <RouteStatusBadge status={section.status} />
              </div>
              {section.status === "success" || section.status === "empty" ? (
                <pre className="mt-4 max-h-72 overflow-auto rounded-md border border-line bg-fog/70 p-3 text-xs leading-5 text-ink/70">
                  {JSON.stringify(section.data, null, 2)}
                </pre>
              ) : (
                <p className="mt-4 rounded-md border border-line bg-fog/70 p-3 text-sm text-ink/60">{section.message}</p>
              )}
            </Panel>
          );
        })}
      </section>

      <Panel className="p-5 text-xs leading-5 text-ink/55">
        This release is observational. Job cancellation, alert acknowledgement, provider changes, order actions, and execution controls remain disabled.
      </Panel>
    </div>
  );
}