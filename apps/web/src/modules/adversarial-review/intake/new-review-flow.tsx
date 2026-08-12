"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CircleDashed } from "lucide-react";
import { Panel, SectionTitle } from "@/components/ui";
import { linkSignalReview, recordProductEvent } from "@/lib/api";
import { createReviewRecord, setReviewAlphaLink, useReviewArchive } from "@/lib/review-store";

type Step = 1 | 2 | 3;

type NewReviewFlowProps = {
  initialParams?: Record<string, string | string[] | undefined>;
};

const STEPS = [
  { id: 1, label: "Instrument" },
  { id: 2, label: "Thesis" },
  { id: 3, label: "Sources" }
] as const;

export function NewReviewFlow({ initialParams }: NewReviewFlowProps) {
  const router = useRouter();
  const { reviews } = useReviewArchive();

  const intakeContext = useMemo(() => {
    const getParamValue = (key: string, fallback = "") => {
      const value = initialParams?.[key];
      if (Array.isArray(value)) return value[0] ?? fallback;
      return value ?? fallback;
    };

    const source = getParamValue("source");
    const guided = getParamValue("guided");
    if (guided === "ambrosia-first-decision") {
      return {
        ticker: "NVDA",
        assetClass: "Equity",
        timeHorizon: "6-12 months",
        expression: "Research decision only — no live order",
        thesis: "A crowded AI infrastructure position deserves a governed disconfirmation review before capital is committed.",
        sourcePointer: "Ambrosia guided sample v1 · source cutoff 2026-08-07 · demo data",
        summary: "dated Ambrosia guided decision (not live market data)",
        link: null,
      };
    }
    const baseContext = {
      ticker: getParamValue("ticker", "AAPL").toUpperCase(),
      assetClass: getParamValue("assetClass", "Equities"),
      timeHorizon: getParamValue("timeHorizon", "2-6 weeks"),
      expression: getParamValue("expression", "Long via equity"),
      thesis: getParamValue("thesis"),
      sourcePointer: getParamValue("sourcePointer"),
      summary: source === "scanner"
        ? "Market Scanner candidate"
        : source === "market-intelligence"
          ? "Market Intelligence research"
          : source
            ? `${source} prefill`
            : "",
      link: null
    };

    if (source !== "alpha") return baseContext.thesis || baseContext.sourcePointer || source ? baseContext : null;

    const alphaTypeRaw = getParamValue("alphaType");
    if (alphaTypeRaw !== "hypothesis" && alphaTypeRaw !== "signal") return baseContext;
    const alphaType: "hypothesis" | "signal" = alphaTypeRaw;

    const hypothesisId = getParamValue("hypothesisId");
    const signalId = getParamValue("signalId");
    const signalVersionRaw = Number(getParamValue("alphaSignalVersion", ""));
    const signalVersion = Number.isFinite(signalVersionRaw) && signalVersionRaw >= 1 ? Math.floor(signalVersionRaw) : undefined;
    const title = getParamValue("alphaTitle");
    const signalFamily = getParamValue("alphaSignalFamily");
    const formula = getParamValue("alphaFormula");

    return {
      ...baseContext,
      summary: `Alpha Lab ${alphaType}${title ? `: ${title}` : ""}`,
      link: {
        source: "alpha" as const,
        objectType: alphaType,
        hypothesisId: hypothesisId || undefined,
        signalId: signalId || undefined,
        signalVersion,
        title: title || undefined,
        signalFamily: signalFamily || undefined,
        formula: formula || undefined,
        ticker: baseContext.ticker,
        createdAt: new Date().toISOString()
      }
    };
  }, [initialParams]);

  const [step, setStep] = useState<Step>(1);
  const [ticker, setTicker] = useState(intakeContext?.ticker ?? "AAPL");
  const [assetClass, setAssetClass] = useState(intakeContext?.assetClass ?? "Equities");
  const [timeHorizon, setTimeHorizon] = useState(intakeContext?.timeHorizon ?? "2-6 weeks");
  const [expression, setExpression] = useState(intakeContext?.expression ?? "Long via equity");
  const [thesis, setThesis] = useState(intakeContext?.thesis ?? "");
  const [sources, setSources] = useState<string[]>(intakeContext?.sourcePointer ? [intakeContext.sourcePointer] : []);
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
        ticker: ticker.trim().toUpperCase(),
        subjectType: "listed_instrument",
        assetClass,
        timeHorizon,
        intendedExpression: expression,
        sourcePointer: sources.join("; ")
      },
      reviews.length
    );

    if (intakeContext?.link) {
      setReviewAlphaLink(review.id, intakeContext.link);
      if (intakeContext.link.signalId) {
        void linkSignalReview(intakeContext.link.signalId, {
          reviewId: review.id,
          hypothesisId: intakeContext.link.hypothesisId,
          signalVersion: intakeContext.link.signalVersion,
        }).catch(() => {
          // Keep intake resilient when the API path is unavailable; local link remains intact.
        });
      }
    }

    setCreateMessage(source === "api" ? "Review created through the API. Opening decision workbench..." : "API unavailable, so Ambrosia saved a local durable review. Opening decision workbench...");
    if (source === "api") {
      void recordProductEvent("packet_saved", "intake", {
        objectReference: review.id,
        properties: { mode: intakeContext?.summary ? "prefilled" : "own_thesis" },
      });
    }
    router.push(`/review/${encodeURIComponent(review.id)}`);
  }

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <SectionTitle eyebrow="New Review" title="Thesis intake workflow" />
        <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">
          Creating a review adds it to the Ambrosia review archive, increments dashboard totals, and makes the packet re-openable from History and Recent Reviews.
        </p>
        {intakeContext?.summary ? <p className="mt-2 rounded-md border border-line bg-fog/70 px-3 py-2 text-xs text-ink/75">Prefilled from {intakeContext.summary}</p> : null}
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
