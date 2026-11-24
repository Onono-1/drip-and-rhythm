"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { Button, Input } from "@/components/ui/primitives";
import { ApiClientError, apiFetch } from "@/lib/api-client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submittedMsg, setSubmittedMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const resp = await apiFetch<{ message: string }>("/api/auth/password/forgot/", {
        method: "POST",
        json: { email: email.trim() },
      });
      setSubmittedMsg(resp.message);
    } catch (err) {
      setErrorMsg(err instanceof ApiClientError ? err.message : "Unable to request password reset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      id="main-content"
      className="amber-stage-glow film-grain flex min-h-dvh items-center justify-center px-5 py-12"
    >
      <div className="w-full max-w-md rounded-lg border border-champagne/30 bg-espresso p-7 sm:p-9">
        <OrganizerWordmark />
        <h1 className="font-display mt-4 text-3xl tracking-wide text-ivory uppercase">
          RESET ADMIN PASSWORD
        </h1>
        <p className="mt-1.5 text-sm text-ivory-muted">
          Enter your administrator email address to receive a one-hour password reset link.
        </p>

        {submittedMsg ? (
          <div className="mt-6 rounded border border-amber/40 bg-chocolate/70 p-4 text-sm text-ivory">
            <p>{submittedMsg}</p>
            <div className="mt-4">
              <Link href="/admin/login">
                <Button variant="outline" size="sm">
                  Return to Sign In
                </Button>
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
              <label htmlFor="forgot-email" className="block text-sm font-semibold text-champagne">
                Administrator email
              </label>
              <Input
                id="forgot-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="host@example.com"
                className="mt-1.5"
              />
            </div>
            <Button type="submit" loading={loading} className="w-full">
              Send Reset Instructions
            </Button>
            <div className="text-center text-xs">
              <Link href="/admin/login" className="text-champagne hover:text-ivory">
                Back to Sign In
              </Link>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
