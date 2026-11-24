"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import { Button, Input } from "@/components/ui/primitives";
import { AdminGuardShell } from "@/features/admin/admin-shell";
import { apiFetch, formatDateTime } from "@/lib/api-client";
import type { AuditLogRecord, PaginatedResponse } from "@/types/api";

function AuditLogsInner() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const params = new URLSearchParams();
  params.set("page", String(page));
  if (search.trim()) params.set("search", search.trim());

  const { data, isLoading } = useQuery({
    queryKey: ["admin-audit-logs", params.toString()],
    queryFn: () => apiFetch<PaginatedResponse<AuditLogRecord>>(`/api/audit-logs/?${params.toString()}`),
  });

  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / 25));

  return (
    <div className="space-y-6">
      <div className="border-b border-champagne/15 pb-5">
        <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">AUDIT LOGS</h1>
        <p className="mt-1 text-sm text-ivory-muted">
          Append-only administrative and security event trail with automatic credential redaction.
        </p>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute top-3.5 left-3.5 h-4 w-4 text-champagne/60" />
        <Input
          type="search"
          aria-label="Search audit logs"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search action, actor email, or reference..."
          className="pl-10"
        />
      </div>

      <div className="overflow-x-auto rounded-lg border border-champagne/20 bg-espresso">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead>
            <tr className="border-b border-champagne/20 bg-midnight/60 font-semibold text-champagne">
              <th className="px-4 py-3.5">Timestamp</th>
              <th className="px-4 py-3.5">Actor</th>
              <th className="px-4 py-3.5">Action</th>
              <th className="px-4 py-3.5">Target</th>
              <th className="px-4 py-3.5">Metadata</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-champagne/10">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-ivory-muted">
                  Loading audit trail...
                </td>
              </tr>
            ) : !data || data.results.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-ivory-muted">
                  No audit events found.
                </td>
              </tr>
            ) : (
              data.results.map((log) => (
                <tr key={log.id}>
                  <td className="px-4 py-3 text-ivory-muted">{formatDateTime(log.created_at)}</td>
                  <td className="px-4 py-3 text-ivory">{log.actor_display_name}</td>
                  <td className="px-4 py-3 font-mono font-semibold text-amber">{log.action_type}</td>
                  <td className="px-4 py-3 text-ivory">
                    {log.target_type} {log.target_id && `· ${log.target_id}`}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 font-mono text-ivory-muted">
                    {Object.keys(log.metadata).length > 0 ? JSON.stringify(log.metadata) : "—"}
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
            Page {page} of {totalPages}
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
    </div>
  );
}

export default function AdminAuditLogsPage() {
  return (
    <AdminGuardShell requireSuperAdmin>
      <AuditLogsInner />
    </AdminGuardShell>
  );
}
