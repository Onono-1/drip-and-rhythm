"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, Check, Copy, Edit3, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, Input, ModalDialog, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell, useAdminUser } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch, formatDateTime } from "@/lib/api-client";
import type { EmailDeliveryRecord, GuestGender, InvitationDetail } from "@/types/api";

function InvitationDetailInner() {
  const { id } = useParams<{ id: string }>();
  const user = useAdminUser();
  const queryClient = useQueryClient();

  const [copied, setCopied] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [correctOpen, setCorrectOpen] = useState(false);
  const [editNickname, setEditNickname] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editGender, setEditGender] = useState<GuestGender | "">("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const { data: inv, isLoading } = useQuery({
    queryKey: ["admin-invitation", id],
    queryFn: () => apiFetch<InvitationDetail>(`/api/invitations/${id}/`),
  });

  const { data: deliveries } = useQuery({
    queryKey: ["admin-invitation-deliveries", id],
    queryFn: () => apiFetch<EmailDeliveryRecord[]>(`/api/invitations/${id}/deliveries/`),
  });

  const refreshAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin-invitation", id] });
    await queryClient.invalidateQueries({ queryKey: ["admin-invitation-deliveries", id] });
    await queryClient.invalidateQueries({ queryKey: ["admin-invitations"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
  };

  const handleResend = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      await apiFetch(`/api/invitations/${id}/resend/`, { method: "POST", json: {} });
      setFeedback({ type: "ok", text: "Queued invitation email resend." });
      await refreshAll();
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to resend email.",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      await apiFetch(`/api/invitations/${id}/revoke/`, {
        method: "POST",
        json: { reason: revokeReason },
      });
      setRevokeOpen(false);
      setFeedback({ type: "ok", text: "Invitation revoked and sharing/admission disabled." });
      await refreshAll();
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to revoke invitation.",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleCorrectGuest = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      const payload: Record<string, unknown> = {
        nickname: editNickname,
        email: editEmail,
        resend_email: true,
      };
      if (editGender) {
        payload.gender = editGender;
      }
      await apiFetch(`/api/invitations/${id}/correct-guest/`, {
        method: "POST",
        json: payload,
      });
      setCorrectOpen(false);
      setFeedback({
        type: "ok",
        text: "Guest details updated.",
      });
      await refreshAll();
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to update guest details.",
      });
    } finally {
      setBusy(false);
    }
  };

  if (isLoading || !inv) {
    return <p className="text-sm text-ivory-muted">Loading invitation record...</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/invitations"
          className="inline-flex items-center gap-2 text-xs font-semibold text-champagne hover:text-ivory"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Invitations
        </Link>
        <div className="mt-3 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">
              {inv.reference}
            </h1>
            <StatusBadge
              tone={
                inv.status === "CLAIMED"
                  ? "success"
                  : inv.status === "REVOKED"
                    ? "danger"
                    : "gold"
              }
            >
              {inv.status}
            </StatusBadge>
          </div>

          <div className="flex flex-wrap gap-2">
            {inv.claim_url && inv.can_manage && (
              <Button
                size="sm"
                onClick={async () => {
                  await navigator.clipboard.writeText(inv.claim_url!);
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 2000);
                }}
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied Link" : "Copy Claim Link"}
              </Button>
            )}
            {inv.status === "CLAIMED" && inv.can_manage && (
              <Button variant="secondary" size="sm" loading={busy} onClick={() => void handleResend()}>
                <Send className="h-4 w-4" />
                Resend Email
              </Button>
            )}
            {inv.status === "CLAIMED" && !inv.is_admitted && user.role === "SUPER_ADMIN" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setEditNickname(inv.nickname);
                  setEditEmail(inv.guest_email);
                  setEditGender(inv.gender);
                  setCorrectOpen(true);
                }}
              >
                <Edit3 className="h-4 w-4" />
                Correct Guest Info
              </Button>
            )}
            {inv.status !== "REVOKED" && !inv.is_admitted && inv.can_manage && (
              <Button variant="danger" size="sm" onClick={() => setRevokeOpen(true)}>
                <Ban className="h-4 w-4" />
                Revoke
              </Button>
            )}
          </div>
        </div>
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

      {/* Details Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-champagne/20 bg-espresso p-6">
          <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
            INVITATION &amp; GUEST RECORD
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Guest Nickname</dt>
              <dd className="font-semibold text-ivory">{inv.nickname || "—"}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Guest Email</dt>
              <dd className="font-semibold text-ivory">{inv.guest_email || "—"}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Gender</dt>
              <dd className="font-semibold text-ivory">
                {inv.gender === "MALE" ? "Male" : inv.gender === "FEMALE" ? "Female" : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Generated By</dt>
              <dd className="text-ivory">{inv.generated_by_name}</dd>
            </div>
            {inv.master_link_name && (
              <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
                <dt className="text-ivory-muted">Master Link</dt>
                <dd className="font-semibold text-amber">{inv.master_link_name}</dd>
              </div>
            )}
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Generated At</dt>
              <dd className="text-ivory">{formatDateTime(inv.generated_at)}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Claimed At</dt>
              <dd className="text-ivory">{formatDateTime(inv.claimed_at)}</dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-champagne/10 pb-2">
              <dt className="text-ivory-muted">Credential Version</dt>
              <dd className="text-ivory">v{inv.admission_credential_version}</dd>
            </div>
            {inv.revoked_at && (
              <div className="rounded bg-red-950/40 p-3 text-xs text-red-200">
                Revoked on {formatDateTime(inv.revoked_at)} by {inv.revoked_by_name || "Admin"}
                {inv.revocation_reason && ` — Reason: ${inv.revocation_reason}`}
              </div>
            )}
          </dl>
        </section>

        <section className="rounded-lg border border-champagne/20 bg-espresso p-6">
          <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
            ADMISSION STATUS
          </h2>
          {inv.checkin_details ? (
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between border-b border-champagne/10 pb-2">
                <dt className="text-ivory-muted">Status</dt>
                <dd>
                  <StatusBadge tone="success">Admitted</StatusBadge>
                </dd>
              </div>
              <div className="flex justify-between border-b border-champagne/10 pb-2">
                <dt className="text-ivory-muted">Checked In At</dt>
                <dd className="text-ivory">{formatDateTime(inv.checkin_details.checked_in_at)}</dd>
              </div>
              <div className="flex justify-between border-b border-champagne/10 pb-2">
                <dt className="text-ivory-muted">Verification Method</dt>
                <dd className="text-ivory">{inv.checkin_details.verification_method}</dd>
              </div>
              <div className="flex justify-between border-b border-champagne/10 pb-2">
                <dt className="text-ivory-muted">Verified By</dt>
                <dd className="text-ivory">{inv.checkin_details.verified_by_name}</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-4 text-sm text-ivory-muted">
              This guest has not checked in at the entrance yet.
            </p>
          )}
        </section>
      </div>

      {/* Delivery Attempts */}
      <section className="rounded-lg border border-champagne/20 bg-espresso p-6">
        <h2 className="font-display text-2xl tracking-wide text-ivory uppercase">
          EMAIL DELIVERY HISTORY
        </h2>
        {!deliveries || deliveries.length === 0 ? (
          <p className="mt-3 text-sm text-ivory-muted">No email deliveries scheduled yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead>
                <tr className="border-b border-champagne/20 text-champagne">
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Recipient</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Attempts</th>
                  <th className="py-2 pr-4">Sent / Delivered</th>
                  <th className="py-2">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-champagne/10">
                {deliveries.map((d) => (
                  <tr key={d.id}>
                    <td className="py-2.5 pr-4 font-semibold text-ivory">{d.email_type}</td>
                    <td className="py-2.5 pr-4 text-ivory-muted">{d.recipient_email}</td>
                    <td className="py-2.5 pr-4">
                      <StatusBadge
                        tone={
                          d.status === "DELIVERED" || d.status === "SENT"
                            ? "success"
                            : d.status === "FAILED" || d.status === "BOUNCED"
                              ? "danger"
                              : "gold"
                        }
                      >
                        {d.status}
                      </StatusBadge>
                    </td>
                    <td className="py-2.5 pr-4 text-ivory-muted">
                      {d.attempt_count} / {d.max_attempts}
                    </td>
                    <td className="py-2.5 pr-4 text-ivory-muted">
                      {formatDateTime(d.delivered_at || d.sent_at || d.created_at)}
                    </td>
                    <td className="py-2.5 text-red-200">{d.failure_reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Revoke Confirmation Modal */}
      <ModalDialog
        open={revokeOpen}
        onOpenChange={setRevokeOpen}
        title="REVOKE INVITATION"
        description="Revoking permanently disables claiming, public sharing, and entrance admission for this invitation."
      >
        <form onSubmit={handleRevoke} className="space-y-4">
          <div>
            <label htmlFor="rev-reason" className="block text-sm font-semibold text-champagne">
              Reason (optional)
            </label>
            <Input
              id="rev-reason"
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              placeholder="e.g. Link sent to wrong contact"
              className="mt-1.5"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setRevokeOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" loading={busy}>
              Confirm Revocation
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Correct Guest Information Modal */}
      <ModalDialog
        open={correctOpen}
        onOpenChange={setCorrectOpen}
        title="CORRECT GUEST INFORMATION"
        description="Changing the guest email immediately invalidates the previous QR admission pass and dispatches a new pass."
      >
        <form onSubmit={handleCorrectGuest} className="space-y-4">
          <div>
            <label htmlFor="corr-nick" className="block text-sm font-semibold text-champagne">
              Guest nickname
            </label>
            <Input
              id="corr-nick"
              required
              maxLength={50}
              value={editNickname}
              onChange={(e) => setEditNickname(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="corr-email" className="block text-sm font-semibold text-champagne">
              Guest email address
            </label>
            <Input
              id="corr-email"
              type="email"
              required
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <fieldset>
            <legend className="block text-sm font-semibold text-champagne">Gender</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-3">
              {(
                [
                  { value: "MALE", label: "Male" },
                  { value: "FEMALE", label: "Female" },
                ] as const
              ).map((option) => (
                <label
                  key={option.value}
                  className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-champagne/25 bg-midnight px-3.5 py-2 text-sm font-medium text-ivory transition-colors hover:border-champagne/50 has-[:checked]:border-amber has-[:checked]:bg-chocolate/70"
                >
                  <input
                    type="radio"
                    name="corr-gender"
                    value={option.value}
                    checked={editGender === option.value}
                    onChange={() => setEditGender(option.value)}
                    className="h-4 w-4 shrink-0 accent-burnt"
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setCorrectOpen(false)}>
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

export default function AdminInvitationDetailPage() {
  return (
    <AdminGuardShell>
      <InvitationDetailInner />
    </AdminGuardShell>
  );
}
