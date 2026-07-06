"use client";

import Link from "next/link";
import {
  ApprovalWorkflowPanel,
  CommentsPanel,
  PacketSharingPanel,
  TemplateCreatePanel,
  TemplateLibraryPanel,
  TemplatePublishPanel,
  WorkspaceManagerPanel
} from "@/components/advanced-panels";
import { Badge, Panel, SectionTitle } from "@/components/ui";

export default function TeamPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Team" title="Shared decision workflows" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/75">
              Workspaces, packet collaboration, approvals, and reusable workflow templates for teams reviewing
              investment decisions together.
            </p>
          </div>
          <Badge tone="info">7 panels</Badge>
        </div>
      </Panel>

      <Panel className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionTitle eyebrow="Governance" title="Team member management" />
          <Link href="/governance/team-management" className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-teal">
            Open team admin
          </Link>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/70">
          Role assignment and invitations stay in the governance management route; day-to-day collaboration lives here.
        </p>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Collaboration" title="Workspaces and approvals" />
      </Panel>
      <section className="grid gap-4 xl:grid-cols-2">
        <WorkspaceManagerPanel />
        <PacketSharingPanel />
        <CommentsPanel />
        <ApprovalWorkflowPanel />
      </section>

      <Panel className="p-5">
        <SectionTitle eyebrow="Templates" title="Reusable workflows" />
      </Panel>
      <section className="grid gap-4 xl:grid-cols-2">
        <TemplateLibraryPanel />
        <TemplateCreatePanel />
        <TemplatePublishPanel />
      </section>
    </div>
  );
}
