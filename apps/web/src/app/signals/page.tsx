"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Database, GitBranch, LoaderCircle, RefreshCw, ShieldCheck } from "lucide-react";
import { Panel, SectionTitle, Badge } from "@/components/ui";
import { RouteLoading, RouteNotice, RouteStatusBadge, type RouteStatus } from "@/components/route-state";
import { fetchControlPlane, mapStatus, numberOrFallback, textOrFallback } from "@/lib/index84-control-plane";
import { seedIndex97Reviews, seedIndex97Signals } from "@/lib/api";

type BadgeTone = "neutral" | "good" | "warn" | "bad" | "info";

type SignalDetails = {
  validationRuns: Array<Record<string, unknown>>;
  decisionLinks: Array<Record<string, unknown>>;
  policyEvents: Array<Record<string, unknown>>;
  versions: Array<Record<string, unknown>>;
};

type DetailTab = "overview" | "formula" | "evidence" | "validation" | "trades" | "reviews" | "outcomes" | "risk" | "policy" | "versions";

const DETAIL_TABS: Array<{ key: DetailTab; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "formula", label: "Formula" },
  { key: "evidence", label: "Evidence" },
  { key: "validation", label: "Validation" },
  { key: "trades", label: "Trades" },
  { key: "reviews", label: "Reviews" },
  { key: "outcomes", label: "Outcomes" },
  { key: "risk", label: "Risk" },
  { key: "policy", label: "Policy Events" },
  { key: "versions", label: "Versions" },
];

const EMPTY_DETAILS: SignalDetails = {
  validationRuns: [],
  decisionLinks: [],
  policyEvents: [],
  versions: [],
};

export default function SignalsPage() {
  const [status, setStatus] = useState<RouteStatus>("loading");
  const [message, setMessage] = useState<string>("Loading signals...");
  const [signals, setSignals] = useState<Array<Record<string, unknown>>>([]);
  const [signalDetails, setSignalDetails] = useState<Record<string, SignalDetails>>({});
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [scorecard, setScorecard] = useState<Record<string, unknown> | null>(null);
  const [seeding, setSeeding] = useState(false);

  async function load() {
    setStatus("loading");
    const [response, metricsResponse, scorecardResponse] = await Promise.all([
      fetchControlPlane("/signals"),
      fetchControlPlane("/signals/program-metrics"),
      fetchControlPlane("/signals/quality-scorecard/weekly")
    ]);
    if (!response.ok) {
      const current = mapStatus(response.status, response.data);
      setStatus(current);
      setMessage(response.message || "Signals endpoint is unavailable.");
      setMetrics(metricsResponse.ok && isRecord(metricsResponse.data) ? metricsResponse.data : null);
      setScorecard(scorecardResponse.ok && isRecord(scorecardResponse.data) ? scorecardResponse.data : null);
      setSignalDetails({});
      setSelectedSignalId(null);
      return;
    }

    const items = Array.isArray(response.data) ? (response.data as Array<Record<string, unknown>>) : [];
    const details = await loadSignalDetails(items);
    const signalIds = items.map((item) => textOrFallback(item.signalId, "")).filter(Boolean);
    setSignals(items);
    setSignalDetails(details);
    setSelectedSignalId((current) => (current && signalIds.includes(current) ? current : signalIds[0] ?? null));
    setMetrics(metricsResponse.ok && isRecord(metricsResponse.data) ? metricsResponse.data : null);
    setScorecard(scorecardResponse.ok && isRecord(scorecardResponse.data) ? scorecardResponse.data : null);
    setStatus(items.length === 0 ? "empty" : "success");
    setMessage(items.length === 0 ? "No signals available yet." : "Signals loaded.");
  }

  async function seedSignals() {
    setSeeding(true);
    setStatus("loading");
    try {
      const response = await seedIndex97Signals();
      await seedIndex97Reviews();
      setMessage(`Seeded ${numberOrFallback(response.signalsSeeded, "0")} lifecycle signals.`);
      await load();
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Unable to seed Index97 signal inventory.");
    } finally {
      setSeeding(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const cockpitMetrics = buildCockpitMetrics(signals, signalDetails);
  const triageEntries = buildDecisionTriage(signals, signalDetails);
  const selectedSignal = signals.find((signal) => textOrFallback(signal.signalId, "") === selectedSignalId) ?? signals[0] ?? null;
  const selectedDetails = selectedSignal ? detailsForSignal(selectedSignal, signalDetails) : EMPTY_DETAILS;

  if (status === "loading") return <RouteLoading title="Signals" />;

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <SectionTitle eyebrow="Index84 Surface" title="Signals" />
            <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/75">
              Trace durable signals from scanner discovery and alpha hypothesis through validation, review, risk, execution, outcome, and history.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RouteStatusBadge status={status} />
            <button
              type="button"
              onClick={() => void seedSignals()}
              disabled={seeding}
              className="focus-ring inline-flex items-center gap-2 rounded-md bg-teal px-3 py-1 text-xs font-semibold text-fog disabled:opacity-60"
            >
              {seeding ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
              Seed lifecycle data
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="focus-ring inline-flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </div>
      </Panel>

      {status !== "success" ? <RouteNotice status={status} message={message} retry={() => void load()} /> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)]">
        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Program" title="Lifecycle coverage" />
            <Badge tone="neutral">{numberOrFallback(metrics?.totalSignals, "0")} signals</Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-4">
            <Metric label="Validated" value={numberOrFallback(metrics?.validatedSignals, "0")} detail={`${numberOrFallback(metrics?.validatedSignalsPct, "0")}%`} />
            <Metric label="Active" value={numberOrFallback(metrics?.promotedSignals, "0")} detail="candidates" />
            <Metric label="Linked" value={numberOrFallback(metrics?.linkedSignals, "0")} detail={`${numberOrFallback(metrics?.linkedSignalsPct, "0")}%`} />
            <Metric label="Outcomes" value={numberOrFallback(metrics?.recordedOutcomes, "0")} detail="closed" />
            <Metric label="Stack links" value={String(cockpitMetrics.stackLinked)} detail={`${cockpitMetrics.stackMissing} missing`} />
            <Metric label="Risk budget" value={String(cockpitMetrics.riskBudgeted)} detail={`${cockpitMetrics.missingRiskBudget} missing`} />
            <Metric label="Blocked" value={String(cockpitMetrics.blocked)} detail="needs action" />
            <Metric label="Validation" value={String(cockpitMetrics.validationPassed)} detail={`${cockpitMetrics.validationMissing} pending`} />
          </div>
        </Panel>

        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Weekly" title="Quality gates" />
            <Badge tone={allGatesPass(scorecard) ? "good" : "warn"}>{allGatesPass(scorecard) ? "pass" : "review"}</Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-ink/70">
            {qualityGateEntries(scorecard).map(([name, gate]) => (
              <div key={name} className="rounded-md border border-line bg-fog/70 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="capitalize">{name.replace(/([A-Z])/g, " $1")}</span>
                  <Badge tone={gateTone(gate.status)}>{textOrFallback(gate.status, "n/a")}</Badge>
                </div>
                <p className="mt-1 font-mono text-[11px] text-ink/55">
                  {numberOrFallback(gate.passed, "0")}/{numberOrFallback(gate.total, "0")}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Operating Queue" title="Decision triage" />
            <Badge tone={cockpitMetrics.blocked > 0 ? "warn" : "good"}>{cockpitMetrics.blocked > 0 ? "review" : "clear"}</Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-3">
            {triageEntries.map((entry) => (
              <div key={entry.key} className="rounded-md border border-line bg-fog/70 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-ink/70">{entry.label}</span>
                  <Badge tone={entry.tone}>{entry.count}</Badge>
                </div>
                <p className="mt-2 text-[11px] leading-4 text-ink/55">{entry.detail}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle eyebrow="Stack Contract" title="Signal relationship map" />
            <GitBranch className="h-4 w-4 text-teal" />
          </div>
          <div className="mt-4 grid gap-2 text-xs text-ink/70 sm:grid-cols-3">
            <RelationshipStep label="Scanner" detail="discovers candidates" />
            <RelationshipStep label="Alpha" detail="explains thesis" />
            <RelationshipStep label="Signal" detail="measures and versions" />
            <RelationshipStep label="Review" detail="decides action" />
            <RelationshipStep label="Risk" detail="sizes or blocks" />
            <RelationshipStep label="Outcome" detail="teaches memory" />
          </div>
        </Panel>
      </div>

      <Panel className="p-6">
        <div className="flex items-center justify-between gap-3">
          <SectionTitle eyebrow="Inventory" title="Signal cockpit" />
          <Badge tone="neutral">{signals.length} total</Badge>
        </div>

        <ul className="mt-4 space-y-3">
          {signals.map((signal) => {
            const signalId = textOrFallback(signal.signalId);
            const statusValue = textOrFallback(signal.status, "hypothesis");
            const details = detailsForSignal(signal, signalDetails);
            const family = signalFamily(signal);
            const origin = signalOrigin(signal);
            const validation = latestValidationStatus(signal, details);
            const risk = riskPosture(signal, details);
            const nextAction = signalNextAction(signal, details);
            const nextTone = nextActionTone(nextAction);
            const reviewIds = stringList(signal.linkedReviewIds);
            const hypothesisIds = stringList(signal.linkedHypothesisIds);
            const sourceTicker = textOrFallback(signal.sourceTicker, stringList(signal.universe)[0] || "");
            return (
              <li key={signalId} className="rounded-md border border-line bg-fog/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-sm font-semibold text-ink">{signalId}</p>
                    <p className="text-xs text-ink/65">{textOrFallback(signal.name)}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone="info">{family}</Badge>
                      <Badge tone="neutral">origin {origin}</Badge>
                      {textOrFallback(signal.demoSeed, "") ? <Badge tone="warn">Demo Lifecycle</Badge> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    <Badge tone={statusTone(statusValue)}>{statusValue}</Badge>
                    <Badge tone={nextTone}>{nextAction}</Badge>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-5">
                  <SignalFact label="Version" value={`v${numberOrFallback(signal.activeVersion, "1")}`} />
                  <SignalFact label="Universe" value={formatList(signal.universe, textOrFallback(signal.sourceTicker, "n/a"))} />
                  <SignalFact label="Horizon" value={textOrFallback(signal.horizon)} />
                  <SignalFact label="Benchmark" value={textOrFallback(signal.benchmark)} />
                  <SignalFact label="Decision use" value="buy / sell / hold / hedge / risk" />
                </div>

                <div className="mt-3 rounded-md border border-line bg-paper/70 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/50">Formula preview</p>
                  <p className="mt-1 break-words font-mono text-xs leading-5 text-ink/75">{textOrFallback(signal.formula, "No formula recorded")}</p>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/70 md:grid-cols-4">
                  <SignalFact label="Validation" value={validation.label} tone={validation.tone} />
                  <SignalFact label="Risk posture" value={risk.label} tone={risk.tone} />
                  <SignalFact label="Risk budget" value={risk.budget} tone={risk.budget === "defined" ? "good" : "warn"} />
                  <SignalFact label="Outcome" value={textOrFallback(signal.latestOutcomeQuality, "open")} />
                  <SignalFact label="Latest decision" value={textOrFallback(signal.latestDecisionState, "pending")} />
                  <SignalFact label="Review links" value={String(Math.max(reviewIds.length, numberValue(signal.linkedReviewCount)))} />
                  <SignalFact label="Policy events" value={String(details.policyEvents.length)} />
                  <SignalFact label="Updated" value={formatDate(textOrFallback(signal.updatedAt, ""))} />
                </div>

                <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                  <div className="rounded-md border border-line bg-paper/70 p-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-ink/70">
                      <GitBranch className="h-3.5 w-3.5 text-teal" />
                      Stack links
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/65 md:grid-cols-3">
                      <StackItem label="Scanner" value={textOrFallback(signal.scannerRunId, "not linked")} />
                      <StackItem label="Alpha" value={hypothesisIds[0] || "not linked"} href={hypothesisIds.length ? "/alpha" : undefined} />
                      <StackItem label="Review" value={reviewIds[0] || "not linked"} href={reviewIds.length ? `/review/${encodeURIComponent(reviewIds[0])}` : undefined} />
                      <StackItem label="Trade" value={details.decisionLinks.length ? "decision-linked" : "not linked"} href={details.decisionLinks.length ? "/execution-intelligence" : undefined} />
                      <StackItem label="Outcome" value={textOrFallback(signal.latestOutcomeQuality, "open")} />
                      <StackItem label="History" value={numberValue(signal.outcomeCount) > 0 ? "recorded" : "pending"} href="/history" />
                    </div>
                  </div>

                  <div className="rounded-md border border-line bg-paper/70 p-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-ink/70">
                      <ShieldCheck className="h-3.5 w-3.5 text-teal" />
                      Next action rationale
                    </div>
                    <p className="mt-2 text-xs leading-5 text-ink/65">{nextActionReason(signal, details)}</p>
                    <p className="mt-2 text-[11px] text-ink/50">Cost: {textOrFallback(signal.costModel)} · Overrides: {numberOrFallback(signal.overrideCount, "0")}</p>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedSignalId(signalId);
                      setDetailTab("overview");
                    }}
                    className="focus-ring inline-flex items-center gap-1 rounded-md border border-line bg-teal px-2 py-1 text-xs font-semibold text-fog"
                  >
                    Inspect details
                    <ArrowRight className="h-3 w-3" />
                  </button>
                  <ActionLink href="/alpha" label="Open Alpha Lab" />
                  {reviewIds[0] ? <ActionLink href={`/review/${encodeURIComponent(reviewIds[0])}`} label="Open Review" /> : null}
                  {sourceTicker ? <ActionLink href={`/markets/${encodeURIComponent(sourceTicker)}`} label="Open Market" /> : null}
                  <ActionLink href="/history" label="Open History" />
                </div>
              </li>
            );
          })}
          {signals.length === 0 ? (
            <li className="rounded-md border border-dashed border-line bg-fog/50 px-3 py-3 text-sm text-ink/60">No signals available.</li>
          ) : null}
        </ul>
      </Panel>

      {selectedSignal ? (
        <SignalDetailPanel signal={selectedSignal} details={selectedDetails} tab={detailTab} onTabChange={setDetailTab} />
      ) : null}
    </div>
  );
}

async function loadSignalDetails(signals: Array<Record<string, unknown>>): Promise<Record<string, SignalDetails>> {
  const entries = await Promise.all(
    signals.map(async (signal) => {
      const signalId = textOrFallback(signal.signalId, "");
      if (!signalId) return null;

      const [validationRuns, decisionLinks, policyEvents, versions] = await Promise.all([
        fetchControlPlane(`/signals/${encodeURIComponent(signalId)}/validation-runs`),
        fetchControlPlane(`/signals/${encodeURIComponent(signalId)}/decision-links`),
        fetchControlPlane(`/signals/${encodeURIComponent(signalId)}/policy-events`),
        fetchControlPlane(`/signals/${encodeURIComponent(signalId)}/versions`),
      ]);

      return [
        signalId,
        {
          validationRuns: recordsFromResponse(validationRuns),
          decisionLinks: recordsFromResponse(decisionLinks),
          policyEvents: recordsFromResponse(policyEvents),
          versions: recordsFromResponse(versions),
        },
      ] as [string, SignalDetails];
    })
  );

  return Object.fromEntries(entries.filter((entry): entry is [string, SignalDetails] => entry !== null));
}

function recordsFromResponse(response: Awaited<ReturnType<typeof fetchControlPlane>>): Array<Record<string, unknown>> {
  return response.ok && Array.isArray(response.data) ? (response.data as Array<Record<string, unknown>>) : [];
}

function RelationshipStep({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <p className="text-xs font-semibold text-ink">{label}</p>
      <p className="mt-1 text-[11px] leading-4 text-ink/55">{detail}</p>
    </div>
  );
}

function ActionLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="focus-ring inline-flex items-center gap-1 rounded-md border border-line bg-paper px-2 py-1 text-xs font-semibold text-teal">
      {label}
      <ArrowRight className="h-3 w-3" />
    </Link>
  );
}

function SignalFact({ label, value, tone }: { label: string; value: string; tone?: BadgeTone }) {
  return (
    <div className="rounded-md border border-line bg-paper/70 p-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/45">{label}</p>
      <div className="mt-1">
        {tone ? <Badge tone={tone}>{value}</Badge> : <p className="break-words text-xs font-medium text-ink/75">{value}</p>}
      </div>
    </div>
  );
}

function StackItem({ label, value, href }: { label: string; value: string; href?: string }) {
  const content = <span className="break-all font-mono text-[11px] text-ink/65">{value}</span>;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/45">{label}</p>
      {href && value !== "not linked" ? (
        <Link href={href} className="focus-ring mt-1 inline-flex text-teal underline-offset-2 hover:underline">
          {content}
        </Link>
      ) : (
        <div className="mt-1">{content}</div>
      )}
    </div>
  );
}

function SignalDetailPanel({
  signal,
  details,
  tab,
  onTabChange,
}: {
  signal: Record<string, unknown>;
  details: SignalDetails;
  tab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
}) {
  const signalId = textOrFallback(signal.signalId);
  const validation = latestValidationStatus(signal, details);
  const risk = riskPosture(signal, details);

  return (
    <Panel className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <SectionTitle eyebrow="Decision-Grade Signal Detail" title={textOrFallback(signal.name, signalId)} />
          <p className="mt-2 font-mono text-xs text-ink/55">{signalId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={statusTone(textOrFallback(signal.status, "hypothesis"))}>{textOrFallback(signal.status, "hypothesis")}</Badge>
          <Badge tone={validation.tone}>validation {validation.label}</Badge>
          <Badge tone={risk.tone}>{risk.label}</Badge>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {DETAIL_TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            data-detail-tab={item.key}
            aria-pressed={tab === item.key}
            onClick={() => onTabChange(item.key)}
            className={`focus-ring rounded-md border px-3 py-1 text-xs font-semibold ${
              tab === item.key ? "border-teal bg-teal text-fog" : "border-line bg-fog/70 text-ink/70"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-4 rounded-md border border-line bg-fog/60 p-4">{renderDetailTab(signal, details, tab)}</div>
    </Panel>
  );
}

function renderDetailTab(signal: Record<string, unknown>, details: SignalDetails, tab: DetailTab) {
  const latestRun = details.validationRuns[0] ?? {};
  const risk = riskPosture(signal, details);

  if (tab === "overview") {
    const latestPolicyEvent = details.policyEvents[0] ?? {};
    const latestVersion = details.versions[0] ?? {};
    return (
      <DetailGrid>
        <DetailItem label="Family" value={signalFamily(signal)} />
        <DetailItem label="Origin" value={signalOrigin(signal)} />
        <DetailItem label="Next action" value={signalNextAction(signal, details)} />
        <DetailItem label="Decision use" value="buy, sell, hold, hedge, or risk-adjust" />
        <DetailItem label="Latest validation" value={`${textOrFallback(latestRun.status, latestValidationStatus(signal, details).label)} · ${textOrFallback(latestRun.runType, "run type n/a")}`} />
        <DetailItem label="Latest policy event" value={`${textOrFallback(latestPolicyEvent.eventType, "none")} -> ${textOrFallback(latestPolicyEvent.toStatus, "n/a")}`} />
        <DetailItem label="Latest version" value={`v${numberOrFallback(latestVersion.version, numberOrFallback(signal.activeVersion, "1"))} · ${textOrFallback(latestVersion.formula, textOrFallback(signal.formula))}`} />
        <DetailItem label="Linked Alpha" value={formatList(signal.linkedHypothesisIds)} />
        <DetailItem label="Linked Reviews" value={formatList(signal.linkedReviewIds)} />
      </DetailGrid>
    );
  }

  if (tab === "formula") {
    return (
      <div className="space-y-3">
        <DetailItem label="Formula" value={textOrFallback(signal.formula, "No formula recorded")} mono />
        <DetailGrid>
          <DetailItem label="Universe" value={formatList(signal.universe)} />
          <DetailItem label="Horizon" value={textOrFallback(signal.horizon)} />
          <DetailItem label="Benchmark" value={textOrFallback(signal.benchmark)} />
          <DetailItem label="Cost model" value={textOrFallback(signal.costModel)} />
          <DetailItem label="Validation gates" value={formatList(signal.validationGates)} />
          <DetailItem label="Active version" value={`v${numberOrFallback(signal.activeVersion, "1")}`} />
        </DetailGrid>
      </div>
    );
  }

  if (tab === "evidence") {
    return (
      <DetailGrid>
        <DetailItem label="Scanner run" value={textOrFallback(signal.scannerRunId, "not linked")} />
        <DetailItem label="Source ticker" value={textOrFallback(signal.sourceTicker, formatList(signal.universe))} />
        <DetailItem label="Source signal" value={textOrFallback(signal.sourceSignal, "not recorded")} />
        <DetailItem label="Artifacts" value={formatList(latestRun.artifactRefs)} />
        <DetailItem label="Point-in-time" value={formatBoolean(latestRun.pointInTimeGuaranteed)} />
        <DetailItem label="Hygiene issues" value={formatList(latestRun.hygieneIssues, "none recorded")} />
      </DetailGrid>
    );
  }

  if (tab === "validation") {
    const metrics = isRecord(latestRun.metrics) ? latestRun.metrics : {};
    return (
      <DetailGrid>
        <DetailItem label="Status" value={textOrFallback(latestRun.status, latestValidationStatus(signal, details).label)} />
        <DetailItem label="Run type" value={textOrFallback(latestRun.runType, "not run")} />
        <DetailItem label="Costs" value={formatBoolean(latestRun.includesCosts)} />
        <DetailItem label="Slippage" value={formatBoolean(latestRun.includesSlippage)} />
        <DetailItem label="Liquidity" value={formatBoolean(latestRun.includesLiquidity)} />
        <DetailItem label="Sharpe" value={formatUnknown(metrics.sharpeRatio)} />
        <DetailItem label="Max drawdown" value={formatUnknown(metrics.maxDrawdown)} />
        <DetailItem label="Hit rate" value={formatUnknown(metrics.hitRate)} />
      </DetailGrid>
    );
  }

  if (tab === "trades") {
    return (
      <DetailGrid>
        <DetailItem label="Decision-linked trade state" value={details.decisionLinks.length ? "decision-linked" : "not linked"} />
        <DetailItem label="Execution surface" value="execution-intelligence" />
        <DetailItem label="Cost model" value={textOrFallback(signal.costModel)} />
        <DetailItem label="Implementation note" value="Compare expected edge against cost, slippage, liquidity, and market impact before promotion." />
      </DetailGrid>
    );
  }

  if (tab === "reviews") {
    return (
      <DetailList
        empty="No review links recorded."
        items={details.decisionLinks.length ? details.decisionLinks : stringList(signal.linkedReviewIds).map((reviewId) => ({ reviewId }))}
        renderItem={(item) => `${textOrFallback(item.reviewId, "review")} · ${textOrFallback(item.reviewDecisionState, textOrFallback(signal.latestDecisionState, "pending"))}`}
      />
    );
  }

  if (tab === "outcomes") {
    return (
      <DetailGrid>
        <DetailItem label="Latest outcome" value={textOrFallback(signal.latestOutcomeQuality, "open")} />
        <DetailItem label="Outcome count" value={String(numberValue(signal.outcomeCount))} />
        <DetailItem label="Last reviewed" value={formatDate(textOrFallback(signal.lastReviewedAt, ""))} />
        <DetailItem label="Calibration state" value={numberValue(signal.outcomeCount) > 0 ? "recorded" : "pending writeback"} />
      </DetailGrid>
    );
  }

  if (tab === "risk") {
    return (
      <DetailGrid>
        <DetailItem label="Risk posture" value={risk.label} />
        <DetailItem label="Risk budget" value={risk.budget} />
        <DetailItem label="Max position" value={formatUnknown(signal.maxPositionSize)} />
        <DetailItem label="Drawdown limit" value={formatUnknown(signal.maxDrawdownLimit)} />
        <DetailItem label="Hedge plan" value={formatUnknown(signal.hedgePlan)} />
        <DetailItem label="Risk owner" value={formatUnknown(signal.riskOwner)} />
      </DetailGrid>
    );
  }

  if (tab === "policy") {
    return <DetailList empty="No policy events recorded." items={details.policyEvents} renderItem={(item) => `${textOrFallback(item.eventType, "event")} -> ${textOrFallback(item.toStatus, "n/a")}`} />;
  }

  return <DetailList empty="No signal versions recorded." items={details.versions} renderItem={(item) => `v${numberOrFallback(item.version, "1")} · ${textOrFallback(item.horizon, textOrFallback(signal.horizon))} · ${textOrFallback(item.formula, textOrFallback(signal.formula))}`} />;
}

function DetailGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

function DetailItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md border border-line bg-paper/70 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/45">{label}</p>
      <p className={`mt-1 break-words text-xs leading-5 text-ink/75 ${mono ? "font-mono" : "font-medium"}`}>{value}</p>
    </div>
  );
}

function DetailList({ empty, items, renderItem }: { empty: string; items: Array<Record<string, unknown>>; renderItem: (item: Record<string, unknown>) => string }) {
  if (items.length === 0) return <p className="text-sm text-ink/60">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${renderItem(item)}-${index}`} className="rounded-md border border-line bg-paper/70 px-3 py-2 text-xs text-ink/70">
          {renderItem(item)}
        </li>
      ))}
    </ul>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-md border border-line bg-fog/70 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/50">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
      <p className="mt-1 text-[11px] text-ink/55">{detail}</p>
    </div>
  );
}

function detailsForSignal(signal: Record<string, unknown>, details: Record<string, SignalDetails>): SignalDetails {
  const signalId = textOrFallback(signal.signalId, "");
  return details[signalId] ?? EMPTY_DETAILS;
}

function buildCockpitMetrics(signals: Array<Record<string, unknown>>, details: Record<string, SignalDetails>) {
  const stackLinked = signals.filter((signal) => hasStackLink(signal, detailsForSignal(signal, details))).length;
  const riskBudgeted = signals.filter((signal) => riskPosture(signal, detailsForSignal(signal, details)).budget === "defined").length;
  const validationPassed = signals.filter((signal) => latestValidationStatus(signal, detailsForSignal(signal, details)).label === "passed").length;
  const blocked = signals.filter((signal) => triageKey(signal, detailsForSignal(signal, details)) === "block").length;

  return {
    stackLinked,
    stackMissing: Math.max(signals.length - stackLinked, 0),
    riskBudgeted,
    missingRiskBudget: Math.max(signals.length - riskBudgeted, 0),
    validationPassed,
    validationMissing: Math.max(signals.length - validationPassed, 0),
    blocked,
  };
}

function buildDecisionTriage(signals: Array<Record<string, unknown>>, details: Record<string, SignalDetails>) {
  const config: Array<{ key: string; label: string; detail: string; tone: BadgeTone }> = [
    { key: "act", label: "Act now", detail: "Validated, linked, and inside policy gates.", tone: "good" },
    { key: "review", label: "Review first", detail: "Needs validation, evidence, or review closure.", tone: "warn" },
    { key: "hedge", label: "Hedge / reduce", detail: "Risk posture requires sizing or constraint work.", tone: "info" },
    { key: "monitor", label: "Monitor", detail: "No immediate action, keep outcome memory warm.", tone: "neutral" },
    { key: "block", label: "Blocked", detail: "Missing stack, risk, validation, or cost gates.", tone: "bad" },
    { key: "retire", label: "Retire", detail: "Closed or no longer fit for promotion.", tone: "neutral" },
  ];

  return config.map((entry) => ({
    ...entry,
    count: signals.filter((signal) => triageKey(signal, detailsForSignal(signal, details)) === entry.key).length,
  }));
}

function triageKey(signal: Record<string, unknown>, details: SignalDetails): string {
  const status = textOrFallback(signal.status, "hypothesis");
  const nextAction = signalNextAction(signal, details);
  const validation = latestValidationStatus(signal, details).label;
  const risk = riskPosture(signal, details);

  if (status === "retired" || nextAction === "Archive postmortem") return "retire";
  if (nextAction === "Link stack source" || nextAction === "Define risk budget") return "block";
  if (status === "constrained" || risk.label === "risk_constrained") return "hedge";
  if (status === "active_candidate" && validation === "passed" && risk.budget === "defined") return "act";
  if (nextAction === "Run validation" || nextAction === "Create review" || nextAction === "Resolve review") return "review";
  return "monitor";
}

function signalFamily(signal: Record<string, unknown>): string {
  const source = `${textOrFallback(signal.sourceSignal, "")} ${textOrFallback(signal.name, "")} ${textOrFallback(signal.formula, "")}`.toLowerCase();
  if (source.includes("momentum") || source.includes("sma") || source.includes("trend")) return "momentum";
  if (source.includes("mean") || source.includes("reversion") || source.includes("rsi")) return "mean_reversion";
  if (source.includes("sentiment") || source.includes("news")) return "sentiment";
  if (source.includes("quality") || source.includes("margin")) return "quality";
  if (source.includes("macro") || source.includes("rates") || source.includes("credit")) return "macro";
  if (source.includes("vol")) return "volatility";
  if (source.includes("liquidity") || source.includes("volume")) return "liquidity";
  return "custom";
}

function signalOrigin(signal: Record<string, unknown>): string {
  const origin = textOrFallback(signal.origin, "");
  if (origin) return origin;
  if (textOrFallback(signal.scannerRunId, "")) return "scanner";
  if (textOrFallback(signal.demoSeed, "")) return "demo";
  return "api/manual";
}

function latestValidationStatus(signal: Record<string, unknown>, details: SignalDetails): { label: string; tone: BadgeTone } {
  const latest = details.validationRuns[0];
  const status = textOrFallback(latest?.status, "");
  if (status) return { label: status, tone: status === "passed" ? "good" : status === "failed" ? "bad" : "warn" };

  const signalStatus = textOrFallback(signal.status, "hypothesis");
  if (["validation_passed", "active_candidate", "constrained", "retired"].includes(signalStatus)) return { label: "passed", tone: "good" };
  if (signalStatus === "validation_pending") return { label: "pending", tone: "warn" };
  return { label: "missing", tone: "warn" };
}

function riskPosture(signal: Record<string, unknown>, details: SignalDetails): { label: string; tone: BadgeTone; budget: string } {
  const status = textOrFallback(signal.status, "hypothesis");
  const hasRiskBudget = [signal.riskBudget, signal.riskLimits, signal.maxPositionSize, signal.maxDrawdownLimit].some(hasValue);
  const validation = latestValidationStatus(signal, details).label;

  if (status === "retired") return { label: "risk_blocked", tone: "bad", budget: hasRiskBudget ? "defined" : "missing" };
  if (status === "constrained") return { label: "risk_constrained", tone: "warn", budget: hasRiskBudget ? "defined" : "missing" };
  if (validation === "failed") return { label: "risk_blocked", tone: "bad", budget: hasRiskBudget ? "defined" : "missing" };
  if (!hasRiskBudget) return { label: "risk_blocked", tone: "bad", budget: "missing" };
  return { label: "risk_add", tone: "info", budget: "defined" };
}

function signalNextAction(signal: Record<string, unknown>, details: SignalDetails): string {
  const status = textOrFallback(signal.status, "hypothesis");
  const reviewIds = stringList(signal.linkedReviewIds);
  const decision = textOrFallback(signal.latestDecisionState, "").toLowerCase();
  const outcome = textOrFallback(signal.latestOutcomeQuality, "").toLowerCase();

  if (status === "retired") return "Archive postmortem";
  if (!hasStackLink(signal, details)) return "Link stack source";
  if (latestValidationStatus(signal, details).label !== "passed") return "Run validation";
  if (riskPosture(signal, details).budget === "missing") return "Define risk budget";
  if (reviewIds.length === 0 && details.decisionLinks.length === 0) return "Create review";
  if (!decision || ["pending", "needs_more_data", "decision_unset"].includes(decision)) return "Resolve review";
  if (!outcome || ["open", "decision_unset"].includes(outcome)) return "Record outcome";
  if (status === "constrained") return "Review constraint";
  return "Monitor";
}

function nextActionReason(signal: Record<string, unknown>, details: SignalDetails): string {
  const nextAction = signalNextAction(signal, details);
  const reasons: Record<string, string> = {
    "Archive postmortem": "The signal is retired; keep it visible for outcome memory and postmortem learning.",
    "Link stack source": "This signal needs a source relationship such as scanner run, alpha hypothesis, or review-origin thesis.",
    "Run validation": "Validation is missing or not passed, so the signal should not promote yet.",
    "Define risk budget": "Risk budget, exposure limit, or hedge plan is missing; promotion should fail closed.",
    "Create review": "The signal is measurable, but it needs a linked human review before decision writeback.",
    "Resolve review": "The latest decision is pending or needs more data; close the review before promotion.",
    "Record outcome": "A decision exists, but outcome memory is still open.",
    "Review constraint": "The signal is constrained; inspect the risk or policy event before reuse.",
    Monitor: "Core lifecycle links are present; keep watching validation, outcomes, and decay.",
  };
  return reasons[nextAction] ?? "Review the signal lifecycle before action.";
}

function nextActionTone(action: string): BadgeTone {
  if (["Link stack source", "Define risk budget"].includes(action)) return "bad";
  if (["Run validation", "Create review", "Resolve review", "Record outcome", "Review constraint"].includes(action)) return "warn";
  if (action === "Monitor") return "good";
  return "neutral";
}

function statusTone(status: string): BadgeTone {
  if (["active_candidate", "validation_passed"].includes(status)) return "good";
  if (status === "retired") return "bad";
  if (status === "constrained" || status === "validation_pending") return "warn";
  return "info";
}

function hasStackLink(signal: Record<string, unknown>, details: SignalDetails): boolean {
  return Boolean(
    textOrFallback(signal.scannerRunId, "") ||
      stringList(signal.linkedHypothesisIds).length > 0 ||
      stringList(signal.linkedReviewIds).length > 0 ||
      details.decisionLinks.length > 0 ||
      numberValue(signal.outcomeCount) > 0
  );
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function formatList(value: unknown, fallback = "n/a"): string {
  const values = stringList(value);
  if (values.length === 0) return fallback;
  if (values.length <= 3) return values.join(", ");
  return `${values.slice(0, 3).join(", ")} +${values.length - 3}`;
}

function numberValue(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return 0;
}

function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function formatBoolean(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  return "n/a";
}

function formatUnknown(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "boolean") return value ? "yes" : "no";
  return "n/a";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function gateTone(status: unknown): "good" | "warn" | "bad" | "neutral" {
  if (status === "pass") return "good";
  if (status === "fail") return "bad";
  return "neutral";
}

function qualityGateEntries(scorecard: Record<string, unknown> | null) {
  const rawGates = scorecard?.gates;
  const gates = isRecord(rawGates) ? rawGates : {};
  return Object.entries(gates).map(([name, value]) => {
    const gate = isRecord(value) ? value : {};
    return [name, gate] as const;
  });
}

function allGatesPass(scorecard: Record<string, unknown> | null): boolean {
  const entries = qualityGateEntries(scorecard);
  return entries.length > 0 && entries.every(([, gate]) => gate.status === "pass");
}

function formatDate(value: string): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
