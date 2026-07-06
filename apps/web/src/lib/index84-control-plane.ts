import { getApiBaseUrl } from "./api";

export type ControlPlaneState = "loading" | "success" | "empty" | "degraded" | "forbidden" | "error";
const CONTROL_PLANE_TIMEOUT_MS = 5000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export async function fetchControlPlane(path: string): Promise<{ ok: boolean; status: number; data: unknown; message?: string }> {
  const base = getApiBaseUrl();
  if (!base) {
    return { ok: false, status: 503, data: null, message: "API base URL is unavailable in this environment." };
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), CONTROL_PLANE_TIMEOUT_MS);

  try {
    const response = await fetch(`${base}${path}`, { method: "GET", signal: controller.signal });
    const data = await response.json().catch(() => null);
    return { ok: response.ok, status: response.status, data };
  } catch {
    return { ok: false, status: 0, data: null, message: "Network request failed." };
  } finally {
    window.clearTimeout(timeout);
  }
}

export function mapStatus(httpStatus: number, data: unknown): ControlPlaneState {
  if (httpStatus === 403) return "forbidden";
  if (httpStatus >= 400 || httpStatus === 0) return "error";
  if (Array.isArray(data) && data.length === 0) return "empty";
  if (isRecord(data) && data.status === "degraded") return "degraded";
  return "success";
}

export function numberOrFallback(value: unknown, fallback = "n/a"): string {
  return typeof value === "number" ? String(value) : fallback;
}

export function textOrFallback(value: unknown, fallback = "n/a"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}
