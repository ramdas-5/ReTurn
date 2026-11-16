"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import { formatKm } from "@/lib/format";
import type { BatchSummary } from "@/lib/types";

export default function AdminRoutesPage() {
  const { data } = useQuery({ queryKey: ["admin-batches", "routes"], queryFn: () => apiGetList<BatchSummary>("/admin/batches?per_page=100") });
  const active = (data?.data ?? []).filter((batch) => ["assigned", "active"].includes(batch.status));
  return (
    <div>
      <PageHeader eyebrow="Route monitoring" title="Active shared routes" description="Open a batch for its stored stop order, geometry source and driver. This page never renders invented vehicle positions." actions={<Link href="/admin/operations" className="btn btn-secondary">Live duty board</Link>} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((batch) => (
          <Link key={batch.id} href={`/admin/batches/${batch.id}`} className="card card-pad hover:border-accent/50">
            <div className="flex items-center justify-between gap-2"><p className="font-semibold">{batch.batch_number}</p><StatusBadge status={batch.status} /></div>
            <p className="mt-2 text-sm text-muted">{batch.driver?.full_name ?? "Unassigned"}</p>
            <p className="mt-1 text-xs text-muted">{formatKm(batch.distance_km)} · {batch.distance_source} · {batch.completed_stops}/{batch.total_stops} stops</p>
          </Link>
        ))}
      </div>
      {active.length === 0 ? <p className="text-sm text-muted">No active or assigned batches.</p> : null}
    </div>
  );
}
