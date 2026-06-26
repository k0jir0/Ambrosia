"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CircleDashed } from "lucide-react";
import { Panel, SectionTitle } from "@/components/ui";
import { createReviewRecord, useReviewArchive } from "@/lib/review-store";

type Step = 1 | 2 | 3;

const STEPS = [
  { id: 1, label: "Instrument" },
  { id: 2, label: "Thesis" },
  { id: 3, label: "Sources" }
] as const;

export default function NewReviewPage() {
  const router = useRouter();
  const { reviews } = useReviewArchive();
  const [step, setStep] = useState<Step>(1);
  const [ticker, setTicker] = useState("AAPL");
  const [assetClass, setAssetClass] = useState("Equities");
  const [timeHorizon, setTimeHorizon] = useState("2-6 weeks");
  const [expression, setExpression] = useState("Long via equity");
  const [thesis, setThesis] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [sourceDraft, setSourceDraft] = useState("");
  const [creating, setCreating] = useState(false);
  const [createMessage, setCreateMessage] = useState<string | null>(null);

  const canContinueStep1 = ticker.trim() && assetClass.trim() && timeHorizon.trim() && expression.trim();
  const canCreateReview = canContinueStep1 && thesis.trim().length > 0;
  const claimCount = useMemo(() => thesis.split(/[.!?]/).filter((item) => item.trim().length > 12).length, [thesis]);

  function addSource() {
    const value = sourceDraft.trim();
    if (!value) return;
    setSources((current) => [...current, value]);
    setSourceDraft("");
  }

  async function startAnalysis() {
    if (!canCreateReview || creating) return;
    setCreating(true);
    setCreateMessage("Creating review packet...");
    const { review, source } = await createReviewRecord(
      {
        thesis,
        ticker: ticker.toUpperCase(),
        assetClass,
        timeHorizon,
        intendedExpression: expression,
        sourcePointer: sources.join("; ")
      },
      reviews.length
    );
    setCreateMessage(source === "api" ? "Review created through the API. Opening decision workbench..." : "API unavailable, so Ambrosia saved a local durable review. Opening decision workbench...");
    router.push(`/review/${encodeURIComponent(review.id)}`);
  }

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <SectionTitle eyebrow="New Review" title="Thesis intake workflow" />
        <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">
          Creating a review adds it to the Ambrosia review archive, increments dashboard totals, and makes the packet re-openable from History and Recent Reviews.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          {STEPS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`focus-ring rounded-full border px-3 py-1 ${step === item.id ? "border-teal bg-teal/10 text-teal" : "border-line text-ink/70"}`}
              onClick={() => setStep(item.id as Step)}
            >
              Step {item.id}: {item.label}
            </button>
          ))}
        </div>
      </Panel>

      {step === 1 ? (
        <Panel className="p-5">
          <h2 className="text-lg font-semibold">What are you reviewing?</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <LabeledInput label="Ticker / instrument" value={ticker} onChange={setTicker} />
            <LabeledInput label="Asset class" value={assetClass} onChange={setAssetClass} />
            <LabeledInput label="Time horizon" value={timeHorizon} onChange={setTimeHorizon} />
            <LabeledInput label="Intended expression" value={expression} onChange={setExpression} />
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-ink/65">
            <p>Type any ticker. Market intelligence will load after continue.</p>
            <button
              type="button"
              className="focus-ring inline-flex items-center gap-1 rounded-md bg-teal px-3 py-2 font-semibold text-fog disabled:opacity-50"
              disabled={!canContinueStep1}
              onClick={() => setStep(2)}
            >
              Continue <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </Panel>
      ) : null}

      {step === 2 ? (
        <Panel className="p-5">
          <h2 className="text-lg font-semibold">Write your thesis</h2>
          <p className="mt-1 text-sm text-ink/70">The system will challenge your claims. Be specific.</p>
          <textarea
            value={thesis}
            onChange={(event) => setThesis(event.target.value)}
            className="focus-ring mt-4 h-52 w-full rounded-md border border-line bg-fog/80 p-3"
            placeholder="State why this instrument is actionable."
          />
          <div className="mt-3 flex items-center justify-between text-sm text-ink/65">
            <p>
              Character count: {thesis.length} | Claim count: {claimCount}
            </p>
            <button
              type="button"
              className="focus-ring inline-flex items-center gap-1 rounded-md bg-teal px-3 py-2 font-semibold text-fog"
              disabled={!thesis.trim()}
              onClick={() => setStep(3)}
            >
              Continue <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </Panel>
      ) : null}

      {step === 3 ? (
        <Panel className="p-5">
          <h2 className="text-lg font-semibold">Add source pointers (optional)</h2>
          <div className="mt-4 flex gap-2">
            <input
              value={sourceDraft}
              onChange={(event) => setSourceDraft(event.target.value)}
              placeholder="URL, note, or document pointer"
              className="focus-ring flex-1 rounded-md border border-line bg-fog/80 px-3 py-2"
            />
            <button type="button" onClick={addSource} className="focus-ring rounded-md border border-line px-3 py-2">
              Add
            </button>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-ink/75">
            {sources.map((source) => (
              <li key={source} className="rounded-md border border-line bg-fog/70 px-3 py-2">
                {source}
              </li>
            ))}
            {sources.length === 0 ? (
              <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-2 text-ink/55">No sources added yet.</li>
            ) : null}
          </ul>
          <div className="mt-4 flex items-center justify-between">
            <button type="button" className="focus-ring rounded-md border border-line px-3 py-2 text-sm disabled:opacity-50" disabled={!canCreateReview || creating} onClick={startAnalysis}>
              Skip
            </button>
            <button type="button" className="focus-ring inline-flex items-center gap-1 rounded-md bg-teal px-3 py-2 font-semibold text-fog disabled:opacity-50" disabled={!canCreateReview || creating} onClick={startAnalysis}>
              <CircleDashed className="h-4 w-4" /> {creating ? "Creating review..." : "Create review"}
            </button>
          </div>
          {createMessage ? <p className="mt-3 text-sm text-ink/65">{createMessage}</p> : null}
        </Panel>
      ) : null}
    </div>
  );
}

function LabeledInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-ink/75">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} className="focus-ring w-full rounded-md border border-line bg-fog/80 px-3 py-2" />
    </label>
  );
}
