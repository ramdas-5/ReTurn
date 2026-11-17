"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageHeader } from "@/components/ui";
import { StatusBadge } from "@/components/Status";
import { apiGetList } from "@/lib/api";
import { formatDateTime, formatKm } from "@/lib/format";
import type { BatchSummary } from "@/lib/types";

export default function AdminBatchesPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin-batches"], queryFn: () => apiGetList<BatchSummary>("/admin/batches?per_page=100") });
  return (
    <div>
      <PageHeader eyebrow="All batches" title="Platform route book" description="Read-only batch summaries; open a batch for its ordered stops and driver." />
      {isLoading ? <p className="text-sm text-muted">Loading batches…</p> : null}
      {error ? <p className="rounded-control bg-red-soft px-4 py-3 text-sm text-red-ink">{(error as Error).message}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {data?.data.map((batch) => (
          <Link key={batch.id} href={`/admin/batches/${batch.id}`} className="card card-pad hover:border-accent/50">
            <div className="flex items-start justify-between gap-2"><div><p className="font-bold">{batch.batch_number}</p><p className="text-sm text-muted">{batch.driver?.full_name ?? "Unassigned"} · {batch.order_count} orders</p></div><StatusBadge status={batch.status} /></div>
            <p className="mt-2 text-sm text-muted">{formatDateTime(batch.planned_start)} · {formatKm(batch.distance_km)} · {batch.distance_source}</p>
          </Link>
        ))}
      </div>
      {data && data.data.length === 0 ? <p className="text-sm text-muted">No batches have been created.</p> : null}
    </div>
  );
}
