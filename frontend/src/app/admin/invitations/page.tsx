"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Check,
  Copy,
  Download,
  Eye,
  Layers,
  Link2,
  Pause,
  Play,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";
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
  MasterLinkCreateResponse,
  MasterLinkSummary,
  PaginatedResponse,
} from "@/types/api";

function statusTone(status: string) {
  switch (status) {
    case "CLAIMED":
    case "DELIVERED":
    case "SENT":
    case "ACTIVE":
      return "success" as const;
    case "UNUSED":
    case "PENDING":
    case "PROCESSING":
    case "EXHAUSTED":
      return "gold" as const;
    case "EXPIRED":
    case "PAUSED":
      return "warning" as const;
    case "REVOKED":
    case "FAILED":
    case "BOUNCED":
    case "CLOSED":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function InvitationsInner() {
  const user = useAdminUser();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"individual" | "master">(() =>
    searchParams.get("tab") === "master" || searchParams.get("master") === "1"
      ? "master"
      : "individual",
  );

  // Individual invitation filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [admissionFilter, setAdmissionFilter] = useState("");
  const [genderFilter, setGenderFilter] = useState("");
  const [masterFilter, setMasterFilter] = useState<{ id: string; name: string } | null>(null);
  const [page, setPage] = useState(1);

  // Master link filters
  const [masterSearch, setMasterSearch] = useState("");
  const [masterStatusFilter, setMasterStatusFilter] = useState("");
  const [masterPage, setMasterPage] = useState(1);

  // Bulk dialog
  const [bulkOpen, setBulkOpen] = useState(() => searchParams.get("bulk") === "1");
  const [bulkQty, setBulkQty] = useState(10);
  const [bulkExpiresAt, setBulkExpiresAt] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkGenerateResponse | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);

  // Master link creation dialog
  const [masterOpen, setMasterOpen] = useState(() => searchParams.get("master") === "1");
  const [masterName, setMasterName] = useState("");
  const [masterTickets, setMasterTickets] = useState(20);
  const [masterExpiresAt, setMasterExpiresAt] = useState("");
  const [masterLoading, setMasterLoading] = useState(false);
  const [masterResult, setMasterResult] = useState<MasterLinkCreateResponse | null>(null);
  const [masterError, setMasterError] = useState<string | null>(null);

  // Master link close confirmation & action busy state
  const [closingLink, setClosingLink] = useState<MasterLinkSummary | null>(null);
  const [actionBusyId, setActionBusyId] = useState<string | null>(null);

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
  if (masterFilter) queryParams.set("master_link", masterFilter.id);

  const masterParams = new URLSearchParams();
  masterParams.set("page", String(masterPage));
  if (masterSearch.trim()) masterParams.set("search", masterSearch.trim());
  if (masterStatusFilter) masterParams.set("status", masterStatusFilter);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-invitations", queryParams.toString()],
    queryFn: () =>
      apiFetch<PaginatedResponse<InvitationSummary>>(`/api/invitations/?${queryParams.toString()}`),
    enabled: activeTab === "individual",
  });

  const { data: masterData, isLoading: masterListLoading } = useQuery({
    queryKey: ["admin-master-links", masterParams.toString()],
    queryFn: () =>
      apiFetch<PaginatedResponse<MasterLinkSummary>>(
        `/api/invitations/master-links/?${masterParams.toString()}`,
      ),
    enabled: activeTab === "master",
  });

  const { data: dashStats } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => apiFetch<DashboardStats>("/api/dashboard/"),
  });

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin-invitations"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-master-links"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
  };

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
      await invalidateAll();
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

  const handleCopyMasterLink = async (ml: MasterLinkSummary) => {
    if (!ml.claim_url) return;
    await navigator.clipboard.writeText(ml.claim_url);
    setCopiedRef(`ml:${ml.id}`);
    window.setTimeout(() => setCopiedRef(null), 2400);
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
      await invalidateAll();
    } catch (err) {
      setBulkError(err instanceof ApiClientError ? err.message : "Bulk generation failed.");
    } finally {
      setBulkLoading(false);
    }
  };

  const handleMasterCreate = async (e: FormEvent) => {
    e.preventDefault();
    setMasterLoading(true);
    setMasterError(null);
    try {
      const body: Record<string, unknown> = {
        name: masterName.trim(),
        max_tickets: masterTickets,
      };
      if (masterExpiresAt) {
        body.expires_at = new Date(masterExpiresAt).toISOString();
      }
      const res = await apiFetch<MasterLinkCreateResponse>("/api/invitations/master-links/", {
        method: "POST",
        json: body,
      });
      setMasterResult(res);
      setActiveTab("master");
      await invalidateAll();
    } catch (err) {
      setMasterError(err instanceof ApiClientError ? err.message : "Master link creation failed.");
    } finally {
      setMasterLoading(false);
    }
  };

  const handleMasterStateAction = async (ml: MasterLinkSummary, action: "pause" | "resume" | "close") => {
    setActionBusyId(ml.id);
    setBannerError(null);
    try {
      await apiFetch<MasterLinkSummary>(`/api/invitations/master-links/${ml.id}/${action}/`, {
        method: "POST",
        json: {},
      });
      if (action === "close") {
        setClosingLink(null);
      }
      await invalidateAll();
    } catch (err) {
      setBannerError(err instanceof ApiClientError ? err.message : `Failed to ${action} master link.`);
    } finally {
      setActionBusyId(null);
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
  const masterTotalCount = masterData?.count ?? 0;
  const masterTotalPages = Math.max(1, Math.ceil(masterTotalCount / 25));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 border-b border-champagne/15 pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">INVITATIONS</h1>
          <p className="mt-1 text-sm text-ivory-muted">
            Generate single, bulk, or master invitation links, inspect guest claims, and manage delivery status.
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
          <Button
            variant="secondary"
            onClick={() => {
              setMasterResult(null);
              setMasterError(null);
              setMasterName("");
              setMasterTickets(20);
              setMasterExpiresAt("");
              setMasterOpen(true);
            }}
          >
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Master Link
          </Button>
          {user.role === "SUPER_ADMIN" && activeTab === "individual" && (
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

      {/* Mode Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Invitation views" className="inline-flex rounded-lg border border-champagne/20 bg-espresso p-1">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "individual"}
            onClick={() => setActiveTab("individual")}
            className={`min-h-10 cursor-pointer rounded-md px-4 text-xs font-semibold transition-colors ${
              activeTab === "individual"
                ? "bg-burnt text-ivory"
                : "text-champagne hover:text-ivory"
            }`}
          >
            Individual Invitations
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "master"}
            onClick={() => setActiveTab("master")}
            className={`inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-md px-4 text-xs font-semibold transition-colors ${
              activeTab === "master"
                ? "bg-burnt text-ivory"
                : "text-champagne hover:text-ivory"
            }`}
          >
            <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
            Master Links
          </button>
        </div>

        {masterFilter && activeTab === "individual" && (
          <div className="inline-flex items-center gap-2 rounded-md border border-amber/40 bg-chocolate/70 px-3 py-1.5 text-xs text-ivory">
            <span>
              Filtered by Master Link: <strong className="text-amber">{masterFilter.name}</strong>
            </span>
            <button
              type="button"
              onClick={() => {
                setMasterFilter(null);
                setPage(1);
              }}
              aria-label="Clear master link filter"
              className="rounded p-0.5 text-champagne hover:text-ivory"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {copiedRef && copiedRef !== "BULK_ALL" && !copiedRef.startsWith("ml:") && (
        <div role="status" className="rounded border border-amber/40 bg-chocolate/70 px-4 py-3 text-xs text-ivory">
          Copied single-use invitation link for <strong>{copiedRef}</strong> to clipboard.
        </div>
      )}

      {copiedRef?.startsWith("ml:") && (
        <div role="status" className="rounded border border-amber/40 bg-chocolate/70 px-4 py-3 text-xs text-ivory">
          Copied master invitation link to clipboard.
        </div>
      )}

      {bannerError && (
        <div role="alert" className="rounded border border-status-err/50 bg-red-950/60 px-4 py-3 text-xs text-red-100">
          {bannerError}
        </div>
      )}

      {activeTab === "individual" ? (
        <>
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
                      No invitations match your current filters.
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
                      <td className="px-4 py-3.5 text-xs text-ivory-muted">
                        <p>{inv.generated_by_name}</p>
                        {inv.master_link_name && (
                          <p className="mt-0.5 text-[11px] text-amber">Master: {inv.master_link_name}</p>
                        )}
                      </td>
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
        </>
      ) : (
        <>
          {/* Master Links Search & Filter */}
          <div className="grid grid-cols-1 gap-3 rounded-lg border border-champagne/20 bg-espresso p-4 sm:grid-cols-3">
            <div className="relative sm:col-span-2">
              <Search className="pointer-events-none absolute top-3.5 left-3.5 h-4 w-4 text-champagne/60" />
              <Input
                type="search"
                aria-label="Search master links"
                value={masterSearch}
                onChange={(e) => {
                  setMasterSearch(e.target.value);
                  setMasterPage(1);
                }}
                placeholder="Search link name or creator..."
                className="pl-10"
              />
            </div>

            <select
              aria-label="Filter master links by status"
              value={masterStatusFilter}
              onChange={(e) => {
                setMasterStatusFilter(e.target.value);
                setMasterPage(1);
              }}
              className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
            >
              <option value="">All Master Link States</option>
              <option value="ACTIVE">Active</option>
              <option value="PAUSED">Paused</option>
              <option value="EXHAUSTED">Exhausted</option>
              <option value="CLOSED">Closed</option>
            </select>
          </div>

          {/* Master Links Table */}
          <div className="overflow-x-auto rounded-lg border border-champagne/20 bg-espresso">
            <table className="w-full min-w-[840px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-champagne/20 bg-midnight/60 text-xs font-semibold text-champagne">
                  <th className="px-4 py-3.5">Link Name</th>
                  <th className="px-4 py-3.5">Creator</th>
                  <th className="px-4 py-3.5">Allocated</th>
                  <th className="px-4 py-3.5">Claimed</th>
                  <th className="px-4 py-3.5">Remaining</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Created</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-champagne/10">
                {masterListLoading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-10 text-center text-ivory-muted">
                      Loading master links...
                    </td>
                  </tr>
                ) : !masterData || masterData.results.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-10 text-center text-ivory-muted">
                      No master invitation links created yet. Use Master Link above to allocate a shareable batch.
                    </td>
                  </tr>
                ) : (
                  masterData.results.map((ml) => {
                    const label = ml.name || "Untitled Master Link";
                    const busy = actionBusyId === ml.id;
                    return (
                      <tr key={ml.id} className="hover:bg-midnight/40">
                        <td className="px-4 py-3.5">
                          <p className="font-semibold text-ivory">{label}</p>
                          {ml.expires_at && (
                            <p className="text-[11px] text-ivory-muted">
                              Expires {formatDateTime(ml.expires_at)}
                            </p>
                          )}
                          {ml.status === "CLOSED" && ml.released_tickets > 0 && (
                            <p className="text-[11px] text-ivory-muted">
                              Released {ml.released_tickets} unused ticket{ml.released_tickets === 1 ? "" : "s"}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-xs text-ivory-muted">{ml.created_by_name}</td>
                        <td className="px-4 py-3.5 font-semibold text-ivory tabular-nums">
                          {ml.max_tickets}
                        </td>
                        <td className="px-4 py-3.5 font-semibold text-amber tabular-nums">
                          {ml.claimed_count}
                        </td>
                        <td className="px-4 py-3.5 font-semibold text-champagne tabular-nums">
                          {ml.remaining_tickets}
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusBadge tone={statusTone(ml.status)}>{ml.status}</StatusBadge>
                        </td>
                        <td className="px-4 py-3.5 text-xs text-ivory-muted">
                          {formatDateTime(ml.created_at)}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <div className="inline-flex flex-wrap items-center justify-end gap-1.5">
                            {ml.claim_url && (ml.status === "ACTIVE" || ml.status === "PAUSED") && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => void handleCopyMasterLink(ml)}
                              >
                                {copiedRef === `ml:${ml.id}` ? (
                                  <Check className="h-3.5 w-3.5 text-status-ok" />
                                ) : (
                                  <Copy className="h-3.5 w-3.5" />
                                )}
                                Copy
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setMasterFilter({ id: ml.id, name: label });
                                setPage(1);
                                setActiveTab("individual");
                              }}
                            >
                              <Users className="h-3.5 w-3.5" />
                              Guests ({ml.claimed_count})
                            </Button>
                            {ml.can_manage && ml.status === "ACTIVE" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                loading={busy}
                                onClick={() => void handleMasterStateAction(ml, "pause")}
                              >
                                <Pause className="h-3.5 w-3.5" />
                                Pause
                              </Button>
                            )}
                            {ml.can_manage && ml.status === "PAUSED" && (
                              <Button
                                variant="secondary"
                                size="sm"
                                loading={busy}
                                onClick={() => void handleMasterStateAction(ml, "resume")}
                              >
                                <Play className="h-3.5 w-3.5" />
                                Resume
                              </Button>
                            )}
                            {ml.can_manage && ml.status !== "CLOSED" && (
                              <Button
                                variant="danger"
                                size="sm"
                                disabled={busy}
                                onClick={() => setClosingLink(ml)}
                              >
                                <Ban className="h-3.5 w-3.5" />
                                Close
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {masterTotalCount > 25 && (
            <div className="flex items-center justify-between text-xs text-ivory-muted">
              <span>
                Showing page {masterPage} of {masterTotalPages} ({masterTotalCount} master links)
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={masterPage <= 1}
                  onClick={() => setMasterPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={masterPage >= masterTotalPages}
                  onClick={() => setMasterPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
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

      {/* Master Link Creation Dialog */}
      <ModalDialog
        open={masterOpen}
        onOpenChange={setMasterOpen}
        title="CREATE MASTER INVITATION LINK"
        description="Reserve a fixed ticket allocation behind one shareable URL. Each claiming guest receives their own unique ticket, QR pass, and email."
      >
        {dashStats && (
          <div className="mb-4 rounded border border-champagne/20 bg-midnight p-3 text-xs text-ivory-muted">
            <p>
              Global remaining:{" "}
              <strong className="text-ivory tabular-nums">
                {dashStats.quota.global_remaining ?? "Unlimited"}
              </strong>{" "}
              · Your remaining quota:{" "}
              <strong className="text-ivory tabular-nums">
                {dashStats.quota.admin_remaining ?? "Unlimited"}
              </strong>
            </p>
          </div>
        )}

        {masterResult ? (
          <div className="space-y-4">
            <p className="text-sm font-semibold text-status-ok">
              Master link created ({masterResult.max_tickets} tickets reserved).
            </p>
            <div className="rounded border border-amber/40 bg-midnight p-3">
              <p className="text-xs font-semibold text-champagne">
                {masterResult.name || "Untitled Master Link"}
              </p>
              <p className="mt-1 break-all font-mono text-xs text-ivory">
                {masterResult.claim_url}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {masterResult.claim_url && (
                <>
                  <Button
                    size="sm"
                    onClick={() => void handleCopyMasterLink(masterResult)}
                  >
                    {copiedRef === `ml:${masterResult.id}` ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                    {copiedRef === `ml:${masterResult.id}` ? "Copied" : "Copy Master Link"}
                  </Button>
                  <a
                    href={`https://wa.me/?text=${encodeURIComponent(
                      `You're invited to DRIP & RHYTHM (5 Dec 2026). Claim your exclusive invitation pass here: ${masterResult.claim_url}`,
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button variant="outline" size="sm">
                      WhatsApp Share
                    </Button>
                  </a>
                </>
              )}
            </div>
            <Button variant="outline" className="w-full" onClick={() => setMasterOpen(false)}>
              Done
            </Button>
          </div>
        ) : (
          <form onSubmit={handleMasterCreate} className="space-y-4">
            {masterError && (
              <p role="alert" className="text-xs font-medium text-status-err">
                {masterError}
              </p>
            )}
            <div>
              <label htmlFor="master-name" className="block text-sm font-semibold text-champagne">
                Internal link name (optional)
              </label>
              <Input
                id="master-name"
                maxLength={120}
                value={masterName}
                onChange={(e) => setMasterName(e.target.value)}
                placeholder="e.g. VIP Table — Muyenga Crew"
                className="mt-1.5"
              />
            </div>
            <div>
              <label htmlFor="master-tickets" className="block text-sm font-semibold text-champagne">
                Maximum claimable tickets
              </label>
              <Input
                id="master-tickets"
                type="number"
                min={1}
                max={5000}
                required
                value={masterTickets}
                onChange={(e) => setMasterTickets(Number(e.target.value))}
                className="mt-1.5"
              />
              <p className="mt-1 text-xs text-ivory-muted">
                Reserved immediately against your quota and the global event limit.
              </p>
            </div>
            <div>
              <label htmlFor="master-exp" className="block text-sm font-semibold text-champagne">
                Optional expiration
              </label>
              <Input
                id="master-exp"
                type="datetime-local"
                value={masterExpiresAt}
                onChange={(e) => setMasterExpiresAt(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setMasterOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={masterLoading}>
                Reserve {masterTickets} Tickets
              </Button>
            </div>
          </form>
        )}
      </ModalDialog>

      {/* Permanent Close Confirmation Dialog */}
      <ModalDialog
        open={Boolean(closingLink)}
        onOpenChange={(open) => {
          if (!open) setClosingLink(null);
        }}
        title="PERMANENTLY CLOSE MASTER LINK"
        description="Closing stops all future claims permanently and releases any remaining unclaimed tickets back to quota."
      >
        {closingLink && (
          <div className="space-y-4">
            <div className="rounded border border-champagne/20 bg-midnight p-3.5 text-xs text-ivory-muted">
              <p className="font-semibold text-ivory">
                {closingLink.name || "Untitled Master Link"}
              </p>
              <p className="mt-1 tabular-nums">
                Claimed: <strong className="text-amber">{closingLink.claimed_count}</strong> ·
                Unclaimed to release:{" "}
                <strong className="text-champagne">{closingLink.remaining_tickets}</strong>
              </p>
              <p className="mt-2">
                All {closingLink.claimed_count} already-claimed individual guest invitations will remain valid.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setClosingLink(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={actionBusyId === closingLink.id}
                onClick={() => void handleMasterStateAction(closingLink, "close")}
              >
                Close Permanently
              </Button>
            </div>
          </div>
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
