"use client";

import {
  AlertQueuePanel,
  CertificationPanel,
  MetricsScoreboardPanel,
  ProviderStatusPanel,
  SystemHealthPanel,
  ToolBoundariesPanel
} from "@/components/advanced-panels";
import { Badge, Panel, SectionTitle } from "@/components/ui";

export default function AdminPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Admin" title="Operational control center" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/75">
              System health, provider availability, alerting, tool limits, and certification evidence for operators.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="info">Status evidence</Badge>
            <Badge tone="warn">Controls require API wiring</Badge>
          </div>
        </div>
      </Panel>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle eyebrow="Read-only" title="Live status and evidence" />
        <Badge tone="neutral">operator safe</Badge>
      </div>
      <section className="grid gap-4 xl:grid-cols-2">
        <SystemHealthPanel />
        <MetricsScoreboardPanel />
        <CertificationPanel />
        <AlertQueuePanel />
        <ProviderStatusPanel />
        <ToolBoundariesPanel />
      </section>
    </div>
  );
}
