"use client";

import type { ComponentType } from "react";
import { BarChart3, FileJson, RefreshCw, BrainCircuit, Plus, FolderOpen, Shield, LogOut } from "lucide-react";

interface CommonActionsProps {
  onNewReview: () => void;
  onOpenExistingReview: () => void;
  onRefreshMetrics: () => void;
  onRunAgentSwarm: () => void;
  onPrepareBacktest: () => void;
  onEvaluateRisk: () => void;
  onDeriveConfidence: () => void;
  onRecordDecision: () => void;
  disabled?: boolean;
}

export function CommonActionsBar({
  onNewReview,
  onOpenExistingReview,
  onRefreshMetrics,
  onRunAgentSwarm,
  onPrepareBacktest,
  onEvaluateRisk,
  onDeriveConfidence,
  onRecordDecision,
  disabled = false,
}: CommonActionsProps) {
  return (
    <div className="space-y-3 rounded-lg border border-line bg-paper p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-300">Core Actions</div>
      <p className="text-sm leading-5 text-slate-400">
        The first-minute operator workflow: open or start a case, enrich it, pressure-test it, and record the human decision.
      </p>
      
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        <ActionButton 
          icon={Plus} 
          label="New Review" 
          onClick={onNewReview}
          disabled={disabled}
          tooltip="Create a new review case"
        />
        <ActionButton 
          icon={FolderOpen} 
          label="Open Existing" 
          onClick={onOpenExistingReview}
          disabled={disabled}
          tooltip="Browse and open a stored review"
        />
        <ActionButton 
          icon={RefreshCw} 
          label="Refresh Metrics" 
          onClick={onRefreshMetrics}
          disabled={disabled}
          tooltip="Update market data and indicators"
        />
        <ActionButton 
          icon={BrainCircuit} 
          label="Run Agent Swarm" 
          onClick={onRunAgentSwarm}
          disabled={disabled}
          tooltip="Run specialist coordinator and synthesis"
        />
        <ActionButton 
          icon={FileJson} 
          label="Prepare Backtest" 
          onClick={onPrepareBacktest}
          disabled={disabled}
          tooltip="Define validation and test gates"
        />
        <ActionButton 
          icon={Shield} 
          label="Evaluate Risk" 
          onClick={onEvaluateRisk}
          disabled={disabled}
          tooltip="Run risk monitor against packet context"
        />
        <ActionButton 
          icon={BarChart3} 
          label="Derive Confidence" 
          onClick={onDeriveConfidence}
          disabled={disabled}
          variant="secondary"
          tooltip="Compute confidence from current evidence"
        />
        <ActionButton 
          icon={LogOut} 
          label="Record Decision" 
          onClick={onRecordDecision}
          disabled={disabled}
          variant="accent"
          tooltip="Capture pursuit, watch, reject, or defer"
        />
      </div>

      <div className="border-t border-line pt-3 text-xs text-slate-300">
        <p className="font-semibold text-ink">Quant Workflow Agent</p>
        <p className="mt-1 text-slate-400">All decisions remain under human authority. Backtests are gated by eligibility rules. No live execution.</p>
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
    primary: "bg-teal/10 hover:bg-teal/20 text-teal",
    secondary: "bg-violet/10 hover:bg-violet/20 text-violet",
    accent: "bg-amber/10 hover:bg-amber/20 text-amber",
  };

  return (
    <div className="group relative">
      <button
        onClick={onClick}
        disabled={disabled}
        className={`flex w-full flex-col items-center justify-center gap-1 rounded border border-line px-2 py-2 text-center text-xs font-medium transition-colors ${variantClasses[variant]} disabled:cursor-not-allowed disabled:opacity-50`}
        title={tooltip}
      >
        <Icon className="h-4 w-4" />
        <span className="line-clamp-2">{label}</span>
      </button>
      {tooltip && (
        <div className="pointer-events-none absolute -top-10 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded border border-line bg-fog px-2 py-1 text-xs text-ink opacity-0 shadow-panel transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          {tooltip}
        </div>
      )}
    </div>
  );
}
