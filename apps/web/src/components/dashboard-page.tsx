"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Beaker, CheckCircle2, CircleDashed, FileInput, ShieldCheck } from "lucide-react";

import { useReviewArchive } from "@/lib/review-store";
import { recordProductEvent } from "@/lib/api";
import { Badge, Panel } from "./ui";

export function DashboardPage() {
  const { reviews, source, loading } = useReviewArchive();
  const awaitingDecision = reviews.filter((review) => review.decisionState === null);
  const decided = reviews.filter((review) => review.decisionState !== null);
  const recent = reviews.slice(0, 5);

  useEffect(() => {
    void recordProductEvent("return_session", "decision_packets");
  }, []);
  const sourceLabel = loading ? "Synchronizing" : source === "api" ? "Tenant database" : "Local fallback · not durable";

  return <div className="mx-auto max-w-6xl space-y-5">
    <Panel className="overflow-hidden p-0"><div className="grid lg:grid-cols-[1.15fr_0.85fr]"><section className="p-6 sm:p-8"><div className="inline-flex items-center gap-2 rounded-full border border-teal/25 bg-teal/5 px-3 py-1.5 text-xs font-semibold text-teal"><ShieldCheck className="h-3.5 w-3.5" /> Human decision authority</div><h1 className="mt-6 max-w-2xl text-3xl font-semibold leading-tight tracking-[-0.035em] sm:text-5xl">Turn one thesis into a decision you can defend later.</h1><p className="mt-5 max-w-2xl text-sm leading-7 text-ink/62">Attach dated evidence, force the strongest disagreement, pass deterministic controls, record the human decision, and preserve what happened next.</p><div className="mt-7 flex flex-wrap gap-3"><Link href="/review/new?guided=ambrosia-first-decision" className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-4 py-3 text-sm font-bold text-[#071411]"><Beaker className="h-4 w-4" /> Run five-minute guided case</Link><Link href="/review/new" className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-4 py-3 text-sm font-semibold"><FileInput className="h-4 w-4" /> Use my thesis</Link></div></section><aside className="border-t border-line bg-fog/65 p-6 lg:border-l lg:border-t-0 sm:p-8"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal">Your next action</p>{awaitingDecision[0] ? <><h2 className="mt-4 text-xl font-semibold">Finish {awaitingDecision[0].ticker || "the open"} packet</h2><p className="mt-3 text-sm leading-6 text-ink/58">A thesis is waiting for its explicit human decision and rationale.</p><Link href={`/review/${awaitingDecision[0].id}`} className="focus-ring mt-6 inline-flex items-center gap-2 text-sm font-bold text-teal">Continue packet <ArrowRight className="h-4 w-4" /></Link></> : <><h2 className="mt-4 text-xl font-semibold">Challenge your first decision</h2><p className="mt-3 text-sm leading-6 text-ink/58">Start with the dated sample or enter a thesis from current work. No live order will be placed.</p><Link href="/onboarding" className="focus-ring mt-6 inline-flex items-center gap-2 text-sm font-bold text-teal">Choose a path <ArrowRight className="h-4 w-4" /></Link></>}</aside></div></Panel>

    <section className="grid gap-4 sm:grid-cols-3"><Metric label="Decision packets" value={String(reviews.length)} note={sourceLabel} /><Metric label="Needs human decision" value={String(awaitingDecision.length)} note="No model can approve" /><Metric label="Outcome memory" value={String(decided.length)} note="Decided packets ready for follow-up" /></section>

    <Panel className="p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal">Governed workflow</p><h2 className="mt-2 text-xl font-semibold">One visible loop, no black-box approval</h2></div><Badge tone={source === "api" ? "good" : "warn"}>{sourceLabel}</Badge></div><ol className="mt-6 grid gap-4 md:grid-cols-5">{[["01", "Intake", "State action, horizon, and falsifier."], ["02", "Evidence", "Expose source and as-of time."], ["03", "Challenge", "Require critique and disconfirmation."], ["04", "Controls", "Replay deterministic risk gates."], ["05", "Decision", "Human rationale becomes memory."]].map(([number, title, copy], index) => <li key={number} className="rounded-lg border border-line bg-fog/60 p-4">{index < Math.min(5, reviews.length ? 4 : 1) ? <CheckCircle2 className="h-4 w-4 text-teal" /> : <CircleDashed className="h-4 w-4 text-ink/35" />}<p className="mt-5 text-[10px] font-bold tracking-[0.16em] text-teal">{number}</p><h3 className="mt-2 text-sm font-semibold">{title}</h3><p className="mt-2 text-xs leading-5 text-ink/48">{copy}</p></li>)}</ol></Panel>

    <Panel className="p-6"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal">Recent packets</p><h2 className="mt-2 text-xl font-semibold">Resume accountable work</h2></div><Link href="/review" className="text-sm font-semibold text-teal">Open queue</Link></div>{recent.length ? <ul className="mt-5 divide-y divide-line">{recent.map((review) => <li key={review.id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div className="flex items-center gap-3"><Badge tone="info">{review.ticker || "Thesis"}</Badge><div><p className="text-sm font-semibold">{review.title}</p><p className="mt-1 text-xs text-ink/45">{review.decisionState ? `Human decision: ${review.decisionState}` : "Human decision required"}</p></div></div><Link href={`/review/${review.id}`} className="focus-ring inline-flex items-center gap-1 text-sm font-semibold text-teal">Open <ArrowRight className="h-4 w-4" /></Link></li>)}</ul> : <div className="mt-5 rounded-lg border border-dashed border-line p-8 text-center"><p className="text-sm font-semibold">No private packets yet</p><p className="mt-2 text-xs text-ink/48">The guided case creates a clearly labelled demonstration packet.</p></div>}</Panel>
  </div>;
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <Panel className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink/45">{label}</p><p className="mt-2 text-3xl font-semibold">{value}</p><p className="mt-2 text-xs text-ink/45">{note}</p></Panel>;
}
