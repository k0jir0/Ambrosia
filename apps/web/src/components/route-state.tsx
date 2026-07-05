"use client";

import { AlertTriangle, LoaderCircle } from "lucide-react";
import { Badge, Panel, cn } from "./ui";

export type RouteStatus = "loading" | "success" | "empty" | "degraded" | "forbidden" | "error";

export function RouteLoading({ title }: { title: string }) {
  return (
    <Panel className="p-6">
      <div className="flex items-center gap-2 text-sm text-ink/70">
        <LoaderCircle className="h-4 w-4 animate-spin text-teal" />
        Loading {title}...
      </div>
    </Panel>
  );
}

export function RouteNotice({
  status,
  message,
  retry,
}: {
  status: Exclude<RouteStatus, "loading" | "success">;
  message: string;
  retry?: () => void;
}) {
  const tone =
    status === "forbidden" ? "warn" : status === "error" ? "bad" : status === "degraded" ? "warn" : "info";

  return (
    <Panel className={cn("p-4", status === "error" ? "border-coral/30" : "")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <AlertTriangle className={cn("h-4 w-4", status === "error" ? "text-coral" : "text-amber")} />
          <span className="text-ink/80">{message}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{status}</Badge>
          {retry ? (
            <button
              type="button"
              onClick={retry}
              className="focus-ring rounded-md border border-line bg-fog/70 px-3 py-1 text-xs font-semibold text-ink/80"
            >
              Retry
            </button>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}

export function RouteStatusBadge({ status }: { status: RouteStatus }) {
  const tone =
    status === "success"
      ? "good"
      : status === "degraded"
        ? "warn"
        : status === "forbidden" || status === "error"
          ? "bad"
          : status === "empty"
            ? "neutral"
            : "info";
  return <Badge tone={tone}>{status}</Badge>;
}
