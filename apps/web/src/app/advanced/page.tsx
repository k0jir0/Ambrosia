"use client";

import type { ComponentType } from "react";
import {
  AlertQueuePanel,
  ApprovalWorkflowPanel,
  AsyncJobQueuePanel,
  CalibrableBandPanel,
  CalibrableCohortPanel,
  CalibrableDetailPanel,
  CalibrationAlertsPanel,
  CalibrationHealthPanel,
  CertificationPanel,
  CommentsPanel,
  FeedbackHistoryPanel,
  FeedbackRecordPanel,
  JobDetailsPanel,
  MetricsScoreboardPanel,
  PacketLibraryPanel,
  PacketSharingPanel,
  ProviderStatusPanel,
  ReviewArchivePanel,
  ScannerLaunchPanel,
  SystemHealthPanel,
  TemplateCreatePanel,
  TemplateLibraryPanel,
  TemplatePublishPanel,
  ToolBoundariesPanel,
  WorkspaceManagerPanel
} from "@/components/advanced-panels";
import { Badge, Panel, SectionTitle } from "@/components/ui";

type AdvancedGroup = {
  title: string;
  eyebrow: string;
  description: string;
  endpointGroup: string;
  defaultOpen?: boolean;
  panels: ComponentType[];
};

const ADVANCED_GROUPS: AdvancedGroup[] = [
  {
    title: "Calibration & Feedback",
    eyebrow: "Quality Loop",
    description: "Confidence calibration, outcome feedback, cohort review, and anomaly visibility.",
    endpointGroup: "GET /metrics, GET /feedback/*, POST /feedback/record",
    panels: [
      CalibrableBandPanel,
      CalibrableCohortPanel,
      CalibrationHealthPanel,
      CalibrationAlertsPanel,
      FeedbackRecordPanel,
      FeedbackHistoryPanel,
      CalibrableDetailPanel
    ]
  },
  {
    title: "Team Collaboration",
    eyebrow: "Governance",
    description: "Workspace management, packet sharing, comments, and approval workflow proof.",
    endpointGroup: "POST /workspaces, POST /packets/{id}/comments, POST /packets/{id}/approval",
    panels: [WorkspaceManagerPanel, PacketSharingPanel, CommentsPanel, ApprovalWorkflowPanel]
  },
  {
    title: "Workflow Templates",
    eyebrow: "Marketplace",
    description: "Template browse, create, publish, archive, and version-management surfaces.",
    endpointGroup: "GET /workflows/templates, POST /workflows/templates/{id}/publish",
    panels: [TemplateLibraryPanel, TemplateCreatePanel, TemplatePublishPanel]
  },
  {
    title: "Admin & Monitoring",
    eyebrow: "Default Proof Surface",
    description: "Open by default because technical reviewers first need system health, provider status, tool boundaries, alerts, and evidence gates.",
    endpointGroup: "GET /health/detailed, GET /providers/status, GET /tools/boundaries, GET /alerts/queue",
    defaultOpen: true,
    panels: [
      SystemHealthPanel,
      MetricsScoreboardPanel,
      CertificationPanel,
      AlertQueuePanel,
      ProviderStatusPanel,
      ToolBoundariesPanel
    ]
  },
  {
    title: "Async Jobs",
    eyebrow: "Execution Queue",
    description: "Background scanner, backtest, and report job controls with progress visibility.",
    endpointGroup: "GET /jobs, GET /jobs/{id}, POST /scanner/run/async",
    panels: [AsyncJobQueuePanel, JobDetailsPanel, ScannerLaunchPanel]
  },
  {
    title: "Archive & Search",
    eyebrow: "Decision Memory",
    description: "Packet and review lookup surfaces for reusable, searchable, auditable history.",
    endpointGroup: "GET /packets, GET /reviews",
    panels: [PacketLibraryPanel, ReviewArchivePanel]
  }
];

const PROVIDER_MODES = ["Local deterministic", "Ollama local", "Hosted", "Hybrid"];

export default function AdvancedPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Advanced" title="Operator and instrumentation surface" />
            <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
              This page is the control-plane proof layer for Ambrosia. It exposes the advanced panel inventory
              from the frontend evolution plan while keeping most groups collapsed until a reviewer needs the detail.
            </p>
          </div>
          <Badge tone="info">25 panels / 6 groups</Badge>
        </div>
      </Panel>

      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionTitle eyebrow="Demo Mode" title="Provider path is visible" />
          <Badge tone="warn">Selection is demonstrational until wired to runtime controls</Badge>
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-4">
          {PROVIDER_MODES.map((mode) => (
            <button
              type="button"
              key={mode}
              className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-2 text-left text-sm font-semibold text-ink transition hover:border-teal/50"
            >
              {mode}
              <span className="mt-1 block text-xs font-normal text-ink/60">Shown in packet providerInfo and fallback badges.</span>
            </button>
          ))}
        </div>
      </Panel>

      <section className="space-y-3">
        {ADVANCED_GROUPS.map((group) => (
          <details key={group.title} open={group.defaultOpen} className="rounded-lg border border-line bg-paper">
            <summary className="cursor-pointer list-none p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-teal">{group.eyebrow}</p>
                  <h2 className="text-base font-semibold text-ink">{group.title}</h2>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">{group.description}</p>
                </div>
                <Badge tone={group.defaultOpen ? "good" : "neutral"}>{group.panels.length} panels</Badge>
              </div>
              <p className="mt-3 rounded-md border border-line bg-fog px-2 py-1 text-xs text-ink/60">{group.endpointGroup}</p>
            </summary>
            <div className="grid gap-4 border-t border-line p-5 xl:grid-cols-2">
              {group.panels.map((PanelComponent) => (
                <PanelComponent key={PanelComponent.name} />
              ))}
            </div>
          </details>
        ))}
      </section>
    </div>
  );
}
