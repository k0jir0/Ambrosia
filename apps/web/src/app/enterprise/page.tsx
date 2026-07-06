"use client";

import { useEffect, useState } from "react";
import { Panel, SectionTitle } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, textOrFallback } from "@/lib/index84-control-plane";

type EnterpriseData = {
  readiness: Record<string, unknown> | null;
  security: Record<string, unknown> | null;
};

export default function EnterprisePage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading enterprise readiness...");
  const [data, setData] = useState<EnterpriseData>({ readiness: null, security: null });

  async function load() {
    setStatus("loading");
    const [readiness, security] = await Promise.all([
      fetchControlPlane("/enterprise/readiness"),
      fetchControlPlane("/enterprise/support/security-packet"),
    ]);

    if (!readiness.ok || !security.ok) {
      const current = mapStatus(Math.max(readiness.status, security.status), null);
      setStatus(current);
      setMessage(readiness.message || security.message || "Enterprise endpoints are unavailable.");
      return;
    }

    setData({
      readiness: (readiness.data as Record<string, unknown>) || null,
      security: (security.data as Record<string, unknown>) || null,
    });
    setStatus("success");
    setMessage("Enterprise state loaded.");
  }

  useEffect(() => {
    void load();
  }, []);

  if (status === "loading") return <RouteLoading title="Enterprise" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Index84 Surface" title="Enterprise" />
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
          Service-account, SSO, audit-export, and security-packet posture for governed enterprise operations.
        </p>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <Panel className="p-6">
        <SectionTitle eyebrow="Readiness" title="Enterprise readiness summary" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Schema" value={textOrFallback(data.readiness?.schemaVersion)} />
          <Metric label="Service accounts" value={textOrFallback(data.readiness?.serviceAccounts)} />
          <Metric label="Audit exports" value={textOrFallback(data.readiness?.auditExports)} />
          <Metric label="SSO provider" value={textOrFallback((data.readiness?.sso as Record<string, unknown> | undefined)?.provider)} />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Security Packet" title="Support and retention posture" />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Schema" value={textOrFallback(data.security?.schemaVersion)} />
          <Metric label="Token rotation" value={textOrFallback((data.security?.securityReview as Record<string, unknown> | undefined)?.tokenRotation)} />
          <Metric label="Support SLA" value={textOrFallback((data.security?.supportPolicy as Record<string, unknown> | undefined)?.sla)} />
          <Metric label="Audit retention" value={textOrFallback((data.security?.retentionPolicy as Record<string, unknown> | undefined)?.auditDays)} />
        </div>
      </Panel>

      <Panel className="p-6">
        <SectionTitle eyebrow="Operational Actions" title="Enterprise checklist" />
        <ul className="mt-3 space-y-2 text-sm text-ink/80">
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Create scoped service accounts for CI and internal automations.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Rotate and revoke credentials through lifecycle operations.</li>
          <li className="rounded-md border border-line bg-fog/70 px-3 py-2">Use audit export and security packet outputs for governance review.</li>
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
