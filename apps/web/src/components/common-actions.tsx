"use client";

import type { ComponentType } from "react";
import { Activity, BarChart3, FileJson, RefreshCw, TrendingUp, AlertCircle, Plus, Sparkles, FileText, Clock, Shield, LogOut } from "lucide-react";

interface CommonActionsProps {
  onNewPacket: () => void;
  onGenerateThesis: () => void;
  onIngestAlert: () => void;
  onRefreshMetrics: () => void;
  onViewTechnicals: () => void;
  onViewSentiment: () => void;
  onCompareMarkets: () => void;
  onPrepareBacktest: () => void;
  onRunBacktest: () => void;
  onRecordDecision: () => void;
  onSetFollowUp: () => void;
  onViewRisks: () => void;
  onExportReport: () => void;
  disabled?: boolean;
}

export function CommonActionsBar({
  onNewPacket,
  onGenerateThesis,
  onIngestAlert,
  onRefreshMetrics,
  onViewTechnicals,
  onViewSentiment,
  onCompareMarkets,
  onPrepareBacktest,
  onRunBacktest,
  onRecordDecision,
  onSetFollowUp,
  onViewRisks,
  onExportReport,
  disabled = false,
}: CommonActionsProps) {
  return (
    <div className="space-y-3 rounded-lg border border-secondary bg-surface-secondary p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-tertiary">Common Actions</div>
      
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {/* Core workflow */}
        <ActionButton 
          icon={Plus} 
          label="New Packet" 
          onClick={onNewPacket}
          disabled={disabled}
          tooltip="Create a new decision packet"
        />
        <ActionButton 
          icon={Sparkles} 
          label="Seed Thesis" 
          onClick={onGenerateThesis}
          disabled={disabled}
          variant="secondary"
          tooltip="AI-assisted thesis generation"
        />
        <ActionButton 
          icon={AlertCircle} 
          label="Ingest Alert" 
          onClick={onIngestAlert}
          disabled={disabled}
          tooltip="Intake TradingView or manual alert"
        />

        {/* Market & Technicals */}
        <ActionButton 
          icon={RefreshCw} 
          label="Refresh Metrics" 
          onClick={onRefreshMetrics}
          disabled={disabled}
          tooltip="Update market data and indicators"
        />
        <ActionButton 
          icon={BarChart3} 
          label="View Technicals" 
          onClick={onViewTechnicals}
          disabled={disabled}
          tooltip="Display RSI, MACD, moving averages"
        />
        <ActionButton 
          icon={TrendingUp} 
          label="View Sentiment" 
          onClick={onViewSentiment}
          disabled={disabled}
          tooltip="View market and news sentiment"
        />
        <ActionButton 
          icon={Activity} 
          label="Compare Markets" 
          onClick={onCompareMarkets}
          disabled={disabled}
          tooltip="Analyze correlations and inter-market context"
        />

        {/* Backtesting & Validation */}
        <ActionButton 
          icon={FileJson} 
          label="Prepare Backtest" 
          onClick={onPrepareBacktest}
          disabled={disabled}
          tooltip="Define backtest parameters and rules"
        />
        <ActionButton 
          icon={TrendingUp} 
          label="Run Backtest" 
          onClick={onRunBacktest}
          disabled={disabled}
          variant="secondary"
          tooltip="Execute controlled backtest if eligible"
        />

        {/* Decision & Risk */}
        <ActionButton 
          icon={LogOut} 
          label="Record Decision" 
          onClick={onRecordDecision}
          disabled={disabled}
          variant="accent"
          tooltip="Capture pursuit, watch, reject, or defer"
        />
        <ActionButton 
          icon={Shield} 
          label="View Risks" 
          onClick={onViewRisks}
          disabled={disabled}
          tooltip="Monitor portfolio and position risks"
        />

        {/* Follow-up & Export */}
        <ActionButton 
          icon={Clock} 
          label="Set Follow-Up" 
          onClick={onSetFollowUp}
          disabled={disabled}
          tooltip="Schedule review or trigger reminder"
        />
        <ActionButton 
          icon={FileText} 
          label="Export Report" 
          onClick={onExportReport}
          disabled={disabled}
          tooltip="Generate PDF or markdown report"
        />
      </div>

      <div className="border-t border-secondary pt-3 text-xs text-tertiary">
        <p className="font-semibold">Quant Workflow Agent</p>
        <p className="mt-1">All decisions remain under human authority. Backtests are gated by eligibility rules. No live execution.</p>
      </div>
    </div>
  );
}

interface ActionButtonProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "accent";
  tooltip?: string;
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  disabled = false,
  variant = "primary",
  tooltip,
}: ActionButtonProps) {
  const variantClasses = {
    primary: "bg-primary/10 hover:bg-primary/20 text-primary",
    secondary: "bg-secondary/10 hover:bg-secondary/20 text-secondary",
    accent: "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600",
  };

  return (
    <div className="group relative">
      <button
        onClick={onClick}
        disabled={disabled}
        className={`flex w-full flex-col items-center justify-center gap-1 rounded border border-secondary/50 px-2 py-2 text-center text-xs font-medium transition-colors ${variantClasses[variant]} disabled:opacity-50 disabled:cursor-not-allowed`}
        title={tooltip}
      >
        <Icon className="h-4 w-4" />
        <span className="line-clamp-2">{label}</span>
      </button>
      {tooltip && (
        <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 rounded bg-surface px-2 py-1 text-xs text-tertiary opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap z-10">
          {tooltip}
        </div>
      )}
    </div>
  );
}
