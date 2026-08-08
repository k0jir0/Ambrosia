"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, MailPlus, ShieldCheck, Trash2, Users } from "lucide-react";

import {
  getAccountSession,
  getTeam,
  inviteTeamMember,
  revokeTeamInvitation,
  updateTeamMember,
  type AccountSession,
  type InvitationRecord,
  type TeamMemberRecord,
} from "@/lib/api";

const card = "rounded-xl border border-line bg-paper p-5";

export default function TeamPage() {
  const [profile, setProfile] = useState<AccountSession | null>(null);
  const [members, setMembers] = useState<TeamMemberRecord[]>([]);
  const [invitations, setInvitations] = useState<InvitationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const [account, team] = await Promise.all([getAccountSession(), getTeam()]);
    setProfile(account);
    setMembers(team.members);
    setInvitations(team.invitations);
  }, []);

  useEffect(() => {
    refresh()
      .catch(() => setError("Team membership could not be loaded."))
      .finally(() => setLoading(false));
  }, [refresh]);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setMessage("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const result = await inviteTeamMember(String(data.get("email")), String(data.get("role")));
      setMessage(
        result.developmentInvitationToken
          ? `Development invite: ${window.location.origin}/accept-invite?token=${encodeURIComponent(result.developmentInvitationToken)}`
          : result.deliveryStatus === "retry_required"
            ? `Invitation saved, but email delivery failed for ${result.email}. Revoke it and retry after checking SES.`
            : `Invitation sent to ${result.email}.`,
      );
      form.reset();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation failed.");
    } finally {
      setPending(false);
    }
  }

  async function revoke(invitation: InvitationRecord) {
    setError("");
    try {
      await revokeTeamInvitation(invitation.id);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to revoke invitation.");
    }
  }

  async function changeMember(
    member: TeamMemberRecord,
    role: "viewer" | "analyst" | "reviewer" | "admin",
    status: "active" | "suspended",
  ) {
    setError("");
    try {
      await updateTeamMember(member.id, role, status);
      setMessage(status === "suspended" ? `${member.email} was suspended and signed out.` : `${member.email} was updated.`);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update member.");
    }
  }

  const canManage = profile?.organization.role === "owner" || profile?.organization.role === "admin";
  const activeCount = members.filter((member) => member.status === "active").length;
  if (loading) {
    return <div className="flex items-center gap-3 py-12 text-sm text-ink/60"><Loader2 className="h-5 w-5 animate-spin text-teal" /> Loading private team…</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className={`${card} sm:p-7`}>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Team</p>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">{profile?.organization.name}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/60">Membership and invitation authority comes from the database. Every person shares this organization’s governed workspace without sharing credentials.</p>
          </div>
          <span className="rounded-full border border-teal/25 bg-teal/5 px-3 py-1.5 text-xs font-semibold text-teal">{activeCount} active member{activeCount === 1 ? "" : "s"}</span>
        </div>
      </header>

      {error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}
      {message ? <p className="break-all rounded-md border border-teal/25 bg-teal/5 p-3 text-sm text-ink/72"><CheckCircle2 className="mr-2 inline h-4 w-4 text-teal" />{message}</p> : null}

      <div className="grid gap-5 lg:grid-cols-[1.4fr_0.8fr]">
        <section className={card}>
          <div className="flex items-center gap-3"><Users className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Membership</h2><p className="text-xs text-ink/48">Server-derived roles; browser role headers are ignored.</p></div></div>
          <div className="mt-5 divide-y divide-line">
            {members.map((member) => {
              const editable = canManage && member.role !== "owner" && member.id !== profile?.user.id;
              return (
                <div key={member.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div><p className="text-sm font-semibold">{member.display_name || member.email}</p><p className="mt-1 text-xs text-ink/48">{member.email} · {member.professional_role.replaceAll("_", " ")}</p></div>
                  {editable ? (
                    <div className="flex items-center gap-2">
                      <select
                        aria-label={`Role for ${member.email}`}
                        value={member.role}
                        onChange={(event) => void changeMember(member, event.target.value as "viewer" | "analyst" | "reviewer" | "admin", member.status as "active" | "suspended")}
                        className="focus-ring rounded-md border border-line bg-fog px-2 py-1.5 text-xs capitalize"
                      >
                        <option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => void changeMember(member, member.role as "viewer" | "analyst" | "reviewer" | "admin", member.status === "active" ? "suspended" : "active")}
                        className="focus-ring rounded-md border border-line px-2.5 py-1.5 text-xs font-semibold text-ink/65"
                      >{member.status === "active" ? "Suspend" : "Reactivate"}</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-teal" /><span className="rounded-full bg-teal/10 px-2.5 py-1 text-xs font-semibold capitalize text-teal">{member.role}</span></div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <section className={card}>
          <div className="flex items-center gap-3"><MailPlus className="h-5 w-5 text-teal" /><div><h2 className="font-semibold">Invite a collaborator</h2><p className="text-xs text-ink/48">Single-use link, seven-day expiry.</p></div></div>
          {canManage ? (
            <form onSubmit={invite} className="mt-5 space-y-4">
              <label className="block text-xs font-semibold">Work email<input name="email" type="email" required className="focus-ring mt-2 w-full rounded-md border border-line bg-fog px-3 py-2.5 text-sm" /></label>
              <label className="block text-xs font-semibold">Access role<select name="role" defaultValue="analyst" className="focus-ring mt-2 w-full rounded-md border border-line bg-fog px-3 py-2.5 text-sm"><option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select></label>
              <button disabled={pending} className="focus-ring flex w-full items-center justify-center gap-2 rounded-md bg-teal px-4 py-3 text-sm font-bold text-[#071411] disabled:opacity-50">{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <MailPlus className="h-4 w-4" />} Send invitation</button>
            </form>
          ) : <p className="mt-5 rounded-md border border-line bg-fog p-3 text-sm text-ink/55">Only owners and administrators can invite members.</p>}
        </section>
      </div>

      <section className={card}>
        <h2 className="font-semibold">Pending invitations</h2>
        {invitations.length ? (
          <div className="mt-4 divide-y divide-line">
            {invitations.map((invitation) => (
              <div key={invitation.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div><p className="text-sm font-medium">{invitation.email}</p><p className="mt-1 text-xs capitalize text-ink/48">{invitation.role} · awaiting acceptance</p></div>
                {canManage ? <button onClick={() => revoke(invitation)} className="focus-ring rounded-md border border-line p-2 text-ink/55 hover:text-rose-200" aria-label={`Revoke invitation for ${invitation.email}`}><Trash2 className="h-4 w-4" /></button> : null}
              </div>
            ))}
          </div>
        ) : <p className="mt-4 text-sm text-ink/48">No pending invitations.</p>}
      </section>
    </div>
  );
}
