"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AccountStatusActions } from "@/components/AdminAccountActions";
import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ApiUser } from "@/lib/types";

export default function AdminConsumersPage() {
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-consumers", q],
    queryFn: () => apiGetList<ApiUser>(`/admin/consumers?per_page=100${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });

  return (
    <div>
      <PageHeader eyebrow="Consumer management" title="Consumer accounts" description="Every consumer registered through the public form. Business profiles are listed separately." />
      <input className="input mb-4 max-w-sm" placeholder="Search name, email or phone" value={q} onChange={(event) => setQ(event.target.value)} />
      {isLoading ? <p className="text-sm text-muted">Loading consumers…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="table-wrap">
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Consumer</th><th>Account</th><th>Status</th><th>Joined</th><th>Action</th></tr></thead>
            <tbody>
              {data?.data.map((user) => (
                <tr key={user.id}>
                  <td><p className="font-medium">{user.full_name}</p><p className="text-xs text-muted">{user.email} · {user.phone ?? "—"}</p></td>
                  <td className="text-[13px]">{user.consumer_profile?.account_type ?? "individual"}{user.business_profile ? ` · ${user.business_profile.business_name}` : ""}</td>
                  <td><span className={`chip ${user.status === "active" ? "chip-green" : "chip-amber"}`}>{user.status}</span></td>
                  <td className="text-[13px]">{formatDateTime(user.created_at)}</td>
                  <td><AccountStatusActions userId={user.id} status={user.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {data && data.data.length === 0 ? <p className="mt-3 text-sm text-muted">No consumers match.</p> : null}
    </div>
  );
}
