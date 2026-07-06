"use client";

import Link from "next/link";
import {
  CheckCircle2,
  Clock3,
  FileText,
  LayoutTemplate,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  ShieldCheck,
  UserPlus,
  Users
} from "lucide-react";
import { Badge, Panel, SectionTitle, cn } from "@/components/ui";

type Workspace = {
  name: string;
  focus: string;
  members: number;
  openReviews: number;
  approvalsDue: number;
};

type ReviewItem = {
  ticker: string;
  title: string;
  owner: string;
  state: "Ready" | "Needs risk" | "In review";
  confidence: number;
  approvals: string;
  updated: string;
  tone: "good" | "warn" | "info";
};

type ApprovalStep = {
  name: string;
  role: string;
  state: "approved" | "pending" | "waiting";
  timestamp: string;
};

type Member = {
  name: string;
  role: string;
  load: number;
  status: "active" | "reviewing" | "away";
};

type Message = {
  author: string;
  role: string;
  body: string;
  time: string;
};

type Template = {
  name: string;
  scope: string;
  used: string;
  owner: string;
};

const WORKSPACES: Workspace[] = [
  { name: "Risk Committee", focus: "Trades awaiting sign-off", members: 4, openReviews: 6, approvalsDue: 3 },
  { name: "PM Desk", focus: "Portfolio sizing and follow-ups", members: 5, openReviews: 8, approvalsDue: 2 },
  { name: "Q3 Strategy", focus: "Macro and sector theses", members: 3, openReviews: 4, approvalsDue: 1 }
];

const REVIEW_QUEUE: ReviewItem[] = [
  {
    ticker: "SPY",
    title: "Breadth confirmation after pullback",
    owner: "Alice Smith",
    state: "Ready",
    confidence: 72,
    approvals: "2/3",
    updated: "8m ago",
    tone: "good"
  },
  {
    ticker: "NVDA",
    title: "Semis momentum after valuation reset",
    owner: "Bob Jones",
    state: "Needs risk",
    confidence: 64,
    approvals: "1/3",
    updated: "24m ago",
    tone: "warn"
  },
  {
    ticker: "TLT",
    title: "Duration hedge into softer growth tape",
    owner: "Maya Patel",
    state: "In review",
    confidence: 58,
    approvals: "0/2",
    updated: "51m ago",
    tone: "info"
  },
  {
    ticker: "XLF",
    title: "Financials rotation on curve steepening",
    owner: "Charlie Lee",
    state: "Ready",
    confidence: 69,
    approvals: "2/2",
    updated: "1h ago",
    tone: "good"
  }
];

const APPROVAL_STEPS: ApprovalStep[] = [
  { name: "Alice Smith", role: "Portfolio Manager", state: "approved", timestamp: "14:23" },
  { name: "Bob Jones", role: "Risk Committee", state: "pending", timestamp: "Due 15:30" },
  { name: "Charlie Lee", role: "Execution", state: "waiting", timestamp: "Queued" }
];

const MEMBERS: Member[] = [
  { name: "Alice Smith", role: "PM", load: 3, status: "reviewing" },
  { name: "Bob Jones", role: "Risk", load: 2, status: "active" },
  { name: "Maya Patel", role: "Analyst", load: 4, status: "active" },
  { name: "Charlie Lee", role: "Trader", load: 1, status: "away" }
];

const MESSAGES: Message[] = [
  {
    author: "Alice Smith",
    role: "PM",
    body: "SPY packet is ready once the risk note lands. Keep the approval open.",
    time: "8m"
  },
  {
    author: "Bob Jones",
    role: "Risk",
    body: "NVDA needs updated factor overlap before I sign off.",
    time: "18m"
  },
  {
    author: "Maya Patel",
    role: "Analyst",
    body: "I added the breadth table and linked the source packet.",
    time: "32m"
  }
];

const TEMPLATES: Template[] = [
  { name: "Swing Setup", scope: "Team", used: "Today", owner: "Alice" },
  { name: "Risk Committee Packet", scope: "Committee", used: "2d ago", owner: "Bob" },
  { name: "Macro Watch", scope: "Shared", used: "4d ago", owner: "Maya" }
];

export default function TeamPage() {
  const activeWorkspace = WORKSPACES[0];

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle eyebrow="Team" title="Risk Committee workspace" />
            <p className="mt-3 max-w-4xl text-sm leading-6 text-ink/75">
              {activeWorkspace.focus} across {activeWorkspace.members} members.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="info">Live membership admin</Badge>
              <Badge tone="warn">Workspace workflow demo</Badge>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/governance/team-management" className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-teal">
              <Users className="h-4 w-4" />
              Team admin
            </Link>
            <button type="button" disabled className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog opacity-60">
              <Plus className="h-4 w-4" />
              New workspace
            </button>
          </div>
        </div>
      </Panel>

      <section className="grid gap-3 xl:grid-cols-[1.2fr_1fr]">
        <Panel className="p-2">
          <div className="grid gap-2 md:grid-cols-3">
            {WORKSPACES.map((workspace, index) => (
              <button
                key={workspace.name}
                type="button"
                disabled={index !== 0}
                className={cn(
                  "focus-ring rounded-md border p-3 text-left transition",
                  index === 0 ? "border-teal/40 bg-teal/10" : "border-line bg-fog/60 opacity-60"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-ink">{workspace.name}</p>
                    <p className="mt-1 min-h-8 text-xs leading-4 text-ink/65">{workspace.focus}</p>
                  </div>
                  <Badge tone={index === 0 ? workspace.approvalsDue > 2 ? "warn" : "neutral" : "warn"}>{index === 0 ? `${workspace.approvalsDue} due` : "demo"}</Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/65">
                  <span>{workspace.members} members</span>
                  <span>{workspace.openReviews} reviews</span>
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-3">
          <Kpi label="Open reviews" value={String(activeWorkspace.openReviews)} />
          <Kpi label="Approvals due" value={String(activeWorkspace.approvalsDue)} tone="warn" />
          <Kpi label="Members online" value="3/4" tone="good" />
        </section>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.9fr)]">
        <Panel className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SectionTitle eyebrow="Review Queue" title="Shared packet queue" />
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <div className="flex min-w-60 items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2">
                <Search className="h-4 w-4 shrink-0 text-ink/60" />
                <input className="focus-ring w-full bg-transparent text-sm" placeholder="Search packets..." />
              </div>
              <button type="button" className="focus-ring rounded-md border border-line bg-fog/70 p-2 text-ink/70" aria-label="Queue options">
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {REVIEW_QUEUE.map((item) => (
              <div key={`${item.ticker}-${item.title}`} className="rounded-md border border-line bg-fog/70 p-3">
                <div className="grid gap-3 md:grid-cols-[80px_minmax(0,1fr)_140px_120px_80px] md:items-center">
                  <Badge tone="info">{item.ticker}</Badge>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{item.title}</p>
                    <p className="mt-1 text-xs text-ink/60">{item.owner} - updated {item.updated}</p>
                  </div>
                  <Badge tone={item.tone}>{item.state}</Badge>
                  <div className="text-sm text-ink/75">
                    <span className="font-semibold text-ink">{item.confidence}%</span> confidence
                  </div>
                  <div className="text-sm font-semibold text-ink/75">{item.approvals}</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel className="p-5">
            <SectionTitle eyebrow="Approval Lane" title="SPY sign-off" />
            <div className="mt-4 space-y-2">
              {APPROVAL_STEPS.map((step) => (
                <div key={step.name} className="flex items-center justify-between gap-3 rounded-md border border-line bg-fog/70 p-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <ApprovalIcon state={step.state} />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{step.name}</p>
                      <p className="text-xs text-ink/60">{step.role}</p>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-ink/60">{step.timestamp}</span>
                </div>
              ))}
            </div>
            <button type="button" disabled className="focus-ring mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog opacity-60">
              <ShieldCheck className="h-4 w-4" />
              Request sign-off
            </button>
          </Panel>

          <Panel className="p-5">
            <div className="flex items-center justify-between gap-3">
              <SectionTitle eyebrow="Members" title="Coverage" />
              <Link href="/governance/team-management" className="focus-ring rounded-md border border-line bg-fog/70 p-2 text-ink/70" aria-label="Invite member">
                <UserPlus className="h-4 w-4" />
              </Link>
            </div>
            <div className="mt-4 grid gap-2">
              {MEMBERS.map((member) => (
                <div key={member.name} className="flex items-center justify-between gap-3 rounded-md border border-line bg-fog/70 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{member.name}</p>
                    <p className="text-xs text-ink/60">{member.role}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={member.status === "active" ? "good" : member.status === "reviewing" ? "info" : "neutral"}>{member.status}</Badge>
                    <span className="w-14 text-right text-xs text-ink/60">{member.load} open</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)]">
        <Panel className="p-5">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Discussion" title="Packet thread" />
            <Badge tone="info">SPY</Badge>
          </div>
          <div className="mt-4 grid gap-3">
            {MESSAGES.map((message) => (
              <div key={`${message.author}-${message.time}`} className="rounded-md border border-line bg-fog/70 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-ink">{message.author}</p>
                    <p className="text-xs text-ink/60">{message.role}</p>
                  </div>
                  <span className="text-xs text-ink/55">{message.time}</span>
                </div>
                <p className="mt-2 text-sm leading-6 text-ink/75">{message.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <input disabled className="focus-ring min-w-0 flex-1 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm opacity-60" placeholder="Thread demo is read-only" />
            <button type="button" disabled className="focus-ring inline-flex shrink-0 items-center gap-2 rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog opacity-60">
              <Send className="h-4 w-4" />
              Send
            </button>
          </div>
        </Panel>

        <Panel className="p-5">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Templates" title="Reusable workflows" />
            <button type="button" disabled className="focus-ring rounded-md border border-line bg-fog/70 p-2 text-ink/70 opacity-60" aria-label="Create template">
              <Plus className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {TEMPLATES.map((template) => (
              <div key={template.name} className="rounded-md border border-line bg-fog/70 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-paper">
                      <LayoutTemplate className="h-4 w-4 text-teal" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{template.name}</p>
                      <p className="text-xs text-ink/60">{template.scope} - {template.owner}</p>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-ink/55">{template.used}</span>
                </div>
              </div>
            ))}
          </div>
          <button type="button" disabled className="focus-ring mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-sm font-semibold text-ink/80 opacity-60">
            <FileText className="h-4 w-4" />
            Save current packet as template
          </button>
        </Panel>
      </section>
    </div>
  );
}

function Kpi({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "good" | "warn" }) {
  return (
    <Panel className="p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/55">{label}</p>
      <p className={cn("mt-2 text-2xl font-semibold", tone === "good" ? "text-teal" : tone === "warn" ? "text-amber" : "text-ink")}>{value}</p>
    </Panel>
  );
}

function ApprovalIcon({ state }: { state: ApprovalStep["state"] }) {
  if (state === "approved") return <CheckCircle2 className="h-5 w-5 shrink-0 text-teal" />;
  if (state === "pending") return <Clock3 className="h-5 w-5 shrink-0 text-amber" />;
  return <MessageSquare className="h-5 w-5 shrink-0 text-ink/45" />;
}
