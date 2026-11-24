"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { Button, Input } from "@/components/ui/primitives";
import { ApiClientError, apiFetch } from "@/lib/api-client";

function ResetPasswordInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!token) {
      setErrorMsg("Missing password reset token in URL.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await apiFetch("/api/auth/password/reset/", {
        method: "POST",
        json: { token, new_password: newPassword },
      });
      setDone(true);
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : "Failed to reset password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md rounded-lg border border-champagne/30 bg-espresso p-7 sm:p-9">
      <OrganizerWordmark />
      <h1 className="font-display mt-4 text-3xl tracking-wide text-ivory uppercase">
        CHOOSE NEW PASSWORD
      </h1>

      {done ? (
        <div className="mt-6 rounded border border-emerald-500/40 bg-emerald-950/60 p-4 text-sm text-ivory">
          <p>Your password has been updated. You can now sign in with your new password.</p>
          <div className="mt-4">
            <Link href="/admin/login">
              <Button size="sm">Go to Sign In</Button>
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {errorMsg && (
            <p role="alert" className="text-xs font-medium text-status-err">
              {errorMsg}
            </p>
          )}
          <div>
            <label htmlFor="new-pw" className="block text-sm font-semibold text-champagne">
              New password (minimum 10 characters)
            </label>
            <Input
              id="new-pw"
              type="password"
              required
              minLength={10}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="confirm-pw" className="block text-sm font-semibold text-champagne">
              Confirm new password
            </label>
            <Input
              id="confirm-pw"
              type="password"
              required
              minLength={10}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <Button type="submit" loading={loading} className="w-full">
            Save New Password
          </Button>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <main
      id="main-content"
      className="amber-stage-glow film-grain flex min-h-dvh items-center justify-center px-5 py-12"
    >
      <Suspense fallback={<div className="text-sm text-champagne">Loading...</div>}>
        <ResetPasswordInner />
      </Suspense>
    </main>
  );
}
