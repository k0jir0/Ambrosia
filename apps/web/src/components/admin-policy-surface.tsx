"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  activateGuardrailPolicy,
  ApiUnavailableError,
  createGuardrailPolicy,
  getActiveGuardrailPolicy,
  listAdminAuditEvents,
  listGuardrailPolicies,
} from "@/lib/api";
import type {
  AdminAuditEvent,
  GuardrailPolicyProfile,
  GuardrailPolicyProfileCreate,
  GuardrailRiskTolerance,
} from "@/lib/types";
import { Badge, Panel, SectionTitle } from "./ui";

const DEFAULT_FORM: GuardrailPolicyProfileCreate = {
  name: "",
  description: "",
  riskTolerance: "balanced",
  maxPositionSizePct: 10,
  maxPortfolioDrawdownPct: 12,
  refusalSensitivity: 65,
  allowLiveMutation: false,
  requiresTwoPersonApproval: true,
  updatedBy: "admin-operator",
};

export function AdminPolicySurface() {
  const [policies, setPolicies] = useState<GuardrailPolicyProfile[]>([]);
  const [activePolicy, setActivePolicy] = useState<GuardrailPolicyProfile | null>(null);
  const [auditEvents, setAuditEvents] = useState<AdminAuditEvent[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "fallback" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [errorText, setErrorText] = useState<string>("");
  const [form, setForm] = useState<GuardrailPolicyProfileCreate>(DEFAULT_FORM);

  const refresh = useCallback(async () => {
    setStatus("loading");
    setErrorText("");
    try {
      const [policyList, active, audit] = await Promise.all([
        listGuardrailPolicies(),
        getActiveGuardrailPolicy(),
        listAdminAuditEvents(20),
      ]);
      setPolicies(policyList);
      setActivePolicy(active);
      setAuditEvents(audit);
      setStatus("ready");
    } catch (error) {
      if (error instanceof ApiUnavailableError) {
        setStatus("fallback");
        setErrorText("Admin policy services are currently unavailable.");
        return;
      }
      const message = error instanceof Error ? error.message : "Unknown error";
      setStatus("error");
      setErrorText(message);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const policySummary = useMemo(() => {
    const activeCount = policies.filter((p) => p.isActive).length;
    return { total: policies.length, activeCount };
  }, [policies]);

  async function handleCreatePolicy() {
    if (!form.name.trim()) {
      setErrorText("Policy name is required.");
      return;
    }

    setBusy(true);
    setErrorText("");
    try {
      await createGuardrailPolicy({ ...form, name: form.name.trim(), description: form.description.trim() });
      setForm(DEFAULT_FORM);
      await refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create policy";
      setErrorText(message);
    } finally {
      setBusy(false);
    }
  }

  async function handleActivate(profileId: string) {
    setBusy(true);
    setErrorText("");
    try {
      await activateGuardrailPolicy(profileId, form.updatedBy || "admin-operator");
      await refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to activate policy";
      setErrorText(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <SectionTitle eyebrow="Policy and Guardrails" title="Configurable refusal and risk policy profiles" />
        <p className="mt-2 text-sm text-ink/75">
          Admin policy profiles define risk tolerance, refusal sensitivity, and privileged execution constraints. Only one profile should be active at a time.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <Badge tone="bad">Privileged controls</Badge>
          <Badge tone={status === "ready" ? "good" : status === "loading" ? "info" : "warn"}>
            {status === "ready" ? "Connected" : status === "loading" ? "Loading" : "Unavailable"}
          </Badge>
          <Badge tone="info">{policySummary.total} profiles</Badge>
          <Badge tone="warn">{policySummary.activeCount} active</Badge>
        </div>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Active Profile" title={activePolicy ? activePolicy.name : "No active profile"} />
        {activePolicy ? (
          <div className="mt-3 grid gap-2 text-sm md:grid-cols-3">
            <Info label="Risk tolerance" value={activePolicy.riskTolerance} />
            <Info label="Max position" value={`${activePolicy.maxPositionSizePct}%`} />
            <Info label="Max drawdown" value={`${activePolicy.maxPortfolioDrawdownPct}%`} />
            <Info label="Refusal sensitivity" value={`${activePolicy.refusalSensitivity}`} />
            <Info label="Two-person approval" value={activePolicy.requiresTwoPersonApproval ? "required" : "optional"} />
            <Info label="Live mutation" value={activePolicy.allowLiveMutation ? "allowed" : "blocked"} />
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink/65">No active policy profile is currently available.</p>
        )}
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Profile Registry" title="Available policy profiles" />
        <div className="mt-4 overflow-hidden rounded-lg border border-line">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-fog/80 text-xs uppercase tracking-wide text-ink/55">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Risk</th>
                <th className="px-3 py-2">Refusal</th>
                <th className="px-3 py-2">Limits</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {policies.map((policy) => (
                <tr key={policy.id} className="bg-paper/95">
                  <td className="px-3 py-2">
                    <p className="font-medium text-ink">{policy.name}</p>
                    <p className="text-xs text-ink/60">{policy.id}</p>
                  </td>
                  <td className="px-3 py-2 capitalize text-ink/70">{policy.riskTolerance}</td>
                  <td className="px-3 py-2 text-ink/70">{policy.refusalSensitivity}</td>
                  <td className="px-3 py-2 text-ink/70">
                    {policy.maxPositionSizePct}% / {policy.maxPortfolioDrawdownPct}%
                  </td>
                  <td className="px-3 py-2">
                    <Badge tone={policy.isActive ? "good" : "neutral"}>{policy.isActive ? "Active" : "Inactive"}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      disabled={busy || policy.isActive}
                      onClick={() => void handleActivate(policy.id)}
                      className="rounded-md border border-line bg-fog px-2 py-1 text-xs font-medium text-ink transition hover:bg-teal/10 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Activate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Create Profile" title="Add a new guardrail policy profile" />
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Field label="Name">
            <input
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
          </Field>
          <Field label="Updated By">
            <input
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.updatedBy}
              onChange={(event) => setForm((prev) => ({ ...prev, updatedBy: event.target.value }))}
            />
          </Field>
          <Field label="Risk Tolerance">
            <select
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.riskTolerance}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, riskTolerance: event.target.value as GuardrailRiskTolerance }))
              }
            >
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </Field>
          <Field label="Refusal Sensitivity (0-100)">
            <input
              type="number"
              min={0}
              max={100}
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.refusalSensitivity}
              onChange={(event) => setForm((prev) => ({ ...prev, refusalSensitivity: Number(event.target.value) || 0 }))}
            />
          </Field>
          <Field label="Max Position Size %">
            <input
              type="number"
              min={1}
              max={100}
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.maxPositionSizePct}
              onChange={(event) => setForm((prev) => ({ ...prev, maxPositionSizePct: Number(event.target.value) || 1 }))}
            />
          </Field>
          <Field label="Max Drawdown %">
            <input
              type="number"
              min={1}
              max={100}
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
              value={form.maxPortfolioDrawdownPct}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, maxPortfolioDrawdownPct: Number(event.target.value) || 1 }))
              }
            />
          </Field>
        </div>
        <Field label="Description" className="mt-3">
          <textarea
            className="min-h-20 w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
          />
        </Field>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <label className="inline-flex items-center gap-2 text-ink/80">
            <input
              type="checkbox"
              checked={form.requiresTwoPersonApproval}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, requiresTwoPersonApproval: event.target.checked }))
              }
            />
            Require two-person approval
          </label>
          <label className="inline-flex items-center gap-2 text-ink/80">
            <input
              type="checkbox"
              checked={form.allowLiveMutation}
              onChange={(event) => setForm((prev) => ({ ...prev, allowLiveMutation: event.target.checked }))}
            />
            Allow live mutation
          </label>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleCreatePolicy()}
            className="rounded-md border border-teal/30 bg-teal/10 px-3 py-2 text-sm font-semibold text-teal transition hover:bg-teal/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Create Policy Profile
          </button>
          {errorText ? <p className="text-sm text-coral">{errorText}</p> : null}
        </div>
      </Panel>

      <Panel className="p-5">
        <SectionTitle eyebrow="Admin Audit" title="Recent privileged actions" />
        <div className="mt-4 overflow-hidden rounded-lg border border-line">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-fog/80 text-xs uppercase tracking-wide text-ink/55">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Actor</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Severity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {auditEvents.length > 0 ? (
                auditEvents.map((event) => (
                  <tr key={event.id} className="bg-paper/95">
                    <td className="px-3 py-2 text-ink/70">{new Date(event.timestamp).toLocaleString()}</td>
                    <td className="px-3 py-2 text-ink/80">{event.eventType}</td>
                    <td className="px-3 py-2 text-ink/70">{event.actor}</td>
                    <td className="px-3 py-2 font-mono text-xs text-ink/70">{event.targetId}</td>
                    <td className="px-3 py-2">
                      <Badge tone={toneForSeverity(event.severity)}>{event.severity}</Badge>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-3 py-6 text-sm text-ink/60" colSpan={5}>
                    {status === "loading" ? "Loading audit log..." : "No audit events available."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink/65">{label}</label>
      {children}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-fog/70 p-2">
      <p className="text-xs uppercase tracking-wide text-ink/55">{label}</p>
      <p className="text-sm font-medium text-ink">{value}</p>
    </div>
  );
}

function toneForSeverity(severity: AdminAuditEvent["severity"]): "neutral" | "good" | "warn" | "bad" | "info" {
  switch (severity) {
    case "critical":
      return "bad";
    case "warning":
      return "warn";
    default:
      return "info";
  }
}
