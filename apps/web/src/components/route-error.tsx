"use client";

import { AlertTriangle } from "lucide-react";
import { Panel } from "./ui";

export function RouteErrorView({
  title,
  message,
  reset,
}: {
  title: string;
  message: string;
  reset?: () => void;
}) {
  return (
    <Panel className="p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-coral" />
          <div>
            <p className="text-sm font-semibold text-ink">{title}</p>
            <p className="mt-1 text-sm text-ink/70">{message}</p>
          </div>
        </div>
        {reset ? (
          <button
            type="button"
            onClick={reset}
            className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
          >
            Retry
          </button>
        ) : null}
      </div>
    </Panel>
  );
}
