"use client";

import { useEffect, useState } from "react";
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
          <RouteStatusBadge status={status} />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink/75">
          Index84 platform overview with readiness and control-plane operating status across research, execution, and governance modules.
        </p>
      </Panel>

      {status !== "success" && status !== "degraded" ? (
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
