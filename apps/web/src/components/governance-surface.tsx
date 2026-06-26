"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import { AlertTriangle, CheckCircle2, Shield, Table2, Workflow } from "lucide-react";
import { ApiUnavailableError, getFunctionRegistry } from "@/lib/api";
import type { FunctionRegistryEntry } from "@/lib/types";
import { Badge, Panel, SectionTitle, cn } from "./ui";

type SurfaceMode = "advanced" | "team" | "admin";

const MODE_META: Record<SurfaceMode, { eyebrow: string; title: string; description: string; tone: "good" | "warn" | "info" }> = {
  advanced: {
    eyebrow: "Advanced Boundary",
    title: "Operator visibility, calibration, and proof surfaces",
    description: "This panel shows the live mapping between backend capabilities and the advanced user route that exposes them.",
    tone: "info",
  },
  team: {
    eyebrow: "Team Boundary",
    title: "Shared workflows and collaboration controls",
    description: "This panel highlights packet collaboration and review control surfaces that belong in the team workspace.",
    tone: "good",
  },
  admin: {
    eyebrow: "Admin Boundary",
    title: "Privileged operational and governance controls",
    description: "This panel surfaces the privileged functions that must remain clearly separated from everyday user flows.",
    tone: "warn",
  },
};

const EXPOSURE_ORDER: Array<FunctionRegistryEntry["exposure"]> = ["user", "advanced", "team", "admin", "internal-only"];

export function GovernanceSurface({ mode }: { mode: SurfaceMode }) {
  const meta = MODE_META[mode];
  const [registry, setRegistry] = useState<FunctionRegistryEntry[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "fallback">("loading");

  useEffect(() => {
    let cancelled = false;

    async function loadRegistry() {
      try {
        const nextRegistry = await getFunctionRegistry();
        if (cancelled) return;
        setRegistry(nextRegistry);
        setStatus("ready");
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiUnavailableError) {
          setStatus("fallback");
          return;
        }
        setStatus("fallback");
      }
    }

    void loadRegistry();

    return () => {
      cancelled = true;
    };
  }, []);

  const counts = useMemo(() => {
    return EXPOSURE_ORDER.reduce<Record<FunctionRegistryEntry["exposure"], number>>(
      (acc, exposure) => {
        acc[exposure] = registry.filter((entry) => entry.exposure === exposure).length;
        return acc;
      },
      {
        user: 0,
        advanced: 0,
        team: 0,
        admin: 0,
        "internal-only": 0,
      }
    );
  }, [registry]);

  const highlightedEntries = registry
    .filter((entry) => entry.exposure === mode || (mode === "advanced" && entry.exposure === "user"))
    .slice(0, 10);

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <SectionTitle eyebrow={meta.eyebrow} title={meta.title} />
        <p className="mt-3 max-w-3xl text-sm text-ink/75">{meta.description}</p>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <Badge tone={meta.tone}>Live function registry</Badge>
          <Badge tone="neutral">{status === "ready" ? "Connected" : status === "fallback" ? "Fallback mode" : "Loading"}</Badge>
          <Badge tone="info">{registry.length} mapped functions</Badge>
        </div>
      </Panel>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="User" value={counts.user} accent="text-teal" />
        <MetricCard label="Advanced" value={counts.advanced} accent="text-violet" />
        <MetricCard label="Team" value={counts.team} accent="text-amber" />
        <MetricCard label="Admin" value={counts.admin} accent="text-coral" />
        <MetricCard label="Internal" value={counts["internal-only"]} accent="text-ink" />
      </section>

      <Panel className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle eyebrow="Coverage" title="Visibility proof by backend function" />
          <div className="flex items-center gap-2 text-xs text-ink/65">
            <Workflow className="h-3.5 w-3.5" />
            Frontend route boundaries remain explicit.
          </div>
        </div>

        <div className="mt-4 overflow-hidden rounded-lg border border-line">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-fog/80 text-xs uppercase tracking-wide text-ink/55">
              <tr>
                <th className="px-3 py-2">Method</th>
                <th className="px-3 py-2">Path</th>
                <th className="px-3 py-2">Exposure</th>
                <th className="px-3 py-2">Frontend Route</th>
                <th className="px-3 py-2">Required Role</th>
                <th className="px-3 py-2">Audit Event</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {highlightedEntries.length > 0 ? (
                highlightedEntries.map((entry) => (
                  <tr key={`${entry.method}-${entry.path}`} className="bg-paper/95">
                    <td className="px-3 py-2 font-medium">{entry.method}</td>
                    <td className="px-3 py-2 font-mono text-xs text-ink/70">{entry.path}</td>
                    <td className="px-3 py-2">
                      <Badge tone={toneForExposure(entry.exposure)}>{entry.exposure}</Badge>
                    </td>
                    <td className="px-3 py-2 text-ink/70">{entry.frontendRoute}</td>
                    <td className="px-3 py-2 text-ink/70">{entry.requiredRole}</td>
                    <td className="px-3 py-2 font-mono text-xs text-ink/70">{entry.auditEvent}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-3 py-6 text-sm text-ink/60" colSpan={6}>
                    {status === "loading" ? "Loading visibility registry..." : "Registry unavailable; fallback mode is active."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle eyebrow="Boundary Notes" title="How to read the registry" />
          <Shield className="h-4 w-4 text-teal" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <NoteCard
            icon={CheckCircle2}
            title="User surface"
            text="Primary end-user flows stay in the dashboard, review, and market-intelligence routes."
          />
          <NoteCard
            icon={AlertTriangle}
            title="Advanced boundary"
            text="Calibration, scorecard, provider, and other operator controls remain grouped behind /advanced."
          />
          <NoteCard
            icon={Table2}
            title="Admin boundary"
            text="Workflow templates and privileged operations stay isolated in /admin with explicit review context."
          />
        </div>
      </Panel>
    </div>
  );
}

function MetricCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <Panel className="p-4">
      <p className="text-sm text-ink/70">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold", accent)}>{value}</p>
    </Panel>
  );
}

function NoteCard({ icon: Icon, title, text }: { icon: ComponentType<{ className?: string }>; title: string; text: string }) {
  return (
    <div className="rounded-lg border border-line bg-fog/70 p-3 text-sm">
      <div className="flex items-center gap-2 font-semibold text-ink">
        <Icon className="h-4 w-4 text-teal" />
        {title}
      </div>
      <p className="mt-2 text-ink/70">{text}</p>
    </div>
  );
}

function toneForExposure(exposure: FunctionRegistryEntry["exposure"]): "neutral" | "good" | "warn" | "bad" | "info" {
  switch (exposure) {
    case "user":
      return "good";
    case "advanced":
      return "info";
    case "team":
      return "warn";
    case "admin":
      return "bad";
    default:
      return "neutral";
  }
}
