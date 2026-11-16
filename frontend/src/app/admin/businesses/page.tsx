"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "@/components/ui";
import { apiGetList } from "@/lib/api";
import type { BusinessProfile } from "@/lib/types";

type Row = BusinessProfile & { owner: { full_name: string; email: string; status: string } | null; orders: number };

export default function AdminBusinessesPage() {
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-businesses", q],
    queryFn: () => apiGetList<Row>(`/admin/businesses?per_page=100${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });

  return (
    <div>
      <PageHeader eyebrow="Business accounts" title="Business profiles" description="Businesses are consumers with a company profile. Order counts are read from stored orders." />
      <input className="input mb-4 max-w-sm" placeholder="Search business name or category" value={q} onChange={(event) => setQ(event.target.value)} />
      {isLoading ? <p className="text-sm text-muted">Loading businesses…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-[#8c2f2f]">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.data.map((row) => (
          <article key={row.id} className="card card-pad">
            <div className="flex items-start justify-between gap-2"><h2 className="font-semibold">{row.business_name}</h2><span className={`chip ${row.verification_status === "verified" ? "chip-green" : "chip-amber"}`}>{row.verification_status ?? "unverified"}</span></div>
            <p className="mt-1 text-sm text-muted">{row.category ?? "Uncategorised"} · {row.area ?? "No area"}</p>
            <p className="mt-2 text-xs text-muted">{row.owner?.full_name} · {row.owner?.email}</p>
            <p className="mt-2 text-sm">{row.orders} orders</p>
          </article>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No business profiles match.</p> : null}
    </div>
  );
}
