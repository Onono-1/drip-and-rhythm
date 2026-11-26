"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button, Input, ModalDialog, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch, formatDateTime } from "@/lib/api-client";
import type { AdminRole, AdminUser, PaginatedResponse } from "@/types/api";

function UsersInner() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminUser | null>(null);
  const [statusTarget, setStatusTarget] = useState<AdminUser | null>(null);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<AdminRole>("ADMIN");
  const [limitStr, setLimitStr] = useState("50");
  const [password, setPassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => apiFetch<PaginatedResponse<AdminUser>>("/api/users/"),
  });

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    try {
      await apiFetch("/api/users/", {
        method: "POST",
        json: {
          email: email.trim(),
          display_name: displayName.trim(),
          role,
          invitation_limit: limitStr.trim() === "" ? null : Number(limitStr),
          password,
          is_active: true,
        },
      });
      setCreateOpen(false);
      setEmail("");
      setDisplayName("");
      setPassword("");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : "Could not create administrator.");
    } finally {
      setBusy(false);
    }
  };

  const handleUpdate = async (e: FormEvent) => {
    e.preventDefault();
    if (!editTarget) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const payload: Record<string, unknown> = {
        display_name: displayName.trim(),
        role,
        invitation_limit: limitStr.trim() === "" ? null : Number(limitStr),
      };
      if (password.trim()) {
        payload.password = password;
      }
      await apiFetch(`/api/users/${editTarget.id}/`, {
        method: "PATCH",
        json: payload,
      });
      setEditTarget(null);
      setPassword("");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : "Could not update administrator.");
    } finally {
      setBusy(false);
    }
  };

  const confirmToggleStatus = async () => {
    if (!statusTarget) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const action = statusTarget.is_active ? "pause" : "resume";
      await apiFetch(`/api/users/${statusTarget.id}/${action}/`, { method: "POST", json: {} });
      setStatusTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 border-b border-champagne/15 pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">
            ADMINISTRATORS
          </h1>
          <p className="mt-1 text-sm text-ivory-muted">
            Manage host accounts, roles, per-administrator invitation limits, and active status.
          </p>
        </div>

        <Button
          onClick={() => {
            setErrorMsg(null);
            setEmail("");
            setDisplayName("");
            setRole("ADMIN");
            setLimitStr("50");
            setPassword("");
            setCreateOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          New Administrator
        </Button>
      </div>

      {errorMsg && (
        <div role="alert" className="rounded border border-status-err/50 bg-red-950/60 p-4 text-xs text-red-100">
          {errorMsg}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-champagne/20 bg-espresso">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-champagne/20 bg-midnight/60 text-xs font-semibold text-champagne">
              <th className="px-4 py-3.5">Administrator</th>
              <th className="px-4 py-3.5">Role</th>
              <th className="px-4 py-3.5">Status</th>
              <th className="px-4 py-3.5">Quota Usage</th>
              <th className="px-4 py-3.5">Last Sign-In</th>
              <th className="px-4 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-champagne/10">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-ivory-muted">
                  Loading administrators...
                </td>
              </tr>
            ) : (
              data?.results.map((adm) => (
                <tr key={adm.id}>
                  <td className="px-4 py-3.5">
                    <p className="font-semibold text-ivory">{adm.display_name}</p>
                    <p className="text-xs text-ivory-muted">{adm.email}</p>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge tone={adm.role === "SUPER_ADMIN" ? "gold" : "neutral"}>
                      {adm.role === "SUPER_ADMIN" ? "Super Admin" : "Admin"}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge tone={adm.is_active ? "success" : "warning"}>
                      {adm.is_active ? "Active" : "Paused"}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory tabular-nums">
                    {adm.invitations_generated_count} / {adm.invitation_limit ?? "Unlimited"}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">
                    {formatDateTime(adm.last_login)}
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <div className="inline-flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setErrorMsg(null);
                          setDisplayName(adm.display_name);
                          setRole(adm.role);
                          setLimitStr(adm.invitation_limit !== null ? String(adm.invitation_limit) : "");
                          setPassword("");
                          setEditTarget(adm);
                        }}
                      >
                        Edit
                      </Button>
                      {adm.role !== "SUPER_ADMIN" && (
                        <Button
                          variant={adm.is_active ? "danger" : "secondary"}
                          size="sm"
                          onClick={() => {
                            setErrorMsg(null);
                            setStatusTarget(adm);
                          }}
                        >
                          {adm.is_active ? (
                            <>
                              <Pause className="h-3.5 w-3.5" aria-hidden="true" />
                              Pause
                            </>
                          ) : (
                            <>
                              <Play className="h-3.5 w-3.5" aria-hidden="true" />
                              Resume
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Admin Dialog */}
      <ModalDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="CREATE ADMINISTRATOR"
        description="Provision a new DRIP & RHYTHM host or entrance check-in administrator."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="new-adm-name" className="block text-sm font-semibold text-champagne">
              Display name
            </label>
            <Input
              id="new-adm-name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="new-adm-email" className="block text-sm font-semibold text-champagne">
              Email address
            </label>
            <Input
              id="new-adm-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="new-adm-role" className="block text-sm font-semibold text-champagne">
                Role
              </label>
              <select
                id="new-adm-role"
                value={role}
                onChange={(e) => setRole(e.target.value as AdminRole)}
                className="mt-1.5 min-h-12 w-full rounded-md border border-champagne/25 bg-midnight px-3 text-sm text-ivory"
              >
                <option value="ADMIN">Ordinary Admin</option>
                <option value="SUPER_ADMIN">Super Admin</option>
              </select>
            </div>
            <div>
              <label htmlFor="new-adm-limit" className="block text-sm font-semibold text-champagne">
                Link Limit (blank = unlimited)
              </label>
              <Input
                id="new-adm-limit"
                type="number"
                min={0}
                value={limitStr}
                onChange={(e) => setLimitStr(e.target.value)}
                className="mt-1.5"
              />
            </div>
          </div>
          <div>
            <label htmlFor="new-adm-pw" className="block text-sm font-semibold text-champagne">
              Initial password (min 10 chars)
            </label>
            <Input
              id="new-adm-pw"
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={busy}>
              Create Account
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Pause / Resume Confirmation Dialog */}
      <ModalDialog
        open={Boolean(statusTarget)}
        onOpenChange={(open) => !open && setStatusTarget(null)}
        title={statusTarget?.is_active ? "PAUSE ADMINISTRATOR ACCOUNT" : "RESUME ADMINISTRATOR ACCOUNT"}
        description={statusTarget?.email}
      >
        {statusTarget && (
          <div className="space-y-4">
            <p className="text-sm leading-relaxed text-ivory-muted">
              {statusTarget.is_active ? (
                <>
                  Pausing <strong className="text-ivory">{statusTarget.display_name}</strong> immediately ends their active sessions and blocks sign-in until a Super Admin restores access. All previously generated single, bulk, and master invitation links will continue working normally.
                </>
              ) : (
                <>
                  Resuming <strong className="text-ivory">{statusTarget.display_name}</strong> restores their administrator sign-in and host operations access.
                </>
              )}
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => setStatusTarget(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant={statusTarget.is_active ? "danger" : "primary"}
                loading={busy}
                onClick={() => void confirmToggleStatus()}
              >
                {statusTarget.is_active ? "Confirm Pause" : "Confirm Resume"}
              </Button>
            </div>
          </div>
        )}
      </ModalDialog>

      {/* Edit Admin Dialog */}
      <ModalDialog
        open={Boolean(editTarget)}
        onOpenChange={(open) => !open && setEditTarget(null)}
        title="EDIT ADMINISTRATOR"
        description={editTarget?.email}
      >
        <form onSubmit={handleUpdate} className="space-y-4">
          <div>
            <label htmlFor="edit-adm-name" className="block text-sm font-semibold text-champagne">
              Display name
            </label>
            <Input
              id="edit-adm-name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="edit-adm-role" className="block text-sm font-semibold text-champagne">
                Role
              </label>
              <select
                id="edit-adm-role"
                value={role}
                onChange={(e) => setRole(e.target.value as AdminRole)}
                className="mt-1.5 min-h-12 w-full rounded-md border border-champagne/25 bg-midnight px-3 text-sm text-ivory"
              >
                <option value="ADMIN">Ordinary Admin</option>
                <option value="SUPER_ADMIN">Super Admin</option>
              </select>
            </div>
            <div>
              <label htmlFor="edit-adm-limit" className="block text-sm font-semibold text-champagne">
                Link Limit (blank = unlimited)
              </label>
              <Input
                id="edit-adm-limit"
                type="number"
                min={0}
                value={limitStr}
                onChange={(e) => setLimitStr(e.target.value)}
                className="mt-1.5"
              />
            </div>
          </div>
          <div>
            <label htmlFor="edit-adm-pw" className="block text-sm font-semibold text-champagne">
              Reset password (leave blank to keep existing)
            </label>
            <Input
              id="edit-adm-pw"
              type="password"
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={busy}>
              Save Changes
            </Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <AdminGuardShell requireSuperAdmin>
      <UsersInner />
    </AdminGuardShell>
  );
}
