"use client";

import Link from "next/link";
import { ArrowRight, Beaker, FileInput, LockKeyhole } from "lucide-react";
import { useEffect } from "react";

import { recordProductEvent } from "@/lib/api";

export default function OnboardingPage() {
  useEffect(() => {
    void recordProductEvent("onboarding_viewed", "onboarding");
  }, []);

  return (
    <div className="mx-auto max-w-5xl py-6 sm:py-12">
      <div className="max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-teal/20 bg-teal/5 px-3 py-1.5 text-xs font-semibold text-teal">
          <LockKeyhole className="h-3.5 w-3.5" /> Private workspace ready
        </div>
        <h1 className="mt-6 text-3xl font-semibold tracking-[-0.035em] sm:text-5xl">Make Ambrosia earn your trust on one decision.</h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-ink/62">Choose a dated guided case to see the complete workflow, or bring a live thesis. Either path ends with a human-owned decision and a revisit plan.</p>
      </div>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        <Link href="/review/new?guided=ambrosia-first-decision" onClick={() => void recordProductEvent("guided_started", "onboarding")} className="focus-ring group rounded-2xl border border-teal/30 bg-gradient-to-br from-teal/10 to-paper p-6 transition hover:border-teal/60 sm:p-8">
          <Beaker className="h-6 w-6 text-teal" />
          <p className="mt-8 text-xs font-semibold uppercase tracking-[0.16em] text-teal">Recommended · about 5 minutes</p>
          <h2 className="mt-3 text-2xl font-semibold">Run the guided decision</h2>
          <p className="mt-3 text-sm leading-6 text-ink/60">Challenge a crowded AI-infrastructure thesis with dated demo evidence, a required bear case, deterministic controls, and an explicit next action.</p>
          <span className="mt-8 inline-flex items-center gap-2 text-sm font-bold text-teal">Start guided case <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
        </Link>

        <Link href="/review/new" onClick={() => void recordProductEvent("own_thesis_started", "onboarding")} className="focus-ring group rounded-2xl border border-line bg-paper/75 p-6 transition hover:border-ink/25 sm:p-8">
          <FileInput className="h-6 w-6 text-ink/65" />
          <p className="mt-8 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">Use your own work</p>
          <h2 className="mt-3 text-2xl font-semibold">Enter a live thesis</h2>
          <p className="mt-3 text-sm leading-6 text-ink/60">Define the intended expression, horizon, source pointer, and conditions that would prove you wrong. No model output is treated as a decision.</p>
          <span className="mt-8 inline-flex items-center gap-2 text-sm font-bold text-ink/75">Open intake <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
        </Link>
      </div>

      <section className="mt-10 rounded-2xl border border-line bg-paper/55 p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal">What you will leave with</p>
        <ol className="mt-6 grid gap-5 sm:grid-cols-3">
          {[
            ["01", "Traceable evidence", "Source, as-of time, permission, and fallback state stay visible."],
            ["02", "A challenged thesis", "Contradictions and disconfirming tests cannot be skipped."],
            ["03", "A durable decision", "Your rationale, controls, revisit date, and outcome become memory."],
          ].map(([number, title, copy]) => (
            <li key={number}>
              <span className="text-xs font-semibold text-teal">{number}</span>
              <h3 className="mt-2 text-sm font-semibold">{title}</h3>
              <p className="mt-2 text-xs leading-5 text-ink/50">{copy}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
