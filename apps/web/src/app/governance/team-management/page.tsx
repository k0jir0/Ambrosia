"use client";

import React, { useState, useEffect } from "react";
import { Badge, Panel, SectionTitle } from "@/components/ui";
import { getApiBaseUrl } from "@/lib/api";

interface TeamMember {
  user_id: string;
  name: string;
  role: string;
  active: boolean;
}

export default function TeamManagementPage() {
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [status, setStatus] = useState<string | null>(null);
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState("analyst");

  // Fetch team members
  useEffect(() => {
    const fetchTeamMembers = async () => {
      try {
        const apiBaseUrl = getApiBaseUrl();
        if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
        const response = await fetch(
          `${apiBaseUrl}/governance/team/members`,
          {
            headers: {
              "X-User-Role": "admin",
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch team: ${response.statusText}`);
        }

        const data = await response.json();
        setTeamMembers(data.team || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchTeamMembers();
  }, []);

  // Invite new team member
  const handleInvite = async () => {
    if (!inviteEmail) {
      setError("Please enter an email address");
      return;
    }

    try {
      setError(null);
      setStatus(null);
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      const response = await fetch(
        `${apiBaseUrl}/governance/team/invite`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Role": "admin",
          },
          body: JSON.stringify({
            email: inviteEmail,
            role: inviteRole,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Invite failed: ${response.statusText}`);
      }

      setTeamMembers([
        ...teamMembers,
        {
          user_id: `usr-${Date.now()}`,
          name: inviteEmail,
          role: inviteRole,
          active: false,
        },
      ]);
      setInviteEmail("");
      setShowInviteForm(false);
      setStatus(`Invitation sent to ${inviteEmail}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const startEdit = (member: TeamMember) => {
    setEditingMemberId(member.user_id);
    setEditingRole(member.role);
    setError(null);
    setStatus(null);
  };

  const saveMemberRole = async (member: TeamMember) => {
    try {
      setError(null);
      setStatus(null);
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      const response = await fetch(`${apiBaseUrl}/governance/team/${member.user_id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-User-Role": "admin",
        },
        body: JSON.stringify({ role: editingRole }),
      });

      if (!response.ok) {
        throw new Error(`Update failed: ${response.statusText}`);
      }

      setTeamMembers((current) => current.map((item) => item.user_id === member.user_id ? { ...item, role: editingRole } : item));
      setEditingMemberId(null);
      setStatus(`${member.name} updated to ${editingRole}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const removeMember = async (member: TeamMember) => {
    try {
      setError(null);
      setStatus(null);
      const apiBaseUrl = getApiBaseUrl();
      if (!apiBaseUrl) throw new Error("Ambrosia API URL is not configured");
      const response = await fetch(`${apiBaseUrl}/governance/team/${member.user_id}`, {
        method: "DELETE",
        headers: {
          "X-User-Role": "admin",
        },
      });

      if (!response.ok) {
        throw new Error(`Remove failed: ${response.statusText}`);
      }

      setTeamMembers((current) => current.filter((item) => item.user_id !== member.user_id));
      setStatus(`${member.name} removed from the team.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const getRoleColor = (role: string): "good" | "neutral" | "warn" | "bad" | "info" => {
    const colors: Record<string, "good" | "neutral" | "warn" | "bad" | "info"> = {
      owner: "bad",
      admin: "warn",
      reviewer: "info",
      analyst: "good",
      viewer: "neutral",
    };
    return colors[role] || "neutral";
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-fog p-8 flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted">Loading team members...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-fog p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex justify-between items-start">
          <Panel className="flex-1">
            <SectionTitle eyebrow="Phase D" title="Team Management" />
            <p className="text-sm text-muted mt-2">
              Manage team members and access permissions
            </p>
          </Panel>
          <button
            onClick={() => setShowInviteForm(!showInviteForm)}
            className="ml-4 px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90"
          >
            {showInviteForm ? "Cancel" : "Invite Member"}
          </button>
        </div>

        {/* Invite Form */}
        {showInviteForm && (
          <Panel className="mb-8 border border-teal/30 bg-teal/5">
            <SectionTitle title="Invite Team Member" />
            <div className="space-y-4 mt-4">
              <div>
                <label className="text-sm font-semibold text-ink block mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="user@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-4 py-2 border border-line rounded font-mono text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-ink block mb-2">
                  Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-4 py-2 border border-line rounded text-sm"
                >
                  <option value="viewer">Viewer (read-only)</option>
                  <option value="analyst">Analyst (create theses)</option>
                  <option value="reviewer">Reviewer (approve trades)</option>
                  <option value="admin">Admin (full access)</option>
                </select>
              </div>
              <button
                onClick={handleInvite}
                className="w-full px-4 py-2 bg-teal text-white rounded font-semibold hover:bg-teal/90"
              >
                Send Invitation
              </button>
            </div>
          </Panel>
        )}

        {/* Error Alert */}
        {error && (
          <Panel className="mb-8 border border-coral/30 bg-coral/10">
            <p className="text-coral font-semibold">Error</p>
            <p className="text-sm text-coral">{error}</p>
          </Panel>
        )}

        {status && (
          <Panel className="mb-8 border border-teal/30 bg-teal/5">
            <p className="text-teal font-semibold">{status}</p>
          </Panel>
        )}

        {/* Team Members Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {teamMembers.map((member) => (
            <div key={member.user_id} data-testid={`team-member-${member.user_id}`}>
              <Panel className="border border-line">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-base font-bold text-ink">{member.name}</h3>
                    <p className="text-xs text-muted font-mono">{member.user_id}</p>
                  </div>
                  <Badge tone={getRoleColor(member.role)}>
                    {member.role}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mb-4">
                  {member.active ? (
                    <>
                      <span className="h-2 w-2 rounded-full bg-teal" aria-hidden="true" />
                      <span className="text-sm text-muted">Active</span>
                    </>
                  ) : (
                    <>
                      <span className="h-2 w-2 rounded-full bg-line" aria-hidden="true" />
                      <span className="text-sm text-muted">Pending</span>
                    </>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => startEdit(member)} className="px-3 py-2 border border-line rounded text-sm font-semibold hover:bg-fog">
                    Edit
                  </button>
                  <button onClick={() => void removeMember(member)} className="px-3 py-2 border border-coral/30 text-coral rounded text-sm font-semibold hover:bg-coral/5">
                    Remove
                  </button>
                </div>
                {editingMemberId === member.user_id && (
                  <div className="mt-3 rounded border border-line bg-fog/70 p-3">
                    <label className="text-xs font-semibold uppercase text-muted">
                      Role
                      <select
                        value={editingRole}
                        onChange={(e) => setEditingRole(e.target.value)}
                        className="mt-2 w-full px-3 py-2 border border-line rounded text-sm normal-case text-ink"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="analyst">Analyst</option>
                        <option value="reviewer">Reviewer</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button onClick={() => void saveMemberRole(member)} className="px-3 py-2 bg-teal text-white rounded text-sm font-semibold hover:bg-teal/90">
                        Save
                      </button>
                      <button onClick={() => setEditingMemberId(null)} className="px-3 py-2 border border-line rounded text-sm font-semibold hover:bg-fog">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </Panel>
            </div>
          ))}
        </div>

        {/* Summary Card */}
        <Panel className="border border-line">
          <SectionTitle title="Team Summary" />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-ink">{teamMembers.length}</p>
              <p className="text-xs text-muted mt-1">Total Members</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-teal">
                {teamMembers.filter((m) => m.active).length}
              </p>
              <p className="text-xs text-muted mt-1">Active</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-coral">
                {teamMembers.filter((m) => m.role === "admin").length}
              </p>
              <p className="text-xs text-muted mt-1">Admins</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-violet">
                {teamMembers.filter((m) => m.role === "reviewer").length}
              </p>
              <p className="text-xs text-muted mt-1">Reviewers</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-teal">
                {teamMembers.filter((m) => m.role === "analyst").length}
              </p>
              <p className="text-xs text-muted mt-1">Analysts</p>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
