"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Layers, Plus, QrCode, RefreshCw, Ticket } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch } from "@/lib/api-client";
import type { DashboardStats, InvitationDetail } from "@/types/api";

function DashboardContent() {
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [quickInvite, setQuickInvite] = useState<InvitationDetail | null>(null);
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [retryingEmails, setRetryingEmails] = useState(false);
  const [retrySummary, setRetrySummary] = useState<string | null>(null);

  const { data: stats, isLoading } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => apiFetch<DashboardStats>("/api/dashboard/"),
  });

  const handleQuickGenerate = async () => {
    setGenerating(true);
    setActionError(null);
    try {
      const created = await apiFetch<InvitationDetail>("/api/invitations/", {
        method: "POST",
        json: {},
      });
      setQuickInvite(created);
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    } catch (err) {
      setActionError(err instanceof ApiClientError ? err.message : "Could not generate link.");
    } finally {
      setGenerating(false);
    }
  };

  const copyQuickUrl = async (url: string) => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const handleRetryEmails = async () => {
    setRetryingEmails(true);
    setActionError(null);
    setRetrySummary(null);
    try {
      const res = await apiFetch<{
        processed: number;
        sent: number;
        failed: number;
        cancelled: number;
        remaining_pending: number;
      }>("/api/emails/process-pending/", {
        method: "POST",
        json: { include_failed: true, max_jobs: 10 },
      });
      setRetrySummary(
        res.processed === 0
          ? "No pending or failed email jobs to retry."
          : `Processed ${res.processed} job(s): ${res.sent} sent, ${res.failed} failed${res.remaining_pending > 0 ? `, ${res.remaining_pending} remaining` : ""}.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    } catch (err) {
      setActionError(err instanceof ApiClientError ? err.message : "Could not retry pending emails.");
    } finally {
      setRetryingEmails(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header + Quick Actions */}
      <div className="flex flex-col justify-between gap-4 border-b border-champagne/15 pb-6 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">
            EVENT OVERVIEW
          </h1>
          <p className="mt-1 text-sm text-ivory-muted">
            Live PostgreSQL invitation, email delivery, and entrance check-in metrics.
          </p>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <Button onClick={() => void handleQuickGenerate()} loading={generating}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Generate Invitation
          </Button>
          <Link href="/admin/invitations?bulk=1">
            <Button variant="secondary">
              <Layers className="h-4 w-4" aria-hidden="true" />
              Bulk Generate
            </Button>
          </Link>
          <Link href="/admin/scanner">
            <Button variant="outline">
              <QrCode className="h-4 w-4" aria-hidden="true" />
              Open QR Scanner
            </Button>
          </Link>
        </div>
      </div>

      {actionError && (
        <div role="alert" className="rounded border border-status-err/50 bg-red-950/60 p-4 text-sm text-red-100">
          {actionError}
        </div>
      )}

      {quickInvite?.claim_url && (
        <div className="rounded-lg border border-amber/50 bg-chocolate/70 p-5">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-amber">
                New Single-Use Link Ready · {quickInvite.reference}
              </p>
              <p className="mt-1 truncate font-mono text-sm text-ivory">{quickInvite.claim_url}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button size="sm" onClick={() => void copyQuickUrl(quickInvite.claim_url!)}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied" : "Copy Link"}
              </Button>
              <a
                href={`https://wa.me/?text=${encodeURIComponent(
                  `You're invited to DRIP & RHYTHM (5 Dec 2026). Secure your exclusive pass here: ${quickInvite.claim_url}`,
                )}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline" size="sm">
                  WhatsApp Share
                </Button>
              </a>
            </div>
          </div>
        </div>
      )}

      {isLoading || !stats ? (
        <p className="text-sm text-ivory-muted">Loading live metrics...</p>
      ) : (
        <>
          {/* Operational Status Flags */}
          <div className="flex flex-wrap gap-3">
            <StatusBadge tone={stats.event_flags.claiming_enabled ? "success" : "danger"}>
              Claiming: {stats.event_flags.claiming_enabled ? "Open" : "Paused"}
            </StatusBadge>
            <StatusBadge tone={stats.event_flags.admission_enabled ? "success" : "danger"}>
              Entrance Admission: {stats.event_flags.admission_enabled ? "Enabled" : "Disabled"}
            </StatusBadge>
            <StatusBadge tone={stats.event_flags.public_sharing_enabled ? "gold" : "neutral"}>
              Social Sharing: {stats.event_flags.public_sharing_enabled ? "Enabled" : "Disabled"}
            </StatusBadge>
          </div>

          {/* Primary Invitation & Admission Metrics */}
          <section aria-label="Invitation and Admission Statistics" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              { label: "Total Generated", value: stats.total_generated, sub: `${stats.available_unused} unused available` },
              { label: "Claimed Invitations", value: stats.claimed, sub: `${stats.claim_rate_percent}% claim rate` },
              { label: "Guests Admitted", value: stats.guests_admitted, sub: `${stats.attendance_rate_percent}% attendance` },
              { label: "Awaiting Admission", value: stats.guests_awaiting_admission, sub: `${stats.revoked} revoked · ${stats.expired} expired` },
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-lg border border-champagne/20 bg-espresso p-5"
              >
                <p className="text-xs font-semibold text-champagne">{card.label}</p>
                <p className="font-display mt-2 text-4xl text-ivory tabular-nums">{card.value}</p>
                <p className="mt-1.5 text-xs text-ivory-muted">{card.sub}</p>
              </div>
            ))}
          </section>

          {/* Gender Breakdown for Claimed & Admitted Guests */}
          <section aria-label="Guest Gender Breakdown" className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {(
              [
                {
                  title: "CLAIMED GUESTS BY GENDER",
                  total: stats.claimed,
                  data: stats.gender_breakdown.claimed,
                },
                {
                  title: "ADMITTED GUESTS BY GENDER",
                  total: stats.guests_admitted,
                  data: stats.gender_breakdown.admitted,
                },
              ] as const
            ).map((group) => (
              <div key={group.title} className="rounded-lg border border-champagne/20 bg-espresso p-6">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
                    {group.title}
                  </h2>
                  <span className="text-xs text-ivory-muted tabular-nums">
                    {group.total} total
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                    <p className="text-xs font-semibold text-champagne">Male</p>
                    <p className="font-display mt-1 text-3xl text-ivory tabular-nums">
                      {group.data.male}
                    </p>
                    <p className="mt-0.5 text-xs text-amber tabular-nums">
                      {group.data.male_percent}%
                    </p>
                  </div>
                  <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                    <p className="text-xs font-semibold text-champagne">Female</p>
                    <p className="font-display mt-1 text-3xl text-ivory tabular-nums">
                      {group.data.female}
                    </p>
                    <p className="mt-0.5 text-xs text-amber tabular-nums">
                      {group.data.female_percent}%
                    </p>
                  </div>
                </div>
                <div
                  aria-hidden="true"
                  className="mt-4 flex h-2 overflow-hidden rounded bg-midnight"
                >
                  <div
                    className="h-full bg-burnt transition-all"
                    style={{ width: `${Math.min(100, group.data.male_percent)}%` }}
                  />
                  <div
                    className="h-full bg-champagne transition-all"
                    style={{ width: `${Math.min(100, group.data.female_percent)}%` }}
                  />
                </div>
              </div>
            ))}
          </section>

          {/* Email Delivery + Quotas */}
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-champagne/20 bg-espresso p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
                  EMAIL DELIVERY PIPELINE
                </h2>
                <div className="flex items-center gap-3">
                  {(stats.emails_pending > 0 || stats.emails_failed > 0) && (
                    <Button
                      variant="outline"
                      size="sm"
                      loading={retryingEmails}
                      onClick={() => void handleRetryEmails()}
                    >
                      <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                      Retry Queue
                    </Button>
                  )}
                  <Link href="/admin/invitations" className="text-xs font-semibold text-amber hover:text-ivory">
                    View Invitations
                  </Link>
                </div>
              </div>
              {retrySummary && (
                <p className="mt-3 rounded border border-champagne/20 bg-midnight/80 px-3 py-2 text-xs text-champagne">
                  {retrySummary}
                </p>
              )}
              <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                  <dt className="text-xs text-ivory-muted">Pending</dt>
                  <dd className="font-display mt-1 text-2xl text-amber">{stats.emails_pending}</dd>
                </div>
                <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                  <dt className="text-xs text-ivory-muted">Sent</dt>
                  <dd className="font-display mt-1 text-2xl text-ivory">{stats.emails_sent}</dd>
                </div>
                <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                  <dt className="text-xs text-ivory-muted">Delivered</dt>
                  <dd className="font-display mt-1 text-2xl text-status-ok">{stats.emails_delivered}</dd>
                </div>
                <div className="rounded border border-champagne/15 bg-midnight p-3.5">
                  <dt className="text-xs text-ivory-muted">Failed / Bounced</dt>
                  <dd className="font-display mt-1 text-2xl text-status-err">{stats.emails_failed}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-lg border border-champagne/20 bg-espresso p-6">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
                  QUOTA CAPACITY
                </h2>
                <Ticket className="h-5 w-5 text-amber" aria-hidden="true" />
              </div>
              <div className="mt-5 space-y-4 text-sm">
                <div>
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-champagne">Global Event Quota</span>
                    <span className="text-ivory">
                      {stats.quota.global_used} / {stats.quota.global_limit ?? "Unlimited"}
                      {stats.quota.global_remaining !== null && ` (${stats.quota.global_remaining} left)`}
                    </span>
                  </div>
                  {stats.quota.global_limit && (
                    <div className="mt-2 h-2 overflow-hidden rounded bg-midnight">
                      <div
                        className="h-full bg-burnt"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.round((stats.quota.global_used / stats.quota.global_limit) * 100),
                          )}%`,
                        }}
                      />
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-champagne">Your Administrator Quota</span>
                    <span className="text-ivory">
                      {stats.quota.admin_used} / {stats.quota.admin_limit ?? "Unlimited"}
                      {stats.quota.admin_remaining !== null && ` (${stats.quota.admin_remaining} left)`}
                    </span>
                  </div>
                  {stats.quota.admin_limit && (
                    <div className="mt-2 h-2 overflow-hidden rounded bg-midnight">
                      <div
                        className="h-full bg-amber"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.round((stats.quota.admin_used / stats.quota.admin_limit) * 100),
                          )}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
                <p className="text-xs text-ivory-muted">
                  All issued links (including expired and revoked) count toward generation quotas.
                </p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default function AdminDashboardPage() {
  return (
    <AdminGuardShell>
      <DashboardContent />
    </AdminGuardShell>
  );
}
