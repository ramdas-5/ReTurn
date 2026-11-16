"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AuditLog } from "@/lib/types";

export default function AdminAuditPage() {
  const [action, setAction] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-audit", action],
    queryFn: () => apiGetList<AuditLog>(`/admin/audit?per_page=100${action ? `&action=${encodeURIComponent(action)}` : ""}`),
  });

  return (
    <div>
      <PageHeader eyebrow="Audit logs" title="Append-only platform history" description="Sensitive actions record who did what, when and why. This view is read-only." />
      <input className="input mb-4 max-w-sm" placeholder="Filter action, e.g. admin.vehicle" value={action} onChange={(event) => setAction(event.target.value)} />
      {isLoading ? <p className="text-sm text-muted">Loading audit entries…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="table-wrap">
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Action</th><th>Summary</th><th>Actor</th><th>Reason</th><th>When</th></tr></thead>
            <tbody>
              {data?.data.map((row) => (
                <tr key={row.id}>
                  <td className="mono text-xs">{row.action}</td>
                  <td className="text-[13px]">{row.summary}<span className="block text-xs text-muted">{row.entity_type} {row.entity_id ?? ""}</span></td>
                  <td className="text-[13px]">{row.actor?.full_name ?? "System"}<span className="block text-xs capitalize text-muted">{row.actor?.role ?? ""}</span></td>
                  <td className="text-[13px]">{row.reason ?? "—"}</td>
                  <td className="text-[13px]">{formatDateTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
