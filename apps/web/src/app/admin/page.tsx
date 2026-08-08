"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Archive,
  BarChart3,
  CheckCircle2,
  Cpu,
  KeyRound,
  Laptop,
  Loader2,
  Shield,
  Trash2,
  UserRound,
} from "lucide-react";

import {
  changeAccountPassword,
  createLocalWorker,
  getAccountSession,
  getActivationReport,
  getGovernedArtifactDownload,
  listAccountSessions,
  listGovernedArtifacts,
  listLlmRuns,
  listLocalWorkers,
  revokeAccountSession,
  revokeLocalWorker,
  updateAccountProfile,
  type AccountSession,
  type AccountSessionRecord,
  type ActivationReport,
  type GovernedArtifactRecord,
  type LlmRunRecord,
  type LocalWorkerRecord,
} from "@/lib/api";

const card = "rounded-xl border border-line bg-paper p-5 sm:p-6";
const input = "focus-ring mt-2 w-full rounded-md border border-line bg-fog px-3 py-2.5 text-sm";
const ACTIVATION_STEPS = [
  ["onboarding_viewed", "Onboarding viewed"],
  ["guided_started", "Guided review started"],
  ["packet_saved", "Decision packet saved"],
  ["review_completed", "Review completed"],
  ["outcome_recorded", "Outcome recorded"],
] as const;

export default function AdminPage() {
  const [profile, setProfile] = useState<AccountSession | null>(null);
  const [sessions, setSessions] = useState<AccountSessionRecord[]>([]);
  const [workers, setWorkers] = useState<LocalWorkerRecord[]>([]);
  const [runs, setRuns] = useState<LlmRunRecord[]>([]);
  const [activation, setActivation] = useState<ActivationReport | null>(null);
  const [artifacts, setArtifacts] = useState<GovernedArtifactRecord[]>([]);
  const [workerToken, setWorkerToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const account = await getAccountSession();
    const sessionRows = await listAccountSessions();
    setProfile(account);
    setSessions(sessionRows.sessions);
    if (["owner", "admin"].includes(account.organization.role)) {
      const [workerRows, runRows, activationRows, artifactRows] = await Promise.all([
        listLocalWorkers(),
        listLlmRuns(),
        getActivationReport(),
        listGovernedArtifacts(),
      ]);
      setWorkers(workerRows.workers);
      setRuns(runRows.runs);
      setActivation(activationRows);
      setArtifacts(artifactRows.artifacts);
    }
  }, []);

  useEffect(() => {
    refresh()
      .catch(() => setError("Account controls could not be loaded."))
      .finally(() => setLoading(false));
  }, [refresh]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await updateAccountProfile({
        displayName: String(data.get("name")),
        professionalRole: String(data.get("role")),
      });
      setMessage("Profile updated.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Profile update failed.");
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await changeAccountPassword(String(data.get("current")), String(data.get("next")));
      form.reset();
      setMessage("Password updated; other sessions were revoked.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Password update failed.");
    }
  }

  async function addWorker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setError("");
    try {
      const created = await createLocalWorker(String(data.get("name")));
      setWorkerToken(created.token);
      form.reset();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Worker creation failed.");
    }
  }

  async function downloadArtifact(artifactId: string) {
    setError("");
    try {
      const result = await getGovernedArtifactDownload(artifactId);
      window.location.assign(result.url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Artifact download failed.");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12 text-sm text-ink/60">
        <Loader2 className="h-5 w-5 animate-spin text-teal" /> Loading account controls…
      </div>
    );
  }

  const canAdminister = Boolean(profile && ["owner", "admin"].includes(profile.organization.role));

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className={`${card} sm:p-7`}>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Administration</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Account security and governed operations</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/60">
          Manage identity, private inference credentials, adoption evidence, and durable artifacts for this organization.
          Model output remains advisory and must pass deterministic verification.
        </p>
      </header>

      {error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}
      {message ? <p className="rounded-md border border-teal/25 bg-teal/5 p-3 text-sm"><CheckCircle2 className="mr-2 inline h-4 w-4 text-teal" />{message}</p> : null}

      {canAdminister ? (
        <section className={card}>
          <div className="flex items-center gap-3">
            <BarChart3 className="h-5 w-5 text-teal" />
            <div>
              <h2 className="font-semibold">Activation evidence</h2>
              <p className="text-xs text-ink/48">Privacy-minimized organization events over the last {activation?.windowDays ?? 30} days.</p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {ACTIVATION_STEPS.map(([key, label]) => {
              const value = activation?.events[key];
              return (
                <div key={key} className="rounded-lg border border-line bg-fog/65 p-4">
                  <p className="text-2xl font-semibold tabular-nums">{value?.count ?? 0}</p>
                  <p className="mt-1 text-xs font-semibold text-ink/65">{label}</p>
                  <p className="mt-2 text-[11px] text-ink/42">{value?.uniqueUsers ?? 0} unique users</p>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs text-ink/45">Counts describe observed workflow use, not returns, efficacy, or customer traction.</p>
        </section>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <section className={card}>
          <div className="flex items-center gap-3"><UserRound className="h-5 w-5 text-teal" /><h2 className="font-semibold">Profile</h2></div>
          <form onSubmit={saveProfile} className="mt-5 space-y-4">
            <label className="block text-xs font-semibold">Name<input name="name" defaultValue={profile?.user.displayName} className={input} /></label>
            <label className="block text-xs font-semibold">Professional role
              <select name="role" defaultValue={profile?.user.professionalRole || "other"} className={input}>
                <option value="analyst">Analyst</option><option value="portfolio_manager">Portfolio manager</option>
                <option value="risk">Risk or compliance</option><option value="cio_founder">CIO or founder</option><option value="other">Other</option>
              </select>
            </label>
            <button className="focus-ring rounded-md bg-teal px-4 py-2.5 text-sm font-bold text-[#071411]">Save profile</button>
          </form>
        </section>

        <section className={card}>
          <div className="flex items-center gap-3"><KeyRound className="h-5 w-5 text-teal" /><h2 className="font-semibold">Change password</h2></div>
          <form onSubmit={changePassword} className="mt-5 space-y-4">
            <label className="block text-xs font-semibold">Current password<input name="current" type="password" autoComplete="current-password" required className={input} /></label>
            <label className="block text-xs font-semibold">New passphrase<input name="next" type="password" autoComplete="new-password" minLength={15} maxLength={256} required className={input} /></label>
            <button className="focus-ring rounded-md border border-line px-4 py-2.5 text-sm font-semibold">Update and revoke other sessions</button>
          </form>
        </section>
      </div>

      <section className={card}>
        <div className="flex items-center gap-3"><Shield className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Active sessions</h2><p className="text-xs text-ink/48">Opaque secrets are never displayed; only bounded metadata is retained.</p></div></div>
        <div className="mt-4 divide-y divide-line">
          {sessions.map((session) => (
            <div key={session.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div><p className="text-sm font-medium">{session.current ? "This session" : "Signed-in session"}</p><p className="mt-1 text-xs text-ink/48">Expires {new Date(session.expiresAt).toLocaleString()} {session.ipPrefix ? `· ${session.ipPrefix}` : ""}</p></div>
              <button onClick={async () => { await revokeAccountSession(session.id); if (session.current) window.location.assign("/"); else await refresh(); }} className="focus-ring rounded-md border border-line px-3 py-2 text-xs font-semibold">Revoke</button>
            </div>
          ))}
        </div>
      </section>

      {canAdminister ? (
        <section className={card}>
          <div className="flex items-center gap-3"><Laptop className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Local Ollama workers</h2><p className="text-xs text-ink/48">Outbound-only organization queue; port 11434 stays on loopback.</p></div></div>
          {workerToken ? <div className="mt-5 rounded-md border border-amber-300/30 bg-amber-300/10 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-amber-200">Copy once</p><code className="mt-2 block break-all text-xs text-ink/72">{workerToken}</code><p className="mt-3 text-xs text-ink/55">Set this as AMBROSIA_WORKER_TOKEN. The database stores only its keyed hash.</p></div> : null}
          <form onSubmit={addWorker} className="mt-5 flex flex-col gap-3 sm:flex-row"><input name="name" required minLength={2} placeholder="Research workstation" className="focus-ring min-w-0 flex-1 rounded-md border border-line bg-fog px-3 py-2.5 text-sm" /><button className="focus-ring rounded-md bg-teal px-4 py-2.5 text-sm font-bold text-[#071411]">Create credential</button></form>
          <div className="mt-4 divide-y divide-line">{workers.map((worker) => <div key={worker.id} className="flex items-center justify-between gap-3 py-3"><div><p className="text-sm font-medium">{worker.name}</p><p className="text-xs text-ink/48">{worker.last_seen_at ? `Last seen ${new Date(worker.last_seen_at).toLocaleString()}` : "Not connected yet"}</p></div><button onClick={async () => { await revokeLocalWorker(worker.id); await refresh(); }} className="focus-ring rounded-md border border-line p-2" aria-label={`Revoke ${worker.name}`}><Trash2 className="h-4 w-4" /></button></div>)}</div>
        </section>
      ) : null}

      {canAdminister ? (
        <section className={card}>
          <div className="flex items-center gap-3"><Archive className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Governed artifacts</h2><p className="text-xs text-ink/48">Tenant-bound, content-hashed records backed by KMS-encrypted object storage in production.</p></div></div>
          {artifacts.length ? <div className="mt-4 divide-y divide-line">{artifacts.slice(0, 20).map((artifact) => <div key={artifact.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="text-sm font-medium capitalize">{artifact.artifact_kind}</p><p className="mt-1 max-w-xl truncate font-mono text-[11px] text-ink/45">sha256:{artifact.content_hash} · {artifact.size_bytes.toLocaleString()} bytes</p></div><div className="flex items-center gap-2"><span className="rounded-full bg-teal/10 px-2 py-1 text-xs font-semibold text-teal">{artifact.storage_status}</span>{artifact.storage_status === "durable" ? <button onClick={() => void downloadArtifact(artifact.id)} className="focus-ring rounded-md border border-line px-3 py-2 text-xs font-semibold">Download</button> : null}</div></div>)}</div> : <p className="mt-5 rounded-md border border-dashed border-line p-5 text-sm text-ink/50">No durable artifact has been generated for this organization yet.</p>}
        </section>
      ) : null}

      <section className={card}>
        <div className="flex items-center gap-3"><Cpu className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Catalogued LLM runs</h2><p className="text-xs text-ink/48">Model digest, schema, verification state, and content hash make each displayed result accountable.</p></div></div>
        {runs.length ? <div className="mt-4 divide-y divide-line">{runs.slice(0, 20).map((run) => <div key={run.id} className="grid gap-2 py-3 text-xs sm:grid-cols-[1fr_1fr_auto]"><div><p className="font-semibold text-ink">{run.model_name}</p><p className="mt-1 truncate text-ink/45">{run.model_digest || "digest unavailable"}</p></div><div><p className="text-ink/65">Schema {run.output_schema_version}</p><p className="mt-1 truncate text-ink/45">{run.content_hash}</p></div><span className="h-fit rounded-full bg-teal/10 px-2 py-1 font-semibold text-teal">{run.verification_status.replaceAll("_", " ")}</span></div>)}</div> : <p className="mt-5 rounded-md border border-dashed border-line p-5 text-sm text-ink/50">No local-model run has been returned yet. Create a worker credential, run the packaged worker, and enqueue a disconfirmation job from a packet.</p>}
      </section>
    </div>
  );
}
