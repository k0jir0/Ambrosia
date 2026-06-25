"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel, SectionTitle } from "./ui";

const CONF_BANDS = [
  { band: "50-60", winRate: 58, target: 60 },
  { band: "60-70", winRate: 65, target: 70 },
  { band: "70-80", winRate: 73, target: 75 },
  { band: "80-90", winRate: 81, target: 85 },
  { band: "90-100", winRate: 88, target: 90 }
];

const EQUITY = [
  { week: "W1", score: 68 },
  { week: "W2", score: 69 },
  { week: "W3", score: 70 },
  { week: "W4", score: 71 },
  { week: "W5", score: 73 }
];

const COHORT = [
  { name: "ETFs", value: 78 },
  { name: "Stocks", value: 65 },
  { name: "Rates", value: 71 }
];

export function CalibrationPage() {
  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionTitle eyebrow="Calibration" title="Performance scorecard" />
          <button type="button" className="focus-ring rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog">
            Record Outcome
          </button>
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <MetricCard
          title="Confidence Calibration"
          value="73%"
          target="75%"
          copy="When you said 70% confident, you were right 73% of the time."
          tone="warn"
        />
        <MetricCard
          title="Win Rate"
          value="72%"
          target="70%"
          copy="72 of your last 100 reviewed trades were profitable."
          tone="good"
        />
      </section>

      <Panel className="p-5">
        <SectionTitle eyebrow="Performance by Confidence Band" title="Calibration diagnostics" />
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={CONF_BANDS}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
              <XAxis dataKey="band" stroke="#9db2bf" />
              <YAxis stroke="#9db2bf" />
              <Tooltip />
              <Bar dataKey="winRate" fill="#38c7b6" />
              <Line type="monotone" dataKey="target" stroke="#f2b84b" strokeWidth={2} dot={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="p-5">
          <SectionTitle eyebrow="Progress" title="Weekly calibration trend" />
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={EQUITY}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2b3f4c" />
                <XAxis dataKey="week" stroke="#9db2bf" />
                <YAxis stroke="#9db2bf" domain={[65, 80]} />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="#38c7b6" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel className="p-5">
          <SectionTitle eyebrow="Cohorts" title="Performance by asset class" />
          <div className="mt-4 space-y-3">
            {COHORT.map((entry) => (
              <div key={entry.name}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>{entry.name}</span>
                  <span className="font-semibold">{entry.value}%</span>
                </div>
                <div className="h-2 rounded bg-line">
                  <div className="h-2 rounded bg-teal" style={{ width: `${entry.value}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-ink/70">Weakest area currently: Stocks. Prioritize thesis quality and follow-up discipline in this cohort.</p>
        </Panel>
      </section>
    </div>
  );
}

function MetricCard({
  title,
  value,
  target,
  copy,
  tone
}: {
  title: string;
  value: string;
  target: string;
  copy: string;
  tone: "good" | "warn";
}) {
  return (
    <Panel className="p-5">
      <SectionTitle eyebrow="Scorecard" title={title} />
      <p className={`mt-3 text-2xl font-semibold ${tone === "good" ? "text-teal" : "text-amber"}`}>{value}</p>
      <p className="mt-1 text-sm text-ink/70">Target: {target}</p>
      <p className="mt-3 text-sm text-ink/75">{copy}</p>
    </Panel>
  );
}
