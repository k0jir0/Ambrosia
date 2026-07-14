"use client";

import Link from "next/link";
import { ArrowRight, ClipboardPlus, FileSearch, ShieldAlert } from "lucide-react";
import { useReviewArchive } from "@/lib/review-store";
import type { TradeReview } from "@/lib/types";
import { Badge, Panel, SectionTitle } from "@/components/ui";

export default function ReviewPage() {
  const { reviews, source, loading } = useReviewArchive();
  const pending = reviews.filter((review) => review.decisionState === null);
  const decided = reviews.length - pending.length;
  const featured = pending[0] ?? reviews[0] ?? null;

  return (
    <div className="space-y-6">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-ink/70">Adversarial Review</p>
            <h1 className="text-2xl font-semibold">Review queue</h1>
          </div>
          <Link href="/review/new" className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-4 py-2 text-sm font-semibold text-fog">
            <ClipboardPlus className="h-4 w-4" />
            New Review
          </Link>
        </div>
      </Panel>

      <section className="grid gap-4 md:grid-cols-3">
        <Metric label="Open Reviews" value={String(reviews.length)} note={loading ? "Syncing archive" : `Source: ${source}`} />
        <Metric label="Pending Decisions" value={String(pending.length)} note="Human decision required" tone={pending.length > 0 ? "warn" : "good"} />
        <Metric label="Closed Decisions" value={String(decided)} note="Ready for outcome tracking" />
      </section>

      {featured ? <FeaturedReview review={featured} /> : <EmptyState />}

      <Panel className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionTitle eyebrow="Archive" title="Recent adversarial reviews" />
          <Link href="/history" className="focus-ring text-sm font-medium text-teal">
            History
          </Link>
        </div>
        <ul className="mt-4 space-y-2">
          {reviews.slice(0, 8).map((review) => (
            <ReviewRow key={review.id} review={review} />
          ))}
          {!loading && reviews.length === 0 ? (
            <li className="rounded-md border border-line bg-fog/70 p-3 text-sm text-ink/70">No reviews are available yet.</li>
          ) : null}
        </ul>
      </Panel>
    </div>
  );
}

function FeaturedReview({ review }: { review: TradeReview }) {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ?? "decision pending"}</Badge>
            <Badge tone="info">{review.ticker}</Badge>
            <span className="text-xs text-ink/60">{review.workflowVersion}</span>
          </div>
          <h2 className="mt-3 text-xl font-semibold">{review.title}</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">{review.thesis}</p>
        </div>
        <Link href={`/review/${encodeURIComponent(review.id)}`} className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 text-sm font-semibold text-teal hover:border-teal/50">
          <FileSearch className="h-4 w-4" />
          Open Workbench
        </Link>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Evidence label="Strongest critique" value={review.strongestCritique} />
        <Evidence label="Disconfirming test" value={review.disconfirmingTest} />
        <Evidence label="Validation" value={review.validation.status === "specified" ? review.validation.protocol : review.validation.refusalReason ?? "Validation refused"} />
      </div>
    </Panel>
  );
}

function ReviewRow({ review }: { review: TradeReview }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-fog/70 p-3 text-sm">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="info">{review.ticker}</Badge>
          <span className="font-medium text-ink">{review.title}</span>
        </div>
        <p className="mt-1 line-clamp-1 text-xs text-ink/60">{review.strongestCritique}</p>
      </div>
      <div className="flex items-center gap-3">
        <Badge tone={review.decisionState ? "good" : "warn"}>{review.decisionState ?? "pending"}</Badge>
        <Link href={`/review/${encodeURIComponent(review.id)}`} className="focus-ring inline-flex items-center gap-1 text-teal">
          Open <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </li>
  );
}

function Metric({ label, value, note, tone = "info" }: { label: string; value: string; note: string; tone?: "info" | "warn" | "good" }) {
  return (
    <Panel className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-ink/70">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
          <p className="mt-2 text-xs text-ink/60">{note}</p>
        </div>
        <Badge tone={tone}>{tone}</Badge>
      </div>
    </Panel>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/50">{label}</p>
      <p className="mt-2 text-sm leading-6 text-ink/70">{value}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-1 h-5 w-5 text-amber" />
          <div>
            <h2 className="text-lg font-semibold">No adversarial reviews yet</h2>
            <p className="mt-1 text-sm text-ink/70">Create the first review to generate critique, validation, tradeability checks, and a decision workbench.</p>
          </div>
        </div>
        <Link href="/review/new" className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-4 py-2 text-sm font-semibold text-fog">
          <ClipboardPlus className="h-4 w-4" />
          New Review
        </Link>
      </div>
    </Panel>
  );
}
