"use client";

import { useEffect, useState } from "react";
import { ProviderModePanel } from "@/components/advanced-panels";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";

type PlatformData = {
  health: unknown;
  phases: unknown;
};

export default function PlatformPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading platform status...");
  const [data, setData] = useState<PlatformData | null>(null);

  async function load() {
    setStatus("loading");
    setMessage("Loading platform status...");
    const [health, phases] = await Promise.all([fetchControlPlane("/health/detailed"), fetchControlPlane("/health/phases")]);

    if (!health.ok || !phases.ok) {
      const current = mapStatus(Math.max(health.status, phases.status), null);
      setStatus(current);
      setMessage(health.message || phases.message || "Platform endpoints are unavailable.");
      return;
    }

    setData({ health: health.data, phases: phases.data });
    setStatus(mapStatus(200, health.data));
    setMessage("Platform state loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Platform" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Platform" />
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
          Index84 platform overview with readiness and control-plane operating status across research, execution, and governance modules.
        </p>
      </Panel>

      {status !== "success" ? (
        <RouteNotice status={status} message={message} retry={() => void load()} />
      ) : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Runtime" title="Health and phase status" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Service" value={textOrFallback((data?.health as Record<string, unknown> | undefined)?.service)} />
          <Metric label="Health" value={textOrFallback((data?.health as Record<string, unknown> | undefined)?.status)} />
          <Metric label="SLO snapshot" value={textOrFallback((data?.health as Record<string, unknown> | undefined)?.status)} />
          <Metric label="Phases" value={textOrFallback((data?.phases as Record<string, unknown> | undefined)?.status)} />
        </div>
      </Panel>

      <ProviderModePanel />

      <Panel className="p-6">
        <SectionTitle eyebrow="Workstreams" title="Index84 control-plane modules" />
        <ul className="mt-3 grid gap-2 text-sm text-ink/80 md:grid-cols-2">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Alpha research and decay analytics</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Execution warm-path telemetry and diagnostics</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Relay benchmark quality and routing evidence</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Enterprise readiness and security packet posture</li>
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
