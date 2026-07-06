"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Database, Download, LoaderCircle, Search } from "lucide-react";
import { PacketLibraryPanel, ReviewArchivePanel } from "@/components/advanced-panels";
import { seedIndex97Reviews } from "@/lib/api";
import { useReviewArchive } from "@/lib/review-store";
import { Badge, Panel, SectionTitle } from "./ui";

const OUTCOME_LOOKUP = ["won", "lost", "pending"] as const;

export function HistoryPage() {
  const { reviews, source, loading } = useReviewArchive();
  const [query, setQuery] = useState("");
  const [decisionFilter, setDecisionFilter] = useState("all");
  const [tickerFilter, setTickerFilter] = useState("all");
  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [minConfidence, setMinConfidence] = useState(40);
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);

  const tickers = useMemo(() => ["all", ...Array.from(new Set(reviews.map((review) => review.ticker)))], [reviews]);

  const rows = useMemo(() => {
    return reviews
      .map((review, index) => {
        const outcome = OUTCOME_LOOKUP[index % OUTCOME_LOOKUP.length];
        const ret = outcome === "won" ? `+${(1.2 + index * 0.4).toFixed(1)}%` : outcome === "lost" ? `-${(0.8 + index * 0.3).toFixed(1)}%` : "-";
        return { ...review, outcome, ret };
      })
      .filter((row) => {
        const text = `${row.ticker} ${row.title} ${row.thesis}`.toLowerCase();
        const q = query.trim().toLowerCase();
        if (q && !text.includes(q)) return false;
        if (decisionFilter !== "all" && (row.decisionState ?? "pending") !== decisionFilter) return false;
        if (tickerFilter !== "all" && row.ticker !== tickerFilter) return false;
        if (outcomeFilter !== "all" && row.outcome !== outcomeFilter) return false;
        if (row.confidence < minConfidence) return false;
        return true;
      });
  }, [decisionFilter, minConfidence, outcomeFilter, query, reviews, tickerFilter]);

  const winRate = rows.length === 0 ? 0 : Math.round((rows.filter((row) => row.outcome === "won").length / rows.length) * 100);

  async function seedDemoArchive() {
    setSeeding(true);
    setSeedMessage(null);
    try {
      const response = await seedIndex97Reviews();
      setSeedMessage(`Seeded ${response.reviewsSeeded ?? 0} demo reviews into the archive.`);
      window.dispatchEvent(new CustomEvent("ambrosia:reviews-updated"));
    } catch (error) {
      setSeedMessage(error instanceof Error ? error.message : "Unable to seed demo reviews.");
    } finally {
      setSeeding(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionTitle eyebrow="Decision History" title={`Archive (${reviews.length} total)`} />
          <button
            type="button"
            onClick={() => void seedDemoArchive()}
            disabled={seeding}
            className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-3 py-2 text-sm font-semibold text-fog disabled:opacity-60"
          >
            {seeding ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            Seed demo archive
          </button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label className="xl:col-span-2">
            <span className="mb-1 block text-xs text-ink/60">Search</span>
            <div className="flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2">
              <Search className="h-4 w-4 text-ink/60" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} className="focus-ring w-full bg-transparent text-sm" placeholder="Search reviews..." />
            </div>
          </label>

          <SelectFilter label="Ticker" value={tickerFilter} onChange={setTickerFilter} options={tickers} />
          <SelectFilter label="Decision" value={decisionFilter} onChange={setDecisionFilter} options={["all", "pursue", "watch", "reject", "needs_more_data", "pending"]} />
          <SelectFilter label="Outcome" value={outcomeFilter} onChange={setOutcomeFilter} options={["all", "won", "lost", "pending"]} />

          <label>
            <span className="mb-1 block text-xs text-ink/60">Min confidence: {minConfidence}%</span>
            <input type="range" min={40} max={100} value={minConfidence} onChange={(event) => setMinConfidence(Number(event.target.value))} className="focus-ring w-full" />
          </label>
        </div>
      </Panel>

      <Panel className="p-4 text-sm text-ink/70">
        Showing {rows.length} of {reviews.length} | Filtered win rate: <span className="font-semibold text-teal">{winRate}%</span> | Source: {loading ? "syncing" : source}
        {seedMessage ? <span className="ml-2 text-teal">{seedMessage}</span> : null}
      </Panel>

      <Panel className="overflow-x-auto p-2">
        <table className="w-full min-w-[860px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left text-ink/65">
              <th className="border-b border-line px-3 py-2">Date</th>
              <th className="border-b border-line px-3 py-2">Ticker</th>
              <th className="border-b border-line px-3 py-2">Decision</th>
              <th className="border-b border-line px-3 py-2">Confidence</th>
              <th className="border-b border-line px-3 py-2">Outcome</th>
              <th className="border-b border-line px-3 py-2">Return</th>
              <th className="border-b border-line px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-white/5">
                <td className="border-b border-line/70 px-3 py-3">{new Date(row.createdAt).toLocaleDateString()}</td>
                <td className="border-b border-line/70 px-3 py-3">
                  <Badge tone="info">{row.ticker}</Badge>
                </td>
                <td className="border-b border-line/70 px-3 py-3 uppercase">{row.decisionState ?? "pending"}</td>
                <td className="border-b border-line/70 px-3 py-3">{row.confidence}%</td>
                <td className="border-b border-line/70 px-3 py-3">
                  <Badge tone={row.outcome === "won" ? "good" : row.outcome === "lost" ? "bad" : "neutral"}>{row.outcome.toUpperCase()}</Badge>
                </td>
                <td className="border-b border-line/70 px-3 py-3">{row.ret}</td>
                <td className="border-b border-line/70 px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Link href={`/review/${row.id}`} className="focus-ring rounded-md border border-line px-2 py-1 text-xs text-teal">
                      Open
                    </Link>
                    {row.outcome === "pending" ? (
                      <button type="button" className="focus-ring rounded-md border border-amber/40 px-2 py-1 text-xs text-amber">
                        Record
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Decision Memory" title="Packet and review lookup" />
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/70">
          Reusable packet search and compact review history sit alongside the full decision archive.
        </p>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <PacketLibraryPanel />
        <ReviewArchivePanel />
      </section>

      <Panel className="p-4">
        <button type="button" className="focus-ring inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm">
          <Download className="h-4 w-4" /> Export CSV (filtered)
        </button>
      </Panel>
    </div>
  );
}

function SelectFilter({
  label,
  value,
  onChange,
  options
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label>
      <span className="mb-1 block text-xs text-ink/60">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="focus-ring w-full rounded-md border border-line bg-fog/70 px-2 py-2 text-sm">
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
