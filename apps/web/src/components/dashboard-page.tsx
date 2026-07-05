"use client";

import Link from "next/link";
import { ArrowRight, BellRing, FileSearch, TrendingUp } from "lucide-react";
import { useReviewArchive } from "@/lib/review-store";
import type { TradeReview } from "@/lib/types";
import { Badge, Panel, SectionTitle } from "./ui";

function averageConfidence(reviews: TradeReview[]) {
  if (reviews.length === 0) return 0;
  return Math.round(reviews.reduce((sum, review) => sum + review.confidence, 0) / reviews.length);
}

export function DashboardPage() {
  const { reviews, source, loading } = useReviewArchive();
  const reviewsAwaitingDecision = reviews.filter((review) => review.decisionState === null).length;
  const dueOutcomes = reviews.filter((review) => review.decisionState !== null).length;
  const recent = reviews.slice(0, 4);

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
        <PulseCard label="Reviews" value={String(reviews.length)} note={loading ? "Syncing archive" : `Archive source: ${source}`} />
        <PulseCard label="Pending Decisions" value={String(reviewsAwaitingDecision)} note="Need your action" />
        <PulseCard label="Average Confidence" value={`${averageConfidence(reviews)}%`} note="Across recent reviews" />
        <PulseCard label="Outcome Queue" value={String(dueOutcomes)} note="Record feedback" />
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        {PROOF_CARDS.map((card) => (
          <ProofCard key={card.title} card={card} />
        ))}
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

type ProofCardModel = {
  title: string;
  claim: string;
  action: string;
  href: string;
  caveat?: string;
};

const PROOF_CARDS: ProofCardModel[] = [
  {
    title: "Agentic AI for Investments",
    claim: "Typed thesis intake becomes claims, sources, validation, critique, and audit under human decision control.",
    action: "Create Review",
    href: "/review/new"
  },
  {
    title: "Investment Trading Decisions",
    claim: "One packet carries market context, backtest, risk, confidence, outcome memory, and reportable state.",
    action: "Run Workflow",
    href: "/review/new"
  },
  {
    title: "Swarm Intelligence",
    claim: "Specialist roles are preserved and coordinated into PM synthesis rather than flattened into one answer.",
    action: "Run Agent Swarm",
    href: "/review/atr-003",
    caveat: "Known limitation: formal pairwise disagreement score is pending."
  },
  {
    title: "Agentic Swarm",
    claim: "Provider-routed specialist actions mutate packet state, emit audit, and surface operator proof.",
    action: "Open Advanced",
    href: "/advanced"
  }
];

function ProofCard({ card }: { card: ProofCardModel }) {
  return (
    <Panel className="p-4">
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ink">{card.title}</p>
            <p className="mt-2 text-sm leading-6 text-ink/70">{card.claim}</p>
          </div>
          <FileSearch className="h-4 w-4 shrink-0 text-teal" />
        </div>
        {card.caveat ? (
          <div className="mt-3">
            <Badge tone="warn">{card.caveat}</Badge>
          </div>
        ) : null}
        <Link href={card.href} className="focus-ring mt-4 inline-flex w-fit items-center gap-1 rounded-md border border-line px-3 py-2 text-sm font-semibold text-teal hover:border-teal/50">
          {card.action} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </Panel>
  );
}
