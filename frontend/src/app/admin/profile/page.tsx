"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button, Input } from "@/components/ui/primitives";
import { AdminGuardShell, useAdminUser } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch } from "@/lib/api-client";

function ProfileInner() {
  const user = useAdminUser();
  const queryClient = useQueryClient();

  const [displayName, setDisplayName] = useState(user.display_name);
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPw, setSavingPw] = useState(false);

  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const handleSaveName = async (e: FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setFeedback(null);
    try {
      await apiFetch("/api/auth/me/", {
        method: "PATCH",
        json: { display_name: displayName.trim() },
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-me"] });
      setFeedback({ type: "ok", text: "Updated profile display name." });
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to update display name.",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    if (newPassword !== confirmPassword) {
      setFeedback({ type: "err", text: "New passwords do not match." });
      return;
    }
    setSavingPw(true);
    try {
      await apiFetch("/api/auth/password/change/", {
        method: "POST",
        json: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setFeedback({ type: "ok", text: "Password changed." });
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to change password.",
      });
    } finally {
      setSavingPw(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div className="border-b border-champagne/15 pb-5">
        <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">MY PROFILE</h1>
        <p className="mt-1 text-sm text-ivory-muted">
          Signed in as <strong className="text-ivory">{user.email}</strong> ({user.role}).
        </p>
      </div>

      {feedback && (
        <div
          role="status"
          className={`rounded border p-4 text-sm ${
            feedback.type === "ok"
              ? "border-emerald-500/40 bg-emerald-950/60 text-emerald-100"
              : "border-status-err/50 bg-red-950/60 text-red-100"
          }`}
        >
          {feedback.text}
        </div>
      )}

      <form onSubmit={handleSaveName} className="space-y-4 rounded-lg border border-champagne/20 bg-espresso p-6">
        <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">DISPLAY NAME</h2>
        <div>
          <label htmlFor="prof-name" className="block text-sm font-semibold text-champagne">
            Name shown on generated invitations &amp; check-ins
          </label>
          <Input
            id="prof-name"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <Button type="submit" loading={savingProfile}>
          Save Display Name
        </Button>
      </form>

      <form onSubmit={handleChangePassword} className="space-y-4 rounded-lg border border-champagne/20 bg-espresso p-6">
        <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
          CHANGE PASSWORD
        </h2>
        <div>
          <label htmlFor="cur-pw" className="block text-sm font-semibold text-champagne">
            Current password
          </label>
          <Input
            id="cur-pw"
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <div>
          <label htmlFor="next-pw" className="block text-sm font-semibold text-champagne">
            New password (minimum 10 characters)
          </label>
          <Input
            id="next-pw"
            type="password"
            required
            minLength={10}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <div>
          <label htmlFor="next-pw2" className="block text-sm font-semibold text-champagne">
            Confirm new password
          </label>
          <Input
            id="next-pw2"
            type="password"
            required
            minLength={10}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <Button type="submit" variant="secondary" loading={savingPw}>
          Update Password
        </Button>
      </form>
    </div>
  );
}

export default function AdminProfilePage() {
  return (
    <AdminGuardShell>
      <ProfileInner />
    </AdminGuardShell>
  );
}
