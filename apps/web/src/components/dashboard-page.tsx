import Link from "next/link";
import { ArrowRight, BellRing, TrendingUp } from "lucide-react";
import { sampleReviews } from "@/lib/sample-data";
import { Badge, Panel, SectionTitle } from "./ui";

function averageConfidence() {
  if (sampleReviews.length === 0) return 0;
  return Math.round(sampleReviews.reduce((sum, review) => sum + review.confidence, 0) / sampleReviews.length);
}

export function DashboardPage() {
  const reviewsAwaitingDecision = sampleReviews.filter((review) => review.decisionState === null).length;
  const dueOutcomes = sampleReviews.filter((review) => review.decisionState !== null).length;
  const recent = sampleReviews.slice(0, 4);

  return (
    <div className="space-y-6">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-ink/70">Daily Briefing</p>
            <h1 className="text-2xl font-semibold">Good morning. You have {reviewsAwaitingDecision} reviews awaiting decision.</h1>
          </div>
          <Link href="/review/new" className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-4 py-2 text-sm font-semibold text-fog">
            New Review <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </Panel>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <PulseCard label="Reviews" value={String(sampleReviews.length)} note="In active archive" />
        <PulseCard label="Pending Decisions" value={String(reviewsAwaitingDecision)} note="Need your action" />
        <PulseCard label="Average Confidence" value={`${averageConfidence()}%`} note="Across recent reviews" />
        <PulseCard label="Outcome Queue" value={String(dueOutcomes)} note="Record feedback" />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel className="p-5 xl:col-span-2">
          <SectionTitle eyebrow="Needs Your Attention" title="Priority queue" />
          <ul className="mt-4 space-y-3">
            <li className="flex items-center justify-between rounded-md border border-line bg-fog/70 p-3 text-sm">
              <span>TLT curve steepener is awaiting decision</span>
              <Link href="/review/atr-003" className="focus-ring inline-flex items-center gap-1 text-teal">
                Continue <ArrowRight className="h-4 w-4" />
              </Link>
            </li>
            <li className="flex items-center justify-between rounded-md border border-line bg-fog/70 p-3 text-sm">
              <span>AAPL intelligence update available with fresh market bars</span>
              <Link href="/markets/AAPL" className="focus-ring inline-flex items-center gap-1 text-teal">
                Open <ArrowRight className="h-4 w-4" />
              </Link>
            </li>
            <li className="flex items-center justify-between rounded-md border border-line bg-fog/70 p-3 text-sm">
              <span>Two outcomes due for calibration update</span>
              <Link href="/calibration" className="focus-ring inline-flex items-center gap-1 text-teal">
                Record <ArrowRight className="h-4 w-4" />
              </Link>
            </li>
          </ul>
        </Panel>

        <Panel className="p-5">
          <SectionTitle eyebrow="Calibration Snapshot" title="Performance this week" />
          <div className="mt-4 space-y-3 text-sm">
            <div className="rounded-md border border-line bg-fog/70 p-3">
              <p className="text-ink/70">Decision accuracy</p>
              <p className="mt-1 text-xl font-semibold">72%</p>
            </div>
            <div className="rounded-md border border-line bg-fog/70 p-3">
              <p className="text-ink/70">Confidence calibration</p>
              <p className="mt-1 flex items-center gap-2 text-xl font-semibold text-amber">
                <TrendingUp className="h-4 w-4" /> 73%
              </p>
            </div>
            <Link href="/calibration" className="focus-ring inline-flex items-center gap-1 text-sm font-medium text-teal">
              See full calibration <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </Panel>
      </section>

      <Panel className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle eyebrow="Recent Reviews" title="Resume active packets" />
          <Link href="/history" className="focus-ring text-sm font-medium text-teal">
            View all
          </Link>
        </div>
        <ul className="space-y-2">
          {recent.map((review) => (
            <li key={review.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-fog/70 p-3 text-sm">
              <div className="flex items-center gap-2">
                <Badge tone="info">{review.ticker}</Badge>
                <span>{review.title}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-ink/70">{review.confidence}% confidence</span>
                <Link href={`/review/${review.id}`} className="focus-ring inline-flex items-center gap-1 text-teal">
                  Open <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel className="p-5">
        <div className="flex items-center gap-2 text-sm text-ink/70">
          <BellRing className="h-4 w-4 text-amber" />
          Live ticker intelligence is now available from the sidebar and from the Markets route.
        </div>
      </Panel>
    </div>
  );
}

function PulseCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Panel className="p-4">
      <p className="text-sm text-ink/70">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      <p className="mt-2 text-xs text-ink/60">{note}</p>
    </Panel>
  );
}
