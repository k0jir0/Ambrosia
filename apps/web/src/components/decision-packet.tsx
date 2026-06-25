"use client";

import { BarChart3, TrendingUp, Zap, Binoculars, DollarSign, Users, Shield, Gauge } from "lucide-react";
import { Badge, Panel, cn } from "./ui";
import type { DecisionPacket } from "@/lib/types";

interface DecisionPacketUIProps {
  packet: DecisionPacket;
}

export function DecisionPacketUI({ packet }: DecisionPacketUIProps) {
  return (
    <div className="space-y-4">
      {/* Header with packet metadata */}
      <Panel>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-bold text-ink">{packet.title}</h2>
            <p className="mt-1 text-sm text-secondary">{packet.thesis}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge>{packet.ticker}</Badge>
              <Badge>{packet.assetClass}</Badge>
              <Badge>{packet.timeHorizon}</Badge>
              <Badge tone="neutral">{packet.intendedExpression}</Badge>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-primary">{packet.confidence}%</div>
            <p className="text-xs text-tertiary">Overall Confidence</p>
          </div>
        </div>
      </Panel>

      {/* Main Grid: Two Columns */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* LEFT COLUMN: Signal & Market Context */}
        <div className="space-y-4">
          {/* Signal/Thesis Section */}
          <PacketSection 
            icon={Zap}
            title="Signal"
          >
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase text-tertiary">Thesis</p>
                <p className="mt-1 text-sm text-ink">{packet.thesis}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-tertiary">Intended Expression</p>
                <p className="mt-1 text-sm text-ink">{packet.intendedExpression}</p>
              </div>
            </div>
          </PacketSection>

          {/* Market Snapshot Section */}
          {packet.marketSnapshot && (
            <PacketSection 
              icon={TrendingUp}
              title="Market Snapshot"
            >
              <div className="grid grid-cols-2 gap-3">
                <MetricDisplay 
                  label="Price" 
                  value={`$${packet.marketSnapshot.price.toFixed(2)}`}
                  change={packet.marketSnapshot.priceChange24h}
                />
                <MetricDisplay 
                  label="Volume (24h)" 
                  value={`$${(packet.marketSnapshot.volume24h / 1e9).toFixed(2)}B`}
                />
                {packet.marketSnapshot.marketCap && (
                  <MetricDisplay 
                    label="Market Cap" 
                    value={`$${(packet.marketSnapshot.marketCap / 1e9).toFixed(2)}B`}
                  />
                )}
                <div className="flex flex-col col-span-2">
                  <span className="text-xs text-tertiary mb-1">Data Provenance</span>
                  <div className="flex flex-wrap items-center gap-2">
                    <ProvenanceBadge mode={packet.marketSnapshot.dataSourceConfidence} />
                    <span className="text-xs text-ink">{packet.marketSnapshot.dataSource}</span>
                    {packet.marketSnapshot.freshnessSeconds !== null && packet.marketSnapshot.freshnessSeconds !== undefined && (
                      <span className="text-xs text-tertiary">· {packet.marketSnapshot.freshnessSeconds}s ago</span>
                    )}
                    {packet.marketSnapshot.freshnessSeconds === null && (
                      <span className="text-xs text-tertiary">· deterministic</span>
                    )}
                  </div>
                </div>
              </div>
            </PacketSection>
          )}

          {/* Technicals Section */}
          {packet.technicals && (
            <PacketSection 
              icon={BarChart3}
              title="Technicals"
            >
              <div className="grid grid-cols-2 gap-3">
                {packet.technicals.rsi !== null && (
                  <MetricDisplay label="RSI (14)" value={packet.technicals.rsi.toFixed(1)} />
                )}
                {packet.technicals.movingAverage50 !== null && (
                  <MetricDisplay label="MA50" value={`$${packet.technicals.movingAverage50.toFixed(2)}`} />
                )}
                {packet.technicals.volatilityRealized !== null && (
                  <MetricDisplay label="Volatility" value={`${(packet.technicals.volatilityRealized * 100).toFixed(1)}%`} />
                )}
                <div className="flex flex-col">
                  <span className="text-xs text-tertiary">Trend</span>
                  <div className={`mt-1 inline-flex w-fit rounded px-2 py-1 text-xs font-semibold ${getTrendColor(packet.technicals.trend)}`}>
                    {packet.technicals.trend.toUpperCase()}
                  </div>
                </div>
                <div className="col-span-2 flex items-center gap-2 pt-1">
                  <ProvenanceBadge mode={packet.technicals.dataMode ?? packet.technicals.dataQuality === "verified" ? "live" : "fallback"} />
                  <span className="text-xs text-tertiary">{packet.technicals.dataQuality}</span>
                </div>
              </div>
            </PacketSection>
          )}

          {/* Sentiment Section */}
          {packet.sentiment && (
            <PacketSection 
              icon={Users}
              title="Sentiment"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-tertiary">Overall Score</span>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-20 overflow-hidden rounded bg-secondary/30">
                      <div 
                        className={`h-full ${getSentimentBarColor(packet.sentiment.overallScore)}`}
                        style={{ width: `${packet.sentiment.overallScore}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-ink">{packet.sentiment.overallScore}%</span>
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-tertiary">{packet.sentiment.sentiment.toUpperCase()}</span>
                  <span className="text-xs text-secondary">{packet.sentiment.trendDirection}</span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <ProvenanceBadge mode={packet.sentiment.dataMode ?? (packet.sentiment.sourceConfidence === "verified" ? "live" : "demo")} />
                  <span className="text-xs text-tertiary">{packet.sentiment.sourceConfidence}</span>
                </div>
              </div>
            </PacketSection>
          )}
        </div>

        {/* RIGHT COLUMN: Analysis & Risk */}
        <div className="space-y-4">
          {/* Inter-Market Section */}
          {packet.interMarket && (
            <PacketSection 
              icon={Binoculars}
              title="Inter-Market"
            >
              <div className="space-y-2">
                {packet.interMarket.correlationWithBenchmark !== null && (
                  <div className="flex justify-between">
                    <span className="text-sm text-secondary">Correlation (Bench)</span>
                    <span className="font-semibold text-ink">{packet.interMarket.correlationWithBenchmark.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-sm text-secondary">Regime</span>
                  <span className={`font-semibold ${packet.interMarket.regimeState === 'risk_on' ? 'text-green-600' : 'text-red-600'}`}>
                    {packet.interMarket.regimeState.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-secondary">Spillover Risk</span>
                  <span className={`font-semibold ${getRiskColor(packet.interMarket.spilloverRisk)}`}>
                    {packet.interMarket.spilloverRisk.toUpperCase()}
                  </span>
                </div>
              </div>
            </PacketSection>
          )}

          {/* Fundamentals Section */}
          {packet.fundamentals && (
            <PacketSection 
              icon={DollarSign}
              title="Fundamentals"
            >
              <div className="grid grid-cols-2 gap-3">
                {packet.fundamentals.priceToBook !== null && (
                  <MetricDisplay label="P/B" value={packet.fundamentals.priceToBook.toFixed(2)} />
                )}
                {packet.fundamentals.roe !== null && (
                  <MetricDisplay label="ROE" value={`${(packet.fundamentals.roe * 100).toFixed(1)}%`} />
                )}
                {packet.fundamentals.debtToEquity !== null && (
                  <MetricDisplay label="D/E" value={packet.fundamentals.debtToEquity.toFixed(2)} />
                )}
                {packet.fundamentals.qualityScore !== null && (
                  <MetricDisplay label="Quality" value={packet.fundamentals.qualityScore.toFixed(0)} />
                )}
              </div>
            </PacketSection>
          )}

          {/* Bull/Bear Section */}
          <PacketSection 
            icon={TrendingUp}
            title="Bull/Bear Debate"
          >
            <div className="space-y-2">
              <div>
                <p className="text-xs font-semibold text-green-600">Bull Case</p>
                <p className="mt-1 text-sm text-ink">{packet.strongestCritique}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-red-600">Bear Test</p>
                <p className="mt-1 text-sm text-ink">{packet.disconfirmingTest}</p>
              </div>
            </div>
          </PacketSection>

          {/* Validation/Backtest Section */}
          {packet.backtestPlan && (
            <PacketSection 
              icon={Gauge}
              title="Validation/Backtest"
            >
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-secondary">Status</span>
                  <Badge tone={packet.backtestPlan.status === 'eligible' ? 'good' : 'neutral'}>
                    {packet.backtestPlan.status.toUpperCase()}
                  </Badge>
                </div>
                {packet.backtestResult && (
                  <div className="grid grid-cols-2 gap-2">
                    {packet.backtestResult.sharpeRatio !== null && (
                      <MetricDisplay label="Sharpe" value={packet.backtestResult.sharpeRatio.toFixed(2)} />
                    )}
                    {packet.backtestResult.maxDrawdown !== null && (
                      <MetricDisplay label="Max DD" value={`${(packet.backtestResult.maxDrawdown * 100).toFixed(1)}%`} />
                    )}
                  </div>
                )}
                {packet.backtestPlan.refusalReason && (
                  <p className="text-xs text-red-600">{packet.backtestPlan.refusalReason}</p>
                )}
              </div>
            </PacketSection>
          )}

          {/* Risk Section */}
          {packet.riskMonitor && (
            <PacketSection 
              icon={Shield}
              title="Risk"
            >
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-secondary">Position Size</span>
                  <span className="font-semibold text-ink">${packet.riskMonitor.activePositionSize.toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-secondary">Concentration</span>
                  <span className={`font-semibold ${getRiskColor(packet.riskMonitor.concentrationRisk)}`}>
                    {packet.riskMonitor.concentrationRisk.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-secondary">Status</span>
                  <span className={`font-semibold ${packet.riskMonitor.status === 'alert' ? 'text-red-600' : packet.riskMonitor.status === 'monitoring' ? 'text-amber-600' : 'text-green-600'}`}>
                    {packet.riskMonitor.status.toUpperCase()}
                  </span>
                </div>
              </div>
            </PacketSection>
          )}
        </div>
      </div>

      {/* Full-width sections */}
      
      {/* Confidence Components */}
      {packet.confidenceBreakdown && (
        <PacketSection title="Confidence Breakdown">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            <ConfidenceBar label="Evidence" score={packet.confidenceBreakdown.evidenceScore} />
            <ConfidenceBar label="Technical" score={packet.confidenceBreakdown.technicalScore} />
            <ConfidenceBar label="Sentiment" score={packet.confidenceBreakdown.sentimentScore} />
            <ConfidenceBar label="Inter-Mkt" score={packet.confidenceBreakdown.interMarketScore} />
            <ConfidenceBar label="Validation" score={packet.confidenceBreakdown.validationScore} />
            <ConfidenceBar label="Tradeability" score={packet.confidenceBreakdown.tradeabilityScore} />
            <ConfidenceBar label="Risk-Adj" score={packet.confidenceBreakdown.riskAdjustedScore} />
            <ConfidenceBar label="Overall" score={packet.confidenceBreakdown.overallConfidence} isMajor />
          </div>
          {packet.confidenceBreakdown.blockers.length > 0 && (
            <div className="mt-3 rounded bg-red-500/10 p-2">
              <p className="text-xs font-semibold text-red-600">Blockers:</p>
              <ul className="mt-1 text-xs text-ink">
                {packet.confidenceBreakdown.blockers.map((blocker, i) => (
                  <li key={i}>• {blocker}</li>
                ))}
              </ul>
            </div>
          )}
        </PacketSection>
      )}

      {/* Portfolio Context */}
      {packet.portfolioContext && (
        <PacketSection title="Portfolio Context">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricDisplay label="Gross Exp" value={`${(packet.portfolioContext.grossExposure * 100).toFixed(0)}%`} />
            <MetricDisplay label="Net Exp" value={`${(packet.portfolioContext.netExposure * 100).toFixed(0)}%`} />
            <MetricDisplay label="Long Exp" value={`${(packet.portfolioContext.longExposure * 100).toFixed(0)}%`} />
            <MetricDisplay label="Short Exp" value={`${(packet.portfolioContext.shortExposure * 100).toFixed(0)}%`} />
          </div>
          {packet.portfolioContext.relatedPositions.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-tertiary">Related Positions:</p>
              <p className="mt-1 text-sm text-ink">{packet.portfolioContext.relatedPositions.join(", ")}</p>
            </div>
          )}
        </PacketSection>
      )}

      {/* Audit */}
      <PacketSection title="Audit">
        <div className="space-y-1">
          {packet.audit.slice(0, 5).map((event) => (
            <div key={event.id} className="flex justify-between text-xs">
              <span className="text-secondary">{event.timestamp}</span>
              <span className="font-semibold text-ink">{event.eventType}</span>
              <span className="text-tertiary">{event.detail}</span>
            </div>
          ))}
        </div>
      </PacketSection>
    </div>
  );
}

/* Helper Components */

interface PacketSectionProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}

function PacketSection({ icon: Icon, title, children }: PacketSectionProps) {
  return (
    <Panel>
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="h-4 w-4 text-primary" />}
        <p className="text-xs font-bold uppercase tracking-wider text-ink">{title}</p>
      </div>
      {children}
    </Panel>
  );
}

interface MetricDisplayProps {
  label: string;
  value: string;
  change?: number;
}

function MetricDisplay({ label, value, change }: MetricDisplayProps) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-tertiary">{label}</span>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-sm font-bold text-ink">{value}</span>
        {change !== undefined && (
          <span className={`text-xs font-semibold ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

interface ConfidenceBarProps {
  label: string;
  score: number;
  isMajor?: boolean;
}

function ConfidenceBar({ label, score, isMajor }: ConfidenceBarProps) {
  return (
    <div className={cn(isMajor && "col-span-2 sm:col-span-1")}>
      <div className="flex justify-between mb-1">
        <span className={`text-xs font-semibold ${isMajor ? 'text-ink' : 'text-secondary'}`}>{label}</span>
        <span className={`text-xs font-bold ${isMajor ? 'text-primary' : 'text-ink'}`}>{score}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-secondary/30">
        <div 
          className="h-full bg-primary/60"
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

function getTrendColor(trend: string): string {
  switch (trend) {
    case "uptrend":
      return "bg-green-500/20 text-green-700";
    case "downtrend":
      return "bg-red-500/20 text-red-700";
    case "sideways":
      return "bg-amber-500/20 text-amber-700";
    default:
      return "bg-secondary/20 text-secondary";
  }
}

function getRiskColor(level: string): string {
  switch (level) {
    case "high":
      return "text-red-600";
    case "medium":
      return "text-amber-600";
    case "low":
      return "text-green-600";
    default:
      return "text-secondary";
  }
}

function getSentimentBarColor(score: number): string {
  if (score >= 66) return "bg-green-500";
  if (score >= 34) return "bg-amber-500";
  return "bg-red-500";
}

interface ProvenanceBadgeProps {
  mode: "live" | "fallback" | "demo" | string;
}

function ProvenanceBadge({ mode }: ProvenanceBadgeProps) {
  const config: Record<string, { dot: string; label: string }> = {
    live:     { dot: "bg-green-500", label: "LIVE" },
    fallback: { dot: "bg-amber-500", label: "FALLBACK" },
    demo:     { dot: "bg-secondary",  label: "DEMO" },
  };
  const c = config[mode] ?? { dot: "bg-secondary", label: mode.toUpperCase() };
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider bg-secondary/20">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
