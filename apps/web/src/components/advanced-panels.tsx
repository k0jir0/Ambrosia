"use client";

import { useState } from "react";
import { Download, Eye, Filter, Plus, Search, Trash2 } from "lucide-react";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { Badge, Panel, SectionTitle } from "./ui";

export function ProviderModePanel() {
  const modes = ["Local deterministic", "Ollama local", "Hosted", "Hybrid"];

  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionTitle eyebrow="Runtime Provider Path" title="Provider path is visible" />
        <Badge tone="warn">Selection is demonstrational until wired to runtime controls</Badge>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-4">
        {modes.map((mode) => (
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
  );
}

// ============================================================================
// SECTION 1: CALIBRATION & FEEDBACK PANELS
// ============================================================================

export function CalibrableBandPanel() {
  const bandData = [
    { band: "50-60%", winRate: 52, samples: 12, avgReturn: -0.5 },
    { band: "60-70%", winRate: 65, samples: 28, avgReturn: 0.8 },
    { band: "70-80%", winRate: 73, samples: 34, avgReturn: 1.2 },
    { band: "80-90%", winRate: 81, samples: 22, avgReturn: 1.8 },
    { band: "90-100%", winRate: 88, samples: 8, avgReturn: 2.3 },
  ];

  const getColor = (winRate: number) => {
    if (winRate >= 70) return "#10b981";
    if (winRate >= 50) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <Panel>
      <SectionTitle eyebrow="Calibration" title="Performance by confidence band" />
      <div className="mt-4 space-y-4">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={bandData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="band" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }} />
            <Bar dataKey="winRate" fill="#3b82f6" radius={[8, 8, 0, 0]} />
            <Bar dataKey="samples" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="grid gap-2 text-xs">
          {bandData.map((item) => (
            <div key={item.band} className="flex items-center justify-between rounded bg-slate-900 p-2">
              <div className="flex items-center gap-2">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: getColor(item.winRate) }}
                />
                <span className="font-mono">{item.band}</span>
              </div>
              <div className="flex items-center gap-4">
                <span>Win: {item.winRate}%</span>
                <span>N: {item.samples}</span>
                <span className={item.avgReturn > 0 ? "text-green-400" : "text-red-400"}>
                  {item.avgReturn > 0 ? "+" : ""}{item.avgReturn}%
                </span>
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <button className="flex-1 rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            <Eye className="mr-2 inline h-4 w-4" /> View Details
          </button>
          <button className="flex-1 rounded bg-slate-700 px-3 py-2 text-sm font-semibold hover:bg-slate-600">
            <Download className="mr-2 inline h-4 w-4" /> Export
          </button>
        </div>
      </div>
    </Panel>
  );
}

export function CalibrableCohortPanel() {
  const cohortData = [
    { ticker: "SPY", assetClass: "ETF", horizon: "2-6w", samples: 23, accuracy: 78, avgConf: 72, winRate: 74, status: "ok" },
    { ticker: "QQQ", assetClass: "ETF", horizon: "2-6w", samples: 18, accuracy: 71, avgConf: 68, winRate: 67, status: "warn" },
    { ticker: "AAPL", assetClass: "Stock", horizon: "1-2w", samples: 12, accuracy: 65, avgConf: 62, winRate: 58, status: "warn" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Calibration" title="Performance by cohort" />
      <div className="mt-4 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Filter ticker..."
            className="flex-1 rounded bg-slate-900 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
          />
          <button className="rounded bg-slate-700 px-2 py-1 text-xs hover:bg-slate-600">
            <Filter className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-2 overflow-y-auto max-h-64">
          {cohortData.map((row) => (
            <div key={`${row.ticker}-${row.horizon}`} className="rounded bg-slate-900 p-2 text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono">
                  <span className="font-semibold">{row.ticker}</span>
                  <Badge>{row.assetClass}</Badge>
                  <Badge tone="info">{row.horizon}</Badge>
                </div>
                <div
                  className={`h-3 w-3 rounded-full ${
                    row.status === "ok"
                      ? "bg-green-500"
                      : row.status === "warn"
                        ? "bg-yellow-500"
                        : "bg-red-500"
                  }`}
                />
              </div>
              <div className="mt-1 flex justify-between text-slate-400">
                <span>N={row.samples}</span>
                <span>Accuracy {row.accuracy}%</span>
                <span>Win {row.winRate}%</span>
                <span>Avg conf {row.avgConf}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function CalibrationHealthPanel() {
  const metrics = [
    { name: "Review Validity", value: 78, target: 75, status: "ok" },
    { name: "Decision Consistency", value: 100, target: 100, status: "ok" },
    { name: "Packet Integrity", value: 92, target: 90, status: "ok" },
    { name: "Data Quality", value: 96, target: 95, status: "ok" },
    { name: "Agent Consensus", value: 68, target: 70, status: "warn" },
    { name: "Backtest Validity", value: 0.78, target: 0.75, status: "ok" },
    { name: "Risk Estimate", value: 82, target: 80, status: "ok" },
    { name: "Confidence Calibration", value: 73, target: 75, status: "warn" },
  ];

  const getStatusColor = (status: string) =>
    status === "ok" ? "text-green-400" : status === "warn" ? "text-yellow-400" : "text-red-400";
  const getStatusIcon = (status: string) =>
    status === "ok" ? "✓" : status === "warn" ? "⚠" : "✗";

  return (
    <Panel>
      <SectionTitle eyebrow="System Health" title="Calibration metrics scorecard" />
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        {metrics.map((metric) => (
          <div key={metric.name} className="rounded bg-slate-900 p-3">
            <div className="flex items-center justify-between">
              <span className="truncate font-semibold">{metric.name}</span>
              <span className={`font-bold ${getStatusColor(metric.status)}`}>
                {getStatusIcon(metric.status)}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-slate-400">
                {metric.value}{typeof metric.value === "number" && metric.value > 1 ? "%" : ""}
              </span>
              <span className="text-slate-500">
                target: {metric.target}{typeof metric.target === "number" && metric.target > 1 ? "%" : ""}
              </span>
            </div>
            <div className="mt-1 h-1 w-full bg-slate-800 rounded overflow-hidden">
              <div
                className={`h-full ${
                  metric.status === "ok"
                    ? "bg-green-500"
                    : metric.status === "warn"
                      ? "bg-yellow-500"
                      : "bg-red-500"
                }`}
                style={{
                  width: `${Math.min((metric.value / (metric.target * 1.2)) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function CalibrationAlertsPanel() {
  const alerts = [
    {
      id: 1,
      severity: "red",
      type: "Metric Threshold",
      message: "Agent Consensus dropped below 70% (now 68%)",
      timestamp: "2 min ago",
    },
    {
      id: 2,
      severity: "yellow",
      type: "Trend Alert",
      message: "Confidence band 60-70% accuracy trending down",
      timestamp: "15 min ago",
    },
    {
      id: 3,
      severity: "yellow",
      type: "Limit Warning",
      message: "System approaching daily idea limit (47/50)",
      timestamp: "32 min ago",
    },
  ];

  const severityColor = {
    red: "bg-red-500/20 text-red-400 border-red-500/50",
    yellow: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
    green: "bg-green-500/20 text-green-400 border-green-500/50",
  };

  return (
    <Panel>
      <SectionTitle eyebrow="Alerts" title="Calibration anomalies & warnings" />
      <div className="mt-4 space-y-2">
        {alerts.map((alert) => (
          <div key={alert.id} className={`rounded border p-3 text-xs ${severityColor[alert.severity as keyof typeof severityColor]}`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="font-semibold">{alert.type}</div>
                <div className="mt-1 text-slate-300">{alert.message}</div>
              </div>
              <div className="text-slate-500 ml-2">{alert.timestamp}</div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function FeedbackRecordPanel() {
  const [formData, setFormData] = useState({
    packetId: "",
    outcome: "won",
    actualReturn: "",
    confidenceMatch: "matched",
    dateSettled: "",
    notes: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Feedback recorded:", formData);
    setFormData({
      packetId: "",
      outcome: "won",
      actualReturn: "",
      confidenceMatch: "matched",
      dateSettled: "",
      notes: "",
    });
  };

  return (
    <Panel>
      <SectionTitle eyebrow="Feedback" title="Record trade outcome" />
      <form onSubmit={handleSubmit} className="mt-4 space-y-3 text-sm">
        <div>
          <label className="block text-xs font-semibold mb-1">Packet ID</label>
          <input
            type="text"
            placeholder="PKT-20260625-SPY-001"
            value={formData.packetId}
            onChange={(e) => setFormData({ ...formData, packetId: e.target.value })}
            className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-semibold mb-1">Outcome</label>
            <select
              value={formData.outcome}
              onChange={(e) => setFormData({ ...formData, outcome: e.target.value })}
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200"
            >
              <option>won</option>
              <option>lost</option>
              <option>partial_win</option>
              <option>breakeven</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1">Actual Return</label>
            <input
              type="text"
              placeholder="+$523 or +2.3%"
              value={formData.actualReturn}
              onChange={(e) => setFormData({ ...formData, actualReturn: e.target.value })}
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-semibold mb-1">Confidence Match</label>
            <select
              value={formData.confidenceMatch}
              onChange={(e) => setFormData({ ...formData, confidenceMatch: e.target.value })}
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200"
            >
              <option>exceeded</option>
              <option>matched</option>
              <option>underperformed</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1">Date Settled</label>
            <input
              type="date"
              value={formData.dateSettled}
              onChange={(e) => setFormData({ ...formData, dateSettled: e.target.value })}
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold mb-1">Notes</label>
          <textarea
            placeholder="Optional context about the outcome..."
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500 h-16 resize-none"
          />
        </div>
        <button
          type="submit"
          className="w-full rounded bg-green-600 px-3 py-2 font-semibold text-white hover:bg-green-700"
        >
          Record Feedback
        </button>
      </form>
    </Panel>
  );
}

export function FeedbackHistoryPanel() {
  const feedbackRecords = [
    { id: "FB-001", date: "2026-06-25", ticker: "SPY", outcome: "won", confidence: "exceeded", return: "+2.3%", packetId: "PKT-123" },
    { id: "FB-002", date: "2026-06-24", ticker: "AAPL", outcome: "lost", confidence: "underperformed", return: "-1.5%", packetId: "PKT-122" },
    { id: "FB-003", date: "2026-06-24", ticker: "QQQ", outcome: "won", confidence: "matched", return: "+1.8%", packetId: "PKT-121" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Feedback" title="Recorded outcomes & calibration" />
      <div className="mt-4 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search ticker or packet ID..."
            className="flex-1 rounded bg-slate-900 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
          />
          <button className="rounded bg-slate-700 px-2 py-1 text-xs hover:bg-slate-600">
            <Search className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-2 overflow-y-auto max-h-64">
          {feedbackRecords.map((record) => (
            <div key={record.id} className="flex items-center justify-between rounded bg-slate-900 p-2 text-xs">
              <div className="font-mono">
                <div className="font-semibold">{record.ticker}</div>
                <div className="text-slate-400">{record.date}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge>{record.outcome}</Badge>
                <span className={record.return.startsWith("+") ? "text-green-400" : "text-red-400"}>
                  {record.return}
                </span>
              </div>
              <button className="rounded hover:bg-slate-800 p-1">
                <Eye className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
        <button className="w-full rounded bg-slate-700 px-3 py-2 text-sm font-semibold hover:bg-slate-600">
          <Download className="mr-2 inline h-4 w-4" /> Export as CSV
        </button>
      </div>
    </Panel>
  );
}

export function CalibrableDetailPanel() {
  return (
    <Panel>
      <SectionTitle eyebrow="Feedback" title="Feedback record detail" />
      <div className="mt-4 space-y-4 text-sm">
        <div className="rounded bg-slate-900 p-3">
          <div className="text-xs font-semibold text-slate-400 uppercase">Decision Context</div>
          <div className="mt-2 space-y-1 font-mono text-sm">
            <div>Packet ID: PKT-20260625-SPY-001</div>
            <div>Ticker: SPY</div>
            <div>Decision Date: 2026-06-20 14:23:45</div>
            <div>Original Confidence: 72%</div>
            <div>Decision: PURSUE</div>
          </div>
        </div>
        <div className="rounded bg-slate-900 p-3">
          <div className="text-xs font-semibold text-slate-400 uppercase">Outcome Recorded</div>
          <div className="mt-2 space-y-1 font-mono text-sm">
            <div>Trade Result: WON</div>
            <div>Actual Return: +$523 (+2.3%)</div>
            <div>Confidence Match: EXCEEDED</div>
            <div>Settlement Date: 2026-06-25</div>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="flex-1 rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            Edit
          </button>
          <button className="flex-1 rounded bg-slate-700 px-3 py-2 text-sm font-semibold hover:bg-slate-600">
            <Trash2 className="mr-2 inline h-4 w-4" /> Delete
          </button>
        </div>
      </div>
    </Panel>
  );
}

// ============================================================================
// SECTION 2: TEAM COLLABORATION PANELS
// ============================================================================

export function WorkspaceManagerPanel() {
  const workspaces = [
    { id: 1, name: "My Ideas", members: 1, modified: "Today" },
    { id: 2, name: "Risk Committee", members: 4, modified: "2h ago" },
    { id: 3, name: "Q3 Strategy", members: 3, modified: "1d ago" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Team" title="Workspace management" />
      <div className="mt-4 space-y-3">
        <button className="w-full rounded bg-blue-600 px-3 py-2 font-semibold text-white hover:bg-blue-700">
          <Plus className="mr-2 inline h-4 w-4" /> Create Workspace
        </button>
        <div className="space-y-2">
          {workspaces.map((ws) => (
            <div key={ws.id} className="flex items-center justify-between rounded bg-slate-900 p-2 text-sm">
              <div>
                <div className="font-semibold">{ws.name}</div>
                <div className="text-xs text-slate-400">{ws.members} members</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">{ws.modified}</span>
                <button className="rounded hover:bg-slate-800 px-2 py-1 text-xs">Switch</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function PacketSharingPanel() {
  const [selected, setSelected] = useState<number[]>([]);

  const workspaces = [
    { id: 1, name: "My Ideas" },
    { id: 2, name: "Risk Committee" },
    { id: 3, name: "Q3 Strategy" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Team" title="Share packet with workspace" />
      <div className="mt-4 space-y-3">
        <div className="rounded bg-slate-900 p-2 text-xs">
          <div className="font-semibold">Packet: PKT-SPY-001</div>
          <div className="text-slate-400">Created 2h ago</div>
        </div>
        <div className="space-y-2">
          {workspaces.map((ws) => (
            <label key={ws.id} className="flex items-center gap-2 rounded hover:bg-slate-800 p-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selected.includes(ws.id)}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, ws.id]
                      : selected.filter((id) => id !== ws.id)
                  )
                }
                className="rounded"
              />
              <span className="text-sm">{ws.name}</span>
            </label>
          ))}
        </div>
        <button className="w-full rounded bg-green-600 px-3 py-2 font-semibold text-white hover:bg-green-700">
          Share to {selected.length} workspace{selected.length !== 1 ? "s" : ""}
        </button>
      </div>
    </Panel>
  );
}

export function CommentsPanel() {
  const comments = [
    { id: 1, author: "Alice Smith", time: "2h ago", text: "Strong setup, waiting for RSI confirmation" },
    { id: 2, author: "Bob Jones", time: "1.5h ago", text: "I see 35 on RSI bottom, looks good", isReply: true },
    { id: 3, author: "Charlie Lee", time: "45m ago", text: "Entry triggered, now watching exit signal" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Team" title="Packet discussion thread" />
      <div className="mt-4 space-y-3">
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {comments.map((comment) => (
            <div
              key={comment.id}
              className={`rounded p-2 text-xs ${comment.isReply ? "ml-4 bg-slate-900/50 border-l-2 border-blue-500" : "bg-slate-900"}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">{comment.author}</span>
                <span className="text-slate-500">{comment.time}</span>
              </div>
              <p className="mt-1 text-slate-300">{comment.text}</p>
            </div>
          ))}
        </div>
        <textarea
          placeholder="Add comment..."
          className="w-full rounded bg-slate-900 px-2 py-1 text-xs text-slate-200 placeholder-slate-500 resize-none h-12"
        />
        <button className="w-full rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700">
          Comment
        </button>
      </div>
    </Panel>
  );
}

export function ApprovalWorkflowPanel() {
  const approvals = [
    { name: "Alice Smith", role: "Owner", status: "approved", timestamp: "2026-06-20 14:23" },
    { name: "Bob Jones", role: "Risk Committee", status: "pending", timestamp: "2026-06-20 14:23" },
    { name: "Charlie Lee", role: "Trader", status: "unassigned", timestamp: null },
  ];

  const statusIcon = {
    approved: "✓",
    pending: "⏱",
    unassigned: "⚪",
  };

  const statusColor = {
    approved: "text-green-400",
    pending: "text-yellow-400",
    unassigned: "text-slate-400",
  };

  return (
    <Panel>
      <SectionTitle eyebrow="Team" title="Approval workflow & sign-offs" />
      <div className="mt-4 space-y-2">
        {approvals.map((approval, idx) => (
          <div key={idx} className="rounded bg-slate-900 p-2 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`font-bold text-lg ${statusColor[approval.status as keyof typeof statusColor]}`}>
                  {statusIcon[approval.status as keyof typeof statusIcon]}
                </span>
                <div>
                  <div className="font-semibold">{approval.name}</div>
                  <div className="text-slate-400">{approval.role}</div>
                </div>
              </div>
              {approval.timestamp && <span className="text-slate-400">{approval.timestamp}</span>}
            </div>
          </div>
        ))}
        <button className="w-full rounded bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700">
          Request Approval
        </button>
      </div>
    </Panel>
  );
}

// ============================================================================
// SECTION 3: WORKFLOW TEMPLATES PANELS
// ============================================================================

export function TemplateLibraryPanel() {
  const templates = [
    { id: 1, name: "Daily Setup", rating: 5, users: "Me", lastUsed: "Today" },
    { id: 2, name: "Swing Setup", rating: 4, users: "Team", lastUsed: "2d ago" },
    { id: 3, name: "ML Signals", rating: 3, users: "47 users", lastUsed: "Marketplace" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Templates" title="Workflow template library" />
      <div className="mt-4 grid grid-cols-3 gap-2">
        {templates.map((tpl) => (
          <div key={tpl.id} className="rounded bg-slate-900 p-2 text-xs">
            <div className="font-semibold truncate">{tpl.name}</div>
            <div className="mt-1 text-slate-400">{"★".repeat(tpl.rating)}{"☆".repeat(5 - tpl.rating)}</div>
            <div className="mt-1 truncate text-slate-400">{tpl.lastUsed}</div>
            <button className="mt-2 w-full rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700">
              Load
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function TemplateCreatePanel() {
  return (
    <Panel>
      <SectionTitle eyebrow="Templates" title="Save as template" />
      <form className="mt-4 space-y-2 text-xs">
        <div>
          <label className="block font-semibold mb-1">Template Name</label>
          <input
            type="text"
            placeholder="Daily Setup"
            className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500"
          />
        </div>
        <div>
          <label className="block font-semibold mb-1">Description</label>
          <textarea
            placeholder="Brief description..."
            className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500 resize-none h-12"
          />
        </div>
        <div>
          <label className="block font-semibold mb-1">Visibility</label>
          <select className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200">
            <option>Private (only me)</option>
            <option>Team</option>
            <option>Public</option>
          </select>
        </div>
        <button
          type="button"
          className="w-full rounded bg-green-600 px-3 py-2 font-semibold text-white hover:bg-green-700"
        >
          Save Template
        </button>
      </form>
    </Panel>
  );
}

export function TemplatePublishPanel() {
  const versions = [
    { version: "1.2", date: "2026-06-25", status: "active", users: 3 },
    { version: "1.1", date: "2026-06-20", status: "archived", users: 2 },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Templates" title="Template version history" />
      <div className="mt-4 space-y-2">
        {versions.map((v) => (
          <div key={v.version} className="rounded bg-slate-900 p-2 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold">
                  Version {v.version}
                  {v.status === "active" && <Badge tone="good">Active</Badge>}
                </div>
                <div className="text-slate-400">{v.date}</div>
              </div>
              <div className="text-slate-400">{v.users} users</div>
            </div>
          </div>
        ))}
        <button className="w-full rounded bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700">
          Publish New Version
        </button>
      </div>
    </Panel>
  );
}

// ============================================================================
// SECTION 4: ADMIN & MONITORING PANELS
// ============================================================================

export function SystemHealthPanel() {
  const healthMetrics = [
    { label: "Status", value: "OPERATIONAL", color: "text-green-400" },
    { label: "Uptime", value: "47d 3h 22m", color: "text-green-400" },
    { label: "Response Time", value: "48ms", color: "text-green-400" },
    { label: "Error Rate", value: "0.02%", color: "text-green-400" },
    { label: "Request Rate", value: "2,341 req/min", color: "text-blue-400" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Admin" title="System health dashboard" />
      <div className="mt-4 space-y-2 text-xs">
        {healthMetrics.map((metric, idx) => (
          <div key={idx} className="flex items-center justify-between rounded bg-slate-900 p-2">
            <span className="text-slate-400">{metric.label}</span>
            <span className={`font-semibold font-mono ${metric.color}`}>{metric.value}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function MetricsScoreboardPanel() {
  // Reuse CalibrationHealthPanel logic
  return <CalibrationHealthPanel />;
}

export function CertificationPanel() {
  const gates = [
    { name: "Zero-downtime Health", status: "passing", detail: "Health check responding" },
    { name: "Feedback Loops Active", status: "passing", detail: "7/7 endpoints active" },
    { name: "Metrics Threshold", status: "passing", detail: "All metrics within target" },
    { name: "All Endpoints Responding", status: "passing", detail: "60/60 endpoints OK" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Certification" title="Index39 operational scorecard" />
      <div className="mt-4 space-y-3">
        <div className="rounded bg-green-500/20 border border-green-500/50 p-2 text-xs text-green-400">
          Status: ✓ CERTIFIED | Index: 39
        </div>
        <div className="space-y-2">
          {gates.map((gate, idx) => (
            <div key={idx} className="rounded bg-slate-900 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{gate.name}</span>
                <span className="text-green-400">✓ {gate.status}</span>
              </div>
              <div className="mt-1 text-slate-400">{gate.detail}</div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function AlertQueuePanel() {
  const alerts = [
    { id: 1, severity: "red", type: "Error", msg: "API response time exceeded 500ms", time: "2m ago" },
    { id: 2, severity: "yellow", type: "Warning", msg: "Scanner queue depth 47/50", time: "5m ago" },
    { id: 3, severity: "blue", type: "Info", msg: "Calibration metrics computed", time: "12m ago" },
  ];

  const severityBg = { red: "bg-red-500/20", yellow: "bg-yellow-500/20", blue: "bg-blue-500/20" };
  const severityText = { red: "text-red-400", yellow: "text-yellow-400", blue: "text-blue-400" };

  return (
    <Panel>
      <SectionTitle eyebrow="Alerts" title="System alert queue" />
      <div className="mt-4 space-y-2">
        {alerts.map((alert) => (
          <div key={alert.id} className={`rounded p-2 text-xs ${severityBg[alert.severity as keyof typeof severityBg]}`}>
            <div className="flex items-center justify-between">
              <span className={`font-semibold ${severityText[alert.severity as keyof typeof severityText]}`}>
                {alert.type}
              </span>
              <span className="text-slate-400">{alert.time}</span>
            </div>
            <div className="mt-1 text-slate-300">{alert.msg}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function ProviderStatusPanel() {
  const providers = [
    { name: "Polygon", status: "up", sla: "99.9%", responseTime: "23ms" },
    { name: "Yahoo Finance", status: "up", sla: "99.5%", responseTime: "45ms" },
    { name: "Crypto API", status: "up", sla: "99.2%", responseTime: "67ms" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Admin" title="Market data provider status" />
      <div className="mt-4 space-y-2">
        {providers.map((provider) => (
          <div key={provider.name} className="rounded bg-slate-900 p-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{provider.name}</span>
              <span className={`${provider.status === "up" ? "text-green-400" : "text-red-400"}`}>
                {provider.status === "up" ? "✓ UP" : "✗ DOWN"}
              </span>
            </div>
            <div className="mt-1 flex justify-between text-slate-400">
              <span>SLA: {provider.sla}</span>
              <span>{provider.responseTime}</span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function ToolBoundariesPanel() {
  const limits = [
    { name: "Daily Ideas", used: 47, limit: 50, warning: true },
    { name: "Daily Backtests", used: 18, limit: 25, warning: false },
    { name: "Concurrent Jobs", used: 2, limit: 10, warning: false },
    { name: "Daily Reports", used: 8, limit: 15, warning: false },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Admin" title="Tool boundaries & limits" />
      <div className="mt-4 space-y-2">
        {limits.map((limit) => (
          <div key={limit.name} className="rounded bg-slate-900 p-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{limit.name}</span>
              <span className={limit.warning ? "text-yellow-400" : "text-slate-400"}>
                {limit.used}/{limit.limit}
              </span>
            </div>
            <div className="mt-1 h-1 w-full bg-slate-800 rounded overflow-hidden">
              <div
                className={`h-full ${
                  (limit.used / limit.limit) * 100 > 90
                    ? "bg-red-500"
                    : (limit.used / limit.limit) * 100 > 70
                      ? "bg-yellow-500"
                      : "bg-green-500"
                }`}
                style={{ width: `${(limit.used / limit.limit) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ============================================================================
// SECTION 5: ASYNC JOBS PANELS
// ============================================================================

export function AsyncJobQueuePanel() {
  const jobs = [
    { id: "JOB-001", type: "Scanner", status: "running", progress: 45, submitted: "14:20", estComplete: "14:25" },
    { id: "JOB-002", type: "Backtest", status: "queued", progress: 0, submitted: "14:19", estComplete: "—" },
    { id: "JOB-003", type: "Report", status: "completed", progress: 100, submitted: "14:15", estComplete: "14:23" },
  ];

  const statusColor = { running: "text-blue-400", queued: "text-yellow-400", completed: "text-green-400" };

  return (
    <Panel>
      <SectionTitle eyebrow="Jobs" title="Async job queue" />
      <div className="mt-4 space-y-2">
        {jobs.map((job) => (
          <div key={job.id} className="rounded bg-slate-900 p-2 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono font-semibold">{job.id}</div>
                <div className="text-slate-400">{job.type}</div>
              </div>
              <span className={`font-semibold ${statusColor[job.status as keyof typeof statusColor]}`}>
                {job.status.toUpperCase()}
              </span>
            </div>
            {job.status === "running" && (
              <div className="mt-1 flex items-center gap-2">
                <div className="flex-1 h-1 bg-slate-800 rounded overflow-hidden">
                  <div className="h-full bg-blue-500" style={{ width: `${job.progress}%` }} />
                </div>
                <span className="text-slate-400">{job.progress}%</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function JobDetailsPanel() {
  return (
    <Panel>
      <SectionTitle eyebrow="Jobs" title="Job execution details" />
      <div className="mt-4 space-y-3 text-xs">
        <div className="rounded bg-slate-900 p-2">
          <div className="text-slate-400 font-semibold uppercase">Job Info</div>
          <div className="mt-2 font-mono space-y-1">
            <div>ID: JOB-20260625-001</div>
            <div>Type: Scanner</div>
            <div>Status: RUNNING</div>
            <div>Progress: 45% (12/27 items)</div>
          </div>
        </div>
        <div className="rounded bg-slate-900 p-2 max-h-32 overflow-y-auto">
          <div className="text-slate-400 font-semibold uppercase">Execution Log</div>
          <div className="mt-2 space-y-1 font-mono text-slate-400">
            <div>14:20:01 - Job started</div>
            <div>14:20:02 - Fetching market data</div>
            <div>14:20:05 - Data retrieved (50 tickers)</div>
            <div>14:20:45 - Scanned 12/27 ideas...</div>
          </div>
        </div>
        <button className="w-full rounded bg-slate-700 px-3 py-2 text-xs font-semibold hover:bg-slate-600">
          Cancel Job
        </button>
      </div>
    </Panel>
  );
}

export function ScannerLaunchPanel() {
  return (
    <Panel>
      <SectionTitle eyebrow="Jobs" title="Launch scanner job" />
      <form className="mt-4 space-y-2 text-xs">
        <div>
          <label className="block font-semibold mb-1">Watchlist</label>
          <select className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200">
            <option>Tech 50 ETF</option>
            <option>S&P 500</option>
            <option>Custom List</option>
          </select>
        </div>
        <div>
          <label className="block font-semibold mb-1">Technical Filters</label>
          <div className="space-y-1">
            <input
              type="text"
              placeholder="RSI < 30"
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500"
            />
            <input
              type="text"
              placeholder="Volume > 1M"
              className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200 placeholder-slate-500"
            />
          </div>
        </div>
        <div>
          <label className="block font-semibold mb-1">Sort By</label>
          <select className="w-full rounded bg-slate-900 px-2 py-1 text-slate-200">
            <option>Momentum (desc)</option>
            <option>Volatility (asc)</option>
            <option>Volume (desc)</option>
          </select>
        </div>
        <button
          type="button"
          className="w-full rounded bg-green-600 px-3 py-2 font-semibold text-white hover:bg-green-700"
        >
          Launch Scanner
        </button>
      </form>
    </Panel>
  );
}

// ============================================================================
// SECTION 6: ARCHIVE & SEARCH PANELS
// ============================================================================

export function PacketLibraryPanel() {
  const packets = [
    { ticker: "SPY", created: "2026-06-25", state: "DECIDED", decision: "PURSUE", outcome: "WON", conf: "72%" },
    { ticker: "AAPL", created: "2026-06-25", state: "DECIDED", decision: "WATCH", outcome: "—", conf: "58%" },
    { ticker: "TSLA", created: "2026-06-24", state: "DECIDED", decision: "REJECT", outcome: "LOST", conf: "42%" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Archive" title="Packet library & search" />
      <div className="mt-4 space-y-2">
        <input
          type="text"
          placeholder="Search packets..."
          className="w-full rounded bg-slate-900 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
        />
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {packets.map((p, idx) => (
            <div key={idx} className="flex items-center justify-between rounded bg-slate-900 p-2 text-xs">
              <span className="font-mono font-semibold">{p.ticker}</span>
              <div className="flex items-center gap-2">
                <Badge>{p.decision}</Badge>
                <span className={p.outcome === "WON" ? "text-green-400" : p.outcome === "LOST" ? "text-red-400" : "text-slate-400"}>
                  {p.outcome}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function ReviewArchivePanel() {
  const reviews = [
    { date: "2026-06-25", ticker: "SPY", decision: "PURSUE", conf: "72%", result: "WON", return: "+2.3%" },
    { date: "2026-06-25", ticker: "AAPL", decision: "WATCH", conf: "58%", result: "—", return: "—" },
    { date: "2026-06-24", ticker: "TSLA", decision: "REJECT", conf: "42%", result: "LOST", return: "-1.5%" },
  ];

  return (
    <Panel>
      <SectionTitle eyebrow="Archive" title="Review archive & history" />
      <div className="mt-4 space-y-2">
        <input
          type="text"
          placeholder="Search reviews..."
          className="w-full rounded bg-slate-900 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
        />
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {reviews.map((r, idx) => (
            <div key={idx} className="flex items-center justify-between rounded bg-slate-900 p-2 text-xs">
              <div>
                <span className="font-mono font-semibold">{r.ticker}</span>
                <div className="text-slate-400">{r.date}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge>{r.decision}</Badge>
                {r.result !== "—" && (
                  <span className={r.result === "WON" ? "text-green-400" : "text-red-400"}>
                    {r.return}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
