"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Lock } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { Button, Input } from "@/components/ui/primitives";
import { ApiClientError, apiFetch, ensureCsrfToken, sanitizeAdminNextPath } from "@/lib/api-client";
import type { AdminUser } from "@/types/api";

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    void ensureCsrfToken();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);
    try {
      const user = await apiFetch<AdminUser>("/api/auth/login/", {
        method: "POST",
        json: { email: email.trim(), password },
      });
      queryClient.setQueryData(["admin-me"], user);
      const safeDestination = sanitizeAdminNextPath(searchParams.get("next"));
      router.replace(safeDestination);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Unable to sign in right now. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md rounded-lg border border-champagne/30 bg-espresso p-7 shadow-2xl sm:p-9">
      <OrganizerWordmark />
      <h1 className="font-display mt-4 text-4xl tracking-wide text-ivory uppercase">
        ADMINISTRATOR SIGN IN
      </h1>
      <p className="mt-1.5 text-sm text-ivory-muted">
        Authorized DRIP &amp; RHYTHM hosts and entrance staff only.
      </p>

      {errorMsg && (
        <div
          role="alert"
          className="mt-5 flex items-start gap-2.5 rounded border border-status-err/50 bg-red-950/60 p-3.5 text-xs text-red-100"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-status-err" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="admin-email" className="block text-sm font-semibold text-champagne">
            Email address
          </label>
          <Input
            id="admin-email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="host@example.com"
            className="mt-1.5"
          />
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label htmlFor="admin-password" className="block text-sm font-semibold text-champagne">
              Password
            </label>
            <Link
              href="/admin/forgot-password"
              className="text-xs font-medium text-amber hover:text-ivory"
            >
              Forgot password?
            </Link>
          </div>
          <Input
            id="admin-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5"
          />
        </div>

        <Button type="submit" size="lg" loading={loading} className="w-full">
          <Lock className="h-4 w-4" aria-hidden="true" />
          Sign in to Dashboard
        </Button>
      </form>

      <div className="mt-6 border-t border-champagne/15 pt-4 text-center text-xs text-ivory-muted">
        <Link href="/" className="text-champagne hover:text-ivory">
          Return to Public Event Page
        </Link>
      </div>
    </div>
  );
}

export default function AdminLoginPage() {
  return (
    <main
      id="main-content"
      className="amber-stage-glow film-grain flex min-h-dvh items-center justify-center px-5 py-12"
    >
      <Suspense fallback={<div className="text-sm text-champagne">Loading sign-in...</div>}>
        <LoginFormInner />
      </Suspense>
    </main>
  );
}
