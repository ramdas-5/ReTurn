"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AccountStatusActions } from "@/components/AdminAccountActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { ApiUser } from "@/lib/types";

type Row = ApiUser & { assigned_orders: number; managed_batches: number };

export default function AdminManagersPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-managers"], queryFn: () => apiGetList<Row>("/admin/managers") });

  return (
    <div>
      <PageHeader eyebrow="Manager management" title="Operations managers" description="Managers are provisioned by administrators and scoped to service areas." actions={<Link href="/admin/accounts/new" className="btn btn-primary">Create manager</Link>} />
      {isLoading ? <p className="text-sm text-muted">Loading managers…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      <div className="table-wrap">
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Manager</th><th>Service areas</th><th>Orders approved</th><th>Batches</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {data?.data.map((row) => (
                <tr key={row.id}>
                  <td><p className="font-medium">{row.full_name}</p><p className="text-xs text-muted">{row.email} · {row.phone ?? "—"}</p></td>
                  <td className="text-sm">{row.manager_profile?.service_areas?.map((area: { name: string }) => area.name).join(", ") || "—"}</td>
                  <td>{row.assigned_orders}</td>
                  <td>{row.managed_batches}</td>
                  <td><span className={`chip ${row.status === "active" ? "chip-green" : "chip-amber"}`}>{row.status}</span></td>
                  <td><AccountStatusActions userId={row.id} status={row.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No managers.</p> : null}
    </div>
  );
}
