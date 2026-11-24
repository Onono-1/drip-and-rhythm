"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Download, Eye, Layers, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { Button, Input, ModalDialog, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell, useAdminUser } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch, formatDateTime } from "@/lib/api-client";
import type {
  BulkGenerateResponse,
  DashboardStats,
  InvitationDetail,
  InvitationSummary,
  PaginatedResponse,
} from "@/types/api";

function statusTone(status: string) {
  switch (status) {
    case "CLAIMED":
    case "DELIVERED":
    case "SENT":
      return "success" as const;
    case "UNUSED":
    case "PENDING":
    case "PROCESSING":
      return "gold" as const;
    case "EXPIRED":
      return "warning" as const;
    case "REVOKED":
    case "FAILED":
    case "BOUNCED":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function InvitationsInner() {
  const user = useAdminUser();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [admissionFilter, setAdmissionFilter] = useState("");
  const [genderFilter, setGenderFilter] = useState("");
  const [page, setPage] = useState(1);

  const [bulkOpen, setBulkOpen] = useState(() => searchParams.get("bulk") === "1");
  const [bulkQty, setBulkQty] = useState(10);
  const [bulkExpiresAt, setBulkExpiresAt] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkGenerateResponse | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);

  const [singleLoading, setSingleLoading] = useState(false);
  const [copiedRef, setCopiedRef] = useState<string | null>(null);
  const [bannerError, setBannerError] = useState<string | null>(null);

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  if (search.trim()) queryParams.set("search", search.trim());
  if (statusFilter) queryParams.set("status", statusFilter);
  if (emailFilter) queryParams.set("email_status", emailFilter);
  if (admissionFilter) queryParams.set("admission_status", admissionFilter);
  if (genderFilter) queryParams.set("gender", genderFilter);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-invitations", queryParams.toString()],
    queryFn: () =>
      apiFetch<PaginatedResponse<InvitationSummary>>(`/api/invitations/?${queryParams.toString()}`),
  });

  const { data: dashStats } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => apiFetch<DashboardStats>("/api/dashboard/"),
  });

  const handleGenerateSingle = async () => {
    setSingleLoading(true);
    setBannerError(null);
    try {
      const created = await apiFetch<InvitationDetail>("/api/invitations/", {
        method: "POST",
        json: {},
      });
      if (created.claim_url) {
        await navigator.clipboard.writeText(created.claim_url);
        setCopiedRef(created.reference);
        window.setTimeout(() => setCopiedRef(null), 3000);
      }
      await queryClient.invalidateQueries({ queryKey: ["admin-invitations"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    } catch (err) {
      setBannerError(err instanceof ApiClientError ? err.message : "Failed to generate link.");
    } finally {
      setSingleLoading(false);
    }
  };

  const handleCopyUnusedLink = async (inv: InvitationSummary) => {
    setBannerError(null);
    try {
      const res = await apiFetch<{ claim_url: string }>(`/api/invitations/${inv.id}/claim-link/`);
      await navigator.clipboard.writeText(res.claim_url);
      setCopiedRef(inv.reference);
      window.setTimeout(() => setCopiedRef(null), 2200);
    } catch (err) {
      setBannerError(err instanceof ApiClientError ? err.message : "Unable to retrieve claim link.");
    }
  };

  const handleBulkSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBulkLoading(true);
    setBulkError(null);
    try {
      const body: Record<string, unknown> = { quantity: bulkQty };
      if (bulkExpiresAt) {
        body.expires_at = new Date(bulkExpiresAt).toISOString();
      }
      const res = await apiFetch<BulkGenerateResponse>("/api/invitations/bulk/", {
        method: "POST",
        json: body,
      });
      setBulkResult(res);
      await queryClient.invalidateQueries({ queryKey: ["admin-invitations"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    } catch (err) {
      setBulkError(err instanceof ApiClientError ? err.message : "Bulk generation failed.");
    } finally {
      setBulkLoading(false);
    }
  };

  const copyAllBulkLinks = async () => {
    if (!bulkResult) return;
    const joined = bulkResult.items.map((i) => `${i.reference}: ${i.claim_url}`).join("\n");
    await navigator.clipboard.writeText(joined);
    setCopiedRef("BULK_ALL");
    window.setTimeout(() => setCopiedRef(null), 2200);
  };

  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / 25));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 border-b border-champagne/15 pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">INVITATIONS</h1>
          <p className="mt-1 text-sm text-ivory-muted">
            Generate single or bulk invitation links, inspect guest claims, and manage delivery status.
          </p>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <Button onClick={() => void handleGenerateSingle()} loading={singleLoading}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            New Link (Auto-Copy)
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setBulkResult(null);
              setBulkError(null);
              setBulkOpen(true);
            }}
          >
            <Layers className="h-4 w-4" aria-hidden="true" />
            Bulk Generate
          </Button>
          {user.role === "SUPER_ADMIN" && (
            <a
              href={`/api/invitations/export/?${queryParams.toString()}`}
              download="drip-and-rhythm-invitations.csv"
            >
              <Button variant="outline">
                <Download className="h-4 w-4" aria-hidden="true" />
                Export CSV
              </Button>
            </a>
          )}
        </div>
      </div>

      {copiedRef && copiedRef !== "BULK_ALL" && (
        <div role="status" className="rounded border border-amber/40 bg-chocolate/70 px-4 py-3 text-xs text-ivory">
          Copied single-use invitation link for <strong>{copiedRef}</strong> to clipboard.
        </div>
      )}

      {bannerError && (
        <div role="alert" className="rounded border border-status-err/50 bg-red-950/60 px-4 py-3 text-xs text-red-100">
          {bannerError}
        </div>
      )}

      {/* Search & Filters */}
      <div className="grid grid-cols-1 gap-3 rounded-lg border border-champagne/20 bg-espresso p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="relative">
          <Search className="pointer-events-none absolute top-3.5 left-3.5 h-4 w-4 text-champagne/60" />
          <Input
            type="search"
            aria-label="Search invitations"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search ref, nickname, email..."
            className="pl-10"
          />
        </div>

        <select
          aria-label="Filter by invitation status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
        >
          <option value="">All Invitation States</option>
          <option value="UNUSED">Unused</option>
          <option value="CLAIMED">Claimed</option>
          <option value="EXPIRED">Expired</option>
          <option value="REVOKED">Revoked</option>
        </select>

        <select
          aria-label="Filter by email status"
          value={emailFilter}
          onChange={(e) => {
            setEmailFilter(e.target.value);
            setPage(1);
          }}
          className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
        >
          <option value="">All Email States</option>
          <option value="NOT_SCHEDULED">Not Scheduled</option>
          <option value="PENDING">Pending</option>
          <option value="SENT">Sent</option>
          <option value="DELIVERED">Delivered</option>
          <option value="FAILED">Failed</option>
          <option value="BOUNCED">Bounced</option>
        </select>

        <select
          aria-label="Filter by admission status"
          value={admissionFilter}
          onChange={(e) => {
            setAdmissionFilter(e.target.value);
            setPage(1);
          }}
          className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
        >
          <option value="">All Admission States</option>
          <option value="ADMITTED">Admitted</option>
          <option value="NOT_ADMITTED">Not Admitted</option>
        </select>

        <select
          aria-label="Filter by gender"
          value={genderFilter}
          onChange={(e) => {
            setGenderFilter(e.target.value);
            setPage(1);
          }}
          className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
        >
          <option value="">All Genders</option>
          <option value="MALE">Male</option>
          <option value="FEMALE">Female</option>
        </select>
      </div>

      {/* Responsive Table */}
      <div className="overflow-x-auto rounded-lg border border-champagne/20 bg-espresso">
        <table className="w-full min-w-[840px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-champagne/20 bg-midnight/60 text-xs font-semibold text-champagne">
              <th className="px-4 py-3.5">Ref</th>
              <th className="px-4 py-3.5">Guest</th>
              <th className="px-4 py-3.5">Gender</th>
              <th className="px-4 py-3.5">Status</th>
              <th className="px-4 py-3.5">Email</th>
              <th className="px-4 py-3.5">Admission</th>
              <th className="px-4 py-3.5">Host</th>
              <th className="px-4 py-3.5">Created</th>
              <th className="px-4 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-champagne/10">
            {isLoading ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-ivory-muted">
                  Loading invitations...
                </td>
              </tr>
            ) : !data || data.results.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-ivory-muted">
                  No invitations match your current filters. Generate a new link to get started.
                </td>
              </tr>
            ) : (
              data.results.map((inv) => (
                <tr key={inv.id} className="hover:bg-midnight/40">
                  <td className="px-4 py-3.5 font-mono text-xs font-semibold text-amber">
                    {inv.reference}
                  </td>
                  <td className="px-4 py-3.5">
                    {inv.nickname ? (
                      <div>
                        <p className="font-semibold text-ivory">{inv.nickname}</p>
                        <p className="text-xs text-ivory-muted">{inv.guest_email}</p>
                      </div>
                    ) : (
                      <span className="text-xs text-ivory-muted">Unclaimed</span>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">
                    {inv.gender === "MALE" ? "Male" : inv.gender === "FEMALE" ? "Female" : "—"}
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge tone={statusTone(inv.status)}>{inv.status}</StatusBadge>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge tone={statusTone(inv.latest_email_status)}>
                      {inv.latest_email_status}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3.5">
                    {inv.is_admitted ? (
                      <StatusBadge tone="success">Admitted</StatusBadge>
                    ) : (
                      <StatusBadge tone="neutral">Pending</StatusBadge>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">{inv.generated_by_name}</td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">
                    {formatDateTime(inv.generated_at)}
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      {inv.status === "UNUSED" && inv.can_manage && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleCopyUnusedLink(inv)}
                        >
                          {copiedRef === inv.reference ? (
                            <Check className="h-3.5 w-3.5 text-status-ok" />
                          ) : (
                            <Copy className="h-3.5 w-3.5" />
                          )}
                          Copy
                        </Button>
                      )}
                      <Link href={`/admin/invitations/${inv.id}`}>
                        <Button variant="outline" size="sm">
                          <Eye className="h-3.5 w-3.5" />
                          Details
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalCount > 25 && (
        <div className="flex items-center justify-between text-xs text-ivory-muted">
          <span>
            Showing page {page} of {totalPages} ({totalCount} total records)
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Bulk Generation Dialog */}
      <ModalDialog
        open={bulkOpen}
        onOpenChange={setBulkOpen}
        title="BULK GENERATE INVITATIONS"
        description="Atomically generate a batch of unique single-use invitation links."
      >
        {dashStats && (
          <div className="mb-4 rounded border border-champagne/20 bg-midnight p-3 text-xs text-ivory-muted">
            <p>
              Global remaining:{" "}
              <strong className="text-ivory">
                {dashStats.quota.global_remaining ?? "Unlimited"}
              </strong>{" "}
              · Your remaining quota:{" "}
              <strong className="text-ivory">
                {dashStats.quota.admin_remaining ?? "Unlimited"}
              </strong>{" "}
              · Max batch: <strong className="text-ivory">{dashStats.quota.max_bulk_quantity}</strong>
            </p>
          </div>
        )}

        {bulkResult ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-status-ok">
                Generated {bulkResult.count} single-use links.
              </p>
              <Button size="sm" onClick={() => void copyAllBulkLinks()}>
                {copiedRef === "BULK_ALL" ? "Copied All!" : "Copy All Links"}
              </Button>
            </div>
            <div className="max-h-64 space-y-2 overflow-y-auto rounded border border-champagne/20 bg-midnight p-3 font-mono text-xs">
              {bulkResult.items.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-2">
                  <span className="truncate text-ivory">
                    <span className="text-amber">{item.reference}</span> · {item.claim_url}
                  </span>
                </div>
              ))}
            </div>
            <Button variant="outline" className="w-full" onClick={() => setBulkOpen(false)}>
              Done
            </Button>
          </div>
        ) : (
          <form onSubmit={handleBulkSubmit} className="space-y-4">
            {bulkError && (
              <p role="alert" className="text-xs font-medium text-status-err">
                {bulkError}
              </p>
            )}
            <div>
              <label htmlFor="bulk-qty" className="block text-sm font-semibold text-champagne">
                Number of links to generate
              </label>
              <Input
                id="bulk-qty"
                type="number"
                min={1}
                max={dashStats?.quota.max_bulk_quantity ?? 100}
                required
                value={bulkQty}
                onChange={(e) => setBulkQty(Number(e.target.value))}
                className="mt-1.5"
              />
            </div>
            <div>
              <label htmlFor="bulk-exp" className="block text-sm font-semibold text-champagne">
                Optional claim expiration
              </label>
              <Input
                id="bulk-exp"
                type="datetime-local"
                value={bulkExpiresAt}
                onChange={(e) => setBulkExpiresAt(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setBulkOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={bulkLoading}>
                Generate {bulkQty} Links
              </Button>
            </div>
          </form>
        )}
      </ModalDialog>
    </div>
  );
}

export default function AdminInvitationsPage() {
  return (
    <AdminGuardShell>
      <Suspense fallback={<p className="text-sm text-ivory-muted">Loading...</p>}>
        <InvitationsInner />
      </Suspense>
    </AdminGuardShell>
  );
}
