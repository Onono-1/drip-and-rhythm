"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useState } from "react";

import { Button, Input, StatusBadge } from "@/components/ui/primitives";
import { AdminGuardShell, useAdminUser } from "@/features/admin/admin-shell";
import { apiFetch, formatDateTime } from "@/lib/api-client";
import type { CheckInRecord, PaginatedResponse } from "@/types/api";

function CheckInsInner() {
  const user = useAdminUser();
  const [search, setSearch] = useState("");
  const [method, setMethod] = useState("");
  const [genderFilter, setGenderFilter] = useState("");
  const [page, setPage] = useState(1);

  const params = new URLSearchParams();
  params.set("page", String(page));
  if (search.trim()) params.set("search", search.trim());
  if (method) params.set("method", method);
  if (genderFilter) params.set("gender", genderFilter);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-checkins", params.toString()],
    queryFn: () => apiFetch<PaginatedResponse<CheckInRecord>>(`/api/check-ins/?${params.toString()}`),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 border-b border-champagne/15 pb-5 sm:flex-row sm:items-end">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">
            GUEST CHECK-INS
          </h1>
          <p className="mt-1 text-sm text-ivory-muted">
            Historical entrance admission log. Completed check-ins are permanent.
          </p>
        </div>

        {user.role === "SUPER_ADMIN" && (
          <a href="/api/check-ins/export/" download="drip-and-rhythm-checkins.csv">
            <Button variant="outline">
              <Download className="h-4 w-4" />
              Export Check-ins CSV
            </Button>
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-champagne/20 bg-espresso p-4 sm:grid-cols-4">
        <div className="relative sm:col-span-2">
          <Search className="pointer-events-none absolute top-3.5 left-3.5 h-4 w-4 text-champagne/60" />
          <Input
            type="search"
            aria-label="Search check-ins"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search reference, nickname, or email..."
            className="pl-10"
          />
        </div>
        <select
          aria-label="Filter verification method"
          value={method}
          onChange={(e) => {
            setMethod(e.target.value);
            setPage(1);
          }}
          className="min-h-12 rounded-md border border-champagne/25 bg-midnight px-3.5 text-sm text-ivory"
        >
          <option value="">All Verification Methods</option>
          <option value="QR">QR Scan</option>
          <option value="MANUAL">Manual Reference</option>
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

      <div className="overflow-x-auto rounded-lg border border-champagne/20 bg-espresso">
        <table className="w-full min-w-[740px] text-left text-sm">
          <thead>
            <tr className="border-b border-champagne/20 bg-midnight/60 text-xs font-semibold text-champagne">
              <th className="px-4 py-3.5">Reference</th>
              <th className="px-4 py-3.5">Guest</th>
              <th className="px-4 py-3.5">Gender</th>
              <th className="px-4 py-3.5">Method</th>
              <th className="px-4 py-3.5">Verified By</th>
              <th className="px-4 py-3.5">Checked In At</th>
              <th className="px-4 py-3.5">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-champagne/10">
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-ivory-muted">
                  Loading check-in records...
                </td>
              </tr>
            ) : !data || data.results.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-ivory-muted">
                  No check-ins recorded yet.
                </td>
              </tr>
            ) : (
              data.results.map((ci) => (
                <tr key={ci.id}>
                  <td className="px-4 py-3.5 font-mono text-xs font-semibold text-amber">
                    {ci.reference}
                  </td>
                  <td className="px-4 py-3.5">
                    <p className="font-semibold text-ivory">{ci.nickname}</p>
                    <p className="text-xs text-ivory-muted">{ci.guest_email}</p>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">
                    {ci.gender === "MALE" ? "Male" : ci.gender === "FEMALE" ? "Female" : "—"}
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge tone={ci.verification_method === "QR" ? "success" : "warning"}>
                      {ci.verification_method}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory">{ci.verified_by_name}</td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">
                    {formatDateTime(ci.checked_in_at)}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-ivory-muted">{ci.notes || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AdminCheckInsPage() {
  return (
    <AdminGuardShell>
      <CheckInsInner />
    </AdminGuardShell>
  );
}
